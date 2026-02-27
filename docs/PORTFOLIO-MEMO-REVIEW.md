# Memo Pipeline — Review & Rewrite Plan

## What Happened

User asked for a follow-on analysis across a 22-company portfolio. System spent 18 API calls and produced:
- A thin exec summary saying "you have a data gap"
- Analysis of only the 2 companies that had ARR (Arcee AI, BeZero Carbon)
- 1 chart (the rest failed)
- Claimed "18 grid suggestions" but none appeared
- PDF export showed a nice table — proving the rendering works, the content doesn't

## What It Should Have Done

- Analyze the portfolio as a whole — themes, stages, sectors, concentration
- Cover ALL 22 companies, not just the 2 with ARR
- For the 18-20 unknowns: at least go learn what they do (lightweight_diligence exists for this)
- Produce a structured, well-formatted memo — not a data dump about 2 companies
- 3-5 API calls max, not 18

---

## The Prompt Chain (Actual Code) & Weaknesses

### Prompt 1: Goal Extraction (`unified_mcp_orchestrator.py:7967`)

```
User request: {prompt}
Companies mentioned: {companies_json}

Extract the concrete goals the user wants achieved. Each goal should map to a tool outcome.
...
Examples:
- "portfolio performance" -> [enrich, analyze, write_memo]
- "analyze @Ramp" -> [enrich_ramp, valuate_ramp, write_memo]
```

**Weakness**: Every example starts with "enrich/fetch." The model learns: step 1 is always enrichment. For a portfolio-level question where companies are already loaded, this is wasted work. There's no goal pattern for "synthesize what you already know" or "go learn about the unknowns." The goals are tool-shaped, not outcome-shaped.

### Prompt 2: TaskPlanner Decomposition (`session_state.py:1158`)

```
RULES:
1. READ THE FINGERPRINT. If a field shows + or ~, DO NOT re-fetch it.
   Skip straight to analysis/valuation. If it shows -, you MUST fill it before proceeding.
2. For missing data: resolve_data_gaps for bulk, parallel search_company_* for 1-2.
   NEVER tell the user "data not available" — GO GET IT.
...
5. Only include generate_memo when the user EXPLICITLY asks for a written deliverable.
7. MINIMAL PLAN. Fewest tools to satisfy goals.
```

**Weaknesses**:
- Rule 1 says "if + or ~, skip fetch" — so the 2 enriched companies get skipped (good) but the 20 with only stage+name also show `~` for stage, so they get partially skipped too. Nobody fetches basic info for the unknowns.
- Rule 2 says "fill missing data" but the fingerprint shows 20 companies with mostly `-` fields. The planner either tries to enrich all 20 (too expensive, too many calls) or gives up and goes to memo.
- Rule 5 says "only include memo when EXPLICITLY asked" — but the goal extraction already added a memo goal. These two prompts fight each other.
- Rule 7 "minimal plan" pushes toward skipping unknowns entirely.
- **Missing**: No concept of "lightweight discovery" — the tool catalog has `lightweight_diligence` but the prompt never suggests using it for bulk portfolio understanding.

### Prompt 3: REASON / Route (`unified_mcp_orchestrator.py:8265`)

```
RULES:
1. Look at State — what data exists? What's missing for the user's request?
2. Pick tool(s) to close the gap. Prerequisites auto-resolve.
3. Run independent calls in parallel. Never say "no data" — use tools to get it.
4. NEVER repeat a tool call that already ran.
5. After data tools finish, ALWAYS write results somewhere persistent.
6. Charts go in the memo, not the chat.
7. You are done when: data is fetched AND written to memo AND grid values updated.
```

**Weaknesses**:
- **Entire framing is "find gaps → fill gaps → persist."** There's no instruction to think, analyze, or synthesize. The agent is a data plumber, not an analyst.
- Rule 3 "never say no data — use tools to get it" sounds right but means the agent always tries to fetch before it thinks. For portfolio-level questions, it should think first with what it has.
- Rule 7 "done when data fetched + memo written + grid updated" — three gates, all data-centric. No gate for "did you actually answer the user's question?"
- **Skip guidance** (`session_state.py:company_needs`) says "these already have data — skip fetch." But it only checks if core fields are populated, not whether the companies are actually understood.
- **No concept of portfolio-level analysis tools.** The route prompt lists tools but doesn't guide the agent toward `run_portfolio_health`, `portfolio_comparison`, or `calculate_fund_metrics` for portfolio queries.

### Prompt 4: Narrative Generation (`lightweight_memo_service.py:181`)

```
System: You are a senior investment analyst...
Quality requirements:
1. Each section MUST be 3-5 dense paragraphs (150-400 words)
4. Cite every key figure with source
6. Only use numbers from the provided data — never invent figures
7. For multi-company: always compare and contrast — never describe in isolation
...
Each paragraph should contain at least one concrete data point.
```

**Weaknesses**:
- **Line 192 contradicts the estimation logic**: `generate()` injects stage benchmarks with `_revenue_estimated: True`, then the prompt says "never invent figures." The LLM sees estimated data and a rule saying don't use it. Result: writes about 2 companies, produces empty sections for the rest.
- **"3-5 dense paragraphs per section"** is the right ask for a 3-company IC memo. For a 22-company portfolio overview, the right format is a structured table with brief commentary — not 60 paragraphs of thin analysis.
- **"Each paragraph should contain at least one concrete data point"** — when 20 companies have only stage + name, the LLM can't satisfy this rule, so it skips them entirely.
- **No guidance on what to do when data is sparse.** The prompt should say: "When data is limited, use tables to show ALL companies with whatever exists. Flag gaps explicitly. Analyze patterns across the portfolio (sector concentration, stage distribution, funding timeline) that don't need per-company financials."

### Data Summary (`lightweight_memo_service.py:960`)

**Weakness**: `_summarize_data()` builds ~500-1000 char narrative blocks per company. 22 companies × 700 chars = 15K for companies alone, well within the 42K budget. BUT the `_summarize_company` method (line 821) can produce 1500+ chars for enriched companies with exit scenarios, comparables, and sources. The 2 enriched companies eat 3K+ chars each, then the budget runs tighter for the rest.

More importantly: even when all 22 companies fit, the format is wrong. The LLM gets 22 narrative blocks and tries to weave them into prose. For portfolio analysis, the LLM needs a **table** it can reference — not 22 paragraphs to mentally compare.

### Assembly (`lightweight_memo_service.py:341`)

```python
# Strip blank sections entirely — remove the heading we just added
if memo_sections and memo_sections[-1].get("type") == "heading2":
    memo_sections.pop()
```

**Weakness**: Empty narratives → heading gets nuked → 12-section template becomes 3-section stub. The user sees a "dump" because most sections were stripped.

### Output Formatting

The PDF renders structured tables well — the `_parse_markdown_to_sections` parser correctly converts markdown tables into `{type: "table", headers, rows}` dicts. But:
- The LLM doesn't produce enough tables because the prompt pushes for "flowing prose"
- When it does produce tables, they only cover the 2 data-rich companies
- The memo canvas (frontend) renders `paragraph` types as plain text blocks — walls of text instead of structured cards
- No visual hierarchy between real data and estimated data
- Charts that fail become dead placeholder text instead of being omitted cleanly

---

## Rewrite Plan

### Phase 1: Portfolio-Level Fast Path (eliminates wasted API calls)

**Goal**: When the user asks about the portfolio and companies are already loaded, skip the enrichment loop entirely. Go straight to analysis + memo.

**Changes**:

1. **`_run_agent_loop` — early exit for portfolio queries** (`unified_mcp_orchestrator.py:~7890`)
   - Before goal extraction, check: `classification.intent in PORTFOLIO_INTENTS and shared_data has companies`
   - If true, skip goal extraction + TaskPlanner + REASON loop
   - Call `_execute_memo_generation` directly with the portfolio data
   - Saves 3-5 LLM calls immediately

2. **`_execute_memo_generation` — lightweight enrichment for unknowns** (`unified_mcp_orchestrator.py:24654`)
   - After loading companies, identify which ones have only stage+name (no description, no revenue, no funding)
   - For those unknowns: run `lightweight_diligence` in parallel (1 web search each, batched)
   - Cap at 10 concurrent lookups, 15s total timeout
   - This gives the memo LLM something to work with for every company — at minimum "what they do"

3. **Skip redundant pre-memo steps** (`unified_mcp_orchestrator.py:24660-24691`)
   - `_enrich_companies` with `depth="benchmark"` is fine (CPU-only, fast)
   - `_run_portfolio_analysis` — keep, but timeout at 5s not 10s
   - `_hydrate_shared_data_from_companies` — keep (CPU-only)
   - `_populate_memo_service_data` — keep but make it skip keys that already exist in shared_data

### Phase 2: Narrative Prompt Rewrite (makes memos cover all companies)

**Goal**: The LLM should analyze the whole portfolio, not just the data-rich companies.

**Changes**:

1. **System prompt** (`lightweight_memo_service.py:181-207`) — rewrite:
   - Remove "Only use numbers from the provided data — never invent figures"
   - Replace with: "Use all provided data. Values from companies marked `[Est]` are stage-based benchmarks — include them but always label as `[Est: $XM]`. NEVER skip a company because its data is estimated."
   - Remove rigid "3-5 dense paragraphs per section" — replace with: "Use the format that best fits the data density. Tables for portfolio-wide comparisons. Prose for deep analysis of data-rich companies. Brief descriptions for companies with limited data."
   - Add: "When analyzing a portfolio, start with the big picture (themes, concentration, stage distribution, total deployed) before drilling into individual companies."
   - Add: "Each paragraph should contain at least one concrete data point" → change to: "Each section should contain concrete data points. When per-company data is sparse, analyze portfolio-level patterns instead."

2. **Data summary format** (`lightweight_memo_service.py:960`) — add a compact mode:
   - When company count > 8, switch to a markdown table format instead of per-company narrative blocks
   - Table columns: Company | Stage | Sector | ARR | Growth | Valuation | Funding | Data Quality
   - Estimated values tagged with `[Est]`
   - All companies fit in ~3-5K chars regardless of count
   - Keeps the detailed narrative format for ≤8 companies (IC memos, comparisons)

3. **Section assembly** (`lightweight_memo_service.py:341-345`) — stop stripping:
   - Instead of popping the heading when narrative is empty, keep the heading
   - Insert: "Analysis pending — limited data available for this section. Key data needed: {data_keys}."
   - Or better: build a mini-table for that section from whatever data exists

### Phase 3: Chart Resilience (charts work with estimated data)

**Goal**: Charts render for the full portfolio, visually distinguishing real vs estimated.

**Changes**:

1. **`_suggest_chart_type`** (`lightweight_memo_service.py:1078`) — lower thresholds:
   - Scatter needs 3+ with revenue → change to 3+ with revenue OR estimated revenue
   - The estimation logic already injected `c["revenue"]` for all companies — the chart code just needs to trust it

2. **`_build_chart`** (`lightweight_memo_service.py:1169`) — pass estimation metadata:
   - When building chart data arrays, include `estimated: true` flag per data point
   - Frontend can render estimated values with different opacity/color
   - Fall back to a simpler chart type (bar instead of scatter) when mostly estimated

3. **CDS methods** — audit each for unnecessary data guards:
   - `generate_revenue_multiple_scatter`: likely rejects companies where revenue is injected estimate
   - `generate_probability_cloud`: needs valuation — estimates should be accepted
   - `generate_bar_comparison`: should work with any numeric data

### Phase 4: Output Formatting (structured, not a dump)

**Goal**: Memo output is well-structured, renders well in both canvas and PDF.

**Changes**:

1. **Portfolio overview table** — always generated deterministically (no LLM) as first section:
   - Built from `shared_data.companies` after estimation
   - Columns adapt to what data exists (don't show empty columns)
   - Real values bold, estimated values in lighter text with `[Est]`
   - This becomes the structural backbone — even if narratives fail, the user gets a complete portfolio view

2. **Section type awareness** — teach `assemble_memo` about data density:
   - If a section's data_keys yield >8 companies with data: use table format
   - If ≤3 companies with deep data: use prose
   - If a mix: table first, then prose commentary on standout companies

3. **Markdown to sections parser** (`_parse_markdown_to_sections`) — already works well for tables. The fix is upstream: get the LLM to produce more tables by telling it to.

4. **Empty section handling** — instead of placeholder text, generate a compact data card:
   ```
   ## Financial Overview
   | Company | ARR | Growth | Burn | Runway |
   | Arcee AI | $14.8M | 150% | $500K/mo | 24mo |
   | BeZero | $21M | 80% | $1.2M/mo | 18mo |
   | [20 others] | [Est] | [Est] | — | — |

   *Detailed financials available for 2 of 22 companies. Run enrichment to fill gaps.*
   ```

### Phase 5: Suggestion Pipeline Fix (grid suggestions actually appear)

**Goal**: When the system says "18 values added as suggestions," they should actually show up.

**Investigation needed**:
- Trace `nl-matrix-controller` / `suggest_grid_edit` output → frontend event path
- Check if suggestions are pushed to the correct grid columns/rows
- Check if the frontend grid component is listening for suggestion events
- May be a column name mismatch (backend uses "revenue", grid uses "ARR")

---

## API Call Budget

| Scenario | Current | Target | How |
|----------|---------|--------|-----|
| Portfolio query (companies loaded) | 18+ | 3-4 | Skip goal extraction + TaskPlanner. 1 call for lightweight diligence batch, 1 for narratives, 1 for portfolio analysis |
| Portfolio query (no companies) | 20+ | 6-8 | 1 query_portfolio + 1 lightweight batch + 1 narratives + 1 portfolio analysis |
| Per-company deep dive | 8-12 | 6-8 | Keep enrichment chain, skip redundant re-fetches |
| Follow-up / polish | 3-5 | 1 | Direct to polish method, no loop |

---

## File Map

| File | What to change |
|------|---------------|
| `unified_mcp_orchestrator.py:7878` | Portfolio fast-path before goal extraction |
| `unified_mcp_orchestrator.py:24640` | Lightweight diligence for unknowns in memo pre-flight |
| `unified_mcp_orchestrator.py:8265` | Route prompt — add portfolio-level analysis guidance |
| `session_state.py:1158` | TaskPlanner decomposition — add portfolio patterns |
| `lightweight_memo_service.py:181` | Narrative system prompt — rewrite for sparse data |
| `lightweight_memo_service.py:960` | Data summary — compact table mode for large portfolios |
| `lightweight_memo_service.py:341` | Assembly — stop stripping empty sections |
| `lightweight_memo_service.py:1078` | Chart selection — lower data thresholds |
| `lightweight_memo_service.py:1169` | Chart building — pass estimation metadata |
| `memo_templates.py` | Review section data_keys for portfolio templates |

## Order of Implementation

1. **Narrative prompt rewrite** (Phase 2.1) — highest ROI, smallest change. Fix the contradiction, let the LLM use what it has.
2. **Portfolio fast-path** (Phase 1.1) — cut API calls from 18 to 3-4.
3. **Compact data summary** (Phase 2.2) — LLM sees all companies.
4. **Stop stripping sections** (Phase 2.3) — memo keeps structure.
5. **Output formatting** (Phase 4) — tables, not dumps.
6. **Chart resilience** (Phase 3) — charts render with estimates.
7. **Lightweight diligence for unknowns** (Phase 1.2) — the system actually learns about the portfolio.
8. **Suggestion pipeline** (Phase 5) — investigate and fix.
