#!/usr/bin/env python3
"""Test script to verify what Tavily returns in response"""

import asyncio
import json
import os
from typing import Dict
from tavily import TavilyClient

async def test_tavily_response():
    """Test what Tavily actually returns"""
    
    # Get API key
    api_key = os.getenv("TAVILY_API_KEY")
    if not api_key:
        print("❌ No TAVILY_API_KEY found in environment")
        return
    
    print("✅ Found Tavily API key")
    
    # Initialize client
    client = TavilyClient(api_key=api_key)
    
    # Test query - same as what the system uses
    query = '"Ramp" startup company -obituary -death -memorial -"real estate"'
    
    print(f"\n📍 Testing query: {query}")
    print("-" * 80)
    
    try:
        # Call WITHOUT include_raw_content (matching current implementation)
        response = client.search(
            query=query,
            search_depth="advanced",
            max_results=3  # Just get a few results for testing
        )
        
        print("\n📊 Response structure:")
        print(f"  - Type: {type(response)}")
        print(f"  - Keys: {list(response.keys()) if isinstance(response, dict) else 'Not a dict'}")
        
        if 'results' in response and response['results']:
            print(f"\n📄 First result structure:")
            first_result = response['results'][0]
            print(f"  - Keys: {list(first_result.keys())}")
            
            # Check each field
            for key, value in first_result.items():
                if key == 'content':
                    print(f"  - {key}: {type(value).__name__} (length: {len(value) if value else 0})")
                    if value:
                        print(f"    Preview: {value[:100]}...")
                elif key == 'raw_content':
                    print(f"  - {key}: {type(value).__name__ if value is not None else 'None'}")
                    if value:
                        print(f"    Length: {len(value)}")
                        print(f"    Preview: {value[:100]}...")
                else:
                    print(f"  - {key}: {type(value).__name__}")
            
            print("\n🔍 Checking raw_content field:")
            if 'raw_content' in first_result:
                raw = first_result['raw_content']
                if raw is None:
                    print("  ✅ raw_content is None (not requested)")
                elif raw == "":
                    print("  ✅ raw_content is empty string (not requested)")
                else:
                    print(f"  ⚠️ raw_content has data: {len(raw)} chars")
            else:
                print("  ✅ raw_content field not present")
                
        # Now test WITH include_raw_content to compare
        print("\n" + "=" * 80)
        print("🔄 Testing WITH include_raw_content=True for comparison:")
        print("-" * 80)
        
        response_with_raw = client.search(
            query=query,
            search_depth="advanced",
            max_results=1,
            include_raw_content=True  # Explicitly request it
        )
        
        if 'results' in response_with_raw and response_with_raw['results']:
            first_result_raw = response_with_raw['results'][0]
            print("\n📄 Result with raw_content requested:")
            
            for key in ['content', 'raw_content']:
                if key in first_result_raw:
                    value = first_result_raw[key]
                    if value:
                        print(f"  - {key}: {type(value).__name__} (length: {len(value)})")
                    else:
                        print(f"  - {key}: {type(value).__name__ if value is not None else 'None'}")
        
        # Save full response for inspection
        with open('/Users/admin/code/dilla-ai/backend/tavily_response_test.json', 'w') as f:
            json.dump({
                'without_raw': response,
                'with_raw': response_with_raw
            }, f, indent=2, default=str)
        
        print("\n✅ Full response saved to tavily_response_test.json")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_tavily_response())