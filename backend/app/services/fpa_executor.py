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
        elif service_name == "custom":
            return await self._call_custom(method_name, kwargs, ctx)
        else:
            raise ValueError(f"Unknown service: {service_name}")

    # ------------------------------------------------------------------
    # Service call implementations
    # ------------------------------------------------------------------

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
