# Data Engine Migration — Handoff

## What Was Done

### `pull_company_data()` is the single FPA data engine

Every service that needs company financial data now pulls from one function.
Zero callers of `get_actuals_for_forecast` remain — only its definition in actuals_ingestion.py.

### Files Migrated

| File | Before | After |
|------|--------|-------|
| `company_data_pull.py` | — | Core. `CompanyData` class with 7 extraction methods |
| `actuals_ingestion.py` | `seed_forecast_from_actuals` did 6+ queries | Thin wrapper → `pull_company_data().to_forecast_seed()` |
| `rolling_forecast_service.py` | 3 separate DB queries (actuals, forecast seed, cell derivations) | 1 pull, `_reshape_to_pnl_rows(cd)` + `cd.to_forecast_seed()` |
| `monte_carlo_engine.py` | `_build_distributions` queried per-category | Uses `cd.historical_variance(category)` |
| `pnl_builder.py` | Already migrated | Passes `cd` to forecast router |
| `scenario_branch_service.py` | Already migrated | Uses `pull_company_data().to_forecast_seed()` |
| `forecast_method_router.py` | 6 calls to `get_actuals_for_forecast` | Takes optional `company_data=`, uses `sorted_amounts()` / `historical_values()` |
| `seasonality_engine.py` | 1 call to `get_actuals_for_forecast` | Takes optional `company_data=`, uses `historical_values(metric)` |
| `fpa_executor.py` | 1 call | `pull_company_data().historical_values("revenue")` |
| `driver_impact_service.py` | 2 calls (metric_a, metric_b) | 1 pull, `dict(cd.historical_values(metric))` |
| `unified_financial_state.py` | N queries (one per category) | 1 pull, loops `cd.time_series` |
| `fpa_query.py` | regression endpoint used `get_actuals_for_forecast` | Uses `cd.historical_values(category)` |
| `cfo_brain.py` | `seed_forecast_from_actuals` + separate router pull | 1 pull, passes `cd` to router |

### Dead Code Removed

- `actuals_ingestion._trailing_growth()` — replaced by `company_data_pull._trailing_growth_from_series()`
- `actuals_ingestion._trailing_growth_window()` — replaced by `_trailing_growth_window_from_series()`
- `actuals_ingestion._recommend_method()` — replaced by `company_data_pull._recommend_method()`

### CompanyData Extraction Methods (the "actions")

```
CompanyData
├── to_forecast_seed()        → flat dict for CashFlowPlanningService
├── by_period(start, end)     → {period: {category: amount}} for P&L grids
├── historical_values(cat)    → [(period, amount)] for regression/seasonality
├── sorted_amounts(cat)       → [amount, ...] for curve fitting
├── historical_variance(cat)  → {min, max, mean, n} for Monte Carlo distributions
├── category_latest_and_prev(cat) → (latest, prev) for KPI trend arrows
├── as_flat_dict()            → backward-compat snapshot shape
└── latest_with_overrides()   → latest values + caller overrides
```

---

## What's Missing — The Other Data Domains

CompanyData covers **FPA/P&L** (from `fpa_actuals` table). But the product has 4 other data domains with NO centralized pull:

### 1. Cap Table — SCATTERED & INFERRED

**Current state:** No `cap_tables` database table. Ownership is reconstructed on-the-fly from `funding_rounds` arrays (extracted by Claude from web sources).

**Who rebuilds it:**
- `pre_post_cap_table.py` — ownership evolution through rounds
- `comprehensive_deal_analyzer.py` — full waterfall reconstruction
- `legal_cap_table_bridge.py` — legal instrument mapping
- `advanced_cap_table.py` — dilution, preferences, anti-dilution

**What's needed:** A `CapitalStructureData` pull object that:
- Pulls from a persistent `cap_table_entries` table (shareholder + round + shares + class)
- Tracks instrument types (equity, debt, warrants, SAFEs, convertible notes)
- Provides: `ownership_by_shareholder()`, `dilution_waterfall()`, `preference_stack()`, `instrument_terms()`

### 2. Funding / Round Data — EXTRACTION-DRIVEN

**Current state:** Lives in `company_data['funding_rounds']` from Claude extraction. Not persisted in its own table. `intelligent_gap_filler.py` generates stage-based rounds when data is missing.

**What's needed:** Either:
- Persist extracted rounds to a `funding_rounds` table, OR
- Include in CapitalStructureData pull

### 3. Budget Data — HYBRID

**Current state:** Two sources:
- `budgets` + `budget_lines` tables (legacy manual budget, `m1`-`m12` columns)
- `scenario_branches` projection (modern, forward-looking)
- `budget_variance_service.py` compares either against FPA actuals

**What's needed:** A `BudgetData` pull that:
- Resolves the hierarchy (approved branch → budget_lines → none)
- Provides: `budget_by_period(category)`, `variance_report()`, `achievement_rate(category)`

### 4. Cost of Capital — HARDCODED STUB

**Current state:** WACC is hardcoded at ~13% in `ma_workflow_service.py`. Stage-based discount rates (60% pre-seed → 15% late) in `valuation_engine_service.py`. No real debt data pulled.

**What's needed:**
- `debt_terms` table (rate, maturity, covenants per instrument)
- Dynamic WACC from actual capital structure
- Provides: `wacc()`, `cost_of_equity()`, `cost_of_debt()`, `weighted_average()`

---

## How UnifiedFinancialState Should Evolve

Currently aggregates:
```
FPA actuals ✅ (via CompanyData)
KPIs        ✅ (via KPIEngine)
Forecast    ✅ (via CashFlowPlanningService)
Drivers     ✅ (via ScenarioBranchService)
Cap Table   ⚠️  minimal (total_raised + latest_round only)
Valuation   ✅ (via ValuationEngineService)
WACC        ❌ stubbed (None)
```

Target architecture — one pull object per domain:
```
CompanyData           → FPA/P&L (DONE)
CapitalStructureData  → cap table + instruments + funding rounds (NEEDED)
BudgetData            → budget lines + variance (NEEDED)
CostOfCapitalData     → WACC + debt terms (NEEDED)
```

Each follows the same pattern as CompanyData:
1. Single query to pull all raw data
2. Structured object with typed fields
3. Multiple extraction methods per consumer need
4. Optional param threading (so callers that already have it don't re-query)

`build_unified_state()` pulls all 4 in parallel → strategic layer reasons across all of them.

---

## Can Be Deleted (if desired)

- `actuals_ingestion.get_actuals_for_forecast()` — zero callers
- `actuals_ingestion.seed_forecast_from_actuals()` — still has callers but is a 2-line wrapper; could be replaced by direct `pull_company_data().to_forecast_seed()` calls
