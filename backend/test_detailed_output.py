#!/usr/bin/env python3
"""
Test to show detailed output of text extraction
"""

import requests
import json

def test_detailed():
    """Test and show full extraction output"""
    
    url = "http://localhost:8000/api/agent/unified-brain"
    
    payload = {
        "prompt": "Get detailed data about @Deel including funding, valuation, and business model",
        "output_format": "analysis",
        "context": {}
    }
    
    print(f"Testing with: {payload['prompt']}")
    print("=" * 80)
    
    try:
        response = requests.post(url, json=payload, timeout=45)
        
        if response.status_code == 200:
            result = response.json()
            
            if result.get('success'):
                data = result.get('result', {}).get('data', {})
                
                # Check for company data
                if 'company-data-fetcher' in data:
                    fetcher_data = data['company-data-fetcher']
                    if 'companies' in fetcher_data:
                        for company in fetcher_data['companies']:
                            print(f"\n📊 Company: {company.get('company', 'Unknown')}")
                            print("-" * 40)
                            
                            # Show extracted data
                            if 'extracted_data' in company:
                                extracted = company['extracted_data']
                                print("\n✅ EXTRACTED DATA (from text):")
                                print(f"  Company Name: {extracted.get('company_name', 'N/A')}")
                                print(f"  Website: {extracted.get('website_url', 'N/A')}")
                                print(f"  Stage: {extracted.get('stage', 'N/A')}")
                                print(f"  Business Model: {extracted.get('business_model', 'N/A')}")
                                print(f"  Team Size: {extracted.get('team_size', 'N/A')}")
                                print(f"  Founder: {extracted.get('founder', 'N/A')}")
                                
                                # Funding info
                                total_raised = extracted.get('total_raised', 0)
                                if total_raised > 0:
                                    print(f"  Total Raised: ${total_raised/1000000:.1f}M")
                                
                                funding_rounds = extracted.get('funding_rounds', [])
                                if funding_rounds:
                                    print(f"\n  Funding Rounds ({len(funding_rounds)}):")
                                    for round_data in funding_rounds[:3]:  # Show first 3
                                        print(f"    - {round_data.get('round', 'Unknown')}: ${round_data.get('amount', 0)/1000000:.1f}M")
                                        if round_data.get('date'):
                                            print(f"      Date: {round_data['date']}")
                                        if round_data.get('investors'):
                                            print(f"      Investors: {', '.join(round_data['investors'][:3])}")
                                
                                # Valuation
                                valuation = extracted.get('valuation', 0)
                                if valuation > 0:
                                    print(f"\n  Valuation: ${valuation/1000000000:.1f}B")
                                
                                # Revenue/ARR
                                revenue = extracted.get('revenue', 0)
                                arr = extracted.get('arr', 0)
                                if revenue > 0:
                                    print(f"  Revenue: ${revenue/1000000:.1f}M")
                                if arr > 0:
                                    print(f"  ARR: ${arr/1000000:.1f}M")
                                
                                # Growth
                                growth = extracted.get('growth_rate', 0)
                                if growth > 0:
                                    print(f"  Growth Rate: {growth*100:.0f}%")
                                
                                # Customers
                                customers = extracted.get('customers', [])
                                if customers:
                                    print(f"\n  Customers ({len(customers)}): {', '.join(customers[:5])}")
                                
                                # Investors  
                                investors = extracted.get('investors', [])
                                if investors:
                                    print(f"  Investors: {', '.join(investors[:5])}")
                            
                            # Show search results summary
                            if 'search_results' in company:
                                print("\n📝 SEARCH RESULTS:")
                                for search_type, result in company['search_results'].items():
                                    if isinstance(result, dict) and result.get('success'):
                                        results = result.get('data', {}).get('results', [])
                                        print(f"  {search_type}: {len(results)} results")
                                        if results:
                                            # Show first result
                                            first = results[0]
                                            print(f"    - {first.get('title', 'No title')[:60]}...")
                                            # Check if we have text content
                                            if 'content' in first:
                                                print(f"      ✅ Text content: {len(first['content'])} chars")
                                            if 'raw_content' in first:
                                                print(f"      ❌ Raw HTML still present!")
                
                print("\n" + "=" * 80)
                print("✅ Extraction completed successfully!")
                
                # Save full result for inspection
                with open('extraction_result.json', 'w') as f:
                    json.dump(result, f, indent=2)
                print("\n💾 Full result saved to extraction_result.json")
                
            else:
                print(f"❌ Request failed: {result.get('error')}")
        else:
            print(f"❌ HTTP {response.status_code}: {response.text[:500]}")
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_detailed()