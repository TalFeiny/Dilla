#!/usr/bin/env python3
"""
Find valuation data in companies table and calculate revenue multiples
"""

import os
import json
from supabase import create_client, Client

def get_supabase_client() -> Client:
    url = os.getenv('NEXT_PUBLIC_SUPABASE_URL')
    key = os.getenv('SUPABASE_SERVICE_ROLE_KEY')
    return create_client(url, key)

def main():
    supabase = get_supabase_client()
    
    print("Finding valuation data and calculating revenue multiples...")
    
    try:
        # Get companies with ARR data and check for valuation in data field
        companies_result = supabase.table('companies').select('name, current_arr_usd, revenue_growth_annual_pct, data, metrics').gt('current_arr_usd', 1000000).execute()
        
        if companies_result.data:
            print(f"Found {len(companies_result.data)} companies with ARR > $1M")
            
            companies_with_multiples = []
            
            for company in companies_result.data:
                name = company.get('name', 'Unknown')
                arr = company.get('current_arr_usd', 0) or 0
                growth_rate = company.get('revenue_growth_annual_pct', 0) or 0
                
                # Check data field for valuation
                data_field = company.get('data')
                valuation = None
                
                if data_field and isinstance(data_field, dict):
                    # Look for valuation in various possible keys
                    for key, value in data_field.items():
                        if isinstance(value, (int, float)) and value > 0:
                            if any(term in key.lower() for term in ['valuation', 'value', 'market_cap', 'enterprise_value']):
                                valuation = value
                                break
                
                # If no valuation found, skip
                if not valuation or valuation <= 0:
                    continue
                
                # Calculate revenue multiple
                revenue_multiple = valuation / arr
                
                # Calculate growth-adjusted multiple if we have growth data
                growth_adjusted_multiple = None
                if growth_rate > 0:
                    growth_adjusted_multiple = revenue_multiple / (growth_rate / 100)
                
                companies_with_multiples.append({
                    'name': name,
                    'arr': arr,
                    'valuation': valuation,
                    'growth_rate': growth_rate,
                    'revenue_multiple': revenue_multiple,
                    'growth_adjusted_multiple': growth_adjusted_multiple
                })
            
            print(f"\nFound {len(companies_with_multiples)} companies with valuation data")
            
            if companies_with_multiples:
                # Sort by revenue multiple
                companies_with_multiples.sort(key=lambda x: x['revenue_multiple'], reverse=True)
                
                print("\nTop companies by Revenue Multiple:")
                print("-" * 80)
                
                for i, company in enumerate(companies_with_multiples[:15], 1):
                    print(f"{i:2d}. {company['name']}")
                    print(f"    ARR: ${company['arr']:,.0f}")
                    print(f"    Valuation: ${company['valuation']:,.0f}")
                    print(f"    Growth Rate: {company['growth_rate']:.1f}%")
                    print(f"    Revenue Multiple: {company['revenue_multiple']:.2f}x")
                    if company['growth_adjusted_multiple']:
                        print(f"    Growth-Adjusted Multiple: {company['growth_adjusted_multiple']:.2f}x")
                    print()
                
                # Calculate statistics
                multiples = [c['revenue_multiple'] for c in companies_with_multiples]
                growth_adjusted_multiples = [c['growth_adjusted_multiple'] for c in companies_with_multiples if c['growth_adjusted_multiple']]
                growth_rates = [c['growth_rate'] for c in companies_with_multiples if c['growth_rate'] > 0]
                
                print("Summary Statistics:")
                print(f"Average Revenue Multiple: {sum(multiples)/len(multiples):.2f}x")
                print(f"Median Revenue Multiple: {sorted(multiples)[len(multiples)//2]:.2f}x")
                
                if growth_adjusted_multiples:
                    print(f"Average Growth-Adjusted Multiple: {sum(growth_adjusted_multiples)/len(growth_adjusted_multiples):.2f}x")
                    print(f"Median Growth-Adjusted Multiple: {sorted(growth_adjusted_multiples)[len(growth_adjusted_multiples)//2]:.2f}x")
                
                if growth_rates:
                    print(f"Average Growth Rate: {sum(growth_rates)/len(growth_rates):.1f}%")
                
                # Size analysis
                small_companies = [c for c in companies_with_multiples if c['arr'] < 25_000_000]
                medium_companies = [c for c in companies_with_multiples if 25_000_000 <= c['arr'] < 100_000_000]
                large_companies = [c for c in companies_with_multiples if c['arr'] >= 100_000_000]
                
                print(f"\nSize Analysis:")
                if small_companies:
                    avg_multiple = sum([c['revenue_multiple'] for c in small_companies])/len(small_companies)
                    print(f"Small companies (<$25M ARR): {len(small_companies)} companies, avg multiple: {avg_multiple:.2f}x")
                
                if medium_companies:
                    avg_multiple = sum([c['revenue_multiple'] for c in medium_companies])/len(medium_companies)
                    print(f"Medium companies ($25-100M ARR): {len(medium_companies)} companies, avg multiple: {avg_multiple:.2f}x")
                
                if large_companies:
                    avg_multiple = sum([c['revenue_multiple'] for c in large_companies])/len(large_companies)
                    print(f"Large companies (>$100M ARR): {len(large_companies)} companies, avg multiple: {avg_multiple:.2f}x")
                
            else:
                print("No companies found with valuation data in the data field")
                
                # Let's check what's actually in the data field
                print("\nChecking what's in the data field for companies with high ARR...")
                for company in companies_result.data[:5]:
                    print(f"\n{company['name']} (ARR: ${company['current_arr_usd']:,.0f}):")
                    data_field = company.get('data')
                    if data_field and isinstance(data_field, dict):
                        for key, value in data_field.items():
                            print(f"  {key}: {value}")
                    else:
                        print(f"  Data field: {data_field}")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
