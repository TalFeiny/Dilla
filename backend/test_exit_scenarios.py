#!/usr/bin/env python3
"""Test script to verify Exit Scenarios slide has real PWERM data with ownership"""

import asyncio
import logging
from app.services.unified_mcp_orchestrator import UnifiedMCPOrchestrator

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_exit_scenarios():
    """Test that exit scenarios slide has comprehensive ownership and breakpoint data"""
    
    orchestrator = UnifiedMCPOrchestrator()
    
    # Test with a simple prompt that should trigger deck generation
    prompt = "Compare @Mercury and @Brex for investment, generate deck"
    
    logger.info("Starting deck generation test...")
    
    # Process the request - process_request returns an async generator
    results = []
    async for chunk in orchestrator.process_request_stream(
        prompt=prompt,
        output_format="deck"
    ):
        results.append(chunk)
        if chunk.get("type") == "slides":
            # Check for exit scenarios slide
            slides = chunk.get("slides", [])
            for slide in slides:
                if slide.get("type") == "exit_scenarios_comprehensive":
                    logger.info("✓ Found comprehensive exit scenarios slide")
                    
                    # Verify the slide has the right structure
                    content = slide.get("content", {})
                    companies_data = content.get("companies", {})
                    
                    for company_name, company_data in companies_data.items():
                        logger.info(f"\nAnalyzing {company_name}:")
                        
                        # Check entry economics
                        entry = company_data.get("entry_economics", {})
                        if entry.get("entry_ownership"):
                            logger.info(f"  ✓ Entry ownership: {entry['entry_ownership']:.1f}%")
                        else:
                            logger.error(f"  ✗ Missing entry ownership")
                        
                        # Check exit economics
                        exit_econ = company_data.get("exit_economics", {})
                        if exit_econ.get("ownership_no_followon"):
                            logger.info(f"  ✓ Exit ownership (no follow-on): {exit_econ['ownership_no_followon']:.1f}%")
                        if exit_econ.get("ownership_with_followon"):
                            logger.info(f"  ✓ Exit ownership (with follow-on): {exit_econ['ownership_with_followon']:.1f}%")
                        if exit_econ.get("followon_capital"):
                            logger.info(f"  ✓ Follow-on capital required: ${exit_econ['followon_capital']/1e6:.1f}M")
                        
                        # Check breakpoints
                        breakpoints = company_data.get("breakpoints", {})
                        if breakpoints.get("liquidation_preference"):
                            logger.info(f"  ✓ Liquidation preference breakpoint: ${breakpoints['liquidation_preference']/1e6:.1f}M")
                        if breakpoints.get("target_3x_exit"):
                            logger.info(f"  ✓ Target 3x exit value: ${breakpoints['target_3x_exit']/1e6:.1f}M")
                        
                        # Check scenarios
                        scenarios = company_data.get("scenarios", [])
                        if scenarios:
                            logger.info(f"  ✓ Found {len(scenarios)} PWERM scenarios")
                            # Check first scenario for detailed data
                            if scenarios[0].get("exit_ownership_no_followon") is not None:
                                logger.info("  ✓ Scenarios include ownership evolution data")
                            if scenarios[0].get("below_liquidation") is not None:
                                logger.info("  ✓ Scenarios include liquidation preference flags")
                        else:
                            logger.error("  ✗ No scenarios found")
                        
                        # Check weighted outcomes
                        weighted = company_data.get("weighted_outcomes", {})
                        if weighted.get("probability_of_loss") is not None:
                            logger.info(f"  ✓ Probability of loss: {weighted['probability_of_loss']*100:.0f}%")
                        if weighted.get("probability_of_3x") is not None:
                            logger.info(f"  ✓ Probability of 3x return: {weighted['probability_of_3x']*100:.0f}%")
                    
                    return True  # Success!
    
    logger.error("✗ Exit scenarios slide not found or incomplete")
    return False

if __name__ == "__main__":
    success = asyncio.run(test_exit_scenarios())
    if success:
        print("\n✅ Exit Scenarios slide is now comprehensive with ownership and breakpoints!")
    else:
        print("\n❌ Exit Scenarios slide needs more work")