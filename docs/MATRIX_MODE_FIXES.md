# Matrix Mode Fixes — Kill Query, Wire @ Search, Fix LP

## The Problems

1. **Query mode is superfluous** — does the same thing as Custom/Sourcing mode but with less functionality. Both show a query bar, both call unified-brain. Custom mode additionally handles `@CompanyName`. No reason for two modes.

2. **@ queries don't land in the grid** — The batch search pipeline (`handleBatchCompanySearch`) POSTs to `/api/matrix/companies/search`, which starts a Tavily web search job, then polls `/api/matrix/companies/search/[jobId]` for results. The POST route and the GET route use **separate in-memory Maps** (`searchJobs`) — the shared `job-store.ts` exists but neither route imports it. So polling always falls through to the backend status endpoint, which may or may not have the job. Results rarely land in the grid.

3. **LP mode reads the wrong table** — `fetchLPsForMatrix` queries `limited_partners` directly with `fund_id.eq.{fundId}`. But the real data model is `lp_fund_commitments` (many-to-many join table, created in `20250211_lp_fund_commitments_join.sql`). The `fund_lp_summary` view already joins through this table and exposes richer columns (ownership_pct, fee terms, side letters). The grid never sees any of it.

---

## 1. Kill Query Mode

Remove `'query'` from `MatrixMode` everywhere. Merge any unique behaviour into `'custom'`.

### Type definitions — remove `'query'` from the union

| File | Line | Current |
|------|------|---------|
| `frontend/src/lib/matrix/matrix-api-service.ts` | 13 | `'portfolio' \| 'query' \| 'custom' \| 'lp' \| 'pnl'` |
| `frontend/src/lib/matrix/cell-action-registry.ts` | 8 | same |
| `frontend/src/components/matrix/UnifiedMatrix.tsx` | 135 | same |
| `frontend/src/components/matrix/AGGridMatrix.tsx` | 63 | same (props type) |
| `frontend/src/components/matrix/AgentPanel.tsx` | 45 | same (props type) |
| `frontend/src/components/agent/AgentChat.tsx` | 138 | same (props type) |
| `frontend/src/lib/matrix/matrix-mode-manager.ts` | 18 | `primaryDataSource` type includes `'query'` |

### Config — delete query block

`frontend/src/lib/matrix/matrix-mode-manager.ts:40-56` — remove entire `query: { ... }` block from `MODE_CONFIGS`.

### Conditionals — simplify

| File | Line | Change |
|------|------|--------|
| `UnifiedMatrix.tsx` | 4301 | `mode === 'query' \|\| mode === 'custom'` → `mode === 'custom'` |
| `UnifiedMatrix.tsx` | 4307 | placeholder ternary referencing query — simplify |
| `UnifiedMatrix.tsx` | 4312 | button label ternary — simplify |

### Mode icons — remove query entry

`frontend/src/app/matrix-control-panel/page.tsx:686` — delete `query: Sparkles` from `modeIcons`.

### Cell action availability — remove `'query'` from arrays

**Frontend:** `frontend/src/app/api/cell-actions/actions/route.ts` — 5 `mode_availability` arrays.

**Backend:** `backend/app/services/cell_action_registry.py`:
- Line 61: default `mode_availability` list
- Line 111: `register_formula` default
- Line 143: `register_workflow` default
- Lines 1681, 1692, 1703: `['query', 'custom']` → `['custom']`
- Lines 1715, 1738, 1749, 1760, 1771: `['portfolio', 'query']` → `['portfolio']`
- Lines 1810, 1822: `['portfolio', 'query', 'custom', 'lp']` → `['portfolio', 'custom', 'lp']`

### Comments — update

`frontend/src/lib/matrix/matrix-api-service.ts`:
- Line 257: `// Custom / query / LP mode` → `// Custom / LP mode`
- Line 307: `// Query/custom mode columns` → `// Custom mode columns`
- Line 320: `// ephemeral column (query/custom mode)` → `// ephemeral column (custom mode)`

---

## 2. Wire @ Search to Grid

### Current broken flow
```
@CompanyName in query bar
  → parseCompanyMentions() extracts names
  → handleBatchCompanySearch(names)
    → POST /api/matrix/companies/search          ← creates job in local Map A
      → backend: POST /api/mcp/batch-search-companies (Tavily)
    → poll GET /api/matrix/companies/search/{jobId}  ← checks local Map B (different Map!)
      → falls through to backend: GET /api/mcp/batch-search-status/{jobId}
      → sometimes works, often doesn't
    → on 'completed': map results to MatrixRow, add to grid
```

### Fix: use shared job store

The shared store already exists at `frontend/src/app/api/matrix/companies/search/job-store.ts`:
```ts
export type SearchJob = { status, companyNames, results, error?, createdAt };
export const searchJobs = new Map<string, SearchJob>();
```

Neither route imports it. Both define their own local Map.

**Changes:**

#### `frontend/src/app/api/matrix/companies/search/route.ts`
- Delete the local `searchJobs` Map (lines 5-11)
- Delete the cleanup `setInterval` (lines 14-21)
- Import from job-store: `import { searchJobs } from './job-store';`
- Keep everything else the same

#### `frontend/src/app/api/matrix/companies/search/[jobId]/route.ts`
- Delete the local `searchJobs` Map (lines 6-12)
- Import from job-store: `import { searchJobs } from '../job-store';`
- Check the shared store FIRST before falling through to backend:
```ts
const localJob = searchJobs.get(jobId);
if (localJob) {
  return NextResponse.json({
    status: localJob.status,
    companyNames: localJob.companyNames,
    results: localJob.results,
    error: localJob.error,
  });
}
// Then fall through to backend poll as existing fallback
```

#### `frontend/src/components/matrix/UnifiedMatrix.tsx` — `handleBatchCompanySearch`
The existing result-to-row mapping at lines 1515-1536 is correct. Once the shared store fix makes polling work, results will land in the grid as rows with cells: `company, sector, arr, valuation, ownership`.

No changes needed to UnifiedMatrix if the route fix works. But optionally: add a cleanup for the `setInterval` in the job store as a module-level side effect.

#### Add cleanup to job-store.ts
```ts
// Clean up old jobs (older than 1 hour)
if (typeof setInterval !== 'undefined') {
  setInterval(() => {
    const oneHourAgo = Date.now() - 3600000;
    for (const [jobId, job] of searchJobs.entries()) {
      if (job.createdAt < oneHourAgo) searchJobs.delete(jobId);
    }
  }, 60000);
}
```

---

## 3. Fix LP Mode Data Structure

### Current broken flow
```
fetchLPsForMatrix(fundId?)
  → supabase.from('limited_partners')
    .select('id, name, lp_type, status, commitment_usd, called_usd, ...')
    .or('fund_id.eq.{fundId},fund_id.is.null')
  → maps to 12 columns: lpName, lpType, status, commitment, called,
    distributed, unfunded, dpi, coInvest, vintageYear, contactName, capacity
```

This reads the OLD 1:1 `fund_id` column on `limited_partners`. The real data lives in `lp_fund_commitments` (per-commitment capital accounts, fee terms, side letters).

### Target flow
```
fetchLPsForMatrix(fundId?)
  → supabase.from('fund_lp_summary')     ← view joining lp_fund_commitments
    .select('*')
    .eq('fund_id', fundId)                ← required, M:M means must filter
  → fallback: limited_partners (if view doesn't exist)
  → maps to richer columns
```

### `fund_lp_summary` view columns (from migration `20250211`)
```sql
fund_id, lp_id, lp_name, lp_type,
commitment_usd, called_usd, distributed_usd, unfunded_usd, dpi,
ownership_pct, management_fee_pct, carried_interest_pct, preferred_return_pct,
co_invest_rights, mfn_clause, advisory_board_seat,
side_letter_terms, commitment_status, commitment_currency
```

### New LP column set

```
lpName          ← lp_name          (text, 180w)
lpType          ← lp_type          (text, 100w)
status          ← commitment_status (text, 90w)
commitment      ← commitment_usd    (currency, 130w)
called          ← called_usd        (currency, 120w)
distributed     ← distributed_usd   (currency, 130w)
unfunded        ← unfunded_usd      (currency, 120w, computed in view, read-only)
dpi             ← dpi               (number, 70w, computed in view, read-only)
ownership       ← ownership_pct     (percentage, 90w)
managementFee   ← management_fee_pct (percentage, 80w)
carry           ← carried_interest_pct (percentage, 70w)
preferredReturn ← preferred_return_pct (percentage, 80w)
coInvest        ← co_invest_rights   (boolean, 80w)
mfnClause       ← mfn_clause        (boolean, 70w)
advisoryBoard   ← advisory_board_seat (boolean, 80w)
currency        ← commitment_currency (text, 70w)
```

### Files to change

#### `frontend/src/lib/matrix/matrix-api-service.ts` — `fetchLPsForMatrix` (line 991-1074)

Rewrite:
1. Primary: query `fund_lp_summary` view filtered by `fund_id`
2. Fallback: if view doesn't exist (error contains "does not exist"), query `limited_partners` as today
3. Map to new column set
4. Computed fields (`unfunded`, `dpi`) come from the view — no client-side math needed

#### `frontend/src/lib/matrix/matrix-mode-manager.ts` — `MODE_CONFIGS.lp`

Update `defaultColumns` to match new column IDs:
```ts
defaultColumns: [
  'lpName', 'lpType', 'status', 'commitment', 'called', 'distributed',
  'unfunded', 'dpi', 'ownership', 'managementFee', 'carry',
  'preferredReturn', 'coInvest', 'mfnClause', 'advisoryBoard', 'currency'
],
```

#### `frontend/src/components/matrix/AGGridMatrix.tsx` — `DEFAULT_LP_COLUMNS` (line 122-135)

Replace with new columns matching the set above.

#### `frontend/src/components/matrix/UnifiedMatrix.tsx` — `getDefaultMatrixData` LP branch (line 317-335)

Replace column definitions to match `DEFAULT_LP_COLUMNS`.

---

## Execution Order

1. Kill query mode (type-level, no runtime impact — safe to do first)
2. Fix @ search pipeline (route-level, isolated to 2 API route files + job-store)
3. Fix LP data structure (data-level, touches API service + 3 column definition sites)

## Verification

- Switch to each mode in matrix-control-panel — query should be gone from dropdown
- In Custom/Sourcing mode: type `@Stripe` in query bar → should see a row appear with Tavily-sourced data
- In LP mode: select a fund → grid should show columns from `fund_lp_summary` including ownership %, fees, carry
- TypeScript build should pass with no 'query' type errors
