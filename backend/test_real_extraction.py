#!/usr/bin/env python3
"""Test actual extraction to see what's happening"""

import asyncio
import json
from app.services.unified_mcp_orchestrator import UnifiedMCPOrchestrator

async def test_extraction():
    orch = UnifiedMCPOrchestrator()
    
    # Test the actual company fetch
    print("=" * 80)
    print("Testing extraction for RelevanceAI...")
    print("=" * 80)
    
    result = await orch._execute_company_fetch({"company": "RelevanceAI"})
    
    if result and "companies" in result:
        company = result["companies"][0]
        print("\nExtracted data:")
        print(f"  Company: {company.get('company')}")
        print(f"  Stage: {company.get('stage')}")
        print(f"  Revenue: {company.get('revenue')}")
        print(f"  Valuation: {company.get('valuation')}")
        print(f"  Total Funding: {company.get('total_funding')}")
        print(f"  Founded: {company.get('founded_year')}")
        print(f"  Team Size: {company.get('team_size')}")
        print(f"  Business Model: {company.get('business_model')}")
        print(f"  Sector: {company.get('sector')}")
        
        # Check what funding rounds were found
        funding_rounds = company.get('funding_rounds', [])
        print(f"\n  Funding Rounds Found: {len(funding_rounds)}")
        for round in funding_rounds:
            print(f"    - {round}")
            
    # Now test Tavily search directly
    print("\n" + "=" * 80)
    print("Testing Tavily search directly...")
    print("=" * 80)
    
    search_result = await orch._tavily_search("RelevanceAI startup funding Series A B valuation")
    if search_result and "results" in search_result:
        print(f"\nTavily found {len(search_result['results'])} results")
        for i, result in enumerate(search_result['results'][:3]):
            print(f"\n  Result {i+1}:")
            print(f"    URL: {result.get('url')}")
            print(f"    Title: {result.get('title')}")
            content = result.get('content', '')[:200]
            print(f"    Content: {content}...")
            
            # Check if it mentions funding
            if any(word in content.lower() for word in ['series', 'funding', 'million', 'raised']):
                print(f"    >>> CONTAINS FUNDING INFO!")

if __name__ == "__main__":
    asyncio.run(test_extraction())