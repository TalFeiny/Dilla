import asyncio
import os
from dotenv import load_dotenv
load_dotenv()

from app.services.unified_mcp_orchestrator import UnifiedMCPOrchestrator
from app.services.mcp_orchestrator import MCPOrchestrator

async def test_what_claude_sees():
    print("\n=== Testing What Claude Actually Sees ===\n")
    
    # First, let's do a manual search to see what we get
    mcp = MCPOrchestrator()
    
    # Search for Dwelly
    queries = [
        '"Dwelly" startup company -tracxn -crunchbase',
        '"Dwelly" UK PropTech lettings'
    ]
    
    all_urls = set()
    all_content = []
    
    for query in queries:
        print(f"\nSearching: {query}")
        result = await mcp.executor.execute_tavily({
            "query": query,
            "search_depth": "advanced",
            "max_results": 10  # Get MORE results
        })
        
        if result.get('success'):
            for r in result['data']['results']:
                # Collect ALL URLs mentioned
                content = r.get('content', '')
                url = r.get('url', '')
                
                # Look for ANY domain mentions in content
                import re
                domains = re.findall(r'(?:https?://)?(?:www\.)?([a-zA-Z0-9\-]+\.(?:com|io|ai|co|dev|app|group|org|net|tech|xyz|vc|one|uk))', content)
                all_urls.update(domains)
                
                # Also check the URL itself
                if 'dwelly' in url.lower():
                    print(f"  Found Dwelly URL: {url}")
                
                # Look for dwelly.group specifically
                if 'dwelly.group' in content.lower() or 'dwelly.group' in url.lower():
                    print(f"  ✅ FOUND dwelly.group in: {url}")
                
                all_content.append(f"[{r.get('title')}]\n{content[:500]}")
    
    print(f"\n=== ALL DOMAINS FOUND IN CONTENT ===")
    for domain in sorted(all_urls):
        if 'dwelly' in domain.lower():
            print(f"  - {domain}")
    
    print(f"\n=== CONTENT PIECES COLLECTED: {len(all_content)} ===")
    
    # Now test what the orchestrator does with this
    orch = UnifiedMCPOrchestrator()
    orch._tavily_cache.clear()
    
    # Mock search results
    mock_results = {
        'general': result if 'result' in locals() else {'success': False}
    }
    
    profile = await orch._extract_comprehensive_profile('Dwelly', mock_results, linkedin_identifier='dwellygroup')
    print(f"\n=== CLAUDE'S EXTRACTION ===")
    print(f"Website: {profile.get('website_url', 'NOT FOUND')}")
    print(f"Business Model: {profile.get('business_model')}")

if __name__ == "__main__":
    asyncio.run(test_what_claude_sees())