"""
Model Router with Fallback Support
Handles multiple LLM providers with automatic failover
"""

import os
import asyncio
import logging
from typing import Dict, Any, Optional, List, Tuple
from enum import Enum
import time
import random
from datetime import datetime, timedelta
import aiohttp
import importlib
import json
import hashlib
from collections import deque
from dataclasses import dataclass, field

# Import settings
from app.core.config import settings

logger = logging.getLogger(__name__)


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
                    self.anthropic_client = AsyncAnthropic(api_key=self.anthropic_key)
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
                        response_text, usage = await self._call_model(
                            model_config,
                            prompt,
                            system_prompt,
                            max_tokens,
                            temperature,
                            json_mode
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
            request_kwargs: Dict[str, Any] = {
                "model": model,
                "max_tokens": max_tokens,
                "temperature": temp,
                "messages": messages,
                "system": system if system else "You are a helpful AI assistant."
            }

            if json_mode:
                # Anthropic has no json_mode -- use assistant prefill to force JSON object
                messages.append({"role": "assistant", "content": "{"})
                request_kwargs["messages"] = messages
                logger.info("[_call_anthropic] JSON mode: prefilling '{' for %s", model)

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

            # CRITICAL FIX: When using assistant prefill for JSON mode, the API
            # response only contains text AFTER the prefill. We must prepend '{'
            # to reconstruct valid JSON.
            if json_mode and not text.lstrip().startswith("{"):
                text = "{" + text
                logger.info("[_call_anthropic] JSON mode: prepended '{' to response")

            # Extract REAL token counts from Anthropic usage
            usage = {"input_tokens": 0, "output_tokens": 0}
            if hasattr(response, "usage") and response.usage:
                usage["input_tokens"] = getattr(response.usage, "input_tokens", 0)
                usage["output_tokens"] = getattr(response.usage, "output_tokens", 0)

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
        
        # If no preference specified, ensure default order: Sonnet 4.6 -> GPT-5.2 -> GPT-5-Mini -> Haiku -> others
        if not preferred:
            default_order = ["claude-sonnet-4-6", "gpt-5.2", "gpt-5-mini", "claude-haiku-4-5", "gemini-2.5-flash"]
            preferred_available = [m for m in default_order if m in capable_models]
            other_models = [m for m in capable_models if m not in default_order]
            result = preferred_available + other_models
            logger.debug(f"[_get_model_order] No preference specified, using default order: {result}")
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