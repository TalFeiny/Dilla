#!/usr/bin/env python3
"""
Check the actual data structure in the companies table
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
    
    print("Checking actual data structure in companies table...")
    
    try:
        # Get a few companies to see the actual data structure
        companies_result = supabase.table('companies').select('*').limit(5).execute()
        
        if companies_result.data:
            for i, company in enumerate(companies_result.data):
                print(f"\nCompany {i+1}: {company.get('name', 'Unknown')}")
                print("=" * 50)
                
                # Check key fields
                print(f"current_arr_usd: {company.get('current_arr_usd')}")
                print(f"valuation: {company.get('valuation')}")
                print(f"latest_valuation_usd: {company.get('latest_valuation_usd')}")
                print(f"revenue_growth_annual_pct: {company.get('revenue_growth_annual_pct')}")
                print(f"revenue_growth_monthly_pct: {company.get('revenue_growth_monthly_pct')}")
                print(f"arr: {company.get('arr')}")
                print(f"growth_rate: {company.get('growth_rate')}")
                print(f"revenue: {company.get('revenue')}")
                
                # Check if data field has useful info
                data_field = company.get('data')
                if data_field:
                    print(f"\nData field contents:")
                    if isinstance(data_field, dict):
                        for key, value in data_field.items():
                            if 'revenue' in key.lower() or 'arr' in key.lower() or 'growth' in key.lower() or 'valuation' in key.lower():
                                print(f"  {key}: {value}")
                    else:
                        print(f"  Data type: {type(data_field)}")
                        print(f"  Data: {str(data_field)[:200]}...")
                
                # Check metrics field
                metrics_field = company.get('metrics')
                if metrics_field:
                    print(f"\nMetrics field contents:")
                    if isinstance(metrics_field, dict):
                        for key, value in metrics_field.items():
                            print(f"  {key}: {value}")
                    else:
                        print(f"  Metrics type: {type(metrics_field)}")
                        print(f"  Metrics: {str(metrics_field)[:200]}...")
                
                print("\n" + "-" * 80)
        
        # Now let's try to find companies with meaningful data
        print("\nLooking for companies with meaningful revenue/valuation data...")
        
        # Try different approaches to find companies with data
        all_companies = supabase.table('companies').select('name, current_arr_usd, valuation, latest_valuation_usd, revenue, arr, data, metrics').execute()
        
        if all_companies.data:
            meaningful_companies = []
            
            for company in all_companies.data:
                name = company.get('name', 'Unknown')
                
                # Check multiple sources for revenue
                arr_sources = [
                    company.get('current_arr_usd', 0) or 0,
                    company.get('arr', 0) or 0,
                    company.get('revenue', 0) or 0
                ]
                
                # Check multiple sources for valuation
                valuation_sources = [
                    company.get('valuation', 0) or 0,
                    company.get('latest_valuation_usd', 0) or 0
                ]
                
                # Check data field for additional info
                data_field = company.get('data')
                if data_field and isinstance(data_field, dict):
                    # Look for revenue/valuation in data field
                    for key, value in data_field.items():
                        if isinstance(value, (int, float)) and value > 0:
                            if 'revenue' in key.lower() or 'arr' in key.lower():
                                arr_sources.append(value)
                            elif 'valuation' in key.lower():
                                valuation_sources.append(value)
                
                max_arr = max(arr_sources) if arr_sources else 0
                max_valuation = max(valuation_sources) if valuation_sources else 0
                
                if max_arr > 1000 or max_valuation > 1000:  # More reasonable thresholds
                    meaningful_companies.append({
                        'name': name,
                        'arr': max_arr,
                        'valuation': max_valuation,
                        'raw_data': company
                    })
            
            print(f"\nFound {len(meaningful_companies)} companies with meaningful data:")
            
            for company in meaningful_companies[:10]:
                print(f"  {company['name']}: ARR=${company['arr']:,.0f}, Valuation=${company['valuation']:,.0f}")
            
            if meaningful_companies:
                print(f"\nTop companies by ARR:")
                sorted_by_arr = sorted(meaningful_companies, key=lambda x: x['arr'], reverse=True)
                for company in sorted_by_arr[:5]:
                    print(f"  {company['name']}: ${company['arr']:,.0f} ARR")
                
                print(f"\nTop companies by Valuation:")
                sorted_by_valuation = sorted(meaningful_companies, key=lambda x: x['valuation'], reverse=True)
                for company in sorted_by_valuation[:5]:
                    print(f"  {company['name']}: ${company['valuation']:,.0f} valuation")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
