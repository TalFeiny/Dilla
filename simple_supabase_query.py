#!/usr/bin/env python3
"""
Simple query to check what's in the companies table and calculate growth-adjusted multiples
"""

import os
from supabase import create_client, Client

def get_supabase_client() -> Client:
    url = os.getenv('NEXT_PUBLIC_SUPABASE_URL')
    key = os.getenv('SUPABASE_SERVICE_ROLE_KEY')
    return create_client(url, key)

def main():
    supabase = get_supabase_client()
    
    print("Querying companies table for growth-adjusted revenue multiples...")
    
    try:
        # First, let's see what columns we have
        result = supabase.table('companies').select('*').limit(5).execute()
        
        if result.data:
            print("Sample company data:")
            for company in result.data:
                print(f"Company: {company.get('name', 'N/A')}")
                print(f"Keys: {list(company.keys())}")
                print("-" * 40)
                break
        
        # Now query with the actual columns we know exist
        companies_result = supabase.table('companies').select(
            'name, sector, current_arr_usd, revenue_growth_annual_pct, revenue_growth_monthly_pct, valuation, latest_valuation_usd, total_invested_usd, data, metrics'
        ).gt('current_arr_usd', 0).execute()
        
        if companies_result.data:
            print(f"\nFound {len(companies_result.data)} companies with ARR > 0")
            
            valid_companies = []
            
            for company in companies_result.data:
                name = company.get('name', 'Unknown')
                arr = company.get('current_arr_usd', 0) or 0
                valuation = company.get('valuation', 0) or company.get('latest_valuation_usd', 0) or 0
                annual_growth = company.get('revenue_growth_annual_pct', 0) or 0
                monthly_growth = company.get('revenue_growth_monthly_pct', 0) or 0
                
                # Calculate growth rate
                growth_rate = annual_growth or (monthly_growth * 12 if monthly_growth else 0)
                
                if arr > 0 and valuation > 0 and growth_rate > 0:
                    revenue_multiple = valuation / arr
                    growth_adjusted_multiple = revenue_multiple / (growth_rate / 100)
                    
                    valid_companies.append({
                        'name': name,
                        'arr': arr,
                        'valuation': valuation,
                        'growth_rate': growth_rate,
                        'revenue_multiple': revenue_multiple,
                        'growth_adjusted_multiple': growth_adjusted_multiple
                    })
            
            print(f"\nCompanies with complete data for multiple analysis: {len(valid_companies)}")
            
            if valid_companies:
                # Sort by growth-adjusted multiple
                valid_companies.sort(key=lambda x: x['growth_adjusted_multiple'], reverse=True)
                
                print("\nTop 10 companies by growth-adjusted revenue multiple:")
                print("-" * 80)
                
                for i, company in enumerate(valid_companies[:10], 1):
                    print(f"{i:2d}. {company['name']}")
                    print(f"    ARR: ${company['arr']:,.0f}")
                    print(f"    Valuation: ${company['valuation']:,.0f}")
                    print(f"    Growth Rate: {company['growth_rate']:.1f}%")
                    print(f"    Revenue Multiple: {company['revenue_multiple']:.2f}x")
                    print(f"    Growth-Adjusted Multiple: {company['growth_adjusted_multiple']:.2f}x")
                    print()
                
                # Calculate statistics
                multiples = [c['revenue_multiple'] for c in valid_companies]
                growth_adjusted_multiples = [c['growth_adjusted_multiple'] for c in valid_companies]
                growth_rates = [c['growth_rate'] for c in valid_companies]
                
                print("Summary Statistics:")
                print(f"Average Revenue Multiple: {sum(multiples)/len(multiples):.2f}x")
                print(f"Average Growth-Adjusted Multiple: {sum(growth_adjusted_multiples)/len(growth_adjusted_multiples):.2f}x")
                print(f"Average Growth Rate: {sum(growth_rates)/len(growth_rates):.1f}%")
                print(f"Median Growth-Adjusted Multiple: {sorted(growth_adjusted_multiples)[len(growth_adjusted_multiples)//2]:.2f}x")
                
                # Size analysis
                small_companies = [c for c in valid_companies if c['arr'] < 5_000_000]
                medium_companies = [c for c in valid_companies if 5_000_000 <= c['arr'] < 25_000_000]
                large_companies = [c for c in valid_companies if c['arr'] >= 25_000_000]
                
                print(f"\nSize Analysis:")
                print(f"Small companies (<$5M ARR): {len(small_companies)} companies, avg growth-adjusted multiple: {sum([c['growth_adjusted_multiple'] for c in small_companies])/len(small_companies):.2f}x" if small_companies else "No small companies")
                print(f"Medium companies ($5-25M ARR): {len(medium_companies)} companies, avg growth-adjusted multiple: {sum([c['growth_adjusted_multiple'] for c in medium_companies])/len(medium_companies):.2f}x" if medium_companies else "No medium companies")
                print(f"Large companies (>$25M ARR): {len(large_companies)} companies, avg growth-adjusted multiple: {sum([c['growth_adjusted_multiple'] for c in large_companies])/len(large_companies):.2f}x" if large_companies else "No large companies")
                
        else:
            print("No companies found with ARR > 0")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
