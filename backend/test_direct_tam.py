#!/usr/bin/env python3
"""Test TAM calculation directly"""

import traceback
from app.services.intelligent_gap_filler import IntelligentGapFiller

def test_tam_directly():
    """Test TAM calculation directly with Mercury data"""
    
    gap_filler = IntelligentGapFiller()
    
    # Simulate Mercury's extracted data with null labor fields
    company_data = {
        'company': 'Mercury',
        'business_model': 'Digital banking platform',
        'sector': 'FinTech',
        'revenue': 250000,
        'labor_statistics': {
            'number_of_workers': None,  # This is the problem!
            'avg_salary_per_role': None,
            'labor_citation': '',
            'total_addressable_labor_spend': None
        }
    }
    
    try:
        result = gap_filler.calculate_market_opportunity(
            company_data,
            search_content="Mercury is a digital banking platform..."
        )
        print(f"✅ TAM calculation succeeded")
        if result and "tam_calculation" in result:
            print(f"  TAM: ${result['tam_calculation']['tam']:,.0f}")
        return True
        
    except Exception as e:
        print(f"❌ TAM calculation failed: {e}")
        print("\nFull traceback:")
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_tam_directly()
    exit(0 if success else 1)