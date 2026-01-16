#!/usr/bin/env python3
"""Test that all deck slides are generated properly"""

import asyncio
import logging
import json
from app.services.unified_mcp_orchestrator import UnifiedMCPOrchestrator

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_deck_slides():
    orchestrator = UnifiedMCPOrchestrator()
    
    prompt = "Compare @Mercury and @Brex for investment"
    
    logger.info("🚀 Testing deck generation with all slides...")
    
    slide_types_found = set()
    has_probability_cloud = False
    
    async for chunk in orchestrator.process_request_stream(
        prompt=prompt,
        output_format="deck"
    ):
        if chunk.get("type") == "slides":
            slides = chunk.get("slides", [])
            for slide in slides:
                slide_type = slide.get("type")
                slide_types_found.add(slide_type)
                logger.info(f"Found slide: {slide_type}")
                
                # Check for probability cloud in exit scenarios
                if slide_type == "exit_scenarios_comprehensive":
                    charts = slide.get("content", {}).get("charts", [])
                    for chart in charts:
                        if chart.get("type") == "probability_cloud":
                            has_probability_cloud = True
                            logger.info("  ✅ Probability cloud found!")
    
    # Check results
    expected_slides = [
        "title",
        "summary", 
        "company_comparison",
        "founder_team_analysis",
        "path_to_100m_comparison",
        "business_analysis_comparison",
        "tam_pincer",
        "cap_table_comparison",
        "exit_scenarios_comprehensive",
        "followon_strategy_table",
        "fund_return_impact_enhanced",
        "risk_analysis",
        "investment_recommendations"
    ]
    
    missing_slides = []
    for expected in expected_slides:
        if expected not in slide_types_found:
            missing_slides.append(expected)
    
    logger.info(f"\n📊 Total slides found: {len(slide_types_found)}")
    logger.info(f"Slides: {', '.join(sorted(slide_types_found))}")
    
    if missing_slides:
        logger.error(f"\n❌ Missing slides: {', '.join(missing_slides)}")
    else:
        logger.info("\n✅ All expected slides present!")
    
    if not has_probability_cloud:
        logger.error("❌ Probability cloud not found in exit scenarios!")
    else:
        logger.info("✅ Probability cloud is present!")
    
    return len(missing_slides) == 0 and has_probability_cloud

if __name__ == "__main__":
    success = asyncio.run(test_deck_slides())
    exit(0 if success else 1)
