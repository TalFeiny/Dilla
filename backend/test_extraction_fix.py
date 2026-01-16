#!/usr/bin/env python3
"""Test that extraction is working correctly after fixes"""

# MUST load environment variables BEFORE any app imports
from dotenv import load_dotenv
load_dotenv()

import asyncio
import json
from app.services.unified_mcp_orchestrator import UnifiedMCPOrchestrator

async def test_extraction_fix():
    orch = UnifiedMCPOrchestrator()
    
    print("=" * 80)
    print("TESTING EXTRACTION FIXES FOR RelevanceAI")
    print("=" * 80)
    print("\nExpected values from Tavily search results:")
    print("  - Stage: Series B")
    print("  - Total Funding: $37M")
    print("  - Latest Round: $24M (May 2025)")
    print("  - Founded: 2020")
    print("=" * 80)
    
    # Fetch company data
    result = await orch._execute_company_fetch({"company": "RelevanceAI"})
    
    if result and "companies" in result:
        company = result["companies"][0]
        
        print("\n🔍 EXTRACTED DATA:")
        print("-" * 40)
        
        # Check critical fields
        stage = company.get("stage", "MISSING")
        total_funding = company.get("total_funding", 0) or company.get("total_raised", 0)
        valuation = company.get("valuation", 0)
        funding_rounds = company.get("funding_rounds", [])
        
        print(f"Stage: {stage}")
        print(f"Total Funding: ${total_funding:,.0f}")
        print(f"Valuation: ${valuation:,.0f}")
        print(f"Number of Funding Rounds: {len(funding_rounds)}")
        
        # Check each funding round
        if funding_rounds:
            print("\nFunding Rounds:")
            for round in funding_rounds:
                round_type = round.get("round", "Unknown")
                amount = round.get("amount", 0)
                date = round.get("date", "Unknown")
                investors = round.get("investors", [])
                print(f"  - {round_type}: ${amount:,.0f} ({date})")
                if investors:
                    print(f"    Investors: {', '.join(investors[:3])}")
        
        # Check inferred values
        print("\n📊 INFERRED VALUES:")
        print("-" * 40)
        for field in ["revenue", "valuation", "growth_rate", "gross_margin"]:
            actual = company.get(field)
            inferred = company.get(f"inferred_{field}")
            print(f"{field}: actual=${actual}, inferred=${inferred}")
        
        # Verify the fixes worked
        print("\n✅ VERIFICATION:")
        print("-" * 40)
        
        issues = []
        
        # Check if stage is correct
        if "series b" not in str(stage).lower():
            issues.append(f"❌ Stage is '{stage}' but should be 'Series B'")
        else:
            print("✓ Stage correctly extracted as Series B")
        
        # Check if total funding is correct (should be around $37M)
        if total_funding < 30_000_000:
            issues.append(f"❌ Total funding is ${total_funding:,.0f} but should be ~$37M")
        else:
            print(f"✓ Total funding correctly extracted as ${total_funding:,.0f}")
        
        # Check if we have the Series B round
        has_series_b = any("series b" in str(r.get("round", "")).lower() for r in funding_rounds)
        if not has_series_b:
            issues.append("❌ Missing Series B round in funding_rounds")
        else:
            series_b = next(r for r in funding_rounds if "series b" in str(r.get("round", "")).lower())
            amount = series_b.get("amount", 0)
            if amount >= 20_000_000:
                print(f"✓ Series B round found with ${amount:,.0f}")
            else:
                issues.append(f"❌ Series B amount is ${amount:,.0f} but should be ~$24M")
        
        if issues:
            print("\n⚠️ ISSUES FOUND:")
            for issue in issues:
                print(f"  {issue}")
            print("\n🔧 The extraction is still not working correctly!")
        else:
            print("\n🎉 All checks passed! Extraction is working correctly!")
            
        # Show raw data for debugging
        print("\n📝 RAW DATA (for debugging):")
        print("-" * 40)
        print(json.dumps({
            "stage": stage,
            "total_funding": total_funding,
            "valuation": valuation,
            "funding_rounds": funding_rounds
        }, indent=2, default=str))
    else:
        print("❌ Failed to fetch company data")

if __name__ == "__main__":
    asyncio.run(test_extraction_fix())