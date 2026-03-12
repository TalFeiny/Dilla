/**
 * Shared PnL column builder — single source of truth for period columns
 * used by both AGGridMatrix and UnifiedMatrix.
 *
 * Supports monthly, quarterly, and annual granularity with configurable
 * trailing/forward period counts.
 */

import type { MatrixColumn } from '@/components/matrix/UnifiedMatrix';
import type { Granularity } from './pnl-views';

export interface PnlColumnOptions {
  granularity?: Granularity;
  trailing?: number;
  forward?: number;
}

function monthLabel(d: Date): string {
  return d.toLocaleDateString('en-US', { month: 'short' }) + ' \u2019' + String(d.getFullYear()).slice(2);
}

function quarterLabel(year: number, q: number): string {
  return `Q${q} '${String(year).slice(2)}`;
}

export function buildPnlColumns(options?: PnlColumnOptions): MatrixColumn[] {
  const { granularity = 'monthly', trailing = 6, forward = 6 } = options || {};
  const now = new Date();
  const cols: MatrixColumn[] = [
    { id: 'lineItem', name: 'Line Item', type: 'text', width: 220, editable: false },
  ];

  if (granularity === 'annual') {
    const currentYear = now.getFullYear();
    for (let i = -trailing; i < forward; i++) {
      const year = currentYear + i;
      cols.push({ id: `${year}`, name: `${year}`, type: 'currency', width: 110, editable: true });
    }
  } else if (granularity === 'quarterly') {
    const currentQ = Math.ceil((now.getMonth() + 1) / 3);
    const currentYear = now.getFullYear();
    for (let i = -trailing; i < forward; i++) {
      let q = currentQ + i;
      let y = currentYear;
      while (q < 1) { q += 4; y--; }
      while (q > 4) { q -= 4; y++; }
      const id = `${y}-Q${q}`;
      cols.push({ id, name: quarterLabel(y, q), type: 'currency', width: 110, editable: true });
    }
  } else {
    // monthly (default)
    for (let i = -trailing; i < forward; i++) {
      const d = new Date(now.getFullYear(), now.getMonth() + i, 1);
      const yyyy = d.getFullYear();
      const mm = String(d.getMonth() + 1).padStart(2, '0');
      cols.push({ id: `${yyyy}-${mm}`, name: monthLabel(d), type: 'currency', width: 110, editable: true });
    }
  }

  return cols;
}

/**
 * Standard income statement skeleton rows — single source of truth.
 * Row IDs match backend/app/services/pnl_builder.py so that grid
 * suggestions land on the correct cells.
 */
export function buildPnlSkeletonRows(): import('@/components/matrix/UnifiedMatrix').MatrixRow[] {
  const row = (
    id: string,
    label: string,
    opts: { isHeader?: boolean; isTotal?: boolean; isComputed?: boolean; depth?: number; parentId?: string } = {},
  ): import('@/components/matrix/UnifiedMatrix').MatrixRow => ({
    id,
    cells: { lineItem: { value: label, source: 'api' as const } },
    depth: opts.depth ?? 0,
    isHeader: opts.isHeader ?? false,
    isTotal: opts.isTotal ?? false,
    isComputed: opts.isComputed ?? false,
    parentId: opts.parentId ?? null,
    childIds: [],
  });

  return [
    row('revenue_header', 'Revenue', { isHeader: true }),
    row('revenue', 'Revenue', { depth: 1 }),
    row('total_revenue', 'Total Revenue', { isTotal: true }),
    row('cogs_header', 'Cost of Sales', { isHeader: true }),
    row('cogs', 'COGS', { depth: 1 }),
    row('total_cogs', 'Total COGS', { isTotal: true }),
    row('gross_profit', 'Gross Profit', { isComputed: true, isTotal: true }),
    row('opex_header', 'Operating Expenses', { isHeader: true }),
    row('opex_rd', 'R&D', { depth: 1 }),
    row('opex_sm', 'Sales & Marketing', { depth: 1 }),
    row('opex_ga', 'G&A', { depth: 1 }),
    row('total_opex', 'Total OpEx', { isTotal: true }),
    row('ebitda', 'EBITDA', { isComputed: true, isTotal: true }),
    row('bottom_header', 'Cash & Runway', { isHeader: true }),
    row('cash_balance', 'Cash Balance', { depth: 1 }),
    row('runway', 'Runway (months)', { depth: 1 }),
  ];
}
