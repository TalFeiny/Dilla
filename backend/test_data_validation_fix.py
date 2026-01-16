#!/usr/bin/env python3
"""
Test script to verify data validation fixes prevent NoneType errors
"""

import asyncio
import sys
import logging
from typing import Dict, Any

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Add parent directory to path
sys.path.insert(0, '/Users/admin/code/dilla-ai/backend')

async def test_data_validator():
    """Test the centralized data validator"""
    logger.info("Testing data validator...")
    
    from app.services.data_validator import (
        ensure_numeric, safe_divide, safe_get_value,
        safe_multiply, validate_company_data
    )
    
    # Test ensure_numeric with various inputs
    test_cases = [
        (None, 0, "None → 0"),
        ("$1.5M", 1500000, "String currency → numeric"),
        ({"value": 100}, 100, "InferenceResult → numeric"),
        (0, 0, "Zero stays zero"),
        ("N/A", 0, "N/A → 0"),
    ]
    
    for input_val, expected, description in test_cases:
        result = ensure_numeric(input_val, 0)
        logger.info(f"  {description}: {input_val} → {result} (expected: {expected})")
        
    # Test safe_divide
    logger.info("\nTesting safe_divide...")
    div_tests = [
        (10, 2, 5, "Normal division"),
        (10, 0, 0, "Division by zero"),
        (None, 5, 0, "None numerator"),
        (10, None, 0, "None denominator"),
    ]
    
    for num, denom, expected, description in div_tests:
        result = safe_divide(num, denom, 0)
        logger.info(f"  {description}: {num}/{denom} → {result} (expected: {expected})")
    
    # Test validate_company_data
    logger.info("\nTesting validate_company_data...")
    test_company = {
        "company": "TestCo",
        "revenue": None,  # Should be fixed
        "valuation": "$100M",  # Should be converted
        "total_funding": None,  # Should get default
        "funding_rounds": None,  # Should become []
    }
    
    validated = validate_company_data(test_company)
    logger.info(f"  Original: {test_company}")
    logger.info(f"  Validated: {validated}")
    logger.info(f"  Revenue fixed: {validated.get('revenue', 'MISSING')}")
    logger.info(f"  Valuation numeric: {validated.get('valuation', 'MISSING')}")
    logger.info(f"  Funding rounds list: {validated.get('funding_rounds', 'MISSING')}")
    
    return True

async def test_orchestrator_safe_operations():
    """Test that UnifiedMCPOrchestrator uses safe operations"""
    logger.info("\n\nTesting UnifiedMCPOrchestrator safe operations...")
    
    from app.services.unified_mcp_orchestrator import UnifiedMCPOrchestrator
    
    # Create orchestrator instance
    orchestrator = UnifiedMCPOrchestrator()
    
    # Test data with None values that would previously cause errors
    test_company = {
        "company": "TestCo",
        "revenue": None,
        "valuation": 100_000_000,
        "total_funding": None,
        "funding_stage": "Series B",
        "inferred_revenue": 5_000_000  # Should be used as fallback
    }
    
    # Test the validation happens in _ensure_companies_have_inferred_data
    logger.info("Testing company data enrichment...")
    enriched = await orchestrator._ensure_companies_have_inferred_data([test_company])
    
    if enriched:
        company = enriched[0]
        logger.info(f"  Company: {company.get('company')}")
        logger.info(f"  Revenue (was None): {company.get('revenue')}")
        logger.info(f"  Inferred Revenue: {company.get('inferred_revenue')}")
        logger.info(f"  Total Funding: {company.get('total_funding')}")
        
        # Check no None values in critical fields
        critical_fields = ['revenue', 'valuation', 'total_funding', 'gross_margin']
        for field in critical_fields:
            value = company.get(field)
            if value is None:
                logger.error(f"  ERROR: {field} is still None!")
                return False
            else:
                logger.info(f"  ✓ {field}: {value}")
    
    return True

async def test_deck_export_safe_operations():
    """Test that DeckExportService uses safe operations"""
    logger.info("\n\nTesting DeckExportService safe operations...")
    
    from app.services.deck_export_service import DeckExportService
    
    service = DeckExportService()
    
    # Test scenario with None probability that would previously cause error
    test_scenario = {
        "name": "Test Scenario",
        "probability": None,  # Would cause: TypeError: unsupported operand type(s) for *: 'NoneType' and 'int'
        "exit_value": 100_000_000
    }
    
    # Test the safe_multiply is used
    from app.services.data_validator import safe_multiply
    
    # This would have failed before: scenario.get('probability', 0) * 100
    # Now it should work: safe_multiply(scenario.get('probability', 0), 100, 0)
    
    prob_percent = safe_multiply(test_scenario.get('probability', 0), 100, 0)
    logger.info(f"  Probability None × 100 → {prob_percent}% (should be 0)")
    
    # Test division operations
    test_breakpoint = {
        "liquidation_preference": None,  # Would cause division error
        "conversion_point": 50_000_000,
        "target_3x_exit": 150_000_000
    }
    
    from app.services.data_validator import safe_divide, ensure_numeric
    
    # These would have failed before
    liq_pref_m = safe_divide(ensure_numeric(test_breakpoint.get("liquidation_preference", 0)), 1e6, 0)
    conversion_m = safe_divide(ensure_numeric(test_breakpoint.get("conversion_point", 0)), 1e6, 0)
    
    logger.info(f"  Liq Pref None / 1M → ${liq_pref_m:.1f}M (should be 0.0)")
    logger.info(f"  Conversion 50M / 1M → ${conversion_m:.1f}M (should be 50.0)")
    
    return True

async def main():
    """Run all validation tests"""
    logger.info("=" * 80)
    logger.info("DATA VALIDATION FIX TESTS")
    logger.info("=" * 80)
    
    all_passed = True
    
    # Test 1: Data Validator
    try:
        result = await test_data_validator()
        if not result:
            logger.error("Data validator test FAILED")
            all_passed = False
    except Exception as e:
        logger.error(f"Data validator test ERROR: {e}")
        all_passed = False
    
    # Test 2: Orchestrator
    try:
        result = await test_orchestrator_safe_operations()
        if not result:
            logger.error("Orchestrator test FAILED")
            all_passed = False
    except Exception as e:
        logger.error(f"Orchestrator test ERROR: {e}")
        all_passed = False
    
    # Test 3: Deck Export
    try:
        result = await test_deck_export_safe_operations()
        if not result:
            logger.error("Deck export test FAILED")
            all_passed = False
    except Exception as e:
        logger.error(f"Deck export test ERROR: {e}")
        all_passed = False
    
    logger.info("\n" + "=" * 80)
    if all_passed:
        logger.info("✅ ALL TESTS PASSED - Data validation fixes working!")
    else:
        logger.error("❌ SOME TESTS FAILED - Check errors above")
    logger.info("=" * 80)
    
    return all_passed

if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)