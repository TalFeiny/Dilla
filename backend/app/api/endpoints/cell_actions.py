"""
Cell Actions API Endpoints

Provides endpoints for:
1. Querying available cell actions (filtered by mode, category, column)
2. Executing cell actions with proper output transformation
"""

from fastapi import APIRouter, HTTPException, Depends
from typing import Optional, List, Dict, Any
from pydantic import BaseModel
import logging

from app.services.cell_action_registry import (
    get_registry,
    ActionCategory,
    OutputType
)

# Load financial tools and chart generator at module load so they are always available.
from app.tools.financial_tools import FinancialTools
from app.skills.chart_generation_skill import ChartGenerationSkill
# Other service imports are lazy (per-request) in _route_to_service so the router loads even if a dependency fails.
from app.services.ma_workflow_service import MAWorkflowService
from decimal import Decimal
import json

logger = logging.getLogger(__name__)


def _make_json_safe(obj: Any) -> Any:
    """
    Coerce value/metadata to JSON-serializable types.
    Converts Decimal to float, strips numpy types, and recurses into dicts/lists.
    """
    if obj is None:
        return None
    if isinstance(obj, Decimal):
        return float(obj)
    if hasattr(obj, 'item'):  # numpy scalar
        return obj.item()
    if hasattr(obj, 'tolist'):  # numpy array
        return obj.tolist()
    if isinstance(obj, dict):
        return {k: _make_json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_make_json_safe(v) for v in obj]
    if isinstance(obj, (int, float, str, bool)):
        return obj
    try:
        json.dumps(obj)
        return obj
    except (TypeError, ValueError):
        return str(obj)


def _get_supabase_client():
    """Lazy-load Supabase client so cell_actions module loads without it."""
    from app.core.database import supabase_service
    return supabase_service.get_client()


router = APIRouter(prefix="/cell-actions", tags=["cell-actions"])


class ActionExecutionRequest(BaseModel):
    """Request to execute a cell action"""
    action_id: str
    row_id: str
    column_id: str
    inputs: Dict[str, Any]
    mode: str = "portfolio"
    fund_id: Optional[str] = None
    company_id: Optional[str] = None
    trace_id: Optional[str] = None


class ActionExecutionResponse(BaseModel):
    """
    Response from action execution. Contract for frontend (UnifiedMatrix / cell-action-registry).

    Frontend expects:
    - success, action_id, value, display_value, metadata, error?
    - metadata.output_type: 'number' | 'object' | 'multi_column' | 'time_series' | 'chart' | ...
    - metadata.columns_to_create (when output_type == 'multi_column'): list of
      { id, name, type, values } where values is Record<row_id: string, number|string>
      (populateCellsForNewColumns uses col.values?.[r.id])
    - metadata.explanation, metadata.citations: for Citations & service logs panel
    - All value/metadata must be JSON-serializable (no Decimal, numpy) — enforced by _make_json_safe.
    """
    success: bool
    action_id: str
    value: Any
    display_value: str
    metadata: Dict[str, Any]
    error: Optional[str] = None


@router.get("/actions")
async def get_available_actions(
    mode: str = "portfolio",
    category: Optional[str] = None,
    column_id: Optional[str] = None,
    column_type: Optional[str] = None
):
    """
    Get available cell actions filtered by mode, category, and column compatibility
    
    Args:
        mode: Matrix mode ('portfolio', 'query', 'custom', 'lp')
        category: Optional category filter ('formula', 'workflow', 'document')
        column_id: Optional column ID
        column_type: Optional column type for compatibility check
    """
    try:
        registry = get_registry()
        actions = registry.get_available_actions(
            mode=mode,
            category=category,
            column_id=column_id,
            column_type=column_type
        )
        
        # Convert to dict format for JSON response
        actions_data = []
        for action in actions:
            actions_data.append({
                "action_id": action.action_id,
                "name": action.name,
                "description": action.description,
                "category": action.category.value,
                "service_name": action.service_name,
                "execution_type": action.execution_type.value,
                "required_inputs": action.required_inputs,
                "output_type": action.output_type.value,
                "mode_availability": action.mode_availability,
                "column_compatibility": action.column_compatibility,
                "config": action.config
            })
        
        return {
            "success": True,
            "actions": actions_data,
            "count": len(actions_data)
        }
    except Exception as e:
        logger.error(f"Error getting available actions: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/actions/{action_id}")
async def get_action(action_id: str):
    """Get specific action by ID"""
    try:
        registry = get_registry()
        action = registry.get_action(action_id)
        
        if not action:
            raise HTTPException(status_code=404, detail=f"Action {action_id} not found")
        
        return {
            "success": True,
            "action": {
                "action_id": action.action_id,
                "name": action.name,
                "description": action.description,
                "category": action.category.value,
                "service_name": action.service_name,
                "api_endpoint": action.api_endpoint,
                "execution_type": action.execution_type.value,
                "required_inputs": action.required_inputs,
                "output_type": action.output_type.value,
                "output_transform": action.output_transform,
                "mode_availability": action.mode_availability,
                "column_compatibility": action.column_compatibility,
                "config": action.config
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting action {action_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/actions/{action_id}/execute")
async def execute_action(
    action_id: str,
    request: ActionExecutionRequest
):
    """
    Execute a cell action.
    
    This endpoint:
    1. Looks up the action in the registry
    2. Routes to the appropriate service
    3. Transforms the output to cell-appropriate format
    4. Returns structured result with metadata
    """
    logger.info("Cell action execute: action_id=%s trace_id=%s", action_id, request.trace_id)
    try:
        registry = get_registry()
        action = registry.get_action(action_id)
        
        if not action:
            raise HTTPException(status_code=404, detail=f"Action {action_id} not found")
        
        if not action.is_active:
            raise HTTPException(status_code=400, detail=f"Action {action_id} is not active")
        
        # Route to appropriate service based on action definition
        service_output = await _route_to_service(action, request)
        
        # Transform output to cell format
        transformed = registry.transform_output(action_id, service_output)
        # Ensure JSON-safe response (no Decimal, numpy, or non-serializable types)
        safe_value = _make_json_safe(transformed.get('value'))
        safe_metadata = _make_json_safe(transformed.get('metadata', {}))
        # Ensure columns_to_create[].values are keyed by row id (string) for frontend
        if isinstance(safe_metadata, dict) and 'columns_to_create' in safe_metadata:
            cols = safe_metadata['columns_to_create']
            if isinstance(cols, list):
                for col in cols:
                    if isinstance(col, dict) and 'values' in col and isinstance(col['values'], dict):
                        col['values'] = {str(k): _make_json_safe(v) for k, v in col['values'].items()}
        return ActionExecutionResponse(
            success=True,
            action_id=action_id,
            value=safe_value,
            display_value=transformed.get('displayValue', '') if isinstance(transformed.get('displayValue'), str) else str(safe_value),
            metadata=safe_metadata if isinstance(safe_metadata, dict) else {}
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error executing action {action_id}: {e}", exc_info=True)
        return ActionExecutionResponse(
            success=False,
            action_id=action_id,
            value=None,
            display_value="",
            metadata={},
            error=str(e)
        )


def _map_company_stage(stage_str: Optional[str]):
    """Map company stage string to Stage enum (round stage / time-since-round; lazy-imports valuation_engine_service)."""
    from app.services.valuation_engine_service import Stage
    if not stage_str:
        return Stage.SERIES_A  # Default

    stage_lower = str(stage_str).lower().strip().replace("-", "_").replace(" ", "_")
    # Also try with spaces for "series a" style
    stage_lower_spaces = str(stage_str).lower().strip()

    stage_mapping = {
        "pre_seed": Stage.PRE_SEED,
        "preseed": Stage.PRE_SEED,
        "seed": Stage.SEED,
        "series_a": Stage.SERIES_A,
        "seriesa": Stage.SERIES_A,
        "series_b": Stage.SERIES_B,
        "seriesb": Stage.SERIES_B,
        "series_c": Stage.SERIES_C,
        "seriesc": Stage.SERIES_C,
        "growth": Stage.GROWTH,
        "late": Stage.LATE,
        "late_stage": Stage.LATE,
        "public": Stage.PUBLIC,
        # Round-stage: single letter / round name
        "a": Stage.SERIES_A,
        "b": Stage.SERIES_B,
        "c": Stage.SERIES_C,
        "round_a": Stage.SERIES_A,
        "rounda": Stage.SERIES_A,
        "round_b": Stage.SERIES_B,
        "roundb": Stage.SERIES_B,
        "round_c": Stage.SERIES_C,
        "roundc": Stage.SERIES_C,
    }
    # With spaces (e.g. "series a")
    stage_mapping["series a"] = Stage.SERIES_A
    stage_mapping["series b"] = Stage.SERIES_B
    stage_mapping["series c"] = Stage.SERIES_C
    stage_mapping["pre seed"] = Stage.PRE_SEED

    return stage_mapping.get(stage_lower) or stage_mapping.get(stage_lower_spaces) or Stage.SERIES_A


def _valuation_inputs_from_request(request: "ActionExecutionRequest", company_data: Dict[str, Any]):
    """Prefer cell/matrix inputs over company_data for stage and last_round_valuation (CFO overrides)."""
    stage_raw = request.inputs.get("stage") or (company_data or {}).get("stage")
    last_round = (
        request.inputs.get("last_round_valuation")
        or request.inputs.get("current_valuation_usd")
        or (company_data or {}).get("current_valuation_usd")
    )
    return _map_company_stage(stage_raw), last_round


def _company_data_from_inputs(inputs: Dict[str, Any]) -> Dict[str, Any]:
    """Build company_data shape from frontend/matrix inputs so services can run with row data only.
    Aligned with SERVICE_ALIGNED_FIELDS for valuation (business_model, sector, category)."""
    revenue = inputs.get("revenue") or inputs.get("arr") or inputs.get("current_arr_usd")
    growth = inputs.get("growth_rate")
    if growth is None and "revenue_growth_annual_pct" in inputs:
        g = inputs["revenue_growth_annual_pct"]
        growth = (float(g) / 100.0) if isinstance(g, (int, float)) and abs(g) < 10 else g
    return {
        "name": inputs.get("name") or inputs.get("company_name") or "Unknown",
        "company_name": inputs.get("company_name") or inputs.get("name") or "Unknown",
        "current_arr_usd": revenue,
        "revenue": revenue,
        "revenue_growth_annual_pct": (growth * 100) if isinstance(growth, (int, float)) and 0 <= growth <= 2 else inputs.get("revenue_growth_annual_pct"),
        "growth_rate": growth if isinstance(growth, (int, float)) else (inputs.get("revenue_growth_annual_pct", 30) / 100.0 if inputs.get("revenue_growth_annual_pct") is not None else 0.3),
        "sector": inputs.get("sector") or "",
        "stage": inputs.get("stage") or "",
        "current_valuation_usd": inputs.get("current_valuation_usd") or inputs.get("last_round_valuation"),
        "total_invested_usd": inputs.get("total_invested_usd") or inputs.get("total_raised"),
        "location": inputs.get("geography") or inputs.get("location"),
        "category": inputs.get("category") or inputs.get("sector"),
        "business_model": inputs.get("business_model"),
    }


def _merge_company_and_inputs(company_data: Dict[str, Any], request: "ActionExecutionRequest") -> Dict[str, Any]:
    """Merge DB company with request.inputs so matrix/frontend values override. Works when company_data is empty (inputs-only)."""
    from_inputs = _company_data_from_inputs(request.inputs or {})
    if not company_data:
        return {k: v for k, v in from_inputs.items() if v is not None}
    merged = dict(company_data)
    for key, value in from_inputs.items():
        if value is not None and value != "":
            merged[key] = value
    return merged


def _has_sufficient_valuation_inputs(merged: Dict[str, Any]) -> bool:
    """True if we have enough to run a valuation (name or revenue/arr)."""
    has_revenue = (merged.get("current_arr_usd") or merged.get("revenue") or merged.get("arr")) not in (None, 0, "")
    has_name = bool(merged.get("name") or merged.get("company_name"))
    return has_revenue or has_name


async def _extract_company_data(company_id: Optional[str]) -> Dict[str, Any]:
    """Fetch company data (backend-agnostic: CompanyDataRepo or Supabase fallback)."""
    if not company_id:
        return {}
    try:
        try:
            from app.core.adapters import get_company_repo
            repo = get_company_repo()
            return repo.get_company(company_id) or {}
        except Exception:
            pass
        client = _get_supabase_client()
        if not client:
            logger.warning("Company data client not available")
            return {}
        response = client.from_("companies").select("*").eq("id", company_id).single().execute()
        if response.data:
            return response.data
        return {}
    except Exception as e:
        logger.error("Error fetching company data: %s", e)
        return {}


async def _extract_funding_rounds(company_id: Optional[str]) -> List[Dict[str, Any]]:
    """Fetch funding rounds for a company (backend-agnostic: CompanyDataRepo or Supabase fallback)."""
    if not company_id:
        return []
    # Try repo first
    try:
        from app.core.adapters import get_company_repo
        repo = get_company_repo()
        rounds = repo.get_funding_rounds(company_id)
        if rounds:
            return rounds
    except Exception:
        pass

    client = _get_supabase_client()
    if not client:
        logger.warning("Supabase client not available")
        return []

    # Try dedicated table (may not exist yet)
    try:
        response = client.from_("funding_rounds").select("*").eq("company_id", company_id).order("date", desc=False).execute()
        if response.data:
            return response.data
    except Exception:
        pass

    # Fall back to JSONB column on companies table
    try:
        company_response = client.from_("companies").select("funding_rounds").eq("id", company_id).single().execute()
        if company_response.data and company_response.data.get("funding_rounds"):
            return company_response.data["funding_rounds"]
    except Exception as e:
        logger.error("Error fetching funding rounds from companies table: %s", e)

    return []


async def _route_to_service(
    action,
    request: ActionExecutionRequest
) -> Any:
    """
    Route action execution to appropriate service.
    
    Calls actual service instances and methods directly.
    """
    service_name = action.service_name.lower()
    action_id = action.action_id.lower()
    
    try:
        # Valuation services (lazy-import to avoid failing router load if valuation_engine has deps issues)
        if 'valuation' in service_name or 'pwerm' in action_id:
            from app.services.valuation_engine_service import (
                ValuationEngineService,
                ValuationRequest,
                ValuationMethod,
                Stage,
            )
            if 'pwerm' in action_id:
                # PWERM: same path as DCF/Auto - ValuationEngineService + ValuationRequest
                company_id = request.company_id or request.inputs.get('company_id')
                company_data = await _extract_company_data(company_id)
                company_data = _merge_company_and_inputs(company_data, request)
                if not _has_sufficient_valuation_inputs(company_data):
                    raise ValueError("Provide company_id or row inputs (e.g. name, ARR/revenue, sector) to run PWERM")
                company_stage, last_round_valuation = _valuation_inputs_from_request(request, company_data)
                revenue = request.inputs.get('revenue') or request.inputs.get('arr') or company_data.get('current_arr_usd') or company_data.get('revenue')
                growth_rate = request.inputs.get('growth_rate') or company_data.get('growth_rate')
                valuation_request = ValuationRequest(
                    company_name=company_data.get('name', 'Unknown'),
                    stage=company_stage,
                    revenue=revenue,
                    growth_rate=growth_rate,
                    last_round_valuation=last_round_valuation,
                    method=ValuationMethod.PWERM,
                    business_model=company_data.get('business_model'),
                    industry=company_data.get('industry') or company_data.get('sector'),
                    category=company_data.get('category'),
                )
                engine = ValuationEngineService()
                result = await engine.calculate_valuation(valuation_request)
                return {
                    'fair_value': float(result.fair_value) if isinstance(result.fair_value, (int, float)) else result.fair_value,
                    'method_used': result.method_used,
                    'explanation': result.explanation,
                    'confidence': float(result.confidence) if isinstance(result.confidence, (int, float)) else result.confidence,
                }

            elif 'dcf' in action_id:
                # DCF: DB + inputs
                company_id = request.company_id or request.inputs.get('company_id')
                company_data = await _extract_company_data(company_id)
                company_data = _merge_company_and_inputs(company_data, request)
                if not _has_sufficient_valuation_inputs(company_data):
                    raise ValueError("Provide company_id or row inputs (name, ARR/revenue) to run DCF")
                company_stage, last_round_valuation = _valuation_inputs_from_request(request, company_data)
                revenue = request.inputs.get('revenue') or request.inputs.get('arr') or company_data.get('current_arr_usd') or company_data.get('revenue')
                growth_rate = request.inputs.get('growth_rate') or company_data.get('growth_rate')
                valuation_request = ValuationRequest(
                    company_name=company_data.get('name', 'Unknown'),
                    stage=company_stage,
                    revenue=revenue,
                    growth_rate=growth_rate,
                    last_round_valuation=last_round_valuation,
                    method=ValuationMethod.DCF,
                    business_model=company_data.get('business_model'),
                    industry=company_data.get('industry') or company_data.get('sector'),
                    category=company_data.get('category'),
                )
                
                engine = ValuationEngineService()
                result = await engine.calculate_valuation(valuation_request)

                return {
                    'fair_value': float(result.fair_value) if isinstance(result.fair_value, (int, float)) else result.fair_value,
                    'method_used': 'DCF',
                    'explanation': result.explanation,
                    'confidence': float(result.confidence) if isinstance(result.confidence, (int, float)) else result.confidence,
                }
            
            elif 'auto' in action_id:
                # Auto: DB + inputs
                company_id = request.company_id or request.inputs.get('company_id')
                company_data = await _extract_company_data(company_id)
                company_data = _merge_company_and_inputs(company_data, request)
                if not _has_sufficient_valuation_inputs(company_data):
                    raise ValueError("Provide company_id or row inputs (name, ARR/revenue) to run Auto valuation")
                company_stage, last_round_valuation = _valuation_inputs_from_request(request, company_data)
                revenue = request.inputs.get('revenue') or request.inputs.get('arr') or company_data.get('current_arr_usd') or company_data.get('revenue')
                growth_rate = request.inputs.get('growth_rate') or company_data.get('growth_rate')
                valuation_request = ValuationRequest(
                    company_name=company_data.get('name', 'Unknown'),
                    stage=company_stage,
                    revenue=revenue,
                    growth_rate=growth_rate,
                    last_round_valuation=last_round_valuation,
                    method=ValuationMethod.AUTO,
                    business_model=company_data.get('business_model'),
                    industry=company_data.get('industry') or company_data.get('sector'),
                    category=company_data.get('category'),
                )
                
                engine = ValuationEngineService()
                result = await engine.calculate_valuation(valuation_request)

                return {
                    'fair_value': float(result.fair_value) if isinstance(result.fair_value, (int, float)) else result.fair_value,
                    'method_used': result.method_used,
                    'explanation': result.explanation,
                    'confidence': float(result.confidence) if isinstance(result.confidence, (int, float)) else result.confidence,
                }

            elif 'opm' in action_id:
                # OPM: DB + inputs
                company_id = request.company_id or request.inputs.get('company_id')
                company_data = await _extract_company_data(company_id)
                company_data = _merge_company_and_inputs(company_data, request)
                if not _has_sufficient_valuation_inputs(company_data):
                    raise ValueError("Provide company_id or row inputs (name, ARR/revenue) to run OPM")
                company_stage, last_round_valuation = _valuation_inputs_from_request(request, company_data)
                valuation_request = ValuationRequest(
                    company_name=company_data.get('name', 'Unknown'),
                    stage=company_stage,
                    revenue=company_data.get('current_arr_usd') or company_data.get('revenue'),
                    growth_rate=company_data.get('growth_rate'),
                    last_round_valuation=last_round_valuation,
                    method=ValuationMethod.OPM,
                    business_model=company_data.get('business_model'),
                    industry=company_data.get('industry') or company_data.get('sector'),
                    category=company_data.get('category'),
                )
                
                engine = ValuationEngineService()
                result = await engine.calculate_valuation(valuation_request)

                return {
                    'fair_value': float(result.fair_value) if isinstance(result.fair_value, (int, float)) else result.fair_value,
                    'method_used': 'OPM',
                    'explanation': result.explanation,
                    'confidence': float(result.confidence) if isinstance(result.confidence, (int, float)) else result.confidence,
                }
            
            elif 'waterfall' in action_id and 'valuation' in action_id:
                # Waterfall: DB + inputs
                company_id = request.company_id or request.inputs.get('company_id')
                company_data = await _extract_company_data(company_id)
                company_data = _merge_company_and_inputs(company_data, request)
                if not _has_sufficient_valuation_inputs(company_data):
                    raise ValueError("Provide company_id or row inputs (name, ARR/revenue) to run Waterfall")
                company_stage, last_round_valuation = _valuation_inputs_from_request(request, company_data)
                revenue = request.inputs.get('revenue') or request.inputs.get('arr') or company_data.get('current_arr_usd') or company_data.get('revenue')
                growth_rate = request.inputs.get('growth_rate') or company_data.get('growth_rate')
                valuation_request = ValuationRequest(
                    company_name=company_data.get('name', 'Unknown'),
                    stage=company_stage,
                    revenue=revenue,
                    growth_rate=growth_rate,
                    last_round_valuation=last_round_valuation,
                    method=ValuationMethod.WATERFALL,
                    business_model=company_data.get('business_model'),
                    industry=company_data.get('industry') or company_data.get('sector'),
                    category=company_data.get('category'),
                )
                
                engine = ValuationEngineService()
                result = await engine.calculate_valuation(valuation_request)

                return {
                    'fair_value': float(result.fair_value) if isinstance(result.fair_value, (int, float)) else result.fair_value,
                    'method_used': 'Waterfall',
                    'explanation': result.explanation,
                    'confidence': float(result.confidence) if isinstance(result.confidence, (int, float)) else result.confidence,
                }
            
            elif 'recent_transaction' in action_id:
                # Recent transaction: DB + inputs
                company_id = request.company_id or request.inputs.get('company_id')
                company_data = await _extract_company_data(company_id)
                company_data = _merge_company_and_inputs(company_data, request)
                if not _has_sufficient_valuation_inputs(company_data):
                    raise ValueError("Provide company_id or row inputs (name, ARR/revenue) to run Recent Transaction")
                company_stage, last_round_valuation = _valuation_inputs_from_request(request, company_data)
                revenue = request.inputs.get('revenue') or request.inputs.get('arr') or company_data.get('current_arr_usd') or company_data.get('revenue')
                growth_rate = request.inputs.get('growth_rate') or company_data.get('growth_rate')
                valuation_request = ValuationRequest(
                    company_name=company_data.get('name', 'Unknown'),
                    stage=company_stage,
                    revenue=revenue,
                    growth_rate=growth_rate,
                    last_round_valuation=company_data.get('current_valuation_usd'),
                    method=ValuationMethod.RECENT_TRANSACTION,
                    business_model=company_data.get('business_model'),
                    industry=company_data.get('industry') or company_data.get('sector'),
                    category=company_data.get('category'),
                )
                
                engine = ValuationEngineService()
                result = await engine.calculate_valuation(valuation_request)

                return {
                    'fair_value': float(result.fair_value) if isinstance(result.fair_value, (int, float)) else result.fair_value,
                    'method_used': 'Recent Transaction',
                    'explanation': result.explanation,
                    'confidence': float(result.confidence) if isinstance(result.confidence, (int, float)) else result.confidence,
                }
            
            elif 'cost_method' in action_id:
                # Cost method: DB + inputs
                company_id = request.company_id or request.inputs.get('company_id')
                company_data = await _extract_company_data(company_id)
                company_data = _merge_company_and_inputs(company_data, request)
                if not _has_sufficient_valuation_inputs(company_data):
                    raise ValueError("Provide company_id or row inputs (name, ARR/revenue) to run Cost Method")
                company_stage, last_round_valuation = _valuation_inputs_from_request(request, company_data)
                valuation_request = ValuationRequest(
                    company_name=company_data.get('name', 'Unknown'),
                    stage=company_stage,
                    revenue=company_data.get('current_arr_usd') or company_data.get('revenue'),
                    growth_rate=company_data.get('growth_rate'),
                    last_round_valuation=last_round_valuation,
                    method=ValuationMethod.COST_METHOD,
                    business_model=company_data.get('business_model'),
                    industry=company_data.get('industry') or company_data.get('sector'),
                    category=company_data.get('category'),
                )
                
                engine = ValuationEngineService()
                result = await engine.calculate_valuation(valuation_request)

                return {
                    'fair_value': float(result.fair_value) if isinstance(result.fair_value, (int, float)) else result.fair_value,
                    'method_used': 'Cost Method',
                    'explanation': result.explanation,
                    'confidence': float(result.confidence) if isinstance(result.confidence, (int, float)) else result.confidence,
                }
            
            elif 'milestone' in action_id and 'valuation' in service_name:
                # Milestone: DB + inputs
                company_id = request.company_id or request.inputs.get('company_id')
                company_data = await _extract_company_data(company_id)
                company_data = _merge_company_and_inputs(company_data, request)
                if not _has_sufficient_valuation_inputs(company_data):
                    raise ValueError("Provide company_id or row inputs (name, ARR/revenue) to run Milestone")
                company_stage, last_round_valuation = _valuation_inputs_from_request(request, company_data)
                revenue = request.inputs.get('revenue') or request.inputs.get('arr') or company_data.get('current_arr_usd') or company_data.get('revenue')
                growth_rate = request.inputs.get('growth_rate') or company_data.get('growth_rate')
                valuation_request = ValuationRequest(
                    company_name=company_data.get('name', 'Unknown'),
                    stage=company_stage,
                    revenue=revenue,
                    growth_rate=growth_rate,
                    last_round_valuation=last_round_valuation,
                    method=ValuationMethod.MILESTONE,
                    business_model=company_data.get('business_model'),
                    industry=company_data.get('industry') or company_data.get('sector'),
                    category=company_data.get('category'),
                )
                
                engine = ValuationEngineService()
                result = await engine.calculate_valuation(valuation_request)

                return {
                    'fair_value': float(result.fair_value) if isinstance(result.fair_value, (int, float)) else result.fair_value,
                    'method_used': 'Milestone',
                    'explanation': result.explanation,
                    'confidence': float(result.confidence) if isinstance(result.confidence, (int, float)) else result.confidence,
                }
        
        # Revenue projection (lazy-import)
        elif 'revenue' in service_name or 'projection' in service_name:
            from app.services.revenue_projection_service import RevenueProjectionService
            base_revenue = request.inputs.get('base_revenue', 1_000_000)
            initial_growth = request.inputs.get('initial_growth', 0.3)
            years = request.inputs.get('years', 5)
            quality_score = request.inputs.get('quality_score', 1.0)
            
            # Call RevenueProjectionService with return_projections=True to get year-by-year data
            projections = RevenueProjectionService.project_revenue_with_decay(
                base_revenue=base_revenue,
                initial_growth=initial_growth,
                years=years,
                quality_score=quality_score,
                stage=request.inputs.get('stage'),
                investor_quality=request.inputs.get('investor_quality'),
                geography=request.inputs.get('geography'),
                sector=request.inputs.get('business_model') or request.inputs.get('sector'),
                company_age_years=request.inputs.get('company_age_years'),
                market_size_tam=request.inputs.get('market_size_tam'),
                return_projections=True
            )
            
            # Transform to MULTI_COLUMN format: create one column per year + optional chart
            if isinstance(projections, list) and len(projections) > 0:
                # Get row_id from request to populate values per row
                row_id = request.row_id
                
                # Generate unique suffix to avoid column ID collisions
                import time
                unique_suffix = int(time.time() * 1000) % 1000000  # Use timestamp modulo for shorter IDs
                
                # Build columns_to_create: one column per year
                columns_to_create = []
                for proj in projections:
                    year = proj.get('year', 0)
                    revenue = proj.get('revenue', 0.0)
                    # Add unique suffix to prevent collisions
                    col_id = f"revenue_{year}_{unique_suffix}"
                    col_name = f"Revenue {year}"
                    
                    # Create values dict for this row
                    values = {row_id: revenue}
                    
                    columns_to_create.append({
                        'id': col_id,
                        'name': col_name,
                        'type': 'currency',
                        'values': values
                    })
                
                # Build chart_to_create: line chart showing revenue over time
                # Use 'tableau' renderType to ensure it's displayed in ChartViewport
                chart_to_create = {
                    'type': 'line',
                    'title': 'Revenue Projection',
                    'data': {
                        'labels': [f"Year {p.get('year', 0)}" for p in projections],
                        'datasets': [{
                            'label': 'Revenue',
                            'data': [p.get('revenue', 0.0) for p in projections],
                            'backgroundColor': 'rgba(66, 133, 244, 0.2)',
                            'borderColor': '#4285F4',
                            'borderWidth': 2
                        }]
                    },
                    'renderType': 'tableau',  # Changed from 'basic' to 'tableau' for ChartViewport display
                    'config': {
                        'width': '100%',
                        'height': 300,
                        'interactive': True
                    }
                }
                
                # Return MULTI_COLUMN format
                # Primary value is the final year revenue
                final_revenue = projections[-1].get('revenue', 0.0) if projections else 0.0
                return {
                    'value': final_revenue,
                    'columns_to_create': columns_to_create,
                    'chart_to_create': chart_to_create
                }
            elif isinstance(projections, list) and len(projections) == 0:
                # Empty list - return error message
                logger.warning(f"Revenue projection returned empty list for row {request.row_id}")
                return {
                    'value': 0.0,
                    'error': 'No revenue projections available',
                    'columns_to_create': [],
                    'chart_to_create': None
                }
            else:
                # Invalid format - log error and return fallback
                logger.error(f"Invalid projections format for row {request.row_id}: {type(projections)}")
                final_value = 0.0
                if isinstance(projections, list) and projections:
                    final_value = projections[-1].get('revenue', 0.0) if isinstance(projections[-1], dict) else (projections[-1] if isinstance(projections[-1], (int, float)) else 0.0)
                elif isinstance(projections, (int, float)):
                    final_value = projections
                return {
                    'value': final_value,
                    'error': 'Invalid projections format',
                    'columns_to_create': [],
                    'chart_to_create': None
                }
        
        # Financial formulas
        elif 'financial' in service_name:
            if 'irr' in action_id:
                cash_flows = request.inputs.get('cash_flows', [])
                if not cash_flows:
                    raise ValueError("cash_flows input required for IRR calculation")
                
                result = FinancialTools.calculate_irr(cash_flows)
                return result.get('irr', 0) if isinstance(result, dict) else result
            
            elif 'npv' in action_id:
                discount_rate = request.inputs.get('discount_rate', 0.1)
                cash_flows = request.inputs.get('cash_flows', [])
                if not cash_flows:
                    raise ValueError("cash_flows input required for NPV calculation")
                
                result = FinancialTools.calculate_npv(discount_rate, cash_flows)
                return result.get('npv', 0) if isinstance(result, dict) else result
            
            elif 'moic' in action_id:
                exit_value = request.inputs.get('exit_value', 0)
                investment = request.inputs.get('investment', 0)
                if investment == 0:
                    return 0
                return exit_value / investment
            
            elif 'cagr' in action_id:
                beginning_value = request.inputs.get('beginning_value', 0)
                ending_value = request.inputs.get('ending_value', 0)
                years = request.inputs.get('years', 1)
                if beginning_value == 0 or years == 0:
                    return 0
                return ((ending_value / beginning_value) ** (1 / years)) - 1
        
        # Market intelligence - find comparables (DB + inputs)
        elif 'market' in service_name and 'comparables' in action_id:
            from app.services.market_intelligence_service import MarketIntelligenceService
            company_id = request.company_id or request.inputs.get('company_id')
            company_data = await _extract_company_data(company_id)
            company_data = _merge_company_and_inputs(company_data, request)
            geography = request.inputs.get('geography') or company_data.get('location') or company_data.get('geography') or 'US'
            sector = request.inputs.get('sector') or company_data.get('sector') or company_data.get('category') or 'SaaS'
            arr = request.inputs.get('arr') or company_data.get('current_arr_usd')
            
            # Call MarketIntelligenceService
            market_service = MarketIntelligenceService()
            comparables = await market_service.find_companies_by_geography_sector(
                geography=geography,
                sector=sector,
                limit=request.inputs.get('limit', 10)
            )
            
            # Extract citations from search results
            # Note: MarketIntelligenceService uses Tavily search internally
            # We need to get the raw search results to extract citations
            citations = []
            try:
                # Build search queries similar to what MarketIntelligenceService does
                search_queries = market_service._build_geography_sector_queries(geography, sector, None)
                
                # Execute searches to get raw results with URLs
                if not market_service.session:
                    async with market_service:
                        pass  # Initialize session
                
                for query in search_queries[:3]:  # Limit to first 3 queries to avoid too many citations
                    search_result = await market_service._execute_tavily_search(query)
                    results = search_result.get('results', [])
                    for result in results[:5]:  # Limit to top 5 results per query
                        url = result.get('url', '')
                        title = result.get('title', '')
                        if url and title:
                            citations.append({
                                'id': f"tavily_{hash(url)}",
                                'source': title[:100] or 'Market Research',
                                'url': url,
                                'title': title
                            })
            except Exception as e:
                logger.warning(f"Error extracting citations from market search: {e}")
            
            # Convert to list of dicts
            comparables_list = [{
                'name': comp.name,
                'sector': comp.sector,
                'geography': comp.geography,
                'stage': comp.stage,
                'estimated_valuation': comp.estimated_valuation,
                'growth_momentum': comp.growth_momentum,
                'investment_readiness': comp.investment_readiness
            } for comp in comparables]
            
            # Return comparables with citations
            return {
                'comparables': comparables_list,
                'citations': citations
            }
        
        # Chart generation - wire up to ChartGenerationSkill
        elif 'chart' in service_name:
            try:
                chart_skill = ChartGenerationSkill()
                chart_data = request.inputs.get('data') or request.inputs.get('context') or {}
                chart_type = request.inputs.get('chart_type', 'auto')
                
                result = await chart_skill.execute({
                    'data': chart_data,
                    'chart_type': chart_type,
                    'companies': request.inputs.get('companies'),
                    'context': request.inputs.get('context')
                })
                
                if result.get('success') and result.get('charts'):
                    # Return first chart or all charts
                    charts = result.get('charts', [])
                    if len(charts) > 0:
                        return {
                            'type': charts[0].get('type', 'bar'),
                            'title': charts[0].get('title', 'Generated Chart'),
                            'data': charts[0].get('data', {}),
                            'renderType': charts[0].get('renderType', 'tableau'),
                            'charts': charts,  # Include all charts
                            'chart_count': len(charts)
                        }
                
                # Fallback if no charts generated
                return {
                    'type': 'bar',
                    'title': 'Generated Chart',
                    'data': chart_data,
                    'renderType': 'basic',
                    'message': 'Chart generation completed but no charts returned'
                }
            except Exception as e:
                logger.error(f"Chart generation error: {e}")
                # Fallback to placeholder
                return {
                    'type': 'bar',
                    'title': 'Generated Chart',
                    'data': request.inputs.get('data', {}),
                    'renderType': 'basic',
                    'error': str(e)
                }
        
        # Document services (lazy-import)
        elif 'document' in service_name:
            from app.services.document_query_service import DocumentQueryService
            document_id = request.inputs.get('document_id')
            if document_id is None or document_id == '':
                raise ValueError("document_id required for document actions")
            # Coerce to str: Supabase ids can be int (44) from frontend, backend expects str
            document_id = str(document_id)

            doc_service = DocumentQueryService()
            if 'extract' in action_id:
                extraction_type = request.inputs.get('extraction_type', 'structured')
                result = await doc_service.extract_structured_data(document_id, extraction_type)
                return result
            elif 'analyze' in action_id:
                result = await doc_service.analyze_document(document_id)
                return result
        
        # Waterfall services
        elif 'waterfall' in service_name or 'waterfall' in action_id:
            from app.services.advanced_cap_table import CapTableCalculator
            company_id = request.company_id or request.inputs.get('company_id')
            exit_value = request.inputs.get('exit_value', 0)
            
            if not company_id:
                raise ValueError("company_id required for waterfall calculations")
            
            company_data = await _extract_company_data(company_id)
            funding_rounds = await _extract_funding_rounds(company_id)
            
            cap_table_calc = CapTableCalculator()
            
            if 'breakpoints' in action_id:
                # Calculate waterfall breakpoints
                base_exit = Decimal(str(exit_value))
                breakpoints = cap_table_calc.calculate_waterfall_breakpoints(
                    base_case_exit=base_exit,
                    bull_multiplier=2.0,
                    bear_multiplier=0.5
                )
                return breakpoints
            
            elif 'exit_scenarios' in action_id:
                # Calculate exit scenario waterfall
                exit_type = request.inputs.get('exit_type', 'M&A')
                result = cap_table_calc.calculate_exit_waterfall(Decimal(str(exit_value)))
                return {
                    'distributions': result.to_dict('records') if hasattr(result, 'to_dict') else result,
                    'exit_type': exit_type,
                    'exit_value': exit_value
                }
            
            else:
                # Standard liquidation waterfall
                cap_table = company_data.get('cap_table', {})
                liquidation_preferences = company_data.get('liquidation_preferences', {})
                
                result = cap_table_calc.calculate_liquidation_waterfall(
                    exit_value=exit_value,
                    cap_table=cap_table,
                    liquidation_preferences=liquidation_preferences,
                    funding_rounds=funding_rounds
                )
                return result
        
        # Cap table services
        elif 'cap_table' in service_name or 'cap_table' in action_id:
            from app.services.pre_post_cap_table import PrePostCapTable
            company_id = request.company_id or request.inputs.get('company_id')
            
            if not company_id:
                raise ValueError("company_id required for cap table calculations")
            
            company_data = await _extract_company_data(company_id)
            funding_rounds = await _extract_funding_rounds(company_id)
            
            if 'calculate' in action_id:
                # Full cap table history
                cap_table_service = PrePostCapTable()
                # Prepare company data structure
                company_data_with_rounds = {
                    'funding_rounds': funding_rounds,
                    'company': company_data.get('name', 'Unknown'),
                    'stage': company_data.get('stage', 'Series A')
                }
                result = cap_table_service.calculate_full_cap_table_history(company_data_with_rounds)
                return result
            
            elif 'ownership' in action_id:
                # Calculate ownership at a point in time
                as_of_date = request.inputs.get('as_of_date')
                cap_table_calc = CapTableCalculator()
                
                # If we have funding rounds, we can calculate ownership
                if funding_rounds:
                    # Use the cap table service to get historical ownership
                    cap_table_service = PrePostCapTable()
                    company_data_with_rounds = {
                        'funding_rounds': funding_rounds,
                        'company': company_data.get('name', 'Unknown')
                    }
                    history = cap_table_service.calculate_full_cap_table_history(company_data_with_rounds)
                    
                    if history and history.get('current_cap_table'):
                        return {
                            'ownership': history['current_cap_table'],
                            'as_of_date': as_of_date or 'current'
                        }
                
                # Fallback to direct calculation
                cap_table = company_data.get('cap_table', {})
                ownership = cap_table_calc.calculate_ownership(
                    cap_table=cap_table,
                    as_of_date=as_of_date
                )
                return ownership
            
            elif 'dilution' in action_id:
                # Calculate dilution path
                cap_table_service = PrePostCapTable()
                company_data_with_rounds = {
                    'funding_rounds': funding_rounds,
                    'company': company_data.get('name', 'Unknown')
                }
                result = cap_table_service.calculate_full_cap_table_history(company_data_with_rounds)
                
                # Extract dilution information from history
                if result and result.get('history'):
                    dilution_path = []
                    for snapshot in result['history']:
                        dilution_path.append({
                            'round': snapshot.get('round_name'),
                            'date': snapshot.get('date'),
                            'pre_money_ownership': snapshot.get('pre_money_ownership', {}),
                            'post_money_ownership': snapshot.get('post_money_ownership', {}),
                            'dilution': snapshot.get('dilution_without_pro_rata', {})
                        })
                    return {
                        'dilution_path': dilution_path,
                        'ownership_evolution': result.get('ownership_evolution', {})
                    }
                
                return {'dilution_path': [], 'ownership_evolution': {}}

            elif 'entry_impact' in action_id:
                # Model our fund's entry into this company
                our_investment = float(request.inputs.get('our_investment', 0))
                round_name = request.inputs.get('round_name', 'Series B')
                if our_investment <= 0:
                    raise ValueError("our_investment must be a positive dollar amount")

                cap_table_service = PrePostCapTable()

                # Ensure funding rounds exist — reconstruct if needed
                if not funding_rounds:
                    from app.services.intelligent_gap_filler import IntelligentGapFiller
                    gap_filler = IntelligentGapFiller()
                    funding_rounds = gap_filler.generate_stage_based_funding_rounds(company_data) or []

                company_data_with_rounds = {
                    'funding_rounds': funding_rounds,
                    'company': company_data.get('name', 'Unknown'),
                    'stage': company_data.get('stage', 'Series A'),
                    'valuation': company_data.get('valuation') or company_data.get('current_valuation_usd') or 100_000_000,
                }
                result = cap_table_service.calculate_our_entry_impact(
                    company_data=company_data_with_rounds,
                    our_investment=our_investment,
                    round_name=round_name,
                )
                return result

        # Ownership & Return Analysis services (DB + inputs)
        elif service_name.startswith('ownership.') or service_name == 'ownership' or action_id.startswith('ownership.'):
            from app.services.ownership_return_analyzer import OwnershipReturnAnalyzer
            company_id = request.company_id or request.inputs.get('company_id')
            company_data = await _extract_company_data(company_id)
            company_data = _merge_company_and_inputs(company_data, request)
            if not _has_sufficient_valuation_inputs(company_data):
                raise ValueError("Provide company_id or row inputs (name, ARR/revenue) for ownership analysis")
            
            analyzer = OwnershipReturnAnalyzer()
            
            if 'analyze' in action_id:
                # Analyze ownership scenarios
                investment_amount = request.inputs.get('investment_amount', 0)
                pre_money_valuation = request.inputs.get('pre_money_valuation', company_data.get('current_valuation_usd', 0))
                
                result = analyzer.calculate_ownership_scenarios(
                    company_data=company_data,
                    investment_amount=investment_amount,
                    fund_size=request.inputs.get('fund_size', 100_000_000)
                )
                return result
            
            elif 'return_scenarios' in action_id:
                # Calculate return scenarios
                investment_amount = request.inputs.get('investment_amount', 0)
                exit_value = request.inputs.get('exit_value', 0)
                
                # Use ownership analyzer to calculate return scenarios
                # This would typically use calculate_fund_impact or similar
                fund_impact = analyzer.calculate_fund_impact(
                    investment_amount=investment_amount,
                    expected_return=exit_value,
                    fund_size=request.inputs.get('fund_size', 100_000_000)
                )
                
                return {
                    'fund_impact': fund_impact,
                    'investment_amount': investment_amount,
                    'exit_value': exit_value,
                    'moic': exit_value / investment_amount if investment_amount > 0 else 0
                }
        
        # M&A Workflow services
        elif service_name.startswith('ma.') or service_name == 'ma' or action_id.startswith('ma.'):
            if 'model_acquisition' in action_id:
                # Model M&A transaction
                acquirer = request.inputs.get('acquirer')
                target = request.inputs.get('target')
                deal_rationale = request.inputs.get('deal_rationale')
                
                if not acquirer or not target:
                    raise ValueError("acquirer and target required for M&A modeling")
                
                ma_service = MAWorkflowService()
                async with ma_service:
                    result = await ma_service.model_acquisition(
                        acquirer=acquirer,
                        target=target,
                        deal_rationale=deal_rationale
                    )
                
                # Convert dataclass to dict
                if hasattr(result, '__dict__'):
                    return result.__dict__
                return result
            
            elif 'transactions' in action_id:
                # Search for M&A transactions - similar to PWERM routes
                target = request.inputs.get('target')
                industry = request.inputs.get('industry', 'SaaS')
                
                try:
                    client = _get_supabase_client()
                    if client:
                        # Query ma_transactions table similar to PWERM routes
                        query = client.table("ma_transactions").select("*")
                        
                        # Filter by target company name if provided
                        if target:
                            query = query.ilike("target_company", f"%{target}%")
                        
                        # Filter by industry if provided
                        if industry:
                            query = query.ilike("industry", f"%{industry}%")
                        
                        response = query.limit(100).execute()
                        
                        if response.data:
                            return {
                                'transactions': response.data,
                                'target': target,
                                'industry': industry,
                                'count': len(response.data)
                            }
                        else:
                            return {
                                'transactions': [],
                                'target': target,
                                'industry': industry,
                                'count': 0,
                                'message': 'No transactions found'
                            }
                except Exception as e:
                    logger.error(f"Error searching M&A transactions: {e}")
                    return {
                        'transactions': [],
                        'target': target,
                        'industry': industry,
                        'error': str(e)
                    }
        
        # Fund metrics - replace placeholder
        elif service_name.startswith('fund.') or service_name == 'fund' or action_id.startswith('fund.'):
            from app.services.ownership_return_analyzer import OwnershipReturnAnalyzer
            fund_id = request.fund_id or request.inputs.get('fund_id')
            if not fund_id:
                raise ValueError("fund_id required for fund metrics")
            
            # Get portfolio companies for the fund
            try:
                client = _get_supabase_client()
                if client:
                    # Get portfolio companies
                    portfolio_response = client.from_("portfolio_companies").select("*, companies(*)").eq("fund_id", fund_id).execute()
                    companies = portfolio_response.data if portfolio_response.data else []
                    
                    # Calculate fund metrics using OwnershipReturnAnalyzer
                    analyzer = OwnershipReturnAnalyzer()
                    total_nav = 0
                    total_invested = 0
                    total_distributed = 0
                    
                    for pc in companies:
                        company = pc.get('companies', {})
                        investment = pc.get('investment_amount', 0) or 0
                        current_valuation = company.get('current_valuation_usd', 0) or 0
                        ownership_pct = pc.get('ownership_pct', 0) or 0
                        
                        total_invested += investment
                        # NAV = ownership % * current valuation
                        total_nav += (ownership_pct / 100) * current_valuation
                        
                        # Get actual distributed amounts from exited companies
                        status = pc.get('status') or company.get('status', 'active')
                        if status == 'exited':
                            exit_value = pc.get('exit_value_usd') or company.get('exit_value_usd', 0) or 0
                            # Distributed amount = ownership % * exit value
                            distributed = (ownership_pct / 100) * exit_value
                            total_distributed += distributed
                    
                    dpi = total_distributed / total_invested if total_invested > 0 else 0
                    tvpi = total_nav / total_invested if total_invested > 0 else 0
                    
                    return {
                        'total_nav': total_nav,
                        'total_invested': total_invested,
                        'total_distributed': total_distributed,
                        'dpi': dpi,
                        'tvpi': tvpi,
                        'company_count': len(companies)
                    }
            except Exception as e:
                logger.error(f"Error calculating fund metrics: {e}")
            
            # Fallback to placeholder
            return {
                'total_nav': 50_000_000,
                'total_invested': 30_000_000,
                'dpi': 0.5,
                'tvpi': 1.67
            }
        
        # DPI Sankey (must run before generic portfolio branch so chart dict is returned)
        elif ('dpi' in action_id and 'sankey' in action_id.lower()):
            fund_id = request.fund_id or request.inputs.get('fund_id')
            if not fund_id:
                raise ValueError("fund_id required for DPI Sankey visualization")
            
            try:
                client = _get_supabase_client()
                if client:
                    # Get portfolio companies
                    portfolio_response = client.from_("portfolio_companies").select("*, companies(*)").eq("fund_id", fund_id).execute()
                    companies = portfolio_response.data if portfolio_response.data else []
                    
                    # Fetch actual fund name
                    fund_name = "Fund"
                    try:
                        fund_resp = client.from_("portfolios").select("name").eq("id", fund_id).limit(1).execute()
                        if fund_resp.data and fund_resp.data[0].get("name"):
                            fund_name = fund_resp.data[0]["name"]
                    except Exception:
                        pass  # fall back to "Fund"

                    # Build Sankey data for DPI flow: Fund → Companies → Exits → Distributions
                    nodes = [
                        {"id": 0, "name": fund_name, "level": 0},
                    ]
                    links = []
                    
                    total_invested = 0
                    total_distributed = 0
                    node_id = 1
                    
                    for pc in companies:
                        company = pc.get('companies', {})
                        company_name = company.get('name', f"Company {node_id}")
                        investment = pc.get('investment_amount', 0) or pc.get('total_invested_usd', 0) or 0
                        ownership_pct = pc.get('ownership_pct', 0) or pc.get('ownership_percentage', 0) or 0
                        status = pc.get('status') or company.get('status', 'active')
                        
                        total_invested += investment
                        
                        # Add company node
                        nodes.append({
                            "id": node_id,
                            "name": company_name,
                            "level": 1,
                            "investment": investment
                        })
                        
                        # Link: Fund → Company
                        links.append({
                            "source": 0,
                            "target": node_id,
                            "value": investment
                        })
                        
                        # If exited, add exit and distribution nodes
                        if status == 'exited':
                            exit_value = pc.get('exit_value_usd') or company.get('exit_value_usd', 0) or 0
                            distributed = (ownership_pct / 100) * exit_value
                            total_distributed += distributed
                            
                            # Exit node
                            exit_node_id = node_id + 1000
                            nodes.append({
                                "id": exit_node_id,
                                "name": f"{company_name} Exit",
                                "level": 2,
                                "exit_value": exit_value
                            })
                            
                            # Distribution node
                            dist_node_id = node_id + 2000
                            if not any(n["id"] == dist_node_id for n in nodes):
                                nodes.append({
                                    "id": dist_node_id,
                                    "name": "LP Distributions",
                                    "level": 3
                                })
                            
                            # Links: Company → Exit → Distribution
                            links.append({
                                "source": node_id,
                                "target": exit_node_id,
                                "value": exit_value
                            })
                            links.append({
                                "source": exit_node_id,
                                "target": dist_node_id,
                                "value": distributed
                            })
                        
                        node_id += 1
                    
                    dpi = total_distributed / total_invested if total_invested > 0 else 0

                    # Guard: if no links (no companies with investment amounts), return message instead of broken chart
                    if not links:
                        return {
                            'type': 'message',
                            'title': f'DPI: {dpi:.2f}x',
                            'data': {'message': 'No portfolio companies with investment amounts found. Add investment amounts to see DPI flow.'},
                            'metrics': {
                                'total_invested': total_invested,
                                'total_distributed': total_distributed,
                                'dpi': dpi,
                                'company_count': len(companies),
                            },
                        }

                    return {
                        'type': 'sankey',
                        'title': f'DPI Flow: {dpi:.2f}x',
                        'data': {
                            'nodes': nodes,
                            'links': links
                        },
                        'metrics': {
                            'total_invested': total_invested,
                            'total_distributed': total_distributed,
                            'dpi': dpi
                        },
                        'renderType': 'tableau'
                    }
            except Exception as e:
                logger.error(f"Error generating DPI Sankey: {e}")
                return {
                    'type': 'sankey',
                    'title': 'DPI Flow',
                    'data': {'nodes': [], 'links': []},
                    'error': str(e)
                }
        
        # Portfolio services - implement actual calculations
        elif 'portfolio' in service_name:
            fund_id = request.fund_id or request.inputs.get('fund_id')
            if not fund_id:
                raise ValueError("fund_id required for portfolio calculations")
            
            try:
                client = _get_supabase_client()
                if client:
                    portfolio_response = client.from_("portfolio_companies").select("*, companies(*)").eq("fund_id", fund_id).execute()
                    companies = portfolio_response.data if portfolio_response.data else []
                    
                    if 'total_nav' in action_id:
                        total_nav = 0
                        for pc in companies:
                            company = pc.get('companies', {})
                            current_valuation = company.get('current_valuation_usd', 0) or 0
                            ownership_pct = pc.get('ownership_pct', 0) or 0
                            total_nav += (ownership_pct / 100) * current_valuation
                        return total_nav
                    
                    elif 'total_invested' in action_id:
                        total_invested = sum(pc.get('investment_amount', 0) or 0 for pc in companies)
                        return total_invested
                    
                    elif 'dpi' in action_id:
                        # DPI = distributed / paid-in
                        total_invested = sum(pc.get('investment_amount', 0) or 0 for pc in companies)
                        # Get actual distributed amounts from exited companies
                        total_distributed = 0
                        for pc in companies:
                            company = pc.get('companies', {})
                            # Check if company has exited
                            status = pc.get('status') or company.get('status', 'active')
                            if status == 'exited':
                                exit_value = pc.get('exit_value_usd') or company.get('exit_value_usd', 0) or 0
                                ownership_pct = pc.get('ownership_pct', 0) or 0
                                # Distributed amount = ownership % * exit value
                                distributed = (ownership_pct / 100) * exit_value
                                total_distributed += distributed
                        return total_distributed / total_invested if total_invested > 0 else 0
                    
                    elif 'tvpi' in action_id:
                        # TVPI = total value / paid-in
                        total_invested = sum(pc.get('investment_amount', 0) or 0 for pc in companies)
                        total_nav = 0
                        for pc in companies:
                            company = pc.get('companies', {})
                            current_valuation = company.get('current_valuation_usd', 0) or 0
                            ownership_pct = pc.get('ownership_pct', 0) or 0
                            total_nav += (ownership_pct / 100) * current_valuation
                        return total_nav / total_invested if total_invested > 0 else 0
                    
                    elif 'optimize' in action_id:
                        # Portfolio optimization - call position sizing service
                        fund_id = request.fund_id or request.inputs.get('fund_id')
                        constraints = request.inputs.get('constraints', {})
                        
                        if not fund_id:
                            raise ValueError("fund_id required for portfolio optimization")
                        
                        try:
                            # Try to import and use position sizing engine
                            try:
                                from app.services.position_sizing_engine import get_sizing_engine, InvestmentOpportunity
                                
                                # Get current portfolio companies as opportunities
                                opportunities = []
                                for pc in companies:
                                    company = pc.get('companies', {})
                                    company_id = pc.get('company_id')
                                    investment = pc.get('investment_amount', 0) or 0
                                    current_valuation = company.get('current_valuation_usd', 0) or 0
                                    
                                    # Calculate expected return (simplified: valuation growth)
                                    # In real implementation, this would use historical returns
                                    expected_return = 0.20  # Default 20% expected return
                                    volatility = 0.30  # Default 30% volatility
                                    
                                    opportunities.append(InvestmentOpportunity(
                                        opportunity_id=company_id,
                                        name=company.get('name', 'Unknown'),
                                        expected_return=expected_return,
                                        volatility=volatility,
                                        probability_success=0.5,
                                        minimum_investment=investment * 0.5,
                                        maximum_investment=investment * 2.0,
                                        sector=company.get('sector', ''),
                                        stage=company.get('stage', '')
                                    ))
                                
                                # Get fund size
                                fund_response = client.from_("funds").select("size").eq("id", fund_id).single().execute()
                                total_fund_size = fund_response.data.get('size', 100_000_000) if fund_response.data else 100_000_000
                                
                                # Call optimization engine
                                engine = get_sizing_engine()
                                result = engine.optimize_portfolio_allocation(
                                    current_portfolio=[],
                                    new_opportunities=opportunities,
                                    total_fund_size=total_fund_size,
                                    optimization_target=constraints.get('target', 'max_sharpe')
                                )
                                
                                return {
                                    'optimal_weights': result.get('optimal_weights', []),
                                    'expected_return': result.get('expected_return', 0),
                                    'volatility': result.get('volatility', 0),
                                    'sharpe_ratio': result.get('sharpe_ratio', 0),
                                    'efficient_frontier': result.get('efficient_frontier', []),
                                    'opportunities': [
                                        {
                                            'id': opp.opportunity_id,
                                            'name': opp.name,
                                            'optimal_weight': result.get('optimal_weights', [])[i] if i < len(result.get('optimal_weights', [])) else 0
                                        }
                                        for i, opp in enumerate(opportunities)
                                    ]
                                }
                            except ImportError:
                                # Fallback: simple equal-weight optimization
                                logger.warning("Position sizing engine not available, using equal-weight fallback")
                                num_companies = len(companies)
                                if num_companies == 0:
                                    return {
                                        'optimal_weights': [],
                                        'expected_return': 0,
                                        'volatility': 0,
                                        'sharpe_ratio': 0,
                                        'message': 'No companies in portfolio'
                                    }
                                
                                equal_weight = 1.0 / num_companies
                                return {
                                    'optimal_weights': [equal_weight] * num_companies,
                                    'expected_return': 0.15,
                                    'volatility': 0.25,
                                    'sharpe_ratio': 0.6,
                                    'efficient_frontier': [],
                                    'opportunities': [
                                        {
                                            'id': pc.get('company_id'),
                                            'name': pc.get('companies', {}).get('name', 'Unknown'),
                                            'optimal_weight': equal_weight
                                        }
                                        for pc in companies
                                    ],
                                    'message': 'Using equal-weight optimization (position sizing engine not available)'
                                }
                        except Exception as e:
                            logger.error(f"Error optimizing portfolio: {e}")
                            # Fallback: return equal weights
                            num_companies = len(companies)
                            return {
                                'optimal_weights': [1.0 / num_companies] * num_companies if num_companies > 0 else [],
                                'expected_return': 0.15,
                                'volatility': 0.25,
                                'sharpe_ratio': 0.6,
                                'message': f'Optimization failed: {str(e)}'
                            }
            except Exception as e:
                logger.error(f"Error calculating portfolio metrics: {e}")
            
            # Fallback
            return 0
        
        # NAV services - improved calculation with manual edit support
        elif 'nav' in service_name:
            if 'timeseries' in action_id or 'timeseries_company' in action_id:
                fund_id = request.fund_id or request.inputs.get('fund_id')
                company_id = request.company_id or request.inputs.get('company_id')
                
                if not fund_id:
                    raise ValueError("fund_id required for NAV timeseries")
                
                # Implement NAV timeseries from historical data
                try:
                    client = _get_supabase_client()
                    if client:
                        # Check for manual edits first (matrix_edits table)
                        if company_id:
                            # Single company NAV time series
                            edits_response = client.from_("matrix_edits")\
                                .select("value, edited_at, column_id")\
                                .eq("company_id", company_id)\
                                .eq("fund_id", fund_id)\
                                .in_("column_id", ["nav", "valuation"])\
                                .order("edited_at")\
                                .execute()
                            
                            # Get portfolio company for ownership
                            pc_response = client.from_("portfolio_companies")\
                                .select("ownership_pct")\
                                .eq("fund_id", fund_id)\
                                .eq("company_id", company_id)\
                                .single().execute()
                            
                            ownership_pct = pc_response.data.get('ownership_pct', 0) if pc_response.data else 0
                            
                            # Build time series from edits and historical data
                            nav_series = []
                            dates = []
                            
                            # Add manual edits
                            for edit in (edits_response.data or []):
                                if edit.get('column_id') == 'valuation':
                                    valuation = float(edit.get('value', 0))
                                    nav = (ownership_pct / 100) * valuation
                                    nav_series.append(nav)
                                    dates.append(edit.get('edited_at', ''))
                            
                            # Add historical metrics if available
                            history_response = client.from_("company_metrics_history")\
                                .select("current_valuation_usd, recorded_at")\
                                .eq("company_id", company_id)\
                                .order("recorded_at")\
                                .execute()
                            
                            for record in (history_response.data or []):
                                valuation = record.get('current_valuation_usd', 0) or 0
                                nav = (ownership_pct / 100) * valuation
                                nav_series.append(nav)
                                dates.append(record.get('recorded_at', ''))
                            
                            # Sort by date
                            if nav_series:
                                sorted_pairs = sorted(zip(dates, nav_series), key=lambda x: x[0])
                                dates, nav_series = zip(*sorted_pairs) if sorted_pairs else ([], [])
                            
                            return {
                                'series': list(nav_series) if nav_series else [],
                                'dates': list(dates) if dates else [],
                                'final_value': nav_series[-1] if nav_series else 0,
                                'data_points': len(nav_series)
                            }
                        else:
                            # Portfolio-level NAV time series
                            portfolio_response = client.from_("portfolio_companies")\
                                .select("company_id, ownership_pct")\
                                .eq("fund_id", fund_id)\
                                .execute()
                            
                            company_ids = [pc.get('company_id') for pc in (portfolio_response.data or [])]
                            
                            if company_ids:
                                # Query historical metrics
                                history_response = client.from_("company_metrics_history")\
                                    .select("company_id, current_valuation_usd, recorded_at")\
                                    .in_("company_id", company_ids)\
                                    .order("recorded_at")\
                                    .execute()
                                
                                # Build ownership map
                                ownership_map = {pc.get('company_id'): pc.get('ownership_pct', 0) 
                                                for pc in (portfolio_response.data or [])}
                                
                                # Group by date and calculate NAV
                                nav_by_date = {}
                                for record in (history_response.data or []):
                                    date = record.get('recorded_at', '')[:10]  # Get date part
                                    if not date:
                                        continue
                                    
                                    company_id = record.get('company_id')
                                    valuation = record.get('current_valuation_usd', 0) or 0
                                    ownership_pct = ownership_map.get(company_id, 0)
                                    
                                    nav_contribution = (ownership_pct / 100) * valuation
                                    
                                    if date not in nav_by_date:
                                        nav_by_date[date] = 0
                                    nav_by_date[date] += nav_contribution
                                
                                # Convert to sorted series
                                sorted_dates = sorted(nav_by_date.keys())
                                series = [nav_by_date[date] for date in sorted_dates]
                                final_value = series[-1] if series else 0
                                
                                return {
                                    'series': series,
                                    'dates': sorted_dates,
                                    'final_value': final_value,
                                    'data_points': len(series)
                                }
                
                except Exception as e:
                    logger.error(f"Error calculating NAV timeseries: {e}")
                
                # Fallback
                return {
                    'series': [1_000_000, 1_200_000, 1_500_000],
                    'final_value': 1_500_000,
                    'message': 'Using placeholder data'
                }
            elif 'forecast' in action_id:
                # NAV forecast using linear regression (like pacing page)
                fund_id = request.fund_id or request.inputs.get('fund_id')
                periods = request.inputs.get('periods', 12)  # Default 12 months
                
                if not fund_id:
                    raise ValueError("fund_id required for NAV forecast")
                
                try:
                    client = _get_supabase_client()
                    if client:
                        # Get NAV timeseries data (reuse timeseries logic)
                        portfolio_response = client.from_("portfolio_companies")\
                            .select("company_id, ownership_pct")\
                            .eq("fund_id", fund_id)\
                            .execute()
                        
                        company_ids = [pc.get('company_id') for pc in (portfolio_response.data or [])]
                        
                        if company_ids:
                            # Query historical metrics
                            history_response = client.from_("company_metrics_history")\
                                .select("company_id, current_valuation_usd, recorded_at")\
                                .in_("company_id", company_ids)\
                                .order("recorded_at")\
                                .execute()
                            
                            # Build ownership map
                            ownership_map = {pc.get('company_id'): pc.get('ownership_pct', 0) 
                                            for pc in (portfolio_response.data or [])}
                            
                            # Group by date and calculate NAV
                            nav_by_date = {}
                            for record in (history_response.data or []):
                                date = record.get('recorded_at', '')[:10]
                                if not date:
                                    continue
                                
                                company_id = record.get('company_id')
                                valuation = record.get('current_valuation_usd', 0) or 0
                                ownership_pct = ownership_map.get(company_id, 0)
                                
                                nav_contribution = (ownership_pct / 100) * valuation
                                
                                if date not in nav_by_date:
                                    nav_by_date[date] = 0
                                nav_by_date[date] += nav_contribution
                            
                            # Convert to sorted series
                            sorted_dates = sorted(nav_by_date.keys())
                            nav_values = [nav_by_date[date] for date in sorted_dates]
                            
                            if len(nav_values) < 2:
                                # Not enough data for regression
                                return {
                                    'series': nav_values,
                                    'forecast': nav_values,
                                    'dates': sorted_dates,
                                    'forecast_dates': sorted_dates,
                                    'slope': 0,
                                    'intercept': nav_values[-1] if nav_values else 0,
                                    'message': 'Insufficient data for regression'
                                }
                            
                            # Linear regression (like pacing page)
                            x = list(range(len(nav_values)))
                            y = nav_values
                            
                            n = len(x)
                            sum_x = sum(x)
                            sum_y = sum(y)
                            sum_xy = sum(x[i] * y[i] for i in range(n))
                            sum_xx = sum(xi * xi for xi in x)
                            
                            # Calculate slope and intercept
                            denominator = (n * sum_xx - sum_x * sum_x)
                            if denominator == 0:
                                slope = 0
                                intercept = sum_y / n if n > 0 else 0
                            else:
                                slope = (n * sum_xy - sum_x * sum_y) / denominator
                                intercept = (sum_y - slope * sum_x) / n
                            
                            # Generate forecast
                            forecast_values = []
                            forecast_dates = []
                            last_date = sorted_dates[-1] if sorted_dates else None
                            
                            for i in range(1, periods + 1):
                                forecast_x = len(nav_values) + i - 1
                                forecast_y = slope * forecast_x + intercept
                                forecast_values.append(max(0, forecast_y))  # NAV can't be negative
                                
                                # Generate forecast date (approximate monthly)
                                if last_date:
                                    # Simple date increment (assuming monthly)
                                    from datetime import datetime, timedelta
                                    try:
                                        last_dt = datetime.fromisoformat(last_date.replace('Z', '+00:00'))
                                        forecast_dt = last_dt + timedelta(days=30 * i)
                                        forecast_dates.append(forecast_dt.strftime('%Y-%m-%d'))
                                    except:
                                        forecast_dates.append(f"Forecast {i}")
                                else:
                                    forecast_dates.append(f"Forecast {i}")
                            
                            # Combine historical and forecast
                            combined_series = nav_values + forecast_values
                            combined_dates = sorted_dates + forecast_dates
                            
                            return {
                                'series': nav_values,
                                'forecast': forecast_values,
                                'combined_series': combined_series,
                                'dates': sorted_dates,
                                'forecast_dates': forecast_dates,
                                'combined_dates': combined_dates,
                                'slope': slope,
                                'intercept': intercept,
                                'final_value': nav_values[-1] if nav_values else 0,
                                'forecast_final': forecast_values[-1] if forecast_values else 0,
                                'data_points': len(nav_values),
                                'forecast_periods': periods
                            }
                
                except Exception as e:
                    logger.error(f"Error forecasting NAV: {e}")
                
                # Fallback
                return {
                    'series': [1_000_000, 1_200_000, 1_500_000],
                    'forecast': [1_600_000, 1_700_000],
                    'slope': 100000,
                    'intercept': 900000,
                    'message': 'Using placeholder forecast data'
                }
            elif 'calculate_portfolio' in action_id:
                # Portfolio-level NAV
                fund_id = request.fund_id or request.inputs.get('fund_id')
                if not fund_id:
                    raise ValueError("fund_id required for portfolio NAV")
                
                try:
                    client = _get_supabase_client()
                    if client:
                        portfolio_response = client.from_("portfolio_companies")\
                            .select("*, companies(*)")\
                            .eq("fund_id", fund_id)\
                            .execute()
                        
                        total_nav = 0
                        for pc in (portfolio_response.data or []):
                            company = pc.get('companies', {})
                            # Check for manual valuation edit first
                            company_id = pc.get('company_id')
                            edits_response = client.from_("matrix_edits")\
                                .select("value")\
                                .eq("company_id", company_id)\
                                .eq("fund_id", fund_id)\
                                .eq("column_id", "valuation")\
                                .order("edited_at", desc=True)\
                                .limit(1)\
                                .execute()
                            
                            if edits_response.data and edits_response.data[0].get('value'):
                                current_valuation = float(edits_response.data[0].get('value', 0))
                            else:
                                current_valuation = company.get('current_valuation_usd', 0) or 0
                            
                            ownership_pct = pc.get('ownership_pct', 0) or 0
                            nav = (ownership_pct / 100) * current_valuation
                            total_nav += nav
                        
                        return {'nav': total_nav, 'company_count': len(portfolio_response.data or [])}
                except Exception as e:
                    logger.error(f"Error calculating portfolio NAV: {e}")
                
                return {'nav': 0}
            else:
                # Company-level NAV (calculate_company or default)
                company_id = request.company_id or request.inputs.get('company_id')
                fund_id = request.fund_id or request.inputs.get('fund_id')
                
                if company_id and fund_id:
                    try:
                        client = _get_supabase_client()
                        if client:
                            # Check for manual valuation edit first
                            edits_response = client.from_("matrix_edits")\
                                .select("value")\
                                .eq("company_id", company_id)\
                                .eq("fund_id", fund_id)\
                                .eq("column_id", "valuation")\
                                .order("edited_at", desc=True)\
                                .limit(1)\
                                .execute()
                            
                            # Get portfolio company record
                            pc_response = client.from_("portfolio_companies")\
                                .select("*, companies(*)")\
                                .eq("fund_id", fund_id)\
                                .eq("company_id", company_id)\
                                .single().execute()
                            
                            if pc_response.data:
                                pc = pc_response.data
                                company = pc.get('companies', {})
                                
                                # Use manual edit if available, otherwise use company valuation
                                if edits_response.data and edits_response.data[0].get('value'):
                                    current_valuation = float(edits_response.data[0].get('value', 0))
                                    manual = True
                                else:
                                    current_valuation = company.get('current_valuation_usd', 0) or 0
                                    manual = False
                                
                                ownership_pct = pc.get('ownership_pct', 0) or 0
                                nav = (ownership_pct / 100) * current_valuation
                                
                                return {
                                    'nav': nav,
                                    'valuation': current_valuation,
                                    'ownership_pct': ownership_pct,
                                    'manual': manual
                                }
                    except Exception as e:
                        logger.error(f"Error calculating NAV: {e}")
                
                return {'nav': 0, 'valuation': 0, 'ownership_pct': 0}
        
        # Advanced debt structures (DB + inputs)
        elif 'debt' in service_name or 'debt' in action_id:
            from app.services.advanced_debt_structures_service import AdvancedDebtStructures
            company_id = request.company_id or request.inputs.get('company_id')
            company_data = await _extract_company_data(company_id) if company_id else {}
            company_data = _merge_company_and_inputs(company_data, request)
            if not _has_sufficient_valuation_inputs(company_data):
                raise ValueError("Provide company_id or row inputs (name, ARR/revenue) for debt analysis")
            
            try:
                debt_service = AdvancedDebtStructures()
                debt_structure = debt_service.analyze_debt_structure(company_data)
                
                # Convert dataclass to dict; add value for registry/grid display
                if hasattr(debt_structure, '__dict__'):
                    out = dict(debt_structure.__dict__)
                    out['value'] = getattr(debt_structure, 'total_debt', 0)
                    return out
                return debt_structure
            except Exception as e:
                logger.error(f"Error analyzing debt structure: {e}")
                raise
        
        # Fund level waterfall
        elif 'fund' in service_name and 'waterfall' in action_id:
            fund_id = request.fund_id or request.inputs.get('fund_id')
            if not fund_id:
                raise ValueError("fund_id required for fund waterfall")
            
            try:
                client = _get_supabase_client()
                if client:
                    # Get portfolio companies with exits
                    portfolio_response = client.from_("portfolio_companies").select("*, companies(*)").eq("fund_id", fund_id).execute()
                    companies = portfolio_response.data if portfolio_response.data else []
                    
                    # Calculate fund waterfall: Gross Proceeds → Return of Capital → Preferred Return → GP Catch-up → Carried Interest → LP Share
                    lp_investment = sum(pc.get('investment_amount', 0) or 0 for pc in companies)
                    total_exits = 0
                    distributions = []
                    
                    for pc in companies:
                        company = pc.get('companies', {})
                        status = pc.get('status') or company.get('status', 'active')
                        if status == 'exited':
                            exit_value = pc.get('exit_value_usd') or company.get('exit_value_usd', 0) or 0
                            ownership_pct = pc.get('ownership_pct', 0) or 0
                            distributed = (ownership_pct / 100) * exit_value
                            total_exits += distributed
                            distributions.append({
                                'company': company.get('name', 'Unknown'),
                                'amount': distributed,
                                'exit_value': exit_value,
                                'multiple': exit_value / (pc.get('investment_amount', 1) or 1)
                            })
                    
                    # Fund waterfall parameters (from deck agent)
                    preferred_return_rate = 0.08
                    catch_up_percentage = 0.80
                    carried_interest_rate = 0.20
                    hurdle_rate = 0.08
                    
                    # Calculate waterfall steps
                    waterfall_steps = []
                    cumulative = lp_investment
                    
                    # Gross Proceeds
                    waterfall_steps.append({
                        'name': 'Gross Proceeds',
                        'value': total_exits,
                        'cumulative': total_exits,
                        'type': 'total'
                    })
                    
                    # Return of Capital
                    return_of_capital = min(lp_investment, total_exits)
                    cumulative = total_exits - return_of_capital
                    waterfall_steps.append({
                        'name': 'Return of Capital',
                        'value': -return_of_capital,
                        'cumulative': cumulative,
                        'type': 'deduction'
                    })
                    
                    # Preferred Return (8%)
                    preferred_return = min(lp_investment * preferred_return_rate, cumulative)
                    cumulative -= preferred_return
                    waterfall_steps.append({
                        'name': 'Preferred Return (8%)',
                        'value': -preferred_return,
                        'cumulative': cumulative,
                        'type': 'deduction'
                    })
                    
                    # GP Catch-up (if hurdle met)
                    if cumulative > lp_investment * (1 + hurdle_rate):
                        gp_catchup = cumulative * catch_up_percentage * carried_interest_rate
                        cumulative -= gp_catchup
                        waterfall_steps.append({
                            'name': 'GP Catch-up',
                            'value': -gp_catchup,
                            'cumulative': cumulative,
                            'type': 'deduction'
                        })
                    
                    # Carried Interest (20%)
                    if cumulative > 0:
                        carry = cumulative * carried_interest_rate
                        cumulative -= carry
                        waterfall_steps.append({
                            'name': 'Carried Interest (20%)',
                            'value': -carry,
                            'cumulative': cumulative,
                            'type': 'deduction'
                        })
                    
                    # LP Share (remaining)
                    waterfall_steps.append({
                        'name': 'LP Share (80%)',
                        'value': -cumulative,
                        'cumulative': 0,
                        'type': 'deduction'
                    })
                    
                    # Final Distribution
                    waterfall_steps.append({
                        'name': 'Final Distribution',
                        'value': 0,
                        'cumulative': 0,
                        'type': 'total'
                    })
                    
                    return {
                        'type': 'waterfall',
                        'title': 'Fund Waterfall Analysis',
                        'data': waterfall_steps,
                        'metrics': {
                            'lp_investment': lp_investment,
                            'total_exits': total_exits,
                            'dpi': total_exits / lp_investment if lp_investment > 0 else 0,
                            'distributions': distributions
                        },
                        'renderType': 'tableau'
                    }
            except Exception as e:
                logger.error(f"Error calculating fund waterfall: {e}")
                return {
                    'type': 'waterfall',
                    'title': 'Fund Waterfall',
                    'data': [],
                    'error': str(e)
                }
        
        # Follow-on strategy - implement actual logic using services
        elif 'follow' in service_name or 'strategy' in action_id:
            company_id = request.company_id or request.inputs.get('company_id')
            fund_id = request.fund_id or request.inputs.get('fund_id')
            
            if not company_id or not fund_id:
                raise ValueError("company_id and fund_id required for follow-on strategy")
            
            try:
                company_data = await _extract_company_data(company_id)
                company_data = _merge_company_and_inputs(company_data, request)
                funding_rounds = await _extract_funding_rounds(company_id)
                
                if not company_data:
                    raise ValueError(f"Company data not found for company_id: {company_id}")
                
                # Get current portfolio position
                client = _get_supabase_client()
                if not client:
                    raise ValueError("Database client not available")
                
                pc_response = client.from_("portfolio_companies").select("*").eq("fund_id", fund_id).eq("company_id", company_id).single().execute()
                if not pc_response.data:
                    raise ValueError(f"Portfolio company not found for fund_id: {fund_id}, company_id: {company_id}")
                
                portfolio_company = pc_response.data
                current_ownership_pct = portfolio_company.get('ownership_pct', 0) or 0
                current_investment = portfolio_company.get('investment_amount', 0) or 0
                
                # Get fund size for context
                fund_response = client.from_("funds").select("size").eq("id", fund_id).single().execute()
                fund_size = fund_response.data.get('size', 100_000_000) if fund_response.data else 100_000_000
                
                from app.services.pre_post_cap_table import PrePostCapTable
                from app.services.ownership_return_analyzer import OwnershipReturnAnalyzer
                # Use PrePostCapTable to calculate pro-rata investment needed
                cap_table_service = PrePostCapTable()
                analyzer = OwnershipReturnAnalyzer()
                
                # Get upcoming round information (from inputs or estimate from company stage)
                upcoming_round_size = request.inputs.get('round_size', 0)
                upcoming_pre_money = request.inputs.get('pre_money_valuation', 0)
                
                # If not provided, estimate from company stage and current valuation
                if not upcoming_round_size or not upcoming_pre_money:
                    current_valuation = company_data.get('current_valuation_usd', 0) or 0
                    stage = company_data.get('stage', 'Series A').lower().replace(' ', '_')
                    benchmarks = analyzer.ROUND_BENCHMARKS.get(stage, analyzer.ROUND_BENCHMARKS['series_a'])
                    
                    upcoming_round_size = upcoming_round_size or benchmarks['typical_round_size']
                    upcoming_pre_money = upcoming_pre_money or current_valuation
                
                # Calculate pro-rata investment needed using actual service
                from decimal import Decimal
                current_ownership_decimal = Decimal(str(current_ownership_pct / 100))
                round_size_decimal = Decimal(str(upcoming_round_size))
                pre_money_decimal = Decimal(str(upcoming_pre_money))
                
                pro_rata_calc = cap_table_service.calculate_pro_rata_investment(
                    current_ownership=current_ownership_decimal,
                    new_money_raised=round_size_decimal,
                    pre_money_valuation=pre_money_decimal
                )
                
                pro_rata_amount = pro_rata_calc['pro_rata_investment_needed']
                ownership_with_pro_rata = pro_rata_calc['ownership_with_pro_rata']
                ownership_without_pro_rata = pro_rata_calc['ownership_without_pro_rata']
                dilution_if_no_pro_rata = pro_rata_calc['dilution_if_no_pro_rata']
                has_pro_rata_rights = pro_rata_calc['has_pro_rata_rights']
                
                # Calculate ownership scenarios using OwnershipReturnAnalyzer
                from app.services.ownership_return_analyzer import InvestmentType
                
                # Determine investment type based on current ownership
                if current_ownership_pct >= 10:
                    investment_type = InvestmentType.PRO_RATA
                elif current_ownership_pct >= 5:
                    investment_type = InvestmentType.FOLLOW
                else:
                    investment_type = InvestmentType.FOLLOW
                
                # Prepare company data for ownership scenario calculation
                company_data_for_scenarios = {
                    **company_data,
                    'our_previous_ownership': current_ownership_pct / 100,
                    'valuation': upcoming_pre_money
                }
                
                ownership_scenarios = analyzer.calculate_ownership_scenarios(
                    company_data=company_data_for_scenarios,
                    investment_amount=pro_rata_amount,
                    investment_type=investment_type,
                    fund_size=fund_size
                )
                
                # Determine strategy recommendation based on analysis
                position_size_pct = (pro_rata_amount / fund_size) * 100
                reserve_recommendation = ownership_scenarios.get('reserve_recommendation', pro_rata_amount * 2)
                
                # Strategy logic
                if not has_pro_rata_rights:
                    strategy = 'pass'
                    recommendation = f'No pro-rata rights (current ownership {current_ownership_pct:.1f}% < 5% threshold). Consider passing unless strategic value.'
                    amount = 0
                elif current_ownership_pct < 3:
                    strategy = 'pass'
                    recommendation = f'Ownership too small ({current_ownership_pct:.1f}%). Dilution risk outweighs benefits.'
                    amount = 0
                elif position_size_pct > 5:
                    strategy = 'selective'
                    recommendation = f'Large position size ({position_size_pct:.1f}% of fund). Consider partial pro-rata to manage concentration risk.'
                    amount = pro_rata_amount * 0.5  # Half pro-rata
                elif current_ownership_pct >= 10:
                    strategy = 'pro-rata'
                    recommendation = f'Strong position ({current_ownership_pct:.1f}% ownership). Maintain with full pro-rata investment.'
                    amount = pro_rata_amount
                else:
                    strategy = 'pro-rata'
                    recommendation = f'Maintain ownership percentage. Pro-rata investment recommended.'
                    amount = pro_rata_amount
                
                return {
                    'strategy': strategy,
                    'recommendation': recommendation,
                    'amount': amount,
                    'pro_rata_amount': pro_rata_amount,
                    'current_ownership': current_ownership_pct,
                    'ownership_with_pro_rata': ownership_with_pro_rata,
                    'ownership_without_pro_rata': ownership_without_pro_rata,
                    'dilution_if_no_pro_rata': dilution_if_no_pro_rata,
                    'has_pro_rata_rights': has_pro_rata_rights,
                    'round_size': upcoming_round_size,
                    'pre_money_valuation': upcoming_pre_money,
                    'position_size_pct': position_size_pct,
                    'reserve_recommendation': reserve_recommendation,
                    'ownership_scenarios': ownership_scenarios
                }
                
            except Exception as e:
                logger.error(f"Error calculating follow-on strategy: {e}", exc_info=True)
                # Return a safe default rather than failing completely
                return {
                    'strategy': 'selective',
                    'recommendation': f'Unable to calculate detailed strategy: {str(e)}. Recommend manual review.',
                    'amount': 0,
                    'error': str(e)
                }
        
        # Market Intelligence Services
        elif 'market' in service_name and 'timing' in action_id:
            # Market timing analysis
            sector = request.inputs.get('sector')
            geography = request.inputs.get('geography')
            indicators = request.inputs.get('indicators')
            
            if not sector or not geography:
                raise ValueError("sector and geography required for market timing analysis")
            
            from app.services.market_intelligence_service import MarketIntelligenceService
            market_service = MarketIntelligenceService()
            async with market_service:
                result = await market_service.analyze_market_timing(
                    sector=sector,
                    geography=geography,
                    indicators=indicators
                )
            
            # Convert dataclass to dict if needed
            if hasattr(result, '__dict__'):
                return result.__dict__
            return result
        
        elif 'market' in service_name and 'investment_readiness' in action_id:
            # Investment readiness scoring
            companies_input = request.inputs.get('companies', [])
            criteria = request.inputs.get('criteria')
            
            if not companies_input:
                raise ValueError("companies array required for investment readiness scoring")
            
            # Convert company inputs to CompanyIntelligence objects
            from app.services.market_intelligence_service import CompanyIntelligence
            
            company_intelligence_list = []
            for company_item in companies_input:
                if isinstance(company_item, dict):
                    # Convert dict to CompanyIntelligence
                    company_intel = CompanyIntelligence(
                        name=company_item.get('name', 'Unknown'),
                        sector=company_item.get('sector', 'Technology'),
                        geography=company_item.get('geography', 'US'),
                        stage=company_item.get('stage', 'Series A'),
                        last_funding_date=company_item.get('last_funding_date'),
                        last_funding_amount=company_item.get('last_funding_amount'),
                        estimated_valuation=company_item.get('estimated_valuation'),
                        employee_count=company_item.get('employee_count'),
                        growth_momentum=company_item.get('growth_momentum'),
                        investment_readiness=company_item.get('investment_readiness'),
                        market_timing_score=company_item.get('market_timing_score'),
                        key_metrics=company_item.get('key_metrics', {}),
                        competitive_position=company_item.get('competitive_position'),
                        investors=company_item.get('investors', []),
                        news_sentiment=company_item.get('news_sentiment')
                    )
                    company_intelligence_list.append(company_intel)
                elif isinstance(company_item, CompanyIntelligence):
                    company_intelligence_list.append(company_item)
                else:
                    # Try to fetch company data by ID
                    company_id = str(company_item)
                    company_data = await _extract_company_data(company_id)
                    if company_data:
                        company_intel = CompanyIntelligence(
                            name=company_data.get('name', 'Unknown'),
                            sector=company_data.get('sector', 'Technology'),
                            geography=company_data.get('location', 'US'),
                            stage=company_data.get('stage', 'Series A'),
                            estimated_valuation=company_data.get('current_valuation_usd'),
                            employee_count=company_data.get('employee_count')
                        )
                        company_intelligence_list.append(company_intel)
            
            if not company_intelligence_list:
                raise ValueError("No valid companies found for investment readiness scoring")
            
            from app.services.market_intelligence_service import MarketIntelligenceService
            market_service = MarketIntelligenceService()
            async with market_service:
                result = await market_service.score_investment_readiness(
                    companies=company_intelligence_list,
                    criteria=criteria
                )
            
            # Convert to list of dicts if needed
            if isinstance(result, list):
                return [item.__dict__ if hasattr(item, '__dict__') else item for item in result]
            return result
        
        elif 'market' in service_name and 'sector_landscape' in action_id:
            # Sector landscape visualization
            sector = request.inputs.get('sector')
            geography = request.inputs.get('geography')
            
            if not sector or not geography:
                raise ValueError("sector and geography required for sector landscape")
            
            from app.services.market_intelligence_service import MarketIntelligenceService
            market_service = MarketIntelligenceService()
            async with market_service:
                result = await market_service.generate_sector_landscape(
                    sector=sector,
                    geography=geography
                )
            
            # Convert to chart config format
            if hasattr(result, '__dict__'):
                landscape_dict = result.__dict__
                return {
                    'type': 'scatter',
                    'title': f'{sector} Landscape in {geography}',
                    'data': landscape_dict,
                    'renderType': 'tableau'
                }
            return result
        
        # Company Scoring Services (DB + inputs)
        elif 'scoring' in service_name or 'scoring' in action_id:
            from app.services.company_scoring_visualizer import CompanyScoringVisualizer
            if 'score_company' in action_id:
                company_id = request.company_id or request.inputs.get('company_id')
                company_data = await _extract_company_data(company_id)
                company_data = _merge_company_and_inputs(company_data, request)
                if not _has_sufficient_valuation_inputs(company_data):
                    raise ValueError("Provide company_id or row inputs (name, ARR/revenue) to score company")
                
                scoring_service = CompanyScoringVisualizer()
                result = await scoring_service.score_company(company_data)
                
                # Convert dataclass to dict; add value for registry/grid display
                if hasattr(result, '__dict__'):
                    out = dict(result.__dict__)
                    out['value'] = getattr(result, 'overall_score', None)
                    return out
                return result
            
            elif 'portfolio_dashboard' in action_id:
                # Portfolio dashboard
                fund_id = request.fund_id or request.inputs.get('fund_id')
                
                if not fund_id:
                    raise ValueError("fund_id required for portfolio dashboard")
                
                # Get portfolio companies
                try:
                    client = _get_supabase_client()
                    if not client:
                        raise ValueError("Database client not available")
                    
                    portfolio_response = client.from_("portfolio_companies")\
                        .select("*, companies(*)")\
                        .eq("fund_id", fund_id)\
                        .execute()
                    
                    companies = [pc.get('companies', {}) for pc in (portfolio_response.data or [])]
                    
                    scoring_service = CompanyScoringVisualizer()
                    result = await scoring_service.generate_portfolio_dashboard(companies)
                    
                    # Convert to dict if needed
                    if hasattr(result, '__dict__'):
                        return result.__dict__
                    return result
                except Exception as e:
                    logger.error(f"Error generating portfolio dashboard: {e}")
                    raise
        
        # Intelligent Gap Filler (DB + inputs)
        elif 'gap_filler' in service_name or 'gap_filler' in action_id:
            from app.services.intelligent_gap_filler import IntelligentGapFiller
            company_id = request.company_id or request.inputs.get('company_id')
            company_data = await _extract_company_data(company_id)
            company_data = _merge_company_and_inputs(company_data, request)
            if not _has_sufficient_valuation_inputs(company_data):
                raise ValueError("Provide company_id or row inputs (name, ARR/revenue) for gap filler")
            
            gap_filler = IntelligentGapFiller()
            
            if 'ai_impact' in action_id:
                # AI impact analysis
                result = gap_filler.analyze_ai_impact(company_data)
                return result
            
            elif 'ai_valuation' in action_id:
                # AI-adjusted valuation
                result = await gap_filler.calculate_ai_adjusted_valuation(company_data)
                return result
            
            elif 'market_opportunity' in action_id:
                # Market opportunity analysis
                search_content = request.inputs.get('search_content')
                tam_data = request.inputs.get('tam_data')
                result = await gap_filler.calculate_market_opportunity(
                    company_data,
                    search_content=search_content,
                    tam_data=tam_data
                )
                return result
            
            elif 'momentum' in action_id:
                # Company momentum analysis
                result = gap_filler.analyze_company_momentum(company_data)
                return result
            
            elif 'fund_fit' in action_id:
                # Fund fit scoring
                fund_id = request.fund_id or request.inputs.get('fund_id')
                
                # Get inferred metrics
                missing_fields = ['valuation', 'revenue', 'burn_rate', 'runway']
                inferred_metrics = await gap_filler.infer_from_funding_cadence(
                    company_data,
                    missing_fields
                )
                
                # Get fund context
                context = {}
                if fund_id:
                    try:
                        client = _get_supabase_client()
                        if client:
                            fund_response = client.from_("funds")\
                                .select("size")\
                                .eq("id", fund_id)\
                                .single().execute()
                            if fund_response.data:
                                context['fund_size'] = fund_response.data.get('size', 100_000_000)
                    except Exception as e:
                        logger.warning(f"Error fetching fund context: {e}")
                
                result = gap_filler.score_fund_fit(
                    company_data,
                    inferred_metrics,
                    context=context
                )
                return result
        
        # M&A Synergy
        elif 'ma' in service_name and 'synergy' in action_id:
            from app.services.ma_workflow_service import MAWorkflowService
            acquirer = request.inputs.get('acquirer')
            target = request.inputs.get('target')
            deal_rationale = request.inputs.get('deal_rationale')
            synergy_types = request.inputs.get('synergy_types')
            
            if not acquirer or not target:
                raise ValueError("acquirer and target required for synergy calculation")
            
            ma_service = MAWorkflowService()
            async with ma_service:
                result = await ma_service.calculate_synergy_value(
                    acquirer=acquirer,
                    target=target,
                    synergy_types=synergy_types
                )
            
            return result
        
        # Unified MCP Orchestrator Skills
        elif 'skill.' in action_id or service_name == 'unified_mcp_orchestrator':
            try:
                from app.services.unified_mcp_orchestrator import UnifiedMCPOrchestrator
                from app.core.dependencies import ServiceFactory
                
                # Create orchestrator instance
                orchestrator = ServiceFactory.create_orchestrator()
                
                # Map action_id to skill name
                skill_name = action_id.replace('skill.', '').replace('_', '-')
                
                # Map to orchestrator skill names (must match UnifiedMCPOrchestrator._initialize_skill_registry)
                skill_mapping = {
                    'company-data-fetch': 'company-data-fetcher',
                    'funding-aggregation': 'funding-aggregator',
                    'market-research': 'market-sourcer',
                    'competitive-analysis': 'competitive-intelligence',
                    'valuation-engine': 'valuation-engine',
                    'pwerm-calculator': 'pwerm-calculator',
                    'financial-analysis': 'financial-analyzer',
                    'scenario-analysis': 'scenario-generator',
                    'deal-comparison': 'deal-comparer',
                    'deck-storytelling': 'deck-storytelling',
                    'excel-generation': 'excel-generator',
                    'memo-generation': 'memo-writer',
                    'chart-generation': 'chart-generator',
                    'cap-table-generation': 'cap-table-generator',
                    'portfolio-analysis': 'portfolio-analyzer',
                    'fund-metrics-calculator': 'fund-metrics-calculator',
                    'stage-analysis': 'stage-analyzer',
                    'exit-modeling': 'exit-modeler',
                }
                
                actual_skill = skill_mapping.get(skill_name, skill_name)
                
                # Check if skill exists
                if actual_skill not in orchestrator.skills:
                    logger.warning(f"Skill {actual_skill} not found in orchestrator")
                    return {'error': f'Skill {actual_skill} not available'}
                
                # Prepare inputs for skill execution (matrix sends company_id/fund_id; skills expect company/companies/fund_context)
                skill_inputs = {
                    **request.inputs,
                    'company_id': request.company_id,
                    'fund_id': request.fund_id
                }
                
                # Normalize so orchestrator skills get what they expect (core fix: skills don't read company_id)
                company_id = request.company_id or request.inputs.get('company_id')
                if company_id and not skill_inputs.get('company') and not skill_inputs.get('companies'):
                    company_data = await _extract_company_data(company_id)
                    if company_data:
                        name = company_data.get('name') or company_data.get('company_name') or company_id
                        skill_inputs['company'] = name
                        skill_inputs['prompt_handle'] = skill_inputs.get('prompt_handle') or name
                        # Some skills (e.g. deal-comparer, deck) expect "companies" list
                        if actual_skill in ('deal-comparer', 'deck-storytelling', 'stage-analyzer'):
                            skill_inputs['companies'] = skill_inputs.get('companies') or [company_data]
                    else:
                        skill_inputs['company'] = str(company_id)
                        skill_inputs['prompt_handle'] = str(company_id)
                
                fund_id = request.fund_id or request.inputs.get('fund_id')
                if fund_id and not skill_inputs.get('fund_context'):
                    try:
                        client = _get_supabase_client()
                        if client:
                            fund_res = client.from_("funds").select("id, size, name").eq("id", fund_id).single().execute()
                            if fund_res.data:
                                skill_inputs['fund_context'] = {
                                    'fund_id': fund_id,
                                    'fund_size': fund_res.data.get('size'),
                                    'fund_name': fund_res.data.get('name'),
                                }
                    except Exception as e:
                        logger.debug("Could not load fund_context for skill: %s", e)
                
                # Execute skill
                skill_handler = orchestrator.skills[actual_skill]['handler']
                result = await skill_handler(skill_inputs)
                
                return result
                
            except Exception as e:
                logger.error(f"Error executing orchestrator skill {action_id}: {e}", exc_info=True)
                return {'error': str(e)}
        
        # Chain: run multiple cell actions in sequence, passing outputs forward
        if action_id == 'chain.execute':
            steps = request.inputs.get('steps', [])
            if not steps:
                raise ValueError("'steps' array required for chain.execute")
            shared_inputs = request.inputs.get('shared_inputs', {})
            results = []
            carry: Dict[str, Any] = {}
            registry = get_registry()
            for i, step in enumerate(steps):
                step_action_id = step.get('action_id')
                if not step_action_id:
                    raise ValueError(f"Step {i} is missing 'action_id'")
                step_action = registry.get_action(step_action_id)
                if not step_action:
                    raise ValueError(f"Action '{step_action_id}' not found in registry (step {i})")
                # Merge: shared_inputs < previous step carry < this step's own inputs
                step_inputs = {**shared_inputs, **carry, **step.get('inputs', {})}
                step_request = ActionExecutionRequest(
                    action_id=step_action_id,
                    row_id=request.row_id,
                    column_id=request.column_id,
                    inputs=step_inputs,
                    mode=request.mode,
                    fund_id=step_inputs.get('fund_id') or request.fund_id,
                    company_id=step_inputs.get('company_id') or request.company_id,
                    trace_id=request.trace_id,
                )
                step_result = await _route_to_service(step_action, step_request)
                results.append({'action_id': step_action_id, 'result': step_result})
                # Carry forward key scalar outputs to the next step's inputs
                if isinstance(step_result, dict):
                    carry = {
                        k: v for k, v in step_result.items()
                        if k in (
                            'fair_value', 'value', 'recommendation', 'strategy',
                            'company_id', 'fund_id', 'nav', 'ownership_pct',
                        ) and v is not None
                    }
            return {
                'steps': results,
                'final_result': results[-1]['result'] if results else None,
                'step_count': len(results),
            }

        # Scenario composition
        if action_id == 'scenario.compose':
            from app.services.matrix_scenario_service import MatrixScenarioService
            
            query = request.inputs.get('query')
            if not query:
                raise ValueError("'query' parameter is required for scenario.compose")
            
            # Get matrix data from inputs
            matrix_data = request.inputs.get('matrix_data', {})
            if not matrix_data:
                raise ValueError("'matrix_data' parameter is required for scenario.compose")
            
            service = MatrixScenarioService()
            result = await service.apply_scenario_to_matrix(
                query=query,
                matrix_data=matrix_data,
                fund_id=request.fund_id
            )
            
            return result
        
        # Default: no handler for this action (unknown action_id); return minimal valid structure
        logger.warning("No service handler for action: %s", action_id)
        return {"value": None, "metadata": {"reason": "unknown_action"}}
        
    except Exception as e:
        logger.error(f"Error routing to service for action {action_id}: {e}", exc_info=True)
        raise
