/**
 * Central export orchestration for matrix, analysis, and chat content.
 * Used by AgentChat (control centre) and UnifiedMatrix.
 */

import type { MatrixData } from '@/components/matrix/UnifiedMatrix';
import { formatCellValue } from '@/lib/matrix/cell-formatters';
import type { CellColumnType } from '@/lib/matrix/cell-formatters';
import * as XLSX from 'xlsx';

function escapeCSV(value: unknown): string {
  if (value === null || value === undefined) return '';
  const str = String(value);
  if (str.includes(',') || str.includes('"') || str.includes('\n')) {
    return `"${str.replace(/"/g, '""')}"`;
  }
  return str;
}


/** Export matrix to CSV (same logic as UnifiedMatrix exportToCSV) */
export function exportMatrixToCSV(matrixData: MatrixData): void {
  const lines: string[] = [];

  lines.push(`Export Date: ${new Date().toISOString()}`);
  lines.push(`Data Source: ${matrixData.metadata?.dataSource || 'unknown'}`);
  if (matrixData.metadata?.fundId) {
    lines.push(`Fund ID: ${matrixData.metadata.fundId}`);
  }
  if (matrixData.metadata?.query) {
    lines.push(`Query: ${matrixData.metadata.query}`);
  }
  lines.push(`Rows: ${matrixData.rows.length}, Columns: ${matrixData.columns.length}`);
  lines.push('');

  const headerRow = matrixData.columns.map((col) => escapeCSV(col.name));
  lines.push(headerRow.join(','));

  matrixData.rows.forEach((row) => {
    const dataRow = matrixData.columns.map((col) => {
      const cell = row.cells?.[col.id];
      const raw =
        cell?.displayValue ?? cell?.value ?? (col.id === 'company' ? row.companyName : row[col.id]);
      return escapeCSV(String(raw ?? ''));
    });
    lines.push(dataRow.join(','));
  });

  const csv = lines.join('\n');
  const blob = new Blob([csv], { type: 'text/csv' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `matrix-export-${Date.now()}.csv`;
  a.click();
  URL.revokeObjectURL(url);
}

/** Export matrix to XLS/XLSX using xlsx library */
export function exportMatrixToXLS(matrixData: MatrixData): void {
  const headers = matrixData.columns.map((col) => col.name || col.id);
  const rows: unknown[][] = [headers];

  matrixData.rows.forEach((row) => {
    const rowData = matrixData.columns.map((col) => {
      const cell = row.cells?.[col.id];
      const raw =
        cell?.displayValue ?? cell?.value ?? (col.id === 'company' ? row.companyName : row[col.id]);
      if (raw != null && typeof raw === 'object' && !Array.isArray(raw)) {
        return (raw as Record<string, unknown>).value ?? (raw as Record<string, unknown>).displayValue ?? raw;
      }
      return raw;
    });
    rows.push(rowData);
  });

  const ws = XLSX.utils.aoa_to_sheet(rows);
  const wb = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(wb, ws, 'Matrix');
  XLSX.writeFile(wb, `matrix-export-${Date.now()}.xlsx`);
}

/** Export chat/analysis content as PDF (print dialog for user to save as PDF) */
export async function exportToPDF(
  content: string,
  options?: { title?: string }
): Promise<void> {
  const win = window.open('', '_blank');
  if (win) {
    win.document.write(`
      <!DOCTYPE html>
      <html><head><title>${options?.title || 'Analysis'}</title></head>
      <body style="font-family: system-ui; padding: 2rem; max-width: 800px; margin: 0 auto;">
        <pre style="white-space: pre-wrap;">${content.replace(/</g, '&lt;').replace(/>/g, '&gt;')}</pre>
      </body></html>
    `);
    win.document.close();
    win.print();
    win.close();
  }
}

/** Export matrix to EU AIFMD Annex 5 XML via the API route */
export async function exportMatrixToAnnex5XML(
  matrixData: MatrixData,
  fundId?: string,
): Promise<void> {
  const response = await fetch('/api/matrix/export/annex5', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      matrixData,
      fundId: fundId || matrixData.metadata?.fundId,
    }),
  });

  if (!response.ok) {
    throw new Error(`Annex 5 export failed: ${response.statusText}`);
  }

  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `aifmd-annex5-${Date.now()}.xml`;
  a.click();
  URL.revokeObjectURL(url);
}

export type ExportFormat = 'csv' | 'xlsx' | 'pdf' | 'annex5';

export interface ExportPayload {
  format: ExportFormat;
  matrixData?: MatrixData;
  messageContent?: string;
}
