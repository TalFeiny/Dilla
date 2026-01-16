"""
Billing API endpoints for credit management and subscriptions
"""

from fastapi import APIRouter, HTTPException, Depends, Request
from typing import Dict, Any
import logging

from app.services.billing_service import LagoService, PricingPlan
from app.api.auth import get_current_user

router = APIRouter()
logger = logging.getLogger(__name__)

# Initialize Lago service
lago_service = LagoService()

@router.get("/credits")
async def get_credits(user = Depends(get_current_user)) -> Dict[str, Any]:
    """
    Get current credit balance and usage
    """
    credits = await lago_service.check_credits(user.id)
    
    return {
        "credits_available": credits["available"],
        "credits_used": credits["used"],
        "credits_limit": credits["limit"],
        "can_proceed": credits["can_proceed"],
        "is_overage": credits.get("is_overage", False)
    }

@router.get("/plans")
async def get_pricing_plans() -> Dict[str, Any]:
    """
    Get available pricing plans
    """
    plans = []
    for plan_enum in PricingPlan:
        plan_data = lago_service.plans[plan_enum]
        plans.append({
            "id": plan_enum.value,
            "name": plan_data["name"],
            "credits": plan_data["credits"],
            "price": plan_data["price"],
            "overage_price": plan_data.get("overage_price"),
            "features": _get_plan_features(plan_enum)
        })
    
    return {"plans": plans}

@router.post("/subscribe/{plan_id}")
async def subscribe_to_plan(
    plan_id: str,
    user = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Create subscription for a plan
    """
    try:
        plan = PricingPlan(plan_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid plan ID")
    
    # Create or update subscription (no payment provider needed for self-hosted)
    subscription = await lago_service.create_subscription(user.id, plan)
    
    if not subscription:
        raise HTTPException(status_code=500, detail="Failed to create subscription")
    
    return {
        "subscription_id": subscription.get("lago_id"),
        "external_id": subscription.get("external_id"),
        "plan": plan_id,
        "status": subscription.get("status", "active"),
        "message": "Subscription created successfully. Credits are now available."
    }

@router.post("/webhook")
async def handle_lago_webhook(request: Request) -> Dict[str, str]:
    """
    Handle Lago webhooks for billing events
    Full webhook documentation: https://doc.getlago.com/docs/api/webhooks/format-signature
    """
    try:
        # Parse Lago webhook payload
        data = await request.json()
        
        # Lago webhook format
        webhook_type = data.get("webhook_type")  # e.g., "invoice.created", "subscription.terminated"
        object_type = data.get("object_type")  # e.g., "invoice", "subscription", "credit_note"
        
        # Handle different Lago webhook events
        if webhook_type == "invoice.created":
            invoice = data.get("invoice", {})
            customer_id = invoice.get("external_customer_id")
            amount = invoice.get("total_amount_cents", 0) / 100
            logger.info(f"Invoice created for {customer_id}: ${amount}")
            
        elif webhook_type == "invoice.payment_status_updated":
            invoice = data.get("invoice", {})
            customer_id = invoice.get("external_customer_id")
            status = invoice.get("payment_status")
            
            if status == "succeeded":
                # Payment successful, credits should be available
                logger.info(f"Payment succeeded for {customer_id}")
            elif status == "failed":
                # Payment failed, may need to restrict access
                logger.warning(f"Payment failed for {customer_id}")
                # Could trigger downgrade to free tier here
                
        elif webhook_type == "subscription.started":
            subscription = data.get("subscription", {})
            customer_id = subscription.get("external_customer_id")
            plan_code = subscription.get("plan_code")
            logger.info(f"Subscription started for {customer_id}: {plan_code}")
            
        elif webhook_type == "subscription.terminated":
            subscription = data.get("subscription", {})
            customer_id = subscription.get("external_customer_id")
            logger.info(f"Subscription terminated for {customer_id}")
            # Reset to free tier
            
        elif webhook_type == "fee.created":
            # Usage-based fee created (credit consumption)
            fee = data.get("fee", {})
            customer_id = fee.get("external_customer_id")
            units = fee.get("units", 0)
            logger.info(f"Usage fee for {customer_id}: {units} credits")
            
        # Pass to service for additional processing
        success = await lago_service.handle_webhook(webhook_type, data)
        
        if success:
            return {"status": "ok"}
        else:
            raise HTTPException(status_code=500, detail="Webhook processing failed")
            
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/usage")
async def get_usage_history(
    user = Depends(get_current_user),
    limit: int = 10
) -> Dict[str, Any]:
    """
    Get user's usage history
    """
    # This would query Lago's events API
    # For now, return mock data
    return {
        "usage": [
            {
                "timestamp": "2024-01-15T10:30:00",
                "event": "company_analysis",
                "credits": 2,
                "companies": ["Stripe", "Square"],
                "model_used": "claude-sonnet-4-5"
            },
            {
                "timestamp": "2024-01-15T14:20:00",
                "event": "deck_generation",
                "credits": 4,
                "companies": ["OpenAI", "Anthropic"],
                "model_used": "gpt-4-turbo"
            }
        ],
        "total_credits_used": 6
    }

def _get_plan_features(plan: PricingPlan) -> list:
    """Get features for each plan"""
    base_features = [
        "Company analysis",
        "Valuation models",
        "Side-by-side comparison"
    ]
    
    if plan == PricingPlan.FREE_TRIAL:
        return base_features
    
    elif plan == PricingPlan.STARTER:
        return base_features + [
            "PDF export",
            "Email support"
        ]
    
    elif plan == PricingPlan.GROWTH:
        return base_features + [
            "PDF & PPTX export",
            "API access (100 calls/month)",
            "Priority support",
            "Custom branding"
        ]
    
    elif plan == PricingPlan.SCALE:
        return base_features + [
            "All export formats",
            "API access (1000 calls/month)",
            "Dedicated support",
            "White-label options",
            "Bulk processing"
        ]
    
    elif plan == PricingPlan.ENTERPRISE:
        return base_features + [
            "Unlimited everything",
            "Custom integrations",
            "SLA guarantee",
            "Dedicated account manager",
            "On-premise deployment option"
        ]
    
    return base_features