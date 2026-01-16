#!/usr/bin/env python3
"""
Test script to validate that all hardcoded values have been replaced with service calculations
Tests with real companies to ensure data comes from services, not hardcoded defaults
"""

import asyncio
import json
import logging
from typing import Dict, Any

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def test_company_analysis(company_name: str) -> Dict[str, Any]:
    """Test analysis for a single company"""
    from app.services.unified_mcp_orchestrator import UnifiedMCPOrchestrator
    
    orchestrator = UnifiedMCPOrchestrator()
    
    # Test company fetch with service calculations
    request = {
        "prompt": f"Analyze {company_name}",
        "skills": ["company_fetch", "valuation", "financial_analysis"],
        "context": {
            "companies": [company_name],
            "output_format": "analysis",
            "validate_services": True  # Flag to ensure service usage
        }
    }
    
    result = await orchestrator.process_request(request)
    
    # Validate that data comes from services
    validation_results = {
        "company": company_name,
        "service_data_used": {},
        "hardcoded_values_found": [],
        "warnings": []
    }
    
    if result and "results" in result:
        company_data = result["results"].get("company_fetch", {}).get("companies", [{}])[0]
        
        # Check for service-calculated fields
        service_fields = [
            "inferred_revenue",
            "market_size",
            "pwerm_valuation",
            "ownership_evolution",
            "adjusted_gross_margin"
        ]
        
        for field in service_fields:
            if field in company_data:
                validation_results["service_data_used"][field] = True
                logger.info(f"✅ {company_name}: Found service-calculated {field}")
            else:
                validation_results["warnings"].append(f"Missing service field: {field}")
        
        # Check for suspicious hardcoded patterns
        suspicious_values = {
            "revenue": [500_000, 2_000_000, 10_000_000, 50_000_000],  # Old defaults
            "valuation": [10_000_000, 50_000_000, 200_000_000, 500_000_000],  # Old defaults
            "team_size": [5, 20, 80, 250],  # Old defaults
            "growth_rate": [2.5, 2.0, 1.5, 1.0],  # Old defaults
            "ebitda_margin": [0.3, 0.35, 0.38, 0.4],  # Old hardcoded values
            "exit_multiple": [5.0],  # Old hardcoded value
            "dilution_per_round": [0.20],  # Old hardcoded value
        }
        
        for field, hardcoded_values in suspicious_values.items():
            field_value = company_data.get(field)
            if field_value in hardcoded_values:
                validation_results["hardcoded_values_found"].append({
                    "field": field,
                    "value": field_value,
                    "suspicious": "Matches old hardcoded default"
                })
                logger.warning(f"⚠️ {company_name}: Field '{field}' = {field_value} matches hardcoded default!")
        
        # Validate TAM calculation
        market_data = company_data.get("market_size", {})
        tam = market_data.get("tam", 0)
        sam = market_data.get("sam", 0)
        
        # Check for hardcoded SAM percentages
        if tam > 0 and sam > 0:
            sam_percentage = sam / tam
            hardcoded_percentages = [0.01, 0.05, 0.10, 0.15]  # Old stage-based percentages
            
            if any(abs(sam_percentage - pct) < 0.001 for pct in hardcoded_percentages):
                validation_results["hardcoded_values_found"].append({
                    "field": "sam_percentage",
                    "value": sam_percentage,
                    "suspicious": "Matches old stage-based percentage"
                })
                logger.warning(f"⚠️ {company_name}: SAM/TAM ratio {sam_percentage:.2%} matches hardcoded percentage!")
        
        # Check ownership calculations
        ownership_data = company_data.get("ownership_evolution", {})
        if ownership_data:
            entry_ownership = ownership_data.get("entry_ownership", 0)
            check_size = company_data.get("optimal_check_size", 0)
            valuation = company_data.get("valuation", 0)
            
            # Check for the old 1.2x multiplier
            if valuation > 0 and check_size > 0:
                implied_post_money = check_size / entry_ownership if entry_ownership > 0 else 0
                if abs(implied_post_money - valuation * 1.2) < 1000:
                    validation_results["hardcoded_values_found"].append({
                        "field": "ownership_calculation",
                        "suspicious": "Uses old 1.2x post-money multiplier"
                    })
                    logger.warning(f"⚠️ {company_name}: Ownership calculation appears to use old 1.2x multiplier!")
    
    return validation_results

async def main():
    """Test multiple companies to ensure no hardcoded values"""
    test_companies = [
        "@Mercury",  # Series B fintech
        "@Ramp",     # Series C fintech
        "@Anthropic" # AI company
    ]
    
    print("\n" + "="*80)
    print("TESTING: No Hardcoded Values - All Data From Services")
    print("="*80 + "\n")
    
    all_results = []
    for company in test_companies:
        print(f"\n📊 Testing {company}...")
        print("-" * 40)
        
        try:
            result = await test_company_analysis(company)
            all_results.append(result)
            
            # Print results
            if result["hardcoded_values_found"]:
                print(f"❌ FAILED: Found {len(result['hardcoded_values_found'])} hardcoded values!")
                for item in result["hardcoded_values_found"]:
                    print(f"   - {item['field']}: {item.get('suspicious', 'Hardcoded value detected')}")
            else:
                print(f"✅ PASSED: All data from services!")
            
            if result["service_data_used"]:
                print(f"✓ Service fields found: {list(result['service_data_used'].keys())}")
            
            if result["warnings"]:
                print(f"⚠️ Warnings: {', '.join(result['warnings'])}")
                
        except Exception as e:
            print(f"❌ ERROR testing {company}: {e}")
            logger.error(f"Test failed for {company}", exc_info=True)
    
    # Summary
    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)
    
    total_hardcoded = sum(len(r["hardcoded_values_found"]) for r in all_results)
    total_service_fields = sum(len(r["service_data_used"]) for r in all_results)
    
    if total_hardcoded == 0:
        print(f"✅ SUCCESS: No hardcoded values found across all {len(test_companies)} companies!")
        print(f"✅ Total service-calculated fields used: {total_service_fields}")
    else:
        print(f"❌ FAILURE: Found {total_hardcoded} hardcoded values that need fixing!")
        print(f"⚠️ Service fields used: {total_service_fields}")
    
    # Save detailed results
    with open("test_no_hardcoded_results.json", "w") as f:
        json.dump(all_results, f, indent=2, default=str)
        print(f"\n📝 Detailed results saved to test_no_hardcoded_results.json")

if __name__ == "__main__":
    asyncio.run(main())