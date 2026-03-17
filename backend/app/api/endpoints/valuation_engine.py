"""
Valuation Engine Endpoints
"""

from fastapi import APIRouter, HTTPException
from typing import Dict, Any, List, Optional
from pydantic import BaseModel
import logging

from app.services.valuation_engine_service import ValuationEngineService

router = APIRouter()
logger = logging.getLogger(__name__)


class ValuationRequest(BaseModel):
    company_data: Dict[str, Any] = {}     # optional when company_id is set
    company_id: Optional[str] = None      # UUID — pulls financials from Supabase
    branch_id: Optional[str] = None       # scenario branch overrides
    method: str = "dcf"                   # dcf, multiples, pwerm
    comparables: List[Dict[str, Any]] = []
    assumptions: Dict[str, Any] = {}
    branch_name: Optional[str] = None     # custom branch name for persisted result


class PWERMRequest(BaseModel):
    company_data: Dict[str, Any] = {}
    company_id: Optional[str] = None
    branch_id: Optional[str] = None
    exit_scenarios: List[Dict[str, Any]] = []
    probabilities: List[float] = []
    time_horizons: List[int] = []
    discount_rate: float = 0.12
    branch_name: Optional[str] = None


class ComparablesRequest(BaseModel):
    company_data: Dict[str, Any] = {}
    company_id: Optional[str] = None
    branch_id: Optional[str] = None
    peer_companies: List[Dict[str, Any]] = []
    metrics: List[str] = ["revenue_multiple", "ebitda_multiple"]
    branch_name: Optional[str] = None


def _resolve_company_data(request: ValuationRequest) -> Dict[str, Any]:
    """Pull company financials + branch overrides, merge with request data."""
    from app.services.company_data_pull import resolve_company_financials
    merged, _ = resolve_company_financials(
        company_id=request.company_id,
        branch_id=request.branch_id,
        overrides=dict(request.company_data),
    )
    return merged


@router.post("/value-company")
async def value_company(request: ValuationRequest):
    """Perform comprehensive company valuation.

    Always persists results to a scenario branch.
    """
    try:
        engine = ValuationEngineService()
        company_data = _resolve_company_data(request)

        result = await engine.value_company(
            company_data=company_data,
            method=request.method,
            comparables=request.comparables,
            assumptions=request.assumptions
        )

        # Persist to branch
        persist_meta = {}
        if request.company_id:
            from app.services.analysis_persistence_service import AnalysisPersistenceService
            aps = AnalysisPersistenceService()
            persist_meta = aps.persist_valuation(
                company_id=request.company_id,
                valuation_result=result,
                method=request.method,
                assumptions=request.assumptions,
                branch_name=request.branch_name,
                parent_branch_id=request.branch_id,
            )

        return {
            "success": True,
            "method": request.method,
            "valuation": result,
            "company": company_data.get("name", "Unknown"),
            "company_id": request.company_id,
            "_persistence": persist_meta,
        }

    except Exception as e:
        logger.error(f"Valuation error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


def _resolve_generic_company_data(company_data: Dict, company_id: Optional[str], branch_id: Optional[str]) -> Dict[str, Any]:
    """Pull company financials + branch overrides for non-ValuationRequest models."""
    from app.services.company_data_pull import resolve_company_financials
    merged, _ = resolve_company_financials(
        company_id=company_id,
        branch_id=branch_id,
        overrides=dict(company_data),
    )
    return merged


@router.post("/pwerm-analysis")
async def pwerm_analysis(request: PWERMRequest):
    """Perform PWERM analysis.  Always persists to a scenario branch."""
    try:
        engine = ValuationEngineService()
        company_data = _resolve_generic_company_data(request.company_data, request.company_id, request.branch_id)

        assumptions = {
            "exit_scenarios": request.exit_scenarios,
            "probabilities": request.probabilities,
            "time_horizons": request.time_horizons,
            "discount_rate": request.discount_rate,
        }
        valuation_data = {
            "company_data": company_data,
            "method": "pwerm",
            "assumptions": assumptions,
        }

        result = await engine.value_company(**valuation_data)

        # Persist to branch
        persist_meta = {}
        if request.company_id:
            from app.services.analysis_persistence_service import AnalysisPersistenceService
            aps = AnalysisPersistenceService()
            persist_meta = aps.persist_valuation(
                company_id=request.company_id,
                valuation_result=result,
                method="pwerm",
                assumptions=assumptions,
                branch_name=request.branch_name,
                parent_branch_id=request.branch_id,
            )

        return {
            "success": True,
            "method": "pwerm",
            "expected_value": result.get("expected_value", 0),
            "scenarios": result.get("scenarios", []),
            "risk_metrics": result.get("risk_metrics", {}),
            "sensitivity_analysis": result.get("sensitivity_analysis", {}),
            "_persistence": persist_meta,
        }

    except Exception as e:
        logger.error(f"PWERM analysis error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/comparables-analysis")
async def comparables_analysis(request: ComparablesRequest):
    """Perform trading comparables analysis.  Always persists to a branch."""
    try:
        engine = ValuationEngineService()
        company_data = _resolve_generic_company_data(request.company_data, request.company_id, request.branch_id)

        assumptions = {"metrics": request.metrics}
        valuation_data = {
            "company_data": company_data,
            "method": "multiples",
            "comparables": request.peer_companies,
            "assumptions": assumptions,
        }

        result = await engine.value_company(**valuation_data)

        # Persist to branch
        persist_meta = {}
        if request.company_id:
            from app.services.analysis_persistence_service import AnalysisPersistenceService
            aps = AnalysisPersistenceService()
            persist_meta = aps.persist_valuation(
                company_id=request.company_id,
                valuation_result=result,
                method="multiples",
                assumptions=assumptions,
                branch_name=request.branch_name,
                parent_branch_id=request.branch_id,
            )

        return {
            "success": True,
            "method": "comparables",
            "target_company": request.company_data.get("name", "Unknown"),
            "peer_analysis": result.get("peer_analysis", []),
            "valuation_range": result.get("valuation_range", {}),
            "recommended_multiple": result.get("recommended_multiple", 0),
            "implied_valuation": result.get("implied_valuation", 0),
            "_persistence": persist_meta,
        }

    except Exception as e:
        logger.error(f"Comparables analysis error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/dcf-model")
async def dcf_model(company_data: Dict[str, Any], projections: Dict[str, Any]):
    """Build DCF valuation model"""
    try:
        engine = ValuationEngineService()
        
        valuation_data = {
            "company_data": company_data,
            "method": "dcf",
            "assumptions": projections
        }
        
        result = await engine.value_company(**valuation_data)
        
        return {
            "success": True,
            "method": "dcf",
            "enterprise_value": result.get("enterprise_value", 0),
            "equity_value": result.get("equity_value", 0),
            "per_share_value": result.get("per_share_value", 0),
            "dcf_components": result.get("dcf_components", {}),
            "sensitivity_table": result.get("sensitivity_table", {})
        }
        
    except Exception as e:
        logger.error(f"DCF model error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/methods")
async def get_valuation_methods():
    """Get available valuation methods and their parameters"""
    return {
        "methods": {
            "dcf": {
                "name": "Discounted Cash Flow",
                "description": "Values company based on projected free cash flows",
                "required_inputs": ["revenue_projections", "margin_assumptions", "capex", "working_capital", "wacc"],
                "typical_use": "Mature companies with predictable cash flows"
            },
            "multiples": {
                "name": "Trading Multiples",
                "description": "Values company based on comparable public companies",
                "required_inputs": ["peer_companies", "financial_metrics", "adjustments"],
                "typical_use": "Companies with clear public comparables"
            },
            "pwerm": {
                "name": "Probability Weighted Expected Return",
                "description": "Values company across multiple exit scenarios",
                "required_inputs": ["exit_scenarios", "probabilities", "time_horizons", "discount_rate"],
                "typical_use": "Early-stage companies with uncertain outcomes"
            }
        },
        "example_requests": {
            "dcf": {
                "company_data": {"name": "Example Corp", "revenue": 10000000},
                "method": "dcf",
                "assumptions": {"growth_rate": 0.15, "wacc": 0.12, "terminal_growth": 0.03}
            }
        }
    }