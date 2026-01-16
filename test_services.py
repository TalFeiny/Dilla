"""Test service failures to identify root causes"""
import asyncio
import sys
import os
sys.path.insert(0, 'backend')
os.chdir('backend')

from app.services.unified_mcp_orchestrator import UnifiedMCPOrchestrator
from app.services.valuation_engine_service import ValuationEngineService
from app.services.pre_post_cap_table import PrePostCapTable
from app.services.intelligent_gap_filler import IntelligentGapFiller

async def test_services():
    print("Testing Services...")
    print("=" * 50)
    
    # 1. Test company fetch
    print("\n1. Testing Company Fetch...")
    orchestrator = UnifiedMCPOrchestrator()
    
    try:
        result = await orchestrator.process_request({
            'skill': 'company_search_and_fetch',
            'params': {'companies': ['@Mercury']}
        })
        
        if result and 'results' in result and result['results']:
            company = result['results'][0]
            print(f"✓ Fetched: {company.get('company_name')}")
            print(f"  Revenue: {company.get('revenue')} / Inferred: {company.get('inferred_revenue')}")
            print(f"  Valuation: {company.get('valuation')} / Inferred: {company.get('inferred_valuation')}")
            print(f"  Stage: {company.get('stage')}")
            
            # 2. Test valuation service
            print("\n2. Testing Valuation Service...")
            valuation_service = ValuationEngineService()
            
            try:
                # Prepare data for valuation
                val_result = await valuation_service.calculate_valuation(company)
                print(f"✓ Valuation calculated: ${val_result.fair_value:,.0f}")
                print(f"  Method: {val_result.primary_method}")
            except Exception as e:
                print(f"✗ Valuation failed: {e}")
                import traceback
                traceback.print_exc()
            
            # 3. Test cap table service
            print("\n3. Testing Cap Table Service...")
            cap_table = PrePostCapTable()
            
            try:
                cap_result = cap_table.calculate_full_cap_table_history(company)
                if cap_result:
                    print(f"✓ Cap table calculated")
                    print(f"  Rounds: {len(cap_result.get('history', []))}")
                else:
                    print("✗ Cap table returned None")
            except Exception as e:
                print(f"✗ Cap table failed: {e}")
                import traceback
                traceback.print_exc()
            
            # 4. Test deck generation
            print("\n4. Testing Deck Generation...")
            try:
                deck_result = await orchestrator.process_request({
                    'skill': 'generate_investment_deck',
                    'params': {
                        'companies': [company],
                        'fund_context': {
                            'fund_name': 'Test Fund',
                            'fund_size': 260_000_000,
                            'check_size_range': [5_000_000, 15_000_000]
                        }
                    }
                })
                
                if deck_result and 'deck' in deck_result:
                    deck = deck_result['deck']
                    print(f"✓ Deck generated: {deck.get('title')}")
                    print(f"  Slides: {len(deck.get('slides', []))}")
                else:
                    print("✗ Deck generation returned no deck")
            except Exception as e:
                print(f"✗ Deck generation failed: {e}")
                import traceback
                traceback.print_exc()
                
        else:
            print("✗ No company data returned")
    except Exception as e:
        print(f"✗ Company fetch failed: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "=" * 50)
    print("Test Complete")

if __name__ == "__main__":
    asyncio.run(test_services())