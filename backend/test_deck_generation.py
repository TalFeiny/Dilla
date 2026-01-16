#!/usr/bin/env python3
"""Test deck generation with new slides"""

import asyncio
import json
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

from app.services.unified_mcp_orchestrator import UnifiedMCPOrchestrator

async def test_deck_generation():
    """Test the deck generation with Path to $100M ARR and Business Analysis slides"""
    
    # Initialize the orchestrator
    orchestrator = UnifiedMCPOrchestrator()
    
    # Test prompt requesting deck format
    prompt = "Compare @Mercury and @Deel for investment with deck format"
    
    print(f"Testing deck generation with prompt: {prompt}")
    print("-" * 50)
    
    try:
        # Process the request
        result = await orchestrator.process_request(
            prompt=prompt,
            output_format="deck",
            context={}
        )
        
        # Check if deck was generated
        if result.get("success") and result.get("results", {}).get("format") == "deck":
            slides = result["results"].get("slides", [])
            print(f"✅ Generated {len(slides)} slides")
            
            # Check for specific slide types
            slide_types = [s.get("type") for s in slides]
            
            # Check for our new slide types
            has_path_to_100m = any("path_to_100m" in t for t in slide_types)
            has_business_analysis = any("business_analysis" in t for t in slide_types)
            has_cap_table = any("cap_table" in t for t in slide_types)
            
            print(f"\nSlide Types Found:")
            for i, slide in enumerate(slides, 1):
                slide_type = slide.get("type", "unknown")
                title = slide.get("content", {}).get("title", "No title")
                print(f"  Slide {i}: {slide_type} - {title}")
            
            print(f"\n✅ Path to $100M ARR slide: {'Found' if has_path_to_100m else 'MISSING'}")
            print(f"✅ Business Analysis slide: {'Found' if has_business_analysis else 'MISSING'}")
            print(f"✅ Cap Table slide: {'Found' if has_cap_table else 'MISSING'}")
            
            # Look at a specific slide in detail
            for slide in slides:
                if slide.get("type") == "path_to_100m":
                    print(f"\n📊 Path to $100M ARR Details:")
                    content = slide.get("content", {})
                    print(f"  Current ARR: ${content.get('current_arr', 0):,.0f}")
                    print(f"  Years to $100M: {content.get('years_to_target', 'N/A')}")
                    print(f"  Growth Rate: {content.get('growth_rate', 'N/A')}")
                    print(f"  Milestones: {content.get('milestones', [])}")
                    break
            
            # Check for charts
            charts = result["results"].get("charts", [])
            print(f"\n📈 Charts: {len(charts)} generated")
            
            # Save output for inspection
            with open("test_deck_output.json", "w") as f:
                # Convert dataclasses and datetime to dicts for JSON serialization
                import dataclasses
                from datetime import datetime, date
                
                def convert_to_dict(obj):
                    if dataclasses.is_dataclass(obj):
                        return dataclasses.asdict(obj)
                    elif isinstance(obj, (datetime, date)):
                        return obj.isoformat()
                    elif isinstance(obj, dict):
                        return {k: convert_to_dict(v) for k, v in obj.items()}
                    elif isinstance(obj, list):
                        return [convert_to_dict(item) for item in obj]
                    else:
                        return obj
                
                serializable_results = convert_to_dict(result["results"])
                json.dump(serializable_results, f, indent=2)
            print(f"\n💾 Full deck saved to test_deck_output.json")
            
            return True
            
        else:
            format_result = result.get("results", {}).get("format") if result.get("success") else None
            print(f"❌ Deck generation failed - got format: {format_result}")
            print(f"Error: {result.get('error', 'Unknown error')}")
            return False
            
    except Exception as e:
        print(f"❌ Error during deck generation: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(test_deck_generation())
    exit(0 if success else 1)