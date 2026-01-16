#!/usr/bin/env python3
"""
REAL test of TAM extraction - no fake data, actual search results
"""

import asyncio
import sys
import os
from pathlib import Path

# Add the backend directory to the Python path
backend_path = Path(__file__).parent / "backend"
sys.path.insert(0, str(backend_path))

from app.services.unified_mcp_orchestrator import UnifiedMCPOrchestrator

async def test_real_tam_extraction():
    """Test TAM extraction with REAL search results"""
    
    print("🧪 Testing REAL TAM Extraction (No Fake Data)")
    print("=" * 50)
    
    try:
        # Initialize the real orchestrator
        print("📋 Initializing UnifiedMCPOrchestrator...")
        orchestrator = UnifiedMCPOrchestrator()
        
        # Test with a real company that should have TAM data
        company_name = "Notion"
        
        print(f"🔍 Running REAL search for {company_name}...")
        
        # This will do actual web searches via Tavily
        result = await orchestrator.execute_company_fetch({
            "company": company_name,
            "include_tam": True
        })
        
        print(f"📊 Result keys: {list(result.keys())}")
        
        # Check if TAM data was extracted
        if 'tam_data' in result and result['tam_data']:
            tam_data = result['tam_data']
            print("✅ TAM data found!")
            print(f"Market Definition: {tam_data.get('tam_market_definition')}")
            print(f"TAM Value: ${tam_data.get('tam_value', 0)/1e9:.1f}B")
            print(f"TAM Formatted: {tam_data.get('tam_formatted')}")
            
            # Show actual sources
            estimates = tam_data.get('tam_estimates', [])
            if estimates:
                print(f"\n📊 Found {len(estimates)} REAL estimates:")
                for i, est in enumerate(estimates, 1):
                    print(f"  {i}. ${est.get('tam_value', 0)/1e9:.1f}B")
                    print(f"     Source: {est.get('source', 'Unknown')}")
                    print(f"     URL: {est.get('url', 'No URL')}")
                    print(f"     Citation: {est.get('citation', 'No citation')[:100]}...")
                    print()
        else:
            print("❌ No TAM data extracted")
            print("This means either:")
            print("  - Search didn't find TAM data")
            print("  - Extraction failed")
            print("  - Our fixes didn't work")
            
        # Show what search content was actually used
        if 'search_content' in result:
            content = result['search_content']
            print(f"\n🔍 Search content length: {len(content)} chars")
            print(f"First 500 chars of REAL search results:")
            print(content[:500])
            print("...")
            
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    print("🚀 Testing REAL TAM Extraction")
    print("=" * 40)
    asyncio.run(test_real_tam_extraction())
