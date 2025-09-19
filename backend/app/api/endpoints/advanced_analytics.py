"""
Advanced Analytics API Endpoint
Bridges frontend institutional research capabilities with backend MCP orchestrator
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks
from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field
from datetime import datetime
import logging
import asyncio

from app.services.mcp_orchestrator import SingleAgentOrchestrator as MCPOrchestrator
from app.services.analytics_bridge import AnalyticsBridge
from app.core.database import supabase_service

router = APIRouter()
logger = logging.getLogger(__name__)

# Initialize services
mcp_orchestrator = MCPOrchestrator()
analytics_bridge = AnalyticsBridge()


class AnalyticsRequest(BaseModel):
    """Request model for advanced analytics"""
    company: str
    analysis_type: str = Field(
        default="full_research",
        description="Type of analysis: full_research, monte_carlo, sensitivity, scenario"
    )
    parameters: Dict[str, Any] = Field(default_factory=dict)
    use_cache: bool = True
    
class AnalyticsResponse(BaseModel):
    """Response model for analytics results"""
    company: str
    analysis_type: str
    results: Dict[str, Any]
    metadata: Dict[str, Any]
    timestamp: datetime
    cached: bool = False

@router.post("/analyze", response_model=AnalyticsResponse)
async def analyze_company(request: AnalyticsRequest, background_tasks: BackgroundTasks):
    """
    Perform advanced analytics on a company
    """
    try:
        # Check cache first
        if request.use_cache:
            cached_result = await analytics_bridge.get_cached_analysis(
                request.company,
                request.analysis_type
            )
            if cached_result:
                return AnalyticsResponse(
                    company=request.company,
                    analysis_type=request.analysis_type,
                    results=cached_result,
                    metadata={"source": "cache"},
                    timestamp=datetime.utcnow(),
                    cached=True
                )
        
        # Process analysis
        results = await analytics_bridge.process_analysis(
            request.company,
            request.analysis_type,
            request.parameters
        )
        
        return AnalyticsResponse(
            company=request.company,
            analysis_type=request.analysis_type,
            results=results,
            metadata={"source": "fresh_analysis"},
            timestamp=datetime.utcnow(),
            cached=False
        )
        
    except Exception as e:
        logger.error(f"Analysis failed for {request.company}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/compare")
async def compare_companies(
    target_company: str,
    peer_companies: List[str],
    metrics: Optional[List[str]] = None
):
    """
    Compare target company against peers
    """
    try:
        # Default metrics if none provided
        if not metrics:
            metrics = ["revenue", "growth_rate", "valuation", "burn_rate", "runway"]
        
        # Gather data for all companies
        all_companies = [target_company] + peer_companies
        company_data = {}
        
        for company in all_companies:
            # Run basic analysis for each
            result = await analytics_bridge.process_analysis(
                company,
                "scenario",
                {"base_revenue": 10_000_000}  # Default params
            )
            company_data[company] = result
        
        # Calculate comparisons
        comparison_results = {
            "target": target_company,
            "peers": peer_companies,
            "metrics_compared": metrics,
            "company_data": company_data,
            "relative_performance": _calculate_relative_performance(
                company_data[target_company],
                {c: company_data[c] for c in peer_companies}
            )
        }
        
        return comparison_results
        
    except Exception as e:
        logger.error(f"Comparison failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/pwerm")
async def calculate_pwerm(
    company: str,
    scenarios: Dict[str, Dict[str, Any]]
):
    """
    Calculate PWERM valuation
    """
    try:
        # Run scenario analysis with provided scenarios
        result = await analytics_bridge.process_analysis(
            company,
            "scenario",
            scenarios
        )
        
        return {
            "company": company,
            "valuation_method": "PWERM",
            "results": result["results"],
            "timestamp": datetime.utcnow()
        }
        
    except Exception as e:
        logger.error(f"PWERM calculation failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/valuation")
async def calculate_valuation(
    company: str,
    method: str = "monte_carlo",
    parameters: Optional[Dict[str, Any]] = None
):
    """
    Calculate company valuation using specified method
    """
    try:
        if parameters is None:
            parameters = {}
        
        result = await analytics_bridge.process_analysis(
            company,
            method,
            parameters
        )
        
        return {
            "company": company,
            "valuation_method": method,
            "results": result.get("results", {}),
            "parameters_used": result.get("parameters_used", {}),
            "timestamp": datetime.utcnow()
        }
        
    except Exception as e:
        logger.error(f"Valuation failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/status")
async def get_status():
    """Get service status"""
    return {
        "status": "operational",
        "services": {
            "mcp_orchestrator": "ready",
            "analytics_bridge": "ready"
        },
        "available_analyses": [
            "monte_carlo",
            "sensitivity",
            "scenario",
            "full_research"
        ]
    }

def _calculate_relative_performance(
    target_data: Dict[str, Any],
    peer_data: Dict[str, Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Calculate relative performance metrics
    """
    # Simple comparison logic
    performance = {
        "above_median": 0,
        "below_median": 0,
        "percentile_rank": 0
    }
    
    # This would be more sophisticated in production
    return performance