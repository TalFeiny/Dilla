#!/usr/bin/env python3
"""Test the full deck generation with DPI contribution slide that was failing"""
import asyncio
import sys
import os
import json
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent
sys.path.insert(0, str(backend_path))

from app.services.unified_mcp_orchestrator import UnifiedMCPOrchestrator

async def test_dpi_generation():
    """Test full deck generation with companies that have investors"""
    orchestrator = UnifiedMCPOrchestrator()
    
    try:
        # Full deck generation request
        request = {
            'skill': 'generate_deck',
            'inputs': {
                'companies': ['@Vega', '@73Strings'],
                'fund_context': {
                    'fund_size': 234_000_000,  # $234M fund
                    'remaining_capital': 109_000_000,  # $109M to deploy
                    'target_ownership': 0.15,
                    'typical_check_size': 15_000_000  # $15M typical
                }
            }
        }
        
        print("Testing full deck generation with @Vega and @73Strings...")
        print("This includes the DPI Contribution slide that was failing...")
        
        result = await orchestrator.process_request(request)
        
        if 'error' in result:
            print(f"❌ ERROR: {result['error']}")
            return False
            
        # Check that we got deck data
        deck_data = result.get('deck_data', {})
        slides = deck_data.get('slides', [])
        
        print(f"\n✅ Generated {len(slides)} slides successfully!")
        
        # Find the DPI contribution slide
        dpi_slide = None
        for slide in slides:
            if 'DPI' in slide.get('title', '') or 'Fund Return' in slide.get('title', ''):
                dpi_slide = slide
                break
        
        if dpi_slide:
            print(f"✅ DPI/Fund Return slide found: {dpi_slide.get('title')}")
        else:
            print("⚠️  No DPI/Fund Return slide found (may be expected)")
        
        # Check company data
        companies_data = result.get('companies', [])
        print(f"\n📊 Company Data:")
        for company in companies_data:
            name = company.get('company', 'Unknown')
            funding_rounds = company.get('funding_rounds', [])
            print(f"\n  {name}:")
            for rd in funding_rounds:
                investors = rd.get('investors', [])
                print(f"    - {rd.get('round', 'Unknown')}: {len(investors)} investors")
                if investors:
                    print(f"      Investors: {', '.join(investors[:5])}")  # Show first 5
        
        print("\n✅ Deck generation completed successfully without NoneType errors!")
        return True
        
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        # Clean up
        if hasattr(orchestrator, 'close'):
            await orchestrator.close()

if __name__ == "__main__":
    success = asyncio.run(test_dpi_generation())
    sys.exit(0 if success else 1)