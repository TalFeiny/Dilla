"""
Model Router with Fallback Support
Handles multiple LLM providers with automatic failover
"""

import os
import asyncio
import logging
from typing import AsyncGenerator, Dict, Any, Optional, List, Tuple
from enum import Enum
import time
import random
from datetime import datetime, timedelta
import aiohttp
import importlib
import json
import hashlib
from collections import deque
from contextvars import ContextVar
from dataclasses import dataclass, field

# Import settings
from app.core.config import settings

logger = logging.getLogger(__name__)

# ── Per-request provider affinity ────────────────────────────────────
# Async-safe contextvar: each concurrent request gets its own rotation
# offset so different users hit different providers first.
_provider_affinity: ContextVar[int] = ContextVar("_provider_affinity", default=0)


def set_provider_affinity(user_id: str) -> int:
    """Set provider rotation offset for the current async context.

    Call once at the API entry point (e.g. unified_brain) before any
    get_completion calls.  The offset is derived from a stable hash of
    the user_id so the same user always gets the same rotation —
    distributing concurrent users across providers.

    Returns the computed offset (useful for logging).
    """
    offset = int(hashlib.md5(user_id.encode()).hexdigest(), 16)
    _provider_affinity.set(offset)
    logger.info(f"[AFFINITY] User {user_id[:8]}… → rotation offset {offset % 5}")
    return offset


class ModelProvider(Enum):
    """Available model providers"""
    ANTHROPIC = "anthropic"
    OPENAI = "openai"
    GOOGLE = "google"
    GROQ = "groq"
    OLLAMA = "ollama"
    TOGETHER = "together"
    PERPLEXITY = "perplexity"
    ANYSCALE = "anyscale"


class ModelCapability(Enum):
    """Model capabilities for routing decisions"""
    ANALYSIS = "analysis"
    CODE = "code"
    STRUCTURED = "structured"
    CREATIVE = "creative"
    FAST = "fast"
    CHEAP = "cheap"


class ModelTier(Enum):
    """Cost/quality tiers for intelligent routing."""
    TRIVIAL = "trivial"    # Classification, routing, yes/no — cheapest possible
    CHEAP = "cheap"        # Bulk extraction, simple structured output
    QUALITY = "quality"    # Analysis, reasoning, narratives — primary workhorse
    PREMIUM = "premium"    # Complex synthesis, deep reasoning, final memos


@dataclass
class IterationCost:
    """Track cost for a single agent loop iteration."""
    reason_tokens: int = 0
    reason_cost: float = 0.0
    reflect_tokens: int = 0
    reflect_cost: float = 0.0


class RequestBudget:
    """Tracks cumulative token usage and cost for a single agent request."""

    def __init__(self, max_cost: float = 2.0, max_tokens: int = 500_000):
        self.max_cost = max_cost
        self.max_tokens = max_tokens
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.total_cost = 0.0
        self.calls: List[Dict[str, Any]] = []
        self.iterations: List[IterationCost] = []
        self.external_calls: int = 0
        self.external_cost: float = 0.0

    @property
    def remaining_cost(self) -> float:
        return max(0.0, self.max_cost - self.total_cost)

    @property
    def exhausted(self) -> bool:
        return self.total_cost >= self.max_cost or (self.total_input_tokens + self.total_output_tokens) >= self.max_tokens

    def record(self, input_tokens: int, output_tokens: int, cost: float, model: str):
        self.total_input_tokens += input_tokens
        self.total_output_tokens += output_tokens
        self.total_cost += cost
        self.calls.append({
            "model": model,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cost": cost,
        })

    def record_external(self, service: str, cost: float):
        """Record an external API call (e.g. Tavily search)."""
        self.external_calls += 1
        self.external_cost += cost
        self.total_cost += cost
        self.calls.append({
            "model": f"external:{service}",
            "input_tokens": 0,
            "output_tokens": 0,
            "cost": cost,
        })

    def warn_if_expensive(self, caller: str) -> Optional[str]:
        """Return warning string if budget is >60% consumed."""
        pct = self.total_cost / self.max_cost if self.max_cost > 0 else 0
        if pct > 0.6:
            return f"Budget {pct:.0%} consumed (${self.total_cost:.3f}/${self.max_cost}). Caller: {caller}"
        return None

    def summary(self) -> Dict[str, Any]:
        return {
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "total_cost": round(self.total_cost, 4),
            "remaining_cost": round(self.remaining_cost, 4),
            "num_calls": len(self.calls),
            "exhausted": self.exhausted,
            "iterations": len(self.iterations),
            "external_calls": self.external_calls,
            "external_cost": round(self.external_cost, 4),
        }


# ── Provider-Agnostic Tool Adapter ───────────────────────────────────
# Converts between canonical tool format and provider-specific formats.
# Canonical format follows Anthropic's schema (most explicit):
#   {"name": str, "description": str, "input_schema": {JSON Schema}}
# Each provider adapter converts definitions AND parses responses.


class ToolAdapter:
    """Convert tool definitions + responses between providers."""

    # ── Informal schema → JSON Schema ────────────────────────────────
    # AGENT_TOOLS use shorthand like {"query": "str", "filters": "dict?"}
    # This converts to proper JSON Schema for provider APIs.

    _TYPE_MAP = {
        "str": {"type": "string"},
        "string": {"type": "string"},
        "int": {"type": "integer"},
        "float": {"type": "number"},
        "number": {"type": "number"},
        "bool": {"type": "boolean"},
        "boolean": {"type": "boolean"},
        "dict": {"type": "object"},
        "object": {"type": "object"},
        "any": {},
        "list": {"type": "array"},
    }

    @classmethod
    def informal_to_json_schema(cls, informal: dict) -> dict:
        """Convert informal input_schema to JSON Schema.

        Example: {"query": "str", "filters": "dict?", "columns": "list[str]?"}
        → {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "filters": {"type": "object"},
                "columns": {"type": "array", "items": {"type": "string"}}
            },
            "required": ["query"]
          }
        """
        properties = {}
        required = []

        for name, type_hint in informal.items():
            hint = str(type_hint).strip()
            optional = hint.endswith("?")
            if optional:
                hint = hint[:-1].strip()

            prop = cls._parse_type_hint(hint)
            properties[name] = prop

            if not optional:
                required.append(name)

        schema: dict = {"type": "object", "properties": properties}
        if required:
            schema["required"] = required
        return schema

    @classmethod
    def _parse_type_hint(cls, hint: str) -> dict:
        """Parse a single type hint like 'str', 'list[str]', 'list[dict]'."""
        # Handle list[X] pattern
        if hint.startswith("list[") and hint.endswith("]"):
            inner = hint[5:-1].strip()
            inner_schema = cls._parse_type_hint(inner)
            return {"type": "array", "items": inner_schema}
        # Handle list without inner type
        if hint == "list":
            return {"type": "array"}
        # Handle complex dict/object descriptions (just map to object)
        if hint.startswith("{") or hint.startswith("list[{"):
            return {"type": "array", "items": {"type": "object"}}
        # Direct type lookup
        return dict(cls._TYPE_MAP.get(hint.lower(), {}))

    # ── Definitions: Canonical → Provider ────────────────────────────

    @staticmethod
    def to_anthropic(tools: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Canonical → Anthropic format (already canonical, pass through)."""
        return tools

    @staticmethod
    def to_openai(tools: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Canonical → OpenAI function-calling format.

        Anthropic: {"name", "description", "input_schema": {JSON Schema}}
        OpenAI:    {"type": "function", "function": {"name", "description", "parameters": {JSON Schema}}}
        """
        out = []
        for tool in tools:
            out.append({
                "type": "function",
                "function": {
                    "name": tool["name"],
                    "description": tool.get("description", ""),
                    "parameters": tool.get("input_schema", {"type": "object", "properties": {}}),
                },
            })
        return out

    @staticmethod
    def to_google(tools: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Canonical → Google Gemini function_declarations format.

        Google: [{"function_declarations": [{"name", "description", "parameters": {JSON Schema}}]}]
        """
        declarations = []
        for tool in tools:
            schema = dict(tool.get("input_schema", {"type": "object", "properties": {}}))
            # Google doesn't support 'additionalProperties' in function declarations
            schema.pop("additionalProperties", None)
            declarations.append({
                "name": tool["name"],
                "description": tool.get("description", ""),
                "parameters": schema,
            })
        return [{"function_declarations": declarations}]

    @staticmethod
    def to_openai_compatible(tools: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Canonical → OpenAI-compatible format (Groq, Together, DeepSeek, etc.)."""
        return ToolAdapter.to_openai(tools)

    # ── Response Parsing: Provider → Canonical ───────────────────────
    # Canonical response:
    # {
    #   "text_parts": [str, ...],
    #   "tool_calls": [{"id": str, "name": str, "input": dict}, ...],
    #   "stop_reason": "end_turn" | "tool_use",
    #   "usage": {"input_tokens": int, "output_tokens": int},
    # }

    @staticmethod
    def parse_anthropic_response(response) -> Dict[str, Any]:
        """Parse Anthropic Messages API response → canonical."""
        text_parts = []
        tool_calls = []
        for block in response.content:
            btype = getattr(block, "type", None)
            if btype == "text":
                text_parts.append(block.text)
            elif btype == "tool_use":
                tool_calls.append({
                    "id": block.id,
                    "name": block.name,
                    "input": block.input,
                })
        usage = {"input_tokens": 0, "output_tokens": 0}
        if hasattr(response, "usage") and response.usage:
            usage["input_tokens"] = getattr(response.usage, "input_tokens", 0)
            usage["output_tokens"] = getattr(response.usage, "output_tokens", 0)
        return {
            "text_parts": text_parts,
            "tool_calls": tool_calls,
            "stop_reason": "tool_use" if tool_calls else "end_turn",
            "usage": usage,
        }

    @staticmethod
    def parse_openai_response(response) -> Dict[str, Any]:
        """Parse OpenAI chat completion response → canonical."""
        message = response.choices[0].message
        text_parts = [message.content] if message.content else []
        tool_calls = []
        if message.tool_calls:
            for tc in message.tool_calls:
                try:
                    args = json.loads(tc.function.arguments) if tc.function.arguments else {}
                except (json.JSONDecodeError, TypeError):
                    args = {}
                tool_calls.append({
                    "id": tc.id,
                    "name": tc.function.name,
                    "input": args,
                })
        usage = {"input_tokens": 0, "output_tokens": 0}
        if hasattr(response, "usage") and response.usage:
            usage["input_tokens"] = getattr(response.usage, "prompt_tokens", 0) or 0
            usage["output_tokens"] = getattr(response.usage, "completion_tokens", 0) or 0
        return {
            "text_parts": text_parts,
            "tool_calls": tool_calls,
            "stop_reason": "tool_use" if tool_calls else "end_turn",
            "usage": usage,
        }

    @staticmethod
    def parse_google_response(response) -> Dict[str, Any]:
        """Parse Google Gemini response → canonical."""
        text_parts = []
        tool_calls = []
        for part in response.parts:
            if hasattr(part, "text") and part.text:
                text_parts.append(part.text)
            elif hasattr(part, "function_call") and part.function_call:
                fc = part.function_call
                tool_calls.append({
                    "id": f"google_{fc.name}_{id(fc)}",
                    "name": fc.name,
                    "input": dict(fc.args) if fc.args else {},
                })
        usage = {"input_tokens": 0, "output_tokens": 0}
        if hasattr(response, "usage_metadata") and response.usage_metadata:
            usage["input_tokens"] = getattr(response.usage_metadata, "prompt_token_count", 0) or 0
            usage["output_tokens"] = getattr(response.usage_metadata, "candidates_token_count", 0) or 0
        return {
            "text_parts": text_parts,
            "tool_calls": tool_calls,
            "stop_reason": "tool_use" if tool_calls else "end_turn",
            "usage": usage,
        }

    # ── Tool Results: Format for each provider ───────────────────────

    @staticmethod
    def format_tool_results_anthropic(
        tool_results: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Format tool results as Anthropic user message.

        Input: [{"id": str, "result": str, "is_error": bool}, ...]
        Output: {"role": "user", "content": [{"type": "tool_result", ...}, ...]}
        """
        content = []
        for tr in tool_results:
            block: Dict[str, Any] = {
                "type": "tool_result",
                "tool_use_id": tr["id"],
                "content": tr["result"],
            }
            if tr.get("is_error"):
                block["is_error"] = True
            content.append(block)
        return {"role": "user", "content": content}

    @staticmethod
    def format_tool_results_openai(
        tool_results: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Format tool results as OpenAI tool messages.

        Input: [{"id": str, "result": str, "is_error": bool}, ...]
        Output: [{"role": "tool", "tool_call_id": str, "content": str}, ...]
        """
        return [
            {
                "role": "tool",
                "tool_call_id": tr["id"],
                "content": tr["result"],
            }
            for tr in tool_results
        ]

    @staticmethod
    def format_tool_results_google(
        tool_results: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Format tool results for Google Gemini.

        Returns a Part with function_response for each result.
        """
        parts = []
        for tr in tool_results:
            try:
                result_data = json.loads(tr["result"]) if isinstance(tr["result"], str) else tr["result"]
            except (json.JSONDecodeError, TypeError):
                result_data = {"result": tr["result"]}
            parts.append({
                "function_response": {
                    "name": tr.get("name", "unknown"),
                    "response": result_data,
                }
            })
        return parts

    # ── Assistant message reconstruction ─────────────────────────────
    # After tool execution, we need to add the assistant's message back
    # to the conversation in the provider's format.

    @staticmethod
    def format_assistant_message_anthropic(parsed: Dict[str, Any]) -> Dict[str, Any]:
        """Reconstruct Anthropic assistant message from canonical parsed response."""
        content = []
        for text in parsed["text_parts"]:
            content.append({"type": "text", "text": text})
        for tc in parsed["tool_calls"]:
            content.append({
                "type": "tool_use",
                "id": tc["id"],
                "name": tc["name"],
                "input": tc["input"],
            })
        return {"role": "assistant", "content": content}

    @staticmethod
    def format_assistant_message_openai(parsed: Dict[str, Any]) -> Dict[str, Any]:
        """Reconstruct OpenAI assistant message from canonical parsed response."""
        msg: Dict[str, Any] = {"role": "assistant"}
        if parsed["text_parts"]:
            msg["content"] = "\n".join(parsed["text_parts"])
        else:
            msg["content"] = None
        if parsed["tool_calls"]:
            msg["tool_calls"] = [
                {
                    "id": tc["id"],
                    "type": "function",
                    "function": {
                        "name": tc["name"],
                        "arguments": json.dumps(tc["input"]),
                    },
                }
                for tc in parsed["tool_calls"]
            ]
        return msg


class ModelRouter:
    """
    Routes requests to different models with fallback support
    Handles rate limiting, errors, and cost optimization
    """

    def __init__(self):
        # Initialize API clients (lazy initialization - don't create async clients here)
        self.anthropic_client = None
        self.openai_client = None
        self.groq_client = None
        self.session = None
        self._genai_module = None
        self._clients_initialized = False

        # Per-request budget (set externally before a chain runs)
        self._active_budget: Optional[RequestBudget] = None

        # Core state objects used before any async initialization occurs
        self.rate_limits: Dict[str, Any] = {}
        self.last_request_time: Dict[str, float] = {}
        self.error_counts: Dict[str, int] = {}
        self.circuit_breaker_until: Dict[str, datetime] = {}
        self.request_queues: Dict[str, asyncio.Queue] = {}
        self.active_requests: Dict[str, int] = {}
        self.max_concurrent_per_model: Dict[str, int] = {
            "claude-sonnet-4-6": 3,
            "claude-sonnet-4-5": 3,
            "claude-haiku-4-5": 8,
            "gpt-5-mini": 5,
            "gpt-5.2": 2,
            "gemini-2.5-flash": 10,
            "gemini-2.5-pro": 5,
            "mixtral-8x7b": 10,
            "llama2-70b": 10,
        }
        self.default_max_concurrent = 3
        self.request_cache: Dict[str, Tuple[Dict[str, Any], float]] = {}
        self.cache_ttl = 300  # 5 minutes cache TTL
        self.queue_processors: Dict[str, asyncio.Task] = {}
        
        # Load API keys from settings
        self.anthropic_key = settings.ANTHROPIC_API_KEY
        self.openai_key = settings.OPENAI_API_KEY
        self.google_key = settings.GOOGLE_API_KEY
        self.groq_key = os.getenv("GROQ_API_KEY")  # Not in settings yet, keeping os.getenv
        self.together_key = os.getenv("TOGETHER_API_KEY")  # Not in settings yet, keeping os.getenv
        self.perplexity_key = os.getenv("PERPLEXITY_API_KEY")  # Not in settings yet, keeping os.getenv
        self.anyscale_key = os.getenv("ANYSCALE_API_KEY")  # Not in settings yet, keeping os.getenv
        
        # VERIFY INITIALIZATION: Log which API keys are available
        logger.info(f"[MODEL_ROUTER_INIT] 🚀 Initializing ModelRouter...")
        logger.info(f"[MODEL_ROUTER_INIT] 📋 API Keys Status:")
        logger.info(f"[MODEL_ROUTER_INIT]   - Anthropic: {'✅ Present' if self.anthropic_key else '❌ Missing'}")
        logger.info(f"[MODEL_ROUTER_INIT]   - OpenAI: {'✅ Present' if self.openai_key else '❌ Missing'}")
        logger.info(f"[MODEL_ROUTER_INIT]   - Groq: {'✅ Present' if self.groq_key else '❌ Missing'}")
        logger.info(f"[MODEL_ROUTER_INIT]   - Google: {'✅ Present' if self.google_key else '❌ Missing'}")
        logger.info(f"[MODEL_ROUTER_INIT]   - Together: {'✅ Present' if self.together_key else '❌ Missing'}")
        logger.info(f"[MODEL_ROUTER_INIT]   - Perplexity: {'✅ Present' if self.perplexity_key else '❌ Missing'}")
        logger.info(f"[MODEL_ROUTER_INIT]   - Anyscale: {'✅ Present' if self.anyscale_key else '❌ Missing'}")
        
        # DON'T initialize clients here - do it lazily in async context
        # This prevents "no current event loop" errors during synchronous initialization
        
        # Model configurations with capabilities and costs
        self.model_configs: Dict[str, Dict[str, Any]] = {}
        self.model_configs = self._build_default_model_configs()
        
        # LOG MODEL CONFIGS: Show registered models (must be after model_configs is defined)
        logger.info(f"[MODEL_ROUTER_INIT] 📊 Registered model configs: {len(self.model_configs)} models")
        for name, config in self.model_configs.items():
            capabilities = [c.value for c in config["capabilities"]]
            logger.info(f"[MODEL_ROUTER_INIT]   - {name}: provider={config['provider'].value}, capabilities={capabilities}, priority={config['priority']}")
        
        # Summary: Check if any LLM keys are available
        available_keys = [
            name for name, key in [
                ("Anthropic", self.anthropic_key),
                ("OpenAI", self.openai_key),
                ("Google", self.google_key),
                ("Groq", self.groq_key),
                ("Together", self.together_key),
                ("Perplexity", self.perplexity_key),
                ("Anyscale", self.anyscale_key)
            ] if key
        ]
        
        if available_keys:
            logger.info(f"[MODEL_ROUTER_INIT] ✅ ModelRouter ready with {len(available_keys)} API key(s): {', '.join(available_keys)}")
        else:
            logger.error("=" * 80)
            logger.error("🔴 [MODEL_ROUTER_INIT] CRITICAL: NO LLM API KEYS CONFIGURED!")
            logger.error("🔴 [MODEL_ROUTER_INIT] ModelRouter will NOT work without at least one API key")
            logger.error("🔴 [MODEL_ROUTER_INIT] Configure at least one of: ANTHROPIC_API_KEY, OPENAI_API_KEY, GOOGLE_API_KEY, GROQ_API_KEY, etc.")
            logger.error("=" * 80)
        
    def _build_default_model_configs(self) -> Dict[str, Dict[str, Any]]:
        """Build the default set of model configurations with defensive logging."""
        try:
            configs: Dict[str, Dict[str, Any]] = {
                # ── Anthropic Models ──────────────────────────────────
                "claude-sonnet-4-6": {
                    "provider": ModelProvider.ANTHROPIC,
                    "model": "claude-sonnet-4-6",
                    "capabilities": [ModelCapability.ANALYSIS, ModelCapability.CODE, ModelCapability.STRUCTURED, ModelCapability.CREATIVE],
                    "max_tokens": 4096,
                    "cost_per_1k_input": 0.003,
                    "cost_per_1k_output": 0.015,
                    "tier": ModelTier.QUALITY,
                    "priority": 1,
                },
                "claude-haiku-4-5": {
                    "provider": ModelProvider.ANTHROPIC,
                    "model": "claude-haiku-4-5",
                    "capabilities": [ModelCapability.ANALYSIS, ModelCapability.STRUCTURED, ModelCapability.FAST, ModelCapability.CHEAP],
                    "max_tokens": 4096,
                    "cost_per_1k_input": 0.001,
                    "cost_per_1k_output": 0.005,
                    "tier": ModelTier.TRIVIAL,
                    "priority": 2,
                },
                # Keep legacy alias so existing preferred_models references don't break
                "claude-sonnet-4-5": {
                    "provider": ModelProvider.ANTHROPIC,
                    "model": "claude-sonnet-4-6",  # silently upgraded
                    "capabilities": [ModelCapability.ANALYSIS, ModelCapability.CODE, ModelCapability.STRUCTURED, ModelCapability.CREATIVE],
                    "max_tokens": 4096,
                    "cost_per_1k_input": 0.003,
                    "cost_per_1k_output": 0.015,
                    "tier": ModelTier.QUALITY,
                    "priority": 1,
                },

                # ── OpenAI Models ─────────────────────────────────────
                "gpt-5-mini": {
                    "provider": ModelProvider.OPENAI,
                    "model": "gpt-5-mini",
                    "capabilities": [ModelCapability.ANALYSIS, ModelCapability.CODE, ModelCapability.STRUCTURED, ModelCapability.FAST, ModelCapability.CHEAP],
                    "max_tokens": 4096,
                    "cost_per_1k_input": 0.00025,   # corrected from 0.0005
                    "cost_per_1k_output": 0.002,     # corrected from 0.0015
                    "tier": ModelTier.CHEAP,
                    "priority": 2,
                },
                "gpt-5.2": {
                    "provider": ModelProvider.OPENAI,
                    "model": "gpt-5.2",
                    "capabilities": [ModelCapability.ANALYSIS, ModelCapability.CODE, ModelCapability.STRUCTURED],
                    "max_tokens": 8192,
                    "cost_per_1k_input": 0.01,
                    "cost_per_1k_output": 0.03,
                    "tier": ModelTier.PREMIUM,
                    "priority": 1,
                },

                # ── Google Models ─────────────────────────────────────
                "gemini-2.5-flash": {
                    "provider": ModelProvider.GOOGLE,
                    "model": "gemini-2.5-flash",
                    "capabilities": [ModelCapability.ANALYSIS, ModelCapability.STRUCTURED, ModelCapability.FAST, ModelCapability.CHEAP],
                    "max_tokens": 4096,
                    "cost_per_1k_input": 0.00015,
                    "cost_per_1k_output": 0.0006,
                    "tier": ModelTier.TRIVIAL,
                    "priority": 3,
                },
                "gemini-2.5-pro": {
                    "provider": ModelProvider.GOOGLE,
                    "model": "gemini-2.5-pro",
                    "capabilities": [ModelCapability.ANALYSIS, ModelCapability.STRUCTURED],
                    "max_tokens": 4096,
                    "cost_per_1k_input": 0.00125,
                    "cost_per_1k_output": 0.01,
                    "tier": ModelTier.QUALITY,
                    "priority": 3,
                },

                # ── Groq Models (ultra-fast inference) ────────────────
                "mixtral-8x7b": {
                    "provider": ModelProvider.GROQ,
                    "model": "mixtral-8x7b-32768",
                    "capabilities": [ModelCapability.FAST, ModelCapability.CHEAP, ModelCapability.CODE],
                    "max_tokens": 4096,
                    "cost_per_1k_input": 0.00024,
                    "cost_per_1k_output": 0.00024,
                    "tier": ModelTier.TRIVIAL,
                    "priority": 2,
                },
                "llama2-70b": {
                    "provider": ModelProvider.GROQ,
                    "model": "llama2-70b-4096",
                    "capabilities": [ModelCapability.FAST, ModelCapability.CHEAP],
                    "max_tokens": 4096,
                    "cost_per_1k_input": 0.0007,
                    "cost_per_1k_output": 0.0008,
                    "tier": ModelTier.CHEAP,
                    "priority": 3,
                },

                # ── Together AI Models ────────────────────────────────
                "llama-3-70b": {
                    "provider": ModelProvider.TOGETHER,
                    "model": "meta-llama/Llama-3-70b-chat-hf",
                    "capabilities": [ModelCapability.FAST, ModelCapability.CHEAP],
                    "max_tokens": 4096,
                    "cost_per_1k_input": 0.00059,    # corrected from 0.0009
                    "cost_per_1k_output": 0.00079,   # corrected from 0.0009
                    "tier": ModelTier.CHEAP,
                    "priority": 3,
                },

                # ── Ollama Local Models (free but slower) ─────────────
                "ollama-mixtral": {
                    "provider": ModelProvider.OLLAMA,
                    "model": "mixtral:8x7b",
                    "capabilities": [ModelCapability.CHEAP],
                    "max_tokens": 4096,
                    "cost_per_1k_input": 0,
                    "cost_per_1k_output": 0,
                    "tier": ModelTier.TRIVIAL,
                    "priority": 5,
                },
            }
            return configs
        except Exception as config_error:
            logger.critical(f"[MODEL_ROUTER_INIT] ❌ Failed to build model configurations: {config_error}")
            raise
        
        # Queue processors (background tasks)
        self.queue_processors: Dict[str, asyncio.Task] = {}
        
    async def _init_clients_if_needed(self):
        """Lazy initialization of API clients - only call this from async context"""
        logger.info(f"[_init_clients] Called - clients_initialized={self._clients_initialized}")
        
        if self._clients_initialized:
            logger.info("[_init_clients] Clients already initialized, skipping")
            return
        
        logger.info("[_init_clients] 🚀 Starting client initialization...")
        
        # Clear any stale circuit breakers on startup
        logger.info("[_init_clients] Clearing any stale circuit breakers")
        self.circuit_breaker_until.clear()
        self.error_counts.clear()
        logger.info("[_init_clients] ✅ Cleared all circuit breakers and error counts")
            
        try:
            if self.anthropic_key:
                logger.info("[_init_clients] Initializing Anthropic client...")
                try:
                    anthropic_module = importlib.import_module("anthropic")
                    AsyncAnthropic = getattr(anthropic_module, "AsyncAnthropic")
                    self.anthropic_client = AsyncAnthropic(
                        api_key=self.anthropic_key,
                        timeout=300.0,  # 5min per-request timeout (SDK default is 600s)
                    )
                    logger.info("[_init_clients] ✅ Anthropic client initialized successfully")
                except ImportError as exc:
                    logger.warning(f"[_init_clients] ⚠️  Anthropic SDK not available: {exc}")
                    self.anthropic_client = None
                except AttributeError as exc:
                    logger.error(f"[_init_clients] ❌ Anthropic SDK missing AsyncAnthropic: {exc}")
                    self.anthropic_client = None
            else:
                logger.warning("[_init_clients] ⚠️  NO ANTHROPIC_API_KEY - Claude models will not work!")
                self.anthropic_client = None
            
            if self.openai_key:
                logger.info("[_init_clients] Initializing OpenAI client...")
                if not self.openai_key or not isinstance(self.openai_key, str) or len(self.openai_key.strip()) == 0:
                    logger.error("[_init_clients] ❌ Invalid OpenAI API key format")
                    raise ValueError("Invalid OpenAI API key")
                    
                try:
                    openai_module = importlib.import_module("openai")
                    AsyncOpenAI = getattr(openai_module, "AsyncOpenAI")
                    self.openai_client = AsyncOpenAI(api_key=self.openai_key)
                    if not self.openai_client:
                        raise ValueError("Failed to create OpenAI client - client is None")
                    logger.info("[_init_clients] ✅ OpenAI client initialized successfully")
                except Exception as exc:
                    logger.warning(f"[_init_clients] ⚠️  OpenAI client init failed (non-fatal, Anthropic still available): {exc}")
                    self.openai_client = None
            else:
                logger.warning("[_init_clients] ⚠️  NO OPENAI_API_KEY - OpenAI models will not work!")
                self.openai_client = None
                
            if self.groq_key:
                logger.info("[_init_clients] Initializing Groq client...")
                if not self.groq_key or not isinstance(self.groq_key, str) or len(self.groq_key.strip()) == 0:
                    logger.warning("[_init_clients] ⚠️  Invalid Groq API key format, skipping")
                else:
                    try:
                        groq_module = importlib.import_module("groq")
                        AsyncGroq = getattr(groq_module, "AsyncGroq")
                        self.groq_client = AsyncGroq(api_key=self.groq_key)
                        if not self.groq_client:
                            logger.warning("[_init_clients] ⚠️  Failed to create Groq client")
                        else:
                            logger.info("[_init_clients] ✅ Groq client initialized successfully")
                    except Exception as exc:
                        logger.warning(f"[_init_clients] ⚠️  Groq client init failed (non-fatal): {exc}")
                        self.groq_client = None
            
            if self.google_key:
                logger.info("[_init_clients] Configuring Google Gemini...")
                if not self.google_key or not isinstance(self.google_key, str) or len(self.google_key.strip()) == 0:
                    logger.warning("[_init_clients] ⚠️  Invalid Google API key format, skipping")
                else:
                    try:
                        self._genai_module = importlib.import_module("google.generativeai")
                        self._genai_module.configure(api_key=self.google_key)
                        logger.info("[_init_clients] ✅ Google Gemini configured successfully")
                    except ImportError as exc:
                        logger.warning(f"[_init_clients] ⚠️  Google generative AI SDK not available: {exc}")
                        self._genai_module = None
                    except Exception as exc:
                        logger.error(f"[_init_clients] ❌ Failed to configure Google Gemini: {exc}")
                        self._genai_module = None
            
            self._clients_initialized = True
            logger.info("[_init_clients] ✅ All clients initialized successfully")
        except Exception as e:
            logger.error(f"[_init_clients] ❌ Unexpected error during client init: {e}")
            import traceback
            logger.error(f"[_init_clients] Traceback: {traceback.format_exc()}")
            # Still mark as initialized — preserve any clients that succeeded
            self._clients_initialized = True
            initialized = []
            if self.anthropic_client: initialized.append("Anthropic")
            if self.openai_client: initialized.append("OpenAI")
            if self.groq_client: initialized.append("Groq")
            if self._genai_module: initialized.append("Google")
            if initialized:
                logger.warning(f"[_init_clients] ⚠️  Partial init — available providers: {', '.join(initialized)}")
            else:
                logger.error("[_init_clients] ❌ No providers initialized at all")
    
    async def get_completion(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        capability: ModelCapability = ModelCapability.ANALYSIS,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        preferred_models: Optional[List[str]] = None,
        max_retries: int = 3,
        fallback_enabled: bool = True,
        json_mode: bool = False,
        caller_context: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get completion with automatic fallback
        
        Args:
            prompt: User prompt
            system_prompt: System instructions
            capability: Required capability for model selection
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature
            preferred_models: List of preferred model names
            max_retries: Maximum retry attempts per model
            fallback_enabled: Whether to fallback to other models on failure
            json_mode: Whether to request JSON format output
            caller_context: Optional context about which skill/operation is calling (for error logging)
        
        Returns:
            Dict with response, model used, cost, and latency
        """
        
        # Budget check — if a budget is active and exhausted, fail fast
        if self._active_budget and self._active_budget.exhausted:
            raise Exception(
                f"Request budget exhausted (${self._active_budget.total_cost:.2f} / "
                f"${self._active_budget.max_cost:.2f}). Returning partial results."
            )

        # COMPREHENSIVE LOGGING: Log all get_completion calls with full context
        context_info = f" (called by: {caller_context})" if caller_context else ""
        prompt_length = len(prompt)
        system_length = len(system_prompt) if system_prompt else 0
        total_length = prompt_length + system_length
        
        logger.info(f"[MODEL_ROUTER] 🚀 get_completion called{context_info}")
        logger.info(f"[MODEL_ROUTER] 📊 Prompt length: {prompt_length:,} chars | System prompt: {system_length:,} chars | Total: {total_length:,} chars")
        logger.info(f"[MODEL_ROUTER] 🎯 Capability: {capability.value} | Max tokens: {max_tokens} | Temperature: {temperature}")
        logger.info(f"[MODEL_ROUTER] 📋 Preferred models: {preferred_models} | JSON mode: {json_mode} | Fallback: {fallback_enabled}")
        logger.info(f"[MODEL_ROUTER] 📝 Prompt preview (first 200 chars): {prompt[:200]}...")
        
        # Check cache first (only for non-json_mode requests to avoid stale structured data)
        if not json_mode:
            cache_key = self._get_request_cache_key(prompt, system_prompt, "any", max_tokens, temperature)
            cached = self._get_cached_response(cache_key)
            if cached:
                logger.info(f"[MODEL_ROUTER] ✅ Returning cached response")
                return cached
        
        # Lazy initialization of clients in async context
        await self._init_clients_if_needed()
        
        # Auto-route to cheap/quality model based on caller_context if no explicit preference
        if not preferred_models and caller_context:
            preferred_models = self.preferred_models_for_task(caller_context)
            if preferred_models:
                logger.info(f"[MODEL_ROUTER] Task-routed {caller_context} → {preferred_models[0]}")

        # Get ordered list of models based on capability and preference
        models = self._get_model_order(capability, preferred_models)
        
        # CRITICAL: Log if no models found
        if not models:
            logger.error(f"[MODEL_ROUTER] ❌ NO MODELS FOUND for capability={capability}, preferred={preferred_models}")
            logger.error(f"[MODEL_ROUTER] Available model configs: {list(self.model_configs.keys())}")
            # Show capabilities of each model
            for name, config in self.model_configs.items():
                logger.error(f"[MODEL_ROUTER] {name}: capabilities={config['capabilities']}")
            raise Exception(f"No models available for capability={capability.value}")
        
        logger.info(f"[MODEL_ROUTER] 🎯 Models to try in order: {models}")
        logger.info(f"[MODEL_ROUTER] 📋 Preferred models requested: {preferred_models}")
        logger.info(f"[MODEL_ROUTER] 🎯 Capability requested: {capability.value}")
        logger.info(f"[MODEL_ROUTER] Current circuit breaker state: {self.circuit_breaker_until}")
        logger.info(f"[MODEL_ROUTER] Current error counts: {self.error_counts}")
        
        # Check if all models are blocked by circuit breakers - if so, reset them all
        ready_models = [m for m in models if self._is_model_ready(m)]
        blocked_models = [m for m in ready_models if self._is_circuit_broken(m)]
        if len(ready_models) > 0 and len(blocked_models) == len(ready_models):
            logger.warning(f"[MODEL_ROUTER] ⚠️  ALL {len(blocked_models)} ready models are blocked by circuit breakers - resetting all")
            self.reset_circuit_breakers()
        
        last_error = None
        for idx, model_name in enumerate(models):
            model_config = self.model_configs[model_name]
            
            # Check circuit breaker
            logger.info(f"[MODEL_ROUTER] Attempting model: {model_name}")

            if not self._is_model_ready(model_name):
                logger.warning(f"[MODEL_ROUTER] ⚠️  Skipping {model_name} - client not initialized or API key missing")
                continue

            # If this is the last available model and circuit breaker is active, try anyway
            # This prevents all models from being blocked simultaneously
            is_last_model = (idx == len(models) - 1)
            is_circuit_broken = self._is_circuit_broken(model_name)
            
            if is_circuit_broken and not is_last_model:
                logger.warning(f"[MODEL_ROUTER] ⚠️  Skipping {model_name} - circuit breaker active")
                continue
            elif is_circuit_broken and is_last_model:
                logger.warning(f"[MODEL_ROUTER] ⚠️  Last model {model_name} has circuit breaker, but trying anyway to avoid total failure")
                # Reset circuit breaker for this attempt
                self.reset_circuit_breakers(model_name)
            
            logger.info(f"[MODEL_ROUTER] ✅ {model_name} passed circuit breaker check")
            
            # Wait for concurrency slot
            await self._wait_for_slot(model_name)
            
            try:
                # Try the model with retries
                for retry in range(max_retries):
                    try:
                        start_time = time.time()
                        
                        # Add delay for rate limiting
                        await self._apply_rate_limit(model_name)
                        
                        # Route to appropriate provider with json_mode for structured output
                        # Per-model timeout scales with max_tokens + prompt size:
                        # large extractions (legal docs, 16k tokens) need more time.
                        input_size_factor = (prompt_length + system_length) // 2000  # ~1s per 2k chars
                        per_call_timeout = max(120, min(600, max_tokens // 50 + input_size_factor * 5))
                        response_text, usage = await asyncio.wait_for(
                            self._call_model(
                                model_config,
                                prompt,
                                system_prompt,
                                max_tokens,
                                temperature,
                                json_mode
                            ),
                            timeout=per_call_timeout,
                        )

                        # Use real token counts from provider; fall back to estimate
                        input_tokens = usage.get("input_tokens", 0) or int((prompt_length + system_length) / 4)
                        output_tokens = usage.get("output_tokens", 0) or int(len(response_text) / 4)

                        # Calculate cost and latency using real token counts
                        latency = time.time() - start_time
                        cost = self._calculate_cost(model_config, input_tokens, output_tokens)

                        # Reset error count on success
                        self.error_counts[model_name] = 0

                        # COMPREHENSIVE LOGGING: Log successful model router calls
                        logger.info(f"[MODEL_ROUTER] ✅ SUCCESS with {model_name}{context_info}")
                        logger.info(f"[MODEL_ROUTER] 📊 Model: {model_name} | Provider: {model_config['provider'].value}")
                        logger.info(f"[MODEL_ROUTER] ⏱️  Latency: {latency:.2f}s | Cost: ${cost:.4f}")
                        logger.info(f"[MODEL_ROUTER] 📏 Tokens in={input_tokens} out={output_tokens} | Retry: {retry}")
                        logger.info(f"[MODEL_ROUTER] 📝 Response preview: {response_text[:200]}...")

                        # Record in active budget if set
                        if self._active_budget:
                            self._active_budget.record(input_tokens, output_tokens, cost, model_name)

                        result = {
                            "response": response_text,
                            "model": model_name,
                            "provider": model_config["provider"].value,
                            "cost": cost,
                            "latency": latency,
                            "retry_count": retry,
                            "input_tokens": input_tokens,
                            "output_tokens": output_tokens,
                        }

                        # Cache result (only for non-json_mode to avoid stale structured data)
                        if not json_mode:
                            cache_key = self._get_request_cache_key(prompt, system_prompt, model_name, max_tokens, temperature)
                            self._cache_response(cache_key, result)

                        return result
                    
                    except asyncio.TimeoutError:
                        last_error = TimeoutError(f"{model_name} timed out")
                        if retry == 0:
                            logger.warning(f"[MODEL_ROUTER] ⏱️  {model_name} timed out after {per_call_timeout}s, retrying once...")
                            await asyncio.sleep(1)
                            continue  # One fast retry before giving up
                        logger.warning(f"[MODEL_ROUTER] ⏱️  {model_name} timed out again after {per_call_timeout}s, trying next model")
                        break  # Move to next model after 1 retry

                    except Exception as e:
                        last_error = e
                        error_type = type(e).__name__

                        # COMPREHENSIVE ERROR LOGGING: Log ALL failures with full exception details and stack traces
                        logger.error(f"[MODEL_ROUTER] ❌ FAILURE with {model_name} (retry {retry + 1}/{max_retries}){context_info}")
                        logger.error(f"[MODEL_ROUTER] 🔴 Error type: {error_type}")
                        logger.error(f"[MODEL_ROUTER] 🔴 Error message: {str(e)}")
                        logger.error(f"[MODEL_ROUTER] 🔴 Error details: {repr(e)}")

                        # Log full stack trace for debugging
                        import traceback
                        logger.error(f"[MODEL_ROUTER] 🔴 Stack trace:\n{traceback.format_exc()}")

                        # Handle specific error types
                        if "429" in str(e) or "rate_limit" in str(e).lower():
                            logger.warning(f"{model_name} rate limited, retry {retry + 1}/{max_retries}")
                            if retry < max_retries - 1:
                                await asyncio.sleep(2 ** retry)  # Exponential backoff
                            else:
                                # All retries exhausted for rate limit - try next model
                                logger.warning(f"{model_name} rate limited after {max_retries} retries, trying next model")
                                break  # Skip to next model without incrementing error count
                            
                        elif "529" in str(e) or "overloaded" in str(e).lower():
                            logger.warning(f"{model_name} overloaded, trying next model")
                            # Don't increment error count - transient overload should not disable
                            break  # Skip to next model
                            
                        elif "401" in str(e) or "403" in str(e):
                            logger.error(f"{model_name} authentication error, skipping")
                            # Don't increment error count for auth errors - just skip for this request
                            break  # Skip to next model
                            
                        else:
                            logger.error(f"{model_name} error: {e}, retry {retry + 1}/{max_retries}")
                            # Don't increment error count for unknown errors on first retry
                            if retry < max_retries - 1:
                                await asyncio.sleep(1)  # Brief delay before retry
                            else:
                                # Only increment error count if all retries failed AND it's a persistent error
                                # Skip transient errors without counting
                                logger.error(f"{model_name} failed after {max_retries} retries, incrementing error count")
                                self._increment_error_count(model_name)
            except Exception as outer_e:
                # Handle any exceptions from the outer try block
                logger.error(f"[MODEL_ROUTER] Outer exception for {model_name}: {outer_e}")
                last_error = outer_e
            finally:
                # Always release concurrency slot
                self._release_slot(model_name)
            
            if not fallback_enabled:
                break
        
        # All models failed - raise exception with full context
        error_msg = f"All models failed{context_info}"
        if last_error:
            error_msg += f". Last error: {last_error}"
            logger.error(f"[MODEL_ROUTER] ❌ ALL MODELS FAILED{context_info}")
            logger.error(f"[MODEL_ROUTER] 🔴 Final error: {type(last_error).__name__}: {str(last_error)}")
            import traceback
            logger.error(f"[MODEL_ROUTER] 🔴 Final error stack trace:\n{traceback.format_exc()}")
        
        raise Exception(error_msg) from last_error
    
    async def _call_model(
        self,
        model_config: Dict[str, Any],
        prompt: str,
        system_prompt: Optional[str],
        max_tokens: int,
        temperature: float,
        json_mode: bool = False
    ) -> Tuple[str, Dict[str, int]]:
        """Call specific model provider.

        Returns:
            Tuple of (response_text, usage_dict) where usage_dict contains
            ``{"input_tokens": int, "output_tokens": int}``.
            If the provider does not return real token counts, values are
            estimated as ``len(text) / 4``.
        """
        provider = model_config["provider"]
        model_name = model_config["model"]

        if provider == ModelProvider.ANTHROPIC:
            return await self._call_anthropic(model_name, prompt, system_prompt, max_tokens, temperature, json_mode)
        elif provider == ModelProvider.OPENAI:
            return await self._call_openai(model_name, prompt, system_prompt, max_tokens, temperature, json_mode)
        elif provider == ModelProvider.GROQ:
            return await self._call_groq(model_name, prompt, system_prompt, max_tokens, temperature)
        elif provider == ModelProvider.GOOGLE:
            return await self._call_gemini(model_name, prompt, system_prompt, max_tokens, temperature)
        elif provider == ModelProvider.TOGETHER:
            return await self._call_together(model_name, prompt, system_prompt, max_tokens, temperature)
        elif provider == ModelProvider.OLLAMA:
            return await self._call_ollama(model_name, prompt, system_prompt, max_tokens, temperature)
        else:
            raise ValueError(f"Unsupported provider: {provider}")
    
    async def _call_anthropic(
        self,
        model: str,
        prompt: str,
        system: Optional[str],
        max_tokens: int,
        temp: float,
        json_mode: bool = False
    ) -> str:
        """Call Anthropic Claude API - async client with proper error handling"""
        logger.info(f"[_call_anthropic] 🚀 CALLING ANTHROPIC with model: {model}")
        
        if not self.anthropic_client:
            logger.error("[_call_anthropic] ❌ Anthropic client not initialized!")
            raise ValueError("Anthropic client not initialized")
        
        messages = [{"role": "user", "content": prompt}]
        
        logger.info(f"[_call_anthropic] Making API call to Anthropic...")
        try:
            # Call Anthropic Messages API (async client)
            # Wrap system prompt as cacheable content block for prompt caching.
            # First call pays 1.25x write cost; subsequent calls with the same
            # prefix get 90% discount on cached input tokens (5-min TTL).
            system_text = system if system else "You are a helpful AI assistant."
            cacheable_system = [
                {"type": "text", "text": system_text, "cache_control": {"type": "ephemeral"}}
            ]

            request_kwargs: Dict[str, Any] = {
                "model": model,
                "max_tokens": max_tokens,
                "temperature": temp,
                "messages": messages,
                "system": cacheable_system,
            }

            response = await self.anthropic_client.messages.create(**request_kwargs)

            # Parse Anthropic response - handle both old and new format
            if not response.content or len(response.content) == 0:
                raise ValueError("Anthropic API returned empty content")

            # Extract text from first content block
            content_block = response.content[0]
            if hasattr(content_block, 'text'):
                text = content_block.text
            elif isinstance(content_block, dict):
                text = content_block.get('text', '')
            else:
                text = str(content_block)

            if not text:
                raise ValueError("Anthropic API returned empty text")

            # Extract REAL token counts from Anthropic usage
            usage = {"input_tokens": 0, "output_tokens": 0}
            if hasattr(response, "usage") and response.usage:
                usage["input_tokens"] = getattr(response.usage, "input_tokens", 0)
                usage["output_tokens"] = getattr(response.usage, "output_tokens", 0)
                # Log prompt caching stats
                cache_read = getattr(response.usage, "cache_read_input_tokens", 0)
                cache_create = getattr(response.usage, "cache_creation_input_tokens", 0)
                if cache_read or cache_create:
                    logger.info(
                        f"[_call_anthropic] PROMPT CACHE: read={cache_read} tokens (90% off), "
                        f"created={cache_create} tokens (1.25x write)"
                    )

            logger.info(f"[_call_anthropic] ✅ Anthropic API call successful! tokens_in={usage['input_tokens']} tokens_out={usage['output_tokens']}")
            return text, usage
            
        except Exception as e:
            # Re-raise API errors with context for proper retry handling
            error_msg = str(e)
            error_lower = error_msg.lower()
            
            # Check for status code in exception attributes (Anthropic SDK)
            status_code = None
            if hasattr(e, 'status_code'):
                status_code = e.status_code
            elif hasattr(e, 'response') and hasattr(e.response, 'status_code'):
                status_code = e.response.status_code
            
            # Map status codes to error types
            if status_code == 429 or "429" in error_msg or "rate_limit" in error_lower or "too_many_requests" in error_lower:
                raise Exception(f"Rate limit error: {error_msg}")
            elif status_code == 529 or "529" in error_msg or "overloaded" in error_lower or "service_unavailable" in error_lower:
                raise Exception(f"Service overloaded: {error_msg}")
            elif status_code == 401 or status_code == 403 or "401" in error_msg or "403" in error_msg or "authentication" in error_lower or "unauthorized" in error_lower:
                raise Exception(f"Authentication error: {error_msg}")
            elif status_code:
                raise Exception(f"Anthropic API error (HTTP {status_code}): {error_msg}")
            raise Exception(f"Anthropic API error: {error_msg}")

    # ── Tool-use conversational API ─────────────────────────────────────
    async def get_completion_with_tools(
        self,
        messages: List[Dict[str, Any]],
        system_prompt: str,
        tools: List[Dict[str, Any]],
        tool_executor,
        model: str = "claude-sonnet-4-6",
        max_tokens: int = 4096,
        temperature: float = 0.7,
        max_tool_rounds: int = 15,
        on_tool_start=None,
        on_tool_end=None,
    ) -> Dict[str, Any]:
        """Conversational completion with native Anthropic tool-use.

        Runs the standard tool-use loop: send messages → if model returns
        tool_use blocks, execute them via *tool_executor*, append tool_result,
        and call the model again.  Repeats until the model responds with
        pure text or *max_tool_rounds* is reached.

        Args:
            messages: Conversation history (user/assistant messages).
            system_prompt: System instructions.
            tools: Tool definitions in Anthropic format
                   [{"name": ..., "description": ..., "input_schema": {...}}].
            tool_executor: ``async (name, input) -> dict`` that runs a tool.
            model: Anthropic model ID.
            max_tokens: Max tokens per model call.
            temperature: Sampling temperature.
            max_tool_rounds: Safety cap on tool-use iterations.
            on_tool_start: Optional ``async (tool_name, tool_input) -> None``.
            on_tool_end: Optional ``async (tool_name, result) -> None``.

        Returns:
            {"response": str, "tool_calls": [...], "model": str,
             "cost": float, "input_tokens": int, "output_tokens": int}
        """
        await self._init_clients_if_needed()
        if not self.anthropic_client:
            raise ValueError("Anthropic client not initialized — tool-use requires Anthropic")

        # Budget check
        if self._active_budget and self._active_budget.exhausted:
            raise Exception(
                f"Request budget exhausted (${self._active_budget.total_cost:.2f}/"
                f"${self._active_budget.max_cost:.2f})"
            )

        all_tool_calls: List[Dict[str, Any]] = []
        total_input = 0
        total_output = 0
        total_cost = 0.0
        working_messages = list(messages)  # Don't mutate caller's list

        for round_idx in range(max_tool_rounds):
            logger.info(f"[TOOL_USE] Round {round_idx + 1}/{max_tool_rounds} — "
                        f"{len(working_messages)} messages, {len(tools)} tools")

            try:
                response = await asyncio.wait_for(
                    self.anthropic_client.messages.create(
                        model=model,
                        max_tokens=max_tokens,
                        temperature=temperature,
                        system=system_prompt,
                        messages=working_messages,
                        tools=tools,
                    ),
                    timeout=90,
                )
            except asyncio.TimeoutError:
                logger.warning("[TOOL_USE] Anthropic call timed out")
                raise Exception("Anthropic tool-use call timed out after 90s")

            # Track usage
            usage = getattr(response, "usage", None)
            inp = getattr(usage, "input_tokens", 0) if usage else 0
            out = getattr(usage, "output_tokens", 0) if usage else 0
            total_input += inp
            total_output += out
            round_cost = self._calculate_cost_by_model(model, inp, out)
            total_cost += round_cost

            if self._active_budget:
                self._active_budget.record(inp, out, round_cost, model)

            # Parse content blocks
            text_parts: List[str] = []
            tool_use_blocks: List[Any] = []
            for block in response.content:
                if getattr(block, "type", None) == "text":
                    text_parts.append(block.text)
                elif getattr(block, "type", None) == "tool_use":
                    tool_use_blocks.append(block)

            # If no tool calls → we're done
            if not tool_use_blocks:
                final_text = "\n".join(text_parts)
                logger.info(f"[TOOL_USE] Complete after {round_idx + 1} rounds, "
                            f"{len(all_tool_calls)} tool calls, ${total_cost:.4f}")
                return {
                    "response": final_text,
                    "tool_calls": all_tool_calls,
                    "model": model,
                    "cost": total_cost,
                    "input_tokens": total_input,
                    "output_tokens": total_output,
                }

            # Append the assistant message (with both text + tool_use blocks)
            working_messages.append({"role": "assistant", "content": response.content})

            # Execute each tool call and collect results
            tool_results_content = []
            for tb in tool_use_blocks:
                tool_name = tb.name
                tool_input = tb.input
                tool_id = tb.id
                logger.info(f"[TOOL_USE] Calling {tool_name}({json.dumps(tool_input)[:200]})")

                if on_tool_start:
                    await on_tool_start(tool_name, tool_input)

                try:
                    result = await asyncio.wait_for(
                        tool_executor(tool_name, tool_input),
                        timeout=120,
                    )
                    result_str = json.dumps(result) if not isinstance(result, str) else result
                    is_error = False
                except Exception as e:
                    logger.warning(f"[TOOL_USE] Tool {tool_name} failed: {e}")
                    result_str = f"Error: {str(e)}"
                    is_error = True

                all_tool_calls.append({
                    "tool": tool_name,
                    "input": tool_input,
                    "output": result_str[:2000],
                    "error": is_error,
                })

                if on_tool_end:
                    await on_tool_end(tool_name, result_str[:500])

                tool_results_content.append({
                    "type": "tool_result",
                    "tool_use_id": tool_id,
                    "content": result_str[:8000],
                    **({"is_error": True} if is_error else {}),
                })

            # Append tool results as user message (Anthropic format)
            working_messages.append({"role": "user", "content": tool_results_content})

            # Budget check between rounds
            if self._active_budget and self._active_budget.exhausted:
                logger.warning("[TOOL_USE] Budget exhausted mid-loop, returning partial")
                return {
                    "response": "\n".join(text_parts) or "Budget exhausted — partial results above.",
                    "tool_calls": all_tool_calls,
                    "model": model,
                    "cost": total_cost,
                    "input_tokens": total_input,
                    "output_tokens": total_output,
                }

        # Reached max rounds
        logger.warning(f"[TOOL_USE] Hit max {max_tool_rounds} rounds")
        return {
            "response": "\n".join(text_parts) if text_parts else "Reached maximum tool-use rounds.",
            "tool_calls": all_tool_calls,
            "model": model,
            "cost": total_cost,
            "input_tokens": total_input,
            "output_tokens": total_output,
        }

    def _calculate_cost_by_model(self, model: str, input_tokens: int, output_tokens: int) -> float:
        """Calculate cost given a model name directly."""
        for name, config in self.model_configs.items():
            if config.get("model") == model or name == model:
                return self._calculate_cost(config, input_tokens, output_tokens)
        # Fallback: Sonnet pricing
        return (input_tokens * 3.0 / 1_000_000) + (output_tokens * 15.0 / 1_000_000)

    async def _call_openai(self, model: str, prompt: str, system: Optional[str], max_tokens: int, temp: float, json_mode: bool = False) -> str:
        """Call OpenAI API with optional JSON mode for structured output and proper error handling"""
        if not self.openai_client:
            raise ValueError("OpenAI client not initialized")
        
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        
        # Use JSON mode for structured extraction when specified (works for modern GPT models too)
        # Some models (e.g. gpt-5-mini) only support the default temperature (1).
        # For those models, omit the temperature parameter entirely.
        no_custom_temp_models = ("gpt-5-mini", "o1", "o3")
        model_lower = model.lower()
        kwargs = {
            "model": model,
            "messages": messages,
        }
        if not any(identifier in model_lower for identifier in no_custom_temp_models):
            kwargs["temperature"] = temp
        
        # Use max_completion_tokens for newer OpenAI models (gpt-5 / gpt-4o / o1 variants)
        modern_token_param_models = ("gpt-5", "gpt-4o", "o1")
        if any(identifier in model_lower for identifier in modern_token_param_models):
            kwargs["max_completion_tokens"] = max_tokens
            logger.info(f"Using max_completion_tokens for {model}")
        else:
            kwargs["max_tokens"] = max_tokens
        
        # Add response_format for JSON mode (supported by newer GPT models)
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}
            logger.info(f"Using JSON mode for {model}")
        
        try:
            response = await self.openai_client.chat.completions.create(**kwargs)
            
            # Parse OpenAI response - handle both old and new format
            if not response.choices or len(response.choices) == 0:
                raise ValueError("OpenAI API returned empty choices")
            
            message = response.choices[0].message
            if not message:
                raise ValueError("OpenAI API returned empty message")
            
            content = message.content
            if content is None:
                raise ValueError("OpenAI API returned None content")

            # Extract REAL token counts from OpenAI usage
            usage = {"input_tokens": 0, "output_tokens": 0}
            if hasattr(response, "usage") and response.usage:
                usage["input_tokens"] = getattr(response.usage, "prompt_tokens", 0) or 0
                usage["output_tokens"] = getattr(response.usage, "completion_tokens", 0) or 0

            logger.info(f"[_call_openai] ✅ tokens_in={usage['input_tokens']} tokens_out={usage['output_tokens']}")
            return content, usage
            
        except Exception as e:
            # Re-raise API errors with context for proper retry handling
            error_msg = str(e)
            error_lower = error_msg.lower()
            
            # Check for status code in exception attributes (OpenAI SDK)
            status_code = None
            if hasattr(e, 'status_code'):
                status_code = e.status_code
            elif hasattr(e, 'response') and hasattr(e.response, 'status_code'):
                status_code = e.response.status_code
            
            # Map status codes to error types
            if status_code == 429 or "429" in error_msg or "rate_limit" in error_lower or "too_many_requests" in error_lower:
                raise Exception(f"Rate limit error: {error_msg}")
            elif status_code == 529 or "529" in error_msg or "overloaded" in error_lower or "service_unavailable" in error_lower:
                raise Exception(f"Service overloaded: {error_msg}")
            elif status_code == 401 or status_code == 403 or "401" in error_msg or "403" in error_msg or "authentication" in error_lower or "unauthorized" in error_lower:
                raise Exception(f"Authentication error: {error_msg}")
            elif status_code:
                raise Exception(f"OpenAI API error (HTTP {status_code}): {error_msg}")
            raise Exception(f"OpenAI API error: {error_msg}")
    
    async def _call_groq(self, model: str, prompt: str, system: Optional[str], max_tokens: int, temp: float) -> str:
        """Call Groq API"""
        if not self.groq_client:
            raise ValueError("Groq client not initialized")
        
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        
        response = await self.groq_client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temp
        )

        text = response.choices[0].message.content
        usage = {"input_tokens": 0, "output_tokens": 0}
        if hasattr(response, "usage") and response.usage:
            usage["input_tokens"] = getattr(response.usage, "prompt_tokens", 0) or 0
            usage["output_tokens"] = getattr(response.usage, "completion_tokens", 0) or 0

        return text, usage
    
    async def _call_gemini(self, model: str, prompt: str, system: Optional[str], max_tokens: int, temp: float) -> str:
        """Call Google Gemini API"""
        if not self.google_key:
            raise ValueError("Google API key not configured")

        if not self._genai_module:
            try:
                self._genai_module = importlib.import_module("google.generativeai")
            except Exception as exc:
                raise Exception(f"Google generative AI SDK not available: {exc}") from exc
        model_instance = self._genai_module.GenerativeModel(model)
        
        full_prompt = f"{system}\n\n{prompt}" if system else prompt
        
        response = await model_instance.generate_content_async(
            full_prompt,
            generation_config={
                "max_output_tokens": max_tokens,
                "temperature": temp
            }
        )

        text = response.text
        # Gemini returns usage_metadata with token counts
        usage = {"input_tokens": 0, "output_tokens": 0}
        if hasattr(response, "usage_metadata") and response.usage_metadata:
            usage["input_tokens"] = getattr(response.usage_metadata, "prompt_token_count", 0) or 0
            usage["output_tokens"] = getattr(response.usage_metadata, "candidates_token_count", 0) or 0

        return text, usage
    
    async def _ensure_session(self):
        """Ensure aiohttp session is initialized"""
        if not self.session:
            self.session = aiohttp.ClientSession()
    
    async def _call_together(self, model: str, prompt: str, system: Optional[str], max_tokens: int, temp: float) -> str:
        """Call Together AI API"""
        await self._ensure_session()
        
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        
        headers = {
            "Authorization": f"Bearer {self.together_key}",
            "Content-Type": "application/json"
        }
        
        data = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temp
        }
        
        async with self.session.post(
            "https://api.together.xyz/v1/chat/completions",
            headers=headers,
            json=data
        ) as response:
            result = await response.json()
            text = result["choices"][0]["message"]["content"]
            # Together API returns OpenAI-compatible usage block
            usage = {"input_tokens": 0, "output_tokens": 0}
            if "usage" in result:
                usage["input_tokens"] = result["usage"].get("prompt_tokens", 0)
                usage["output_tokens"] = result["usage"].get("completion_tokens", 0)
            return text, usage
    
    async def _call_ollama(self, model: str, prompt: str, system: Optional[str], max_tokens: int, temp: float) -> str:
        """Call local Ollama API"""
        await self._ensure_session()
        
        full_prompt = f"{system}\n\n{prompt}" if system else prompt
        
        data = {
            "model": model,
            "prompt": full_prompt,
            "stream": False,
            "options": {
                "num_predict": max_tokens,
                "temperature": temp
            }
        }
        
        try:
            async with self.session.post(
                "http://localhost:11434/api/generate",
                json=data,
                timeout=aiohttp.ClientTimeout(total=60)
            ) as response:
                result = await response.json()
                text = result["response"]
                # Ollama returns token counts in the response
                usage = {"input_tokens": 0, "output_tokens": 0}
                usage["input_tokens"] = result.get("prompt_eval_count", 0) or 0
                usage["output_tokens"] = result.get("eval_count", 0) or 0
                return text, usage
        except Exception as e:
            raise Exception(f"Ollama not available: {e}")
    
    def _get_model_order(self, capability: ModelCapability, preferred: Optional[List[str]]) -> List[str]:
        """Get ordered list of models based on capability and preference
        
        Default order ensures Claude 4.5 primary, GPT-5-Mini secondary when no preference specified
        """
        # Filter models by capability
        capable_models = [
            name for name, config in self.model_configs.items()
            if capability in config["capabilities"]
        ]
        
        logger.debug(f"[_get_model_order] Capability={capability}, Found {len(capable_models)} capable models")
        
        if not capable_models:
            # CRITICAL: If no models match, return ALL models as fallback
            logger.warning(f"[_get_model_order] ⚠️  No models with capability={capability}, using ALL models as fallback")
            capable_models = list(self.model_configs.keys())
        
        # Sort by priority (lower is better)
        capable_models.sort(key=lambda x: self.model_configs[x]["priority"])
        
        # If no preference specified, rotate default order by user affinity
        # so concurrent users hit different providers first.
        if not preferred:
            default_order = ["claude-sonnet-4-6", "gpt-5.2", "gpt-5-mini", "claude-haiku-4-5", "gemini-2.5-flash"]
            preferred_available = [m for m in default_order if m in capable_models]
            other_models = [m for m in capable_models if m not in default_order]
            base = preferred_available + other_models

            # Apply per-user rotation: rotate the list so different users
            # start with different providers.  Offset 0 = no rotation (default).
            affinity = _provider_affinity.get(0)
            if affinity and len(base) > 1:
                rotation = affinity % len(base)
                result = base[rotation:] + base[:rotation]
                logger.debug(f"[_get_model_order] Affinity rotation={rotation}, order: {result}")
            else:
                result = base
                logger.debug(f"[_get_model_order] No affinity, default order: {result}")
            return result
        
        # Preferred models (from caller_context task routing) always go first,
        # even if they don't match the capability filter — task routing wins.
        preferred_in_config = [m for m in preferred if m in self.model_configs]
        other_models = [m for m in capable_models if m not in preferred]
        result = preferred_in_config + other_models
        if set(preferred_in_config) != set(m for m in preferred if m in capable_models):
            skipped = [m for m in preferred_in_config if m not in capable_models]
            logger.info(f"[_get_model_order] Preferred models {skipped} lack capability={capability} but included anyway (task routing wins)")
        logger.debug(f"[_get_model_order] Preferred={preferred}, Result={result}")
        return result
    
    def _get_request_cache_key(self, prompt: str, system_prompt: Optional[str], model_name: str, max_tokens: int, temperature: float) -> str:
        """Generate cache key for request"""
        cache_data = f"{model_name}:{prompt}:{system_prompt or ''}:{max_tokens}:{temperature}"
        return hashlib.md5(cache_data.encode()).hexdigest()
    
    def _get_cached_response(self, cache_key: str) -> Optional[Dict[str, Any]]:
        """Get cached response if available and not expired"""
        if cache_key in self.request_cache:
            response, timestamp = self.request_cache[cache_key]
            if time.time() - timestamp < self.cache_ttl:
                logger.info(f"[MODEL_ROUTER] ✅ Cache hit for request")
                return response
            else:
                # Expired, remove from cache
                del self.request_cache[cache_key]
        return None
    
    def _cache_response(self, cache_key: str, response: Dict[str, Any]):
        """Cache response"""
        self.request_cache[cache_key] = (response, time.time())
        # Limit cache size (keep last 100 entries)
        if len(self.request_cache) > 100:
            # Remove oldest entry
            oldest_key = min(self.request_cache.keys(), key=lambda k: self.request_cache[k][1])
            del self.request_cache[oldest_key]
    
    async def _apply_rate_limit(self, model_name: str):
        """Apply rate limiting delay if needed"""
        if model_name in self.last_request_time:
            elapsed = time.time() - self.last_request_time[model_name]
            
            # Model-specific rate limits (requests per second)
            min_delay = {
                "claude-sonnet-4-6": 0.5,
                "claude-sonnet-4-5": 0.5,
                "claude-haiku-4-5": 0.15,   # faster model, higher throughput
                "gpt-5-mini": 0.1,
                "gpt-5.2": 1.0,
                "gemini-2.5-flash": 0.05,   # very fast
                "gemini-2.5-pro": 0.3,
                "mixtral-8x7b": 0.05,
            }.get(model_name, 0.1)
            
            if elapsed < min_delay:
                await asyncio.sleep(min_delay - elapsed)
        
        self.last_request_time[model_name] = time.time()
    
    async def _wait_for_slot(self, model_name: str):
        """Wait for available slot in concurrency limit"""
        max_concurrent = self.max_concurrent_per_model.get(model_name, self.default_max_concurrent)
        active = self.active_requests.get(model_name, 0)
        
        if active >= max_concurrent:
            # Wait for a slot to become available
            wait_time = 0.1
            while self.active_requests.get(model_name, 0) >= max_concurrent:
                await asyncio.sleep(wait_time)
                wait_time = min(wait_time * 1.5, 1.0)  # Exponential backoff up to 1 second
        
        # Increment active requests
        self.active_requests[model_name] = self.active_requests.get(model_name, 0) + 1
    
    def _release_slot(self, model_name: str):
        """Release concurrency slot"""
        if model_name in self.active_requests:
            self.active_requests[model_name] = max(0, self.active_requests[model_name] - 1)
    
    def _calculate_cost(self, model_config: Dict, input_tokens: int, output_tokens: int) -> float:
        """Calculate cost for a request using real token counts."""
        input_cost = (input_tokens / 1000) * model_config["cost_per_1k_input"]
        output_cost = (output_tokens / 1000) * model_config["cost_per_1k_output"]
        return input_cost + output_cost
    
    def _is_circuit_broken(self, model_name: str) -> bool:
        """Check if circuit breaker is active for a model"""
        logger.info(f"[CIRCUIT_BREAKER] Checking {model_name}...")
        logger.info(f"[CIRCUIT_BREAKER] Error counts: {self.error_counts}")
        logger.info(f"[CIRCUIT_BREAKER] Circuit breaker state: {self.circuit_breaker_until}")
        
        if model_name in self.circuit_breaker_until:
            cb_time = self.circuit_breaker_until[model_name]
            logger.info(f"[CIRCUIT_BREAKER] {model_name} has circuit breaker until: {cb_time}")
            logger.info(f"[CIRCUIT_BREAKER] Current time: {datetime.now()}")
            
            if datetime.now() < cb_time:
                time_remaining = cb_time - datetime.now()
                logger.warning(f"[CIRCUIT_BREAKER] ⚠️  {model_name} BLOCKED - circuit breaker active for {time_remaining}")
                return True
            else:
                # Circuit breaker timeout expired - reset it
                logger.info(f"[CIRCUIT_BREAKER] ✅ {model_name} circuit breaker expired, resetting")
                del self.circuit_breaker_until[model_name]
                self.error_counts[model_name] = 0
        
        # Also reset error count if it's been a while since last error (> 1 minute)
        # This handles cases where errors happened but circuit breaker wasn't triggered
        if model_name in self.error_counts and self.error_counts[model_name] > 0:
            if model_name not in self.last_request_time:
                return False
            time_since = time.time() - self.last_request_time.get(model_name, 0)
            if time_since > 60:  # 1 minute (reduced from 5 minutes for faster recovery)
                logger.info(f"[CIRCUIT_BREAKER] Resetting error count for {model_name} after {time_since:.0f}s")
                self.error_counts[model_name] = 0
        
        logger.info(f"[CIRCUIT_BREAKER] ✅ {model_name} is NOT broken")
        return False
    
    def _increment_error_count(self, model_name: str):
        """Increment error count and activate circuit breaker if needed"""
        self.error_counts[model_name] = self.error_counts.get(model_name, 0) + 1
        error_count = self.error_counts[model_name]
        
        logger.warning(f"[MODEL_ROUTER] ⚠️  Error count for {model_name}: {error_count}/5")
        
        # Activate circuit breaker after 5 consecutive errors (increased from 3 for more leniency)
        if error_count >= 5:
            # Reduced timeout from 5 minutes to 1 minute for faster recovery
            self.circuit_breaker_until[model_name] = datetime.now() + timedelta(minutes=1)
            logger.error(f"[MODEL_ROUTER] 🚨 CIRCUIT BREAKER ACTIVATED for {model_name} for 1 minute")
            logger.error(f"[MODEL_ROUTER] 🚨 Circuit breaker will reset at: {self.circuit_breaker_until[model_name]}")
    
    def _is_model_ready(self, model_name: str) -> bool:
        """Check if a model has the necessary client or config available"""
        model_config = self.model_configs.get(model_name)
        if not model_config:
            return False

        provider = model_config["provider"]

        if provider == ModelProvider.ANTHROPIC:
            return self.anthropic_client is not None
        if provider == ModelProvider.OPENAI:
            return self.openai_client is not None
        if provider == ModelProvider.GROQ:
            return self.groq_client is not None
        if provider == ModelProvider.GOOGLE:
            if not self.google_key:
                return False
            if self._genai_module is None:
                try:
                    self._genai_module = importlib.import_module("google.generativeai")
                    self._genai_module.configure(api_key=self.google_key)
                    logger.info("[MODEL_ROUTER] ✅ Google generative AI module loaded on demand")
                except Exception as exc:
                    logger.warning(f"[MODEL_ROUTER] ⚠️  Unable to load Google generative AI module: {exc}")
                    self._genai_module = None
                    return False
            return True
        if provider == ModelProvider.TOGETHER:
            return bool(self.together_key)
        if provider == ModelProvider.PERPLEXITY:
            return bool(self.perplexity_key)
        if provider == ModelProvider.ANYSCALE:
            return bool(self.anyscale_key)
        if provider == ModelProvider.OLLAMA:
            return True  # local service assumed available

        return False
    
    def reset_circuit_breakers(self, model_name: Optional[str] = None):
        """Reset circuit breakers for a specific model or all models
        
        Args:
            model_name: If provided, reset only this model. If None, reset all models.
        """
        if model_name:
            if model_name in self.circuit_breaker_until:
                del self.circuit_breaker_until[model_name]
            if model_name in self.error_counts:
                self.error_counts[model_name] = 0
            logger.info(f"[MODEL_ROUTER] ✅ Reset circuit breaker for {model_name}")
        else:
            self.circuit_breaker_until.clear()
            self.error_counts.clear()
            logger.info(f"[MODEL_ROUTER] ✅ Reset all circuit breakers")
    
    # ------------------------------------------------------------------
    # 4-Tier Intelligent Task Routing
    # ------------------------------------------------------------------
    # Maps every caller_context → ModelTier so the router picks the
    # cheapest model that can handle the job.
    #
    # TRIVIAL  → intent classification, routing, yes/no, scoring
    #            Models: claude-haiku-4-5, gemini-2.5-flash, mixtral-8x7b
    #
    # CHEAP    → bulk extraction, structured JSON, enrichment, parsing
    #            Models: gpt-5-mini, claude-haiku-4-5
    #
    # QUALITY  → analysis, reasoning, narratives, reflection
    #            Models: claude-sonnet-4-6, gemini-2.5-pro
    #
    # PREMIUM  → complex synthesis, final memos, deep multi-step reasoning
    #            Models: claude-sonnet-4-6, gpt-5.2
    # ------------------------------------------------------------------

    _TASK_TIER_MAP: Dict[str, "ModelTier"] = {
        # ── TRIVIAL: classification, routing, simple scoring ──────────
        "intent_classification":              ModelTier.TRIVIAL,
        "agent_loop_goal_extraction":         ModelTier.TRIVIAL,
        "task_planner_decompose":             ModelTier.TRIVIAL,
        "source_companies_semantic_score":    ModelTier.TRIVIAL,
        "single_shot_answer":                 ModelTier.TRIVIAL,

        # ── CHEAP: bulk extraction, enrichment, parsing ───────────────
        "enrichment":                         ModelTier.CHEAP,
        "extraction":                         ModelTier.CHEAP,
        "gap_filling":                        ModelTier.CHEAP,
        "suggestions":                        ModelTier.CHEAP,
        "sourcing_enrich":                    ModelTier.CHEAP,
        "granular_search_extract":            ModelTier.CHEAP,
        "parse_accounts":                     ModelTier.CHEAP,
        "lightweight_diligence_extract":      ModelTier.CHEAP,
        "micro_skill_extract":                ModelTier.CHEAP,
        "enrich_field":                       ModelTier.CHEAP,
        "build_company_list_query_gen":       ModelTier.CHEAP,
        "build_company_list_name_extraction": ModelTier.CHEAP,
        "find_comparables_extract":           ModelTier.CHEAP,
        "source_companies_rubric_llm":        ModelTier.CHEAP,
        "source_companies_decompose":         ModelTier.CHEAP,
        "generate_rubric_llm":                ModelTier.CHEAP,
        "memo_gap_fill":                      ModelTier.CHEAP,
        "lightweight_memo_polish":            ModelTier.CHEAP,

        # ── QUALITY: analysis, reasoning, narratives ──────────────────
        "narrative":                          ModelTier.QUALITY,
        "plan_generation":                    ModelTier.QUALITY,
        "agent_loop_reason":                  ModelTier.QUALITY,
        "agent_loop_reflect":                 ModelTier.QUALITY,
        "lightweight_memo_narratives":        ModelTier.QUALITY,
        "lightweight_memo_freeform":          ModelTier.QUALITY,
        "document_process_service.extract_structured": ModelTier.QUALITY,

        # ── PREMIUM: deep synthesis, final deliverables ───────────────
        "memo_generation":                    ModelTier.PREMIUM,
        "agent_loop_synthesize":              ModelTier.PREMIUM,
        "agent_loop_synthesize_brief":        ModelTier.PREMIUM,

        # ── Conversational cadence routing ────────────────────────────
        "conversational_phatic":              ModelTier.TRIVIAL,
        "conversational_status":              ModelTier.CHEAP,
        "conversational_retrieval":           ModelTier.QUALITY,
        "conversational_iteration":           ModelTier.CHEAP,
        "conversational_analysis":            ModelTier.QUALITY,
        "conversational_steering":            ModelTier.CHEAP,
        "conversational_synthesis":           ModelTier.PREMIUM,
        "conversation_summarize":             ModelTier.TRIVIAL,
        "conversation_crystallize":            ModelTier.CHEAP,
        "conversation_handoff":               ModelTier.TRIVIAL,
    }

    # Preferred model fallback chains per tier
    _TIER_MODEL_CHAINS: Dict["ModelTier", List[str]] = {
        ModelTier.TRIVIAL: ["claude-haiku-4-5", "gemini-2.5-flash", "gpt-5-mini", "mixtral-8x7b", "claude-sonnet-4-6"],
        ModelTier.CHEAP:   ["gpt-5-mini", "claude-haiku-4-5", "gemini-2.5-flash", "claude-sonnet-4-6"],
        ModelTier.QUALITY: ["claude-sonnet-4-6", "gemini-2.5-pro", "gpt-5-mini", "gpt-5.2"],
        ModelTier.PREMIUM: ["claude-sonnet-4-6", "gpt-5.2", "gemini-2.5-pro"],
    }

    def preferred_models_for_task(self, caller_context: Optional[str] = None) -> Optional[List[str]]:
        """Return preferred model list based on 4-tier intelligent routing.

        Looks up the caller_context in _TASK_TIER_MAP to find the tier,
        then returns the corresponding fallback chain from _TIER_MODEL_CHAINS.

        Handles dynamic caller_context patterns like:
          "source_companies_bulk_r2"  → matches "source_companies_bulk" → CHEAP
          "_extract_comprehensive_profile(Anthropic)" → matches on prefix
        """
        if not caller_context:
            return None

        # Normalize: strip parenthesized suffixes and lowercase
        task = caller_context.split("(")[0].strip().lower()

        # Direct lookup
        tier = self._TASK_TIER_MAP.get(task)

        # Prefix matching for dynamic contexts like source_companies_bulk_r2
        if tier is None:
            for known_task, known_tier in self._TASK_TIER_MAP.items():
                if task.startswith(known_task):
                    tier = known_tier
                    break

        # Pattern matching for sourcing extraction rounds
        if tier is None:
            if "extract" in task or "enrich" in task or "parse" in task:
                tier = ModelTier.CHEAP
            elif "synthe" in task or "memo" in task:
                tier = ModelTier.PREMIUM
            elif "classif" in task or "routing" in task or "score" in task:
                tier = ModelTier.TRIVIAL
            elif "reason" in task or "reflect" in task or "narrat" in task:
                tier = ModelTier.QUALITY

        if tier is None:
            return None

        chain = self._TIER_MODEL_CHAINS.get(tier)
        if chain:
            logger.info(f"[TIER_ROUTING] {caller_context} → {tier.value} → {chain[0]}")
        return chain

    # ------------------------------------------------------------------
    # Budget helpers
    # ------------------------------------------------------------------

    def start_budget(self, max_cost: float = 2.0, max_tokens: int = 500_000) -> RequestBudget:
        """Start a new per-request budget. Returns the budget object."""
        self._active_budget = RequestBudget(max_cost=max_cost, max_tokens=max_tokens)
        logger.info(f"[MODEL_ROUTER] Budget started: max_cost=${max_cost}, max_tokens={max_tokens}")
        return self._active_budget

    def end_budget(self) -> Optional[Dict[str, Any]]:
        """End the active budget and return its summary."""
        if not self._active_budget:
            return None
        summary = self._active_budget.summary()
        logger.info(f"[MODEL_ROUTER] Budget ended: {summary}")
        self._active_budget = None
        return summary

    @property
    def budget(self) -> Optional[RequestBudget]:
        return self._active_budget

    # ------------------------------------------------------------------
    # Tool-Use Completion (Conversational Agent Path)
    # ------------------------------------------------------------------

    # ── Provider-agnostic tool-use completion ────────────────────────
    # Uses ToolAdapter for format conversion so ANY provider can do tool-use.

    async def get_completion_with_tools(
        self,
        messages: List[Dict[str, Any]],
        system_prompt: str,
        tools: List[Dict[str, Any]],
        max_tokens: int = 4096,
        temperature: float = 0.7,
        caller_context: Optional[str] = None,
        preferred_models: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Provider-agnostic LLM call with tool-use support.

        Accepts canonical tool definitions (Anthropic format) and messages.
        ToolAdapter converts to/from each provider's format automatically.

        The caller (orchestrator) handles the tool execution loop:
        call → execute tools → feed tool_results → call again → ...

        Returns canonical format:
            {
                "text_parts": [str, ...],
                "tool_calls": [{"id": str, "name": str, "input": dict}, ...],
                "stop_reason": "end_turn" | "tool_use",
                "model": str,
                "usage": {"input_tokens": int, "output_tokens": int},
                "cost": float,
                "latency": float,
                "provider": str,
            }
        """
        if self._active_budget and self._active_budget.exhausted:
            raise Exception(
                f"Request budget exhausted (${self._active_budget.total_cost:.2f} / "
                f"${self._active_budget.max_cost:.2f})."
            )

        await self._init_clients_if_needed()

        if not preferred_models and caller_context:
            preferred_models = self.preferred_models_for_task(caller_context)

        if not preferred_models:
            preferred_models = ["claude-sonnet-4-6", "claude-haiku-4-5"]

        models = self._get_model_order(ModelCapability.ANALYSIS, preferred_models)

        context_info = f" (called by: {caller_context})" if caller_context else ""
        logger.info(f"[MODEL_ROUTER] get_completion_with_tools{context_info} tools={len(tools)}")

        # Provider dispatch table
        _PROVIDER_CALLERS = {
            ModelProvider.ANTHROPIC: self._call_anthropic_with_tools,
            ModelProvider.OPENAI: self._call_openai_with_tools,
            ModelProvider.GOOGLE: self._call_google_with_tools,
            ModelProvider.GROQ: self._call_openai_compatible_with_tools,
            ModelProvider.TOGETHER: self._call_openai_compatible_with_tools,
        }

        last_error = None
        for idx, model_name in enumerate(models):
            model_config = self.model_configs.get(model_name)
            if not model_config:
                continue

            provider = model_config["provider"]
            if provider not in _PROVIDER_CALLERS:
                continue

            if not self._is_model_ready(model_name):
                continue

            is_last = idx == len(models) - 1
            if self._is_circuit_broken(model_name) and not is_last:
                continue
            elif self._is_circuit_broken(model_name) and is_last:
                self.reset_circuit_breakers(model_name)

            await self._wait_for_slot(model_name)
            try:
                start_time = time.time()
                await self._apply_rate_limit(model_name)

                caller_fn = _PROVIDER_CALLERS[provider]
                result = await asyncio.wait_for(
                    caller_fn(
                        model=model_config["model"],
                        messages=messages,
                        system_prompt=system_prompt,
                        tools=tools,
                        max_tokens=max_tokens,
                        temperature=temperature,
                    ),
                    timeout=120,
                )

                latency = time.time() - start_time
                input_tokens = result["usage"].get("input_tokens", 0)
                output_tokens = result["usage"].get("output_tokens", 0)
                cost = self._calculate_cost(model_config, input_tokens, output_tokens)

                self.error_counts[model_name] = 0

                if self._active_budget:
                    self._active_budget.record(input_tokens, output_tokens, cost, model_name)

                logger.info(
                    f"[MODEL_ROUTER] tool-use SUCCESS {model_name} ({provider.value}) "
                    f"latency={latency:.2f}s cost=${cost:.4f} "
                    f"in={input_tokens} out={output_tokens} "
                    f"stop={result['stop_reason']}"
                )

                result["model"] = model_name
                result["cost"] = cost
                result["latency"] = latency
                result["provider"] = provider.value
                return result

            except asyncio.TimeoutError:
                logger.warning(f"[MODEL_ROUTER] {model_name} tool-use timed out")
                last_error = TimeoutError(f"{model_name} timed out")
            except Exception as e:
                logger.error(f"[MODEL_ROUTER] {model_name} tool-use error: {e}")
                last_error = e
                self._increment_error_count(model_name)
            finally:
                self._release_slot(model_name)

        raise Exception(f"All tool-use models failed{context_info}") from last_error

    async def stream_completion_with_tools(
        self,
        messages: List[Dict[str, Any]],
        system_prompt: str,
        tools: List[Dict[str, Any]],
        max_tokens: int = 4096,
        temperature: float = 0.3,
        caller_context: Optional[str] = None,
        preferred_models: Optional[List[str]] = None,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Streaming variant of get_completion_with_tools.

        Yields events as they arrive from the model:
        - {"type": "text_delta", "text": "..."}        — individual text tokens
        - {"type": "tool_use_start", "id": ..., "name": ...} — tool call begins
        - {"type": "tool_use_delta", "id": ..., "json": ...}  — tool input JSON fragment
        - {"type": "done", "text_parts": [...], "tool_calls": [...], "stop_reason": ..., "usage": ..., "model": ..., "cost": ...}

        Falls back to non-streaming for non-Anthropic providers.
        """
        if self._active_budget and self._active_budget.exhausted:
            raise Exception(
                f"Request budget exhausted (${self._active_budget.total_cost:.2f} / "
                f"${self._active_budget.max_cost:.2f})."
            )

        await self._init_clients_if_needed()

        if not preferred_models and caller_context:
            preferred_models = self.preferred_models_for_task(caller_context)
        if not preferred_models:
            preferred_models = ["claude-sonnet-4-6", "claude-haiku-4-5"]

        models = self._get_model_order(ModelCapability.ANALYSIS, preferred_models)
        context_info = f" (called by: {caller_context})" if caller_context else ""
        logger.info(f"[MODEL_ROUTER] stream_completion_with_tools{context_info} tools={len(tools)}")

        last_error = None
        for idx, model_name in enumerate(models):
            model_config = self.model_configs.get(model_name)
            if not model_config:
                continue
            provider = model_config["provider"]
            if not self._is_model_ready(model_name):
                continue
            is_last = idx == len(models) - 1
            if self._is_circuit_broken(model_name) and not is_last:
                continue
            elif self._is_circuit_broken(model_name) and is_last:
                self.reset_circuit_breakers(model_name)

            await self._wait_for_slot(model_name)
            try:
                start_time = time.time()
                await self._apply_rate_limit(model_name)

                if provider == ModelProvider.ANTHROPIC and self.anthropic_client:
                    # True streaming path for Anthropic
                    async for event in self._stream_anthropic_with_tools(
                        model=model_config["model"],
                        messages=messages,
                        system_prompt=system_prompt,
                        tools=tools,
                        max_tokens=max_tokens,
                        temperature=temperature,
                    ):
                        if event["type"] == "done":
                            # Enrich final event with cost/latency
                            latency = time.time() - start_time
                            input_tokens = event["usage"].get("input_tokens", 0)
                            output_tokens = event["usage"].get("output_tokens", 0)
                            cost = self._calculate_cost(model_config, input_tokens, output_tokens)
                            self.error_counts[model_name] = 0
                            if self._active_budget:
                                self._active_budget.record(input_tokens, output_tokens, cost, model_name)
                            event["model"] = model_name
                            event["cost"] = cost
                            event["latency"] = latency
                            event["provider"] = provider.value
                            logger.info(
                                f"[MODEL_ROUTER] stream SUCCESS {model_name} "
                                f"latency={latency:.2f}s cost=${cost:.4f} "
                                f"in={input_tokens} out={output_tokens} "
                                f"stop={event['stop_reason']}"
                            )
                        yield event
                    return  # Success — don't try next model

                else:
                    # Non-streaming fallback for other providers
                    caller_fn = {
                        ModelProvider.OPENAI: self._call_openai_with_tools,
                        ModelProvider.GOOGLE: self._call_google_with_tools,
                        ModelProvider.GROQ: self._call_openai_compatible_with_tools,
                        ModelProvider.TOGETHER: self._call_openai_compatible_with_tools,
                    }.get(provider)
                    if not caller_fn:
                        continue
                    result = await asyncio.wait_for(
                        caller_fn(
                            model=model_config["model"],
                            messages=messages,
                            system_prompt=system_prompt,
                            tools=tools,
                            max_tokens=max_tokens,
                            temperature=temperature,
                        ),
                        timeout=120,
                    )
                    latency = time.time() - start_time
                    input_tokens = result["usage"].get("input_tokens", 0)
                    output_tokens = result["usage"].get("output_tokens", 0)
                    cost = self._calculate_cost(model_config, input_tokens, output_tokens)
                    self.error_counts[model_name] = 0
                    if self._active_budget:
                        self._active_budget.record(input_tokens, output_tokens, cost, model_name)
                    # Emit text as a single chunk then done
                    for text in result.get("text_parts", []):
                        yield {"type": "text_delta", "text": text}
                    yield {
                        "type": "done",
                        "text_parts": result.get("text_parts", []),
                        "tool_calls": result.get("tool_calls", []),
                        "stop_reason": result.get("stop_reason", "end_turn"),
                        "usage": result.get("usage", {}),
                        "model": model_name,
                        "cost": cost,
                        "latency": latency,
                        "provider": provider.value,
                    }
                    return

            except asyncio.TimeoutError:
                logger.warning(f"[MODEL_ROUTER] {model_name} stream timed out")
                last_error = TimeoutError(f"{model_name} timed out")
            except Exception as e:
                logger.error(f"[MODEL_ROUTER] {model_name} stream error: {e}")
                last_error = e
                self._increment_error_count(model_name)
            finally:
                self._release_slot(model_name)

        raise Exception(f"All streaming models failed{context_info}") from last_error

    async def _stream_anthropic_with_tools(
        self,
        model: str,
        messages: List[Dict[str, Any]],
        system_prompt: str,
        tools: List[Dict[str, Any]],
        max_tokens: int,
        temperature: float,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Stream from Anthropic Messages API. Yields text deltas and tool calls."""
        if not self.anthropic_client:
            raise ValueError("Anthropic client not initialized")

        cacheable_system = [
            {"type": "text", "text": system_prompt, "cache_control": {"type": "ephemeral"}}
        ]

        async with self.anthropic_client.messages.stream(
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            system=cacheable_system,
            messages=messages,
            tools=ToolAdapter.to_anthropic(tools),
        ) as stream:
            # Track tool_use blocks being built
            current_tool_id = None
            current_tool_name = None
            current_tool_json = ""

            async for event in stream:
                event_type = getattr(event, "type", None)

                if event_type == "content_block_start":
                    block = getattr(event, "content_block", None)
                    if block and getattr(block, "type", None) == "tool_use":
                        current_tool_id = getattr(block, "id", None)
                        current_tool_name = getattr(block, "name", None)
                        current_tool_json = ""
                        yield {
                            "type": "tool_use_start",
                            "id": current_tool_id,
                            "name": current_tool_name,
                        }

                elif event_type == "content_block_delta":
                    delta = getattr(event, "delta", None)
                    if delta:
                        delta_type = getattr(delta, "type", None)
                        if delta_type == "text_delta":
                            text = getattr(delta, "text", "")
                            if text:
                                yield {"type": "text_delta", "text": text}
                        elif delta_type == "input_json_delta":
                            json_frag = getattr(delta, "partial_json", "")
                            if json_frag:
                                current_tool_json += json_frag

                elif event_type == "content_block_stop":
                    # If we were building a tool_use block, it's done
                    if current_tool_id:
                        current_tool_id = None
                        current_tool_name = None
                        current_tool_json = ""

            # Get final message with full parsed content
            final_message = await stream.get_final_message()

        # Parse final message for canonical output
        result = ToolAdapter.parse_anthropic_response(final_message)
        yield {
            "type": "done",
            "text_parts": result["text_parts"],
            "tool_calls": result["tool_calls"],
            "stop_reason": result["stop_reason"],
            "usage": result["usage"],
        }

    # ── Per-provider tool-use callers ─────────────────────────────────
    # Each returns canonical format:
    # {"text_parts": [...], "tool_calls": [...], "stop_reason": str, "usage": dict}

    async def _call_anthropic_with_tools(
        self,
        model: str,
        messages: List[Dict[str, Any]],
        system_prompt: str,
        tools: List[Dict[str, Any]],
        max_tokens: int,
        temperature: float,
    ) -> Dict[str, Any]:
        """Call Anthropic Messages API with tool-use definitions."""
        if not self.anthropic_client:
            raise ValueError("Anthropic client not initialized")

        # Cacheable system prompt — same prefix gets 90% input discount
        cacheable_system = [
            {"type": "text", "text": system_prompt, "cache_control": {"type": "ephemeral"}}
        ]

        response = await self.anthropic_client.messages.create(
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            system=cacheable_system,
            messages=messages,
            tools=ToolAdapter.to_anthropic(tools),
        )

        return ToolAdapter.parse_anthropic_response(response)

    async def _call_openai_with_tools(
        self,
        model: str,
        messages: List[Dict[str, Any]],
        system_prompt: str,
        tools: List[Dict[str, Any]],
        max_tokens: int,
        temperature: float,
    ) -> Dict[str, Any]:
        """Call OpenAI Chat Completions API with function calling."""
        if not self.openai_client:
            raise ValueError("OpenAI client not initialized")

        # Build OpenAI message array (system + conversation)
        oai_messages = [{"role": "system", "content": system_prompt}]

        for msg in messages:
            role = msg["role"]
            content = msg.get("content")

            if role == "user" and isinstance(content, list):
                # Anthropic-format tool_result blocks → OpenAI tool messages
                tool_results = [b for b in content if isinstance(b, dict) and b.get("type") == "tool_result"]
                if tool_results:
                    for tr in tool_results:
                        oai_messages.append({
                            "role": "tool",
                            "tool_call_id": tr["tool_use_id"],
                            "content": tr.get("content", ""),
                        })
                else:
                    # Regular content blocks
                    text = " ".join(
                        b["text"] if isinstance(b, dict) and "text" in b else str(b)
                        for b in content
                    )
                    oai_messages.append({"role": "user", "content": text})
            elif role == "assistant" and isinstance(content, list):
                # Reconstruct OpenAI assistant message from canonical blocks
                text_parts = []
                tool_calls = []
                for block in content:
                    if isinstance(block, dict):
                        if block.get("type") == "text":
                            text_parts.append(block["text"])
                        elif block.get("type") == "tool_use":
                            tool_calls.append({
                                "id": block["id"],
                                "type": "function",
                                "function": {
                                    "name": block["name"],
                                    "arguments": json.dumps(block["input"]),
                                },
                            })
                assistant_msg: Dict[str, Any] = {"role": "assistant"}
                assistant_msg["content"] = "\n".join(text_parts) if text_parts else None
                if tool_calls:
                    assistant_msg["tool_calls"] = tool_calls
                oai_messages.append(assistant_msg)
            else:
                oai_messages.append({"role": role, "content": content})

        # Build kwargs
        model_lower = model.lower()
        kwargs: Dict[str, Any] = {
            "model": model,
            "messages": oai_messages,
            "tools": ToolAdapter.to_openai(tools),
        }

        no_custom_temp_models = ("gpt-5-mini", "o1", "o3")
        if not any(identifier in model_lower for identifier in no_custom_temp_models):
            kwargs["temperature"] = temperature

        modern_token_param_models = ("gpt-5", "gpt-4o", "o1")
        if any(identifier in model_lower for identifier in modern_token_param_models):
            kwargs["max_completion_tokens"] = max_tokens
        else:
            kwargs["max_tokens"] = max_tokens

        response = await self.openai_client.chat.completions.create(**kwargs)
        return ToolAdapter.parse_openai_response(response)

    async def _call_google_with_tools(
        self,
        model: str,
        messages: List[Dict[str, Any]],
        system_prompt: str,
        tools: List[Dict[str, Any]],
        max_tokens: int,
        temperature: float,
    ) -> Dict[str, Any]:
        """Call Google Gemini with function calling."""
        if not self._genai_module:
            raise ValueError("Google Generative AI not initialized")

        genai = self._genai_module
        gemini_model = genai.GenerativeModel(
            model_name=model,
            system_instruction=system_prompt,
            tools=ToolAdapter.to_google(tools),
        )

        # Convert messages to Gemini content format
        gemini_contents = []
        for msg in messages:
            role = msg["role"]
            content = msg.get("content")
            gemini_role = "model" if role == "assistant" else "user"

            if role == "user" and isinstance(content, list):
                # Check for tool_result blocks
                tool_results = [b for b in content if isinstance(b, dict) and b.get("type") == "tool_result"]
                if tool_results:
                    parts = ToolAdapter.format_tool_results_google([
                        {"name": tr.get("name", "tool"), "result": tr.get("content", "")}
                        for tr in tool_results
                    ])
                    gemini_contents.append({"role": "user", "parts": parts})
                    continue

            if isinstance(content, list):
                text = " ".join(
                    b["text"] if isinstance(b, dict) and "text" in b else str(b)
                    for b in content
                )
            elif isinstance(content, str):
                text = content
            else:
                text = str(content) if content else ""

            gemini_contents.append({"role": gemini_role, "parts": [{"text": text}]})

        response = await asyncio.to_thread(
            gemini_model.generate_content,
            gemini_contents,
            generation_config={"max_output_tokens": max_tokens, "temperature": temperature},
        )

        return ToolAdapter.parse_google_response(response)

    async def _call_openai_compatible_with_tools(
        self,
        model: str,
        messages: List[Dict[str, Any]],
        system_prompt: str,
        tools: List[Dict[str, Any]],
        max_tokens: int,
        temperature: float,
    ) -> Dict[str, Any]:
        """Call OpenAI-compatible APIs (Groq, Together, etc.) with function calling."""
        # Use groq client for groq models, otherwise fall back to openai-compatible
        client = None
        model_lower = model.lower()
        if self.groq_client and ("mixtral" in model_lower or "llama" in model_lower or "groq" in model_lower):
            client = self.groq_client
        elif self.openai_client:
            client = self.openai_client

        if not client:
            raise ValueError("No OpenAI-compatible client available")

        oai_messages = [{"role": "system", "content": system_prompt}]
        for msg in messages:
            role = msg["role"]
            content = msg.get("content")
            if role == "user" and isinstance(content, list):
                tool_results = [b for b in content if isinstance(b, dict) and b.get("type") == "tool_result"]
                if tool_results:
                    for tr in tool_results:
                        oai_messages.append({
                            "role": "tool",
                            "tool_call_id": tr["tool_use_id"],
                            "content": tr.get("content", ""),
                        })
                else:
                    text = " ".join(
                        b["text"] if isinstance(b, dict) and "text" in b else str(b)
                        for b in content
                    )
                    oai_messages.append({"role": "user", "content": text})
            elif role == "assistant" and isinstance(content, list):
                text_parts = []
                tool_calls = []
                for block in content:
                    if isinstance(block, dict):
                        if block.get("type") == "text":
                            text_parts.append(block["text"])
                        elif block.get("type") == "tool_use":
                            tool_calls.append({
                                "id": block["id"],
                                "type": "function",
                                "function": {
                                    "name": block["name"],
                                    "arguments": json.dumps(block["input"]),
                                },
                            })
                assistant_msg: Dict[str, Any] = {"role": "assistant"}
                assistant_msg["content"] = "\n".join(text_parts) if text_parts else None
                if tool_calls:
                    assistant_msg["tool_calls"] = tool_calls
                oai_messages.append(assistant_msg)
            else:
                oai_messages.append({"role": role, "content": content})

        response = await client.chat.completions.create(
            model=model,
            messages=oai_messages,
            tools=ToolAdapter.to_openai_compatible(tools),
            max_tokens=max_tokens,
            temperature=temperature,
        )

        return ToolAdapter.parse_openai_response(response)

    # ------------------------------------------------------------------
    # Provider-level routing for concurrent multi-doc processing
    # ------------------------------------------------------------------

    def get_available_providers(self) -> list[str]:
        """Return provider names with valid API keys and no active circuit breaker.

        Used by ParallelDocProcessor to fan LLM calls across providers.
        """
        provider_key_map: dict[str, bool] = {
            "anthropic": bool(self.anthropic_key),
            "openai": bool(self.openai_key),
            "google": bool(self.google_key),
            "groq": bool(self.groq_key),
            "together": bool(self.together_key),
        }
        available: list[str] = []
        for provider, has_key in provider_key_map.items():
            if not has_key:
                continue
            # Pick the best model for this provider and check circuit breaker
            best = self.get_model_for_provider(provider)
            if best and not self._is_circuit_broken(best["name"]):
                available.append(provider)
        return available

    def get_model_for_provider(self, provider: str) -> dict | None:
        """Return the best analysis-capable model config for a specific provider.

        Returns dict with keys: name, model, provider, max_tokens, tier
        or None if no model available for that provider.
        """
        from app.services.model_router import ModelProvider
        try:
            target_provider = ModelProvider(provider)
        except ValueError:
            return None

        candidates = []
        for name, config in self.model_configs.items():
            if config["provider"] != target_provider:
                continue
            # Prefer models with ANALYSIS or STRUCTURED capability
            has_analysis = ModelCapability.ANALYSIS in config.get("capabilities", [])
            has_structured = ModelCapability.STRUCTURED in config.get("capabilities", [])
            candidates.append({
                "name": name,
                "model": config["model"],
                "provider": provider,
                "max_tokens": config.get("max_tokens", 4096),
                "tier": config.get("tier", ModelTier.CHEAP).value,
                "priority": config.get("priority", 99),
                "has_analysis": has_analysis,
                "has_structured": has_structured,
            })

        if not candidates:
            return None

        # Sort: analysis-capable first, then by priority (lower is better)
        candidates.sort(key=lambda c: (not c["has_analysis"], c["priority"]))
        best = candidates[0]
        # Strip internal sorting fields
        return {
            "name": best["name"],
            "model": best["model"],
            "provider": best["provider"],
            "max_tokens": best["max_tokens"],
            "tier": best["tier"],
        }

    async def close(self):
        """Close any open sessions"""
        if self.session:
            await self.session.close()


# Singleton instance
_model_router = None

def get_model_router() -> ModelRouter:
    """Get singleton model router instance"""
    global _model_router
    if _model_router is None:
        _model_router = ModelRouter()
    return _model_router