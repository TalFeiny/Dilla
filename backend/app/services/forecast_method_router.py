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
    "growth_rate", "regression", "advanced_regression", "driver_based",
    "seasonal", "budget_pct", "manual", "model_construction", "liquidity",
    "monte_carlo",
}


class ForecastMethodRouter:

    def auto_select_method(
        self, company_id: str, seed_data: Dict, company_data=None
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
        if company_data is None:
            from app.services.company_data_pull import pull_company_data
            company_data = pull_company_data(company_id)

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
                pattern = engine.detect_pattern(company_id, "revenue", min_periods=12, company_data=company_data)
                if pattern and pattern.strength > 0.2:
                    return (
                        "seasonal",
                        f"Seasonal pattern detected (strength={pattern.strength:.2f}, "
                        f"confidence={pattern.confidence:.2f}) from {rev_months} months"
                    )
            except Exception as e:
                logger.debug(f"Seasonal detection failed: {e}")

        # 3. Advanced regression if enough data
        if rev_months >= 6:
            try:
                best_model = self._quick_advanced_regression_check(company_data)
                if best_model:
                    model_name = best_model.get("model_name", "unknown")
                    adj_r2 = best_model.get("adjusted_r_squared", 0)
                    if adj_r2 > 0.7:
                        return (
                            "advanced_regression",
                            f"Best fit: {model_name} (adj R²={adj_r2:.2f}) from {rev_months} months — "
                            f"{best_model.get('qualitative_assessment', '')}"
                        )
            except Exception as e:
                logger.debug(f"Advanced regression check failed: {e}")

        # 3b. Fallback to basic linear regression
        if rev_months >= 12:
            try:
                r2 = self._quick_regression_check(company_data)
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
        company_data=None,
    ) -> Tuple[List[Dict], Dict]:
        """Dispatch to the right engine based on method.

        Returns (forecast_rows, provenance_dict).
        """
        if company_data is None and company_id:
            from app.services.company_data_pull import pull_company_data
            company_data = pull_company_data(company_id)

        if method not in METHODS:
            logger.warning(f"Unknown method '{method}', falling back to growth_rate")
            method = "growth_rate"

        provenance = {"method": method, "seed_data_keys": list(seed_data.keys())}

        if method == "growth_rate":
            forecast = self._build_growth_rate(seed_data, months, assumptions)
        elif method == "advanced_regression":
            forecast = self._build_advanced_regression(
                company_id, seed_data, months, start_period, provenance, company_data
            )
        elif method == "regression":
            forecast = self._build_regression(company_id, seed_data, months, start_period, provenance, company_data)
        elif method == "driver_based":
            forecast = self._build_driver_based(
                {**seed_data, "company_id": company_id}, months, assumptions
            )
        elif method == "seasonal":
            forecast = self._build_seasonal(company_id, seed_data, months, assumptions, provenance, company_data)
        elif method == "budget_pct":
            forecast = self._build_budget_pct(company_id, seed_data, months, provenance, company_data)
        elif method == "manual":
            forecast = self._build_manual(assumptions, months)
        elif method == "model_construction":
            forecast = self._build_model_construction(
                company_id, seed_data, months, start_period, provenance, company_data
            )
        elif method == "liquidity":
            forecast = self._build_liquidity(
                company_id, seed_data, months, start_period, provenance
            )
        elif method == "monte_carlo":
            forecast = self._build_monte_carlo(
                company_id, seed_data, months, start_period, provenance
            )
        else:
            forecast = self._build_growth_rate(seed_data, months, assumptions)

        # Evolve balance sheet positions across forecast periods
        if forecast and method != "manual":
            try:
                forecast = self._evolve_balance_sheet(company_id, forecast, seed_data)
                provenance["bs_evolved"] = True
            except Exception as e:
                logger.debug(f"BS evolution failed (non-fatal): {e}")
                provenance["bs_evolved"] = False

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
        start_period: str, provenance: Dict, company_data=None,
    ) -> List[Dict]:
        """Regression-based forecast: fit actuals, project forward, then
        feed projected revenue growth into LiquidityManagementService."""
        from app.services.fpa_regression_service import FPARegressionService
        from app.services.liquidity_management_service import LiquidityManagementService
        import asyncio

        svc = FPARegressionService()
        y = company_data.sorted_amounts("revenue") if company_data else []
        overrides = {}

        if len(y) >= 6:
            x = list(range(len(y)))

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
                reg_result = self._simple_linear_regression(x, y)

            provenance["regression"] = reg_result

            slope = reg_result.get("slope", 0)
            intercept = reg_result.get("intercept", 0)
            last_x = len(y)

            last_revenue = seed_data.get("revenue", 0)
            projected_12m = slope * (last_x + 12) + intercept
            if last_revenue > 0 and projected_12m > 0:
                implied_annual_growth = (projected_12m / last_revenue) - 1
                overrides["growth_rate"] = implied_annual_growth
                provenance["implied_annual_growth"] = implied_annual_growth

        # Build using LiquidityManagementService with regression-adjusted growth
        lms = LiquidityManagementService()
        lms_result = lms.build_liquidity_model(
            company_id=company_id,
            months=months,
            start_period=start_period,
            scenario_overrides=overrides,
        )
        forecast = lms_result.get("monthly", [])
        return forecast if forecast else self._build_growth_rate(seed_data, months)

    def _build_driver_based(
        self, seed_data: Dict, months: int, assumptions: Dict = None
    ) -> List[Dict]:
        """Driver-based model — uses LiquidityManagementService with customer/ACV drivers."""
        from app.services.liquidity_management_service import LiquidityManagementService

        # Promote detected drivers to top-level keys
        overrides = dict(assumptions or {})
        if seed_data.get("_detected_acv") and "acv_override" not in overrides:
            overrides["acv_override"] = seed_data["_detected_acv"]
        if seed_data.get("_detected_customer_count") and "customers" not in overrides:
            overrides["customers"] = seed_data["_detected_customer_count"]
        if seed_data.get("churn_rate"):
            overrides.setdefault("churn_rate", seed_data["churn_rate"])
        if seed_data.get("nrr"):
            overrides.setdefault("nrr", seed_data["nrr"])

        company_id = seed_data.get("company_id", "")
        if not company_id:
            # Fallback: use CashFlowPlanningService if no company_id for LMS
            from app.services.cash_flow_planning_service import CashFlowPlanningService
            enriched = {**seed_data, **overrides}
            svc = CashFlowPlanningService()
            return svc.build_monthly_cash_flow_model(enriched, months=months)

        lms = LiquidityManagementService()
        lms_result = lms.build_liquidity_model(
            company_id=company_id,
            months=months,
            scenario_overrides=overrides,
        )
        forecast = lms_result.get("monthly", [])
        return forecast if forecast else self._build_growth_rate(seed_data, months)

    def _build_model_construction(
        self, company_id: str, seed_data: Dict, months: int,
        start_period: str, provenance: Dict, company_data=None,
    ) -> List[Dict]:
        """Full model construction engine: AgentModelConstructor → ModelSpecExecutor.

        Uses macro/business event analysis, strategic signals, driver sensitivity,
        and causal event chains to build a proper forecast instead of basic growth decay.
        """
        import asyncio
        from app.services.model_router import get_model_router
        from app.services.agent_model_constructor import AgentModelConstructor
        from app.services.model_spec_executor import ModelSpecExecutor

        model_router = get_model_router()
        constructor = AgentModelConstructor(model_router)

        # Build a prompt from the seed data context so the constructor
        # has something to reason about even without an explicit user prompt
        stage = seed_data.get("stage", "growth")
        revenue = seed_data.get("revenue", 0)
        growth = seed_data.get("growth_rate", 0)
        prompt = (
            f"Build a {months}-month forecast for this {stage}-stage company. "
            f"Current monthly revenue: ${revenue:,.0f}, growth rate: {growth:.0%}. "
            f"Use all available signals, macro context, and business events."
        )

        try:
            # AgentModelConstructor is async — bridge into sync context
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    specs = pool.submit(
                        asyncio.run,
                        constructor.construct_models(
                            prompt=prompt,
                            company_data=company_data,
                            company_id=company_id,
                        ),
                    ).result()
            else:
                specs = loop.run_until_complete(
                    constructor.construct_models(
                        prompt=prompt,
                        company_data=company_data,
                        company_id=company_id,
                    )
                )

            if not specs:
                logger.warning("model_construction returned no specs, falling back to growth_rate")
                return self._build_growth_rate(seed_data, months)

            # Execute the first spec
            executor = ModelSpecExecutor()
            result = executor.execute(
                spec=specs[0],
                company_data=seed_data,
                months=months,
                start_period=start_period,
            )

            provenance["model_id"] = specs[0].model_id
            provenance["event_chain_events"] = len(
                specs[0].event_chain.events if specs[0].event_chain else []
            )
            provenance["curves"] = list(specs[0].curves.keys())

            # Return the forecast rows from execution result
            if result.forecast:
                return result.forecast

            logger.warning("model_construction execution returned no forecast rows")
            return self._build_growth_rate(seed_data, months)

        except Exception as e:
            logger.error(f"model_construction failed: {e}", exc_info=True)
            provenance["model_construction_error"] = str(e)
            return self._build_growth_rate(seed_data, months)

    def _build_seasonal(
        self, company_id: str, seed_data: Dict, months: int,
        assumptions: Dict, provenance: Dict, company_data=None,
    ) -> List[Dict]:
        """LiquidityManagementService base + empirical seasonal overlay."""
        from app.services.seasonality_engine import SeasonalityEngine
        from app.services.liquidity_management_service import LiquidityManagementService

        # Build base forecast with proper subcategory modeling
        lms = LiquidityManagementService()
        lms_result = lms.build_liquidity_model(
            company_id=company_id,
            months=months,
            scenario_overrides=assumptions,
        )
        forecast = lms_result.get("monthly", [])

        if not forecast:
            forecast = self._build_growth_rate(seed_data, months, assumptions)

        # Detect and apply seasonality
        engine = SeasonalityEngine()
        pattern = engine.detect_pattern(company_id, "revenue", min_periods=12, company_data=company_data)
        if pattern:
            forecast = engine.apply_seasonal_factors(forecast, pattern, "revenue")
            provenance["seasonal_pattern"] = {
                "monthly_factors": pattern.monthly_factors,
                "strength": pattern.strength,
                "confidence": pattern.confidence,
            }

        return forecast

    def _build_budget_pct(
        self, company_id: str, seed_data: Dict, months: int, provenance: Dict,
        company_data=None,
    ) -> List[Dict]:
        """Forecast = budget × trailing achievement rate via LiquidityManagementService."""
        from app.core.supabase_client import get_supabase_client
        from app.services.liquidity_management_service import LiquidityManagementService

        sb = get_supabase_client()
        if not sb:
            return self._build_liquidity(company_id, seed_data, months, None, provenance)

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
            provenance["fallback"] = "no_approved_budget"
            return self._build_liquidity(company_id, seed_data, months, None, provenance)

        budget_id = budget_result.data[0]["id"]
        lines = (
            sb.table("budget_lines")
            .select("*")
            .eq("budget_id", budget_id)
            .execute()
        )

        if not lines.data:
            provenance["fallback"] = "no_budget_lines"
            return self._build_liquidity(company_id, seed_data, months, None, provenance)

        # Compute trailing achievement rate from actuals vs budget
        rev_amounts = company_data.sorted_amounts("revenue") if company_data else []
        budget_revenue_line = next(
            (l for l in lines.data if l.get("category") == "revenue"), None
        )

        achievement_rate = 1.0
        if budget_revenue_line and rev_amounts:
            recent = rev_amounts[-3:]
            actual_avg = sum(recent) / len(recent)
            budget_months = [budget_revenue_line.get(f"m{i}", 0) or 0 for i in range(1, 13)]
            budget_avg = sum(budget_months) / 12 if budget_months else 0
            if budget_avg > 0:
                achievement_rate = actual_avg / budget_avg

        provenance["budget_id"] = budget_id
        provenance["achievement_rate"] = achievement_rate

        # Build using LiquidityManagementService with budget-adjusted growth
        lms = LiquidityManagementService()
        lms_result = lms.build_liquidity_model(
            company_id=company_id,
            months=months,
        )
        forecast = lms_result.get("monthly", [])
        return forecast if forecast else self._build_growth_rate(seed_data, months)

    def _build_manual(self, assumptions: Dict, months: int) -> List[Dict]:
        """Manual forecast — just pass through whatever values were given."""
        if not assumptions or not isinstance(assumptions, dict):
            return []
        # Assumptions should contain per-period values
        # Return them as-is in forecast format
        return assumptions.get("forecast", [])

    def _build_advanced_regression(
        self, company_id: str, seed_data: Dict, months: int,
        start_period: str, provenance: Dict, company_data=None,
    ) -> List[Dict]:
        """Advanced regression: fit all models, pick best, project revenue,
        then use LiquidityManagementService for full P&L with proper subcategory modeling."""
        from app.services.advanced_regression_service import AdvancedRegressionService
        from app.services.liquidity_management_service import LiquidityManagementService

        adv = AdvancedRegressionService()
        hist = company_data.historical_values("revenue") if company_data else []
        actuals = [{"period": p, "amount": v} for p, v in hist]

        if len(actuals) < 3:
            logger.warning("Not enough actuals for advanced regression, falling back to liquidity")
            return self._build_liquidity(company_id, seed_data, months, start_period, provenance)

        try:
            result = adv.project_metric(
                actuals, periods=months, metric_key="amount", metric_name="revenue"
            )

            provenance["advanced_regression"] = {
                "model": result["model"],
                "selection_reasoning": result["selection_reasoning"],
                "data_characteristics": result["data_characteristics"],
            }

            projected_revenue = result["projected_values"]
            confidence_intervals = result["confidence_intervals"]

            # Compute implied growth from the regression curve
            last_actual = actuals[-1]["amount"]
            if last_actual > 0 and len(projected_revenue) >= 12:
                rev_12m = projected_revenue[min(11, len(projected_revenue) - 1)]
                implied_annual_growth = (rev_12m / last_actual) - 1
            elif last_actual > 0 and projected_revenue:
                n = len(projected_revenue)
                implied_annual_growth = ((projected_revenue[-1] / last_actual) ** (12 / n)) - 1
            else:
                implied_annual_growth = seed_data.get("growth_rate", 0)

            provenance["implied_annual_growth"] = implied_annual_growth
            provenance["regression_model_name"] = result["model"]["model_name"]

            # Build full P&L using LiquidityManagementService (proper subcategory growth drivers)
            # with regression-derived growth, then overlay the regression revenue curve
            lms = LiquidityManagementService()
            lms_result = lms.build_liquidity_model(
                company_id=company_id,
                months=months,
                start_period=start_period,
                scenario_overrides={"growth_rate": implied_annual_growth},
            )
            forecast = lms_result.get("monthly", [])

            if not forecast:
                forecast = self._build_growth_rate(seed_data, months)

            # Override revenue with actual regression projections (more accurate)
            for i, month_data in enumerate(forecast):
                if i < len(projected_revenue):
                    new_rev = projected_revenue[i]
                    if new_rev > 0:
                        month_data["revenue"] = round(new_rev, 2)
                        gm = month_data.get("gross_margin") or seed_data.get("gross_margin", 0.65)
                        month_data["cogs"] = round(new_rev * (1 - gm), 2)
                        month_data["gross_profit"] = round(new_rev * gm, 2)
                        total_opex = month_data.get("total_opex", 0) or 0
                        month_data["ebitda"] = round(month_data["gross_profit"] - total_opex, 2)
                        capex = month_data.get("capex", 0) or 0
                        month_data["free_cash_flow"] = round(month_data["ebitda"] - capex, 2)

                    if i < len(confidence_intervals):
                        month_data["_revenue_ci_lower"] = confidence_intervals[i]["lower"]
                        month_data["_revenue_ci_upper"] = confidence_intervals[i]["upper"]

            # Recalculate cumulative cash balance
            for i in range(1, len(forecast)):
                prev_cash = forecast[i - 1].get("cash_balance", 0) or 0
                fcf = forecast[i].get("free_cash_flow", 0) or 0
                forecast[i]["cash_balance"] = round(prev_cash + fcf, 2)

            return forecast

        except Exception as e:
            logger.warning(f"Advanced regression failed ({e}), falling back to liquidity")
            return self._build_liquidity(company_id, seed_data, months, start_period, provenance)

    def _build_liquidity(
        self, company_id: str, seed_data: Dict, months: int,
        start_period: str, provenance: Dict,
    ) -> List[Dict]:
        """LiquidityManagementService — granular subcategory-level cash flow
        modeling with proper growth drivers (headcount, usage, stepped, cac,
        revenue_pct).  Replaces CashFlowPlanningService for production use."""
        from app.services.liquidity_management_service import LiquidityManagementService

        svc = LiquidityManagementService()
        try:
            result = svc.build_liquidity_model(
                company_id=company_id,
                months=months,
                start_period=start_period,
            )
            provenance["liquidity_events"] = result.get("events_applied", 0)
            provenance["risk_alerts"] = len(result.get("risk_alerts", []))
            monthly = result.get("monthly", [])
            if monthly:
                return monthly
            logger.warning("Liquidity model returned empty monthly, falling back")
            return self._build_growth_rate(seed_data, months)
        except Exception as e:
            logger.warning(f"Liquidity model failed ({e}), falling back to growth_rate")
            provenance["liquidity_error"] = str(e)
            return self._build_growth_rate(seed_data, months)

    def _build_monte_carlo(
        self, company_id: str, seed_data: Dict, months: int,
        start_period: str, provenance: Dict,
    ) -> List[Dict]:
        """Monte Carlo simulation — returns the median (p50) trajectory."""
        from app.services.monte_carlo_engine import MonteCarloEngine

        engine = MonteCarloEngine()
        try:
            mc_result = engine.simulate(company_id, iterations=500, months=months)
            provenance["mc_iterations"] = mc_result.iterations
            provenance["mc_break_even_prob"] = mc_result.break_even_probability
            provenance["mc_var_cash_12m"] = mc_result.var_cash_12m

            # Build forecast rows from p50 trajectories
            periods = mc_result.periods or []
            if not periods:
                return self._build_growth_rate(seed_data, months)

            forecast: List[Dict] = []
            for i, period in enumerate(periods):
                row: Dict[str, Any] = {"period": period}
                for metric, percentiles in mc_result.trajectory_percentiles.items():
                    p50 = percentiles.get("p50", [])
                    if i < len(p50):
                        row[metric] = round(p50[i], 2)
                    # Also attach confidence bands
                    p5 = percentiles.get("p5", [])
                    p95 = percentiles.get("p95", [])
                    if i < len(p5):
                        row[f"_{metric}_ci_lower"] = round(p5[i], 2)
                    if i < len(p95):
                        row[f"_{metric}_ci_upper"] = round(p95[i], 2)
                forecast.append(row)

            return forecast if forecast else self._build_growth_rate(seed_data, months)
        except Exception as e:
            logger.warning(f"Monte Carlo failed ({e}), falling back")
            provenance["mc_error"] = str(e)
            return self._build_growth_rate(seed_data, months)

    # ------------------------------------------------------------------
    # Balance Sheet evolution — runs after P&L forecast to evolve BS
    # ------------------------------------------------------------------

    def _evolve_balance_sheet(
        self,
        company_id: str,
        forecast: List[Dict],
        seed_data: Dict,
    ) -> List[Dict]:
        """Evolve balance sheet positions across forecast periods.

        Uses DSO/DPO/DIO ratios from seed data or defaults to derive:
          bs_receivables = revenue × (dso / 30)
          bs_payables = cogs × (dpo / 30)
          bs_inventory = cogs × (dio / 30)
          bs_cash[t] = bs_cash[t-1] + fcf + Δworking_capital
          bs_ppe[t] = bs_ppe[t-1] - depreciation + capex
          bs_lt_debt[t] = bs_lt_debt[t-1] - debt_service_principal

        Attaches bs_* fields to each forecast row in-place.
        """
        # Load opening BS position from actuals
        opening = self._load_opening_bs(company_id)

        # Working capital assumptions (days)
        dso = seed_data.get("dso_days", opening.get("dso_days", 45))
        dpo = seed_data.get("dpo_days", opening.get("dpo_days", 30))
        dio = seed_data.get("dio_days", opening.get("dio_days", 0))
        monthly_depreciation = seed_data.get("depreciation_monthly", opening.get("depreciation_monthly", 0))
        debt_service = seed_data.get("debt_service_monthly", 0)

        # Initialize from opening position
        prev_cash = opening.get("bs_cash", seed_data.get("cash_balance", 0))
        prev_ppe = opening.get("bs_ppe", 0)
        prev_lt_debt = opening.get("bs_lt_debt", 0)
        prev_deferred_rev = opening.get("bs_deferred_revenue", 0)
        prev_retained_earnings = opening.get("bs_retained_earnings", 0)
        share_capital = opening.get("bs_share_capital", 0)

        for row in forecast:
            revenue = row.get("revenue", 0) or 0
            cogs = row.get("cogs", 0) or 0
            fcf = row.get("free_cash_flow", 0) or 0
            capex = row.get("capex", 0) or 0
            net_income = row.get("net_income", 0) or row.get("ebitda", 0) or 0

            # Receivables/payables/inventory from ratio model
            bs_receivables = round(revenue * (dso / 30), 2)
            bs_payables = round(cogs * (dpo / 30), 2)
            bs_inventory = round(cogs * (dio / 30), 2) if dio > 0 else 0

            # PP&E evolution
            bs_ppe = round(prev_ppe - monthly_depreciation + capex, 2)

            # Debt paydown
            bs_lt_debt = round(max(0, prev_lt_debt - debt_service), 2)

            # Cash from P&L FCF (working capital delta already in FCF for most models)
            bs_cash = round(prev_cash + fcf, 2)

            # Deferred revenue — hold constant unless revenue growth implies change
            bs_deferred_revenue = round(prev_deferred_rev, 2)

            # Equity: retained earnings accumulates net income each period
            bs_retained_earnings = round(prev_retained_earnings + net_income, 2)

            # Working capital & net debt
            working_capital = bs_receivables + bs_inventory - bs_payables - bs_deferred_revenue
            net_debt = bs_lt_debt - bs_cash

            # Total assets & total liabilities+equity for balance check
            total_assets = bs_cash + bs_receivables + bs_inventory + bs_ppe
            total_liabilities = bs_payables + bs_lt_debt + bs_deferred_revenue
            total_equity = share_capital + bs_retained_earnings

            row["bs_cash"] = bs_cash
            row["bs_receivables"] = bs_receivables
            row["bs_payables"] = bs_payables
            row["bs_inventory"] = bs_inventory
            row["bs_ppe"] = bs_ppe
            row["bs_lt_debt"] = bs_lt_debt
            row["bs_st_debt"] = 0
            row["bs_deferred_revenue"] = bs_deferred_revenue
            row["bs_retained_earnings"] = bs_retained_earnings
            row["bs_share_capital"] = share_capital
            row["bs_total_equity"] = round(total_equity, 2)
            row["working_capital"] = round(working_capital, 2)
            row["net_debt"] = round(net_debt, 2)
            row["bs_total_assets"] = round(total_assets, 2)
            row["bs_total_liabilities"] = round(total_liabilities, 2)

            # Carry forward
            prev_cash = bs_cash
            prev_ppe = bs_ppe
            prev_lt_debt = bs_lt_debt
            prev_deferred_rev = bs_deferred_revenue
            prev_retained_earnings = bs_retained_earnings

        return forecast

    def _load_opening_bs(self, company_id: str) -> Dict[str, float]:
        """Load the most recent BS position from fpa_actuals."""
        try:
            from app.core.supabase_client import get_supabase_client

            sb = get_supabase_client()
            if not sb:
                return {}

            result = (
                sb.table("fpa_actuals")
                .select("period, category, amount")
                .eq("company_id", company_id)
                .like("category", "bs_%")
                .order("period", desc=True)
                .limit(200)
                .execute()
            )

            if not result.data:
                return {}

            # Get the latest period's values
            latest_period = result.data[0]["period"][:7]
            opening: Dict[str, float] = {}
            for row in result.data:
                if row["period"][:7] != latest_period:
                    break
                cat = row["category"]
                opening[cat] = opening.get(cat, 0) + float(row["amount"])

            # Compute implied DSO/DPO from actuals if we have revenue/cogs
            # (pull latest P&L too)
            # Filter to the single latest period using .like on YYYY-MM prefix
            pnl_result = (
                sb.table("fpa_actuals")
                .select("category, amount")
                .eq("company_id", company_id)
                .like("period", f"{latest_period}%")
                .in_("category", ["revenue", "cogs"])
                .execute()
            )
            pnl_vals: Dict[str, float] = {}
            for row in (pnl_result.data or []):
                pnl_vals[row["category"]] = pnl_vals.get(row["category"], 0) + float(row["amount"])

            rev = pnl_vals.get("revenue", 0)
            cogs = pnl_vals.get("cogs", 0)
            if rev > 0 and opening.get("bs_receivables", 0) > 0:
                opening["dso_days"] = round(opening["bs_receivables"] / rev * 30, 0)
            if cogs > 0 and opening.get("bs_payables", 0) > 0:
                opening["dpo_days"] = round(opening["bs_payables"] / cogs * 30, 0)
            if cogs > 0 and opening.get("bs_inventory", 0) > 0:
                opening["dio_days"] = round(opening["bs_inventory"] / cogs * 30, 0)

            return opening
        except Exception as e:
            logger.debug(f"Could not load opening BS: {e}")
            return {}

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _quick_advanced_regression_check(self, company_data) -> Optional[Dict]:
        """Quick check: fit advanced models on revenue actuals, return best model info."""
        from app.services.advanced_regression_service import AdvancedRegressionService

        y = company_data.sorted_amounts("revenue") if company_data else []
        if len(y) < 6:
            return None

        x = list(range(len(y)))

        try:
            adv = AdvancedRegressionService()
            result = adv.auto_select_best_model(x, y, forecast_periods=12, metric_name="revenue")
            return result.best_model.to_dict()
        except Exception as e:
            logger.debug(f"Advanced regression check failed: {e}")
            return None

    def _quick_regression_check(self, company_data) -> Optional[float]:
        """Quick R² check on revenue actuals."""
        y = company_data.sorted_amounts("revenue") if company_data else []
        if len(y) < 6:
            return None

        x = list(range(len(y)))
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
