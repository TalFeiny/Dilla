#!/usr/bin/env python3
"""
Test the data flow with user's specific fund parameters:
- $76M seed fund
- $34M deployed
- Year 3
- Compare @artificialsocieties and @meshedcover
"""

import asyncio
import json
import logging
from datetime import datetime
from app.services.unified_mcp_orchestrator import UnifiedMCPOrchestrator

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def test_fund_comparison():
    """Test with user's specific fund and companies"""
    
    # Initialize orchestrator
    orchestrator = UnifiedMCPOrchestrator()
    
    # User's fund context
    fund_context = {
        'fund_size': 76_000_000,  # $76M fund
        'deployed_capital': 34_000_000,  # $34M deployed
        'fund_year': 3,  # Year 3
        'dry_powder': 42_000_000,  # $42M remaining
        'portfolio_count': 15,  # Estimated based on typical seed
        'lead_investor': True,
        'stage_focus': 'Seed',
        'average_check': 2_000_000,  # Typical seed check
    }
    
    # Test prompt exactly as user specified
    test_prompt = "I AM A 76M SEED FUND WITH 34M DEPLOYED IN YR 3. compare @artificialsocieties and @meshedcover"
    
    logger.info("=" * 80)
    logger.info("TESTING DATA FLOW WITH USER'S FUND PARAMETERS")
    logger.info("=" * 80)
    logger.info(f"Fund Size: $76M")
    logger.info(f"Deployed: $34M")
    logger.info(f"Year: 3")
    logger.info(f"Companies: @artificialsocieties and @meshedcover")
    logger.info("=" * 80)
    
    try:
        # Process the request
        result = await orchestrator.process_request(
            prompt=test_prompt,
            output_format="analysis",
            context=fund_context
        )
        
        # Check if we got companies data
        if 'skill_results' in result:
            for skill_name, skill_data in result['skill_results'].items():
                logger.info(f"\n{'='*60}")
                logger.info(f"SKILL: {skill_name}")
                logger.info(f"{'='*60}")
                
                if skill_name == 'company-data-fetcher':
                    companies = skill_data.get('companies', [])
                    logger.info(f"Found {len(companies)} companies")
                    
                    for comp in companies:
                        logger.info(f"\n--- {comp.get('company', 'Unknown')} ---")
                        logger.info(f"Overall Score: {comp.get('overall_score', 0):.1f}/100")
                        logger.info(f"Fund Fit Score: {comp.get('fund_fit_score', 0):.1f}/100")
                        logger.info(f"Revenue: ${comp.get('revenue', 0):,.0f}")
                        logger.info(f"Funding Stage: {comp.get('funding_analysis', {}).get('current_stage', 'Unknown')}")
                        logger.info(f"Total Raised: ${comp.get('funding_analysis', {}).get('total_raised', 0):,.0f}")
                        
                        # Check if scores are being calculated
                        if comp.get('fund_fit_score', 0) == 0:
                            logger.warning("⚠️  Fund fit score is 0 - scoring may have failed")
                        if comp.get('overall_score', 0) == 0:
                            logger.warning("⚠️  Overall score is 0 - scoring may have failed")
                        
                        # Check for errors
                        if 'error' in comp:
                            logger.error(f"❌ Error: {comp['error']}")
                        if 'scoring_error' in comp:
                            logger.error(f"❌ Scoring Error: {comp['scoring_error']}")
                
                elif skill_name == 'deal-comparer':
                    comparison = skill_data.get('comparison', {})
                    logger.info(f"Comparison Result: {comparison.get('recommended_investment', 'None')}")
                    logger.info(f"Analysis: {comparison.get('analysis', 'No analysis')[:200]}...")
        
        # Save results for inspection
        output_file = f"test_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(output_file, 'w') as f:
            json.dump(result, f, indent=2, default=str)
        logger.info(f"\n✅ Results saved to {output_file}")
        
        # Check for critical issues
        logger.info("\n" + "="*60)
        logger.info("VALIDATION CHECKS")
        logger.info("="*60)
        
        issues = []
        if result.get('metrics', {}).get('tavily_calls', 0) == 0:
            issues.append("❌ No Tavily API calls made")
        else:
            logger.info(f"✅ Tavily calls: {result.get('metrics', {}).get('tavily_calls', 0)}")
            
        if result.get('metrics', {}).get('claude_calls', 0) == 0:
            issues.append("❌ No Claude API calls made")
        else:
            logger.info(f"✅ Claude calls: {result.get('metrics', {}).get('claude_calls', 0)}")
        
        if issues:
            logger.error("\nISSUES FOUND:")
            for issue in issues:
                logger.error(issue)
        else:
            logger.info("\n✅ All validation checks passed!")
        
        return result
        
    except Exception as e:
        logger.error(f"Test failed with error: {e}", exc_info=True)
        return None

if __name__ == "__main__":
    result = asyncio.run(test_fund_comparison())
    
    if result:
        logger.info("\n" + "="*60)
        logger.info("TEST COMPLETED SUCCESSFULLY")
        logger.info("="*60)
    else:
        logger.error("\n" + "="*60)
        logger.error("TEST FAILED")
        logger.error("="*60)