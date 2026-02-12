# Backend → Frontend Grid Integration

## System You Built

You have a **grid command protocol** so the backend (or API) can tell the frontend what to do:

1. **Backend** returns a `commands` array of strings, e.g. `grid.write("A1", 100)`, `grid.formula("B2", "=A1*2")`.
2. **Frontend** parses and runs them against the **Grid API** (`window.gridApi` / `window.grid`).

## What’s Wired

| Layer | Role |
|-------|------|
| **Grid API** | `grid-api-manager.ts`, `useGridAPI`, `GridContext` – singleton, `write` / `formula` / `style` / `chart` etc. |
| **Execution** | `GridContext.executeCommand` / `executeBatch` – parse `grid.method(...)`, call Grid API |
| **Spreadsheet UIs** | `EnhancedSpreadsheet` (management-accounts, financial-models), `AgentDataGrid` – register grid, expose on `window` |
| **Agent runner** | `AgentRunner` – calls `/api/agent/unified-brain` with `outputFormat: 'spreadsheet'`, reads `commands` from response, runs `executeBatch(commands)` |
| **Spreadsheet-direct** | `/api/agent/spreadsheet-direct` – Next.js route, calls Claude, returns `grid.*` commands only |

## Command Contract

- **Format**: `grid.method("arg1", arg2, ...)` — one call per line.
- **Supported**: `grid.write`, `grid.formula`, `grid.style`, `grid.format`, `grid.clear`, `grid.link`, `grid.writeRange`, `grid.createChart`, `grid.createChartBatch`, etc.
- **Parser**: `GridContext` uses `grid\.(\w+)\((.*)\)$`; `SecureCommandExecutor` strips `grid.` then parses. Both expect the `grid.` prefix.

## Where It’s Used vs Not Used

- **Uses grid commands**: Agent runner, spreadsheet-direct, any client that sends `commands` into `executeBatch` or `EnhancedSpreadsheet`’s `commands` prop.
- **Does not use grid commands**: **Matrix** (UnifiedMatrix, AGGridMatrix, portfolio/matrix-control-panel).

## Matrix vs Grid

Matrix cell actions use a **different** path:

- **Matrix**: User clicks cell dropdown → `executeAction` → `POST /api/cell-actions/actions/{id}/execute` → backend runs service → returns `{ value, display_value, metadata }` → `handleCellActionResult` updates **matrix React state** (`setMatrixData`).
- **Grid**: Backend (or API) returns **commands** → frontend runs them on the **Grid API** → spreadsheet state updates.

So:

- **Backend → frontend** = grid **commands** executed by the grid layer.
- **Matrix** = **frontend → backend** request/response, then frontend applies the result to matrix state. No grid commands involved.

Matrix components do not use `GridContext`, `useGridAPI`, or `window.gridApi`.

## Backend Command Format Mismatch

- **spreadsheet-direct** (Next.js): Emits `grid.write(...)`, `grid.formula(...)` etc. → **compatible** with frontend.
- **Python unified-brain** (`output_format=spreadsheet`): `unified_mcp_orchestrator` uses `sheet.write(...)`, `sheet.formula(...)` and **chaining** (e.g. `.style(...)`). Frontend only parses `grid.*` and one method per command → **incompatible**.

So the backend→frontend **system** works when commands are `grid.*` (e.g. from spreadsheet-direct). The Python orchestrator’s spreadsheet output would need to emit `grid.*` and drop chaining to work with the existing frontend.

## Summary

| Question | Answer |
|----------|--------|
| Backend→frontend system exists? | Yes: commands → GridContext / Grid API. |
| Where is it used? | Agent runner, spreadsheet-direct, EnhancedSpreadsheet `commands` prop. |
| Is Matrix hooked up to it? | No. Matrix uses cell-actions + `handleCellActionResult`, not grid commands. |
| Frontend actions well integrated? | **Within Matrix**: yes (dropdown → executeAction → backend → handleCellActionResult). **With Grid**: Matrix never uses the grid command system. |

To **unify** things you could, for example:

- Have cell-action results optionally **emit grid commands** (e.g. for a shared spreadsheet view), or
- Add a **matrix-aware** backend flow that returns `grid.*` commands and run them via the existing grid layer where the matrix is embedded alongside a grid.
