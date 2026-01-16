#!/usr/bin/env python3
"""
Check what valuation-related columns actually exist in the companies table
"""

import os
from supabase import create_client, Client

def get_supabase_client() -> Client:
    url = os.getenv('NEXT_PUBLIC_SUPABASE_URL')
    key = os.getenv('SUPABASE_SERVICE_ROLE_KEY')
    return create_client(url, key)

def main():
    supabase = get_supabase_client()
    
    print("Checking valuation-related columns in companies table...")
    
    try:
        # Get one company to see all column names
        result = supabase.table('companies').select('*').limit(1).execute()
        
        if result.data:
            company = result.data[0]
            print(f"Sample company: {company.get('name', 'Unknown')}")
            print("\nAll available columns:")
            
            # Look for valuation-related columns
            valuation_columns = []
            for key, value in company.items():
                print(f"  {key}: {value}")
                if any(term in key.lower() for term in ['valuation', 'value', 'market', 'cap', 'price', 'worth']):
                    valuation_columns.append((key, value))
            
            print(f"\nPotential valuation-related columns:")
            for col_name, col_value in valuation_columns:
                print(f"  {col_name}: {col_value}")
            
            # Now let's query companies with different potential valuation columns
            print(f"\nTrying different valuation column names...")
            
            # Try various column names
            potential_columns = [
                'valuation', 'latest_valuation_usd', 'market_cap', 'enterprise_value',
                'estimated_valuation', 'current_valuation', 'last_valuation',
                'total_raised', 'amount_raised', 'latest_funding_round'
            ]
            
            for col in potential_columns:
                try:
                    test_result = supabase.table('companies').select(f'name, {col}').not_.is_(col, 'null').limit(3).execute()
                    if test_result.data:
                        print(f"\nColumn '{col}' has data:")
                        for company in test_result.data:
                            print(f"  {company['name']}: {company.get(col)}")
                except:
                    print(f"Column '{col}' does not exist or has no data")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
