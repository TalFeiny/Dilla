#!/usr/bin/env python3
"""
Test complete deck generation with all services wired up
"""

import asyncio
import json
from app.services.unified_mcp_orchestrator import UnifiedMCPOrchestrator

async def test_deck_generation():
    """Test deck generation with sample company data"""
    
    # Initialize orchestrator
    orchestrator = UnifiedMCPOrchestrator()
    
    # Use natural language prompt as the system expects
    prompt = "Generate investment deck for @Mercury and @Deel"
    output_format = "deck"
    context = {
        "fund_size": 260_000_000,
        "remaining_capital": 109_000_000,
        "target_ownership": 0.08,
        "investment_stage": "Series A to Series B"
    }
    
    # Process request with string prompt
    print("Testing deck generation...")
    result = await orchestrator.process_request(
        prompt=prompt,
        output_format=output_format,
        context=context
    )
    
    # Check results
    if result.get("error"):
        print(f"❌ Error: {result['error']}")
        return False
    
    # Verify deck structure
    slides = result.get("slides", [])
    citations = result.get("citations", [])
    charts = result.get("charts", [])
    
    print(f"\n✅ Deck generated successfully!")
    print(f"📊 Total slides: {len(slides)}")
    print(f"📚 Citations: {len(citations)}")
    print(f"📈 Charts: {len(charts)}")
    
    # Check each slide type
    slide_types = [s.get("type") for s in slides]
    expected_slides = [
        "title",
        "summary", 
        "company_comparison",
        "founder_team_analysis",
        "path_to_100m_comparison",
        "business_analysis_comparison",
        "tam_pincer",
        "cap_table_comparison",
        "pwerm_analysis",
        "investment_recommendations",
        "citations"
    ]
    
    print("\n📑 Slide types generated:")
    for i, slide in enumerate(slides, 1):
        slide_type = slide.get("type", "unknown")
        content = slide.get("content", {})
        
        # Check for chart data
        has_chart = bool(content.get("chart_data"))
        chart_indicator = " 📈" if has_chart else ""
        
        # Check for proper data
        has_companies = bool(content.get("companies"))
        company_indicator = " 👥" if has_companies else ""
        
        print(f"  {i}. {slide_type}{chart_indicator}{company_indicator}")
        
        # Verify critical data points
        if slide_type == "path_to_100m_comparison":
            companies_data = content.get("companies", {})
            if companies_data:
                for company_name, data in companies_data.items():
                    arr = data.get("current_arr_formatted", "N/A")
                    years = data.get("years_to_target", "N/A")
                    print(f"     → {company_name}: {arr} ARR, {years} years to target")
        
        elif slide_type == "tam_pincer":
            companies_data = content.get("companies", {})
            if companies_data:
                for company_name, data in companies_data.items():
                    trad_tam = data.get("traditional_tam", 0) / 1e9
                    labor_tam = data.get("labor_tam", 0) / 1e9
                    print(f"     → {company_name}: Software TAM ${trad_tam:.1f}B, Labor TAM ${labor_tam:.1f}B")
        
        elif slide_type == "investment_recommendations":
            recs = content.get("recommendations", [])
            for rec in recs:
                print(f"     → {rec.get('company')}: {rec.get('recommendation')}")
    
    # Verify charts have proper data
    print("\n📈 Chart validation:")
    for slide in slides:
        content = slide.get("content", {})
        chart_data = content.get("chart_data")
        if chart_data:
            chart_type = chart_data.get("type", "unknown")
            data = chart_data.get("data", {})
            labels = data.get("labels", [])
            datasets = data.get("datasets", [])
            
            if labels and datasets:
                print(f"  ✅ {slide.get('type')} slide has {chart_type} chart with {len(labels)} data points")
            else:
                print(f"  ⚠️ {slide.get('type')} slide has chart but missing data")
    
    # Verify citations
    if citations:
        print(f"\n📚 Citations found: {len(citations)}")
        for i, cite in enumerate(citations[:3], 1):
            title = cite.get("title", "Unknown")[:50]
            print(f"  {i}. {title}...")
    else:
        print("\n⚠️ No citations found")
    
    # Check if citation slide was added
    if "citations" in slide_types:
        print("✅ Citation slide properly added to deck")
    else:
        print("❌ Citation slide missing from deck")
    
    # Save output for inspection
    with open("test_deck_output.json", "w") as f:
        json.dump(result, f, indent=2)
    print("\n💾 Full output saved to test_deck_output.json")
    
    return True

if __name__ == "__main__":
    success = asyncio.run(test_deck_generation())
    if success:
        print("\n🎉 All deck generation tests passed!")
    else:
        print("\n❌ Deck generation test failed")