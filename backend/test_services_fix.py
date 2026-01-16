#!/usr/bin/env python3
"""Test that valuation engine, PWERM, and cap table services work with inferred data"""

import asyncio
import logging
from app.services.unified_mcp_orchestrator import UnifiedMCPOrchestrator
from app.services.valuation_engine_service import ValuationEngineService, Stage, ValuationRequest
from app.services.pre_post_cap_table import PrePostCapTable

logging.basicConfig(level=logging.INFO)

async def test_services():
    print("Testing services with inferred data...")
    
    # Initialize services
    orchestrator = UnifiedMCPOrchestrator()
    valuation_engine = ValuationEngineService()
    cap_table_service = PrePostCapTable()
    
    # Test 1: Stage enum mapping
    print("\n1. Testing Stage enum mapping:")
    test_stages = ['Series A', 'Series D', 'Series E', 'Series F']
    for stage_str in test_stages:
        enum_val = orchestrator._get_stage_enum(stage_str)
        print(f"  {stage_str} -> {enum_val}")
    
    # Test 2: ValuationRequest with proper field access
    print("\n2. Testing ValuationRequest with _get_field_safe:")
    test_company = {
        "company": "TestCo",
        "stage": "Series B",
        "revenue": None,  # Missing real value
        "inferred_revenue": 5_000_000,  # Has inferred value
        "valuation": 50_000_000,  # Has real value
        "inferred_valuation": 40_000_000,  # Also has inferred (real should win)
        "growth_rate": None,
        "inferred_growth_rate": 1.5
    }
    
    # Test _get_field_safe
    revenue = orchestrator._get_field_safe(test_company, "revenue")
    valuation = orchestrator._get_field_safe(test_company, "valuation")
    growth_rate = orchestrator._get_field_safe(test_company, "growth_rate", 1.0)
    
    print(f"  Revenue: {revenue:,.0f} (should be 5M from inferred)")
    print(f"  Valuation: {valuation:,.0f} (should be 50M from real)")
    print(f"  Growth rate: {growth_rate} (should be 1.5 from inferred)")
    
    # Test 3: ValuationRequest creation
    print("\n3. Testing ValuationRequest creation:")
    val_request = ValuationRequest(
        company_name="TestCo",
        stage=orchestrator._get_stage_enum(test_company["stage"]),
        revenue=revenue,
        growth_rate=growth_rate,
        last_round_valuation=valuation,
        total_raised=20_000_000
    )
    print(f"  Created: {val_request}")
    
    # Test 4: Valuation calculation
    print("\n4. Testing valuation calculation:")
    try:
        val_result = await valuation_engine.calculate_valuation(val_request)
        print(f"  Fair value: ${val_result.fair_value:,.0f}")
        print(f"  Method: {val_result.method_used}")
        print(f"  Has scenarios: {bool(val_result.scenarios)}")
    except Exception as e:
        print(f"  Error: {e}")
    
    # Test 5: Cap table with synthetic funding rounds
    print("\n5. Testing cap table with synthetic rounds:")
    test_company["funding_rounds"] = orchestrator.gap_filler.generate_stage_based_funding_rounds(test_company)
    print(f"  Generated {len(test_company['funding_rounds'])} synthetic rounds")
    
    try:
        cap_table_result = cap_table_service.calculate_full_cap_table_history(test_company)
        if cap_table_result:
            print(f"  Cap table history: {len(cap_table_result.get('history', []))} rounds")
            print(f"  Has ownership evolution: {bool(cap_table_result.get('ownership_evolution'))}")
        else:
            print("  Cap table returned None")
    except Exception as e:
        print(f"  Error: {e}")
    
    print("\n✅ All tests completed!")

if __name__ == "__main__":
    asyncio.run(test_services())