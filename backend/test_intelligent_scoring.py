#!/usr/bin/env python3
"""
Test intelligent scoring and TAM data extraction with real companies
"""
import asyncio
import json
import os
from app.services.unified_mcp_orchestrator import UnifiedMCPOrchestrator

async def test_company(company_name: str):
    """Test a single company"""
    print(f"\n{'='*60}")
    print(f"Testing: {company_name}")
    print('='*60)
    
    # Initialize orchestrator (it sets up its own model router)
    orchestrator = UnifiedMCPOrchestrator()
    
    print(f"Model Router available: {orchestrator.model_router is not None}")
    print(f"Tavily API configured: {orchestrator.tavily_api_key is not None}")
    
    try:
        # Fetch company data
        print(f"Fetching data for {company_name}...")
        result = await orchestrator.process_request({
            'skill': 'company-fetch',
            'companies': [company_name]
        })
        
        print(f"Result keys: {result.keys() if result else 'None'}")
        
        # Check what's in results
        results = result.get('results', {})
        print(f"Results type: {type(results)}")
        print(f"Results keys: {results.keys() if isinstance(results, dict) else 'Not a dict'}")
        
        # Try to get companies from nested structure
        companies = None
        if isinstance(results, dict):
            companies = results.get('companies', [])
        elif isinstance(results, list):
            companies = results
        
        print(f"Companies found: {len(companies) if companies else 0}")
        
        if companies and len(companies) > 0:
            company = companies[0]
            print(f"Company data keys: {list(company.keys())[:10] if isinstance(company, dict) else 'Not a dict'}")
            
            # Display TAM data
            print("\n📊 TAM DATA:")
            print(f"  - TAM: ${company.get('tam', 0)/1e9:.1f}B")
            print(f"  - TAM Source: {company.get('tam_source', 'Not found')}")
            print(f"  - Labor TAM: ${company.get('labor_tam', 0)/1e9:.1f}B")
            print(f"  - Labor Roles: {company.get('labor_roles_replaced', 'Not found')}")
            print(f"  - SAM: ${company.get('sam', 0)/1e9:.1f}B")
            print(f"  - Market CAGR: {company.get('market_cagr', 0)*100:.0f}%")
            
            # Display Moat Analysis
            moat = company.get('moat_reasoning', {})
            if moat:
                print("\n🏰 MOAT ANALYSIS:")
                print(f"  - Key Insight: {moat.get('key_insight', 'N/A')}")
                print(f"  - Factors: {', '.join(moat.get('factors', []))}")
                print(f"  - Evidence:")
                for e in moat.get('evidence', [])[:3]:
                    print(f"    • {e}")
                print(f"  - Score Breakdown:")
                for k, v in moat.get('score_breakdown', {}).items():
                    print(f"    • {k}: {v:.2f}")
            
            # Display Momentum Analysis
            momentum = company.get('momentum_reasoning', {})
            if momentum:
                print("\n🚀 MOMENTUM ANALYSIS:")
                print(f"  - Key Insight: {momentum.get('key_insight', 'N/A')}")
                print(f"  - Factors: {', '.join(momentum.get('factors', []))}")
                print(f"  - Evidence:")
                for e in momentum.get('evidence', [])[:3]:
                    print(f"    • {e}")
                print(f"  - Score Breakdown:")
                for k, v in momentum.get('score_breakdown', {}).items():
                    print(f"    • {k}: {v:.2f}")
            
            # Display basic metrics
            print("\n📈 BASIC METRICS:")
            print(f"  - Revenue: ${company.get('revenue', 0)/1e6:.1f}M")
            print(f"  - Valuation: ${company.get('valuation', 0)/1e6:.1f}M")
            print(f"  - Total Funding: ${company.get('total_funding', 0)/1e6:.1f}M")
            print(f"  - Stage: {company.get('stage', 'Unknown')}")
            print(f"  - Business Model: {company.get('business_model', 'Unknown')}")
            print(f"  - Sector: {company.get('sector', 'Unknown')}")
            
        else:
            print(f"❌ No data returned for {company_name}")
            
    except Exception as e:
        print(f"❌ Error testing {company_name}: {e}")
        import traceback
        traceback.print_exc()

async def main():
    """Test multiple companies"""
    test_companies = [
        "@Perplexity",  # AI search
        "@Mercury",     # Fintech
        "@Deel"         # HR Tech
    ]
    
    for company in test_companies:
        await test_company(company)
        await asyncio.sleep(2)  # Rate limiting

if __name__ == "__main__":
    asyncio.run(main())