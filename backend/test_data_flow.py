#!/usr/bin/env python3
"""Test data flow through the system"""

import requests
import json

def test_data_flow():
    url = "http://localhost:8000/api/agent/unified-brain"
    
    # First test: just fetch company data
    print("=" * 50)
    print("TEST 1: Fetch Company Data")
    print("=" * 50)
    
    payload = {
        "prompt": "Analyze @Ramp",
        "output_format": "json"
    }
    
    response = requests.post(url, json=payload)
    data = response.json()
    
    if "company-data-fetcher" in data:
        companies = data["company-data-fetcher"].get("companies", [])
        if companies:
            company = companies[0]
            print(f"✅ Company: {company.get('company')}")
            print(f"  Revenue: ${company.get('revenue', 0):,.0f}")
            print(f"  Burn Rate: ${company.get('burn_rate', 0):,.0f}")
            print(f"  Runway Months: {company.get('runway_months', 'N/A')}")
            print(f"  Valuation: ${company.get('valuation', 0):,.0f}")
            
            funding = company.get('funding_analysis', {})
            print(f"  Total Raised: ${funding.get('total_raised', 0):,.0f}")
            print(f"  Current Stage: {funding.get('current_stage', 'N/A')}")
            
            rounds = funding.get('rounds', [])
            print(f"  Funding Rounds: {len(rounds)}")
            for r in rounds[:3]:
                print(f"    - {r.get('round', 'N/A')}: ${r.get('amount', 0):,.0f}")
    
    print("\n" + "=" * 50)
    print("TEST 2: Valuation with Same Company")
    print("=" * 50)
    
    payload = {
        "prompt": "Value @Ramp with cap table",
        "output_format": "json"
    }
    
    response = requests.post(url, json=payload)
    data = response.json()
    
    # Check if company data was properly passed to valuation
    if "valuation-engine" in data:
        val = data["valuation-engine"]
        if "error" in val:
            print(f"❌ Valuation error: {val['error']}")
        else:
            print("✅ Valuation executed")
            
            # Check if cap table has actual data
            ct = val.get("cap_table", {})
            print(f"  Cap table total raised: ${ct.get('total_raised', 0):,.0f}")
            
            # Check if company data made it through
            if "scoring" in val:
                scoring = val["scoring"]
                print(f"  Scoring valuation: ${scoring.get('valuation', 0):,.0f}")

if __name__ == "__main__":
    test_data_flow()