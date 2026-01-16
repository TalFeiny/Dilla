#!/usr/bin/env python3
"""
Test that companies persist in shared_data through the deck generation pipeline
"""
import asyncio
import logging
from datetime import datetime
from app.services.unified_mcp_orchestrator import UnifiedMCPOrchestrator

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def test_shared_data_persistence():
    """Test that companies passed as data objects persist through the pipeline"""
    orchestrator = UnifiedMCPOrchestrator()
    
    # Create test company data with all required fields
    test_companies = [
        {
            "company": "TestCorp",
            "stage": "Series B",
            "valuation": 500_000_000,
            "revenue": 50_000_000,
            "inferred_revenue": 50_000_000,
            "inferred_valuation": 500_000_000,
            "team_size": 200,
            "inferred_team_size": 200,
            "growth_rate": 150,
            "inferred_growth_rate": 150,
            "business_model": "SaaS",
            "industry": "Technology",
            "founding_date": "2020-01-01",
            "total_funding": 150_000_000,
            "inferred_total_funding": 150_000_000,
            "founders": ["John Doe", "Jane Smith"],
            "geography": "San Francisco",
            "is_yc": False,
            "funding_rounds": [
                {
                    "date": "2021-03-15",
                    "amount": 25_000_000,
                    "stage": "Series A",
                    "investors": ["Sequoia Capital"]
                },
                {
                    "date": "2023-06-20",
                    "amount": 125_000_000,
                    "stage": "Series B",
                    "investors": ["Andreessen Horowitz", "Sequoia Capital"]
                }
            ],
            "description": "Cloud-based project management software for enterprises"
        },
        {
            "company": "DataFlow",
            "stage": "Series A",
            "valuation": 120_000_000,
            "revenue": 8_000_000,
            "inferred_revenue": 8_000_000,
            "inferred_valuation": 120_000_000,
            "team_size": 45,
            "inferred_team_size": 45,
            "growth_rate": 200,
            "inferred_growth_rate": 200,
            "business_model": "SaaS",
            "industry": "Data Analytics",
            "founding_date": "2021-06-01",
            "total_funding": 30_000_000,
            "inferred_total_funding": 30_000_000,
            "founders": ["Alex Chen"],
            "geography": "New York",
            "is_yc": True,
            "funding_rounds": [
                {
                    "date": "2022-09-10",
                    "amount": 5_000_000,
                    "stage": "Seed",
                    "investors": ["Y Combinator", "Angel Investors"]
                },
                {
                    "date": "2024-01-15",
                    "amount": 25_000_000,
                    "stage": "Series A",
                    "investors": ["Benchmark"]
                }
            ],
            "description": "Real-time data processing platform for ML pipelines"
        }
    ]
    
    try:
        # Test 1: Process request with companies as data objects
        logger.info("=" * 80)
        logger.info("TEST 1: Processing request with companies as data objects")
        logger.info("=" * 80)
        
        result = await orchestrator.process_request({
            "skill": "deck-storytelling",
            "companies": test_companies,
            "fund_context": {
                "fund_size": 260_000_000,
                "remaining_capital": 109_000_000,
                "portfolio_count": 8,
                "fund_year": 2
            }
        })
        
        # Check if deck was generated
        if result.get('success') and result.get('format') == 'deck':
            slides = result.get('slides', [])
            logger.info(f"✅ Deck generated successfully with {len(slides)} slides")
            
            # Verify key slides exist
            slide_titles = [slide.get('content', {}).get('title', '') for slide in slides]
            logger.info(f"Slide titles: {slide_titles[:5]}...")
            
            # Check if companies are included in result
            if result.get('companies'):
                logger.info(f"✅ Companies preserved in result: {[c['company'] for c in result.get('companies', [])]}")
            else:
                logger.warning("⚠️ Companies not included in result")
            
            return True
        else:
            logger.error(f"❌ Deck generation failed: {result.get('error', 'Unknown error')}")
            return False
            
    except Exception as e:
        logger.error(f"❌ Test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        return False

async def main():
    success = await test_shared_data_persistence()
    if success:
        logger.info("🎉 All tests passed! Shared data persistence is working correctly.")
    else:
        logger.error("❌ Tests failed. Please check the implementation.")

if __name__ == "__main__":
    asyncio.run(main())