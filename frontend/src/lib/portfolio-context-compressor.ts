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
 * Mode-aware: portfolio → key financial columns, legal → clause-level columns,
 * pnl → all period columns (handled by session_state from fpa_pnl_result).
 */
export function buildGridSnapshot(
  matrixData: MatrixData,
  maxSizeBytes: number = 5000,
  gridMode: string = 'portfolio'
): { rows: Array<{ rowId: string; companyName: string; cells: Record<string, unknown>; documentId?: string; clauseId?: string }>; columns: Array<{ id: string; name: string }> } | undefined {
  if (!matrixData?.rows?.length) return undefined;

  const isLegal = gridMode === 'legal';

  // Legal mode: pass all legal clause columns; portfolio: key financial columns
  const legalColumns = [
    'documentName', 'contractType', 'party', 'counterparty', 'status',
    'effectiveDate', 'expiryDate', 'totalValue', 'annualValue',
    'keyTerms', 'flags', 'obligations', 'nextDeadline', 'reasoning',
  ];
  const portfolioColumns = ['arr', 'valuation', 'burnRate', 'runway', 'grossMargin', 'ownership', 'sector', 'stage', 'documents'];

  const keyColumns = isLegal ? legalColumns : portfolioColumns;
  const columnFilter = isLegal
    ? (c: { id: string }) => keyColumns.includes(c.id) || /document|contract|party|counter|status|effective|expiry|value|annual|terms|flags|obligation|deadline|reasoning/i.test(c.id)
    : (c: { id: string }) => keyColumns.includes(c.id) || /arr|valuation|burn|runway|sector|stage|documents/i.test(c.id);

  const columns = (matrixData.columns || [])
    .filter(columnFilter)
    .slice(0, 20)
    .map((c) => ({ id: c.id, name: c.name || c.id }));

  // If no columns matched (legal grid columns might not be in matrixData.columns),
  // fall back to passing ALL cell keys from the first row
  if (columns.length === 0 && matrixData.rows[0]?.cells) {
    const firstRowKeys = Object.keys(matrixData.rows[0].cells).slice(0, 20);
    for (const k of firstRowKeys) {
      columns.push({ id: k, name: k });
    }
  }

  const rows: Array<{ rowId: string; companyName: string; cells: Record<string, unknown>; documentId?: string; clauseId?: string }> = [];
  let currentSize = 0;

  for (const row of matrixData.rows.slice(0, 50)) {
    const cells: Record<string, unknown> = {};
    // In legal mode, extract document_id and clause_id from cell metadata
    let documentId: string | undefined;
    let clauseId: string | undefined;

    for (const col of columns) {
      const cell = row.cells?.[col.id];
      if (!cell) continue;
      let val = cell?.displayValue ?? cell?.value ?? (col.id === 'company' ? row.companyName : undefined);
      if (col.id === 'documents' && Array.isArray(val)) {
        val = (val as Array<{ id?: string; name?: string; title?: string }>).slice(0, 10).map((d) => ({
          id: d.id ?? null,
          name: d.name ?? d.title ?? 'Document',
        }));
      }
      if (val !== undefined && val !== null) {
        cells[col.id] = val;
      }
      // Extract document_id / clause metadata from any cell's metadata
      if (isLegal && !documentId && cell?.metadata) {
        const meta = cell.metadata as Record<string, unknown>;
        if (meta.document_id) documentId = String(meta.document_id);
      }
    }

    // Clause ID from the row id (format: "legal:{clause_id}")
    if (isLegal && row.id?.startsWith('legal:')) {
      clauseId = row.id.replace('legal:', '');
    }

    const entry: { rowId: string; companyName: string; cells: Record<string, unknown>; documentId?: string; clauseId?: string } = {
      rowId: row.id,
      companyName: row.companyName || row.cells?.['company']?.value || row.id,
      cells,
    };
    if (documentId) entry.documentId = documentId;
    if (clauseId) entry.clauseId = clauseId;

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
