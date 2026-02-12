# Cell Action → Grid Audit: Document, Valuation, DPI Sankey, Charts & Services

This doc traces how cell actions (document extraction, valuation, DPI Sankey, charts, etc.) run and write to the grid, and what was done so they work outside deck/memo.

## End-to-end flow

1. **Frontend**  
   User picks an action (dropdown or valuation picker) → `executeAction({ action_id, row_id, column_id, inputs, mode, fund_id, company_id })` in `frontend/src/lib/matrix/cell-action-registry.ts`.

2. **Proxy**  
   `POST /api/cell-actions/actions/[actionId]/execute` (Next.js) forwards the body to backend `POST /api/cell-actions/actions/{action_id}/execute`.

3. **Backend**  
   `backend/app/api/endpoints/cell_actions.py`:
   - `execute_action()` loads the action from the registry.
   - `_route_to_service(action, request)` calls the right service (valuation, document, DPI Sankey, chart, etc.).
   - `registry.transform_output(action_id, service_output)` turns service output into a single shape: `{ value, displayValue, metadata }`.
   - Returns `ActionExecutionResponse(success, action_id, value, display_value, metadata, error?)`.  
   All of `value` and `metadata` are made JSON-safe (`_make_json_safe`).

4. **Frontend again**  
   `handleCellActionResult(rowId, columnId, response)` in `UnifiedMatrix.tsx`:
   - Uses `extractCellValue(response)` → `response.value`.
   - Uses `formatActionOutput(response, column.type)` for display.
   - `applySingleActionResult()` updates the trigger cell with `value`, `displayValue`, `metadata` (including `chart_config`, `time_series`, `columns_to_create`), and optionally creates new columns from `metadata.columns_to_create`.
   - Persists via `onCellEdit` and `/api/matrix/cells` when in portfolio mode.

So for the grid to show the right thing, the backend must return a proper **value** and, where needed, **metadata** (chart_config, time_series, columns_to_create). The registry’s `transform_output` and `_extract_default_value` are what produce that shape.

---

## What was changed (no fallbacks / real services only)

### 1. Registry: `_extract_default_value` (backend)

**File:** `backend/app/services/cell_action_registry.py`

OBJECT actions without `output_transform` used to fall through to `value` / `result` / `data`. Some services never set those keys, so the grid got 0 or empty.

**Added explicit handling for:**

- **document** (`document_query_service`): `value` or `summary` (document.extract / document.analyze return `{ value, summary }` or `{ value, metadata }`).
- **debt** (`advanced_debt_structures`): `value`, `total_debt`, `debt_to_equity_ratio`, `recommendation`, `summary` (dataclass `__dict__` has `total_debt`, etc.).
- **scoring** (`company_scoring_visualizer`): `overall_score`, `score`, `total_score`, `value` (CompanyScore has `overall_score`).
- **gap_filler** (`intelligent_gap_filler`): `value`, `overall_score`, `score`, `ai_adjusted_multiple`, `momentum_score`, `tam_value`, `recommendation`.

So when these services return their native dict/dataclass, the registry still produces a single **value** (and display) for the cell.

### 2. Router: return shape for debt and scoring (backend)

**File:** `backend/app/api/endpoints/cell_actions.py`

- **Debt:** Still returns the debt dataclass as a dict, but now also sets `value = total_debt` so the grid has a primary numeric value and the default branch can use `value` if needed.
- **Scoring (score_company):** Still returns CompanyScore as a dict, but now also sets `value = overall_score` so the grid shows the main score.

No change to document or chart branches: document already returns `{ value, summary }`; chart branch returns a dict with `type`, `title`, `data`, `renderType`, which the registry’s CHART transform puts into `metadata.chart_config`.

---

## Service-by-service: what makes them write to the grid

### Document extraction (`document.extract`, `document.analyze`)

- **Backend:** Document branch returns `DocumentQueryService.extract_structured_data` / `analyze_document` result: `{ value, summary }` or `{ value, metadata }`. Registry document case uses `value` or `summary` for the cell value.
- **Frontend:** `buildActionInputs` did **not** set `document_id`. So:
  - **Document upload flow (MatrixCellFeatures):** After upload, the code calls `executeAction` with `document_id: result.documentId` → works.
  - **Generic dropdown:** If the user picks “Extract Document Data” or “Analyze Document” from the dropdown without a document in that row, `document_id` was missing → backend raises “document_id required”.
- **Fix (in this audit):** Add `document.*` handling in `buildActionInputs` to pass `document_id` from a row cell when the matrix has a column that holds document id (e.g. `document_id`, `document`, or a doc link column). That way document actions can work from the dropdown when the row has a document reference.

### Valuation (`valuation_engine.pwerm`, `.dcf`, `.auto`, etc.)

- **Backend:** Valuation branches return `{ fair_value, method_used, explanation, confidence, raw_result }`. Registry uses `output_transform="fair_value"` → cell value is `fair_value`.
- **Frontend:** `buildActionInputs` fills name, revenue/arr, sector, growth, stage, valuation, invested from row/columns. `company_id` and `fund_id` come from row and matrix metadata.
- **Grid:** `value` = fair_value, `displayValue` from `formatActionOutput`, `metadata` has method/explanation; grid and citations panel can show them. No further change needed for “writing to the grid.”

### DPI Sankey (`portfolio.dpi_sankey`)

- **Backend:** Branch returns `{ type: 'sankey', title, data: { nodes, links }, metrics, renderType: 'tableau' }`. Registry CHART transform puts that in `metadata.chart_config` and sets a string value (e.g. “sankey: DPI Flow”).
- **Frontend:** `buildActionInputs` sets `fund_id` from `matrixData?.metadata?.fundId`. UnifiedMatrix sets `metadata.fundId` when in portfolio mode with a selected fund, so DPI Sankey gets `fund_id` when used from the matrix in portfolio mode.
- **Grid:** Cell gets `value` (title string), `metadata.chart_config` (full config). ChartViewport / MatrixInsights read `cell.metadata?.chart_config` to show the chart. So DPI Sankey **does** write to the grid (value + chart_config); the chart is shown in the chart panel/viewport, not necessarily inside the cell.

### Charts (`chart_intelligence.generate`)

- **Backend:** “chart” in service_name branch uses `ChartGenerationSkill`, returns `{ type, title, data, renderType }` (or fallback with error). Registry CHART transform → `metadata.chart_config`, value = “type: title”.
- **Frontend:** `buildActionInputs` sets `data` (row data), `chart_type`, `context` for `chart_intelligence.generate`. No `document_id`-style dependency.
- **Grid:** Same as DPI Sankey: cell gets value + `metadata.chart_config`; chart appears in ChartViewport/insights when they read that cell.

### Fund metrics (`fund_metrics.calculate`)

- **Backend:** Returns `total_nav`, `total_invested`, `dpi`, `tvpi`. Registry uses `output_transform="total_nav"` → value is total_nav.
- **Frontend:** `fund_id` from matrix metadata. Grid shows numeric value. OK.

### Revenue projection (`revenue_projection.build`)

- **Backend:** Returns `{ value, columns_to_create, chart_to_create }`. Registry MULTI_COLUMN transform passes these through to metadata; frontend creates columns and optional chart from metadata.
- **Grid:** Trigger cell value + new columns populated from `metadata.columns_to_create`. OK.

### Market comparables (`market.find_comparables`)

- **Backend:** Returns `{ comparables, citations }`. Registry ARRAY transform → value = count, metadata has structured_array/citations.
- **Frontend:** buildActionInputs fills company/sector/geography/arr; limit 10. Grid shows count and can show list/citations. OK.

### NAV (e.g. `nav.calculate`, `nav.timeseries`)

- **Backend:** Return `nav` or `{ series, final_value }` etc. Registry NUMBER or TIME_SERIES transform; NAV branch in `_extract_default_value` uses `nav` / `value`.
- **Grid:** Numeric or time series + sparkline from `metadata.time_series`. OK.

### Follow-on strategy (`followon_strategy.recommend`)

- **Backend:** Returns `strategy`, `recommendation`, etc. Registry uses `output_transform="strategy"` → value is strategy text.
- **Grid:** Text in cell. OK.

### Debt, scoring, gap_filler (OBJECT, no output_transform)

- **Backend:** Now covered by registry `_extract_default_value` and (for debt/scoring) router adding `value` so the grid always gets a primary value when the service succeeds.
- **Grid:** Cell shows the extracted value (e.g. total_debt, overall_score, or gap_filler summary). OK.

---

## What “writing to the grid” means here

- **Numeric/text cells:** `response.value` and `response.display_value` are written to the trigger cell; user sees the number or text.
- **Chart cells:** Same cell gets a value (e.g. “sankey: DPI Flow”) and `metadata.chart_config`. The **visible chart** is rendered from ChartViewport / MatrixInsights when they read `cell.metadata?.chart_config`. So “works and writes to the grid” means: backend returns chart_config in metadata, frontend stores it and the chart UI consumes it.
- **Multi-column (e.g. revenue projection):** Trigger cell value + new columns created and filled from `metadata.columns_to_create`.
- **Array (e.g. comparables):** Trigger cell value = count (or similar); detailed list is in metadata/raw_output for tooltips/panels.

So document extraction, valuation, DPI Sankey, charts, and the other services **do** write to the grid when:
1. Backend returns the right shape (value + metadata where needed).
2. Registry transforms that into the contract (value, displayValue, metadata with chart_config / columns_to_create / time_series / etc.).
3. Frontend has the right inputs (e.g. `document_id` for document, `fund_id` for DPI Sankey) and applies the response to the cell and optional chart/columns.

The only gap identified was **document_id** not being passed from the row when running document actions from the generic dropdown; that is fixed by adding document input wiring in `buildActionInputs`.

---

## Checklist: high-value actions

| Action type              | Registry expects (value key)     | Backend return shape              | Frontend inputs              | Writes to grid? |
|--------------------------|-----------------------------------|-----------------------------------|-------------------------------|------------------|
| valuation_engine.*       | fair_value                        | dict with fair_value              | company_id, row data          | Yes              |
| fund_metrics.calculate   | total_nav                         | dict with total_nav               | fund_id                      | Yes              |
| followon_strategy.recommend | strategy                       | dict with strategy                | company_id, fund_id           | Yes              |
| nav.*                    | nav or value                      | dict with nav / number            | company_id, fund_id           | Yes              |
| document.extract/analyze | value (or summary)               | dict with value, summary          | **document_id** (now from row or upload) | Yes (with doc input fix) |
| debt                     | total_debt / value                | dict + value                      | company_id, row data          | Yes              |
| scoring.*                | overall_score / value             | dict + value                      | company_id, row data          | Yes              |
| gap_filler.*             | value/score/overall_score/etc.    | dict from service                 | company_id, row data          | Yes              |
| revenue_projection.build | value, columns_to_create, chart   | dict with these                   | row data                      | Yes              |
| chart_intelligence.generate | type, title (chart_config)     | dict type, title, data            | data, chart_type              | Yes (chart in viewport) |
| portfolio.dpi_sankey     | chart_config                      | type, title, data, renderType     | fund_id                      | Yes (chart in viewport) |
| market.find_comparables  | list / comparables                | comparables, citations            | company, sector, geography   | Yes (count + list) |

---

## Files touched (summary)

- **Backend**
  - `backend/app/services/cell_action_registry.py`: extended `_extract_default_value` for document, debt, scoring, gap_filler.
  - `backend/app/api/endpoints/cell_actions.py`: debt and scoring branches now include `value` in the returned dict.
- **Frontend**
  - `frontend/src/components/matrix/CellDropdownRenderer.tsx`: add `document_id` (and optional `extraction_type`) in `buildActionInputs` for `document.extract` / `document.analyze` from a row column when present.

Nothing else was changed for “no fallbacks, real services only”; the above is what ensures document extraction, valuation methods, DPI Sankey, charts, and other services actually work and write to the grid outside the deck/memo feature.
