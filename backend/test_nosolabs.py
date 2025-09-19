#!/usr/bin/env python3
"""Test with @NosoLabs - an early stage company"""

import asyncio
import json
import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

from app.services.unified_mcp_orchestrator import UnifiedMCPOrchestrator

async def test_nosolabs():
    """Test the complete data flow for NosoLabs"""
    
    print("🚀 Testing with NosoLabs (early-stage company)")
    print("=" * 80)
    
    # Initialize orchestrator
    orchestrator = UnifiedMCPOrchestrator()
    
    # Test with NosoLabs
    test_prompt = "Analyze @NosoLabs"
    
    print(f"📝 Testing with prompt: {test_prompt}")
    print("-" * 80)
    
    try:
        # Process the request
        result = await orchestrator.process_request(
            prompt=test_prompt,
            output_format="analysis",
            context={}
        )
        
        print("\n✅ Request processed successfully!")
        print("\n📊 Result structure:")
        
        if isinstance(result, dict):
            # Save full result for debugging
            with open('test_nosolabs_result.json', 'w') as f:
                json.dump(result, f, indent=2, default=str)
            print(f"  - Full result saved to test_nosolabs_result.json")
            
            # Check for companies data in results
            if 'results' in result:
                results = result['results']
                
                # If results is a dict, check for companies key
                if isinstance(results, dict) and 'companies' in results:
                    companies = results['companies']
                    if companies:
                        company = companies[0]  # First company
                        print(f"\n🏢 Company: {company.get('company', 'Unknown')}")
                        print(f"  - Website: {company.get('website_url', 'Not found')}")
                        print(f"  - Stage: {company.get('stage', 'Unknown')}")
                        print(f"  - Total raised: ${company.get('total_raised', 0):,.0f}")
                        print(f"  - Revenue: ${company.get('revenue', 0):,.0f}")
                        print(f"  - ARR: ${company.get('arr', 0):,.0f}")
                        print(f"  - Valuation: ${company.get('valuation', 0):,.0f}")
                        print(f"  - Business model: {company.get('business_model', 'Unknown')}")
                        print(f"  - Fund fit score: {company.get('fund_fit_score', 0):.2f}")
                        
                        # Check if YC company
                        print(f"\n🚀 YC Analysis:")
                        print(f"  - YC Company: {company.get('is_yc', False)}")
                        print(f"  - YC Batch: {company.get('yc_batch', 'N/A')}")
                        
                        # Check SAFE/convertible notes
                        print(f"\n💰 Funding structure:")
                        funding = company.get('funding_analysis', {})
                        if funding.get('rounds'):
                            for round_data in funding['rounds']:
                                print(f"  - {round_data.get('series', 'Unknown')}: ${round_data.get('amount', 0):,.0f}")
                                if 'safe' in str(round_data.get('type', '')).lower():
                                    print(f"    → SAFE detected!")
                                if 'convertible' in str(round_data.get('type', '')).lower():
                                    print(f"    → Convertible note detected!")
                        
                        # Check valuation methods applied
                        print(f"\n📈 Valuation methods:")
                        if 'valuation_methods' in company:
                            for method, value in company['valuation_methods'].items():
                                print(f"  - {method}: ${value:,.0f}")
                        
                        # Check cap table
                        print(f"\n📊 Cap table:")
                        if 'cap_table' in company:
                            cap_table = company['cap_table']
                            if isinstance(cap_table, dict):
                                for investor, ownership in cap_table.items():
                                    print(f"  - {investor}: {ownership}%")
                        
                        # Check investor advice
                        print(f"\n💡 Investor advice:")
                        if 'investor_advice' in company:
                            print(f"  {company['investor_advice']}")
                        if 'fund_multiple_potential' in company:
                            print(f"  - Fund multiple potential: {company['fund_multiple_potential']}x")
                        
            else:
                print("  - No results found")
                print(f"  - Keys in result: {list(result.keys())}")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_nosolabs())