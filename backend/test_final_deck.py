#!/usr/bin/env python3
"""
Generate a final deck with real companies and export to PDF
"""

import asyncio
import json
from app.services.unified_mcp_orchestrator import UnifiedMCPOrchestrator
from app.services.deck_export_service import DeckExportService

async def main():
    """Generate a complete deck and export to PDF"""
    
    print("\n🚀 Generating Final Investment Deck...")
    print("=" * 60)
    
    # Initialize the orchestrator
    orchestrator = UnifiedMCPOrchestrator()
    
    # Generate deck for two real companies
    companies = ["@Mercury", "@Ramp"]
    prompt = f"Compare {companies[0]} and {companies[1]} for investment with deck format"
    
    print(f"\n📊 Analyzing: {', '.join(companies)}")
    print(f"📝 Format: Investment Deck")
    
    # Process the request
    result = await orchestrator.process_request(
        prompt=prompt,
        output_format="deck",
        context={
            "fund_size": 260_000_000,
            "fund_stage": "seed_to_a",
            "check_size_range": [2_000_000, 10_000_000]
        }
    )
    
    # Save the deck data
    with open("final_deck_data.json", "w") as f:
        json.dump(result, f, indent=2, default=str)
    
    # Debug: Check what we got
    deck_data = {"slides": []}  # Initialize with default
    if result.get("success"):
        deck_data = result.get("results", {})
        slides = deck_data.get("slides", deck_data.get("deck_slides", []))
    else:
        print(f"❌ Error: {result.get('error')}")
        slides = []
    
    print(f"\n✅ Generated {len(slides)} slides")
    
    # Export to PDF
    print("\n📄 Exporting to PDF...")
    exporter = DeckExportService()
    
    # Pass the deck data, not the wrapper
    pdf_bytes = exporter.export_to_pdf(deck_data)
    
    # Save the PDF
    pdf_path = "final_investment_deck.pdf"
    with open(pdf_path, "wb") as f:
        f.write(pdf_bytes)
    
    print(f"✅ PDF saved as: {pdf_path}")
    print(f"📏 File size: {len(pdf_bytes):,} bytes")
    
    # Also export to PowerPoint
    print("\n📊 Exporting to PowerPoint...")
    pptx_bytes = exporter.export_to_pptx(deck_data if deck_data else {"slides": []})
    
    pptx_path = "final_investment_deck.pptx"
    with open(pptx_path, "wb") as f:
        f.write(pptx_bytes)
    
    print(f"✅ PowerPoint saved as: {pptx_path}")
    print(f"📏 File size: {len(pptx_bytes):,} bytes")
    
    print("\n" + "=" * 60)
    print("🎉 Deck generation complete!")
    print(f"\n📁 Output files:")
    print(f"  • PDF: {pdf_path}")
    print(f"  • PowerPoint: {pptx_path}")
    print(f"  • Data: final_deck_data.json")

if __name__ == "__main__":
    asyncio.run(main())
