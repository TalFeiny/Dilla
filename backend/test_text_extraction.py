#!/usr/bin/env python3
"""
Test script to verify text extraction works correctly after removing HTML parsing
"""

import asyncio
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.services.unified_mcp_orchestrator import UnifiedMCPOrchestrator

async def test_text_extraction():
    """Test that company data extraction works with text content instead of HTML"""
    
    print("Initializing UnifiedMCPOrchestrator...")
    orchestrator = UnifiedMCPOrchestrator()
    
    # Test with a simple company
    test_prompt = "Compare @Cursor and @Perplexity"
    
    print(f"\nTesting with prompt: {test_prompt}")
    print("-" * 50)
    
    try:
        result = await orchestrator.process_request(
            prompt=test_prompt,
            output_format="analysis",
            context={}
        )
        
        # Check if we got a result
        if result and result.get('success'):
            print("✅ SUCCESS: Text extraction is working!")
            print(f"\nResult type: {result.get('result_type')}")
            
            # Check if companies were extracted
            if 'companies' in result.get('data', {}):
                companies = result['data']['companies']
                print(f"\nExtracted {len(companies)} companies:")
                for company in companies:
                    print(f"  - {company.get('company_name', 'Unknown')}")
                    print(f"    Website: {company.get('website_url', 'Not found')}")
                    print(f"    Funding: ${company.get('total_raised', 0)/1000000:.1f}M")
                    print(f"    Stage: {company.get('stage', 'Unknown')}")
            
            # Check if analysis was generated
            if 'analysis' in result.get('data', {}):
                analysis = result['data']['analysis']
                print(f"\nAnalysis generated: {len(analysis)} characters")
                print(f"First 200 chars: {analysis[:200]}...")
        else:
            print("❌ FAILED: No successful result returned")
            print(f"Error: {result.get('error', 'Unknown error')}")
            
    except Exception as e:
        print(f"❌ ERROR during test: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    print("Starting text extraction test...")
    print("=" * 50)
    asyncio.run(test_text_extraction())
    print("\n" + "=" * 50)
    print("Test complete!")