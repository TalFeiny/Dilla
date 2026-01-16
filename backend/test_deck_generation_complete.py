#!/usr/bin/env python3
"""
Test the complete deck generation with all fixes
"""

import asyncio
import json
from datetime import datetime
from app.services.unified_mcp_orchestrator import UnifiedMCPOrchestrator

async def test_deck_generation():
    """Test deck generation with sample companies"""
    
    # Initialize orchestrator
    orchestrator = UnifiedMCPOrchestrator()
    
    # Sample company data (simulating what would come from search)
    test_companies = [
        {
            "company": "Mercury",
            "stage": "Series B",
            "valuation": 1_600_000_000,
            "revenue": 40_000_000,
            "arr": 40_000_000,
            "total_funding": 163_000_000,
            "team_size": 400,
            "founded_year": 2017,
            "business_model": "Banking platform for startups",
            "sector": "Fintech",
            "geography": "San Francisco",
            "website_url": "https://mercury.com",
            "investors": ["Andreessen Horowitz", "CRV", "Coatue"],
            "tam": 50_000_000_000,
            "sam": 5_000_000_000,
            "som": 500_000_000,
            "gross_margin": 75,
            "growth_rate": 150,
            "customer_type": "B2B",
            "pricing_model": "Subscription + Transaction fees",
            "target_customers": "Startups and SMBs",
            "funding_rounds": [
                {"round_name": "Seed", "amount": 6_000_000, "valuation": 20_000_000},
                {"round_name": "Series A", "amount": 20_000_000, "valuation": 100_000_000},
                {"round_name": "Series B", "amount": 120_000_000, "valuation": 1_600_000_000}
            ]
        },
        {
            "company": "Brex",
            "stage": "Series D",
            "valuation": 12_300_000_000,
            "revenue": 400_000_000,
            "arr": 400_000_000,
            "total_funding": 1_500_000_000,
            "team_size": 1100,
            "founded_year": 2017,
            "business_model": "Corporate cards and spend management",
            "sector": "Fintech",
            "geography": "San Francisco",
            "website_url": "https://brex.com",
            "investors": ["Y Combinator", "DST Global", "Tiger Global"],
            "tam": 100_000_000_000,
            "sam": 10_000_000_000,
            "som": 1_000_000_000,
            "gross_margin": 70,
            "growth_rate": 100,
            "customer_type": "B2B",
            "pricing_model": "Subscription + Interchange",
            "target_customers": "Startups and enterprises",
            "funding_rounds": [
                {"round_name": "Seed", "amount": 7_000_000, "valuation": 30_000_000},
                {"round_name": "Series A", "amount": 50_000_000, "valuation": 250_000_000},
                {"round_name": "Series B", "amount": 100_000_000, "valuation": 1_100_000_000},
                {"round_name": "Series C", "amount": 260_000_000, "valuation": 2_600_000_000},
                {"round_name": "Series D", "amount": 425_000_000, "valuation": 12_300_000_000}
            ]
        }
    ]
    
    # Store companies in shared data
    orchestrator.shared_data["companies"] = test_companies
    
    # Generate deck
    print("Generating deck...")
    result = await orchestrator._execute_deck_generation({})
    
    # Analyze results
    print(f"\n✅ Deck generated successfully!")
    print(f"Total slides: {result.get('slide_count', 0)}")
    print(f"\nSlides generated:")
    
    slide_types_expected = [
        "title",
        "summary",
        "company_comparison",
        "path_to_100m_comparison",
        "business_analysis_comparison",
        "comparison",
        "tam_pincer",
        "cap_table",  # Individual cap tables
        "cap_table_comparison",  # Side-by-side Sankey
        "exit_scenarios",
        "investment_recommendations"
    ]
    
    slides_found = {}
    for i, slide in enumerate(result.get('slides', [])):
        slide_type = slide.get('type', 'unknown')
        if slide_type not in slides_found:
            slides_found[slide_type] = []
        slides_found[slide_type].append(i + 1)
        
        # Check for specific content
        content = slide.get('content', {})
        print(f"  {i+1}. {slide_type}: {content.get('title', 'No title')}")
        
        # Verify Path to $100M insights don't have f-string errors
        if slide_type == 'path_to_100m_comparison':
            insights = content.get('insights', [])
            print(f"     - Insights: {len(insights)} items")
            for insight in insights:
                if insight and '{' in str(insight):
                    print(f"     ⚠️  WARNING: Possible f-string error in insight: {insight}")
        
        # Check cap table Sankey data
        if slide_type == 'cap_table_comparison':
            if 'company1_data' in content:
                sankey1 = content.get('company1_data', {})
                sankey2 = content.get('company2_data', {})
                print(f"     - Company 1 Sankey: {len(sankey1.get('nodes', []))} nodes, {len(sankey1.get('links', []))} links")
                print(f"     - Company 2 Sankey: {len(sankey2.get('nodes', []))} nodes, {len(sankey2.get('links', []))} links")
            elif content.get('chart_type') == 'side_by_side_sankey':
                print(f"     - Chart type: side_by_side_sankey ✓")
    
    print(f"\n📊 Slide Type Analysis:")
    for expected_type in slide_types_expected:
        if expected_type in slides_found:
            print(f"  ✅ {expected_type}: Found at position(s) {slides_found[expected_type]}")
        else:
            print(f"  ❌ {expected_type}: MISSING!")
    
    # Check for charts
    charts = result.get('charts', [])
    print(f"\n📈 Charts: {len(charts)} total")
    for chart in charts:
        print(f"  - {chart.get('type', 'unknown')}: {chart.get('title', 'No title')}")
    
    # Save output for inspection
    with open('deck_generation_test_output.json', 'w') as f:
        json.dump(result, f, indent=2, default=str)
    print(f"\n💾 Full output saved to deck_generation_test_output.json")
    
    return result

if __name__ == "__main__":
    result = asyncio.run(test_deck_generation())
    
    # Final summary
    if result.get('error'):
        print(f"\n❌ Error in deck generation: {result['error']}")
    else:
        print(f"\n✅ Deck generation completed successfully!")
        print(f"   - {result.get('slide_count', 0)} slides generated")
        print(f"   - {len(result.get('charts', []))} charts included")