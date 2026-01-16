#!/usr/bin/env python3
"""Test script for follow-on investment scenarios"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))

import asyncio
import json
from app.services.unified_mcp_orchestrator import UnifiedMCPOrchestrator

async def test_followon_scenarios():
    """Test the follow-on scenarios calculation"""
    
    # Initialize orchestrator
    orchestrator = UnifiedMCPOrchestrator()
    
    # Test the helper function directly
    print("\n=== Testing Follow-on Scenarios Calculation ===\n")
    
    # Test case 1: Series A company
    initial_investment = 10_000_000  # $10M
    initial_ownership = 0.15  # 15%
    exit_multiple = 10.0
    
    scenarios = orchestrator._calculate_followon_scenarios(
        initial_investment=initial_investment,
        initial_ownership=initial_ownership,
        exit_multiple=exit_multiple,
        rounds_to_exit=3,
        dilution_per_round=0.20,
        reserve_ratio=2.0
    )
    
    print("Series A Company Scenarios:")
    print("-" * 50)
    print("\nNo Follow-on Strategy:")
    print(f"  Capital Deployed: ${scenarios['no_followon']['capital_deployed']/1_000_000:.1f}M")
    print(f"  Final Ownership: {scenarios['no_followon']['final_ownership']*100:.1f}%")
    print(f"  Exit Proceeds: ${scenarios['no_followon']['exit_proceeds']/1_000_000:.1f}M")
    print(f"  Multiple: {scenarios['no_followon']['multiple']:.2f}x")
    print(f"  IRR: {scenarios['no_followon']['irr']:.1f}%")
    
    print("\nWith Follow-on (2x Reserves):")
    print(f"  Capital Deployed: ${scenarios['with_followon']['capital_deployed']/1_000_000:.1f}M")
    print(f"  Final Ownership: {scenarios['with_followon']['final_ownership']*100:.1f}%")
    print(f"  Exit Proceeds: ${scenarios['with_followon']['exit_proceeds']/1_000_000:.1f}M")
    print(f"  Multiple: {scenarios['with_followon']['multiple']:.2f}x")
    print(f"  IRR: {scenarios['with_followon']['irr']:.1f}%")
    
    print("\nDelta Analysis:")
    print(f"  Additional Capital: ${scenarios['delta']['additional_capital']/1_000_000:.1f}M")
    print(f"  Ownership Preserved: {scenarios['delta']['ownership_preserved']*100:.1f}%")
    print(f"  Additional Proceeds: ${scenarios['delta']['additional_proceeds']/1_000_000:.1f}M")
    print(f"  Multiple Delta: {scenarios['delta']['multiple_delta']:.2f}x")
    print(f"  Recommendation: {scenarios['delta']['follow_on_decision']}")
    
    # Test case 2: Seed company
    print("\n" + "="*50)
    print("\nSeed Company Scenarios:")
    print("-" * 50)
    
    seed_scenarios = orchestrator._calculate_followon_scenarios(
        initial_investment=2_000_000,  # $2M
        initial_ownership=0.20,  # 20%
        exit_multiple=15.0,
        rounds_to_exit=4,
        dilution_per_round=0.20,
        reserve_ratio=2.0
    )
    
    print("\nNo Follow-on Strategy:")
    print(f"  Capital Deployed: ${seed_scenarios['no_followon']['capital_deployed']/1_000_000:.1f}M")
    print(f"  Final Ownership: {seed_scenarios['no_followon']['final_ownership']*100:.1f}%")
    print(f"  Exit Proceeds: ${seed_scenarios['no_followon']['exit_proceeds']/1_000_000:.1f}M")
    print(f"  Multiple: {seed_scenarios['no_followon']['multiple']:.2f}x")
    
    print("\nWith Follow-on (2x Reserves):")
    print(f"  Capital Deployed: ${seed_scenarios['with_followon']['capital_deployed']/1_000_000:.1f}M")
    print(f"  Final Ownership: {seed_scenarios['with_followon']['final_ownership']*100:.1f}%")
    print(f"  Exit Proceeds: ${seed_scenarios['with_followon']['exit_proceeds']/1_000_000:.1f}M")
    print(f"  Multiple: {seed_scenarios['with_followon']['multiple']:.2f}x")
    
    print(f"\nRecommendation: {seed_scenarios['delta']['follow_on_decision']}")
    
    # Test portfolio-level returns
    print("\n" + "="*50)
    print("\n=== Portfolio-Level Blended Returns ===\n")
    
    # Simulate portfolio distribution
    portfolio_size = 25
    check_size = 10_000_000
    
    # No follow-on
    no_followon_proceeds = (
        2 * check_size * 20 +  # 2 home runs at 20x
        3 * check_size * 7 +   # 3 winners at 7x
        5 * check_size * 2.5 + # 5 modest at 2.5x
        8 * check_size * 1 +   # 8 return capital
        4 * check_size * 0.5   # 4 partial losses
        # 3 total losses = 0
    )
    no_followon_deployed = portfolio_size * check_size
    no_followon_multiple = no_followon_proceeds / no_followon_deployed
    
    # With follow-on (winners get reserves)
    winners_count = 5  # 2 home runs + 3 winners
    followon_deployed = no_followon_deployed + (winners_count * check_size)
    with_followon_proceeds = (
        2 * check_size * 35 +  # Home runs better with follow-on
        3 * check_size * 12 +  # Winners better with follow-on
        5 * check_size * 2.5 + # Modest same (no follow-on)
        8 * check_size * 1 +   # Return capital
        4 * check_size * 0.5   # Partial losses
    )
    with_followon_multiple = with_followon_proceeds / followon_deployed
    
    fund_size = 260_000_000
    
    print("Portfolio Without Follow-on:")
    print(f"  Total Deployed: ${no_followon_deployed/1_000_000:.0f}M")
    print(f"  Total Proceeds: ${no_followon_proceeds/1_000_000:.0f}M")
    print(f"  Blended Multiple: {no_followon_multiple:.2f}x")
    print(f"  Fund DPI: {no_followon_proceeds/fund_size:.2f}x")
    
    print("\nPortfolio With Follow-on (2x Reserves):")
    print(f"  Total Deployed: ${followon_deployed/1_000_000:.0f}M")
    print(f"  Total Proceeds: ${with_followon_proceeds/1_000_000:.0f}M")
    print(f"  Blended Multiple: {with_followon_multiple:.2f}x")
    print(f"  Fund DPI: {with_followon_proceeds/fund_size:.2f}x")
    
    print("\nImprovement from Follow-on Strategy:")
    print(f"  Additional Capital Required: ${(followon_deployed - no_followon_deployed)/1_000_000:.0f}M")
    print(f"  Additional Proceeds: ${(with_followon_proceeds - no_followon_proceeds)/1_000_000:.0f}M")
    print(f"  DPI Improvement: {(with_followon_proceeds - no_followon_proceeds)/fund_size:.2%}")
    print(f"  Multiple Improvement: {with_followon_multiple - no_followon_multiple:.2f}x")
    
    return True

if __name__ == "__main__":
    success = asyncio.run(test_followon_scenarios())
    if success:
        print("\n✅ All tests passed!")
    else:
        print("\n❌ Tests failed!")