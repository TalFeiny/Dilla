/**
 * Chart handling helper functions
 * Extracted from UnifiedMatrix.tsx and ChartViewport.tsx for maintainability
 */

export interface ChartConfig {
  type?: string;
  title?: string;
  data?: Record<string, unknown> | unknown[];
  description?: string;
  renderType?: string;
  source?: 'cell' | 'mcp';
  cellId?: string;
  rowId?: string;
  columnId?: string;
  companyName?: string;
}

const ADVANCED_CHART_TYPES = [
  'sankey', 'sunburst', 'heatmap', 'waterfall', 'boxplot',
  'candlestick', 'bubble', 'gantt', 'funnel', 'radialBar',
  'streamgraph', 'chord', 'force', 'side_by_side_sankey',
  'timeline_valuation', 'probability_cloud', 'pie', 'line', 'bar', 'treemap', 'scatter',
  'cap_table_evolution', 'cap_table_waterfall', 'breakpoint_chart',
  'dpi_sankey', 'radar_comparison', 'funnel_pipeline', 'scatter_multiples',
  'scenario_tree', 'scenario_paths', 'tornado', 'cash_flow_waterfall',
  // Analytics-bridge chart types
  'sensitivity_tornado', 'regression_line', 'monte_carlo_histogram',
  'revenue_forecast_decay', 'fund_scenarios', 'multi_chart', 'ltm_ntm_regression',
];

/**
 * Normalize chart config from metadata
 * Handles various formats: chart_to_create, chart_config, etc.
 */
export function normalizeChartConfig(metadata: any): ChartConfig | null {
  if (!metadata) return null;
  
  // Try different possible locations
  const chartConfig = metadata.chart_to_create ?? metadata.chart_config ?? metadata.chart;
  
  if (!chartConfig || typeof chartConfig !== 'object') {
    return null;
  }
  
  // Ensure it has required structure
  const normalized: ChartConfig = {
    type: chartConfig.type || 'bar',
    title: chartConfig.title,
    data: chartConfig.data,
    description: chartConfig.description,
    renderType: chartConfig.renderType || (isAdvancedChart(chartConfig.type) ? 'tableau' : 'basic'),
    ...chartConfig,
  };
  
  return normalized;
}

/**
 * Check if a chart should be displayed in ChartViewport
 */
export function shouldDisplayChart(chartConfig: ChartConfig | null): boolean {
  if (!chartConfig) return false;
  
  const renderType = chartConfig.renderType;
  const type = chartConfig.type?.toLowerCase();
  
  // Display if renderType is 'tableau' or if it's an advanced chart type
  return renderType === 'tableau' || (type ? isAdvancedChart(type) : false);
}

/**
 * Check if chart type is an advanced type that requires Tableau rendering
 */
function isAdvancedChart(type: string): boolean {
  return ADVANCED_CHART_TYPES.includes(type.toLowerCase());
}

/**
 * Merge existing chart config with new chart config
 */
export function mergeChartConfigs(
  existing: ChartConfig | null | undefined,
  newConfig: ChartConfig | null | undefined
): ChartConfig | null {
  if (!newConfig) return existing || null;
  if (!existing) return newConfig;
  
  // Merge with new config taking precedence
  return {
    ...existing,
    ...newConfig,
    data: newConfig.data || existing.data,
    // Preserve source metadata
    source: existing.source || newConfig.source,
    cellId: existing.cellId || newConfig.cellId,
    rowId: existing.rowId || newConfig.rowId,
    columnId: existing.columnId || newConfig.columnId,
    companyName: existing.companyName || newConfig.companyName,
  };
}

/**
 * Extract all charts from matrix data
 */
export function extractChartsFromMatrix(matrixData: {
  rows: Array<{
    id: string;
    companyName?: string;
    cells: Record<string, { metadata?: any }>;
  }>;
  metadata?: { charts?: any[] };
}): ChartConfig[] {
  const cellCharts: ChartConfig[] = [];
  const rawMcp = matrixData.metadata?.charts ?? [];
  const mcpChartsList = Array.isArray(rawMcp) ? rawMcp : [];

  // Extract charts from cell metadata
  matrixData.rows.forEach(row => {
    Object.entries(row.cells).forEach(([columnId, cell]) => {
      const chartConfig = normalizeChartConfig(cell.metadata);
      if (chartConfig && shouldDisplayChart(chartConfig)) {
        cellCharts.push({
          ...chartConfig,
          source: 'cell',
          cellId: `${row.id}-${columnId}`,
          rowId: row.id,
          columnId,
          companyName: row.companyName,
        });
      }
    });
  });

  // Extract charts from MCP orchestrator
  const mcpCharts: ChartConfig[] = mcpChartsList
    .map((c: any) => normalizeChartConfig(c))
    .filter((c): c is ChartConfig => c !== null && shouldDisplayChart(c))
    .map((c: ChartConfig) => ({ ...c, source: 'mcp' }));

  return [...cellCharts, ...mcpCharts];
}

/** Column ID → ChartGenerationSkill / deck-agent company field */
const MATRIX_TO_CHART_FIELD: Record<string, string> = {
  company: 'company',
  companyName: 'company',
  name: 'company',
  arr: 'revenue',
  currentArr: 'revenue',
  valuation: 'valuation',
  currentValuation: 'valuation',
  burnRate: 'burn_rate',
  runway: 'runway_months',
  runwayMonths: 'runway_months',
  cashInBank: 'cash_balance',
  grossMargin: 'gross_margin',
  totalInvested: 'total_funding',
  invested: 'total_funding',
  investmentAmount: 'total_funding',
  sector: 'sector',
  stage: 'stage',
};

/**
 * Transform matrix data into ChartGenerationSkill / deck-agent input format.
 * Reuses same field mapping as cell-workflows and deck orchestrator.
 */
export function matrixToChartInput(matrixData: {
  rows: Array<{
    id: string;
    companyName?: string;
    cells: Record<string, { value?: unknown }>;
  }>;
  columns?: Array<{ id: string }>;
}): { companies: Record<string, unknown>[]; data: Record<string, unknown> } {
  const rows = matrixData.rows ?? [];
  const columns = matrixData.columns ?? [];

  const companies: Record<string, unknown>[] = rows.map((row) => {
    const company: Record<string, unknown> = {
      company: row.companyName ?? row.id,
      id: row.id,
    };
    const cells = row.cells ?? {};
    for (const [colId, cell] of Object.entries(cells)) {
      const chartField = MATRIX_TO_CHART_FIELD[colId] ?? colId;
      const v = (cell as { value?: unknown })?.value;
      if (v === undefined || v === null || v === '') continue;
      // Keep strings for company/sector/stage; coerce numbers for metrics
      if (chartField === 'company' || chartField === 'sector' || chartField === 'stage') {
        company[chartField] = String(v);
      } else {
        const num = typeof v === 'number' ? v : parseFloat(String(v).replace(/[$,%]/g, ''));
        company[chartField] = Number.isFinite(num) ? num : v;
      }
    }
    return company;
  });

  const data: Record<string, unknown> = {
    companies,
    labels: companies.map((c) => c.company ?? c.id),
    // For ChartIntelligence / bar charts
    datasets: columns
      .filter((col) => MATRIX_TO_CHART_FIELD[col.id] || ['arr', 'valuation', 'burnRate', 'runway'].includes(col.id))
      .slice(0, 5)
      .map((col) => ({
        label: col.id,
        data: companies.map((c) => c[MATRIX_TO_CHART_FIELD[col.id] ?? col.id] ?? 0),
      })),
  };

  return { companies, data };
}
