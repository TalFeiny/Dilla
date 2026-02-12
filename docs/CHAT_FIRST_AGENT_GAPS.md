# Chat-First Actions and Suggestions — Implementation Gap Analysis

**Plan:** [chat-first_actions_and_suggestions_dbb5abbe.plan.md](/.cursor/plans/chat-first_actions_and_suggestions_dbb5abbe.plan.md)  
**Checked:** Full agent flow (backend → frontend → suggestions → accept/reject → grid refresh).

---

## Summary

| Area | Status | Notes |
|------|--------|--------|
| Phase 1: Chat as primary entry | **Mostly done** | Backend maps grid-run-valuation/pwerm; parseGridIntent covers value/run/extract. One small backend gap. |
| Phase 2: Reduce redundant panels | **Done** | Toasts say "review in chat"; no "Charts panel" found. |
| Phase 3: Suggestions in chat | **Done** | Suggestions in chat, rowId mapping, batch upload polling. |
| Phase 4: Accept/Reject → grid | **Done** | Accept calls POST cells via suggestions API; refreshMatrix listener refetches. |
| Phase 5: Run → Suggestion → Accept → Grid | **Done** | handleGridCommandsFromBackend → runActionWrapper → addServiceSuggestion → refresh; accept persists via API. |

---

## Phase 1: Chat as Primary Action Entry Point

### 1.1 Backend: Grid-run-* selection for valuation/PWERM

- **Done:** `tool_to_skill` (unified_mcp_orchestrator.py ~1268) maps all `GRID_ACTION_MAP` keys; planning prompt (1220–1221) tells LLM to use `grid-run-valuation` / `grid-run-pwerm` when user asks to run valuation or PWERM for companies.
- **Done:** `_build_grid_commands_for_run()` (618–638) builds `grid_commands` with `action: "run"`, `rowId`, `columnId`, `actionId`; `_get_target_row_ids()` uses `matrix_context.rowIds` / `companyNames`; grid-run-* skills append to `shared_data["grid_commands"]` (1683–1687).
- **Gap (minor):** Planning prompt lists only `grid-run-valuation` and `grid-run-pwerm`. For "extract document for @X" to be planned as a grid action, add `grid-run-document-extract` to the planning prompt and tool list (e.g. "extract document for company" → `grid-run-document-extract` with companies).

### 1.2 Frontend: parseGridIntent

- **Done:** `parseGridIntent` in AgentChat.tsx (195–277) handles:
  - "value @X" / "value X" → run valuation
  - "run valuation/pwerm/dcf for @X" → run with correct actionId
  - "extract document for @X" → document.extract
  - Edit intents (edit valuation/ARR for X to $Y)
- **Done:** Grid commands from response are used: `commandsToRun = gridCommandsFromIntent ?? data.result?.grid_commands ?? data.grid_commands ?? []`; when present, they go through `onGridCommandsFromBackend` (437–440).

---

## Phase 2: Reduce Redundant Panels and Buttons

- **Done:** UnifiedMatrix toasts already say "Suggestion added — review in chat" (e.g. 1885, 1974, 2074, 2099). No "Charts panel" string found in matrix-control-panel or UnifiedMatrix.
- **Done:** `refreshSuggestionsAndOpenViewport` handler (516–522) only calls `refreshSuggestions()`; with useAgentPanel, suggestions appear in chat.
- **Done:** Matrix-control-panel does not pass a custom onRunService; UnifiedMatrix uses `runActionWrapper` when `useAgentPanel` is true (3576), so chat is the primary path.

---

## Phase 3: Suggestions Working Correctly

### 3.1 Suggestions in chat

- **Done:** AgentPanel passes `suggestions`, `suggestionsLoading`, `suggestionsError`, `refreshSuggestions`, `onSuggestionAccept`, `onSuggestionReject` to AgentChat (127–132).
- **Done:** AgentChat renders suggestions (1031–1092) with Accept/Reject; Accept calls `onSuggestionAccept(s.id, { rowId, columnId, suggestedValue, sourceDocumentId })`.
- **Done:** `useDocumentSuggestions` uses `buildRowLookup(rows)` (companyId and id); API returns `rowId` as company_id; mapped suggestions use `row.id` so portfolio matrix (row.id === company_id) resolves.

### 3.2 Document upload → suggestions

- **Done:** Batch upload in UnifiedMatrix (456–474) calls `refreshSuggestions()` then polls GET suggestions (2s interval, 3 attempts) when fundId is set.
- **Done:** Cell upload flows through extraction and refresh; `company_id` and `fund_id` are set on processed_documents so GET suggestions returns them.

---

## Phase 4: Accept/Reject Affecting Grid

### 4.1 Accept flow

- **Done:** `handleSuggestionAccept` (UnifiedMatrix 525–581): optimistic update of `matrixData`, then for service suggestions `acceptSuggestionViaApi(suggestionId, fundId)`, for document suggestions `buildApplyPayloadFromSuggestion` + `acceptSuggestionViaApi(suggestionId, applyPayload)`; then `refreshSuggestions()` and `window.dispatchEvent(new CustomEvent('refreshMatrix'))`.
- **Done:** Suggestions API accept (route.ts 1054–1134): service suggestion → lookup pending_suggestions → POST /api/matrix/cells → delete pending row; document suggestion → POST /api/matrix/cells with applyPayload.
- **Done:** POST /api/matrix/cells persists to companies (fieldMap + extra_data) and matrix_edits; returns success.
- **Done:** UnifiedMatrix listens for `refreshMatrix` (781–802), calls `loadPortfolioDataRef.current()` so grid refetches and shows persisted values.

### 4.2 Reject flow

- **Done:** Reject calls `rejectSuggestion(suggestionId, fundId)` then `refreshSuggestions()`; no grid update needed.

---

## Phase 5: Run Action → Suggestion → Accept → Grid

### 5.1 handleGridCommandsFromBackend for action 'run'

- **Done:** For `cmd.action === 'run'`, handler calls `runActionWrapper(cmd.actionId, cmd.rowId, cmd.columnId)` (2107).
- **Done:** `runActionWrapper` (1924–1992): executes action via `executeAction`, then `handleCellActionResult`; when suggestBeforeApply and fundId, `handleCellActionResult` calls `addServiceSuggestion` then `refreshSuggestions()` and toast "Suggestion added — review in chat" (1963–1975).

### 5.2 Consolidate onRunService

- **Done:** When useAgentPanel is true, AgentPanel gets `onRunService={runActionWrapper}` (3576); cell dropdown and grid_commands both go through the same path: executeAction → addServiceSuggestion → refreshSuggestions. Suggestions appear in chat.

---

## Recommended Fix (Minor)

**Backend — planning prompt:** Include `grid-run-document-extract` in the planning prompt so that phrases like "extract document for @Acme" produce a plan step with `tool_to_use: "grid-run-document-extract"` and the companies list, and the skill chain emits grid_commands for the frontend.

- File: `backend/app/services/unified_mcp_orchestrator.py`
- In the planning prompt (~1215–1221):
  - Add `grid-run-document-extract` to the `tool_to_use` list and to the "Map tool_to_use to one of: ..." sentence.
  - Add one line: e.g. "When the user asks to extract a document for a company, use tool_to_use \"grid-run-document-extract\" with the company in the \"companies\" field."

---

## Verification Checklist (from plan)

| # | Check | Status |
|---|--------|--------|
| 1 | User types "run valuation for @Acme" in chat → backend returns grid_commands with action "run" → suggestion appears in chat | ✅ Implemented (plan prompt + runActionWrapper + addServiceSuggestion) |
| 2 | User accepts suggestion → grid cell updates; after refresh, persisted value shown | ✅ Accept → API → POST cells → refreshMatrix → loadPortfolioData |
| 3 | User rejects suggestion → suggestion disappears; grid unchanged | ✅ rejectSuggestion + refreshSuggestions |
| 4 | Document upload (chat or cell) → after processing, suggestions appear in chat with cell + citation + reasoning | ✅ Polling after batch upload; GET suggestions returns by company_id/fund_id |
| 5 | No need to use cell dropdown or valuation Dialog for normal flows; chat is sufficient | ✅ Chat path wired; toasts say "review in chat" |
| 6 | Toasts say "review in chat" (not "Charts panel") when AgentPanel is active | ✅ All relevant toasts use "review in chat" |

---

**Conclusion:** The chat-first agent implementation matches the plan with one optional improvement: add `grid-run-document-extract` to the backend planning prompt so "extract document for @X" is planned and emitted as grid_commands when the user expects it from the agent.
