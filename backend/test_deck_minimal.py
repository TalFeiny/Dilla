#!/usr/bin/env python3
"""Minimal test to verify deck generation works"""
import asyncio
import sys
import json
from app.services.unified_mcp_orchestrator import UnifiedMCPOrchestrator

async def test_minimal_deck():
    """Test the absolute minimum for deck generation"""
    orchestrator = UnifiedMCPOrchestrator()
    
    print("=" * 80)
    print("MINIMAL DECK GENERATION TEST")
    print("=" * 80)
    
    try:
        # Test 1: Direct deck-storytelling skill call with no companies
        print("\n1. Testing deck-storytelling skill directly (no companies)...")
        result = await orchestrator._execute_deck_generation({})
        print(f"   Result type: {type(result)}")
        print(f"   Has slides: {'slides' in result}")
        if 'slides' in result:
            print(f"   Slide count: {len(result['slides'])}")
            if result['slides']:
                print(f"   First slide: {result['slides'][0].get('template', 'NO_TEMPLATE')}")
        
        # Test 2: Via process_request with simple prompt
        print("\n2. Testing via process_request with simple prompt...")
        result = await orchestrator.process_request(
            prompt="Generate investment deck for @Mercury",
            output_format="deck"
        )
        print(f"   Success: {result.get('success', False)}")
        print(f"   Has slides: {'slides' in result}")
        if 'slides' in result:
            print(f"   Slide count: {len(result['slides'])}")
        
        # Test 3: Via skill invocation (like test_dpi_generation.py does)
        print("\n3. Testing via skill invocation (generate_deck -> deck-storytelling mapping)...")
        result = await orchestrator.process_request({
            'skill': 'generate_deck',
            'inputs': {
                'companies': ['@Mercury'],
                'fund_context': {
                    'fund_size': 234_000_000
                }
            }
        })
        print(f"   Success: {result.get('success', False)}")
        print(f"   Result keys: {list(result.keys())}")
        print(f"   Has slides: {'slides' in result}")
        if 'slides' in result:
            print(f"   Slide count: {len(result['slides'])}")
            
        # Save last result for inspection
        with open("test_deck_minimal_output.json", "w") as f:
            json.dump(result, f, indent=2, default=str)
        print("\n✅ Output saved to test_deck_minimal_output.json")
        
        print("\n" + "=" * 80)
        if result.get('slides'):
            print("✅ DECK GENERATION IS WORKING!")
        else:
            print("❌ DECK GENERATION FAILED - NO SLIDES RETURNED")
            print(f"   Error: {result.get('error', 'Unknown error')}")
        print("=" * 80)
        
        return bool(result.get('slides'))
        
    except Exception as e:
        print(f"\n❌ Test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(test_minimal_deck())
    sys.exit(0 if success else 1)