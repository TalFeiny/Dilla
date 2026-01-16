#!/usr/bin/env python3
"""Debug test to see response structure"""

import asyncio
import json
from app.services.unified_mcp_orchestrator import UnifiedMCPOrchestrator

async def test_response():
    orchestrator = UnifiedMCPOrchestrator()
    
    try:
        response = await orchestrator.process_request({
            "prompt": "Create investment deck for @Extruct",
            "output_format": "deck"
        })
        
        print(f"Response keys: {list(response.keys())}")
        
        # Check if we have results
        if "results" in response:
            results = response["results"]
            print(f"Results keys: {list(results.keys()) if isinstance(results, dict) else 'Not a dict'}")
            
            # Check for company-fetch
            if "company-fetch" in results:
                fetch_data = results["company-fetch"]
                print(f"company-fetch keys: {list(fetch_data.keys()) if isinstance(fetch_data, dict) else 'Not a dict'}")
                
                if "companies" in fetch_data:
                    companies = fetch_data["companies"]
                    print(f"Found {len(companies)} companies")
                    for company in companies:
                        name = company.get('company', 'Unknown')
                        val = company.get('valuation', 0)
                        inferred_val = company.get('inferred_valuation', 0)
                        revenue = company.get('revenue', 0)
                        inferred_rev = company.get('inferred_revenue', 0)
                        
                        print(f"\n{name}:")
                        print(f"  Revenue: ${revenue:,.0f} (inferred: ${inferred_rev:,.0f})")
                        print(f"  Valuation: ${val:,.0f} (inferred: ${inferred_val:,.0f})")
                        
            # Check for deck generation
            if "deck-generation" in results:
                deck_data = results["deck-generation"]
                print(f"\ndeck-generation keys: {list(deck_data.keys()) if isinstance(deck_data, dict) else 'Not a dict'}")
                if isinstance(deck_data, dict) and "slides" in deck_data:
                    print(f"Found {len(deck_data['slides'])} slides")
                    
        # Check shared_data
        if hasattr(orchestrator, 'shared_data'):
            print(f"\nshared_data keys: {list(orchestrator.shared_data.keys())}")
            if "companies" in orchestrator.shared_data:
                print(f"Companies in shared_data: {len(orchestrator.shared_data['companies'])}")
                
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if hasattr(orchestrator, 'session') and orchestrator.session:
            await orchestrator.session.close()

if __name__ == "__main__":
    asyncio.run(test_response())