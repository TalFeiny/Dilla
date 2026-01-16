#!/usr/bin/env python3
"""Test if PWERM calculation works after fixing missing fields"""

import asyncio
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

from app.services.valuation_engine_service import ValuationEngineService, ValuationRequest, Stage


async def test_pwerm_calculation():
    """Test PWERM calculation with all stages"""
    
    service = ValuationEngineService()
    
    test_cases = [
        ("Seed Stage", Stage.SEED, 10_000_000, 1.5, 50_000_000),
        ("Series A", Stage.SERIES_A, 20_000_000, 2.0, 100_000_000),
        ("Series B", Stage.SERIES_B, 50_000_000, 1.8, 250_000_000),
        ("Late Stage", Stage.LATE, 100_000_000, 1.3, 1_000_000_000),
    ]
    
    for name, stage, revenue, growth, valuation in test_cases:
        print(f"\n{'='*60}")
        print(f"Testing {name}")
        print(f"{'='*60}")
        
        request = ValuationRequest(
            company_name=f"Test {name} Company",
            stage=stage,
            revenue=revenue,
            growth_rate=growth,
            last_round_valuation=valuation,
            total_raised=valuation * 0.3
        )
        
        try:
            # Generate scenarios
            scenarios = service._generate_exit_scenarios(request)
            print(f"✓ Generated {len(scenarios)} scenarios")
            
            # Test each scenario has required fields
            for i, scenario in enumerate(scenarios):
                assert hasattr(scenario, 'funding_path'), f"Scenario {i} missing funding_path"
                assert hasattr(scenario, 'exit_type'), f"Scenario {i} missing exit_type"
                assert hasattr(scenario, 'moic'), f"Scenario {i} missing moic"
                print(f"  Scenario {i+1}: {scenario.scenario}")
                print(f"    - funding_path: {scenario.funding_path}")
                print(f"    - exit_type: {scenario.exit_type}")
            
            # Test model_cap_table_evolution
            print("\nTesting cap table evolution...")
            our_investment = {
                'amount': 10_000_000,
                'ownership': 0.10
            }
            company_data = {
                'total_funding': valuation * 0.3,
                'stage': stage.name
            }
            
            for scenario in scenarios[:2]:  # Test first 2 scenarios
                service.model_cap_table_evolution(scenario, company_data, our_investment)
                print(f"  ✓ {scenario.scenario}: Cap table modeled successfully")
            
            # Test full PWERM calculation
            print("\nTesting full PWERM calculation...")
            result = await service._calculate_pwerm(request)
            print(f"✓ PWERM calculation successful")
            print(f"  Fair value: ${result.fair_value:,.0f}")
            print(f"  Method: {result.method_used}")
            
        except Exception as e:
            print(f"\n❌ ERROR in {name}: {str(e)}")
            import traceback
            traceback.print_exc()
            return False
    
    print("\n" + "="*60)
    print("✅ ALL TESTS PASSED!")
    print("="*60)
    return True


if __name__ == "__main__":
    success = asyncio.run(test_pwerm_calculation())
    sys.exit(0 if success else 1)
