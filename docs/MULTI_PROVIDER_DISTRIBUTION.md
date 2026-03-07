# Multi-Provider User-Level Distribution

## Problem

Every `get_completion` call tries `claude-sonnet-4-6` first. With N concurrent users, all N hammer Anthropic's rate limit simultaneously while OpenAI sits idle.

## Solution

Hash-based provider affinity — each user gets a deterministic rotation of the model order so different users hit different providers first.

```
User A (hash % 5 = 0) → claude-sonnet-4-6 → gpt-5.2 → gpt-5-mini → ...
User B (hash % 5 = 1) → gpt-5.2 → gpt-5-mini → claude-haiku-4-5 → ...
User C (hash % 5 = 3) → claude-haiku-4-5 → gemini-2.5-flash → claude-sonnet-4-6 → ...
```

Same user always gets the same rotation (deterministic MD5 hash). Fallback still works — if your first-choice provider fails, you fall through to the rest.

## Architecture

```
Request arrives at /unified-brain or /cfo-brain
    │
    ▼
set_provider_affinity(user_id)          ← sets a ContextVar (async-safe)
    │                                      uses: context.user_id > JWT token prefix > random UUID
    ▼
orchestrator.process_request()
    │
    ▼
model_router.get_completion()
    │
    ▼
_get_model_order()                      ← reads ContextVar, rotates default_order
    │
    ▼
base = [sonnet-4.6, gpt-5.2, gpt-5-mini, haiku-4.5, gemini-2.5-flash]
result = base[rotation:] + base[:rotation]
```

### Why ContextVar, not instance state?

`ModelRouter` is a singleton shared across all concurrent requests. Instance-level `self._affinity` would be overwritten by concurrent requests. `ContextVar` gives each async task its own value — the same mechanism Python uses for `decimal.localcontext()`.

## Files Changed

| File | Change |
|------|--------|
| `app/services/model_router.py` | `_provider_affinity` ContextVar, `set_provider_affinity()`, `_get_model_order()` rotation |
| `app/api/endpoints/unified_brain.py` | Wired into `/unified-brain` + `/unified-brain-stream` |
| `app/api/endpoints/cfo_brain.py` | Wired into `/cfo-brain` + `/cfo-brain-stream` |
| `app/endpoints/unified_brain.py` | Wired into legacy `/unified-brain` |

## What it does NOT touch

- **`get_completion()` signature** — zero callers changed
- **Task-routed calls** — explicit `preferred_models` (from `caller_context`) bypass rotation entirely
- **Fallback logic** — if the rotated first-choice fails, circuit breaker + retry still works

## Current State: 2 Providers

Today only Anthropic and OpenAI keys are wired. The rotation distributes users ~50/50 across them. Models without a valid API key will fail on first attempt and fallback kicks in — so the rotation is self-healing.

## Future: Adding Providers

When you add new provider keys (Gemini, Grok, OpenRouter, local Ollama):

1. Add the model config in `_build_default_model_configs()`
2. Add the model name to `default_order` in `_get_model_order()` if you want it in the rotation
3. Done — `% len(base)` automatically distributes across all available models

No other code changes needed. The rotation scales from 2 to N providers automatically.

## User ID Resolution Order

The affinity hash uses the first available identifier:

1. `context.user_id` — passed explicitly from frontend
2. First 32 chars of JWT Bearer token — stable per authenticated user
3. Random UUID — ensures even unauthenticated/anonymous requests get distributed

## Logging

```
[AFFINITY] User abc12345… → rotation offset 3
[_get_model_order] Affinity rotation=3, order: [claude-haiku-4-5, gemini-2.5-flash, claude-sonnet-4-6, ...]
```

## Cost Implications

This is load distribution, not cost optimization. Users rotated to `gpt-5.2` first will cost more per request than users on `gpt-5-mini`. For cost-aware routing, use the existing `ModelTier` / `caller_context` task routing which picks cheap models for trivial tasks — that system is orthogonal and unaffected by this change.
