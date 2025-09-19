import sys
sys.path.append(".")
from app.services.intelligent_gap_filler import IntelligentGapFiller
from datetime import datetime, timedelta
import asyncio
import logging

logging.basicConfig(level=logging.INFO)

gap_filler = IntelligentGapFiller()

# Test Dwelly with full context
dwelly = {
    "company": "Dwelly",
    "stage": "Series A",
    "category": "ai_enhanced_rollup",
    "revenue": None,
    "funding_rounds": [
        {
            "round": "Series A",
            "amount": 15_000_000,
            "date": "2024-03-15",  # 10 months ago
            "investors": [{"name": "Sequoia Capital"}]
        }
    ],
    "team_size": 25,
    "geography": "San Francisco",
    "pricing_tiers": {"has_enterprise": True},
    "customer_logos": ["Microsoft", "Google", "Amazon"]
}

print("=== Testing Dwelly with Time & Quality Adjustments ===")
print(f"Stage: {dwelly['stage']}")
print(f"Location: {dwelly['geography']}")
print(f"Team size: {dwelly['team_size']}")
print("Has enterprise pricing: Yes")
print("Has Tier 1 VCs: Yes (Sequoia)")
print("Has enterprise customers: Yes (Microsoft, Google, Amazon)")
print()

async def test():
    inferences = await gap_filler.infer_from_stage_benchmarks(
        dwelly,
        ["revenue"]
    )
    
    for field, result in inferences.items():
        if hasattr(result, "value"):
            print(f"INFERRED {field.upper()}: ${result.value:,.0f}")
            print("\nReasoning breakdown:")
            # Parse the reasoning string
            parts = result.reasoning.split(" | ")
            for part in parts:
                print(f"  - {part}")

asyncio.run(test())
