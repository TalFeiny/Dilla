/**
 * Column creation helper functions
 * Extracted from UnifiedMatrix.tsx for maintainability
 */

import { MatrixColumn, MatrixRow, MatrixCell } from '@/components/matrix/UnifiedMatrix';

/** Canonical column ids that must appear first (company identifier column) */
const COMPANY_FIRST_IDS = ['company', 'companyName'];

/** Pattern for dummy placeholder columns (e.g. "company 163636773" or "New Company 1736...") */
const DUMMY_COLUMN_PATTERN = /^(?:company|companyName|New\s+Company)\s*\d+/i;

/** Pattern for temp col-IDs (e.g. "col-1255353") – matches migration 20250127_delete_dummy_matrix_columns */
const COLDUMmy_PATTERN = /^col-\d+$/i;

/** Normalize column id for flexible matching (e.g. burn_rate <-> burnRate, current_valuation_usd <-> valuation) */
export function normalizeColumnIdForMatch(id: string): string {
  if (!id || typeof id !== 'string') return '';
  return id
    .toLowerCase()
    .replace(/\s+/g, '')
    .replace(/_/g, '');
}

/** Return true if two column ids refer to the same logical column (flexible snake_case / camelCase) */
export function columnIdsMatch(a: string, b: string): boolean {
  if (!a || !b) return false;
  if (a === b) return true;
  return normalizeColumnIdForMatch(a) === normalizeColumnIdForMatch(b);
}

/**
 * Returns true if column_id or name matches dummy placeholder (temp-company remnants or col-123 style).
 * Use when filtering or deleting from matrix_columns in the DB. Aligns with migration ^col-[0-9]+$.
 */
export function isDummyMatrixColumn(columnId: string, name: string): boolean {
  const id = (columnId || '').trim();
  const n = (name || '').trim();
  return DUMMY_COLUMN_PATTERN.test(id) || DUMMY_COLUMN_PATTERN.test(n) || COLDUMmy_PATTERN.test(id) || COLDUMmy_PATTERN.test(n);
}

/**
 * Strip dummy placeholder columns and enforce company-first order.
 * Use after merging saved columns, after add-company, and when building final column list.
 */
export function canonicalizeMatrixColumns(columns: MatrixColumn[]): MatrixColumn[] {
  if (!columns?.length) return columns;
  const filtered = columns.filter((col) => {
    const id = (col.id || '').trim();
    const name = (col.name || '').trim();
    if (DUMMY_COLUMN_PATTERN.test(id) || DUMMY_COLUMN_PATTERN.test(name)) return false;
    return true;
  });
  const companyCol = filtered.find(
    (c) =>
      COMPANY_FIRST_IDS.includes(c.id) ||
      c.id?.toLowerCase() === 'company' ||
      c.id?.toLowerCase() === 'companyname'
  );
  const rest = filtered.filter((c) => c !== companyCol);
  if (companyCol) return [companyCol, ...rest];
  return rest.length ? rest : filtered;
}

export interface ColumnDefinition {
  id: string;
  name: string;
  type: string;
  values?: Record<string, any>; // rowId -> value mapping
}

export interface ValidationResult {
  valid: boolean;
  errors: string[];
}

/**
 * Validate a column definition
 */
export function validateColumnDefinition(col: ColumnDefinition): ValidationResult {
  const errors: string[] = [];
  
  if (!col.id || typeof col.id !== 'string') {
    errors.push('Column ID is required and must be a string');
  }
  
  if (!col.name || typeof col.name !== 'string') {
    errors.push('Column name is required and must be a string');
  }
  
  if (!col.type || typeof col.type !== 'string') {
    errors.push('Column type is required and must be a string');
  }
  
  // Validate type is one of the allowed types
  const allowedTypes: MatrixColumn['type'][] = ['text', 'number', 'currency', 'percentage', 'date', 'boolean', 'formula', 'sparkline'];
  if (col.type && !allowedTypes.includes(col.type as MatrixColumn['type'])) {
    errors.push(`Invalid column type: ${col.type}. Must be one of: ${allowedTypes.join(', ')}`);
  }
  
  return {
    valid: errors.length === 0,
    errors,
  };
}

/**
 * Create columns from metadata (columns_to_create array)
 */
export function createColumnsFromMetadata(
  columnsToCreate: ColumnDefinition[],
  existingColumns: MatrixColumn[],
  _triggerColumnId?: string
): MatrixColumn[] {
  const existingIds = new Set(existingColumns.map((c) => c.id));
  
  // Filter out duplicates and validate
  const validColumns = columnsToCreate
    .filter((col) => {
      const validation = validateColumnDefinition(col);
      if (!validation.valid) {
        console.warn('Invalid column definition:', col, validation.errors);
        return false;
      }
      return !existingIds.has(col.id);
    })
    .map((col) => ({
      id: col.id,
      name: col.name,
      type: (col.type as MatrixColumn['type']) || 'number',
      width: 150,
    }));
  
  // Append new columns at the end (triggerColumnId kept for API compat but not used for position)
  const combined = [...existingColumns, ...validColumns];
  return canonicalizeMatrixColumns(combined);
}

/**
 * Populate cells for newly created columns
 */
export function populateCellsForNewColumns(
  rows: MatrixRow[],
  columnsToCreate: ColumnDefinition[],
  triggerInfo: { rowId: string; columnId: string; actionId?: string }
): MatrixRow[] {
  return rows.map((r) => {
    const cells: Record<string, MatrixCell> = { ...r.cells };
    
    columnsToCreate.forEach((col) => {
      const v = col.values?.[r.id];
      if (v === undefined) return;
      
      // Format display value based on type
      const display = typeof v === 'number' 
        ? (v as number).toLocaleString(undefined, { maximumFractionDigits: 2 }) 
        : String(v);
      
      cells[col.id] = {
        value: v,
        displayValue: display,
        source: 'api',
        lastUpdated: new Date().toISOString(),
        metadata: {
          generated_by: triggerInfo.actionId,
          source_column: triggerInfo.columnId,
          source_row: triggerInfo.rowId,
        },
      };
    });
    
    return { ...r, cells };
  });
}
