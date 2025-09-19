import asyncio
import json
from app.services.unified_mcp_orchestrator import UnifiedMCPOrchestrator

async def test_capsaai():
    orchestrator = UnifiedMCPOrchestrator()
    
    # Process the request
    result = await orchestrator.process_request({
        'prompt': '@capsaai',
        'output_format': 'analysis',
        'context': {}
    })
    
    if 'result' in result and 'data' in result['result']:
        result_data = result['result']['data']
        if 'company-data-fetcher' in result_data:
            fetcher = result_data['company-data-fetcher']
            if 'companies' in fetcher and fetcher['companies']:
                company = fetcher['companies'][0]
                print('=== CAPSAAI EXTRACTION ===')
                print(f"Company: {company.get('company_name', 'Unknown')}")
                print(f"Website: {company.get('website_url', 'Not found')}")
                
                # Check what search results found
                if 'search_results' in company:
                    sr = company['search_results']
                    print("\n=== SEARCH RESULTS ===")
                    for search_type, result in sr.items():
                        if isinstance(result, dict) and result.get('success'):
                            print(f"\n{search_type.upper()} search:")
                            if 'data' in result and 'results' in result['data']:
                                results = result['data']['results']
                                for i, r in enumerate(results[:3]):
                                    print(f"\n  Result {i+1}:")
                                    print(f"    URL: {r.get('url', '')[:80]}")
                                    content = r.get('content', '')
                                    # Look for actual funding info
                                    if any(word in content.lower() for word in ['seed', 'series', 'raised', 'funding', '2.7', 'million']):
                                        print(f"    FUNDING MENTION: {content[:300]}")
                
                print(f"\n=== EXTRACTED DATA ===")
                print(f"Funding Rounds: {len(company.get('funding_rounds', []))}")
                for round in company.get('funding_rounds', []):
                    print(f"  Amount: ${round.get('amount', 0)/1000000:.1f}M")
                    print(f"  Round: {round.get('round', 'Unknown')}")
                    print(f"  Raw text: {round.get('raw_text', 'No raw text')}")
                
                print(f"\nTotal Raised: ${company.get('total_raised', 0)/1000000:.1f}M")
                print(f"Valuation: ${company.get('valuation', 0)/1000000:.0f}M")

if __name__ == "__main__":
    asyncio.run(test_capsaai())