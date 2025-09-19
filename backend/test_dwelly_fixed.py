#!/usr/bin/env python3
"""
Test the fixed Dwelly extraction with new two-step approach
"""
import asyncio
import os
from dotenv import load_dotenv
load_dotenv()

# Set up logging
import logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

from app.services.unified_mcp_orchestrator import UnifiedMCPOrchestrator

async def test_dwelly():
    """Test if we can now correctly identify Dwelly"""
    print("\n" + "="*80)
    print("TESTING DWELLY WITH TWO-STEP APPROACH")
    print("="*80 + "\n")
    
    orchestrator = UnifiedMCPOrchestrator()
    
    # Test the unified brain endpoint
    request = {
        "prompt": "Analyze @Dwelly",
        "output_format": "analysis",
        "context": {}
    }
    
    print("Sending request to unified brain...")
    print(f"Prompt: {request['prompt']}")
    print(f"Format: {request['output_format']}")
    
    try:
        result = await orchestrator.process_request(
            prompt=request['prompt'],
            output_format=request['output_format'],
            context=request['context']
        )
        
        print("\n" + "="*80)
        print("RESULT")
        print("="*80)
        
        # Check if we got company data
        if 'analysis' in result and 'companies' in result['analysis']:
            companies = result['analysis']['companies']
            if companies and len(companies) > 0:
                dwelly = companies[0]
                print(f"\n✅ Successfully analyzed Dwelly!")
                print(f"Company Name: {dwelly.get('name', 'Unknown')}")
                print(f"Website URL: {dwelly.get('website_url', 'Not found')}")
                print(f"Business Model: {dwelly.get('business_model', 'Unknown')}")
                print(f"Description: {dwelly.get('description', 'No description')}")
                print(f"Total Raised: ${dwelly.get('total_raised', 0):,}")
                print(f"Valuation: ${dwelly.get('valuation', 0):,}")
                
                # Check if we got the RIGHT Dwelly
                website = dwelly.get('website_url', '').lower()
                if 'dwelly.group' in website:
                    print("\n🎉 SUCCESS! Found the correct UK PropTech Dwelly!")
                elif 'dwelly.io' in website:
                    print("\n❌ WRONG! Found the crypto Dwelly instead of UK PropTech")
                elif website:
                    print(f"\n❓ Found website {website} - need to verify if correct")
                else:
                    print("\n❌ No website found")
                    
                # Show funding rounds if available
                if 'funding_rounds' in dwelly and dwelly['funding_rounds']:
                    print(f"\nFunding Rounds: {len(dwelly['funding_rounds'])}")
                    for round_data in dwelly['funding_rounds'][:3]:
                        print(f"  - {round_data.get('round', 'Unknown')}: ${round_data.get('amount', 0):,}")
            else:
                print("❌ No companies found in result")
        else:
            print("❌ Unexpected result structure")
            print(f"Keys in result: {list(result.keys())}")
            
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_dwelly())