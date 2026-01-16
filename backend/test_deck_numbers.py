#!/usr/bin/env python3
"""Test script to verify deck number formatting fixes"""

import asyncio
import json
from app.services.unified_mcp_orchestrator import UnifiedMCPOrchestrator

async def test_deck_generation():
    """Test deck generation with proper number formatting"""
    
    orchestrator = UnifiedMCPOrchestrator()
    
    # Test request for Tavily and Lago
    request = {
        "prompt": "Analyze @Tavily and @Lago for investment",
        "output_format": "deck",
        "context": {
            "fund_stage": "seed",
            "check_size_range": [500000, 2000000],
            "ownership_target": 0.10
        }
    }
    
    print("Testing deck generation with @Tavily and @Lago...")
    print("-" * 50)
    
    try:
        result = await orchestrator.process_request(request)
        
        # Check if slides were generated
        if "slides" in result:
            print(f"✓ Generated {len(result['slides'])} slides")
            
            # Check each slide for proper formatting
            for i, slide in enumerate(result['slides']):
                slide_type = slide.get('type', 'unknown')
                print(f"\nSlide {i+1}: {slide_type}")
                
                # Check Executive Summary
                if slide_type == 'title' and 'content' in slide:
                    content = slide['content']
                    if 'bullets' in content:
                        print("  Executive Summary bullets:")
                        for bullet in content['bullets'][:3]:
                            print(f"    - {bullet}")
                
                # Check company comparison
                if slide_type == 'company_comparison' and 'content' in slide:
                    content = slide['content']
                    if 'companies' in content:
                        for company in content['companies']:
                            print(f"  Company: {company.get('name', 'Unknown')}")
                            if 'metrics' in company:
                                for key, value in company['metrics'].items():
                                    print(f"    {key}: {value}")
                
                # Check investment thesis
                if slide_type == 'investment_comparison' and 'content' in slide:
                    content = slide['content']
                    if 'chart_data' in content and 'data' in content['chart_data']:
                        chart_data = content['chart_data']['data']
                        print(f"  Radar chart labels: {chart_data.get('labels', [])}")
                        for dataset in chart_data.get('datasets', []):
                            print(f"  {dataset.get('label', 'Unknown')}: {dataset.get('data', [])}")
                
                # Check for gibberish numbers
                slide_str = json.dumps(slide)
                if "100000000" in slide_str or "1000000000" in slide_str:
                    print("  ⚠️ WARNING: Found unformatted large numbers!")
                elif "$100M" in slide_str or "$1B" in slide_str or "$10M" in slide_str:
                    print("  ✓ Numbers properly formatted")
        
        else:
            print("✗ No slides generated")
            
        # Check for specific issues mentioned
        print("\n" + "=" * 50)
        print("Checking for reported issues:")
        print("-" * 50)
        
        # Check if valuations are correct
        companies = result.get('data', {}).get('companies', [])
        for company in companies:
            name = company.get('company', 'Unknown')
            valuation = company.get('valuation') or company.get('inferred_valuation')
            print(f"{name} valuation: {valuation}")
        
        return result
        
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == "__main__":
    result = asyncio.run(test_deck_generation())
    
    if result:
        print("\n" + "=" * 50)
        print("Test completed. Check output above for issues.")
        
        # Save result for inspection
        with open("test_deck_output.json", "w") as f:
            json.dump(result, f, indent=2, default=str)
        print("Full output saved to test_deck_output.json")