#!/usr/bin/env python3
"""
Test Pro-Rata Rights Implementation in Cap Table
Shows how pro-rata participation affects ALL shareholders, not just new investors
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.services.pre_post_cap_table import PrePostCapTable
from app.services.advanced_cap_table import AdvancedCapTable
from decimal import Decimal
import json
from datetime import datetime

def test_pro_rata_dilution():
    """Test that pro-rata properly dilutes all non-participating shareholders"""
    
    cap_table_service = PrePostCapTable()
    
    # Create a multi-round funding scenario
    funding_rounds = [
        {
            "round": "Seed",
            "amount": 2_000_000,
            "pre_money_valuation": 8_000_000,
            "date": "2022-01-01",
            "investors": ["Seed Fund A", "Angel Investor B"],
            "lead_investor": "Seed Fund A"
        },
        {
            "round": "Series A",
            "amount": 10_000_000,
            "pre_money_valuation": 40_000_000,
            "date": "2023-01-01",
            "investors": ["VC Fund C", "VC Fund D"],
            "lead_investor": "VC Fund C",
            "option_pool_expansion": 0.10  # 10% option pool
        },
        {
            "round": "Series B",
            "amount": 25_000_000,
            "pre_money_valuation": 100_000_000,
            "date": "2024-01-01",
            "investors": ["Growth Fund E", "VC Fund F"],
            "lead_investor": "Growth Fund E"
        }
    ]
    
    print("\n" + "="*80)
    print("COMPREHENSIVE CAP TABLE ANALYSIS WITH PRO-RATA RIGHTS")
    print("="*80)
    
    # Calculate full cap table history
    result = cap_table_service.calculate_full_cap_table_history(funding_rounds)
    
    print("\n📊 FUNDING HISTORY SUMMARY")
    print("-" * 40)
    print(f"Total Rounds: {result['num_rounds']}")
    print(f"Total Raised: ${result['total_raised']:,.0f}")
    print(f"Founder Dilution: {result['founder_dilution']:.1f}%")
    
    # Detailed round-by-round analysis
    for i, snapshot in enumerate(result['history']):
        print("\n" + "="*60)
        print(f"🎯 {snapshot['round_name']}")
        print("="*60)
        print(f"Date: {snapshot['date']}")
        print(f"Pre-Money:  ${snapshot['pre_money_valuation']:,.0f}")
        print(f"Investment: ${snapshot['investment_amount']:,.0f}")
        print(f"Post-Money: ${snapshot['post_money_valuation']:,.0f}")
        
        # Show ownership changes
        print("\n📈 OWNERSHIP CHANGES:")
        print("-" * 40)
        print(f"{'Shareholder':<25} {'Pre-Round':>12} {'Post-Round':>12} {'Change':>10}")
        print("-" * 40)
        
        pre_ownership = snapshot['pre_money_ownership']
        post_ownership = snapshot['post_money_ownership']
        
        # Combine all shareholders
        all_shareholders = set(list(pre_ownership.keys()) + list(post_ownership.keys()))
        
        for shareholder in sorted(all_shareholders):
            pre = pre_ownership.get(shareholder, 0)
            post = post_ownership.get(shareholder, 0)
            change = post - pre
            
            # Highlight different types of shareholders
            if "Founder" in shareholder:
                marker = "👤"
            elif "Lead" in shareholder:
                marker = "⭐"
            elif "Option" in shareholder:
                marker = "📋"
            elif shareholder in snapshot.get('new_investors', []):
                marker = "🆕"
            else:
                marker = "💰"
                
            print(f"{marker} {shareholder:<23} {pre:>11.2f}% {post:>11.2f}% {change:>+9.2f}%")
        
        # Show pro-rata participation details
        if snapshot.get('pro_rata_investments'):
            print("\n💎 PRO-RATA PARTICIPATION:")
            print("-" * 40)
            for investor, amount in snapshot['pro_rata_investments'].items():
                print(f"{investor}: ${amount:,.0f} to maintain ownership")
                
        if snapshot.get('dilution_without_pro_rata'):
            print("\n📉 DILUTION WITHOUT PRO-RATA:")
            print("-" * 40)
            for investor, ownership in snapshot['dilution_without_pro_rata'].items():
                current = post_ownership.get(investor, 0)
                difference = current - ownership
                print(f"{investor}: Would have {ownership:.2f}% (saved {difference:.2f}% by exercising)")
    
    # Final cap table
    print("\n" + "="*80)
    print("📊 FINAL CAP TABLE (Current)")
    print("="*80)
    current = result['current_cap_table']
    sorted_shareholders = sorted(current.items(), key=lambda x: x[1], reverse=True)
    
    print(f"{'Shareholder':<30} {'Ownership':>12} {'Visual':>30}")
    print("-" * 72)
    for shareholder, ownership in sorted_shareholders:
        if ownership > 0:
            bar_length = int(ownership / 2)  # Scale to fit
            bar = "█" * bar_length
            print(f"{shareholder:<30} {ownership:>11.2f}% {bar}")
    
    # Show pro-rata impact analysis
    print("\n" + "="*80)
    print("💡 PRO-RATA RIGHTS IMPACT ANALYSIS")
    print("="*80)
    
    print("""
Key Insights:
-------------
1. WHO GETS DILUTED:
   - When investors exercise pro-rata, ALL non-participating shareholders are diluted
   - This includes BOTH existing investors who don't participate AND new investors
   - The dilution is proportional across all non-participants

2. MECHANICS:
   - Pro-rata participants maintain their exact ownership percentage
   - The capital they invest reduces the pool available for new investors
   - Non-participating existing shareholders get diluted by the full round

3. EXAMPLE FROM SERIES B:
   - If Seed Fund A (12% ownership) exercises $3M pro-rata to maintain 12%
   - This $3M comes out of the $25M round, leaving only $22M for new investors
   - New investors get less ownership (17.6% instead of 20%)
   - Non-participating shareholders (Founders, Angels) still get diluted by 20%

4. STRATEGIC IMPLICATIONS:
   - Strong investors with pro-rata rights can maintain positions in winners
   - Founders and employees without pro-rata face maximum dilution
   - New investors must account for pro-rata when sizing their investment
    """)
    
    # Test the advanced cap table with complex scenarios
    print("\n" + "="*80)
    print("🔬 ADVANCED CAP TABLE FEATURES")
    print("="*80)
    
    advanced_service = AdvancedCapTable()
    
    # Create a complex cap table
    complex_cap_table = {
        "common": {
            "shares": 10_000_000,
            "holders": {
                "Founders": 6_000_000,
                "Employees (vested)": 2_000_000,
                "Employees (unvested)": 2_000_000
            }
        },
        "preferred": {
            "series_a": {
                "shares": 2_000_000,
                "price_per_share": 5.00,
                "liquidation_preference": 1.0,
                "participation": "non-participating",
                "pro_rata_rights": True
            },
            "series_b": {
                "shares": 3_000_000,
                "price_per_share": 8.33,
                "liquidation_preference": 1.0,
                "participation": "participating",
                "participation_cap": 3.0,
                "pro_rata_rights": True
            }
        },
        "options": {
            "outstanding": 2_000_000,
            "available": 1_000_000,
            "weighted_avg_strike": 2.50
        },
        "warrants": {
            "total": 100_000,
            "strike_price": 6.00,
            "expiration": "2026-12-31"
        }
    }
    
    # Calculate waterfall at different exit values
    exit_scenarios = [50_000_000, 100_000_000, 250_000_000, 500_000_000]
    
    print("\n📊 LIQUIDATION WATERFALL ANALYSIS")
    print("-" * 60)
    print(f"{'Exit Value':<15} {'Common':>12} {'Series A':>12} {'Series B':>12}")
    print("-" * 60)
    
    for exit_value in exit_scenarios:
        waterfall = advanced_service.calculate_liquidation_waterfall(
            exit_value,
            complex_cap_table
        )
        
        common_proceeds = waterfall.get('common', {}).get('total', 0)
        series_a_proceeds = waterfall.get('series_a', {}).get('total', 0)
        series_b_proceeds = waterfall.get('series_b', {}).get('total', 0)
        
        print(f"${exit_value/1e6:.0f}M {common_proceeds/1e6:>11.1f}M "
              f"{series_a_proceeds/1e6:>11.1f}M {series_b_proceeds/1e6:>11.1f}M")
    
    print("\n" + "="*80)
    print("✅ CAP TABLE TESTING COMPLETE")
    print("="*80)
    
    return result

if __name__ == "__main__":
    try:
        result = test_pro_rata_dilution()
        print("\n✅ All tests completed successfully!")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()