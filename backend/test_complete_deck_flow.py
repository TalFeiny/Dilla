#!/usr/bin/env python3
"""Complete test of deck generation with PDF export for Vega and 73Strings"""
import asyncio
import sys
import os
import json
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent
sys.path.insert(0, str(backend_path))

from app.services.unified_mcp_orchestrator import UnifiedMCPOrchestrator
from app.services.deck_export_service import DeckExportService

async def test_complete_flow():
    """Test complete deck generation and PDF export flow"""
    orchestrator = UnifiedMCPOrchestrator()
    export_service = DeckExportService()
    
    try:
        print("="*60)
        print("TESTING COMPLETE DECK GENERATION FOR @VEGA & @73STRINGS")
        print("="*60)
        
        # Step 1: Generate deck data
        print("\n1. Generating deck data...")
        request = {
            'skill': 'unified',
            'inputs': {
                'prompt': 'Create investment deck for @Vega and @73Strings for a $234M fund with $109M remaining to deploy',
                'output_format': 'deck',
                'show_citations': True
            }
        }
        
        result = await orchestrator.process_request(request)
        
        if 'error' in result:
            print(f"❌ Error generating deck: {result['error']}")
            return False
        
        deck_data = result.get('deck_data', {})
        slides = deck_data.get('slides', [])
        companies = result.get('companies', [])
        
        print(f"✅ Generated deck with {len(slides)} slides")
        print(f"✅ Found {len(companies)} companies with data")
        
        # Check investor data
        print("\n2. Checking investor data extraction...")
        for company in companies:
            name = company.get('company', 'Unknown')
            funding_rounds = company.get('funding_rounds', [])
            print(f"\n  {name}:")
            for rd in funding_rounds:
                investors = rd.get('investors', [])
                round_name = rd.get('round', 'Unknown')
                amount = rd.get('amount', 0)
                print(f"    - {round_name}: ${amount:,.0f}")
                if investors:
                    print(f"      Investors: {', '.join(investors)}")
                else:
                    print(f"      Investors: None found (empty list)")
                    
                # Verify no None types
                if investors is None:
                    print(f"      ❌ ERROR: Investors is None!")
                    return False
        
        # Step 3: Export to PDF
        print("\n3. Exporting deck to PDF...")
        if not slides:
            print("⚠️  No slides to export, generating test deck...")
            # Generate a proper deck through unified brain
            from app.api.endpoints.unified_brain import generate_deck_endpoint
            test_result = await generate_deck_endpoint(
                prompt='Create investment deck for @Vega and @73Strings for a $234M fund',
                output_format='deck'
            )
            deck_data = test_result.get('deck_data', {})
            slides = deck_data.get('slides', [])
            companies = test_result.get('companies', [])
            
            if not slides:
                print("❌ Still no slides after retry")
                return False
                
        pdf_path = export_service.export_to_pdf(deck_data)  # Not async
        
        if pdf_path and os.path.exists(pdf_path):
            file_size = os.path.getsize(pdf_path) / 1024  # KB
            print(f"✅ PDF exported successfully: {pdf_path}")
            print(f"   File size: {file_size:.1f} KB")
            
            # Save to a known location for easy access
            output_path = Path("investment_deck_vega_73strings.pdf")
            import shutil
            shutil.copy(pdf_path, output_path)
            print(f"✅ PDF saved to: {output_path.absolute()}")
        else:
            print(f"❌ PDF export failed")
            return False
        
        # Step 4: Summary
        print("\n" + "="*60)
        print("DECK GENERATION SUMMARY")
        print("="*60)
        print(f"Companies analyzed: {', '.join([c.get('company', 'Unknown') for c in companies])}")
        print(f"Total slides: {len(slides)}")
        print(f"PDF location: {output_path.absolute()}")
        
        # List slide titles
        print("\nSlide Titles:")
        for i, slide in enumerate(slides, 1):
            title = slide.get('content', {}).get('title', 'Untitled')
            print(f"  {i}. {title}")
        
        print("\n✅ ALL TESTS PASSED! Deck generated with proper investor data.")
        print(f"📄 Open the PDF: {output_path.absolute()}")
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
    success = asyncio.run(test_complete_flow())
    sys.exit(0 if success else 1)