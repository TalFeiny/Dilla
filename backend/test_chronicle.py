import asyncio
import os
from dotenv import load_dotenv
load_dotenv()

async def test_chronicle():
    from app.services.unified_mcp_orchestrator import UnifiedMCPOrchestrator
    
    orchestrator = UnifiedMCPOrchestrator()
    
    print('\n=== TESTING CHRONICLE ===\n')
    
    # Call the main process_request method instead
    result = await orchestrator.process_request(
        prompt='Analyze @Chronicle',
        output_format='analysis',
        context={}
    )
    
    # The result should contain analyzed companies
    if isinstance(result, dict):
        # Check if companies are in the result
        if 'companies' in result and result['companies']:
            company = result['companies'][0]
            print(f"Company: {company.get('company_name', 'Unknown')}")
            print(f"Website: {company.get('website_url', 'Not found')}")
            print(f"Business Model: {company.get('business_model', 'Unknown')}")
            print(f"Total Raised: ${company.get('total_raised', 0):,}")
            
            if company.get('website_url'):
                print('\n✅ Website found and extracted!')
            else:
                print('\n❌ No website found')
        else:
            # Check top level for company data
            print(f"Result keys: {list(result.keys())[:10]}")

if __name__ == "__main__":
    asyncio.run(test_chronicle())