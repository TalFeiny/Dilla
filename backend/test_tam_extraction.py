#!/usr/bin/env python3
"""Test script for enhanced TAM extraction"""

import asyncio
import json
from app.services.unified_mcp_orchestrator import UnifiedMCPOrchestrator
from app.services.intelligent_gap_filler import IntelligentGapFiller

async def test_tam_extraction():
    """Test TAM extraction for various companies"""
    
    orchestrator = UnifiedMCPOrchestrator()
    gap_filler = IntelligentGapFiller()
    
    # Initialize the aiohttp session
    import aiohttp
    orchestrator.session = aiohttp.ClientSession()
    
    test_companies = ["@Cursor", "@Perplexity", "@Toast"]
    
    try:
        for company in test_companies:
            print(f"\n{'='*50}")
            print(f"Testing TAM extraction for {company}")
            print('='*50)
            
            # Fetch company data
            result = await orchestrator._execute_company_fetch({"company": company})
            
            if result and "companies" in result:
                company_data = result["companies"][0]
                
                print(f"\nCompany: {company_data.get('company', 'Unknown')}")
                print(f"Business Model: {company_data.get('business_model', 'Unknown')}")
                print(f"Sector: {company_data.get('sector', 'Unknown')}")
                print(f"Category: {company_data.get('category', 'Unknown')}")
                
                if "tam_analysis" in company_data:
                    tam = company_data["tam_analysis"]
                    print(f"\nTAM Analysis:")
                    print(f"  TAM: {tam.get('tam_formatted', 'N/A')}")
                    print(f"  SAM: {tam.get('sam_formatted', 'N/A')}")
                    print(f"  SOM: {tam.get('som_formatted', 'N/A')}")
                    print(f"  Growth Rate: {tam.get('cagr_percentage', 'N/A')}")
                    print(f"  Market Category: {tam.get('market_category', 'N/A')}")
                    print(f"  Methodology: {tam.get('tam_methodology', 'N/A')}")
                    print(f"  Citation: {tam.get('tam_citation', 'N/A')}")
                    print(f"  Confidence: {tam.get('confidence_level', 'N/A')}")
                else:
                    print("No TAM analysis available")
            else:
                print(f"Failed to fetch data for {company}")
    
    finally:
        # Close the session
        await orchestrator.session.close()

if __name__ == "__main__":
    asyncio.run(test_tam_extraction())