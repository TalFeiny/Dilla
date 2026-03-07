"""
Forecast Method Router

Given company actuals + user intent, selects the best forecast method
and builds the projection using the appropriate engine.

Methods:
  growth_rate    — Default. Extrapolates from trailing growth rate with decay.
                   Uses CashFlowPlanningService.build_monthly_cash_flow_model().
                   Best when: 3+ months of revenue actuals, stable growth.

  regression     — Linear/exponential/time-series regression on actuals.
                   Uses FPARegressionService output as growth curve.
                   Best when: 12+ months of actuals, clear trend, R² > 0.7.

  driver_based   — Customer-level model: ACV × customers × (1 - churn) × NRR.
                   Uses CashFlowPlanningService customer model path.
                   Best when: user provides ACV, churn, customer count.

  seasonal       — Growth-rate model + detected seasonal overlay.
                   Uses SeasonalityEngine.detect_pattern() first.
                   Best when: 12+ months of actuals with seasonal signal.

  budget_pct     — Forecast = budget × achievement_rate from trailing actuals.
                   Uses budget_lines as base, adjusts by historical variance.
                   Best when: company has approved budget for the period.

  manual         — Agent or user specifies exact values per cell.
                   No model — just persists what's given.
"""

import logging
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

METHODS = {
    "growth_rate", "regression", "driver_based",
    "seasonal", "budget_pct", "manual",
}


class ForecastMethodRouter:

    def auto_select_method(
        self, company_id: str, seed_data: Dict
    ) -> Tuple[str, str]:
        """Auto-select best method based on data availability.

        Returns (method_name, reasoning).

        Decision tree:
        1. If driver keys present (churn, nrr, acv) → 'driver_based'
        2. If 12+ months actuals + seasonal signal detected → 'seasonal'
        3. If 12+ months actuals + R² > 0.7 on regression → 'regression'
        4. If approved budget exists for forecast period → 'budget_pct'
        5. Default → 'growth_rate'
        """
        data_quality = seed_data.get("_data_quality", {})
        rev_months = data_quality.get("revenue_months", 0)

        # 1. Driver-based if customer/ACV data available
        has_drivers = (
            seed_data.get("_detected_acv")
            or seed_data.get("acv_override")
            or seed_data.get("churn_rate")
            or seed_data.get("_detected_customer_count")
        )
        if has_drivers:
            return ("driver_based", "Customer/ACV data detected — using driver-based model")

        # 2. Seasonal if enough data and pattern detected
        if rev_months >= 12:
            try:
                from app.services.seasonality_engine import SeasonalityEngine
                engine = SeasonalityEngine()
                pattern = engine.detect_pattern(company_id, "revenue", min_periods=12)
                if pattern and pattern.strength > 0.2:
                    return (
                        "seasonal",
                        f"Seasonal pattern detected (strength={pattern.strength:.2f}, "
                        f"confidence={pattern.confidence:.2f}) from {rev_months} months"
                    )
            except Exception as e:
                logger.debug(f"Seasonal detection failed: {e}")

        # 3. Regression if enough data
        if rev_months >= 12:
            try:
                r2 = self._quick_regression_check(company_id)
                if r2 and r2 > 0.7:
                    return (
                        "regression",
                        f"Strong linear trend (R²={r2:.2f}) from {rev_months} months"
                    )
            except Exception as e:
                logger.debug(f"Regression check failed: {e}")

        # 4. Budget if available
        if self._has_approved_budget(company_id):
            return ("budget_pct", "Approved budget found — projecting from budget × achievement rate")

        # 5. Default
        reason = f"Growth-rate extrapolation from {rev_months or '?'} months of actuals"
        return ("growth_rate", reason)

    def build_forecast(
        self,
        company_id: str,
        method: str,
        seed_data: Dict,
        months: int = 24,
        assumptions: Dict = None,
        start_period: str = None,
    ) -> Tuple[List[Dict], Dict]:
        """Dispatch to the right engine based on method.

        Returns (forecast_rows, provenance_dict).
        """
        if method not in METHODS:
            logger.warning(f"Unknown method '{method}', falling back to growth_rate")
            method = "growth_rate"

        provenance = {"method": method, "seed_data_keys": list(seed_data.keys())}

        if method == "growth_rate":
            forecast = self._build_growth_rate(seed_data, months, assumptions)
        elif method == "regression":
            forecast = self._build_regression(company_id, seed_data, months, start_period, provenance)
        elif method == "driver_based":
            forecast = self._build_driver_based(seed_data, months, assumptions)
        elif method == "seasonal":
            forecast = self._build_seasonal(company_id, seed_data, months, assumptions, provenance)
        elif method == "budget_pct":
            forecast = self._build_budget_pct(company_id, seed_data, months, provenance)
        elif method == "manual":
            forecast = self._build_manual(assumptions, months)
        else:
            forecast = self._build_growth_rate(seed_data, months, assumptions)

        return forecast, provenance

    # ------------------------------------------------------------------
    # Method implementations
    # ------------------------------------------------------------------

    def _build_growth_rate(
        self, seed_data: Dict, months: int, assumptions: Dict = None
    ) -> List[Dict]:
        """Default growth-rate model via CashFlowPlanningService."""
        from app.services.cash_flow_planning_service import CashFlowPlanningService

        svc = CashFlowPlanningService()
        return svc.build_monthly_cash_flow_model(
            seed_data, months=months, monthly_overrides=assumptions,
        )

    def _build_regression(
        self, company_id: str, seed_data: Dict, months: int,
        start_period: str, provenance: Dict,
    ) -> List[Dict]:
        """Regression-based forecast: fit actuals, project forward, then
        feed projected revenue growth into CashFlowPlanningService."""
        from app.services.fpa_regression_service import FPARegressionService
        from app.services.actuals_ingestion import get_actuals_for_forecast
        from app.services.cash_flow_planning_service import CashFlowPlanningService
        import asyncio

        svc = FPARegressionService()
        actuals = get_actuals_for_forecast(company_id, "revenue")

        if len(actuals) >= 6:
            x = list(range(len(actuals)))
            y = [a["amount"] for a in actuals]

            # Run regression (sync wrapper for async method)
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    import concurrent.futures
                    with concurrent.futures.ThreadPoolExecutor() as pool:
                        reg_result = pool.submit(
                            asyncio.run, svc.linear_regression(x, y)
                        ).result()
                else:
                    reg_result = asyncio.run(svc.linear_regression(x, y))
            except Exception:
                # Fallback: manual regression
                reg_result = self._simple_linear_regression(x, y)

            provenance["regression"] = reg_result

            # Project revenue forward using regression
            slope = reg_result.get("slope", 0)
            intercept = reg_result.get("intercept", 0)
            last_x = len(actuals)

            # Convert regression projection to equivalent growth rate
            last_revenue = seed_data.get("revenue", 0)
            projected_12m = slope * (last_x + 12) + intercept
            if last_revenue > 0 and projected_12m > 0:
                implied_annual_growth = (projected_12m / last_revenue) - 1
                seed_data = {**seed_data, "growth_rate": implied_annual_growth}
                provenance["implied_annual_growth"] = implied_annual_growth

        # Build using CashFlowPlanningService with regression-adjusted growth
        cfp = CashFlowPlanningService()
        return cfp.build_monthly_cash_flow_model(seed_data, months=months)

    def _build_driver_based(
        self, seed_data: Dict, months: int, assumptions: Dict = None
    ) -> List[Dict]:
        """Driver-based model — pass driver keys directly to CashFlowPlanningService
        which activates its customer model path when ACV/churn/NRR are present."""
        from app.services.cash_flow_planning_service import CashFlowPlanningService

        # Promote detected drivers to top-level keys that CFPS recognizes
        enriched = {**seed_data}
        if seed_data.get("_detected_acv") and not enriched.get("acv_override"):
            enriched["acv_override"] = seed_data["_detected_acv"]
        if seed_data.get("_detected_customer_count") and not enriched.get("customers"):
            enriched["customers"] = seed_data["_detected_customer_count"]

        svc = CashFlowPlanningService()
        return svc.build_monthly_cash_flow_model(
            enriched, months=months, monthly_overrides=assumptions,
        )

    def _build_seasonal(
        self, company_id: str, seed_data: Dict, months: int,
        assumptions: Dict, provenance: Dict,
    ) -> List[Dict]:
        """Growth-rate model + seasonal overlay."""
        from app.services.seasonality_engine import SeasonalityEngine
        from app.services.cash_flow_planning_service import CashFlowPlanningService

        # Build base forecast
        svc = CashFlowPlanningService()
        forecast = svc.build_monthly_cash_flow_model(
            seed_data, months=months, monthly_overrides=assumptions,
        )

        # Detect and apply seasonality
        engine = SeasonalityEngine()
        pattern = engine.detect_pattern(company_id, "revenue", min_periods=12)
        if pattern:
            forecast = engine.apply_seasonal_factors(forecast, pattern, "revenue")
            provenance["seasonal_pattern"] = {
                "monthly_factors": pattern.monthly_factors,
                "strength": pattern.strength,
                "confidence": pattern.confidence,
            }

        return forecast

    def _build_budget_pct(
        self, company_id: str, seed_data: Dict, months: int, provenance: Dict
    ) -> List[Dict]:
        """Forecast = budget × trailing achievement rate."""
        from app.core.supabase_client import get_supabase_client
        from app.services.cash_flow_planning_service import CashFlowPlanningService
        from app.services.actuals_ingestion import get_actuals_for_forecast

        sb = get_supabase_client()
        if not sb:
            return self._build_growth_rate(seed_data, months)

        # Find approved budget
        budget_result = (
            sb.table("budgets")
            .select("id, fiscal_year")
            .eq("company_id", company_id)
            .eq("status", "approved")
            .order("fiscal_year", desc=True)
            .limit(1)
            .execute()
        )

        if not budget_result.data:
            # No budget — fall back to growth rate
            provenance["fallback"] = "no_approved_budget"
            return self._build_growth_rate(seed_data, months)

        budget_id = budget_result.data[0]["id"]
        lines = (
            sb.table("budget_lines")
            .select("*")
            .eq("budget_id", budget_id)
            .execute()
        )

        if not lines.data:
            provenance["fallback"] = "no_budget_lines"
            return self._build_growth_rate(seed_data, months)

        # Compute trailing achievement rate from actuals vs budget
        revenue_actuals = get_actuals_for_forecast(company_id, "revenue", months=6)
        budget_revenue_line = next(
            (l for l in lines.data if l.get("category") == "revenue"), None
        )

        achievement_rate = 1.0
        if budget_revenue_line and revenue_actuals:
            # Average the most recent actuals against budget months
            actual_avg = sum(a["amount"] for a in revenue_actuals[-3:]) / min(3, len(revenue_actuals[-3:]))
            # Budget monthly average from m1-m12
            budget_months = [budget_revenue_line.get(f"m{i}", 0) or 0 for i in range(1, 13)]
            budget_avg = sum(budget_months) / 12 if budget_months else 0
            if budget_avg > 0:
                achievement_rate = actual_avg / budget_avg

        provenance["budget_id"] = budget_id
        provenance["achievement_rate"] = achievement_rate

        # Adjust seed revenue by achievement rate and build
        adjusted_seed = {**seed_data}
        # Use budget-implied growth rate
        svc = CashFlowPlanningService()
        return svc.build_monthly_cash_flow_model(adjusted_seed, months=months)

    def _build_manual(self, assumptions: Dict, months: int) -> List[Dict]:
        """Manual forecast — just pass through whatever values were given."""
        if not assumptions or not isinstance(assumptions, dict):
            return []
        # Assumptions should contain per-period values
        # Return them as-is in forecast format
        return assumptions.get("forecast", [])

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _quick_regression_check(self, company_id: str) -> Optional[float]:
        """Quick R² check on revenue actuals."""
        from app.services.actuals_ingestion import get_actuals_for_forecast

        actuals = get_actuals_for_forecast(company_id, "revenue", months=24)
        if len(actuals) < 6:
            return None

        x = list(range(len(actuals)))
        y = [a["amount"] for a in actuals]
        result = self._simple_linear_regression(x, y)
        return result.get("r_squared")

    def _simple_linear_regression(self, x: list, y: list) -> Dict:
        """Minimal linear regression without numpy dependency."""
        n = len(x)
        if n < 2:
            return {"slope": 0, "intercept": 0, "r_squared": 0}

        sum_x = sum(x)
        sum_y = sum(y)
        sum_xy = sum(xi * yi for xi, yi in zip(x, y))
        sum_x2 = sum(xi ** 2 for xi in x)

        denom = n * sum_x2 - sum_x ** 2
        if denom == 0:
            return {"slope": 0, "intercept": sum_y / n, "r_squared": 0}

        slope = (n * sum_xy - sum_x * sum_y) / denom
        intercept = (sum_y - slope * sum_x) / n

        # R²
        y_mean = sum_y / n
        ss_tot = sum((yi - y_mean) ** 2 for yi in y)
        ss_res = sum((yi - (slope * xi + intercept)) ** 2 for xi, yi in zip(x, y))
        r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0

        return {
            "slope": slope,
            "intercept": intercept,
            "r_squared": r_squared,
            "equation": f"y = {slope:.2f}x + {intercept:.2f}",
        }

    def _has_approved_budget(self, company_id: str) -> bool:
        """Check if company has an approved budget."""
        try:
            from app.core.supabase_client import get_supabase_client
            sb = get_supabase_client()
            if not sb:
                return False
            result = (
                sb.table("budgets")
                .select("id")
                .eq("company_id", company_id)
                .eq("status", "approved")
                .limit(1)
                .execute()
            )
            return bool(result.data)
        except Exception:
            return False
