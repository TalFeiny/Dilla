#!/usr/bin/env python3
"""Test that the output quality fixes are working"""

import asyncio
import json
from app.services.unified_mcp_orchestrator import UnifiedMCPOrchestrator

async def test_output_quality():
    orch = UnifiedMCPOrchestrator()
    
    print("=" * 80)
    print("TESTING OUTPUT QUALITY FIXES")
    print("=" * 80)
    print("\nTesting with two different companies to verify:")
    print("1. TAM values are different (not all $210B)")
    print("2. Categories are specific (not all 'saas')")
    print("3. Business models are descriptive")
    print("=" * 80)
    
    # Test with two different companies
    test_companies = ["@Mercury", "@Anthropic"]
    
    for company_name in test_companies:
        print(f"\n🔍 Testing {company_name}:")
        print("-" * 40)
        
        # Fetch company data
        result = await orch._execute_company_fetch({"company": company_name})
        
        if result and "companies" in result:
            company = result["companies"][0]
            
            # Check TAM
            tam = company.get("tam", 0)
            tam_source = company.get("tam_source", "")
            tam_citation = company.get("tam_citation", "")
            
            print(f"TAM: ${tam/1e9:.1f}B")
            if tam_source:
                print(f"TAM Source: {tam_source}")
            if tam_citation:
                print(f"TAM Citation: {tam_citation[:100]}...")
                
            # Check if TAM is the generic $210B
            if abs(tam - 210_000_000_000) < 1_000_000_000:  # Within $1B of $210B
                print("⚠️ WARNING: TAM is still the generic $210B!")
            else:
                print("✅ TAM is specific to this company")
            
            # Check category
            category = company.get("category", "")
            print(f"\nCategory: {category}")
            if category == "saas":
                print("⚠️ WARNING: Category is still generic 'saas'!")
            else:
                print("✅ Category is specific")
            
            # Check business model
            business_model = company.get("business_model", "")
            what_they_do = company.get("what_they_do", "")
            print(f"\nBusiness Model: {business_model}")
            print(f"What They Do: {what_they_do}")
            
            if business_model == "SaaS" or not business_model:
                print("⚠️ WARNING: Business model is generic or missing!")
            else:
                print("✅ Business model is descriptive")
            
            # Check vertical/sector
            vertical = company.get("vertical", "")
            sector = company.get("sector", "")
            print(f"\nVertical: {vertical}")
            print(f"Sector: {sector}")
            
            # Check GPU cost ratio for AI companies
            if "ai" in category.lower():
                gpu_cost_ratio = company.get("gpu_cost_ratio", 0)
                print(f"\nGPU Cost Ratio: {gpu_cost_ratio*100:.1f}%")
                if abs(gpu_cost_ratio - 3.6) < 0.01:  # 360%
                    print("⚠️ WARNING: GPU cost ratio is still the generic 360%!")
                else:
                    print("✅ GPU cost ratio is specific to this company")
        else:
            print(f"❌ Failed to fetch data for {company_name}")
    
    print("\n" + "=" * 80)
    print("TEST COMPLETE - Check results above")
    print("=" * 80)

if __name__ == "__main__":
    asyncio.run(test_output_quality())