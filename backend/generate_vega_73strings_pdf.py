#!/usr/bin/env python3
"""Generate and save PDF deck for Vega and 73Strings"""
import asyncio
import sys
import os
import json
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent))

from app.services.unified_mcp_orchestrator import UnifiedMCPOrchestrator
from app.services.deck_export_service import DeckExportService

async def generate_and_save_pdf():
    """Generate deck and save as PDF"""
    orchestrator = UnifiedMCPOrchestrator()
    export_service = DeckExportService()
    
    try:
        print("="*70)
        print("🚀 GENERATING INVESTMENT DECK FOR @VEGA & @73STRINGS")
        print("="*70)
        
        # Generate deck with full unified brain
        print("\n📊 Fetching company data and generating deck...")
        request = {
            'skill': 'unified',
            'inputs': {
                'prompt': 'Create comprehensive investment deck for @Vega and @73Strings. Fund context: $234M fund with $109M remaining to deploy. Include full analysis with TAM, cap tables, exit scenarios, and investment recommendations.',
                'output_format': 'deck',
                'show_citations': True,
                'fund_context': {
                    'fund_size': 234_000_000,
                    'remaining_capital': 109_000_000,
                    'target_ownership': 0.15,
                    'typical_check_size': 15_000_000
                }
            }
        }
        
        result = await orchestrator.process_request(request)
        
        if 'error' in result:
            print(f"❌ Error: {result['error']}")
            return False
        
        deck_data = result.get('deck_data')
        companies = result.get('companies', [])
        
        if not deck_data:
            print("⚠️ No deck data returned, trying direct company fetch...")
            # Try fetching companies first
            fetch_request = {
                'skill': 'company_fetch',
                'inputs': {
                    'companies': ['@Vega', '@73Strings']
                }
            }
            fetch_result = await orchestrator.process_request(fetch_request)
            companies = fetch_result.get('companies', [])
            
            # Now generate deck with fetched data
            deck_request = {
                'skill': 'generate_deck',
                'inputs': {
                    'companies': companies,
                    'fund_context': {
                        'fund_size': 234_000_000,
                        'remaining_capital': 109_000_000
                    }
                }
            }
            deck_result = await orchestrator.process_request(deck_request)
            deck_data = deck_result.get('deck_data', {})
        
        slides = deck_data.get('slides', [])
        
        print(f"\n✅ Generated {len(slides)} slides")
        
        # Show company data with investors
        print("\n📈 Company Data Summary:")
        for company in companies:
            name = company.get('company', 'Unknown')
            valuation = company.get('latest_valuation', 0)
            revenue = company.get('revenue', company.get('inferred_revenue', 0))
            print(f"\n  {name}:")
            print(f"    Valuation: ${valuation:,.0f}")
            print(f"    Revenue: ${revenue:,.0f}")
            
            funding_rounds = company.get('funding_rounds', [])
            for rd in funding_rounds:
                investors = rd.get('investors', [])
                print(f"    {rd.get('round', 'Unknown')}: ${rd.get('amount', 0):,.0f}")
                if investors:
                    print(f"      Led by: {', '.join(investors[:3])}")
        
        # Export to PDF
        print("\n📄 Generating PDF...")
        pdf_bytes = export_service.export_to_pdf(deck_data)
        
        if pdf_bytes:
            # Save with descriptive filename
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"Vega_73Strings_Investment_Deck_{timestamp}.pdf"
            output_path = Path(filename)
            
            with open(output_path, 'wb') as f:
                f.write(pdf_bytes)
            
            file_size = len(pdf_bytes) / 1024  # KB
            
            print(f"\n✅ PDF SAVED SUCCESSFULLY!")
            print(f"📍 Location: {output_path.absolute()}")
            print(f"📊 Size: {file_size:.1f} KB")
            print(f"📑 Slides: {len(slides)}")
            
            # List slides
            if slides:
                print("\n📋 Slide Contents:")
                for i, slide in enumerate(slides, 1):
                    title = slide.get('content', {}).get('title', 'Untitled')
                    print(f"   {i:2}. {title}")
            
            print(f"\n🎉 DECK COMPLETE! Open the PDF:")
            print(f"   open {output_path.absolute()}")
            
            return True
        else:
            print("❌ Failed to generate PDF bytes")
            return False
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        if hasattr(orchestrator, 'close'):
            await orchestrator.close()

if __name__ == "__main__":
    success = asyncio.run(generate_and_save_pdf())
    sys.exit(0 if success else 1)