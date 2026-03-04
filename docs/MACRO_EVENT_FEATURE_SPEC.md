# Macro Event Analysis — Build Spec

## What it does
User says: *"analyse the impact of the iran war on my pnl and scenarios"*

System does:
1. NL composer detects this is a macro/geopolitical event (not a company-specific what-if)
2. LLM generates targeted web search queries ("iran war oil price impact", "middle east conflict supply chain disruption startups")
3. Tavily searches execute, return real evidence
4. LLM reasons over evidence → extracts structured macro factors (oil +35%, shipping +20%, defense spending +15%, VC funding -10%) with 1st and 2nd order effects
5. LLM maps those factors to each portfolio company's specific drivers (from the 28-driver registry), considering sector exposure, revenue model, cost structure
6. Runs branched scenarios (severe/moderate/mild) through existing ScenarioBranchService
7. Either overlays onto existing scenario tree OR builds a new one
8. Returns full auditable reasoning chain + branched impact chart

**Key design principle: DYNAMIC, not template-based.** No hardcoded shock profiles. The LLM reasons from real search evidence every time. An "iran war" in 2024 vs 2026 will produce different impacts because the search evidence is different.

## What exists already

### Created (needs finishing)
- **`backend/app/services/macro_event_analysis_service.py`** — Core service with 5-step pipeline:
  - `_generate_search_queries()` — LLM generates search queries from event
  - `_execute_searches()` — Parallel Tavily searches, deduped
  - `_extract_macro_factors()` — LLM extracts structured MacroFactor objects from evidence
  - `_map_factors_to_drivers()` — LLM maps factors → DriverAdjustment objects per company
  - `_run_branched_scenarios()` — Runs severe/moderate/mild through ScenarioBranchService
  - Has chart builder and audit chain throughout
  - **Uses ModelRouter for LLM calls, Tavily for search** (matches existing codebase patterns)

### Updated (partially)
- **`unified_mcp_orchestrator.py`** — Tool registration updated:
  - New `analyse_macro_event` tool registered (both instances at ~line 938 and ~8171)
  - Old `apply_macro_shock` kept as "quick preset" fallback
  - **Handler `_tool_analyse_macro_event` NOT YET WRITTEN** — needs to be added

### Existing infrastructure to use
- **`driver_registry.py`** — 28 drivers with ripple chains, assumption key mapping, `drivers_to_assumptions()`
- **`driver_impact_service.py`** — `explain_ripple_path()` for audit narration
- **`scenario_branch_service.py`** — Fork-aware engine with `_apply_overrides()`, projection, chart generation
- **`scenario_tree_service.py`** — `apply_macro_shock()` for overlay onto existing trees (still useful for the overlay path)
- **`nl_scenario_composer.py`** — `is_macro_shock_query()` detection + `parse_what_if_query()` routing
- **`cash_flow_planning_service.py`** — `build_monthly_cash_flow_model()` for projections
- **`actuals_ingestion.py`** — `seed_forecast_from_actuals()` for base data
- **ModelRouter** — `get_completion(prompt, capability, json_mode=True, caller_context=...)` for LLM calls
- **Tavily** — `self._tavily_search(query)` on the orchestrator, returns `{results: [{title, url, content}]}`

## What needs to be built

### 1. `_tool_analyse_macro_event` handler in `unified_mcp_orchestrator.py`
Add next to `_tool_macro_shock` (~line 5177). This is the bridge between the agent and the service.

```python
async def _tool_analyse_macro_event(self, inputs: dict) -> dict:
    # 1. Instantiate MacroEventAnalysisService with self.model_router and self._tavily_search
    # 2. Get portfolio companies from self.shared_data["companies"]
    # 3. Call service.analyse_event(event, companies, forecast_months)
    # 4. Store result in self.shared_data["scenario_analysis"] and self.shared_data["macro_analysis"]
    # 5. If existing scenario_tree in shared_data, ALSO overlay using ScenarioTreeService
    # 6. Return serialized result with charts + reasoning chain
```

Key: pass `tavily_search_fn=self._tavily_search` so the service can search.

### 2. Add `analyse_macro_event` to intent tool lists
In the `INTENT_TOOLS` dict (~line 2024), add `"analyse_macro_event"` to these intents:
- `"scenario"` — primary home
- `"fpa"` — financial planning context
- `"general"` — should be discoverable from any intent

### 3. Upgrade `is_macro_shock_query` in `nl_scenario_composer.py` (~line 616)
Current detection is keyword-only ("recession", "tariff", "pandemic"). Needs to catch broader events:
- Wars/conflicts: "iran war", "china taiwan", "russia", "invasion"
- Policy: "eu ai act", "section 230", "antitrust", "ban"
- Market: "housing crash", "crypto collapse", "bank run"
- Supply chain: "suez canal", "chip shortage", "embargo"
- Or just: any question with "impact on my portfolio/pnl/companies/scenarios"

The detection doesn't need to be perfect — it just routes to the right tool. The LLM inside the service does the real understanding.

### 4. Scenario tree overlay path
When `self.shared_data["scenario_tree"]` already exists:
- The service should compute driver adjustments as normal
- Then translate those into the format `ScenarioTreeService.apply_macro_shock()` expects
- OR build a custom overlay: for each path in the tree, apply the per-company driver adjustments to the company snapshots at each node
- This gives the "purple overlay" visual on the existing tree chart

This means `_run_branched_scenarios` in the service needs a second code path:
```python
if existing_tree:
    # overlay mode: apply adjustments to existing tree nodes
else:
    # standalone mode: build new branches from actuals
```

### 5. 1st and 2nd order effects
The LLM prompt in `_extract_macro_factors` already asks for this but could be more explicit. Separate the factors into:
- **1st order**: Direct impact (oil price → energy costs)
- **2nd order**: Indirect impact (oil price → customer purchasing power → our revenue)
- **3rd order**: Systemic (oil price → inflation → rate hikes → funding environment → our runway)

Tag each MacroFactor with `order: 1|2|3` so the UI can show the causal chain.

### 6. ModelCapability fix
The service currently passes `capability="analysis"` as a string but ModelRouter expects `ModelCapability.ANALYSIS` enum. Fix the imports in the service:
```python
from app.services.model_router import ModelRouter, ModelCapability
```
And use `capability=ModelCapability.ANALYSIS` in all `get_completion` calls.

## Architecture summary

```
User: "analyse impact of iran war on my pnl"
  │
  ├─ Agent sees `analyse_macro_event` tool description
  │  (matches: geopolitical event + portfolio impact)
  │
  ▼
_tool_analyse_macro_event(event="iran war")
  │
  ├─ Gets portfolio companies from shared_data
  │
  ▼
MacroEventAnalysisService.analyse_event()
  │
  ├─ Step 1: LLM → search queries
  │   ["iran war oil price impact 2026", "middle east conflict startup funding"]
  │
  ├─ Step 2: Tavily parallel search → 15 sources
  │
  ├─ Step 3: LLM reasons over evidence → MacroFactors
  │   [{name: "oil spike", direction: "increase", magnitude: +35%, order: 1, confidence: "high",
  │     reasoning: "Brent crude historically +30-40% in ME conflicts...", sources: [...]}]
  │
  ├─ Step 4: LLM maps factors → DriverAdjustments per company
  │   [{company: "Tundex", driver: "revenue_growth", adjustment: -0.12,
  │     caused_by: "oil spike", reasoning: "Aerospace supply chain exposure..."}]
  │
  ├─ Step 5a: If existing scenario tree → overlay adjustments onto tree nodes
  │   OR
  ├─ Step 5b: Build new severe/moderate/mild branches from actuals
  │
  └─ Returns: MacroEventAnalysis
       ├─ reasoning_chain (step-by-step audit)
       ├─ macro_factors (with evidence + confidence)
       ├─ driver_adjustments (per company, with causal reasoning)
       ├─ scenario_branches (3 severities with projections)
       └─ chart (branched impact visualization)
```

## Files to touch
1. `unified_mcp_orchestrator.py` — Add `_tool_analyse_macro_event`, update intent tool lists
2. `macro_event_analysis_service.py` — Fix ModelCapability import, add overlay path, add effect ordering
3. `nl_scenario_composer.py` — Broaden `is_macro_shock_query` detection keywords
4. `scenario_tree_service.py` — Possibly add `apply_dynamic_macro_shock()` that takes driver adjustments instead of a shock_type string (optional, can work through existing overlay)

## What NOT to do
- Don't add more hardcoded shock types to `SHOCKS` dict in `scenario_tree_service.py`
- Don't template macro impacts — every event is unique, let the LLM reason
- Don't skip the web search step — real evidence prevents hallucinated numbers
- Don't remove `apply_macro_shock` — it's still useful as a quick preset fallback
