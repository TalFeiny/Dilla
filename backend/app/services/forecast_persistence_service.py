"""Forecast Persistence Service — save, load, version, and compare forecasts."""

import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# Map from CashFlowPlanningService output keys to fpa_forecast_lines categories
FORECAST_KEY_TO_CATEGORY = {
    "revenue": "revenue",
    "cogs": "cogs",
    "gross_profit": "gross_profit",
    "rd_spend": "opex_rd",
    "sm_spend": "opex_sm",
    "ga_spend": "opex_ga",
    "total_opex": "opex_total",
    "ebitda": "ebitda",
    "net_income": "net_income",
    "free_cash_flow": "free_cash_flow",
    "cash_balance": "cash_balance",
    "headcount": "headcount",
    "runway_months": "runway_months",
    "capex": "capex",
    "debt_service": "debt_service",
}


class ForecastPersistenceService:
    """Save, load, version, and compare forecasts."""

    def __init__(self):
        from app.core.supabase_client import get_supabase_client
        self._sb = get_supabase_client()

    # ------------------------------------------------------------------
    # Save
    # ------------------------------------------------------------------

    def save_forecast(
        self,
        company_id: str,
        forecast: List[Dict],
        method: str,
        seed_snapshot: Dict,
        assumptions: Dict = None,
        name: str = None,
        activate: bool = False,
        explanation: str = None,
        created_by: str = "agent",
        fund_id: str = None,
    ) -> Dict:
        """Persist a forecast to fpa_forecasts + fpa_forecast_lines.

        If activate=True, deactivates any existing active forecast first.
        Returns the saved forecast header with id.
        """
        if not self._sb:
            return {"error": "Supabase client not available"}

        # Determine start period from first forecast month
        start_period = ""
        if forecast:
            first_period = forecast[0].get("period", "")
            start_period = first_period[:7] if first_period else ""

        # Auto-generate name if not provided
        if not name:
            method_label = method.replace("_", " ").title()
            name = f"{method_label} Forecast — {start_period}"

        # Deactivate existing active forecast if activating this one
        if activate:
            self._deactivate_all(company_id)

        # Insert forecast header
        header = {
            "company_id": company_id,
            "fund_id": fund_id,
            "name": name,
            "method": method,
            "basis": self._infer_basis(method),
            "seed_snapshot": json.loads(json.dumps(seed_snapshot, default=str)),
            "assumptions": json.loads(json.dumps(assumptions or {}, default=str)),
            "status": "active" if activate else "draft",
            "is_active": activate,
            "horizon_months": len(forecast),
            "start_period": start_period,
            "created_by": created_by,
            "explanation": explanation,
        }

        result = self._sb.table("fpa_forecasts").insert(header).execute()
        if not result.data:
            return {"error": "Failed to insert forecast header"}

        forecast_id = result.data[0]["id"]

        # Insert forecast lines
        lines = self._forecast_to_lines(forecast_id, forecast)
        if lines:
            # Batch insert in chunks of 500
            for i in range(0, len(lines), 500):
                chunk = lines[i:i + 500]
                self._sb.table("fpa_forecast_lines").insert(chunk).execute()

        # Audit log
        self._log_audit(company_id, forecast_id, "created", {
            "method": method,
            "months": len(forecast),
            "lines": len(lines),
            "activated": activate,
        })

        saved = result.data[0]
        saved["line_count"] = len(lines)
        return saved

    # ------------------------------------------------------------------
    # Load
    # ------------------------------------------------------------------

    def load_forecast(self, forecast_id: str) -> Optional[Dict]:
        """Load a forecast with all its lines."""
        if not self._sb:
            return None

        header = (
            self._sb.table("fpa_forecasts")
            .select("*")
            .eq("id", forecast_id)
            .execute()
        )
        if not header.data:
            return None

        lines = (
            self._sb.table("fpa_forecast_lines")
            .select("*")
            .eq("forecast_id", forecast_id)
            .order("period")
            .execute()
        )

        result = header.data[0]
        result["lines"] = lines.data or []
        return result

    def get_active_forecast(self, company_id: str) -> Optional[Dict]:
        """Get the currently active forecast for a company."""
        if not self._sb:
            return None

        result = (
            self._sb.table("fpa_forecasts")
            .select("*")
            .eq("company_id", company_id)
            .eq("is_active", True)
            .limit(1)
            .execute()
        )
        if not result.data:
            return None
        return result.data[0]

    def list_forecasts(self, company_id: str) -> List[Dict]:
        """List all forecasts for a company, most recent first."""
        if not self._sb:
            return []

        result = (
            self._sb.table("fpa_forecasts")
            .select("id, name, method, basis, status, is_active, horizon_months, start_period, created_by, created_at, explanation")
            .eq("company_id", company_id)
            .order("created_at", desc=True)
            .limit(50)
            .execute()
        )
        return result.data or []

    # ------------------------------------------------------------------
    # Activate / Archive
    # ------------------------------------------------------------------

    def activate_forecast(self, forecast_id: str) -> Dict:
        """Set a forecast as the active one (deactivates others)."""
        if not self._sb:
            return {"error": "Supabase client not available"}

        # Get the forecast to find company_id
        header = (
            self._sb.table("fpa_forecasts")
            .select("id, company_id, name")
            .eq("id", forecast_id)
            .execute()
        )
        if not header.data:
            return {"error": f"Forecast {forecast_id} not found"}

        company_id = header.data[0]["company_id"]

        # Deactivate all, then activate this one
        self._deactivate_all(company_id)

        self._sb.table("fpa_forecasts").update({
            "is_active": True,
            "status": "active",
            "updated_at": datetime.utcnow().isoformat(),
        }).eq("id", forecast_id).execute()

        self._log_audit(company_id, forecast_id, "activated", {})
        return {"success": True, "forecast_id": forecast_id}

    # ------------------------------------------------------------------
    # Compare
    # ------------------------------------------------------------------

    def compare_forecasts(self, forecast_id_a: str, forecast_id_b: str) -> Dict:
        """Side-by-side comparison with deltas per period per category."""
        a = self.load_forecast(forecast_id_a)
        b = self.load_forecast(forecast_id_b)

        if not a or not b:
            return {"error": "One or both forecasts not found"}

        # Index lines by (period, category)
        def index_lines(lines):
            idx = {}
            for line in lines:
                key = (line["period"], line["category"])
                idx[key] = line["amount"]
            return idx

        idx_a = index_lines(a.get("lines", []))
        idx_b = index_lines(b.get("lines", []))

        all_keys = sorted(set(idx_a.keys()) | set(idx_b.keys()))

        deltas = []
        for period, category in all_keys:
            val_a = idx_a.get((period, category))
            val_b = idx_b.get((period, category))
            delta = None
            delta_pct = None
            if val_a is not None and val_b is not None:
                delta = val_b - val_a
                if val_a != 0:
                    delta_pct = delta / abs(val_a)

            deltas.append({
                "period": period,
                "category": category,
                "forecast_a": val_a,
                "forecast_b": val_b,
                "delta": delta,
                "delta_pct": delta_pct,
            })

        return {
            "forecast_a": {"id": a["id"], "name": a["name"], "method": a["method"]},
            "forecast_b": {"id": b["id"], "name": b["name"], "method": b["method"]},
            "deltas": deltas,
            "summary": self._summarize_deltas(deltas),
        }

    # ------------------------------------------------------------------
    # Write to actuals (grid apply)
    # ------------------------------------------------------------------

    def write_forecast_to_actuals(
        self, forecast_id: str, source: str = "forecast_applied"
    ) -> int:
        """Write forecast lines into fpa_actuals with source tag.

        This is how a forecast becomes 'real' in the grid.
        Returns row count.
        """
        if not self._sb:
            return 0

        forecast = self.load_forecast(forecast_id)
        if not forecast:
            return 0

        company_id = forecast["company_id"]
        fund_id = forecast.get("fund_id")

        rows = []
        for line in forecast.get("lines", []):
            # Skip computed/derived metrics that shouldn't be in actuals
            if line["category"] in ("runway_months", "gross_profit", "free_cash_flow"):
                continue
            rows.append({
                "company_id": company_id,
                "fund_id": fund_id,
                "period": line["period"],
                "category": line["category"],
                "subcategory": line.get("subcategory", ""),
                "hierarchy_path": line.get("hierarchy_path", line["category"]),
                "amount": line["amount"],
                "source": source,
            })

        if not rows:
            return 0

        # Batch upsert
        for i in range(0, len(rows), 500):
            chunk = rows[i:i + 500]
            self._sb.table("fpa_actuals").upsert(
                chunk,
                on_conflict="company_id,period,category,subcategory,hierarchy_path",
            ).execute()

        self._log_audit(company_id, forecast_id, "applied_to_grid", {"rows": len(rows)})
        return len(rows)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _deactivate_all(self, company_id: str):
        """Deactivate all active forecasts for a company."""
        self._sb.table("fpa_forecasts").update({
            "is_active": False,
            "status": "archived",
            "updated_at": datetime.utcnow().isoformat(),
        }).eq("company_id", company_id).eq("is_active", True).execute()

    def _forecast_to_lines(
        self, forecast_id: str, forecast: List[Dict]
    ) -> List[Dict]:
        """Convert CashFlowPlanningService output to fpa_forecast_lines rows."""
        lines = []
        for month in forecast:
            period = month.get("period", "")
            if not period:
                continue
            # Normalize to YYYY-MM-01
            if len(period) == 7:
                period = f"{period}-01"

            for fc_key, category in FORECAST_KEY_TO_CATEGORY.items():
                value = month.get(fc_key)
                if value is None:
                    continue
                lines.append({
                    "forecast_id": forecast_id,
                    "period": period,
                    "category": category,
                    "subcategory": "",
                    "hierarchy_path": category,
                    "amount": float(value),
                })
        return lines

    def _infer_basis(self, method: str) -> str:
        """Infer the basis from the method."""
        mapping = {
            "growth_rate": "actuals",
            "regression": "actuals",
            "driver_based": "actuals",
            "seasonal": "actuals",
            "budget_pct": "budget",
            "manual": "manual",
            "scenario_promoted": "scenario",
        }
        return mapping.get(method, "actuals")

    def _summarize_deltas(self, deltas: List[Dict]) -> Dict:
        """Summarize comparison deltas."""
        revenue_deltas = [d for d in deltas if d["category"] == "revenue" and d["delta"] is not None]
        ebitda_deltas = [d for d in deltas if d["category"] == "ebitda" and d["delta"] is not None]

        summary = {}
        if revenue_deltas:
            avg_delta = sum(d["delta"] for d in revenue_deltas) / len(revenue_deltas)
            summary["avg_revenue_delta"] = round(avg_delta, 2)
        if ebitda_deltas:
            avg_delta = sum(d["delta"] for d in ebitda_deltas) / len(ebitda_deltas)
            summary["avg_ebitda_delta"] = round(avg_delta, 2)

        return summary

    def _log_audit(
        self, company_id: str, forecast_id: str, action: str, details: Dict
    ):
        """Write to fpa_forecast_audit."""
        try:
            self._sb.table("fpa_forecast_audit").insert({
                "company_id": company_id,
                "forecast_id": forecast_id,
                "action": action,
                "details": json.loads(json.dumps(details, default=str)),
            }).execute()
        except Exception as e:
            logger.warning(f"Audit log failed: {e}")
