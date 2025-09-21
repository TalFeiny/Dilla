#!/usr/bin/env python3
"""
Test the improved valuation scoring that considers entry points
Tests whether system now properly balances growth vs value at entry
"""

import asyncio
import json
from app.services.intelligent_gap_filler import IntelligentGapFiller

async def test_value_vs_growth_scoring():
    """Test that entry value is now properly considered alongside growth"""
    
    gap_filler = IntelligentGapFiller()
    
    # Test Case 1: High growth but expensive company (like n8n)
    expensive_growth_company = {
        "company": "FastGrowthCo",
        "revenue": 10_000_000,  # $10M revenue
        "valuation": 500_000_000,  # $500M valuation = 50x revenue (EXPENSIVE!)
        "growth_rate": 3.0,  # 300% YoY growth (very fast)
        "tam": 50_000_000_000,  # $50B TAM
        "stage": "Series B",
        "funding_rounds": [
            {"revenue": 2_000_000, "date": "2023-01"},
            {"revenue": 10_000_000, "date": "2024-01"}
        ]
    }
    
    # Test Case 2: Moderate growth but great value entry
    value_company = {
        "company": "ValueCo", 
        "revenue": 8_000_000,  # $8M revenue
        "valuation": 80_000_000,  # $80M valuation = 10x revenue (CHEAP!)
        "growth_rate": 1.5,  # 150% YoY growth (solid)
        "tam": 30_000_000_000,  # $30B TAM
        "stage": "Series B",
        "funding_rounds": [
            {"revenue": 3_000_000, "date": "2023-01"},
            {"revenue": 8_000_000, "date": "2024-01"}
        ]
    }
    
    # Test Case 3: Decelerating growth but still reasonable entry
    decelerating_company = {
        "company": "DeceleratingCo",
        "revenue": 15_000_000,  # $15M revenue  
        "valuation": 200_000_000,  # $200M valuation = 13x revenue
        "growth_rate": 0.8,  # 80% YoY growth (slowing)
        "tam": 20_000_000_000,  # $20B TAM
        "stage": "Series B",
        "funding_rounds": [
            {"revenue": 5_000_000, "date": "2022-01"},
            {"revenue": 10_000_000, "date": "2023-01"},  # Was 100% growth
            {"revenue": 15_000_000, "date": "2024-01"}   # Now 50% growth - DECELERATING
        ]
    }
    
    # Fund context
    fund_context = {
        "fund_size": 500_000_000,  # $500M fund
        "fund_year": 2,
        "portfolio_count": 8,
        "remaining_capital": 350_000_000,
        "deployment_rate": 0.30
    }
    
    print("=" * 80)
    print("TESTING IMPROVED VALUATION SCORING: Growth vs Value at Entry")
    print("=" * 80)
    
    # Score each company
    for company_data in [expensive_growth_company, value_company, decelerating_company]:
        print(f"\n📊 Analyzing {company_data['company']}:")
        print(f"  Revenue: ${company_data['revenue']/1e6:.1f}M")
        print(f"  Valuation: ${company_data['valuation']/1e6:.1f}M ({company_data['valuation']/company_data['revenue']:.1f}x revenue)")
        print(f"  Growth: {company_data['growth_rate']*100:.0f}%")
        
        # First infer missing data
        inferred_data = gap_filler.infer_missing_data(company_data, fund_context)
        # Then score with inferred data
        score_result = gap_filler.score_fund_fit(company_data, inferred_data, context=fund_context)
        
        print(f"\n  📈 SCORES:")
        print(f"    Overall Score: {score_result['overall_score']:.1f}/100")
        for key, value in score_result['component_scores'].items():
            print(f"    {key}: {value:.0f}")
        
        print(f"\n  💡 RECOMMENDATION: {score_result['recommendation']}")
        print(f"  🎯 ACTION: {score_result['action']}")
        
        print(f"\n  📝 KEY REASONS:")
        for reason in score_result['reasons'][:5]:  # Top 5 reasons
            print(f"    • {reason}")
        
        print(f"\n  💰 SPECIFIC RECOMMENDATIONS:")
        for rec in score_result['specific_recommendations'][:3]:  # Top 3 recommendations
            print(f"    • {rec}")
    
    print("\n" + "=" * 80)
    print("EXPECTED RESULTS:")
    print("=" * 80)
    print("1. FastGrowthCo: Should score LOWER due to 50x entry multiple despite 300% growth")
    print("2. ValueCo: Should score HIGHER due to attractive 10x entry with solid 150% growth")
    print("3. DeceleratingCo: Should score MODERATE - growth slowing but still reasonable entry")
    print("\nThe system should now favor ValueCo over FastGrowthCo!")
    print("=" * 80)

if __name__ == "__main__":
    asyncio.run(test_value_vs_growth_scoring())