#!/usr/bin/env python3
"""Test NosoLabs (YC S25) investment math to verify calculations are reasonable"""

import asyncio
from app.services.unified_mcp_orchestrator import UnifiedMCPOrchestrator

async def test():
    orchestrator = UnifiedMCPOrchestrator()
    
    # Test with NosoLabs (YC S25)
    result = await orchestrator.process_request({
        'prompt': '@NosoLabs',
        'output_format': 'analysis',
        'context': {}
    })
    
    # Extract key numbers
    companies = result.get('results', {}).get('company-data-fetcher', {}).get('companies', [])
    if companies:
        company = companies[0]
        print("="*60)
        print(f"Company: {company.get('company', 'Unknown')}")
        print(f"YC Company: {company.get('is_yc', False)}")
        print(f"YC Batch: {company.get('yc_batch', 'N/A')}")
        print(f"Stage: {company.get('stage', 'Unknown')}")
        print(f"Business Model: {company.get('business_model', 'Unknown')}")
        print("-"*60)
        print("FINANCIAL METRICS:")
        print(f"Revenue: ${company.get('revenue', 0):,.0f}")
        print(f"Valuation: ${company.get('valuation', 0):,.0f}")
        print(f"Growth Rate: {company.get('growth_rate', 0):.1f}")
        print(f"SAFE Cap: ${company.get('safe_cap', 0):,.0f}")
        print("-"*60)
        print("CAP TABLE:")
        cap_table = company.get('cap_table', {})
        if cap_table:
            for investor, ownership in cap_table.items():
                print(f"  {investor}: {ownership}%")
        print("-"*60)
        print("INVESTOR ADVICE:")
        advice = company.get('investor_advice', {})
        print(f"Investment Amount: ${advice.get('investment_amount', 0):,.0f}")
        print(f"Entry Ownership: {advice.get('ownership_at_entry', 0):.1f}%")
        print(f"Exit Ownership: {advice.get('ownership_at_exit', 0):.1f}%")
        print(f"Dilution: {advice.get('dilution_expected', 0):.1f}%")
        print("-"*60)
        print("EXIT SCENARIOS:")
        for scenario in advice.get('scenarios', []):
            print(f"\n{scenario['scenario']}:")
            print(f"  Exit Multiple: {scenario.get('exit_multiple', 0)}x revenue")
            print(f"  Exit Valuation: ${scenario.get('exit_valuation', 0):,.0f}")
            print(f"  Proceeds: ${scenario.get('proceeds', 0):,.0f}")
            print(f"  MOIC: {scenario.get('moic', 0):.2f}x")
            print(f"  IRR: {scenario.get('irr', 0)*100:.0f}%")
        
        print("-"*60)
        print(f"Recommendation: {advice.get('recommendation', 'N/A')}")
        print("="*60)
        
        # Sanity checks
        print("\nSANITY CHECKS:")
        base_case = advice.get('scenarios', [{}])[1] if len(advice.get('scenarios', [])) > 1 else advice.get('scenarios', [{}])[0]
        if base_case:
            moic = base_case.get('moic', 0)
            irr = base_case.get('irr', 0) * 100
            exit_val = base_case.get('exit_valuation', 0)
            
            print(f"✓ MOIC reasonable (1-20x)? {1 <= moic <= 20}: MOIC = {moic:.1f}x")
            print(f"✓ IRR reasonable (0-100%)? {0 <= irr <= 100}: IRR = {irr:.0f}%")
            print(f"✓ Exit val reasonable ($10M-$10B)? {10_000_000 <= exit_val <= 10_000_000_000}: ${exit_val:,.0f}")
            
            if moic < 1:
                print("\n❌ ERROR: MOIC is less than 1x - math is broken!")
            if irr < 0:
                print("❌ ERROR: IRR is negative - math is broken!")
            if exit_val < 1_000_000:
                print("❌ ERROR: Exit valuation unreasonably low - math is broken!")

if __name__ == "__main__":
    asyncio.run(test())