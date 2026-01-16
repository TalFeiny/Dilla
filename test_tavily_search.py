#!/usr/bin/env python3
"""Quick test to see if Tavily can find Fyxer and Gradient Labs"""
import os
import asyncio
import aiohttp
import json

TAVILY_API_KEY = "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"

async def test_search(company_name):
    """Test Tavily search for a company"""
    print(f"\n{'='*60}")
    print(f"Searching for: {company_name}")
    print(f"{'='*60}")
    
    async with aiohttp.ClientSession() as session:
        url = "https://api.tavily.com/search"
        payload = {
            "api_key": TAVILY_API_KEY,
            "query": f"{company_name} startup funding Series A B",
            "search_depth": "advanced",
            "max_results": 5
        }
        
        async with session.post(url, json=payload) as response:
            if response.status == 200:
                result = await response.json()
                print(f"\n✓ Found {len(result.get('results', []))} results\n")
                
                for idx, r in enumerate(result.get('results', []), 1):
                    print(f"Result #{idx}:")
                    print(f"  Title: {r.get('title', 'N/A')}")
                    print(f"  URL: {r.get('url', 'N/A')}")
                    content_preview = r.get('content', '')[:200].replace('\n', ' ')
                    print(f"  Preview: {content_preview}...")
                    print()
                    
                # Check if any mention funding
                has_funding = any('funding' in r.get('content', '').lower() or 
                                'series' in r.get('content', '').lower() or
                                'raised' in r.get('content', '').lower()
                                for r in result.get('results', []))
                
                print(f"Has funding mentions: {has_funding}")
                
            else:
                error = await response.text()
                print(f"✗ API Error: {response.status}")
                print(f"Error: {error}")

async def main():
    await test_search("Fyxer")
    await test_search("Gradient Labs")
    await test_search("GradientLabs")

if __name__ == "__main__":
    asyncio.run(main())



