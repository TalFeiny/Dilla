# Model Construction System — Complete Handoff

## What This Is

The model construction system is the core product loop:

**User prompts → event chain (causal reasoning) → derived curve params → P&L cascade → confidence bands → composable UI where humans and agents adjust together**

It replaces the old pattern where the agent just guessed params and waited for the next prompt. Now every parameter traces back to a business event, every event shows its ripple through the cascade, and the UI lets you toggle events, change probabilities, and watch the model recalculate.

## The Architecture

```
User prompt ("Build me a Series A forecast by March")
    │
    ▼
AgentModelConstructor.construct_models()
    │
    ├── NLScenarioComposer.parse_what_if_query(prompt)
    │     → Structured events: funding, competitive, operational, growth_change, etc.
    │
    ├── MacroEventAnalysisService.analyse_event()          ← FOR MACRO EVENTS
    │     → event → web search → LLM causal chain (1st/2nd/3rd order)
    │     → MacroFactor[] with caused_by chains
    │     → DriverAdjustment[] with ripple_path per company
    │
    ├── StrategicIntelligenceService.analyze()              ← FOR BUSINESS EVENTS
    │     → detect_signals(state) from actuals
    │     → trace_strategic_impact() cross-domain BFS
    │     → LLM synthesis → recommendations with quantified impact
    │
    ├── DriverImpactService                                 ← FOR ALL EVENTS
    │     → driver_impact_ranking(): perturbation sensitivity per metric
    │     → explain_ripple_path(): causal DAG traversal
    │     → trace_strategic_impact(): cross-silo quantified chains
    │     → explain_reverse_path(): "what affects runway_months?"
    │
    ├── DriverRegistry                                      ← THE GRAPH
    │     → 43 drivers with explicit ripple chains
    │     → revenue_growth → gross_profit → ebitda → cash_balance → runway_months
    │     → Cross-domain edges: ebitda → debt_capacity, runway → fundraise_urgency
    │
    ▼
EventChain (new schema layer)
    │  events: [{id, event, category, probability, timing, reasoning}]
    │  links: [{source, target, effect, magnitude, delay_months, reasoning}]
    │  param_origins: {"revenue.k": ["current-growth"], "revenue.step": ["enterprise-pipeline"]}
    │
    ▼
LLM derives ModelSpec FROM the traced chains
    │  Every curve param → traced to events
    │  Every macro shock → from MacroEventAnalysis causal chain
    │  Every funding event → from prompt events
    │  Every milestone → from prompt targets
    │
    ▼
ModelSpecExecutor.execute()
    │  → evaluate_curve() per metric (topo-sorted)
    │  → _apply_modifiers() (seasonal, shock, trend_break, step)
    │  → CashFlowPlanningService.build_monthly_cash_flow_model() ← EXISTING CASCADE
    │  → Override non-revenue metrics, recompute derived (gross_profit, ebitda, fcf)
    │  → Apply funding events (cash injection + debt service)
    │  → _generate_confidence_bands() Monte Carlo over priors
    │  → Check milestones (hit/miss/gap)
    │
    ▼
ExecutionResult
    ├── event_chain: EventChain          ← passed through for frontend
    ├── forecast: [{period, revenue, cogs, ..., cash_balance, runway}]
    ├── confidence_bands: {p10, p25, p50, p75, p90}
    ├── cascade_ripple: {metric → [{period, delta, source}]}  ← NEW
    ├── milestones: [{target, actual, hit, gap}]
    ├── curves: {revenue: [...], cogs: [...]}
    └── spec: ModelSpec
```

## What Exists (Built & Working)

### Causal Reasoning Infrastructure

| Service | File | What It Does |
|---------|------|-------------|
| **MacroEventAnalysisService** | `macro_event_analysis_service.py` | World events → Tavily search → LLM causal chain (1st/2nd/3rd order MacroFactors with caused_by) → DriverAdjustments with ripple_path → branched scenarios. Full audit chain. |
| **StrategicIntelligenceService** | `strategic_intelligence_service.py` | Detects signals from actuals (runway, growth, burn, margins, cash, unit economics) → traces cross-domain impact chains via DriverImpactService → dynamic WACC → LLM synthesis → strategic recommendations. Also proactive_check() after any tool. |
| **DriverImpactService** | `driver_impact_service.py` | 5 methods: correlate_actuals, driver_impact_ranking (perturbation sensitivity), explain_ripple_path (DAG traversal), explain_reverse_path (backward BFS), trace_strategic_impact (cross-silo quantified chains). Full audit trails. |
| **DriverRegistry** | `driver_registry.py` | 43 drivers with ripple chains. Each driver: id, label, level, unit, assumption_key, ripple targets. Cross-domain edges: 16+ bridges across FPA/Investment/Strategy. |
| **NLScenarioComposer** | `nl_scenario_composer.py` | Parses "what if" prompts → ScenarioEvent[] with event_type (growth_change, partnership, funding, exit, competitive, operational, regulatory), timing, parameters, impact_factors. |
| **WorldModelBuilder** | `world_model_builder.py` | Entities, factors (qualitative + quantitative across 8 categories), relationships, temporal dynamics. |
| **ScenarioAnalyzer** | `scenario_analyzer.py` | Multi-dimensional scenarios with factor overrides, probability weighting. |

### Model Spec Engine

| File | What It Does |
|------|-------------|
| **model_spec_schema.py** | Pydantic types: EventNode, CausalLink, EventChain (NEW), PriorSpec, ModifierSpec, ComponentSpec, CurveSpec, MacroShockSpec, FundingEventSpec, MilestoneSpec, ModelSpec (now has event_chain), ExecutionResult (now has event_chain + cascade_ripple) |
| **model_spec_executor.py** | evaluate_curve() for 10 curve types. _apply_modifiers(). Topo-sorted evaluation. Feeds into CashFlowPlanningService. Monte Carlo confidence bands from prior perturbation. Milestone checking. Bayesian update_model_with_actuals(). |
| **agent_model_constructor.py** | **NEEDS REBUILD** — currently just sends actuals to LLM and hopes for good params. Should orchestrate the services above. |

### Routing (Already Wired)

| File | What's Done |
|------|------------|
| `nl_fpa_parser.py` | `model_construction` in _QUERY_TYPE_PATTERNS and _STEP_PATTERNS |
| `forecast_method_router.py` | `model_construction` in METHODS set |
| `fpa_query_classifier.py` | `model_construction` in _keyword_fallback() |
| `scenario_branch_service.py` | `_execute_model_spec_branch()` — deserializes ModelSpec from branch assumptions, runs executor |
| `unified_mcp_orchestrator.py` | `construct_forecast_model` + `execute_forecast_model` tools with handlers |

---

## What Needs To Be Built

### 1. Rebuild `agent_model_constructor.py`

**The core change.** The constructor should orchestrate existing services, not guess params.

```python
class AgentModelConstructor:
    def __init__(self, model_router, tavily_search_fn=None):
        self.model_router = model_router
        self.tavily_search_fn = tavily_search_fn

    async def construct_models(self, prompt, company_data, company_id=None, existing_models=None):
        # 1. Parse prompt → events
        composer = NLScenarioComposer()
        scenario = await composer.parse_what_if_query(prompt)

        # 2. Detect signals from actuals (StrategicIntelligenceService pattern)
        state = await build_unified_state(company_id, company_data=...)
        signals = detect_signals(state)

        # 3. For macro events → MacroEventAnalysisService
        macro_analysis = None
        if _has_macro_events(scenario):
            macro_svc = MacroEventAnalysisService(self.model_router, self.tavily_search_fn)
            macro_analysis = await macro_svc.analyse_event(
                event=_extract_macro_text(prompt),
                portfolio_companies=[company_summary],
            )
            # macro_analysis.macro_factors → 1st/2nd/3rd order causal chain
            # macro_analysis.driver_adjustments → quantified per-driver changes

        # 4. For business events → DriverImpactService + StrategicIntelligenceService
        dis = DriverImpactService()
        impact_chains = []
        sensitivity = {}
        for target in ["revenue", "cash_balance", "runway_months", "ebitda"]:
            ranking = await dis.driver_impact_ranking(company_id, target)
            sensitivity[target] = ranking.get("rankings", [])[:5]

        # For signals, trace cross-domain impacts
        for signal in signals:
            if signal.current_value and signal.metric in TRACEABLE:
                trace = dis.trace_strategic_impact(state, signal.metric, delta, max_depth=4)
                impact_chains.extend(trace.get("chains", [])[:3])

        # 5. Get driver ripple map
        ripple_map = _format_driver_ripple_map()

        # 6. Feed ALL context to LLM → derive curves with traceability
        #    The LLM sees: events, macro causal chain, signals, impact chains,
        #    sensitivity rankings, ripple map, actuals summary
        #    It derives: EventChain + ModelSpec with param_origins
        result = await self.model_router.get_completion(
            system_prompt=CONSTRUCTOR_SYSTEM_PROMPT,  # see below
            prompt=_build_context_prompt(
                prompt, actuals_summary, scenario, macro_analysis,
                signals, impact_chains, sensitivity, ripple_map,
            ),
            json_mode=True,
        )

        # 7. Parse → validate → fill defaults → return
        specs = _parse_and_validate(result, company_data)
        return specs
```

**System prompt** tells the LLM:
- You receive traced impact chains from real services — USE them
- Identify events from the prompt, map causal links using the provided ripple graph
- Derive every curve param from specific events (param_origins required)
- No arbitrary numbers — every param traces to an event or data point

### 2. Build `business_event_analysis_service.py` (Micro Equivalent)

Same pattern as MacroEventAnalysisService but for company-level events:

```python
class BusinessEventAnalysisService:
    """Micro-level event analysis — same pattern as MacroEventAnalysisService.

    Macro: world event → search → causal chain → driver adjustments
    Micro: business event → actuals + signals → causal chain → driver adjustments

    Events: funding, hiring, product launch, pricing change, partnership,
    competitor move, expansion, churn spike, contract win/loss, etc.
    """

    async def analyse_event(
        self,
        event: str,                    # "Close Series A at $5M pre"
        company_id: str,
        company_data: Dict,
    ) -> BusinessEventAnalysis:
        # 1. Build unified state from actuals
        state = await build_unified_state(company_id, company_data=company_data)

        # 2. Detect existing signals (what's already happening)
        signals = detect_signals(state)

        # 3. LLM extracts business impact factors with causal orders
        #    Same structure as MacroFactor but business-focused:
        #    Order 1: "Series A closes" → cash_balance +$5M
        #    Order 2: "Hire 5 engineers" → burn_rate +$75K/mo, rd_spend +$75K/mo
        #    Order 3: "Product velocity increases" → revenue_growth +5%, churn -1%
        factors = await self._extract_business_factors(event, state, signals)

        # 4. Map factors → driver adjustments (same as macro pattern)
        adjustments = await self._map_factors_to_drivers(event, factors, state)

        # 5. Trace ripple paths for each adjustment
        dis = DriverImpactService()
        for adj in adjustments:
            path = dis.explain_ripple_path(adj.driver_id)
            adj.ripple_path = path.get("path", [])

        return BusinessEventAnalysis(
            event_description=event,
            signals=signals,
            factors=factors,
            driver_adjustments=adjustments,
            reasoning_chain=reasoning_chain,
        )
```

This mirrors MacroEventAnalysisService exactly:
- Macro: event → **web search** for context → LLM causal chain → driver adjustments
- Micro: event → **actuals + signals** for context → LLM causal chain → driver adjustments

### 3. Update Executor — Pass event_chain + cascade_ripple

**File:** `model_spec_executor.py`

In `execute()`, after computing the forecast:

```python
# In execute(), after step 5 (override non-revenue metrics):

# Compute cascade ripple — how each curve's values propagate
cascade_ripple = self._compute_cascade_ripple(spec, context, forecast, start_period)

# Pass event_chain through to result
return ExecutionResult(
    model_id=spec.model_id,
    narrative=spec.narrative,
    event_chain=spec.event_chain,          # ← pass through
    forecast=forecast,
    confidence_bands=bands,
    cascade_ripple=cascade_ripple,          # ← new
    milestones=milestone_results,
    curves=curves_out,
    spec=spec,
)
```

`_compute_cascade_ripple()` compares each metric's curve values against a baseline (no-change) to show deltas at each period — this is what the stacked bar chart needs.

### 4. Orchestrator — Write model_spec to branch assumptions

**File:** `unified_mcp_orchestrator.py`

In `_tool_construct_forecast_model()`, after storing specs in shared_data, also create a branch with the model_spec in assumptions:

```python
# After storing in shared_data["forecast_models"]
for spec in specs:
    # Create a scenario branch with model_spec embedded
    branch_assumptions = {
        "model_spec": spec.model_dump(),
        "model_spec_id": spec.model_id,
    }
    # Use ScenarioBranchService to create the branch
    await sbs.create_branch(
        company_id=company_id,
        branch_name=spec.model_id,
        assumptions=branch_assumptions,
        parent_branch_id=None,  # or existing branch
    )
```

This way `_execute_model_spec_branch()` in ScenarioBranchService (already wired) picks it up automatically.

### 5. Frontend — CascadeModelView ✅ BUILT

**File:** `frontend/src/components/memo/sections/CascadeModelView.tsx`

Composes three visualization layers in one vertical stack:

1. **Branched line** — forecast trajectory with confidence bands (p10/p25/p50/p75/p90) using `renderBranchedLine()`. Milestone annotations shown as fork-point markers.
2. **Stacked bar** — cascade ripple showing cumulative delta per metric (revenue, cogs, gross_profit, opex, ebitda, cash_balance, runway). Color-coded per metric.
3. **Event chain narrative** — each event as a card showing probability, timing, reasoning. Causal links displayed as `source → target (effect, magnitude)` with delay indicators.

Data contract: takes `ModelExecutionResult` with `forecast`, `confidence_bands`, `cascade_ripple`, `event_chain`, `milestones`, `narrative`.

### 6. Frontend — ModelSpecEditor ✅ BUILT

**File:** `frontend/src/components/memo/sections/ModelSpecEditor.tsx`

Shows the EVENT CHAIN with interactive controls:

- **Event cards** — checkbox toggle (enable/disable), probability slider (0-1), category badge, expandable detail
- **Expanded view** — timing, reasoning, outgoing ripple links with magnitude and delay
- **Param origins** — grid showing which events drive which curve parameters
- **Re-prompt input** — "Add event or adjust..." triggers new construction
- **Run button** — re-executes with current event state

When user toggles an event: sets probability to 0 (disabled) or restores original. Probability changes update local state, re-run on "Run" click propagates to executor.

### 7. Wire into ForecastMethodSection ✅ BUILT

**File:** `frontend/src/components/memo/sections/ForecastMethodSection.tsx`

`model_construction` added as first option in method dropdown. When selected:
- Config bar hides metric/chart/view selectors (model construction renders all three views)
- NL prompt input replaces the Build button (MessageSquare icon, "Construct" CTA)
- Chart area replaced with `CascadeModelView` (branched line + cascade bar + narrative)
- Below chart: `ModelSpecEditor` shows event chain with toggles/probability/re-prompt
- Flow: user enters prompt → `constructForecastModel()` → `executeForecastModel()` → result feeds both views

API helpers added in `frontend/src/lib/memo/api-helpers.ts`:
- `constructForecastModel(companyId, prompt)` — routes through unified-brain with tool_hint
- `executeForecastModel(companyId, modelId?, months?)` — routes through unified-brain with tool_hint

---

## Service Wiring Map

```
AgentModelConstructor
  ├── uses → NLScenarioComposer (parse prompt → events)
  ├── uses → MacroEventAnalysisService (macro events → causal chain → driver adj)
  ├── uses → BusinessEventAnalysisService (micro events → signals → driver adj)
  ├── uses → StrategicIntelligenceService (signals from actuals → impact chains)
  ├── uses → DriverImpactService (sensitivity, ripple paths, cross-silo traces)
  ├── uses → DriverRegistry (what impacts what — the graph)
  ├── uses → ModelRouter (LLM derives params from ALL the above)
  └── outputs → ModelSpec (with EventChain attached)

ModelSpecExecutor
  ├── uses → CashFlowPlanningService (existing P&L cascade)
  ├── uses → evaluate_curve() (logistic/linear/exponential/gompertz/etc)
  ├── computes → cascade_ripple (delta per metric per period)
  └── outputs → ExecutionResult (forecast + bands + ripple + milestones + event_chain)

Orchestrator (unified_mcp_orchestrator.py)
  ├── construct_forecast_model → AgentModelConstructor + ScenarioBranchService (create branch)
  ├── execute_forecast_model → ModelSpecExecutor → returns event_chain + cascade_ripple + forecast
  └── stores results in shared_data for cross-tool access

Frontend
  ├── api-helpers.ts → constructForecastModel() + executeForecastModel() via unified-brain
  ├── ForecastMethodSection → model_construction mode (NL prompt + compose views)
  ├── CascadeModelView → branched_line + stacked_bar + event narrative
  └── ModelSpecEditor → event chain with toggles, probability, re-prompt, run
```

## The Key Insight

The entire system — DriverRegistry, DriverImpactService, MacroEventAnalysisService, BusinessEventAnalysisService, StrategicIntelligenceService, NLScenarioComposer, WorldModelBuilder — was built for THIS. The model constructor is the orchestration layer that ties them together:

- **Macro** asks: "What world events matter?" → MacroEventAnalysisService
- **Micro** asks: "What business events matter?" → BusinessEventAnalysisService + StrategicIntelligenceService
- **Graph** asks: "What impacts what?" → DriverRegistry + DriverImpactService
- **Sensitivity** asks: "How much?" → DriverImpactService.driver_impact_ranking()
- **Derivation** asks: "So what are the curve params?" → LLM with ALL the traced context
- **UI** asks: "Show me why" → EventChain with param_origins
- **UI** asks: "What if I change this?" → Toggle event, adjust probability, re-run

The agent doesn't guess. It reasons through traced, auditable chains. The human sees those chains and can adjust. The model recalculates. That's the loop.

## What's Next — Chart Shape Generation

The CascadeModelView currently passes data directly to TableauLevelCharts. The shape transformation happens in `buildBranchedLineData()` and `buildCascadeStackedBar()` inside CascadeModelView. For richer chart shapes:

1. **Backend shape generation** — the executor could pre-build chart shapes (like ForecastMethodSection's `fit_data` pattern) so the frontend just passes through
2. **Monte Carlo fan** — confidence bands could render as a proper fan chart using `renderMonteCarloFan()` instead of branched lines
3. **Time-series cascade** — stacked bar could show period-by-period deltas instead of cumulative, allowing the user to see when each ripple hits

---

## What's Next — Event→Math Composition Engine

**The core gap.** Right now the pipeline is:

```
Events (structured) → LLM (black box) → curve params (JSON) → executor (math)
```

The LLM still guesses the math. Events trace *why* but don't mathematically *determine* the curve. We need a deterministic composition layer where events directly produce the model's shape, weights, dips, variance, and volatility.

### 1. Shape — curve type + param derivation from actuals + events

The curve type and its parameters should be computed, not LLM-picked.

```
Signals from actuals:
  growing + ceiling detected (market size, capacity)  → logistic
  growing + no ceiling visible                        → exponential
  decelerating + ceiling approaching                  → gompertz
  flat / mature                                       → linear or constant
  step changes in history                             → step_function or piecewise_linear

Base params from actuals (not LLM):
  k (growth rate)   ← trailing MoM growth from actuals
  L (ceiling)       ← operational ceiling from market/segment/capacity signals
  x0 (inflection)   ← current position on curve given k and current revenue vs L
  intercept         ← last actual value

Events then MODIFY the base shape:
  "enterprise pipeline closes" (p=0.5) → step modifier at timing month, delta = deal size × p
  "hire 5 engineers" (p=0.9)           → trend_break: steeper slope after ramp delay
  "competitor enters" (p=0.4)          → shock: magnitude from CausalLink, weighted by p
  "Series A closes" (p=0.7)           → funding event + downstream capacity unlock
```

### 2. Weights — probability-weighted event composition

When multiple events affect the same metric, their contributions combine by probability:

```
Base curve: logistic(L=300K, k=0.08, x0=12)  ← from actuals

Event contributions (additive modifiers):
  current_traction (p=0.9): already baked into base k — this IS the base curve
  enterprise_pipeline (p=0.5): step +$40K/mo at month 6, weighted by p → +$20K/mo
  recession_risk (p=0.3): shock -15% for 6mo, weighted by p → -4.5% effective
  new_product_line (p=0.4): separate sub-curve, weight = p = 0.4

Composite: base_logistic + Σ(event_modifier × event.probability)
```

For composite curves (multiple revenue streams), each component's weight should reflect its event probability, not a static number.

### 3. Dips — event-driven negative pressure

Negative events should mathematically create dips in the curve at the right time:

```python
for event in negative_events:
    link = find_link(event.id, target_metric)
    modifier = ShockModifier(
        start_month=period_to_month(event.timing) + link.delay_months,
        magnitude=link.magnitude * event.probability,   # probability-weighted
        duration_months=event.duration_months or 6,
        recovery="gradual",  # or from link metadata
    )
```

A 40% chance of -30% competitor impact = an effective -12% dip in the curve. The user sees the full -30% in the event card but the math applies the probability-weighted version. When they toggle the event OFF, the dip disappears. When they set p=1.0, the full -30% hits.

### 4. Variance — event-probability-driven confidence bands

Current: perturb ALL params by `(1 - confidence) * 0.5` uniformly.

Should be: **each event's probability determines the variance it contributes.**

```
Event at p=0.95 → near-certain, contributes almost no variance
Event at p=0.50 → coin flip, contributes maximum variance (Bernoulli: p(1-p) = 0.25)
Event at p=0.10 → unlikely, contributes modest variance but in one tail

Variance contribution per event = magnitude² × p × (1-p)
  → peaks at p=0.5 (maximum uncertainty)
  → vanishes at p=0 or p=1 (certain)

Confidence bands should be WIDER at months where uncertain events hit.
A funding event at p=0.5 in month 6 → bands widen starting month 6.
A growth continuation at p=0.9 → bands stay narrow.
```

Monte Carlo should sample event ON/OFF (Bernoulli with event.probability) rather than perturbing params with Gaussian noise. Each MC sample either includes an event or doesn't, producing naturally bimodal bands around uncertain events.

### 5. Volatility — period-to-period noise from business characteristics

Currently zero volatility — all curves are smooth. Real data has noise.

```
Volatility sources:
  customer_concentration: few customers → high vol (one churn = big swing)
  revenue_type: recurring (low vol) vs project-based (high vol)
  growth_stage: early (high vol) vs mature (low vol)
  seasonality_strength: strong seasonal → predictable vol pattern
  event_uncertainty: more uncertain events → higher regime-change vol

Vol model:
  base_vol = f(customer_count, revenue_type, growth_stage)
  event_vol = Σ(event.magnitude × sqrt(event.p × (1-event.p)))  # from Bernoulli variance
  total_vol = sqrt(base_vol² + event_vol²)

Apply as multiplicative noise per period:
  y[t] = curve[t] × (1 + N(0, total_vol))
  or with mean-reversion:
  noise[t] = ρ × noise[t-1] + sqrt(1-ρ²) × N(0, vol)  # AR(1) for realistic stickiness
```

### 6. Shape (the synthesis)

All of the above composes into the final curve the user sees:

```
final_shape[t] =
    base_curve(t; params_from_actuals)                      # shape from data
  + Σ event_modifiers(t; magnitude × probability)           # weighted event effects
  × (1 + seasonal(t))                                       # seasonality overlay
  × (1 + volatility_noise(t))                               # realistic noise

confidence_band[t] = Monte Carlo over:
  - Bernoulli sampling of events (on/off by probability)
  - param perturbation scaled by prior confidence
  - volatility noise
```

### Implementation: `EventComposer`

New service: `event_composer.py` — sits between the constructor and executor.

```python
class EventComposer:
    """Deterministic: EventChain + actuals → ModelSpec. No LLM for math."""

    def compose(
        self,
        event_chain: EventChain,
        actuals: CompanyData,
        signals: List[Signal],
    ) -> ModelSpec:
        # 1. Select curve type from signals
        curve_type = self._select_shape(actuals, signals)

        # 2. Derive base params from actuals
        base_params = self._fit_base_params(curve_type, actuals)

        # 3. Layer event modifiers (probability-weighted)
        modifiers = self._events_to_modifiers(event_chain)

        # 4. Compute per-event variance contributions
        priors = self._events_to_priors(event_chain)

        # 5. Derive volatility from business characteristics
        vol = self._compute_volatility(actuals, event_chain)

        # 6. Assemble ModelSpec
        return ModelSpec(...)
```

The LLM's role shrinks to:
- **Causal reasoning**: which events matter, what order, what magnitude (still LLM)
- **Narrative**: explaining the model in business terms (still LLM)
- **Math**: deterministic from events + actuals (NO LLM)

This means toggling an event in the UI instantly recomputes the curve — no LLM round-trip needed for re-execution. The LLM only runs on initial construction and re-prompt.
