'use client';

import React, { useState, useRef } from 'react';
import { toast } from 'sonner';
import { useCellActionContextOptional } from './CellActionContext';
import { MoreVertical, FileText, Link as LinkIcon, Calculator, Edit2, Database, Sparkles, TrendingUp, Zap, BarChart3, List, Info, ExternalLink, X, Trash2, Columns3, Loader2, CheckCircle2, AlertCircle } from 'lucide-react';
import { getAvailableWorkflows } from '@/lib/matrix/cell-workflows';
import { executeAction, type ActionExecutionResponse, type ActionExecutionRequest, type CellAction } from '@/lib/matrix/cell-action-registry';
import { getActionIdForWorkflow } from '@/lib/matrix/workflow-action-map';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { Badge } from '@/components/ui/badge';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Checkbox } from '@/components/ui/checkbox';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { cn } from '@/lib/utils';
import type { DocumentSuggestion } from './DocumentSuggestions';
import { DocumentSuggestionBadge } from './DocumentSuggestions';

const ICON_CLASS = 'h-3.5 w-3.5 flex-shrink-0';
const DROPDOWN_ITEM_CLASS = 'flex items-center gap-2';
const DROPDOWN_ITEM_TWO_LINE_CLASS = 'flex items-start gap-2 py-2';

/** Icon for a backend cell action — every action gets exactly one icon for consistent dropdown UI. */
function getActionIcon(action: CellAction): React.ReactNode {
  if (action.category === 'formula') return <Calculator className={ICON_CLASS} />;
  if (action.action_id?.includes('chart')) return <BarChart3 className={ICON_CLASS} />;
  if (action.action_id?.includes('valuation')) return <TrendingUp className={ICON_CLASS} />;
  if (action.action_id?.includes('portfolio') || action.action_id?.includes('nav') || action.action_id?.includes('fund')) return <Database className={ICON_CLASS} />;
  if (action.action_id?.includes('skill')) return <Sparkles className={ICON_CLASS} />;
  if (action.category === 'document') return <FileText className={ICON_CLASS} />;
  return <Zap className={ICON_CLASS} />;
}

/** Icon for a workflow (when backend actions not used) — every workflow gets exactly one icon. */
function getWorkflowIcon(category: string): React.ReactNode {
  if (category === 'financial') return <Calculator className={ICON_CLASS} />;
  if (category === 'chart') return <BarChart3 className={ICON_CLASS} />;
  if (category === 'valuation') return <TrendingUp className={ICON_CLASS} />;
  if (category === 'portfolio' || category === 'cap_table') return <Database className={ICON_CLASS} />;
  if (category === 'analysis') return <Sparkles className={ICON_CLASS} />;
  if (category === 'market') return <BarChart3 className={ICON_CLASS} />;
  return <Zap className={ICON_CLASS} />;
}

export interface CellDropdownRendererProps {
  value: any;
  data: any;
  colDef: any;
  api: any;
  node: any;
  onSourceChange?: (rowId: string, columnId: string, source: 'manual' | 'document' | 'api' | 'formula') => void;
  onEdit?: (rowId: string, columnId: string) => void;
  onFormulaBuilder?: (rowId: string, columnId: string) => void;
  onLinkDocument?: (rowId: string, columnId: string) => void;
  onValuationMethodChange?: (rowId: string, columnId: string, method: string) => void;
  onCellActionResult?: (rowId: string, columnId: string, response: ActionExecutionResponse) => void | Promise<void>;
  /** Run a cell action from the parent (POST runs in parent so it is not lost when cell unmounts). If not provided, falls back to calling executeAction in cell. */
  onRunCellAction?: (request: ActionExecutionRequest) => Promise<void>;
  onWorkflowStart?: (rowId: string, columnId: string, formula: string) => void;
  /** Write formula and run workflow immediately (no second Apply). */
  onWorkflowRun?: (rowId: string, columnId: string, formula: string) => void | Promise<void>;
  onRowDelete?: (rowId: string) => Promise<void>;
  onDeleteColumn?: (columnId: string) => void;
  matrixData?: MatrixDataLike;
  fundId?: string;
  /** Backend-registered actions; when set, Workflows section and picker show these. */
  availableActions?: CellAction[];
  /** Document suggestions for this matrix; in-grid badge shows accept/reject. */
  documentSuggestions?: DocumentSuggestion[];
  onSuggestionAccept?: (suggestionId: string, payload?: { rowId: string; columnId: string; suggestedValue: unknown }) => void;
  onSuggestionReject?: (suggestionId: string) => void;
  /** Upload a file to this cell (documents column). Runs full flow: POST /api/documents → extract → apply. */
  onUploadDocumentToCell?: (rowId: string, columnId: string, file: File) => Promise<void>;
  /** Open valuation method picker in parent (survives cell unmount). If set, cell does not render inline Dialog. */
  onOpenValuationPicker?: (rowId: string, columnId: string, rowData: any, matrixData: MatrixDataLike) => void;
  /** Request file upload from parent (survives cell unmount). If set, cell does not render file input. */
  onRequestUploadDocument?: (rowId: string, columnId: string) => void;
  /** When true (chat-first), show hint for Run valuation/PWERM: "Or ask in chat: run valuation for @Company". */
  useAgentPanel?: boolean;
}

/** Exported for use by parent-level valuation picker (UnifiedMatrix). */
export interface ValuationMethod {
  value: string;
  label: string;
  description: string;
  category: 'Early Stage' | 'Growth' | 'Late Stage' | 'General';
}

type MatrixDataLike = { rows: { id: string; companyId?: string; companyName?: string; company?: string; cells: Record<string, { value?: unknown }> }[]; columns: { id: string; name?: string }[]; metadata?: { fundId?: string } } | undefined;

/** Resolve a numeric cell value by column id/name match (e.g. /arr|revenue/i). */
function cellValue(row: { cells?: Record<string, { value?: unknown }> } | null, cols: { id: string; name?: string }[], pattern: RegExp): number {
  if (!row?.cells || !cols.length) return 0;
  const col = cols.find(c => pattern.test(c.id) || (c.name != null && pattern.test(String(c.name))));
  const v = col ? row.cells[col.id]?.value : undefined;
  const n = typeof v === 'number' ? v : parseFloat(String(v ?? 0));
  return Number.isFinite(n) ? n : 0;
}

/** Resolve a string cell value by column id/name match. */
function cellStr(row: { cells?: Record<string, { value?: unknown }> } | null, cols: { id: string; name?: string }[], pattern: RegExp): string {
  if (!row?.cells || !cols.length) return '';
  const col = cols.find(c => pattern.test(c.id) || (c.name != null && pattern.test(String(c.name))));
  const v = col ? row.cells[col.id]?.value : undefined;
  return typeof v === 'string' ? v : (v != null ? String(v) : '');
}

/** Exported for use by parent-level valuation picker (UnifiedMatrix). */
export function buildActionInputs(
  actionId: string,
  row: { id?: string; companyId?: string; cells?: Record<string, { value?: unknown }> } | null,
  columnId: string,
  matrixData?: MatrixDataLike
): Record<string, unknown> {
  const inputs: Record<string, unknown> = {};
  const fundId = matrixData?.metadata?.fundId;
  const companyId = row?.companyId;
  const rows = matrixData?.rows ?? [];
  const cols = matrixData?.columns ?? [];
  let r = rows.find(rr => rr.id === row?.id) ?? row;
  // If resolved row has no cells (e.g. AG Grid row only), build cells from AG Grid row's _${colId}_cell
  if (row && (!r?.cells || !Object.keys(r.cells).length) && cols.length) {
    const cells: Record<string, { value?: unknown }> = {};
    cols.forEach((c) => {
      const v = (row as Record<string, unknown>)[`_${c.id}_cell`];
      const cellVal = typeof v === 'object' && v !== null && 'value' in v ? (v as { value?: unknown }).value : v;
      if (cellVal !== undefined) cells[c.id] = { value: cellVal };
    });
    r = { ...r, id: row.id, companyId: row.companyId, cells };
  }

  if (companyId) inputs.company_id = companyId;
  if (fundId) inputs.fund_id = fundId;

  if (actionId.startsWith('financial.')) {
    const exitCol = cols.find(c => /exit|valuation/i.test(c.id));
    const invCol = cols.find(c => /invest|investment/i.test(c.id));
    if (r?.cells) {
      if (actionId === 'financial.moic' && exitCol && invCol) {
        inputs.exit_value = Number(r.cells[exitCol.id]?.value ?? 0);
        inputs.investment = Number(r.cells[invCol.id]?.value ?? 0);
      }
      if (actionId === 'financial.cagr') {
        const vals = cols.map(c => Number(r.cells[c.id]?.value ?? 0)).filter(n => !isNaN(n));
        if (vals.length >= 2) {
          inputs.beginning_value = vals[0];
          inputs.ending_value = vals[vals.length - 1];
          inputs.years = Math.max(1, vals.length - 1);
        }
      }
      if ((actionId === 'financial.irr' || actionId === 'financial.npv') && columnId) {
        const cashFlows = rows.map(rr => Number(rr.cells[columnId]?.value ?? 0)).filter(n => !isNaN(n));
        if (cashFlows.length) inputs.cash_flows = cashFlows;
      }
      if (actionId === 'financial.npv') {
        const dr = cellValue(r, cols, /discount|rate/i);
        inputs.discount_rate = (dr && Number.isFinite(dr)) ? dr : 0.1;
      }
    }
  }

  if (actionId.startsWith('valuation_engine.') || actionId.startsWith('valuation.')) {
    const nameVal = cellStr(r, cols, /company|companyName|^name$/i);
    if (nameVal) {
      inputs.name = nameVal;
      inputs.company_name = nameVal;
    }
    const arrRev = cellValue(r, cols, /arr|revenue|current_arr/i);
    if (arrRev) {
      inputs.revenue = arrRev;
      inputs.arr = arrRev;
      inputs.current_arr_usd = arrRev;
    }
    const sectorVal = cellStr(r, cols, /sector/i);
    if (sectorVal) inputs.sector = sectorVal;
    const growthVal = cellValue(r, cols, /growth|revenueGrowth/i);
    if (growthVal !== undefined && Number.isFinite(growthVal)) {
      inputs.growth_rate = growthVal;
      inputs.revenue_growth_annual_pct = growthVal > 2 ? growthVal : growthVal * 100;
    }
    const stageVal = cellStr(r, cols, /stage|round|time_since|since_round|funnel/i);
    if (stageVal) inputs.stage = stageVal;
    const valuationVal = cellValue(r, cols, /valuation|value|currentValuation/i);
    if (valuationVal !== undefined && Number.isFinite(valuationVal)) {
      inputs.last_round_valuation = valuationVal;
      inputs.current_valuation_usd = valuationVal;
    }
    const investedVal = cellValue(r, cols, /invest|raised|total_invested|investmentAmount/i);
    if (investedVal !== undefined && Number.isFinite(investedVal)) {
      inputs.total_raised = investedVal;
      inputs.total_invested_usd = investedVal;
    }
  }

  if (actionId.includes('revenue_projection') || actionId.includes('revenue.projection')) {
    const nameVal = cellStr(r, cols, /company|companyName|^name$/i);
    if (nameVal) inputs.name = nameVal;
    inputs.base_revenue = cellValue(r, cols, /arr|revenue|revenue_|current_arr/i) || 1_000_000;
    inputs.initial_growth = cellValue(r, cols, /growth|revenueGrowth/i) || 0.3;
    inputs.years = Math.max(1, cellValue(r, cols, /years|period/i) || 5);
    inputs.quality_score = 1.0;
  }

  if (actionId.includes('market.') || actionId.includes('find_comparables')) {
    const nameVal = cellStr(r, cols, /company|companyName|^name$/i);
    if (nameVal) {
      inputs.name = nameVal;
      inputs.company_name = nameVal;
    }
    const sectorVal = cellStr(r, cols, /sector/i);
    if (sectorVal) inputs.sector = sectorVal;
    const geoVal = cellStr(r, cols, /geo|location|region|country/i);
    if (geoVal) inputs.geography = geoVal;
    const arrVal = cellValue(r, cols, /arr|revenue|current_arr/i);
    if (arrVal) inputs.arr = arrVal;
    inputs.limit = 10;
  }

  if (actionId.includes('ownership') || actionId.includes('scoring') || actionId.includes('gap_filler') || actionId.includes('score_company') || actionId.includes('debt')) {
    const nameVal = cellStr(r, cols, /company|companyName|^name$/i);
    if (nameVal) {
      inputs.name = nameVal;
      inputs.company_name = nameVal;
    }
    const arrRev = cellValue(r, cols, /arr|revenue|current_arr/i);
    if (arrRev) {
      inputs.revenue = arrRev;
      inputs.arr = arrRev;
      inputs.current_arr_usd = arrRev;
    }
    const sectorVal = cellStr(r, cols, /sector/i);
    if (sectorVal) inputs.sector = sectorVal;
    const growthVal = cellValue(r, cols, /growth|revenueGrowth/i);
    if (growthVal !== undefined && Number.isFinite(growthVal)) {
      inputs.growth_rate = growthVal;
      inputs.revenue_growth_annual_pct = growthVal > 2 ? growthVal : growthVal * 100;
    }
    const valuationVal = cellValue(r, cols, /valuation|value|currentValuation/i);
    if (valuationVal !== undefined && Number.isFinite(valuationVal)) {
      inputs.current_valuation_usd = valuationVal;
    }
    const investedVal = cellValue(r, cols, /invest|raised|total_invested|investmentAmount/i);
    if (investedVal !== undefined && Number.isFinite(investedVal)) {
      inputs.investment_amount = investedVal;
      inputs.total_invested_usd = investedVal;
    }
    const exitVal = cellValue(r, cols, /exit|exitValue/i);
    if (exitVal !== undefined && Number.isFinite(exitVal)) inputs.exit_value = exitVal;
  }

  if (actionId === 'chart_intelligence.generate') {
    inputs.context = row ? { rowId: row.id, companyId: row.companyId } : {};
    inputs.chart_type = 'auto';
    const rowData: Record<string, unknown> = {};
    cols.forEach(c => { rowData[c.id] = r?.cells?.[c.id]?.value; });
    inputs.data = rowData;
  }

  // Document actions: require document_id from a column (document_id, document, doc_id, documentId)
  if (actionId.startsWith('document.') || actionId.includes('document.extract') || actionId.includes('document.analyze')) {
    const docIdStr = cellStr(r, cols, /document_id|document|doc_id|documentId/i);
    const docIdVal = cellValue(r, cols, /document_id|document|doc_id|documentId/i);
    const documentId = docIdStr || (docIdVal != null && String(docIdVal) !== '' ? String(docIdVal) : undefined);
    if (documentId) inputs.document_id = documentId;
    if (actionId === 'document.extract') {
      inputs.extraction_type = (r?.cells && cols.find(c => /extraction_type|extract_type/i.test(c.id)))
        ? cellStr(r, cols, /extraction_type|extract_type/i) || 'structured'
        : 'structured';
    }
  }

  return inputs;
}

/** Exported for use by parent-level valuation picker (UnifiedMatrix). */
export const VALUATION_METHODS: ValuationMethod[] = [
  {
    value: 'auto',
    label: 'AUTO',
    description: 'Auto-select based on company stage',
    category: 'General',
  },
  {
    value: 'pwerm',
    label: 'PWERM',
    description: 'Probability Weighted Expected Return Method',
    category: 'Early Stage',
  },
  {
    value: 'dcf',
    label: 'DCF',
    description: 'Discounted Cash Flow analysis',
    category: 'Late Stage',
  },
  {
    value: 'opm',
    label: 'OPM',
    description: 'Option Pricing Model',
    category: 'Late Stage',
  },
  {
    value: 'waterfall',
    label: 'WATERFALL',
    description: 'Liquidation waterfall analysis',
    category: 'Growth',
  },
  {
    value: 'recent_transaction',
    label: 'RECENT TRANSACTION',
    description: 'Recent transaction method',
    category: 'General',
  },
  {
    value: 'cost_method',
    label: 'COST METHOD',
    description: 'Cost-based valuation',
    category: 'General',
  },
  {
    value: 'milestone',
    label: 'MILESTONE',
    description: 'Milestone-based valuation',
    category: 'Early Stage',
  },
];

const isDocumentsColumn = (colDef: { field?: string; headerName?: string }) => {
  const id = (colDef?.field ?? '').toLowerCase();
  const name = (colDef?.headerName ?? '').toLowerCase();
  return id === 'documents' || name.includes('document');
};

export function CellDropdownRenderer(props: CellDropdownRendererProps) {
  const { value, data, colDef, api, node } = props;
  const ctx = useCellActionContextOptional();
  // Prefer context over props when inside CellActionProvider (UnifiedMatrix) — guarantees stable callback access
  const onRunCellAction = ctx?.onRunCellAction ?? props.onRunCellAction;
  const onOpenValuationPicker = ctx?.onOpenValuationPicker ?? props.onOpenValuationPicker;
  const onRequestUploadDocument = ctx?.onRequestUploadDocument ?? props.onRequestUploadDocument;
  const [isHovered, setIsHovered] = useState(false);
  const [isOpen, setIsOpen] = useState(false);
  const [showCitations, setShowCitations] = useState(false);
  const [valuationPicker, setValuationPicker] = useState<{ rowId: string; columnId: string } | null>(null);
  const [workflowPicker, setWorkflowPicker] = useState<{
    rowId: string;
    columnId: string;
    selectedIds: string[];
    target: 'current' | 'all';
  } | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  /** Actions to show in workflow picker: backend action_ids when availableActions set, else workflow ids */
  const pickerActions = props.availableActions?.length
    ? props.availableActions.map((a) => ({ id: a.action_id, name: a.name, description: a.description ?? '' }))
    : getAvailableWorkflows('row').map((w) => ({ id: w.id, name: w.name, description: w.description ?? '' }));
  const cellRef = useRef<HTMLDivElement>(null);
  const isDocuments = isDocumentsColumn(colDef);

  // Fix: Access cell data from the correct location (AGGridMatrix stores it as _${colId}_cell)
  const cell = data?.[`_${colDef.field}_cell`] || {};
  const source = cell.source || 'manual';
  const valuationMethod = cell.metadata?.valuationMethod || 'auto';
  
  // Check if this column is valuation-related
  const isValuationColumn = colDef.field?.toLowerCase().includes('valuation') || 
                            colDef.headerName?.toLowerCase().includes('valuation');
  
  // Check for complex data types
  const isArray = cell.metadata?.output_type === 'array' || Array.isArray(cell.value) || Array.isArray(cell.metadata?.raw_output);
  const hasChart = cell.metadata?.chart_config;
  const hasCitations = cell.metadata?.citations?.length > 0;
  const hasExplanation = cell.metadata?.explanation || cell.metadata?.method;
  const citations = cell.metadata?.citations || [];
  const arrayData = cell.metadata?.raw_output || cell.value;
  const arrayLength = Array.isArray(arrayData) ? arrayData.length : 0;
  
  // Format value for display
  const formatValue = (val: any): string => {
    if (val === null || val === undefined) return '';
    if (isArray && Array.isArray(val)) {
      return `${val.length} items`;
    }
    if (typeof val === 'number') {
      return val.toLocaleString();
    }
    return String(val);
  };
  
  // Group valuation methods by category
  const groupedMethods = VALUATION_METHODS.reduce((acc, method) => {
    if (!acc[method.category]) {
      acc[method.category] = [];
    }
    acc[method.category].push(method);
    return acc;
  }, {} as Record<string, ValuationMethod[]>);

  const sourceIcons = {
    manual: Edit2,
    document: FileText,
    api: Database,
    formula: Calculator,
  };

  const SourceIcon = sourceIcons[source] || Edit2;

  const rowId = String(data?.id ?? '');
  const columnId = String(colDef?.field ?? '');
  const cellStatus = ctx?.cellActionStatus?.[`${rowId}_${columnId}`];

  return (
    <div
      ref={cellRef}
      className="relative w-full min-h-full flex flex-col group"
      style={{ overflow: 'hidden' }}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
    >
      {/* Cell Value with Badges - always visible; use inherit so AG Grid theme colors apply (fixes invisible cells) */}
      <div className="flex-1 px-2 py-1 truncate flex items-center gap-1 min-h-[24px] opacity-100" style={{ color: 'inherit' }}>
        {isDocuments ? (() => {
          // Normalize documents: prefer metadata.documents, or derive from value/raw_output (upload result)
          const docs = cell.metadata?.documents;
          let displayDocs: { id: string | number; name: string }[] = [];
          if (Array.isArray(docs) && docs.length > 0) {
            displayDocs = docs.map((d: { id: string | number; name?: string }) => ({
              id: d.id,
              name: d.name ?? String(d.id),
            }));
          } else {
            const raw = cell.metadata?.raw_output ?? cell.value;
            if (Array.isArray(raw) && raw.some((r: any) => r && typeof r === 'object' && 'id' in r)) {
              displayDocs = raw.map((r: { id: string | number; name?: string; filename?: string }) => ({
                id: r.id,
                name: r.name ?? r.filename ?? String(r.id),
              }));
            } else if (raw && typeof raw === 'object' && 'id' in raw) {
              displayDocs = [{
                id: raw.id,
                name: raw.name ?? raw.filename ?? String(raw.id),
              }];
            }
          }
          return displayDocs.length > 0 ? (
            <span className="truncate flex items-center gap-1.5 min-w-0">
              {displayDocs.map((doc) => (
                <a
                  key={String(doc.id)}
                  href={`/documents/${doc.id}/analysis`}
                  target="_blank"
                  rel="noopener noreferrer"
                  onClick={(e) => e.stopPropagation()}
                  className="text-primary hover:underline truncate max-w-[140px]"
                >
                  {doc.name.length > 20 ? `${doc.name.slice(0, 20)}…` : doc.name}
                </a>
              ))}
            </span>
          ) : null;
        })() : (
          <span className="truncate min-w-0 flex-1" style={{ color: 'inherit' }} title={formatValue(value ?? cell.displayValue ?? cell.value) || undefined}>{formatValue(value ?? cell.displayValue ?? cell.value)}</span>
        )}

        {/* In-cell document suggestion badge */}
        {props.documentSuggestions?.length && (
          <DocumentSuggestionBadge
            rowId={rowId}
            columnId={columnId}
            cell={cell}
            suggestions={props.documentSuggestions}
            onAccept={(suggestionId, payload) => props.onSuggestionAccept?.(suggestionId, payload)}
            onReject={(suggestionId) => props.onSuggestionReject?.(suggestionId)}
          />
        )}

        {/* In-cell status (replaces toast) */}
        {cellStatus && (
          <span
            className={cn(
              'flex items-center gap-1 text-xs flex-shrink-0 ml-auto',
              cellStatus.state === 'loading' && 'text-amber-600',
              cellStatus.state === 'success' && 'text-green-600',
              cellStatus.state === 'error' && 'text-red-600'
            )}
          >
            {cellStatus.state === 'loading' && <Loader2 className="h-3 w-3 animate-spin" />}
            {cellStatus.state === 'success' && <CheckCircle2 className="h-3 w-3" />}
            {cellStatus.state === 'error' && <AlertCircle className="h-3 w-3" />}
            <span className="truncate max-w-[120px]">{cellStatus.message}</span>
          </span>
        )}

        {/* Array Badge */}
        {isArray && arrayLength > 0 && (
          <Dialog>
            <DialogTrigger asChild>
              <Badge
                variant="outline"
                className="h-5 px-1.5 text-xs cursor-pointer hover:bg-accent flex-shrink-0"
                onClick={(e) => e.stopPropagation()}
              >
                <List className="h-3 w-3 mr-1" />
                {arrayLength}
              </Badge>
            </DialogTrigger>
            <DialogContent className="sm:max-w-[600px] max-h-[80vh] overflow-y-auto">
              <DialogHeader>
                <DialogTitle>Array Data ({arrayLength} items)</DialogTitle>
                <DialogDescription>
                  Full list of items from the action result
                </DialogDescription>
              </DialogHeader>
              <div className="space-y-2 mt-4">
                {Array.isArray(arrayData) && arrayData.map((item, idx) => (
                  <div
                    key={idx}
                    className="p-2 border rounded-md text-sm"
                  >
                    {typeof item === 'object' && item !== null ? (
                      <pre className="text-xs overflow-x-auto">
                        {JSON.stringify(item, null, 2)}
                      </pre>
                    ) : (
                      <span>{String(item)}</span>
                    )}
                  </div>
                ))}
              </div>
            </DialogContent>
          </Dialog>
        )}
        
        {/* Chart Badge */}
        {hasChart && (
          <TooltipProvider>
            <Tooltip>
              <TooltipTrigger asChild>
                <Badge
                  variant="outline"
                  className="h-5 px-1.5 text-xs cursor-pointer hover:bg-accent flex-shrink-0"
                  onClick={(e) => {
                    e.stopPropagation();
                    // Navigate to insights panel or open chart preview
                    // This would be handled by the parent component
                  }}
                >
                  <BarChart3 className="h-3 w-3" />
                </Badge>
              </TooltipTrigger>
              <TooltipContent>
                <p>View chart in insights panel</p>
              </TooltipContent>
            </Tooltip>
          </TooltipProvider>
        )}
        
        {/* Citation Badge */}
        {hasCitations && (
          <Badge
            variant="outline"
            className="h-5 px-1.5 text-xs cursor-pointer hover:bg-accent flex-shrink-0"
            onClick={(e) => {
              e.stopPropagation();
              setShowCitations(!showCitations);
            }}
          >
            {citations.length}
          </Badge>
        )}

        {/* Explanation Tooltip */}
        {hasExplanation && (
          <TooltipProvider>
            <Tooltip>
              <TooltipTrigger asChild>
                <Info className="h-3 w-3 text-muted-foreground hover:text-primary cursor-help flex-shrink-0" />
              </TooltipTrigger>
              <TooltipContent className="max-w-xs">
                <div className="space-y-1">
                  {cell.metadata?.method && (
                    <div className="font-semibold">{cell.metadata.method}</div>
                  )}
                  {cell.metadata?.explanation && (
                    <div className="text-xs">{cell.metadata.explanation}</div>
                  )}
                </div>
              </TooltipContent>
            </Tooltip>
          </TooltipProvider>
        )}
      </div>
      
      {/* Inline Citations - expands within cell */}
      {showCitations && hasCitations && (
        <div 
          className="px-2 pb-1"
          onClick={(e) => e.stopPropagation()}
        >
          <div className="p-2 rounded-md border border-slate-200 bg-slate-50 text-xs">
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <h4 className="font-medium text-sm">Citations</h4>
                <button
                  onClick={() => setShowCitations(false)}
                  className="text-muted-foreground hover:text-foreground"
                >
                  <X className="h-3 w-3" />
                </button>
              </div>
              {cell.metadata?.explanation && (
                <div className="text-xs text-muted-foreground pb-2 border-b">
                  {cell.metadata.explanation}
                </div>
              )}
              <div className="space-y-1 max-h-32 overflow-y-auto">
                {citations.map((citation, idx) => (
                  <div key={citation.id || idx} className="text-xs">
                    <div className="flex items-center justify-between">
                      <span className="text-muted-foreground">
                        {citation.source || citation.title || 'Source'}
                      </span>
                      {citation.url && (
                        <a
                          href={citation.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-primary hover:underline ml-2"
                        >
                          <ExternalLink className="h-3 w-3" />
                        </a>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Thin Dropdown Button - Only visible on hover or when cell is selected */}
      {(isHovered || isOpen || node.isSelected()) && (
        <div className="absolute top-0 right-0 z-10">
          <DropdownMenu open={isOpen} onOpenChange={setIsOpen}>
            <DropdownMenuTrigger asChild>
              <button
                className={cn(
                  "h-5 w-5 flex items-center justify-center rounded-sm",
                  "hover:bg-accent hover:text-accent-foreground",
                  "text-muted-foreground hover:text-foreground"
                )}
                onClick={(e) => {
                  e.stopPropagation();
                }}
              >
                <MoreVertical className="h-3 w-3" />
              </button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-72 p-0">
              <div className="max-h-[min(60vh,500px)] overflow-y-auto overflow-x-hidden overscroll-contain p-1">
              {/* Data Source Selection */}
              <div className="px-2 py-1.5 text-xs font-semibold text-muted-foreground">
                Data Source
              </div>
              <DropdownMenuItem
                onClick={() => {
                  props.onSourceChange?.(data.id, colDef.field, 'manual');
                  setIsOpen(false);
                }}
                className={cn(DROPDOWN_ITEM_CLASS, source === 'manual' && "bg-accent")}
              >
                <Edit2 className={ICON_CLASS} />
                <span>Manual Entry</span>
              </DropdownMenuItem>
              <DropdownMenuItem
                onClick={() => {
                  props.onSourceChange?.(data.id, colDef.field, 'document');
                  setIsOpen(false);
                }}
                className={cn(DROPDOWN_ITEM_CLASS, source === 'document' && "bg-accent")}
              >
                <FileText className={ICON_CLASS} />
                <span>From Document</span>
              </DropdownMenuItem>
              <DropdownMenuItem
                onClick={() => {
                  props.onSourceChange?.(data.id, colDef.field, 'api');
                  setIsOpen(false);
                }}
                className={cn(DROPDOWN_ITEM_CLASS, source === 'api' && "bg-accent")}
              >
                <Database className={ICON_CLASS} />
                <span>From API</span>
              </DropdownMenuItem>
              <DropdownMenuItem
                onClick={() => {
                  props.onSourceChange?.(data.id, colDef.field, 'formula');
                  props.onFormulaBuilder?.(data.id, colDef.field);
                  setIsOpen(false);
                }}
                className={cn(DROPDOWN_ITEM_CLASS, source === 'formula' && "bg-accent")}
              >
                <Calculator className={ICON_CLASS} />
                <span>Formula</span>
              </DropdownMenuItem>

              <DropdownMenuSeparator />

              {/* Valuation Method Selection - Only show for valuation columns */}
              {isValuationColumn && (
                <>
                  <div className="px-2 py-1.5 text-xs font-semibold text-muted-foreground">
                    Valuation Method
                  </div>
                  {Object.entries(groupedMethods).map(([category, methods]) => (
                    <div key={category}>
                      <div className="px-2 py-1 text-xs font-medium text-muted-foreground/80 uppercase tracking-wider">
                        {category}
                      </div>
                      {methods.map((method) => (
                        <DropdownMenuItem
                          key={method.value}
                          onClick={() => {
                            props.onValuationMethodChange?.(data.id, colDef.field, method.value);
                            setIsOpen(false);
                          }}
                          className={cn(DROPDOWN_ITEM_TWO_LINE_CLASS, valuationMethod === method.value && "bg-accent")}
                        >
                          <TrendingUp className={ICON_CLASS} />
                          <div className="flex flex-col">
                            <span className="font-medium text-sm">{method.label}</span>
                            <span className="text-xs text-muted-foreground">
                              {method.description}
                            </span>
                          </div>
                        </DropdownMenuItem>
                      ))}
                    </div>
                  ))}
                  <DropdownMenuSeparator />
                </>
              )}

              {/* Actions */}
              <div className="px-2 py-1.5 text-xs font-semibold text-muted-foreground">
                Actions
              </div>
              <DropdownMenuItem
                className={DROPDOWN_ITEM_CLASS}
                onClick={() => {
                  props.onEdit?.(data.id, colDef.field);
                  setIsOpen(false);
                }}
              >
                <Edit2 className={ICON_CLASS} />
                <span>Edit Cell</span>
              </DropdownMenuItem>
              <DropdownMenuItem
                className={DROPDOWN_ITEM_CLASS}
                onClick={() => {
                  props.onLinkDocument?.(data.id, colDef.field);
                  setIsOpen(false);
                }}
              >
                <LinkIcon className={ICON_CLASS} />
                <span>Link Document</span>
              </DropdownMenuItem>
              {isDocuments && (props.onUploadDocumentToCell || onRequestUploadDocument) && (
                <>
                  {!onRequestUploadDocument && (
                    <input
                      ref={fileInputRef}
                      type="file"
                      className="hidden"
                      accept=".pdf,.docx,.doc,.xlsx,.xls"
                      onChange={async (e) => {
                        const selectedFiles = e.target.files;
                        if (!selectedFiles?.length || !data?.id || !colDef?.field) {
                          e.target.value = '';
                          return;
                        }
                        setIsOpen(false);
                        for (let i = 0; i < selectedFiles.length; i++) {
                          await props.onUploadDocumentToCell?.(data.id, colDef.field, selectedFiles[i]);
                        }
                        e.target.value = '';
                      }}
                    />
                  )}
                  <DropdownMenuItem
                    className={DROPDOWN_ITEM_CLASS}
                    onClick={() => {
                      if (onRequestUploadDocument) {
                        onRequestUploadDocument(String(data?.id ?? ''), String(colDef?.field ?? ''));
                        setIsOpen(false);
                        return;
                      }
                      fileInputRef.current?.click();
                    }}
                  >
                    <FileText className={ICON_CLASS} />
                    <span>Upload document</span>
                  </DropdownMenuItem>
                </>
              )}
              {source === 'formula' && (
                <DropdownMenuItem
                  className={DROPDOWN_ITEM_CLASS}
                  onClick={() => {
                    props.onFormulaBuilder?.(data.id, colDef.field);
                    setIsOpen(false);
                  }}
                >
                  <Sparkles className={ICON_CLASS} />
                  <span>Edit Formula</span>
                </DropdownMenuItem>
              )}

              {/* Workflows Section */}
              <DropdownMenuSeparator />
              <div className="px-2 py-1.5 text-xs font-semibold text-muted-foreground">
                Workflows
              </div>
              <DropdownMenuItem
                className={DROPDOWN_ITEM_TWO_LINE_CLASS}
                onClick={() => {
                  setWorkflowPicker({
                    rowId: String(data?.id ?? ''),
                    columnId: String(colDef?.field ?? ''),
                    selectedIds: [],
                    target: 'all',
                  });
                  setIsOpen(false);
                }}
              >
                <Zap className={ICON_CLASS} />
                <div className="flex flex-col">
                  <span className="font-medium text-sm">Run workflow...</span>
                  <span className="text-xs text-muted-foreground">
                    Compose and run multiple actions
                  </span>
                </div>
              </DropdownMenuItem>
              {props.availableActions?.length
                ? props.availableActions.map((action) => {
                    const isValuationOrPwerm = /valuation|pwerm/i.test(action.action_id ?? '');
                    const companyName = (data?.companyName ?? data?.company ?? props.matrixData?.rows?.find((r: any) => r.id === data?.id)?.companyName) || 'Company';
                    const desc = props.useAgentPanel && isValuationOrPwerm
                      ? `Or ask in chat: run ${(action.action_id ?? '').includes('pwerm') ? 'pwerm' : 'valuation'} for @${companyName}`
                      : (action.description ?? action.action_id);
                    return (
                    <DropdownMenuItem
                      key={action.action_id}
                      className={cn(DROPDOWN_ITEM_TWO_LINE_CLASS, props.useAgentPanel && isValuationOrPwerm && 'opacity-90')}
                      onClick={async () => {
                        const fundId = props.fundId ?? props.matrixData?.metadata?.fundId;
                        const inputs = buildActionInputs(action.action_id, data, colDef.field, props.matrixData);
                        const request = {
                          action_id: action.action_id,
                          row_id: String(data?.id ?? ''),
                          column_id: String(colDef?.field ?? ''),
                          inputs,
                          mode: 'portfolio' as const,
                          fund_id: fundId ?? undefined,
                          company_id: data?.companyId ?? undefined,
                        };
                        setIsOpen(false);
                        if (onRunCellAction) {
                          try {
                            await onRunCellAction(request);
                          } catch {
                            /* Status shown in-cell via cellActionStatus */
                          }
                          return;
                        }
                        try {
                          const res = await executeAction(request);
                          if (res.success && props.onCellActionResult) {
                            await props.onCellActionResult(String(data?.id), String(colDef?.field), res);
                          } else if (!res.success) {
                            toast.error(res.error ?? 'Action failed');
                          }
                        } catch (e) {
                          toast.error(e instanceof Error ? e.message : 'Action failed');
                        }
                      }}
                    >
                      {getActionIcon(action)}
                      <div className="flex flex-col">
                        <span className="font-medium text-sm">{action.name}</span>
                        <span className={cn("text-xs text-muted-foreground", props.useAgentPanel && isValuationOrPwerm && "italic")}>{desc}</span>
                      </div>
                    </DropdownMenuItem>
                  ); })
                : getAvailableWorkflows('row').map((workflow) => {
                    const actionId = getActionIdForWorkflow(workflow.id);
                    const isRunValuation = workflow.id === 'runValuation';
                    const isRunPWERM = workflow.id === 'runPWERM';
                    const companyName = (data?.companyName ?? data?.company ?? props.matrixData?.rows?.find((r: any) => r.id === data?.id)?.companyName) || 'Company';
                    const chatHint = props.useAgentPanel && (isRunValuation || isRunPWERM)
                      ? `Or ask in chat: run ${isRunValuation ? 'valuation' : 'pwerm'} for @${companyName}`
                      : workflow.description;
                    return (
                      <DropdownMenuItem
                        key={workflow.id}
                        className={cn(DROPDOWN_ITEM_TWO_LINE_CLASS, props.useAgentPanel && (isRunValuation || isRunPWERM) && 'opacity-90')}
                        disabled={!actionId && !isRunValuation}
                        onClick={async () => {
                          if (isRunValuation) {
                            if (onOpenValuationPicker) {
                              onOpenValuationPicker(String(data?.id ?? ''), String(colDef?.field ?? ''), data, props.matrixData ?? undefined);
                              setIsOpen(false);
                              return;
                            }
                            setValuationPicker({ rowId: String(data?.id ?? ''), columnId: String(colDef?.field ?? '') });
                            setIsOpen(false);
                            return;
                          }
                          if (!actionId) { setIsOpen(false); return; }
                          const fundId = props.fundId ?? props.matrixData?.metadata?.fundId;
                          const inputs = buildActionInputs(actionId, data, colDef.field, props.matrixData);
                          const request = {
                            action_id: actionId,
                            row_id: String(data?.id ?? ''),
                            column_id: String(colDef?.field ?? ''),
                            inputs,
                            mode: 'portfolio' as const,
                            fund_id: fundId ?? undefined,
                            company_id: data?.companyId ?? undefined,
                          };
                          setIsOpen(false);
                          if (onRunCellAction) {
                            try {
                              await onRunCellAction(request);
                            } catch {
                              /* Status shown in-cell via cellActionStatus */
                            }
                            return;
                          }
                          try {
                            const res = await executeAction(request);
                            if (res.success && props.onCellActionResult) {
                              await props.onCellActionResult(String(data?.id), String(colDef?.field), res);
                            } else if (!res.success) {
                              toast.error(res.error ?? 'Action failed');
                            }
                          } catch (e) {
                            toast.error(e instanceof Error ? e.message : 'Action failed');
                          }
                        }}
                      >
                        {getWorkflowIcon(workflow.category)}
                        <div className="flex flex-col">
                          <span className="font-medium text-sm">{workflow.name}</span>
                          <span className={cn("text-xs text-muted-foreground", props.useAgentPanel && (isRunValuation || isRunPWERM) && "italic")}>{chatHint}</span>
                        </div>
                      </DropdownMenuItem>
                    );
                  })}

              {/* Delete company / Delete column */}
              {(props.onRowDelete || props.onDeleteColumn) && (
                <>
                  <DropdownMenuSeparator />
                  <div className="px-2 py-1.5 text-xs font-semibold text-muted-foreground">
                    Remove
                  </div>
                  {props.onRowDelete && (
                    <DropdownMenuItem
                      className={cn(DROPDOWN_ITEM_CLASS, "text-destructive focus:text-destructive")}
                      onClick={async () => {
                        setIsOpen(false);
                        const rowId = data?.id;
                        if (rowId) await props.onRowDelete?.(rowId);
                      }}
                    >
                      <Trash2 className={ICON_CLASS} />
                      <span>Delete company</span>
                    </DropdownMenuItem>
                  )}
                  {props.onDeleteColumn && (
                    <DropdownMenuItem
                      className={cn(DROPDOWN_ITEM_CLASS, "text-destructive focus:text-destructive")}
                      onClick={() => {
                        setIsOpen(false);
                        const columnId = colDef?.field;
                        if (columnId) props.onDeleteColumn?.(columnId);
                      }}
                    >
                      <Columns3 className={ICON_CLASS} />
                      <span>Delete column</span>
                    </DropdownMenuItem>
                  )}
                </>
              )}
              </div>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      )}

      {/* Valuation method picker: only render when parent does not handle it (onOpenValuationPicker not set) */}
      {!onOpenValuationPicker && (
      <Dialog open={!!valuationPicker} onOpenChange={(open) => !open && setValuationPicker(null)}>
        <DialogContent className="sm:max-w-md" onPointerDownOutside={(e) => e.stopPropagation()}>
          <DialogHeader>
            <DialogTitle>Run Valuation — choose method</DialogTitle>
            <DialogDescription>Select a valuation method to run for this row.</DialogDescription>
          </DialogHeader>
          <div className="grid gap-2 py-4 max-h-[60vh] overflow-y-auto">
            {Object.entries(groupedMethods).map(([category, methods]) => (
              <div key={category}>
                <div className="px-0 py-1 text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                  {category}
                </div>
                {methods.map((method) => (
                  <Button
                    key={method.value}
                    variant="outline"
                    className="justify-start h-auto py-2 text-left"
                    onClick={async () => {
                      if (!valuationPicker) return;
                      const fundId = props.fundId ?? props.matrixData?.metadata?.fundId;
                      const companyId = data?.companyId;
                      const actionId = method.value === 'auto' ? 'valuation_engine.auto' : `valuation_engine.${method.value}`;
                      const inputs = buildActionInputs(actionId, data, colDef.field, props.matrixData);
                      if (method.value !== 'auto') inputs.method = method.value;
                      setValuationPicker(null);
                      const request = {
                        action_id: actionId,
                        row_id: valuationPicker.rowId,
                        column_id: valuationPicker.columnId,
                        inputs,
                        mode: 'portfolio' as const,
                        fund_id: fundId ?? undefined,
                        company_id: companyId ?? undefined,
                      };
                      if (onRunCellAction) {
                        try {
                          await onRunCellAction(request);
                        } catch {
                          /* Status shown in-cell via cellActionStatus */
                        }
                        return;
                      }
                      try {
                        const res = await executeAction(request);
                        if (res.success && props.onCellActionResult) {
                          await props.onCellActionResult(valuationPicker.rowId, valuationPicker.columnId, res);
                        } else if (!res.success) {
                          toast.error(res.error ?? 'Valuation failed');
                        }
                      } catch (e) {
                        toast.error(e instanceof Error ? e.message : 'Valuation failed');
                      }
                    }}
                  >
                    <TrendingUp className="h-3.5 w-3.5 mr-2 flex-shrink-0" />
                    <div className="flex flex-col items-start">
                      <span className="font-medium text-sm">{method.label}</span>
                      <span className="text-xs text-muted-foreground">{method.description}</span>
                    </div>
                  </Button>
                ))}
              </div>
            ))}
          </div>
        </DialogContent>
      </Dialog>
      )}

      {/* Workflow/action picker: choose actions and target, then build formula and call onWorkflowStart */}
      <Dialog open={!!workflowPicker} onOpenChange={(open) => !open && setWorkflowPicker(null)}>
        <DialogContent className="sm:max-w-md" onPointerDownOutside={(e) => e.stopPropagation()}>
          <DialogHeader>
            <DialogTitle>Run workflow</DialogTitle>
            <DialogDescription>
              Select one or more actions and the target (current row or all rows). The formula will be written to the cell.
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 py-4">
            <div>
              <Label className="text-xs font-semibold text-muted-foreground">Target</Label>
              <Select
                value={workflowPicker?.target ?? 'all'}
                onValueChange={(v: 'current' | 'all') =>
                  setWorkflowPicker((p) => (p ? { ...p, target: v } : null))
                }
              >
                <SelectTrigger className="mt-1">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="current">Current row</SelectItem>
                  <SelectItem value="all">All rows</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div>
              <Label className="text-xs font-semibold text-muted-foreground">Actions</Label>
              <div className="mt-2 max-h-[40vh] overflow-y-auto space-y-2 border rounded-md p-2">
                {pickerActions.map((wf) => {
                  const checked = workflowPicker?.selectedIds.includes(wf.id) ?? false;
                  return (
                    <div
                      key={wf.id}
                      className={cn(
                        'flex items-start gap-2 rounded p-2 hover:bg-accent/50 cursor-pointer',
                        checked && 'bg-accent/30'
                      )}
                      onClick={() =>
                        setWorkflowPicker((p) =>
                          p
                            ? {
                                ...p,
                                selectedIds: checked
                                  ? p.selectedIds.filter((id) => id !== wf.id)
                                  : [...p.selectedIds, wf.id],
                              }
                            : null
                        )
                      }
                    >
                      <Checkbox checked={checked} onCheckedChange={() => {}} />
                      <div className="flex flex-col">
                        <span className="font-medium text-sm">{wf.name}</span>
                        <span className="text-xs text-muted-foreground">{wf.description}</span>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
            <div className="flex justify-end gap-2">
              <Button variant="outline" onClick={() => setWorkflowPicker(null)}>
                Cancel
              </Button>
              <Button
                variant="outline"
                onClick={() => {
                  if (!workflowPicker || !props.onWorkflowStart) {
                    setWorkflowPicker(null);
                    return;
                  }
                  const ids = workflowPicker.selectedIds.length ? workflowPicker.selectedIds : pickerActions.slice(0, 1).map((a) => a.id);
                  const formula = `=WORKFLOW("${ids.join(',')}", "${workflowPicker.target}")`;
                  props.onWorkflowStart(workflowPicker.rowId, workflowPicker.columnId, formula);
                  setWorkflowPicker(null);
                }}
              >
                Apply formula
              </Button>
              {props.onWorkflowRun && (
                <Button
                  onClick={async () => {
                    if (!workflowPicker || !props.onWorkflowRun) {
                      setWorkflowPicker(null);
                      return;
                    }
                    const rowId = workflowPicker.rowId;
                    const columnId = workflowPicker.columnId;
                    const ids = workflowPicker.selectedIds.length ? workflowPicker.selectedIds : pickerActions.slice(0, 1).map((a) => a.id);
                    const formula = `=WORKFLOW("${ids.join(',')}", "${workflowPicker.target}")`;
                    setWorkflowPicker(null);
                    await props.onWorkflowRun(rowId, columnId, formula);
                  }}
                >
                  Apply and run
                </Button>
              )}
            </div>
          </div>
        </DialogContent>
      </Dialog>

      {/* Source Indicator Badge - Small, subtle */}
      {source !== 'manual' && (
        <div className="absolute bottom-0 right-0">
          <SourceIcon className="h-2.5 w-2.5 text-muted-foreground/60" />
        </div>
      )}
    </div>
  );
}
