"""
Stripe Subscription API Endpoints
"""
from fastapi import APIRouter, HTTPException, Request, Header, Depends, BackgroundTasks
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field
import logging
from datetime import datetime
import stripe

from app.services.stripe_service import stripe_service
from app.core.auth import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/stripe", tags=["stripe"])

# Pydantic models for request/response
class CreateProductRequest(BaseModel):
    name: str
    description: Optional[str] = None
    metadata: Optional[Dict[str, str]] = None

class CreatePriceRequest(BaseModel):
    product_id: str
    amount: int = Field(..., description="Amount in cents")
    currency: str = "usd"
    interval: str = Field("month", description="Billing interval: day, week, month, year")
    interval_count: int = 1
    nickname: Optional[str] = None
    metadata: Optional[Dict[str, str]] = None

class CreateCustomerRequest(BaseModel):
    email: str
    name: Optional[str] = None
    payment_method_id: Optional[str] = None
    metadata: Optional[Dict[str, str]] = None

class CreateSubscriptionRequest(BaseModel):
    customer_id: str
    price_id: str
    trial_period_days: Optional[int] = None
    metadata: Optional[Dict[str, str]] = None

class UpdateSubscriptionRequest(BaseModel):
    price_id: Optional[str] = None
    quantity: Optional[int] = None
    proration_behavior: str = "create_prorations"
    metadata: Optional[Dict[str, str]] = None

class CancelSubscriptionRequest(BaseModel):
    immediately: bool = False
    feedback: Optional[str] = None

class CreateCheckoutSessionRequest(BaseModel):
    price_id: str
    success_url: str
    cancel_url: str
    customer_email: Optional[str] = None
    customer_id: Optional[str] = None
    trial_period_days: Optional[int] = None
    allow_promotion_codes: bool = True
    metadata: Optional[Dict[str, str]] = None

class CreatePortalSessionRequest(BaseModel):
    customer_id: str
    return_url: str

class AttachPaymentMethodRequest(BaseModel):
    payment_method_id: str
    customer_id: str
    set_as_default: bool = True

# Product endpoints
@router.post("/products")
async def create_product(request: CreateProductRequest):
    """Create a new product"""
    try:
        product = stripe_service.create_product(
            name=request.name,
            description=request.description,
            metadata=request.metadata
        )
        return {"success": True, "product": product}
    except Exception as e:
        logger.error(f"Error creating product: {e}")
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/products")
async def list_products(active: bool = True):
    """List all products"""
    try:
        products = stripe_service.list_products(active=active)
        return {"success": True, "products": products}
    except Exception as e:
        logger.error(f"Error listing products: {e}")
        raise HTTPException(status_code=400, detail=str(e))

# Price endpoints
@router.post("/prices")
async def create_price(request: CreatePriceRequest):
    """Create a new price for a product"""
    try:
        price = stripe_service.create_price(
            product_id=request.product_id,
            amount=request.amount,
            currency=request.currency,
            interval=request.interval,
            interval_count=request.interval_count,
            nickname=request.nickname,
            metadata=request.metadata
        )
        return {"success": True, "price": price}
    except Exception as e:
        logger.error(f"Error creating price: {e}")
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/prices")
async def list_prices(product_id: Optional[str] = None, active: bool = True):
    """List all prices"""
    try:
        prices = stripe_service.list_prices(product_id=product_id, active=active)
        return {"success": True, "prices": prices}
    except Exception as e:
        logger.error(f"Error listing prices: {e}")
        raise HTTPException(status_code=400, detail=str(e))

# Customer endpoints
@router.post("/customers")
async def create_customer(request: CreateCustomerRequest):
    """Create a new customer"""
    try:
        customer = stripe_service.create_customer(
            email=request.email,
            name=request.name,
            payment_method_id=request.payment_method_id,
            metadata=request.metadata
        )
        return {"success": True, "customer": customer}
    except Exception as e:
        logger.error(f"Error creating customer: {e}")
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/customers/{customer_id}")
async def get_customer(customer_id: str):
    """Get customer details"""
    try:
        customer = stripe_service.get_customer(customer_id)
        return {"success": True, "customer": customer}
    except Exception as e:
        logger.error(f"Error getting customer: {e}")
        raise HTTPException(status_code=404, detail=str(e))

# Subscription endpoints
@router.post("/subscriptions")
async def create_subscription(request: CreateSubscriptionRequest):
    """Create a new subscription"""
    try:
        subscription = stripe_service.create_subscription(
            customer_id=request.customer_id,
            price_id=request.price_id,
            trial_period_days=request.trial_period_days,
            metadata=request.metadata,
            expand=["latest_invoice.payment_intent"]
        )
        return {"success": True, "subscription": subscription}
    except Exception as e:
        logger.error(f"Error creating subscription: {e}")
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/subscriptions/{subscription_id}")
async def get_subscription(subscription_id: str):
    """Get subscription details"""
    try:
        subscription = stripe_service.get_subscription(subscription_id)
        return {"success": True, "subscription": subscription}
    except Exception as e:
        logger.error(f"Error getting subscription: {e}")
        raise HTTPException(status_code=404, detail=str(e))

@router.put("/subscriptions/{subscription_id}")
async def update_subscription(subscription_id: str, request: UpdateSubscriptionRequest):
    """Update a subscription (change plan, quantity, etc.)"""
    try:
        subscription = stripe_service.update_subscription(
            subscription_id=subscription_id,
            price_id=request.price_id,
            quantity=request.quantity,
            proration_behavior=request.proration_behavior,
            metadata=request.metadata
        )
        return {"success": True, "subscription": subscription}
    except Exception as e:
        logger.error(f"Error updating subscription: {e}")
        raise HTTPException(status_code=400, detail=str(e))

@router.delete("/subscriptions/{subscription_id}")
async def cancel_subscription(subscription_id: str, request: CancelSubscriptionRequest):
    """Cancel a subscription"""
    try:
        subscription = stripe_service.cancel_subscription(
            subscription_id=subscription_id,
            immediately=request.immediately,
            feedback=request.feedback
        )
        return {"success": True, "subscription": subscription}
    except Exception as e:
        logger.error(f"Error cancelling subscription: {e}")
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/subscriptions")
async def list_subscriptions(
    customer_id: Optional[str] = None,
    status: Optional[str] = None
):
    """List subscriptions"""
    try:
        subscriptions = stripe_service.list_subscriptions(
            customer_id=customer_id,
            status=status
        )
        return {"success": True, "subscriptions": subscriptions}
    except Exception as e:
        logger.error(f"Error listing subscriptions: {e}")
        raise HTTPException(status_code=400, detail=str(e))

# Checkout session endpoints
@router.post("/checkout/sessions")
async def create_checkout_session(request: CreateCheckoutSessionRequest):
    """Create a Stripe Checkout session"""
    try:
        session = stripe_service.create_checkout_session(
            price_id=request.price_id,
            success_url=request.success_url,
            cancel_url=request.cancel_url,
            customer_email=request.customer_email,
            customer_id=request.customer_id,
            trial_period_days=request.trial_period_days,
            allow_promotion_codes=request.allow_promotion_codes,
            metadata=request.metadata
        )
        return {"success": True, "session": session}
    except Exception as e:
        logger.error(f"Error creating checkout session: {e}")
        raise HTTPException(status_code=400, detail=str(e))

# Customer portal endpoints
@router.post("/portal/sessions")
async def create_portal_session(request: CreatePortalSessionRequest):
    """Create a customer portal session"""
    try:
        session = stripe_service.create_customer_portal_session(
            customer_id=request.customer_id,
            return_url=request.return_url
        )
        return {"success": True, "session": session}
    except Exception as e:
        logger.error(f"Error creating portal session: {e}")
        raise HTTPException(status_code=400, detail=str(e))

# Payment method endpoints
@router.post("/payment-methods/attach")
async def attach_payment_method(request: AttachPaymentMethodRequest):
    """Attach a payment method to a customer"""
    try:
        payment_method = stripe_service.attach_payment_method(
            payment_method_id=request.payment_method_id,
            customer_id=request.customer_id
        )
        
        if request.set_as_default:
            stripe_service.set_default_payment_method(
                customer_id=request.customer_id,
                payment_method_id=request.payment_method_id
            )
        
        return {"success": True, "payment_method": payment_method}
    except Exception as e:
        logger.error(f"Error attaching payment method: {e}")
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/payment-methods/{customer_id}")
async def list_payment_methods(customer_id: str, type: str = "card"):
    """List payment methods for a customer"""
    try:
        payment_methods = stripe_service.list_payment_methods(
            customer_id=customer_id,
            type=type
        )
        return {"success": True, "payment_methods": payment_methods}
    except Exception as e:
        logger.error(f"Error listing payment methods: {e}")
        raise HTTPException(status_code=400, detail=str(e))

# Webhook endpoint
@router.post("/webhooks")
async def handle_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    stripe_signature: str = Header(None)
):
    """Handle Stripe webhooks"""
    try:
        payload = await request.body()
        event = stripe_service.validate_webhook_signature(payload, stripe_signature)
        
        # Handle different event types
        event_type = event["type"]
        event_data = event["data"]["object"]
        
        logger.info(f"Received webhook event: {event_type}")
        
        # Process events asynchronously
        background_tasks.add_task(process_webhook_event, event_type, event_data)
        
        return {"success": True, "received": True}
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        raise HTTPException(status_code=400, detail=str(e))

async def process_webhook_event(event_type: str, event_data: Dict):
    """Process webhook events asynchronously"""
    try:
        if event_type == "customer.subscription.created":
            logger.info(f"Subscription created: {event_data['id']}")
            # Handle new subscription
            
        elif event_type == "customer.subscription.updated":
            logger.info(f"Subscription updated: {event_data['id']}")
            # Handle subscription update
            
        elif event_type == "customer.subscription.deleted":
            logger.info(f"Subscription cancelled: {event_data['id']}")
            # Handle subscription cancellation
            
        elif event_type == "invoice.payment_succeeded":
            logger.info(f"Payment succeeded: {event_data['id']}")
            # Handle successful payment
            
        elif event_type == "invoice.payment_failed":
            logger.info(f"Payment failed: {event_data['id']}")
            # Handle failed payment
            
        elif event_type == "checkout.session.completed":
            logger.info(f"Checkout completed: {event_data['id']}")
            # Handle checkout completion
            
        else:
            logger.info(f"Unhandled event type: {event_type}")
            
    except Exception as e:
        logger.error(f"Error processing webhook event: {e}")

# Configuration endpoint to get publishable key
@router.get("/config")
async def get_stripe_config():
    """Get Stripe configuration for frontend"""
    return {
        "publishableKey": stripe_service.stripe_publishable_key,
        "mode": "subscription"
    }