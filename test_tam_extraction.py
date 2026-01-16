#!/usr/bin/env python3
"""
Test script to verify TAM extraction is working with ModelRouter
"""
import asyncio
import sys
import os

# Add the backend directory to Python path
backend_path = os.path.join(os.path.dirname(__file__), 'backend')
sys.path.insert(0, backend_path)

from app.services.intelligent_gap_filler import IntelligentGapFiller
from app.services.unified_mcp_orchestrator import UnifiedMCPOrchestrator


def test_missing_tam_values_handling():
    """
    Regression test: ensure TAM/SAM/SOM formatting tolerates None/zero values.
    Mirrors the orchestrator logging path so missing data can't crash deck generation.
    """
    print("🔎 Verifying TAM/SAM/SOM formatting with missing values...")
    
    tam_display = UnifiedMCPOrchestrator._format_billions(
        None,
        zero_label="$0B",
        none_label="$0B"
    )
    sam_display = UnifiedMCPOrchestrator._format_billions(
        0,
        zero_label="$0B",
        none_label="$0B"
    )
    som_display = UnifiedMCPOrchestrator._format_billions(
        "",
        zero_label="$0B",
        none_label="$0B"
    )
    
    assert tam_display == "$0B", "TAM display should default to $0B when value missing"
    assert sam_display == "$0B", "SAM display should handle zero safely"
    assert som_display == "$0B", "SOM display should handle empty strings safely"
    
    calc_method = (
        f"Selected: Labor TAM | "
        f"{UnifiedMCPOrchestrator._format_billions(None, zero_label='$0B', none_label='$0B')}"
    )
    assert calc_method.endswith("$0B"), "Calculation method string should include safe default"
    
    print("✅ Missing TAM/SAM/SOM value formatting is safe.")

async def test_tam_extraction():
    """Test that ModelRouter successfully extracts TAM data"""
    
    # Initialize the gap filler
    gap_filler = IntelligentGapFiller()
    
    # Test company data for Cogna
    company_data = {
        'company_name': 'Cogna',
        'vertical': 'Education Technology',
        'business_model': 'EdTech Platform',
        'sector': 'Education',
        'description': 'AI-powered educational technology platform for personalized learning',
        'competitors': ['Coursera', 'Udemy', 'Khan Academy']
    }
    
    # Test with REAL Tavily search instead of hardcoded data
    print("Testing with REAL Tavily search...")
    
    # Make actual Tavily API call
    import aiohttp
    import os
    
    tavily_api_key = os.getenv('TAVILY_API_KEY')
    if not tavily_api_key:
        print("❌ TAVILY_API_KEY not set - cannot test real search")
        return
    
    async with aiohttp.ClientSession() as session:
        url = "https://api.tavily.com/search"
        payload = {
            "api_key": tavily_api_key,
            "query": "EdTech education technology market size TAM 2024 billion Coursera Udemy",
            "search_depth": "advanced",
            "max_results": 5
        }
        
        print(f"🔍 Searching Tavily: {payload['query']}")
        
        async with session.post(url, json=payload) as response:
            if response.status == 200:
                result = await response.json()
                print(f"✅ Got {len(result.get('results', []))} results from Tavily")
                
                # Format results like the real system does
                search_content = "=== TAM SEARCH RESULTS ===\n\n"
                for r in result.get('results', []):
                    snippet = r.get('snippet', '')
                    title = r.get('title', '')
                    url = r.get('url', '')
                    text_content = snippet if snippet else r.get('content', '')
                    search_content += f"[{title}]\nURL: {url}\n{text_content}\n\n---\n\n"
                
                print(f"📄 Formatted search content length: {len(search_content)} chars")
                print(f"📄 First 500 chars:\n{search_content[:500]}...")
                
            else:
                error = await response.text()
                print(f"❌ Tavily API error: {response.status} - {error}")
                return
    
    print("Testing TAM extraction with ModelRouter...")
    print(f"Company: {company_data['company_name']}")
    print(f"ModelRouter available: {gap_filler.model_router is not None}")
    
    # Check API keys
    import os
    print(f"ANTHROPIC_API_KEY: {'SET' if os.getenv('ANTHROPIC_API_KEY') else 'NOT SET'}")
    print(f"OPENAI_API_KEY: {'SET' if os.getenv('OPENAI_API_KEY') else 'NOT SET'}")
    print(f"GROQ_API_KEY: {'SET' if os.getenv('GROQ_API_KEY') else 'NOT SET'}")
    
    try:
        # Test the async extraction
        print("\n🔍 Calling extract_tam_from_search...")
        result = await gap_filler.extract_tam_from_search(search_content, company_data)
        
        if result:
            print("\n✅ TAM extraction successful!")
            print(f"Market definition: {result.get('tam_market_definition', 'Not found')}")
            print(f"TAM value: ${result.get('tam_value', 0)/1e9:.1f}B")
            print(f"Source: {result.get('source', 'Not found')}")
            print(f"Confidence: {result.get('confidence', 'Not found')}")
            
            # Show what we actually got
            print(f"\nFull result keys: {list(result.keys())}")
            if 'tam_estimates' in result:
                print(f"TAM estimates: {len(result['tam_estimates'])}")
                for est in result['tam_estimates']:
                    print(f"  - ${est.get('tam_value', 0)/1e9:.1f}B from {est.get('source', 'Unknown')}")
                    print(f"    URL: {est.get('url', 'No URL')}")
            
            if 'incumbents' in result:
                print(f"Incumbents found: {len(result['incumbents'])}")
                for incumbent in result['incumbents']:
                    print(f"  - {incumbent.get('name')}: {incumbent.get('market_share_percentage')}")
        else:
            print("❌ TAM extraction returned None")
            
    except Exception as e:
        print(f"❌ TAM extraction failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_missing_tam_values_handling()
    asyncio.run(test_tam_extraction())
