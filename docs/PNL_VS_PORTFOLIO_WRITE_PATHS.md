# P&L Grid vs Portfolio Grid: Write Path Comparison

## Portfolio Grid — Works End-to-End

```
Agent ("update Acme's ARR to 5M")
  → bulk_write_grid tool
    → INSERT into pending_suggestions table (session-scoped)
      → Frontend shows accept/reject UI
        → User accepts → onCellEdit() → PATCH /api/portfolio/[id]/companies/[cid]
          → UPDATE companies table (persisted)

CSV Upload
  → POST /api/portfolio/[id]/import-csv
    → UPSERT directly into companies table (persisted)
      → loadPortfolioData() re-fetches grid → grid re-renders

User Cell Edit
  → onCellEdit() → PATCH /api/portfolio/[id]/companies/[cid]
    → UPDATE companies table (persisted)
```

**Key:** Portfolio has a suggestions queue (`pending_suggestions`). Agent proposes → user reviews → accepted edits persist to `companies` table. CSV bypasses the queue and writes directly. Grid reads from `companies` table.

---

## P&L Grid — Broken Chain

```
Agent ("set Q1 revenue to 500K")
  → fpa_cell_edit tool (NOW wired into INTENT_TOOLS, was missing before)
    → UPSERT directly into fpa_actuals table (persisted to DB)
      → ??? nobody tells the frontend to re-fetch
        → Grid shows stale data

  → OR agent falls back to bulk_write_grid (wrong tool)
    → INSERT into pending_suggestions (portfolio queue, wrong shape)
      → Frontend tries to apply as portfolio edit → fails silently
        → Data never reaches fpa_actuals

CSV Upload (P&L mode)
  → POST /api/fpa/upload-actuals
    → INSERT into fpa_actuals table (persisted)
      → handlePnlCsvUpload() calls loadPnlData() → grid re-renders ✓

CSV Upload (Portfolio mode with period columns)
  → POST /api/portfolio/[id]/import-csv
    → Also ingests into fpa_actuals (lines 441-557 of route.ts)
      → Only calls loadPortfolioData() → P&L grid never re-fetches ✗

User Cell Edit (P&L)
  → No dedicated P&L cell edit handler in frontend
    → onCellEdit routes through portfolio path → wrong table
```

**Key:** P&L has NO suggestions queue. FPA tools write directly to `fpa_actuals` (no review step). The grid reads from `fpa_actuals` via `fetchPnlView()` → `/api/fpa/pnl` → `PnlBuilder`. But there's no mechanism to trigger a re-fetch after agent writes, and no accept/reject flow.

---

## The Gaps

| Capability | Portfolio Grid | P&L Grid |
|---|---|---|
| Agent writes to correct table | ✅ `pending_suggestions` → `companies` | ⚠️ `fpa_actuals` (direct, no review) |
| Suggestions queue (accept/reject) | ✅ `pending_suggestions` | ❌ None — writes go straight to DB |
| Grid refreshes after agent write | ✅ `handleGridCommandsFromBackend` | ❌ No refresh signal |
| Grid refreshes after CSV upload | ✅ `loadPortfolioData()` | ⚠️ Only in P&L upload mode, not portfolio mode |
| User can edit cells in grid | ✅ `onCellEdit` → companies table | ❌ No P&L cell edit in frontend |
| Data persists across sessions | ✅ `companies` table | ✅ `fpa_actuals` table (if it gets written) |

---

## What Needs to Happen

### Option A: Direct Write + Refresh (Simpler)
FPA tools write directly to `fpa_actuals` (they already do), and we add a refresh signal so the grid re-fetches. No suggestions queue.

- Pro: Less code, data persists immediately
- Con: No review step — agent edits are immediately live

### Option B: P&L Suggestions Queue (Matches Portfolio Pattern)
Create a `pnl_pending_suggestions` table (or reuse `pending_suggestions` with a `grid_type` column). Agent proposes P&L edits → user accepts/rejects → accepted edits write to `fpa_actuals`.

- Pro: User reviews before data changes, consistent UX with portfolio grid
- Con: More plumbing — need new table, new accept/reject UI for P&L cells, new apply handler

### Option C: Hybrid
Agent reads from `fpa_actuals` (always fresh). Agent writes go through a suggestions queue. CSV upload and user edits write directly.

---

## Tables Involved

| Table | Purpose | Who writes | Who reads |
|---|---|---|---|
| `companies` | Portfolio company master data | CSV upload, cell edits, accepted suggestions | Portfolio grid |
| `pending_suggestions` | Agent-proposed portfolio edits | `bulk_write_grid` tool | Accept/reject UI |
| `fpa_actuals` | P&L line items (actuals + agent edits) | CSV upload, `fpa_cell_edit`, `fpa_upload_actuals` | `PnlBuilder` → P&L grid |
| `fpa_forecasts` | Saved forecast runs | `fpa_forecast` tool | `PnlBuilder` (forecast overlay) |
| `fpa_upload_jobs` | Upload job tracking | `fpa_upload_actuals` tool | Status checks |
