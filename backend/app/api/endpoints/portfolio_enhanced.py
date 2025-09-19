"""
Enhanced Portfolio Management API Endpoints
Includes communication tracking and multi-method valuation support
"""

from fastapi import APIRouter, HTTPException, Depends, Query
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from pydantic import BaseModel
import logging

from app.services.portfolio_management_service import enhanced_portfolio_service
from app.core.auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v2/portfolio", tags=["enhanced_portfolio"])


# Pydantic models for request/response
class CommunicationLogRequest(BaseModel):
    type: str
    date: str
    subject: Optional[str] = None
    summary: Optional[str] = None
    participants: Optional[List[str]] = []
    follow_up_required: bool = False
    follow_up_date: Optional[str] = None
    sentiment: Optional[str] = "neutral"
    key_topics: Optional[List[str]] = []
    action_items: Optional[Dict[str, Any]] = {}


class ValuationRequest(BaseModel):
    method: str
    date: str
    amount: float
    revenue: Optional[float] = None
    arr: Optional[float] = None
    ebitda: Optional[float] = None
    growth_rate: Optional[float] = None
    revenue_multiple: Optional[float] = None
    arr_multiple: Optional[float] = None
    ebitda_multiple: Optional[float] = None
    confidence_level: str = "medium"
    assumptions: Optional[Dict[str, Any]] = {}
    notes: Optional[str] = None
    performed_by: Optional[str] = None


class MetricsUpdateRequest(BaseModel):
    metric_date: str
    revenue: Optional[float] = None
    arr: Optional[float] = None
    mrr: Optional[float] = None
    gross_margin: Optional[float] = None
    burn_rate: Optional[float] = None
    runway_months: Optional[int] = None
    customer_count: Optional[int] = None
    employee_count: Optional[int] = None
    nps_score: Optional[int] = None
    churn_rate: Optional[float] = None
    cac: Optional[float] = None
    ltv: Optional[float] = None
    ltv_cac_ratio: Optional[float] = None
    additional_metrics: Optional[Dict[str, Any]] = {}


@router.get("/enhanced")
async def get_enhanced_portfolios(
    current_user: Optional[Dict] = Depends(get_current_user)
):
    """
    Get all portfolios with enhanced communication and valuation tracking
    """
    try:
        # For demo purposes, return mock data
        portfolios = await enhanced_portfolio_service.get_portfolio_with_communications("demo-portfolio-id")
        
        return {
            "success": True,
            "portfolios": [portfolios] if portfolios else [],
            "summary": {
                "total_portfolios": 1 if portfolios else 0,
                "companies_needing_attention": portfolios.get("communication_summary", {}).get("companies_needing_attention", 0) if portfolios else 0
            }
        }
    except Exception as e:
        logger.error(f"Error getting enhanced portfolios: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/enhanced/{portfolio_id}")
async def get_enhanced_portfolio(
    portfolio_id: str,
    current_user: Optional[Dict] = Depends(get_current_user)
):
    """
    Get a specific portfolio with all enhanced tracking data
    """
    try:
        portfolio = await enhanced_portfolio_service.get_portfolio_with_communications(portfolio_id)
        
        if not portfolio:
            raise HTTPException(status_code=404, detail="Portfolio not found")
        
        return {
            "success": True,
            "portfolio": portfolio
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting enhanced portfolio {portfolio_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/companies/{company_id}/communication")
async def log_communication(
    company_id: str,
    communication: CommunicationLogRequest,
    current_user: Optional[Dict] = Depends(get_current_user)
):
    """
    Log a communication with a portfolio company
    """
    try:
        communication_data = {
            "type": communication.type,
            "date": communication.date,
            "subject": communication.subject,
            "summary": communication.summary,
            "participants": communication.participants,
            "follow_up_required": communication.follow_up_required,
            "follow_up_date": communication.follow_up_date,
            "sentiment": communication.sentiment,
            "key_topics": communication.key_topics,
            "action_items": communication.action_items,
            "created_by": current_user.get("email") if current_user else "system"
        }
        
        result = await enhanced_portfolio_service.log_communication(company_id, communication_data)
        
        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])
        
        return {
            "success": True,
            "communication_id": result.get("communication_id"),
            "message": "Communication logged successfully"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error logging communication for company {company_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/companies/{company_id}/communications")
async def get_communication_history(
    company_id: str,
    limit: int = Query(50, ge=1, le=200),
    current_user: Optional[Dict] = Depends(get_current_user)
):
    """
    Get communication history for a portfolio company
    """
    try:
        communications = await enhanced_portfolio_service.get_communication_history(company_id, limit)
        
        return {
            "success": True,
            "company_id": company_id,
            "communications": communications,
            "total": len(communications)
        }
    except Exception as e:
        logger.error(f"Error getting communication history for company {company_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/companies/{company_id}/valuation")
async def add_valuation(
    company_id: str,
    valuation: ValuationRequest,
    current_user: Optional[Dict] = Depends(get_current_user)
):
    """
    Add a new valuation for a portfolio company
    """
    try:
        valuation_data = {
            "date": valuation.date,
            "method": valuation.method,
            "amount": valuation.amount,
            "revenue": valuation.revenue,
            "arr": valuation.arr,
            "ebitda": valuation.ebitda,
            "growth_rate": valuation.growth_rate,
            "revenue_multiple": valuation.revenue_multiple,
            "arr_multiple": valuation.arr_multiple,
            "ebitda_multiple": valuation.ebitda_multiple,
            "assumptions": valuation.assumptions,
            "notes": valuation.notes,
            "performed_by": valuation.performed_by or (current_user.get("email") if current_user else "system"),
            "confidence_level": valuation.confidence_level
        }
        
        # Calculate multiples if not provided
        if valuation.arr and not valuation.arr_multiple:
            valuation_data["arr_multiple"] = valuation.amount / valuation.arr if valuation.arr > 0 else None
        if valuation.revenue and not valuation.revenue_multiple:
            valuation_data["revenue_multiple"] = valuation.amount / valuation.revenue if valuation.revenue > 0 else None
        
        result = await enhanced_portfolio_service.add_valuation(company_id, valuation_data)
        
        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])
        
        return {
            "success": True,
            "valuation_id": result.get("valuation_id"),
            "message": "Valuation added successfully"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error adding valuation for company {company_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/companies/{company_id}/valuations")
async def get_valuation_history(
    company_id: str,
    current_user: Optional[Dict] = Depends(get_current_user)
):
    """
    Get valuation history with all methods for a portfolio company
    """
    try:
        valuations = await enhanced_portfolio_service.get_valuation_history(company_id)
        
        # Calculate summary statistics
        all_valuations = []
        for method_valuations in valuations.values():
            all_valuations.extend([v["valuation_amount"] for v in method_valuations])
        
        summary = {}
        if all_valuations:
            summary = {
                "average": sum(all_valuations) / len(all_valuations),
                "min": min(all_valuations),
                "max": max(all_valuations),
                "count": len(all_valuations),
                "methods_used": len(valuations)
            }
        
        return {
            "success": True,
            "company_id": company_id,
            "valuations_by_method": valuations,
            "summary": summary
        }
    except Exception as e:
        logger.error(f"Error getting valuation history for company {company_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/companies/{company_id}/metrics")
async def update_metrics(
    company_id: str,
    metrics: MetricsUpdateRequest,
    current_user: Optional[Dict] = Depends(get_current_user)
):
    """
    Update metrics for a portfolio company
    """
    try:
        # This would insert into the portfolio_metrics table
        metrics_data = metrics.dict(exclude_none=True)
        metrics_data["portfolio_company_id"] = company_id
        
        # In a real implementation, this would use the database
        return {
            "success": True,
            "message": "Metrics updated successfully",
            "metrics": metrics_data
        }
    except Exception as e:
        logger.error(f"Error updating metrics for company {company_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/communications/dashboard")
async def get_communications_dashboard(
    days: int = Query(30, ge=1, le=365),
    current_user: Optional[Dict] = Depends(get_current_user)
):
    """
    Get a dashboard view of all portfolio communications
    """
    try:
        # This would aggregate communication data across all portfolios
        cutoff_date = datetime.now() - timedelta(days=days)
        
        # Mock dashboard data
        dashboard = {
            "summary": {
                "total_communications": 156,
                "companies_contacted": 42,
                "companies_not_contacted": 8,
                "average_days_between_contact": 14,
                "follow_ups_pending": 12
            },
            "by_type": {
                "email": 67,
                "call": 34,
                "meeting": 28,
                "quarterly_report": 15,
                "board_meeting": 12
            },
            "by_sentiment": {
                "positive": 89,
                "neutral": 52,
                "negative": 10,
                "concerning": 5
            },
            "companies_needing_attention": [
                {
                    "company_name": "AI Analytics Co",
                    "days_since_contact": 65,
                    "last_contact_type": "email",
                    "portfolio": "Growth Fund I"
                },
                {
                    "company_name": "CloudOps Platform",
                    "days_since_contact": 31,
                    "last_contact_type": "call",
                    "portfolio": "Growth Fund I"
                }
            ],
            "upcoming_follow_ups": [
                {
                    "company_name": "DataSync Inc",
                    "follow_up_date": "2024-01-20",
                    "notes": "Discuss Series C timeline"
                }
            ]
        }
        
        return {
            "success": True,
            "period_days": days,
            "dashboard": dashboard
        }
    except Exception as e:
        logger.error(f"Error getting communications dashboard: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/valuations/comparison")
async def get_valuation_comparison(
    portfolio_id: Optional[str] = None,
    current_user: Optional[Dict] = Depends(get_current_user)
):
    """
    Compare valuations across different methods for all portfolio companies
    """
    try:
        # This would aggregate valuation data
        comparison = {
            "companies": [
                {
                    "company_name": "DataSync Inc",
                    "methods": {
                        "dcf": 16000000,
                        "comps": 14500000,
                        "vc_method": 18000000,
                        "pwerm": 15000000,
                        "average": 15875000
                    },
                    "variance": 0.12,  # 12% variance between methods
                    "confidence": "high"
                },
                {
                    "company_name": "CloudOps Platform",
                    "methods": {
                        "dcf": 8500000,
                        "comps": 7800000,
                        "vc_method": 9000000,
                        "pwerm": 8000000,
                        "average": 8325000
                    },
                    "variance": 0.08,
                    "confidence": "medium"
                }
            ],
            "summary": {
                "total_portfolio_value_dcf": 24500000,
                "total_portfolio_value_comps": 22300000,
                "total_portfolio_value_vc_method": 27000000,
                "total_portfolio_value_pwerm": 23000000,
                "total_portfolio_value_average": 24200000
            }
        }
        
        return {
            "success": True,
            "portfolio_id": portfolio_id,
            "comparison": comparison
        }
    except Exception as e:
        logger.error(f"Error getting valuation comparison: {e}")
        raise HTTPException(status_code=500, detail=str(e))