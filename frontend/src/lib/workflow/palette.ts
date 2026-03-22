// ---------------------------------------------------------------------------
// Workflow Builder — Palette Registry
// ---------------------------------------------------------------------------
// Maps chip definitions + operators into draggable palette items.

import type { PaletteCategory, PaletteItem } from './types';
import { DOMAIN_META } from '../chips/types';
import type { ChipDef } from '../chips/types';
import { PORTS } from './port-types';

// ── Trigger definitions ──────────────────────────────────────────────────

const triggerItems: PaletteItem[] = [
  { id: 'trigger_manual', label: 'Manual Trigger', icon: 'Play', kind: 'trigger', domain: 'transform' as any, color: 'emerald', description: 'Start workflow manually with the Run button', defaultParams: {}, outputPorts: [PORTS.dataOut()] },
  { id: 'trigger_schedule', label: 'Scheduled', icon: 'Clock', kind: 'trigger', domain: 'transform' as any, color: 'emerald', description: 'Run workflow on a schedule (cron)', defaultParams: { cron: '0 9 * * 1' }, outputPorts: [PORTS.dataOut()] },
  { id: 'trigger_data_change', label: 'Data Changed', icon: 'RefreshCw', kind: 'trigger', domain: 'data' as any, color: 'emerald', description: 'Trigger when financial data updates', defaultParams: { watchMetric: 'revenue' }, outputPorts: [PORTS.dataOut()] },
  { id: 'trigger_event', label: 'Event Trigger', icon: 'Zap', kind: 'trigger', domain: 'transform' as any, color: 'emerald', description: 'Trigger on external event (webhook, alert)', defaultParams: {}, outputPorts: [PORTS.dataOut()] },
];

// ── Operator definitions ─────────────────────────────────────────────────

const operators: PaletteItem[] = [
  // Control flow
  {
    id: 'op_loop', label: 'Loop', icon: 'Repeat', kind: 'operator', domain: 'transform', color: 'sky', operatorType: 'loop',
    description: 'Iterate over companies, scenarios, or periods',
    defaultParams: { loopOver: 'scenarios', variable: 'item' },
    inputPorts: [PORTS.dataIn(true)],
    outputPorts: [PORTS.dataOut()],
  },
  {
    id: 'op_conditional', label: 'If / Else', icon: 'GitBranch', kind: 'operator', domain: 'transform', color: 'sky', operatorType: 'conditional',
    description: 'Branch based on a condition (if metric > threshold)',
    defaultParams: { metric: 'revenue', op: '>', threshold: 0 },
    inputPorts: [PORTS.dataIn(true)],
    outputPorts: [PORTS.trueOut(), PORTS.falseOut()],
  },
  {
    id: 'op_bridge', label: 'Bridge', icon: 'Link', kind: 'operator', domain: 'bridge', color: 'fuchsia', operatorType: 'bridge',
    description: 'Chain multiple tools sequentially',
    defaultParams: {},
    inputPorts: [PORTS.dataIn(true)],
    outputPorts: [PORTS.dataOut()],
  },
  {
    id: 'op_parallel', label: 'Parallel', icon: 'Columns', kind: 'operator', domain: 'transform', color: 'sky', operatorType: 'parallel',
    description: 'Run branches concurrently, merge results',
    defaultParams: {},
    inputPorts: [PORTS.dataIn(true)],
    outputPorts: [PORTS.dataOut()],
  },
  {
    id: 'op_switch', label: 'Switch', icon: 'ListTree', kind: 'operator', domain: 'transform', color: 'sky', operatorType: 'switch',
    description: 'Multi-way branch (N paths based on value)',
    defaultParams: { field: '', cases: [] },
    inputPorts: [PORTS.dataIn(true)],
    outputPorts: [PORTS.dataOut()],
  },
  // Data/transform
  {
    id: 'op_filter', label: 'Filter', icon: 'Filter', kind: 'operator', domain: 'transform', color: 'sky', operatorType: 'filter',
    description: 'Subset data by condition',
    defaultParams: { field: '', op: '>', value: 0 },
    inputPorts: [PORTS.dataIn(true)],
    outputPorts: [PORTS.dataOut()],
  },
  {
    id: 'op_aggregate', label: 'Aggregate', icon: 'Sigma', kind: 'operator', domain: 'transform', color: 'sky', operatorType: 'aggregate',
    description: 'Sum/avg/median across items',
    defaultParams: { fn: 'sum', field: '', groupBy: '' },
    inputPorts: [PORTS.dataInMulti(true)],
    outputPorts: [PORTS.dataOut()],
  },
  {
    id: 'op_map', label: 'Map', icon: 'ArrowRight', kind: 'operator', domain: 'transform', color: 'sky', operatorType: 'map',
    description: 'Transform each item with an expression',
    defaultParams: { expression: '', outputField: '' },
    inputPorts: [PORTS.dataIn(true)],
    outputPorts: [PORTS.dataOut()],
  },
  {
    id: 'op_merge', label: 'Merge', icon: 'Merge', kind: 'operator', domain: 'transform', color: 'sky', operatorType: 'merge',
    description: 'Combine results from multiple paths',
    defaultParams: { strategy: 'concat', joinKey: '' },
    inputPorts: [PORTS.dataInMulti(true)],
    outputPorts: [PORTS.dataOut()],
  },
  // Transform — reshapes mismatching data between nodes
  {
    id: 'op_transform', label: 'Transform', icon: 'ArrowLeftRight', kind: 'operator', domain: 'transform', color: 'sky', operatorType: 'transform',
    description: 'Reshape data to fit the next node\'s expected input schema',
    defaultParams: { mapping: '', outputType: 'any' },
    inputPorts: [PORTS.dataIn(true)],
    outputPorts: [PORTS.dataOut()],
  },
  // Events
  {
    id: 'op_event_business', label: 'Business Event', icon: 'Building2', kind: 'operator', domain: 'scenario', color: 'amber', operatorType: 'event_business',
    description: 'Model a business event (expansion, pivot, etc.)',
    defaultParams: { event: '' },
    inputPorts: [PORTS.forecastIn()],
    outputPorts: [PORTS.scenarioOut()],
  },
  {
    id: 'op_event_macro', label: 'Macro Event', icon: 'Globe', kind: 'operator', domain: 'macro', color: 'red', operatorType: 'event_macro',
    description: 'Model a macro event with causal chains',
    defaultParams: { event: '' },
    inputPorts: [PORTS.forecastIn()],
    outputPorts: [PORTS.scenarioOut()],
  },
  {
    id: 'op_event_funding', label: 'Funding Event', icon: 'Banknote', kind: 'operator', domain: 'funding', color: 'teal', operatorType: 'event_funding',
    description: 'Model equity or debt raise',
    defaultParams: { event: '' },
    inputPorts: [PORTS.forecastIn(), PORTS.capTableIn()],
    outputPorts: [PORTS.forecastOut(), PORTS.capTableOut()],
  },
  // Probabilistic
  {
    id: 'op_prior', label: 'Prior', icon: 'BarChart3', kind: 'operator', domain: 'analytics', color: 'blue', operatorType: 'prior',
    description: 'Set confidence/distribution on parameters',
    defaultParams: { parameter: '', distribution: 'normal', low: 0, high: 0 },
    inputPorts: [PORTS.dataIn()],
    outputPorts: [PORTS.dataOut()],
  },
];

// ── Output node ──────────────────────────────────────────────────────────

const outputItems: PaletteItem[] = [
  { id: 'output_memo', label: 'Memo Section', icon: 'FileText', kind: 'output', domain: 'report', color: 'slate', description: 'Output to memo document section', defaultParams: { format: 'memo-section' }, inputPorts: [PORTS.dataIn(true)] },
  { id: 'output_deck', label: 'Deck Slide', icon: 'Presentation', kind: 'output', domain: 'report', color: 'slate', description: 'Output to presentation slide', defaultParams: { format: 'deck-slide' }, inputPorts: [PORTS.dataIn(true)] },
  { id: 'output_chart', label: 'Chart', icon: 'BarChart', kind: 'output', domain: 'chart', color: 'pink', description: 'Output as standalone chart', defaultParams: { format: 'chart' }, inputPorts: [PORTS.dataIn(true)] },
  { id: 'output_grid', label: 'Grid Write', icon: 'Table2', kind: 'output', domain: 'data', color: 'zinc', description: 'Write results back to grid cells', defaultParams: { format: 'grid' }, inputPorts: [PORTS.dataIn(true)] },
  { id: 'output_export', label: 'Export', icon: 'Download', kind: 'output', domain: 'data', color: 'zinc', description: 'Export as PDF/Excel/CSV', defaultParams: { format: 'export', fileType: 'pdf' }, inputPorts: [PORTS.dataIn(true)] },
];

// ── Formula / Driver ─────────────────────────────────────────────────────

const formulaItems: PaletteItem[] = [
  {
    id: 'formula', label: 'Formula', icon: 'Calculator', kind: 'formula', domain: 'modeling', color: 'lime',
    description: 'Inline expression node',
    defaultParams: { expression: '' },
    inputPorts: [PORTS.dataIn()],
    outputPorts: [PORTS.numberOut()],
  },
];

const driverItems: PaletteItem[] = [
  // Growth & revenue
  { id: 'driver_revenue_growth', label: 'Revenue Growth', icon: 'TrendingUp', kind: 'driver', domain: 'driver', color: 'purple', description: 'Override revenue growth rate', defaultParams: { key: 'revenue_growth_override', value: 0 }, outputPorts: [PORTS.driversOut()] },
  { id: 'driver_pricing', label: 'Pricing Change', icon: 'Tag', kind: 'driver', domain: 'driver', color: 'purple', description: 'Override pricing % change', defaultParams: { key: 'pricing_pct_change', value: 0 }, outputPorts: [PORTS.driversOut()] },
  { id: 'driver_nrr', label: 'Net Revenue Retention', icon: 'Repeat', kind: 'driver', domain: 'driver', color: 'purple', description: 'Override NRR', defaultParams: { key: 'nrr', value: 1.1 }, outputPorts: [PORTS.driversOut()] },
  { id: 'driver_acv', label: 'ACV Override', icon: 'CreditCard', kind: 'driver', domain: 'driver', color: 'purple', description: 'Override average contract value', defaultParams: { key: 'acv_override', value: 0 }, outputPorts: [PORTS.driversOut()] },
  // Costs & burn
  { id: 'driver_burn_rate', label: 'Burn Rate', icon: 'Flame', kind: 'driver', domain: 'driver', color: 'purple', description: 'Override monthly burn rate', defaultParams: { key: 'burn_rate_override', value: 0 }, outputPorts: [PORTS.driversOut()] },
  { id: 'driver_headcount', label: 'Headcount', icon: 'Users', kind: 'driver', domain: 'driver', color: 'purple', description: 'Override headcount assumption', defaultParams: { key: 'headcount_override', value: 0 }, outputPorts: [PORTS.driversOut()] },
  { id: 'driver_gross_margin', label: 'Gross Margin', icon: 'Percent', kind: 'driver', domain: 'driver', color: 'purple', description: 'Override gross margin', defaultParams: { key: 'gross_margin_override', value: 0 }, outputPorts: [PORTS.driversOut()] },
  { id: 'driver_capex', label: 'CapEx Override', icon: 'HardDrive', kind: 'driver', domain: 'driver', color: 'purple', description: 'Override monthly CapEx', defaultParams: { key: 'capex_override', value: 0 }, outputPorts: [PORTS.driversOut()] },
  // Unit economics
  { id: 'driver_churn', label: 'Churn Rate', icon: 'UserMinus', kind: 'driver', domain: 'driver', color: 'purple', description: 'Override churn rate', defaultParams: { key: 'churn_override', value: 0 }, outputPorts: [PORTS.driversOut()] },
  { id: 'driver_cac', label: 'CAC', icon: 'DollarSign', kind: 'driver', domain: 'driver', color: 'purple', description: 'Override customer acquisition cost', defaultParams: { key: 'cac_override', value: 0 }, outputPorts: [PORTS.driversOut()] },
  { id: 'driver_sales_cycle', label: 'Sales Cycle', icon: 'Clock', kind: 'driver', domain: 'driver', color: 'purple', description: 'Override sales cycle months', defaultParams: { key: 'sales_cycle_months', value: 0 }, outputPorts: [PORTS.driversOut()] },
  // Capital
  { id: 'driver_funding', label: 'Funding Injection', icon: 'Banknote', kind: 'driver', domain: 'driver', color: 'teal', description: 'One-time funding injection', defaultParams: { key: 'funding_injection', value: 0 }, outputPorts: [PORTS.driversOut()] },
  { id: 'driver_debt_service', label: 'Debt Service', icon: 'Landmark', kind: 'driver', domain: 'driver', color: 'purple', description: 'Monthly debt service payments', defaultParams: { key: 'debt_service_monthly', value: 0 }, outputPorts: [PORTS.driversOut()] },
  { id: 'driver_tax_rate', label: 'Tax Rate', icon: 'Percent', kind: 'driver', domain: 'driver', color: 'purple', description: 'Override tax rate', defaultParams: { key: 'tax_rate', value: 0 }, outputPorts: [PORTS.driversOut()] },
  // Flexible
  { id: 'driver_custom', label: 'Custom Driver', icon: 'Sliders', kind: 'driver', domain: 'driver', color: 'purple', description: 'Custom driver override', defaultParams: { key: '', value: 0 }, outputPorts: [PORTS.driversOut()] },
];

// ── Build palette from chip registry ─────────────────────────────────────

/**
 * Convert chip defs from the registry into palette items (tool nodes).
 * Passes through inputPorts/outputPorts from chip definitions.
 */
export function chipsToPaletteItems(chips: ChipDef[]): PaletteItem[] {
  return chips
    .filter((c) => !c.kind || c.kind === 'tool' || c.kind === 'event' || c.kind === 'chart')
    .map((c) => ({
      id: c.id,
      label: c.label,
      icon: c.icon,
      kind: 'tool' as const,
      domain: c.domain,
      color: DOMAIN_META[c.domain]?.color || 'gray',
      chipId: c.id,
      chipDef: c,
      defaultParams: Object.fromEntries(c.params.map((p) => [p.key, p.default])),
      inputPorts: c.inputPorts,
      outputPorts: c.outputPorts,
      description: c.description,
    }));
}

/**
 * Build the full palette with categories.
 * Pass the chip registry to generate tool categories dynamically.
 */
export function buildPalette(chips: ChipDef[]): PaletteCategory[] {
  const toolItems = chipsToPaletteItems(chips);

  // Group tools by domain
  const domainGroups = new Map<string, PaletteItem[]>();
  for (const item of toolItems) {
    const domain = item.domain;
    if (!domainGroups.has(domain)) domainGroups.set(domain, []);
    domainGroups.get(domain)!.push(item);
  }

  const categories: PaletteCategory[] = [];

  // Triggers — always first
  categories.push({
    id: 'cat_triggers',
    label: 'Triggers',
    icon: 'Play',
    color: 'emerald',
    items: triggerItems,
  });

  // Tool categories by domain
  const domainOrder: string[] = ['fpa', 'scenario', 'capital', 'funding', 'analytics', 'portfolio', 'macro', 'intel', 'data', 'report'];
  for (const domain of domainOrder) {
    const items = domainGroups.get(domain);
    if (!items || items.length === 0) continue;
    const meta = DOMAIN_META[domain as keyof typeof DOMAIN_META];
    if (!meta) continue;
    categories.push({
      id: `cat_${domain}`,
      label: meta.label,
      icon: meta.icon,
      color: meta.color,
      items,
    });
  }

  // Operators
  categories.push({
    id: 'cat_operators',
    label: 'Operators',
    icon: 'Workflow',
    color: 'sky',
    items: operators,
  });

  // Drivers
  categories.push({
    id: 'cat_drivers',
    label: 'Drivers',
    icon: 'Sliders',
    color: 'purple',
    items: driverItems,
  });

  // Formula
  categories.push({
    id: 'cat_formula',
    label: 'Formula',
    icon: 'Calculator',
    color: 'lime',
    items: formulaItems,
  });

  // Output
  categories.push({
    id: 'cat_output',
    label: 'Output',
    icon: 'ArrowDownToLine',
    color: 'slate',
    items: outputItems,
  });

  return categories;
}
