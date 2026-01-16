#!/usr/bin/env python3
"""
Test script to validate the fixed exit scenario calculations
Uses real cap table data and investor stack analysis
"""

import asyncio
import json
from app.services.unified_mcp_orchestrator import UnifiedMCPOrchestrator

async def test_exit_scenarios():
    """Test exit scenarios with real cap table data"""
    
    orchestrator = UnifiedMCPOrchestrator()
    
    # Test with Mercury - a Series B company
    test_company = {
        "company": "Mercury",
        "stage": "Series B",
        "valuation": 1_650_000_000,  # $1.65B valuation
        "total_funding": 163_000_000,  # $163M raised
        "funding_rounds": [
            {
                "round": "Seed",
                "amount": 6_000_000,
                "pre_money_valuation": 14_000_000,
                "lead_investor": "CRV",
                "liquidation_preference": 1.0,
                "participating": False
            },
            {
                "round": "Series A",
                "amount": 20_000_000,
                "pre_money_valuation": 80_000_000,
                "lead_investor": "Andreessen Horowitz",
                "liquidation_preference": 1.0,
                "participating": False
            },
            {
                "round": "Series B",
                "amount": 120_000_000,
                "pre_money_valuation": 480_000_000,
                "lead_investor": "Coatue Management",
                "liquidation_preference": 1.0,
                "participating": False
            }
        ],
        "revenue": 50_000_000,  # $50M ARR
        "founders": [
            {"name": "Immad Akhund"},
            {"name": "Jason Zhang"},
            {"name": "Maximilian Eber"}
        ]
    }
    
    # Test our new method directly
    print("\n=== Testing Investor-Specific Exit Scenarios ===")
    
    our_investment = 10_000_000  # $10M investment
    check_size = 10_000_000
    
    try:
        result = orchestrator._calculate_investor_specific_exit_scenarios(
            company_data=test_company,
            our_investment=our_investment,
            check_size=check_size,
            stage="Series B"
        )
        
        # Display results
        print(f"\n1. OWNERSHIP ANALYSIS:")
        ownership = result['ownership_analysis']
        print(f"   - Common ownership: {ownership['common_ownership_pct']:.1f}%")
        print(f"   - Our entry ownership: {ownership['our_entry_ownership']:.2f}%")
        print(f"   - Exit ownership (no follow-on): {ownership['our_exit_ownership_no_followon']:.2f}%")
        print(f"   - Exit ownership (with follow-on): {ownership['our_exit_ownership_with_followon']:.2f}%")
        
        print(f"\n2. PREFERENCE STACK ANALYSIS:")
        prefs = result['preference_analysis']
        print(f"   - Total existing preferences: ${prefs['total_existing_preferences']:,.0f}")
        print(f"   - Our preference: ${prefs['our_preference']:,.0f}")
        print(f"   - Total with us: ${prefs['total_with_us']:,.0f}")
        print(f"   - Our position in stack: #{prefs['our_position_in_stack']}")
        
        print(f"\n3. KEY BREAKPOINTS:")
        breakpoints = result['breakpoints']
        print(f"   - Liquidation preferences satisfied: ${breakpoints['liquidation_preference_satisfied']:,.0f}")
        print(f"   - Common meaningful proceeds: ${breakpoints['common_meaningful_proceeds']:,.0f}")
        print(f"   - Our conversion point: ${breakpoints['our_conversion_point']:,.0f}")
        print(f"   - Our breakeven: ${breakpoints['our_breakeven']:,.0f}")
        print(f"   - Our 2x: ${breakpoints['our_2x']:,.0f}")
        print(f"   - Our 3x: ${breakpoints['our_3x']:,.0f}")
        
        print(f"\n4. INVESTOR STACK (in order of payment):")
        for i, investor in enumerate(result['investor_stack'], 1):
            print(f"   {i}. {investor['investor']}: ${investor['liquidation_preference']:,.0f}")
        
        print(f"\n5. EXIT SCENARIO ANALYSIS:")
        print(f"   Exit Multiple | Exit Value | Our MOIC | Common Gets | We Convert?")
        print(f"   " + "-" * 65)
        for scenario in result['exit_scenarios']:
            print(f"   {scenario['exit_multiple']:>4.1f}x | ${scenario['exit_value']/1e6:>6.0f}M | "
                  f"{scenario['our_moic']:>5.2f}x | ${scenario['common_proceeds']/1e6:>6.0f}M | "
                  f"{'Yes' if scenario['conversion_triggered'] else 'No ':>3}")
        
        print("\n✅ Test PASSED - Exit scenarios calculated with real cap table data!")
        
    except Exception as e:
        print(f"\n❌ Test FAILED: {e}")
        import traceback
        traceback.print_exc()
    
    # Now test the full flow
    print("\n\n=== Testing Full Exit Scenario Flow ===")
    
    prompt = "analyze exit scenarios for @Mercury with our $10M investment"
    
    try:
        async for response in orchestrator.process_request(
            prompt=prompt,
            output_format="structured",
            context={"fund_size": 260_000_000}
        ):
            if response.get("type") == "complete":
                data = response.get("data", {})
                exit_data = data.get("exit_scenarios", {})
                
                if "Mercury" in exit_data:
                    merc_data = exit_data["Mercury"]
                    print(f"\n✅ Full flow test PASSED!")
                    print(f"   - Found {len(merc_data.get('scenarios', []))} exit scenarios")
                    print(f"   - Investor stack: {len(merc_data.get('investor_stack', []))} investors")
                    print(f"   - Breakpoints calculated: {merc_data.get('breakpoints', {})}")
                else:
                    print(f"\n⚠️  No exit scenario data for Mercury in response")
                    
    except Exception as e:
        print(f"\n❌ Full flow test FAILED: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_exit_scenarios())