#!/usr/bin/env python3
"""
Test semantic extraction is working properly
"""

import asyncio
import json
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent))

from app.services.unified_mcp_orchestrator import UnifiedMCPOrchestrator

async def test_semantic():
    orchestrator = UnifiedMCPOrchestrator()
    
    # Test with companies that have specific business models
    result = await orchestrator.process_request(
        prompt="Analyze @Perplexity and @Cursor for investment",
        output_format="analysis",
        context={}
    )
    
    print("\n" + "="*60)
    print("SEMANTIC EXTRACTION TEST RESULTS")
    print("="*60 + "\n")
    
    if 'companies' in result:
        for company in result['companies']:
            name = company.get('company', 'Unknown')
            print(f"\n📊 {name}")
            print("-" * 40)
            
            # Check semantic fields
            print(f"Business Model: {company.get('business_model', 'MISSING')}")
            print(f"Sector: {company.get('sector', 'MISSING')}")
            print(f"Product Description: {company.get('product_description', 'MISSING')}")
            print(f"Who They Sell To: {company.get('who_they_sell_to', 'MISSING')}")
            print(f"How They Grow: {company.get('how_they_grow', 'MISSING')}")
            
            # Check TAM and GPU calculations
            print(f"\n💰 Economics:")
            print(f"TAM: ${company.get('tam', 0):,.0f}")
            print(f"Labor TAM: ${company.get('labor_tam', 0):,.0f}")
            print(f"GPU Cost Ratio: {company.get('gpu_cost_ratio', 0):.1%}")
            print(f"Labor Roles Replaced: {company.get('labor_roles_replaced', 'N/A')}")
            
            # Check valuations
            val = company.get('valuation', 0)
            if hasattr(val, 'value'):
                val = val.value
            rev = company.get('revenue', 0) or company.get('inferred_revenue', 0)
            if hasattr(rev, 'value'):
                rev = rev.value
                
            print(f"\n📈 Financials:")
            print(f"Valuation: ${val:,.0f}")
            print(f"Revenue: ${rev:,.0f}")
            
            # Check for issues
            issues = []
            if company.get('business_model') == 'SaaS':
                issues.append("Generic 'SaaS' categorization")
            if company.get('sector') == 'Unknown':
                issues.append("Unknown sector")
            if not company.get('product_description'):
                issues.append("Missing product_description")
            if company.get('tam') == 210_000_000_000:
                issues.append("Using hardcoded $210B TAM")
                
            if issues:
                print(f"\n⚠️ Issues: {', '.join(issues)}")
            else:
                print(f"\n✅ All semantic fields extracted!")
    
    # Check chart data
    if 'charts' in result:
        print("\n\n📊 Charts Generated:")
        for chart in result.get('charts', []):
            if chart.get('type') == 'side_by_side_sankey':
                print(f"✅ Cap Table Sankey Diagram")
    
if __name__ == "__main__":
    asyncio.run(test_semantic())