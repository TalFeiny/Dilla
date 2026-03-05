elin
# P&L Page — What's Built vs What's Missing

## The Problem

The PnL mode is a non-functional shell. The backend is fully built (PnlBuilder, fpa_actuals table, 18 CFO agent tools, Xero sync). The frontend PnL mode was scaffolded as a copy of portfolio mode and never given its own data pipeline.

Core issue: **the services exist but nothing populates the grid or memo.**

---

## Architecture: How Data Should Flow

```
                         ┌──────────────┐
  CSV Upload ──────────► │              │
  Xero Sync ───────────► │  fpa_actuals │ (Supabase table)
  Manual Cell Edit ────► │              │
                         └──────┬───────┘
                                │
                    PnlBuilder.build()
                    (backend/app/services/pnl_builder.py)
                                │
                    ┌───────────▼────────────┐
                    │  GET /api/fpa/pnl      │
                    │  {periods, rows,       │
                    │   forecastStartIndex}  │
                    └───────────┬────────────┘
                                │
              ┌─────────────────┼─────────────────┐
              ▼                 ▼                  ▼
         ┌─────────┐    ┌────────────┐    ┌──────────────┐
         │  Grid   │    │   Memo     │    │  Suggestions │
         │ (direct │    │ (narrative │    │  (proposed   │
         │  render)│    │  + charts) │    │  cell edits) │
         └─────────┘    └────────────┘    └──────────────┘
```

**Agent tool results → memo** (primary: narrative, analysis, recommendations)
**Agent tool results → suggestions** (secondary: proposed cell updates via `addServiceSuggestion`)
**User accepts suggestion → grid cell upsert** (via existing suggestions pipeline)

The suggestions system is fully built:
- `SuggestionsContext.tsx` — React context for suggestions state
- `DocumentSuggestions.tsx` — UI for accept/reject badges per cell
- `suggestion-helpers.ts` — `addServiceSuggestion()`, `acceptSuggestionViaApi()`, `rejectSuggestion()`
- `POST /api/matrix/suggestions` — backend persistence
- `UnifiedMatrix.tsx:2177` — already calls `addServiceSuggestion` for service results

The memo system is fully built:
- `AgentPanel.tsx:onMemoUpdates` — callback from agent response
- `AgentChat.tsx:856` — forwards `memo_updates` sections from backend response
- `AgentChat.tsx:1065` — auto-generates memo sections from rich content when backend doesn't
- Backend returns `memo_updates: { action: 'append'|'replace', sections: [...] }`

**Neither is wired for PnL mode.**

---

## What's Built (Backend)

| Component | File | What It Does |
|-----------|------|-------------|
| `fpa_actuals` table | `supabase/migrations/20260303_add_fpa_actuals.sql` | Time-series: `(company_id, period, category, subcategory, amount, source)` |
| `PnlBuilder` | `backend/app/services/pnl_builder.py` | Reads fpa_actuals → derives ratios → projects forecast → assembles hierarchical rows |
| `GET /api/fpa/pnl` | `backend/app/api/endpoints/fpa_query.py:79` | Returns `{periods, forecastStartIndex, rows}` — requires `company_id` |
| `fpa_pnl` tool | `unified_mcp_orchestrator.py:1432` → `_tool_fpa_pnl:7148` | Calls PnlBuilder, stores in `shared_data["fpa_pnl_result"]` |
| `fpa_upload_actuals` tool | `unified_mcp_orchestrator.py:1534` | Ingests `[{period, revenue, cogs, ...}]` into fpa_actuals |
| `fpa_actuals` tool | `unified_mcp_orchestrator.py:1518` | Fetches structured actuals for a company |
| `fpa_variance` tool | `unified_mcp_orchestrator.py:1440` | Budget vs actuals comparison |
| `fpa_forecast` tool | `unified_mcp_orchestrator.py:1448` | Generate forecast from actuals |
| `fpa_cash_flow` tool | `unified_mcp_orchestrator.py:1456` | Monthly cash flow model → EBITDA → FCF → runway |
| `fpa_xero_sync` tool | `unified_mcp_orchestrator.py:1566` | Pulls P&L from Xero → fpa_actuals |
| Xero OAuth2 | `backend/app/services/xero_service.py` | Full OAuth flow, token management, data mapping |
| PnL section config | `pnl_builder.py:20-47` | `SECTION_ORDER`, `CATEGORY_SECTION`, `CATEGORY_LABELS` — defines waterfall structure |

---

## What's Broken (Frontend) — Code-Level

### 1. Empty grid — no skeleton

**Files:**
- `UnifiedMatrix.tsx:333-340` — default PnL state
- `AGGridMatrix.tsx:141-143` — `DEFAULT_PNL_COLUMNS`

**Current code:**
```ts
// UnifiedMatrix.tsx:333
} else if (mode === 'pnl') {
  return {
    columns: [{ id: 'lineItem', name: 'Line Item', type: 'text', width: 220, editable: false }],
    rows: [],
    metadata: { dataSource: 'pnl', lastUpdated: new Date().toISOString() },
  };
}

// AGGridMatrix.tsx:141
const DEFAULT_PNL_COLUMNS: MatrixColumn[] = [
  { id: 'lineItem', name: 'Line Item', type: 'text', width: 220, editable: false },
];
```

**Fix:** Both need 12 month columns + the standard income statement row skeleton from `pnl_builder.py:SECTION_ORDER`. Match the backend's structure: Revenue, COGS, Gross Profit, OpEx, EBITDA, D&A, Interest, EBT, Tax, Net Income — with `depth`, `isHeader`, `isTotal`, `isComputed` metadata so `PnLLineItemRenderer` renders correctly. All cell values `null` / `'—'`.

### 2. No company_id — PnL calls the wrong entity

**Files:**
- `matrix-api-service.ts:1083` — `fetchPnlForMatrix(fundId?, companyId?)`
- `UnifiedMatrix.tsx:1389` — `fetchPnlForMatrix(fundId)` — **never passes companyId**
- `backend/app/api/endpoints/fpa_query.py:94` — returns empty if no company_id

**Current code:**
```ts
// UnifiedMatrix.tsx:1389
const pnlData = await fetchPnlForMatrix(fundId);  // no companyId!
```

```python
# fpa_query.py:94
if not company_id:
    return {"periods": [], "forecastStartIndex": 0, "rows": []}
```

**Fix:** PnL mode needs a company selector in `matrix-control-panel/page.tsx`. When user selects company, pass `companyId` through to `UnifiedMatrix` → `loadPnlData()` → `fetchPnlForMatrix(fundId, companyId)`. The company list can come from the existing fund's portfolio companies.

### 3. No CSV upload for PnL

**Existing infrastructure to reuse:**
- `onUploadDocumentToCell` in AGGridMatrix — handles file drop per cell (portfolio mode)
- `csv-field-mapper.ts` imported in `UnifiedMatrix.tsx:128` — already has CSV mapping logic
- Backend `fpa_upload_actuals` tool accepts `{company_id, time_series: [{period, revenue, cogs, ...}]}`

**What's missing:**
- No upload button in PnL toolbar
- No CSV → fpa_actuals category mapping
- No frontend route to `fpa_upload_actuals`

**Fix:** Add "Upload CSV" button to PnL mode toolbar. Flow:
1. File picker → papaparse (already in deps or add) → parse rows
2. Map CSV columns to fpa_actuals categories using `pnl_builder.py:CATEGORY_SECTION` as the schema
3. POST to new frontend API route `/api/fpa/upload-actuals` → backend `fpa_upload_actuals`
4. On success, call `loadPnlData()` to refresh grid
5. Agent can also trigger this — user drops CSV in chat, agent calls `fpa_upload_actuals`

### 4. Add Row hits companies table

**Current:** No PnL-specific Add Row. Falls through to portfolio's handler → INSERT into `companies` → `funnel_status` constraint error.

**Fix:** In `UnifiedMatrix.tsx`, when `mode === 'pnl'`, Add Row should:
1. Open a small form: category dropdown (from `CATEGORY_LABELS`), subcategory text input
2. INSERT into `fpa_actuals` (company_id, period=null initially, category, subcategory, amount=0)
3. Reload grid

Or simpler: disable Add Row in PnL mode. The skeleton rows are the template. Data comes in via CSV/Xero/agent, not manual row creation.

### 5. No Xero sync in PnL toolbar

**Existing infrastructure:**
- `backend/app/services/xero_service.py` — full sync service
- `fpa_xero_sync` tool — `{company_id, months?}` → pulls actuals
- `frontend/src/app/settings/integrations/page.tsx` — Xero connect button (OAuth)

**What's missing:**
- No "Sync from Xero" button in PnL mode
- No way to trigger sync for selected company from the grid

**Fix:** Add "Import from Xero" button in PnL toolbar (only visible when Xero is connected). Calls `POST /api/integrations/xero/sync` with `company_id`, then reloads grid.

### 6. Agent results don't populate grid or memo

**Existing infrastructure:**
- `addServiceSuggestion()` in `suggestion-helpers.ts:70` — writes proposed cell edits to `pending_suggestions`
- `SuggestionsProvider` wraps the grid — already renders accept/reject badges
- `onMemoUpdates` callback — already wired from AgentPanel → UnifiedMatrix
- `AgentChat.tsx:856` — already forwards `memo_updates` from backend

**What's missing:**
- When agent calls `fpa_pnl` → the grid should reload with the waterfall data
- When agent calls `fpa_variance` or `fpa_forecast` → results should:
  - Flow to **memo** as narrative (via existing `memo_updates`)
  - Flow to **suggestions** as proposed cell edits (via `addServiceSuggestion`)
- Backend FPA tools don't currently return `memo_updates` in their response format
- Frontend doesn't listen for FPA tool results to trigger grid refresh

**Fix — two parts:**

**A) Grid refresh on FPA tool results:**
When `AgentChat` receives a response where the agent called `fpa_pnl`, `fpa_upload_actuals`, or `fpa_xero_sync` → emit callback to `UnifiedMatrix` to call `loadPnlData()`. This reloads the grid from the backend (PnlBuilder re-reads fpa_actuals).

**B) Suggestions from FPA analysis tools:**
When agent calls `fpa_variance`, `fpa_forecast`, `fpa_cash_flow` → backend should return both:
1. `memo_updates` with narrative sections (already handled by AgentChat:856)
2. Proposed cell edits as structured data → frontend calls `addServiceSuggestion()` for each → appears in suggestions feed → user accepts → grid updates

This mirrors how document extraction already works: document → extract values → suggestions → accept → grid.

---

## User Flow (Target)

```
1. Switch to P&L mode → see empty income statement skeleton (12 months × standard rows)
2. Pick company from dropdown
3. Get data in:
   a. "Upload CSV" button → parse → write to fpa_actuals → grid reloads
   b. "Sync from Xero" button → pulls actuals → grid reloads
   c. Chat: "here's my P&L data" + drop CSV → agent calls fpa_upload_actuals → grid reloads
4. Grid shows actuals + forecast waterfall (PnlBuilder)
5. Ask agent questions:
   - "Show me variance vs budget" → memo shows analysis + suggestions appear on grid cells
   - "Forecast next 12 months" → forecast columns fill via suggestions → memo summarizes
   - "What's our runway?" → memo answers + cash flow data suggested to grid
6. User reviews suggestions → accept/reject → grid updates
7. Manual cell overrides as needed (saves to fpa_actuals)
```

## Priority

1. **Grid skeleton** — `UnifiedMatrix.tsx:333` + `AGGridMatrix.tsx:141` — show template when empty
2. **Company picker** — `matrix-control-panel/page.tsx` — PnL needs company_id
3. **Agent → memo** — backend FPA tools return `memo_updates` → already wired
4. **Agent → suggestions → grid** — FPA tool results → `addServiceSuggestion()` → accept → grid
5. **CSV upload** — toolbar button + parse + POST to `fpa_upload_actuals`
6. **Xero sync button** — toolbar button → `fpa_xero_sync` → reload grid
7. **Fix Add Row** — disable or redirect to fpa_actuals instead of companies
