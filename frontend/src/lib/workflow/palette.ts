// ---------------------------------------------------------------------------
// Workflow Builder — Palette Registry
// ---------------------------------------------------------------------------
// Maps chip definitions + operators into draggable palette items.

import type { PaletteCategory, PaletteItem } from './types';
import { DOMAIN_META } from '../chips/types';
import type { ChipDef } from '../chips/types';

// ── Operator definitions ─────────────────────────────────────────────────

const operators: PaletteItem[] = [
  // Control flow
  { id: 'op_loop', label: 'Loop', icon: 'Repeat', kind: 'operator', domain: 'transform', color: 'sky', operatorType: 'loop', description: 'Iterate over companies, scenarios, or periods', defaultParams: { loopOver: 'scenarios' } },
  { id: 'op_conditional', label: 'Conditional', icon: 'GitBranch', kind: 'operator', domain: 'transform', color: 'sky', operatorType: 'conditional', description: 'Branch based on a condition (if metric > threshold)', defaultParams: { metric: 'revenue', op: '>', threshold: 0 } },
  { id: 'op_bridge', label: 'Bridge', icon: 'Link', kind: 'operator', domain: 'bridge', color: 'fuchsia', operatorType: 'bridge', description: 'Chain multiple tools sequentially', defaultParams: {} },
  { id: 'op_parallel', label: 'Parallel', icon: 'Columns', kind: 'operator', domain: 'transform', color: 'sky', operatorType: 'parallel', description: 'Run branches concurrently, merge results', defaultParams: {} },
  { id: 'op_switch', label: 'Switch', icon: 'ListTree', kind: 'operator', domain: 'transform', color: 'sky', operatorType: 'switch', description: 'Multi-way branch (N paths based on value)', defaultParams: { cases: [] } },
  // Data/transform
  { id: 'op_filter', label: 'Filter', icon: 'Filter', kind: 'operator', domain: 'transform', color: 'sky', operatorType: 'filter', description: 'Subset data by condition', defaultParams: { field: '', op: '>', value: 0 } },
  { id: 'op_aggregate', label: 'Aggregate', icon: 'Sigma', kind: 'operator', domain: 'transform', color: 'sky', operatorType: 'aggregate', description: 'Sum/avg/median across items', defaultParams: { fn: 'sum' } },
  { id: 'op_map', label: 'Map', icon: 'ArrowRight', kind: 'operator', domain: 'transform', color: 'sky', operatorType: 'map', description: 'Transform each item in a collection', defaultParams: {} },
  { id: 'op_merge', label: 'Merge', icon: 'Merge', kind: 'operator', domain: 'transform', color: 'sky', operatorType: 'merge', description: 'Combine results from parallel paths', defaultParams: {} },
  // Events
  { id: 'op_event_business', label: 'Business Event', icon: 'Building2', kind: 'operator', domain: 'scenario', color: 'amber', operatorType: 'event_business', description: 'Model a business event (expansion, pivot, etc.)', defaultParams: { event: '' } },
  { id: 'op_event_macro', label: 'Macro Event', icon: 'Globe', kind: 'operator', domain: 'macro', color: 'red', operatorType: 'event_macro', description: 'Model a macro event with causal chains', defaultParams: { event: '' } },
  { id: 'op_event_funding', label: 'Funding Event', icon: 'Banknote', kind: 'operator', domain: 'funding', color: 'teal', operatorType: 'event_funding', description: 'Model equity or debt raise', defaultParams: { type: 'equity', amount: 0 } },
  // Probabilistic
  { id: 'op_prior', label: 'Prior', icon: 'BarChart3', kind: 'operator', domain: 'analytics', color: 'blue', operatorType: 'prior', description: 'Set confidence/distribution on parameters', defaultParams: { distribution: 'normal' } },
];

// ── Output node ──────────────────────────────────────────────────────────

const outputItems: PaletteItem[] = [
  { id: 'output_memo', label: 'Memo Section', icon: 'FileText', kind: 'output', domain: 'report', color: 'slate', description: 'Output to memo document section', defaultParams: { format: 'memo-section' } },
  { id: 'output_deck', label: 'Deck Slide', icon: 'Presentation', kind: 'output', domain: 'report', color: 'slate', description: 'Output to presentation slide', defaultParams: { format: 'deck-slide' } },
  { id: 'output_chart', label: 'Chart', icon: 'BarChart', kind: 'output', domain: 'chart', color: 'pink', description: 'Output as standalone chart', defaultParams: { format: 'chart' } },
  { id: 'output_grid', label: 'Grid Write', icon: 'Table2', kind: 'output', domain: 'data', color: 'zinc', description: 'Write results back to grid cells', defaultParams: { format: 'grid' } },
  { id: 'output_export', label: 'Export', icon: 'Download', kind: 'output', domain: 'data', color: 'zinc', description: 'Export as PDF/Excel/CSV', defaultParams: { format: 'export', fileType: 'pdf' } },
];

// ── Formula / Driver ─────────────────────────────────────────────────────

const formulaItems: PaletteItem[] = [
  { id: 'formula', label: 'Formula', icon: 'Calculator', kind: 'formula', domain: 'modeling', color: 'lime', description: 'Inline expression node', defaultParams: { expression: '' } },
];

const driverItems: PaletteItem[] = [
  { id: 'driver_revenue_growth', label: 'Revenue Growth', icon: 'TrendingUp', kind: 'driver', domain: 'driver', color: 'purple', description: 'Override revenue growth rate', defaultParams: { value: 0 } },
  { id: 'driver_burn_rate', label: 'Burn Rate', icon: 'Flame', kind: 'driver', domain: 'driver', color: 'purple', description: 'Override monthly burn rate', defaultParams: { value: 0 } },
  { id: 'driver_headcount', label: 'Headcount', icon: 'Users', kind: 'driver', domain: 'driver', color: 'purple', description: 'Override headcount assumption', defaultParams: { value: 0 } },
  { id: 'driver_churn', label: 'Churn Rate', icon: 'UserMinus', kind: 'driver', domain: 'driver', color: 'purple', description: 'Override churn rate', defaultParams: { value: 0 } },
  { id: 'driver_cac', label: 'CAC', icon: 'DollarSign', kind: 'driver', domain: 'driver', color: 'purple', description: 'Override customer acquisition cost', defaultParams: { value: 0 } },
  { id: 'driver_custom', label: 'Custom Driver', icon: 'Sliders', kind: 'driver', domain: 'driver', color: 'purple', description: 'Custom driver override', defaultParams: { key: '', value: 0 } },
];

// ── Build palette from chip registry ─────────────────────────────────────

/**
 * Convert chip defs from the registry into palette items (tool nodes).
 * Only includes chips that are actual backend tools (not operators/drivers).
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
