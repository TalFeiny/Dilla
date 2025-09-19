import asyncio
import os
from dotenv import load_dotenv

load_dotenv()

from app.services.unified_mcp_orchestrator import UnifiedMCPOrchestrator

async def test_dwelly_fresh():
    print("\n=== Testing Fresh Dwelly Search (No Cache) ===\n")
    
    orchestrator = UnifiedMCPOrchestrator()
    
    # Clear cache for Dwelly
    orchestrator._tavily_cache.clear()
    print("✅ Cache cleared")
    
    # Create a minimal execution context
    class ExecutionContext:
        def __init__(self):
            self.entities = {'companies': ['Dwelly'], 'sectors': [], 'stages': []}
            self.results = {}
            self.fund_params = {
                'fund_size': 100_000_000,
                'deployed': 0,
                'year': 3
            }
    
    context = ExecutionContext()
    
    # Execute company fetch
    print("Fetching data for @Dwelly...")
    result = await orchestrator._execute_company_fetch(
        {'companies': ['Dwelly']},
        context
    )
    
    print("\n=== RESULTS ===")
    if 'companies' in result and result['companies']:
        company = result['companies'][0]
        print(f"Company: {company.get('company', 'Unknown')}")
        print(f"Website: {company.get('website_url', 'Not found')}")
        print(f"Business Model: {company.get('business_model', 'Not extracted')}")
        print(f"Strategy: {company.get('strategy', 'Not extracted')}")
        print(f"Sector: {company.get('sector', 'Not extracted')}")
        print(f"Total Raised: ${company.get('total_raised', 0):,}")
        
        if company.get('acquisitions'):
            print(f"Acquisitions: {len(company['acquisitions'])} found")
            for acq in company['acquisitions'][:3]:
                if isinstance(acq, dict):
                    print(f"  - {acq.get('company', 'Unknown')}")
                else:
                    print(f"  - {acq}")
        
        if company.get('founders'):
            print(f"Founders: {len(company['founders'])} found")
            for founder in company['founders'][:3]:
                if isinstance(founder, dict):
                    print(f"  - {founder.get('name', 'Unknown')} ({founder.get('background', '')})")
                else:
                    print(f"  - {founder}")
    else:
        print("No company data returned")
        print(f"Result keys: {result.keys()}")

if __name__ == "__main__":
    asyncio.run(test_dwelly_fresh())