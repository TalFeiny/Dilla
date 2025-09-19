#!/usr/bin/env python3
"""
Test the improved extraction in UnifiedMCPOrchestrator
Tests specific business model and sector extraction for companies
"""

import asyncio
import json
import logging
from app.services.unified_mcp_orchestrator import UnifiedMCPOrchestrator

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def test_extraction():
    """Test extraction with companies that were showing generic business models"""
    
    # Test companies that should have specific business models
    test_companies = [
        "@Corti",      # Should be "Healthcare AI consultation analysis" not "SaaS"
        "@AdaptiveML", # Should be "ML Infrastructure platform" not "SaaS"
        "@Cursor",     # Should be "AI-powered code editor/IDE" 
        "@Perplexity", # Should be "AI-powered search engine"
        "@Mercury",    # Should be "Digital banking for startups"
    ]
    
    orchestrator = UnifiedMCPOrchestrator()
    
    print("\n" + "="*80)
    print("TESTING IMPROVED BUSINESS MODEL & SECTOR EXTRACTION")
    print("="*80 + "\n")
    
    for company in test_companies:
        print(f"\n📊 Testing {company}...")
        print("-" * 40)
        
        try:
            # Process the request
            result = await orchestrator.process_request(
                prompt=f"Analyze {company}",
                output_format="analysis"
            )
            
            # Extract company data
            companies = result.get("companies", [])
            if companies:
                company_data = companies[0]
                
                # Check business model and sector
                business_model = company_data.get("business_model", "NOT FOUND")
                sector = company_data.get("sector", "NOT FOUND")
                category = company_data.get("category", "NOT FOUND")
                website = company_data.get("website_url", "NOT FOUND")
                
                # Determine if extraction is specific or generic
                is_generic = business_model in ["SaaS", "Software", "Technology", "Platform", "Tech"]
                is_generic_sector = sector in ["Technology", "Software", "IT", "Tech"]
                
                # Print results with color coding
                status = "❌" if is_generic else "✅"
                sector_status = "❌" if is_generic_sector else "✅"
                
                print(f"{status} Business Model: {business_model}")
                print(f"{sector_status} Sector: {sector}")
                print(f"   Category: {category}")
                print(f"   Website: {website}")
                
                if is_generic or is_generic_sector:
                    print(f"   ⚠️  WARNING: Still getting generic descriptions!")
                else:
                    print(f"   ✨ SUCCESS: Specific extraction working!")
                    
                # Also check other key fields
                print(f"   Stage: {company_data.get('stage', 'N/A')}")
                print(f"   Funding: ${company_data.get('total_funding', 0):,.0f}")
                print(f"   Valuation: ${company_data.get('valuation', 0):,.0f}")
                
        except Exception as e:
            print(f"   ❌ ERROR: {str(e)}")
            logger.error(f"Failed to process {company}: {e}", exc_info=True)
    
    print("\n" + "="*80)
    print("EXTRACTION TEST COMPLETE")
    print("="*80 + "\n")

if __name__ == "__main__":
    asyncio.run(test_extraction())
