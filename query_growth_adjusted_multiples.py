#!/usr/bin/env python3
"""
Simple SQL query script to analyze growth-adjusted revenue multiples from Supabase companies table
"""

import os
from supabase import create_client, Client

def get_supabase_client() -> Client:
    """Initialize Supabase client"""
    url = os.getenv('NEXT_PUBLIC_SUPABASE_URL')
    key = os.getenv('SUPABASE_SERVICE_ROLE_KEY')
    
    if not url or not key:
        raise ValueError("Missing Supabase credentials. Set NEXT_PUBLIC_SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY")
    
    return create_client(url, key)

def main():
    supabase = get_supabase_client()
    
    print("Querying growth-adjusted revenue multiples from companies table...")
    
    # Query companies with revenue multiples, growth rates, and size data
    query = """
    SELECT 
        name,
        sector,
        current_arr_usd,
        revenue_growth_annual_pct,
        revenue_growth_monthly_pct,
        valuation,
        estimated_valuation,
        total_invested_usd,
        amount_raised,
        cached_funding_data,
        customer_segment_enterprise_pct,
        customer_segment_midmarket_pct,
        customer_segment_sme_pct,
        data,
        metrics,
        created_at
    FROM companies 
    WHERE 
        current_arr_usd > 0 
        AND (revenue_growth_annual_pct > 0 OR revenue_growth_monthly_pct > 0)
        AND (valuation > 0 OR estimated_valuation IS NOT NULL)
    ORDER BY current_arr_usd DESC
    LIMIT 100;
    """
    
    try:
        # Execute the query using RPC
        result = supabase.rpc('exec_sql', {'sql': query}).execute()
        
        if result.data:
            print(f"Found {len(result.data)} companies with valid data")
            
            # Display results
            for company in result.data[:10]:  # Show first 10
                print(f"\nCompany: {company['name']}")
                print(f"Sector: {company['sector']}")
                print(f"ARR: ${company['current_arr_usd']:,.0f}")
                print(f"Annual Growth: {company['revenue_growth_annual_pct'] or 'N/A'}%")
                print(f"Valuation: ${company['valuation'] or company.get('estimated_valuation', {}).get('estimated_valuation', 'N/A')}")
                
                # Calculate revenue multiple
                arr = company['current_arr_usd']
                valuation = company['valuation'] or (company.get('estimated_valuation', {}) or {}).get('estimated_valuation', 0)
                if arr and valuation:
                    multiple = valuation / arr
                    print(f"Revenue Multiple: {multiple:.2f}x")
                    
                    # Calculate growth-adjusted multiple
                    growth_rate = company['revenue_growth_annual_pct'] or (company['revenue_growth_monthly_pct'] or 0) * 12
                    if growth_rate and growth_rate > 0:
                        growth_adjusted_multiple = multiple / (growth_rate / 100)
                        print(f"Growth-Adjusted Multiple: {growth_adjusted_multiple:.2f}x")
                
                print("-" * 50)
        else:
            print("No data found")
            
    except Exception as e:
        print(f"Error executing query: {e}")
        
        # Try alternative approach with direct table query
        print("Trying alternative query approach...")
        try:
            result = supabase.table('companies').select(
                'name, sector, current_arr_usd, revenue_growth_annual_pct, revenue_growth_monthly_pct, valuation, estimated_valuation'
            ).gt('current_arr_usd', 0).execute()
            
            if result.data:
                print(f"Found {len(result.data)} companies")
                
                # Calculate and display multiples
                for company in result.data[:10]:
                    print(f"\n{company['name']}: ARR=${company['current_arr_usd']:,.0f}")
                    
        except Exception as e2:
            print(f"Alternative query also failed: {e2}")

if __name__ == "__main__":
    main()
