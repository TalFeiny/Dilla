import asyncio
import logging
from app.services.unified_mcp_orchestrator import UnifiedMCPOrchestrator

# Enable debug logging to see what's happening
logging.basicConfig(level=logging.INFO, format='%(message)s')

async def test_dwelly():
    orchestrator = UnifiedMCPOrchestrator()
    
    print("\n=== Testing Dwelly Website Extraction ===\n")
    
    # First, let's just search for Dwelly
    try:
        # Manually call the search like the main function does
        import aiohttp
        from app.services.web_scraper import WebScraper
        
        scraper = WebScraper()
        search_tasks = []
        
        # Run the 4 searches like the actual code
        search_tasks.append(scraper.search_web(f"Dwelly startup company"))
        search_tasks.append(scraper.search_web(f"Dwelly raised seed series million funding"))
        search_tasks.append(scraper.search_web(f"Dwelly startup company website"))
        
        search_results_list = await asyncio.gather(*search_tasks)
        
        # Format results like the actual code does
        search_results = {
            'general': search_results_list[0],
            'funding': search_results_list[1],
            'website': search_results_list[2]
        }
        
        print(f"Search completed. Found search results")
        
        # Extract company profile
        profile = await orchestrator._extract_company_profile("Dwelly", search_results)
        print(f"\nCompany Profile Extracted:")
        print(f"- Business Model: {profile.get('business_model', 'NOT FOUND')}")
        print(f"- Acquisitions: {profile.get('acquisitions', 'NOT FOUND')}")
        print(f"- Geography: {profile.get('geography', 'NOT FOUND')}")
        print(f"- Website mentioned: {profile.get('website', 'NOT FOUND')}")
        
        # Extract website URL
        website = await orchestrator._extract_website_url("Dwelly", search_results, profile)
        print(f"\n✅ Final Website Selected: {website}")
        
        return website
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == "__main__":
    result = asyncio.run(test_dwelly())
    print(f"\n=== RESULT: {result} ===")