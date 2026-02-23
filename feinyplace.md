d of them then# Matrix System Bug Audit

**Date**: 2026-02-22
**Scope**: Full matrix stack — frontend components, API routes, backend services, cell actions, suggestions pipeline
**Total**: 54 claimed → **18 confirmed real** (0 critical, 5 high, 9 medium, 4 low) — 36 false positives

---

## CRITICAL (7) — Will crash or corrupt data

### C1. Missing import for MAWorkflowService

**File:** `backend/app/api/endpoints/cell_actions.py:1155`

`MAWorkflowService()` used without import. `NameError` at runtime when any M&A action is triggered.

**Fix:**
```python
# Add before line 1155:
from app.services.ma_workflow_service import MAWorkflowService
```

---

### C2. `founderOwnership` not in fieldMap or percentageFields

**File:** `frontend/src/lib/matrix/apply-cell-server.ts:26-76, 228`

Cell edits to founderOwnership silently fail to persist — column not mapped to any DB field.

**Fix:**
```typescript
// In fieldMap (~line 76), add:
founderOwnership: 'founder_ownership',

// In percentageFields array (~line 228), add:
'founderOwnership',
```

---

### C3. Unsafe `parseFloat(raw as string)` without type check

**File:** `frontend/src/lib/matrix/apply-cell-server.ts:248`

Objects/booleans cast to string produce NaN silently.

**Fix:**
```typescript
// Replace:
let n = typeof raw === 'number' ? raw : parseFloat(raw as string);
// With:
let n = typeof raw === 'number'
  ? raw
  : typeof raw === 'string'
    ? parseFloat(raw)
    : (raw && typeof raw === 'object' && 'value' in (raw as Record<string, unknown>))
      ? parseFloat(String((raw as Record<string, unknown>).value))
      : NaN;
```

---

### C4. Pagination total returns current page count

**File:** `frontend/src/app/api/documents/route.ts:262-263`

`total` and `hasMore` use `transformedData.length` (page size) instead of actual total.

**Fix:**
```typescript
// Before the main query, add a count query:
const { count: totalCount } = await supabaseService
  .from('documents')
  .select('id', { count: 'exact', head: true })
  .eq('fund_id', fundId);

// Replace lines 262-263:
total: totalCount ?? transformedData.length,
hasMore: offset + limit < (totalCount ?? 0),
```

---

### C5. State closure bug in valuation picker

**File:** `frontend/src/components/matrix/CellDropdownRenderer.tsx:1047-1082`

`setValuationPicker(null)` at line 1054, then `valuationPicker.rowId` referenced at lines 1057/1075. If React batches the state update before the async block at line 1072, `valuationPicker` could be null.

**Fix:** Capture values before clearing state:
```typescript
// At start of onClick, before setValuationPicker(null):
const pickerRowId = valuationPicker!.rowId;
const pickerColumnId = valuationPicker!.columnId;
setValuationPicker(null);
// Use pickerRowId/pickerColumnId everywhere below
```

---

### C6. cellRendererParams recreated every render

**File:** `frontend/src/components/matrix/AGGridMatrix.tsx:533-598`

Arrow function in `cellRendererParams` causes AG Grid to recreate cell renderers on every parent re-render — losing hover/selection state and causing cell flash.

**Fix:** Extract the factory to a stable callback. Since all callbacks already use `propsRef.current`, the function body doesn't depend on props:
```typescript
// Move outside the columnDefs useMemo, wrap in useCallback with [] deps:
const cellRendererParamsFactory = useCallback((params: any, colId: string) => ({
  rowId: params.data?.id,
  columnId: colId,
  onSourceChange: (rowId: string, columnId: string, source: string) => {
    propsRef.current.onSourceChange?.(rowId, columnId, source);
  },
  // ... rest of callbacks using propsRef.current ...
}), []);

// In columnDefs:
cellRendererParams: (params: any) => cellRendererParamsFactory(params, col.id),
```

---

### C7. Invalid column mapping (`pwerm` → `valuation`)

**File:** `frontend/src/app/api/matrix/suggestions/route.ts:652`

`pwerm` is not a real column. Mapping it to `valuation` causes wrong current-value comparisons for suggestions.

**Fix:** Delete the line:
```typescript
// DELETE:
pwerm: 'valuation',
```

---

## HIGH (16) — Wrong data, wrong routing, race conditions

### H1. Substring collision `'ma'` in action routing

**File:** `backend/app/api/endpoints/cell_actions.py:1145`

`'ma' in service_name` matches "market_intelligence", "market_timing", "company_metrics" etc.

**Fix:**
```python
# Replace:
elif 'ma' in service_name or 'ma' in action_id:
# With:
elif service_name.startswith('ma.') or service_name == 'ma' or action_id.startswith('ma.'):
```

---

### H2. Substring collision `'fund'`/`'ownership'`

**File:** `backend/app/api/endpoints/cell_actions.py:1102, 1214`

Overlapping `in` checks cause misrouting.

**Fix:** Replace all substring checks with prefix matching:
```python
elif service_name.startswith('ownership.') or action_id.startswith('ownership.'):
# ...
elif service_name.startswith('fund.') or action_id.startswith('fund.'):
```

Better long-term: refactor entire dispatch to a dict-based registry keyed on `service_name.split('.')[0]`.

---

### H3. CAGR no-op math

**File:** `backend/app/services/chart_data_service.py:282`

`(yoy_growth - 1) * 100 / 100.0` cancels out to `yoy_growth - 1`. The multiply/divide is dead code.

**Fix:**
```python
# Replace:
cagr = (yoy_growth - 1) * 100 / 100.0 if years_to_target > 0 else 0.2
# With:
cagr = (yoy_growth - 1) if years_to_target > 0 else 0.2
```

---

### H4. Percentage normalization only for `grossMargin`

**File:** `frontend/src/lib/matrix/apply-cell-server.ts:250`

Only `grossMargin` gets 0-100 → 0-1 conversion. All other % fields skip it.

**Fix:**
```typescript
// Replace:
if (n > 1 && column_id === 'grossMargin') n = n / 100;
// With:
if (n > 1) n = n / 100;
```

---

### H5. Revenue growth fields in `numberFields` instead of `percentageFields`

**File:** `frontend/src/lib/matrix/apply-cell-server.ts:225`

`revenueGrowthMonthly` and `revenueGrowthAnnual` treated as plain numbers — 30% stored as 30, displayed as 3000%.

**Fix:** Move from `numberFields` to `percentageFields`.

---

### H6. Customer segment % fields in `numberFields`

**File:** `frontend/src/lib/matrix/apply-cell-server.ts:225`

Same 100x bug for `customerSegmentEnterprise`, `customerSegmentMidmarket`, `customerSegmentSme`.

**Fix:** Move from `numberFields` to `percentageFields`.

---

### H7. Empty string fallback instead of null

**File:** `frontend/src/lib/matrix/apply-cell-server.ts:137-143`

Object unwrapping falls back to `''` instead of `null` — ambiguous for numeric field parsing.

**Fix:** Change fallback from `''` to `null`.

---

### H8. Infinite useEffect loop risk

**File:** `frontend/src/components/matrix/AGGridMatrix.tsx:749-784`

`actionInProgressRef` (a ref) in dependency array. Refs don't trigger re-renders — including them is pointless and can cause instability.

**Fix:** Remove `actionInProgressRef` from the dependency array. Keep reading `.current` inside the effect body.

---

### H9. `node.isSelected()` without null check

**File:** `frontend/src/components/matrix/CellDropdownRenderer.tsx:668`

Crashes if AG Grid passes undefined node during grid destruction.

**Fix:** `node?.isSelected?.()`.

---

### H10. Upload promise never rejects properly

**File:** `frontend/src/components/matrix/MatrixCellFeatures.tsx:346-403`

XHR load handler's inner try/catch resolves even on extraction failure.

**Fix:** Add `reject(err)` in the catch block instead of silently continuing.

---

### H11. Race condition in fetchSuggestions — no AbortController

**File:** `frontend/src/components/matrix/DocumentSuggestions.tsx:330-394`

Rapid `fundId` changes can cause stale responses to overwrite fresh data.

**Fix:** Add AbortController:
```typescript
const abortRef = useRef<AbortController | null>(null);

const fetchSuggestions = useCallback(async () => {
  abortRef.current?.abort();
  const controller = new AbortController();
  abortRef.current = controller;
  const response = await fetch(url, { signal: controller.signal });
  // ...
}, [deps]);

useEffect(() => () => abortRef.current?.abort(), []);
```

---

### H12. `acceptSuggestionViaApi` failure ignored

**File:** `frontend/src/components/matrix/UnifiedMatrix.tsx:680-685`

API result not checked. Optimistic update stays even when backend rejects.

**Fix:** Check `apiResult.success` — if false, call `refreshSuggestions()` to revert.

---

### H13. Optimistic update race — hardcoded 2s timeout

**File:** `frontend/src/components/matrix/UnifiedMatrix.tsx:706-710`

2s timeout may be too short for slow networks.

**Fix:** Decrement `editInFlightRef` on API response (in the `finally` block), not on a fixed timer.

---

### H14. Document name matching too loose

**File:** `frontend/src/app/api/matrix/suggestions/route.ts:810`

Substring check causes cross-company mis-assignment. "Financial_Report.pdf" matches any company with "financial" in name.

**Fix:** Require minimum candidate length (>=4 chars) and prefer exact matches. Consider Levenshtein distance or token overlap instead.

---

### H15. Silent cleanup failure in batch upload

**File:** `frontend/src/app/api/documents/batch/route.ts:99`

Storage cleanup error swallowed. Failed uploads may be reported as success.

**Fix:** Log the cleanup error, but still throw the original insert error so `Promise.allSettled` captures it as `rejected`.

---

### H16. Agent system prompt references non-existent tools

**File:** `frontend/src/lib/agent-system-prompt.ts:61`

`sparse-grid-enricher`, `batch_valuate`, `batch_enrich` listed but not implemented. Agent errors when calling them.

**Fix:** Remove references to unimplemented tools or implement them.

---

## MEDIUM (22)

### M1. Uninitialized `action` in registry transform

**File:** `backend/app/services/cell_action_registry.py:220-256`

If `get_action()` returns None, elif branches still access `action.output_type`.

**Fix:** Return early after the None check.

---

### M2. Inconsistent error returns in chart_data_service

**File:** `backend/app/services/chart_data_service.py` (multiple methods)

Some return `None`, others return error dicts.

**Fix:** Standardize: always return `{"type": chart_type, "data": {}, "error": str(e)}`.

---

### M3. `formatActionOutput` assumes % values are 0-1

**File:** `frontend/src/lib/matrix/cell-action-registry.ts:219-227`

Services returning 0-100 values display as 4500%.

**Fix:** Add smart check: `const pct = value > 1 ? value : value * 100;`.

---

### M4. `isAdvancedChart()` called with undefined type

**File:** `frontend/src/lib/matrix/chart-utils.ts:49`

Crashes on `.toLowerCase()` if `chartConfig.type` is undefined.

**Fix:** Guard: `chartConfig.type && isAdvancedChart(chartConfig.type)`.

---

### M5. Object cell values stringified as `[object Object]`

**File:** `frontend/src/lib/matrix/workflow-executor.ts:74`

Unwrap object before stringifying: check for `.value` property first.

**Fix:**
```typescript
let n: number;
if (typeof v === 'number') {
  n = v;
} else if (v && typeof v === 'object' && 'value' in v) {
  n = parseFloat(String((v as Record<string, unknown>).value));
} else {
  n = parseFloat(String(v ?? 0));
}
return Number.isFinite(n) ? n : 0;
```

---

### M6. No pre-validation in `rejectSuggestion`

**File:** `frontend/src/lib/matrix/suggestion-helpers.ts:113-146`

Validate `suggestionId` and `fundId` are non-empty before making API call.

**Fix:**
```typescript
if (!suggestionId?.trim() || !fundId?.trim()) {
  return { success: false, error: 'suggestionId and fundId are required' };
}
```

---

### M7. Runway column type mismatch

**File:** `frontend/src/components/matrix/AGGridMatrix.tsx:109`

Defined as `'number'` but COLUMN_FORMAT_MAP has `'runway'` with "m" suffix formatting.

**Fix:** Add runway-specific valueFormatter in the number case.

---

### M8. gridApi used after isDestroyed check

**File:** `frontend/src/components/matrix/AGGridMatrix.tsx:705-727`

Add guard before each subsequent API call.

---

### M9. formulaEngine null check

**File:** `frontend/src/components/matrix/AGGridMatrix.tsx:361-367`

Already guarded with `&& formulaEngine` — verify the check is in the right position.

---

### M10. Edit error keeps component stuck in edit mode

**File:** `frontend/src/components/matrix/MatrixFieldCard.tsx:99-107`

**Fix:** Call `setIsEditing(false)` in the catch block.

---

### M11. XHR listeners not cleaned up on unmount

**File:** `frontend/src/components/matrix/MatrixCellFeatures.tsx:336-407`

**Fix:** Store XHR in a ref, call `xhr.abort()` on unmount.

---

### M12. Callback after async without mounted check

**File:** `frontend/src/components/matrix/MatrixCellFeatures.tsx:357-379`

**Fix:** Add `mountedRef` pattern.

---

### M13. Stale closure in workflow picker

**File:** `frontend/src/components/matrix/CellDropdownRenderer.tsx:1137-1147`

**Fix:** Use functional setState: `setWorkflowPicker(prev => ...)`.

---

### M14. File input ref never cleaned up

**File:** `frontend/src/components/matrix/CellDropdownRenderer.tsx:797-814`

**Fix:** Clear ref on unmount in useEffect cleanup.

---

### M15. Waterfall panel: no AbortController + silent error

**File:** `frontend/src/components/matrix/custom-renderers/EnhancedMasterDetail.tsx:509-529`

**Fix:** Add error state + AbortController (same pattern as H11).
```typescript
const [error, setError] = useState<string | null>(null);

const handleCalculate = async () => {
  setLoading(true);
  setError(null);
  try {
    const res = await fetch(/* ... */);
    if (!res.ok) throw new Error(`Failed: ${res.status}`);
    const data = await res.json();
    setResult(data.result || data);
  } catch (e: any) {
    setError(e.message || 'Calculation failed');
    setResult(null);
  } finally {
    setLoading(false);
  }
};
```

---

### M16. `Object.entries(null)` crash in distributions

**File:** `frontend/src/components/matrix/custom-renderers/EnhancedMasterDetail.tsx:531-537`

`result.distributions` can be `null` (not undefined). `Object.entries(null)` throws.

**Fix:** Add `if (!dist || typeof dist !== 'object') return [];`.

---

### M17. `setState` inside `useMemo`

**File:** `frontend/src/components/matrix/UnifiedMatrix.tsx:445-452`

Calling `setOptimisticallyHiddenIds` inside a `useMemo` causes re-render during render.

**Fix:** Split into pure `useMemo` + separate `useEffect` for stale ID cleanup:
```typescript
// Keep useMemo pure:
const visibleSuggestions = useMemo(() => {
  return documentSuggestionsList.filter(s => !optimisticallyHiddenIds.has(s.id));
}, [documentSuggestionsList, optimisticallyHiddenIds]);

// Separate effect for cleanup:
useEffect(() => {
  const serverIds = new Set(documentSuggestionsList.map(s => s.id));
  setOptimisticallyHiddenIds(prev => {
    const next = new Set(prev);
    for (const id of prev) {
      if (!serverIds.has(id)) next.delete(id);
    }
    return next.size === prev.size ? prev : next;
  });
}, [documentSuggestionsList]);
```

---

### M18. Unknown rowId suggestions silently dropped

**File:** `frontend/src/components/matrix/DocumentSuggestions.tsx:353-356`

**Fix:** Add `console.debug` log for dropped suggestions.

---

### M19. All-zero treemap shows nothing

**File:** `frontend/src/components/matrix/custom-renderers/TreemapRenderer.tsx:225-233`

**Fix:** Render empty-state message when all values are <= 0.

---

### M20. Field naming inconsistency (camelCase vs snake_case)

**File:** `frontend/src/app/api/portfolio/[id]/companies/route.ts:76-124`

GET returns snake_case from DB, POST returns camelCase. Frontend can't rely on either.

**Fix:** Apply `toCamelCase` transform to GET response.

---

### M21. Async processing fallback always returns true

**File:** `frontend/src/app/api/documents/route.ts:18`

**Fix:** Check `asyncRes.ok` before returning true.

---

### M22. Column tier list hardcoded in suggestions

**File:** `frontend/src/app/api/matrix/suggestions/route.ts:524-537`

New DB columns silently excluded.

**Fix:** Use `SELECT *` as first tier.

---

## LOW (9)

### L1. MutationObserver cleanup during SSR

**File:** `frontend/src/components/matrix/AGGridMatrix.tsx:842-850`

Move observer creation inside the `typeof document !== 'undefined'` guard.

---

### L2. Citation data mapped without type check

**File:** `frontend/src/components/matrix/MatrixFieldCard.tsx:252`

Filter out null/non-object elements before mapping.

---

### L3. Division by zero in cap table summary

**File:** `frontend/src/components/matrix/MatrixCellFeatures.tsx:764`

Guard: `if (evolution.length === 0) return 'No rounds';`.

---

### L4. Row ID millisecond collision

**File:** `frontend/src/components/matrix/CustomRowBuilder.tsx:121`

Use `crypto.randomUUID()` instead of `Date.now()`.

---

### L5. Missing null check on chart data

**File:** `frontend/src/components/matrix/UnifiedMatrix.tsx:416`

Add `if (!c?.data) continue;` in chart iteration.

---

### L6. Confidence range not validated

**File:** `frontend/src/components/matrix/DocumentSuggestions.tsx:250`

Clamp: `Math.min(100, Math.max(0, Math.round((confidence ?? 0) * 100)))`.

---

### L7. `extractCellValue` inconsistent null/undefined

**File:** `frontend/src/lib/matrix/cell-action-registry.ts:305-351`

Return `value ?? null` at end to normalize.

---

### L8. setInterval not captured for cleanup

**File:** `frontend/src/app/api/documents/route.ts:133`

Capture in module-level variable, guard against duplicate intervals.

---

### L9. Invalid action gets success response

**File:** `frontend/src/app/api/matrix/suggestions/route.ts:1677`

Return 400 error for unknown actions instead of generic success.

---

## Implementation Order

| Phase | Bugs | Focus |
|-------|------|-------|
| **1 — Data corruption** | C1, C2, C3, C5, H4, H5, H6, H7 | apply-cell-server.ts cluster + missing import |
| **2 — Routing & suggestions** | C4, C7, H1, H2, H14, M1, M17, L9 | Action dispatch + suggestion pipeline |
| **3 — Race conditions** | H8, H10, H11, H12, H13, M11, M12, M15 | AbortControllers + async cleanup |
| **4 — Display & UX** | H3, H9, H16, M3, M4, M5, M7, M10, M16, M19 | Formatters + chart config + error states |
| **5 — Hardening** | All remaining M* + L* | Validation, cleanup, edge cases |
