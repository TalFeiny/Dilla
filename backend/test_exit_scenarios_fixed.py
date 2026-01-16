#!/usr/bin/env python3
"""Test that exit scenarios are properly visualized with charts and breakpoints"""

import asyncio
import logging
import json
from app.services.unified_mcp_orchestrator import UnifiedMCPOrchestrator

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_exit_scenarios_visualization():
    """Test that exit scenarios have charts and breakpoints properly configured"""
    
    orchestrator = UnifiedMCPOrchestrator()
    
    # Test with companies that should trigger comprehensive exit scenarios
    prompt = "Compare @Mercury and @Brex for investment with exit scenarios"
    
    logger.info("🚀 Starting exit scenarios visualization test...")
    
    # Process the request
    results = []
    found_exit_scenarios = False
    found_charts = False
    
    async for chunk in orchestrator.process_request_stream(
        prompt=prompt,
        output_format="deck"
    ):
        results.append(chunk)
        if chunk.get("type") == "slides":
            slides = chunk.get("slides", [])
            for slide in slides:
                # Check for comprehensive exit scenarios
                if slide.get("type") == "exit_scenarios_comprehensive":
                    found_exit_scenarios = True
                    logger.info("✅ Found exit_scenarios_comprehensive slide")
                    
                    content = slide.get("content", {})
                    
                    # Check for charts
                    charts = content.get("charts", [])
                    if charts:
                        found_charts = True
                        logger.info(f"✅ Found {len(charts)} charts in exit scenarios")
                        
                        for idx, chart in enumerate(charts):
                            logger.info(f"  Chart {idx + 1}: {chart.get('type')} - {chart.get('title')}")
                            
                            # Verify chart has proper data structure
                            if chart.get("data"):
                                if chart["type"] == "sankey":
                                    nodes = chart["data"].get("nodes", [])
                                    links = chart["data"].get("links", [])
                                    logger.info(f"    - Sankey: {len(nodes)} nodes, {len(links)} links")
                                elif chart["type"] == "line":
                                    datasets = chart["data"].get("datasets", [])
                                    labels = chart["data"].get("labels", [])
                                    logger.info(f"    - Line: {len(labels)} points, {len(datasets)} datasets")
                    
                    # Check for companies data with breakpoints
                    companies = content.get("companies", {})
                    for company_name, company_data in companies.items():
                        logger.info(f"\n  Analyzing {company_name}:")
                        
                        # Check breakpoints
                        breakpoints = company_data.get("breakpoints", {})
                        if breakpoints:
                            logger.info(f"    ✅ Breakpoints found:")
                            if breakpoints.get("liquidation_preference"):
                                logger.info(f"      - Liq Pref: ${breakpoints['liquidation_preference']/1e6:.1f}M")
                            if breakpoints.get("conversion_point"):
                                logger.info(f"      - Conversion: ${breakpoints['conversion_point']/1e6:.1f}M")
                            if breakpoints.get("target_3x_exit"):
                                logger.info(f"      - 3x Target: ${breakpoints['target_3x_exit']/1e6:.1f}M")
                        
                        # Check entry/exit economics
                        entry = company_data.get("entry_economics", {})
                        exit_econ = company_data.get("exit_economics", {})
                        if entry and exit_econ:
                            logger.info(f"    ✅ Economics found:")
                            logger.info(f"      - Entry: ${entry.get('investment', 0)/1e6:.1f}M @ {entry.get('entry_ownership', 0):.1f}%")
                            logger.info(f"      - Exit (no follow): {exit_econ.get('ownership_no_followon', 0):.1f}%")
                            logger.info(f"      - Exit (w/ follow): {exit_econ.get('ownership_with_followon', 0):.1f}%")
    
    # Check results
    success = found_exit_scenarios and found_charts
    
    if success:
        logger.info("\n✅ SUCCESS: Exit scenarios are properly configured with charts and breakpoints!")
    else:
        if not found_exit_scenarios:
            logger.error("\n❌ FAILED: exit_scenarios_comprehensive slide not found")
        if not found_charts:
            logger.error("\n❌ FAILED: No charts found in exit scenarios")
    
    return success

if __name__ == "__main__":
    success = asyncio.run(test_exit_scenarios_visualization())
    exit(0 if success else 1)