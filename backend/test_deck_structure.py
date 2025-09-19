#!/usr/bin/env python3
"""Test deck generation and verify slide structure"""

import asyncio
import json
from app.services.unified_mcp_orchestrator import get_unified_orchestrator

async def test_deck_structure():
    """Test deck generation and print the actual structure"""
    orchestrator = get_unified_orchestrator()
    
    # Test prompt for deck generation
    prompt = "Create a pitch deck comparing @Deel and @Ramp with valuation analysis and cap table"
    
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
        
        # Print the structure
        print("\n=== RESULT STRUCTURE ===")
        print(f"Top-level keys: {list(result.keys())}")
        
        # Check for slides at different levels
        if 'slides' in result:
            print(f"✅ Found slides at top level: {len(result['slides'])} slides")
            print("\nSlide templates found:")
            for i, slide in enumerate(result['slides'][:3]):
                print(f"  Slide {i+1}: {slide.get('template', 'unknown')} - {slide.get('content', {}).get('title', 'No title')}")
        
        if 'results' in result:
            print(f"\nresults keys: {list(result['results'].keys())}")
            if 'slides' in result['results']:
                print(f"✅ Found slides in results: {len(result['results']['slides'])} slides")
            
            # Check for data from skills
            if 'data' in result['results']:
                print(f"\ndata keys (skills): {list(result['results']['data'].keys())}")
                
                # Check for valuation engine
                if 'valuation-engine' in result['results']['data']:
                    val_data = result['results']['data']['valuation-engine']
                    print("\n📊 Valuation Engine Data:")
                    print(f"  Keys: {list(val_data.keys())[:10]}")  # First 10 keys
                    
                    if 'cap_table' in val_data:
                        print(f"  ✅ Cap table found with keys: {list(val_data['cap_table'].keys())}")
                        if 'rounds' in val_data['cap_table']:
                            print(f"    - {len(val_data['cap_table']['rounds'])} funding rounds")
                        if 'current_ownership' in val_data['cap_table']:
                            print(f"    - Current ownership data available")
                    
                    if 'pwerm_valuation' in val_data:
                        print(f"  ✅ PWERM valuation: ${val_data['pwerm_valuation']/1e6:.1f}M")
                
                # Check for deck storytelling
                if 'deck-storytelling' in result['results']['data']:
                    deck_data = result['results']['data']['deck-storytelling']
                    print("\n📝 Deck Storytelling Data:")
                    print(f"  Keys: {list(deck_data.keys())}")
                    
                    if 'deck_content' in deck_data:
                        deck_content = deck_data['deck_content']
                        print(f"  Deck content keys: {list(deck_content.keys())}")
                        
                        if 'narrative' in deck_content:
                            print(f"  ✅ Narrative with {len(deck_content['narrative'])} sections")
        
        # Check format field
        if 'format' in result:
            print(f"\nFormat: {result['format']}")
        
        # Save the full result for inspection
        with open('deck_structure_test.json', 'w') as f:
            json.dump(result, f, indent=2, default=str)
        print("\n✅ Full result saved to deck_structure_test.json")
        
        # Print cap table if found
        print("\n=== CAP TABLE DATA ===")
        if 'results' in result and 'data' in result['results']:
            if 'valuation-engine' in result['results']['data']:
                val_data = result['results']['data']['valuation-engine']
                if 'cap_table' in val_data:
                    cap_table = val_data['cap_table']
                    
                    # Print rounds
                    if 'rounds' in cap_table:
                        for round_data in cap_table['rounds'][:3]:  # First 3 rounds
                            print(f"\n{round_data.get('round_name', 'Unknown')}:")
                            print(f"  Pre-money: ${round_data.get('pre_money_valuation', 0):,.0f}")
                            print(f"  Investment: ${round_data.get('investment_amount', 0):,.0f}")
                            print(f"  Post-money: ${round_data.get('post_money_valuation', 0):,.0f}")
                            
                            if 'post_money_ownership' in round_data:
                                print("  Ownership:")
                                for investor, pct in list(round_data['post_money_ownership'].items())[:3]:
                                    print(f"    {investor}: {pct:.1%}")
                    
                    # Print current ownership
                    if 'current_ownership' in cap_table:
                        print("\nCurrent Ownership:")
                        for investor, pct in cap_table['current_ownership'].items():
                            print(f"  {investor}: {pct:.1%}")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_deck_structure())