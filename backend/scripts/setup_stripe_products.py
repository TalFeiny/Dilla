#!/usr/bin/env python3
"""
Setup script to create Stripe products and prices for the subscription plans
Run this once to initialize your Stripe account with the subscription plans
"""
import os
import sys
import stripe
from dotenv import load_dotenv

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config.subscription_plans import PLAN_FEATURES, PLAN_PRICING, PlanTier, BillingInterval

load_dotenv()

def setup_stripe_products():
    """Create products and prices in Stripe"""
    
    # Initialize Stripe
    stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
    
    if not stripe.api_key:
        print("❌ Error: STRIPE_SECRET_KEY not found in environment variables")
        print("Please set up your .env file with Stripe credentials")
        return False
    
    products_created = {}
    prices_created = {}
    
    try:
        # Create products for each plan tier (except Free)
        for tier in [PlanTier.STARTER, PlanTier.PROFESSIONAL]:
            plan_info = PLAN_FEATURES[tier]
            
            print(f"\n📦 Creating product for {tier.value} plan...")
            
            # Create product
            product = stripe.Product.create(
                name=f"Dilla AI {plan_info['name']} Plan",
                description=plan_info['description'],
                metadata={
                    "tier": tier.value,
                    "features": ", ".join(plan_info['features'][:3])  # Store first 3 features
                }
            )
            
            products_created[tier] = product
            print(f"✅ Created product: {product.id}")
            
            # Create prices for monthly and yearly billing
            for interval in [BillingInterval.MONTHLY, BillingInterval.YEARLY]:
                price_amount = PLAN_PRICING[tier][interval]
                
                if price_amount is None:
                    continue
                
                print(f"💰 Creating {interval.value} price...")
                
                # Create recurring price
                price = stripe.Price.create(
                    product=product.id,
                    unit_amount=price_amount,
                    currency="usd",
                    recurring={
                        "interval": interval.value,
                        "interval_count": 1 if interval == BillingInterval.MONTHLY else 12
                    },
                    nickname=f"{plan_info['name']} {interval.value.capitalize()}",
                    metadata={
                        "tier": tier.value,
                        "billing_interval": interval.value
                    }
                )
                
                prices_created[f"{tier.value}_{interval.value}"] = price
                print(f"✅ Created price: {price.id} (${price_amount/100}/{interval.value})")
        
        # Print summary
        print("\n" + "="*50)
        print("🎉 Stripe setup completed successfully!")
        print("="*50)
        
        print("\n📋 Created Products:")
        for tier, product in products_created.items():
            print(f"  - {tier.value}: {product.id}")
        
        print("\n💳 Created Prices:")
        for key, price in prices_created.items():
            print(f"  - {key}: {price.id}")
        
        # Generate environment variables
        print("\n🔧 Add these to your .env file:")
        print("-"*50)
        
        if PlanTier.STARTER in products_created:
            starter_monthly = prices_created.get(f"{PlanTier.STARTER.value}_{BillingInterval.MONTHLY.value}")
            starter_yearly = prices_created.get(f"{PlanTier.STARTER.value}_{BillingInterval.YEARLY.value}")
            
            if starter_monthly:
                print(f"NEXT_PUBLIC_STRIPE_STARTER_MONTHLY={starter_monthly.id}")
            if starter_yearly:
                print(f"NEXT_PUBLIC_STRIPE_STARTER_YEARLY={starter_yearly.id}")
        
        if PlanTier.PROFESSIONAL in products_created:
            pro_monthly = prices_created.get(f"{PlanTier.PROFESSIONAL.value}_{BillingInterval.MONTHLY.value}")
            pro_yearly = prices_created.get(f"{PlanTier.PROFESSIONAL.value}_{BillingInterval.YEARLY.value}")
            
            if pro_monthly:
                print(f"NEXT_PUBLIC_STRIPE_PRO_MONTHLY={pro_monthly.id}")
            if pro_yearly:
                print(f"NEXT_PUBLIC_STRIPE_PRO_YEARLY={pro_yearly.id}")
        
        print("-"*50)
        
        # Create promo codes
        print("\n🎁 Creating promotional codes...")
        
        # Create a coupon for launch discount
        coupon = stripe.Coupon.create(
            percent_off=50,
            duration="repeating",
            duration_in_months=3,
            name="Launch Discount",
            metadata={"code": "LAUNCH50"}
        )
        
        promo_code = stripe.PromotionCode.create(
            coupon=coupon.id,
            code="LAUNCH50"
        )
        
        print(f"✅ Created promo code: LAUNCH50 (50% off for 3 months)")
        
        # Create webhook endpoint
        print("\n🔗 Setting up webhook endpoint...")
        print("Please manually create a webhook endpoint in the Stripe Dashboard:")
        print(f"  URL: https://your-domain.com/api/stripe/webhooks")
        print("  Events to listen for:")
        print("    - customer.subscription.created")
        print("    - customer.subscription.updated")
        print("    - customer.subscription.deleted")
        print("    - invoice.payment_succeeded")
        print("    - invoice.payment_failed")
        print("    - checkout.session.completed")
        
        return True
        
    except stripe.error.StripeError as e:
        print(f"\n❌ Stripe Error: {e}")
        return False
    except Exception as e:
        print(f"\n❌ Error: {e}")
        return False

def check_existing_products():
    """Check if products already exist"""
    stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
    
    try:
        products = stripe.Product.list(limit=100)
        
        if products.data:
            print("\n📦 Existing products found:")
            for product in products.data:
                print(f"  - {product.name} ({product.id})")
            
            response = input("\n⚠️  Products already exist. Continue anyway? (y/n): ")
            return response.lower() == 'y'
        
        return True
        
    except Exception as e:
        print(f"Error checking existing products: {e}")
        return False

if __name__ == "__main__":
    print("🚀 Stripe Products Setup Script")
    print("="*50)
    
    # Check for existing products
    if not check_existing_products():
        print("Setup cancelled.")
        sys.exit(0)
    
    # Run setup
    success = setup_stripe_products()
    
    if success:
        print("\n✅ Setup completed successfully!")
        print("\nNext steps:")
        print("1. Add the generated environment variables to your .env file")
        print("2. Create the webhook endpoint in Stripe Dashboard")
        print("3. Start your application and test the subscription flow")
    else:
        print("\n❌ Setup failed. Please check the errors above.")
        sys.exit(1)