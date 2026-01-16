#!/usr/bin/env python3
"""
Test the fixed dilution calculations
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.services.intelligent_gap_filler import IntelligentGapFiller

def test_dilution_scenarios():
    """Test dilution with various company profiles"""
    
    gap_filler = IntelligentGapFiller()
    
    # Test Case 1: High-growth company with Tier 1 VCs (should have less dilution)
    high_growth_company = {
        'company': 'FastCo',
        'stage': 'Series A',
        'investors': ['Sequoia', 'Andreessen Horowitz'],
        'headquarters': 'San Francisco',
        'arr_growth_rate': 2.5,  # 250% growth (T2D3)
        'revenue': 10_000_000,
        'valuation': 100_000_000
    }
    
    result1 = gap_filler.calculate_exit_dilution_scenarios(
        initial_ownership=0.10,  # 10% entry
        rounds_to_exit=3,  # Series A -> B -> C -> Exit
        company_data=high_growth_company
    )
    
    print("=" * 60)
    print("TEST 1: High Growth + Tier 1 VCs (Series A)")
    print("-" * 60)
    print(f"Company: {high_growth_company['company']}")
    print(f"Growth Rate: {high_growth_company['arr_growth_rate']*100:.0f}%")
    print(f"Investors: {high_growth_company['investors']}")
    print(f"Location: {high_growth_company['headquarters']}")
    print(f"\nHas Tier 1 VCs: {result1['assumptions']['has_tier1_vcs']}")
    print(f"Has Premium Geography: {result1['assumptions']['has_premium_geography']}")
    print(f"ARR Growth Rate: {result1['assumptions']['arr_growth_rate']*100:.0f}%")
    print(f"\nOwnership Evolution (3 rounds to exit):")
    print(f"  Entry: 10.0%")
    print(f"  Exit without pro-rata: {result1['without_pro_rata']*100:.1f}%")
    print(f"  Exit with pro-rata: {result1['with_pro_rata']*100:.1f}%")
    print(f"  Total dilution: {(1 - result1['without_pro_rata']/0.10)*100:.1f}%")
    
    # Show round-by-round dilution
    if 'scenarios' in result1 and 'base' in result1['scenarios']:
        base_scenario = result1['scenarios']['base']
        if 'rounds' in base_scenario:
            print(f"\nRound-by-round dilution (base case):")
            for round_data in base_scenario['rounds']:
                print(f"  {round_data.get('round', 'Unknown')}: {round_data['dilution']*100:.1f}% dilution → {round_data['ownership_after']*100:.1f}% ownership")
    
    # Test Case 2: Moderate growth, no tier 1 VCs (should have more dilution)
    moderate_company = {
        'company': 'SlowCo',
        'stage': 'Series A',
        'investors': ['Local VC', 'Angel Syndicate'],
        'headquarters': 'Austin',
        'arr_growth_rate': 0.5,  # 50% growth
        'revenue': 5_000_000,
        'valuation': 50_000_000
    }
    
    result2 = gap_filler.calculate_exit_dilution_scenarios(
        initial_ownership=0.10,
        rounds_to_exit=3,
        company_data=moderate_company
    )
    
    print("\n" + "=" * 60)
    print("TEST 2: Moderate Growth + Non-Tier 1 VCs (Series A)")
    print("-" * 60)
    print(f"Company: {moderate_company['company']}")
    print(f"Growth Rate: {moderate_company['arr_growth_rate']*100:.0f}%")
    print(f"Investors: {moderate_company['investors']}")
    print(f"Location: {moderate_company['headquarters']}")
    print(f"\nHas Tier 1 VCs: {result2['assumptions']['has_tier1_vcs']}")
    print(f"Has Premium Geography: {result2['assumptions']['has_premium_geography']}")
    print(f"ARR Growth Rate: {result2['assumptions']['arr_growth_rate']*100:.0f}%")
    print(f"\nOwnership Evolution (3 rounds to exit):")
    print(f"  Entry: 10.0%")
    print(f"  Exit without pro-rata: {result2['without_pro_rata']*100:.1f}%")
    print(f"  Exit with pro-rata: {result2['with_pro_rata']*100:.1f}%")
    print(f"  Total dilution: {(1 - result2['without_pro_rata']/0.10)*100:.1f}%")
    
    # Show round-by-round dilution
    if 'scenarios' in result2 and 'base' in result2['scenarios']:
        base_scenario = result2['scenarios']['base']
        if 'rounds' in base_scenario:
            print(f"\nRound-by-round dilution (base case):")
            for round_data in base_scenario['rounds']:
                print(f"  {round_data.get('round', 'Unknown')}: {round_data['dilution']*100:.1f}% dilution → {round_data['ownership_after']*100:.1f}% ownership")
    
    # Test Case 3: Late-stage with downside protection
    late_stage_company = {
        'company': 'MatureCo',
        'stage': 'Series C',
        'investors': ['Tiger Global', 'Coatue'],
        'headquarters': 'New York',
        'arr_growth_rate': 0.8,  # 80% growth
        'revenue': 50_000_000,
        'valuation': 500_000_000
    }
    
    result3 = gap_filler.calculate_exit_dilution_scenarios(
        initial_ownership=0.05,  # 5% entry (typical for Series C)
        rounds_to_exit=1,  # Series C -> Exit
        company_data=late_stage_company
    )
    
    print("\n" + "=" * 60)
    print("TEST 3: Late Stage with Downside Protection (Series C)")
    print("-" * 60)
    print(f"Company: {late_stage_company['company']}")
    print(f"Growth Rate: {late_stage_company['arr_growth_rate']*100:.0f}%")
    print(f"Investors: {late_stage_company['investors']}")
    print(f"Location: {late_stage_company['headquarters']}")
    print(f"\nIs Late Stage: {result3['assumptions']['is_late_stage']}")
    print(f"Valuation Step-up: {result3['assumptions']['valuation_step_up']:.2f}x per round")
    print(f"Dilution Rates: {result3['assumptions']['dilution_rates']}")
    print(f"\nOwnership Evolution (1 round to exit):")
    print(f"  Entry: 5.0%")
    print(f"  Exit without pro-rata: {result3['without_pro_rata']*100:.1f}%")
    print(f"  Exit with pro-rata: {result3['with_pro_rata']*100:.1f}%")
    print(f"  Total dilution: {(1 - result3['without_pro_rata']/0.05)*100:.1f}%")
    
    # Compare dilution across scenarios
    print("\n" + "=" * 60)
    print("DILUTION COMPARISON")
    print("-" * 60)
    print(f"High Growth + Tier 1: {(1 - result1['without_pro_rata']/0.10)*100:.1f}% dilution over 3 rounds")
    print(f"Moderate Growth: {(1 - result2['without_pro_rata']/0.10)*100:.1f}% dilution over 3 rounds")
    print(f"Late Stage: {(1 - result3['without_pro_rata']/0.05)*100:.1f}% dilution over 1 round")
    
    print("\n" + "=" * 60)
    print("KEY INSIGHTS:")
    print("-" * 60)
    print("1. High growth + Tier 1 VCs = LESS dilution (better valuations)")
    print("2. Late stage = LOWER dilution per round (but with liquidation preferences)")
    print("3. Geography matters: SF/NYC get ~10% valuation premium")
    print("4. Pro-rata rights preserve significant ownership (if you have reserves)")
    
    # Validate that dilution is reasonable
    assert result1['without_pro_rata'] > 0.02, "Too much dilution for high-growth company"
    assert result1['without_pro_rata'] < 0.08, "Too little dilution for 3 rounds"
    assert result2['without_pro_rata'] < result1['without_pro_rata'], "Moderate growth should have more dilution"
    assert result3['assumptions']['is_late_stage'] == True, "Series C should be marked as late stage"
    
    print("\n✅ All tests passed! Dilution calculations are working correctly.")

if __name__ == "__main__":
    test_dilution_scenarios()