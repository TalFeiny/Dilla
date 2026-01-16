#!/usr/bin/env python3
"""Test extraction only to see what's being returned"""

import asyncio
from app.services.structured_data_extractor import StructuredDataExtractor

async def test():
    extractor = StructuredDataExtractor()
    
    # Test with realistic data
    text_sources = [{
        'text': '''Anthropic is an AI safety company that develops large language models. 
        The company raised $450 million in Series C funding in May 2023 at a $4.1 billion valuation.
        Anthropic's flagship product is Claude, an AI assistant that competes with ChatGPT.
        The global AI market is expected to reach $1.8 trillion by 2030 according to Grand View Research.
        The company was founded by former OpenAI executives including Dario Amodei.
        Anthropic focuses on AI safety and constitutional AI to build helpful, harmless AI systems.''',
        'source': 'Test',
        'url': 'test.com'
    }]
    
    result = await extractor.extract_from_text(text_sources, 'Anthropic')
    
    print('Key extracted fields:')
    print(f"  business_model: {result.get('business_model')}")
    print(f"  what_they_do: {result.get('what_they_do')}")
    print(f"  category: {result.get('category')}")
    print(f"  vertical: {result.get('vertical')}")
    print(f"  valuation: ${result.get('valuation', 0)/1e9:.1f}B")
    
    if result.get('software_market_size'):
        market = result['software_market_size']
        print(f"\nMarket data extracted:")
        print(f"  market_size: ${market.get('market_size', 0)/1e9:.1f}B")
        print(f"  source: {market.get('source')}")
    else:
        print("\nNo software_market_size extracted")
    
    print(f"\nAll fields: {list(result.keys())}")

asyncio.run(test())