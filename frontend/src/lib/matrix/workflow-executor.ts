/**
 * Workflow executor: run cell actions across target rows (current / all).
 * Used by in-cell =WORKFLOW("action1,action2", "all") — no popovers.
 *
 * Key feature: result chaining — action N's output is passed as context
 * to action N+1, enabling multi-step workflows like pwerm → dcf.
 */

import {
  executeAction,
  type ActionExecutionResponse,
  type ActionExecutionRequest,
  type MatrixMode,
} from '@/lib/matrix/cell-action-registry';
import { getActionIdForWorkflow } from '@/lib/matrix/workflow-action-map';

export type WorkflowTarget = 'current' | 'all' | 'selected';

/** Accumulated results from previous workflow steps, keyed by actionId. */
export type WorkflowContext = Record<string, ActionExecutionResponse>;

export interface WorkflowRunResult {
  success: boolean;
  processedCount: number;
  results: { rowId: string; columnId: string; actionId: string; response: ActionExecutionResponse }[];
  error?: string;
  /** Per-row workflow context so callers can inspect chained results. */
  contextByRow?: Record<string, WorkflowContext>;
}

export interface RunWorkflowParams {
  actionIds: string[];
  target: WorkflowTarget;
  triggerRowId: string;
  triggerColumnId: string;
  matrixData: {
    rows: { id: string; companyId?: string; cells: Record<string, { value?: unknown }> }[];
    columns: { id: string }[];
    metadata?: { fundId?: string };
  };
  selectedRowIds?: string[]; // Required when target is 'selected'
  fundId?: string;
  mode?: MatrixMode;
}

/**
 * Parse =WORKFLOW("actions", "target") from cell formula.
 * Actions: comma-separated workflow ids or action_ids (e.g. "pwerm,regression" or "valuation_engine.pwerm").
 * Target: "current" | "all" | "selected".
 */
export function parseWorkflowFormula(
  formula: string
): { actionIds: string[]; target: WorkflowTarget } | null {
  const m = /^=WORKFLOW\s*\(\s*["']([^"']+)["']\s*,\s*["'](current|all|selected)["']\s*\)\s*$/i.exec(
    String(formula).trim()
  );
  if (!m) return null;
  const rawActions = m[1].split(',').map((s) => s.trim()).filter(Boolean);
  const actionIds = rawActions.map((a) => {
    if (a.includes('.')) return a;
    return getActionIdForWorkflow(a) ?? a;
  });
  const targetStr = m[2].toLowerCase();
  const target = (targetStr === 'all' ? 'all' : targetStr === 'selected' ? 'selected' : 'current') as WorkflowTarget;
  return { actionIds, target };
}

type ColsLike = { id: string; name?: string }[];

function cellValue(row: { cells?: Record<string, { value?: unknown }> } | null, cols: ColsLike, pattern: RegExp): number {
  if (!row?.cells || !cols.length) return 0;
  const col = cols.find((c) => pattern.test(c.id) || (c.name != null && pattern.test(String(c.name))));
  const v = col ? row.cells[col.id]?.value : undefined;
  const n = typeof v === 'number' ? v : parseFloat(String(v ?? 0));
  return Number.isFinite(n) ? n : 0;
}

function cellStr(row: { cells?: Record<string, { value?: unknown }> } | null, cols: ColsLike, pattern: RegExp): string {
  if (!row?.cells || !cols.length) return '';
  const col = cols.find((c) => pattern.test(c.id) || (c.name != null && pattern.test(String(c.name))));
  const v = col ? row.cells[col.id]?.value : undefined;
  return typeof v === 'string' ? v : v != null ? String(v) : '';
}

/**
 * Extract numeric values from a workflow context response.
 * Flattens nested result objects into a flat key-value map.
 */
function flattenResponse(resp: ActionExecutionResponse): Record<string, unknown> {
  const flat: Record<string, unknown> = {};
  if (!resp) return flat;
  const data = (resp as any).result ?? (resp as any).data ?? resp;
  if (typeof data !== 'object' || data === null) return flat;
  for (const [k, v] of Object.entries(data)) {
    if (v !== null && v !== undefined) {
      flat[k] = v;
    }
  }
  return flat;
}

function buildInputs(
  actionId: string,
  row: { id: string; companyId?: string; cells?: Record<string, { value?: unknown }> },
  columnId: string,
  matrixData: RunWorkflowParams['matrixData'],
  workflowCtx?: WorkflowContext,
): Record<string, unknown> {
  const inputs: Record<string, unknown> = {};
  const fundId = matrixData.metadata?.fundId;
  const companyId = row.companyId;
  const rows = matrixData.rows ?? [];
  const cols = (matrixData.columns ?? []) as ColsLike;
  const r = rows.find((rr) => rr.id === row.id) ?? row;

  if (companyId) inputs.company_id = companyId;
  if (fundId) inputs.fund_id = fundId;

  // --- Merge previous workflow step results into inputs ---
  // This enables chaining: pwerm result feeds into dcf, etc.
  if (workflowCtx && Object.keys(workflowCtx).length > 0) {
    const chainedData: Record<string, unknown> = {};
    for (const [prevActionId, prevResponse] of Object.entries(workflowCtx)) {
      const flat = flattenResponse(prevResponse);
      // Namespace by action: prev_pwerm_valuation, prev_dcf_fair_value, etc.
      const prefix = `prev_${prevActionId.replace(/\./g, '_')}`;
      for (const [k, v] of Object.entries(flat)) {
        chainedData[`${prefix}_${k}`] = v;
      }
      // Also set common fields directly so actions can pick them up
      if (flat.valuation !== undefined || flat.fair_value !== undefined) {
        inputs.prev_valuation = flat.valuation ?? flat.fair_value;
      }
      if (flat.scenarios !== undefined) {
        inputs.prev_scenarios = flat.scenarios;
      }
      if (flat.pwerm_valuation !== undefined) {
        inputs.pwerm_valuation = flat.pwerm_valuation;
      }
    }
    inputs._workflow_context = chainedData;
    inputs._prev_action_ids = Object.keys(workflowCtx);
  }

  if (actionId.startsWith('financial.')) {
    const exitCol = cols.find((c) => /exit|valuation/i.test(c.id));
    const invCol = cols.find((c) => /invest|investment/i.test(c.id));
    if (r?.cells) {
      if (actionId === 'financial.moic' && exitCol && invCol) {
        inputs.exit_value = Number(r.cells[exitCol.id]?.value ?? 0);
        inputs.investment = Number(r.cells[invCol.id]?.value ?? 0);
      }
      if (actionId === 'financial.cagr') {
        const vals = cols.map((c) => Number(r.cells[c.id]?.value ?? 0)).filter((n) => !isNaN(n));
        if (vals.length >= 2) {
          inputs.beginning_value = vals[0];
          inputs.ending_value = vals[vals.length - 1];
          inputs.years = Math.max(1, vals.length - 1);
        }
      }
      if ((actionId === 'financial.irr' || actionId === 'financial.npv') && columnId) {
        const cashFlows = rows.map((rr) => Number(rr.cells[columnId]?.value ?? 0)).filter((n) => !isNaN(n));
        if (cashFlows.length) inputs.cash_flows = cashFlows;
      }
      if (actionId === 'financial.npv') {
        const dr = cellValue(r, cols, /discount|rate/i);
        inputs.discount_rate = dr && Number.isFinite(dr) ? dr : 0.1;
      }
    }
  }

  if (actionId.startsWith('valuation_engine.') || actionId.startsWith('valuation.')) {
    const nameVal = cellStr(r, cols, /company|companyName|^name$/i);
    if (nameVal) {
      inputs.name = nameVal;
      inputs.company_name = nameVal;
    }
    const arrRev = cellValue(r, cols, /arr|revenue|current_arr/i);
    if (arrRev) {
      inputs.revenue = arrRev;
      inputs.arr = arrRev;
      inputs.current_arr_usd = arrRev;
    }
    const sectorVal = cellStr(r, cols, /sector/i);
    if (sectorVal) inputs.sector = sectorVal;
    const growthVal = cellValue(r, cols, /growth|revenueGrowth/i);
    if (growthVal !== undefined && Number.isFinite(growthVal)) {
      inputs.growth_rate = growthVal;
      inputs.revenue_growth_annual_pct = growthVal > 2 ? growthVal : growthVal * 100;
    }
    const stageVal = cellStr(r, cols, /stage|round|time_since|since_round|funnel/i);
    if (stageVal) inputs.stage = stageVal;
    // Use chained valuation from previous step if available, else from grid
    const valuationVal = (inputs.prev_valuation as number) ?? cellValue(r, cols, /valuation|value|currentValuation/i);
    if (valuationVal !== undefined && Number.isFinite(valuationVal)) {
      inputs.last_round_valuation = valuationVal;
      inputs.current_valuation_usd = valuationVal;
    }
    const investedVal = cellValue(r, cols, /invest|raised|total_invested|investmentAmount/i);
    if (investedVal !== undefined && Number.isFinite(investedVal)) {
      inputs.total_raised = investedVal;
      inputs.total_invested_usd = investedVal;
    }
  }

  if (actionId.includes('revenue_projection') || actionId.includes('revenue.projection')) {
    const nameVal = cellStr(r, cols, /company|companyName|^name$/i);
    if (nameVal) inputs.name = nameVal;
    inputs.base_revenue = cellValue(r, cols, /arr|revenue|revenue_|current_arr/i) || 1_000_000;
    inputs.initial_growth = cellValue(r, cols, /growth|revenueGrowth/i) || 0.3;
    inputs.years = Math.max(1, cellValue(r, cols, /years|period/i) || 5);
    inputs.quality_score = 1.0;
  }

  if (actionId.includes('market.') || actionId.includes('find_comparables')) {
    const nameVal = cellStr(r, cols, /company|companyName|^name$/i);
    if (nameVal) {
      inputs.name = nameVal;
      inputs.company_name = nameVal;
    }
    const sectorVal = cellStr(r, cols, /sector/i);
    if (sectorVal) inputs.sector = sectorVal;
    const geoVal = cellStr(r, cols, /geo|location|region|country/i);
    if (geoVal) inputs.geography = geoVal;
    const arrVal = cellValue(r, cols, /arr|revenue|current_arr/i);
    if (arrVal) inputs.arr = arrVal;
    inputs.limit = 10;
  }

  if (actionId.includes('ownership') || actionId.includes('scoring') || actionId.includes('gap_filler') || actionId.includes('score_company') || actionId.includes('debt')) {
    const nameVal = cellStr(r, cols, /company|companyName|^name$/i);
    if (nameVal) {
      inputs.name = nameVal;
      inputs.company_name = nameVal;
    }
    const arrRev = cellValue(r, cols, /arr|revenue|current_arr/i);
    if (arrRev) {
      inputs.revenue = arrRev;
      inputs.arr = arrRev;
      inputs.current_arr_usd = arrRev;
    }
    const sectorVal = cellStr(r, cols, /sector/i);
    if (sectorVal) inputs.sector = sectorVal;
    const growthVal = cellValue(r, cols, /growth|revenueGrowth/i);
    if (growthVal !== undefined && Number.isFinite(growthVal)) {
      inputs.growth_rate = growthVal;
      inputs.revenue_growth_annual_pct = growthVal > 2 ? growthVal : growthVal * 100;
    }
    const valuationVal = (inputs.prev_valuation as number) ?? cellValue(r, cols, /valuation|value|currentValuation/i);
    if (valuationVal !== undefined && Number.isFinite(valuationVal)) {
      inputs.current_valuation_usd = valuationVal;
    }
    const investedVal = cellValue(r, cols, /invest|raised|total_invested|investmentAmount/i);
    if (investedVal !== undefined && Number.isFinite(investedVal)) {
      inputs.investment_amount = investedVal;
      inputs.total_invested_usd = investedVal;
    }
    const exitVal = cellValue(r, cols, /exit|exitValue/i);
    if (exitVal !== undefined && Number.isFinite(exitVal)) inputs.exit_value = exitVal;
  }

  if (actionId === 'chart_intelligence.generate') {
    inputs.context = { rowId: row.id, companyId: row.companyId };
    inputs.chart_type = 'auto';
    const rowData: Record<string, unknown> = {};
    cols.forEach((c) => {
      rowData[c.id] = r?.cells?.[c.id]?.value;
    });
    inputs.data = rowData;
  }
  return inputs;
}

/** Shared helper: build cell-derived inputs for any action. Used by dropdown, panel, workflow executor. */
export { buildInputs as buildActionInputs };

/**
 * Run workflow: execute each action for each target row, chaining results
 * from action N into action N+1 via WorkflowContext.
 *
 * For each row, actions execute sequentially (preserving chain order).
 * Different rows can be processed in parallel for throughput.
 */
export async function runWorkflow(params: RunWorkflowParams): Promise<WorkflowRunResult> {
  const { actionIds, target, triggerRowId, triggerColumnId, matrixData, selectedRowIds, fundId, mode } = params;
  const results: { rowId: string; columnId: string; actionId: string; response: ActionExecutionResponse }[] = [];
  const rows = matrixData.rows ?? [];

  // Determine target rows based on target type
  let targetRows: typeof rows;
  if (target === 'all') {
    targetRows = rows;
  } else if (target === 'selected') {
    if (!selectedRowIds || selectedRowIds.length === 0) {
      return {
        success: false,
        processedCount: 0,
        results: [],
        error: 'No rows selected for workflow execution',
      };
    }
    targetRows = rows.filter((r) => selectedRowIds.includes(r.id));
  } else {
    // 'current'
    targetRows = rows.filter((r) => r.id === triggerRowId);
  }

  const effectiveMode = (mode ?? 'portfolio') as MatrixMode;
  const contextByRow: Record<string, WorkflowContext> = {};

  // Process each row: actions chain sequentially within a row
  for (const row of targetRows) {
    const rowCtx: WorkflowContext = {};
    contextByRow[row.id] = rowCtx;

    for (const actionId of actionIds) {
      try {
        // Pass accumulated context from previous actions for this row
        const inputs = buildInputs(actionId, row, triggerColumnId, matrixData, rowCtx);
        const req: ActionExecutionRequest = {
          action_id: actionId,
          row_id: row.id,
          column_id: triggerColumnId,
          inputs,
          mode: effectiveMode,
          fund_id: fundId ?? matrixData.metadata?.fundId,
          company_id: row.companyId,
        };
        const response = await executeAction(req);
        results.push({ rowId: row.id, columnId: triggerColumnId, actionId, response });
        // Store in workflow context so next action can access it
        rowCtx[actionId] = response;
      } catch (e) {
        const err = e instanceof Error ? e.message : String(e);
        // Don't fail entire workflow — log error and continue to next action
        console.error(`[workflow] Row ${row.id} / ${actionId} failed: ${err}`);
        results.push({
          rowId: row.id,
          columnId: triggerColumnId,
          actionId,
          response: { success: false, error: err } as any,
        });
        // Still continue — partial results are better than total failure
      }
    }
  }

  const failCount = results.filter((r) => (r.response as any)?.error).length;
  return {
    success: failCount === 0,
    processedCount: results.length,
    results,
    contextByRow,
    error: failCount > 0 ? `${failCount} action(s) failed` : undefined,
  };
}


// ---------------------------------------------------------------------------
// Plan-based workflow execution with dependency-aware parallel steps
// ---------------------------------------------------------------------------

export interface PlanStep {
  id: string;
  actionId: string;
  label: string;
  status: 'pending' | 'running' | 'done' | 'failed';
  dependsOn?: string[];
  parallel?: boolean;
}

export type PlanStepUpdateCallback = (stepId: string, status: PlanStep['status'], result?: ActionExecutionResponse) => void;

export interface RunPlanParams {
  steps: PlanStep[];
  rowId: string;
  columnId: string;
  matrixData: RunWorkflowParams['matrixData'];
  fundId?: string;
  mode?: MatrixMode;
  onStepUpdate?: PlanStepUpdateCallback;
}

export interface PlanRunResult {
  success: boolean;
  steps: PlanStep[];
  results: Record<string, ActionExecutionResponse>;
  error?: string;
}

/**
 * Group plan steps into dependency levels for parallel execution.
 * Steps in the same level have no mutual dependencies and can run concurrently.
 */
function topologicalLevels(steps: PlanStep[]): PlanStep[][] {
  const levels: PlanStep[][] = [];
  const completed = new Set<string>();
  let remaining = [...steps];

  while (remaining.length > 0) {
    const level = remaining.filter((s) => {
      if (!s.dependsOn?.length) return true;
      return s.dependsOn.every((dep) => completed.has(dep));
    });

    if (level.length === 0) {
      // Circular dependency or unresolvable — push all remaining
      levels.push(remaining);
      break;
    }

    levels.push(level);
    for (const s of level) completed.add(s.id);
    remaining = remaining.filter((s) => !completed.has(s.id));
  }

  return levels;
}

/**
 * Execute a plan: steps grouped by dependency level, each level runs in parallel.
 * Results from earlier levels are available to later levels via WorkflowContext.
 */
export async function runPlan(params: RunPlanParams): Promise<PlanRunResult> {
  const { steps, rowId, columnId, matrixData, fundId, mode, onStepUpdate } = params;
  const effectiveMode = (mode ?? 'portfolio') as MatrixMode;
  const row = matrixData.rows.find((r) => r.id === rowId) ?? matrixData.rows[0];
  if (!row) {
    return { success: false, steps, results: {}, error: 'No matching row found' };
  }

  const levels = topologicalLevels(steps);
  const workflowCtx: WorkflowContext = {};
  const allResults: Record<string, ActionExecutionResponse> = {};
  const updatedSteps = steps.map((s) => ({ ...s }));

  for (const level of levels) {
    // Execute all steps in this level concurrently
    const promises = level.map(async (step) => {
      const stepRef = updatedSteps.find((s) => s.id === step.id)!;
      stepRef.status = 'running';
      onStepUpdate?.(step.id, 'running');

      try {
        const inputs = buildInputs(step.actionId, row, columnId, matrixData, workflowCtx);
        const req: ActionExecutionRequest = {
          action_id: step.actionId,
          row_id: rowId,
          column_id: columnId,
          inputs,
          mode: effectiveMode,
          fund_id: fundId ?? matrixData.metadata?.fundId,
          company_id: row.companyId,
        };
        const response = await executeAction(req);
        allResults[step.id] = response;
        workflowCtx[step.actionId] = response;
        stepRef.status = 'done';
        onStepUpdate?.(step.id, 'done', response);
      } catch (e) {
        const err = e instanceof Error ? e.message : String(e);
        allResults[step.id] = { success: false, error: err } as any;
        stepRef.status = 'failed';
        onStepUpdate?.(step.id, 'failed');
        console.error(`[plan] Step ${step.id} (${step.actionId}) failed: ${err}`);
      }
    });

    await Promise.all(promises);
  }

  const failCount = updatedSteps.filter((s) => s.status === 'failed').length;
  return {
    success: failCount === 0,
    steps: updatedSteps,
    results: allResults,
    error: failCount > 0 ? `${failCount} step(s) failed` : undefined,
  };
}
