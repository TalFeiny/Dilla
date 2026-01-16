#!/usr/bin/env python3
"""
Test deck generation improvements - Score target: 100/100
Tests improvements from feedback #6
"""

import asyncio
import json
from app.services.unified_mcp_orchestrator import UnifiedMCPOrchestrator
from app.services.deck_export_service import DeckExportService
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_deck_improvements():
    """Test all deck generation improvements"""
    
    orchestrator = UnifiedMCPOrchestrator()
    deck_export = DeckExportService()
    
    # Test with music tech example (hard market)
    test_request = {
        "skill": "unified-brain",
        "prompt": "@Mozart AI @Clanmark",  # Music production AI vs some other startup
        "options": {
            "output_format": "deck",
            "analysis_depth": "comprehensive"
        }
    }
    
    logger.info("=" * 80)
    logger.info("TESTING DECK IMPROVEMENTS - Target Score: 100/100")
    logger.info("=" * 80)
    
    # Process request
    result = await orchestrator.process_request(test_request)
    
    # Check improvements
    checks = {
        "1. Investment Thesis": False,
        "2. Competitive Analysis": False,
        "3. Company Logos": False,
        "4. Neo-Noir Theme": False,
        "5. Path to $100M Y-Axis": False,
        "6. Clear Invest/Pass": False,
        "7. Market Incumbents": False,
        "8. Unit Economics": False
    }
    
    # Validate deck data
    deck_data = result.get("deck_data", {})
    slides = deck_data.get("slides", [])
    
    if not slides:
        logger.error("❌ No slides generated!")
        return
    
    # Check each improvement
    for slide in slides:
        content = slide.get("content", {})
        
        # 1. Check for real investment thesis (not keyword scoring)
        if "investment" in str(slide).lower():
            thesis = content.get("investment_thesis", "")
            if thesis and "platform" not in thesis.lower():  # No generic keywords
                checks["1. Investment Thesis"] = True
                logger.info("✅ Real investment thesis found (no keyword stuffing)")
        
        # 2. Check for competitive analysis
        if content.get("competitors") or "competitive" in str(content).lower():
            checks["2. Competitive Analysis"] = True
            logger.info("✅ Competitive analysis included")
        
        # 3. Check for logo support
        if slide.get("type") == "title" and content.get("companies"):
            checks["3. Company Logos"] = True
            logger.info("✅ Company logos on title slide")
        
        # 4. Check neo-noir theme colors
        chart_data = content.get("chart_data", {})
        if chart_data:
            datasets = chart_data.get("data", {}).get("datasets", [])
            for dataset in datasets:
                border_color = dataset.get("borderColor", "")
                if "0, 255, 159" in border_color or "255, 71, 87" in border_color:
                    checks["4. Neo-Noir Theme"] = True
                    logger.info("✅ Neo-noir color theme applied")
                    break
        
        # 5. Check Path to $100M chart formatting
        if "path_to_100m" in slide.get("type", "").lower():
            options = chart_data.get("options", {})
            y_axis = options.get("scales", {}).get("y", {})
            ticks = y_axis.get("ticks", {})
            if "1000000" in str(ticks.get("callback", "")):
                checks["5. Path to $100M Y-Axis"] = True
                logger.info("✅ Path to $100M Y-axis properly formatted")
        
        # 6. Check for clear invest/pass reasoning
        if content.get("recommendation"):
            recommendation = content.get("recommendation", "")
            action = content.get("action", "")
            if action and len(action) > 50:  # Detailed reasoning
                checks["6. Clear Invest/Pass"] = True
                logger.info(f"✅ Clear recommendation: {recommendation}")
                logger.info(f"   Reasoning: {action[:100]}...")
        
        # 7. Check for market incumbents (music tech should mention Ableton, FL Studio, etc)
        companies_data = result.get("companies", [])
        for company in companies_data:
            competitors = company.get("competitors", [])
            if any("ableton" in str(c).lower() or "logic" in str(c).lower() for c in competitors):
                checks["7. Market Incumbents"] = True
                logger.info("✅ Market incumbents identified (Ableton, Logic, etc)")
        
        # 8. Check for unit economics
        if content.get("unit_economics") or "ltv" in str(content).lower() or "cac" in str(content).lower():
            checks["8. Unit Economics"] = True
            logger.info("✅ Unit economics analysis included")
    
    # Calculate score
    passed = sum(1 for v in checks.values() if v)
    total = len(checks)
    score = (passed / total) * 100
    
    logger.info("=" * 80)
    logger.info(f"FINAL SCORE: {score:.0f}/100")
    logger.info("=" * 80)
    
    # Detail missing items
    if score < 100:
        logger.warning("Missing improvements:")
        for check, passed in checks.items():
            if not passed:
                logger.warning(f"  ❌ {check}")
    
    # Export to PDF to check rendering
    if score >= 80:
        logger.info("Exporting to PDF to check rendering...")
        try:
            pdf_bytes = deck_export.export_to_pdf(deck_data)
            with open("test_deck_output_v2.pdf", "wb") as f:
                f.write(pdf_bytes)
            logger.info("✅ PDF exported to test_deck_output_v2.pdf")
        except Exception as e:
            logger.error(f"❌ PDF export failed: {e}")
    
    return score

if __name__ == "__main__":
    score = asyncio.run(test_deck_improvements())
    
    if score >= 90:
        logger.info("🎉 EXCELLENT! Deck quality significantly improved!")
    elif score >= 70:
        logger.info("👍 Good progress, but more work needed")
    else:
        logger.info("⚠️ Significant improvements still required")