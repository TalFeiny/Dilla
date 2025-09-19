import asyncio
from app.services.unified_mcp_orchestrator import UnifiedMCPOrchestrator

async def test():
    print("\n=== Testing Dwelly with Simple Request ===\n")
    
    orchestrator = UnifiedMCPOrchestrator()
    
    # Just run the actual request
    result = await orchestrator.process_request(
        prompt="Analyze @Dwelly",
        output_format="analysis",
        context={}
    )
    
    # Check what we got
    print(f"Result keys: {result.keys()}")
    
    # Check different possible locations for companies
    companies = result.get('results', {}).get('companies', []) or result.get('companies', [])
    print(f"Found {len(companies)} companies")
    
    if companies:
        for company in companies:
            print(f"\nCompany: {company.get('company', 'Unknown')}")
            print(f"Website: {company.get('website_url', 'NOT FOUND')}")
            print(f"Business Model: {company.get('business_model', 'NOT FOUND')}")
            print(f"Category: {company.get('category', 'NOT FOUND')}")
            print(f"Acquisitions: {company.get('acquisitions', 'NOT FOUND')}")
            
            # Check key metrics
            key_metrics = company.get('key_metrics', {})
            print(f"\nKey Metrics:")
            print(f"  Gross Margin: {key_metrics.get('gross_margin', 'NOT SET')}")
            print(f"  Compute Costs: {key_metrics.get('compute_costs', 'NOT SET')}")
            print(f"  Margin Viability: {key_metrics.get('margin_viability', 'NOT SET')}")
            
            # Check if dwelly.app was selected
            if 'dwelly.app' in str(company.get('website_url', '')).lower():
                print("❌ WRONG: Got dwelly.app (US ADU company)")
            elif 'dwelly.group' in str(company.get('website_url', '')).lower():
                print("✅ CORRECT: Got dwelly.group (UK PropTech roll-up)")
            elif company.get('website_url') is None:
                print("⚠️ No website found - Claude rejected all candidates")

if __name__ == "__main__":
    asyncio.run(test())