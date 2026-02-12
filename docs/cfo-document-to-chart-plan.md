# CFO Document-to-Chart Code-Level Plan

**Philosophy**: Cursor-for-CFO flow — document processing → accept/reject suggestions (Cursor-style) → flow into advanced Tableau charts (deck-agent style).

---

## Full Infrastructure: Multi-Doc & Single-Doc, Extraction → Suggestions → Insights → Risks → Accept/Reject

### Single-Doc Flow

| Step | Component | Endpoint / File | Status |
|------|-----------|-----------------|--------|
| 1. Upload | Frontend | `POST /api/documents` (Supabase storage) | ✅ |
| 2. Insert metadata | Frontend | `processed_documents` row (company_id, fund_id) | ✅ |
| 3. Trigger process | Frontend | `POST /api/documents/process` → backend `POST /api/documents/process` | ✅ Sync |
| 4. Extract text | Backend | `document_process_service._text_from_file()` (PDF/DOCX) | ✅ |
| 5. AI extraction | Backend | `_extract_document_structured_async()` → model_router (Claude) | ✅ |
| 6. Normalize | Backend | `_normalize_extraction()` → `financial_metrics`, `business_updates`, `red_flags`, `implications`, `value_explanations` | ✅ |
| 7. Persist | Backend | `document_repo.update()` → `extracted_data`, `status: completed` | ✅ |
| 8. Suggestions | Frontend | `GET /api/matrix/suggestions?fundId=&companyId=` | ✅ |
| 9. Insights/Risks | Frontend | Same response: `insights[]` with redFlags, implications, achievements, challenges, risks | ✅ |
| 10. Accept/Reject | Frontend | `onSuggestionAccept` → `POST /api/matrix/cells` with `source_document_id` | ✅ |

### Multi-Doc (Batch) Flow

| Step | Component | Endpoint / File | Status |
|------|-----------|-----------------|--------|
| 1. Batch upload | Frontend | `POST /api/documents/batch` (FormData) | ✅ |
| 2. Loop: upload + insert | Frontend | Supabase storage + `processed_documents` per file | ✅ |
| 3. Trigger batch process | Frontend | Fire-and-forget `POST /api/documents/process-batch` | ✅ Sync |
| 4. Backend batch | Backend | `documents_process.process_batch` → `asyncio.gather` + `run_document_process` per doc | ✅ |
| 5. Per-doc extraction | Backend | Same as single-doc (steps 4–7) | ✅ |
| 6. Suggestions/Insights | Frontend | `GET /api/matrix/suggestions` (reads all completed docs) | ✅ |
| 7. Accept/Reject | Frontend | Same as single-doc | ✅ |

### Extraction Output Shape (used by Suggestions API)

From `document_process_service._normalize_extraction()` / schemas:

- **financial_metrics**: arr, revenue, mrr, burn_rate, runway_months, cash_balance, gross_margin, growth_rate
- **business_updates**: product_updates, achievements, challenges, risks, key_milestones, asks, latest_update, defensive_language
- **operational_metrics**: new_hires, headcount, customer_count, enterprise_customers, smb_customers
- **market_size**: tam_usd, sam_usd, som_usd (investment_memo)
- **red_flags**: array of strings
- **implications**: array of strings
- **value_explanations**: `{ [metric_key]: string }` (doc-sourced reasoning per metric)

### Suggestions API Logic

- Compares `extracted_data` vs matrix row values (companies + extra_data)
- Builds `suggestions[]` for changed/new metrics (arr, burnRate, runway, cash, grossMargin, valuation, headcount, optionPool, tam/sam/som, sector, latestUpdate, productUpdates)
- `buildReasoningAndConfidence()` uses `value_explanations[columnId]` when present (Phase 1)
- Confidence: explicit in doc (+0.25), caution signals (−0.15), extrapolated (−0.1)

### Insights (per document)

- `redFlags`, `implications`, `achievements`, `challenges`, `risks` from `extracted_data.business_updates` and `extracted_data.red_flags`
- Returned alongside `suggestions` in `GET /api/matrix/suggestions`

### Accept/Reject → Persistence

- Accept: `handleCellEdit(..., { sourceDocumentId })` → `POST /api/matrix/cells` with `source_document_id`, `data_source: 'document'`
- `matrix_edits` row includes `source_document_id` for audit trail
- Company columns (`current_arr_usd`, etc.) and `*_document_id` (e.g. `revenue_document_id`) updated

### Gaps / To-Build

| Component | Status | Phase |
|-----------|--------|-------|
| Celery async single-doc | ❌ | Phase 2: `POST /api/documents/process-async` |
| Celery async batch | ❌ | Phase 2: `POST /api/documents/process-batch-async` |
| Long-running + rate-limit respect | ❌ | Phase 2: task `acks_late`, `autoretry_for` RateLimitError, Celery rate_limit |
| `value_explanations` in prompts | ⚠️ Partial | Phase 1: prompts + normalize |
| Batch status polling | ❌ | Phase 4 (optional) |

---

## Data Flow Overview

```
Documents (upload) → Extraction (value_explanations) → Suggestions API → Accept/Reject
                                                                              ↓
Matrix data (companies + extra_data) ← POST /api/matrix/cells (source_document_id)
                                                                              ↓
ChartViewport ← extractChartsFromMatrix(matrixData) → TableauLevelCharts
```

---

## Phase 1: Document-Sourced Reasoning (Extraction)

### 1.1 Backend: `document_process_service.py`

**Add to extraction schemas** (`value_explanations` / `metric_reasoning`):

| Schema | Add Field | Purpose |
|--------|-----------|---------|
| `COMPANY_UPDATE_SIGNAL_SCHEMA` | `value_explanations: { [metric_key]: string }` | Per-metric doc-sourced reasoning |
| `INVESTMENT_MEMO_SCHEMA` | same | Same |
| `DOCUMENT_EXTRACTION_SCHEMA` | same | Same |

**Metric keys** (align with suggestions API columnIds):
- `arr`, `burn_rate`, `runway_months`, `cash_balance`, `gross_margin`, `growth_rate`
- `headcount`, `option_pool_bps`, `tam_usd`, `sam_usd`, `som_usd`
- `valuation`, `sector`, `latest_update`, `product_updates`

**Prompt changes** (in `_signal_first_prompt`, `_memo_prompt`, `_flat_prompt`):
- "For each extracted metric, add a short doc-sourced explanation to value_explanations, e.g. `option_pool_bps: 'We did an options refresh'`."
- "For extrapolated values (e.g. option pool from senior hires), include the doc excerpt and inference in value_explanations."

**Normalize in `_normalize_extraction`**:
- Ensure `value_explanations` is a dict in output; default `{}` if missing.

**File**: `backend/app/services/document_process_service.py`

---

### 1.2 Frontend: Suggestions API `value_explanations` Usage

**In `buildReasoningAndConfidence`** (`frontend/src/app/api/matrix/suggestions/route.ts`):
- Accept optional `valueExplanation?: string` param.
- When present, prefer it over generic "Doc: X. Matrix: Y.":
  - `reasoning = valueExplanation + (currentValue != null ? ` (was ${currentValue}).` : '.')`
- Fall back to existing logic when `valueExplanation` is null/undefined.

**When building each suggestion**:
- `const valueExplanation = (extractedData.value_explanations as Record<string, string>)?.[columnId] ?? (extractedData.value_explanations as Record<string, string>)?.[mapColumnToMetricKey(columnId)];`
- Pass `valueExplanation` into `buildReasoningAndConfidence`.

**Implied column → metric key map** (e.g. `runway` → `runway_months`, `optionPool` → `option_pool_bps`).

**File**: `frontend/src/app/api/matrix/suggestions/route.ts`

---

## Phase 2: Celery Queue for Batch Processing (Scale + Long-Running + Rate-Limit Respect)

**Requirements**:
- **Long-running analysis**: Document extraction can take minutes (AI calls, large PDFs). Celery tasks must have adequate `time_limit` / `soft_time_limit`.
- **Rate limiting**: LLM APIs (Claude, etc.) return 429. Tasks must wait and retry rather than fail.
- **Waits for rate limit respect**: On 429, use exponential backoff; `autoretry_for` + `retry_backoff` + `retry_jitter`.

### 2.1 Backend: New Async Endpoint

**New route**: `POST /api/documents/process-async`

**Request body**:
```json
{
  "document_id": "uuid",
  "file_path": "documents/123/file.pdf",
  "document_type": "monthly_update",
  "company_id": "uuid",
  "fund_id": "uuid"
}
```

**Behavior**:
- Enqueue `app.tasks.document.process` with `acks_late=True`.
- Return `{ "queued": true, "document_id": "...", "message": "Processing queued" }`.

**File**: `backend/app/api/endpoints/documents_process.py` (add new route)

---

### 2.2 Backend: `tasks.py` — Update `process_document`

**Current**: Accepts `document_id`, `file_path`, `document_type` only.

**Change**:
- Add `company_id`, `fund_id` as optional kwargs.
- When calling `run_document_process`, pass `company_id`, `fund_id` (already supported).
- `acks_late=True` so message is re-queued if worker dies before ack.
- `autoretry_for=(RateLimitError,)` or catch 429 in `run_document_process` and re-raise as `RateLimitError`.
- `retry_backoff=True`, `retry_backoff_max=600` (10 min), `retry_jitter=True`.
- Celery `task_annotations` for `app.tasks.document.process`: `rate_limit: "5/m"` to avoid hammering LLM APIs when many docs queued.

**File**: `backend/app/tasks.py`

**Note**: `run_document_process` uses `model_router` which already retries on 429; Celery retries provide an additional safety net if the whole task fails (e.g. timeout).

---

### 2.3 Frontend: Batch Upload → Enqueue

**Current**: Batch route uploads files, inserts `processed_documents`, then fires HTTP to `POST /api/documents/process-batch` (sync).

**Change**:
- Option A: Call `POST /api/documents/process-async` per document (backend enqueues).
- Option B: Add backend `POST /api/documents/process-batch-async` that enqueues N tasks and returns immediately.

**Recommendation**: Option B — single batch call, backend enqueues all.

**File**: `frontend/src/app/api/documents/batch/route.ts`
- Keep upload loop; after all inserts, call backend `process-batch-async` instead of `process-batch`.
- Backend: add `POST /api/documents/process-batch-async` that loops and enqueues each doc.

**File**: `backend/app/api/endpoints/documents_process.py`

---

## Phase 3: Accept/Reject → Persist with Audit Trail

### 3.1 Portfolio Page: Pass `sourceDocumentId` to API

**Current**: `onCellEdit` handles `documents` column specially; else calls `handleEditMatrixCell` (PUT `/api/portfolio/...`), which does not support `source_document_id`.

**Change**:
- When `options?.sourceDocumentId != null` (suggestion accept), call `POST /api/matrix/cells` instead of `handleEditMatrixCell`:
  - `company_id`, `column_id`, `new_value`, `fund_id`, `source_document_id`, `data_source: 'document'`, `metadata: { sourceDocumentId }`.
- For non-suggestion edits (manual), keep `handleEditMatrixCell` flow.

**File**: `frontend/src/app/portfolio/page.tsx`

```ts
onCellEdit={async (rowId, columnId, value, options) => {
  if (columnId === 'documents' && options?.metadata?.documents != null) { /* existing */ return; }
  if (options?.sourceDocumentId != null) {
    const res = await fetch('/api/matrix/cells', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        company_id: rowId,
        column_id: columnId,
        new_value: value,
        fund_id: portfolio.id,
        source_document_id: options.sourceDocumentId,
        data_source: 'document',
        metadata: { sourceDocumentId: options.sourceDocumentId },
      }),
    });
    if (!res.ok) throw new Error(/* ... */);
    return;
  }
  await handleEditMatrixCell(rowId, columnId, value);
}}
```

---

### 3.2 Matrix Cells API: `source_document_id` in Audit

**Current**: `matrix_edits` insert uses `metadata`; `source_document_id` column exists in migration but may not be passed.

**Change**:
- In `POST /api/matrix/cells` insert to `matrix_edits`:
  - Add `source_document_id: sourceDocumentId ?? null` when present.

**File**: `frontend/src/app/api/matrix/cells/route.ts`

---

### 3.3 UnifiedMatrix: `handleCellEdit` Options

**Current**: `handleCellEdit` accepts `options?: { sourceDocumentId }` and passes to `onCellEdit` / `saveCellEditToCompany`. This is already correct.

**Verify**: `onSuggestionAccept` and `onApplySuggestions` pass `{ sourceDocumentId: s.sourceDocumentId }` to `handleCellEdit`. Done in ChartViewport → UnifiedMatrix.

---

## Phase 4: Refresh After Processing

### 4.1 DocumentsCell: Trigger Refresh ✅

**Implemented**. Parent now refreshes suggestions and opens viewport after doc process.

**Current (reference)**: `onSuggestChanges` is called after extraction; parent should call `refreshSuggestions`.

**Change**:
- Ensure `DocumentsCell` parent (UnifiedMatrix) passes `onSuggestChanges` that calls `refreshSuggestions()` and optionally `setShowChartViewport(true)`.
- After single-doc process completes (via cell action or sync process), parent refreshes suggestions.

**File**: `frontend/src/components/matrix/MatrixCellFeatures.tsx` (DocumentsCell)
**File**: `frontend/src/components/matrix/UnifiedMatrix.tsx` (where DocumentsCell is rendered)

**Verify**: `onSuggestChanges` → `refreshSuggestions` + open viewport. May already exist; ensure it’s wired.

---

### 4.2 Batch: Polling or Webhook (Optional)

- Option: `GET /api/documents/batch-status/{batchId}` for polling after batch upload.
- Simpler: Frontend returns immediately; user can manually refresh. Or use short polling (e.g. 5s) for 30s before stopping.

**Defer** to Phase 2 completion; not critical for MVP.

---

## Phase 5: Charts Flow (Deck-Agent Style)

### 5.1 Chart Data Sources

**Current**: ChartViewport reads charts from:
1. `extractChartsFromMatrix(matrixData)` — cell metadata (`chart_config`, `chart_to_create`) and `matrixData.metadata.charts` (MCP).
2. Renders via `TableauLevelCharts` for advanced types.

**Flow**: Matrix data (companies + extra_data) → cell metadata / MCP charts → ChartViewport → TableauLevelCharts.

---

### 5.2 Ensure Accepted Suggestions Flow to Charts

**Current**: Accept suggestion → `POST /api/matrix/cells` → updates `companies` and `extra_data`. Matrix reloads from API; `matrixData` updates; `extractChartsFromMatrix` picks up any new cell metadata.

**Charts from cells** come from:
- Cell actions that return `chart_config` in metadata (e.g. cap table, valuation).
- MCP orchestrator `metadata.charts`.

**Gap**: Document-extracted metrics (ARR, burn, runway, etc.) do not by themselves create chart configs. Charts are created by:
- Cell actions (e.g. valuation, cap table analysis).
- Deck agent (unified_mcp_orchestrator) generating `chart_data` for slides.

**To get “document → accept → chart” flow:**

1. **Option A — Cell metadata charts**: When a cell action runs (e.g. from documents column or a “Generate chart” action), it can use the updated matrix data (which now includes accepted doc values) to produce chart config. No change needed if actions already read matrix state.

2. **Option B — Chart generation action**: Add a cell action (e.g. `chart.generate_from_matrix`) that:
   - Takes selected rows/columns or full matrix.
   - Calls ChartGenerationSkill (or equivalent) with current matrix data.
   - Returns `chart_config`; store in cell metadata → ChartViewport displays.

3. **Option C — ChartViewport “Generate from matrix”**: Button in ChartViewport that:
   - Sends current `matrixData` to backend chart generation.
   - Receives chart config; append to `matrixData.metadata.charts` or a temp state.
   - Render in ChartViewport via TableauLevelCharts.

**Recommendation**: Implement Option C as a “Generate charts from matrix” control in ChartViewport. Reuse `ChartGenerationSkill` / `chart_renderer_service` pattern from deck agent.

---

### 5.2a Getting NAV, Revenue Growth, J-Curve, and Other Charts **Without** Pressing Build Chart

**Problem**: The plan above assumes user clicks "Generate charts from matrix." How do we get NAV, revenue growth, J-curve, probability cloud, and Path-to-$100M charts (which deck agent produces) without that manual step?

**Solution: Two-Pronged Approach**

#### A. Always-Available Portfolio Charts (No User Action)

These charts use **existing APIs** and portfolio data. ChartViewport fetches them automatically when opened (or when `fundId` + matrixData are present). No "Build Chart" needed.

| Chart Type | Data Source | Implementation |
|------------|-------------|----------------|
| **NAV over time** | `GET /api/portfolio/[id]/nav-timeseries` | Already exists. UnifiedMatrix fetches for sparklines. ChartViewport adds a "Portfolio NAV" card that fetches same endpoint and renders a full line chart via TableauLevelCharts (`type: "line"`). |
| **J-curve / Pacing** | `GET /api/portfolio/pacing` or portfolio companies + deployment dates | Pacing page has J-curve logic. Extract into shared util or API. ChartViewport adds "Fund Pacing" card that fetches and renders deployment curve (cumulative invested vs time). |
| **Revenue growth** | Matrix `arr` / `currentArr` over time | Requires `matrix_edits` history for arr (or doc-extracted snapshots). If available: aggregate by date → line chart. Phase 2: add `GET /api/portfolio/[id]/arr-timeseries` similar to nav-timeseries. |

**Implementation**:
- Add `portfolioOverviewCharts` section to ChartViewport (above or alongside `extractChartsFromMatrix` results).
- On mount/`fundId` change: `useEffect` fetches nav-timeseries, pacing (if endpoint exists), etc.
- Transform API responses into `ChartConfig` format (`type`, `data`, `title`) and render via TableauLevelCharts.
- No backend chart-generation skill needed for these — they are deterministic from portfolio data.

#### B. Auto-Generate on Accept (Deck-Agent Style Charts)

For sankey, probability cloud, Path to $100M, waterfall — these require ChartGenerationSkill or deck orchestrator logic. Trigger them **automatically** when user accepts suggestions:

1. **On `onSuggestionAccept` completion** (after `POST /api/matrix/cells` and matrix reload):
   - Call `POST /api/matrix/charts/generate` with `chart_type: "auto"` and current `matrixData`.
   - Backend returns chart configs (same as Option C).
   - Append returned charts to ChartViewport (e.g. `matrixData.metadata.charts` or local state).
   - User never clicks "Generate" — charts appear after accept.

2. **Backend chart generation** must produce deck-agent equivalents:
   - `path_to_100m` / revenue growth line: Reuse `_execute_deck_generation` Path-to-$100M logic from `unified_mcp_orchestrator.py` (lines ~9140–9514) or extract into shared service.
   - `probability_cloud`: Reuse `_generate_probability_cloud_data` / `_format_probability_cloud_chart` (lines ~17142, 18944).
   - `sankey`, `waterfall`: ChartGenerationSkill or valuation_engine_service already supports these.

3. **Optional**: Add `autoGenerateChartsOnAccept: boolean` (default: true) so users can disable if they prefer manual control.

**Files to touch**:
- `ChartViewport.tsx`: Add portfolio-overview fetch + render; add post-accept chart generation call.
- `unified_mcp_orchestrator.py` or new `chart_data_service.py`: Extract Path-to-$100M, probability cloud, J-curve builders into callable functions for `/api/matrix/charts/generate`.
- `POST /api/matrix/charts/generate`: Extend to support `chart_type: "nav" | "pacing" | "path_to_100m" | "probability_cloud" | "auto"` and route to appropriate builders.

**Result**: NAV, pacing/J-curve, and revenue growth appear automatically (portfolio APIs). Sankey, probability cloud, Path to $100M appear automatically after accept (chart generation). "Generate charts from matrix" remains as optional manual trigger for ad-hoc charts.

---

### 5.3 Chart Generation Endpoint for Matrix

**New**: `POST /api/matrix/charts/generate`

**Request**:
```json
{
  "fund_id": "...",
  "matrix_data": { "rows": [...], "columns": [...] },
  "chart_type": "auto" | "sankey" | "waterfall" | "heatmap" | ...
}
```

**Response**:
```json
{
  "charts": [
    { "type": "sankey", "title": "...", "data": {...}, "renderType": "tableau" }
  ]
}
```

**Implementation**:
- Reuse `ChartGenerationSkill` from `backend/app/skills/chart_generation_skill.py`.
- **Data transformation**: Use `matrixToChartInput()` from `frontend/src/lib/matrix/chart-utils.ts` to transform matrix rows → ChartGenerationSkill input (companies, data). Same field mapping as deck agent.
- **Output**: Use `extractChartsFromMatrix(matrixData)` and `normalizeChartConfig()` for chart display; ChartViewport uses `TableauLevelCharts` (deck-agent style).

**Frontend**: ChartViewport “Generate” button → POST → append to local chart list or `matrixData.metadata.charts` for the session.

---

### 5.4 Tableau Chart Types (Same as Deck Agent)

**Supported in TableauLevelCharts**:
- `sankey`, `side_by_side_sankey`, `sunburst`, `waterfall`, `heatmap`, `bubble`, `radialBar`, `funnel`, `probability_cloud`, `timeline_valuation`, `pie`, `line`

**ChartViewport** already uses `TableauLevelCharts` for `extractChartsFromMatrix` results. No change needed for rendering.

---

## Phase 6: “Cursor for CFO” UX

### 6.1 DocumentsCell as Entry Point

- User uploads doc in DocumentsCell (or batch).
- Processing runs (sync or Celery).
- `onSuggestChanges` → `refreshSuggestions` → ChartViewport opens with Suggestions tab.

### 6.2 Suggestions Tab (Cursor-Style)

- List of suggestions with Accept / Reject per suggestion.
- Batch select + “Accept selected” / “Reject selected”.
- “Auto-apply high confidence” (≥0.9).
- Reasoning shown per suggestion (from `value_explanations` when available).

### 6.3 Charts Tab

- Charts from `extractChartsFromMatrix(matrixData)`.
- “Generate charts from matrix” → calls new chart generation API, adds to viewport.
- Each chart rendered via `TableauLevelCharts` (deck-agent style).

### 6.4 Insights Tab

- Red flags, implications, achievements, challenges, risks (already in place).

---

## Files to Modify (Summary)

| Layer | File | Changes |
|-------|------|---------|
| Backend | `document_process_service.py` | Add `value_explanations` to schemas; prompt for doc-sourced reasoning; normalize in output |
| Backend | `tasks.py` | Add `company_id`, `fund_id` to `process_document` |
| Backend | `documents_process.py` | Add `POST /process-async`, `POST /process-batch-async` |
| Frontend | `api/matrix/suggestions/route.ts` | Use `value_explanations[columnId]` in `buildReasoningAndConfidence` |
| Frontend | `portfolio/page.tsx` | When `options?.sourceDocumentId`, call `POST /api/matrix/cells` instead of `handleEditMatrixCell` |
| Frontend | `api/matrix/cells/route.ts` | Add `source_document_id` to `matrix_edits` insert |
| Frontend | `api/documents/batch/route.ts` | Call `process-batch-async` instead of `process-batch` |
| Frontend | `ChartViewport.tsx` | Add “Generate charts from matrix” button; call new chart API |
| Backend | New: `api/matrix/charts/generate` or extend cell_actions | Chart generation from matrix data |

---

## Implementation Order

1. **Phase 1** — Document-sourced reasoning (extraction + suggestions API)
2. **Phase 3** — Accept/reject → persist with `source_document_id` (portfolio + cells API)
3. **Phase 2** — Celery async batch (optional but recommended for scale)
4. **Phase 4** — Refresh after processing
5. **Phase 5** — Chart generation from matrix
6. **Phase 6** — UX polish (ordering, copy, etc.)

---

## Example End-to-End Flow

1. User uploads board deck in DocumentsCell for Company A.
2. Backend processes → `extracted_data` includes `value_explanations: { arr: "Q3 exceeded target; doc states $1.2M ARR" }`.
3. Suggestions API returns `{ suggestedValue: 1200000, reasoning: "Q3 exceeded target; doc states $1.2M ARR (was $1M).", ... }`.
4. User accepts in ChartViewport → `handleCellEdit(..., { sourceDocumentId })` → `POST /api/matrix/cells` with `source_document_id`.
5. Matrix reloads; Company A’s ARR is $1.2M.
6. User clicks “Generate charts from matrix” → sankey/waterfall/heatmap from updated data → ChartViewport displays via TableauLevelCharts.

---

*Last updated: February 2025*
