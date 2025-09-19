from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional, Dict, Any
from pydantic import BaseModel
import logging
from app.services.market_research_service import market_research_service

router = APIRouter()
logger = logging.getLogger(__name__)


class MarketAnalysisRequest(BaseModel):
    query: str
    company_name: Optional[str] = None
    sector: Optional[str] = None
    deep_search: bool = True


@router.post("/analyze", response_model=Dict[str, Any])
async def analyze_market(request: MarketAnalysisRequest):
    """Perform market analysis."""
    try:
        research = await market_research_service.research_market(
            query=request.query,
            company_name=request.company_name,
            sector=request.sector,
            deep_search=request.deep_search
        )
        
        return {
            "query": research.query,
            "timestamp": research.timestamp,
            "market_size": research.market_size,
            "growth_rate": research.growth_rate,
            "key_players": research.key_players,
            "trends": research.trends,
            "opportunities": research.opportunities,
            "threats": research.threats,
            "summary": research.summary
        }
        
    except Exception as e:
        logger.error(f"Error in market analysis: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/reports", response_model=List[Dict[str, Any]])
async def get_reports(
    sector: Optional[str] = Query(None),
    limit: int = Query(10, le=50)
):
    """Get market research reports."""
    # This would fetch stored reports from database
    # For now, return mock data
    return [
        {
            "id": "1",
            "title": f"{sector or 'Technology'} Market Analysis Q4 2024",
            "date": "2024-10-01",
            "sector": sector or "Technology",
            "summary": "Comprehensive market analysis report"
        },
        {
            "id": "2",
            "title": f"{sector or 'Technology'} Investment Trends 2024",
            "date": "2024-09-15",
            "sector": sector or "Technology",
            "summary": "Investment trends and opportunities"
        }
    ]


@router.get("/trends", response_model=Dict[str, Any])
async def get_market_trends(
    sector: str = Query(...),
    time_period: str = Query("current", regex="^(current|1y|3y|5y)$")
):
    """Get market trends for a sector."""
    try:
        query = f"{sector} market trends {time_period} analysis"
        research = await market_research_service.research_market(
            query=query,
            sector=sector,
            deep_search=False
        )
        
        return {
            "sector": sector,
            "time_period": time_period,
            "trends": research.trends,
            "growth_rate": research.growth_rate,
            "opportunities": research.opportunities,
            "key_insights": research.summary
        }
        
    except Exception as e:
        logger.error(f"Error getting market trends: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/comparables", response_model=List[Dict[str, Any]])
async def get_ma_comparables(
    sector: str = Query(...),
    min_revenue: Optional[float] = Query(None),
    max_revenue: Optional[float] = Query(None)
):
    """Find M&A comparables in the sector."""
    try:
        revenue_range = None
        if min_revenue and max_revenue:
            revenue_range = (min_revenue, max_revenue)
        
        comparables = await market_research_service.get_ma_comparables(
            sector=sector,
            revenue_range=revenue_range
        )
        
        return comparables
        
    except Exception as e:
        logger.error(f"Error getting M&A comparables: {e}")
        raise HTTPException(status_code=500, detail=str(e))