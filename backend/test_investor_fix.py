#!/usr/bin/env python3
import asyncio
import sys
import os
import json
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent
sys.path.insert(0, str(backend_path))

# Set up environment
os.environ['OPENAI_API_KEY'] = os.environ.get('OPENAI_API_KEY', '')
os.environ['CLAUDE_API_KEY'] = os.environ.get('CLAUDE_API_KEY', '')
os.environ['TAVILY_API_KEY'] = os.environ.get('TAVILY_API_KEY', '')

from app.services.unified_mcp_orchestrator import UnifiedMCPOrchestrator

async def test_investor_extraction():
    """Test that investor extraction works for Vega and 73Strings"""
    orchestrator = UnifiedMCPOrchestrator()
    
    try:
        # Test the company fetch
        request = {
            'skill': 'company_fetch',
            'inputs': {
                'companies': ['@Vega', '@73Strings'],
                'show_citations': False
            }
        }
        
        print("Testing investor extraction for @Vega and @73Strings...")
        result = await orchestrator.process_request(request)
        
        if 'error' in result:
            print(f"ERROR: {result['error']}")
            return False
        
        # Check each company
        companies = result.get('companies', [])
        print(f"\nFound {len(companies)} companies")
        
        for company in companies:
            company_name = company.get('company', 'Unknown')
            print(f"\n{'='*50}")
            print(f"Company: {company_name}")
            print(f"Business: {company.get('business_model', 'Unknown')}")
            print(f"Total Funding: ${company.get('total_funding', 0):,.0f}")
            
            funding_rounds = company.get('funding_rounds', [])
            print(f"Funding Rounds: {len(funding_rounds)}")
            
            for round_data in funding_rounds:
                round_name = round_data.get('round', 'Unknown')
                amount = round_data.get('amount', 0)
                investors = round_data.get('investors', [])
                
                print(f"\n  {round_name}: ${amount:,.0f}")
                print(f"  Investors ({len(investors)}): {', '.join(investors) if investors else 'None found'}")
                
                # Check for None investors - this was the bug
                if investors is None:
                    print(f"  ❌ ERROR: Investors is None for {round_name}!")
                    return False
                elif not isinstance(investors, list):
                    print(f"  ❌ ERROR: Investors is not a list: {type(investors)}")
                    return False
                elif len(investors) == 0:
                    print(f"  ⚠️  Warning: No investors found for {round_name}")
        
        print(f"\n{'='*50}")
        print("✅ All funding rounds have investors as lists (not None)")
        return True
        
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        # Clean up
        if hasattr(orchestrator, 'close'):
            await orchestrator.close()

if __name__ == "__main__":
    success = asyncio.run(test_investor_extraction())
    sys.exit(0 if success else 1)