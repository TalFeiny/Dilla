#!/usr/bin/env python3
"""Test what Claude is actually extracting"""

import asyncio
import json
from app.services.structured_data_extractor import StructuredDataExtractor

async def test():
    extractor = StructuredDataExtractor()
    
    # Create test text with ACTUAL Tavily results
    text_sources = [{
        "text": """Australian AI agent startup Relevance AI bags $24 million
AI startup Relevance AI, which launched in 2020, has banked $24 million in its Series B fundraising round, bringing its total funding to $37 million.
The round was led by US$20 billion San Francisco venture firm Bessemer Venture Partners.
Relevance AI raises $24M to help businesses build AI agents
Relevance AI, a San Francisco- and Sydney-based startup developing an AI agent operating system to enable businesses to build teams of AI agents, has raised $24 million in Series B funding.""",
        "source": "Combined news",
        "url": "https://techcrunch.com"
    }]
    
    print("Testing extraction with real RelevanceAI data...")
    print("=" * 80)
    
    result = await extractor.extract_from_text(text_sources, "RelevanceAI")
    
    print("\nExtracted data:")
    print(json.dumps(result, indent=2, default=str))
    
    # Check key fields
    print("\n" + "=" * 80)
    print("Key fields:")
    print(f"  Total raised: {result.get('total_raised')}")
    print(f"  Valuation: {result.get('valuation')}")
    print(f"  Funding rounds: {len(result.get('funding_rounds', []))}")
    if result.get('funding_rounds'):
        for round in result['funding_rounds']:
            print(f"    - {round.get('round')}: ${round.get('amount'):,} ({round.get('date')})")

asyncio.run(test())