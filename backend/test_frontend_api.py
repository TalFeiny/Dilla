#!/usr/bin/env python3
"""Test the full flow through the frontend API"""

import requests
import json
import time

# Wait for servers to be ready
time.sleep(3)

# Test through the frontend's unified-brain API endpoint
url = "http://localhost:3001/api/agent/unified-brain"

payload = {
    "prompt": "@NosoLabs",
    "output_format": "analysis",
    "context": {}
}

print("="*60)
print("TESTING FULL PIPELINE: @NosoLabs")
print("="*60)
print(f"Request: {url}")
print(f"Payload: {json.dumps(payload, indent=2)}")
print("-"*60)

try:
    response = requests.post(url, json=payload, timeout=30)
    
    if response.status_code == 200:
        data = response.json()
        
        # Extract company data
        companies = data.get('results', {}).get('company-data-fetcher', {}).get('companies', [])
        
        if companies:
            company = companies[0]
            print("✅ COMPANY DATA RETRIEVED:")
            print(f"  Name: {company.get('company')}")
            print(f"  YC: {company.get('is_yc', False)}")
            print(f"  Stage: {company.get('stage')}")
            print(f"  Revenue: ${company.get('revenue', 0):,.0f}")
            print(f"  Valuation: ${company.get('valuation', 0):,.0f}")
            
            # Check investor advice
            advice = company.get('investor_advice', {})
            if advice:
                print("\n✅ INVESTOR ADVICE CALCULATED:")
                print(f"  Investment: ${advice.get('investment_amount', 0):,.0f}")
                print(f"  Ownership: {advice.get('ownership_at_entry', 0):.1f}% → {advice.get('ownership_at_exit', 0):.1f}%")
                
                scenarios = advice.get('scenarios', [])
                if scenarios:
                    print("\n  SCENARIOS:")
                    for s in scenarios:
                        print(f"    {s['scenario']}:")
                        print(f"      Exit: ${s.get('exit_valuation', 0):,.0f}")
                        print(f"      MOIC: {s.get('moic', 0):.2f}x")
                        print(f"      IRR: {s.get('irr', 0)*100:.0f}%")
                        if 'liquidation_preference_impact' in s:
                            print(f"      Liq Pref: {s['liquidation_preference_impact']}")
                    
                    # Check if math is reasonable
                    base = scenarios[2] if len(scenarios) > 2 else scenarios[1] if len(scenarios) > 1 else scenarios[0]
                    moic = base.get('moic', 0)
                    irr = base.get('irr', 0) * 100
                    
                    print("\n  VALIDATION:")
                    if moic > 0 and moic < 100:
                        print(f"    ✅ MOIC looks reasonable: {moic:.2f}x")
                    else:
                        print(f"    ❌ MOIC unrealistic: {moic:.2f}x")
                    
                    if irr > -50 and irr < 200:
                        print(f"    ✅ IRR looks reasonable: {irr:.0f}%")
                    else:
                        print(f"    ❌ IRR unrealistic: {irr:.0f}%")
                else:
                    print("  ❌ No scenarios generated")
            else:
                print("\n❌ No investor advice generated")
                
            # Check cap table
            cap_table = company.get('cap_table', {})
            if cap_table:
                print("\n✅ CAP TABLE GENERATED:")
                for holder, pct in cap_table.items():
                    print(f"    {holder}: {pct}%")
            
            # Check fund fit
            print(f"\n  Fund Fit: {advice.get('fund_fit', 'N/A')}")
            print(f"  Recommendation: {advice.get('recommendation', 'N/A')}")
            
        else:
            print("❌ No company data returned")
            print(f"Full response: {json.dumps(data, indent=2)[:500]}")
    else:
        print(f"❌ API Error: {response.status_code}")
        print(f"Response: {response.text[:500]}")
        
except requests.exceptions.Timeout:
    print("❌ Request timed out (30s) - server may be processing")
except Exception as e:
    print(f"❌ Error: {e}")

print("="*60)