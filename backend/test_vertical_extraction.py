#!/usr/bin/env python3
"""Test vertical and category extraction fix"""

import asyncio
import json
import logging
from app.services.unified_mcp_orchestrator import UnifiedMCPOrchestrator

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_extraction():
    """Test that vertical and category are properly extracted"""
    
    orchestrator = UnifiedMCPOrchestrator()
    
    # Test with a simple company fetch request
    prompt = "analyze @Mercury"  # Financial services company
    
    logger.info("Testing company extraction for Mercury...")
    result = await orchestrator.process_request(
        prompt=prompt,
        output_format="analysis"
    )
    
    if result and "results" in result:
        companies = result["results"].get("companies", [])
        if companies:
            company = companies[0]
            print("\n=== EXTRACTION RESULTS ===")
            print(f"Company: {company.get('company', 'Unknown')}")
            print(f"Business Model: {company.get('business_model', 'Unknown')}")
            print(f"Sector: {company.get('sector', 'Unknown')}")
            print(f"Vertical: {company.get('vertical', 'Unknown')}")
            print(f"Category: {company.get('category', 'Unknown')}")
            print(f"Stage: {company.get('stage', 'Unknown')}")
            
            # Check if TAM searches would work
            vertical = company.get('vertical', '')
            sector = company.get('sector', '')
            
            print("\n=== TAM SEARCH VALIDATION ===")
            if vertical and vertical != 'Unknown':
                print(f"✓ Vertical found: {vertical}")
                print(f"  TAM searches will use: '{vertical} software market size'")
            elif sector and sector != 'Unknown':
                print(f"✓ Sector found: {sector}")
                print(f"  TAM searches will use: '{sector} software market size'")
            else:
                print("✗ No vertical or sector found - TAM searches will fail!")
                
            # Check category
            valid_categories = ['ai_first', 'ai_saas', 'saas', 'rollup', 'marketplace', 
                              'services', 'tech_enabled_services', 'hardware', 
                              'gtm_software', 'deeptech_hardware', 'materials', 
                              'manufacturing', 'industrial']
            
            category = company.get('category', '')
            if category in valid_categories:
                print(f"✓ Valid category: {category}")
            else:
                print(f"✗ Invalid category: {category} (should be one of: {', '.join(valid_categories)})")
                
            return company
        else:
            print("No companies found in result")
    else:
        print("No result returned from orchestrator")
        
    return None

if __name__ == "__main__":
    result = asyncio.run(test_extraction())
    if result:
        print("\n=== FULL COMPANY DATA ===")
        print(json.dumps(result, indent=2, default=str))