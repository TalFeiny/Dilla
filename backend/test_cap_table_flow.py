#!/usr/bin/env python3
"""Test cap table generation through the full pipeline"""

import requests
import json
import time

# Test through the backend API
url = "http://localhost:8000/api/agent/unified-brain"

payload = {
    "prompt": "@NosoLabs",
    "output_format": "analysis",
    "context": {}
}

print("="*60)
print("CAP TABLE GENERATION TEST")
print("="*60)

try:
    response = requests.post(url, json=payload, timeout=30)
    
    if response.status_code == 200:
        data = response.json()
        
        # Extract company data
        companies = data.get('result', {}).get('data', {}).get('company-data-fetcher', {}).get('companies', [])
        
        if companies:
            company = companies[0]
            print(f"Company: {company.get('company')}")
            print(f"YC Batch: {company.get('yc_batch', 'N/A')}")
            print(f"Stage: {company.get('stage', 'Unknown')}")
            print(f"Total Raised: ${company.get('total_raised', 0):,.0f}")
            
            # Check cap table
            cap_table = company.get('cap_table', {})
            if cap_table:
                print("\n✅ CAP TABLE GENERATED:")
                print("-"*40)
                total = 0
                for holder, ownership in cap_table.items():
                    print(f"  {holder:30s}: {ownership:6.2f}%")
                    total += ownership
                print("-"*40)
                print(f"  {'TOTAL':30s}: {total:6.2f}%")
                
                # Validation
                print("\nVALIDATION:")
                if abs(total - 100) < 0.1:
                    print("  ✅ Ownership adds up to 100%")
                else:
                    print(f"  ❌ Ownership doesn't add up: {total:.2f}%")
                
                if 'Founders' in cap_table or 'founders' in str(cap_table).lower():
                    print("  ✅ Founders included")
                else:
                    print("  ❌ No founders in cap table")
                
                if 'Y Combinator' in cap_table or 'YC' in cap_table:
                    print("  ✅ YC ownership tracked")
                    yc_ownership = cap_table.get('Y Combinator', cap_table.get('YC', 0))
                    if 6 <= yc_ownership <= 8:
                        print(f"    ✅ YC ownership correct: {yc_ownership:.1f}%")
                    else:
                        print(f"    ⚠️  YC ownership unusual: {yc_ownership:.1f}% (expected 7%)")
                
                if 'Employees' in cap_table or 'Option Pool' in cap_table:
                    print("  ✅ Employee pool included")
                
                # Check funding rounds in cap table
                print("\nFUNDING ROUNDS IN CAP TABLE:")
                funding_rounds = company.get('funding_rounds', [])
                for round_data in funding_rounds:
                    if isinstance(round_data, dict):
                        round_name = round_data.get('round', 'Unknown')
                        round_amount = round_data.get('amount', 0)
                        print(f"  {round_name}: ${round_amount:,.0f}")
                        
                        # Check if round is in cap table
                        round_in_cap = any(round_name.lower() in holder.lower() for holder in cap_table.keys())
                        if round_in_cap:
                            print(f"    ✅ {round_name} investors in cap table")
                        else:
                            print(f"    ⚠️  {round_name} investors not explicitly in cap table")
            else:
                print("\n❌ NO CAP TABLE GENERATED")
            
            # Check pre/post money valuations
            print("\nVALUATION EVOLUTION:")
            pre_post = company.get('pre_post_valuations', {})
            if pre_post:
                for round_name, vals in pre_post.items():
                    if isinstance(vals, dict):
                        pre = vals.get('pre_money', 0)
                        post = vals.get('post_money', 0)
                        dilution = vals.get('dilution', 0)
                        print(f"  {round_name}:")
                        print(f"    Pre:  ${pre:,.0f}")
                        print(f"    Post: ${post:,.0f}")
                        print(f"    Dilution: {dilution:.1f}%")
            
            # Check liquidation waterfall
            waterfall = company.get('liquidation_waterfall', {})
            if waterfall:
                print("\n✅ LIQUIDATION WATERFALL CALCULATED")
                scenarios = waterfall.get('scenarios', [])
                for scenario in scenarios[:3]:  # First 3 scenarios
                    exit_val = scenario.get('exit_value', 0)
                    distributions = scenario.get('distributions', {})
                    print(f"  At ${exit_val/1e6:.0f}M exit:")
                    for holder, amount in distributions.items():
                        if amount > 0:
                            print(f"    {holder}: ${amount/1e6:.1f}M")
            
        else:
            print("❌ No company data returned")
    else:
        print(f"❌ API Error: {response.status_code}")
        
except Exception as e:
    print(f"❌ Error: {e}")

print("="*60)