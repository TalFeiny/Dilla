#!/usr/bin/env python3
"""
Test script to verify that the model fixes are working properly.
This tests the key issues:
1. Safe getters preventing None/zero values
2. Proper data flow from IntelligentGapFiller
3. Deck generation with proper slides
"""

import asyncio
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.services.unified_mcp_orchestrator import UnifiedMCPOrchestrator

async def test_model_fixes():
    """Test the key fixes for the model issues"""
    print("🧪 Testing Model Fixes...")
    
    # Initialize orchestrator
    orchestrator = UnifiedMCPOrchestrator()
    
    # Test 1: Safe getters
    print("\n1️⃣ Testing Safe Getters...")
    test_company = {
        "company": "TestCorp",
        "revenue": None,  # This should trigger inferred_revenue lookup
        "inferred_revenue": 5000000,  # This should be used
        "valuation": 0,  # This should trigger inferred_valuation lookup
        "inferred_valuation": 50000000,  # This should be used
        "total_funding": None,
        "inferred_total_funding": 10000000
    }
    
    # Test safe getters
    revenue = orchestrator._get_field_safe(test_company, 'revenue')
    valuation = orchestrator._get_field_safe(test_company, 'valuation')
    funding = orchestrator._get_field_safe(test_company, 'total_funding')
    
    print(f"   Revenue: {revenue} (should be 5000000)")
    print(f"   Valuation: {valuation} (should be 50000000)")
    print(f"   Funding: {funding} (should be 10000000)")
    
    # Verify safe getters work
    assert revenue == 5000000, f"Expected 5000000, got {revenue}"
    assert valuation == 50000000, f"Expected 50000000, got {valuation}"
    assert funding == 10000000, f"Expected 10000000, got {funding}"
    print("   ✅ Safe getters working correctly!")
    
    # Test 2: Safe division
    print("\n2️⃣ Testing Safe Division...")
    result1 = orchestrator._safe_divide(100, 0)  # Should return 0, not crash
    result2 = orchestrator._safe_divide(100, None)  # Should return 0, not crash
    result3 = orchestrator._safe_divide(100, 10)  # Should return 10
    
    print(f"   100/0: {result1} (should be 0)")
    print(f"   100/None: {result2} (should be 0)")
    print(f"   100/10: {result3} (should be 10)")
    
    assert result1 == 0, f"Expected 0, got {result1}"
    assert result2 == 0, f"Expected 0, got {result2}"
    assert result3 == 10, f"Expected 10, got {result3}"
    print("   ✅ Safe division working correctly!")
    
    # Test 3: Deck generation with proper data
    print("\n3️⃣ Testing Deck Generation...")
    
    # Create test companies with proper data
    test_companies = [
        {
            "company": "TestCorp1",
            "revenue": None,  # This should trigger inferred_revenue
            "inferred_revenue": 5000000,
            "valuation": None,  # This should trigger inferred_valuation
            "inferred_valuation": 50000000,
            "total_funding": None,  # This should trigger inferred_total_funding
            "inferred_total_funding": 10000000,
            "stage": "Series A",
            "business_model": "SaaS",
            "market_size": {
                "tam": 10000000000,  # $10B TAM
                "sam": 2000000000,   # $2B SAM
                "som": 200000000     # $200M SOM
            },
            "fund_fit_score": 75,
            "optimal_check_size": 5000000,
            "funding_rounds": [  # Add funding rounds to trigger valuation inference
                {
                    "round": "Series A",
                    "amount": 10000000,
                    "date": "2023-01-01"
                }
            ]
        },
        {
            "company": "TestCorp2", 
            "revenue": None,  # This should trigger inferred_revenue
            "inferred_revenue": 8000000,
            "valuation": None,  # This should trigger inferred_valuation
            "inferred_valuation": 80000000,
            "total_funding": None,  # This should trigger inferred_total_funding
            "inferred_total_funding": 15000000,
            "stage": "Series B",
            "business_model": "AI SaaS",
            "market_size": {
                "tam": 15000000000,  # $15B TAM
                "sam": 3000000000,   # $3B SAM
                "som": 300000000     # $300M SOM
            },
            "fund_fit_score": 80,
            "optimal_check_size": 8000000,
            "funding_rounds": [  # Add funding rounds to trigger valuation inference
                {
                    "round": "Series B",
                    "amount": 20000000,
                    "date": "2023-06-01"
                }
            ]
        }
    ]
    
    # Set up shared data
    orchestrator.shared_data["companies"] = test_companies
    orchestrator.shared_data["fund_context"] = {
        "fund_size": 78000000,
        "remaining_capital": 50000000,
        "typical_check_size": 5000000
    }
    
    # Test deck generation
    try:
        deck_result = await orchestrator._execute_deck_generation({"test": True})
        
        print(f"   Deck format: {deck_result.get('format')}")
        print(f"   Slide count: {deck_result.get('slide_count', len(deck_result.get('slides', [])))}")
        print(f"   Slides type: {type(deck_result.get('slides'))}")
        
        if deck_result.get('slides'):
            slide_types = [slide.get('template', slide.get('type', 'unknown')) for slide in deck_result['slides']]
            print(f"   Slide types: {slide_types}")
        
        # Verify deck generation worked
        assert deck_result.get('format') == 'deck', f"Expected 'deck' format, got {deck_result.get('format')}"
        assert deck_result.get('slides'), "Expected slides to be generated"
        assert len(deck_result['slides']) > 0, "Expected at least one slide"
        
        print("   ✅ Deck generation working correctly!")
        
    except Exception as e:
        print(f"   ❌ Deck generation failed: {e}")
        raise
    
    print("\n🎉 All tests passed! Model fixes are working correctly.")
    return True

if __name__ == "__main__":
    asyncio.run(test_model_fixes())
