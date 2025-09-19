#!/usr/bin/env python3
"""Debug search queries"""

import asyncio
from app.services.unified_mcp_orchestrator import UnifiedMCPOrchestrator

async def test_searches():
    orchestrator = UnifiedMCPOrchestrator()
    
    # Test 1: Website search
    print("="*80)
    print("WEBSITE SEARCH TEST")
    print("="*80)
    website_result = await orchestrator.executor.execute_tavily({
        "query": '"Dwelly" official website -site:tracxn.com -site:crunchbase.com -site:pitchbook.com',
        "search_depth": "advanced",
        "max_results": 5
    })
    
    if website_result.get('success'):
        for r in website_result['data']['results'][:3]:
            print(f"URL: {r['url']}")
            print(f"Title: {r['title']}")
            print(f"Content: {r['content'][:200]}...\n")
    
    # Test 2: Funding search
    print("="*80)
    print("FUNDING SEARCH TEST")
    print("="*80)
    funding_result = await orchestrator.executor.execute_tavily({
        "query": '"Dwelly" raised funding "series A" OR "seed" -site:tracxn.com -site:crunchbase.com site:techcrunch.com OR site:forbes.com OR site:businessinsider.com',
        "search_depth": "advanced", 
        "max_results": 5
    })
    
    if funding_result.get('success'):
        for r in funding_result['data']['results'][:3]:
            print(f"URL: {r['url']}")
            print(f"Title: {r['title']}")
            print(f"Content: {r['content'][:200]}...\n")

if __name__ == "__main__":
    asyncio.run(test_searches())