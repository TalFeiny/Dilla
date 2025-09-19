#!/usr/bin/env python3
"""
Test with @Flai - a different company
"""
import asyncio
import os
from dotenv import load_dotenv
load_dotenv()

import logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

from app.services.unified_mcp_orchestrator import UnifiedMCPOrchestrator

async def test_flai():
    """Test if the system works for Flai"""
    print("\n" + "="*80)
    print("TESTING FLAI - GENERIC SYSTEM TEST")
    print("="*80 + "\n")
    
    orchestrator = UnifiedMCPOrchestrator()
    
    request = {
        "prompt": "Analyze @Flai",
        "output_format": "analysis",
        "context": {}
    }
    
    print("Sending request to unified brain...")
    print(f"Prompt: {request['prompt']}")
    
    try:
        result = await orchestrator.process_request(
            prompt=request['prompt'],
            output_format=request['output_format'],
            context=request['context']
        )
        
        print("\n" + "="*80)
        print("RESULT")
        print("="*80)
        
        if 'analysis' in result and 'companies' in result['analysis']:
            companies = result['analysis']['companies']
            if companies and len(companies) > 0:
                flai = companies[0]
                print(f"\n✅ Successfully analyzed {flai.get('name', 'Unknown')}!")
                print(f"Website URL: {flai.get('website_url', 'Not found')}")
                print(f"Business Model: {flai.get('business_model', 'Unknown')}")
                print(f"Description: {flai.get('description', 'No description')}")
                print(f"Total Raised: ${flai.get('total_raised', 0):,}")
                print(f"Valuation: ${flai.get('valuation', 0):,}")
                print(f"Founders: {flai.get('founders', 'Unknown')}")
                
                if 'funding_rounds' in flai and flai['funding_rounds']:
                    print(f"\nFunding Rounds: {len(flai['funding_rounds'])}")
                    for round_data in flai['funding_rounds'][:3]:
                        print(f"  - {round_data.get('round', 'Unknown')}: ${round_data.get('amount', 0):,}")
            else:
                print("❌ No companies found in result")
        else:
            print("❌ Unexpected result structure")
            
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_flai())