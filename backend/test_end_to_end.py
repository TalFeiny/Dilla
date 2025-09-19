#!/usr/bin/env python3
"""Test end-to-end data flow with a real company"""

import asyncio
import json
import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

# Now import after path is set
from app.services.unified_mcp_orchestrator import UnifiedMCPOrchestrator

async def test_company_flow():
    """Test the complete data flow for a company"""
    
    print("🚀 Testing end-to-end data flow")
    print("=" * 80)
    
    # Initialize orchestrator
    orchestrator = UnifiedMCPOrchestrator()
    
    # Test with a single company
    test_prompt = "Analyze @Ramp"
    
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
            with open('test_full_result.json', 'w') as f:
                json.dump(result, f, indent=2, default=str)
            print(f"  - Full result saved to test_full_result.json")
            
            # Check for companies data in results
            if 'results' in result:
                results = result['results']
                print(f"  - Results type: {type(results)}")
                
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
                            print(f"  - Employees: {company.get('employees', 0)}")
                            print(f"  - Business model: {company.get('business_model', 'Unknown')}")
                            print(f"  - Fund fit score: {company.get('fund_fit_score', 0):.2f}")
                            
                            # Check funding rounds
                            funding = company.get('funding_analysis', {})
                            if funding.get('rounds'):
                                print(f"\n💰 Funding rounds: {len(funding['rounds'])}")
                                for round_data in funding['rounds'][:3]:  # Show first 3
                                    print(f"    - {round_data.get('series', 'Unknown')}: ${round_data.get('amount', 0):,.0f}")
                            
                            # Check if numeric values are properly extracted
                            print(f"\n🔢 Type checking:")
                            print(f"  - revenue type: {type(company.get('revenue'))}")
                            print(f"  - arr type: {type(company.get('arr'))}")
                            print(f"  - valuation type: {type(company.get('valuation'))}")
                            print(f"  - employees type: {type(company.get('employees'))}")
                            
                            # Check for inferred values
                            print(f"\n🔮 Inferred values:")
                            for key in company:
                                if '_confidence' in key:
                                    base_key = key.replace('_confidence', '')
                                    if base_key in company:
                                        print(f"  - {base_key}: {company[base_key]} (confidence: {company[key]})")
                            
                            # Save full result for inspection
                            with open('test_end_to_end_result.json', 'w') as f:
                                json.dump(company, f, indent=2, default=str)
                            print(f"\n💾 Full company data saved to test_end_to_end_result.json")
                            
            else:
                print("  - No skill_results found")
                print(f"  - Keys in result: {list(result.keys())}")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_company_flow())