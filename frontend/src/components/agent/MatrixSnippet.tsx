'use client';

import React from 'react';
import { formatCellValue } from '@/lib/matrix/cell-formatters';
import type { CellColumnType } from '@/lib/matrix/cell-formatters';
import type { MatrixRow, MatrixColumn } from '@/components/matrix/UnifiedMatrix';
import { cn } from '@/lib/utils';

export interface MatrixSnippetData {
  rowIds: string[];
  columnIds?: string[];
  title?: string;
}

interface MatrixSnippetProps {
  rows: MatrixRow[];
  columns: MatrixColumn[];
  highlightColumnId?: string;
  title?: string;
  maxRows?: number;
  className?: string;
}

/** Compact slice of the matrix inline in chat (like Cursor showing edited file region) */
export function MatrixSnippet({
  rows,
  columns,
  highlightColumnId,
  title,
  maxRows = 5,
  className,
}: MatrixSnippetProps) {
  const visibleRows = rows.slice(0, maxRows);
  const displayColumns = columns.filter((c) =>
    ['company', 'companyName', 'valuation', 'arr', 'sector', 'revenue', 'growth_rate'].includes(c.id) ||
    c.id.includes('valuation') ||
    c.id.includes('arr')
  );
  const cols = displayColumns.length > 0 ? displayColumns : columns.slice(0, 6);

  if (visibleRows.length === 0) return null;

  return (
    <div
      className={cn(
        'rounded-lg border border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-900/80 overflow-hidden font-mono text-xs',
        className
      )}
    >
      {title && (
        <div className="px-3 py-2 border-b border-gray-200 dark:border-gray-700 bg-gray-100 dark:bg-gray-800/80 text-gray-600 dark:text-gray-400 font-medium">
          {title}
        </div>
      )}
      <div className="overflow-x-auto">
        <table className="w-full min-w-[240px]">
          <thead>
            <tr className="border-b border-gray-200 dark:border-gray-700">
              {cols.map((col) => (
                <th
                  key={col.id}
                  className={cn(
                    'px-2 py-1.5 text-left font-medium text-gray-600 dark:text-gray-400 whitespace-nowrap',
                    highlightColumnId === col.id && 'bg-amber-100 dark:bg-amber-900/30'
                  )}
                >
                  {col.name || col.id}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {visibleRows.map((row) => (
              <tr
                key={row.id}
                className="border-b border-gray-100 dark:border-gray-800 last:border-b-0 hover:bg-gray-100/50 dark:hover:bg-gray-800/50"
              >
                {cols.map((col) => {
                  const cell = row.cells?.[col.id];
                  const rawValue =
                    cell?.displayValue ??
                    cell?.value ??
                    (col.id === 'company' ? row.companyName : row[col.id]);
                  const displayValue = formatCellValue(rawValue, (col.type || 'text') as CellColumnType);
                  return (
                    <td
                      key={col.id}
                      className={cn(
                        'px-2 py-1.5 text-gray-800 dark:text-gray-200 whitespace-nowrap',
                        highlightColumnId === col.id && 'bg-amber-50 dark:bg-amber-900/20'
                      )}
                    >
                      {displayValue || '-'}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {rows.length > maxRows && (
        <div className="px-3 py-1 text-[10px] text-gray-500 dark:text-gray-400 border-t border-gray-200 dark:border-gray-700">
          +{rows.length - maxRows} more rows
        </div>
      )}
    </div>
  );
}
