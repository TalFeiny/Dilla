"""
Agent Model Constructor
Orchestrates existing services → feeds traced context to LLM → outputs ModelSpec.

The LLM is still the reasoning engine. But instead of guessing params from raw actuals,
it now receives:
  - Parsed events from NLScenarioComposer
  - Macro causal chains from MacroEventAnalysisService (for world events)
  - Business causal chains from BusinessEventAnalysisService (for company events)
  - Signals from StrategicIntelligenceService (what's already happening)
  - Sensitivity rankings from DriverImpactService (what matters most)
  - Ripple map from DriverRegistry (what impacts what)

Every curve parameter traces back to an event in the chain.
"""

import json
import logging
import uuid
from typing import Any, Dict, List, Optional

from app.services.model_router import ModelRouter, ModelCapability
from app.services.model_spec_schema import (
    CurveSpec,
    EventChain,
    ModelSpec,
    PriorSpec,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# System prompt — tells the LLM how to use the traced context
# ---------------------------------------------------------------------------

MODEL_CONSTRUCTOR_PROMPT = """You are a financial model constructor for a CFO intelligence platform.

You receive TRACED CONTEXT from real analytical services — events parsed from the user's
prompt, causal chains from macro/business analysis, detected signals from actual data,
sensitivity rankings, and the driver ripple graph.

Your job: synthesize ALL this traced context into ModelSpec JSON — custom mathematical
forecast models where every parameter traces back to a specific event or data point.

WHAT YOU RECEIVE:
- EVENTS: Parsed from the user's prompt (funding, hiring, partnerships, competitive, etc.)
- MACRO CHAINS: For world events — 1st/2nd/3rd order causal factors with evidence
- BUSINESS CHAINS: For company events — causal factors from actuals + signals
- SIGNALS: What's already happening (runway risk, growth deceleration, burn, margins)
- SENSITIVITY: Which drivers matter most for key metrics (perturbation-ranked)
- RIPPLE MAP: What impacts what — the driver dependency graph
- ACTUALS: Structured summary of company financials

WHAT YOU OUTPUT:
1. EVENT CHAIN — events with probabilities, causal links, and param_origins
   This IS the reasoning. Every parameter you set must trace to events in the chain.

2. MODEL SPEC — curves, priors, modifiers, macro shocks, funding events, milestones
   Every param derived from the event chain.

CURVE TYPES:
- logistic: S-curve with ceiling (capacity, saturation, market share limits)
- exponential: unconstrained growth (early stage, no ceiling yet)
- gompertz: asymmetric S-curve (slow start, fast middle, slow ceiling)
- linear: constant slope
- composite: weighted sub-curves by subcategory
- step_function: discrete jumps (pricing change, expansion, contract win)
- ratio: fraction of another metric (COGS = 35% of revenue)
- constant: flat value

METRIC KEYS (use these exact names as curve dict keys):
- revenue: top-line monthly revenue
- cogs: cost of goods sold
- gross_profit: revenue - cogs
- rd_spend: R&D expense
- sm_spend: Sales & Marketing expense
- ga_spend: General & Administrative expense
- total_opex: rd_spend + sm_spend + ga_spend
- ebitda: gross_profit - total_opex
- capex: capital expenditure
- free_cash_flow: ebitda - capex - debt_service - tax
- cash_balance: cumulative cash position
DO NOT use aliases like "opex", "fcf", "gp" — use the exact keys above.

RULES:
- EVERY parameter must trace to an event. No arbitrary numbers.
- Use the macro/business chains and sensitivity data — don't ignore what the services found.
- Preserve subcategory structure from actuals when available.
- Set priors based on data quality AND event probability.
- Include milestones when the request implies targets.
- The narrative must explain the model in business terms, referencing the event chain.
- driver_overrides should use the existing driver assumption keys listed below.

Output: JSON object with "event_chain" and "specs" (array of ModelSpec objects).
The event_chain is shared across all specs. Each spec references events by id."""


class AgentModelConstructor:
    """Orchestrates services → feeds LLM traced context → outputs ModelSpec."""

    def __init__(
        self,
        model_router: ModelRouter,
        tavily_search_fn=None,
    ):
        self.model_router = model_router
        self.tavily_search_fn = tavily_search_fn

    async def construct_models(
        self,
        prompt: str,
        company_data: Any,  # CompanyData from company_data_pull
        company_id: Optional[str] = None,
        existing_models: Optional[List[ModelSpec]] = None,
    ) -> List[ModelSpec]:
        """Build ModelSpecs from NL prompt + actuals + service context.

        Orchestration flow:
        1. Parse prompt → events (NLScenarioComposer)
        2. Detect signals from actuals (StrategicIntelligenceService pattern)
        3. For macro events → MacroEventAnalysisService causal chain
        4. For business events → BusinessEventAnalysisService causal chain
        5. Get sensitivity rankings (DriverImpactService)
        6. Get ripple map (DriverRegistry)
        7. Feed ALL context to LLM → derive EventChain + ModelSpec
        """
        existing_models = existing_models or []

        # Gather all context in parallel where possible
        actuals_summary = self._summarize_actuals(company_data)
        driver_keys = self._get_driver_keys()
        ripple_map = self._get_ripple_map()

        # 1. Parse prompt → structured events
        scenario_context = await self._parse_events(prompt)

        # 2. Detect signals from actuals
        signals_context = await self._detect_signals(company_id, company_data)

        # 3. Macro event analysis (if prompt mentions world events)
        macro_context = await self._analyse_macro_events(
            prompt, scenario_context, company_data
        )

        # 4. Business event analysis (for company-level events)
        business_context = await self._analyse_business_events(
            prompt, scenario_context, company_id, company_data
        )

        # 5. Sensitivity rankings
        sensitivity_context = await self._get_sensitivity(company_id)

        # 6. Build the LLM prompt with ALL traced context
        existing_ids = [m.model_id for m in existing_models]

        user_prompt = self._build_context_prompt(
            prompt=prompt,
            actuals_summary=actuals_summary,
            driver_keys=driver_keys,
            ripple_map=ripple_map,
            scenario_context=scenario_context,
            signals_context=signals_context,
            macro_context=macro_context,
            business_context=business_context,
            sensitivity_context=sensitivity_context,
            existing_ids=existing_ids,
        )

        # 7. LLM derives EventChain + ModelSpec from all context
        result = await self.model_router.get_completion(
            system_prompt=MODEL_CONSTRUCTOR_PROMPT,
            prompt=user_prompt,
            capability=ModelCapability.STRUCTURED,
            max_tokens=8192,
            temperature=0.4,
            json_mode=True,
            caller_context="agent_model_constructor",
        )

        response_text = result.get("response", "[]")
        return self._parse_response(response_text, company_data)

    # ------------------------------------------------------------------
    # Service orchestration steps
    # ------------------------------------------------------------------

    async def _parse_events(self, prompt: str) -> str:
        """Step 1: Parse prompt → structured events via NLScenarioComposer."""
        try:
            from app.services.nl_scenario_composer import NLScenarioComposer
            composer = NLScenarioComposer()
            scenario = composer.parse_what_if_query(prompt)

            if not scenario or not scenario.events:
                return "No structured events parsed from prompt."

            lines = [f"Parsed {len(scenario.events)} events from prompt:"]
            for ev in scenario.events:
                lines.append(
                    f"  - [{ev.event_type}] {ev.event_description}"
                    f" (entity: {ev.entity_name}, timing: {ev.timing})"
                )
                if ev.parameters:
                    lines.append(f"    params: {ev.parameters}")
                if ev.impact_factors:
                    lines.append(f"    impacts: {ev.impact_factors}")
            return "\n".join(lines)
        except Exception as e:
            logger.warning("NLScenarioComposer failed: %s", e)
            return f"Event parsing unavailable: {e}"

    async def _detect_signals(
        self, company_id: Optional[str], company_data: Any
    ) -> str:
        """Step 2: Detect strategic signals from actuals."""
        if not company_id:
            return "No company_id — signal detection skipped."
        try:
            from app.services.unified_financial_state import build_unified_state
            from app.services.strategic_intelligence_service import detect_signals

            state = await build_unified_state(
                company_id,
                company_data=company_data.to_forecast_seed()
                if hasattr(company_data, "to_forecast_seed") else None,
            )
            signals = detect_signals(state)

            if not signals:
                return "No strategic signals detected from actuals."

            lines = [f"Detected {len(signals)} signals from actuals:"]
            for s in signals:
                val = f" (current: {s.current_value})" if s.current_value else ""
                lines.append(f"  - [{s.severity}] {s.description}{val}")
            return "\n".join(lines)
        except Exception as e:
            logger.warning("Signal detection failed: %s", e)
            return f"Signal detection unavailable: {e}"

    async def _analyse_macro_events(
        self,
        prompt: str,
        scenario_context: str,
        company_data: Any,
    ) -> str:
        """Step 3: If prompt mentions world/macro events, run MacroEventAnalysis."""
        try:
            from app.services.nl_scenario_composer import NLScenarioComposer
            composer = NLScenarioComposer()
            if not composer.is_macro_shock_query(prompt):
                return "No macro events detected in prompt."
        except Exception:
            # If we can't check, try anyway if keywords suggest macro
            macro_keywords = [
                "war", "recession", "tariff", "rate", "inflation",
                "pandemic", "sanctions", "embargo", "regulation",
            ]
            if not any(kw in prompt.lower() for kw in macro_keywords):
                return "No macro events detected in prompt."

        try:
            from app.services.macro_event_analysis_service import (
                MacroEventAnalysisService,
            )

            # Build company summary for macro analysis
            cd = company_data
            company_summary = {
                "name": getattr(cd, "company_name", "Company"),
                "sector": getattr(cd, "sector", "technology"),
                "revenue": cd.latest.get("revenue", 0),
                "burn_rate": cd.analytics.get("burn_rate", 0),
                "headcount": cd.latest.get("headcount", 0),
            }

            svc = MacroEventAnalysisService(
                self.model_router, self.tavily_search_fn
            )
            analysis = await svc.analyse_event(
                event=prompt,
                portfolio_companies=[company_summary],
            )

            lines = ["Macro event analysis:"]
            for f in analysis.macro_factors[:8]:
                lines.append(
                    f"  Order {f.order}: {f.name} → {f.direction} "
                    f"{f.magnitude_pct:+.0%} (confidence: {f.confidence})"
                )
                if f.caused_by:
                    lines.append(f"    caused by: {f.caused_by}")
                if f.reasoning:
                    lines.append(f"    reasoning: {f.reasoning[:200]}")

            if analysis.driver_adjustments:
                lines.append(f"\n  Driver adjustments ({len(analysis.driver_adjustments)}):")
                for adj in analysis.driver_adjustments[:10]:
                    lines.append(
                        f"    {adj.driver_id}: {adj.adjustment_pct:+.0%}"
                        f" — {adj.reasoning[:100]}"
                    )
                    if adj.ripple_path:
                        lines.append(f"      ripple: {' → '.join(adj.ripple_path)}")

            return "\n".join(lines)
        except Exception as e:
            logger.warning("Macro event analysis failed: %s", e)
            return f"Macro analysis unavailable: {e}"

    async def _analyse_business_events(
        self,
        prompt: str,
        scenario_context: str,
        company_id: Optional[str],
        company_data: Any,
    ) -> str:
        """Step 4: Business event analysis for company-level events."""
        if not company_id:
            return "No company_id — business event analysis skipped."
        try:
            from app.services.business_event_analysis_service import (
                BusinessEventAnalysisService,
            )

            svc = BusinessEventAnalysisService(self.model_router)
            analysis = await svc.analyse_event(
                event=prompt,
                company_id=company_id,
                company_data=company_data.to_forecast_seed()
                if hasattr(company_data, "to_forecast_seed") else {},
            )

            lines = ["Business event analysis:"]
            for f in analysis.factors[:8]:
                lines.append(
                    f"  Order {f.order}: {f.name} → {f.direction} "
                    f"{f.magnitude_pct:+.0%} (confidence: {f.confidence})"
                )
                if f.caused_by:
                    lines.append(f"    caused by: {f.caused_by}")

            if analysis.driver_adjustments:
                lines.append(f"\n  Driver adjustments ({len(analysis.driver_adjustments)}):")
                for adj in analysis.driver_adjustments[:10]:
                    lines.append(
                        f"    {adj.driver_id}: {adj.adjustment_pct:+.0%}"
                        f" — {adj.reasoning[:100]}"
                    )

            return "\n".join(lines)
        except ImportError:
            return "Business event analysis service not available."
        except Exception as e:
            logger.warning("Business event analysis failed: %s", e)
            return f"Business event analysis unavailable: {e}"

    async def _get_sensitivity(self, company_id: Optional[str]) -> str:
        """Step 5: Sensitivity rankings from DriverImpactService."""
        if not company_id:
            return "No company_id — sensitivity analysis skipped."
        try:
            from app.services.driver_impact_service import DriverImpactService
            dis = DriverImpactService()

            lines = ["Sensitivity rankings (which drivers matter most):"]
            for target in ["revenue", "cash_balance", "runway_months", "ebitda"]:
                try:
                    ranking = await dis.driver_impact_ranking(company_id, target)
                    top = ranking.get("rankings", [])[:5]
                    if top:
                        drivers = ", ".join(
                            f"{r['driver_id']}({r.get('impact_pct', 0):+.0%})"
                            for r in top
                        )
                        lines.append(f"  {target}: {drivers}")
                except Exception:
                    continue

            return "\n".join(lines) if len(lines) > 1 else "Sensitivity data unavailable."
        except Exception as e:
            logger.warning("Sensitivity analysis failed: %s", e)
            return f"Sensitivity unavailable: {e}"

    # ------------------------------------------------------------------
    # Context assembly
    # ------------------------------------------------------------------

    @staticmethod
    def _get_ripple_map() -> str:
        """Get driver ripple map showing what impacts what."""
        try:
            from app.services.driver_registry import get_all_drivers
            drivers = get_all_drivers()
            lines = ["Driver ripple map (driver → downstream effects):"]
            for d in drivers.values():
                if d.ripple:
                    lines.append(f"  {d.id} → {', '.join(d.ripple)}")
            return "\n".join(lines)
        except Exception:
            return "(driver ripple map unavailable)"

    def _build_context_prompt(
        self,
        prompt: str,
        actuals_summary: str,
        driver_keys: str,
        ripple_map: str,
        scenario_context: str,
        signals_context: str,
        macro_context: str,
        business_context: str,
        sensitivity_context: str,
        existing_ids: List[str],
    ) -> str:
        """Assemble all traced context into a single LLM prompt."""
        return f"""User request: {prompt}

=== COMPANY ACTUALS ===
{actuals_summary}

=== PARSED EVENTS ===
{scenario_context}

=== STRATEGIC SIGNALS (from actuals) ===
{signals_context}

=== MACRO EVENT ANALYSIS ===
{macro_context}

=== BUSINESS EVENT ANALYSIS ===
{business_context}

=== SENSITIVITY RANKINGS ===
{sensitivity_context}

=== DRIVER RIPPLE MAP ===
{ripple_map}

=== AVAILABLE DRIVER KEYS ===
{driver_keys}

=== EXISTING MODELS (for inheritance) ===
{existing_ids if existing_ids else "None"}

Output a JSON object:
{{
  "event_chain": {{
    "events": [
      {{
        "id": "short-slug",
        "event": "Human-readable description of what happens",
        "category": "business | market | macro | funding | operational",
        "probability": 0.8,
        "timing": "2026-03",
        "duration_months": 12,
        "reasoning": "Why this event matters"
      }}
    ],
    "links": [
      {{
        "source": "event-id-or-metric",
        "target": "event-id-or-metric",
        "effect": "amplifies | dampens | triggers | blocks | shifts_timing | sets_ceiling | sets_floor | scales",
        "magnitude": 0.3,
        "delay_months": 2,
        "reasoning": "Why this causal connection exists"
      }}
    ],
    "param_origins": {{"metric.param": ["event-id", ...]}},
    "summary": "..."
  }},
  "specs": [
    {{
      "model_id": "short-slug",
      "narrative": "...",
      "curves": {{"revenue": ..., "cogs": ...}},
      "macro_shocks": [...],
      "funding_events": [...],
      "milestones": [...],
      "driver_overrides": {{}},
      "priors": {{}}
    }}
  ]
}}"""

    # ------------------------------------------------------------------
    # Response parsing
    # ------------------------------------------------------------------

    def _parse_response(
        self, response_text: str, company_data: Any
    ) -> List[ModelSpec]:
        """Parse LLM response → validated ModelSpec objects with EventChain."""
        try:
            raw = json.loads(response_text)
        except json.JSONDecodeError:
            logger.error(
                "Model constructor returned invalid JSON: %s",
                response_text[:200],
            )
            return []

        # Extract event chain
        event_chain = None
        if isinstance(raw, dict) and "event_chain" in raw:
            try:
                event_chain = EventChain.model_validate(raw["event_chain"])
            except Exception as e:
                logger.warning("Failed to parse EventChain: %s", e)

        # Extract specs
        if isinstance(raw, dict):
            specs_raw = raw.get("specs", raw.get("models", [raw]))
        elif isinstance(raw, list):
            specs_raw = raw
        else:
            specs_raw = [raw]

        if not isinstance(specs_raw, list):
            specs_raw = [specs_raw]

        specs = []
        for item in specs_raw:
            try:
                spec = ModelSpec.model_validate(item)
                # Attach the shared event chain to each spec
                if event_chain and not spec.event_chain:
                    spec.event_chain = event_chain
                spec = self._fill_defaults(spec, company_data)
                specs.append(spec)
            except Exception as e:
                logger.warning("Failed to validate ModelSpec: %s", e)
                continue

        return specs

    # ------------------------------------------------------------------
    # Actuals summary for LLM context
    # ------------------------------------------------------------------

    def _summarize_actuals(self, cd: Any) -> str:
        """Structured summary of what the LLM needs to reason about."""
        lines = []

        # Revenue structure
        rev_subs = {
            k: v for k, v in cd.time_series.items() if k.startswith("revenue:")
        }
        total_rev = cd.latest.get("revenue", 0)

        if rev_subs:
            lines.append(f"Revenue: ${total_rev:,.0f}/mo")
            for sub, ts in rev_subs.items():
                latest = list(ts.values())[-1] if ts else 0
                pct = (latest / total_rev * 100) if total_rev else 0
                lines.append(f"  {sub}: ${latest:,.0f} ({pct:.0f}%)")
        else:
            lines.append(f"Revenue: ${total_rev:,.0f}/mo (no subcategories)")

        # Growth trajectory
        a = cd.analytics
        if a.get("_trailing_growth_3m"):
            lines.append(
                f"Growth (3mo trailing): {a['_trailing_growth_3m']:.1%}"
            )
        if a.get("_trailing_growth_6m"):
            lines.append(
                f"Growth (6mo trailing): {a['_trailing_growth_6m']:.1%}"
            )
        if a.get("growth_rate"):
            lines.append(f"Growth rate: {a['growth_rate']:.1%}")

        # Cost structure
        gm = a.get("gross_margin") or cd.latest.get("gross_margin")
        if gm:
            lines.append(
                f"Gross margin: {gm:.1%}"
                if isinstance(gm, float)
                else f"Gross margin: {gm}"
            )

        for cat in ["_rd_spend", "_sm_spend", "_ga_spend"]:
            val = a.get(cat)
            if val:
                lines.append(f"  {cat.lstrip('_')}: ${val:,.0f}/mo")

        # Cash position
        burn = a.get("burn_rate", 0)
        if burn:
            lines.append(f"Burn: ${burn:,.0f}/mo")
        runway = a.get("runway_months")
        if runway:
            lines.append(f"Runway: {runway:.0f} months")

        cash = cd.latest.get("cash_balance")
        if cash:
            lines.append(f"Cash: ${cash:,.0f}")

        # Available categories
        all_cats = list(cd.time_series.keys())
        lines.append(f"Available categories: {all_cats}")

        # History depth
        if cd.periods:
            lines.append(
                f"Periods: {len(cd.periods)} months "
                f"({cd.periods[0]} to {cd.periods[-1]})"
            )

        # Data quality
        dq = a.get("_data_quality", {})
        if dq:
            lines.append(f"Data quality: {dq}")

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Driver keys from registry
    # ------------------------------------------------------------------

    @staticmethod
    def _get_driver_keys() -> str:
        """List available driver assumption keys for the LLM."""
        try:
            from app.services.driver_registry import get_all_drivers

            drivers = get_all_drivers()
            return ", ".join(
                f"{d.assumption_key} ({d.label})" for d in drivers.values()
            )
        except Exception:
            return "(driver registry unavailable)"

    # ------------------------------------------------------------------
    # Fill defaults the LLM might miss
    # ------------------------------------------------------------------

    def _fill_defaults(self, spec: ModelSpec, cd: Any) -> ModelSpec:
        """Fill gaps the LLM didn't specify, using actuals."""
        # Ensure model_id
        if not spec.model_id:
            spec.model_id = f"model-{uuid.uuid4().hex[:8]}"

        # If no COGS curve and we have gross margin data, derive it
        a = cd.analytics
        if "cogs" not in spec.curves:
            gm = a.get("gross_margin")
            if gm and isinstance(gm, (int, float)):
                spec.curves["cogs"] = CurveSpec(
                    type="ratio",
                    params={"of": "revenue", "ratio": round(1 - gm, 4)},
                )

        # Set prior confidence based on data quality
        dq = a.get("_data_quality", {})
        rev_months = dq.get("revenue_months", 0)
        if rev_months > 0:
            base_confidence = min(0.9, 0.4 + rev_months * 0.04)
            for curve in spec.curves.values():
                if curve.prior is None:
                    curve.prior = PriorSpec(confidence=base_confidence)

        return spec
