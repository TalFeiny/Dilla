#!/usr/bin/env python3
"""Test the full _execute_company_fetch to see where data is lost"""

import asyncio
import json
from app.services.unified_mcp_orchestrator import UnifiedMCPOrchestrator

async def test_full_company_fetch():
    orch = UnifiedMCPOrchestrator()
    
    print("=" * 80)
    print("TESTING FULL COMPANY FETCH")
    print("=" * 80)
    
    # Test the FULL company fetch method
    result = await orch._execute_company_fetch({"company": "RelevanceAI"})
    
    if result and "companies" in result:
        company = result["companies"][0]
        
        print("\n✅ FINAL OUTPUT FROM _execute_company_fetch:")
        print("-" * 40)
        
        # Show key fields
        print(f"Stage: {company.get('stage', 'MISSING')}")
        print(f"Total Raised: ${company.get('total_raised', 0):,.0f}")
        print(f"Total Funding: ${company.get('total_funding', 0):,.0f}")
        print(f"Valuation: ${company.get('valuation', 0):,.0f}")
        
        # Show funding rounds
        funding_rounds = company.get('funding_rounds', [])
        print(f"\nFunding Rounds: {len(funding_rounds)}")
        for r in funding_rounds:
            print(f"  - {r.get('round', 'Unknown')}: ${r.get('amount', 0):,.0f}")
        
        # Show what was inferred vs extracted
        print("\n📊 EXTRACTED vs INFERRED:")
        print("-" * 40)
        for field in ["revenue", "valuation", "total_funding", "growth_rate"]:
            actual = company.get(field)
            inferred = company.get(f"inferred_{field}")
            print(f"{field:15} actual: {actual:15} inferred: {inferred}")
        
        # Check for issues
        print("\n🔍 ANALYSIS:")
        print("-" * 40)
        if "series b" in str(company.get('stage', '')).lower():
            print("✓ Stage is correct (Series B)")
        else:
            print(f"❌ Stage is wrong: {company.get('stage')}")
        
        total = company.get('total_funding', 0) or company.get('total_raised', 0)
        if total > 30_000_000:
            print(f"✓ Total funding is correct: ${total:,.0f}")
        else:
            print(f"❌ Total funding is wrong: ${total:,.0f}")
        
        if len(funding_rounds) >= 3:
            print(f"✓ Has {len(funding_rounds)} funding rounds")
        else:
            print(f"❌ Only has {len(funding_rounds)} funding rounds")
    else:
        print("❌ No company data returned")

if __name__ == "__main__":
    asyncio.run(test_full_company_fetch())