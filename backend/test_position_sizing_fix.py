#!/usr/bin/env python3
"""Test that position sizing works correctly even when valuation is missing"""

import asyncio
import json
from app.services.unified_mcp_orchestrator import UnifiedMCPOrchestrator

async def test_position_sizing():
    """Test optimal check size calculation with and without valuation"""
    
    # Initialize orchestrator
    orchestrator = UnifiedMCPOrchestrator()
    
    # Test 1: Company with valuation (should calculate based on ownership target)
    print("\n=== Test 1: Company WITH valuation ===")
    test_company_with_val = {
        'company': 'TestCo',
        'valuation': 100_000_000,  # $100M valuation
        'stage': 'Series A',
        'revenue': 10_000_000,
        'funding_rounds': [
            {'round': 'Series A', 'amount': 20_000_000}
        ]
    }
    
    fund_context_lead = {
        'fund_size': 500_000_000,  # $500M fund
        'is_lead': True,
        'remaining_capital': 300_000_000
    }
    
    # Test the helper method directly
    check_with_val = orchestrator._get_optimal_check_size(test_company_with_val, fund_context_lead)
    print(f"Company with $100M valuation:")
    print(f"  - Optimal check size: ${check_with_val/1e6:.1f}M")
    print(f"  - As % of fund: {check_with_val/fund_context_lead['fund_size']*100:.1f}%")
    
    # Test 2: Company WITHOUT valuation (should use position sizing fallback)
    print("\n=== Test 2: Company WITHOUT valuation ===")
    test_company_no_val = {
        'company': 'NoValCo', 
        'valuation': 0,  # No valuation data
        'stage': 'Series B',
        'revenue': 15_000_000,
        'optimal_check_size': 0  # Fund fit couldn't calculate due to missing valuation
    }
    
    check_no_val = orchestrator._get_optimal_check_size(test_company_no_val, fund_context_lead)
    print(f"Company with no valuation (Series B):")
    print(f"  - Fallback check size: ${check_no_val/1e6:.1f}M")
    print(f"  - As % of fund: {check_no_val/fund_context_lead['fund_size']*100:.1f}%")
    print(f"  - Calculation: Fund=${fund_context_lead['fund_size']/1e6:.0f}M × 5% (lead) × 70% (Series B) = ${check_no_val/1e6:.1f}M")
    
    # Test 3: Different stages should get different check sizes
    print("\n=== Test 3: Stage-based position sizing ===")
    stages_to_test = ['Seed', 'Series A', 'Series B', 'Series C']
    
    for stage in stages_to_test:
        test_company = {
            'company': f'{stage}Co',
            'stage': stage,
            'valuation': 0,  # No valuation
            'optimal_check_size': 0
        }
        
        check_size = orchestrator._get_optimal_check_size(test_company, fund_context_lead)
        print(f"{stage:10s}: ${check_size/1e6:5.1f}M ({check_size/fund_context_lead['fund_size']*100:.2f}% of fund)")
    
    # Test 4: Lead vs Follow investor
    print("\n=== Test 4: Lead vs Follow investor ===")
    fund_context_follow = {
        'fund_size': 500_000_000,
        'is_lead': False,
        'remaining_capital': 300_000_000
    }
    
    test_company_b = {
        'company': 'SeriesBCo',
        'stage': 'Series B',
        'valuation': 0,
        'optimal_check_size': 0
    }
    
    check_lead = orchestrator._get_optimal_check_size(test_company_b, fund_context_lead)
    check_follow = orchestrator._get_optimal_check_size(test_company_b, fund_context_follow)
    
    print(f"Series B company:")
    print(f"  - As lead investor:   ${check_lead/1e6:.1f}M (5% max × 70% stage)")
    print(f"  - As follow investor: ${check_follow/1e6:.1f}M (3% max × 70% stage)")
    
    # Test 5: End-to-end test with actual company fetch
    print("\n=== Test 5: End-to-end test with Mercury (may have missing valuation) ===")
    
    result = await orchestrator.process_request({
        'type': 'company_fetch',
        'query': '@Mercury',
        'fund_size': 456_000_000,
        'fund_year': 3,
        'remaining_capital': 276_000_000
    })
    
    if result['companies']:
        company = result['companies'][0]
        print(f"\nMercury analysis:")
        print(f"  - Valuation: ${company.get('valuation', 0)/1e6:.0f}M")
        print(f"  - Optimal check: ${company.get('optimal_check_size', 0)/1e6:.1f}M")
        print(f"  - Fund fit score: {company.get('fund_fit_score', 0):.0f}")
        print(f"  - Stage: {company.get('stage', 'Unknown')}")
        
        # Verify no hardcoded 10M values
        check_size = company.get('optimal_check_size', 0)
        if check_size == 10_000_000:
            print("  ⚠️ WARNING: Check size is exactly $10M - might be hardcoded!")
        elif check_size > 0:
            print(f"  ✅ Check size ${check_size/1e6:.1f}M appears calculated")
        else:
            print("  ⚠️ Check size is 0 - fallback should have been used")

if __name__ == "__main__":
    asyncio.run(test_position_sizing())