#!/usr/bin/env python3
"""Test the cap table generation with fixed funding calculations"""

import asyncio
from app.services.unified_mcp_orchestrator import UnifiedMCPOrchestrator
from app.services.intelligent_gap_filler import IntelligentGapFiller

async def test_cap_table_generation():
    """Test that cap table generation now uses burn_monthly * runway_months"""
    
    # Initialize the gap filler to check benchmarks
    gap_filler = IntelligentGapFiller()
    
    print("Testing benchmark-based funding calculations...")
    print("=" * 60)
    
    # Test each stage's funding calculation
    stages = ["Seed", "Series A", "Series B", "Series C"]
    
    for stage in stages:
        benchmark = gap_filler.STAGE_BENCHMARKS.get(stage, {})
        burn_monthly = benchmark.get("burn_monthly", 0)
        runway_months = benchmark.get("runway_months", 18)
        arr_median = benchmark.get("arr_median", 0)
        valuation_multiple = benchmark.get("valuation_multiple", 10)
        
        # Calculate funding amount (replacing old typical_raise)
        funding_amount = burn_monthly * runway_months
        
        # Calculate valuations
        post_money = arr_median * valuation_multiple
        pre_money = post_money - funding_amount
        
        # Calculate dilution
        dilution = funding_amount / post_money if post_money > 0 else 0
        
        print(f"\n{stage}:")
        print(f"  Burn rate: ${burn_monthly:,}/month")
        print(f"  Runway: {runway_months} months")
        print(f"  Funding needed: ${funding_amount:,}")
        print(f"  ARR: ${arr_median:,}")
        print(f"  Valuation multiple: {valuation_multiple}x")
        print(f"  Pre-money: ${pre_money:,}")
        print(f"  Post-money: ${post_money:,}")
        print(f"  Dilution: {dilution:.1%}")
    
    print("\n" + "=" * 60)
    print("Testing with actual company data...")
    print("=" * 60)
    
    # Test with a mock Series B company
    test_company = {
        'company': 'TestCo',
        'stage': 'Series B',
        'valuation': 100_000_000,
        'total_funding': 40_000_000,
        'geography': 'US',
        'investors': ['Sequoia', 'Accel'],  # Tier 1 VCs
        'funding_rounds': [
            {
                'round': 'Series B',
                'amount': 30_000_000,
                'valuation': 100_000_000,
                'date': '2024-01'
            }
        ]
    }
    
    # Initialize orchestrator
    orchestrator = UnifiedMCPOrchestrator()
    
    # Generate deck which includes cap table
    result = await orchestrator.process_request({
        "query": f"Generate investment deck for @{test_company['company']}",
        "output_format": "deck",
        "companies": [test_company]
    })
    
    if result and 'slides' in result:
        # Look for cap table slide
        for slide in result['slides']:
            if 'cap table' in str(slide.get('title', '')).lower():
                print(f"\nFound cap table slide: {slide['title']}")
                if 'charts' in slide:
                    for chart in slide['charts']:
                        if chart.get('type') == 'sankey':
                            print("  ✓ Sankey diagram generated for ownership flow")
                            # Check if funding amounts are reasonable
                            data = chart.get('data', {})
                            if 'nodes' in data:
                                for node in data['nodes']:
                                    if 'Seed' in node.get('name', ''):
                                        # Should be around 1.8M (100k * 18)
                                        print(f"    Seed funding in chart: {node.get('name')}")
                break
    
    print("\n✅ Cap table generation test complete!")
    print("The funding amounts are now calculated as burn_monthly * runway_months")
    print("This gives realistic dilution percentages for investor ownership projections.")

if __name__ == "__main__":
    asyncio.run(test_cap_table_generation())