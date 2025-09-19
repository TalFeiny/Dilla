import asyncio
import json
from app.services.unified_mcp_orchestrator import UnifiedMCPOrchestrator

async def test_extraction():
    orchestrator = UnifiedMCPOrchestrator()
    
    # Test with a company that likely has CloudFlare protection
    # Create a proper context object
    from types import SimpleNamespace
    context = SimpleNamespace(
        skill_chain=None,
        entities={'companies': ['@Stripe']}
    )
    
    config = {
        'companies': ['@Stripe']
    }
    
    result = await orchestrator._execute_company_fetch(
        config=config,
        context=context
    )
    
    # Pretty print the first company's extracted data
    if result and result.get('companies'):
        company = result['companies'][0]
        print('Extracted fields for @Stripe:')
        print(f'  Website: {company.get("website_url", "Not found")}')
        print(f'  Business Model: {company.get("business_model", "Not extracted")}')
        print(f'  Strategy: {company.get("strategy", "Not extracted")}')
        print(f'  Vertical: {company.get("vertical", "Not extracted")}')
        print(f'  Category: {company.get("category", "Not extracted")}')
        print(f'  Founder Score: {company.get("founder_score", 0)}')
        print(f'  Founder Signals: {company.get("founder_quality_signals", [])}')
        print(f'  Compute Intensity: {company.get("compute_intensity", "Not extracted")}')
        print(f'  Traction Level: {company.get("traction_level", "Not extracted")}')
        print(f'  Traction Signals: {company.get("traction_signals", [])}')
        print(f'  Valuation: ${company.get("valuation", 0):,.0f}')
        print(f'  ARR: ${company.get("arr", 0):,.0f}')
        print(f'  Fund Fit Score: {company.get("fund_fit_score", 0):.1f}')
        
        # Check if we got data without website scraping
        if not company.get("website_url") or "stripe.com" not in company.get("website_url", ""):
            print("\n✅ Successfully extracted data without website scraping!")
        else:
            print("\n⚠️ Website was scraped - may not work with anti-bot measures")
    else:
        print('No data extracted')

if __name__ == "__main__":
    asyncio.run(test_extraction())