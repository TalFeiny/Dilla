#!/usr/bin/env python3
"""Test valuation engine with cap tables"""

import requests
import json

def test_valuation():
    url = "http://localhost:8000/api/agent/unified-brain"
    payload = {
        "prompt": "Value @Ramp with full cap table and PWERM scenarios",
        "output_format": "json"
    }
    
    response = requests.post(url, json=payload)
    data = response.json()
    
    # Check if valuation-engine skill was executed
    if "valuation-engine" in data:
        val = data["valuation-engine"]
        print("✅ Valuation Engine Executed")
        print(f"Company: {val.get('company')}")
        
        # Check cap table
        if "cap_table" in val:
            print("✅ Cap Table Present")
            ct = val["cap_table"]
            if "final_cap_table_at_exit" in ct:
                print("  Final cap table stakeholders:", list(ct["final_cap_table_at_exit"].keys())[:3])
            if "total_raised" in ct:
                print(f"  Total raised: ${ct['total_raised']:,.0f}")
        else:
            print("❌ No cap table")
        
        # Check PWERM scenarios
        if "scenarios" in val:
            print("✅ PWERM Scenarios Present")
            for s in val["scenarios"]:
                print(f"  - {s.get('name')}: IRR {s.get('irr', 0):.1%}, Multiple {s.get('multiple', 0):.1f}x")
        else:
            print("❌ No scenarios")
        
        # Check valuation details
        if "valuation" in val:
            print("✅ Valuation Details Present")
            v = val["valuation"]
            print(f"  Method: {v.get('method_used')}")
            print(f"  Fair Value: ${v.get('fair_value', 0):,.0f}")
        else:
            print("❌ No valuation details")
            
        # Check for errors
        if "error" in val:
            print(f"❌ Error in valuation: {val['error']}")
    else:
        print("❌ Valuation Engine NOT executed")
        print("Available skills:", list(data.keys()))
        
        # Check for errors in other skills
        for skill, result in data.items():
            if isinstance(result, dict) and "error" in result:
                print(f"  Error in {skill}: {result['error']}")

if __name__ == "__main__":
    test_valuation()