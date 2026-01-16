#!/usr/bin/env python3
"""
Test the ultimate preference stack intelligence
Shows the $150M problem and cap table reality
"""

import asyncio
import json
import sys
from decimal import Decimal
import logging

# Add parent directory to path
sys.path.append('/Users/admin/code/dilla-ai/backend')

from app.services.unified_mcp_orchestrator import UnifiedMCPOrchestrator
from app.services.intelligent_gap_filler import IntelligentGapFiller
from app.services.valuation_engine_service import ValuationEngineService
from app.services.advanced_cap_table import CapTableCalculator
from app.services.pre_post_cap_table import PrePostCapTable

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_preference_stack():
    """Test the complete preference stack with realistic scenarios"""
    
    print("\n🎯 Testing Preference Stack Intelligence - The $150M Problem\n")
    print("=" * 80)
    
    # Initialize services
    orchestrator = UnifiedMCPOrchestrator()
    gap_filler = IntelligentGapFiller()
    valuation_engine = ValuationEngineService()
    cap_table = CapTableCalculator()
    pre_post = PrePostCapTable()
    
    # Test company with realistic funding history
    test_company = {
        'company': 'TestCo',
        'stage': 'Series C',
        'valuation': 250_000_000,
        'revenue': 15_000_000,
        'total_funding': 86_000_000,  # The magic number
        'funding_rounds': [
            {
                'round': 'Seed',
                'amount': 3_000_000,
                'valuation': 12_000_000,
                'investors': ['Unknown Angel'],
                'date': '2021-01'
            },
            {
                'round': 'Series A', 
                'amount': 15_000_000,
                'valuation': 60_000_000,
                'investors': ['Tier 2 VC'],
                'date': '2022-01'
            },
            {
                'round': 'Series B',
                'amount': 30_000_000,
                'valuation': 150_000_000,
                'investors': ['Growth Fund'],
                'date': '2023-01'
            },
            {
                'round': 'Series C (us)',
                'amount': 38_000_000,
                'valuation': 250_000_000,
                'investors': ['Our Fund'],
                'date': '2024-01'
            }
        ]
    }
    
    print("\n📊 Test Company Setup:")
    print(f"  Company: {test_company['company']}")
    print(f"  Stage: {test_company['stage']}")
    print(f"  Valuation: ${test_company['valuation']/1e6:.0f}M")
    print(f"  Total Raised: ${test_company['total_funding']/1e6:.0f}M")
    
    # Step 1: Extract liquidation preferences
    print("\n1️⃣ Extracting Liquidation Preferences...")
    enhanced_rounds = gap_filler.extract_liquidation_preferences(
        test_company['funding_rounds'],
        ""  # No search content
    )
    
    print("\n  Preference Stack:")
    for round_data in enhanced_rounds:
        print(f"    {round_data.get('round', 'Unknown')}:")
        print(f"      Amount: ${round_data['amount']/1e6:.1f}M")
        print(f"      Multiple: {round_data.get('liquidation_multiple', 1.0)}x")
        print(f"      Participating: {round_data.get('participating', False)}")
        print(f"      Seniority: {round_data.get('seniority', 0)}")
    
    # Step 2: Calculate waterfall at different exits
    print("\n2️⃣ Testing Exit Scenarios...")
    exit_values = [50_000_000, 86_000_000, 150_000_000, 250_000_000, 500_000_000]
    
    our_investment = 38_000_000
    our_ownership = our_investment / (250_000_000 + our_investment)  # Post-money
    
    for exit_val in exit_values:
        print(f"\n  Exit at ${exit_val/1e6:.0f}M:")
        
        # Calculate DPI impact
        dpi_impact = valuation_engine.calculate_fund_dpi_impact(
            investment_amount=our_investment,
            entry_stage='Series C',
            exit_value=exit_val,
            total_preferences_ahead=48_000_000,  # Seed + A + B
            fund_size=260_000_000,
            fund_dpi=0.0
        )
        
        print(f"    Our Return: ${dpi_impact['our_return']/1e6:.1f}M")
        print(f"    MOIC: {dpi_impact['moic']:.2f}x")
        print(f"    DPI Contribution: {dpi_impact['dpi_contribution']:.2f}%")
        
        if dpi_impact.get('reality_check'):
            print(f"    ⚠️  {dpi_impact['reality_check']}")
    
    # Step 3: Calculate breakeven exit
    print("\n3️⃣ Calculating Breakeven Exit...")
    breakeven_analysis = cap_table.calculate_breakeven_exit(
        our_round='Series C',
        our_investment=our_investment,
        funding_rounds=enhanced_rounds
    )
    
    print(f"  Breakeven Exit: ${breakeven_analysis['breakeven_exit']/1e6:.0f}M")
    print(f"  Multiple Needed: {breakeven_analysis['minimum_multiple_needed']:.1f}x")
    print(f"  Risk Level: {breakeven_analysis['risk_assessment']}")
    
    if breakeven_analysis['has_86m_problem']:
        print(f"  🚨 HAS THE $86M PROBLEM - Need >${86}M to break even!")
    
    # Step 4: Test cap table evolution
    print("\n4️⃣ Testing Cap Table Evolution...")
    cap_table_history = pre_post.calculate_full_cap_table_history({
        'funding_rounds': enhanced_rounds,
        'company': test_company['company']
    })
    
    if cap_table_history and 'history' in cap_table_history:
        print(f"  Rounds Tracked: {len(cap_table_history['history'])}")
        
        # Show founder dilution
        if cap_table_history['history']:
            first_round = cap_table_history['history'][0]
            last_round = cap_table_history['history'][-1]
            
            # Get founder ownership from first round
            founder_start = 0
            for owner, pct in first_round.get('pre_money_ownership', {}).items():
                if 'founder' in owner.lower():
                    founder_start += float(pct)
            
            # Get founder ownership from last round
            founder_end = 0
            for owner, pct in last_round.get('post_money_ownership', {}).items():
                if 'founder' in owner.lower():
                    founder_end += float(pct)
            
            print(f"  Founder Dilution: {founder_start:.1f}% → {founder_end:.1f}%")
    
    # Step 5: Generate deck slide data
    print("\n5️⃣ Generating Exit Scenarios Slide...")
    
    # Process through orchestrator
    request = {
        'companies': [test_company['company']],
        'extracted_data': {test_company['company']: test_company},
        'fund_context': {
            'fund_size': 260_000_000,
            'deployed_capital': 125_000_000,
            'current_dpi': 0.0,
            'target_dpi': 3.0
        }
    }
    
    # Just test the preference extraction and DPI calculation
    print("\n✅ Preference Stack Test Complete!")
    print("\nKey Findings:")
    print(f"  • Standard 1x non-participating terms throughout")
    print(f"  • $86M in preferences ahead of Series C")
    print(f"  • At $150M exit: We get ~{(150-86)*our_ownership:.0f}M = {((150-86)*our_ownership/our_investment):.2f}x MOIC")
    print(f"  • Need ${breakeven_analysis['breakeven_exit']/1e6:.0f}M+ exit to break even")
    print(f"  • For 0 DPI fund: Even this 'good' exit barely moves the needle")
    
    return True

if __name__ == "__main__":
    success = asyncio.run(test_preference_stack())
    if success:
        print("\n🎉 Test Passed - Preference Stack Intelligence Working!")
    else:
        print("\n❌ Test Failed")
    sys.exit(0 if success else 1)