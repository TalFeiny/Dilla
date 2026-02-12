# Implementation Summary: General-Purpose Portfolio CFO Agent

**Date**: 2026-02-11
**Sessions**: 2 (context compaction between sessions)

---

## What Was Built

Transformed the unified MCP orchestrator from a single-purpose dealflow scraper (`@Company` -> Tavily -> extraction -> valuation -> grid) into a general-purpose portfolio CFO agent with 13 tools, a ReAct reasoning loop, cost-tiered model routing, an inline memo editor, and ephemeral plan approval — all while keeping the existing dealflow pipeline untouched.

---

## Backend Changes

### 1. Tool Registry — 13 Tools Wrapping Existing Services

**File**: `backend/app/services/unified_mcp_orchestrator.py` (lines 399-503)

Added `AgentTool` dataclass and `AGENT_TOOLS` registry. Each tool is a thin adapter wrapping an existing backend service with metadata for the routing LLM:

| Tool | Wraps | Cost Tier |
|------|-------|-----------|
| `query_portfolio` | MatrixQueryOrchestrator | free |
| `query_documents` | DocumentQueryService | free |
| `calculate_fund_metrics` | FundModelingService | free |
| `run_valuation` | ValuationEngineService | cheap |
| `run_scenario` | ScenarioAnalyzer | cheap |
| `generate_chart` | ChartDataService | free |
| `web_search` | Tavily (existing) | cheap |
| `suggest_grid_edit` | Accept/reject flow | free |
| `suggest_action` | Insight/warning/action cards | free |
| `write_to_memo` | Returns sections to frontend | free |
| `fetch_company_data` | Existing dealflow pipeline | expensive |
| `run_fpa` | FPAExecutor | cheap |
| `parse_accounts` | LLM structured extraction | expensive |

Each tool has `name`, `description` (<=80 chars, shown to routing LLM), `handler` (method name), `input_schema`, `cost_tier`, and `timeout_ms`.

```python
AGENT_TOOL_MAP: dict[str, AgentTool] = {t.name: t for t in AGENT_TOOLS}  # line 503
```

### 2. Three-Way Complexity Gate

**File**: `unified_mcp_orchestrator.py` (line 1211)

Rule-based classifier — no LLM call, ~0ms:

```
_assess_complexity(prompt, context) -> "simple" | "dealflow" | "complex"
```

- **simple**: Regex-matched single-metric questions ("What's our DPI?", "How many companies?")
- **dealflow**: Has `@mentions` without complex keywords -> existing skill chain (unchanged)
- **complex**: Everything else -> ReAct agent loop

Wired into `process_request_stream` at line 1974:
- simple -> `_direct_dispatch()` (one tool call, no loop)
- complex -> `_run_agent_loop()` (ReAct)
- dealflow -> falls through to existing skill chain

### 3. Direct Dispatch for Simple Queries

**File**: `unified_mcp_orchestrator.py` (line 1255)

Pattern-matches simple queries to a single tool call without any LLM routing:
- Fund metric keywords -> `_tool_fund_metrics()`
- Portfolio listing keywords -> `_tool_query_portfolio()`
- Fallback -> `_single_shot_answer()` (one LLM call)

### 4. ReAct Agent Loop

**File**: `unified_mcp_orchestrator.py` (line 1684)

```
_run_agent_loop(prompt, context, memo_text="", max_iterations=6)
```

Each iteration:
1. **REASON** (cheap model, `ModelCapability.FAST`, <=300 tokens out): Pick next tool from catalog
2. **ACT** (Python service call, no LLM): Execute tool via `_execute_tool()` with retry/timeout
3. **REFLECT** (cheap model, `ModelCapability.FAST`, <=150 tokens out): Is data sufficient?
4. **SYNTHESIZE** (full model, `ModelCapability.ANALYSIS`, once): Generate final answer

Side effects collected during loop:
- `memo_sections` -> forwarded to frontend for MemoEditor append
- `grid_commands` -> forwarded for accept/reject flow
- `charts` -> rendered inline in chat
- `suggestions` -> action items, warnings, insights

**Cost per complex query**: ~$0.04 (3 cheap routing + 1 synthesis) vs ~$0.10+ previously

### 5. Tool Executor with Retry

**File**: `unified_mcp_orchestrator.py` (line 1321)

```python
_execute_tool(tool_name, tool_input, max_retries=2)
```

- Dispatches to handler method by name from `AGENT_TOOL_MAP`
- `asyncio.wait_for()` with per-tool timeout
- Exponential backoff with jitter for rate limits (429s)
- Returns `{"error": "..."}` on failure (routing LLM can react)

### 6. Lightweight Plan Mode

**File**: `unified_mcp_orchestrator.py` (lines 1610-1670)

For expensive/destructive operations ("stress test all", "revalue entire", "lp report"):
- `_needs_plan()` (line 1610): Rule-based check
- `_generate_cheap_plan()` (line 1618): Fast model generates 3-6 step plan (<=200 tokens)
- Returns `awaiting_approval: true` -> frontend shows PlanApprovalCard

### 7. Feedback Correction Loop

**File**: `unified_mcp_orchestrator.py` (line 1587)

```python
_get_recent_corrections(prompt, company=None) -> list[str]
```

Reads from `agent_corrections` Supabase table. Injected into synthesis prompt:
```
User has previously corrected: [correction1]; [correction2]
Adjust your response accordingly.
```

Closes the loop: user thumbs-down -> stored -> next query reads corrections -> agent adjusts.

### 8. Budget Enforcement

**File**: `unified_mcp_orchestrator.py` (line 1717, inside agent loop)

At the top of each iteration:
- Check `budget.exhausted` -> break loop
- Check `budget.warn_if_expensive()` -> log warning at >60% consumed

**File**: `backend/app/services/model_router.py` (lines 50-95)

Added `IterationCost` dataclass and extended `RequestBudget`:
- `iterations: List[IterationCost]` for per-iteration tracking
- `warn_if_expensive(caller)` returns warning string at >60% budget
- Budget: $2.00 max, 500k tokens per request

### 9. Revenue Multiples Scatter Chart

**File**: `backend/app/services/chart_data_service.py` (line 615)

```python
def generate_revenue_multiples_scatter(grid_snapshot) -> dict
```

- X = ARR ($M), Y = Valuation/ARR multiple, dot size = total funding
- Stage-based coloring: seed=#94a3b8, series_a=#3b82f6, series_b=#8b5cf6, etc.
- Grouped by funding stage into separate Chart.js datasets
- Works from grid snapshots (matrix rows), not company data arrays

### 10. Memo Context Injection

**File**: `unified_mcp_orchestrator.py` (lines 1841, 1985-1988)

- Memo sections extracted from `shared_data.agent_context.memo_sections`
- Text joined and truncated to 2000 chars
- Injected into synthesis prompt as "Working memo context"
- Enables continuity: memo content influences agent responses

---

## Frontend Changes

### 11. MemoEditor Component

**New file**: `frontend/src/components/memo/MemoEditor.tsx` (303 lines)

Full rich-text editor supporting 10 section types:

| Section Type | Rendering |
|-------------|-----------|
| heading1-3 | contentEditable headings with size scaling |
| paragraph | contentEditable paragraph with relaxed leading |
| chart | TableauLevelCharts embedded in document flow (16:9, responsive) |
| list | contentEditable bullet list items |
| quote | Styled blockquote with left border |
| code | Monospace pre/code block |
| table | Headers + rows with currency/percentage/number formatting |
| image | img with caption |

Features:
- Toolbar: Add heading, paragraph, list, chart, table + PDF export button
- Compact mode for embedded use (smaller fonts, tighter spacing)
- Inline citations (source/document/reasoning) per section
- Delete button on hover per section
- `DocumentSection` interface exported for type sharing

### 12. Memo Tab in ChartViewport

**File**: `frontend/src/components/matrix/ChartViewport.tsx` (lines 336-430)

- Extended `ChartTab` type: `'charts' | 'insights' | 'memo'`
- Added MemoEditor import and memo props to interface
- Third tab with FileText icon renders MemoEditor in compact mode
- Props: `memoSections`, `onMemoChange`, `onMemoExportPdf`, `memoExportingPdf`

### 13. Memo State in UnifiedMatrix

**File**: `frontend/src/components/matrix/UnifiedMatrix.tsx` (line 373)

```typescript
const [memoSections, setMemoSections] = useState<DocumentSection[]>([
  { type: 'heading1', content: 'Working Memo' },
  { type: 'paragraph', content: '' },
]);
```

- Passed to ChartViewport (standalone path)
- Passed to AgentPanel with `onMemoUpdates` callback that handles append/replace

### 14. Memo PDF Export

**New file**: `frontend/src/app/api/memos/export/route.ts` (49 lines)

POST handler that:
1. Converts memo sections to slides format
2. Proxies to backend `/api/export/deck` with `theme: 'memo'`
3. Streams PDF back with Content-Disposition header

### 15. AgentPanel Memo Prop Chain

**File**: `frontend/src/components/matrix/AgentPanel.tsx` (lines 75-77, 103, 130-131)

Added to `AgentPanelProps`:
- `memoSections?: Array<{ type: string; content?: string }>`
- `onMemoUpdates?: (updates: { action: string; sections: ... }) => void`

Destructured in component, forwarded to AgentChat.

### 16. AgentChat — Enriched Message Handling

**File**: `frontend/src/components/agent/AgentChat.tsx`

#### New Message Interface Fields (lines 101-105)
```typescript
planSteps?: Array<{ id: string; label: string; status: 'pending'|'running'|'done'|'failed'; tool?: string }>;
awaitingApproval?: boolean;
agentSuggestions?: Array<{ type: 'warning'|'action_item'|'insight'; title: string; description: string }>;
```

#### Props Added (lines 150-153)
- `onMemoUpdates` — callback when agent returns memo_updates
- `memoSections` — current memo for context forwarding

#### Context Forwarding (lines 565-566)
Sends `memo_sections` (last 15) and `memo_title` in agent_context with every request.

#### Response Parsing (lines 637-649)
Extracts from backend response:
- `messagePlanSteps` — plan steps for inline rendering
- `isAwaitingApproval` — triggers PlanApprovalCard
- `agentSuggestions` — action items, warnings, insights

#### Memo Updates Forwarding (lines 632-636)
```typescript
const memoUpdates = result.memo_updates ?? data.memo_updates;
if (memoUpdates?.sections?.length && onMemoUpdates) {
  onMemoUpdates(memoUpdates);
}
```

### 17. Inline Plan Steps Progress (line 1301)

Renders in assistant message bubbles:
- Pending: empty circle
- Running: spinning Loader2 (blue)
- Done: Check (green)
- Failed: X (red)
- Tool badge next to each step

### 18. PlanApprovalCard (line 1317)

Inline card with:
- Numbered step list with tool badges
- "Ephemeral — copy to memo to save" label
- **Execute** button: re-sends original prompt (marks plan as approved)
- **Dismiss** button: hides the card

### 19. Agent Suggestion Cards (line 1361)

Inline in message bubbles, 3 types:
- **warning**: amber background, AlertTriangle icon
- **action_item**: blue background, Target icon
- **insight**: gray background, Lightbulb icon

Each shows title + description.

### 20. Rich Citations — 3 Types (line 1398)

Replaced flat citation list with color-coded pills:
- **source** (blue pill): clickable link to URL
- **document** (green pill): uploaded doc reference
- **reasoning** (amber pill): shows tooltip with agent's reasoning

### 21. Unified Brain Route — Context Forwarding

**File**: `frontend/src/app/api/agent/unified-brain/route.ts` (lines 146-150)

Forwards to backend:
- `agent_context.memo_sections` — memo content for context
- `agent_context.memo_title` — memo title
- `approved_plan` — when user clicks Execute on PlanApprovalCard

---

## Architecture Diagram

```
User Query
    │
    ▼
_assess_complexity() ──── "simple" ──→ _direct_dispatch() ──→ Single tool call ──→ Response
    │                                                          (no LLM routing)
    ├──── "dealflow" (@mentions) ──→ Existing skill chain (unchanged)
    │
    └──── "complex" ──→ _run_agent_loop()
                              │
                              ├── REASON (cheap model, ~300 tok)
                              │     └── Pick tool from 13-tool catalog
                              │
                              ├── ACT (Python, no LLM)
                              │     └── _execute_tool() with retry/timeout
                              │
                              ├── REFLECT (cheap model, ~150 tok)
                              │     └── Sufficient? → break or continue
                              │
                              └── SYNTHESIZE (full model, once)
                                    └── memo_context + corrections + tool results
                                          │
                                          ▼
                                    EnrichedResponse {
                                      content, charts, grid_commands,
                                      suggestions, memo_updates,
                                      plan_steps, citations
                                    }
```

---

## Files Changed

| Action | File | Lines |
|--------|------|-------|
| MODIFY | `backend/app/services/unified_mcp_orchestrator.py` | +650 lines (tools, agent loop, complexity gate) |
| MODIFY | `backend/app/services/model_router.py` | +45 lines (IterationCost, warn_if_expensive) |
| MODIFY | `backend/app/services/chart_data_service.py` | +120 lines (revenue multiples scatter) |
| NEW | `frontend/src/components/memo/MemoEditor.tsx` | 303 lines |
| NEW | `frontend/src/app/api/memos/export/route.ts` | 49 lines |
| MODIFY | `frontend/src/components/matrix/ChartViewport.tsx` | +20 lines (memo tab) |
| MODIFY | `frontend/src/components/matrix/UnifiedMatrix.tsx` | +15 lines (memo state + wiring) |
| MODIFY | `frontend/src/components/matrix/AgentPanel.tsx` | +8 lines (memo prop forwarding) |
| MODIFY | `frontend/src/components/agent/AgentChat.tsx` | +120 lines (plan UI, suggestions, citations, memo) |
| MODIFY | `frontend/src/app/api/agent/unified-brain/route.ts` | +8 lines (context forwarding) |
| NEW | `docs/AGENT_ARCHITECTURE_REVIEW.md` | Code-level review doc |

---

## Design Decisions

| Decision | Rationale |
|----------|-----------|
| Memos are **stateless** (React state only, no DB) | User explicitly requested. Simpler, no sync bugs. |
| Plans are **ephemeral** (shown in chat, never persisted) | Avoids stale plans. User manually copies to memo for handoff. |
| Complexity gate is **rule-based** (no LLM) | ~0ms latency, $0 cost. Simple queries stay cheap. |
| Routing uses **cheap model** (ModelCapability.FAST) | 3 routing calls at ~$0.0001/1k tokens vs full model |
| Synthesis uses **full model** once | Quality matters for final answer, not for tool selection |
| Tool handlers are **thin adapters** | Wrap existing services, don't duplicate logic |
| Budget enforcement at **loop level** | Prevents runaway iterations from exceeding $2.00 |
| Feedback loop reads **corrections table** | Closes the loop: user correction -> stored -> next query reads back |

---

## Remaining Work (Lower Priority)

1. **Runtime verification**: Lazy imports for `MatrixQueryOrchestrator.query()`, `FPAExecutor.execute()`, `ScenarioAnalyzer.analyze()` need to be tested to confirm correct method signatures
2. **Grid snapshot validation**: Tools that read gridSnapshot should return clear errors when portfolio data unavailable
3. **Failed tool tracking in agent loop**: Prevent routing LLM from retrying same broken tool
4. **Feedback re-run on thumbs-down**: `handleFeedbackWithRerun` in AgentChat (plan specifies it but not yet implemented)
