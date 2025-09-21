#!/usr/bin/env python3
"""Test extraction directly to debug why business models are generic"""

import asyncio
import os
from anthropic import AsyncAnthropic

async def test_extraction():
    """Test Claude extraction directly"""
    
    # Sample search result for Perplexity
    search_content = """
    [Perplexity AI raises $74M and will triple valuation to $520M]
    URL: https://techcrunch.com/2024/01/04/perplexity-ai-raises-74m/
    Perplexity AI, the conversational search engine that provides real-time answers to questions, has raised $74 million in Series B funding at a $520 million valuation. The company's AI-powered search engine uses large language models to provide direct answers with citations, competing with traditional search engines like Google. Perplexity processes millions of queries daily and offers both free and paid tiers.

    [Perplexity: The AI Search Engine Taking on Google]  
    URL: https://www.forbes.com/perplexity-ai/
    Perplexity is an AI-powered conversational search engine that provides instant, accurate answers to questions with real-time information from the web. Unlike traditional search that returns links, Perplexity synthesizes information from multiple sources and provides comprehensive answers with citations. The platform uses advanced AI models to understand context and deliver precise responses.
    """
    
    extraction_prompt = f"""Extract comprehensive structured data about Perplexity from the following search results.

Search Results:
{search_content}

Extract and return a JSON object with the following structure. BE SPECIFIC, not generic:

{{
    "company": "Perplexity",
    "business_model": "ULTRA-SPECIFIC description of what they do. NEVER use generic terms like SaaS, Software, Platform alone",
    "sector": "SPECIFIC vertical/industry they serve. NEVER just 'Technology' or 'Software'",
    "category": "SPECIFIC product category. Be precise about what the product actually does"
}}

BUSINESS MODEL EXTRACTION (MOST IMPORTANT):
- Read the search results carefully to understand WHAT THE COMPANY ACTUALLY DOES
- Look for phrases like "builds", "develops", "provides", "helps", "enables"
- Extract the SPECIFIC product/service, not generic categories
- BAD: "SaaS", "Software", "Platform", "Technology company"
- GOOD: "AI-powered conversational search engine with real-time web synthesis"

Return ONLY the JSON object, no other text."""

    claude = AsyncAnthropic(api_key=os.environ.get('ANTHROPIC_API_KEY'))
    
    response = await claude.messages.create(
        model="claude-3-5-sonnet-20241022",
        max_tokens=1000,
        temperature=0.1,
        messages=[
            {"role": "user", "content": extraction_prompt}
        ]
    )
    
    print("Claude's response:")
    print(response.content[0].text if response.content else "No response")

if __name__ == "__main__":
    asyncio.run(test_extraction())
