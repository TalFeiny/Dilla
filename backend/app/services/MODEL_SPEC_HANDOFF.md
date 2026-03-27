# Priors-Based Custom Model Engine — Handoff

## What This Is

NL prompt + actuals → LLM constructs custom weighted curves with priors → full P&L cascade → divergent paths with confidence bands and narration.

Replaces the disconnected regression/driver forecast paths with a unified engine where the LLM reasons about the business and outputs a structured ModelSpec that gets executed mathematically.

## What's Done

### 3 new files created

| File | Lines | What it does |
|------|-------|-------------|
| `backend/app/services/model_spec_schema.py` | ~135 | Pydantic types: `ModelSpec`, `CurveSpec`, `PriorSpec`, `ModifierSpec`, `ComponentSpec`, `MacroShockSpec`, `FundingEventSpec`, `MilestoneSpec`, `ExecutionResult` |
| `backend/app/services/model_spec_executor.py` | ~370 | `evaluate_curve()` — numpy math for logistic/linear/exponential/gompertz/composite/ratio/step/inherit curves. `ModelSpecExecutor.execute()` — evaluates all curves in topo-sorted order, feeds revenue into existing `CashFlowPlanningService.build_monthly_cash_flow_model()` via `revenue_trajectory`, overrides non-revenue metrics, applies funding events, generates Monte Carlo confidence bands from priors, checks milestones. Also: `update_model_with_actuals()` for Bayesian prior updating. |
| `backend/app/services/agent_model_constructor.py` | ~210 | `AgentModelConstructor.construct_models()` — sends actuals summary + user prompt to LLM via existing `ModelRouter`, gets back ModelSpec JSON. Summarizes actuals (revenue subcategories, growth rates, cost structure, cash position, data quality). Lists driver registry keys so the LLM can set `driver_overrides`. Fills defaults the LLM misses (COGS from gross margin, prior confidence from data quality). |

### Orchestrator wired (unified_mcp_orchestrator.py)

Two new entries in `AGENT_TOOLS` (lines ~1998-2012):
- `construct_forecast_model` — handler: `_tool_construct_forecast_model`. Calls `AgentModelConstructor`, stores specs in `shared_data["forecast_models"]`.
- `execute_forecast_model` — handler: `_tool_execute_forecast_model`. Calls `ModelSpecExecutor`, stores results in `shared_data["forecast_model_results"]`.

Two new entries in `TOOL_WIRING` (lines ~2381-2389):
- `construct_forecast_model`: requires `["companies"]`, produces `["forecast_models"]`
- `execute_forecast_model`: requires `["forecast_models"]`, produces `[]`

Auto-chaining works: if agent calls `execute_forecast_model` and `forecast_models` is missing, orchestrator auto-runs `construct_forecast_model` first.

Two handler methods added (lines ~10958-11088):
- `_tool_construct_forecast_model()` — resolves company_id, pulls actuals via `pull_company_data()`, calls constructor, stores in shared_data
- `_tool_execute_forecast_model()` — resolves company, calls executor with seed data, handles parent model inheritance chaining, stores results

### What was NOT created (already exists)

- **No `macro_shock_service.py`** — `MacroEventAnalysisService` already does this: LLM + Tavily search → sector-specific driver adjustments → scenario branches
- **No new regression math** — `AdvancedRegressionService` already has logistic/gompertz/polynomial fitting with auto-selection. The executor's `evaluate_curve()` is different: it evaluates with KNOWN params (from the LLM), not fitting from data
- **No new Monte Carlo engine** — `MonteCarloEngine` already wraps `build_monthly_cash_flow_model()` with perturbed drivers. The executor's `_generate_confidence_bands()` perturbs CURVE PARAMETERS based on PriorSpec confidence instead

---

## What's NOT Done Yet

### 1. NL Parser — add `model_construction` query type

**File:** `backend/app/services/nl_fpa_parser.py`

**What to do:** Add `"model_construction"` to `_QUERY_TYPE_PATTERNS` dict (line ~63):

```python
"model_construction": [
    r"\bbuild\b.*\b(model|forecast|projection)\b",
    r"\bcustom\b.*\b(model|curve|forecast)\b",
    r"\bpriors?\b", r"\bconfidence\b.*\bband",
    r"\bcomposite\b.*\b(curve|model)\b",
    r"\bmulti[\s-]?(model|scenario)\b.*\b(forecast|project)\b",
    r"\bseries\s+[a-d]\b.*\bby\b",  # "Series A by March"
    r"\bimpact\b.*\b(war|recession|tariff|rate)\b",  # macro event → model
],
```

Also add to `_STEP_PATTERNS`:
```python
"model_construction": [
    r"\b(build|construct|create)\b.*\b(model|forecast)\b.*\b(with|using|from)\b",
],
```

### 2. ForecastMethodRouter — add `model_construction` method

**File:** `backend/app/services/forecast_method_router.py`

**What to do:** Add `"model_construction"` to `METHODS` set (line ~38):
```python
METHODS = {
    "growth_rate", "regression", "advanced_regression", "driver_based",
    "seasonal", "budget_pct", "manual", "model_construction",
}
```

Consider adding auto-selection logic in `auto_select_method()` — when the user prompt contains model construction signals AND has 6+ months of actuals, route to `model_construction`.

### 3. ScenarioBranchService — `model_spec_id` support

**File:** `backend/app/services/scenario_branch_service.py`

**What to do:** In `execute_branch()` (line ~217), after merging assumptions, check if the branch has a `model_spec_id` in its assumptions. If so, load the ModelSpec and use `ModelSpecExecutor` instead of the default growth-rate cascade:

```python
# After line 240 (merged = self.merge_assumptions(chain))
model_spec_id = merged.get("model_spec_id")
if model_spec_id:
    from app.services.model_spec_executor import ModelSpecExecutor
    from app.services.model_spec_schema import ModelSpec
    # Load spec from DB or shared_data
    # executor = ModelSpecExecutor()
    # result = executor.execute(spec, base_data, months=forecast_months)
    # return result as branch forecast
```

This requires deciding WHERE ModelSpecs are persisted. Options:
- Supabase table (`forecast_model_specs`) — proper persistence
- In-memory `shared_data` only — session-scoped, simpler

### 4. FPAQueryClassifier — route `model_construction` to the right handler

**File:** `backend/app/services/fpa_query_classifier.py`

Check how `route()` works and ensure `model_construction` query type maps to calling `construct_forecast_model` + `execute_forecast_model` through the orchestrator.

### 5. Frontend — confidence bands + milestones on charts

The executor returns `confidence_bands` (p10/p25/p50/p75/p90 arrays) and `milestones` (hit/miss results). The frontend `ScenarioSection` / chart components need to:
- Render shaded regions for confidence bands on line charts
- Render milestone markers (target line + label + hit/miss indicator)
- Display the model's `narrative` in the AI narrative section

### 6. Persistence layer (optional but recommended)

Currently ModelSpecs live in `shared_data` (session-scoped). For persistence:
- Create `forecast_model_specs` Supabase table: `{id, company_id, user_id, spec_json, created_at, updated_at}`
- Add load/save methods to `_tool_construct_forecast_model` and `_tool_execute_forecast_model`
- Enable `update_model_with_actuals()` to run when new actuals are ingested

### 7. Bayesian updating integration

`model_spec_executor.update_model_with_actuals()` exists but isn't wired. When new actuals land (via `actuals_ingestion.py` or `parse_accounts`), call this to adjust prior confidence on stored ModelSpecs. This is the "learning" loop — models that predict well gain confidence, models that miss lose confidence and flag `needs_refit`.

---

## Architecture Diagram

```
User prompt ("Build me a Series A forecast by March")
    │
    ▼
NLFPAParser.parse() ─── classifies as "model_construction"
    │
    ▼
AgentModelConstructor.construct_models()
    │  ├── _summarize_actuals(CompanyData) → structured text
    │  ├── _get_driver_keys() → from DriverRegistry
    │  └── ModelRouter.get_completion() → LLM outputs ModelSpec JSON
    │
    ▼
ModelSpec (validated Pydantic)
    │  ├── curves: {revenue: logistic, cogs: ratio, opex: step_function}
    │  ├── macro_shocks: [{event: "recession", probability: 0.3, ...}]
    │  ├── funding_events: [{type: "equity", amount: 5M, period: "2026-03"}]
    │  ├── milestones: [{metric: "revenue", target: 200000, period: "2026-03"}]
    │  ├── priors: {confidence: 0.7, floor: 50000, ceiling: 500000}
    │  └── driver_overrides: {churn_rate: 0.03, nrr: 1.15}
    │
    ▼
ModelSpecExecutor.execute()
    │  ├── evaluate_curve() per metric (topo-sorted for ratio dependencies)
    │  ├── _apply_modifiers() — seasonal, shock, trend_break, step overlays
    │  ├── Build revenue_trajectory from curve arrays
    │  ├── CashFlowPlanningService.build_monthly_cash_flow_model() ← EXISTING
    │  ├── Override non-revenue metrics, recompute derived fields
    │  ├── Apply funding events (cash injection + debt service)
    │  ├── _generate_confidence_bands() — Monte Carlo over perturbed priors
    │  └── Check milestones (hit/miss/gap)
    │
    ▼
ExecutionResult
    ├── forecast: [{period, revenue, cogs, ..., cash_balance, runway}]  ← same shape as existing
    ├── confidence_bands: {p10: [...], p25: [...], p50: [...], p75: [...], p90: [...]}
    ├── milestones: [{target: 200K, actual: 185K, hit: false, gap: 15K}]
    ├── curves: {revenue: [...], cogs: [...]}  ← raw arrays for charting
    └── spec: ModelSpec  ← for comparison/inheritance
```

## How It Integrates (Not Replaces)

| Existing Service | How This Uses It |
|-----------------|-----------------|
| `CashFlowPlanningService` | Executor feeds `revenue_trajectory` into `build_monthly_cash_flow_model()`. Same P&L cascade, same output shape. |
| `ModelRouter` | Constructor calls `get_completion()` with `json_mode=True` to get ModelSpec JSON from LLM. |
| `DriverRegistry` | Constructor lists all driver assumption keys so LLM can set `driver_overrides`. Executor passes them through to cascade. |
| `MacroEventAnalysisService` | NOT called directly. Macro shocks in ModelSpec use the same reasoning pattern (probability-weighted, sector-specific) but are embedded in the spec by the constructor LLM. For deeper macro analysis, the agent should call `MacroEventAnalysisService` first, then feed insights into the model construction prompt. |
| `AdvancedRegressionService` | NOT called directly. Different job: it FITS curves from data (finds params). The executor EVALUATES curves with KNOWN params (from the LLM). Complementary, not overlapping. |
| `MonteCarloEngine` | NOT called directly. Different perturbation target: MonteCarloEngine perturbs DRIVERS. The executor perturbs CURVE PARAMETERS based on prior confidence. Both produce percentile bands. |
| `ScenarioBranchService` | Branches can reference a `model_spec_id` to use a ModelSpec instead of the default growth-rate model. (NOT YET WIRED — see "What's Not Done" #3.) |
| `CompanyData` / `pull_company_data()` | Constructor uses `CompanyData.time_series`, `.latest`, `.analytics` to summarize actuals for the LLM. Executor uses `.to_forecast_seed()` for cascade input. |

## Testing Plan

1. **Unit: curve evaluation** — Create a ModelSpec by hand with known params, evaluate, assert output matches manual calculation
2. **Unit: confidence bands** — Run `_generate_confidence_bands()` with a spec that has varying priors, verify band widths correlate with confidence
3. **Integration: constructor** — Give constructor a real `CompanyData` + prompt like "Build me a 24-month forecast", verify valid ModelSpec comes back with business-appropriate curves
4. **Integration: executor** — Feed constructor output into executor, verify P&L output shape matches `build_monthly_cash_flow_model()` output
5. **End-to-end via orchestrator** — Call `construct_forecast_model` tool with a prompt, then `execute_forecast_model`, verify results in `shared_data`
6. **Multi-model inheritance** — "Build base case and aggressive scenario" → two specs, second inherits from first
7. **Bayesian updating** — Run `update_model_with_actuals()` with actuals that match/diverge from prediction, verify confidence adjusts

## Key Design Decisions

- **No `safe_eval` / `custom_expr`** — The executor logs a warning and returns zeros. The LLM should use `composite` curves instead. Eval is a security risk we don't need.
- **Confidence bands use curve parameter perturbation, not driver perturbation** — This is intentional. The priors are about curve shape uncertainty ("is the logistic ceiling 200K or 300K?"), not driver uncertainty ("will churn be 3% or 5%?"). `MonteCarloEngine` already handles driver uncertainty. They're complementary.
- **MacroShockSpec is in the schema, not delegated to MacroEventAnalysisService** — The constructor LLM embeds shocks directly in the spec. For deep macro analysis, the agent should call `MacroEventAnalysisService` separately and feed results into the construction prompt. This keeps the executor stateless and deterministic.
- **No persistence yet** — Specs live in `shared_data` (session-scoped). Persistence is straightforward (Supabase table + JSON column) but was deferred to avoid premature schema decisions.
