#!/usr/bin/env python3
"""Ensure fallback extraction returns real funding values when Claude is unavailable."""

import asyncio

from app.services.structured_data_extractor import StructuredDataExtractor


async def test_structured_funding_fallback():
    extractor = StructuredDataExtractor()

    # Force fallback path by disabling LLM clients
    extractor.model_router = None
    extractor.claude_client = None

    html = """
    <html>
        <body>
            <p>The startup raised $12.5M in Series A funding led by Sequoia Capital.</p>
            <p>It previously closed a $3M seed round in 2022.</p>
        </body>
    </html>
    """

    result = await extractor.extract_from_html(html, "FallbackCo")

    total_raised = result.get("total_raised", 0)
    assert total_raised == 15_500_000, f"Expected $15.5M total_raised, got {total_raised}"

    print("Fallback extraction total_raised:", total_raised)


if __name__ == "__main__":
    asyncio.run(test_structured_funding_fallback())
