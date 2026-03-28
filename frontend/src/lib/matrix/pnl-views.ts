/**
 * P&L View Definitions
 *
 * Defines the 4 views available inside P&L mode:
 *   1. waterfall   — PnlBuilder hierarchical income statement
 *   2. forecast    — RollingForecastService actuals vs forecast
 *   3. budget      — BudgetVarianceService actuals vs budget w/ variance
 *   4. cashflow    — LiquidityManagementService full cash flow projection
 *
 * Each view has its own column builder and row transformer that maps service
 * output into MatrixData (columns + rows) for the grid.
 */

import type { MatrixColumn, MatrixRow, MatrixData, MatrixCell } from '@/components/matrix/UnifiedMatrix';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type PnlView = 'waterfall' | 'forecast' | 'budget' | 'cashflow' | 'scenarios' | 'balancesheet' | 'captable';
export type Granularity = 'monthly' | 'quarterly' | 'annual';

export interface PnlViewConfig {
  id: PnlView;
  label: string;
  description: string;
  supportsGranularity: boolean;
  /** Backend route path (relative to /api/fpa) */
  endpoint: string;
  method: 'GET' | 'POST';
}

export const PNL_VIEW_CONFIGS: Record<PnlView, PnlViewConfig> = {
  waterfall: {
    id: 'waterfall',
    label: 'P&L',
    description: 'Hierarchical income statement — actuals + forecast',
    supportsGranularity: true,
    endpoint: '/api/fpa/pnl',
    method: 'GET',
  },
  forecast: {
    id: 'forecast',
    label: 'Forecast',
    description: 'Actuals vs forecast with visual boundary',
    supportsGranularity: true,
    endpoint: '/api/fpa/rolling-forecast',
    method: 'GET',
  },
  budget: {
    id: 'budget',
    label: 'Budget',
    description: 'Actuals vs budget with variance & trend',
    supportsGranularity: true,
    endpoint: '/api/fpa/variance',
    method: 'GET',
  },
  cashflow: {
    id: 'cashflow',
    label: 'Cash Flow',
    description: 'Revenue through FCF, cash balance, runway',
    supportsGranularity: true,
    endpoint: '/api/fpa/forecast',
    method: 'POST',
  },
  scenarios: {
    id: 'scenarios',
    label: 'Scenarios',
    description: 'Fork-based scenario forecasts with branch comparison',
    supportsGranularity: true,
    endpoint: '/api/fpa/scenarios/tree',
    method: 'GET',
  },
  balancesheet: {
    id: 'balancesheet',
    label: 'Balance Sheet',
    description: 'Assets, liabilities & equity with balance check',
    supportsGranularity: false,
    endpoint: '/api/fpa/balance-sheet',
    method: 'GET',
  },
  captable: {
    id: 'captable',
    label: 'Cap Table',
    description: 'Equity, debt & convertibles — editable ledger from documents',
    supportsGranularity: false,
    endpoint: '/api/agent/cap-table-entries',
    method: 'GET',
  },
};

// ---------------------------------------------------------------------------
// Column builders
// ---------------------------------------------------------------------------

function monthLabel(period: string): string {
  const [y, m] = period.split('-');
  const d = new Date(parseInt(y), parseInt(m) - 1, 1);
  return d.toLocaleDateString('en-US', { month: 'short' }) + ' \u2019' + y.slice(2);
}

function quarterLabel(period: string): string {
  // period like "2025-Q1" or "2025-01" (first month of quarter)
  if (period.includes('Q')) return period;
  const [y, m] = period.split('-');
  const q = Math.ceil(parseInt(m) / 3);
  return `Q${q} '${y.slice(2)}`;
}

function periodLabel(period: string, granularity: Granularity): string {
  if (granularity === 'annual') return period.slice(0, 4);
  if (granularity === 'quarterly') return quarterLabel(period);
  return monthLabel(period);
}

/** Standard P&L waterfall columns — built from the periods array returned by PnlBuilder */
export function buildWaterfallColumns(periods: string[]): MatrixColumn[] {
  return [
    { id: 'lineItem', name: 'Line Item', type: 'text', width: 220, editable: false },
    ...periods.map((p) => ({
      id: p,
      name: monthLabel(p),
      type: 'currency' as const,
      width: 110,
      editable: true,
    })),
  ];
}

/** Actuals vs Forecast columns — same period columns but tagged with source */
export function buildForecastColumns(
  periods: string[],
  boundaryIndex: number,
  granularity: Granularity
): MatrixColumn[] {
  return [
    { id: 'lineItem', name: 'Line Item', type: 'text', width: 220, editable: false },
    ...periods.map((p, i) => ({
      id: p,
      name: periodLabel(p, granularity),
      type: 'currency' as const,
      width: 110,
      editable: i >= boundaryIndex, // only forecast cells editable
    })),
  ];
}

/** Actuals vs Budget — triple sub-columns per category: Actual | Budget | Variance */
export function buildBudgetColumns(categories: string[]): MatrixColumn[] {
  const cols: MatrixColumn[] = [
    { id: 'category', name: 'Category', type: 'text', width: 180, editable: false },
  ];
  // Flat layout: actual, budget, variance$, variance%, status, trend
  cols.push(
    { id: 'actual', name: 'Actual', type: 'currency', width: 120, editable: false },
    { id: 'budget', name: 'Budget', type: 'currency', width: 120, editable: false },
    { id: 'variance', name: 'Variance $', type: 'currency', width: 110, editable: false },
    { id: 'variance_pct', name: 'Var %', type: 'percentage', width: 80, editable: false },
    { id: 'status', name: 'Status', type: 'text', width: 100, editable: false },
    { id: 'trend', name: 'Trend', type: 'text', width: 100, editable: false },
  );
  return cols;
}

/** Cash flow columns — period columns like forecast but may extend further */
export function buildCashFlowColumns(
  periods: string[],
  granularity: Granularity
): MatrixColumn[] {
  return [
    { id: 'lineItem', name: 'Line Item', type: 'text', width: 220, editable: false },
    ...periods.map((p) => ({
      id: p,
      name: periodLabel(p, granularity),
      type: 'currency' as const,
      width: 110,
      editable: false,
    })),
  ];
}

// ---------------------------------------------------------------------------
// Row transformers — map service output → MatrixRow[]
// ---------------------------------------------------------------------------

function cell(value: any, extra?: Partial<MatrixCell>): MatrixCell {
  return { value, ...extra };
}

/**
 * Waterfall: PnlBuilder output → rows.
 * Input shape: { periods, forecastStartIndex, rows: [{ id, label, values, isHeader, isComputed, depth, section }] }
 */
export function transformWaterfallRows(data: any): { columns: MatrixColumn[]; rows: MatrixRow[]; meta: any } {
  const periods: string[] = data.periods || [];
  const forecastStartIndex: number = data.forecastStartIndex ?? periods.length;
  const columns = buildWaterfallColumns(periods);

  const rows: MatrixRow[] = (data.rows || []).map((r: any) => {
    const cells: Record<string, MatrixCell> = {
      lineItem: cell(r.label || r.id, {
        metadata: {
          generated_by: r.isHeader ? 'header' : r.isComputed ? 'computed' : undefined,
        },
      }),
    };
    for (const p of periods) {
      const val = r.values?.[p] ?? null;
      const isForecast = periods.indexOf(p) >= forecastStartIndex;
      cells[p] = cell(val, {
        source: isForecast ? 'formula' : 'api',
        metadata: {
          ...(isForecast ? { generated_by: 'forecast' } : undefined),
          ...(r.explanation ? { explanation: r.explanation } : undefined),
          ...(r.isComputed ? { method: 'Computed' } : r.isTotal ? { method: 'Total' } : undefined),
        },
      });
    }
    return {
      id: r.id,
      cells,
      isHeader: r.isHeader,
      isComputed: r.isComputed,
      isTotal: r.isTotal,
      depth: r.depth ?? 0,
      section: r.section,
      parentId: r.parentId,
    } as MatrixRow;
  });

  return {
    columns,
    rows,
    meta: { forecastStartIndex },
  };
}

/**
 * Forecast: RollingForecastService output → rows.
 * Input shape: { periods, boundary_index, rows: [{ period, source, revenue, cogs, ... }] }
 */

const FORECAST_LINE_ITEMS = [
  { key: 'revenue', rowId: 'revenue', label: 'Revenue', section: 'revenue', depth: 0 },
  { key: 'cogs', rowId: 'cogs', label: 'COGS', section: 'cogs', depth: 0 },
  { key: 'gross_profit', rowId: 'gross_profit', label: 'Gross Profit', section: 'gross_profit', depth: 0, isComputed: true },
  { key: 'rd_spend', rowId: 'opex_rd', label: 'R&D', section: 'opex', depth: 1 },
  { key: 'sm_spend', rowId: 'opex_sm', label: 'Sales & Marketing', section: 'opex', depth: 1 },
  { key: 'ga_spend', rowId: 'opex_ga', label: 'G&A', section: 'opex', depth: 1 },
  { key: 'total_opex', rowId: 'total_opex', label: 'Total OpEx', section: 'opex', depth: 0, isComputed: true },
  { key: 'ebitda', rowId: 'ebitda', label: 'EBITDA', section: 'ebitda', depth: 0, isComputed: true },
  { key: 'debt_service', rowId: 'debt_service', label: 'Interest / Debt Service', section: 'below_line', depth: 0 },
  { key: 'tax_expense', rowId: 'tax_expense', label: 'Tax', section: 'below_line', depth: 0 },
  { key: 'net_income', rowId: 'net_income', label: 'Net Income', section: 'below_line', depth: 0, isComputed: true },
  { key: 'gross_burn_rate', rowId: 'gross_burn_rate', label: 'Gross Burn Rate', section: 'metrics', depth: 0, isComputed: true },
  { key: 'net_burn_rate', rowId: 'net_burn_rate', label: 'Net Burn Rate', section: 'metrics', depth: 0, isComputed: true },
  { key: 'runway_months', rowId: 'runway_months', label: 'Runway (months)', section: 'metrics', depth: 0, isComputed: true },
  { key: 'rule_of_40', rowId: 'rule_of_40', label: 'Rule of 40', section: 'metrics', depth: 0, isComputed: true },
];

export function transformForecastRows(
  data: any,
  granularity: Granularity
): { columns: MatrixColumn[]; rows: MatrixRow[]; meta: any } {
  const rawRows: any[] = data.rows || [];
  const periods = rawRows.map((r: any) => r.period);
  const boundaryIndex: number = data.boundary_index ?? periods.length;
  const columns = buildForecastColumns(periods, boundaryIndex, granularity);
  const derivations: Record<string, string> = data.cell_derivations || {};

  // Pivot: service returns one object per period, we need one row per line item
  const rows: MatrixRow[] = FORECAST_LINE_ITEMS.map((item) => {
    const cells: Record<string, MatrixCell> = {
      lineItem: cell(item.label),
    };
    rawRows.forEach((periodRow: any, idx: number) => {
      const isForecast = idx >= boundaryIndex;
      const derivationKey = `${periodRow.period}|${item.key}`;
      const explanation = derivations[derivationKey] || undefined;
      cells[periodRow.period] = cell(periodRow[item.key] ?? null, {
        source: isForecast ? 'formula' : 'api',
        metadata: {
          generated_by: isForecast ? 'forecast' : 'actual',
          explanation,
        },
      });
    });
    return {
      id: item.rowId || item.key,
      cells,
      isComputed: item.isComputed || false,
      depth: item.depth,
      section: item.section,
    } as MatrixRow;
  });

  return {
    columns,
    rows,
    meta: {
      boundaryIndex,
      boundaryPeriod: data.boundary_period,
      granularity,
      actualsStart: data.actuals_start,
      actualsEnd: data.actuals_end,
    },
  };
}

/**
 * Budget: BudgetVarianceService output → rows.
 * Input shape: { variances: { summary, by_category: [{ category, actual, budget, variance, variance_pct, status, trend }], monthly_trend } }
 */
export function transformBudgetRows(data: any): { columns: MatrixColumn[]; rows: MatrixRow[]; meta: any } {
  const variances = data.variances || data;
  const categories: any[] = variances.by_category || [];
  const columns = buildBudgetColumns(categories.map((c: any) => c.category));

  const rows: MatrixRow[] = categories.map((cat: any) => ({
    id: cat.category,
    cells: {
      category: cell(cat.category),
      actual: cell(cat.actual),
      budget: cell(cat.budget),
      variance: cell(cat.variance, {
        metadata: {
          // Positive variance on revenue = good, positive on cost = bad
          generated_by: cat.status,
        },
      }),
      variance_pct: cell(cat.variance_pct != null ? cat.variance_pct / 100 : null),
      status: cell(cat.status, {
        displayValue: statusBadge(cat.status),
      }),
      trend: cell(cat.trend, {
        displayValue: trendArrow(cat.trend),
      }),
    },
  } as MatrixRow));

  // Summary row at top
  const summary = variances.summary;
  if (summary) {
    rows.unshift({
      id: '_summary',
      cells: {
        category: cell('Total'),
        actual: cell(summary.total_actual),
        budget: cell(summary.total_budget),
        variance: cell(summary.total_variance),
        variance_pct: cell(summary.total_variance_pct != null ? summary.total_variance_pct / 100 : null),
        status: cell(null),
        trend: cell(null),
      },
      isHeader: true,
      isComputed: true,
    } as MatrixRow);
  }

  return {
    columns,
    rows,
    meta: {
      source: variances.source,
      period: data.period,
      categoriesCritical: summary?.categories_critical,
      categoriesOver: summary?.categories_over,
    },
  };
}

function statusBadge(status: string): string {
  switch (status) {
    case 'critical': return 'Critical';
    case 'over': return 'Over Budget';
    case 'under': return 'Under Budget';
    case 'on_track': return 'On Track';
    default: return status || '';
  }
}

function trendArrow(trend: string): string {
  switch (trend) {
    case 'worsening': return 'Worsening';
    case 'improving': return 'Improving';
    case 'stable': return 'Stable';
    default: return trend || '';
  }
}

/**
 * Cash Flow: LiquidityManagementService.build_liquidity_model output → rows.
 * Input shape: { forecast: [{ period, revenue, cogs, gross_profit, ..., free_cash_flow, cash_balance, runway_months }], granularity }
 */

const CASHFLOW_LINE_ITEMS = [
  // Operating Activities
  { key: 'net_income', label: 'Net Income', section: 'operating', depth: 0, isComputed: true },
  { key: 'working_capital_delta', label: 'Working Capital Changes', section: 'operating', depth: 1 },
  { key: 'operating_cash_flow', label: 'Operating Cash Flow', section: 'operating', depth: 0, isComputed: true, isDerived: true },
  // Investing Activities
  { key: 'capex', label: 'CapEx', section: 'investing', depth: 0 },
  // Financing Activities
  { key: 'debt_service', label: 'Debt Service', section: 'financing', depth: 0 },
  // Summary
  { key: 'free_cash_flow', label: 'Free Cash Flow', section: 'summary', depth: 0, isComputed: true },
  { key: 'cash_balance', label: 'Cash Balance', section: 'summary', depth: 0 },
  { key: 'runway_months', label: 'Runway (months)', section: 'summary', depth: 0 },
];

export function transformCashFlowRows(
  data: any,
  granularity: Granularity
): { columns: MatrixColumn[]; rows: MatrixRow[]; meta: any } {
  const forecast: any[] = data.forecast || [];
  const periods = forecast.map((r: any) => r.period);
  const columns = buildCashFlowColumns(periods, granularity);

  const rows: MatrixRow[] = CASHFLOW_LINE_ITEMS.map((item) => {
    const cells: Record<string, MatrixCell> = {
      lineItem: cell(item.label),
    };
    forecast.forEach((periodRow: any) => {
      let val: number | null;
      if ((item as any).isDerived && item.key === 'operating_cash_flow') {
        // Derive: net_income + working_capital_delta
        const ni = periodRow.net_income ?? 0;
        const wc = periodRow.working_capital_delta ?? 0;
        val = ni + wc;
      } else {
        val = periodRow[item.key] ?? null;
      }
      cells[periodRow.period] = cell(val, { source: 'formula' });
    });
    return {
      id: item.key,
      cells,
      isHeader: false,
      isComputed: item.isComputed || false,
      depth: item.depth,
      section: item.section,
    } as MatrixRow;
  });

  return {
    columns,
    rows,
    meta: { granularity, periods: data.periods },
  };
}

/**
 * Scenarios: Transform a single branch's ForecastMonth[] into grid rows.
 * Same line items as the forecast view, just reads from the hook's cached forecast.
 */
export function transformScenarioRows(
  forecast: any[],
  granularity: Granularity
): { columns: MatrixColumn[]; rows: MatrixRow[]; meta: any } {
  const periods = forecast.map((r: any) => r.period);
  const columns = buildForecastColumns(periods, 0, granularity);

  const rows: MatrixRow[] = FORECAST_LINE_ITEMS.map((item) => {
    const cells: Record<string, MatrixCell> = {
      lineItem: cell(item.label),
    };
    forecast.forEach((periodRow: any) => {
      cells[periodRow.period] = cell(periodRow[item.key] ?? null, {
        source: 'formula',
        metadata: { generated_by: 'scenario' },
      });
    });
    return {
      id: item.rowId || item.key,
      cells,
      isComputed: item.isComputed || false,
      depth: item.depth,
      section: item.section,
    } as MatrixRow;
  });

  return {
    columns,
    rows,
    meta: { granularity },
  };
}

// ---------------------------------------------------------------------------
// Balance Sheet columns + row transformer
// ---------------------------------------------------------------------------

/** Balance Sheet columns — period columns with % of Total Assets computed column */
export function buildBalanceSheetColumns(periods: string[]): MatrixColumn[] {
  return [
    { id: 'lineItem', name: 'Line Item', type: 'text', width: 260, editable: false },
    ...periods.map((p) => ({
      id: p,
      name: monthLabel(p),
      type: 'currency' as const,
      width: 120,
      editable: true,
    })),
  ];
}

/**
 * Balance Sheet: BalanceSheetBuilder output → rows.
 * Input shape: { periods, rows: [{ id, label, values, isHeader, isComputed, isTotal, depth, section }], totals }
 */
export function transformBalanceSheetRows(data: any): { columns: MatrixColumn[]; rows: MatrixRow[]; meta: any } {
  const periods: string[] = data.periods || [];
  const columns = buildBalanceSheetColumns(periods);

  const rows: MatrixRow[] = (data.rows || []).map((r: any) => {
    const cells: Record<string, MatrixCell> = {
      lineItem: cell(r.label || r.id, {
        metadata: {
          generated_by: r.isHeader ? 'header' : r.isComputed ? 'computed' : r.isTotal ? 'total' : undefined,
        },
      }),
    };
    for (const p of periods) {
      const val = r.values?.[p] ?? null;
      cells[p] = cell(val, {
        source: r.isComputed || r.isTotal ? 'formula' : 'api',
      });
    }
    return {
      id: r.id,
      cells,
      isHeader: r.isHeader,
      isComputed: r.isComputed,
      isTotal: r.isTotal,
      depth: r.depth ?? 0,
      section: r.section,
      parentId: r.parentId,
    } as MatrixRow;
  });

  return {
    columns,
    rows,
    meta: { totals: data.totals },
  };
}

// ---------------------------------------------------------------------------
// Cap Table columns + transform
// ---------------------------------------------------------------------------

const CAP_TABLE_COLUMNS: MatrixColumn[] = [
  { id: 'shareholder_name', name: 'Stakeholder', type: 'text', width: 180, editable: true },
  { id: 'stakeholder_type', name: 'Type', type: 'text', width: 100, editable: true },
  { id: 'instrument_type', name: 'Instrument', type: 'text', width: 110, editable: true },
  { id: 'share_class', name: 'Class', type: 'text', width: 110, editable: true },
  { id: 'num_shares', name: 'Shares', type: 'number', width: 110, editable: true },
  { id: 'price_per_share', name: 'Price/Share', type: 'currency', width: 110, editable: true },
  { id: 'ownership_pct', name: 'Ownership %', type: 'percentage', width: 100, editable: false },
  { id: 'round_name', name: 'Round', type: 'text', width: 100, editable: true },
  { id: 'investment_date', name: 'Date', type: 'text', width: 100, editable: true },
  { id: 'liquidation_pref', name: 'Liq Pref', type: 'number', width: 80, editable: true },
  { id: 'outstanding_principal', name: 'Principal', type: 'currency', width: 120, editable: true },
  { id: 'interest_rate', name: 'Rate %', type: 'percentage', width: 80, editable: true },
  { id: 'maturity_date', name: 'Maturity', type: 'text', width: 100, editable: true },
  { id: 'conversion_discount', name: 'Disc %', type: 'percentage', width: 80, editable: true },
  { id: 'valuation_cap', name: 'Val Cap', type: 'currency', width: 110, editable: true },
  { id: 'source', name: 'Source', type: 'text', width: 80, editable: false },
  { id: 'notes', name: 'Notes', type: 'text', width: 160, editable: true },
];

export function transformCapTableRows(data: any): { columns: MatrixColumn[]; rows: MatrixRow[]; meta: any } {
  const entries: any[] = data?.share_entries || data?.entries || [];
  const ownership: Record<string, number> = data?.ownership || {};

  const rows: MatrixRow[] = entries.map((e: any, i: number) => {
    const ownershipPct = e.ownership_pct ?? ownership[e.shareholder_name] ?? null;
    const cells: Record<string, MatrixCell> = {};
    for (const col of CAP_TABLE_COLUMNS) {
      const val = col.id === 'ownership_pct' ? ownershipPct : (e[col.id] ?? null);
      cells[col.id] = cell(val, {
        source: e.source === 'legal' ? 'api' : e.source === 'csv' ? 'api' : 'manual',
      });
    }
    return {
      id: e.id || `cap-${i}`,
      cells,
      companyId: e.company_id,
    } as MatrixRow;
  });

  return {
    columns: CAP_TABLE_COLUMNS,
    rows,
    meta: {
      totalRaised: data?.total_raised,
      totalEquity: data?.total_equity,
      totalDebt: data?.total_debt,
      equityWeight: data?.equity_weight,
      debtWeight: data?.debt_weight,
      entryCount: data?.entry_count,
    },
  };
}

// ---------------------------------------------------------------------------
// Unified fetch + transform
// ---------------------------------------------------------------------------

export interface PnlViewFetchParams {
  view: PnlView;
  companyId: string;
  fundId?: string;
  granularity?: Granularity;
  budgetId?: string;
  start?: string;
  end?: string;
}

export interface PnlViewResult extends MatrixData {
  /** Charts returned by the backend for rendering in the memo */
  charts?: Array<{ type: string; title?: string; data: any; renderType?: string }>;
}

/**
 * Fetch data for a P&L view and transform into MatrixData.
 */
export async function fetchPnlView(params: PnlViewFetchParams): Promise<PnlViewResult> {
  const { view, companyId, fundId, granularity = 'monthly', budgetId, start, end } = params;
  const config = PNL_VIEW_CONFIGS[view];

  let url: string;
  let fetchOpts: RequestInit = { method: config.method };

  switch (view) {
    case 'waterfall': {
      const qs = new URLSearchParams({ company_id: companyId });
      if (fundId) qs.set('fund_id', fundId);
      if (start) qs.set('start', start);
      if (end) qs.set('end', end);
      url = `${config.endpoint}?${qs}`;
      break;
    }
    case 'forecast': {
      const qs = new URLSearchParams({ company_id: companyId, granularity });
      url = `${config.endpoint}?${qs}`;
      break;
    }
    case 'budget': {
      const now = new Date();
      const qs = new URLSearchParams({
        company_id: companyId,
        start: start || `${now.getFullYear()}-01`,
        end: end || `${now.getFullYear()}-12`,
      });
      if (budgetId) qs.set('budget_id', budgetId);
      url = `${config.endpoint}?${qs}`;
      break;
    }
    case 'cashflow': {
      url = config.endpoint;
      fetchOpts = {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          company_id: companyId,
          granularity,
          forecast_periods: granularity === 'annual' ? 5 : granularity === 'quarterly' ? 12 : 24,
        }),
      };
      break;
    }
    case 'scenarios': {
      const qs = new URLSearchParams({ company_id: companyId, enrich: 'true' });
      url = `${config.endpoint}?${qs}`;
      break;
    }
    case 'balancesheet': {
      const qs = new URLSearchParams({ company_id: companyId });
      if (fundId) qs.set('fund_id', fundId);
      if (start) qs.set('start', start);
      if (end) qs.set('end', end);
      url = `${config.endpoint}?${qs}`;
      break;
    }
    case 'captable': {
      const qs = new URLSearchParams({ company_id: companyId, view: 'company' });
      if (fundId) qs.set('fund_id', fundId);
      url = `${config.endpoint}?${qs}`;
      break;
    }
    default:
      throw new Error(`Unknown P&L view: ${view}`);
  }

  let data: any;
  try {
    const res = await fetch(url, fetchOpts);
    if (!res.ok) {
      console.warn(`FPA ${view} returned ${res.status} — rendering empty grid`);
      data = {};
    } else {
      data = await res.json();
    }
  } catch (err) {
    console.warn(`FPA ${view} fetch failed — rendering empty grid`, err);
    data = {};
  }

  // Transform based on view — transformers handle empty/missing data gracefully
  let result: { columns: MatrixColumn[]; rows: MatrixRow[]; meta: any };

  switch (view) {
    case 'waterfall':
      result = transformWaterfallRows(data);
      break;
    case 'forecast':
      result = transformForecastRows(data, granularity);
      break;
    case 'budget':
      result = transformBudgetRows(data);
      break;
    case 'cashflow':
      result = transformCashFlowRows(data, granularity);
      break;
    case 'scenarios': {
      // Scenarios initial load returns tree; use base_forecast for grid
      const baseFc = data.base_forecast ?? [];
      result = transformScenarioRows(baseFc, granularity);
      break;
    }
    case 'balancesheet':
      result = transformBalanceSheetRows(data);
      break;
    case 'captable':
      result = transformCapTableRows(data);
      break;
    default:
      throw new Error(`Unknown view: ${view}`);
  }

  return {
    columns: result.columns,
    rows: result.rows,
    metadata: {
      dataSource: `fpa-${view}`,
      forecastStartIndex: result.meta.forecastStartIndex ?? result.meta.boundaryIndex,
      ...result.meta,
    },
    charts: data.charts ?? undefined,
  };
}
