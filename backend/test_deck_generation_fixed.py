#!/usr/bin/env python3
"""
Test deck generation with the fixes applied
"""
import asyncio
import json
from app.services.unified_mcp_orchestrator import UnifiedMCPOrchestrator

async def test_deck_generation():
    """Test deck generation with Mercury and Deel"""
    
    # Initialize orchestrator
    orchestrator = UnifiedMCPOrchestrator()
    
    # Test parameters
    prompt = "Compare @Mercury and @Deel for investment"
    output_format = "deck"
    context = {
        "fund_size": 260_000_000,
        "typical_check": 10_000_000,
        "stage_focus": ["Series A", "Series B"]
    }
    
    # Process request
    result = await orchestrator.process_request(
        prompt=prompt,
        output_format=output_format,
        context=context
    )
    
    # Check results
    print("\n=== DECK GENERATION TEST ===\n")
    
    if result.get("success"):
        slides = result.get("slides", [])
        print(f"✓ Generated {len(slides)} slides")
        
        # Check each slide type
        slide_types = [s.get("type") for s in slides]
        print("\nSlides generated:")
        for i, slide in enumerate(slides, 1):
            slide_type = slide.get("type")
            title = slide.get("content", {}).get("title", "")
            print(f"  {i}. {slide_type}: {title}")
            
            # Check for specific issues from feedback
            if slide_type == "summary":
                bullets = slide.get("content", {}).get("bullets", [])
                if any("avg" in b.lower() or "combined valuation" in b.lower() for b in bullets):
                    print("    ❌ WARNING: Contains 'avg/combined valuation' - should be removed")
            
            if slide_type == "company_comparison":
                print("    ✓ Companies combined on single slide")
            
            if slide_type == "path_to_100m_comparison":
                if slide.get("content", {}).get("chart_data"):
                    print("    ✓ Has chart data with proper formatting")
                if slide.get("content", {}).get("insights"):
                    print("    ✓ Has insights")
            
            if slide_type == "cap_table_comparison":
                company1 = slide.get("content", {}).get("company1", {})
                company2 = slide.get("content", {}).get("company2", {})
                
                # Check if ownership data is different for each company
                if company1 and company2:
                    c1_founders = company1.get("metrics", {}).get("Founder Ownership", "")
                    c2_founders = company2.get("metrics", {}).get("Founder Ownership", "")
                    if c1_founders == c2_founders:
                        print(f"    ❌ WARNING: Same ownership % for both companies ({c1_founders}) - likely hardcoded")
                    else:
                        print(f"    ✓ Different ownership: {c1_founders} vs {c2_founders}")
        
        # Check for required slides
        required_types = [
            "title", "summary", "company_comparison", "path_to_100m_comparison",
            "business_analysis_comparison", "tam_pincer", "cap_table", 
            "cap_table_comparison", "exit_scenarios", "investment_recommendations"
        ]
        
        missing = set(required_types) - set(slide_types)
        if missing:
            print(f"\n❌ Missing required slides: {missing}")
        else:
            print("\n✓ All required slides present")
        
        # Check companies data
        companies = result.get("companies", [])
        if companies:
            print(f"\n✓ {len(companies)} companies analyzed")
            for company in companies:
                name = company.get("company")
                revenue = company.get("revenue", 0)
                valuation = company.get("valuation", 0) 
                team_size = company.get("team_size", "Unknown")
                
                print(f"\n  {name}:")
                print(f"    Revenue: ${revenue/1_000_000:.1f}M")
                print(f"    Valuation: ${valuation/1_000_000:.0f}M")
                print(f"    Team Size: {team_size}")
                
                # Check for reasonable team size
                if isinstance(team_size, (int, float)) and team_size > 1000:
                    print(f"    ❌ WARNING: Team size {team_size} seems too high")
        
        # Save output for inspection
        with open("test_deck_output.json", "w") as f:
            json.dump(result, f, indent=2, default=str)
        print("\n✓ Full output saved to test_deck_output.json")
        
    else:
        print(f"❌ Deck generation failed: {result.get('error')}")
    
    print("\n=== TEST COMPLETE ===\n")

if __name__ == "__main__":
    asyncio.run(test_deck_generation())