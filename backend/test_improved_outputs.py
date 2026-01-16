#!/usr/bin/env python3
"""Test that outputs are improved with specific TAM and business models"""

import asyncio
import json
from app.services.unified_mcp_orchestrator import UnifiedMCPOrchestrator

async def test_improved_outputs():
    orch = UnifiedMCPOrchestrator()
    
    print("=" * 80)
    print("TESTING IMPROVED OUTPUT QUALITY")
    print("=" * 80)
    
    # Test just one company for speed
    company_name = "@Anthropic"
    
    print(f"\n🔍 Testing {company_name}:")
    print("-" * 40)
    
    # Fetch company data
    result = await orch._execute_company_fetch({"company": company_name})
    
    if result and "companies" in result:
        company = result["companies"][0]
        
        # Check key improvements
        print("\n📊 KEY METRICS:")
        print(f"Business Model: {company.get('business_model', 'MISSING')}")
        print(f"What They Do: {company.get('what_they_do', 'MISSING')}")
        print(f"Category: {company.get('category', 'MISSING')}")
        print(f"Vertical: {company.get('vertical', 'MISSING')}")
        
        # Check TAM
        tam = company.get("tam", 0)
        tam_source = company.get("tam_source", "")
        print(f"\nTAM: ${tam/1e9:.1f}B")
        if tam_source:
            print(f"TAM Source: {tam_source}")
        
        # Check for generic values
        issues = []
        if abs(tam - 210_000_000_000) < 1_000_000_000:
            issues.append("TAM is still generic $210B")
        if tam == 50_000_000_000:
            issues.append("TAM is generic $50B estimate")
        if company.get("category") == "saas":
            issues.append("Category is generic 'saas'")
        if not company.get("business_model") or company.get("business_model") == "SaaS":
            issues.append("Business model is missing or generic")
        
        if issues:
            print("\n⚠️ ISSUES:")
            for issue in issues:
                print(f"  - {issue}")
        else:
            print("\n✅ All metrics look specific and good!")
        
        # Show software market data if extracted
        if company.get("software_market_size"):
            market = company["software_market_size"]
            print(f"\n📈 Extracted Market Data:")
            print(f"  Market Size: ${market.get('market_size', 0)/1e9:.1f}B")
            print(f"  Source: {market.get('source', 'Unknown')}")
            print(f"  Citation: {market.get('citation', '')[:100]}")
    else:
        print(f"❌ Failed to fetch data for {company_name}")
    
    print("\n" + "=" * 80)

if __name__ == "__main__":
    asyncio.run(test_improved_outputs())