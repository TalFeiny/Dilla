"""
FPA Executor
Executes workflow steps by calling appropriate services
"""

import logging
from typing import Dict, List, Any, Optional
from pydantic import BaseModel

from app.services.fpa_workflow_builder import WorkflowStep

logger = logging.getLogger(__name__)


class ExecutorContext(BaseModel):
    """Context for FPA execution"""
    fund_id: Optional[str] = None
    company_ids: Optional[List[str]] = None
    portfolio_snapshot: Optional[Dict[str, Any]] = None  # pre-fetched companies
    model_id: Optional[str] = None
    user_id: Optional[str] = None


class FPAExecutor:
    """Executes FPA workflows by calling backend services"""

    def __init__(self):
        self._regression_service = None
        self._valuation_engine = None
        self._gap_filler = None
        self._driver_impact_service = None

    # ------------------------------------------------------------------
    # Lazy service accessors
    # ------------------------------------------------------------------

    def _get_regression_service(self):
        if self._regression_service is None:
            from app.services.fpa_regression_service import FPARegressionService
            self._regression_service = FPARegressionService()
        return self._regression_service

    def _get_valuation_engine(self):
        if self._valuation_engine is None:
            from app.services.valuation_engine_service import ValuationEngineService
            self._valuation_engine = ValuationEngineService()
        return self._valuation_engine

    def _get_gap_filler(self):
        if self._gap_filler is None:
            from app.services.intelligent_gap_filler import IntelligentGapFiller
            self._gap_filler = IntelligentGapFiller()
        return self._gap_filler

    def _get_driver_impact_service(self):
        if self._driver_impact_service is None:
            from app.services.driver_impact_service import DriverImpactService
            self._driver_impact_service = DriverImpactService()
        return self._driver_impact_service


    # ------------------------------------------------------------------
    # Main execute
    # ------------------------------------------------------------------

    async def execute(
        self,
        workflow: List[WorkflowStep],
        ctx: ExecutorContext
    ) -> Dict[str, Any]:
        """Execute a workflow and return results."""
        logger.info(f"Executing workflow with {len(workflow)} steps")

        state = {}
        results = []

        for step in workflow:
            try:
                inputs = self._resolve_inputs(step.inputs, state, ctx)
                output = await self._execute_step(step, inputs, ctx)

                for output_key in step.outputs:
                    state[output_key] = output

                results.append({
                    "step_id": step.step_id,
                    "name": step.name,
                    "output": output,
                    "success": True
                })

            except Exception as e:
                logger.error(f"Error executing step {step.step_id}: {e}")
                results.append({
                    "step_id": step.step_id,
                    "name": step.name,
                    "error": str(e),
                    "success": False
                })

        return {
            "results": state,
            "step_results": results,
            "model_structure": self._build_model_structure(workflow, state)
        }

    def _resolve_inputs(
        self,
        inputs: Dict[str, Any],
        state: Dict[str, Any],
        ctx: ExecutorContext
    ) -> Dict[str, Any]:
        """Resolve input references to actual values"""
        resolved = {}

        for key, value in inputs.items():
            if isinstance(value, str) and value.startswith("$"):
                ref_key = value[1:]
                resolved[key] = state.get(ref_key, value)
            else:
                resolved[key] = value

        # Inject context
        if ctx.fund_id:
            resolved.setdefault("fund_id", ctx.fund_id)
        if ctx.portfolio_snapshot:
            resolved.setdefault("portfolio_snapshot", ctx.portfolio_snapshot)

        return resolved

    async def _execute_step(
        self,
        step: WorkflowStep,
        inputs: Dict[str, Any],
        ctx: ExecutorContext
    ) -> Any:
        """Execute a single workflow step"""
        service_name = step.service_call.get("service")
        method_name = step.service_call.get("method")
        kwargs = step.service_call.get("kwargs", {})

        kwargs.update(inputs)

        if service_name == "revenue_projection":
            return await self._call_revenue_projection(method_name, kwargs, ctx)
        elif service_name == "valuation_engine":
            return await self._call_valuation_engine(method_name, kwargs, ctx)
        elif service_name == "pwerm":
            return await self._call_pwerm(method_name, kwargs, ctx)
        elif service_name == "gap_filler":
            return await self._call_gap_filler(method_name, kwargs, ctx)
        elif service_name == "scenario_branch":
            return await self._call_scenario_branch(method_name, kwargs, ctx)
        elif service_name == "driver_impact":
            return await self._call_driver_impact(method_name, kwargs, ctx)
        elif service_name == "budget_variance":
            return await self._call_budget_variance(method_name, kwargs, ctx)
        elif service_name == "custom":
            return await self._call_custom(method_name, kwargs, ctx)
        else:
            raise ValueError(f"Unknown service: {service_name}")

    # ------------------------------------------------------------------
    # Service call implementations
    # ------------------------------------------------------------------

    async def _call_scenario_branch(
        self,
        method: str,
        kwargs: Dict[str, Any],
        ctx: ExecutorContext
    ) -> Any:
        """
        Create a scenario branch and compare to base case.
        Routes through ScenarioBranchService for full fork-aware,
        monthly-granularity projections with parent chain inheritance.
        """
        from app.services.scenario_branch_service import ScenarioBranchService

        company_id = kwargs.get("company_id") or (ctx.company_ids[0] if ctx.company_ids else None)
        if not company_id:
            return {"error": "No company_id for scenario branch"}

        assumptions = kwargs.get("assumptions", {})
        branch_name = kwargs.get("branch_name", "What-if scenario")
        fork_period = kwargs.get("fork_period")
        granularity = kwargs.get("granularity", "monthly")
        forecast_months = kwargs.get("forecast_months", 24)

        # Persist branch to DB first so ScenarioBranchService can walk the chain
        branch_id = await self._persist_scenario_branch(
            company_id=company_id,
            fund_id=ctx.fund_id,
            name=branch_name,
            assumptions=assumptions,
            fork_period=fork_period,
        )

        if not branch_id:
            return {"error": "Failed to persist scenario branch"}

        sbs = ScenarioBranchService()

        # Execute the branch with full fork-aware projection
        result = sbs.execute_branch(
            branch_id=branch_id,
            company_id=company_id,
            forecast_months=forecast_months,
        )

        if "error" in result:
            return result

        # Aggregate to requested granularity if not monthly
        branch_forecast = result.get("forecast", [])
        base_forecast = result.get("base_forecast", [])

        if granularity != "monthly":
            from app.services.cash_flow_planning_service import CashFlowPlanningService
            if granularity == "quarterly":
                branch_forecast = CashFlowPlanningService._aggregate_to_quarterly(branch_forecast)
                base_forecast = CashFlowPlanningService._aggregate_to_quarterly(base_forecast)
            elif granularity == "annual":
                branch_forecast = CashFlowPlanningService._aggregate_to_annual(branch_forecast)
                base_forecast = CashFlowPlanningService._aggregate_to_annual(base_forecast)

        # Build comparison summary
        b_last = branch_forecast[-1] if branch_forecast else {}
        base_last = base_forecast[-1] if base_forecast else {}

        # Build chart data using ScenarioBranchService's multi-branch chart builder
        comparisons = [
            {"branch_id": None, "name": "Base Case", "forecast": base_forecast, "fork_month_index": 0},
            {"branch_id": branch_id, "name": branch_name, "forecast": branch_forecast,
             "fork_month_index": result.get("fork_month_index", 0)},
        ]
        charts = sbs._build_multi_branch_charts(comparisons)

        # Capital raising analysis if runway is short
        capital_raising = sbs.analyze_capital_needs(
            branch_id, company_id, forecast_months=forecast_months,
        )

        return {
            "branch_id": branch_id,
            "branch_name": branch_name,
            "granularity": granularity,
            "base_case": {
                "final_revenue": base_last.get("revenue", 0),
                "final_ebitda": base_last.get("ebitda", 0),
                "final_cash": base_last.get("cash_balance", 0),
                "final_runway": base_last.get("runway_months", 0),
            },
            "branch_case": {
                "final_revenue": b_last.get("revenue", 0),
                "final_ebitda": b_last.get("ebitda", 0),
                "final_cash": b_last.get("cash_balance", 0),
                "final_runway": b_last.get("runway_months", 0),
            },
            "delta": {
                "revenue": round(b_last.get("revenue", 0) - base_last.get("revenue", 0), 2),
                "ebitda": round(b_last.get("ebitda", 0) - base_last.get("ebitda", 0), 2),
                "cash": round(b_last.get("cash_balance", 0) - base_last.get("cash_balance", 0), 2),
            },
            "charts": charts,
            "base_forecast": base_forecast,
            "branch_forecast": branch_forecast,
            "assumptions": result.get("assumptions", {}),
            "capital_raising": capital_raising,
        }

    async def _persist_scenario_branch(
        self,
        company_id: str,
        fund_id: Optional[str],
        name: str,
        assumptions: Dict[str, Any],
        fork_period: Optional[str] = None,
    ) -> Optional[str]:
        """Save scenario branch to DB. Returns branch ID."""
        try:
            from app.core.supabase_client import get_supabase_client
            import json
            sb = get_supabase_client()
            if not sb:
                return None
            row = {
                "company_id": company_id,
                "name": name,
                "assumptions": json.dumps(assumptions) if isinstance(assumptions, dict) else assumptions,
            }
            if fund_id:
                row["fund_id"] = fund_id
            if fork_period:
                row["fork_period"] = fork_period
            result = sb.table("scenario_branches").insert(row).execute()
            if result.data:
                return result.data[0].get("id")
        except Exception as e:
            logger.warning("Failed to persist scenario branch: %s", e)
        return None

    async def _call_revenue_projection(
        self,
        method: str,
        kwargs: Dict[str, Any],
        ctx: ExecutorContext
    ) -> Any:
        """Call FPARegressionService for revenue forecasting."""
        svc = self._get_regression_service()

        # Build historical data from portfolio snapshot or kwargs
        historical_data = kwargs.get("historical_data")
        periods = kwargs.get("periods", 12)

        if not historical_data:
            # Try to seed from fpa_actuals first
            company_id = kwargs.get("company_id") or (ctx.company_ids[0] if ctx.company_ids else None)
            if company_id:
                try:
                    from app.services.actuals_ingestion import get_actuals_for_forecast
                    actuals = get_actuals_for_forecast(company_id, "revenue", months=24)
                    if actuals:
                        historical_data = [{"period": a["period"], "value": a["amount"]} for a in actuals]
                except Exception as e:
                    logger.warning("Failed to load actuals for forecast: %s", e)

        if not historical_data:
            # Try to build from portfolio snapshot
            historical_data = self._extract_historical_revenue(kwargs, ctx)

        if historical_data and len(historical_data) >= 1:
            result = await svc.time_series_forecast(
                historical_data=historical_data,
                periods=int(periods),
            )
            return result

        # Fallback: if we have at least two data points, try linear regression
        x = kwargs.get("x")
        y = kwargs.get("y")
        if x and y and len(x) >= 2:
            return await svc.linear_regression(x=x, y=y)

        # Minimal fallback — return what we have
        return {
            "forecast": [],
            "note": "Insufficient historical data for projection. Provide revenue time series.",
            "input_received": {k: v for k, v in kwargs.items() if k not in ("portfolio_snapshot",)},
        }

    async def _call_valuation_engine(
        self,
        method: str,
        kwargs: Dict[str, Any],
        ctx: ExecutorContext
    ) -> Any:
        """Call ValuationEngineService."""
        svc = self._get_valuation_engine()

        # Build a ValuationRequest if we have company data
        company_data = kwargs.get("company_data") or {}
        companies = kwargs.get("companies", [])

        # If we have company names but no data, try portfolio snapshot
        if companies and not company_data and ctx.portfolio_snapshot:
            rows = ctx.portfolio_snapshot.get("rows", [])
            for row in rows:
                if row.get("name", "").lower() in [c.lower() for c in companies]:
                    company_data = row
                    break

        if company_data:
            try:
                from app.services.valuation_engine_service import ValuationRequest
                request = ValuationRequest(
                    company_name=company_data.get("name", "Unknown"),
                    revenue=company_data.get("revenue") or company_data.get("arr"),
                    growth_rate=company_data.get("growth_rate"),
                    industry=company_data.get("sector") or company_data.get("industry"),
                    stage=company_data.get("funding_stage"),
                )
                result = await svc.calculate_valuation(request)
                return result if isinstance(result, dict) else {"valuation": str(result)}
            except Exception as e:
                logger.warning(f"ValuationEngine call failed: {e}")
                return {"error": str(e), "service": "valuation_engine"}

        return {
            "note": "No company data available for valuation",
            "input_received": {k: v for k, v in kwargs.items() if k not in ("portfolio_snapshot",)},
        }

    async def _call_pwerm(
        self,
        method: str,
        kwargs: Dict[str, Any],
        ctx: ExecutorContext
    ) -> Any:
        """Call PWERM via ValuationEngineService."""
        svc = self._get_valuation_engine()

        company_data = kwargs.get("company_data") or {}
        if company_data:
            try:
                from app.services.valuation_engine_service import ValuationRequest
                request = ValuationRequest(
                    company_name=company_data.get("name", "Unknown"),
                    revenue=company_data.get("revenue") or company_data.get("arr"),
                    growth_rate=company_data.get("growth_rate"),
                    industry=company_data.get("sector"),
                    stage=company_data.get("funding_stage"),
                    method="pwerm",
                )
                result = await svc.calculate_valuation(request)
                return result if isinstance(result, dict) else {"pwerm": str(result)}
            except Exception as e:
                logger.warning(f"PWERM call failed: {e}")
                return {"error": str(e), "service": "pwerm"}

        return {"note": "No company data available for PWERM analysis"}

    async def _call_gap_filler(
        self,
        method: str,
        kwargs: Dict[str, Any],
        ctx: ExecutorContext
    ) -> Any:
        """Call IntelligentGapFiller to enrich company data."""
        svc = self._get_gap_filler()

        company_data = kwargs.get("company_data") or {}
        if company_data:
            try:
                result = await svc.fill_gaps(company_data)
                return result if isinstance(result, dict) else {"filled": str(result)}
            except Exception as e:
                logger.warning(f"GapFiller call failed: {e}")
                return {"error": str(e), "service": "gap_filler"}

        return {"note": "No company data to fill gaps for"}

    async def _call_driver_impact(
        self,
        method: str,
        kwargs: Dict[str, Any],
        ctx: ExecutorContext,
    ) -> Any:
        """Route to DriverImpactService methods."""
        svc = self._get_driver_impact_service()
        company_id = kwargs.get("company_id") or (ctx.company_ids[0] if ctx.company_ids else None)
        if not company_id:
            return {"error": "No company_id for driver impact analysis"}

        if method == "correlate_actuals":
            return await svc.correlate_actuals(
                company_id=company_id,
                metric_a=kwargs.get("metric_a", "revenue"),
                metric_b=kwargs.get("metric_b", "headcount"),
                method=kwargs.get("correlation_method", "pearson"),
            )
        elif method == "driver_impact_ranking":
            return await svc.driver_impact_ranking(
                company_id=company_id,
                target_metric=kwargs.get("target_metric", "revenue"),
            )
        elif method == "explain_ripple_path":
            return await svc.explain_ripple_path(
                company_id=company_id,
                driver_id=kwargs.get("driver_id", "revenue_growth"),
            )
        elif method == "explain_reverse_path":
            return await svc.explain_reverse_path(
                company_id=company_id,
                metric=kwargs.get("metric", "cash_balance"),
            )
        elif method == "trace_strategic_impact":
            return await svc.trace_strategic_impact(
                company_id=company_id,
                driver_id=kwargs.get("driver_id", "revenue_growth"),
            )
        else:
            return {"error": f"Unknown driver_impact method: {method}"}

    async def _call_budget_variance(
        self,
        method: str,
        kwargs: Dict[str, Any],
        ctx: ExecutorContext,
    ) -> Any:
        """Route to budget_variance_service module functions."""
        from app.services.budget_variance_service import (
            get_variance_report,
            get_ytd_variance,
            get_department_drilldown,
        )
        company_id = kwargs.get("company_id") or (ctx.company_ids[0] if ctx.company_ids else None)
        if not company_id:
            return {"error": "No company_id for budget variance"}

        if method == "variance_report":
            return get_variance_report(
                company_id=company_id,
                category=kwargs.get("category", "revenue"),
                budget_id=kwargs.get("budget_id"),
                period_start=kwargs.get("period_start"),
                period_end=kwargs.get("period_end"),
            )
        elif method == "ytd_variance":
            return get_ytd_variance(
                company_id=company_id,
                budget_id=kwargs.get("budget_id"),
            )
        elif method == "department_drilldown":
            return get_department_drilldown(
                company_id=company_id,
                budget_id=kwargs.get("budget_id"),
                department=kwargs.get("department", "all"),
            )
        else:
            return {"error": f"Unknown budget_variance method: {method}"}

    async def _call_custom(
        self,
        method: str,
        kwargs: Dict[str, Any],
        ctx: ExecutorContext
    ) -> Any:
        """Handle custom step types — pass through kwargs as result."""
        return {"custom_result": kwargs, "note": "Custom step executed with pass-through"}

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _extract_historical_revenue(
        self,
        kwargs: Dict[str, Any],
        ctx: ExecutorContext,
    ) -> List[Dict[str, Any]]:
        """Try to extract historical revenue data points from context."""
        data_points = []
        companies = kwargs.get("companies", [])

        if ctx.portfolio_snapshot:
            rows = ctx.portfolio_snapshot.get("rows", [])
            for row in rows:
                name = row.get("name", "")
                if companies and name.lower() not in [c.lower() for c in companies]:
                    continue
                revenue = row.get("revenue") or row.get("arr")
                if revenue and isinstance(revenue, (int, float)):
                    data_points.append({
                        "value": revenue,
                        "period": name,
                        "date": row.get("last_funding_date"),
                    })

        return data_points

    def _build_model_structure(
        self,
        workflow: List[WorkflowStep],
        state: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Build model structure for frontend display"""
        return {
            "steps": [
                {
                    "step_id": step.step_id,
                    "name": step.name,
                    "formula": step.formula,
                    "assumptions": step.assumptions,
                    "editable": step.editable
                }
                for step in workflow
            ],
            "formulas": {
                step.step_id: step.formula
                for step in workflow
            },
            "assumptions": {
                step.step_id: step.assumptions
                for step in workflow
            }
        }
