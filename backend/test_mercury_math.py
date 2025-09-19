#!/usr/bin/env python3
"""Test Mercury's investment math to verify calculations are reasonable"""

import asyncio
from app.services.unified_mcp_orchestrator import UnifiedMCPOrchestrator

async def test():
    orchestrator = UnifiedMCPOrchestrator()
    
    # Test with Mercury (known YC company)
    result = await orchestrator.process_request({
        'prompt': '@Mercury',
        'output_format': 'analysis',
        'context': {}
    })
    
    # Extract key numbers
    companies = result.get('results', {}).get('company-data-fetcher', {}).get('companies', [])
    if companies:
        company = companies[0]
        print("="*60)
        print(f"Company: {company.get('company', 'Unknown')}")
        print(f"Stage: {company.get('stage', 'Unknown')}")
        print(f"Business Model: {company.get('business_model', 'Unknown')}")
        print("-"*60)
        print(f"Revenue: ${company.get('revenue', 0):,.0f}")
        print(f"Valuation: ${company.get('valuation', 0):,.0f}")
        print(f"Growth Rate: {company.get('growth_rate', 0):.1f}")
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

if __name__ == "__main__":
    asyncio.run(test())