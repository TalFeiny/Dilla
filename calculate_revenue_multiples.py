#!/usr/bin/env python3
"""
Calculate revenue multiples from amount_raised data and analyze growth-adjusted multiples
"""

import os
from supabase import create_client, Client

def get_supabase_client() -> Client:
    url = os.getenv('NEXT_PUBLIC_SUPABASE_URL')
    key = os.getenv('SUPABASE_SERVICE_ROLE_KEY')
    return create_client(url, key)

def main():
    supabase = get_supabase_client()
    
    print("Calculating revenue multiples from amount_raised data...")
    
    try:
        # Get companies with ARR and amount_raised data
        companies_result = supabase.table('companies').select(
            'name, sector, current_arr_usd, revenue_growth_annual_pct, revenue_growth_monthly_pct, amount_raised, total_invested_usd'
        ).gt('current_arr_usd', 1000000).execute()
        
        if companies_result.data:
            print(f"Found {len(companies_result.data)} companies with ARR > $1M")
            
            companies_with_multiples = []
            
            for company in companies_result.data:
                name = company.get('name', 'Unknown')
                arr = company.get('current_arr_usd', 0) or 0
                annual_growth = company.get('revenue_growth_annual_pct', 0) or 0
                monthly_growth = company.get('revenue_growth_monthly_pct', 0) or 0
                
                # Calculate growth rate
                growth_rate = annual_growth or (monthly_growth * 12 if monthly_growth else 0)
                
                # Extract valuation from amount_raised (which contains total_raised)
                amount_raised_data = company.get('amount_raised')
                total_invested = company.get('total_invested_usd', 0) or 0
                
                valuation = None
                
                if amount_raised_data and isinstance(amount_raised_data, dict):
                    # The amount_raised field contains total_raised in millions
                    total_raised_millions = amount_raised_data.get('total_raised', 0)
                    if total_raised_millions and total_raised_millions > 0:
                        # Convert from millions to actual dollars
                        valuation = total_raised_millions * 1_000_000
                
                # Use total_invested as fallback if available
                if not valuation and total_invested > 0:
                    # Estimate valuation as 3-5x total invested (typical for later stage companies)
                    valuation = total_invested * 4  # Use 4x as middle estimate
                
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
                    'sector': company.get('sector', 'Unknown'),
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
                print("-" * 90)
                
                for i, company in enumerate(companies_with_multiples[:20], 1):
                    print(f"{i:2d}. {company['name']}")
                    print(f"    Sector: {company['sector']}")
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
                print(f"Min Revenue Multiple: {min(multiples):.2f}x")
                print(f"Max Revenue Multiple: {max(multiples):.2f}x")
                
                if growth_adjusted_multiples:
                    print(f"Average Growth-Adjusted Multiple: {sum(growth_adjusted_multiples)/len(growth_adjusted_multiples):.2f}x")
                    print(f"Median Growth-Adjusted Multiple: {sorted(growth_adjusted_multiples)[len(growth_adjusted_multiples)//2]:.2f}x")
                
                if growth_rates:
                    print(f"Average Growth Rate: {sum(growth_rates)/len(growth_rates):.1f}%")
                    print(f"Median Growth Rate: {sorted(growth_rates)[len(growth_rates)//2]:.1f}%")
                
                # Size analysis
                small_companies = [c for c in companies_with_multiples if c['arr'] < 25_000_000]
                medium_companies = [c for c in companies_with_multiples if 25_000_000 <= c['arr'] < 100_000_000]
                large_companies = [c for c in companies_with_multiples if c['arr'] >= 100_000_000]
                
                print(f"\nSize-Adjusted Analysis:")
                if small_companies:
                    avg_multiple = sum([c['revenue_multiple'] for c in small_companies])/len(small_companies)
                    avg_growth_adj = sum([c['growth_adjusted_multiple'] for c in small_companies if c['growth_adjusted_multiple']])/len([c for c in small_companies if c['growth_adjusted_multiple']]) if any(c['growth_adjusted_multiple'] for c in small_companies) else 0
                    print(f"Small companies (<$25M ARR): {len(small_companies)} companies")
                    print(f"  - Avg Revenue Multiple: {avg_multiple:.2f}x")
                    if avg_growth_adj > 0:
                        print(f"  - Avg Growth-Adjusted Multiple: {avg_growth_adj:.2f}x")
                
                if medium_companies:
                    avg_multiple = sum([c['revenue_multiple'] for c in medium_companies])/len(medium_companies)
                    avg_growth_adj = sum([c['growth_adjusted_multiple'] for c in medium_companies if c['growth_adjusted_multiple']])/len([c for c in medium_companies if c['growth_adjusted_multiple']]) if any(c['growth_adjusted_multiple'] for c in medium_companies) else 0
                    print(f"Medium companies ($25-100M ARR): {len(medium_companies)} companies")
                    print(f"  - Avg Revenue Multiple: {avg_multiple:.2f}x")
                    if avg_growth_adj > 0:
                        print(f"  - Avg Growth-Adjusted Multiple: {avg_growth_adj:.2f}x")
                
                if large_companies:
                    avg_multiple = sum([c['revenue_multiple'] for c in large_companies])/len(large_companies)
                    avg_growth_adj = sum([c['growth_adjusted_multiple'] for c in large_companies if c['growth_adjusted_multiple']])/len([c for c in large_companies if c['growth_adjusted_multiple']]) if any(c['growth_adjusted_multiple'] for c in large_companies) else 0
                    print(f"Large companies (>$100M ARR): {len(large_companies)} companies")
                    print(f"  - Avg Revenue Multiple: {avg_multiple:.2f}x")
                    if avg_growth_adj > 0:
                        print(f"  - Avg Growth-Adjusted Multiple: {avg_growth_adj:.2f}x")
                
                # Sector analysis
                sectors = {}
                for company in companies_with_multiples:
                    sector = company['sector']
                    if sector not in sectors:
                        sectors[sector] = []
                    sectors[sector].append(company)
                
                print(f"\nSector Analysis:")
                for sector, companies in sectors.items():
                    if len(companies) >= 2:  # Only show sectors with 2+ companies
                        avg_multiple = sum([c['revenue_multiple'] for c in companies])/len(companies)
                        avg_growth_adj = sum([c['growth_adjusted_multiple'] for c in companies if c['growth_adjusted_multiple']])/len([c for c in companies if c['growth_adjusted_multiple']]) if any(c['growth_adjusted_multiple'] for c in companies) else 0
                        print(f"{sector}: {len(companies)} companies, avg multiple: {avg_multiple:.2f}x", end="")
                        if avg_growth_adj > 0:
                            print(f", avg growth-adjusted: {avg_growth_adj:.2f}x")
                        else:
                            print()
                
            else:
                print("No companies found with valuation data")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
