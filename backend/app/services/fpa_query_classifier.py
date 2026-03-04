"""
FPA Query Classifier
Routes parsed queries to appropriate handlers via LLM classification.
"""

import json
import logging
from typing import Dict, Any
from enum import Enum

from app.services.nl_fpa_parser import ParsedQuery

logger = logging.getLogger(__name__)


class QueryHandlerType(str, Enum):
    """Types of query handlers"""
    SCENARIO = "scenario"
    FORECAST = "forecast"
    VALUATION = "valuation"
    IMPACT = "impact"
    SENSITIVITY = "sensitivity"
    COMPARISON = "comparison"
    REGRESSION = "regression"
    GROWTH_DECAY = "growth_decay"


_VALID_HANDLERS = {h.value for h in QueryHandlerType}


class FPAQueryClassifier:
    """Classifies parsed queries and routes them to appropriate handlers"""

    def __init__(self):
        self._model_router = None

    def _get_router(self):
        if self._model_router is None:
            from app.services.model_router import get_model_router
            self._model_router = get_model_router()
        return self._model_router

    async def route(self, parsed: ParsedQuery) -> str:
        """
        Route a parsed query to the appropriate handler using LLM classification.
        Falls back to keyword matching if the LLM call fails.
        """
        # Try LLM classification first
        try:
            handler = await self._llm_classify(parsed)
            if handler:
                return handler
        except Exception as e:
            logger.warning(f"[FPA_CLASSIFY] LLM classification failed: {e}")

        # Fallback: keyword matching on query_type
        return self._keyword_fallback(parsed)

    async def _llm_classify(self, parsed: ParsedQuery) -> str | None:
        """Small LLM call to classify the FPA query intent."""
        from app.services.model_router import ModelCapability

        router = self._get_router()
        handler_descriptions = (
            "scenario: What-if analysis, multi-step scenarios, assumption changes\n"
            "forecast: Revenue/cost projections, growth modeling, future estimates\n"
            "valuation: Company valuation, multiples, DCF, mark-to-market\n"
            "impact: Impact analysis, ripple effects, driver changes\n"
            "sensitivity: Sensitivity analysis, tornado charts, variable ranges\n"
            "comparison: Side-by-side comparison of scenarios, companies, periods\n"
            "regression: Statistical analysis, trend fitting, correlation\n"
            "growth_decay: Growth/decay curves, churn modeling, cohort analysis"
        )

        classify_prompt = (
            f"Classify this FP&A query into exactly one handler. Return JSON only.\n\n"
            f"Query: {parsed.original_query}\n"
            f"Parsed type: {parsed.query_type}\n"
            f"Entities: {json.dumps(parsed.entities)}\n"
            f"Steps: {[s.operation for s in parsed.steps]}\n\n"
            f"Handlers:\n{handler_descriptions}\n\n"
            f'Return: {{"handler": "<handler_name>", "confidence": 0.0-1.0}}'
        )

        result = await router.get_completion(
            prompt=classify_prompt,
            system_prompt="Classify FP&A queries. Return valid JSON only.",
            capability=ModelCapability.FAST,
            max_tokens=60,
            temperature=0.0,
            json_mode=True,
            caller_context="fpa_query_classification",
        )

        content = result.get("response", "{}") if isinstance(result, dict) else str(result)
        data = json.loads(content)
        handler = data.get("handler", "").lower()

        if handler in _VALID_HANDLERS:
            logger.info(f"[FPA_CLASSIFY] LLM classified '{parsed.original_query[:60]}' → {handler} (conf={data.get('confidence')})")
            return QueryHandlerType(handler)

        logger.warning(f"[FPA_CLASSIFY] LLM returned unknown handler '{handler}'")
        return None

    @staticmethod
    def _keyword_fallback(parsed: ParsedQuery) -> str:
        """Keyword-based fallback classification."""
        qt = parsed.query_type.lower()
        query = parsed.original_query.lower()

        if "scenario" in qt or "multi_step" in qt or "what if" in query:
            return QueryHandlerType.SCENARIO
        elif "forecast" in qt or "project" in query or "predict" in query:
            return QueryHandlerType.FORECAST
        elif "valuation" in qt or "worth" in query or "multiple" in query:
            return QueryHandlerType.VALUATION
        elif "impact" in qt or "ripple" in query or "effect" in query:
            return QueryHandlerType.IMPACT
        elif "sensitivity" in qt or "tornado" in query:
            return QueryHandlerType.SENSITIVITY
        elif "compar" in qt or "vs" in query or "side by side" in query:
            return QueryHandlerType.COMPARISON
        elif "regression" in qt or "correlat" in query or "trend" in query:
            return QueryHandlerType.REGRESSION
        elif "decay" in qt or "churn" in query or "cohort" in query:
            return QueryHandlerType.GROWTH_DECAY
        else:
            return QueryHandlerType.SCENARIO
