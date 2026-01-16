#!/usr/bin/env python3
"""
Comprehensive test of the data pipeline to verify all fixes are working
"""

import asyncio
import json
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent))

from app.services.unified_mcp_orchestrator import UnifiedMCPOrchestrator
from app.services.structured_data_extractor import StructuredDataExtractor
from app.services.intelligent_gap_filler import IntelligentGapFiller
from app.services.valuation_engine_service import ValuationEngineService

async def test_data_pipeline():
    """Test the complete data flow with a real company"""
    
    print("\n" + "="*80)
    print("DATA PIPELINE VERIFICATION TEST")
    print("="*80 + "\n")
    
    # Initialize services
    orchestrator = UnifiedMCPOrchestrator()
    extractor = StructuredDataExtractor()
    gap_filler = IntelligentGapFiller()
    valuation_engine = ValuationEngineService()
    
    # Test with @Cursor (AI code editor company)
    test_prompt = "Analyze @Cursor and @Perplexity for investment"
    
    print("🔍 Testing with prompt:", test_prompt)
    print("-" * 40)
    
    try:
        # Process through orchestrator
        result = await orchestrator.process_request(
            prompt=test_prompt,
            output_format="analysis",
            context={}
        )
        
        # Check if we got companies data
        if 'companies' in result:
            companies = result['companies']
            print(f"\n✅ Found {len(companies)} companies\n")
            
            for i, company in enumerate(companies, 1):
                print(f"\n{'='*60}")
                print(f"Company #{i}: {company.get('name', 'Unknown')}")
                print(f"{'='*60}")
                
                # 1. Check semantic extraction fields
                print("\n📝 SEMANTIC EXTRACTION:")
                print(f"  Product Description: {company.get('product_description', 'MISSING')}")
                print(f"  Who They Sell To: {company.get('who_they_sell_to', 'MISSING')}")
                print(f"  How They Grow: {company.get('how_they_grow', 'MISSING')}")
                print(f"  Business Model: {company.get('business_model', 'MISSING')}")
                print(f"  Vertical: {company.get('vertical', 'MISSING')}")
                
                # 2. Check TAM calculation
                print("\n💰 TAM CALCULATION:")
                tam = company.get('tam', 0)
                labor_tam = company.get('labor_tam', 0)
                traditional_tam = company.get('traditional_tam', 0)
                print(f"  Traditional TAM: ${traditional_tam:,.0f}")
                print(f"  Labor TAM: ${labor_tam:,.0f}")
                print(f"  Final TAM: ${tam:,.0f}")
                print(f"  Labor Roles Replaced: {company.get('labor_roles_replaced', 'N/A')}")
                
                # 3. Check GPU economics
                print("\n🖥️ GPU ECONOMICS:")
                gpu_cost_ratio = company.get('gpu_cost_ratio', 0)
                gpu_cost_per_transaction = company.get('gpu_cost_per_transaction', 0)
                print(f"  GPU Cost Ratio: {gpu_cost_ratio:.1%}")
                print(f"  Cost per Transaction: ${gpu_cost_per_transaction:.2f}")
                print(f"  Business Type: {company.get('business_type', 'Unknown')}")
                
                # 4. Check valuation and revenue
                print("\n📊 VALUATION & REVENUE:")
                valuation = company.get('valuation', 0)
                inferred_valuation = company.get('inferred_valuation', 0)
                revenue = company.get('revenue', 0) 
                inferred_revenue = company.get('inferred_revenue', 0)
                
                # Extract numeric values properly
                if hasattr(valuation, 'value'):
                    valuation = valuation.value
                if hasattr(revenue, 'value'):
                    revenue = revenue.value
                    
                print(f"  Valuation: ${valuation:,.0f}")
                print(f"  Inferred Valuation: ${inferred_valuation:,.0f}")
                print(f"  Revenue: ${revenue:,.0f}")
                print(f"  Inferred Revenue: ${inferred_revenue:,.0f}")
                
                # 5. Check cap table data
                print("\n📈 CAP TABLE DATA:")
                cap_table = company.get('cap_table', {})
                if cap_table:
                    print(f"  Rounds: {len(cap_table.get('rounds', []))}")
                    print(f"  Current Ownership:")
                    ownership = cap_table.get('current_ownership', {})
                    for owner, pct in ownership.items():
                        print(f"    - {owner}: {pct:.1f}%")
                else:
                    print("  ❌ No cap table data")
                
                # Check for issues
                issues = []
                if not company.get('product_description'):
                    issues.append("Missing product_description")
                if company.get('business_model') == 'SaaS' and company.get('vertical') == 'Unknown':
                    issues.append("Generic SaaS categorization (not specific)")
                if tam == 210_000_000_000:
                    issues.append("Using hardcoded $210B TAM")
                if gpu_cost_ratio == 3.6:
                    issues.append("Using hardcoded 360% GPU ratio")
                if valuation == 0 or revenue == 0:
                    issues.append("Zero valuation or revenue")
                    
                if issues:
                    print("\n⚠️ ISSUES FOUND:")
                    for issue in issues:
                        print(f"  - {issue}")
                else:
                    print("\n✅ All checks passed!")
        
        # Check chart data
        if 'charts' in result:
            print("\n\n📊 CHART DATA CHECK:")
            print("-" * 40)
            for chart in result['charts']:
                chart_type = chart.get('type', 'Unknown')
                title = chart.get('title', 'Untitled')
                print(f"\nChart: {title} (Type: {chart_type})")
                
                if chart_type == 'side_by_side_sankey':
                    print("  ✅ Cap table Sankey diagram configured")
                    if 'data' in chart:
                        for side in ['left', 'right']:
                            if side in chart['data']:
                                nodes = len(chart['data'][side].get('nodes', []))
                                links = len(chart['data'][side].get('links', []))
                                print(f"    - {side}: {nodes} nodes, {links} links")
                elif 'data' in chart:
                    data_points = len(chart.get('data', []))
                    print(f"  Data points: {data_points}")
                    if data_points > 0 and isinstance(chart['data'][0], (int, float)):
                        print(f"  First value: {chart['data'][0]:,.2f}")
        
        print("\n" + "="*80)
        print("TEST COMPLETE")
        print("="*80)
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        
if __name__ == "__main__":
    asyncio.run(test_data_pipeline())