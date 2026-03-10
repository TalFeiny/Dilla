# Agent Loop Redesign: Workers, Not Narrators

## The Core Problem

Our agents don't feel like workers. They feel like report generators.

Every message triggers the same pipeline: classify intent → run tools → synthesize a memo → return a wall of text. "What's our burn?" takes 15 seconds and produces a 4-section markdown document nobody asked for. The agent doesn't _do_ things — it _describes_ things.

Real agent loops (Claude Code, Cursor, Devin) work differently:
- Quick question → quick answer (sub-second)
- Explicit task → plan, execute in small steps, iterate
- Never a 30-second workflow for a one-liner

Our agent is the opposite: every message is a workflow call.

---

## What's Actually Broken

### 1. The agent can't write to the grid

`suggest_grid_edit` is a single-cell tool: `{company, column, value, reasoning}`. It's only in 4 of 16 intents (enrichment, grid_edit, sourcing, and a couple of workflow aliases). It's not in: **portfolio, kpi, strategy, forecast, general, company_lookup, valuation, scenario, comparison, memo, deck, market, fx**.

So when the CFO agent runs a forecast or the sourcing agent finds companies, they literally can't push results to the grid. The tool isn't visible to them.

There's also no bulk write. If the agent computes 24 months of revenue forecast across 5 line items, it would need to call `suggest_grid_edit` 120 times. One cell at a time. With accept/reject for each.

### 2. Upload → Grid is broken

CSV upload goes to `fpa_actuals` table via `actuals_ingestion.py`. The portfolio grid reads from a completely different data model (`matrix_context`, `gridSnapshot`). These are two separate worlds:

- **FPA world**: `fpa_actuals`, `fpa_forecasts`, `fpa_forecast_lines` — time-series financial data
- **Grid world**: `pending_suggestions`, `gridSnapshot` — flat key-value cells per company

The agent can write to FPA tables but can't get that data into the grid. The grid can show suggestions but doesn't read from FPA tables. There's no bridge.

### 3. Every message triggers the full pipeline

The orchestrator's `process_request_stream` always:
1. Classifies intent (LLM call, ~2s)
2. Builds a plan (LLM call, ~2s)
3. Runs tools in a loop (3-10s per tool)
4. Synthesizes results into prose (LLM call, ~3s)
5. Optionally generates a full memo (LLM call, ~5s)

Minimum response time: ~10 seconds. For "what's our burn?" when the data is already in `shared_data`.

### 4. The synthesis prompt is one-size-fits-all

```
"You are a senior analyst at a venture fund. Write a structured analysis
with ## markdown headings for each section."
```

This is the synthesis system prompt regardless of:
- Whether the user asked a yes/no question
- Whether the agent is in CFO mode vs portfolio mode
- Whether a memo was already generated
- Whether the user just wants a number

### 5. Nine services built, zero wired in

The plan in `FPA_PIPELINE_FIX_PLAN.md` called for 9 new tools. The service files all exist:
- `forecast_persistence_service.py` ✓
- `forecast_method_router.py` ✓
- `forecast_explainer.py` ✓
- `computed_metrics.py` ✓
- Migration file ✓

**Zero of these are callable from the agent.** None are registered as tools in the orchestrator. The persistence layer exists but the agent has no tool to call it.

---

## How Agent Loops Actually Work

Think about how Claude Code works:

```
User: "what does this function do?"
Agent: [reads file] → "It computes the trailing growth rate from actuals."
       (1 tool call, <1s thinking, short answer)

User: "refactor it to handle edge cases"
Agent: [reads file] → [plans changes] → [edits file] → [runs tests]
       (4 tool calls, iterates until tests pass)

User: "now do the same for the other 5 functions in this file"
Agent: [reads file] → [edits 5 functions] → [runs tests] → [fixes failures]
       (big task, runs a loop, adjusts as it goes)
```

The pattern:
1. **Quick replies** for informational questions — no pipeline, just answer
2. **Small tool calls** for direct actions — read, write, check
3. **Task loops** only when explicitly given a multi-step task
4. **Iteration** — do something, check result, adjust, repeat

Our agent does #3 for everything. There's no #1 or #2.

---

## What the Agent Loop Should Be

### Response Modes

The agent should have three modes, selected **before** any tool calls:

| Mode | Trigger | Behavior | Target Time |
|------|---------|----------|-------------|
| **Reply** | Question, greeting, clarification, status check | Answer from context/memory. Zero or one tool call max. No memo. | <2s |
| **Action** | Direct command: "update X", "write Y", "add Z" | Execute the action. Bulk write to grid. Short confirmation. | 2-5s |
| **Task** | Complex request: "forecast revenue", "build a model", "analyze the portfolio" | Plan → execute loop → synthesize. Memo only if appropriate. | 10-30s |

The mode selection should be a single fast classifier — not the current intent taxonomy with 16+ categories that all funnel into the same pipeline.

### Reply Mode (the missing mode)

90% of chat messages should be Reply mode. The agent should:
- Check `shared_data` / `session_memo` for the answer
- If found → respond immediately, no tools
- If not found → one tool call (usually `query_portfolio`), then respond
- Never generate a memo
- Never trigger synthesis pipeline
- Response format: 1-3 sentences, maybe a number

Examples:
- "What's our burn?" → "$420K/mo net burn, 14 months runway" (from session_memo)
- "How many companies?" → "32 companies in the portfolio" (from matrix_context)
- "What did you just do?" → "I ran a 24-month forecast for Acme using growth-rate method" (from session_memo)

### Action Mode (bulk grid writes)

When the user says "write this to the grid" or "update the forecast" or the agent needs to persist results, it should bulk-write. Not 120 individual `suggest_grid_edit` calls.

**New tool: `bulk_grid_write`**

```python
AgentTool(
    name="bulk_grid_write",
    description="Write multiple values to the grid in one operation. Supports portfolio grid cells and FPA grid cells.",
    handler="_tool_bulk_grid_write",
    input_schema={
        "edits": "list[dict]",  # [{company, column, value, reasoning}, ...]
        "target": "str?",       # "portfolio" | "fpa" — defaults to "portfolio"
        "auto_apply": "bool?",  # skip accept/reject, write directly
    },
)
```

This tool should:
1. Accept a list of edits (not one at a time)
2. Persist all of them in a single DB operation
3. Return a count + summary, not 120 individual confirmations
4. Support both portfolio grid (company × column) and FPA grid (period × category)

**New tool: `write_forecast_to_grid`**

```python
AgentTool(
    name="write_forecast_to_grid",
    description="Persist current forecast results to the FPA grid. Writes all forecast lines to fpa_actuals with source='forecast_applied'.",
    handler="_tool_write_forecast_to_grid",
    input_schema={
        "company_id": "str",
        "forecast_id": "str?",  # if omitted, uses latest from shared_data
        "source_tag": "str?",   # default: "forecast_applied"
    },
)
```

This is the bridge between the FPA world and the grid. The agent runs a forecast → calls this tool → forecast appears in the P&L grid.

### Task Mode (the existing loop, but smarter)

Keep the current agent loop for genuine multi-step tasks, but fix:

1. **Don't force memos.** The current system prompt says "every request produces a memo". Most requests shouldn't. Only generate a memo when:
   - User explicitly asks for one ("write me an IC memo", "generate an LP report")
   - The analysis is genuinely complex enough to warrant a document (multi-company comparison, full due diligence)
   - The output format is "docs" or "deck"

2. **Don't dump synthesis into chat when a memo exists.** If `detected_format == "docs"` and `memo_sections` exist, the chat content should be a 1-2 sentence pointer: "I've generated a 12-section analysis of the portfolio. Key finding: 4 companies have <6 months runway."

3. **Make synthesis context-aware.** The synthesis prompt should know:
   - Which agent personality is active (CFO vs portfolio vs sourcing)
   - What the user actually asked (question vs command vs analysis request)
   - What format the output is in (don't describe the memo in prose if the memo is right there)

---

## INTENT_TOOLS Fix

`suggest_grid_edit` (and the new `bulk_grid_write`) should be available in ALL intents that produce data. The agent should always be able to write results back to the grid.

Add to these intents:
- `portfolio` — after analysis, write updated metrics back
- `kpi` — write computed KPIs to grid
- `strategy` — write strategic recommendations as actions
- `forecast` — write forecast to grid (via `write_forecast_to_grid`)
- `general` — fallback should include grid write
- `valuation` — write valuation results back
- `scenario` — write scenario results back
- `comparison` — write comparison metrics back
- `company_lookup` — write fetched data to grid (already happens via `_auto_suggest_grid_edits` but not reliably)

Also add `bulk_grid_write` and `write_forecast_to_grid` to the tool registry.

---

## CFO Mode Fix

When `system_prompt_override` contains "CFO", the agent should:

1. **Force-include FPA tools** regardless of classified intent: `fpa_forecast`, `fpa_pnl`, `fpa_actuals`, `fpa_kpi_dashboard`, `fpa_cash_flow`, `fpa_scenario_compare`, `write_forecast_to_grid`, `bulk_grid_write`
2. **Use CFO personality** in synthesis — not "senior analyst at a venture fund"
3. **Default to Reply mode** for simple questions about the company's financials
4. **Wire in the existing services** — `ForecastPersistenceService`, `ForecastMethodRouter`, `ForecastExplainer`, `ComputedMetrics` are all built. Register them as tools.

---

## Immediate Priorities (What to Build First)

Forget the 9-phase plan. Here's what actually unblocks the product:

### P0: Bulk grid write (1 day)
- New `bulk_grid_write` tool
- New `write_forecast_to_grid` tool
- Add both + `suggest_grid_edit` to all data-producing intents
- Wire `ForecastPersistenceService.write_forecast_to_actuals()` into `write_forecast_to_grid`

### P0: Response mode classifier (0.5 day)
- Before the agent loop starts, classify: reply / action / task
- Reply mode: skip tools, answer from context, <2s
- Action mode: execute, bulk write, confirm
- Task mode: existing agent loop

### P1: Wire existing services as tools (1 day)
- Register `ForecastPersistenceService` methods as MCP tools
- Register `ForecastMethodRouter.build_forecast` as `fpa_forecast` upgrade
- Register `ComputedMetrics.compute_all` as a tool
- These files exist and work — they just need tool wrappers

### P1: Fix synthesis (0.5 day)
- Context-aware synthesis prompt (know which agent, what was asked)
- Don't dump full analysis into chat when memo exists
- Reply mode gets no synthesis — just the answer

### P2: CFO mode awareness (0.5 day)
- Detect CFO mode in intent routing
- Force-include FPA + grid tools
- CFO personality in synthesis

---

## What We Stop Doing

1. **Stop writing plan docs.** We have 20+ docs in `/docs`. Most describe features that don't exist. Write code, not plans.
2. **Stop adding tools without wiring them.** 9 tools planned, 0 registered. If it's not in `INTENT_TOOLS`, the agent can't see it.
3. **Stop treating every message as a workflow.** Quick question = quick answer. The memo pipeline is for memos, not for "what's our burn?"
4. **Stop single-cell grid writes.** Bulk or nothing. The agent should write 100 cells in one call, not fire `suggest_grid_edit` in a loop.
