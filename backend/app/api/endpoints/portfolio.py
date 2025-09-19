from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional, Dict, Any
from pydantic import BaseModel
import logging
from app.services.portfolio_service import portfolio_service

router = APIRouter()
logger = logging.getLogger(__name__)


class PortfolioAnalysisRequest(BaseModel):
    portfolio_id: str
    analysis_type: str = "comprehensive"
    include_projections: bool = True


@router.get("/", response_model=List[Dict[str, Any]])
async def get_portfolio():
    """Get portfolio overview."""
    # Return list of available portfolios
    return [
        {
            "id": "1",
            "name": "Fund I",
            "vintage_year": 2020,
            "fund_size": 100000000,
            "deployed_capital": 45000000,
            "portfolio_companies": 12
        },
        {
            "id": "2",
            "name": "Fund II",
            "vintage_year": 2023,
            "fund_size": 150000000,
            "deployed_capital": 20000000,
            "portfolio_companies": 5
        }
    ]


@router.post("/analyze", response_model=Dict[str, Any])
async def analyze_portfolio(request: PortfolioAnalysisRequest):
    """Analyze portfolio performance."""
    try:
        portfolio = await portfolio_service.get_portfolio(request.portfolio_id)
        
        if not portfolio:
            raise HTTPException(status_code=404, detail="Portfolio not found")
        
        # Add additional analysis based on type
        analysis = {
            "portfolio_id": request.portfolio_id,
            "analysis_type": request.analysis_type,
            "metrics": portfolio.get("metrics", {}),
            "companies": portfolio.get("companies", [])
        }
        
        if request.include_projections:
            # Add projections
            pacing = await portfolio_service.get_portfolio_pacing(request.portfolio_id)
            analysis["projections"] = pacing
        
        return analysis
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error analyzing portfolio: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{portfolio_id}", response_model=Dict[str, Any])
async def get_portfolio_details(portfolio_id: str):
    """Get detailed portfolio information."""
    try:
        portfolio = await portfolio_service.get_portfolio(portfolio_id)
        
        if not portfolio:
            raise HTTPException(status_code=404, detail="Portfolio not found")
        
        return portfolio
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting portfolio details: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{portfolio_id}/companies", response_model=List[Dict[str, Any]])
async def get_portfolio_companies(portfolio_id: str):
    """Get companies in a portfolio."""
    try:
        portfolio = await portfolio_service.get_portfolio(portfolio_id)
        
        if not portfolio:
            raise HTTPException(status_code=404, detail="Portfolio not found")
        
        return portfolio.get("companies", [])
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting portfolio companies: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{portfolio_id}/graduation-rates", response_model=Dict[str, Any])
async def get_graduation_rates(
    portfolio_id: str,
    time_period: Optional[str] = Query("all", regex="^(all|1y|3y|5y)$")
):
    """Get portfolio graduation rates between funding rounds."""
    try:
        rates = await portfolio_service.calculate_graduation_rates(
            portfolio_id=portfolio_id,
            time_period=time_period
        )
        
        return rates
        
    except Exception as e:
        logger.error(f"Error calculating graduation rates: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{portfolio_id}/pacing", response_model=Dict[str, Any])
async def get_portfolio_pacing(
    portfolio_id: str,
    target_deployment: Optional[float] = None
):
    """Analyze portfolio deployment pacing."""
    try:
        pacing = await portfolio_service.get_portfolio_pacing(
            portfolio_id=portfolio_id,
            target_deployment=target_deployment
        )
        
        return pacing
        
    except Exception as e:
        logger.error(f"Error calculating pacing: {e}")
        raise HTTPException(status_code=500, detail=str(e))