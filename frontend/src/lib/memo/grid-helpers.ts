/**
 * Grid Helpers — Direct readers for matrixData cells.
 *
 * All memo sections should use these instead of hardcoded ID sets.
 * Handles aliases (rd_spend vs opex_rd), dynamic subcategories,
 * and forecast field mapping.
 */

import type { MatrixData, MatrixRow, MatrixCell } from '@/components/matrix/UnifiedMatrix';

// ---------------------------------------------------------------------------
// Row discovery — by section tag, not hardcoded ID
// ---------------------------------------------------------------------------

/** Get all rows tagged with a given section (set by PnlBuilder / pnl-views transforms) */
export function getRowsBySection(data: MatrixData, section: string): MatrixRow[] {
  return data.rows.filter(r => (r as any).section === section);
}

/** Get ALL P&L rows — revenue + cogs + gross_profit + opex + ebitda + below_line.
 *  Includes dynamic subcategories. */
export function getAllPnlRows(data: MatrixData): MatrixRow[] {
  const pnlSections = new Set([
    'revenue', 'cogs', 'gross_profit', 'opex', 'ebitda', 'below_line',
    'bottom', 'metrics',
  ]);
  return data.rows.filter(r => {
    const section = (r as any).section;
    if (section && pnlSections.has(section)) return true;
    // Fallback: match known prefixes for rows without section tags
    return /^(revenue|total_revenue|cogs|total_cogs|opex_|rd_spend|sm_spend|ga_spend|gross_profit|total_opex|ebitda|net_income|total_|debt_service|tax_expense|pre_tax|cash_balance|runway|gross_burn|net_burn|rule_of_40)/.test(r.id);
  });
}

/** Get balance sheet rows */
export function getBalanceSheetRows(data: MatrixData): MatrixRow[] {
  const bsSections = new Set([
    'assets', 'liabilities', 'equity',
    'current_assets', 'noncurrent_assets',
    'current_liabilities', 'noncurrent_liabilities',
  ]);
  return data.rows.filter(r => {
    const section = (r as any).section;
    if (section && bsSections.has(section)) return true;
    return /^(assets|liabilities|equity|total_assets|total_liabilities|total_equity|cash_equiv|accounts_|inventory|prepaid|ppe|intangible|goodwill|short_term_debt|long_term_debt|deferred|accrued|common_stock|retained|additional_paid)/.test(r.id);
  });
}

/** Get cash flow rows */
export function getCashFlowRows(data: MatrixData): MatrixRow[] {
  const cfSections = new Set([
    'operating', 'investing', 'financing', 'summary', 'metrics',
  ]);
  return data.rows.filter(r => {
    const section = (r as any).section;
    if (section && cfSections.has(section)) return true;
    return /^(operating_cash|free_cash|cash_balance|net_burn|gross_burn|runway|capex|debt_service|working_capital|net_income|rule_of_40)/.test(r.id);
  });
}

// ---------------------------------------------------------------------------
// Cell value extraction
// ---------------------------------------------------------------------------

/** Get numeric value from a cell, handling string/number/null */
export function cellValue(cell: MatrixCell | undefined): number | null {
  if (!cell || cell.value == null) return null;
  if (typeof cell.value === 'number') return cell.value;
  const parsed = parseFloat(cell.value);
  return isNaN(parsed) ? null : parsed;
}

/** Get all period column IDs (everything except 'lineItem') */
export function getPeriodColumns(data: MatrixData): string[] {
  return data.columns.filter(c => c.id !== 'lineItem').map(c => c.id);
}

/** Get the value of a row across all periods -> { "2025-01": 50000, ... } */
export function getRowTimeSeries(
  data: MatrixData,
  rowId: string,
): Record<string, number> {
  const row = data.rows.find(r => r.id === rowId);
  if (!row) return {};
  const result: Record<string, number> = {};
  for (const col of getPeriodColumns(data)) {
    const v = cellValue(row.cells[col]);
    if (v != null) result[col] = v;
  }
  return result;
}

/** Find a row by ID, trying multiple aliases.
 *  Handles rd_spend vs opex_rd, runway vs runway_months, etc. */
export function findRow(
  data: MatrixData,
  ...ids: string[]
): MatrixRow | undefined {
  for (const id of ids) {
    const row = data.rows.find(r => r.id === id);
    if (row) return row;
  }
  return undefined;
}

/** Get latest period value for a row (last column with data) */
export function getLatestValue(
  data: MatrixData,
  ...rowIds: string[]
): number | null {
  const row = findRow(data, ...rowIds);
  if (!row) return null;
  const periods = getPeriodColumns(data);
  for (let i = periods.length - 1; i >= 0; i--) {
    const v = cellValue(row.cells[periods[i]]);
    if (v != null) return v;
  }
  return null;
}

/** Extract a summary snapshot of key metrics from grid cells.
 *  Used for AI context, monte carlo base scenario, etc. */
export function extractGridSummary(
  data: MatrixData,
): Record<string, number | null> {
  return {
    revenue: getLatestValue(data, 'revenue', 'total_revenue'),
    cogs: getLatestValue(data, 'cogs', 'total_cogs'),
    gross_profit: getLatestValue(data, 'gross_profit'),
    ebitda: getLatestValue(data, 'ebitda'),
    net_income: getLatestValue(data, 'net_income'),
    cash_balance: getLatestValue(data, 'cash_balance'),
    runway: getLatestValue(data, 'runway', 'runway_months'),
    free_cash_flow: getLatestValue(data, 'free_cash_flow'),
    total_opex: getLatestValue(data, 'total_opex'),
    rd: getLatestValue(data, 'opex_rd', 'rd_spend'),
    sm: getLatestValue(data, 'opex_sm', 'sm_spend'),
    ga: getLatestValue(data, 'opex_ga', 'ga_spend'),
  };
}

/** Build chart-ready time series from rows.
 *  Returns [{ period, Revenue: 50000, COGS: 20000, isForecast: false }, ...] */
export function buildChartData(
  data: MatrixData,
  rowMappings: Array<{ ids: string[]; label: string }>,
  forecastStartIndex?: number,
): Record<string, any>[] {
  const periods = getPeriodColumns(data);
  return periods.map((period, idx) => {
    const entry: Record<string, any> = {
      period,
      isForecast: forecastStartIndex != null && idx >= forecastStartIndex,
    };
    for (const mapping of rowMappings) {
      const row = findRow(data, ...mapping.ids);
      if (row) {
        const v = cellValue(row.cells[period]);
        if (v != null) entry[mapping.label] = v;
      }
    }
    return entry;
  });
}

// ---------------------------------------------------------------------------
// Forecast -> grid application
// ---------------------------------------------------------------------------

/** Maps backend forecast field names to possible grid row IDs.
 *  Tries each ID in order -- writes to the first one that exists in the grid. */
const FORECAST_TO_GRID: Record<string, string[]> = {
  revenue: ['revenue', 'total_revenue'],
  cogs: ['cogs', 'total_cogs'],
  gross_profit: ['gross_profit'],
  rd_spend: ['opex_rd', 'rd_spend'],
  sm_spend: ['opex_sm', 'sm_spend'],
  ga_spend: ['opex_ga', 'ga_spend'],
  total_opex: ['total_opex'],
  ebitda: ['ebitda'],
  capex: ['capex'],
  debt_service: ['debt_service'],
  tax_expense: ['tax_expense'],
  net_income: ['net_income'],
  free_cash_flow: ['free_cash_flow'],
  working_capital_delta: ['working_capital_delta'],
  cash_balance: ['cash_balance'],
  runway_months: ['runway_months', 'runway'],
  gross_burn_rate: ['gross_burn_rate'],
  net_burn_rate: ['net_burn_rate'],
  rule_of_40: ['rule_of_40'],
};

/** Apply forecast response (array of period dicts from /fpa/forecast) into matrixData.
 *  Call this with setMatrixData(prev => applyForecastToGrid(prev, data.forecast)). */
export function applyForecastToGrid(
  prev: MatrixData,
  forecast: Array<Record<string, any>>,
): MatrixData {
  const rowMap = new Map(
    prev.rows.map(r => [r.id, { ...r, cells: { ...r.cells } }]),
  );

  for (const month of forecast) {
    const colId = month.period;
    if (!colId) continue;
    for (const [backendKey, gridIds] of Object.entries(FORECAST_TO_GRID)) {
      const val = month[backendKey];
      if (val == null) continue;
      for (const gridId of gridIds) {
        const row = rowMap.get(gridId);
        if (row) {
          row.cells[colId] = { value: val, source: 'scenario' as any };
          break;
        }
      }
    }
  }

  // Ensure columns exist for all forecast periods
  const existingColIds = new Set(prev.columns.map(c => c.id));
  const newCols = [...prev.columns];
  for (const month of forecast) {
    if (month.period && !existingColIds.has(month.period)) {
      newCols.push({
        id: month.period,
        name: month.period,
        type: 'number',
      } as any);
      existingColIds.add(month.period);
    }
  }

  return { ...prev, rows: Array.from(rowMap.values()), columns: newCols };
}
