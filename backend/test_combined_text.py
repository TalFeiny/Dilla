#!/usr/bin/env python3
"""See what text is actually being sent to Claude"""

import asyncio
from app.services.unified_mcp_orchestrator import UnifiedMCPOrchestrator

async def test():
    orch = UnifiedMCPOrchestrator()
    
    # Get search results
    search_results = []
    queries = [
        "RelevanceAI startup funding valuation revenue",
        "RelevanceAI company business model team founders",
        "RelevanceAI seed pre-seed Series A B C funding round investors",
    ]
    
    for query in queries:
        result = await orch._tavily_search(query)
        search_results.append(result)
    
    # Build combined text like the orchestrator does
    combined_text = "\n\n---\n\n".join([
        f"Source {idx+1}:\n{result.get('content', '')[:3000]}"
        for idx, search_result in enumerate(search_results)
        if search_result and "results" in search_result
        for result in search_result.get("results", [])
        if result.get("content")
    ])
    
    print("COMBINED TEXT SENT TO CLAUDE:")
    print("=" * 80)
    print(combined_text[:5000])  # First 5000 chars
    print("\n...")
    print(f"\nTotal length: {len(combined_text)} characters")
    
    # Count funding mentions
    import re
    funding_mentions = re.findall(r'\$\d+[MmBb]|\d+\s*million|\d+\s*billion', combined_text, re.IGNORECASE)
    print(f"\nFunding mentions found: {len(funding_mentions)}")
    for mention in funding_mentions[:10]:
        print(f"  - {mention}")

asyncio.run(test())