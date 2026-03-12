"""
Rolling Forecast Service

Stitches actuals (left) + forecast (right) into a continuous 24-month
rolling view. This is what makes the P&L grid useful: actuals on the
left, forecast on the right, with a clear boundary.

The boundary moves forward each month as new actuals arrive.

Usage:
    svc = RollingForecastService()
    result = svc.build_rolling_view(company_id, window_months=24, granularity="monthly")

Returns:
    {
        "periods": ["2025-01", ..., "2026-12"],
        "boundary_index": 6,       # index where forecast starts
        "boundary_period": "2025-07",
        "rows": [
            {
                "period": "2025-01",
                "source": "actual",   # or "forecast"
                "revenue": 500000,
                "cogs": ...,
                ...full P&L row
            },
            ...
        ],
        "granularity": "monthly",
    }
"""

import logging
from datetime import date
from typing import Any, Dict, List, Optional, Literal

logger = logging.getLogger(__name__)


class RollingForecastService:

    def build_rolling_view(
        self,
        company_id: str,
        window_months: int = 24,
        granularity: Literal["monthly", "quarterly", "annual"] = "monthly",
    ) -> Dict[str, Any]:
        """
        Build a rolling actuals+forecast view.

        1. Pull actuals from fpa_actuals (most recent `window_months` worth)
        2. Generate forecast from the month after last actual to fill the window
        3. Tag each row with source="actual" or source="forecast"
        4. Aggregate to requested granularity
        """
        from app.services.actuals_ingestion import seed_forecast_from_actuals
        from app.services.cash_flow_planning_service import CashFlowPlanningService

        # --- 1. Pull actuals ---
        actuals_monthly = self._load_actuals_monthly(company_id)
        num_actuals = len(actuals_monthly)

        # --- 2. Determine forecast start ---
        if actuals_monthly:
            last_actual_period = actuals_monthly[-1]["period"]
            forecast_start = self._next_period(last_actual_period)
        else:
            today = date.today()
            forecast_start = f"{today.year}-{today.month:02d}"

        forecast_months_needed = max(0, window_months - num_actuals)

        # --- 3. Build forecast — prefer active saved forecast ---
        forecast_monthly: List[Dict[str, Any]] = []
        if forecast_months_needed > 0:
            # Try loading active saved forecast first
            saved_forecast = self._load_active_forecast(company_id, forecast_start, forecast_months_needed)
            if saved_forecast:
                forecast_monthly = saved_forecast
            else:
                # Fall back to computing forecast on the fly
                company_data = seed_forecast_from_actuals(company_id)
                if company_data.get("revenue", 0) > 0:
                    svc = CashFlowPlanningService()
                    forecast_monthly = svc.build_monthly_cash_flow_model(
                        company_data,
                        months=forecast_months_needed,
                        start_period=forecast_start,
                    )
            for row in forecast_monthly:
                row["source"] = "forecast"

        # Tag actuals
        for row in actuals_monthly:
            row["source"] = "actual"

        # --- 4. Stitch together ---
        # Trim actuals to fit within window (keep most recent)
        max_actuals = window_months - len(forecast_monthly)
        if len(actuals_monthly) > max_actuals:
            actuals_monthly = actuals_monthly[-max_actuals:]

        combined = actuals_monthly + forecast_monthly
        boundary_index = len(actuals_monthly)
        boundary_period = forecast_start if forecast_monthly else None

        # --- 5. Aggregate if needed ---
        if granularity != "monthly":
            combined, boundary_index, boundary_period = self._aggregate(
                combined, granularity
            )

        periods = [row.get("period", "") for row in combined]

        return {
            "company_id": company_id,
            "periods": periods,
            "boundary_index": boundary_index,
            "boundary_period": boundary_period,
            "rows": combined,
            "granularity": granularity,
            "actuals_count": sum(1 for r in combined if r.get("source") == "actual"),
            "forecast_count": sum(1 for r in combined if r.get("source") == "forecast"),
        }

    # ------------------------------------------------------------------
    # Load actuals into P&L-shaped monthly rows
    # ------------------------------------------------------------------

    def _load_active_forecast(
        self, company_id: str, start_period: str, months_needed: int
    ) -> Optional[List[Dict[str, Any]]]:
        """Load active saved forecast lines and reshape to P&L row format."""
        try:
            from app.services.forecast_persistence_service import ForecastPersistenceService

            fps = ForecastPersistenceService()
            active = fps.get_active_forecast(company_id)
            if not active:
                return None

            loaded = fps.load_forecast(active["id"])
            if not loaded or not loaded.get("lines"):
                return None

            # Group lines by period
            by_period: Dict[str, Dict[str, float]] = {}
            for line in loaded["lines"]:
                period = line["period"][:7]
                if period < start_period:
                    continue
                by_period.setdefault(period, {})[line["category"]] = float(line["amount"])

            # Convert to P&L row format matching CashFlowPlanningService output
            result = []
            for period in sorted(by_period.keys())[:months_needed]:
                vals = by_period[period]
                row = {"period": period}
                # Map category names to expected keys
                category_to_key = {
                    "revenue": "revenue",
                    "cogs": "cogs",
                    "gross_profit": "gross_profit",
                    "opex_rd": "rd_spend",
                    "opex_sm": "sm_spend",
                    "opex_ga": "ga_spend",
                    "opex_total": "total_opex",
                    "ebitda": "ebitda",
                    "net_income": "net_income",
                    "free_cash_flow": "free_cash_flow",
                    "cash_balance": "cash_balance",
                    "headcount": "headcount",
                    "runway_months": "runway_months",
                }
                for cat, key in category_to_key.items():
                    if cat in vals:
                        row[key] = vals[cat]

                # Compute derived fields if missing
                if "gross_profit" not in row and "revenue" in row and "cogs" in row:
                    row["gross_profit"] = row["revenue"] - row["cogs"]
                if "gross_margin" not in row and "revenue" in row and row["revenue"] > 0:
                    row["gross_margin"] = (row.get("gross_profit", 0)) / row["revenue"]

                result.append(row)

            return result if result else None
        except Exception as e:
            logger.debug(f"Failed to load active forecast for rolling view: {e}")
            return None

    def _load_actuals_monthly(self, company_id: str) -> List[Dict[str, Any]]:
        """
        Pull fpa_actuals and reshape into monthly P&L rows matching
        the CashFlowPlanningService output shape.
        """
        from app.core.supabase_client import get_supabase_client

        sb = get_supabase_client()
        if not sb:
            return []

        result = (
            sb.table("fpa_actuals")
            .select("period, category, subcategory, amount")
            .eq("company_id", company_id)
            .order("period")
            .execute()
        )

        # Group by period
        by_period: Dict[str, Dict[str, float]] = {}
        for row in result.data or []:
            period = row["period"][:7]  # "2025-01-01" → "2025-01"
            if period not in by_period:
                by_period[period] = {}
            cat = row["category"]
            amount = float(row["amount"])

            # Map to standard keys
            if cat == "revenue":
                by_period[period]["revenue"] = by_period[period].get("revenue", 0) + amount
            elif cat == "cogs":
                by_period[period]["cogs"] = amount
            elif cat in ("opex_total", "opex"):
                by_period[period]["total_opex"] = amount
            elif cat == "opex_rd":
                by_period[period]["rd_spend"] = amount
            elif cat == "opex_sm":
                by_period[period]["sm_spend"] = amount
            elif cat == "opex_ga":
                by_period[period]["ga_spend"] = amount
            elif cat == "ebitda":
                by_period[period]["ebitda"] = amount
            elif cat == "cash_balance":
                by_period[period]["cash_balance"] = amount
            elif cat == "burn_rate":
                by_period[period]["burn_rate"] = amount
            # Balance sheet categories
            elif cat == "bs_cash":
                by_period[period]["bs_cash"] = by_period[period].get("bs_cash", 0) + amount
            elif cat == "bs_receivables":
                by_period[period]["bs_receivables"] = by_period[period].get("bs_receivables", 0) + amount
            elif cat == "bs_payables":
                by_period[period]["bs_payables"] = by_period[period].get("bs_payables", 0) + amount
            elif cat == "bs_inventory":
                by_period[period]["bs_inventory"] = by_period[period].get("bs_inventory", 0) + amount
            elif cat == "bs_deferred_revenue":
                by_period[period]["bs_deferred_revenue"] = by_period[period].get("bs_deferred_revenue", 0) + amount
            elif cat == "bs_lt_debt":
                by_period[period]["bs_lt_debt"] = by_period[period].get("bs_lt_debt", 0) + amount
            elif cat == "bs_st_debt":
                by_period[period]["bs_st_debt"] = by_period[period].get("bs_st_debt", 0) + amount
            elif cat == "bs_ppe":
                by_period[period]["bs_ppe"] = by_period[period].get("bs_ppe", 0) + amount

        # Build rows in standard P&L shape
        rows: List[Dict[str, Any]] = []
        for period in sorted(by_period.keys()):
            vals = by_period[period]
            revenue = vals.get("revenue", 0)
            cogs = vals.get("cogs", 0)
            gross_profit = revenue - cogs
            total_opex = vals.get("total_opex", 0)
            rd = vals.get("rd_spend", 0)
            sm = vals.get("sm_spend", 0)
            ga = vals.get("ga_spend", 0)

            # If we have line-item opex but no total, sum them
            if total_opex == 0 and (rd or sm or ga):
                total_opex = rd + sm + ga

            ebitda = vals.get("ebitda", gross_profit - total_opex)

            # Balance sheet fields
            bs_cash = vals.get("bs_cash", 0)
            bs_receivables = vals.get("bs_receivables", 0)
            bs_payables = vals.get("bs_payables", 0)
            bs_inventory = vals.get("bs_inventory", 0)
            bs_deferred_revenue = vals.get("bs_deferred_revenue", 0)
            bs_lt_debt = vals.get("bs_lt_debt", 0)
            bs_st_debt = vals.get("bs_st_debt", 0)
            bs_ppe = vals.get("bs_ppe", 0)

            # Derived BS metrics
            working_capital = bs_receivables + bs_inventory - bs_payables - bs_deferred_revenue
            net_debt = bs_lt_debt + bs_st_debt - bs_cash

            rows.append({
                "period": period,
                "revenue": round(revenue, 2),
                "cogs": round(cogs, 2),
                "gross_profit": round(gross_profit, 2),
                "gross_margin": round(gross_profit / revenue, 4) if revenue else 0,
                "rd_spend": round(rd, 2),
                "sm_spend": round(sm, 2),
                "ga_spend": round(ga, 2),
                "total_opex": round(total_opex, 2),
                "ebitda": round(ebitda, 2),
                "ebitda_margin": round(ebitda / revenue, 4) if revenue else -1.0,
                "capex": 0,
                "free_cash_flow": round(ebitda, 2),  # no capex in actuals
                "cash_balance": round(vals.get("cash_balance", 0), 2),
                "runway_months": 0,
                # Balance sheet position
                "bs_cash": round(bs_cash, 2),
                "bs_receivables": round(bs_receivables, 2),
                "bs_payables": round(bs_payables, 2),
                "bs_inventory": round(bs_inventory, 2),
                "bs_deferred_revenue": round(bs_deferred_revenue, 2),
                "bs_lt_debt": round(bs_lt_debt, 2),
                "bs_st_debt": round(bs_st_debt, 2),
                "bs_ppe": round(bs_ppe, 2),
                "working_capital": round(working_capital, 2),
                "net_debt": round(net_debt, 2),
            })

        return rows

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _next_period(period: str) -> str:
        """Given 'YYYY-MM', return next month."""
        y, m = int(period[:4]), int(period[5:7])
        m += 1
        if m > 12:
            m = 1
            y += 1
        return f"{y}-{m:02d}"

    @staticmethod
    def _aggregate(
        rows: List[Dict[str, Any]],
        granularity: str,
    ) -> tuple:
        """Aggregate combined rows and recompute boundary."""
        from app.services.cash_flow_planning_service import CashFlowPlanningService

        if granularity == "quarterly":
            aggregated = CashFlowPlanningService._aggregate_to_quarterly(rows)
        else:
            aggregated = CashFlowPlanningService._aggregate_to_annual(rows)

        # Determine source for each aggregated period: if ANY month in the
        # bucket is forecast, the bucket is "mixed" or "forecast"
        from itertools import groupby

        def _group_key(m: Dict[str, Any]) -> str:
            period = m.get("period", "")
            if granularity == "quarterly" and len(period) >= 7:
                y, mo = int(period[:4]), int(period[5:7])
                q = (mo - 1) // 3 + 1
                return f"{y}-Q{q}"
            return period[:4] if len(period) >= 4 else "unknown"

        source_by_bucket: Dict[str, str] = {}
        for bk, group in groupby(rows, key=_group_key):
            sources = {m.get("source", "actual") for m in group}
            if "forecast" in sources and "actual" in sources:
                source_by_bucket[bk] = "mixed"
            elif "forecast" in sources:
                source_by_bucket[bk] = "forecast"
            else:
                source_by_bucket[bk] = "actual"

        boundary_index = 0
        boundary_period = None
        for i, row in enumerate(aggregated):
            p = row.get("period", "")
            row["source"] = source_by_bucket.get(p, "actual")
            if row["source"] in ("forecast", "mixed") and boundary_period is None:
                boundary_index = i
                boundary_period = p

        if boundary_period is None:
            boundary_index = len(aggregated)

        return aggregated, boundary_index, boundary_period
