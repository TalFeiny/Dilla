#!/usr/bin/env python3
"""
Test script to verify business model detection in the unified MCP orchestrator
"""
import asyncio
import json
from app.services.unified_mcp_orchestrator import UnifiedMCPOrchestrator

async def test_business_model_detection():
    """Test that business model is properly detected for different company types"""
    
    print("Testing Business Model Detection")
    print("=" * 50)
    
    orchestrator = UnifiedMCPOrchestrator()
    
    # Test companies with different business models
    test_cases = [
        {
            "company": "@Societies",  # AI SaaS - market research platform
            "expected_model": "AI SaaS",
            "description": "AI-powered market research platform"
        },
        {
            "company": "@Dwelly",  # Roll-up Model - acquiring lettings agencies
            "expected_model": "Roll-up Model", 
            "description": "Acquiring and consolidating lettings agencies"
        },
        {
            "company": "@Airbnb",  # Marketplace
            "expected_model": "Marketplace",
            "description": "Two-sided platform connecting hosts and guests"
        },
        {
            "company": "@Stripe",  # API/Infrastructure
            "expected_model": "API/Infrastructure",
            "description": "Payment infrastructure for developers"
        }
    ]
    
    for test_case in test_cases:
        print(f"\nTesting {test_case['company']} - {test_case['description']}")
        print("-" * 40)
        
        try:
            # Process request with company data fetcher skill
            result = await orchestrator.process_request(
                prompt=f"Analyze {test_case['company']}",
                output_format="analysis",
                context={}
            )
            
            # Check if business_model is in the result
            if 'skills_executed' in result:
                for skill in result['skills_executed']:
                    if skill.get('skill') == 'company-data-fetcher':
                        companies = skill.get('result', {}).get('companies', [])
                        if companies:
                            company_data = companies[0]
                            business_model = company_data.get('business_model', {})
                            
                            print(f"Detected Model: {business_model.get('model_type', 'Not detected')}")
                            print(f"Expected Model: {test_case['expected_model']}")
                            print(f"Confidence: {business_model.get('confidence', 'N/A')}")
                            print(f"Reasoning: {business_model.get('reasoning', 'N/A')}")
                            print(f"Valuation Impact: {business_model.get('valuation_impact', 'N/A')}")
                            
                            # Check if it matches expected
                            if business_model.get('model_type') == test_case['expected_model']:
                                print("✅ PASS - Correct business model detected")
                            else:
                                print("❌ FAIL - Incorrect business model detected")
                        else:
                            print("❌ No company data found")
            
        except Exception as e:
            print(f"❌ Error testing {test_case['company']}: {e}")
    
    print("\n" + "=" * 50)
    print("Business Model Detection Test Complete")

if __name__ == "__main__":
    asyncio.run(test_business_model_detection())