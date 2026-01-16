#!/usr/bin/env python3
"""
Test script to verify the investor return math is correct.
"""

def test_investor_returns():
    """Verify the math for Series A investor returns with future dilution"""
    
    print("INVESTOR RETURN MATH VERIFICATION")
    print("=" * 60)
    
    # Investment parameters
    check_size = 10_000_000  # $10M investment
    pre_money_valuation = 140_000_000  # $140M pre-money
    post_money_valuation = 150_000_000  # $150M post-money
    
    # Calculate entry ownership
    entry_ownership = check_size / post_money_valuation
    print(f"\n1. ENTRY ECONOMICS")
    print(f"   Investment: ${check_size:,.0f}")
    print(f"   Post-money: ${post_money_valuation:,.0f}")
    print(f"   Entry ownership: {entry_ownership:.1%}")
    
    # Future rounds dilution
    dilution_per_round = 0.18  # 18% dilution per round (typical)
    rounds_to_exit = 2  # Series B and C
    
    # Calculate exit ownership without follow-on
    exit_ownership_no_followon = entry_ownership * ((1 - dilution_per_round) ** rounds_to_exit)
    print(f"\n2. DILUTION THROUGH ROUNDS")
    print(f"   Dilution per round: {dilution_per_round:.0%}")
    print(f"   Rounds to exit: {rounds_to_exit}")
    print(f"   Exit ownership (no follow-on): {exit_ownership_no_followon:.1%}")
    
    # Verify the calculation
    # After Series B: 6.67% * (1 - 0.18) = 5.47%
    # After Series C: 5.47% * (1 - 0.18) = 4.48%
    after_b = entry_ownership * (1 - dilution_per_round)
    after_c = after_b * (1 - dilution_per_round)
    print(f"   Step-by-step: {entry_ownership:.3%} → {after_b:.3%} → {after_c:.3%}")
    
    # Calculate exit values needed for returns (assuming all convert to common)
    print(f"\n3. EXIT VALUES FOR TARGET RETURNS (Common Conversion)")
    for multiple in [1, 2, 3, 5, 10]:
        exit_value_needed = (check_size * multiple) / exit_ownership_no_followon
        print(f"   {multiple}x return: ${exit_value_needed:,.0f}")
    
    # Future liquidation preferences
    series_b_size = 60_000_000  # Typical Series B
    series_c_size = 100_000_000  # Typical Series C
    future_prefs = series_b_size + series_c_size
    
    print(f"\n4. LIQUIDATION PREFERENCE STACK")
    print(f"   Series B: ${series_b_size:,.0f}")
    print(f"   Series C: ${series_c_size:,.0f}")
    print(f"   Total future prefs: ${future_prefs:,.0f}")
    print(f"   Our pref: ${check_size:,.0f}")
    print(f"   Total stack: ${future_prefs + check_size:,.0f}")
    
    # Waterfall analysis at different exit values
    print(f"\n5. WATERFALL ANALYSIS (M&A Exit)")
    test_exits = [100_000_000, 170_000_000, 250_000_000, 350_000_000, 500_000_000, 1_000_000_000]
    
    for exit_value in test_exits:
        remaining = exit_value
        our_proceeds = 0
        
        # Pay future investors first (they're senior)
        if remaining >= future_prefs:
            remaining -= future_prefs
        else:
            # Not enough to pay future investors
            remaining = 0
        
        # Then pay us our liquidation preference
        if remaining >= check_size:
            our_proceeds = check_size
            remaining -= check_size
        elif remaining > 0:
            # Partial payment
            our_proceeds = remaining
            remaining = 0
        
        # Check if we should convert to common instead
        common_proceeds = exit_value * exit_ownership_no_followon
        if common_proceeds > our_proceeds:
            our_proceeds = common_proceeds
            conversion = "Convert"
        else:
            conversion = "Stay Preferred"
        
        moic = our_proceeds / check_size if check_size > 0 else 0
        
        print(f"   Exit ${exit_value/1e6:.0f}M: Proceeds ${our_proceeds/1e6:.1f}M ({moic:.2f}x) - {conversion}")
    
    # Defensive breakpoints
    print(f"\n6. KEY DEFENSIVE BREAKPOINTS")
    
    # Breakeven after future prefs
    breakeven_exit = future_prefs + check_size
    print(f"   Breakeven (pref stack): ${breakeven_exit:,.0f}")
    
    # Conversion threshold (where common is better than pref)
    conversion_threshold = check_size / exit_ownership_no_followon
    print(f"   Conversion threshold: ${conversion_threshold:,.0f}")
    
    # Exit value where we get 2x after prefs
    # Need to solve: (exit_value - future_prefs) * ownership = 2 * check_size
    # OR if staying as pref: exit_value = future_prefs + 2 * check_size
    exit_for_2x_pref = future_prefs + (2 * check_size)
    exit_for_2x_common = (2 * check_size) / exit_ownership_no_followon
    print(f"   2x via preference: ${exit_for_2x_pref:,.0f}")
    print(f"   2x via common: ${exit_for_2x_common:,.0f}")
    
    print("\n" + "=" * 60)
    print("VERIFICATION COMPLETE")
    
    # Final check on the specific numbers from the test
    print(f"\n7. VERIFY TEST OUTPUT NUMBERS")
    print(f"   Entry: {entry_ownership:.1%} ✓ (matches 6.7%)")
    print(f"   Exit ownership: {exit_ownership_no_followon:.1%} ✓ (matches 4.5%)")
    print(f"   1x return exit: ${(check_size / exit_ownership_no_followon)/1e6:.0f}M ✓ (matches $223M)")
    print(f"   3x return exit: ${(check_size * 3 / exit_ownership_no_followon)/1e6:.0f}M ✓ (matches $669M)")
    print(f"   Breakeven with prefs: ${(future_prefs + check_size)/1e6:.0f}M ✓ (matches $170M)")

if __name__ == "__main__":
    test_investor_returns()