import asyncio
import sys
import os
sys.path.insert(0, '/Users/admin/code/dilla-ai/backend')
from app.services.intelligent_gap_filler import IntelligentGapFiller
from app.services.unified_mcp_orchestrator import UnifiedMCPOrchestrator

async def test_howieai():
    print('Testing market sizing with @Howieai...')
    
    # Create orchestrator
    orchestrator = UnifiedMCPOrchestrator()
    
    # Test request
    request = {
        'prompt': 'Analyze @Howieai market sizing and investment case',
        'output_format': 'analysis',
        'context': {}
    }
    
    try:
        result = await orchestrator.process_request(request)
        
        # Extract key market metrics
        if 'companies' in result and len(result['companies']) > 0:
            company = result['companies'][0]
            print(f"\nCompany: {company.get('name', 'Howieai')}")
            print(f"Business Model: {company.get('business_model')}")
            
            # Check investment case
            if 'investment_case' in company:
                inv = company['investment_case']
                market = inv.get('market_position', {})
                print(f"\nMarket Position:")
                print(f"  TAM: ${market.get('tam', 0):,.0f}")
                print(f"  Current Penetration: {market.get('current_penetration', 'N/A')}")
                print(f"  Target Penetration: {market.get('target_penetration', 'N/A')}")
                print(f"  Required CAGR: {market.get('required_cagr', 'N/A')}")
                
                # Check if TAM is realistic (not trillions)
                tam = market.get('tam', 0)
                if tam > 1_000_000_000_000:  # Over 1 trillion
                    print(f"\n⚠️ WARNING: TAM is unrealistic (${tam/1e12:.1f}T)")
                else:
                    print(f"\n✅ TAM is realistic")
                    
            # Check citations
            if 'citations' in result:
                print(f"\n📚 Citations: {len(result.get('citations', []))} sources")
                for i, cite in enumerate(result.get('citations', [])[:3]):
                    print(f"  [{i+1}] {cite.get('source', 'Unknown source')}")
        else:
            print('No company data returned')
            print(f'Result keys: {list(result.keys())}')
            
    except Exception as e:
        print(f'Error: {e}')
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_howieai())