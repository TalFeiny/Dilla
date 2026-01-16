#!/usr/bin/env python3
"""
Test script to verify comprehensive PWERM integration in ValuationEngineService
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))

from backend.app.services.valuation_engine_service import ValuationEngineService, ValuationRequest, Stage, ValuationMethod

async def test_pwerm_integration():
    """Test that the comprehensive PWERM integration works correctly"""
    
    # Create a test request
    request = ValuationRequest(
        company_name="Test Company",
        stage=Stage.SERIES_A,
        revenue=5_000_000,
        growth_rate=1.5,
        last_round_valuation=50_000_000,
        total_raised=10_000_000,
        business_model="saas",
        method=ValuationMethod.PWERM
    )
    
    # Initialize the service
    service = ValuationEngineService()
    
    try:
        # Test the exit scenarios generation
        print("Testing comprehensive PWERM integration...")
        scenarios = service._generate_exit_scenarios(request)
        
        print(f"Generated {len(scenarios)} scenarios:")
        for i, scenario in enumerate(scenarios[:5]):  # Show first 5
            print(f"  {i+1}. {scenario.scenario} - {scenario.probability:.1%} - ${scenario.exit_value:,.0f}")
        
        # Test the full valuation
        print("\nTesting full valuation...")
        result = await service.calculate_valuation(request)
        
        print(f"Valuation result: ${result.fair_value:,.0f}")
        print(f"Confidence: {result.confidence:.1%}")
        print(f"Methodology: {result.explanation}")
        
        print("\n✅ PWERM integration test passed!")
        return True
        
    except Exception as e:
        print(f"❌ PWERM integration test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    import asyncio
    success = asyncio.run(test_pwerm_integration())
    sys.exit(0 if success else 1)
