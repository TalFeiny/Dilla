"""
Subscription Plans Configuration
"""
from typing import Dict, List, Any
from enum import Enum

class PlanTier(str, Enum):
    FREE = "free"
    STARTER = "starter"
    PROFESSIONAL = "professional"
    ENTERPRISE = "enterprise"

class BillingInterval(str, Enum):
    MONTHLY = "month"
    YEARLY = "year"

# Plan features and limits
PLAN_FEATURES = {
    PlanTier.FREE: {
        "name": "Free",
        "description": "Perfect for trying out our platform",
        "features": [
            "Up to 5 company analyses per month",
            "Basic market research",
            "Limited API calls (100/month)",
            "Community support",
            "Basic data export (CSV)"
        ],
        "limits": {
            "companies_per_month": 5,
            "api_calls_per_month": 100,
            "users": 1,
            "data_retention_days": 30,
            "export_formats": ["csv"],
            "advanced_analytics": False,
            "custom_reports": False,
            "priority_support": False
        }
    },
    PlanTier.STARTER: {
        "name": "Starter",
        "description": "Great for small teams and growing startups",
        "features": [
            "Up to 50 company analyses per month",
            "Enhanced market research",
            "Standard API calls (1,000/month)",
            "Email support",
            "Export to CSV and Excel",
            "Basic analytics dashboard",
            "7-day free trial"
        ],
        "limits": {
            "companies_per_month": 50,
            "api_calls_per_month": 1000,
            "users": 5,
            "data_retention_days": 90,
            "export_formats": ["csv", "excel"],
            "advanced_analytics": False,
            "custom_reports": False,
            "priority_support": False
        }
    },
    PlanTier.PROFESSIONAL: {
        "name": "Professional",
        "description": "For professional investors and VC firms",
        "features": [
            "Up to 500 company analyses per month",
            "Deep market intelligence",
            "Enhanced API calls (10,000/month)",
            "Priority email & chat support",
            "Export to CSV, Excel, and PDF",
            "Advanced analytics & insights",
            "Custom report templates",
            "Team collaboration features",
            "14-day free trial"
        ],
        "limits": {
            "companies_per_month": 500,
            "api_calls_per_month": 10000,
            "users": 20,
            "data_retention_days": 365,
            "export_formats": ["csv", "excel", "pdf"],
            "advanced_analytics": True,
            "custom_reports": True,
            "priority_support": True,
            "custom_integrations": False
        }
    },
    PlanTier.ENTERPRISE: {
        "name": "Enterprise",
        "description": "Custom solutions for large organizations",
        "features": [
            "Unlimited company analyses",
            "Premium market intelligence",
            "Unlimited API calls",
            "Dedicated account manager",
            "24/7 phone & email support",
            "All export formats + custom formats",
            "White-label options",
            "Custom integrations",
            "SLA guarantee",
            "On-premise deployment option"
        ],
        "limits": {
            "companies_per_month": -1,  # Unlimited
            "api_calls_per_month": -1,  # Unlimited
            "users": -1,  # Unlimited
            "data_retention_days": -1,  # Unlimited
            "export_formats": ["csv", "excel", "pdf", "json", "custom"],
            "advanced_analytics": True,
            "custom_reports": True,
            "priority_support": True,
            "custom_integrations": True,
            "white_label": True,
            "sla": True
        }
    }
}

# Pricing configuration (in cents)
PLAN_PRICING = {
    PlanTier.FREE: {
        BillingInterval.MONTHLY: 0,
        BillingInterval.YEARLY: 0
    },
    PlanTier.STARTER: {
        BillingInterval.MONTHLY: 9900,  # $99/month
        BillingInterval.YEARLY: 99000   # $990/year (2 months free)
    },
    PlanTier.PROFESSIONAL: {
        BillingInterval.MONTHLY: 49900,  # $499/month
        BillingInterval.YEARLY: 499000   # $4,990/year (2 months free)
    },
    PlanTier.ENTERPRISE: {
        BillingInterval.MONTHLY: None,  # Custom pricing
        BillingInterval.YEARLY: None    # Custom pricing
    }
}

# Add-on services (for usage-based billing)
ADDON_SERVICES = {
    "extra_companies": {
        "name": "Additional Company Analyses",
        "description": "Analyze more companies beyond your plan limit",
        "price_per_unit": 1000,  # $10 per company
        "unit": "company"
    },
    "extra_api_calls": {
        "name": "Additional API Calls",
        "description": "Extra API calls beyond your plan limit",
        "price_per_unit": 100,  # $1 per 100 calls
        "unit": "100 calls"
    },
    "priority_processing": {
        "name": "Priority Processing",
        "description": "Jump to the front of the queue",
        "price_per_unit": 5000,  # $50 per request
        "unit": "request"
    },
    "custom_report": {
        "name": "Custom Report Generation",
        "description": "Generate a custom investment report",
        "price_per_unit": 25000,  # $250 per report
        "unit": "report"
    },
    "data_export": {
        "name": "Bulk Data Export",
        "description": "Export large datasets",
        "price_per_unit": 10000,  # $100 per export
        "unit": "export"
    }
}

# Trial periods (in days)
TRIAL_PERIODS = {
    PlanTier.FREE: 0,
    PlanTier.STARTER: 7,
    PlanTier.PROFESSIONAL: 14,
    PlanTier.ENTERPRISE: 30
}

# Discount codes
PROMO_CODES = {
    "LAUNCH50": {
        "description": "50% off first 3 months",
        "percent_off": 50,
        "duration": "repeating",
        "duration_in_months": 3,
        "valid_until": "2025-12-31"
    },
    "YEARLY20": {
        "description": "20% off yearly plans",
        "percent_off": 20,
        "duration": "forever",
        "applies_to": [BillingInterval.YEARLY],
        "valid_until": "2025-12-31"
    },
    "STARTUP": {
        "description": "Special pricing for startups",
        "percent_off": 30,
        "duration": "repeating",
        "duration_in_months": 12,
        "valid_until": "2025-12-31",
        "metadata": {
            "requirements": "Must be a startup with < $5M funding"
        }
    }
}

def get_plan_details(tier: PlanTier) -> Dict[str, Any]:
    """Get complete details for a plan tier"""
    return {
        "tier": tier.value,
        "features": PLAN_FEATURES.get(tier, {}),
        "pricing": PLAN_PRICING.get(tier, {}),
        "trial_days": TRIAL_PERIODS.get(tier, 0)
    }

def calculate_price_with_discount(
    base_price: int,
    promo_code: str = None,
    billing_interval: BillingInterval = BillingInterval.MONTHLY
) -> int:
    """Calculate price after applying discount"""
    if not promo_code or promo_code not in PROMO_CODES:
        return base_price
    
    promo = PROMO_CODES[promo_code]
    
    # Check if promo applies to billing interval
    if "applies_to" in promo and billing_interval not in promo["applies_to"]:
        return base_price
    
    # Calculate discounted price
    discount_amount = int(base_price * (promo["percent_off"] / 100))
    return base_price - discount_amount

def validate_plan_upgrade(current_tier: PlanTier, new_tier: PlanTier) -> bool:
    """Validate if a plan upgrade is allowed"""
    tier_order = [PlanTier.FREE, PlanTier.STARTER, PlanTier.PROFESSIONAL, PlanTier.ENTERPRISE]
    
    current_index = tier_order.index(current_tier)
    new_index = tier_order.index(new_tier)
    
    # Allow upgrades and downgrades
    return current_index != new_index

def get_usage_limits(tier: PlanTier) -> Dict[str, Any]:
    """Get usage limits for a plan tier"""
    features = PLAN_FEATURES.get(tier, {})
    return features.get("limits", {})

def check_usage_limit(tier: PlanTier, resource: str, current_usage: int) -> bool:
    """Check if usage is within plan limits"""
    limits = get_usage_limits(tier)
    limit = limits.get(resource, 0)
    
    # -1 means unlimited
    if limit == -1:
        return True
    
    return current_usage < limit