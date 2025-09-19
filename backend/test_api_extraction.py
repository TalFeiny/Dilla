#!/usr/bin/env python3
"""
Test the API directly to verify text extraction works
"""

import requests
import json

def test_api():
    """Test the unified-brain API with text extraction"""
    
    url = "http://localhost:8000/api/agent/unified-brain"
    
    payload = {
        "prompt": "Get basic data about @Cursor",
        "output_format": "analysis",
        "context": {}
    }
    
    print(f"Testing API: {url}")
    print(f"Prompt: {payload['prompt']}")
    print("-" * 50)
    
    try:
        response = requests.post(url, json=payload, timeout=30)
        
        if response.status_code == 200:
            result = response.json()
            print("✅ API call successful!")
            
            # Pretty print the result
            print("\nResponse:")
            print(json.dumps(result, indent=2)[:1000])
            
            if result.get('success'):
                print("\n✅ Text extraction is working!")
            else:
                print(f"\n⚠️ API returned but not successful: {result.get('error')}")
        else:
            print(f"❌ API call failed with status {response.status_code}")
            print(f"Response: {response.text[:500]}")
            
    except requests.exceptions.Timeout:
        print("❌ Request timed out after 30 seconds")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    test_api()