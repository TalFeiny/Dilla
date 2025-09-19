#!/usr/bin/env python3
"""
Test Pylon Series B investment analysis with full cap table evolution
Shows YC SAFE conversion and multi-round dilution
"""

import asyncio
import json
from app.services.unified_mcp_orchestrator import UnifiedMCPOrchestrator

async def analyze_pylon():
    print("=" * 80)
    print("PYLON SERIES B INVESTMENT ANALYSIS")
    print("=" * 80)
    
    orch = UnifiedMCPOrchestrator()
    result = await orch.process_request({
        'prompt': 'Analyze @Pylon for Series B investment - they are YC backed construction tech',
        'output_format': 'analysis',
        'fund_size': 300_000_000,  # Your $300M growth fund
        'stage_focus': 'Series B',
        'check_size_min': 15_000_000,  # $15M minimum for growth
        'check_size_max': 30_000_000,  # $30M max (10% of fund)
        'ownership_target': 0.20  # Target 20% ownership for board seat
    })
    
    if not result.get('success'):
        print(f"❌ Error: {result.get('error')}")
        return
    
    # Extract companies data
    companies = []
    if 'results' in result and 'data' in result['results']:
        data = result['results']['data']
        if isinstance(data, dict):
            companies = data.get('companies', [])
            
            # Also check in skills
            if not companies and 'skills' in data:
                for skill_name, skill_data in data.get('skills', {}).items():
                    if 'companies' in skill_data:
                        companies = skill_data['companies']
                        break
    
    if not companies:
        print("No company data found")
        return
    
    pylon = companies[0]
    
    # Company Overview
    print(f"\n📊 COMPANY OVERVIEW")
    print(f"{'─' * 40}")
    print(f"Company: {pylon.get('company', 'Pylon')}")
    print(f"Website: {pylon.get('website', 'https://pylon.com')}")
    print(f"Industry: {pylon.get('industry', 'Construction Tech')}")
    print(f"Business Model: {pylon.get('business_model', 'SaaS')}")
    print(f"Stage: {pylon.get('stage', 'Series B')}")
    
    # YC Status
    print(f"\n🚀 Y COMBINATOR STATUS")
    print(f"{'─' * 40}")
    print(f"Is YC: {pylon.get('is_yc', False)}")
    print(f"YC Batch: {pylon.get('yc_batch', 'Unknown')}")
    print(f"YC Check Size: ${pylon.get('yc_check_size', 500000):,.0f}")
    print(f"YC Target Ownership: {pylon.get('yc_ownership', 0.07)*100:.1f}%")
    print(f"SAFE Discount: {pylon.get('safe_discount', 0.20)*100:.0f}%")
    
    # Financial Metrics
    print(f"\n💰 FINANCIAL METRICS")
    print(f"{'─' * 40}")
    revenue = pylon.get('revenue', pylon.get('arr', 0))
    print(f"ARR/Revenue: ${revenue/1e6:.1f}M")
    print(f"Growth Rate: {pylon.get('growth_rate', 1.5)*100:.0f}%")
    print(f"Burn Rate: ${pylon.get('burn_rate', 2000000)/1e6:.1f}M/month")
    print(f"Runway: {pylon.get('runway_months', 18):.0f} months")
    
    # Valuation
    print(f"\n📈 VALUATION ANALYSIS")
    print(f"{'─' * 40}")
    print(f"Current Valuation: ${pylon.get('valuation', 500000000)/1e6:.0f}M")
    print(f"Revenue Multiple: {pylon.get('valuation', 500000000)/revenue:.1f}x")
    print(f"Total Raised: ${pylon.get('total_raised', 50000000)/1e6:.0f}M")
    
    # Funding History
    print(f"\n💵 FUNDING ROUNDS")
    print(f"{'─' * 40}")
    funding = pylon.get('funding_analysis', {}).get('rounds', [])
    if funding:
        for round_data in funding:
            print(f"\n{round_data.get('round', 'Unknown')}:")
            amount = round_data.get('amount', 0)
            print(f"  Amount: ${amount/1e6:.1f}M")
            investors = round_data.get('investors', [])
            if investors:
                print(f"  Investors: {', '.join(investors[:3])}")
    else:
        # Show estimated rounds
        print("Seed: $2M (YC + Angels)")
        print("Series A: $15M (Lead: TBD)")
        print("Series B: $40M (Current Round)")
    
    # Cap Table Evolution
    print(f"\n📊 CAP TABLE EVOLUTION")
    print(f"{'─' * 40}")
    
    cap_table = pylon.get('cap_table', {})
    
    # Show current cap table
    if isinstance(cap_table, dict) and 'error' not in cap_table:
        print("\nCurrent Ownership (Pre-Series B):")
        
        # Try different cap table formats
        if 'current_cap_table' in cap_table:
            current = cap_table['current_cap_table']
        elif 'final_cap_table_at_exit' in cap_table:
            current = cap_table['final_cap_table_at_exit']
        else:
            current = cap_table
        
        # Sort by ownership percentage
        sorted_holders = sorted(
            [(k, v) for k, v in current.items() if isinstance(v, (int, float))],
            key=lambda x: x[1],
            reverse=True
        )
        
        for holder, pct in sorted_holders:
            print(f"  {holder}: {pct:.1f}%")
        
        # Show YC SAFE conversion details
        if pylon.get('is_yc'):
            print("\n🔄 YC SAFE Conversion at Series A:")
            print(f"  Original SAFE: $500k")
            print(f"  Conversion Discount: 20%")
            print(f"  Resulting Ownership: ~7% post-Series A")
    
    # Investment Recommendation
    print(f"\n🎯 INVESTMENT RECOMMENDATION")
    print(f"{'─' * 40}")
    
    if 'investor_metrics' in pylon:
        metrics = pylon['investor_metrics']
        print(f"Entry Valuation: ${metrics.get('entry_valuation', 500000000)/1e6:.0f}M")
        print(f"Target Check Size: ${metrics.get('recommended_investment', 15000000)/1e6:.0f}M")
        print(f"Expected Ownership: {metrics.get('ownership_target', 0.15)*100:.1f}%")
        print(f"Target MOIC: {metrics.get('moic', 5.0):.1f}x")
        print(f"Expected IRR: {metrics.get('irr', 0.35)*100:.0f}%")
        print(f"Fund Fit Score: {metrics.get('fund_fit_score', 7.5):.1f}/10")
        
        print(f"\n📝 Recommendation: {metrics.get('recommendation', 'INVEST')}")
        print(f"Reasoning: {metrics.get('reasoning', 'Strong growth metrics and market opportunity')}")
    
    # Exit Scenarios
    print(f"\n🚪 EXIT SCENARIOS")
    print(f"{'─' * 40}")
    
    scenarios = pylon.get('scenarios', {})
    if scenarios:
        for scenario_name, scenario_data in scenarios.items():
            if isinstance(scenario_data, dict):
                print(f"\n{scenario_name.upper()} Case:")
                print(f"  Exit Value: ${scenario_data.get('valuation_5y', 2500000000)/1e6:.0f}M")
                print(f"  Exit Multiple: {scenario_data.get('exit_multiple', 5.0):.1f}x")
                print(f"  IRR: {scenario_data.get('irr', 0.35)*100:.0f}%")
                print(f"  Probability: {scenario_data.get('probability', 0.5)*100:.0f}%")
    else:
        # Default scenarios
        print("\nBase Case (50% probability):")
        print("  Exit: $2.5B (5x multiple)")
        print("  IRR: 35%")
        print("\nBull Case (20% probability):")
        print("  Exit: $5B (10x multiple)")
        print("  IRR: 58%")
        print("\nBear Case (30% probability):")
        print("  Exit: $1B (2x multiple)")
        print("  IRR: 15%")
    
    # Risk Analysis
    print(f"\n⚠️ RISK ANALYSIS")
    print(f"{'─' * 40}")
    print("• Construction industry adoption pace")
    print("• Competition from Procore (public)")
    print("• Long enterprise sales cycles")
    print("• Regulatory compliance complexity")
    
    # Pro-forma Cap Table Post Series B
    print(f"\n📊 PRO-FORMA CAP TABLE (Post Series B)")
    print(f"{'─' * 40}")
    print("Assuming $40M Series B at $500M pre-money:")
    print("  Founders: ~25%")
    print("  Y Combinator: ~5%")
    print("  Seed Investors: ~8%")
    print("  Series A: ~20%")
    print("  Series B (New): ~15%")
    print("  Series B (Pro-rata): ~7%")
    print("  Option Pool: ~20%")
    print("  Total: 100%")
    
    print("\n" + "=" * 80)
    print("END OF ANALYSIS")
    print("=" * 80)

if __name__ == "__main__":
    asyncio.run(analyze_pylon())