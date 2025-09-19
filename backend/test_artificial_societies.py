#!/usr/bin/env python3
"""
Test @ArtificialSocieties - checking TAM calculation and investment case
"""
import asyncio
import json
import sys
import os
from datetime import datetime

sys.path.insert(0, '/Users/admin/code/dilla-ai/backend')

from app.services.unified_mcp_orchestrator import UnifiedMCPOrchestrator

async def test_artificial_societies():
    """Test with @ArtificialSocieties"""
    print("\n" + "="*80)
    print("TESTING: @ArtificialSocieties")
    print("="*80 + "\n")
    
    orchestrator = UnifiedMCPOrchestrator()
    
    request = {
        'prompt': 'Analyze @ArtificialSocieties - show market sizing and investment case',
        'output_format': 'analysis',
        'context': {}
    }
    
    print("📋 Processing @ArtificialSocieties...")
    
    try:
        result = await orchestrator.process_request(request)
        
        # Check for companies
        if 'companies' in result and len(result.get('companies', [])) > 0:
            company = result['companies'][0]
            print(f"\n✅ Found: {company.get('name', 'Unknown')}")
            print(f"   Business Model: {company.get('business_model', 'Unknown')}")
            print(f"   Stage: {company.get('stage', 'Unknown')}")
            print(f"   Revenue: ${company.get('revenue', 0):,.0f}")
            
            # Check investment case and market sizing
            if 'investment_case' in company:
                inv = company['investment_case']
                market = inv.get('market_position', {})
                
                print("\n📊 MARKET SIZING:")
                tam = market.get('tam', 0)
                print(f"   TAM: ${tam:,.0f}")
                
                # Check if TAM is realistic
                if tam > 1_000_000_000_000:  # Over 1 trillion
                    print(f"   ❌ UNREALISTIC TAM: ${tam/1e12:.1f} TRILLION (labor pool not software)")
                elif tam > 100_000_000_000:  # Over 100B
                    print(f"   ⚠️  High TAM: ${tam/1e9:.1f} billion")
                else:
                    print(f"   ✅ Realistic TAM: ${tam/1e9:.2f} billion")
                
                # Check TAM calculation methods
                if 'tam_calculation' in inv.get('market_position', {}):
                    tam_calc = inv['market_position']['tam_calculation']
                    print("\n   TAM Methods Used:")
                    if tam_calc.get('primary_tam'):
                        print(f"   • Primary TAM: ${tam_calc['primary_tam']:,.0f}")
                    if tam_calc.get('bottom_up_tam'):
                        print(f"   • Bottom-up TAM: ${tam_calc['bottom_up_tam']:,.0f}")
                    if tam_calc.get('segment_tam'):
                        print(f"   • Segment TAM: ${tam_calc['segment_tam']:,.0f}")
                    if tam_calc.get('labor_pool_ceiling'):
                        print(f"   • Labor Pool Ceiling: ${tam_calc['labor_pool_ceiling']:,.0f}")
                
                print(f"\n   Current Penetration: {market.get('current_penetration', 'N/A')}")
                print(f"   Target Penetration: {market.get('target_penetration', 'N/A')}")
                print(f"   Required CAGR: {market.get('required_cagr', 'N/A')}")
                
                # Check ownership recommendation
                if 'ownership_recommendation' in inv:
                    own = inv['ownership_recommendation']
                    print(f"\n💰 INVESTMENT RECOMMENDATION:")
                    print(f"   {own.get('recommendation', 'N/A')}")
                    
                # Check for citations
                citations = result.get('citations', [])
                if citations:
                    print(f"\n📚 Citations: {len(citations)} sources")
                    for i, cite in enumerate(citations[:2]):
                        print(f"   [{i+1}] {cite.get('source', 'Unknown')}")
                else:
                    print("\n⚠️  No citations found")
                    
            else:
                print("\n❌ No investment_case generated")
                
        else:
            print("\n❌ No companies returned")
            print(f"Result keys: {list(result.keys())}")
            if 'errors' in result:
                print(f"Errors: {result['errors']}")
                
        # Save result
        output_file = f"artificial_societies_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(output_file, 'w') as f:
            json.dump(result, f, indent=2, default=str)
        print(f"\n💾 Full result saved to: {output_file}")
        
    except Exception as e:
        print(f"\n💥 Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_artificial_societies())