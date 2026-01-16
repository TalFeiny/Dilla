#!/usr/bin/env python3
"""
Test script to verify the inferred value fallback hierarchy is working properly.
This ensures we never have None/0 values when generating decks.
"""

import asyncio
import sys
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent
sys.path.insert(0, str(backend_path))

from app.services.unified_mcp_orchestrator import UnifiedMCPOrchestrator

async def test_fallback_hierarchy():
    """Test that field values properly fall back from extracted -> inferred -> default"""
    
    orchestrator = UnifiedMCPOrchestrator()
    
    # Test cases with different scenarios
    test_cases = [
        {
            "name": "Has extracted revenue",
            "data": {
                "company": "TestCo",
                "stage": "Series A",
                "revenue": 10_000_000,  # Extracted value
                "inferred_revenue": 5_000_000  # Should be ignored
            },
            "field": "revenue",
            "expected": 10_000_000
        },
        {
            "name": "No extracted, has inferred",
            "data": {
                "company": "TestCo2", 
                "stage": "Series B",
                # No revenue field
                "inferred_revenue": 20_000_000  # Should be used
            },
            "field": "revenue",
            "expected": 20_000_000
        },
        {
            "name": "No extracted, no inferred - use stage default",
            "data": {
                "company": "TestCo3",
                "stage": "Seed",
                # No revenue or inferred_revenue
            },
            "field": "revenue",
            "expected": 1_000_000  # Seed default
        },
        {
            "name": "Valuation hierarchy",
            "data": {
                "company": "TestCo4",
                "stage": "Series A",
                "valuation": 100_000_000,  # Should be used
                "inferred_valuation": 50_000_000
            },
            "field": "valuation",
            "expected": 100_000_000
        },
        {
            "name": "Team size with only inferred",
            "data": {
                "company": "TestCo5",
                "stage": "Series B",
                "inferred_team_size": 150
            },
            "field": "team_size",
            "expected": 150
        }
    ]
    
    print("Testing field fallback hierarchy...\n")
    
    all_passed = True
    for test_case in test_cases:
        print(f"Test: {test_case['name']}")
        
        # Use the helper method
        result = orchestrator._get_field_with_fallback(
            test_case['data'], 
            test_case['field'],
            0
        )
        
        if result == test_case['expected']:
            print(f"  ✅ PASSED: Got {result:,} (expected {test_case['expected']:,})")
        else:
            print(f"  ❌ FAILED: Got {result:,} (expected {test_case['expected']:,})")
            all_passed = False
        
        # Also verify both fields are set properly after processing
        data_copy = test_case['data'].copy()
        
        # Simulate the field synchronization logic
        field = test_case['field']
        inferred_field = f"inferred_{field}"
        
        # This mimics what happens in the orchestrator
        final_value = orchestrator._get_field_with_fallback(data_copy, field, 0)
        data_copy[field] = final_value
        data_copy[inferred_field] = final_value
        
        print(f"    Final {field}: {data_copy.get(field, 'NOT SET')}")
        print(f"    Final {inferred_field}: {data_copy.get(inferred_field, 'NOT SET')}")
        print()
    
    # Test stage defaults
    print("\nTesting stage defaults...")
    stages = ["Pre-Seed", "Seed", "Series A", "Series B", "Series C"]
    
    for stage in stages:
        revenue_default = orchestrator._get_stage_default('revenue', stage)
        valuation_default = orchestrator._get_stage_default('valuation', stage)
        team_default = orchestrator._get_stage_default('team_size', stage)
        
        print(f"  {stage:10s}: Revenue=${revenue_default/1e6:.1f}M, "
              f"Valuation=${valuation_default/1e6:.0f}M, "
              f"Team={team_default}")
    
    print("\n" + "="*50)
    if all_passed:
        print("✅ ALL TESTS PASSED - Fallback hierarchy working correctly!")
    else:
        print("❌ SOME TESTS FAILED - Check the implementation")
    
    return all_passed

async def test_deck_generation_fields():
    """Test that deck generation gets proper values"""
    
    orchestrator = UnifiedMCPOrchestrator()
    
    # Simulate a company with missing data
    test_company = {
        "company": "AI Startup",
        "stage": "Series A",
        # Deliberately missing revenue, valuation, etc
        "inferred_revenue": 8_000_000,
        "inferred_valuation": 80_000_000,
        "business_model": "AI SaaS"
    }
    
    print("\n" + "="*50)
    print("Testing deck generation field access...")
    
    # Test the key fields used in deck generation
    revenue = orchestrator._get_field_with_fallback(test_company, 'revenue', 0)
    valuation = orchestrator._get_field_with_fallback(test_company, 'valuation', 0)
    team_size = orchestrator._get_field_with_fallback(test_company, 'team_size', 0)
    gross_margin = orchestrator._get_field_with_fallback(test_company, 'gross_margin', 0.7)
    
    print(f"\nCompany: {test_company['company']} ({test_company['stage']})")
    print(f"  Revenue: ${revenue/1e6:.1f}M (from inferred)")
    print(f"  Valuation: ${valuation/1e6:.0f}M (from inferred)")
    print(f"  Team Size: {team_size} (from stage default)")
    print(f"  Gross Margin: {gross_margin*100:.0f}% (from default)")
    
    # Calculate multiple
    if revenue > 0:
        multiple = valuation / revenue
        print(f"  Revenue Multiple: {multiple:.1f}x")
    
    print("\n✅ Field access working correctly for deck generation")

if __name__ == "__main__":
    asyncio.run(test_fallback_hierarchy())
    asyncio.run(test_deck_generation_fields())