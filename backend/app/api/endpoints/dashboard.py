from fastapi import APIRouter, HTTPException
from typing import Dict, Any, List
import logging
from datetime import datetime, timedelta

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/overview")
async def get_dashboard_overview():
    """
    Get dashboard overview with key metrics.
    """
    return await get_dashboard_metrics()

@router.get("/stats")
async def get_dashboard_stats():
    """
    Get dashboard statistics.
    """
    return await get_dashboard_metrics()

@router.get("/metrics")
async def get_dashboard_metrics():
    """
    Get dashboard metrics and analytics.
    """
    try:
        # Return mock metrics for now
        return {
            "portfolio": {
                "total_value": 150000000,
                "companies": 12,
                "irr": 0.28,
                "tvpi": 2.3
            },
            "pipeline": {
                "opportunities": 45,
                "in_review": 8,
                "in_due_diligence": 3
            },
            "recent_activity": [
                {
                    "type": "new_deal",
                    "company": "TechCo",
                    "timestamp": datetime.now().isoformat()
                },
                {
                    "type": "document_upload",
                    "company": "HealthTech",
                    "timestamp": (datetime.now() - timedelta(hours=2)).isoformat()
                }
            ]
        }
    except Exception as e:
        logger.error(f"Error getting dashboard metrics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/portfolio-summary")
async def get_portfolio_summary():
    """
    Get portfolio summary for dashboard.
    """
    try:
        return {
            "summary": {
                "total_investments": 12,
                "realized_gains": 45000000,
                "unrealized_value": 105000000,
                "top_performers": [
                    {"company": "TechCo", "multiple": 5.2},
                    {"company": "HealthTech", "multiple": 3.8}
                ]
            }
        }
    except Exception as e:
        logger.error(f"Error getting portfolio summary: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/analytics")
async def get_analytics():
    """
    Get analytics data for dashboard visualizations.
    """
    try:
        return {
            "performance": {
                "monthly_returns": [0.05, 0.03, 0.08, 0.02, 0.06],
                "sector_breakdown": {
                    "Technology": 0.40,
                    "Healthcare": 0.25,
                    "Fintech": 0.20,
                    "Other": 0.15
                }
            },
            "pipeline": {
                "conversion_rate": 0.12,
                "average_deal_size": 5000000
            }
        }
    except Exception as e:
        logger.error(f"Error getting analytics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/alerts")
async def get_alerts():
    """
    Get system alerts and notifications.
    """
    try:
        return {
            "alerts": [
                {
                    "type": "info",
                    "message": "New market report available",
                    "timestamp": datetime.now().isoformat()
                }
            ]
        }
    except Exception as e:
        logger.error(f"Error getting alerts: {e}")
        raise HTTPException(status_code=500, detail=str(e))