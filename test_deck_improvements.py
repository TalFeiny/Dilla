#!/usr/bin/env python3
"""
Test script for deck generation improvements
Tests all the fixes made based on feedback
"""

import asyncio
import json
import os
import sys

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))

from app.services.unified_mcp_orchestrator import UnifiedMCPOrchestrator
from app.services.intelligent_gap_filler import IntelligentGapFiller

async def test_deck_generation():
    """Test the improved deck generation"""
    
    print("Testing Deck Generation Improvements")
    print("=" * 50)
    
    # Initialize orchestrator
    orchestrator = UnifiedMCPOrchestrator()
    
    # Test request with two companies - simple prompt format
    request = {
        "prompt": "analyze @Mercury and @Deel",
        "output_format": "deck",
        "context": {}
    }
    
    print("\n1. Testing Company Analysis...")
    result = await orchestrator.process_request(request)
    
    if "error" in result:
        print(f"❌ Error: {result['error']}")
        return
    
    # Check companies data
    companies = result.get("final_data", {}).get("companies", [])
    print(f"✅ Found {len(companies)} companies")
    
    # Verify team size fixes
    print("\n2. Checking Team Size Inference...")
    for company in companies:
        team_size = company.get("team_size", 0)
        stage = company.get("stage", "Unknown")
        print(f"  - {company.get('company')}: {team_size} employees ({stage})")
        
        # Verify caps are applied
        if "Seed" in stage and team_size > 35:
            print(f"    ⚠️ Warning: Seed company has {team_size} employees (cap should be 35)")
        elif "Series A" in stage and team_size > 120:
            print(f"    ⚠️ Warning: Series A company has {team_size} employees (cap should be 120)")
        elif "Series B" in stage and team_size > 350:
            print(f"    ⚠️ Warning: Series B company has {team_size} employees (cap should be 350)")
        else:
            print(f"    ✅ Team size within expected range")
    
    # Check deck slides
    print("\n3. Verifying Deck Structure...")
    deck = result.get("deck", {})
    slides = deck.get("slides", [])
    
    slide_types = [slide.get("type") for slide in slides]
    print(f"Total slides: {len(slides)}")
    print(f"Slide types: {slide_types}")
    
    # Check for required slides
    required_slides = [
        "title",
        "summary", 
        "company_comparison",
        "path_to_100m_comparison",
        "business_analysis_comparison",
        "tam_pincer",
        "cap_table",
        "cap_table_comparison",
        "exit_scenarios",
        "investment_recommendations"
    ]
    
    print("\n4. Checking Required Slides...")
    for slide_type in required_slides:
        if slide_type in slide_types:
            print(f"  ✅ {slide_type}")
            
            # Additional checks for specific slides
            if slide_type == "summary":
                summary_slide = next(s for s in slides if s["type"] == "summary")
                bullets = summary_slide.get("content", {}).get("bullets", [])
                if any("avg" in b.lower() or "combined" in b.lower() for b in bullets):
                    print(f"    ⚠️ Warning: Summary still contains avg/combined metrics")
                else:
                    print(f"    ✅ Summary has meaningful metrics")
            
            elif slide_type == "company_comparison":
                comp_slide = next(s for s in slides if s["type"] == "company_comparison")
                companies_data = comp_slide.get("content", {}).get("companies", [])
                for comp in companies_data:
                    metrics = comp.get("metrics", {})
                    if "Revenue" in metrics and "Valuation" in metrics:
                        print(f"    ✅ {comp['name']}: Revenue and Valuation on same slide")
                    if "Revenue Multiple" in metrics:
                        print(f"    ✅ {comp['name']}: Revenue multiple calculated")
                    if "Capital Efficiency" in metrics:
                        print(f"    ✅ {comp['name']}: Capital efficiency calculated")
            
            elif slide_type == "path_to_100m_comparison":
                path_slide = next(s for s in slides if s["type"] == "path_to_100m_comparison")
                chart_data = path_slide.get("content", {}).get("chart_data", {})
                options = chart_data.get("options", {})
                y_ticks = options.get("scales", {}).get("y", {}).get("ticks", {})
                if "callback" in y_ticks and "$" in str(y_ticks["callback"]) and "M" in str(y_ticks["callback"]):
                    print(f"    ✅ Y-axis formatted in millions")
                labels = chart_data.get("data", {}).get("labels", [])
                if len(labels) == 6:  # Reduced from 8
                    print(f"    ✅ Timeline reduced to 6 years for better visibility")
        else:
            print(f"  ❌ Missing: {slide_type}")
    
    # Check for removed/fixed issues
    print("\n5. Verifying Fixes...")
    
    # Check executive summary doesn't have avg/combined valuation
    summary_slides = [s for s in slides if s["type"] == "summary"]
    if summary_slides:
        summary = summary_slides[0]
        bullets = summary.get("content", {}).get("bullets", [])
        has_avg = any("average" in str(b).lower() or "combined" in str(b).lower() for b in bullets)
        if not has_avg:
            print("  ✅ Executive summary fixed (no avg/combined valuations)")
        else:
            print("  ❌ Executive summary still has avg/combined valuations")
    
    # Check cap table format
    cap_table_slides = [s for s in slides if "cap_table" in s["type"]]
    for slide in cap_table_slides:
        chart_data = slide.get("content", {}).get("chart_data", {})
        chart_type = slide.get("content", {}).get("chart_type")
        if chart_type == "side_by_side_sankey":
            print("  ✅ Cap table using Sankey diagram")
        elif chart_data.get("type") == "waterfall":
            print("  ✅ Individual cap table using waterfall chart")
    
    print("\n" + "=" * 50)
    print("Deck Generation Test Complete!")
    
    # Save result for inspection
    with open("test_deck_output.json", "w") as f:
        json.dump(result, f, indent=2, default=str)
    print(f"\nFull result saved to test_deck_output.json")

if __name__ == "__main__":
    asyncio.run(test_deck_generation())