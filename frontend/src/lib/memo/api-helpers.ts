/**
 * API Helpers — Correct API callers with correct paths and request shapes.
 *
 * Every FPA endpoint that exists in the backend is represented here.
 * Sections import from here instead of making raw fetch calls.
 *
 * All endpoints take company_id as the primary identifier.
 */

const json = (body: any) => ({
  method: 'POST' as const,
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(body),
});

// ---------------------------------------------------------------------------
// P&L (/fpa/pnl — GET)
// ---------------------------------------------------------------------------

export async function fetchPnl(
  companyId: string,
  start?: string,
  end?: string,
  months: number = 24,
) {
  const params = new URLSearchParams({ company_id: companyId, months: String(months) });
  if (start) params.set('start', start);
  if (end) params.set('end', end);
  const res = await fetch(`/api/fpa/pnl?${params}`, {
    method: 'GET',
    headers: { 'Content-Type': 'application/json' },
  });
  if (!res.ok) throw new Error(`P&L fetch failed: ${res.status}`);
  return res.json();
  // -> { periods, rows, forecastStartIndex, ratios?, ... }
}

// ---------------------------------------------------------------------------
// Balance Sheet (/fpa/balance-sheet — GET)
// ---------------------------------------------------------------------------

export async function fetchBalanceSheet(
  companyId: string,
  start?: string,
  end?: string,
) {
  const params = new URLSearchParams({ company_id: companyId });
  if (start) params.set('start', start);
  if (end) params.set('end', end);
  const res = await fetch(`/api/fpa/balance-sheet?${params}`, {
    method: 'GET',
    headers: { 'Content-Type': 'application/json' },
  });
  if (!res.ok) throw new Error(`Balance Sheet fetch failed: ${res.status}`);
  return res.json();
  // -> { periods, rows, totals }
}

// ---------------------------------------------------------------------------
// Cash Flow (/fpa/cash-flow — GET)
// ---------------------------------------------------------------------------

export async function fetchCashFlow(
  companyId: string,
  start?: string,
  end?: string,
) {
  const params = new URLSearchParams({ company_id: companyId });
  if (start) params.set('start', start);
  if (end) params.set('end', end);
  const res = await fetch(`/api/fpa/cash-flow?${params}`, {
    method: 'GET',
    headers: { 'Content-Type': 'application/json' },
  });
  if (!res.ok) throw new Error(`Cash Flow fetch failed: ${res.status}`);
  return res.json();
  // -> { periods, rows }
}

// ---------------------------------------------------------------------------
// Metrics (/fpa/metrics — GET)
// ---------------------------------------------------------------------------

export async function fetchMetrics(companyId: string) {
  const params = new URLSearchParams({ company_id: companyId });
  const res = await fetch(`/api/fpa/metrics?${params}`, {
    method: 'GET',
    headers: { 'Content-Type': 'application/json' },
  });
  if (!res.ok) throw new Error(`Metrics fetch failed: ${res.status}`);
  return res.json();
  // -> { metrics: ComputedMetric[] }
}

// ---------------------------------------------------------------------------
// Forecast (/fpa/forecast)
// ---------------------------------------------------------------------------

export async function buildForecast(
  companyId: string,
  params?: Record<string, any>,
) {
  const res = await fetch(`/api/fpa/forecast`, json({
    company_id: companyId,
    ...params,
  }));
  if (!res.ok) throw new Error(`Forecast failed: ${res.status}`);
  return res.json();
  // -> { forecast: [...], granularity, periods, budget_ids, assumptions, charts }
}

// ---------------------------------------------------------------------------
// Rolling Forecast (/fpa/rolling-forecast)
// ---------------------------------------------------------------------------

export async function fetchRollingForecast(
  companyId: string,
  window: number = 24,
  granularity: string = 'monthly',
) {
  const params = new URLSearchParams({
    company_id: companyId,
    window: String(window),
    granularity,
  });
  const res = await fetch(`/api/fpa/rolling-forecast?${params}`, {
    method: 'GET',
    headers: { 'Content-Type': 'application/json' },
  });
  if (!res.ok) throw new Error(`Rolling forecast failed: ${res.status}`);
  return res.json();
}

// ---------------------------------------------------------------------------
// AI Narrative (/api/agent/unified-brain)
//
// UnifiedRequest model: { prompt, output_format, context, options }
// There is NO 'action' field. There is NO 'narrate' mode.
// ---------------------------------------------------------------------------

export async function requestNarrative(
  companyId: string,
  sectionType: string,
  dataContext?: Record<string, any>,
): Promise<string> {
  // Backend pulls actuals + forecast from Supabase via pull_company_data
  // and the active branch. We forward the full data context so the AI
  // has real numbers to work with.
  const branchId = dataContext?.branch_id || dataContext?.branchId || null;
  try {
    const res = await fetch(
      `/api/agent/unified-brain`,
      json({
        prompt: `Analyze the ${sectionType.replace(/_/g, ' ')} for this company. Use pull_company_data to get actuals from Supabase${branchId ? ` and execute branch ${branchId} for the forecast` : ' and load the active forecast'}. Identify key trends, inflection points, and risks from the real numbers. Be specific — cite actual figures and periods.`,
        output_format: 'analysis',
        context: {
          company_id: companyId,
          section_type: sectionType,
          branch_id: branchId,
          include_actuals: true,
          include_forecast: true,
          ...(dataContext || {}),
        },
      }),
    );
    if (!res.ok) {
      console.warn(`AI narrative request failed: ${res.status}`);
      return '';
    }
    const data = await res.json();
    return (
      data.result?.narrative ||
      data.result?.content ||
      data.narrative ||
      data.content ||
      (typeof data.result === 'string' ? data.result : '')
    );
  } catch (err) {
    console.warn('AI narrative error:', err);
    return '';
  }
}

// ---------------------------------------------------------------------------
// Cap Table Engine (/api/agent/cap-table-bridge)
// Note the /agent/ prefix — NOT /api/cap-table-bridge
// BuildRequest: { company_id, fund_id, document_id? }
// ---------------------------------------------------------------------------

export async function fetchCapTable(
  companyId: string,
  fundId?: string,
  documentId?: string,
) {
  const res = await fetch(
    `/api/agent/cap-table-bridge`,
    json({ company_id: companyId, fund_id: fundId || '', document_id: documentId }),
  );
  if (!res.ok) throw new Error(`Cap table failed: ${res.status}`);
  return res.json();
}

/** Recalculate cap table from edited share entries */
export async function recalculateCapTable(
  shareEntries: Array<Record<string, any>>,
) {
  const res = await fetch(
    `/api/agent/cap-table-bridge/recalculate`,
    json({ share_entries: shareEntries }),
  );
  if (!res.ok) throw new Error(`Cap table recalculate failed: ${res.status}`);
  return res.json();
}

/** Simulate new financing round + exit waterfall */
export async function simulateCapTable(
  shareEntries: Array<Record<string, any>>,
  investmentAmount: number,
  preMoneyValuation: number,
  optionPoolIncrease: number = 0,
  exitValue?: number,
) {
  const res = await fetch(
    `/api/agent/cap-table-bridge/simulate`,
    json({
      share_entries: shareEntries,
      investment_amount: investmentAmount,
      pre_money_valuation: preMoneyValuation,
      option_pool_increase: optionPoolIncrease,
      exit_value: exitValue,
    }),
  );
  if (!res.ok) throw new Error(`Cap table simulate failed: ${res.status}`);
  return res.json();
}

// ---------------------------------------------------------------------------
// Cascade Analysis — route through unified-brain
// /api/cascade/analyze does NOT exist as a standalone endpoint
// ---------------------------------------------------------------------------

export async function runCascadeAnalysis(
  companyId: string,
  triggerType: string,
  branchId?: string | null,
) {
  const res = await fetch(
    `/api/agent/unified-brain`,
    json({
      prompt: `Analyze cascade effects of a ${triggerType.replace(/_/g, ' ')} trigger event. Show step-by-step dependency chain with financial impact.`,
      output_format: 'analysis',
      context: {
        company_id: companyId,
        analysis_type: 'cascade',
        trigger_type: triggerType,
        branch_id: branchId,
      },
    }),
  );
  if (!res.ok) throw new Error(`Cascade failed: ${res.status}`);
  return res.json();
}

// ---------------------------------------------------------------------------
// Valuation (/api/valuation/*)
// ValuationRequest: { company_data: Dict, method: str, comparables?, assumptions? }
// NOT { company_id: str }
// ---------------------------------------------------------------------------

export async function runValuation(
  companyId: string,
  method: string = 'dcf',
  branchId?: string | null,
  companyData?: Record<string, any>,
) {
  const endpoint =
    method === 'all'
      ? 'value-company'
      : method === 'pwerm'
        ? 'pwerm-analysis'
        : method === 'dcf'
          ? 'dcf-model'
          : 'comparables-analysis';

  const res = await fetch(
    `/api/valuation/${endpoint}`,
    json({
      company_id: companyId,
      branch_id: branchId,
      company_data: companyData || {},
      method,
    }),
  );
  if (!res.ok) throw new Error(`Valuation failed: ${res.status}`);
  return res.json();
}

// ---------------------------------------------------------------------------
// Regression / Stress Test / Monte Carlo / Sensitivity (/fpa/regression)
//
// Backend FPARegressionRequest: { regression_type, data, options? }
// NOT { company_id, type, target_metric, simulations }
//
// Supported regression_type: linear, exponential, time_series, monte_carlo, sensitivity
// ---------------------------------------------------------------------------

export async function runRegression(
  regressionType: string,
  data: Record<string, any>,
  options?: Record<string, any>,
) {
  const res = await fetch(
    `/api/fpa/regression`,
    json({
      regression_type: regressionType,
      data,
      options,
    }),
  );
  if (!res.ok) throw new Error(`Regression (${regressionType}) failed: ${res.status}`);
  return res.json();
}

/** Monte Carlo — company_id-first. Backend pulls actuals from Supabase. */
export async function runMonteCarlo(
  companyId: string,
  targetMetric: string = 'revenue',
  iterations: number = 1000,
  branchId?: string | null,
  overrides?: Record<string, any>,
) {
  return runRegression('monte_carlo', {
    company_id: companyId,
    branch_id: branchId,
    target_metric: targetMetric,
    base_scenario: overrides || {},
  }, { iterations });
}

/** Sensitivity — company_id-first. Backend pulls actuals from Supabase. */
export async function runSensitivity(
  companyId: string,
  targetMetric: string = 'ebitda',
  branchId?: string | null,
  overrides?: Record<string, any>,
) {
  return runRegression('sensitivity', {
    company_id: companyId,
    branch_id: branchId,
    target_metric: targetMetric,
    base_inputs: overrides || {},
  });
}

/** Stress Test (time series) — convenience wrapper */
export async function runStressTest(
  historicalData: Array<Record<string, any>>,
  periods: number = 12,
) {
  return runRegression('time_series', {
    historical_data: historicalData,
  }, { periods });
}

/** Linear Regression — convenience wrapper */
export async function runLinearRegression(
  x: number[],
  y: number[],
) {
  return runRegression('linear', { x, y });
}

// ---------------------------------------------------------------------------
// Budget Variance (/fpa/variance — GET)
// ---------------------------------------------------------------------------

export async function fetchBudgetVariance(
  companyId: string,
  budgetIdOrPeriod?: string,
  start?: string,
  end?: string,
) {
  const params = new URLSearchParams({ company_id: companyId });
  if (budgetIdOrPeriod) params.set('budget_id', budgetIdOrPeriod);
  if (start) params.set('start', start);
  if (end) params.set('end', end);
  const res = await fetch(
    `/api/fpa/variance?${params}`,
    { method: 'GET', headers: { 'Content-Type': 'application/json' } },
  );
  if (!res.ok) throw new Error(`Variance failed: ${res.status}`);
  return res.json();
}

// ---------------------------------------------------------------------------
// Budget Management (/fpa/budgets)
// ---------------------------------------------------------------------------

export async function createBudget(
  companyId: string,
  name: string,
  fiscalYear: number,
  status: string = 'draft',
) {
  const res = await fetch(
    `/api/fpa/budgets`,
    json({ company_id: companyId, name, fiscal_year: fiscalYear, status }),
  );
  if (!res.ok) throw new Error(`Budget create failed: ${res.status}`);
  return res.json();
}

export async function listBudgets(companyId: string) {
  const params = new URLSearchParams({ company_id: companyId });
  const res = await fetch(
    `/api/fpa/budgets?${params}`,
    { method: 'GET' },
  );
  if (!res.ok) throw new Error(`Budget list failed: ${res.status}`);
  return res.json();
}

// ---------------------------------------------------------------------------
// Advanced Analytics — WACC, Health Score (/api/advanced-analytics/analyze)
//
// AnalyticsRequest: { company: str, analysis_type: str, parameters?: {}, use_cache? }
// 'company' is a NAME string, NOT a UUID.
// But we pass company_id and let the backend resolve.
// ---------------------------------------------------------------------------

export async function runAdvancedAnalytics(
  companyId: string,
  analysisType: string,
  parameters?: Record<string, any>,
  branchId?: string | null,
) {
  const res = await fetch(
    `/api/advanced-analytics/analyze`,
    json({
      company_id: companyId,
      branch_id: branchId,
      analysis_type: analysisType,
      parameters: parameters || {},
    }),
  );
  if (!res.ok) throw new Error(`Analytics failed: ${res.status}`);
  return res.json();
}

// ---------------------------------------------------------------------------
// NL Scenarios (/api/nl-scenarios/what-if — NOT /parse)
//
// WhatIfQueryRequest: { query, model_id?, fund_id? }
// NOT { company_id, query, base_branch_id }
// ---------------------------------------------------------------------------

export async function parseNLScenario(
  query: string,
  companyId: string,
  modelId?: string,
  fundId?: string,
) {
  const res = await fetch(
    `/api/nl-scenarios/what-if`,
    json({ query, company_id: companyId, model_id: modelId, fund_id: fundId }),
  );
  if (!res.ok) throw new Error(`NL scenario failed: ${res.status}`);
  return res.json();
  // -> { query, composed_scenario: { scenario_name, events, probability } }
}

// ---------------------------------------------------------------------------
// Scenario Branch CRUD (/fpa/scenarios/*)
// ---------------------------------------------------------------------------

export async function createScenarioBranch(
  companyId: string,
  name: string,
  parentBranchId?: string | null,
  forkPeriod?: string | null,
  assumptions?: Record<string, any>,
  probability?: number,
) {
  const res = await fetch(
    `/api/fpa/scenarios/branch`,
    json({
      company_id: companyId,
      name,
      parent_branch_id: parentBranchId,
      fork_period: forkPeriod,
      assumptions: assumptions || {},
      probability,
    }),
  );
  if (!res.ok) throw new Error(`Branch create failed: ${res.status}`);
  return res.json();
}

export async function updateScenarioBranch(
  branchId: string,
  drivers?: Record<string, any>,
  meta?: { name?: string; description?: string; probability?: number; forecast_months?: number },
) {
  const res = await fetch(
    `/api/fpa/scenarios/branch/${branchId}`,
    {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ drivers, ...meta }),
    },
  );
  if (!res.ok) throw new Error(`Branch update failed: ${res.status}`);
  return res.json();
}

export async function deleteScenarioBranch(branchId: string) {
  const res = await fetch(
    `/api/fpa/scenarios/branch/${branchId}`,
    { method: 'DELETE' },
  );
  if (!res.ok) throw new Error(`Branch delete failed: ${res.status}`);
  return res.json();
}

export async function fetchScenarioTree(companyId: string, enrich: boolean = true) {
  const params = new URLSearchParams({ company_id: companyId });
  if (enrich) params.set('enrich', 'true');
  const res = await fetch(
    `/api/fpa/scenarios/tree?${params}`,
    { method: 'GET' },
  );
  if (!res.ok) throw new Error(`Scenario tree failed: ${res.status}`);
  return res.json();
}

export async function fetchDriverRegistry(companyId: string) {
  const params = new URLSearchParams({ company_id: companyId });
  const res = await fetch(
    `/api/fpa/drivers/registry?${params}`,
    { method: 'GET' },
  );
  if (!res.ok) throw new Error(`Driver registry failed: ${res.status}`);
  return res.json();
}

// ---------------------------------------------------------------------------
// P&L Cell Writes (/fpa/pnl)
// ---------------------------------------------------------------------------

export async function upsertPnlCell(
  companyId: string,
  category: string,
  period: string,
  amount: number,
  subcategory?: string,
  source: string = 'manual_cell_edit',
) {
  const res = await fetch(
    `/api/fpa/pnl`,
    json({
      company_id: companyId,
      category,
      period,
      amount,
      subcategory,
      source,
    }),
  );
  if (!res.ok) throw new Error(`P&L upsert failed: ${res.status}`);
  return res.json();
}

export async function bulkUpsertPnlCells(
  cells: Array<{
    company_id: string;
    category: string;
    period: string;
    amount: number;
    subcategory?: string;
    source?: string;
  }>,
) {
  const res = await fetch(
    `/api/fpa/pnl/bulk`,
    json({ cells }),
  );
  if (!res.ok) throw new Error(`Bulk P&L upsert failed: ${res.status}`);
  return res.json();
}

// ---------------------------------------------------------------------------
// FPA NL Query (/fpa/query)
// ---------------------------------------------------------------------------

export async function queryFPA(
  query: string,
  fundId?: string,
  companyIds?: string[],
) {
  const res = await fetch(
    `/api/fpa/query`,
    json({
      query,
      fund_id: fundId,
      company_ids: companyIds,
    }),
  );
  if (!res.ok) throw new Error(`FPA query failed: ${res.status}`);
  return res.json();
}

// ---------------------------------------------------------------------------
// Scenario Compare (/fpa/scenarios/compare)
// ---------------------------------------------------------------------------

export async function compareScenarios(
  branchIds: string[],
  forecastMonths?: number,
  startPeriod?: string,
) {
  const res = await fetch(
    `/api/fpa/scenarios/compare`,
    json({
      branch_ids: branchIds,
      forecast_months: forecastMonths,
      start_period: startPeriod,
    }),
  );
  if (!res.ok) throw new Error(`Scenario compare failed: ${res.status}`);
  return res.json();
}

// ---------------------------------------------------------------------------
// Model Construction — construct + execute via unified-brain deterministic path
// tool_hint in context triggers direct tool execution (no LLM decision loop)
// ---------------------------------------------------------------------------

export async function constructForecastModel(
  companyId: string,
  prompt: string,
) {
  const res = await fetch(
    `/api/agent/unified-brain`,
    json({
      prompt,
      output_format: 'tool_result',
      context: {
        company_id: companyId,
        tool_hint: 'construct_forecast_model',
        tool_inputs: { prompt, company_id: companyId },
      },
    }),
  );
  if (!res.ok) throw new Error(`Model construction failed: ${res.status}`);
  return res.json();
}

export async function executeForecastModel(
  companyId: string,
  modelId?: string,
  months: number = 24,
) {
  if (!modelId) throw new Error('model_id is required for execution');
  const params = new URLSearchParams({
    company_id: companyId,
    months: String(months),
  });
  const res = await fetch(
    `/api/fpa/models/${encodeURIComponent(modelId)}/execute?${params}`,
    { method: 'POST' },
  );
  if (!res.ok) throw new Error(`Model execution failed: ${res.status}`);
  return res.json();
}
