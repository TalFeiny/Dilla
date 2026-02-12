'use client';

import React, { useMemo, useCallback, useRef, useState, useEffect } from 'react';
import { AgGridReact } from 'ag-grid-react';
import { getTheme } from '@/lib/theme';
import { ModuleRegistry, AllCommunityModule, ColDef, GridApi, CellValueChangedEvent, CellEditingStartedEvent } from 'ag-grid-community';
// Import AG Grid styles - using legacy CSS themes
import 'ag-grid-community/styles/ag-grid.css';
import 'ag-grid-community/styles/ag-theme-alpine.css';
import { FileText, Copy, Plus } from 'lucide-react';
import { Button } from '@/components/ui/button';

ModuleRegistry.registerModules([AllCommunityModule]);
import { MatrixData, MatrixColumn, MatrixRow, MatrixCell } from './UnifiedMatrix';
import { formatCellValue as formatCellValueShared, formatCurrency, parseCurrencyInput } from '@/lib/matrix/cell-formatters';
import { CellDropdownRenderer } from './CellDropdownRenderer';
import { FormulaEngine } from '@/lib/spreadsheet-formulas';
import { cn } from '@/lib/utils';
import { DataBarRenderer } from './custom-renderers/DataBarRenderer';
import { EnhancedMasterDetailRenderer } from './custom-renderers/EnhancedMasterDetail';
import { TreemapRenderer } from './custom-renderers/TreemapRenderer';
import type { DocumentSuggestion } from './DocumentSuggestions';

export type SuggestionAcceptPayload = { rowId: string; columnId: string; suggestedValue: unknown };

export interface AGGridMatrixProps {
  matrixData: MatrixData;
  /** Backend-registered cell actions; when set, dropdown/picker show these instead of static workflows. */
  availableActions?: import('@/lib/matrix/cell-action-registry').CellAction[];
  onCellEdit?: (rowId: string, columnId: string, value: any) => Promise<void>;
  onSourceChange?: (rowId: string, columnId: string, source: 'manual' | 'document' | 'api' | 'formula') => void;
  onFormulaBuilder?: (rowId: string, columnId: string) => void;
  onLinkDocument?: (rowId: string, columnId: string) => void;
  onValuationMethodChange?: (rowId: string, columnId: string, method: string) => void;
  onRowEdit?: (rowId: string) => void;
  onRowDelete?: (rowId: string) => Promise<void>;
  onRowDuplicate?: (rowId: string) => void;
  onRunValuation?: (rowId: string) => Promise<void>;
  onRunPWERM?: (rowId: string) => Promise<void>;
  onUploadDocument?: (rowId: string) => void;
  /** Upload a file to a specific cell (e.g. drag-and-drop document onto cell). Completes upload → process → extract → apply. */
  onUploadDocumentToCell?: (rowId: string, columnId: string, file: File) => Promise<void>;
  onEditColumn?: (columnId: string, updates: Partial<MatrixColumn>) => void;
  onDeleteColumn?: (columnId: string) => void;
  onCellActionResult?: (rowId: string, columnId: string, response: import('@/lib/matrix/cell-action-registry').ActionExecutionResponse) => void | Promise<void>;
  /** Run cell action from parent (POST survives cell unmount). */
  onRunCellAction?: (request: import('@/lib/matrix/cell-action-registry').ActionExecutionRequest) => Promise<void>;
  /** Open valuation picker in parent. */
  onOpenValuationPicker?: (rowId: string, columnId: string, rowData: any, matrixData: any) => void;
  /** Request document upload from parent. */
  onRequestUploadDocument?: (rowId: string, columnId: string) => void;
  /** When true, skip refreshCells to avoid race during cell action execution. */
  actionInProgressRef?: React.MutableRefObject<boolean>;
  onWorkflowStart?: (rowId: string, columnId: string, formula: string) => void;
  /** Write formula and run workflow immediately (no second Apply). */
  onWorkflowRun?: (rowId: string, columnId: string, formula: string) => void | Promise<void>;
  onAddRow?: () => void | Promise<void>;
  onAddColumn?: () => void;
  onSelectionChange?: (selectedRowIds: string[]) => void;
  onStartEditingCell?: (callback: (rowId: string, columnId: string) => void) => void;
  /** Document suggestions for in-grid badge; accept/reject callbacks use same signature as ChartViewport. */
  documentSuggestions?: DocumentSuggestion[];
  onSuggestionAccept?: (suggestionId: string, payload?: SuggestionAcceptPayload) => void;
  onSuggestionReject?: (suggestionId: string) => void;
  /** When document extraction completes (from Documents cell), refresh suggestions and open viewport. */
  onSuggestChanges?: (documentId: string, extractedData?: unknown) => void;
  mode?: 'portfolio' | 'query' | 'custom' | 'lp';
  /** When true (chat-first), de-emphasize Run valuation/PWERM in dropdown and show chat hint. */
  useAgentPanel?: boolean;
}

/** Format cell value using shared formatters. */
function formatCellValue(value: any, type: MatrixColumn['type']): string {
  const displayType = type === 'formula' || type === 'sparkline' ? 'text' : type;
  return formatCellValueShared(value, displayType as 'text' | 'number' | 'currency' | 'percentage' | 'date' | 'boolean' | 'runway');
}

/** Format currency for AG-Grid cell display (e.g. valueFormatter). */
function formatCurrencyCompact(value: number): string {
  return formatCurrency(value) || '';
}

/**
 * Parse cell value based on column type (for save/inline edit).
 */
function parseCellValue(value: string, type: MatrixColumn['type']): any {
  if (!value) return null;

  switch (type) {
    case 'number':
      return parseFloat(value.replace(/[^0-9.-]/g, '')) || 0;
    case 'currency':
      return parseCurrencyInput(value);
    case 'percentage':
      return parseFloat(value.replace(/[^0-9.-]/g, '')) / 100 || 0;
    case 'boolean':
      return value.toLowerCase() === 'yes' || value === 'true' || value === '1';
    case 'date':
      return new Date(value);
    case 'formula':
    case 'sparkline':
      return value;
    default:
      return value;
  }
}

// Default column definitions by mode - single source of truth (no duplication)
const DEFAULT_PORTFOLIO_COLUMNS: MatrixColumn[] = [
  { id: 'company', name: 'Company', type: 'text' as const, width: 200, editable: true },
  { id: 'documents', name: 'Documents', type: 'text' as const, width: 140, editable: false },
  { id: 'sector', name: 'Sector', type: 'text' as const, width: 120, editable: true },
  { id: 'arr', name: 'ARR', type: 'currency' as const, width: 120, editable: true },
  { id: 'burnRate', name: 'Burn Rate', type: 'currency' as const, width: 120, editable: true },
  { id: 'runway', name: 'Runway (mo)', type: 'number' as const, width: 100, editable: true },
  { id: 'grossMargin', name: 'Gross Margin', type: 'percentage' as const, width: 120, editable: true },
  { id: 'cashInBank', name: 'Cash in Bank', type: 'currency' as const, width: 140, editable: true },
  { id: 'valuation', name: 'Current Valuation', type: 'currency' as const, width: 140, editable: true },
  { id: 'ownership', name: 'Ownership %', type: 'percentage' as const, width: 120, editable: true },
  { id: 'optionPool', name: 'Option Pool (bps)', type: 'number' as const, width: 120, editable: true },
  { id: 'latestUpdate', name: 'Latest Update', type: 'text' as const, width: 160, editable: true },
  { id: 'productUpdates', name: 'Product Updates', type: 'text' as const, width: 160, editable: true },
];

const DEFAULT_LP_COLUMNS: MatrixColumn[] = [
  { id: 'lpName', name: 'LP Name', type: 'text' as const, width: 180, editable: true },
  { id: 'lpType', name: 'Type', type: 'text' as const, width: 120, editable: true },
  { id: 'status', name: 'Status', type: 'text' as const, width: 100, editable: true },
  { id: 'commitment', name: 'Commitment', type: 'currency' as const, width: 140, editable: true },
  { id: 'called', name: 'Called', type: 'currency' as const, width: 130, editable: true },
  { id: 'distributed', name: 'Distributed', type: 'currency' as const, width: 140, editable: true },
  { id: 'unfunded', name: 'Unfunded', type: 'currency' as const, width: 130, editable: false },
  { id: 'dpi', name: 'DPI', type: 'number' as const, width: 80, editable: false },
  { id: 'coInvest', name: 'Co-Invest', type: 'boolean' as const, width: 90, editable: true },
  { id: 'vintageYear', name: 'Vintage', type: 'number' as const, width: 90, editable: true },
  { id: 'contactName', name: 'Contact', type: 'text' as const, width: 140, editable: true },
  { id: 'capacity', name: 'Capacity', type: 'currency' as const, width: 130, editable: true },
];

const DEFAULT_CUSTOM_COLUMNS: MatrixColumn[] = [
  { id: 'name', name: 'Name', type: 'text' as const, editable: true },
  { id: 'value', name: 'Value', type: 'text' as const, editable: true },
];

function getDefaultColumns(mode: string): MatrixColumn[] {
  if (mode === 'portfolio') return DEFAULT_PORTFOLIO_COLUMNS;
  if (mode === 'lp') return DEFAULT_LP_COLUMNS;
  return DEFAULT_CUSTOM_COLUMNS;
}

export function AGGridMatrix({
  matrixData,
  availableActions,
  onCellEdit,
  onSourceChange,
  onFormulaBuilder,
  onLinkDocument,
  onValuationMethodChange,
  onRowEdit,
  onRowDelete,
  onRowDuplicate,
  onRunValuation,
  onRunPWERM,
  onUploadDocument,
  onUploadDocumentToCell,
  onEditColumn,
  onDeleteColumn,
  onCellActionResult,
  onRunCellAction,
  onOpenValuationPicker,
  onRequestUploadDocument,
  actionInProgressRef,
  onWorkflowStart,
  onWorkflowRun,
  onAddRow,
  onAddColumn,
  onSelectionChange,
  onStartEditingCell,
  documentSuggestions,
  onSuggestionAccept,
  onSuggestionReject,
  onSuggestChanges,
  mode = 'portfolio',
  useAgentPanel,
}: AGGridMatrixProps) {
  const gridRef = useRef<AgGridReact>(null);
  const gridContainerRef = useRef<HTMLDivElement>(null);
  const [gridApi, setGridApi] = useState<GridApi | null>(null);
  const gridApiRef = useRef<GridApi | null>(null);
  const [dragOverCell, setDragOverCell] = useState<{ rowId: string; columnId: string } | null>(null);
  const [expandedRows, setExpandedRows] = useState<Set<string>>(new Set());
  // Use refs to track previous values and prevent unnecessary updates
  const prevRowDataRef = useRef<any[] | null>(null);
  const prevColumnDefsRef = useRef<ColDef[] | null>(null);
  const pendingRafRef = useRef<number | null>(null);
  // Track if grid is ready (not just if API exists)
  const isGridReadyRef = useRef(false);
  // Stable grid instance ID to prevent unnecessary remounts during Fast Refresh
  const gridInstanceIdRef = useRef<string>(`grid-${mode}-${Date.now()}`);
  // Refs for callbacks so columnDefs useMemo doesn't change on every parent re-render (prevents grid restart loop)
  const propsRef = useRef<AGGridMatrixProps>({
    matrixData,
    availableActions,
    onSourceChange,
    onFormulaBuilder,
    onLinkDocument,
    onValuationMethodChange,
    onRowEdit,
    onRowDelete,
    onRowDuplicate,
    onRunValuation,
    onRunPWERM,
    onUploadDocument,
    onUploadDocumentToCell,
    onEditColumn,
    onDeleteColumn,
    onCellActionResult,
    onRunCellAction,
    onOpenValuationPicker,
    onRequestUploadDocument,
    onWorkflowStart,
    onWorkflowRun,
    onAddRow,
    onAddColumn,
    onSelectionChange,
    onStartEditingCell,
    documentSuggestions,
    onSuggestionAccept,
    onSuggestionReject,
    onSuggestChanges,
    mode,
    useAgentPanel,
  });
  propsRef.current = {
    matrixData,
    availableActions,
    onSourceChange,
    onFormulaBuilder,
    onLinkDocument,
    onValuationMethodChange,
    onRowEdit,
    onRowDelete,
    onRowDuplicate,
    onRunValuation,
    onRunPWERM,
    onUploadDocument,
    onUploadDocumentToCell,
    onEditColumn,
    onDeleteColumn,
    onCellActionResult,
    onRunCellAction,
    onOpenValuationPicker,
    onRequestUploadDocument,
    onWorkflowStart,
    onWorkflowRun,
    onAddRow,
    onAddColumn,
    onSelectionChange,
    onStartEditingCell,
    documentSuggestions,
    onSuggestionAccept,
    onSuggestionReject,
    onSuggestChanges,
    mode,
    useAgentPanel,
  };

  // Track when matrixData prop changes - will refresh grid after rowData is computed

  // Ensure matrixData has required structure - NEVER return empty columns
  const safeMatrixData = useMemo(() => {
    if (!matrixData || !matrixData.columns || matrixData.columns.length === 0) {
      return {
        columns: getDefaultColumns(mode),
        rows: matrixData?.rows || [],
        metadata: matrixData?.metadata || { dataSource: 'manual', lastUpdated: new Date().toISOString() },
      };
    }
    return {
      ...matrixData,
      columns: matrixData.columns || [],
      rows: matrixData.rows || [],
    };
  }, [matrixData, mode]);
  
  // Cached formula engine - created once per matrixData change, not per cell
  const formulaEngine = useMemo(() => {
    const data = safeMatrixData;
    if (!data.rows?.length || !data.columns?.length) return null;
    const cells: Record<string, any> = {};
    data.rows.forEach((row, rowIdx) => {
      data.columns.forEach((col, colIdx) => {
        const cell = row.cells[col.id];
        if (cell) {
          const colLetter = String.fromCharCode(65 + colIdx);
          const ref = `${colLetter}${rowIdx + 1}`;
          cells[ref] = {
            value: cell.value,
            formula: cell.formula,
          };
        }
      });
    });
    return new FormulaEngine(cells);
  }, [safeMatrixData]);

  // Helper function to create formula engine from arbitrary data (for edits)
  const createFormulaEngine = useCallback((data: MatrixData) => {
    const cells: Record<string, any> = {};
    data.rows.forEach((row, rowIdx) => {
      data.columns.forEach((col, colIdx) => {
        const cell = row.cells[col.id];
        if (cell) {
          const colLetter = String.fromCharCode(65 + colIdx);
          const ref = `${colLetter}${rowIdx + 1}`;
          cells[ref] = {
            value: cell.value,
            formula: cell.formula,
          };
        }
      });
    });
    return new FormulaEngine(cells);
  }, []);

  // Columns to use for rowData — must match columnDefs so every grid column has rowData[col.id]
  const columnsForRowData = useMemo(() => {
    const cols = safeMatrixData.columns;
    if (!cols || !Array.isArray(cols) || cols.length === 0) {
      return getDefaultColumns(mode);
    }
    return cols;
  }, [safeMatrixData.columns, mode]);

  // Transform MatrixData to AG Grid rowData (use columnsForRowData so all grid columns get values)
  const rowData = useMemo(() => {
    if (!safeMatrixData.rows || !Array.isArray(safeMatrixData.rows) || safeMatrixData.rows.length === 0) {
      return [];
    }
    
    // Filter out phantom empty rows (no id, no companyId, no companyName - can cause empty row above data)
    const validRows = safeMatrixData.rows.filter((row) => {
      const id = row.id != null ? String(row.id).trim() : '';
      const companyId = row.companyId != null ? String(row.companyId).trim() : '';
      const companyName = row.companyName != null ? String(row.companyName).trim() : '';
      const hasId = id !== '';
      const hasCompanyId = companyId !== '';
      const hasCompanyName = companyName !== '';
      if (!hasId && !hasCompanyId && !hasCompanyName) return false;
      // Filter out placeholder rows (temp-, new, empty-ish IDs with no real company)
      const looksLikePlaceholder = /^(temp-|new$|placeholder$|row-0$)/i.test(id) || id === '0';
      if (looksLikePlaceholder && !hasCompanyName && !hasCompanyId) return false;
      return true;
    });
    
    const transformedRows = validRows.map((row) => {
      const rowData: any = {
        id: row.id,
        companyId: row.companyId,
        companyName: row.companyName,
        _originalRow: row,
      };

      columnsForRowData.forEach((col) => {
        const cell = row.cells[col.id] || { value: null };
        const isCompanyCol = col.id === 'company' || col.id === 'companyName';
        const rawValue = isCompanyCol ? (row.companyName ?? cell.value) : cell.value;

        let displayValue = cell.displayValue;
        if (cell.formula && cell.formula.startsWith('=') && formulaEngine) {
          try {
            const result = formulaEngine.evaluate(cell.formula);
            displayValue = formatCellValue(result, col.type);
          } catch {
            displayValue = '#ERROR';
          }
        } else {
          displayValue = displayValue || formatCellValue(rawValue, col.type);
        }

        rowData[col.id] = displayValue;
        rowData[`_${col.id}_cell`] = cell;
      });

      return rowData;
    });
    return transformedRows;
  }, [safeMatrixData, columnsForRowData, formulaEngine]);

  // Keep gridApiRef in sync so columnDefs can read it without depending on gridApi (prevents restart loop)
  useEffect(() => {
    gridApiRef.current = gridApi;
  }, [gridApi]);

  // ResizeObserver: when grid container first gets non-zero height (e.g. after scroll into view),
  // fire sizeColumnsToFit once so AG Grid paints cells correctly (fixes "text only shows on click").
  // Only fires once to avoid resetting user-resized columns on every layout shift.
  useEffect(() => {
    const el = gridContainerRef.current;
    if (!el) return;
    let hasFired = false;
    const ro = new ResizeObserver(() => {
      if (hasFired) return;
      const api = gridApiRef.current;
      if (!api || api.isDestroyed()) return;
      const rect = el.getBoundingClientRect();
      if (rect.height > 0) {
        hasFired = true;
        try {
          api.sizeColumnsToFit();
        } catch (_) {}
      }
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  // Cell styling - conditional formatting based on value ranges (use safeMatrixData for stable deps)
  const getCellStyle = useCallback((params: any) => {
    if (!params.colDef?.field) return {};
    
    const cell = params.data?.[`_${params.colDef.field}_cell`] as MatrixCell | undefined;
    const value = params.value;
    const col = safeMatrixData.columns.find(c => c.id === params.colDef.field);
    
    const style: React.CSSProperties = {};
    
    // Risk-based coloring for financial metrics
    if (col?.type === 'currency' || col?.type === 'number') {
      const numValue = typeof value === 'number' ? value : parseFloat(String(value).replace(/[^0-9.-]/g, ''));
      if (!isNaN(numValue)) {
        // ARR thresholds
        if (params.colDef.field === 'arr' || params.colDef.field?.toLowerCase().includes('arr')) {
          if (numValue > 10000000) {
            style.backgroundColor = '#C8E6C9'; // Light green
          } else if (numValue > 1000000) {
            style.backgroundColor = '#FFF9C4'; // Light yellow
          } else if (numValue < 100000) {
            style.backgroundColor = '#FFCDD2'; // Light red
          }
        }
        // Growth rate thresholds
        if (params.colDef.field === 'growthRate' || params.colDef.field?.toLowerCase().includes('growth')) {
          if (numValue > 0.5) {
            style.backgroundColor = '#C8E6C9';
          } else if (numValue > 0.2) {
            style.backgroundColor = '#FFF9C4';
          } else if (numValue < 0) {
            style.backgroundColor = '#FFCDD2';
          }
        }
        // Burn rate / runway risk
        if (params.colDef.field === 'burnRate' || params.colDef.field?.toLowerCase().includes('burn')) {
          if (numValue > 1000000) {
            style.backgroundColor = '#FFCDD2';
          }
        }
        if (params.colDef.field === 'runway' || params.colDef.field?.toLowerCase().includes('runway')) {
          if (numValue < 6) {
            style.backgroundColor = '#FFCDD2';
          } else if (numValue < 12) {
            style.backgroundColor = '#FFF9C4';
          }
        }
      }
    }
    
    // Stale data indicator
    if (cell?.lastUpdated) {
      const daysSinceUpdate = (Date.now() - new Date(cell.lastUpdated).getTime()) / (1000 * 60 * 60 * 24);
      if (daysSinceUpdate > 90) {
        style.opacity = 0.6;
        style.fontStyle = 'italic';
      }
    }
    
    // Low confidence indicator
    if (cell?.metadata?.confidence !== undefined && cell.metadata.confidence < 0.5) {
      style.borderLeft = '3px solid #FF9800';
    }
    
    return style;
  }, [safeMatrixData.columns]);

  // Add actions column if row actions are available
  const hasRowActions = onRowEdit || onRowDelete || onRowDuplicate || onRunValuation || onRunPWERM || onUploadDocument;

  // Create column definitions from MatrixColumn
  const columnDefs = useMemo<ColDef[]>(() => {
    // NEVER return empty array - grid won't render
    let columnsToUse = safeMatrixData.columns;
    if (!columnsToUse || !Array.isArray(columnsToUse) || columnsToUse.length === 0) {
      columnsToUse = getDefaultColumns(mode);
    }

    const p = propsRef.current;
    const cols: ColDef[] = [];
    // When selection is enabled (for workflow target "selected"), prepend checkbox column
    if (p.onSelectionChange) {
      cols.push({
        headerCheckboxSelection: true,
        checkboxSelection: true,
        width: 48,
        pinned: 'left',
        resizable: false,
        sortable: false,
        filter: false,
        editable: false,
        suppressMovable: true,
        field: 'id',
        headerName: '',
        hide: false,
      } as ColDef);
    }
    // Add data columns
    const dataCols = columnsToUse.map((col): ColDef => {
      const baseColDef: ColDef = {
        field: col.id,
        headerName: col.name,
        width: col.width || 150,
        resizable: true,
        sortable: true,
        filter: false, // Remove filter icon from headers
        editable: col.editable !== false, // Respect explicit false, otherwise default to true
        // Ensure cell value is always from cell object so text shows (fix: "only name has values")
        valueGetter: (params) => {
          if (!params?.data) return null;
          const cell = params.data[`_${col.id}_cell`] as MatrixCell | undefined;
          if (cell?.displayValue != null && cell.displayValue !== '') return cell.displayValue;
          if (cell?.value != null && cell.value !== '') return cell.value;
          const isCompanyCol = col.id === 'company' || col.id === 'companyName';
          if (isCompanyCol && params.data.companyName) return params.data.companyName;
          return params.data[col.id] ?? null;
        },
        cellRenderer: CellDropdownRenderer,
        cellRendererParams: (params: any) => ({
          rowId: params.data?.id,
          columnId: col.id,
          onSourceChange: (rowId: string, columnId: string, source: 'manual' | 'document' | 'api' | 'formula') => {
            propsRef.current.onSourceChange?.(rowId, columnId, source);
          },
          onEdit: (rowId: string, columnId: string) => {
            const api = gridApiRef.current;
            if (api && !api.isDestroyed() && isGridReadyRef.current && params.node) {
              try {
                api.startEditingCell({
                  rowIndex: params.node.rowIndex!,
                  colKey: columnId,
                });
              } catch (error) {
                console.error('[AGGridMatrix] Error starting cell edit:', error);
              }
            }
          },
          onFormulaBuilder: (rowId: string, columnId: string) => {
            propsRef.current.onFormulaBuilder?.(rowId, columnId);
          },
          onLinkDocument: (rowId: string, columnId: string) => {
            propsRef.current.onLinkDocument?.(rowId, columnId);
          },
          onValuationMethodChange: (rowId: string, columnId: string, method: string) => {
            propsRef.current.onValuationMethodChange?.(rowId, columnId, method);
          },
          onWorkflowStart: (rowId: string, columnId: string, formula: string) => {
            propsRef.current.onWorkflowStart?.(rowId, columnId, formula);
          },
          onWorkflowRun: (rowId: string, columnId: string, formula: string) => {
            propsRef.current.onWorkflowRun?.(rowId, columnId, formula);
          },
          onCellActionResult: (rowId: string, columnId: string, response: any) => {
            propsRef.current.onCellActionResult?.(rowId, columnId, response);
          },
          onRunCellAction: (request: any) => {
            return propsRef.current.onRunCellAction?.(request);
          },
          onOpenValuationPicker: (rowId: string, columnId: string, rowData: any, matrixData: any) => {
            propsRef.current.onOpenValuationPicker?.(rowId, columnId, rowData, matrixData);
          },
          onRequestUploadDocument: (rowId: string, columnId: string) => {
            propsRef.current.onRequestUploadDocument?.(rowId, columnId);
          },
          onRowDelete: (rowId: string) => {
            return propsRef.current.onRowDelete?.(rowId);
          },
          onDeleteColumn: (columnId: string) => {
            propsRef.current.onDeleteColumn?.(columnId);
          },
          matrixData: p.matrixData,
          availableActions: p.availableActions,
          fundId: p.matrixData?.metadata?.fundId,
          // Wire services based on column type/service – read from ref at call time so backend is hit
          onRunService: async (rowId: string, columnId: string, serviceName: string) => {
            const current = propsRef.current;
            const row = (current.matrixData?.rows ?? []).find((r: any) => r.id === rowId);
            if (!row?.companyId) return;
            try {
              if (serviceName === 'pwerm' || columnId === 'pwerm') {
                await current.onRunPWERM?.(rowId);
              } else if (serviceName === 'valuation' || columnId === 'valuation') {
                await current.onRunValuation?.(rowId);
              }
            } catch (error) {
              console.error(`Error running ${serviceName}:`, error);
            }
          },
          documentSuggestions: p.documentSuggestions ?? [],
          onSuggestionAccept: (suggestionId: string, payload?: { rowId: string; columnId: string; suggestedValue: unknown }) => {
            propsRef.current.onSuggestionAccept?.(suggestionId, payload);
          },
          onSuggestionReject: (suggestionId: string) => {
            propsRef.current.onSuggestionReject?.(suggestionId);
          },
          onUploadDocumentToCell: (rowId: string, columnId: string, file: File) => {
            propsRef.current.onUploadDocumentToCell?.(rowId, columnId, file);
          },
          useAgentPanel: p.useAgentPanel,
        }),
        valueFormatter: (params) => {
          if (params.value === null || params.value === undefined || params.value === '') return '';
          const cell = params.data?.[`_${col.id}_cell`] as MatrixCell | undefined;
          if (cell?.displayValue) return cell.displayValue;
          return formatCellValue(params.value, col.type);
        },
        valueParser: (params) => {
          return parseCellValue(params.newValue, col.type);
        },
        cellEditor: col.type === 'formula' ? 'agTextCellEditor' : undefined,
      };

      // Add cell styling
      baseColDef.cellStyle = getCellStyle as any;
      
      // Type-specific configurations
      switch (col.type) {
        case 'currency':
          baseColDef.type = 'numericColumn';
          baseColDef.valueFormatter = (params) => {
            if (params.value === null || params.value === undefined) return '';
            return formatCurrencyCompact(Number(params.value));
          };
          break;
        case 'percentage':
          baseColDef.type = 'numericColumn';
          baseColDef.valueFormatter = (params) => {
            if (params.value === null || params.value === undefined) return '';
            return `${(Number(params.value) * 100).toFixed(1)}%`;
          };
          break;
        case 'number':
          baseColDef.type = 'numericColumn';
          break;
        case 'date':
          baseColDef.type = 'dateColumn';
          break;
        case 'boolean':
          baseColDef.cellEditor = 'agCheckboxCellEditor';
          break;
        case 'formula':
          baseColDef.editable = true;
          baseColDef.cellEditor = 'agTextCellEditor';
          break;
      }
      
      // Special renderers for certain column types
      if (col.id === 'companyName' && mode === 'portfolio') {
        baseColDef.cellRenderer = EnhancedMasterDetailRenderer;
        baseColDef.cellRendererParams = {
          fetchDetails: async (rowId: string) => {
            return null;
          },
        };
      }
      
      // Data bar renderer for visualization columns
      if (col.type === 'sparkline' || col.id?.toLowerCase().includes('trend')) {
        baseColDef.cellRenderer = DataBarRenderer;
        baseColDef.cellRendererParams = {
          minValue: 0,
          maxValue: 10000000,
          showValue: true,
        };
      }

      return baseColDef;
    });
    const finalCols = cols.concat(dataCols);

    // CRITICAL: AG Grid requires at least one column to render
    if (finalCols.length === 0) {
      return getDefaultColumns(mode).map(col => ({
        field: col.id,
        headerName: col.name,
        width: col.width,
        editable: col.editable,
      }));
    }
    
    return finalCols;
  }, [safeMatrixData.columns, hasRowActions, mode, getCellStyle]);

  // Default column definition
  const defaultColDef = useMemo<ColDef>(() => ({
    resizable: true,
    sortable: true,
    filter: false, // Remove filter icon from headers
    editable: true, // Make all columns editable by default
    cellStyle: getCellStyle as any,
  }), [getCellStyle]);

  // Handle cell editing started - detect empty grid and add row before edit
  const handleCellEditingStarted = useCallback((event: CellEditingStartedEvent) => {
    // If grid is empty (no data) and user tries to edit, add a row first
    if (!event.data && onAddRow) {
      // Grid is empty, add row first
      onAddRow();
    }
  }, [onAddRow]);

  // Handle cell value changes
  // Handle selection changes
  const handleSelectionChanged = useCallback(() => {
    if (!gridApi || !onSelectionChange) return;
    const selectedNodes = gridApi.getSelectedRows();
    const selectedRowIds = selectedNodes.map((node: any) => node?.id).filter(Boolean);
    onSelectionChange(selectedRowIds);
  }, [gridApi, onSelectionChange]);

  const handleCellValueChanged = useCallback(async (event: CellValueChangedEvent) => {
    if (!event.data || !event.colDef?.field) return;

    const rowId = event.data.id;
    const columnId = event.colDef.field;
    const newValue = event.newValue;

    // Check if it's a formula
    const column = safeMatrixData.columns.find((c) => c.id === columnId);
    const isFormula = column?.type === 'formula' || (typeof newValue === 'string' && newValue.startsWith('='));

    if (isFormula && typeof newValue === 'string' && newValue.startsWith('=')) {
      // Evaluate formula
      try {
        // Create updated matrix data with new formula
        const updatedRows = safeMatrixData.rows.map(r => {
          if (r.id === rowId) {
            return {
              ...r,
              cells: {
                ...r.cells,
                [columnId]: {
                  ...r.cells[columnId],
                  formula: newValue,
                },
              },
            };
          }
          return r;
        });
        
        const updatedData: MatrixData = {
          ...matrixData,
          rows: updatedRows,
        };
        
        const engine = createFormulaEngine(updatedData);
        const result = engine.evaluate(newValue);
        event.node.setDataValue(columnId, formatCellValue(result, column?.type || 'text'));
      } catch (error) {
        console.error('Formula evaluation error:', error);
        event.node.setDataValue(columnId, '#ERROR');
      }
    }

    // Call onCellEdit callback
    if (onCellEdit) {
      await onCellEdit(rowId, columnId, newValue);
    }
  }, [safeMatrixData, onCellEdit, onAddRow]);

  // Grid ready callback
  const onGridReady = useCallback((params: any) => {
    if (!params?.api || params.api.isDestroyed()) return;
    setGridApi(params.api);
    isGridReadyRef.current = true;
    requestAnimationFrame(() => {
      if (!params.api || params.api.isDestroyed()) {
        isGridReadyRef.current = false;
        return;
      }
      try {
        if (columnDefs?.length) {
          params.api.setGridOption('columnDefs', columnDefs);
          prevColumnDefsRef.current = columnDefs;
        }
        if (rowData) {
          params.api.setGridOption('rowData', rowData);
          prevRowDataRef.current = rowData;
          params.api.refreshCells({ force: false });
        }
      } catch (error) {
        console.error('[AGGridMatrix] Error syncing initial data:', error);
      }
    });
  }, [rowData, columnDefs]);

  // Helper function to safely check if grid is ready (must be declared before use in effects below)
  const isGridReady = useCallback(() => {
    return gridApi != null && !gridApi.isDestroyed() && isGridReadyRef.current;
  }, [gridApi]);

  // Expose startEditingCell function to parent via callback
  useEffect(() => {
    if (onStartEditingCell && gridApi && isGridReady()) {
      onStartEditingCell((rowId: string, columnId: string) => {
        if (!gridApi || !isGridReady()) return;
        try {
          // Find the row node by rowId
          let targetNode = null;
          gridApi.forEachNode((node: any) => {
            if (node.data?.id === rowId) {
              targetNode = node;
            }
          });
          if (targetNode) {
            gridApi.startEditingCell({
              rowIndex: targetNode.rowIndex!,
              colKey: columnId,
            });
          }
        } catch (error) {
          console.error('[AGGridMatrix] Error starting cell edit:', error);
        }
      });
    }
  }, [gridApi, onStartEditingCell, isGridReady]);

  // Grid pre-destroy callback - clean up gridApi state
  const onGridPreDestroyed = useCallback(() => {
    isGridReadyRef.current = false;
    gridApiRef.current = null;
    setGridApi(null);
    if (pendingRafRef.current != null) {
      cancelAnimationFrame(pendingRafRef.current);
      pendingRafRef.current = null;
    }
  }, []);


  // Sync rowData and columnDefs changes to AG Grid via API (runs only when data/structure actually changes)
  useEffect(() => {
    if (!isGridReady()) return;

    const rowDataChanged = prevRowDataRef.current !== rowData;
    const columnDefsChanged = prevColumnDefsRef.current !== columnDefs;
    if (!rowDataChanged && !columnDefsChanged) return;

    // Skip when a cell action is running (valuation/PWERM)
    if (actionInProgressRef?.current) return;

    // Cancel any pending rAF — latest data always wins, never dropped
    if (pendingRafRef.current != null) {
      cancelAnimationFrame(pendingRafRef.current);
    }

    pendingRafRef.current = requestAnimationFrame(() => {
      pendingRafRef.current = null;
      if (!isGridReady()) return;
      if (actionInProgressRef?.current) return;

      try {
        if (columnDefsChanged && columnDefs?.length) {
          gridApi!.setGridOption('columnDefs', columnDefs);
          prevColumnDefsRef.current = columnDefs;
        }
        if (rowDataChanged) {
          gridApi!.setGridOption('rowData', rowData || []);
          prevRowDataRef.current = rowData;
        }
        gridApi!.refreshCells({ force: true });
      } catch (error) {
        console.error('[AGGridMatrix] Error syncing data:', error);
        isGridReadyRef.current = false;
      }
    });
  }, [gridApi, rowData, columnDefs, isGridReady, actionInProgressRef]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      isGridReadyRef.current = false;
      if (pendingRafRef.current != null) {
        cancelAnimationFrame(pendingRafRef.current);
      }
    };
  }, []);

  // CSV export (Excel export requires Enterprise, using CSV as fallback)
  const handleExcelExport = useCallback(() => {
    if (!isGridReady()) return;
    
    try {
      // Use CSV export (available in Community)
      gridApi!.exportDataAsCsv({
        fileName: `matrix-export-${new Date().toISOString().split('T')[0]}.csv`,
        processCellCallback: (params: any) => {
          // Preserve cell values
          return params.value ?? '';
        },
        processHeaderCallback: (params: any) => {
          return params.column.getColDef().headerName || '';
        },
      });
    } catch (error) {
      console.error('[AGGridMatrix] Error exporting CSV:', error);
    }
  }, [gridApi]);

  // Clipboard operations
  const handleCopy = useCallback(() => {
    if (!isGridReady()) return;
    try {
      gridApi!.copySelectedRowsToClipboard();
    } catch (error) {
      console.error('[AGGridMatrix] Error copying to clipboard:', error);
    }
  }, [gridApi]);

  // Get data path for tree data (hierarchical structure)
  const getDataPath = useCallback((data: any) => {
    // Build hierarchy: Fund > Sector > Stage > Company
    const path: string[] = [];
    
    if (data.fund) path.push(data.fund);
    if (data.sector) path.push(data.sector);
    if (data.stage) path.push(data.stage);
    if (data.companyName) path.push(data.companyName);
    
    return path.length > 0 ? path : [data.companyName || 'Uncategorized'];
  }, []);

  // Theme-aware: use built-in dark theme when app is in night mode so cell text is visible
  const [isDark, setIsDark] = useState(() => typeof document !== 'undefined' && getTheme() === 'night');
  useEffect(() => {
    const check = () => setIsDark(getTheme() === 'night');
    check();
    const observer = new MutationObserver(check);
    if (typeof document !== 'undefined') {
      observer.observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] });
    }
    return () => observer.disconnect();
  }, []);

  // Note: Status bar requires Enterprise modules, removed for Community edition

  return (
    <div className={cn(isDark ? "ag-theme-alpine-dark" : "ag-theme-alpine", "dilla-matrix-no-anim w-full")} style={{ height: '100%', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
      <style jsx global>{`
        /* Ensure headers and cells are visible in both themes */
        .ag-theme-alpine .ag-header-cell,
        .ag-theme-alpine-dark .ag-header-cell {
          font-weight: 600;
          padding: 8px 12px;
        }
        .ag-theme-alpine .ag-header-cell-text,
        .ag-theme-alpine-dark .ag-header-cell-text {
          display: block;
          white-space: nowrap;
          overflow: hidden;
          text-overflow: ellipsis;
        }
        /* Cell padding and explicit text color so values are always visible */
        .ag-theme-alpine .ag-cell,
        .ag-theme-alpine-dark .ag-cell {
          padding: 8px 12px;
        }
        .ag-theme-alpine .ag-cell {
          color: #181d1f !important;
        }
        .ag-theme-alpine-dark .ag-cell {
          color: #e2e8f0 !important;
        }
        /* Ensure empty state overlay doesn't block interactions */
        .ag-theme-alpine .ag-overlay-no-rows-wrapper,
        .ag-theme-alpine-dark .ag-overlay-no-rows-wrapper {
          pointer-events: none;
        }
        .ag-theme-alpine .ag-overlay-no-rows-center,
        .ag-theme-alpine-dark .ag-overlay-no-rows-center {
          pointer-events: none;
        }
        /* Disable all transitions and animations to prevent grid movement */
        .dilla-matrix-no-anim,
        .dilla-matrix-no-anim *,
        .ag-theme-alpine, .ag-theme-alpine *,
        .ag-theme-alpine-dark, .ag-theme-alpine-dark * {
          transition: none !important;
          animation: none !important;
        }
        /* Disable tooltip popup entirely */
        .ag-theme-alpine .ag-tooltip,
        .ag-theme-alpine [class*="tooltip"],
        .ag-theme-alpine-dark .ag-tooltip,
        .ag-theme-alpine-dark [class*="tooltip"] {
          display: none !important;
          visibility: hidden !important;
          pointer-events: none !important;
        }
      `}</style>
      <div
        style={{ height: '100%', display: 'flex', flexDirection: 'column' }}
        onDragOver={(e) => {
          e.preventDefault();
          e.stopPropagation();
          e.dataTransfer.dropEffect = 'copy';
        }}
        onDrop={async (e) => {
          e.preventDefault();
          e.stopPropagation();
          
          try {
            const data = e.dataTransfer.getData('application/json');
            if (!data) {
              // Try to get file from dataTransfer
              const files = Array.from(e.dataTransfer.files);
              const docFiles = files.filter((f: File) =>
                /\.(pdf|docx?|xlsx?|xls)$/i.test(f.name)
              );
              if (docFiles.length > 0) {
                if (onUploadDocumentToCell) {
                  const rowId = dragOverCell?.rowId ?? (() => {
                    const rowNode = gridApi?.getDisplayedRowAtIndex(0);
                    return rowNode?.data?.id ?? rowNode?.data?.companyId ?? safeMatrixData.rows?.[0]?.id ?? safeMatrixData.rows?.[0]?.companyId;
                  })();
                  const columnId = dragOverCell?.columnId ?? (() => {
                    const docCol = safeMatrixData.columns?.find(c => c.id === 'documents' || c.name?.toLowerCase().includes('document'));
                    return docCol?.id ?? safeMatrixData.columns?.[0]?.id;
                  })();
                  if (rowId && columnId) {
                    for (const file of docFiles) {
                      await onUploadDocumentToCell(rowId, columnId, file);
                    }
                  }
                } else if (onUploadDocument) {
                  // Legacy: no upload-to-cell handler, navigate to documents for first row
                  const rowNode = gridApi?.getDisplayedRowAtIndex(0);
                  const rowId = rowNode?.data?.id ?? rowNode?.data?.companyId;
                  if (rowId) onUploadDocument(rowId);
                }
              }
              if (docFiles.length > 0) return;
            }

            const dropData = JSON.parse(data);
            if (dropData.type === 'document') {
              const documentId = dropData.documentId;
              
              // Get drop target from AG Grid
              if (gridApi && dragOverCell) {
                const { rowId, columnId } = dragOverCell;
                
                // Link document to cell
                if (onLinkDocument) {
                  await onLinkDocument(rowId, columnId);
                }
                
                // Update cell source
                if (onSourceChange) {
                  onSourceChange(rowId, columnId, 'document');
                }
              }
            }
          } catch (error) {
            console.error('Error handling drop:', error);
          } finally {
            setDragOverCell(null);
          }
        }}
        onDragEnter={(e) => {
          e.preventDefault();
        }}
      >
        <div className="flex flex-col h-full">
          {/* Toolbar */}
          <div className="flex items-center gap-2 p-2 border-b bg-muted/50">
            {onAddRow && (
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={(e) => {
                  e.preventDefault();
                  e.stopPropagation();
                  e.nativeEvent.stopImmediatePropagation();
                  onAddRow?.();
                }}
                className="h-8"
              >
                <Plus className="h-4 w-4 mr-2" />
                {mode === 'portfolio' ? 'Add Company' : mode === 'lp' ? 'Add LP' : 'Add Row'}
              </Button>
            )}
            {onAddColumn && (
              <Button
                variant="outline"
                size="sm"
                onClick={() => onAddColumn?.()}
                className="h-8"
              >
                <Plus className="h-4 w-4 mr-2" />
                Add Column
              </Button>
            )}
            <Button
              variant="outline"
              size="sm"
              onClick={handleExcelExport}
              className="h-8"
            >
              <FileText className="h-4 w-4 mr-2" />
              Export CSV
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={handleCopy}
              className="h-8"
            >
              <Copy className="h-4 w-4 mr-2" />
              Copy
            </Button>
          </div>
          
          {/* Grid - AG Grid requires explicit height on its container. minHeight ensures cells paint even when parent chain is broken (fixes "text only shows on click"). */}
          <div ref={gridContainerRef} style={{ flex: '1 1 0', minHeight: 500, height: '100%', overflow: 'auto', overscrollBehaviorX: 'contain', touchAction: 'pan-y' }}>
            <AgGridReact
              key={gridInstanceIdRef.current}
              ref={gridRef}
              rowData={rowData}
              getRowId={(params) => params.data?.id ?? String(params.data?.companyId ?? (params as { node?: { id?: string } }).node?.id ?? '')}
              columnDefs={columnDefs}
              defaultColDef={defaultColDef}
              onGridReady={onGridReady}
              onFirstDataRendered={(params: { api?: GridApi }) => {
                if (params?.api && !params.api.isDestroyed()) {
                  params.api.sizeColumnsToFit();
                  // Force cell refresh so all values paint (fixes "only company name shows until click")
                  requestAnimationFrame(() => {
                    try {
                      params.api?.refreshCells({ force: true });
                    } catch (_) {}
                  });
                }
              }}
              onGridPreDestroyed={onGridPreDestroyed}
              onCellEditingStarted={handleCellEditingStarted}
              onCellValueChanged={handleCellValueChanged}
              onSelectionChanged={handleSelectionChanged}
              rowSelection={onSelectionChange ? 'multiple' : undefined}
              suppressRowClickSelection={onSelectionChange ? false : true}
              animateRows={false}
              suppressColumnMoveAnimation={true}
              suppressAnimationFrame={true}
              suppressCellFocus={false}
              tooltipShowDelay={999999}
              tooltipHideDelay={999999}
              suppressNoRowsOverlay={true}
              domLayout="normal"
              rowBuffer={30}
              debounceVerticalScrollbar={true}
              singleClickEdit={true}
              stopEditingWhenCellsLoseFocus={true}
              theme="legacy"
              // Clipboard (Community edition supports basic clipboard)
              clipboardDelimiter="\t"
              // Events
              onCellMouseOver={(params) => {
                if (params.data && params.colDef?.field) {
                  setDragOverCell({
                    rowId: params.data.id,
                    columnId: params.colDef.field,
                  });
                }
              }}
              onCellMouseOut={() => {
                // Don't clear immediately - only on actual drop
              }}
              onRowGroupOpened={(params) => {
                // Handle group expansion
              }}
            />
          </div>
        </div>
      </div>
    </div>
  );
}
