#!/usr/bin/env python3
"""Test script to verify the data flow from company-data-fetcher to valuation-engine"""

import asyncio
import json
from app.services.unified_mcp_orchestrator import UnifiedMCPOrchestrator

async def test_valuation_flow():
    """Test the flow with proper skill ordering"""
    orchestrator = UnifiedMCPOrchestrator()
    
    # Test 1: Correct flow - fetch data first, then valuation
    print("=" * 50)
    print("TEST 1: Correct Flow (fetch -> valuation)")
    print("=" * 50)
    
    prompt1 = "Analyze @Cursor and provide valuation"
    result1 = await orchestrator.process_request(
        prompt=prompt1,
        output_format="analysis",
        context={}
    )
    
    print(f"Success: {result1.get('success', False)}")
    if 'skill_chain' in result1:
        print(f"Skills executed: {[s['skill'] for s in result1['skill_chain']]}")
    if 'results' in result1:
        companies = result1['results'].get('companies', [])
        if companies:
            company = companies[0]
            print(f"Company: {company.get('company', 'N/A')}")
            print(f"Has valuation data: {'valuation' in company}")
            print(f"Has error: {'error' in company}")
    
    print("\n" + "=" * 50)
    print("TEST 2: Incorrect Flow (valuation only)")
    print("=" * 50)
    
    # Test 2: Incorrect flow - try valuation without fetching data
    context2 = {
        "skill_chain": [{"skill": "valuation-engine", "parameters": {"companies": ["@Cursor"]}}],
        "results": {}
    }
    
    # Directly call valuation without data
    valuation_result = await orchestrator.execute_skill(
        "valuation-engine",
        {"companies": ["@Cursor"]},
        context2
    )
    
    if 'error' in valuation_result:
        print(f"✅ Correctly caught error: {valuation_result['error']}")
    else:
        print("❌ Should have caught missing data error")
    
    print("\n" + "=" * 50)
    print("TEST 3: Check error messages")
    print("=" * 50)
    
    # Check that proper error messages are returned
    if isinstance(valuation_result, dict) and 'valuations' in valuation_result:
        for val in valuation_result['valuations']:
            if 'error' in val:
                print(f"Company: {val.get('company')}")
                print(f"Error: {val.get('error')}")
                print(f"Suggestion: {val.get('suggestion', 'None')}")

if __name__ == "__main__":
    asyncio.run(test_valuation_flow())