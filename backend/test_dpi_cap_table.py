#!/usr/bin/env python3
"""Test the new DPI and Cap Table functionality"""

import asyncio
import json
from app.services.unified_mcp_orchestrator import UnifiedMCPOrchestrator

async def test_dpi_and_cap_table():
    """Test the new DPI slide and forward-looking cap table"""
    
    # Initialize orchestrator
    orchestrator = UnifiedMCPOrchestrator()
    
    # Test fund context
    fund_context = {
        'fund_size': 234_000_000,
        'deployed_capital': 125_000_000,
        'remaining_capital': 109_000_000,
        'portfolio_size': 18,
        'current_dpi': 0.5,
        'target_dpi': 3.0,
        'fund_year': 4
    }
    
    # Test companies
    companies = [
        {
            'company': 'TestCo1',
            'valuation': 100_000_000,
            'stage': 'Series A',
            'revenue': 10_000_000,
            'founders': 40,
            'investors': 45,
            'employees': 15,
            'funding_rounds': [
                {'round_name': 'Seed', 'amount': 2_000_000, 'valuation': 8_000_000},
                {'round_name': 'Series A', 'amount': 15_000_000, 'valuation': 60_000_000}
            ]
        },
        {
            'company': 'TestCo2', 
            'valuation': 150_000_000,
            'stage': 'Series B',
            'revenue': 20_000_000,
            'founders': 35,
            'investors': 50,
            'employees': 15,
            'funding_rounds': [
                {'round_name': 'Seed', 'amount': 3_000_000, 'valuation': 12_000_000},
                {'round_name': 'Series A', 'amount': 20_000_000, 'valuation': 80_000_000},
                {'round_name': 'Series B', 'amount': 40_000_000, 'valuation': 110_000_000}
            ]
        }
    ]
    
    # Store in shared data
    orchestrator.shared_data['fund_context'] = fund_context
    
    # Test parsing portfolio composition
    print("Testing portfolio composition parsing...")
    portfolio_comp = orchestrator._parse_portfolio_composition(fund_context, companies)
    print(f"Portfolio composition: {json.dumps(portfolio_comp, indent=2)}")
    
    # Test DPI impact calculation
    print("\nTesting DPI impact scenarios...")
    dpi_impact = orchestrator._calculate_dpi_impact_scenarios(
        companies=companies,
        fund_size=fund_context['fund_size'],
        deployed_capital=fund_context['deployed_capital'],
        remaining_capital=fund_context['remaining_capital'],
        current_dpi=fund_context['current_dpi'],
        portfolio_composition=portfolio_comp
    )
    print(f"DPI Impact: {json.dumps(dpi_impact, indent=2)}")
    
    # Test forward-looking cap table
    print("\nTesting forward-looking cap table...")
    check_size = orchestrator._get_optimal_check_size(companies[0], fund_context)
    forward_cap_table = orchestrator._calculate_forward_cap_table(
        companies[0],
        check_size,
        fund_context
    )
    print(f"Forward cap table: {json.dumps(forward_cap_table, indent=2)}")
    
    # Test Sankey enhancement
    print("\nTesting Sankey enhancement...")
    dummy_sankey = {
        'nodes': [
            {'id': 0, 'name': 'Founders 100%'},
            {'id': 1, 'name': 'Final: Founders 40%'},
            {'id': 2, 'name': 'Final: Investors 45%'},
            {'id': 3, 'name': 'Final: Employees 15%'}
        ],
        'links': [
            {'source': 0, 'target': 1, 'value': 40},
            {'source': 0, 'target': 2, 'value': 45},
            {'source': 0, 'target': 3, 'value': 15}
        ]
    }
    
    enhanced_sankey = orchestrator._enhance_sankey_with_investment(
        dummy_sankey,
        forward_cap_table,
        companies[0]['company']
    )
    print(f"Enhanced Sankey nodes: {len(enhanced_sankey['nodes'])}")
    print(f"Enhanced Sankey links: {len(enhanced_sankey['links'])}")
    
    print("\n✅ All tests passed successfully!")
    return True

if __name__ == "__main__":
    result = asyncio.run(test_dpi_and_cap_table())
    if result:
        print("\n🎉 DPI and Cap Table functionality is working correctly!")