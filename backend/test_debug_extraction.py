#!/usr/bin/env python3
"""Debug the Claude extraction to see what's being sent and received"""

import asyncio
import json
from app.services.unified_mcp_orchestrator import UnifiedMCPOrchestrator
from app.services.structured_data_extractor import StructuredDataExtractor

async def debug_extraction():
    orch = UnifiedMCPOrchestrator()
    extractor = StructuredDataExtractor()
    
    print("=" * 80)
    print("DEBUGGING CLAUDE EXTRACTION")
    print("=" * 80)
    
    # First, get the Tavily search results
    print("\n1️⃣ FETCHING TAVILY SEARCH RESULTS...")
    print("-" * 40)
    
    company = "RelevanceAI"
    search_queries = [
        f"{company} startup funding valuation revenue Series B",
        f"{company} company business model team founders",
        f"{company} seed pre-seed Series A B C funding round investors $24 million",
        f"{company} technology product customers market"
    ]
    
    # Get search results
    all_search_results = []
    for query in search_queries:
        result = await orch._tavily_search(query)
        if result:
            all_search_results.append(result)
            if "results" in result:
                print(f"✓ Found {len(result['results'])} results for: {query[:50]}...")
                # Show snippets that mention funding
                for r in result['results'][:2]:
                    content = r.get('content', '')
                    if any(word in content.lower() for word in ['$24', 'series b', '$37', 'million']):
                        print(f"  → Found funding mention: {content[:200]}...")
    
    print(f"\nTotal search result sets: {len(all_search_results)}")
    
    # Combine text for Claude
    print("\n2️⃣ COMBINING TEXT FOR CLAUDE...")
    print("-" * 40)
    
    combined_text = "\n\n---\n\n".join([
        f"Source {idx+1}:\n{result.get('content', '')[:3000]}"
        for idx, search_result in enumerate(all_search_results)
        if search_result and "results" in search_result
        for result in search_result.get("results", [])
        if result.get("content")
    ])
    
    print(f"Combined text length: {len(combined_text)} characters")
    
    # Check if the key data is in the combined text
    print("\n3️⃣ CHECKING IF KEY DATA IS IN COMBINED TEXT...")
    print("-" * 40)
    
    if "$24 million" in combined_text or "$24M" in combined_text:
        print("✓ Found $24 million Series B in combined text")
    else:
        print("❌ $24 million NOT found in combined text")
    
    if "$37 million" in combined_text or "$37M" in combined_text:
        print("✓ Found $37 million total in combined text")
    else:
        print("❌ $37 million NOT found in combined text")
    
    if "Series B" in combined_text:
        print("✓ Found 'Series B' in combined text")
    else:
        print("❌ 'Series B' NOT found in combined text")
    
    # Now extract using Claude
    print("\n4️⃣ EXTRACTING WITH CLAUDE...")
    print("-" * 40)
    
    # Call the extraction
    text_sources = [{"text": combined_text, "source": "Tavily"}]
    extracted = await extractor.extract_from_text(text_sources, company)
    
    print("\n5️⃣ CLAUDE'S EXTRACTION RESULT:")
    print("-" * 40)
    
    # Show key fields
    print(f"Stage: {extracted.get('stage', 'MISSING')}")
    print(f"Total Raised: ${extracted.get('total_raised', 0):,.0f}")
    print(f"Valuation: ${extracted.get('valuation', 0):,.0f}")
    print(f"Revenue: ${extracted.get('revenue', 0):,.0f}")
    
    # Show funding rounds
    funding_rounds = extracted.get('funding_rounds', [])
    print(f"\nFunding Rounds: {len(funding_rounds)}")
    for r in funding_rounds:
        print(f"  - {r.get('round', 'Unknown')}: ${r.get('amount', 0):,.0f} ({r.get('date', 'Unknown')})")
    
    # Show full extracted data
    print("\n6️⃣ FULL EXTRACTED DATA:")
    print("-" * 40)
    print(json.dumps(extracted, indent=2, default=str)[:2000])
    
    print("\n" + "=" * 80)
    print("DEBUG COMPLETE")
    print("=" * 80)

if __name__ == "__main__":
    asyncio.run(debug_extraction())
