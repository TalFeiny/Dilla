/**
 * Workflow executor: run cell actions across target rows (current / all).
 * Used by in-cell =WORKFLOW("action1,action2", "all") — no popovers.
 */

import {
  executeAction,
  type ActionExecutionResponse,
  type ActionExecutionRequest,
  type MatrixMode,
} from '@/lib/matrix/cell-action-registry';
import { getActionIdForWorkflow } from '@/lib/matrix/workflow-action-map';

export type WorkflowTarget = 'current' | 'all' | 'selected';

export interface WorkflowRunResult {
  success: boolean;
  processedCount: number;
  results: { rowId: string; columnId: string; response: ActionExecutionResponse }[];
  error?: string;
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

function buildInputs(
  actionId: string,
  row: { id: string; companyId?: string; cells?: Record<string, { value?: unknown }> },
  columnId: string,
  matrixData: RunWorkflowParams['matrixData']
): Record<string, unknown> {
  const inputs: Record<string, unknown> = {};
  const fundId = matrixData.metadata?.fundId;
  const companyId = row.companyId;
  const rows = matrixData.rows ?? [];
  const cols = (matrixData.columns ?? []) as ColsLike;
  const r = rows.find((rr) => rr.id === row.id) ?? row;

  if (companyId) inputs.company_id = companyId;
  if (fundId) inputs.fund_id = fundId;

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
    const valuationVal = cellValue(r, cols, /valuation|value|currentValuation/i);
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
    const valuationVal = cellValue(r, cols, /valuation|value|currentValuation/i);
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
 * Run workflow: execute each action for each target row, collect results.
 */
export async function runWorkflow(params: RunWorkflowParams): Promise<WorkflowRunResult> {
  const { actionIds, target, triggerRowId, triggerColumnId, matrixData, selectedRowIds, fundId, mode } = params;
  const results: { rowId: string; columnId: string; response: ActionExecutionResponse }[] = [];
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

  for (const row of targetRows) {
    for (const actionId of actionIds) {
      try {
        const inputs = buildInputs(actionId, row, triggerColumnId, matrixData);
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
        results.push({ rowId: row.id, columnId: triggerColumnId, response });
      } catch (e) {
        const err = e instanceof Error ? e.message : String(e);
        return {
          success: false,
          processedCount: results.length,
          results,
          error: `Row ${row.id} / ${actionId}: ${err}`,
        };
      }
    }
  }

  return {
    success: true,
    processedCount: results.length,
    results,
  };
}
