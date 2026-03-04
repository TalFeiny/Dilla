# CFO/P&L Pivot — Full Audit Report

## CRITICAL — Will Break in Production

### 1. `_tool_fpa_pnl` doesn't use PnlBuilder — returns flat garbage
**File:** `unified_mcp_orchestrator.py:6888`

The agent's P&L tool calls `get_company_actuals()` which returns raw `{key: {period: amount}}` dicts, NOT the hierarchical waterfall rows. Meanwhile the REST endpoint `/api/fpa/pnl` (`fpa_query.py:166`) uses `PnlBuilder` and returns proper rows. The agent gets worse P&L data than the API.

**Fix:** Rewrite `_tool_fpa_pnl` to instantiate `PnlBuilder`, call `build(company_id, start, end)`, and return the structured waterfall rows. Drop the raw `get_company_actuals()` path entirely.

---

### 2. `_tool_fpa_variance` over-validates — requires ALL 4 params
**File:** `unified_mcp_orchestrator.py:6938`

Requires `company_id`, `budget_id`, `start`, AND `end`. But `BudgetVarianceService.get_variance_report()` has smart defaults (YTD, approved branch as budget). The agent can NEVER call "show me YTD variance" because it doesn't know the `budget_id` upfront.

**Fix:** Make `budget_id`, `start`, and `end` optional. When omitted, let `BudgetVarianceService` use its own defaults (approved branch, YTD range).

---

### 3. `_tool_fpa_regression` calls wrong method signatures
**File:** `unified_mcp_orchestrator.py:7161-7167`

Calls:
- `svc.exponential_regression()` — actual method is `exponential_decay(data, time_periods)`
- `svc.monte_carlo_simulation(values, periods)` — actual signature is `monte_carlo_simulation(base_scenario, distributions, iterations)` (needs dict + dict, not list + int)
- `svc.sensitivity_analysis(values, periods)` — actual signature is `sensitivity_analysis(base_inputs, variable_ranges, model_function)` (needs dict + dict + callable, not list + int)

These will crash with `AttributeError` / `TypeError` every time.

**Fix:** Align tool wrapper to actual `FPARegressionService` method names and signatures. Build proper input dicts from the agent's parameters before calling each method.

---

### 4. Tool name mismatch: prompt says hyphens, registry uses underscores
**Files:** `cfo_brain.py:74-84`, tool registry in orchestrator

CFO prompt lists `fpa-pnl`, `fpa-variance`, etc. The registered tools are `fpa_pnl`, `fpa_variance`. If the LLM requests `fpa-pnl`, the orchestrator needs to normalize hyphens to underscores or the agent will fail to call any FPA tool.

**Fix:** Either update the CFO prompt to use underscores, or add hyphen-to-underscore normalization in the tool dispatch layer. Prompt update is simpler and less fragile.

---

### 5. `GET /api/fpa/models` is completely stubbed
**File:** `frontend/src/app/api/fpa/models/route.ts:45-48`

Always returns `{ models: [] }`. Dead endpoint.

**Fix:** Wire to backend scenario/model listing, or remove the endpoint and any frontend code that calls it.

---

## HIGH — Functional But Wrong Numbers

### 6. `seed_forecast_from_actuals` computes wrong growth rate
**File:** `actuals_ingestion.py:142-149`

`_trailing_growth` computes MoM growth from the last 2 data points. This is passed as `growth_rate` to `CashFlowPlanningService` which treats it as an **annual** growth rate. A 5% MoM growth gets treated as 5% annual, massively understating the forecast.

**Fix:** Annualize the MoM rate: `(1 + mom_rate) ** 12 - 1`.

---

### 7. PnlBuilder COGS double-counting
**File:** `pnl_builder.py:222-227`

Starts with `total_cogs = val("cogs")`, then loops and ADDS subcategory values. If actuals have both `cogs` (total) and `cogs:hosting` (subcategory), COGS will be counted twice.

**Fix:** If subcategories exist, sum them and ignore the parent `cogs` key. Only use the parent key when no subcategories are present.

---

### 8. `_tool_fpa_pnl` hardcodes 12-month forecast
**File:** `unified_mcp_orchestrator.py:6908`

`months=12` is hardcoded. Should respect the input or default to 24 like every other FPA tool.

**Fix:** Accept an optional `months` parameter, default to 24.

---

### 9. Duplicate P&L endpoint logic
**File:** `fpa_query.py:79-105`

The `/api/fpa/pnl` endpoint has its own `PNL_ROW_DEFS` with hardcoded splits (SaaS 85%, Services 15%, R&D salaries 75%, tooling 25%). `PnlBuilder` discovers these dynamically. Two completely different P&L rendering paths that will produce different numbers for the same company.

**Fix:** Refactor `/api/fpa/pnl` to use `PnlBuilder` instead of its own hardcoded row definitions. Single source of truth.

---

### 10. `CashFlowPlanningService` uses `revenue * opex_pct` even when revenue=0
**File:** `cash_flow_planning_service.py:163-165`

When `revenue > 0`, OpEx = revenue * benchmark %. When `revenue = 0`, it falls back to `burn_monthly * benchmark %`. But `burn_monthly` defaults to `STAGE_BURN_MONTHLY.get(stage, 400_000)` — a hardcoded guess. Pre-revenue companies get made-up burn figures.

**Fix:** When revenue=0 and no explicit burn rate is provided, flag the output as estimated and source the fallback from company actuals if available. At minimum, add a warning field to the response.

---

## MEDIUM — Missing Features / Incomplete Wiring

### 11. CFO prompt lists tools that DON'T EXIST
**File:** `cfo_brain.py`

The prompt lists `fpa-budget-create`, `fpa-upload-actuals`, `fpa-upload-budget`, `fpa-scenario-delete` — none of these are registered in `AGENT_TOOLS`. The LLM will try to call them and fail silently.

**Fix:** Either register these tools (services exist for most of them) or remove them from the CFO prompt. Don't promise tools that aren't wired.

---

### 12. `fpa_scenario_create` doesn't execute the branch
**File:** `unified_mcp_orchestrator.py:7051-7082`

Creates a DB row but never calls `ScenarioBranchService.execute_branch()`. The agent creates a scenario but never sees the projected numbers.

**Fix:** After creating the branch, call `execute_branch()`, run `driver_narration.py` for a structured summary, and return the comparison data.

---

### 13. `RollingForecastService` and `PnlBuilder` have no agent tools
Both are sophisticated services:
- `RollingForecastService` — stitches actuals + forecast into a rolling 24-month view
- `PnlBuilder` — builds a hierarchical P&L waterfall

Neither is callable by the CFO agent.

**Fix:** Register `fpa_rolling_forecast` and `fpa_pnl_waterfall` tools that wrap these services.

---

### 14. `FPAQueryClassifier` is a passthrough stub
**File:** `fpa_query_classifier.py:43`

`# TODO: Implement classification logic`. Just reads `parsed.query_type` and returns it.

**Fix:** Implement keyword/intent classification or remove the class and let callers use the parsed query type directly. Don't ship dead indirection.

---

### 15. `time_series_forecast` ignores the smoothing it computes
**File:** `fpa_regression_service.py:114-128`

Computes exponential smoothing but then forecasts using simple linear trend extrapolation (`last_value + trend * i`). The smoothed values are never used for the forecast.

**Fix:** Use the smoothed series as the basis for trend extraction, or use Holt's method which combines smoothing with trend natively.

---

### 16. No Xero sync agent tool
`XeroService` exists and works but the CFO agent can't trigger a data sync.

**Fix:** Register an `fpa_xero_sync` tool that calls `XeroService.sync_company_data(company_id)` and returns a summary of what was ingested.

---

### 17. `analyze_world_model_relationships` fake correlation
**File:** `fpa_regression_service.py:346-358`

Computes "relationship strength" from a single data point by dividing one value by another. This isn't correlation — it's meaningless.

**Fix:** Require minimum N data points and compute Pearson correlation, or remove the feature and don't surface fake statistics.

---

## LOW — Polish / Code Quality

### 18. `fpa_query.py` `/pnl` endpoint duplicates PnlBuilder with hardcoded splits
**File:** `fpa_query.py:79-105`

Defines `PNL_ROW_DEFS` with hardcoded revenue and cost splits. Superseded by `PnlBuilder`'s dynamic discovery.

**Fix:** Covered by issue #9 — refactor to use `PnlBuilder`.

---

### 19. Frontend FPA components are orphaned
`FPACanvas`, `MatrixCanvas`, `ModelEditor`, `NaturalLanguageQuery`, `QueryResults` — not imported by any page. They exist but aren't mounted anywhere.

**Fix:** Wire into the CFO dashboard page or delete. Dead components add confusion.

---

### 20. Hardcoded $15,000 cost per head
**File:** `scenario_branch_service.py:20`

`DEFAULT_COST_PER_HEAD_MONTHLY = 15_000`. Reasonable for US SaaS but should come from company data or be configurable per geography.

**Fix:** Accept as an optional driver input. Fall back to the hardcoded default only when not provided.

---

### 21. Revenue projection alpha = 0.3 hardcoded
**File:** `fpa_regression_service.py:115`

Fixed smoothing parameter with no optimization.

**Fix:** Use simple grid search or Holt-Winters optimization to pick alpha from the data.

---

## What's Actually Solid

| Component | Notes |
|---|---|
| **PnlBuilder** | Dynamic waterfall discovery from actuals, proper section ordering, computed rows. Well-built. |
| **CashFlowPlanningService** | Full monthly P&L engine with 15+ driver inputs (churn, NRR, CAC, sales cycle, debt, tax, working capital). Abacum-level complexity. |
| **ScenarioBranchService** | Fork-aware execution with parent chain, assumption merging, multi-branch charts, probability-weighted EV, capital raising analysis. Production quality. |
| **BudgetVarianceService** | Approved branch as budget source, YTD shortcuts, trend detection, department drilldown. Clean. |
| **DriverRegistry** | 28 drivers covering revenue/opex/workforce/capital/unit economics. Well-structured. |
| **DriverNarration** | Structured ripple traces and headlines so the agent doesn't hallucinate numbers. Great pattern. |
