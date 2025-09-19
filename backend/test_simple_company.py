#!/usr/bin/env python3
"""
Test with a simpler prompt to see extraction
"""

import requests
import json

def test_simple():
    """Test with simple company request"""
    
    url = "http://localhost:8000/api/agent/unified-brain"
    
    # Use a simpler prompt
    payload = {
        "prompt": "Analyze @Deel",
        "output_format": "analysis", 
        "context": {}
    }
    
    print(f"Testing with: {payload['prompt']}")
    print("=" * 80)
    
    try:
        response = requests.post(url, json=payload, timeout=45)
        
        if response.status_code == 200:
            result = response.json()
            
            # Save for inspection
            with open('deel_result.json', 'w') as f:
                json.dump(result, f, indent=2)
            
            if result.get('success'):
                # Pretty print key parts
                print(json.dumps(result, indent=2)[:3000])
                print("\n✅ Full result saved to deel_result.json")
            else:
                print(f"❌ Failed: {result}")
        else:
            print(f"❌ HTTP {response.status_code}")
            
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    test_simple()