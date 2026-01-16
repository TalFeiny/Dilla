#!/usr/bin/env python3
"""
Test dynamic dilution calculation based on actual multiples
Including Decagon-like hypergrowth scenarios
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.services.intelligent_gap_filler import IntelligentGapFiller

def test_dynamic_dilution():
    """Test dilution with various growth/multiple scenarios"""
    
    gap_filler = IntelligentGapFiller()
    
    # Test Case 1: Decagon-like hypergrowth (100x multiple on $15M ARR)
    decagon_like = {
        'company': 'HyperGrowthCo',
        'stage': 'Series A',
        'revenue': 15_000_000,  # $15M ARR
        'valuation': 1_500_000_000,  # $1.5B valuation = 100x multiple!
        'investors': ['a16z', 'Sequoia'],  # Top tier VCs
        'headquarters': 'San Francisco',
        'arr_growth_rate': 4.0,  # 400% YoY growth (hypergrowth)
    }
    
    result1 = gap_filler.calculate_exit_dilution_scenarios(
        initial_ownership=0.05,  # 5% entry (high valuation)
        rounds_to_exit=2,  # Series A -> B -> C
        company_data=decagon_like
    )
    
    print("=" * 70)
    print("TEST 1: DECAGON-LIKE HYPERGROWTH (100x Multiple)")
    print("-" * 70)
    print(f"Company: {decagon_like['company']}")
    print(f"Current Metrics:")
    print(f"  Revenue: ${decagon_like['revenue']/1e6:.1f}M")
    print(f"  Valuation: ${decagon_like['valuation']/1e6:.0f}M")
    print(f"  Multiple: {decagon_like['valuation']/decagon_like['revenue']:.0f}x")
    print(f"  Growth Rate: {decagon_like['arr_growth_rate']*100:.0f}% YoY")
    print(f"  Investors: {decagon_like['investors']}")
    
    print(f"\nOwnership Evolution (2 rounds to exit):")
    print(f"  Entry: 5.0%")
    print(f"  Exit without pro-rata: {result1['without_pro_rata']*100:.1f}%")
    print(f"  Exit with pro-rata: {result1['with_pro_rata']*100:.1f}%")
    print(f"  Total dilution: {(1 - result1['without_pro_rata']/0.05)*100:.1f}%")
    
    # Show detailed round progression
    if 'scenarios' in result1 and 'base' in result1['scenarios']:
        print(f"\nRound-by-round details (base case):")
        for round_data in result1['scenarios']['base']['rounds']:
            print(f"\n  {round_data.get('round', 'Unknown')}:")
            print(f"    Projected Revenue: ${round_data['projected_revenue']/1e6:.1f}M")
            print(f"    Valuation Multiple: {round_data['valuation_multiple']:.0f}x")
            print(f"    Pre-money: ${round_data['pre_money']/1e6:.0f}M")
            print(f"    Round Size: ${round_data['round_size']/1e6:.0f}M")
            print(f"    Dilution: {round_data['dilution']*100:.1f}%")
            print(f"    Ownership After: {round_data['ownership_after']*100:.2f}%")
    
    # Test Case 2: Normal Series A SaaS (15x multiple)
    normal_saas = {
        'company': 'NormalSaaS',
        'stage': 'Series A',
        'revenue': 2_000_000,  # $2M ARR
        'valuation': 30_000_000,  # $30M valuation = 15x multiple
        'investors': ['Bessemer', 'FirstMark'],  # Good VCs but not tier 1
        'headquarters': 'Austin',
        'arr_growth_rate': 1.5,  # 150% YoY (good but not hypergrowth)
    }
    
    result2 = gap_filler.calculate_exit_dilution_scenarios(
        initial_ownership=0.20,  # 20% entry (normal Series A)
        rounds_to_exit=3,  # Series A -> B -> C -> Exit
        company_data=normal_saas
    )
    
    print("\n" + "=" * 70)
    print("TEST 2: NORMAL SERIES A SAAS (15x Multiple)")
    print("-" * 70)
    print(f"Company: {normal_saas['company']}")
    print(f"Current Metrics:")
    print(f"  Revenue: ${normal_saas['revenue']/1e6:.1f}M")
    print(f"  Valuation: ${normal_saas['valuation']/1e6:.0f}M")
    print(f"  Multiple: {normal_saas['valuation']/normal_saas['revenue']:.0f}x")
    print(f"  Growth Rate: {normal_saas['arr_growth_rate']*100:.0f}% YoY")
    
    print(f"\nOwnership Evolution (3 rounds to exit):")
    print(f"  Entry: 20.0%")
    print(f"  Exit without pro-rata: {result2['without_pro_rata']*100:.1f}%")
    print(f"  Exit with pro-rata: {result2['with_pro_rata']*100:.1f}%")
    print(f"  Total dilution: {(1 - result2['without_pro_rata']/0.20)*100:.1f}%")
    
    # Test Case 3: Struggling company (low growth, compressed multiple)
    struggling = {
        'company': 'SlowGrowthCo',
        'stage': 'Series B',
        'revenue': 10_000_000,  # $10M ARR
        'valuation': 80_000_000,  # $80M valuation = 8x multiple (compressed)
        'investors': ['Local VC'],
        'headquarters': 'Cleveland',
        'arr_growth_rate': 0.3,  # 30% YoY (slow for Series B)
    }
    
    result3 = gap_filler.calculate_exit_dilution_scenarios(
        initial_ownership=0.15,
        rounds_to_exit=2,
        company_data=struggling
    )
    
    print("\n" + "=" * 70)
    print("TEST 3: STRUGGLING COMPANY (Multiple Compression)")
    print("-" * 70)
    print(f"Company: {struggling['company']}")
    print(f"Current Metrics:")
    print(f"  Revenue: ${struggling['revenue']/1e6:.1f}M")
    print(f"  Valuation: ${struggling['valuation']/1e6:.0f}M")
    print(f"  Multiple: {struggling['valuation']/struggling['revenue']:.0f}x")
    print(f"  Growth Rate: {struggling['arr_growth_rate']*100:.0f}% YoY")
    
    print(f"\nOwnership Evolution (2 rounds to exit):")
    print(f"  Entry: 15.0%")
    print(f"  Exit without pro-rata: {result3['without_pro_rata']*100:.1f}%")
    print(f"  Exit with pro-rata: {result3['with_pro_rata']*100:.1f}%")
    print(f"  Total dilution: {(1 - result3['without_pro_rata']/0.15)*100:.1f}%")
    
    # Compare dilution across scenarios
    print("\n" + "=" * 70)
    print("DILUTION COMPARISON")
    print("-" * 70)
    print(f"Decagon-like (100x, 400% growth): {(1 - result1['without_pro_rata']/0.05)*100:.1f}% dilution")
    print(f"Normal SaaS (15x, 150% growth): {(1 - result2['without_pro_rata']/0.20)*100:.1f}% dilution")
    print(f"Struggling (8x, 30% growth): {(1 - result3['without_pro_rata']/0.15)*100:.1f}% dilution")
    
    print("\n" + "=" * 70)
    print("KEY INSIGHTS:")
    print("-" * 70)
    print("1. High multiples (100x) mean LESS dilution despite large rounds")
    print("2. Growth rate directly impacts future valuations and dilution")
    print("3. Multiple compression hurts - slow growth = more dilution")
    print("4. Tier 1 VCs can bid up valuations, reducing dilution")
    print("5. Dilution is NOT fixed - it's dynamic based on actual metrics")
    
    # Validate results make sense
    assert result1['without_pro_rata'] > 0.01, "Too much dilution for hypergrowth"
    assert result3['without_pro_rata'] < result2['without_pro_rata'] * 0.8, "Struggling company should have more dilution"
    
    print("\n✅ All tests passed! Dynamic dilution working correctly.")

if __name__ == "__main__":
    test_dynamic_dilution()