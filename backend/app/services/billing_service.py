"""
Lago Billing Service for Usage-Based Pricing
Tracks credits, enforces limits, and manages subscriptions
"""

import os
import logging
import httpx
from typing import Dict, Any, Optional
from datetime import datetime
from enum import Enum

logger = logging.getLogger(__name__)

class PricingPlan(Enum):
    """Available pricing plans"""
    FREE_TRIAL = "free_trial"
    STARTER = "starter"
    GROWTH = "growth"
    SCALE = "scale"
    ENTERPRISE = "enterprise"

class LagoService:
    """
    Lago integration for usage-based billing
    Tracks credit usage and enforces limits
    """
    
    def __init__(self):
        self.api_key = os.getenv("LAGO_API_KEY")
        self.base_url = os.getenv("LAGO_API_URL", "https://api.getlago.com/api/v1")
        self.client = httpx.AsyncClient(
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
        )
        
        # Plan configurations
        self.plans = {
            PricingPlan.FREE_TRIAL: {
                "credits": 5,
                "price": 0,
                "name": "Free Trial"
            },
            PricingPlan.STARTER: {
                "credits": 20,
                "price": 19,
                "name": "Starter",
                "overage_price": 1.50  # Per credit after limit
            },
            PricingPlan.GROWTH: {
                "credits": 100,
                "price": 49,
                "name": "Growth",
                "overage_price": 0.75
            },
            PricingPlan.SCALE: {
                "credits": 300,
                "price": 99,
                "name": "Scale",
                "overage_price": 0.50
            },
            PricingPlan.ENTERPRISE: {
                "credits": -1,  # Unlimited
                "price": 299,
                "name": "Enterprise"
            }
        }
    
    async def get_current_usage(self, user_id: str) -> Dict[str, Any]:
        """
        Get current period usage for a customer
        """
        try:
            # Get current usage from Lago
            response = await self.client.get(
                f"{self.base_url}/customers/{user_id}/current_usage",
                params={"external_subscription_id": f"sub_{user_id}"}
            )
            
            if response.status_code == 200:
                data = response.json()
                usage = data.get("customer_usage", {}).get("charges_usage", [])
                
                # Find credit usage
                credit_usage = 0
                for charge in usage:
                    if charge.get("billable_metric", {}).get("code") == "credit_usage":
                        credit_usage = charge.get("units", 0)
                        break
                
                return {
                    "credits_used": credit_usage,
                    "raw_data": data
                }
            return {"credits_used": 0}
            
        except Exception as e:
            logger.error(f"Failed to get usage: {e}")
            return {"credits_used": 0}
    
    async def check_credits(self, user_id: str) -> Dict[str, Any]:
        """
        Check user's available credits
        Returns: {available: int, used: int, limit: int, can_proceed: bool}
        """
        try:
            # Get current usage from Lago
            response = await self.client.get(
                f"{self.base_url}/customers/{user_id}/current_usage"
            )
            
            if response.status_code != 200:
                logger.error(f"Lago API error: {response.status_code}")
                # Fail open in development, fail closed in production
                return {
                    "available": 0,
                    "used": 0,
                    "limit": 0,
                    "can_proceed": os.getenv("ENVIRONMENT") == "development"
                }
            
            data = response.json()
            usage = data.get("usage", {})
            
            # Get user's plan
            plan_response = await self.client.get(
                f"{self.base_url}/subscriptions?customer_id={user_id}"
            )
            
            if plan_response.status_code == 200:
                subscriptions = plan_response.json().get("subscriptions", [])
                if subscriptions:
                    plan_code = subscriptions[0].get("plan_code", "free_trial")
                    plan = self.plans.get(PricingPlan(plan_code), self.plans[PricingPlan.FREE_TRIAL])
                    
                    credits_used = usage.get("credits", 0)
                    credits_limit = plan["credits"]
                    
                    # Check if enterprise (unlimited)
                    if credits_limit == -1:
                        return {
                            "available": 999999,
                            "used": credits_used,
                            "limit": "unlimited",
                            "can_proceed": True
                        }
                    
                    # Check overage allowance
                    can_proceed = credits_used < credits_limit
                    if not can_proceed and "overage_price" in plan:
                        # Allow overage for paid plans
                        can_proceed = True
                    
                    return {
                        "available": max(0, credits_limit - credits_used),
                        "used": credits_used,
                        "limit": credits_limit,
                        "can_proceed": can_proceed,
                        "is_overage": credits_used >= credits_limit
                    }
            
            # No subscription - use free trial
            return {
                "available": 5,
                "used": 0,
                "limit": 5,
                "can_proceed": True
            }
            
        except Exception as e:
            logger.error(f"Credit check failed: {e}")
            # Fail open in dev, closed in prod
            return {
                "available": 0,
                "used": 0,
                "limit": 0,
                "can_proceed": os.getenv("ENVIRONMENT") == "development"
            }
    
    async def track_usage(self, user_id: str, event_type: str, credits: int = 1, metadata: Optional[Dict] = None) -> bool:
        """
        Track credit usage in Lago
        
        Args:
            user_id: User identifier (external_id in Lago)
            event_type: Type of usage (e.g., "company_analysis", "deck_generation") 
            credits: Number of credits to deduct
            metadata: Additional data (company names, model used, etc.)
        """
        try:
            # Lago event structure per their API docs
            event = {
                "event": {
                    "transaction_id": f"{user_id}_{datetime.utcnow().timestamp()}_{event_type}",
                    "external_subscription_id": f"sub_{user_id}",  # User's subscription ID
                    "code": "credit_usage",  # Billable metric code
                    "timestamp": int(datetime.utcnow().timestamp()),
                    "properties": {
                        "credits": credits,
                        "event_type": event_type,
                        **(metadata or {})
                    }
                }
            }
            
            response = await self.client.post(
                f"{self.base_url}/events",
                json=event
            )
            
            if response.status_code == 200:
                logger.info(f"Usage tracked: {user_id} used {credits} credits for {event_type}")
                
                # If model cost is provided, track it for internal metrics
                if metadata and "model_cost" in metadata:
                    await self._track_model_cost(
                        user_id,
                        metadata["model_cost"],
                        metadata.get("model_used", "unknown")
                    )
                
                return True
            else:
                logger.error(f"Failed to track usage: {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"Usage tracking failed: {e}")
            return False
    
    async def _track_model_cost(self, user_id: str, cost: float, model: str):
        """Internal tracking of actual model costs for margin analysis"""
        try:
            await self.client.post(
                f"{self.base_url}/events",
                json={
                    "transaction_id": f"cost_{user_id}_{datetime.utcnow().isoformat()}",
                    "customer_id": "internal_metrics",
                    "code": "model_cost",
                    "timestamp": datetime.utcnow().isoformat(),
                    "properties": {
                        "cost_usd": cost,
                        "model": model,
                        "user_id": user_id
                    }
                }
            )
        except Exception as e:
            logger.warning(f"Cost tracking failed: {e}")
    
    async def create_or_get_customer(self, user_id: str, email: str, name: str = None) -> bool:
        """
        Create or update customer in Lago
        """
        try:
            # Create customer with external_id (no payment provider needed for self-hosted)
            customer_data = {
                "customer": {
                    "external_id": user_id,  # Your system's user ID
                    "email": email,
                    "name": name or email,
                    "currency": "USD",  # Default currency
                    "tax_rate": 0  # Can be configured per customer
                }
            }
            
            response = await self.client.post(
                f"{self.base_url}/customers",
                json=customer_data
            )
            
            return response.status_code in [200, 201]
            
        except Exception as e:
            logger.error(f"Customer creation failed: {e}")
            return False
    
    async def create_subscription(self, user_id: str, plan: PricingPlan) -> Optional[Dict]:
        """
        Create a subscription for a customer
        Returns subscription details
        """
        try:
            # Create subscription per Lago API
            subscription_data = {
                "subscription": {
                    "external_customer_id": user_id,
                    "plan_code": plan.value,
                    "external_id": f"sub_{user_id}",  # Subscription external ID
                    "billing_time": "anniversary",  # or "calendar"
                    "subscription_at": datetime.utcnow().isoformat()
                }
            }
            
            response = await self.client.post(
                f"{self.base_url}/subscriptions",
                json=subscription_data
            )
            
            if response.status_code in [200, 201]:
                data = response.json()
                return data.get("subscription")
            else:
                logger.error(f"Failed to create subscription: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"Checkout creation failed: {e}")
            return None
    
    async def handle_webhook(self, event_type: str, data: Dict) -> bool:
        """
        Handle Lago webhooks (payment success, credit exhausted, etc.)
        """
        try:
            if event_type == "credit_exhausted":
                user_id = data.get("customer_id")
                logger.warning(f"User {user_id} exhausted credits")
                # Send notification, pause access, etc.
                
            elif event_type == "payment_succeeded":
                user_id = data.get("customer_id")
                logger.info(f"Payment successful for {user_id}")
                # Enable features, send confirmation, etc.
                
            elif event_type == "payment_failed":
                user_id = data.get("customer_id")
                logger.error(f"Payment failed for {user_id}")
                # Downgrade to free tier, send notification
                
            return True
            
        except Exception as e:
            logger.error(f"Webhook handling failed: {e}")
            return False


# Middleware for credit enforcement
class CreditMiddleware:
    """
    FastAPI middleware to check credits before processing requests
    """
    
    def __init__(self):
        self.lago = LagoService()
        self.protected_endpoints = [
            "/api/agent/unified-brain",
            "/api/valuation",
            "/api/deck/generate"
        ]
    
    async def __call__(self, request, call_next):
        """Check credits for protected endpoints"""
        
        # Skip non-protected endpoints
        if not any(request.url.path.startswith(ep) for ep in self.protected_endpoints):
            return await call_next(request)
        
        # Get user ID from auth token or session
        user_id = request.headers.get("X-User-ID") or request.session.get("user_id")
        
        if not user_id:
            from fastapi.responses import JSONResponse
            return JSONResponse(
                status_code=401,
                content={"error": "Authentication required"}
            )
        
        # Check credits
        credits = await self.lago.check_credits(user_id)
        
        if not credits["can_proceed"]:
            from fastapi.responses import JSONResponse
            return JSONResponse(
                status_code=402,  # Payment Required
                content={
                    "error": "Insufficient credits",
                    "credits_available": credits["available"],
                    "credits_used": credits["used"],
                    "upgrade_url": f"/billing/upgrade?user_id={user_id}"
                }
            )
        
        # Add credit info to request state
        request.state.credits = credits
        request.state.user_id = user_id
        
        # Process request
        response = await call_next(request)
        
        # Track usage if successful
        if response.status_code == 200:
            # Determine credits to charge based on endpoint
            credits_to_charge = 2  # Default for company comparison
            
            if "/deck/generate" in request.url.path:
                credits_to_charge = 4  # Deck generation costs more
            
            await self.lago.track_usage(
                user_id,
                event_type=request.url.path.split("/")[-1],
                credits=credits_to_charge,
                metadata={
                    "endpoint": request.url.path,
                    "timestamp": datetime.utcnow().isoformat()
                }
            )
        
        return response