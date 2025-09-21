#!/usr/bin/env python3
"""Test the deck generation fix"""

import asyncio
import logging
from app.services.unified_mcp_orchestrator import get_unified_orchestrator

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_deck_generation():
    """Test deck generation with @ companies"""
    orchestrator = get_unified_orchestrator()
    
    # Test with @ companies
    prompt = "Create a pitch deck for @Stripe and @Square"
    logger.info(f"Testing prompt: {prompt}")
    
    result = await orchestrator.process_request(
        prompt=prompt,
        output_format="deck",
        context={}
    )
    
    if result.get("success"):
        deck_data = result.get("results", {})
        slides = deck_data.get("slides", [])
        logger.info(f"✅ Deck generation successful!")
        logger.info(f"   Format: {deck_data.get('format')}")
        logger.info(f"   Slides: {len(slides)}")
        logger.info(f"   Companies in shared_data: {len(orchestrator.shared_data.get('companies', []))}")
        
        # Show slide titles
        for i, slide in enumerate(slides[:5]):
            title = slide.get("content", {}).get("title", "Untitled")
            logger.info(f"   Slide {i+1}: {title}")
            
        return True
    else:
        logger.error(f"❌ Deck generation failed: {result.get('error')}")
        return False

if __name__ == "__main__":
    success = asyncio.run(test_deck_generation())
    exit(0 if success else 1)