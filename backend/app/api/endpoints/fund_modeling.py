"""
Fund Modeling API Endpoints
API for fund-level world modeling and metrics
"""

import logging
from fastapi import APIRouter, HTTPException
from typing import Dict, List, Any, Optional
from pydantic import BaseModel
from datetime import datetime

from app.services.fund_modeling_service import FundModelingService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/fund-modeling", tags=["fund-modeling"])

# Initialize service
fund_modeling = FundModelingService()


@router.get("/fund/{fund_id}/metrics")
async def get_fund_metrics(fund_id: str):
    """Calculate comprehensive fund metrics (NAV, IRR, DPI, TVPI, RVPI)"""
    try:
        metrics = await fund_modeling.calculate_fund_metrics(fund_id)
        return metrics
    except Exception as e:
        logger.error(f"Error calculating fund metrics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/fund/{fund_id}/nav-timeseries")
async def get_nav_timeseries(
    fund_id: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
):
    """Get NAV time series for a fund"""
    try:
        start = datetime.fromisoformat(start_date) if start_date else None
        end = datetime.fromisoformat(end_date) if end_date else None
        
        timeseries = await fund_modeling.calculate_nav_time_series(
            fund_id=fund_id,
            start_date=start,
            end_date=end
        )
        return timeseries
    except Exception as e:
        logger.error(f"Error getting NAV time series: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/fund/{fund_id}/optimize")
async def optimize_portfolio(
    fund_id: str,
    constraints: Optional[Dict[str, Any]] = None
):
    """Optimize portfolio construction"""
    try:
        optimization = await fund_modeling.optimize_portfolio(
            fund_id=fund_id,
            constraints=constraints
        )
        return optimization
    except Exception as e:
        logger.error(f"Error optimizing portfolio: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/fund/{fund_id}/pacing")
async def analyze_pacing(
    fund_id: str,
    target_deployment: Optional[float] = None
):
    """Analyze fund deployment pacing"""
    try:
        pacing = await fund_modeling.analyze_pacing(
            fund_id=fund_id,
            target_deployment=target_deployment
        )
        return pacing
    except Exception as e:
        logger.error(f"Error analyzing pacing: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/fund/{fund_id}/portfolio-world-model")
async def create_portfolio_world_model(
    fund_id: str,
    model_name: Optional[str] = None
):
    """Create a portfolio-level world model"""
    try:
        model = await fund_modeling.create_portfolio_world_model(
            fund_id=fund_id,
            model_name=model_name
        )
        return model
    except Exception as e:
        logger.error(f"Error creating portfolio world model: {e}")
        raise HTTPException(status_code=500, detail=str(e))
