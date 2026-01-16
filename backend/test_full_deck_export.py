#!/usr/bin/env python3
"""
Test full deck generation with actual orchestrator
"""

import asyncio
import logging
from app.services.unified_mcp_orchestrator import UnifiedMCPOrchestrator
from app.services.deck_export_service import DeckExportService

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def generate_full_deck():
    """Generate full deck using orchestrator with user's prompt"""
    
    # Initialize orchestrator
    orchestrator = UnifiedMCPOrchestrator()
    
    # User's exact prompt with fund context
    prompt = "Compare @anam and @unosecur for series A for my 134m fund with 0 dpi, 3.6 tvpi"
    
    logger.info(f"Processing prompt: {prompt}")
    
    # Process the request
    result = await orchestrator.process_request({
        'prompt': prompt,
        'output_format': 'deck',
        'fund_context': {
            'fund_size': 134_000_000,  # $134M fund
            'dpi': 0,  # 0 DPI (no distributions yet)
            'tvpi': 3.6,  # 3.6x TVPI target
            'stage_focus': ['Seed', 'Series A'],
            'year': 3,  # Assuming year 3 of fund
            'portfolio_count': 9  # Assuming some portfolio
        }
    })
    
    # Check if we got slides
    if 'slides' in result:
        logger.info(f"Generated {len(result['slides'])} slides")
        
        # Log each slide type
        for i, slide in enumerate(result['slides']):
            logger.info(f"  Slide {i+1}: {slide.get('type', 'unknown')}")
        
        # Export to PDF
        exporter = DeckExportService()
        logger.info("Exporting to PDF...")
        
        pdf_bytes = exporter.export_to_pdf(result)
        
        # Save to file
        output_file = 'full_investment_deck_anam_unosecur.pdf'
        with open(output_file, 'wb') as f:
            f.write(pdf_bytes)
        
        logger.info(f"PDF saved to: backend/{output_file}")
        logger.info(f"File size: {len(pdf_bytes):,} bytes")
        
        # Also save the raw deck data for debugging
        import json
        with open('deck_data.json', 'w') as f:
            # Convert any numpy types to regular Python types
            def convert_types(obj):
                import numpy as np
                if isinstance(obj, np.integer):
                    return int(obj)
                elif isinstance(obj, np.floating):
                    return float(obj)
                elif isinstance(obj, np.ndarray):
                    return obj.tolist()
                elif isinstance(obj, dict):
                    return {k: convert_types(v) for k, v in obj.items()}
                elif isinstance(obj, list):
                    return [convert_types(item) for item in obj]
                return obj
            
            clean_result = convert_types(result)
            json.dump(clean_result, f, indent=2)
        logger.info("Deck data saved to: backend/deck_data.json")
        
        return result
    else:
        logger.error(f"No slides in result. Keys: {result.keys()}")
        if 'error' in result:
            logger.error(f"Error: {result['error']}")
        return None

if __name__ == "__main__":
    # Run the async function
    result = asyncio.run(generate_full_deck())
    
    if result:
        print(f"\n✅ Successfully generated deck with {len(result.get('slides', []))} slides")
        print("📄 PDF saved to: backend/full_investment_deck_anam_unosecur.pdf")
        print("📊 Raw data saved to: backend/deck_data.json")
    else:
        print("\n❌ Failed to generate deck")