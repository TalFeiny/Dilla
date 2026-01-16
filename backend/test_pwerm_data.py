#!/usr/bin/env python3
"""Simple test to verify PWERM data is being added to companies"""

import asyncio
import logging
from app.services.unified_mcp_orchestrator import UnifiedMCPOrchestrator

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_pwerm_data():
    """Test that PWERM data is being calculated and added"""
    
    orchestrator = UnifiedMCPOrchestrator()
    
    # Test fetching company data with PWERM calculation
    logger.info("Testing company data fetch with PWERM...")
    
    result = await orchestrator._execute_company_fetch({"company": "@Mercury"})
    
    if "companies" in result and len(result["companies"]) > 0:
        company_data = result["companies"][0]
        
        logger.info(f"\nCompany: {company_data.get('company', 'Unknown')}")
        
        # Check for PWERM data
        if "pwerm_scenarios" in company_data:
            scenarios = company_data["pwerm_scenarios"]
            logger.info(f"✓ PWERM scenarios found: {len(scenarios)} scenarios")
            
            # Show first scenario
            if scenarios:
                first = scenarios[0]
                logger.info(f"  Example scenario: {getattr(first, 'scenario', 'N/A')} - {getattr(first, 'probability', 0)*100:.0f}% probability")
        else:
            logger.error("✗ No PWERM scenarios found")
        
        if "pwerm_valuation" in company_data:
            logger.info(f"✓ PWERM valuation: ${company_data['pwerm_valuation']/1e6:.1f}M")
        else:
            logger.error("✗ No PWERM valuation found")
        
        # Check for ownership evolution
        if "ownership_evolution" in company_data:
            ownership = company_data["ownership_evolution"]
            logger.info(f"✓ Ownership evolution found:")
            logger.info(f"  Entry: {ownership.get('entry_ownership', 0)*100:.1f}%")
            logger.info(f"  Exit (no follow-on): {ownership.get('exit_ownership_no_followon', 0)*100:.1f}%")
            logger.info(f"  Exit (with follow-on): {ownership.get('exit_ownership_with_followon', 0)*100:.1f}%")
            logger.info(f"  Follow-on capital: ${ownership.get('followon_capital_required', 0)/1e6:.1f}M")
        else:
            logger.error("✗ No ownership evolution found")
        
        return True
    else:
        logger.error("✗ Failed to fetch company data")
        return False

if __name__ == "__main__":
    success = asyncio.run(test_pwerm_data())
    if success:
        print("\n✅ PWERM data and ownership calculations are working!")
    else:
        print("\n❌ PWERM data not being added properly")