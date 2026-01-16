import pytest

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "backend"))

from app.services.model_router import ModelRouter, ModelCapability


@pytest.mark.asyncio
async def test_router_returns_stub_response(monkeypatch):
    router = ModelRouter()

    async def fake_init():
        router._clients_initialized = True

    async def fake_call(model_config, prompt, system_prompt, max_tokens, temperature, json_mode):
        return f"{model_config['model']}::response"

    async def fake_rate_limit(model_name: str):
        return None

    monkeypatch.setattr(router, "_init_clients_if_needed", fake_init)
    monkeypatch.setattr(router, "_call_model", fake_call)
    monkeypatch.setattr(router, "_apply_rate_limit", fake_rate_limit)
    monkeypatch.setattr(router, "_is_model_ready", lambda name: True)

    result = await router.get_completion(
        prompt="ping",
        capability=ModelCapability.ANALYSIS,
        preferred_models=["claude-sonnet-4-5"],
        fallback_enabled=False,
    )

    assert result["response"] == "claude-sonnet-4-5::response"
    assert result["model"] == "claude-sonnet-4-5"


@pytest.mark.asyncio
async def test_router_fallbacks_to_next_model(monkeypatch):
    router = ModelRouter()

    async def fake_init():
        router._clients_initialized = True

    call_attempts = {"claude": 0}

    async def fake_call(model_config, prompt, system_prompt, max_tokens, temperature, json_mode):
        if model_config["model"] == "claude-sonnet-4-5":
            call_attempts["claude"] += 1
            raise RuntimeError("claude down")
        return "gpt-response"

    async def fake_rate_limit(model_name: str):
        return None

    monkeypatch.setattr(router, "_init_clients_if_needed", fake_init)
    monkeypatch.setattr(router, "_call_model", fake_call)
    monkeypatch.setattr(router, "_apply_rate_limit", fake_rate_limit)
    monkeypatch.setattr(router, "_is_model_ready", lambda name: True)

    result = await router.get_completion(
        prompt="ping",
        capability=ModelCapability.ANALYSIS,
        preferred_models=["claude-sonnet-4-5", "gpt-5-mini"],
        max_retries=1,
    )

    assert call_attempts["claude"] == 1
    assert result["model"] == "gpt-5-mini"
    assert result["response"] == "gpt-response"

