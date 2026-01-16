#!/usr/bin/env python3
"""Test that revenue inference applies all adjustments correctly"""

import asyncio
import sys
sys.path.append('/Users/admin/code/dilla-ai/backend')

from app.services.intelligent_gap_filler import IntelligentGapFiller

async def test_revenue_adjustments():
    gap_filler = IntelligentGapFiller()
    
    # Test company with SF location and Sequoia as investor
    test_company = {
        "name": "TestCo",
        "stage": "Series B",
        "headquarters": "San Francisco, CA",
        "funding_rounds": [
            {
                "round": "Series B",
                "amount": 30_000_000,
                "date": "2024-01-15",  # ~11 months ago
                "investors": ["Sequoia Capital", "Index Ventures"]
            },
            {
                "round": "Series A", 
                "amount": 10_000_000,
                "date": "2023-01-15",
                "investors": ["Accel Partners"]
            }
        ]
    }
    
    print("Testing revenue inference with adjustments...")
    print(f"Company: {test_company['name']}")
    print(f"Stage: {test_company['stage']}")
    print(f"Location: {test_company['headquarters']}")
    print(f"Investors: Sequoia Capital (Tier 1)")
    print(f"Last funding: 2024-01-15 (11 months ago)")
    print()
    
    # Test the calculate_gpu_adjusted_metrics method which contains the revenue inference
    gpu_metrics = gap_filler.calculate_gpu_adjusted_metrics(test_company)
    result = gpu_metrics.get('final_revenue', 0)
    print(f"Inferred Revenue: ${result:,.0f}")
    
    # Expected calculation:
    # Base (Series B arr_median): $8,000,000
    # Time adjustment (11 months at 1.5x growth): ~1.42x
    # Geography (SF): 1.15x
    # Investor (Sequoia): 1.2x
    # Total: $8M * 1.42 * 1.15 * 1.2 = ~$15.7M
    
    expected_min = 14_000_000  # Allow some variance
    expected_max = 18_000_000
    
    print(f"\nExpected range: ${expected_min:,.0f} - ${expected_max:,.0f}")
    print(f"Base Series B median: $8,000,000")
    print(f"× Time growth (~11 months): ~1.42x")
    print(f"× SF premium: 1.15x")
    print(f"× Tier 1 VC boost: 1.2x")
    print(f"= Expected: ~$15,700,000")
    
    if expected_min <= result <= expected_max:
        print("\n✅ PASS: Revenue adjustments are being applied correctly!")
    else:
        print(f"\n❌ FAIL: Revenue {result:,.0f} is outside expected range!")
        if result == 8_000_000:
            print("   Looks like raw median is being used without adjustments!")
    
    return result

if __name__ == "__main__":
    result = asyncio.run(test_revenue_adjustments())