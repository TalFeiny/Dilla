#!/usr/bin/env python3
"""Quick test for probability cloud generation"""

import asyncio
import logging
from app.services.unified_mcp_orchestrator import UnifiedMCPOrchestrator

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_probability_cloud():
    orchestrator = UnifiedMCPOrchestrator()
    
    # Test company data
    company_data = {
        'company': 'TestCompany',
        'stage': 'Series A',
        'revenue': 10_000_000,
        'valuation': 100_000_000,
        'total_funding': 20_000_000,
        'growth_rate': 2.0
    }
    
    check_size = 10_000_000
    
    try:
        # Call the probability cloud generation method directly
        result = orchestrator._generate_probability_cloud_data(company_data, check_size)
        
        logger.info("Probability cloud data generated:")
        logger.info(f"- Scenario curves: {len(result.get('scenario_curves', []))} curves")
        logger.info(f"- Breakpoint clouds: {len(result.get('breakpoint_clouds', []))} breakpoints")
        logger.info(f"- Decision zones: {len(result.get('decision_zones', []))} zones")
        
        if result.get('scenario_curves'):
            logger.info("✅ Probability cloud generation successful!")
            return True
        else:
            logger.error("❌ No scenario curves generated")
            return False
            
    except Exception as e:
        logger.error(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(test_probability_cloud())
    exit(0 if success else 1)
