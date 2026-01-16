#!/usr/bin/env python3
"""Test script to debug ModelRouter issue"""

import asyncio
import sys
import os

import pytest

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "backend"))

from app.services.model_router import ModelRouter, ModelCapability


@pytest.mark.asyncio
async def test_router():
    """Test the model router to see what's happening"""
    router = ModelRouter()

    print("Testing ModelRouter...")
    print(f"Model configs: {list(router.model_configs.keys())}")

    # Test getting model order
    models = router._get_model_order(ModelCapability.ANALYSIS, None)
    print(f"\nModels for ANALYSIS capability: {models}")

    models = router._get_model_order(ModelCapability.ANALYSIS, ["claude-sonnet-4-5"])
    print(f"\nModels with preference: {models}")

    available_models = [name for name in models if router._is_model_ready(name)]
    if not available_models:
        if os.environ.get("PYTEST_CURRENT_TEST"):
            pytest.skip("No model providers are configured; skipping completion test.")
        print("\n⚠️  No model providers are configured; skipping completion test.")
        return

    print(f"\nModels ready for use: {available_models}")

    # Test with a simple prompt
    try:
        result = await router.get_completion(
            prompt="Hello, what is 2+2?",
            capability=ModelCapability.ANALYSIS,
            max_tokens=100,
            temperature=0.7,
        )
        print(f"\n✅ Success! Result: {result}")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_router())

