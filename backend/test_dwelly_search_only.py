#!/usr/bin/env python3
"""
Test just the search part to see what URLs are coming back
"""
import asyncio
import os
from dotenv import load_dotenv
load_dotenv()

from app.services.mcp_orchestrator import MCPOrchestrator

async def test_searches():
    """Run searches for Dwelly and see what comes back"""
    print("\n" + "="*80)
    print("TESTING DWELLY SEARCHES")
    print("="*80 + "\n")
    
    orch = MCPOrchestrator()
    
    # Test different search queries
    queries = [
        '"Dwelly" UK PropTech lettings roll-up',
        '"Dwelly" dwelly.group UK startup',
        'site:dwelly.group',
        '"Dwelly" "ex-Uber" lettings UK startup',
        'Dwelly UK property management AI roll-up website'
    ]
    
    for query in queries:
        print(f"\n--- SEARCH: {query} ---")
        try:
            result = await orch.tools['tavily_search'].execute(
                query=query,
                search_type='general',
                max_results=5
            )
            
            if result.get('success') and result.get('data'):
                for i, item in enumerate(result['data']['results'][:3], 1):
                    print(f"\n{i}. {item.get('title', 'No title')}")
                    print(f"   URL: {item.get('url', 'No URL')}")
                    content = item.get('content', '')[:200]
                    print(f"   Content: {content}")
                    
                    # Look for website mentions in content
                    import re
                    websites = re.findall(r'dwelly\.[a-z]+', content.lower())
                    if websites:
                        print(f"   FOUND WEBSITES IN CONTENT: {websites}")
            else:
                print("   No results")
        except Exception as e:
            print(f"   Error: {e}")
    
    print("\n" + "="*80)
    print("SEARCH COMPLETE")
    print("="*80)

if __name__ == "__main__":
    asyncio.run(test_searches())