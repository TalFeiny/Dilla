"""
Business Event Analysis Service
Micro-level equivalent of MacroEventAnalysisService.

Same pattern, different context source:
  Macro: world event → web search → LLM causal chain → driver adjustments
  Micro: business event → actuals + signals → LLM causal chain → driver adjustments

Events: funding, hiring, product launch, pricing change, partnership,
competitor move, expansion, churn spike, contract win/loss, etc.

Every output includes an auditable reasoning chain:
  event → signals + actuals → business_factors → driver_adjustments
"""

import json
import logging
from dataclasses import dataclass, field, asdict
from typing import Any, Callable, Dict, List, Optional

from app.services.driver_registry import (
    get_all_drivers,
    get_registry_schema,
    DriverDef,
)
from app.services.model_router import ModelRouter, ModelCapability

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data classes — mirror MacroEventAnalysis structure
# ---------------------------------------------------------------------------

@dataclass
class BusinessFactor:
    """A business impact factor extracted by the LLM from company context."""
    name: str                       # e.g. "Series A cash injection"
    direction: str                  # "increase" | "decrease"
    magnitude_pct: float            # estimated % change (0.25 = +25%)
    confidence: str                 # "high" | "medium" | "low"
    reasoning: str                  # LLM's reasoning
    order: int = 1                  # 1=direct, 2=indirect, 3=downstream
    caused_by: Optional[str] = None # parent factor for 2nd/3rd order
    metric_affected: Optional[str] = None  # primary metric this affects


@dataclass
class BusinessDriverAdjustment:
    """Concrete adjustment to a registered driver, with audit trail."""
    driver_id: str
    driver_label: str
    adjustment_pct: float           # e.g. -0.15 = -15%
    caused_by: str                  # which BusinessFactor caused this
    reasoning: str                  # LLM explanation
    ripple_path: List[str] = field(default_factory=list)


@dataclass
class BusinessEventAnalysis:
    """Complete business event analysis result."""
    event_description: str
    signals: List[Any]              # StrategicSignal objects
    factors: List[BusinessFactor]
    driver_adjustments: List[BusinessDriverAdjustment]
    reasoning_chain: List[Dict[str, str]]


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------

class BusinessEventAnalysisService:
    """
    Business event → actuals + signals → LLM causal chain → driver adjustments.
    Same architecture as MacroEventAnalysisService but for company-level events.
    """

    def __init__(self, model_router: ModelRouter):
        self.model_router = model_router
        self._driver_registry = get_all_drivers()

    async def analyse_event(
        self,
        event: str,
        company_id: str,
        company_data: Dict[str, Any],
    ) -> BusinessEventAnalysis:
        """
        Full pipeline: event → state + signals → reason → drivers → audit.

        Args:
            event: Natural language event description
                   e.g. "Close Series A at $5M pre", "Hire 10 engineers",
                   "Lose biggest client", "Launch enterprise tier"
            company_id: Company to analyse
            company_data: Forecast seed dict
        """
        reasoning_chain: List[Dict[str, str]] = []

        reasoning_chain.append({
            "step": "event_received",
            "detail": f"Analysing business event: '{event}'",
        })

        # 1. Build unified state from actuals
        state = await self._build_state(company_id, company_data)
        reasoning_chain.append({
            "step": "state_built",
            "detail": "Built unified financial state from actuals",
        })

        # 2. Detect existing signals
        signals = self._detect_signals(state)
        reasoning_chain.append({
            "step": "signals_detected",
            "detail": f"Detected {len(signals)} strategic signals",
        })

        # 3. LLM extracts business factors with causal orders
        factors = await self._extract_business_factors(event, state, signals)
        reasoning_chain.append({
            "step": "factors_extracted",
            "detail": (
                f"Identified {len(factors)} business factors "
                f"({sum(1 for f in factors if f.order == 1)} direct, "
                f"{sum(1 for f in factors if f.order == 2)} indirect, "
                f"{sum(1 for f in factors if f.order >= 3)} downstream)"
            ),
        })

        # 4. Map factors → driver adjustments
        adjustments = await self._map_factors_to_drivers(event, factors, state)
        reasoning_chain.append({
            "step": "drivers_mapped",
            "detail": f"Mapped to {len(adjustments)} driver adjustments",
        })

        # 5. Trace ripple paths
        self._attach_ripple_paths(adjustments)
        reasoning_chain.append({
            "step": "ripples_traced",
            "detail": "Attached ripple paths from driver registry",
        })

        return BusinessEventAnalysis(
            event_description=event,
            signals=signals,
            factors=factors,
            driver_adjustments=adjustments,
            reasoning_chain=reasoning_chain,
        )

    # ------------------------------------------------------------------
    # Internal steps
    # ------------------------------------------------------------------

    async def _build_state(
        self, company_id: str, company_data: Dict[str, Any]
    ) -> Any:
        """Build UnifiedFinancialState from actuals."""
        from app.services.unified_financial_state import build_unified_state

        return await build_unified_state(
            company_id, company_data=company_data
        )

    def _detect_signals(self, state: Any) -> List[Any]:
        """Detect strategic signals from state."""
        try:
            from app.services.strategic_intelligence_service import (
                detect_signals,
            )
            return detect_signals(state)
        except Exception as e:
            logger.warning("Signal detection failed: %s", e)
            return []

    async def _extract_business_factors(
        self,
        event: str,
        state: Any,
        signals: List[Any],
    ) -> List[BusinessFactor]:
        """LLM extracts causal business factors from event + company context."""
        state_summary = self._summarize_state(state)
        signals_text = "\n".join(
            f"  - [{s.severity}] {s.description}"
            for s in signals
        ) or "  No signals detected."

        driver_schema = get_registry_schema()
        driver_ids = [d["id"] for d in driver_schema]

        prompt = f"""Analyse this business event for a specific company:

Event: "{event}"

Company financial state:
{state_summary}

Current strategic signals:
{signals_text}

Available driver IDs: {driver_ids}

Extract business impact factors with causal ordering:
- Order 1 (DIRECT): immediate effects of the event
  e.g. "Series A closes" → cash_balance +$5M
- Order 2 (INDIRECT): effects caused by order 1
  e.g. "Hire 5 engineers" → burn_rate +$75K/mo, rd_spend +$75K/mo
- Order 3 (DOWNSTREAM): effects caused by order 2
  e.g. "Product velocity increases" → revenue_growth +5%, churn -1%

Output JSON array of factors:
[{{
  "name": "descriptive name",
  "direction": "increase|decrease",
  "magnitude_pct": 0.25,
  "confidence": "high|medium|low",
  "reasoning": "why this happens for THIS company given its current state",
  "order": 1,
  "caused_by": null,
  "metric_affected": "driver_id or metric name"
}}]"""

        result = await self.model_router.get_completion(
            system_prompt=(
                "You are a financial analyst extracting causal business impact "
                "factors. Be specific to this company's actual numbers. Every "
                "factor must reference the company's real financial state."
            ),
            prompt=prompt,
            capability=ModelCapability.STRUCTURED,
            max_tokens=4096,
            temperature=0.3,
            json_mode=True,
            caller_context="business_event_analysis",
        )

        response_text = result.get("response", "[]")
        try:
            raw = json.loads(response_text)
            if isinstance(raw, dict):
                raw = raw.get("factors", [raw])
            if not isinstance(raw, list):
                raw = [raw]

            factors = []
            for item in raw:
                try:
                    factors.append(BusinessFactor(**{
                        k: v for k, v in item.items()
                        if k in BusinessFactor.__dataclass_fields__
                    }))
                except Exception as e:
                    logger.warning("Failed to parse factor: %s", e)
            return factors
        except json.JSONDecodeError:
            logger.error("Business factor extraction returned invalid JSON")
            return []

    async def _map_factors_to_drivers(
        self,
        event: str,
        factors: List[BusinessFactor],
        state: Any,
    ) -> List[BusinessDriverAdjustment]:
        """LLM maps business factors → concrete driver adjustments."""
        factors_text = "\n".join(
            f"  - [{f.order}] {f.name}: {f.direction} {f.magnitude_pct:+.0%}"
            f" ({f.confidence}) — {f.reasoning[:100]}"
            for f in factors
        )

        driver_info = []
        for d in self._driver_registry.values():
            driver_info.append(
                f"  {d.id} ({d.label}, {d.unit}, ripple: {d.ripple})"
            )

        prompt = f"""Given these business impact factors from event "{event}":

{factors_text}

Map each factor to specific driver adjustments using these registered drivers:
{chr(10).join(driver_info)}

Output JSON array:
[{{
  "driver_id": "revenue_growth",
  "driver_label": "Revenue Growth Rate",
  "adjustment_pct": 0.05,
  "caused_by": "factor name that caused this",
  "reasoning": "why this driver changes by this amount"
}}]"""

        result = await self.model_router.get_completion(
            system_prompt=(
                "You are mapping business event impacts to registered financial "
                "drivers. Use exact driver_id values. Be quantitatively specific."
            ),
            prompt=prompt,
            capability=ModelCapability.STRUCTURED,
            max_tokens=4096,
            temperature=0.3,
            json_mode=True,
            caller_context="business_event_driver_mapping",
        )

        response_text = result.get("response", "[]")
        try:
            raw = json.loads(response_text)
            if isinstance(raw, dict):
                raw = raw.get("adjustments", raw.get("driver_adjustments", [raw]))
            if not isinstance(raw, list):
                raw = [raw]

            adjustments = []
            for item in raw:
                try:
                    adjustments.append(BusinessDriverAdjustment(**{
                        k: v for k, v in item.items()
                        if k in BusinessDriverAdjustment.__dataclass_fields__
                    }))
                except Exception as e:
                    logger.warning("Failed to parse driver adjustment: %s", e)
            return adjustments
        except json.JSONDecodeError:
            logger.error("Driver mapping returned invalid JSON")
            return []

    def _attach_ripple_paths(
        self, adjustments: List[BusinessDriverAdjustment]
    ) -> None:
        """Attach ripple paths from driver registry to each adjustment."""
        for adj in adjustments:
            driver = self._driver_registry.get(adj.driver_id)
            if driver and driver.ripple:
                adj.ripple_path = list(driver.ripple)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _summarize_state(state: Any) -> str:
        """Summarize UnifiedFinancialState for LLM context."""
        lines = []
        if state.revenue is not None:
            lines.append(f"Revenue: ${state.revenue:,.0f}/mo")
        if state.growth_rate is not None:
            lines.append(f"Growth rate: {state.growth_rate:.1%}")
        if state.growth_trajectory:
            lines.append(f"Growth trajectory: {state.growth_trajectory}")
        if state.burn_rate is not None:
            lines.append(f"Burn rate: ${state.burn_rate:,.0f}/mo")
        if state.runway_months is not None:
            lines.append(f"Runway: {state.runway_months:.1f} months")
        if state.cash_balance is not None:
            lines.append(f"Cash: ${state.cash_balance:,.0f}")
        if state.gross_margin is not None:
            lines.append(f"Gross margin: {state.gross_margin:.1%}")
        if state.headcount is not None:
            lines.append(f"Headcount: {state.headcount}")
        if state.stage:
            lines.append(f"Stage: {state.stage}")
        return "\n".join(lines) or "Limited financial data available."
