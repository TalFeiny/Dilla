#!/usr/bin/env python3
"""Debug test for valuation calculation"""

import asyncio
import json
from app.services.unified_mcp_orchestrator import UnifiedMCPOrchestrator

async def test_valuation():
    orchestrator = UnifiedMCPOrchestrator()
    
    try:
        # Test with @Extruct and @RelevanceAI
        response = await orchestrator.process_request({
            "prompt": "Create investment deck for @Extruct and @RelevanceAI",
            "output_format": "deck"
        })
        
        # Check if we have companies
        if "companies" in response:
            print(f"✅ Found {len(response['companies'])} companies")
            for company in response['companies']:
                name = company.get('company', 'Unknown')
                val = company.get('valuation', 0)
                inferred_val = company.get('inferred_valuation', 0)
                revenue = company.get('revenue', 0)
                inferred_rev = company.get('inferred_revenue', 0)
                
                print(f"\n{name}:")
                print(f"  Revenue: ${revenue:,.0f} (inferred: ${inferred_rev:,.0f})")
                print(f"  Valuation: ${val:,.0f} (inferred: ${inferred_val:,.0f})")
        
        # Check slides
        if response.get("slides"):
            print(f"\n✅ Generated {len(response['slides'])} slides")
            return True
        else:
            print("\n❌ No slides generated")
            print(f"Response keys: {list(response.keys())}")
            if "error" in response:
                print(f"Error: {response['error']}")
            return False
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        # Clean up the session
        if hasattr(orchestrator, 'session') and orchestrator.session:
            await orchestrator.session.close()

if __name__ == "__main__":
    success = asyncio.run(test_valuation())
    print("\n✅ Valuation fix working!" if success else "\n❌ Still broken")