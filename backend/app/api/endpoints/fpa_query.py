"""
FPA Query API Endpoints
Natural Language FP&A query processing
"""

from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field
import logging
import time

from app.services.nl_fpa_parser import NLFPAParser
from app.services.fpa_query_classifier import FPAQueryClassifier
from app.services.fpa_workflow_builder import FPAWorkflowBuilder
from app.services.fpa_executor import FPAExecutor, ExecutorContext
from app.services.fpa_model_editor import FPAModelEditor
from app.services.fpa_regression_service import FPARegressionService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/fpa", tags=["fpa"])


# Request/Response models
class FPAQueryRequest(BaseModel):
    """Request for FPA query"""
    query: str = Field(..., description="Natural language query")
    fund_id: Optional[str] = None
    company_ids: Optional[list[str]] = None
    save_model: bool = False
    model_name: Optional[str] = None


class FPAModelRequest(BaseModel):
    """Request to create/update FPA model"""
    name: str
    model_type: str
    model_definition: Dict[str, Any]
    formulas: Dict[str, str]
    assumptions: Dict[str, Any]
    fund_id: Optional[str] = None


class FPARegressionRequest(BaseModel):
    """Request for regression analysis"""
    regression_type: str  # "linear" | "exponential" | "time_series" | "monte_carlo" | "sensitivity"
    data: Dict[str, Any]
    options: Optional[Dict[str, Any]] = None


class FPAForecastRequest(BaseModel):
    """Request for forecast generation"""
    base_data: Dict[str, Any]
    forecast_periods: int
    growth_rate: Optional[float] = None
    assumptions: Optional[Dict[str, Any]] = None


# Initialize services
nl_parser = NLFPAParser()
classifier = FPAQueryClassifier()
workflow_builder = FPAWorkflowBuilder()
executor = FPAExecutor()
model_editor = FPAModelEditor()
regression_service = FPARegressionService()


@router.post("/query")
async def process_fpa_query(request: FPAQueryRequest):
    """
    Process a natural language FP&A query
    
    Returns parsed query, workflow, results, and model structure
    """
    start_time = time.time()
    
    try:
        # Parse query
        parsed_query = nl_parser.parse(request.query)
        
        # Classify query
        handler = classifier.route(parsed_query)
        
        # Build workflow
        workflow = workflow_builder.build(parsed_query, handler)
        
        # Execute workflow
        ctx = ExecutorContext(
            fund_id=request.fund_id,
            company_ids=request.company_ids,
            user_id=None  # TODO: Get from auth
        )
        
        execution_result = await executor.execute(workflow, ctx)
        
        execution_time_ms = int((time.time() - start_time) * 1000)
        
        # Optionally save model
        model_id = None
        if request.save_model and request.model_name:
            model = await model_editor.create_model(
                name=request.model_name,
                model_type=handler,
                model_definition=parsed_query.dict(),
                formulas=execution_result["model_structure"]["formulas"],
                assumptions=execution_result["model_structure"]["assumptions"],
                created_by="user",  # TODO: Get from auth
                fund_id=request.fund_id
            )
            model_id = model.get("id")
        
        return {
            "parsed_query": parsed_query.dict(),
            "handler": handler,
            "workflow": [step.dict() for step in workflow],
            "results": execution_result["results"],
            "step_results": execution_result["step_results"],
            "model_structure": execution_result["model_structure"],
            "execution_time_ms": execution_time_ms,
            "model_id": model_id
        }
        
    except Exception as e:
        logger.error(f"Error processing FPA query: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/models")
async def create_fpa_model(request: FPAModelRequest):
    """Create a new FPA model"""
    try:
        model = await model_editor.create_model(
            name=request.name,
            model_type=request.model_type,
            model_definition=request.model_definition,
            formulas=request.formulas,
            assumptions=request.assumptions,
            created_by="user",  # TODO: Get from auth
            fund_id=request.fund_id
        )
        return model
    except Exception as e:
        logger.error(f"Error creating model: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/models/{model_id}")
async def get_fpa_model(model_id: str):
    """Get an FPA model by ID"""
    try:
        model = await model_editor.get_model(model_id)
        if not model:
            raise HTTPException(status_code=404, detail="Model not found")
        return model
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting model: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/models/{model_id}/formula")
async def update_model_formula(
    model_id: str,
    step_id: str,
    formula: str
):
    """Update a formula for a specific step"""
    try:
        result = await model_editor.update_formula(model_id, step_id, formula)
        return result
    except Exception as e:
        logger.error(f"Error updating formula: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/models/{model_id}/assumptions")
async def update_model_assumptions(
    model_id: str,
    assumptions: Dict[str, Any]
):
    """Update assumptions for a model"""
    try:
        result = await model_editor.update_assumptions(model_id, assumptions)
        return result
    except Exception as e:
        logger.error(f"Error updating assumptions: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/models/{model_id}/execute")
async def execute_model(model_id: str):
    """Re-run a model with current formulas/assumptions"""
    try:
        model = await model_editor.get_model(model_id)
        if not model:
            raise HTTPException(status_code=404, detail="Model not found")
        
        # Rebuild workflow from model definition
        # TODO: Implement model re-execution
        return {"status": "executed", "model_id": model_id}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error executing model: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/regression")
async def run_regression(request: FPARegressionRequest):
    """Run regression analysis"""
    try:
        if request.regression_type == "linear":
            x = request.data.get("x", [])
            y = request.data.get("y", [])
            result = await regression_service.linear_regression(x, y)
        elif request.regression_type == "exponential":
            data = request.data.get("data", [])
            time_periods = request.data.get("time_periods", [])
            result = await regression_service.exponential_decay(data, time_periods)
        elif request.regression_type == "time_series":
            historical_data = request.data.get("historical_data", [])
            periods = request.options.get("periods", 12) if request.options else 12
            result = await regression_service.time_series_forecast(historical_data, periods)
        elif request.regression_type == "monte_carlo":
            base_scenario = request.data.get("base_scenario", {})
            distributions = request.data.get("distributions", {})
            iterations = request.options.get("iterations", 1000) if request.options else 1000
            result = await regression_service.monte_carlo_simulation(base_scenario, distributions, iterations)
        elif request.regression_type == "sensitivity":
            base_inputs = request.data.get("base_inputs", {})
            variable_ranges = request.data.get("variable_ranges", {})
            # TODO: Pass model function
            result = await regression_service.sensitivity_analysis(base_inputs, variable_ranges, None)
        else:
            raise HTTPException(status_code=400, detail=f"Unknown regression type: {request.regression_type}")
        
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error running regression: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/forecast")
async def generate_forecast(request: FPAForecastRequest):
    """Generate forecast with editable parameters"""
    try:
        # TODO: Implement forecast generation
        return {
            "forecast": [],
            "assumptions": request.assumptions or {}
        }
    except Exception as e:
        logger.error(f"Error generating forecast: {e}")
        raise HTTPException(status_code=500, detail=str(e))
