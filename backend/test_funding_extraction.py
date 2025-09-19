#!/usr/bin/env python3
"""
Test funding extraction with citations for @Dwelly
"""
import asyncio
import json
from app.services.unified_mcp_orchestrator import UnifiedMCPOrchestrator

async def test_dwelly_extraction():
    """Test extraction for @Dwelly with improved citation tracking"""
    orchestrator = UnifiedMCPOrchestrator()
    
    # Test with @Dwelly
    result = await orchestrator.process_request(
        prompt="Get funding data for @Dwelly",
        output_format="json",
        context={}
    )
    
    # Print results with citations
    if result.get('success'):
        data = result.get('data', {})
        if 'companies' in data:
            for company in data['companies']:
                print(f"\n=== {company.get('company', 'Unknown')} ===")
                print(f"Total Raised: ${company.get('total_raised', 0):,.0f}")
                
                if 'funding_rounds' in company:
                    print("\nFunding Rounds:")
                    for round_data in company['funding_rounds']:
                        print(f"\n  {round_data.get('round', 'Unknown')}:")
                        print(f"    Amount: ${round_data.get('amount', 0):,.0f}")
                        print(f"    Date: {round_data.get('date', 'Unknown')}")
                        
                        if 'citation' in round_data:
                            citation = round_data['citation']
                            print(f"    Citation:")
                            print(f"      Text: {citation.get('text', 'No text')[:100]}...")
                            print(f"      URL: {citation.get('url', 'No URL')}")
                            print(f"      Confidence: {citation.get('confidence', 'Unknown')}")
                        else:
                            print(f"    Citation: MISSING!")
    
    return result

if __name__ == "__main__":
    result = asyncio.run(test_dwelly_extraction())
    
    # Save full result for analysis
    with open('dwelly_funding_test.json', 'w') as f:
        json.dump(result, f, indent=2, default=str)
    
    print("\n\nFull results saved to dwelly_funding_test.json")