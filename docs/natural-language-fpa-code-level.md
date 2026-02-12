# Natural Language FP&A World Model — Code-Level Implementation

This doc maps the [Natural Language FP&A World Model](.cursor/plans/natural_language_fp&a_world_model_system_34b11228.plan.md) plan to the **actual codebase**: files, request flows, and how new FPA pieces plug into existing services.

---

## 1. End-to-End Request Flow

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│  USER: "What if Company X gets seed extension, then growth slows to 20%,         │
│         then distressed acquisition?"                                            │
└─────────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│  FRONTEND                                                                        │
│  • NaturalLanguageQuery.tsx  →  POST /api/fpa/query  (Next.js API route)         │
└─────────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│  NEXT.JS API  (frontend/src/app/api/fpa/query/route.ts)                          │
│  • Validate body, attach fund_id / user from session                             │
│  • POST → getBackendUrl() + /api/fpa/query                                       │
└─────────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│  BACKEND  (backend/app/api/endpoints/fpa_query.py)                               │
│  POST /api/fpa/query                                                             │
│  • nl_fpa_parser.parse(query) → ParsedQuery                                      │
│  • fpa_query_classifier.route(parsed) → handler key (scenario | forecast | …)    │
│  • fpa_workflow_builder.build(parsed, handler) → Workflow[]                      │
│  • fpa_executor.execute(workflow, context) → results + model_structure           │
│  • Optional: persist to fpa_queries, return model_id if user saves               │
└─────────────────────────────────────────────────────────────────────────────────┘
                                        │
                    ┌───────────────────┴───────────────────┐
                    ▼                                       ▼
┌──────────────────────────────┐         ┌──────────────────────────────────────────┐
│  FPA Executor (per step)     │         │  Existing services (used by executor)     │
│  • Runs workflow steps       │         │  • ValuationEngineService                 │
│  • Resolves step inputs      │         │  • RevenueProjectionService               │
│  • Calls service layer       │         │  • PWERM (pwerm_service, pwerm_comprehensive)│
│  • Collects outputs          │         │  • IntelligentGapFiller                   │
│  • Returns model + results   │         │  • AdvancedCapTable / waterfall           │
└──────────────────────────────┘         └──────────────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│  RESPONSE                                                                        │
│  { parsed_query, workflow, results, model_structure, execution_time_ms }         │
│  model_structure: { steps: [...], formulas: {...}, assumptions: {...} }          │
└─────────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│  FRONTEND                                                                        │
│  • QueryResults.tsx: timeline, before/after, impact waterfall                    │
│  • ModelEditor.tsx: edit formulas/assumptions → PUT /api/fpa/models/:id/formula  │
│  • FPACanvas.tsx: ephemeral graphs, matrix viz                                  │
│  • MatrixCanvas / NL matrix: "Update matrix with these projections"              │
│    → existing MatrixQueryOrchestrator + /api/matrix/cells or unified-brain       │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. File Layout (New vs Existing)

### 2.1 Backend — New Files

| File | Purpose |
|------|---------|
| `backend/app/services/nl_fpa_parser.py` | Parse NL → `ParsedQuery` (entities, events, temporal steps). |
| `backend/app/services/fpa_query_classifier.py` | Route parsed query → `scenario` \| `forecast` \| `valuation` \| `impact` \| `sensitivity` \| `comparison` \| `regression` \| `growth_decay`. |
| `backend/app/services/fpa_workflow_builder.py` | Build `WorkflowStep[]` with `formula`, `assumptions`, `editable`. |
| `backend/app/services/fpa_executor.py` | Run workflow; call ValuationEngine, RevenueProjection, PWERM, etc.; return results + model. |
| `backend/app/services/fpa_model_editor.py` | CRUD for `fpa_models` / `fpa_model_versions`; get/update formulas and assumptions. |
| `backend/app/services/fpa_regression_service.py` | Linear regression, exponential decay, time-series, Monte Carlo, sensitivity sweeps. |
| `backend/app/services/nl_matrix_controller.py` | NL → matrix actions (“show ARR & burn”, “add projected valuation column”); wraps `MatrixQueryOrchestrator`. |
| `backend/app/services/ephemeral_graph_service.py` | Create/serialize ephemeral chart configs (optional backend-side if you store temporary configs). |
| `backend/app/api/endpoints/fpa_query.py` | FastAPI router: `POST /query`, `POST /models`, `GET/PUT /models/:id`, `POST /models/:id/execute`, `POST /regression`, `POST /forecast`. |

### 2.2 Backend — Existing Files to Use

| File | How FPA uses it |
|------|------------------|
| `valuation_engine_service.py` | `ValuationEngineService.calculate_valuation` (DCF, PWERM, etc.) from workflow steps. |
| `revenue_projection_service.py` | `RevenueProjectionService.project_revenue_with_decay` for growth/decay steps. |
| `pwerm_service.py` / `pwerm_comprehensive.py` | Exit scenarios, probability-weighted returns. |
| `intelligent_gap_filler.py` | Infer missing revenue, growth, etc. for workflow inputs. |
| `matrix_query_orchestrator.py` | `process_matrix_query` for matrix-style FPA output; used by `nl_matrix_controller`. |
| `document_query_service.py` | `query_portfolio_documents`, `query_by_metric`; `MatrixQueryType`-like concepts can be reused/extended. |
| `cell_actions.py` + `cell_action_registry` | Reference for “action → service” routing; FPA executor uses services directly but same pattern. |

### 2.3 Frontend — New Files

| File | Purpose |
|------|---------|
| `frontend/src/components/fpa/NaturalLanguageQuery.tsx` | Chat-like UI: input, parse preview, history, templates. |
| `frontend/src/components/fpa/ModelEditor.tsx` | Formula editor, assumption overrides, growth curve editor. |
| `frontend/src/components/fpa/FPACanvas.tsx` | Canvas (e.g. React Flow / D3): scenarios, cascading impacts, ephemeral graphs. |
| `frontend/src/components/fpa/EphemeralGraph.tsx` | Temporary charts (forecast curves, regressions, tornado); not persisted. |
| `frontend/src/components/fpa/MatrixCanvas.tsx` | Canvas matrix with cells, formula viz, sparklines. |
| `frontend/src/components/fpa/QueryResults.tsx` | Timeline, before/after, impact waterfall. |
| `frontend/src/lib/fpa/ephemeral-graphs.ts` | Ephemeral graph config helpers (data → chart options). |
| `frontend/src/app/api/fpa/query/route.ts` | Proxy `POST /api/fpa/query` → backend. |
| `frontend/src/app/api/fpa/models/route.ts` | Proxy CRUD for models. |
| `frontend/src/app/api/fpa/regression/route.ts` | Proxy `POST /api/fpa/regression`. |
| `frontend/src/app/api/fpa/forecast/route.ts` | Proxy `POST /api/fpa/forecast`. |

### 2.4 Frontend — Existing to Reuse

| File | How FPA uses it |
|------|------------------|
| `lib/backend-url.ts` | `getBackendUrl()` for backend proxying. |
| `lib/supabase.ts` | Auth, optional persistence. |
| `app/api/valuation/calculate/route.ts` | Pattern: fetch company → backend valuation → return. |
| `app/api/scenarios/run/route.ts` | Pattern: portfolio + companies → unified-brain / backend. |
| `app/api/matrix/cells/route.ts` | Persist matrix updates from “update matrix with projections”. |
| `lib/matrix/matrix-api-service.ts` | `queryMatrix` (unified-brain); NL matrix control can reuse or extend. |
| Matrix components (`UnifiedMatrix`, etc.) | Embed `MatrixCanvas` or feed FPA-driven matrix data. |

---

## 3. Key Types and Interfaces

### 3.1 Parsed Query (Backend)

```python
# nl_fpa_parser.py
from typing import List, Dict, Any, Optional
from pydantic import BaseModel
from enum import Enum

class StepType(str, Enum):
    FUNDING_EVENT = "funding_event"
    GROWTH_CHANGE = "growth_change"
    EXIT_EVENT = "exit_event"
    REVENUE_PROJECTION = "revenue_projection"
    VALUATION = "valuation"
    CUSTOM = "custom"

class ParsedStep(BaseModel):
    type: StepType
    payload: Dict[str, Any]  # e.g. {"event": "seed_extension", "rd_extension": True}

class ParsedQuery(BaseModel):
    query_type: str  # "multi_step_scenario" | "forecast" | "valuation" | ...
    steps: List[ParsedStep]
    temporal_sequence: List[str]  # ["step1", "step2", "step3"]
    entities: Dict[str, List[str]]  # companies, funds, metrics
    inferred_params: Dict[str, Any]
```

### 3.2 Workflow Step (Backend)

```python
# fpa_workflow_builder.py
class WorkflowStep(BaseModel):
    step_id: str
    name: str
    inputs: Dict[str, Any]       # references to prior outputs or literals
    outputs: List[str]
    formula: str                 # human-readable; maps to service call
    editable: bool
    assumptions: Dict[str, Any]
    service_call: Dict[str, Any] # e.g. {"service": "revenue_projection", "method": "project_revenue_with_decay", "kwargs": {...}}
```

### 3.3 Executor Context

```python
# fpa_executor.py
class ExecutorContext(BaseModel):
    fund_id: Optional[str] = None
    company_ids: Optional[List[str]] = None
    portfolio_snapshot: Optional[Dict[str, Any]] = None  # pre-fetched companies
    model_id: Optional[str] = None
    user_id: Optional[str] = None
```

---

## 4. How the Executor Calls Existing Services

`fpa_executor` runs each `WorkflowStep`. The step’s `service_call` identifies the backend service and method. Example mappings:

| Step type | Service | Method | Notes |
|-----------|---------|--------|-------|
| `revenue_projection` | `RevenueProjectionService` | `project_revenue_with_decay` | Same as cell_actions; pass `base_revenue`, `initial_growth`, `years`, `quality_score`. |
| `valuation` | `ValuationEngineService` | `calculate_valuation` | Build `ValuationRequest` from `ExecutorContext` + step inputs. |
| `pwerm` / exit scenarios | `pwerm_service` / `PWERMComprehensive` | Existing PWERM API | Use portfolio + company payload similar to `scenarios/run`. |
| `gap_fill` | `IntelligentGapFiller` | `infer_missing_data` | Infer revenue, growth, etc. for workflow inputs. |
| `waterfall` | `AdvancedCapTable` / `waterfall_advanced` | `calculate_waterfall`, etc. | For liquidation / distribution steps. |

Executor pseudocode:

```python
# fpa_executor.py (simplified)
class FPAExecutor:
    def __init__(self):
        self.valuation = ValuationEngineService()
        self.revenue = RevenueProjectionService
        self.gap_filler = IntelligentGapFiller()
        # ... pwerm, waterfall, etc.

    async def execute(self, workflow: List[WorkflowStep], ctx: ExecutorContext) -> Dict[str, Any]:
        state = {}
        for step in workflow:
            inputs = self._resolve_inputs(step.inputs, state, ctx)
            if step.service_call["service"] == "revenue_projection":
                out = RevenueProjectionService.project_revenue_with_decay(**inputs)
            elif step.service_call["service"] == "valuation":
                req = self._build_valuation_request(inputs, ctx)
                out = await self.valuation.calculate_valuation(req)
            # ... etc.
            for k in step.outputs:
                state[k] = out
        return {"results": state, "model_structure": self._model_structure(workflow)}
```

---

## 5. API Surface

### 5.1 Backend (FastAPI)

Wire `fpa_query` router in `router_fixed.py`:

```python
# router_fixed.py
"app.api.endpoints.fpa_query": {"prefix": "/fpa", "tags": ["fpa"]},
```

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/fpa/query` | Body: `{ "query": "..." }`. Returns parsed query, workflow, results, model structure. |
| `POST` | `/api/fpa/models` | Create model. Body: `{ "name", "model_type", "model_definition", "formulas", "assumptions" }`. |
| `GET` | `/api/fpa/models/{id}` | Get model. |
| `PUT` | `/api/fpa/models/{id}/formula` | Update one formula. |
| `PUT` | `/api/fpa/models/{id}/assumptions` | Update assumptions. |
| `POST` | `/api/fpa/models/{id}/execute` | Re-run model with current formulas/assumptions. |
| `POST` | `/api/fpa/regression` | Run regression on portfolio/series. |
| `POST` | `/api/fpa/forecast` | Generate forecast with editable params. |

### 5.2 Frontend (Next.js)

- `POST /api/fpa/query` → proxy to `POST ${getBackendUrl()}/api/fpa/query`.
- Same pattern for `/api/fpa/models`, `/api/fpa/regression`, `/api/fpa/forecast` as in valuation / scenarios routes: validate, add `fund_id`/user, proxy to backend, return JSON.

---

## 6. Database Migrations

New tables (as in the plan):

- `fpa_models` — id, name, model_type, model_definition (JSONB), formulas (JSONB), assumptions (JSONB), created_by, fund_id, timestamps.
- `fpa_model_versions` — id, model_id, version_number, model_definition, changed_by, change_description, created_at.
- `fpa_queries` — id, query_text, parsed_query (JSONB), workflow (JSONB), results (JSONB), execution_time, created_by, fund_id, created_at.
- `ephemeral_graphs` (optional) — id, session_id, graph_type, graph_config (JSONB), data (JSONB), expires_at, created_at.

Use `supabase/migrations/` with timestamped filenames, e.g. `20250126_add_fpa_tables.sql`.

---

## 7. NL Matrix Control

“Show me ARR and burn rate”, “Add column for projected valuation”, “Update matrix with these projections”:

- **Backend:** `nl_matrix_controller` interprets NL → structured matrix intent (columns, filters, computed columns). It can call `MatrixQueryOrchestrator.process_matrix_query` and/or return column/cell updates.
- **Frontend:** Either (a) call a new `POST /api/fpa/matrix-control` that returns `{ columns, rows, cellUpdates }` and then apply via existing `POST /api/matrix/cells` and column APIs, or (b) extend `queryMatrix` in `matrix-api-service` to use FPA when the intent is scenario/forecast-driven.
- Reuse `DocumentQueryService.detect_query_type` / `_extract_query_entities` concepts where useful, and extend with FPA-specific intents (e.g. “add projected valuation from scenario X”).

---

## 8. Ephemeral Graphs

- **Frontend:** `EphemeralGraph.tsx` + `lib/fpa/ephemeral-graphs.ts`. Data lives in React state (or session storage). Chart options (e.g. Recharts) built from workflow results (e.g. revenue projection series, sensitivity ticks). No DB write unless “save” is explicitly added.
- **Backend:** `ephemeral_graph_service` is optional. Use it only if you need to generate or store ephemeral configs server-side (e.g. for sharing via link). Otherwise, keep ephemeral purely client-side.

---

## 9. Implementation Order (Aligned with Plan)

1. **Phase 1:** `nl_fpa_parser` + `fpa_query_classifier` (plus `POST /api/fpa/query` stub that returns parsed + classified).
2. **Phase 2:** `fpa_workflow_builder` + `fpa_executor` (wire to ValuationEngine, RevenueProjection, PWERM, etc.).
3. **Phase 3:** `fpa_model_editor` + DB migrations + `GET/PUT /api/fpa/models/...`.
4. **Phase 4:** `FPACanvas` + basic `QueryResults` (timeline, before/after).
5. **Phase 5:** `EphemeralGraph` + `ephemeral-graphs` helpers.
6. **Phase 6:** `MatrixCanvas` + integrate with existing matrix columns/cells.
7. **Phase 7:** `fpa_regression_service` + `POST /api/fpa/regression`, `POST /api/fpa/forecast`.
8. **Phase 8:** `nl_matrix_controller` + NL matrix UX.

---

## 10. Example: One Scenario Through the Stack

1. **User:** “What if R&D is extended in a seed extension, then growth slows to 20%, then distressed acquisition?”
2. **Parser:** `ParsedQuery(query_type="multi_step_scenario", steps=[...], temporal_sequence=[...])`.
3. **Classifier:** `scenario`.
4. **Workflow builder:** Three steps: (1) funding_event + R&D extension, (2) growth_change 20%, (3) exit_event distressed_acquisition. Each step has `formula`, `assumptions`, `service_call`.
5. **Executor:** Load portfolio/company data → run (1) cap table / gap filler if needed, (2) `RevenueProjectionService.project_revenue_with_decay` with new growth, (3) PWERM/waterfall for distressed exit. Populate `state`, build `model_structure`.
6. **API:** Return `{ parsed_query, workflow, results, model_structure }`.
7. **Frontend:** `QueryResults` shows timeline and impacts; `ModelEditor` offers formula/assumption overrides; `EphemeralGraph` draws projection and exit curves; user can trigger “update matrix” via NL matrix control.

This gives a concrete code-level map from the product plan to the repo: **where** each piece lives, **how** FPA reuses ValuationEngine, RevenueProjection, PWERM, MatrixQueryOrchestrator, and **what** to add in what order.
