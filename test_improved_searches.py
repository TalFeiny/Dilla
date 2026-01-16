#!/usr/bin/env python3
"""Test the improved TAM search strategy"""

import asyncio
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))

from app.services.unified_mcp_orchestrator import UnifiedMCPOrchestrator
import logging

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

async def test_search_strategy():
    orchestrator = UnifiedMCPOrchestrator()
    
    # Test with a company that should have good TAM data
    test_company = "Ramp"
    
    logger.info(f"\n{'='*60}")
    logger.info(f"Testing improved search strategy for: {test_company}")
    logger.info(f"{'='*60}\n")
    
    # Fetch the company with the new search strategy
    result = await orchestrator._execute_company_fetch({
        "companies": [test_company]
    })
    
    if result and "companies" in result and len(result["companies"]) > 0:
        company_data = result["companies"][0]
        
        # Check what searches were executed
        logger.info("\n📊 Company Data Retrieved:")
        logger.info(f"  Name: {company_data.get('name', 'Unknown')}")
        logger.info(f"  Description: {company_data.get('description', 'Unknown')[:100]}...")
        logger.info(f"  Vertical: {company_data.get('vertical', 'Unknown')}")
        logger.info(f"  Category: {company_data.get('category', 'Unknown')}")
        
        # Check TAM data
        logger.info("\n💰 TAM Data:")
        market_size = company_data.get('market_size', {})
        if isinstance(market_size, dict):
            logger.info(f"  Traditional TAM: ${market_size.get('tam_traditional', 0):,.0f}")
            logger.info(f"  Labor TAM: ${market_size.get('tam_labor', 0):,.0f}")
            logger.info(f"  SAM: ${market_size.get('sam', 0):,.0f}")
            logger.info(f"  SOM: ${market_size.get('som', 0):,.0f}")
        else:
            logger.info(f"  Market Size: {market_size}")
        
        # Check citations
        logger.info("\n📚 TAM Citations:")
        citations = company_data.get('citations', [])
        if citations:
            for i, citation in enumerate(citations[:5], 1):
                logger.info(f"  {i}. {citation.get('title', 'No title')}")
                logger.info(f"     URL: {citation.get('url', 'No URL')}")
        else:
            logger.info("  No citations found")
    else:
        logger.error("Failed to fetch company data")

if __name__ == "__main__":
    asyncio.run(test_search_strategy())