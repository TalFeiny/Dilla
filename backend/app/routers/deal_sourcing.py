"""
Deal Sourcing API Routes
Endpoints for intelligent investment opportunity discovery
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks
from typing import Dict, Any
import os
from ..services.intelligent_deal_sourcing import (
    IntelligentDealSourcing,
    DealSourcingRequest
)

router = APIRouter(prefix="/deal-sourcing", tags=["deal-sourcing"])

# Initialize the service
deal_sourcing_service = IntelligentDealSourcing(
    tavily_api_key=os.getenv("TAVILY_API_KEY", ""),
    firecrawl_api_key=os.getenv("FIRECRAWL_API_KEY", "")
)

@router.post("/find-candidates")
async def find_investment_candidates(request: DealSourcingRequest) -> Dict[str, Any]:
    """
    Find companies ready for investment based on funding cadence patterns
    
    Example requests:
    - {"target_stage": "Series A", "sectors": ["SaaS", "AI"], "geography": "NYC"}
    - {"target_stage": "Series B", "sectors": ["Fintech"], "geography": "Europe"}
    - {"target_stage": "Seed", "sectors": ["Climate"], "min_revenue": 100000}
    """
    try:
        result = await deal_sourcing_service.find_investment_candidates(request)
        return {
            "success": True,
            "data": result,
            "message": f"Found {len(result['companies'])} candidates for {request.target_stage}"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/funding-patterns")
async def get_funding_patterns() -> Dict[str, Any]:
    """
    Get funding stage patterns and timing benchmarks
    """
    return {
        "patterns": deal_sourcing_service.FUNDING_PATTERNS,
        "description": "Typical time between funding rounds by stage"
    }

@router.post("/search-preview")
async def preview_search_strategy(
    target_stage: str,
    sectors: list = None,
    geography: str = None
) -> Dict[str, Any]:
    """
    Preview the search strategy without executing searches
    Useful for understanding what queries will be run
    """
    try:
        request = DealSourcingRequest(
            target_stage=target_stage,
            sectors=sectors,
            geography=geography
        )
        
        pattern = deal_sourcing_service.FUNDING_PATTERNS.get(target_stage)
        if not pattern:
            raise HTTPException(status_code=400, detail=f"Unknown stage: {target_stage}")
        
        from datetime import datetime
        search_window = deal_sourcing_service._calculate_search_window(pattern, datetime.now())
        search_queries = deal_sourcing_service._generate_search_queries(
            pattern["from_stage"],
            search_window,
            sectors,
            geography
        )
        
        return {
            "target_stage": target_stage,
            "previous_stage": pattern["from_stage"],
            "search_window": {
                "start": search_window["optimal_start"].isoformat(),
                "end": search_window["optimal_end"].isoformat(),
                "months_ago": f"{pattern['min_months']}-{pattern['max_months']}"
            },
            "search_queries": search_queries[:10],
            "data_sources": ["TechCrunch", "European Database", "SEC EDGAR", "Crunchbase"],
            "example": f"Will search for {pattern['from_stage']} announcements from {pattern['min_months']}-{pattern['max_months']} months ago"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))