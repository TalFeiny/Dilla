#!/usr/bin/env python3
"""
Test script to verify data flow fixes in UnifiedMCPOrchestrator
Tests that companies with incomplete data get properly enriched with inferred values
"""

import asyncio
import json
from app.services.unified_mcp_orchestrator import UnifiedMCPOrchestrator

async def test_data_flow_with_incomplete_data():
    """Test that incomplete company data gets enriched properly"""
    
    print("\n" + "="*80)
    print("TESTING DATA FLOW WITH INCOMPLETE COMPANY DATA")
    print("="*80)
    
    # Initialize orchestrator
    orchestrator = UnifiedMCPOrchestrator()
    
    # Create test companies with MISSING DATA
    test_companies = [
        {
            "company": "TestCorp A",
            "stage": "Series B",
            "business_model": "Enterprise SaaS for supply chain optimization",
            "sector": "Supply Chain Tech",
            "total_funding": 45_000_000,
            "funding_rounds": [
                {"round": "Seed", "amount": 2_000_000, "date": "2021-03"},
                {"round": "Series A", "amount": 12_000_000, "date": "2022-06"},
                {"round": "Series B", "amount": 31_000_000, "date": "2023-09"}
            ],
            # MISSING: revenue, valuation, team_size, growth_rate
            "geography": "San Francisco",
            "is_yc": False,
            "founders": ["Alice Smith", "Bob Johnson"]
        },
        {
            "company": "DataFlow Inc",
            "stage": "Series A", 
            "business_model": "Real-time data analytics platform",
            "sector": "Data Infrastructure",
            "revenue": 3_500_000,  # Has revenue
            # MISSING: valuation, total_funding, team_size
            "funding_rounds": [
                {"round": "Seed", "amount": 3_000_000, "date": "2022-01"},
                {"round": "Series A", "amount": 15_000_000, "date": "2023-06"}
            ],
            "geography": "New York",
            "is_yc": True,
            "founders": ["Charlie Davis"]
        }
    ]
    
    print("\nTest Companies Created:")
    print(f"1. {test_companies[0]['company']} - Missing: revenue, valuation, team_size")
    print(f"2. {test_companies[1]['company']} - Missing: valuation, total_funding, team_size")
    
    # Test the enrichment process
    print("\n" + "-"*60)
    print("TESTING INFERENCE ENRICHMENT...")
    print("-"*60)
    
    enriched = await orchestrator._ensure_companies_have_inferred_data(test_companies.copy())
    
    # Check enrichment results
    for i, company in enumerate(enriched):
        print(f"\n{company['company']}:")
        print(f"  Revenue: {company.get('revenue')} -> Inferred: {company.get('inferred_revenue')}")
        print(f"  Valuation: {company.get('valuation')} -> Inferred: {company.get('inferred_valuation')}")
        print(f"  Team Size: {company.get('team_size')} -> Inferred: {company.get('inferred_team_size')}")
        print(f"  Growth Rate: {company.get('growth_rate')} -> Inferred: {company.get('inferred_growth_rate')}")
        
        # Verify critical fields exist
        assert company.get('inferred_revenue') is not None, f"Missing inferred_revenue for {company['company']}"
        assert company.get('inferred_valuation') is not None, f"Missing inferred_valuation for {company['company']}"
        print(f"  ✓ All critical inferred fields present")
    
    # Test deck generation with incomplete data
    print("\n" + "-"*60)
    print("TESTING DECK GENERATION WITH ENRICHED DATA...")
    print("-"*60)
    
    deck_input = {
        "skill": "deck-storytelling",
        "companies": enriched,  # Use enriched companies
        "fund_context": {
            "fund_size": 260_000_000,
            "focus": "Enterprise SaaS, Series A-C",
            "check_size_range": [5_000_000, 25_000_000]
        }
    }
    
    # Execute deck generation
    result = await orchestrator.process_request(deck_input)
    
    # Check deck generation results
    if result.get('success'):
        slides = result.get('slides', [])
        print(f"\n✓ Deck generated successfully with {len(slides)} slides")
        
        # Check specific slides for data presence
        slide_checks = {
            "Executive Summary": False,
            "Company Overview": False,
            "Path to $100M": False,
            "Business Analysis": False,
            "Cap Table": False,
            "PWERM": False
        }
        
        for slide in slides:
            title = slide.get('title', '')
            for check_title in slide_checks:
                if check_title.lower() in title.lower():
                    slide_checks[check_title] = True
                    
                    # Check for data in slide
                    if 'chart' in slide or 'chart_data' in slide:
                        print(f"  ✓ {check_title}: Has chart data")
                    elif 'companies' in slide:
                        print(f"  ✓ {check_title}: Has company data")
                    elif 'content' in slide:
                        print(f"  ✓ {check_title}: Has content")
                    break
        
        # Print slide summary
        print("\nSlide Coverage:")
        for title, found in slide_checks.items():
            status = "✓" if found else "✗"
            print(f"  {status} {title}")
        
        # Check that critical data flows through
        print("\nData Flow Verification:")
        
        # Check executive summary has revenue data
        exec_summary = next((s for s in slides if 'executive' in s.get('title', '').lower()), None)
        if exec_summary:
            content = str(exec_summary.get('content', ''))
            has_revenue = any(word in content.lower() for word in ['revenue', '$', 'million'])
            print(f"  {'✓' if has_revenue else '✗'} Executive Summary has financial data")
        
        # Check path to 100M has projections
        path_slide = next((s for s in slides if '100m' in s.get('title', '').lower()), None)
        if path_slide:
            chart_data = path_slide.get('chart_data') or path_slide.get('chart')
            has_data = bool(chart_data and chart_data.get('data'))
            print(f"  {'✓' if has_data else '✗'} Path to $100M has projection data")
        
        # Check cap table has ownership data
        cap_slide = next((s for s in slides if 'cap table' in s.get('title', '').lower()), None)
        if cap_slide:
            chart_data = cap_slide.get('chart_data') or cap_slide.get('chart')
            has_data = bool(chart_data)
            print(f"  {'✓' if has_data else '✗'} Cap Table has ownership data")
            
    else:
        print(f"\n✗ Deck generation failed: {result.get('error', 'Unknown error')}")
    
    print("\n" + "="*80)
    print("TEST COMPLETE")
    print("="*80)
    
    return result

if __name__ == "__main__":
    result = asyncio.run(test_data_flow_with_incomplete_data())
    
    # Save result for inspection
    with open("test_data_flow_result.json", "w") as f:
        json.dump(result, f, indent=2, default=str)
    
    print("\nFull result saved to test_data_flow_result.json")