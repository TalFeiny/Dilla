#!/usr/bin/env python3
"""
Test script to verify cap table functionality
"""

import asyncio
import json
from app.services.pre_post_cap_table import PrePostCapTable

async def test_cap_table():
    """Test cap table with sample data"""
    
    cap_table = PrePostCapTable()
    
    # Test case 1: Valid funding rounds
    test_data_1 = {
        "funding_rounds": [
            {
                "round": "Seed",
                "amount": 2000000,
                "date": "2022-01-01",
                "investors": ["Seed VC", "Angel Investor"],
                "lead_investor": "Seed VC",
                "pre_money_valuation": 8000000
            },
            {
                "round": "Series A",
                "amount": 10000000,
                "date": "2023-01-01",
                "investors": ["Series A Lead", "Follow-on Fund"],
                "lead_investor": "Series A Lead",
                "pre_money_valuation": 40000000
            }
        ]
    }
    
    print("Test 1: Valid funding rounds")
    print("-" * 50)
    result1 = cap_table.calculate_full_cap_table_history(test_data_1)
    print(f"Number of rounds processed: {result1['num_rounds']}")
    print(f"Total raised: ${result1['total_raised']:,.0f}")
    print(f"Founder dilution: {result1['founder_dilution']:.1f}%")
    print(f"Current cap table: {json.dumps(result1['current_cap_table'], indent=2)}")
    print()
    
    # Test case 2: Empty funding rounds
    test_data_2 = {
        "funding_rounds": []
    }
    
    print("Test 2: Empty funding rounds")
    print("-" * 50)
    result2 = cap_table.calculate_full_cap_table_history(test_data_2)
    print(f"Number of rounds processed: {result2['num_rounds']}")
    print(f"Current cap table: {json.dumps(result2['current_cap_table'], indent=2)}")
    print()
    
    # Test case 3: Invalid/partial data
    test_data_3 = {
        "funding_rounds": [
            {
                "round": "Seed",
                "amount": 0,  # Invalid amount
                "investors": ["Test VC"]
            },
            {
                "round": "Series A",
                "amount": 5000000,  # Valid
                "investors": ["Series A VC"]
            }
        ]
    }
    
    print("Test 3: Partial/invalid data")
    print("-" * 50)
    result3 = cap_table.calculate_full_cap_table_history(test_data_3)
    print(f"Number of rounds processed: {result3['num_rounds']}")
    print(f"Total raised: ${result3['total_raised']:,.0f}")
    print(f"Current cap table: {json.dumps(result3['current_cap_table'], indent=2)}")
    print()
    
    # Test case 4: Direct list of rounds (not wrapped)
    test_data_4 = [
        {
            "round": "Pre-seed",
            "amount": 500000,
            "investors": ["Angel"]
        }
    ]
    
    print("Test 4: Direct list (unwrapped)")
    print("-" * 50)
    result4 = cap_table.calculate_full_cap_table_history(test_data_4)
    print(f"Number of rounds processed: {result4['num_rounds']}")
    print(f"Total raised: ${result4['total_raised']:,.0f}")
    print(f"Current cap table: {json.dumps(result4['current_cap_table'], indent=2)}")
    
    print("\n✅ All cap table tests completed successfully!")

if __name__ == "__main__":
    asyncio.run(test_cap_table())