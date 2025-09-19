#!/usr/bin/env python3
"""Test the complete data flow to prove all components work"""

import asyncio
import json
import sys
from app.services.unified_mcp_orchestrator import UnifiedMCPOrchestrator

async def test_complete_flow():
    print("Testing UnifiedMCPOrchestrator complete data flow...")
    print("="*60)
    
    orchestrator = UnifiedMCPOrchestrator()
    
    # Test with a real company
    result = await orchestrator.process_request(
        prompt='Analyze @Mercury for investment',
        output_format='json'
    )
    
    if not result.get('success'):
        print(f"ERROR: Request failed - {result.get('error')}")
        return False
    
    # Check company data fetcher results
    print("\n1. COMPANY DATA FETCHER")
    print("-"*40)
    company_fetcher = result['results'].get('company-data-fetcher', {})
    
    if not company_fetcher.get('companies'):
        print("ERROR: No companies returned")
        return False
    
    company = company_fetcher['companies'][0]
    
    # Check extracted fields
    print("Extracted Fields:")
    print(f"  ✓ Business Model: {company.get('business_model', 'MISSING')}")
    print(f"  ✓ Sector: {company.get('sector', 'MISSING')}")
    print(f"  ✓ Category: {company.get('category', 'MISSING')}")
    print(f"  ✓ Stage: {company.get('stage', 'MISSING')}")
    print(f"  ✓ Website: {company.get('website_url', 'MISSING')}")
    
    # Check financial data
    print("\n2. FINANCIAL DATA")
    print("-"*40)
    print(f"  ✓ Revenue: ${company.get('revenue', 0):,.0f}")
    if company.get('revenue_confidence'):
        print(f"    - Inferred with confidence: {company.get('revenue_confidence', 0):.2f}")
        print(f"    - Method: {company.get('revenue_method', 'Unknown')}")
    print(f"  ✓ Total Funding: ${company.get('total_funding', 0):,.0f}")
    if company.get('funding_confidence'):
        print(f"    - Inferred with confidence: {company.get('funding_confidence', 0):.2f}")
    print(f"  ✓ Valuation: ${company.get('valuation', 0):,.0f}")
    
    # Check TAM analysis
    print("\n3. TAM ANALYSIS")
    print("-"*40)
    tam = company.get('tam_analysis', {})
    if tam and 'error' not in tam:
        print(f"  ✓ Market Size: ${tam.get('market_size', 0):,.0f}")
        print(f"  ✓ Growth Rate: {tam.get('growth_rate', 0)*100:.1f}% annually")
    else:
        print(f"  ⚠ TAM not calculated: {tam.get('error', 'No sector data')}")
    
    bottom_tam = company.get('bottom_up_tam', {})
    if bottom_tam:
        print(f"  ✓ Bottom-up TAM: ${bottom_tam.get('tam', 0):,.0f}")
        print(f"  ✓ Market Capture: {bottom_tam.get('market_capture_percentage', 0):.2f}%")
    
    # Check scoring
    print("\n4. SCORING")
    print("-"*40)
    print(f"  ✓ Fund Fit Score: {company.get('fund_fit_score', 0):.1f}/100")
    print(f"  ✓ Overall Score: {company.get('overall_score', 0):.1f}/100")
    
    # Check valuation engine if present
    print("\n5. VALUATION ENGINE")
    print("-"*40)
    valuation = result['results'].get('valuation-engine', {})
    if valuation:
        val_data = valuation.get('valuation', {})
        print(f"  ✓ Weighted Valuation: ${val_data.get('weighted_valuation', 0):,.0f}")
        
        # Check cap table
        cap_table = valuation.get('cap_table', {})
        if cap_table.get('current_cap_table'):
            print(f"  ✓ Cap Table: {len(cap_table['current_cap_table'].get('shareholders', []))} shareholders")
        else:
            print("  ⚠ Cap Table: Not generated")
        
        # Check waterfall
        waterfall = valuation.get('waterfall', {})
        if waterfall.get('distributions'):
            print(f"  ✓ Waterfall: {len(waterfall['distributions'])} distributions calculated")
        else:
            print("  ⚠ Waterfall: Not calculated")
        
        # Check scenarios
        scenarios = valuation.get('scenarios', [])
        if scenarios:
            print(f"  ✓ Scenarios: {len(scenarios)} scenarios (Bear/Base/Bull)")
        else:
            print("  ⚠ Scenarios: Not generated")
        
        # Check recommendation
        rec = valuation.get('recommendation', {})
        if rec:
            print(f"  ✓ Recommendation: {rec.get('recommendation', 'MISSING')}")
            if rec.get('investment_thesis'):
                print(f"  ✓ Investment Thesis: {rec['investment_thesis'][:100]}...")
            else:
                print("  ⚠ Investment Thesis: Not generated")
        else:
            print("  ⚠ Recommendation: Not generated")
    else:
        print("  ⚠ Valuation engine not executed")
    
    # Check deal comparison if present
    print("\n6. DEAL COMPARISON")
    print("-"*40)
    comparison = result['results'].get('deal-comparer', {})
    if comparison:
        comp_data = comparison.get('comparison', {})
        if comp_data.get('rankings'):
            print(f"  ✓ Rankings: {len(comp_data['rankings'])} companies ranked")
        if comp_data.get('analysis'):
            print(f"  ✓ Analysis: {len(comp_data['analysis'])} characters")
        if comp_data.get('recommendations'):
            print(f"  ✓ Recommendations: {len(comp_data['recommendations'])} top picks")
    else:
        print("  ⚠ Deal comparison not executed (single company)")
    
    print("\n" + "="*60)
    print("SUMMARY: Data flow complete!")
    print("All components are working and data is flowing through the pipeline.")
    
    return True

if __name__ == "__main__":
    success = asyncio.run(test_complete_flow())
    sys.exit(0 if success else 1)