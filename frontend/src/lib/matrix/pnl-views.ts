/**
 * P&L View Definitions
 *
 * Defines the 4 views available inside P&L mode:
 *   1. waterfall   — PnlBuilder hierarchical income statement
 *   2. forecast    — RollingForecastService actuals vs forecast
 *   3. budget      — BudgetVarianceService actuals vs budget w/ variance
 *   4. cashflow    — CashFlowPlanningService full cash flow projection
 *
 * Each view has its own column builder and row transformer that maps service
 * output into MatrixData (columns + rows) for the grid.
 */

import type { MatrixColumn, MatrixRow, MatrixData, MatrixCell } from '@/components/matrix/UnifiedMatrix';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type PnlView = 'waterfall' | 'forecast' | 'budget' | 'cashflow' | 'scenarios';
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
        metadata: isForecast ? { generated_by: 'forecast' } : undefined,
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
  { key: 'revenue', label: 'Revenue', section: 'revenue', depth: 0 },
  { key: 'cogs', label: 'COGS', section: 'cogs', depth: 0 },
  { key: 'gross_profit', label: 'Gross Profit', section: 'gross_profit', depth: 0, isComputed: true },
  { key: 'rd_spend', label: 'R&D', section: 'opex', depth: 1 },
  { key: 'sm_spend', label: 'Sales & Marketing', section: 'opex', depth: 1 },
  { key: 'ga_spend', label: 'G&A', section: 'opex', depth: 1 },
  { key: 'total_opex', label: 'Total OpEx', section: 'opex', depth: 0, isComputed: true },
  { key: 'ebitda', label: 'EBITDA', section: 'ebitda', depth: 0, isComputed: true },
  { key: 'capex', label: 'CapEx', section: 'below', depth: 0 },
  { key: 'free_cash_flow', label: 'Free Cash Flow', section: 'below', depth: 0, isComputed: true },
  { key: 'cash_balance', label: 'Cash Balance', section: 'below', depth: 0 },
  { key: 'runway_months', label: 'Runway (months)', section: 'below', depth: 0 },
];

export function transformForecastRows(
  data: any,
  granularity: Granularity
): { columns: MatrixColumn[]; rows: MatrixRow[]; meta: any } {
  const rawRows: any[] = data.rows || [];
  const periods = rawRows.map((r: any) => r.period);
  const boundaryIndex: number = data.boundary_index ?? periods.length;
  const columns = buildForecastColumns(periods, boundaryIndex, granularity);

  // Pivot: service returns one object per period, we need one row per line item
  const rows: MatrixRow[] = FORECAST_LINE_ITEMS.map((item) => {
    const cells: Record<string, MatrixCell> = {
      lineItem: cell(item.label),
    };
    rawRows.forEach((periodRow: any, idx: number) => {
      const isForecast = idx >= boundaryIndex;
      cells[periodRow.period] = cell(periodRow[item.key] ?? null, {
        source: isForecast ? 'formula' : 'api',
        displayValue: isForecast ? undefined : undefined,
        metadata: {
          generated_by: isForecast ? 'forecast' : 'actual',
        },
      });
    });
    return {
      id: item.key,
      cells,
      isComputed: item.isComputed || false,
      depth: item.depth,
      section: item.section,
    } as MatrixRow;
  });

  return {
    columns,
    rows,
    meta: { boundaryIndex, boundaryPeriod: data.boundary_period, granularity },
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
 * Cash Flow: CashFlowPlanningService.build_projection output → rows.
 * Input shape: { forecast: [{ period, revenue, cogs, gross_profit, ..., free_cash_flow, cash_balance, runway_months }], granularity }
 */

const CASHFLOW_LINE_ITEMS = [
  { key: 'revenue', label: 'Revenue', section: 'revenue', depth: 0 },
  { key: 'cogs', label: 'COGS', section: 'cogs', depth: 0 },
  { key: 'gross_profit', label: 'Gross Profit', section: 'gross_profit', depth: 0, isComputed: true },
  { key: 'gross_margin', label: 'Gross Margin %', section: 'gross_profit', depth: 1, isComputed: true, isPct: true },
  { key: 'rd_spend', label: 'R&D', section: 'opex', depth: 1 },
  { key: 'sm_spend', label: 'Sales & Marketing', section: 'opex', depth: 1 },
  { key: 'ga_spend', label: 'G&A', section: 'opex', depth: 1 },
  { key: 'total_opex', label: 'Total OpEx', section: 'opex', depth: 0, isComputed: true },
  { key: 'ebitda', label: 'EBITDA', section: 'ebitda', depth: 0, isComputed: true },
  { key: 'ebitda_margin', label: 'EBITDA Margin %', section: 'ebitda', depth: 1, isComputed: true, isPct: true },
  { key: 'capex', label: 'CapEx', section: 'capex', depth: 0 },
  { key: 'debt_service', label: 'Debt Service', section: 'debt', depth: 0 },
  { key: 'tax', label: 'Tax', section: 'tax', depth: 0 },
  { key: 'free_cash_flow', label: 'Free Cash Flow', section: 'fcf', depth: 0, isComputed: true },
  { key: 'cash_balance', label: 'Cash Balance', section: 'cash', depth: 0 },
  { key: 'runway_months', label: 'Runway (months)', section: 'cash', depth: 0 },
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
      const val = periodRow[item.key] ?? null;
      const isPct = (item as any).isPct && val != null;
      cells[periodRow.period] = cell(
        isPct ? val / 100 : val,
        {
          source: 'formula',
          displayValue: isPct ? `${val.toFixed(1)}%` : undefined,
          metadata: isPct ? { output_type: 'percentage' } : undefined,
        }
      );
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
      id: item.key,
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

/**
 * Fetch data for a P&L view and transform into MatrixData.
 */
export async function fetchPnlView(params: PnlViewFetchParams): Promise<MatrixData> {
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
    default:
      throw new Error(`Unknown P&L view: ${view}`);
  }

  const res = await fetch(url, fetchOpts);
  if (!res.ok) {
    const err = await res.json().catch(() => ({ error: 'Request failed' }));
    throw new Error(err.detail || err.error || `HTTP ${res.status}`);
  }
  const data = await res.json();

  // Transform based on view
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
  };
}
