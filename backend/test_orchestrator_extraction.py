#!/usr/bin/env python3
"""Debug what the orchestrator's extraction method returns"""

import asyncio
import json
from app.services.unified_mcp_orchestrator import UnifiedMCPOrchestrator

async def test_orchestrator_extraction():
    orch = UnifiedMCPOrchestrator()
    
    print("=" * 80)
    print("TESTING ORCHESTRATOR EXTRACTION")
    print("=" * 80)
    
    company = "RelevanceAI"
    
    # Get search results first
    print("\n1️⃣ Getting search results...")
    search_queries = [
        f"{company} startup funding valuation revenue Series B",
        f"{company} company business model team founders",
        f"{company} seed pre-seed Series A B C funding round investors $24 million",
        f"{company} technology product customers market"
    ]
    
    all_search_results = []
    for query in search_queries:
        result = await orch._tavily_search(query)
        if result:
            all_search_results.append(result)
    
    print(f"Got {len(all_search_results)} search result sets")
    
    # Now extract using the orchestrator's method
    print("\n2️⃣ Extracting with orchestrator's _extract_comprehensive_profile...")
    extracted = await orch._extract_comprehensive_profile(
        company_name=company,
        search_results=all_search_results
    )
    
    print("\n3️⃣ ORCHESTRATOR EXTRACTION RESULT:")
    print("-" * 40)
    
    # Show key fields
    print(f"Stage: {extracted.get('stage', 'MISSING')}")
    print(f"Total Raised: ${extracted.get('total_raised', 0):,.0f}")
    print(f"Total Funding: ${extracted.get('total_funding', 0):,.0f}")
    print(f"Valuation: ${extracted.get('valuation', 0):,.0f}")
    
    # Show funding rounds
    funding_rounds = extracted.get('funding_rounds', [])
    print(f"\nFunding Rounds: {len(funding_rounds)}")
    for r in funding_rounds:
        print(f"  - {r.get('round', 'Unknown')}: ${r.get('amount', 0):,.0f}")
    
    # Show full data
    print("\n4️⃣ FULL EXTRACTED DATA:")
    print("-" * 40)
    print(json.dumps(extracted, indent=2, default=str)[:1500])
    
    print("\n" + "=" * 80)

if __name__ == "__main__":
    asyncio.run(test_orchestrator_extraction())