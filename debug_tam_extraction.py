#!/usr/bin/env python3
"""
Debug TAM extraction to see what's happening with ModelRouter
"""

import asyncio
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))

from app.services.intelligent_gap_filler import IntelligentGapFiller

async def debug_tam_extraction():
    """Debug why TAM extraction is failing"""
    
    # Initialize the gap filler
    gap_filler = IntelligentGapFiller()
    
    # Test with Mercury-like data
    mercury_data = {
        'company_name': 'Mercury',
        'vertical': 'Fintech',
        'business_model': 'Digital Banking Platform',
        'description': 'Mercury is a digital banking platform designed specifically for startups and small businesses.',
        'what_they_do': 'provides digital banking infrastructure for startups and small businesses'
    }
    
    # Mock search content with actual market data
    search_content = """
    [Title] Global Digital Banking Market Size Valued at $3.5 Billion in 2024
    URL: https://example.com/digital-banking-report
    
    The global digital banking market was valued at $3.5 billion in 2024 and is expected to reach $8.2 billion by 2030, according to Gartner research.
    
    [Title] Neobank Market Analysis - $2B TAM for Business Banking
    URL: https://example.com/neobank-analysis
    
    The neobank market for business banking services has a total addressable market of $2 billion, with companies like Mercury competing in this space.
    
    [Title] Fintech Market Size Report 2024
    URL: https://example.com/fintech-report
    
    The global fintech market reached $310 billion in 2024, with digital banking representing a significant segment.
    """
    
    print("🔍 Debugging TAM Extraction")
    print("=" * 50)
    print(f"Company: {mercury_data['company_name']}")
    print(f"Search content length: {len(search_content)} chars")
    print(f"Search content preview:\n{search_content[:500]}...")
    print()
    
    # Test TAM extraction
    try:
        result = await gap_filler.extract_tam_from_search(search_content, mercury_data)
        
        if result:
            print("✅ TAM Extraction Result:")
            print(f"   - TAM Value: ${result.get('tam_value', 0)/1e9:.1f}B")
            print(f"   - Market Definition: {result.get('tam_market_definition', 'Unknown')}")
            print(f"   - Source: {result.get('source', 'Unknown')}")
            print(f"   - Citation: {result.get('citation', 'None')}")
            print(f"   - Confidence: {result.get('confidence', 0):.1%}")
        else:
            print("❌ TAM Extraction Failed - No result returned")
            
    except Exception as e:
        print(f"❌ TAM Extraction Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(debug_tam_extraction())
