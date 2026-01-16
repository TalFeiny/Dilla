#!/usr/bin/env python3
"""Test that business model extraction avoids buzzwords"""

import asyncio
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.unified_mcp_orchestrator import UnifiedMCPOrchestrator

async def test_extraction():
    """Test extraction with companies that often get misclassified"""
    
    orchestrator = UnifiedMCPOrchestrator()
    
    # Test companies that should NOT have "AI-powered platform" descriptions
    test_cases = [
        {
            "company": "@CoreWeave",
            "expected_not_contain": ["AI-powered", "platform", "SaaS"],
            "should_contain": ["data center", "GPU", "infrastructure"],
            "category": "infrastructure"  # They operate infrastructure, not AI
        },
        {
            "company": "@Cursor",  
            "expected_not_contain": ["AI-powered platform"],  # Too generic
            "should_contain": ["code", "IDE", "editor"],
            "category": "ai_first"  # Heavy GPU use for code generation
        },
        {
            "company": "@Dilla",
            "expected_not_contain": ["AI-powered platform"],
            "should_contain": ["valuation", "venture", "analysis"],
            "category": "ai_saas"  # SaaS that uses AI
        }
    ]
    
    for test in test_cases:
        print(f"\nTesting {test['company']}...")
        
        result = await orchestrator.process_request({
            "prompt": f"Analyze {test['company']}",
            "output_format": "analysis",
            "skills": ["company_fetch"]
        })
        
        companies = result.get("companies", [])
        if companies:
            company = companies[0]
            business_model = company.get("business_model", "").lower()
            category = company.get("category", "")
            
            print(f"  Business Model: {business_model}")
            print(f"  Category: {category}")
            
            # Check for unwanted buzzwords
            issues = []
            for term in test["expected_not_contain"]:
                if term.lower() in business_model:
                    issues.append(f"❌ Contains '{term}' (should be avoided)")
            
            # Check for expected terms
            found_expected = False
            for term in test["should_contain"]:
                if term.lower() in business_model:
                    found_expected = True
                    print(f"  ✓ Contains expected term '{term}'")
                    break
            
            if not found_expected:
                issues.append(f"⚠️  Missing expected terms: {test['should_contain']}")
            
            if category != test["category"]:
                issues.append(f"❌ Wrong category: {category} (expected {test['category']})")
            
            if issues:
                print("  Issues found:")
                for issue in issues:
                    print(f"    {issue}")
            else:
                print("  ✅ Extraction looks good!")

if __name__ == "__main__":
    asyncio.run(test_extraction())