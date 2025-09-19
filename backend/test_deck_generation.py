#!/usr/bin/env python3
"""Test deck generation with real skills execution"""

import asyncio
import json
from app.services.unified_mcp_orchestrator import get_unified_orchestrator

async def test_deck_generation():
    """Test deck generation with valuation and cap table"""
    orchestrator = get_unified_orchestrator()
    
    # Test prompt for deck generation
    prompt = "Create a pitch deck comparing @Deel and @Ramp with valuation analysis"
    
    print(f"Testing prompt: {prompt}")
    print("-" * 50)
    
    try:
        # Clear cache for fresh results
        orchestrator._tavily_cache.clear()
        
        # Process request with deck format
        result = await orchestrator.process_request(
            prompt=prompt,
            output_format='deck',
            context={
                'deckType': 'pitch',
                'includeValuation': True,
                'includeCapTable': True
            }
        )
        
        # Check the nested structure - slides should be in results
        actual_result = result.get('results', result)
        
        # Check if we have slides
        if 'slides' in actual_result:
            print(f"✅ Generated {len(actual_result['slides'])} slides")
            
            # Check for specific slide types
            slide_types = set()
            for slide in actual_result['slides']:
                template = slide.get('template', 'unknown')
                slide_types.add(template)
                if template == 'valuation':
                    print(f"  ✅ Found valuation slide: {slide['content']['title']}")
                elif template == 'cap_table':
                    print(f"  ✅ Found cap table slide: {slide['content']['title']}")
                elif template == 'waterfall':
                    print(f"  ✅ Found waterfall slide: {slide['content']['title']}")
            
            print(f"\nSlide types found: {slide_types}")
            
            # Check skills used
            if 'metadata' in result and 'skills_used' in result['metadata']:
                print(f"\nSkills executed: {result['metadata']['skills_used']}")
            
            # Check for valuation data
            if 'valuation' in result:
                print(f"\n✅ Valuation data included")
                if 'pwerm_valuation' in result['valuation']:
                    print(f"  - PWERM: ${result['valuation']['pwerm_valuation']/1e6:.1f}M")
                if 'dcf_valuation' in result['valuation']:
                    print(f"  - DCF: ${result['valuation']['dcf_valuation']/1e6:.1f}M")
            
            # Save result for inspection
            with open('deck_test_result.json', 'w') as f:
                json.dump(result, f, indent=2, default=str)
            print("\n✅ Full result saved to deck_test_result.json")
            
        else:
            print("❌ No slides in result")
            print(f"Result keys: {result.keys()}")
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_deck_generation())