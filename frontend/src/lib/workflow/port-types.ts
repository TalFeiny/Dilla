// ---------------------------------------------------------------------------
// Workflow Port Type System
// ---------------------------------------------------------------------------
// Typed ports for workflow nodes. Every node declares what data it accepts
// (input ports) and what it produces (output ports). Edges are only valid
// when the source port type is compatible with the target port type.
//
// A "transform" operator can bridge incompatible types by reshaping data.

/** Data types that flow between nodes */
export type PortDataType =
  | 'forecast'       // Monthly forecast array [{month, revenue, cogs, opex, ebitda, cash, ...}]
  | 'pnl'            // P&L periods with hierarchical rows
  | 'balance_sheet'  // Assets / liabilities / equity sections
  | 'cash_flow'      // Cash flow model array
  | 'variance'       // Variance report [{category, budget, actual, variance_pct}]
  | 'scenario'       // Single scenario branch {branch_id, assumptions, forecast}
  | 'scenario_set'   // Multiple scenarios for comparison
  | 'valuation'      // {fair_value, method, equity_value, summary}
  | 'cap_table'      // {rounds[], founder_ownership, sankey}
  | 'waterfall'      // Liquidation distributions
  | 'sensitivity'    // 2D sensitivity matrix
  | 'monte_carlo'    // Probability distributions {p10..p90}
  | 'model_spec'     // Constructed forecast model (ModelSpec[])
  | 'drivers'        // Driver overrides {driver_id: value}
  | 'number'         // Single numeric value
  | 'table'          // Generic tabular data
  | 'chart'          // Chart specification
  | 'narrative'      // Text / memo / report output
  | 'any';           // Accepts anything — used by output/formula/transform nodes

/** Port definition — one input or output slot on a node */
export interface PortDef {
  /** Unique within the node, e.g. 'forecast_out', 'data_in' */
  id: string;
  /** Human label, e.g. 'Forecast', 'Data' */
  label: string;
  /** What type of data flows through this port */
  dataType: PortDataType;
  direction: 'in' | 'out';
  /** Must be connected for the node to execute? */
  required: boolean;
  /** Can accept multiple connections? (e.g. merge, aggregate) */
  multi: boolean;
}

// ---------------------------------------------------------------------------
// Compatibility — which output types can feed into which input types
// ---------------------------------------------------------------------------

/**
 * Map from output type → set of input types it can connect to.
 * If a target port accepts 'any', it always matches (handled in canConnect).
 * If a source port produces 'any', it always matches too.
 */
const COMPAT: Record<PortDataType, PortDataType[]> = {
  forecast:      ['forecast', 'pnl', 'variance', 'scenario', 'cash_flow', 'table', 'chart', 'narrative'],
  pnl:           ['pnl', 'table', 'chart', 'narrative'],
  balance_sheet: ['balance_sheet', 'table', 'chart', 'narrative'],
  cash_flow:     ['cash_flow', 'table', 'chart', 'narrative'],
  variance:      ['variance', 'table', 'chart', 'narrative'],
  scenario:      ['scenario', 'scenario_set', 'forecast', 'table', 'chart', 'narrative'],
  scenario_set:  ['scenario_set', 'table', 'chart', 'narrative'],
  valuation:     ['valuation', 'sensitivity', 'waterfall', 'number', 'table', 'chart', 'narrative'],
  cap_table:     ['cap_table', 'waterfall', 'table', 'chart', 'narrative'],
  waterfall:     ['waterfall', 'table', 'chart', 'narrative'],
  sensitivity:   ['sensitivity', 'table', 'chart', 'narrative'],
  monte_carlo:   ['monte_carlo', 'table', 'chart', 'narrative'],
  model_spec:    ['model_spec', 'forecast'],
  drivers:       ['drivers', 'forecast', 'scenario'],
  number:        ['number', 'table', 'chart'],
  table:         ['table', 'chart', 'narrative'],
  chart:         ['chart'],
  narrative:     ['narrative'],
  any:           [], // 'any' is handled specially — always matches
};

/** Check if an output port can connect to an input port */
export function canConnect(source: PortDef, target: PortDef): boolean {
  // Direction check
  if (source.direction !== 'out' || target.direction !== 'in') return false;
  // 'any' on either side always matches
  if (source.dataType === 'any' || target.dataType === 'any') return true;
  // Same type always works
  if (source.dataType === target.dataType) return true;
  // Check compatibility map
  return COMPAT[source.dataType]?.includes(target.dataType) ?? false;
}

/** Get a human-readable label for a port data type */
export function portTypeLabel(dt: PortDataType): string {
  const labels: Record<PortDataType, string> = {
    forecast: 'Forecast', pnl: 'P&L', balance_sheet: 'Balance Sheet',
    cash_flow: 'Cash Flow', variance: 'Variance', scenario: 'Scenario',
    scenario_set: 'Scenarios', valuation: 'Valuation', cap_table: 'Cap Table',
    waterfall: 'Waterfall', sensitivity: 'Sensitivity', monte_carlo: 'Monte Carlo',
    model_spec: 'Model Spec', drivers: 'Drivers', number: 'Number',
    table: 'Table', chart: 'Chart', narrative: 'Narrative', any: 'Any',
  };
  return labels[dt] || dt;
}

// ---------------------------------------------------------------------------
// Port color map — each data type gets a consistent color for handles
// ---------------------------------------------------------------------------

export const PORT_COLORS: Record<PortDataType, string> = {
  forecast:      '#10b981', // emerald
  pnl:           '#10b981',
  balance_sheet: '#10b981',
  cash_flow:     '#10b981',
  variance:      '#f59e0b', // amber
  scenario:      '#f59e0b',
  scenario_set:  '#f59e0b',
  valuation:     '#6366f1', // indigo
  cap_table:     '#6366f1',
  waterfall:     '#6366f1',
  sensitivity:   '#3b82f6', // blue
  monte_carlo:   '#3b82f6',
  model_spec:    '#84cc16', // lime
  drivers:       '#a855f7', // purple
  number:        '#64748b', // slate
  table:         '#64748b',
  chart:         '#ec4899', // pink
  narrative:     '#64748b',
  any:           '#6b7280', // gray
};

// ---------------------------------------------------------------------------
// Port presets — common port configurations reusable across chips
// ---------------------------------------------------------------------------

export const PORTS = {
  // ── Inputs ──
  forecastIn:   (required = false): PortDef => ({ id: 'forecast_in', label: 'Forecast', dataType: 'forecast', direction: 'in', required, multi: false }),
  driversIn:   (required = false): PortDef => ({ id: 'drivers_in', label: 'Drivers', dataType: 'drivers', direction: 'in', required, multi: false }),
  scenarioIn:  (required = false): PortDef => ({ id: 'scenario_in', label: 'Scenario', dataType: 'scenario', direction: 'in', required, multi: false }),
  capTableIn:  (required = false): PortDef => ({ id: 'cap_table_in', label: 'Cap Table', dataType: 'cap_table', direction: 'in', required, multi: false }),
  valuationIn: (required = false): PortDef => ({ id: 'valuation_in', label: 'Valuation', dataType: 'valuation', direction: 'in', required, multi: false }),
  modelIn:     (required = false): PortDef => ({ id: 'model_in', label: 'Model', dataType: 'model_spec', direction: 'in', required, multi: false }),
  dataIn:      (required = false): PortDef => ({ id: 'data_in', label: 'Data', dataType: 'any', direction: 'in', required, multi: false }),
  dataInMulti: (required = false): PortDef => ({ id: 'data_in', label: 'Data', dataType: 'any', direction: 'in', required, multi: true }),
  tableIn:     (required = false): PortDef => ({ id: 'table_in', label: 'Table', dataType: 'table', direction: 'in', required, multi: false }),
  scenariosIn: (required = false): PortDef => ({ id: 'scenarios_in', label: 'Scenarios', dataType: 'scenario', direction: 'in', required, multi: true }),

  // ── Outputs ──
  forecastOut:  (): PortDef => ({ id: 'forecast_out', label: 'Forecast', dataType: 'forecast', direction: 'out', required: false, multi: false }),
  pnlOut:       (): PortDef => ({ id: 'pnl_out', label: 'P&L', dataType: 'pnl', direction: 'out', required: false, multi: false }),
  bsOut:        (): PortDef => ({ id: 'bs_out', label: 'Balance Sheet', dataType: 'balance_sheet', direction: 'out', required: false, multi: false }),
  cashFlowOut:  (): PortDef => ({ id: 'cf_out', label: 'Cash Flow', dataType: 'cash_flow', direction: 'out', required: false, multi: false }),
  varianceOut:  (): PortDef => ({ id: 'variance_out', label: 'Variance', dataType: 'variance', direction: 'out', required: false, multi: false }),
  scenarioOut:  (): PortDef => ({ id: 'scenario_out', label: 'Scenario', dataType: 'scenario', direction: 'out', required: false, multi: false }),
  scenarioSetOut: (): PortDef => ({ id: 'scenario_set_out', label: 'Scenarios', dataType: 'scenario_set', direction: 'out', required: false, multi: false }),
  valuationOut: (): PortDef => ({ id: 'valuation_out', label: 'Valuation', dataType: 'valuation', direction: 'out', required: false, multi: false }),
  capTableOut:  (): PortDef => ({ id: 'cap_table_out', label: 'Cap Table', dataType: 'cap_table', direction: 'out', required: false, multi: false }),
  waterfallOut: (): PortDef => ({ id: 'waterfall_out', label: 'Waterfall', dataType: 'waterfall', direction: 'out', required: false, multi: false }),
  sensitivityOut: (): PortDef => ({ id: 'sensitivity_out', label: 'Sensitivity', dataType: 'sensitivity', direction: 'out', required: false, multi: false }),
  monteCarloOut: (): PortDef => ({ id: 'mc_out', label: 'Monte Carlo', dataType: 'monte_carlo', direction: 'out', required: false, multi: false }),
  modelOut:     (): PortDef => ({ id: 'model_out', label: 'Model', dataType: 'model_spec', direction: 'out', required: false, multi: false }),
  driversOut:   (): PortDef => ({ id: 'drivers_out', label: 'Drivers', dataType: 'drivers', direction: 'out', required: false, multi: false }),
  numberOut:    (): PortDef => ({ id: 'number_out', label: 'Value', dataType: 'number', direction: 'out', required: false, multi: false }),
  tableOut:     (): PortDef => ({ id: 'table_out', label: 'Table', dataType: 'table', direction: 'out', required: false, multi: false }),
  chartOut:     (): PortDef => ({ id: 'chart_out', label: 'Chart', dataType: 'chart', direction: 'out', required: false, multi: false }),
  narrativeOut: (): PortDef => ({ id: 'narrative_out', label: 'Text', dataType: 'narrative', direction: 'out', required: false, multi: false }),
  dataOut:      (): PortDef => ({ id: 'data_out', label: 'Data', dataType: 'any', direction: 'out', required: false, multi: false }),
  trueOut:      (): PortDef => ({ id: 'true_out', label: 'True', dataType: 'any', direction: 'out', required: false, multi: false }),
  falseOut:     (): PortDef => ({ id: 'false_out', label: 'False', dataType: 'any', direction: 'out', required: false, multi: false }),
} as const;
