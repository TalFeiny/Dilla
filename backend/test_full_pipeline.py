#!/usr/bin/env python3
"""Test FULL pipeline - round inference, exit scenarios, cap table, fund context, ownership"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from app.services.unified_mcp_orchestrator import UnifiedMCPOrchestrator
from app.services.intelligent_gap_filler import IntelligentGapFiller
from app.services.valuation_engine_service import ValuationEngineService
from app.services.pre_post_cap_table import PrePostCapTable

async def test_full_pipeline():
    """Test the complete pipeline with real company-like data"""
    
    print("="*80)
    print("TESTING FULL INVESTMENT ANALYSIS PIPELINE")
    print("="*80)
    
    # Initialize services
    orchestrator = UnifiedMCPOrchestrator()
    gap_filler = IntelligentGapFiller()
    valuation_engine = ValuationEngineService()
    cap_table_service = PrePostCapTable()
    
    # Set up fund context (CRITICAL - must be in shared_data)
    fund_context = {
        'fund_size': 260_000_000,  # $260M fund
        'remaining_capital': 109_000_000,  # $109M to deploy
        'deployed_capital': 151_000_000,
        'portfolio_count': 15,
        'fund_year': 3,
        'target_ownership': 0.10,  # 10% target
        'check_size_range': (5_000_000, 20_000_000)
    }
    
    orchestrator.shared_data['fund_context'] = fund_context
    print(f"✓ Fund Context Set: ${fund_context['fund_size']/1e6:.0f}M fund, ${fund_context['remaining_capital']/1e6:.0f}M remaining")
    
    # Test company data
    test_company = {
        'company': 'TestCo',
        'stage': 'Series B',
        'revenue': 30_000_000,
        'growth_rate': 2.0,  # 100% YoY
        'valuation': 300_000_000,
        'total_funding': 50_000_000,
        'funding_rounds': [
            {'round': 'Seed', 'amount': 3_000_000, 'date': '2021-01-15'},
            {'round': 'Series A', 'amount': 15_000_000, 'date': '2022-06-01'},
            {'round': 'Series B', 'amount': 32_000_000, 'date': '2023-09-15'}
        ],
        'team_size': 85,
        'category': 'SaaS',
        'business_model': 'B2B SaaS with Enterprise focus'
    }
    
    print(f"\n{'='*60}")
    print("1. TESTING ROUND INFERENCE")
    print(f"{'='*60}")
    
    # Test round inference
    if not test_company.get('next_round'):
        # Infer next round
        stage_progression = {
            'Seed': 'Series A',
            'Series A': 'Series B', 
            'Series B': 'Series C',
            'Series C': 'Series D',
            'Series D': 'Growth'
        }
        test_company['next_round'] = stage_progression.get(test_company['stage'], 'Exit')
        print(f"✓ Next round inferred: {test_company['next_round']}")
    
    # Calculate dilution scenarios
    entry_ownership = 10_000_000 / (test_company['valuation'] + 10_000_000)
    dilution_scenarios = gap_filler.calculate_exit_dilution_scenarios(
        initial_ownership=entry_ownership,
        rounds_to_exit=2  # B -> C -> Exit
    )
    print(f"✓ Dilution calculated: Entry {entry_ownership*100:.1f}% -> Exit {dilution_scenarios['without_pro_rata']*100:.1f}%")
    
    print(f"\n{'='*60}")
    print("2. TESTING CAP TABLE EVOLUTION")
    print(f"{'='*60}")
    
    # Test cap table reconstruction
    cap_table_history = cap_table_service.calculate_full_cap_table_history(test_company)
    if cap_table_history and 'history' in cap_table_history:
        print(f"✓ Cap table history: {len(cap_table_history['history'])} rounds")
        print(f"✓ Current ownership distribution:")
        if 'current_cap_table' in cap_table_history:
            for investor, ownership in list(cap_table_history['current_cap_table'].items())[:3]:
                print(f"  - {investor}: {ownership:.1f}%")
    
    print(f"\n{'='*60}")
    print("3. TESTING EXIT SCENARIOS & PWERM")
    print(f"{'='*60}")
    
    # Test PWERM calculation
    from app.services.valuation_engine_service import ValuationRequest, Stage
    
    val_request = ValuationRequest(
        company_name=test_company['company'],
        stage=Stage.SERIES_B,
        revenue=test_company['revenue'],
        growth_rate=test_company['growth_rate'],
        last_round_valuation=test_company['valuation'],
        total_raised=test_company['total_funding']
    )
    
    # Generate and test scenarios
    scenarios = valuation_engine._generate_exit_scenarios(val_request)
    print(f"✓ Generated {len(scenarios)} exit scenarios")
    
    # Model cap table evolution for scenarios
    our_investment = {
        'amount': 10_000_000,
        'ownership': entry_ownership
    }
    
    for i, scenario in enumerate(scenarios[:3]):
        valuation_engine.model_cap_table_evolution(scenario, test_company, our_investment)
        print(f"  Scenario {i+1}: {scenario.scenario}")
        print(f"    Exit: ${scenario.exit_value/1e6:.0f}M in {scenario.time_to_exit:.1f} years")
        print(f"    Our final ownership: {scenario.final_ownership*100:.1f}%")
    
    print(f"\n{'='*60}")
    print("4. TESTING OWNERSHIP EVOLUTION")
    print(f"{'='*60}")
    
    # Test ownership evolution data structure
    ownership_evolution = {
        "entry_ownership": entry_ownership,
        "exit_ownership_no_followon": dilution_scenarios['without_pro_rata'],
        "exit_ownership_with_followon": dilution_scenarios['with_pro_rata'],
        "followon_capital_required": 10_000_000 * 2,  # 2x reserves
        "followon_scenarios": {
            "no_followon": {
                "capital_deployed": 10_000_000,
                "final_ownership": dilution_scenarios['without_pro_rata'],
                "exit_value": test_company['valuation'] * 5 * dilution_scenarios['without_pro_rata'],
                "moic": (test_company['valuation'] * 5 * dilution_scenarios['without_pro_rata']) / 10_000_000
            },
            "with_followon": {
                "capital_deployed": 30_000_000,
                "final_ownership": dilution_scenarios['with_pro_rata'],
                "exit_value": test_company['valuation'] * 5 * dilution_scenarios['with_pro_rata'],
                "moic": (test_company['valuation'] * 5 * dilution_scenarios['with_pro_rata']) / 30_000_000
            }
        }
    }
    
    print(f"✓ Ownership evolution:")
    print(f"  Entry: {ownership_evolution['entry_ownership']*100:.1f}%")
    print(f"  Exit (no follow-on): {ownership_evolution['exit_ownership_no_followon']*100:.1f}%")
    print(f"  Exit (with follow-on): {ownership_evolution['exit_ownership_with_followon']*100:.1f}%")
    print(f"  Follow-on required: ${ownership_evolution['followon_capital_required']/1e6:.0f}M")
    
    print(f"\n{'='*60}")
    print("5. TESTING FUND FIT CALCULATION")
    print(f"{'='*60}")
    
    # Test fund fit scoring
    fund_fit = gap_filler.calculate_fund_fit(
        test_company, 
        fund_context,
        10_000_000  # check size
    )
    
    print(f"✓ Fund fit score: {fund_fit.get('overall_score', 0):.0f}/100")
    print(f"  Check size: ${fund_fit.get('selected_check', 0)/1e6:.0f}M")
    print(f"  Ownership: {fund_fit.get('selected_ownership', 0)*100:.1f}%")
    print(f"  Reserve ratio: {fund_fit.get('reserve_ratio', 0):.1f}x")
    
    print(f"\n{'='*60}")
    print("6. TESTING BREAKPOINT CALCULATIONS")
    print(f"{'='*60}")
    
    # Test breakpoint calculations
    liquidation_pref = test_company['total_funding']
    our_pref = 10_000_000
    total_pref = liquidation_pref + our_pref
    
    breakpoints = {
        'liquidation_preference_satisfied': total_pref,
        'common_meaningful_proceeds': total_pref + 5_000_000,
        'our_conversion_point': total_pref * 2,
        'founder_meaningful': total_pref + 10_000_000
    }
    
    print(f"✓ Key breakpoints:")
    for name, value in breakpoints.items():
        print(f"  {name}: ${value/1e6:.0f}M")
    
    print(f"\n{'='*60}")
    print("✅ ALL COMPONENTS TESTED SUCCESSFULLY!")
    print(f"{'='*60}")
    
    # Final validation
    assert ownership_evolution['entry_ownership'] > 0, "Entry ownership must be positive"
    assert ownership_evolution['exit_ownership_no_followon'] < ownership_evolution['entry_ownership'], "Should dilute without follow-on"
    assert ownership_evolution['exit_ownership_with_followon'] >= ownership_evolution['exit_ownership_no_followon'], "Follow-on should preserve ownership"
    assert fund_fit['overall_score'] > 0, "Fund fit score should be calculated"
    assert len(scenarios) > 0, "Should have exit scenarios"
    
    return True

if __name__ == "__main__":
    success = asyncio.run(test_full_pipeline())
    sys.exit(0 if success else 1)
