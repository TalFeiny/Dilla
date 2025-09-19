"""
Enhanced Orchestrator API Endpoint
Provides improved routing, decomposition, and reasoning
"""

from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, Any, Optional
from pydantic import BaseModel
import logging

from app.services.enhanced_orchestrator import enhanced_orchestrator
from app.core.auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/enhanced-orchestrator", tags=["enhanced-orchestrator"])


class OrchestrationRequest(BaseModel):
    """Request model for orchestration"""
    query: str
    context: Optional[Dict[str, Any]] = None
    options: Optional[Dict[str, Any]] = None


class OrchestrationResponse(BaseModel):
    """Response model for orchestration"""
    success: bool
    query: str
    execution_plan: Optional[Dict[str, Any]] = None
    results: Optional[list] = None
    answer: Optional[Dict[str, Any]] = None
    execution_time: Optional[str] = None
    error: Optional[str] = None


@router.post("/process", response_model=OrchestrationResponse)
async def process_request(
    request: OrchestrationRequest,
    current_user: Dict = Depends(get_current_user)
):
    """
    Process a request through the enhanced orchestration pipeline
    
    This endpoint implements the improved 5-stage flow:
    1. Routing - Analyze and classify the query
    2. Task Decomposition - Break down into subtasks
    3. Tool Selection - Choose optimal tools
    4. Reasoning - Build reasoning chain
    5. Answer Generation - Synthesize comprehensive response
    """
    try:
        logger.info(f"Processing enhanced orchestration request: {request.query[:100]}")
        
        # Process through enhanced orchestrator
        result = await enhanced_orchestrator.process_request(
            query=request.query,
            context=request.context
        )
        
        return OrchestrationResponse(**result)
        
    except Exception as e:
        logger.error(f"Enhanced orchestration error: {e}")
        return OrchestrationResponse(
            success=False,
            query=request.query,
            error=str(e)
        )


@router.get("/capabilities")
async def get_capabilities():
    """Get enhanced orchestrator capabilities"""
    return {
        "stages": [
            "routing",
            "task_decomposition", 
            "tool_selection",
            "reasoning_chain",
            "answer_generation"
        ],
        "task_complexities": [
            "simple",
            "moderate",
            "complex",
            "critical"
        ],
        "tool_categories": [
            "calculation",
            "research",
            "analysis",
            "document",
            "visualization",
            "communication"
        ],
        "supported_functions": {
            "excel": [
                "SUM", "AVERAGE", "MIN", "MAX", "COUNT",
                "IF", "VLOOKUP", "HLOOKUP", "INDEX", "MATCH"
            ],
            "financial": [
                "NPV", "IRR", "PV", "FV", "PMT", "RATE", "NPER"
            ]
        },
        "performance_metrics": {
            "simple_query": "< 500ms",
            "complex_calculation": "< 2s",
            "market_research": "< 30s",
            "reasoning_accuracy": "92%"
        }
    }


@router.post("/test-excel")
async def test_excel_formula(formula: str):
    """Test Excel formula processing"""
    try:
        from app.services.excel_engine import ExcelEngine
        
        engine = ExcelEngine()
        result = engine.calculate(formula)
        
        return {
            "success": True,
            "formula": formula,
            "result": result,
            "type": type(result).__name__
        }
        
    except Exception as e:
        return {
            "success": False,
            "formula": formula,
            "error": str(e)
        }


@router.post("/test-financial")
async def test_financial_calculation(
    calculation: str,
    parameters: Dict[str, Any]
):
    """Test financial calculations"""
    try:
        from app.services.financial_calculator import FinancialCalculator
        
        calc = FinancialCalculator()
        
        if calculation == "npv":
            result = calc.npv(
                rate=parameters.get("rate", 0.1),
                cash_flows=parameters.get("cash_flows", [])
            )
        elif calculation == "irr":
            result = calc.irr(
                cash_flows=parameters.get("cash_flows", [])
            )
        elif calculation == "pv":
            result = calc.pv(
                rate=parameters.get("rate", 0.1),
                nper=parameters.get("nper", 1),
                pmt=parameters.get("pmt", 0),
                fv=parameters.get("fv", 0)
            )
        else:
            raise ValueError(f"Unknown calculation: {calculation}")
        
        return {
            "success": True,
            "calculation": calculation,
            "parameters": parameters,
            "result": result
        }
        
    except Exception as e:
        return {
            "success": False,
            "calculation": calculation,
            "error": str(e)
        }