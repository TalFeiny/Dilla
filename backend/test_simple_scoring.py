#!/usr/bin/env python3
"""
Simple test for improved valuation scoring
"""

import asyncio
from app.services.intelligent_gap_filler import IntelligentGapFiller, InferenceResult

async def test_scoring():
    gap_filler = IntelligentGapFiller()
    
    # Test data with all required fields
    expensive_company = {
        "company": "ExpensiveCo",
        "revenue": 10_000_000,
        "inferred_revenue": 10_000_000,
        "valuation": 500_000_000,  # 50x revenue!
        "growth_rate": 3.0,
        "tam": 50_000_000_000,
        "stage": "Series B",
        "sector": "AI",
        "geography": "US",
        "last_round_amount": 50_000_000,
        "runway": 18,
        "next_round_timing": 12
    }
    
    cheap_company = {
        "company": "CheapCo",
        "revenue": 10_000_000,
        "inferred_revenue": 10_000_000,
        "valuation": 100_000_000,  # 10x revenue
        "growth_rate": 1.5,
        "tam": 50_000_000_000,
        "stage": "Series B", 
        "sector": "AI",
        "geography": "US",
        "last_round_amount": 20_000_000,
        "runway": 24,
        "next_round_timing": 12
    }
    
    fund_context = {
        "fund_size": 500_000_000,
        "fund_year": 2,
        "portfolio_count": 8,
        "remaining_capital": 350_000_000
    }
    
    print("Testing Entry Value Scoring:\n")
    
    # Create dummy inferred data (empty since we have all fields)
    inferred_data = {}
    
    # Score both companies
    print("ExpensiveCo (50x revenue multiple):")
    expensive_score = gap_filler.score_fund_fit(expensive_company, inferred_data, fund_context)
    print(f"  Overall Score: {expensive_score['overall_score']:.1f}")
    print(f"  Entry Value Score: {expensive_score['component_scores'].get('entry_value', 0):.0f}")
    print(f"  Growth Trajectory: {expensive_score['component_scores'].get('growth_trajectory', 0):.0f}")
    print(f"  Recommendation: {expensive_score['recommendation']}\n")
    
    print("CheapCo (10x revenue multiple):")
    cheap_score = gap_filler.score_fund_fit(cheap_company, inferred_data, fund_context)
    print(f"  Overall Score: {cheap_score['overall_score']:.1f}")
    print(f"  Entry Value Score: {cheap_score['component_scores'].get('entry_value', 0):.0f}")
    print(f"  Growth Trajectory: {cheap_score['component_scores'].get('growth_trajectory', 0):.0f}")
    print(f"  Recommendation: {cheap_score['recommendation']}\n")
    
    print("✅ CheapCo should score HIGHER than ExpensiveCo due to better entry value!")
    print(f"Result: CheapCo ({cheap_score['overall_score']:.1f}) vs ExpensiveCo ({expensive_score['overall_score']:.1f})")
    
    if cheap_score['overall_score'] > expensive_score['overall_score']:
        print("SUCCESS: System now properly values entry price!")
    else:
        print("ISSUE: System still overvaluing growth vs entry price")

if __name__ == "__main__":
    asyncio.run(test_scoring())