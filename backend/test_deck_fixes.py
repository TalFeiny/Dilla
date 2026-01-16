#!/usr/bin/env python3
"""Test the deck generation fixes"""

import asyncio
import logging
from app.services.unified_mcp_orchestrator import UnifiedMCPOrchestrator
from app.services.intelligent_gap_filler import IntelligentGapFiller
from app.services.citation_manager import CitationManager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_deck_fixes():
    """Test that deck generation works with real data"""
    try:
        orchestrator = UnifiedMCPOrchestrator()
        
        # Create test company data
        test_company = {
            'company': 'TestCo',
            'business_model': 'AI-powered data analytics platform',
            'product_description': 'Cloud-based analytics with ML',
            'target_market': 'Fortune 500 enterprises',
            'sector': 'Enterprise AI',
            'stage': 'Series A',
            'valuation': 50000000,
            'revenue': 5000000,
            'team_size': 45,
            'inferred_team_size': 45,
            'market_size': {
                'tam': 10000000000,
                'sam': 500000000,
                'som': 50000000,
                'bottom_up_tam': 8000000000,
                'labor_value_capturable': 15000000000,
                'labor_value_total': 50000000000,
                'labor_replacement_rate': 0.30,
                'tam_citation': 'Gartner Analytics Report 2024',
                'tam_methodology': 'Bottom-up from enterprise spend'
            },
            'pricing_model': 'Usage-based with enterprise contracts',
            'customers': ['Microsoft', 'Google', 'Amazon'],
            'fund_fit_score': 75,
            'fund_fit_recommendation': 'INVEST - Strong fit',
            'fund_fit_action': 'Invest 10M',
            'fund_fit_reasons': ['Can achieve 12% ownership', 'Good entry valuation', 'High growth potential'],
            'optimal_check_size': 10000000,
            'actual_ownership_pct': 0.12,
            'exit_ownership_pct': 0.084,
            'exit_proceeds': 84000000,
            'expected_irr': 35
        }
        
        # Test deck generation
        orchestrator.shared_data = {'companies': [test_company, test_company]}
        
        print("Testing deck generation...")
        deck_result = await orchestrator._execute_deck_generation({})
        
        if 'error' in deck_result:
            print(f"Error: {deck_result['error']}")
            return False
        
        print(f"Generated {deck_result.get('slide_count', 0)} slides")
        return True
        
    except Exception as e:
        print(f"Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    asyncio.run(test_deck_fixes())
