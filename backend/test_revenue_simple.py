#!/usr/bin/env python3
"""Simple test to verify revenue inference works"""

import asyncio
import aiohttp
import json
from datetime import datetime

async def test_deal_valuation():
    """Test Deel valuation through the API"""
    
    print("\n" + "="*80)
    print("TESTING DEEL VALUATION - REVENUE INFERENCE")
    print("="*80)
    
    url = "http://localhost:8000/api/agent/unified-brain"
    
    payload = {
        "prompt": "Value @Deel using PWERM and comparables. Show me the revenue used.",
        "output_format": "default"
    }
    
    headers = {
        "Content-Type": "application/json"
    }
    
    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(url, json=payload, headers=headers) as response:
                if response.status == 200:
                    result = await response.json()
                    
                    print("\n✓ API call successful")
                    
                    # Parse the result to check revenue
                    if 'result' in result:
                        result_text = str(result['result'])
                        
                        # Check for revenue mentions
                        if 'revenue' in result_text.lower():
                            # Try to extract revenue value
                            import re
                            revenue_pattern = r'revenue[:\s]+\$?([\d,]+(?:\.\d+)?)\s*(?:million|M|billion|B)?'
                            matches = re.findall(revenue_pattern, result_text, re.IGNORECASE)
                            
                            if matches:
                                print(f"\n✅ SUCCESS: Revenue found in response: {matches[0]}")
                            else:
                                print("\n⚠️  Revenue mentioned but value not extracted")
                        
                        # Check for valuation values
                        if 'valuation' in result_text.lower() or 'fair value' in result_text.lower():
                            print("✓ Valuation calculations present in response")
                        
                        # Save full response
                        filename = f'test_revenue_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
                        with open(filename, 'w') as f:
                            json.dump(result, f, indent=2)
                        print(f"\n✓ Full response saved to {filename}")
                        
                        # Print a snippet of the response
                        print("\n" + "-"*40)
                        print("Response snippet (first 500 chars):")
                        print(result_text[:500] + "...")
                        
                    else:
                        print("\n❌ No result in response")
                        print(json.dumps(result, indent=2))
                    
                else:
                    error_text = await response.text()
                    print(f"\n❌ API error: {response.status}")
                    print(error_text[:500])
                    
        except Exception as e:
            print(f"\n❌ Connection error: {e}")
            print("Make sure the backend server is running on port 8000")
    
    print("\n" + "="*80)
    print("TEST COMPLETE")
    print("="*80)

if __name__ == "__main__":
    asyncio.run(test_deal_valuation())