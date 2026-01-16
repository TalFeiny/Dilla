#!/usr/bin/env python3
"""Test extraction pipeline with logging for 2 failing companies"""

import asyncio
import logging
import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))

# Configure verbose logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('extraction_debug.log', mode='w')
    ]
)

from app.services.unified_mcp_orchestrator import UnifiedMCPOrchestrator

async def test_company_extraction(company_name: str):
    print("=" * 80)
    print(f"TESTING EXTRACTION FOR: {company_name}")
    print("=" * 80)
    
    orch = UnifiedMCPOrchestrator()
    
    result = await orch._execute_company_fetch({"company": company_name})
    
    if result and "companies" in result and len(result["companies"]) > 0:
        company = result["companies"][0]
        
        print(f"\n✅ EXTRACTION COMPLETE")
        print(f"Stage: {company.get('stage', 'MISSING')}")
        print(f"Total Funding: ${company.get('total_funding', 0):,.0f}")
        print(f"Valuation: ${company.get('valuation', 0):,.0f}")
        print(f"Funding Rounds: {len(company.get('funding_rounds', []))}")
        for r in company.get('funding_rounds', []):
            print(f"  - {r.get('round')}: ${r.get('amount', 0):,.0f} on {r.get('date', 'unknown')}")
        print(f"Founders: {len(company.get('founders', []))}")
        print(f"Business Model: {company.get('business_model', 'MISSING')[:150]}")
    else:
        print(f"\n❌ EXTRACTION FAILED - No company data returned")
    
    print("\n" + "=" * 80)
    print("Check extraction_debug.log for detailed pipeline logs")
    print("=" * 80)

async def main():
    # Test with Gradient Labs
    import sys
    if len(sys.argv) > 1:
        company_name = sys.argv[1]
        await test_company_extraction(company_name)
    else:
        # Default test companies
        companies = [
            "Gradient Labs"
        ]
        for company in companies:
            await test_company_extraction(company)
            print("\n\n")

if __name__ == "__main__":
    asyncio.run(main())
