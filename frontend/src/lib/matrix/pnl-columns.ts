/**
 * Shared PnL column builder — single source of truth for the 12-month period
 * columns used by both AGGridMatrix and UnifiedMatrix.
 *
 * Generates trailing 6 months + current + forward 5 = 12 columns.
 */

import type { MatrixColumn } from '@/components/matrix/UnifiedMatrix';

export function buildPnlColumns(): MatrixColumn[] {
  const now = new Date();
  const cols: MatrixColumn[] = [
    { id: 'lineItem', name: 'Line Item', type: 'text', width: 220, editable: false },
  ];
  for (let i = -6; i < 6; i++) {
    const d = new Date(now.getFullYear(), now.getMonth() + i, 1);
    const yyyy = d.getFullYear();
    const mm = String(d.getMonth() + 1).padStart(2, '0');
    const id = `${yyyy}-${mm}`;
    const label = d.toLocaleDateString('en-US', { month: 'short' }) + ' \u2019' + String(yyyy).slice(2);
    cols.push({ id, name: label, type: 'currency', width: 110, editable: true });
  }
  return cols;
}
