"""
Analysis Persistence Service — save analysis results to branches + grid.

Follows the rolling forecast pattern (forecast_persistence_service.py):
  1. Service computes results (MC, valuation, sensitivity, etc.)
  2. This service ALWAYS persists them:
     - Creates a scenario branch with the assumptions used
     - If the analysis produced time-series output (MC p50 trajectory,
       DCF projections), saves as forecast lines
     - Writes to grid (fpa_actuals) if no actuals exist yet,
       otherwise keeps results on the branch
     - Returns branch_id + metadata for frontend

Every analysis service calls persist_analysis_result() after computing.
This is NOT optional — every analysis creates a branch.
"""

import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# Map from MC / analysis output keys to fpa_actuals categories
_TRAJECTORY_KEY_TO_CATEGORY = {
    "revenue": "revenue",
    "cogs": "cogs",
    "ebitda": "ebitda",
    "cash_balance": "cash_balance",
    "total_opex": "opex_total",
    "free_cash_flow": "free_cash_flow",
    "runway_months": "runway_months",
    "headcount": "headcount",
    "net_income": "net_income",
    "capex": "capex",
    "rd_spend": "opex_rd",
    "sm_spend": "opex_sm",
    "ga_spend": "opex_ga",
}

# Categories that are derived / computed — skip when writing to grid
_SKIP_GRID_CATEGORIES = {"runway_months", "gross_profit"}


class AnalysisPersistenceService:
    """Save analysis results to scenario branches and the grid.

    Always creates a branch.  If the grid has no actuals for this company,
    writes the trajectory directly to fpa_actuals.  If actuals already
    exist, the trajectory lives on the branch (as a forecast) so it
    doesn't clobber real data.
    """

    def __init__(self):
        from app.core.supabase_client import get_supabase_client

        self._sb = get_supabase_client()

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    def persist_analysis_result(
        self,
        company_id: str,
        analysis_type: str,
        assumptions: Dict[str, Any],
        *,
        branch_name: Optional[str] = None,
        parent_branch_id: Optional[str] = None,
        trajectory: Optional[List[Dict[str, Any]]] = None,
        periods: Optional[List[str]] = None,
        summary: Optional[Dict[str, Any]] = None,
        probability: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Persist an analysis result: branch + forecast + grid (if empty).

        Parameters
        ----------
        company_id : str
            Company UUID.
        analysis_type : str
            "monte_carlo", "sensitivity", "valuation_dcf", etc.
        assumptions : dict
            The assumptions/parameters used.  Stored in branch.assumptions.
        branch_name : str, optional
            Human-readable branch name.  Auto-generated if None.
        parent_branch_id : str, optional
            Fork from this branch.  None = fork from base.
        trajectory : list[dict], optional
            Time-series rows: [{"period": "2025-01", "revenue": 1e6, ...}, ...]
            If provided, saved as forecast lines.  Written to grid if no
            actuals exist yet.
        periods : list[str], optional
            Period labels (fallback if rows lack "period" key).
        summary : dict, optional
            High-level result summary (fair_value, VaR, etc.) stored on branch.
        probability : float, optional
            Branch probability for expected-value weighting (0-1).

        Returns
        -------
        dict with: branch_id, forecast_id, rows_written, wrote_to_grid,
        branch_name.
        """
        if not self._sb:
            return {"error": "Supabase not available"}

        result: Dict[str, Any] = {"wrote_to_grid": False, "rows_written": 0}

        # 1. Always create scenario branch
        branch_id = self._create_branch(
            company_id=company_id,
            analysis_type=analysis_type,
            assumptions=assumptions,
            branch_name=branch_name,
            parent_branch_id=parent_branch_id,
            summary=summary,
            probability=probability,
        )
        result["branch_id"] = branch_id
        result["branch_name"] = branch_name or self._auto_name(analysis_type)

        # 2. If trajectory data, save as forecast + decide grid vs branch
        if trajectory and branch_id:
            forecast_id = self._save_trajectory_as_forecast(
                company_id=company_id,
                branch_id=branch_id,
                analysis_type=analysis_type,
                trajectory=trajectory,
                periods=periods,
                assumptions=assumptions,
            )
            result["forecast_id"] = forecast_id

            # 3. Write to grid if no actuals exist, otherwise stays on branch
            grid_empty = self._grid_is_empty(company_id)
            if grid_empty:
                rows_written = self._write_to_grid(
                    company_id=company_id,
                    trajectory=trajectory,
                    periods=periods,
                    source=f"{analysis_type}_applied",
                )
                result["rows_written"] = rows_written
                result["wrote_to_grid"] = True
                logger.info(
                    "[ANALYSIS_PERSIST] grid empty — wrote %d rows for %s",
                    rows_written, company_id,
                )
            else:
                logger.info(
                    "[ANALYSIS_PERSIST] grid has actuals — results on branch %s",
                    branch_id,
                )

        return result

    # ------------------------------------------------------------------
    # Monte Carlo convenience
    # ------------------------------------------------------------------

    def persist_monte_carlo(
        self,
        company_id: str,
        mc_result: Dict[str, Any],
        *,
        branch_name: Optional[str] = None,
        parent_branch_id: Optional[str] = None,
        percentile: str = "p50",
    ) -> Dict[str, Any]:
        """Persist Monte Carlo result using the median (p50) trajectory.

        Extracts the selected percentile trajectory from
        mc_result["trajectory_percentiles"] and saves it as forecast rows.
        Always creates a branch.  Writes to grid if grid is empty.
        """
        trajectory_pcts = mc_result.get("trajectory_percentiles", {})
        periods = mc_result.get("periods", [])

        # Build trajectory rows from the selected percentile
        trajectory = self._percentile_to_rows(trajectory_pcts, periods, percentile)

        summary = {
            "iterations": mc_result.get("iterations"),
            "months": mc_result.get("months"),
            "percentile_used": percentile,
            "var_cash_12m": mc_result.get("var_cash_12m"),
            "break_even_probability": mc_result.get("break_even_probability"),
            "runway_distribution": mc_result.get("runway_distribution"),
            "final_distribution": mc_result.get("final_distribution"),
        }

        assumptions = {
            "analysis_type": "monte_carlo",
            "percentile": percentile,
            "iterations": mc_result.get("iterations"),
            "driver_sensitivity": mc_result.get("driver_sensitivity", []),
        }

        return self.persist_analysis_result(
            company_id=company_id,
            analysis_type="monte_carlo",
            assumptions=assumptions,
            branch_name=branch_name or f"Monte Carlo {percentile.upper()}",
            parent_branch_id=parent_branch_id,
            trajectory=trajectory,
            periods=periods,
            summary=summary,
        )

    # ------------------------------------------------------------------
    # Sensitivity convenience
    # ------------------------------------------------------------------

    def persist_sensitivity(
        self,
        company_id: str,
        sensitivity_result: Dict[str, Any],
        base_inputs: Dict[str, Any],
        *,
        branch_name: Optional[str] = None,
        parent_branch_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Persist sensitivity analysis as a branch (no trajectory).

        Sensitivity produces tornado charts, not time-series — so no grid
        write, but the assumptions and rankings are saved on the branch.
        """
        summary = {
            "tornado_chart_data": sensitivity_result.get("tornado_chart_data"),
            "sensitivity_rankings": sensitivity_result.get("sensitivity_rankings"),
            "base_output": sensitivity_result.get("base_output"),
        }

        assumptions = {
            "analysis_type": "sensitivity",
            "base_inputs": base_inputs,
        }

        return self.persist_analysis_result(
            company_id=company_id,
            analysis_type="sensitivity",
            assumptions=assumptions,
            branch_name=branch_name or "Sensitivity Analysis",
            parent_branch_id=parent_branch_id,
            summary=summary,
        )

    # ------------------------------------------------------------------
    # Valuation convenience
    # ------------------------------------------------------------------

    def persist_valuation(
        self,
        company_id: str,
        valuation_result: Dict[str, Any],
        method: str,
        assumptions: Dict[str, Any],
        *,
        branch_name: Optional[str] = None,
        parent_branch_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Persist a valuation result as a scenario branch.

        Valuations are point-in-time — no time-series to grid-write.
        The result (fair_value, scenarios) is stored as summary on branch.
        """
        summary = {
            "method": method,
            "fair_value": valuation_result.get("fair_value")
                or valuation_result.get("enterprise_value"),
            "equity_value": valuation_result.get("equity_value"),
            "scenarios": valuation_result.get("scenarios"),
            "confidence": valuation_result.get("confidence"),
        }

        valuation_assumptions = {
            "analysis_type": f"valuation_{method}",
            **assumptions,
        }

        method_label = method.upper().replace("_", " ")
        return self.persist_analysis_result(
            company_id=company_id,
            analysis_type=f"valuation_{method}",
            assumptions=valuation_assumptions,
            branch_name=branch_name or f"Valuation — {method_label}",
            parent_branch_id=parent_branch_id,
            summary=summary,
        )

    # ------------------------------------------------------------------
    # Analytics convenience
    # ------------------------------------------------------------------

    def persist_analytics(
        self,
        company_id: str,
        analysis_type: str,
        analytics_result: Dict[str, Any],
        parameters: Dict[str, Any],
        *,
        branch_name: Optional[str] = None,
        parent_branch_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Persist advanced analytics result (WACC, health, scenario).

        Stores the full result as summary on a branch.
        """
        return self.persist_analysis_result(
            company_id=company_id,
            analysis_type=f"analytics_{analysis_type}",
            assumptions={"analysis_type": analysis_type, **parameters},
            branch_name=branch_name,
            parent_branch_id=parent_branch_id,
            summary=analytics_result,
        )

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _grid_is_empty(self, company_id: str) -> bool:
        """Check if fpa_actuals has any rows for this company."""
        try:
            result = (
                self._sb.table("fpa_actuals")
                .select("id", count="exact")
                .eq("company_id", company_id)
                .limit(1)
                .execute()
            )
            return (result.count or 0) == 0
        except Exception:
            return False

    def _create_branch(
        self,
        company_id: str,
        analysis_type: str,
        assumptions: Dict[str, Any],
        branch_name: Optional[str],
        parent_branch_id: Optional[str],
        summary: Optional[Dict[str, Any]],
        probability: Optional[float],
    ) -> Optional[str]:
        """Insert a row into scenario_branches."""
        try:
            name = branch_name or self._auto_name(analysis_type)
            row = {
                "company_id": company_id,
                "name": name,
                "parent_branch_id": parent_branch_id,
                "assumptions": json.dumps(
                    {**assumptions, "_analysis_summary": summary or {}},
                    default=str,
                ),
                "probability": probability,
                "source": analysis_type,
            }
            result = self._sb.table("scenario_branches").insert(row).execute()
            if result.data:
                branch_id = result.data[0]["id"]
                logger.info(
                    "[ANALYSIS_PERSIST] branch created: %s (%s) for %s",
                    name, branch_id, company_id,
                )
                return branch_id
        except Exception as e:
            logger.error("Failed to create analysis branch: %s", e, exc_info=True)
        return None

    def _save_trajectory_as_forecast(
        self,
        company_id: str,
        branch_id: str,
        analysis_type: str,
        trajectory: List[Dict[str, Any]],
        periods: Optional[List[str]],
        assumptions: Dict[str, Any],
    ) -> Optional[str]:
        """Save trajectory rows as fpa_forecasts + fpa_forecast_lines."""
        from app.services.forecast_persistence_service import ForecastPersistenceService

        fps = ForecastPersistenceService()
        try:
            forecast_rows = []
            for i, row in enumerate(trajectory):
                period = row.get("period") or (
                    periods[i] if periods and i < len(periods) else None
                )
                if not period:
                    continue
                forecast_row = {"period": period}
                for key, val in row.items():
                    if key == "period":
                        continue
                    if isinstance(val, (int, float)):
                        forecast_row[key] = val
                forecast_rows.append(forecast_row)

            if not forecast_rows:
                return None

            saved = fps.save_forecast(
                company_id=company_id,
                forecast=forecast_rows,
                method=analysis_type,
                seed_snapshot=assumptions,
                assumptions=assumptions,
                name=f"{analysis_type} forecast — {branch_id[:8]}",
                activate=False,
                created_by="analysis_engine",
            )
            forecast_id = saved.get("id")
            if forecast_id:
                logger.info(
                    "[ANALYSIS_PERSIST] forecast saved: %s (%d rows)",
                    forecast_id, len(forecast_rows),
                )
            return forecast_id
        except Exception as e:
            logger.error("Failed to save analysis forecast: %s", e, exc_info=True)
            return None

    def _write_to_grid(
        self,
        company_id: str,
        trajectory: List[Dict[str, Any]],
        periods: Optional[List[str]],
        source: str,
    ) -> int:
        """Upsert trajectory rows into fpa_actuals.

        Same pattern as ForecastPersistenceService.write_forecast_to_actuals:
        batch upsert in 500-row chunks.
        """
        rows = []
        for i, row in enumerate(trajectory):
            period = row.get("period") or (
                periods[i] if periods and i < len(periods) else None
            )
            if not period:
                continue
            if len(period) == 7:
                period = f"{period}-01"

            for key, val in row.items():
                if key == "period" or not isinstance(val, (int, float)):
                    continue
                category = _TRAJECTORY_KEY_TO_CATEGORY.get(key)
                if not category or category in _SKIP_GRID_CATEGORIES:
                    continue
                rows.append({
                    "company_id": company_id,
                    "period": period,
                    "category": category,
                    "subcategory": "",
                    "hierarchy_path": category,
                    "amount": float(val),
                    "source": source,
                })

        if not rows:
            return 0

        for i in range(0, len(rows), 500):
            chunk = rows[i : i + 500]
            self._sb.table("fpa_actuals").upsert(
                chunk,
                on_conflict="company_id,period,category,subcategory,hierarchy_path,source",
            ).execute()

        logger.info(
            "[ANALYSIS_PERSIST] grid write: %d rows, source=%s", len(rows), source
        )
        return len(rows)

    def _percentile_to_rows(
        self,
        trajectory_pcts: Dict[str, Dict[str, list]],
        periods: List[str],
        percentile: str,
    ) -> List[Dict[str, Any]]:
        """Convert MC trajectory_percentiles into [{period, revenue, ...}]."""
        if not periods:
            return []

        rows: List[Dict[str, Any]] = []
        for i, period in enumerate(periods):
            row: Dict[str, Any] = {"period": period}
            for metric, pct_bands in trajectory_pcts.items():
                values = pct_bands.get(percentile, [])
                if i < len(values):
                    row[metric] = round(values[i], 2)
            rows.append(row)
        return rows

    @staticmethod
    def _auto_name(analysis_type: str) -> str:
        """Generate a branch name from analysis type + timestamp."""
        label = analysis_type.replace("_", " ").title()
        ts = datetime.utcnow().strftime("%b %d %H:%M")
        return f"{label} — {ts}"
