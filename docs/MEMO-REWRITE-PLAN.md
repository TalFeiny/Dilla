o  what # Memo Pipeline Rewrite — What Actually Needs to Change

## The Problem in One Sentence

We have 28 chart generators, a sourcing/scoring engine, gap fillers, radar inference, NAV estimation, PWERM modeling — and the memo pipeline ignores almost all of it, hardcodes DPI Sankey into every output, and templates force the memo into rigid boxes instead of letting the data shape the output.

---

## What We Have (and aren't using)

| Layer | What It Does | Used by Deck? | Used by Memo? |
|-------|-------------|---------------|---------------|
| `ChartDataService` — 28 generators | Scatter, radar, heatmap, treemap, waterfall, probability cloud, bull/bear/base, market map, tornado, monte carlo, etc. | ✅ Full dispatch (lines 5054-5114) | ❌ Only ~8 types via if/elif |
| `_infer_nav()` | Stage-based NAV with time appreciation | ✅ | ❌ |
| `_infer_radar_scores()` | 6D scoring from company attributes | ✅ | ❌ |
| `ensure_numeric()` fallback chains | revenue → arr → inferred_revenue → default | ✅ Consistent | ⚠️ Inconsistent |
| `SourcingService.score_companies()` | 7-dimension weighted scoring | ❌ | ❌ |
| `SourcingService.query_companies()` | SQL filter engine, 20+ filters | ❌ (for memo) | ❌ |
| `format_*_chart()` helpers | Consistent output structure for every chart type | ✅ | ⚠️ Partial |
| Frontend `chartDataFixer.ts` | Repairs broken/incomplete chart data | ✅ | ✅ (same renderer) |
| `lightweight_diligence` | Bulk web lookup for unknown companies | Available | Never triggered |
| `MarketIntelligenceService` | TAM, competitive mapping, trends | Initialized | Never called |
| `RevenueProjectionService` | Decay curves, forecasting | ✅ Pre-computed | ⚠️ Computed but charts don't use it |

---

## What's Actually Wrong

### 1. Templates are boxes, not guides

Every template in `memo_templates.py` declares fixed sections with hardcoded `chart_type` values. The memo is forced into that shape regardless of what data exists or what the user asked.

- `LP_QUARTERLY_ENHANCED` hardcodes `chart_type="dpi_sankey"` on two sections
- `PORTFOLIO_REVIEW` hardcodes `chart_type="dpi_sankey"`
- `IC_MEMO` hardcodes `chart_type="revenue_forecast"`, `"probability_cloud"`, `"cap_table_evolution"`
- No template uses `chart_type="auto"` despite `_suggest_chart_type` existing

**Result**: Template says "revenue forecast chart" → company has no revenue → "Chart data not available". Instead of showing what DOES work.

### 2. DPI Sankey has god-mode

It wins at every layer:
- **Templates**: Hardcoded in LP and Portfolio templates
- **Scoring**: Gets score 3 if `fund_metrics` exists (it always does), score 1 if ANY company has `total_funding`
- **Heading boost**: "DPI", "distribution", "flow" in heading → +2
- **Orchestrator**: Pre-computes it unconditionally before memo service runs
- **Fallback**: 3 nested strategies — Strategy 3 invents ownership (`funding × 0.1`) so it NEVER returns None
- **ChartDataService**: `generate_dpi_sankey()` fabricates investment amounts (`total_funding × 0.08`) and NAV (stage markup tables)

Every other chart can fail. DPI Sankey cannot. So every memo gets a DPI Sankey whether it makes sense or not.

### 3. Memo `_build_chart` only knows ~8 chart types

The deck agent dispatches 28 chart types via a clean lookup table. The memo service has a hand-written if/elif chain that handles ~8. The other 20 chart generators — heatmap, radar, market map, bull/bear/base, tornado, monte carlo, stacked bar, nav_live — are unreachable from the memo path.

### 4. Sourcing layer is disconnected

`SourcingService` has `query_companies()` and `score_companies()` — fast, local, no LLM. But:
- Memo generation never calls it
- The agent doesn't route portfolio queries through it
- Company scoring (growth signal, capital efficiency, stage fit, recency) is never used to inform chart selection or narrative focus
- When 20 companies arrive as name + stage stubs, nobody runs them through scoring to at least rank what's interesting

### 5. Prompt contradicts the data

System prompt says "never invent figures." Pipeline injects `[Est]` benchmarks. LLM sees conflict → drops estimated companies → writes about 2 out of 22.

### 6. `_summarize_data` only details data-rich companies

For portfolios >8 companies, it sends a compact table (good) plus detailed narratives only for companies with actual revenue (bad). The LLM latches onto the detailed ones, ignores the rest.

### 7. Memo generation skips upstream analysis

Deck generation runs: valuations → cap tables → PWERM → scenarios → revenue projections → THEN generates slides.

Memo generation runs: load companies → maybe benchmark enrich → call LightweightMemoService. The analysis that would populate `scenario_analysis`, `cap_table_history`, `revenue_projections` in shared_data is skipped or partial. So when templates reference these keys, they're empty.

---

## What to Change

### A. Kill template-locked charts — use the deck's dispatch pattern

**Files**: `lightweight_memo_service.py`, `memo_templates.py`

Instead of the if/elif chain in `_build_chart`, use the same dispatch table pattern as the deck agent:

```python
# Replace the if/elif chain with:
chart_dispatch = {
    "scatter_multiples": lambda: cds.generate_revenue_multiple_scatter(companies),
    "probability_cloud": lambda: cds.generate_probability_cloud(companies[0], check_size),
    "radar_comparison": lambda: cds.generate_radar_comparison(companies),
    "heatmap": lambda: cds.generate_heatmap(companies),
    "market_map": lambda: cds.generate_market_map(companies),
    "bull_bear_base": lambda: cds.generate_bull_bear_base(companies),
    "waterfall": lambda: cds.generate_waterfall(companies),
    "bar_comparison": lambda: cds.generate_bar_comparison(companies),
    "revenue_treemap": lambda: cds.generate_revenue_treemap(companies),
    "path_to_100m": lambda: cds.generate_path_to_100m(companies),
    "cap_table_evolution": lambda: cds.generate_cap_table_evolution(companies),
    "nav_live": lambda: cds.generate_nav_live(companies),
    "fpa_stress_test": lambda: cds.generate_fpa_stress_test(companies),
    "dpi_sankey": lambda: cds.generate_dpi_sankey(companies),
    # ... all 28 types
}
```

Then change all templates to `chart_type="auto"`. The template declares a chart *section*, `_suggest_chart_type` picks what works.

### B. Fix chart scoring — no more god-mode for any chart type

**File**: `lightweight_memo_service.py` `_suggest_chart_type`

Rewrite scoring to be data-driven, not chart-biased:

- Score based on **data availability**, not chart identity
- `dpi_sankey`: only score 2+ if actual `investment_amount` or `cost_basis` data exists — not just `fund_metrics` existing
- Count `inferred_revenue` / `inferred_valuation` toward thresholds (scatter needs 3+ with revenue — estimated counts)
- Remove the unconditional pre-computation of `dpi_sankey` in the orchestrator
- Let `generate_dpi_sankey()` return None when it doesn't have real investment data instead of fabricating `total_funding × 0.08`

### C. Wire sourcing into memo pre-flight

**File**: `unified_mcp_orchestrator.py` `_execute_memo_generation`

Before calling LightweightMemoService:

```python
# After loading companies, before memo generation:
sourcing = SourcingService(db)
scored = sourcing.score_companies(companies, target_stage=dominant_stage)

# Attach scores to shared_data so chart selection + narrative can use them
for company in companies:
    match = next((s for s in scored if s["name"] == company["company"]), None)
    if match:
        company["composite_score"] = match["score"]
        company["score_breakdown"] = match["score_breakdown"]
```

This gives every company a quality signal. Chart selection can prioritize high-scoring companies for detailed charts. Narrative can lead with what's interesting based on scoring, not just what has ARR.

### D. Fix the prompt/data contradiction

**File**: `lightweight_memo_service.py` system prompt (~line 181)

Remove:
> "Only use numbers from the provided data — never invent figures"

Replace with:
> "Use all provided data. Values tagged [Est] are stage-based benchmarks — include them but always label as estimates. NEVER skip a company because its data is estimated. When data is sparse, analyze portfolio-level patterns (sector concentration, stage distribution, deployment pace) that don't require per-company financials."

### E. Fix `_summarize_data` — profile all companies, not just data-rich

**File**: `lightweight_memo_service.py` `_summarize_data` (~line 1001)

Currently: compact table for all + detailed narrative only for companies with actual revenue.

Change: compact table for all + brief profile for EVERY company (what they do, stage, sector, key metric if any). Don't gate detailed profiles on `c.get("revenue")` — gate on composite_score from sourcing (top 5-8 get detail regardless of data source).

### F. Make templates flexible, not rigid

**File**: `memo_templates.py`

Templates should declare *intent*, not structure:

- Instead of 13 fixed sections with hardcoded chart types, declare 3-5 section *slots* with data requirements
- Each slot says "I need a chart about X" not "I need chart_type=dpi_sankey"
- The memo service fills slots based on what data actually exists
- If a slot can't be filled meaningfully, skip it — don't force a fabricated chart

Concrete example — a portfolio review template should say:
```python
sections = [
    _section("overview", "Portfolio Overview", type="narrative",
             prompt_hint="Big picture: themes, concentration, stage distribution, deployment"),
    _section("chart_1", "Portfolio Visualization", type="chart",
             chart_type="auto",
             prompt_hint="Best chart for showing portfolio composition or performance"),
    _section("analysis", "Key Findings", type="narrative",
             prompt_hint="What stands out, what needs attention, follow-on candidates"),
    _section("chart_2", "Supporting Analysis", type="chart",
             chart_type="auto",
             prompt_hint="Best chart for the analytical point being made"),
    _section("recommendations", "Recommendations", type="narrative",
             prompt_hint="Actionable next steps"),
]
```

Not 13 sections where half will fail because the data doesn't support them.

### G. Run upstream analysis before memo generation

**File**: `unified_mcp_orchestrator.py` `_execute_memo_generation`

The deck path runs valuations, PWERM, cap tables, projections BEFORE generating. The memo path skips most of this. Add the same pre-computation:

```python
# In _execute_memo_generation, BEFORE calling memo service:
# 1. Score companies via sourcing (fast, local)
# 2. Run PWERM for top-scored companies (enables probability_cloud, bull_bear_base)
# 3. Run revenue projections (enables path_to_100m, forecasts)
# 4. Compute fund metrics if fund_context exists (enables waterfall, nav_live)
# 5. THEN call LightweightMemoService with populated shared_data
```

This ensures the memo service has actual analysis data to work with, not empty keys.

---

## What NOT to Do

- **Don't build a deterministic portfolio table** — the memo should be flexible, not forced into yet another box
- **Don't add lightweight_diligence to the critical path** — it's web calls, adds latency and cost. Keep it optional / triggered by user
- **Don't add more templates** — we need fewer, more flexible templates
- **Don't over-engineer chart selection** — the deck dispatch table already works. Just use it.

---

## Order of Implementation

| # | Change | Why First | Files | Risk |
|---|--------|-----------|-------|------|
| 1 | Wire dispatch table into memo `_build_chart` | Unlocks all 28 chart types immediately | `lightweight_memo_service.py` | Low — additive |
| 2 | All templates → `chart_type="auto"` | Stop forcing charts that don't fit | `memo_templates.py` | Low — auto already exists |
| 3 | Fix `_suggest_chart_type` scoring | Level playing field, count estimated data | `lightweight_memo_service.py` | Medium — needs testing |
| 4 | Fix prompt contradiction | LLM uses all companies, not just data-rich | `lightweight_memo_service.py` | Low — prompt change |
| 5 | Fix `_summarize_data` | All companies get profiles | `lightweight_memo_service.py` | Low — logic change |
| 6 | Wire sourcing scoring into pre-flight | Companies get ranked, charts/narrative informed | `unified_mcp_orchestrator.py` | Low — additive |
| 7 | Simplify templates (fewer slots, intent-based) | Stop failing on empty sections | `memo_templates.py` | Medium — structural |
| 8 | Add upstream analysis to memo path | Populated shared_data for charts | `unified_mcp_orchestrator.py` | Medium — mirrors deck path |
| 9 | Remove DPI Sankey god-mode | Stop pre-computing, stop fabricating data | `unified_mcp_orchestrator.py`, `chart_data_service.py` | Low |

---

## The Goal

User asks a question → gets a memo with:
- 2-3 relevant charts picked by what data exists
- Clear narrative that covers the full portfolio
- Not forced into a 13-section template where 10 sections fail
- Not a DPI Sankey every time
- Sourcing scores informing what's interesting
- All the tooling we already built, actually wired in
