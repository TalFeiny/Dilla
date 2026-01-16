"""
Test endpoint for ModelRouter debugging
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, Any, Optional
import logging

from app.services.model_router import ModelRouter, ModelCapability, get_model_router
from app.services.unified_mcp_orchestrator import UnifiedMCPOrchestrator

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/test-model-router", tags=["model-router-test"])


class TestRequest(BaseModel):
    prompt: str
    capability: str = "analysis"


class CompanyFetchRequest(BaseModel):
    company: str


@router.post("/test")
async def test_model_router(request: TestRequest) -> Dict[str, Any]:
    """
    Direct test of ModelRouter to see what's happening
    """
    try:
        logger.info(f"[TEST] Testing ModelRouter with prompt: {request.prompt[:50]}")
        
        # Get the router
        model_router = get_model_router()
        
        # Map capability string to enum
        capability_map = {
            "analysis": ModelCapability.ANALYSIS,
            "code": ModelCapability.CODE,
            "structured": ModelCapability.STRUCTURED,
            "creative": ModelCapability.CREATIVE,
            "fast": ModelCapability.FAST,
            "cheap": ModelCapability.CHEAP,
        }
        capability = capability_map.get(request.capability, ModelCapability.ANALYSIS)
        
        # Try to get a completion
        result = await model_router.get_completion(
            prompt=request.prompt,
            capability=capability,
            max_tokens=100,
            temperature=0.7,
            caller_context="test_model_router_endpoint"
        )
        
        return {
            "success": True,
            "result": result,
            "model_used": result.get("model"),
            "provider": result.get("provider"),
            "cost": result.get("cost"),
            "latency": result.get("latency"),
            "response": result.get("response")
        }
        
    except Exception as e:
        logger.error(f"[TEST] ModelRouter error: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e),
            "error_type": type(e).__name__
        }


@router.get("/models")
async def list_available_models():
    """List all available models in ModelRouter"""
    model_router = get_model_router()
    
    models_info = []
    for name, config in model_router.model_configs.items():
        is_ready = model_router._is_model_ready(name)
        is_broken = model_router._is_circuit_broken(name)
        error_count = model_router.error_counts.get(name, 0)
        cb_until = model_router.circuit_breaker_until.get(name)
        
        models_info.append({
            "name": name,
            "provider": config["provider"].value,
            "model": config["model"],
            "capabilities": [c.value for c in config["capabilities"]],
            "priority": config["priority"],
            "max_tokens": config["max_tokens"],
            "is_ready": is_ready,
            "is_circuit_broken": is_broken,
            "error_count": error_count,
            "circuit_breaker_until": cb_until.isoformat() if cb_until else None
        })
    
    return {
        "total_models": len(models_info),
        "models": models_info
    }


@router.get("/circuit-breakers")
async def get_circuit_breaker_status():
    """Get current circuit breaker status for all models"""
    model_router = get_model_router()
    
    return {
        "circuit_breaker_until": {
            k: v.isoformat() if v else None 
            for k, v in model_router.circuit_breaker_until.items()
        },
        "error_counts": model_router.error_counts,
        "total_blocked": len(model_router.circuit_breaker_until)
    }


@router.post("/circuit-breakers/reset")
async def reset_circuit_breakers(model_name: Optional[str] = None):
    """Reset circuit breakers for a specific model or all models
    
    Args:
        model_name: Optional model name to reset. If not provided, resets all.
    """
    model_router = get_model_router()
    model_router.reset_circuit_breakers(model_name)
    
    return {
        "success": True,
        "message": f"Circuit breakers reset for {model_name if model_name else 'all models'}",
        "circuit_breaker_until": {
            k: v.isoformat() if v else None 
            for k, v in model_router.circuit_breaker_until.items()
        },
        "error_counts": model_router.error_counts
    }


@router.post("/companies")
async def test_company_fetcher(request: CompanyFetchRequest) -> Dict[str, Any]:
    """
    Test company fetcher directly to debug company extraction issues
    Takes company name as input and returns raw extracted data before/after model router call
    """
    try:
        logger.info(f"[TEST] Testing company fetcher for: {request.company}")
        
        # Create orchestrator instance
        orchestrator = UnifiedMCPOrchestrator()
        
        # Call _execute_company_fetch directly
        inputs = {
            "company": request.company,
            "prompt_handle": request.company
        }
        
        logger.info(f"[TEST] Calling _execute_company_fetch with inputs: {inputs}")
        result = await orchestrator._execute_company_fetch(inputs)
        
        # Extract what we got
        companies = result.get("companies", [])
        if companies:
            company_data = companies[0]
            logger.info(f"[TEST] Company fetcher returned data with keys: {list(company_data.keys())[:20]}")
            
            return {
                "success": True,
                "company": company_data.get("company", request.company),
                "extracted_fields": list(company_data.keys()),
                "sample_data": {
                    "company": company_data.get("company"),
                    "stage": company_data.get("stage"),
                    "valuation": company_data.get("valuation"),
                    "revenue": company_data.get("revenue"),
                    "total_funding": company_data.get("total_funding"),
                    "team_size": company_data.get("team_size"),
                    "funding_rounds_count": len(company_data.get("funding_rounds", [])),
                    "founders_count": len(company_data.get("founders", [])),
                    "business_model": company_data.get("business_model", "")[:100] if company_data.get("business_model") else "",
                    "has_extraction_error": company_data.get("extraction_error") is not None,
                    "extraction_partial": company_data.get("extraction_partial", False)
                },
                "full_data": company_data
            }
        else:
            logger.warning(f"[TEST] Company fetcher returned no companies")
            return {
                "success": False,
                "error": "No companies returned",
                "raw_result": result
            }
            
    except Exception as e:
        logger.error(f"[TEST] Company fetcher error: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e),
            "error_type": type(e).__name__
        }
