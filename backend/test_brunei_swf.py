#!/usr/bin/env python3
"""
Brunei SWF investment analysis test
"""

import requests
import json
from datetime import datetime

BRUNEI_PROMPT = """
Compare @Saturn and @murphyai for my sovereign wealth fund for brunei, how can i get in or is @N8N a better investment. we have 2.B u management with 805k in real estate, we want to capitalise on AI. but should we invest in this or asset backed finance?
"""

def run_brunei_test():
    url = "http://localhost:8000/api/agent/unified-brain"
    
    payload = {
        "prompt": BRUNEI_PROMPT,
        "output_format": "analysis",
        "context": {
            "fund_aum": "2B",
            "real_estate_allocation": "805k",
            "investor_type": "sovereign_wealth_fund",
            "geography": "Brunei"
        }
    }
    
    print("🏦 Running Brunei SWF analysis...")
    print("-" * 50)
    
    try:
        response = requests.post(url, json=payload, timeout=60)
        data = response.json()
        
        # Save with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"brunei_swf_analysis_{timestamp}.json"
        
        with open(filename, 'w') as f:
            json.dump(data, f, indent=2)
        
        print(f"✅ Saved to: {filename}")
        
        # Quick summary
        if data.get("success") and "companies" in data.get("result", {}):
            companies = data["result"]["companies"]
            print(f"\n📊 Analyzed {len(companies)} companies:")
            
            for c in companies:
                name = c.get("company", "Unknown")
                val = c.get("latest_valuation")
                rev = c.get("inferred_revenue") or c.get("revenue")
                model = c.get("business_model", "Unknown")
                stage = c.get("stage", "Unknown")
                
                print(f"\n🏢 {name}")
                print(f"   Stage: {stage}")
                if val: print(f"   Valuation: ${val:,.0f}")
                if rev: print(f"   Revenue: ${rev:,.0f}")
                print(f"   Model: {model[:80]}..." if len(str(model)) > 80 else f"   Model: {model}")
                
                # Check for inferred values
                if c.get("inferred_revenue"):
                    print(f"   ✅ Inferred revenue: ${c['inferred_revenue']:,.0f}")
                if c.get("inferred_growth_rate"):
                    print(f"   ✅ Growth rate: {c['inferred_growth_rate']:.1%}")
        
        return filename
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return None

if __name__ == "__main__":
    filename = run_brunei_test()
    if filename:
        print(f"\n🎯 Full analysis saved to: {filename}")
        print("💡 Open the JSON to review valuation calculations and recommendations")