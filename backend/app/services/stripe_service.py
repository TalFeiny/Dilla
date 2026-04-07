"""
Stripe Service — thin wrapper around the Stripe Python SDK.
Used by app.api.stripe_subscriptions endpoints.
"""

import os
import logging
import stripe
from typing import Optional, Dict, List, Any

logger = logging.getLogger(__name__)


class StripeService:
    def __init__(self):
        self.stripe_secret_key = os.getenv("STRIPE_SECRET_KEY", "")
        self.stripe_publishable_key = os.getenv("STRIPE_PUBLISHABLE_KEY", "")
        self.webhook_secret = os.getenv("STRIPE_WEBHOOK_SECRET", "")

        if self.stripe_secret_key:
            stripe.api_key = self.stripe_secret_key
            logger.info("Stripe API key configured")
        else:
            logger.warning("STRIPE_SECRET_KEY not set — Stripe calls will fail")

    # ── Products ──────────────────────────────────────────────────────

    def create_product(self, name: str, description: Optional[str] = None, metadata: Optional[Dict] = None):
        return stripe.Product.create(
            name=name,
            description=description,
            metadata=metadata or {},
        )

    def list_products(self, active: bool = True):
        return stripe.Product.list(active=active).data

    # ── Prices ────────────────────────────────────────────────────────

    def create_price(
        self,
        product_id: str,
        amount: int,
        currency: str = "gbp",
        interval: str = "month",
        interval_count: int = 1,
        nickname: Optional[str] = None,
        metadata: Optional[Dict] = None,
    ):
        return stripe.Price.create(
            product=product_id,
            unit_amount=amount,
            currency=currency,
            recurring={"interval": interval, "interval_count": interval_count},
            nickname=nickname,
            metadata=metadata or {},
        )

    def list_prices(self, product_id: Optional[str] = None, active: bool = True):
        params: Dict[str, Any] = {"active": active}
        if product_id:
            params["product"] = product_id
        return stripe.Price.list(**params).data

    # ── Customers ─────────────────────────────────────────────────────

    def create_customer(
        self,
        email: str,
        name: Optional[str] = None,
        payment_method_id: Optional[str] = None,
        metadata: Optional[Dict] = None,
    ):
        params: Dict[str, Any] = {"email": email, "metadata": metadata or {}}
        if name:
            params["name"] = name
        if payment_method_id:
            params["payment_method"] = payment_method_id
            params["invoice_settings"] = {"default_payment_method": payment_method_id}
        return stripe.Customer.create(**params)

    def get_customer(self, customer_id: str):
        return stripe.Customer.retrieve(customer_id)

    def get_or_create_customer(self, email: str, name: Optional[str] = None, metadata: Optional[Dict] = None):
        """Find existing customer by email, or create one."""
        existing = stripe.Customer.list(email=email, limit=1).data
        if existing:
            return existing[0]
        return self.create_customer(email=email, name=name, metadata=metadata)

    # ── Subscriptions ─────────────────────────────────────────────────

    def create_subscription(
        self,
        customer_id: str,
        price_id: str,
        trial_period_days: Optional[int] = None,
        metadata: Optional[Dict] = None,
        expand: Optional[List[str]] = None,
    ):
        params: Dict[str, Any] = {
            "customer": customer_id,
            "items": [{"price": price_id}],
            "metadata": metadata or {},
        }
        if trial_period_days:
            params["trial_period_days"] = trial_period_days
        if expand:
            params["expand"] = expand
        return stripe.Subscription.create(**params)

    def get_subscription(self, subscription_id: str):
        return stripe.Subscription.retrieve(subscription_id)

    def update_subscription(
        self,
        subscription_id: str,
        price_id: Optional[str] = None,
        quantity: Optional[int] = None,
        proration_behavior: str = "create_prorations",
        metadata: Optional[Dict] = None,
    ):
        params: Dict[str, Any] = {"proration_behavior": proration_behavior}
        if price_id:
            sub = stripe.Subscription.retrieve(subscription_id)
            params["items"] = [{"id": sub["items"]["data"][0]["id"], "price": price_id}]
        if quantity is not None:
            params["quantity"] = quantity
        if metadata:
            params["metadata"] = metadata
        return stripe.Subscription.modify(subscription_id, **params)

    def cancel_subscription(self, subscription_id: str, immediately: bool = False, feedback: Optional[str] = None):
        if immediately:
            return stripe.Subscription.cancel(subscription_id)
        return stripe.Subscription.modify(subscription_id, cancel_at_period_end=True)

    def list_subscriptions(self, customer_id: Optional[str] = None, status: Optional[str] = None):
        params: Dict[str, Any] = {}
        if customer_id:
            params["customer"] = customer_id
        if status:
            params["status"] = status
        return stripe.Subscription.list(**params).data

    # ── Checkout Sessions ─────────────────────────────────────────────

    def create_checkout_session(
        self,
        price_id: str,
        success_url: str,
        cancel_url: str,
        customer_email: Optional[str] = None,
        customer_id: Optional[str] = None,
        trial_period_days: Optional[int] = None,
        allow_promotion_codes: bool = True,
        metadata: Optional[Dict] = None,
    ):
        params: Dict[str, Any] = {
            "mode": "subscription",
            "line_items": [{"price": price_id, "quantity": 1}],
            "success_url": success_url,
            "cancel_url": cancel_url,
            "allow_promotion_codes": allow_promotion_codes,
            "metadata": metadata or {},
        }
        if customer_id:
            params["customer"] = customer_id
        elif customer_email:
            params["customer_email"] = customer_email
        sub_data: Dict[str, Any] = {}
        if trial_period_days:
            sub_data["trial_period_days"] = trial_period_days
        if metadata:
            sub_data["metadata"] = metadata  # Copy metadata to the subscription too
        if sub_data:
            params["subscription_data"] = sub_data
        return stripe.checkout.Session.create(**params)

    # ── Customer Portal ───────────────────────────────────────────────

    def create_customer_portal_session(self, customer_id: str, return_url: str):
        return stripe.billing_portal.Session.create(
            customer=customer_id,
            return_url=return_url,
        )

    # ── Payment Methods ───────────────────────────────────────────────

    def attach_payment_method(self, payment_method_id: str, customer_id: str):
        return stripe.PaymentMethod.attach(payment_method_id, customer=customer_id)

    def set_default_payment_method(self, customer_id: str, payment_method_id: str):
        return stripe.Customer.modify(
            customer_id,
            invoice_settings={"default_payment_method": payment_method_id},
        )

    def list_payment_methods(self, customer_id: str, type: str = "card"):
        return stripe.PaymentMethod.list(customer=customer_id, type=type).data

    # ── Webhooks ──────────────────────────────────────────────────────

    def validate_webhook_signature(self, payload: bytes, sig_header: str):
        if not self.webhook_secret:
            logger.warning("No webhook secret configured — skipping signature check")
            import json
            return json.loads(payload)
        return stripe.Webhook.construct_event(payload, sig_header, self.webhook_secret)


# Singleton
stripe_service = StripeService()
