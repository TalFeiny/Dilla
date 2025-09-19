import asyncio
import os
from dotenv import load_dotenv
load_dotenv()

async def test_julius():
    from app.services.unified_mcp_orchestrator import UnifiedMCPOrchestrator
    
    orchestrator = UnifiedMCPOrchestrator()
    
    print('\n=== TESTING JULIUS AI ===\n')
    
    result = await orchestrator.process_request(
        prompt='Analyze @Julius and tell me their business category, compute intensity, and founder quality',
        output_format='analysis',
        context={}
    )
    
    if isinstance(result, dict) and 'companies' in result and result['companies']:
        company = result['companies'][0]
        print(f"Company: {company.get('company_name', 'Unknown')}")
        print(f"Website: {company.get('website_url', 'Not found')}")
        print(f"Business Model: {company.get('business_model', 'Unknown')}")
        print(f"Category: {company.get('category', company.get('business_model', 'Unknown'))}")
        
        total = company.get('total_raised', 0)
        if total:
            print(f"Total Raised: ${total:,}")
        else:
            print("Total Raised: Unknown")
            
        print(f"Founder: {company.get('founder', 'Unknown')}")
        print(f"Team Size: {company.get('team_size', 0)}")
        
        # Check for compute intensity and founder quality in the analysis
        if 'analysis' in result:
            print(f"\nAnalysis Preview: {result['analysis'][:500]}...")

if __name__ == "__main__":
    asyncio.run(test_julius())