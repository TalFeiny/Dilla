import asyncio
import sys
sys.path.append('.')
from app.services.unified_mcp_orchestrator import UnifiedMCPOrchestrator

async def test():
    orchestrator = UnifiedMCPOrchestrator()
    
    # Fetch actual Capsaai data
    result = await orchestrator._execute_company_fetch('Capsaai')
    
    if result and result.get('companies'):
        company = result['companies'][0]
        print('Capsaai Founder Information:')
        print(f"Founders field: {company.get('founders', 'Not found')}")
        print(f"Founder field: {company.get('founder', 'Not found')}")
        print(f"Company: {company.get('company')}")
        print(f"Stage: {company.get('stage')}")
        
        # Check funding rounds
        if company.get('funding_rounds'):
            print(f"\nFunding Rounds: {len(company.get('funding_rounds'))} found")
            for round in company.get('funding_rounds'):
                investors = round.get('investors', [])
                amount = round.get('amount', 0)
                print(f"  - {round.get('round')}: ${amount:,.0f}")
                if investors:
                    print(f"    Investors: {', '.join(investors)}")

asyncio.run(test())