#!/usr/bin/env python3
"""
Test all IPEV valuation methods with real-world scenarios
Validates fair value calculations across different methods
"""

import asyncio
import json
from datetime import datetime, timedelta
from app.services.valuation_engine_service import (
    ValuationEngineService, 
    ValuationRequest,
    Stage,
    ValuationMethod
)

async def test_all_ipev_methods():
    """Test all IPEV methods with realistic scenarios"""
    
    valuation_engine = ValuationEngineService()
    
    # Test Case 1: Recent Series B HR Tech company (like Sana pre-acquisition)
    sana_like = ValuationRequest(
        company_name="HRTechCo",
        stage=Stage.SERIES_B,
        revenue=50_000_000,  # $50M ARR
        growth_rate=1.0,  # 100% YoY
        last_round_valuation=500_000_000,  # $500M last round
        last_round_date=(datetime.now() - timedelta(days=180)).strftime("%Y-%m-%d"),  # 6 months ago
        total_raised=150_000_000,
        industry="hr_tech",
        business_model="SaaS"
    )
    
    # Test Case 2: Early stage AI search company (like Perplexity)
    perplexity_like = ValuationRequest(
        company_name="AISearchCo",
        stage=Stage.SERIES_A,
        revenue=10_000_000,  # $10M ARR
        growth_rate=3.0,  # 300% YoY (hypergrowth)
        last_round_valuation=250_000_000,
        last_round_date=(datetime.now() - timedelta(days=90)).strftime("%Y-%m-%d"),  # 3 months ago
        total_raised=50_000_000,
        industry="ai_search",
        business_model="AI-first SaaS"
    )
    
    # Test Case 3: Mature fintech (like Ramp)
    ramp_like = ValuationRequest(
        company_name="FintechCo",
        stage=Stage.SERIES_C,
        revenue=300_000_000,  # $300M ARR
        growth_rate=1.0,  # 100% YoY
        last_round_valuation=5_500_000_000,
        last_round_date=(datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d"),  # 1 year ago
        total_raised=1_000_000_000,
        industry="fintech",
        business_model="Payments"
    )
    
    # Test Case 4: Very early stage (for Cost Method)
    seed_company = ValuationRequest(
        company_name="SeedCo",
        stage=Stage.SEED,
        revenue=100_000,  # $100K ARR
        growth_rate=5.0,  # 500% but off small base
        last_round_valuation=10_000_000,
        last_round_date=(datetime.now() - timedelta(days=60)).strftime("%Y-%m-%d"),  # 2 months ago
        total_raised=3_000_000,
        industry="dev_tools",
        business_model="Developer Tools"
    )
    
    print("=" * 80)
    print("TESTING ALL IPEV FAIR VALUE METHODS")
    print("=" * 80)
    
    test_cases = [
        ("Sana-like (HR Tech Series B)", sana_like),
        ("Perplexity-like (AI Search Series A)", perplexity_like),
        ("Ramp-like (Fintech Series C)", ramp_like),
        ("Seed Stage Dev Tools", seed_company)
    ]
    
    methods = [
        ValuationMethod.RECENT_TRANSACTION,
        ValuationMethod.COMPARABLES,
        ValuationMethod.PWERM,
        ValuationMethod.DCF,
        ValuationMethod.COST_METHOD,
        ValuationMethod.MILESTONE
    ]
    
    for case_name, request in test_cases:
        print(f"\n{'='*60}")
        print(f"📊 {case_name}")
        print(f"{'='*60}")
        print(f"Revenue: ${request.revenue/1e6:.1f}M | Growth: {request.growth_rate*100:.0f}%")
        print(f"Last Round: ${request.last_round_valuation/1e6:.0f}M | Stage: {request.stage}")
        print(f"\nValuation Results:")
        print("-" * 60)
        
        results = {}
        for method in methods:
            try:
                request.method = method
                result = await valuation_engine.calculate_valuation(request)
                results[method.value] = result
                
                print(f"\n{method.value.upper()}:")
                print(f"  Fair Value: ${result.fair_value/1e6:.1f}M")
                print(f"  Confidence: {result.confidence*100:.0f}%")
                if result.dlom_discount:
                    print(f"  DLOM Applied: {result.dlom_discount*100:.0f}%")
                print(f"  Explanation: {result.explanation[:100]}...")
                
            except Exception as e:
                print(f"\n{method.value.upper()}: ❌ Error - {str(e)[:50]}")
        
        # Calculate average across high-confidence methods
        high_conf_values = [
            r.fair_value for r in results.values() 
            if r.confidence >= 0.7
        ]
        if high_conf_values:
            avg_value = sum(high_conf_values) / len(high_conf_values)
            print(f"\n💎 AVERAGE FAIR VALUE (high confidence): ${avg_value/1e6:.1f}M")
            
            # Compare to last round
            premium = (avg_value / request.last_round_valuation - 1) * 100
            print(f"📈 vs Last Round: {premium:+.1f}%")
    
    print("\n" + "=" * 80)
    print("KEY INSIGHTS:")
    print("=" * 80)
    print("1. Recent Transaction Method most reliable for <12 month old rounds")
    print("2. Comparables enhanced with M&A data provides market validation")
    print("3. PWERM best for early stage with multiple scenarios")
    print("4. DCF works well for mature companies with predictable revenue")
    print("5. Cost Method appropriate for very recent investments (<3 months)")
    print("6. Milestone Method useful for deep tech/biotech with clear markers")
    print("=" * 80)

if __name__ == "__main__":
    asyncio.run(test_all_ipev_methods())