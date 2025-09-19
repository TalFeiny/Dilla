#!/usr/bin/env python3
"""Test website finding and funding scraping for specific companies"""

import asyncio
import json
from app.services.unified_mcp_orchestrator import get_unified_orchestrator

async def test_company(company_name):
    """Test a single company's data extraction"""
    print(f"\n{'='*80}")
    print(f"Testing: {company_name}")
    print('='*80)
    
    orchestrator = get_unified_orchestrator()
    
    # Test with deck format to get full cap table
    prompt = f"Create a comprehensive investment deck for {company_name} with full cap table and funding history"
    
    result = await orchestrator.process_request(
        prompt=prompt,
        output_format="deck",
        context={}
    )
    
    # Extract and display key information
    if result.get('success'):
        data = result.get('data', {})
        
        # Check website extraction
        print(f"\n📌 WEBSITE EXTRACTION:")
        if 'company_overview' in data:
            overview = data['company_overview']
            print(f"  Website: {overview.get('website', 'NOT FOUND')}")
            print(f"  Location: {overview.get('location', 'NOT FOUND')}")
        
        # Check funding extraction
        print(f"\n💰 FUNDING DATA:")
        if 'funding_history' in data:
            funding = data['funding_history']
            print(f"  Total Raised: ${funding.get('total_raised', 0):,.0f}")
            print(f"  Number of Rounds: {funding.get('num_rounds', 0)}")
            
            if 'rounds' in funding:
                for round_data in funding['rounds'][:5]:  # Show first 5 rounds
                    print(f"\n  Round: {round_data.get('round', 'Unknown')}")
                    print(f"    Amount: ${round_data.get('amount', 0):,.0f}")
                    print(f"    Date: {round_data.get('date', 'N/A')}")
                    print(f"    Investors: {round_data.get('investors', [])}")
        
        # Check cap table
        print(f"\n📊 CAP TABLE:")
        if 'cap_table' in data:
            cap_table = data['cap_table']
            if 'current_ownership' in cap_table:
                print("  Current Ownership:")
                for holder, pct in cap_table['current_ownership'].items():
                    print(f"    {holder}: {pct:.2f}%")
            elif 'current_cap_table' in cap_table:
                print("  Current Cap Table:")
                for holder, pct in cap_table['current_cap_table'].items():
                    print(f"    {holder}: {pct:.2f}%")
        
        # Save full response
        filename = f"test_output_{company_name.replace('@', '').lower()}.json"
        with open(filename, 'w') as f:
            json.dump(result, f, indent=2, default=str)
        print(f"\n✅ Full response saved to {filename}")
        
    else:
        print(f"❌ Error: {result.get('error', 'Unknown error')}")
    
    return result

async def main():
    """Test both companies"""
    companies = ["@Dwelly", "@ArtificialSocieties"]
    
    for company in companies:
        try:
            await test_company(company)
        except Exception as e:
            print(f"❌ Failed to test {company}: {e}")

if __name__ == "__main__":
    asyncio.run(main())