/**
 * Portfolio Context Compressor
 * Compresses portfolio data into compact format for @ symbol queries (< 2KB)
 */

import { MatrixData, MatrixRow } from '@/components/matrix/UnifiedMatrix';

export interface CompressedPortfolioContext {
  text: string;
  size: number;
  companyCount: number;
}

/**
 * Compress portfolio matrix data into compact text format
 * Format: @CompanyName ARR: $X, Burn: $Y, Runway: Zmo, Margin: A%, NAV: $B
 */
export function compressPortfolioContext(
  matrixData: MatrixData,
  maxSize: number = 2000
): CompressedPortfolioContext {
  if (!matrixData || !matrixData.rows.length) {
    return {
      text: '',
      size: 0,
      companyCount: 0,
    };
  }

  const lines: string[] = [];
  let currentSize = 0;

  // Helper to format currency compactly
  const formatCompactCurrency = (value: number | undefined): string => {
    if (!value && value !== 0) return '-';
    if (value >= 1000000000) return `$${(value / 1000000000).toFixed(1)}B`;
    if (value >= 1000000) return `$${(value / 1000000).toFixed(1)}M`;
    if (value >= 1000) return `$${(value / 1000).toFixed(0)}K`;
    return `$${value.toFixed(0)}`;
  };

  // Helper to format percentage
  const formatCompactPercent = (value: number | undefined): string => {
    if (!value && value !== 0) return '-';
    return `${(value * 100).toFixed(0)}%`;
  };

  // Extract key metrics for each company
  for (const row of matrixData.rows) {
    const companyName = row.companyName || row.cells['company']?.value || 'Unknown';
    
    // Get key metrics
    const arr = row.cells['arr']?.value;
    const burnRate = row.cells['burnRate']?.value;
    const runway = row.cells['runway']?.value;
    const grossMargin = row.cells['grossMargin']?.value;
    const nav = row.cells['nav']?.value;
    const valuation = row.cells['valuation']?.value;
    const ownership = row.cells['ownership']?.value;

    // Build compact line
    const parts: string[] = [`@${companyName}`];
    
    if (arr !== undefined && arr !== null) {
      parts.push(`ARR: ${formatCompactCurrency(arr)}`);
    }
    if (burnRate !== undefined && burnRate !== null) {
      parts.push(`Burn: ${formatCompactCurrency(burnRate)}`);
    }
    if (runway !== undefined && runway !== null) {
      parts.push(`Runway: ${runway}mo`);
    }
    if (grossMargin !== undefined && grossMargin !== null) {
      parts.push(`Margin: ${formatCompactPercent(grossMargin)}`);
    }
    if (nav !== undefined && nav !== null) {
      parts.push(`NAV: ${formatCompactCurrency(nav)}`);
    } else if (valuation !== undefined && ownership !== undefined) {
      // Calculate NAV if not directly available
      const calculatedNav = (valuation || 0) * ((ownership || 0) / 100);
      if (calculatedNav > 0) {
        parts.push(`NAV: ${formatCompactCurrency(calculatedNav)}`);
      }
    }

    const line = parts.join(', ');
    const lineSize = new Blob([line]).size;

    // Check if adding this line would exceed max size
    if (currentSize + lineSize + 1 > maxSize && lines.length > 0) {
      break; // Stop if we'd exceed the limit
    }

    lines.push(line);
    currentSize += lineSize + 1; // +1 for newline
  }

  const text = lines.join('\n');
  const finalSize = new Blob([text]).size;

  return {
    text,
    size: finalSize,
    companyCount: lines.length,
  };
}

/**
 * Copy compressed context to clipboard
 */
export async function copyCompressedContextToClipboard(
  context: CompressedPortfolioContext
): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(context.text);
    return true;
  } catch (err) {
    console.error('Failed to copy to clipboard:', err);
    return false;
  }
}

/**
 * Build a compact grid snapshot for agent context (< 5KB).
 * Per-row: rowId, companyName, and key column values (ARR, valuation, burn, etc.)
 */
export function buildGridSnapshot(
  matrixData: MatrixData,
  maxSizeBytes: number = 5000
): { rows: Array<{ rowId: string; companyName: string; cells: Record<string, unknown> }>; columns: Array<{ id: string; name: string }> } | undefined {
  if (!matrixData?.rows?.length) return undefined;

  const keyColumns = ['arr', 'valuation', 'burnRate', 'runway', 'grossMargin', 'ownership', 'sector', 'stage', 'documents'];
  const columns = (matrixData.columns || [])
    .filter((c) => keyColumns.includes(c.id) || /arr|valuation|burn|runway|sector|stage|documents/i.test(c.id))
    .slice(0, 20)
    .map((c) => ({ id: c.id, name: c.name || c.id }));

  const rows: Array<{ rowId: string; companyName: string; cells: Record<string, unknown> }> = [];
  let currentSize = 0;

  for (const row of matrixData.rows.slice(0, 50)) {
    const cells: Record<string, unknown> = {};
    for (const col of columns) {
      const cell = row.cells?.[col.id];
      let val = cell?.displayValue ?? cell?.value ?? (col.id === 'company' ? row.companyName : undefined);
      if (col.id === 'documents' && Array.isArray(val)) {
        // Compact document list for agent: [{ id, name }] so agent can read/link documents
        val = (val as Array<{ id?: string; name?: string; title?: string }>).slice(0, 10).map((d) => ({
          id: d.id ?? null,
          name: d.name ?? d.title ?? 'Document',
        }));
      }
      if (val !== undefined && val !== null) {
        cells[col.id] = typeof val === 'number' && val > 1e6 ? val : val;
      }
    }
    const entry = {
      rowId: row.id,
      companyName: row.companyName || row.cells?.['company']?.value || row.id,
      cells,
    };
    const entrySize = new Blob([JSON.stringify(entry)]).size;
    if (currentSize + entrySize > maxSizeBytes && rows.length > 0) break;
    rows.push(entry);
    currentSize += entrySize;
  }

  return { rows, columns };
}

/**
 * Download compressed context as text file
 */
export function downloadCompressedContext(
  context: CompressedPortfolioContext,
  filename: string = 'portfolio-context.txt'
): void {
  const blob = new Blob([context.text], { type: 'text/plain' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}
