'use client';

import React, { useState, useEffect, useMemo, useCallback, useRef } from 'react';
import { toast } from 'sonner';
import { formatCurrency, formatCellValue as formatCellValueShared } from '@/lib/matrix/cell-formatters';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Label } from '@/components/ui/label';
import { Badge } from '@/components/ui/badge';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  Download,
  Save,
  Upload,
  RefreshCw,
  Edit2,
  X,
  Check,
  TrendingUp,
  DollarSign,
  AlertTriangle,
  Sparkles,
  Filter,
  Search,
  Eye,
  EyeOff,
  FileSpreadsheet,
  FileCode,
  Copy,
  FileText,
  Calendar,
  Link as LinkIcon,
  Loader2,
  MoreVertical,
  Plus,
  BarChart3,
  ChevronDown,
  ChevronUp,
  Pin,
} from 'lucide-react';
import { MatrixInsights } from './MatrixInsights';
import { ChartViewport, type ChartTab } from './ChartViewport';
import { AgentPanel, type ToolCallEntry, type PlanStep } from './AgentPanel';
import {
  compressPortfolioContext,
  copyCompressedContextToClipboard,
  downloadCompressedContext,
  buildGridSnapshot,
} from '@/lib/portfolio-context-compressor';
import CitationDisplay, { Citation } from '@/components/CitationDisplay';
import {
  ValuationCell,
  DocumentsCell,
  ChartsCell,
  AnalyticsCell,
  CitationsCell,
} from './MatrixCellFeatures';
import { MatrixFieldCard } from './MatrixFieldCard';
import { AGGridMatrix } from './AGGridMatrix';
import ReactMarkdown from 'react-markdown';
import dynamic from 'next/dynamic';
import { MemoEditor, type DocumentSection } from '@/components/memo/MemoEditor';

const TableauLevelCharts = dynamic(() => import('@/components/charts/TableauLevelCharts'), { ssr: false });
import { SkeletonTable } from '@/components/ui/skeleton';
import { CellActionProvider } from './CellActionContext';
import { SuggestionsProvider } from './SuggestionsContext';
import { useDocumentSuggestions } from './DocumentSuggestions';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { addMatrixColumn, addCompanyToMatrix, createCompanyForMatrix } from '@/lib/matrix/matrix-api-service';
import {
  formatActionOutput,
  extractExplanation,
  extractCellValue,
  executeAction,
  type ActionExecutionResponse,
  type ActionExecutionRequest,
} from '@/lib/matrix/cell-action-registry';
import { buildActionInputs, VALUATION_METHODS } from './CellDropdownRenderer';
import {
  createColumnsFromMetadata,
  populateCellsForNewColumns,
  canonicalizeMatrixColumns,
  columnIdsMatch,
  normalizeColumnIdForMatch,
  isDummyMatrixColumn,
  type ColumnDefinition,
} from '@/lib/matrix/column-helpers';
import {
  parseWorkflowFormula,
  runWorkflow,
  type WorkflowRunResult,
} from '@/lib/matrix/workflow-executor';
import {
  mapCsvHeadersToColumns,
  mapCsvValue,
  createColumnDefinitions,
  getDbFieldName,
  type FieldMapping,
} from '@/lib/csv-field-mapper';
import { normalizeChartConfig } from '@/lib/matrix/chart-utils';
import { buildCellEditOptionsFromSuggestion, buildApplyPayloadFromSuggestion, acceptSuggestionViaApi, rejectSuggestion, addServiceSuggestion } from '@/lib/matrix/suggestion-helpers';
import { exportMatrixToCSV, exportMatrixToXLS, exportToPDF } from '@/lib/matrix/export-orchestrator';

export type MatrixMode = 'portfolio' | 'query' | 'custom' | 'lp';

export interface MatrixColumn {
  id: string;
  name: string;
  type: 'text' | 'number' | 'currency' | 'percentage' | 'date' | 'boolean' | 'formula' | 'sparkline';
  width?: number;
  formula?: string;
  editable?: boolean;
}

export interface MatrixCell {
  value: any;
  displayValue?: string;
  source?: 'manual' | 'document' | 'api' | 'formula' | 'scenario' | 'agent';
  sourceDocumentId?: number | string;
  lastUpdated?: string;
  editedBy?: string;
  formula?: string;
  metadata?: {
    confidence?: number;
    citation?: string;
    citations?: { id?: string; source?: string; url?: string; title?: string }[];
    explanation?: string; // Explanation from cell actions (e.g., valuation method explanation)
    method?: string; // Method used (e.g., 'PWERM', 'DCF', 'OPM')
    chart_config?: any; // Chart configuration for advanced visualizations
    raw_output?: any; // Raw output from service (for arrays, objects, etc.)
    output_type?: string; // Output type: 'number', 'array', 'chart', 'object', etc.
    time_series?: any[]; // Time series data for sparklines
    scenario?: boolean;
    scenario_change?: unknown;
    scenario_change_pct?: unknown;
    documents?: any;
    documentCount?: number;
    chartData?: any;
    chartType?: string;
    structured_array?: any[];
    array_length?: number;
    output_structure?: string;
    generated_by?: string;
    source_column?: string;
    source_row?: string;
    workflow_ran?: boolean;
    query?: string;
    query_result?: boolean;
    valuationMethod?: string;
  };
  sparkline?: number[];
}

export interface MatrixRow {
  id: string;
  companyId?: string;
  companyName?: string;
  cells: Record<string, MatrixCell>;
  [key: string]: any; // Allow additional properties
}

export interface MatrixData {
  columns: MatrixColumn[];
  rows: MatrixRow[];
  formulas?: Record<string, string>;
  metadata?: {
    lastUpdated?: string;
    dataSource?: string;
    confidence?: number;
    query?: string;
    fundId?: string;
    charts?: any[]; // Charts from unified MCP orchestrator
  };
}

interface UnifiedMatrixProps {
  mode?: MatrixMode;
  fundId?: string;
  initialData?: MatrixData;
  onDataChange?: (data: MatrixData) => void;
  showInsights?: boolean;
  showExport?: boolean;
  showQueryBar?: boolean; // For portfolio mode - hide query bar
  onCellEdit?: (rowId: string, columnId: string, value: any, options?: { data_source?: 'manual' | 'service' | 'document' | 'api' | 'formula'; metadata?: Record<string, unknown>; sourceDocumentId?: string | number }) => Promise<void>;
  onRefresh?: () => void; // Callback to refresh parent data (e.g., reload portfolios)
  onQuery?: (query: string) => Promise<MatrixData>; // Optional external query handler
  onCitationsChange?: (citations: Citation[]) => void; // Callback for citations
  /** Called after a cell action completes; panel can show explanation/citations in Citations & service logs. */
  onServiceResultLog?: (rowId: string, columnId: string, response: ActionExecutionResponse) => void;
  // Row-level actions
  onRowEdit?: (rowId: string) => void;
  onRowDelete?: (rowId: string) => Promise<void>;
  onRowDuplicate?: (rowId: string) => void;
  // Service actions
  onRunValuation?: (rowId: string) => Promise<void>;
  onRunPWERM?: (rowId: string) => Promise<void>;
  onUploadDocument?: (rowId: string) => void;
  /** Backend-registered cell actions (from getAvailableActions). When set, dropdown/picker show these. */
  availableActions?: import('@/lib/matrix/cell-action-registry').CellAction[];
  /** When true, cell action results go to suggestions feed (addServiceSuggestion) instead of applying directly. */
  suggestBeforeApply?: boolean;
  /** Phase 6: Use AgentPanel (Chat + Suggestions + Plan + Activity) instead of ChartViewport only. */
  useAgentPanel?: boolean;
  /** Phase 6: Tool-call feed entries for Activity tab. */
  toolCallEntries?: ToolCallEntry[];
  /** Phase 6: Plan steps for Plan tab. */
  planSteps?: PlanStep[];
  /** Phase 6: Log tool call start/end for Activity feed. */
  onToolCallLog?: (entry: Omit<ToolCallEntry, 'id' | 'at'>) => void;
  /** Phase 6: Run service from panel (actionId, rowId, columnId) → execute + add suggestion. */
  onRunService?: (actionId: string, rowId: string, columnId: string) => Promise<void>;
  /** Phase 6: Retry a service suggestion (re-run same action). */
  onRetrySuggestion?: (suggestion: import('./DocumentSuggestions').DocumentSuggestion) => Promise<void>;
}

export function UnifiedMatrix({
  mode = 'portfolio',
  fundId,
  initialData,
  onDataChange,
  showInsights = true,
  showExport = true,
  showQueryBar = true, // Show query bar by default, can hide in portfolio mode
  onCellEdit,
  onRefresh,
  onQuery,
  onCitationsChange,
  onServiceResultLog,
  onRowEdit,
  onRowDelete,
  onRowDuplicate,
  onRunValuation,
  onRunPWERM,
  onUploadDocument,
  availableActions,
  suggestBeforeApply = true,
  useAgentPanel = true,
  toolCallEntries = [],
  planSteps = [],
  onToolCallLog,
  onRunService,
  onRetrySuggestion,
}: UnifiedMatrixProps) {
  // Helper to create default matrix structure based on mode
  const getDefaultMatrixData = useCallback((mode: MatrixMode, fundId?: string): MatrixData => {
    if (mode === 'portfolio') {
      return {
        columns: [
          { id: 'company', name: 'Company', type: 'text', width: 200, editable: true },
          { id: 'documents', name: 'Documents', type: 'text', width: 140, editable: false },
          { id: 'sector', name: 'Sector', type: 'text', width: 120, editable: true },
          { id: 'stage', name: 'Stage', type: 'text', width: 100, editable: true },
          { id: 'arr', name: 'ARR', type: 'currency', width: 120, editable: true },
          { id: 'burnRate', name: 'Burn Rate', type: 'currency', width: 120, editable: true },
          { id: 'runway', name: 'Runway (mo)', type: 'number', width: 100, editable: true },
          { id: 'grossMargin', name: 'Gross Margin', type: 'percentage', width: 120, editable: true },
          { id: 'cashInBank', name: 'Cash in Bank', type: 'currency', width: 140, editable: true },
          { id: 'valuation', name: 'Current Valuation', type: 'currency', width: 140, editable: true },
          { id: 'ownership', name: 'Ownership %', type: 'percentage', width: 120, editable: true },
          { id: 'optionPool', name: 'Option Pool (bps)', type: 'number', width: 120, editable: true },
          { id: 'latestUpdate', name: 'Latest Update', type: 'text', width: 160, editable: true },
          { id: 'productUpdates', name: 'Product Updates', type: 'text', width: 160, editable: true },
        ],
        rows: [],
        metadata: {
          dataSource: 'manual',
          fundId,
          lastUpdated: new Date().toISOString(),
        },
      };
    } else if (mode === 'custom') {
      return {
        columns: [
          { id: 'company', name: 'Company', type: 'text', editable: true },
          { id: 'sector', name: 'Sector', type: 'text', editable: true },
          { id: 'arr', name: 'ARR', type: 'currency', editable: true },
          { id: 'valuation', name: 'Valuation', type: 'currency', editable: true },
          { id: 'ownership', name: 'Ownership %', type: 'percentage', editable: true },
        ],
        rows: [],
        metadata: { dataSource: 'custom', lastUpdated: new Date().toISOString() },
      };
    } else if (mode === 'lp') {
      return {
        columns: [
          { id: 'lpName', name: 'LP Name', type: 'text', width: 180, editable: true },
          { id: 'lpType', name: 'Type', type: 'text', width: 120, editable: true },
          { id: 'status', name: 'Status', type: 'text', width: 100, editable: true },
          { id: 'commitment', name: 'Commitment', type: 'currency', width: 140, editable: true },
          { id: 'called', name: 'Called', type: 'currency', width: 130, editable: true },
          { id: 'distributed', name: 'Distributed', type: 'currency', width: 140, editable: true },
          { id: 'unfunded', name: 'Unfunded', type: 'currency', width: 130, editable: false },
          { id: 'dpi', name: 'DPI', type: 'number', width: 80, editable: false },
          { id: 'coInvest', name: 'Co-Invest', type: 'boolean', width: 90, editable: true },
          { id: 'vintageYear', name: 'Vintage', type: 'number', width: 90, editable: true },
          { id: 'contactName', name: 'Contact', type: 'text', width: 140, editable: true },
          { id: 'capacity', name: 'Capacity', type: 'currency', width: 130, editable: true },
        ],
        rows: [],
        metadata: { dataSource: 'lp', lastUpdated: new Date().toISOString() },
      };
    } else {
      // query mode - minimal default
      return {
        columns: [
          { id: 'name', name: 'Name', type: 'text', editable: true },
          { id: 'value', name: 'Value', type: 'text', editable: true },
        ],
        rows: [],
        metadata: { dataSource: 'query', lastUpdated: new Date().toISOString() },
      };
    }
  }, []);

  // ALWAYS initialize with defaults - never allow null
  const [matrixData, setMatrixData] = useState<MatrixData>(
    initialData || getDefaultMatrixData(mode, fundId)
  );
  const [isLoading, setIsLoading] = useState(false);
  const [editingCell, setEditingCell] = useState<{ rowId: string; columnId: string } | null>(null);
  const [editValue, setEditValue] = useState('');
  const editInFlightRef = useRef(0);
  const [query, setQuery] = useState('');
  const [showInsightsPanel, setShowInsightsPanel] = useState(mode === 'portfolio' ? false : showInsights);
  const [selectedRows, setSelectedRows] = useState<Set<string>>(new Set());
  const [startEditingCellRef, setStartEditingCellRef] = useState<((rowId: string, columnId: string) => void) | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isImporting, setIsImporting] = useState(false);
  const [showImportDialog, setShowImportDialog] = useState(false);
  const [isDraggingCSV, setIsDraggingCSV] = useState(false);
  const [isDraggingDocument, setIsDraggingDocument] = useState(false);
  const [showLoadDialog, setShowLoadDialog] = useState(false);
  const [savedConfigs, setSavedConfigs] = useState<any[]>([]);
  const [citations, setCitations] = useState<Citation[]>([]);
  const [showAddColumnDialog, setShowAddColumnDialog] = useState(false);
  const [newColumn, setNewColumn] = useState({
    name: '',
    type: 'text' as MatrixColumn['type'],
    service: '',
  });
  const [showAddCompanyDialog, setShowAddCompanyDialog] = useState(false);
  const [newCompany, setNewCompany] = useState({
    name: '',
    sector: '',
    stage: '',
    investmentAmount: mode === 'portfolio' ? '1' : '',
    ownershipPercentage: '',
    currentArr: '',
  });
  /** Phase 6: Right panel (Agent/Charts) always-on by default — Cursor-like layout */
  const [showChartViewport, setShowChartViewport] = useState(true);
  const [viewportActiveTab, setViewportActiveTab] = useState<ChartTab>('charts');
  /** Ref to the memo editor container for html2canvas chart capture in PDF export */
  const memoContainerRef = useRef<HTMLDivElement>(null);

  /** Memo sections — persisted to localStorage, shared between ChartViewport and AgentChat */
  const [memoSections, setMemoSections] = useState<DocumentSection[]>(() => {
    if (typeof window === 'undefined') return [{ type: 'heading1', content: 'Working Memo' }, { type: 'paragraph', content: '' }];
    try {
      const stored = localStorage.getItem(`dilla_memo_${fundId || 'default'}`);
      if (stored) return JSON.parse(stored);
    } catch {}
    return [{ type: 'heading1', content: 'Working Memo' }, { type: 'paragraph', content: '' }];
  });

  /** Memo panel below grid — emerges when agent builds it out */
  const [memoPanelExpanded, setMemoPanelExpanded] = useState(false);
  /** Track companies/capTables from last analysis for pin-to-company */
  const [memoPanelContext, setMemoPanelContext] = useState<{ companies?: any[]; capTables?: any[] }>({});

  const handleAnalysisReady = useCallback((analysis: {
    sections: Array<{ title?: string; content?: string; level?: number }>;
    charts: Array<{ type: string; title?: string; data: any }>;
    companies?: any[];
    capTables?: any[];
  }) => {
    // Convert raw analysis sections → DocumentSection[] and append to memo
    const converted: DocumentSection[] = [];
    for (const s of analysis.sections) {
      if (s.title) {
        const headingType = (s.level ?? 1) <= 1 ? 'heading1' : (s.level === 2 ? 'heading2' : 'heading3');
        converted.push({ type: headingType, content: s.title });
      }
      if (s.content) {
        converted.push({ type: 'paragraph', content: s.content });
      }
    }
    for (const c of analysis.charts) {
      converted.push({ type: 'chart', chart: { type: c.type, title: c.title, data: c.data } });
    }
    if (converted.length > 0) {
      setMemoSections(prev => [...prev, ...converted]);
      setMemoPanelExpanded(true);
    }
    setMemoPanelContext({ companies: analysis.companies, capTables: analysis.capTables });
  }, []);

  // Persist memo to localStorage on change (debounced)
  const memoSaveTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  useEffect(() => {
    if (memoSaveTimer.current) clearTimeout(memoSaveTimer.current);
    memoSaveTimer.current = setTimeout(() => {
      try {
        localStorage.setItem(`dilla_memo_${fundId || 'default'}`, JSON.stringify(memoSections));
      } catch {}
    }, 800);
    return () => { if (memoSaveTimer.current) clearTimeout(memoSaveTimer.current); };
  }, [memoSections, fundId]);
  const [valuationPicker, setValuationPicker] = useState<{ rowId: string; columnId: string; rowData: any; matrixData: MatrixData } | null>(null);
  const [uploadDocumentTarget, setUploadDocumentTarget] = useState<{ rowId: string; columnId: string } | null>(null);
  const uploadFileInputRef = useRef<HTMLInputElement>(null);
  /** Per-cell status for in-cell display (replaces toast). Key = rowId_columnId. */
  const [cellActionStatus, setCellActionStatus] = useState<import('./CellActionContext').CellActionStatusMap>({});
  const { suggestions: documentSuggestionsList, insights: documentInsights, loading: suggestionsLoading, error: suggestionsError, refresh: refreshSuggestions } = useDocumentSuggestions(matrixData, fundId);
  /** Optimistically hide accepted/rejected suggestions so they disappear immediately on click.
   *  Prune stale IDs once the server list no longer contains them (i.e. they were persisted). */
  const [optimisticallyHiddenIds, setOptimisticallyHiddenIds] = useState<Set<string>>(new Set());
  const visibleSuggestions = useMemo(() => {
    return documentSuggestionsList.filter((s) => !optimisticallyHiddenIds.has(s.id));
  }, [documentSuggestionsList, optimisticallyHiddenIds]);

  // Prune stale hidden IDs once the server list no longer contains them
  useEffect(() => {
    const serverIds = new Set(documentSuggestionsList.map((s) => s.id));
    setOptimisticallyHiddenIds((prev) => {
      const next = new Set(prev);
      for (const id of prev) {
        if (!serverIds.has(id)) next.delete(id);
      }
      return next.size === prev.size ? prev : next;
    });
  }, [documentSuggestionsList]);
  const suggestPollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  /** Plan steps from agent (Plan tab) - updated by AgentChat when backend returns plan_steps */
  const [planStepsState, setPlanStepsState] = useState<PlanStep[]>(planSteps || []);
  const loadPortfolioDataRef = useRef<() => Promise<void>>();
  const portfolioAbortRef = useRef<AbortController | null>(null);
  const matrixDataRef = useRef<MatrixData | null>(null);
  matrixDataRef.current = matrixData;

  /** Export from chat: CSV, XLS, or PDF */
  const handleExportRequest = useCallback((format: 'csv' | 'xlsx' | 'pdf', payload?: { matrixData?: MatrixData; messageContent?: string }) => {
    const data = payload?.matrixData ?? matrixData;
    if (!data) return;
    if (format === 'csv') exportMatrixToCSV(data);
    else if (format === 'xlsx') exportMatrixToXLS(data);
    else if (format === 'pdf') {
      const content = payload?.messageContent ?? data.rows.map((r) =>
        data.columns.map((c) => {
          const cell = r.cells?.[c.id];
          const v = cell?.displayValue ?? cell?.value ?? (c.id === 'company' ? r.companyName : r[c.id]);
          return `${c.name}: ${v ?? '-'}`;
        }).join(' | ')
      ).join('\n');
      exportToPDF(content, { title: 'Matrix Export' });
    }
  }, [matrixData]);

  /** Chart from chat: NAV or DPI Sankey - same endpoints as ChartViewport */
  const handleRequestChart = useCallback(async (chartType: 'nav' | 'dpi_sankey'): Promise<Array<{ type: string; title?: string; data: unknown }>> => {
    if (!fundId || !matrixData?.rows?.length) return [];
    const companyIds = matrixData.rows.map((r) => r.id).filter(Boolean);
    const charts: Array<{ type: string; title?: string; data: unknown }> = [];
    if (chartType === 'nav') {
      const res = await fetch(`/api/portfolio/${fundId}/nav-timeseries?companyIds=${companyIds.join(',')}&aggregate=true`);
      if (res.ok) {
        const navData = await res.json();
        if (navData.aggregate?.labels?.length) {
          charts.push({
            type: 'line',
            title: 'Portfolio NAV (Live)',
            data: {
              labels: navData.aggregate.labels,
              datasets: [{ label: 'Total NAV', data: navData.aggregate.data, borderColor: '#059669' }],
            },
          });
        }
      }
    } else if (chartType === 'dpi_sankey') {
      const res = await fetch(`/api/cell-actions/actions/portfolio.dpi_sankey/execute`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ fund_id: fundId, inputs: {} }),
      });
      if (res.ok) {
        const dpiJson = await res.json();
        const cfg = dpiJson.metadata?.chart_config || dpiJson.metadata?.chart_to_create || dpiJson;
        if (cfg?.data) {
          charts.push({
            type: 'sankey',
            title: cfg.title || 'DPI Flow (Follow-on Strategy)',
            data: cfg.data,
          });
        }
      }
    }
    return charts;
  }, [fundId, matrixData?.rows]);

  /** Document upload from chat: bulk upload → Celery process-batch-async; poll for suggestions so they appear in chat. */
  const handleUploadDocument = useCallback(async (files: File[], opts: { companyId?: string; fundId?: string }) => {
    if (!files.length) return;
    const formData = new FormData();
    for (const file of files) formData.append('file', file);
    if (opts.companyId) formData.append('company_id', opts.companyId);
    if (opts.fundId) formData.append('fund_id', opts.fundId);
    const res = await fetch('/api/documents/batch', { method: 'POST', body: formData });
    if (!res.ok) {
      const data = await res.json().catch(() => ({}));
      throw new Error(data.error || res.statusText);
    }
    const data = await res.json();
    toast.success(`Uploaded ${data.documentIds?.length ?? files.length} document(s)`, {
      description: 'Processing queued in background (Celery)',
    });
    window.dispatchEvent(new CustomEvent('refreshMatrix'));
    // The batch route processes synchronously, so suggestions should be
    // available after a short delay. Single refresh is enough — no polling loop.
    await refreshSuggestions();
  }, [fundId, refreshSuggestions]);

  /** Chart viewport "Ask" bar: send prompt to same agent (unified-brain) that has tools for docs, memo, modeling, what-if. */
  const handleAskFromViewport = useCallback(async (prompt: string) => {
    const matrixContext = matrixData?.rows?.length
      ? {
          rowIds: matrixData.rows.slice(0, 50).map((r) => r.id),
          companyNames: matrixData.rows.slice(0, 50).map((r) => r.companyName || r.id),
          columns: (matrixData.columns || []).slice(0, 30).map((c) => ({ id: c.id, name: c.name || c.id })),
          fundId,
          gridSnapshot: buildGridSnapshot(matrixData),
        }
      : undefined;
    try {
      const res = await fetch('/api/agent/unified-brain', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          prompt,
          output_format: 'analysis',
          context: { matrixContext, fundId },
          stream: false,
        }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        toast.error(data.error || data.details || 'Request failed');
        return;
      }
      if (data.result?.format === 'deck' && data.result?.slides?.length) {
        toast.success('Deck generated', { description: `${data.result.slides.length} slides — check chat or export for full view` });
      } else if (data.result?.sections?.length) {
        toast.success('Memo generated', { description: 'Check chat or export for full document' });
      } else {
        toast.success('Done', { description: 'Agent ran with existing tools (docs, reports, modeling)' });
      }
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Failed to run agent');
    }
  }, [matrixData, fundId]);

  useEffect(() => {
    const handler = () => {
      refreshSuggestions();
    };
    window.addEventListener('refreshSuggestionsAndOpenViewport', handler);
    return () => window.removeEventListener('refreshSuggestionsAndOpenViewport', handler);
  }, [refreshSuggestions]);

  /** Shared accept handler: optimistic grid update + suggestion removal for fast UX. */
  const handleSuggestionAccept = useCallback(async (suggestionId: string, payload?: { rowId: string; columnId: string; suggestedValue: unknown; sourceDocumentId?: string | number }) => {
    if (!payload) return;
    const row = matrixData?.rows.find((r) =>
      r.id === payload.rowId ||
      r.companyId === payload.rowId ||
      (r.companyName && r.companyName.toLowerCase() === payload.rowId.toLowerCase())
    );
    if (!row) {
      toast.error('Company no longer in matrix');
      return;
    }
    const companyId = row.companyId ?? row.id ?? payload.rowId;
    const effectiveFundId = fundId ?? matrixData?.metadata?.fundId;
    if (!effectiveFundId) {
      toast.error('Unable to save suggestion');
      return;
    }
    const { rowId, columnId, suggestedValue } = payload;
    const currencyCols = ['arr', 'valuation', 'burnRate', 'cashInBank', 'tamUsd', 'samUsd', 'somUsd'];
    const displayValue =
      typeof suggestedValue === 'number' && currencyCols.includes(columnId)
        ? formatCurrency(suggestedValue)
        : suggestedValue != null
          ? String(suggestedValue)
          : undefined;

    const suggestion = documentSuggestionsList.find((s) => s.id === suggestionId);
    const isService = suggestion?.source === 'service';

    const prevMatrix = matrixData;
    const updatedData: MatrixData = prevMatrix
      ? {
          ...prevMatrix,
          rows: prevMatrix.rows.map((r) => {
            const isMatch = r.id === rowId || r.companyId === rowId || (r.companyName && r.companyName.toLowerCase() === rowId.toLowerCase());
            if (!isMatch) return r;
            const cell = r.cells[columnId] || {};
            return {
              ...r,
              cells: {
                ...r.cells,
                [columnId]: {
                  ...cell,
                  value: suggestedValue,
                  displayValue: displayValue ?? (cell as { displayValue?: string }).displayValue,
                  source: 'agent' as const,
                  lastUpdated: new Date().toISOString(),
                },
              },
            };
          }),
        }
      : prevMatrix!;

    setMatrixData(updatedData);
    // Synchronously update the ref so any in-flight loadPortfolioData merge
    // sees the 'agent' source cell and preserves it (React render is async).
    matrixDataRef.current = updatedData;
    onDataChange?.(updatedData);
    setOptimisticallyHiddenIds((ids) => new Set([...ids, suggestionId]));

    // Prevent loadPortfolioData from running while the DB write is in flight.
    // Keep the guard up for a cooldown after accept to prevent race conditions
    // where a concurrent loadPortfolioData or refreshSuggestions sees stale data.
    editInFlightRef.current++;
    try {
      let success = false;
      if (isService && effectiveFundId) {
        const res = await acceptSuggestionViaApi(suggestionId, effectiveFundId);
        success = res.success;
        if (!success && res.error) {
          setMatrixData(prevMatrix!);
          matrixDataRef.current = prevMatrix!;
          onDataChange?.(prevMatrix!);
          setOptimisticallyHiddenIds((ids) => {
            const next = new Set(ids);
            next.delete(suggestionId);
            return next;
          });
          toast.error(res.error);
          loadPortfolioDataRef.current?.();
          return;
        }
      } else if (effectiveFundId) {
        const applyPayload = buildApplyPayloadFromSuggestion(payload, effectiveFundId, companyId, isService ? 'service' : 'document');
        const res = await acceptSuggestionViaApi(suggestionId, applyPayload);
        success = res.success;
        if (!success && res.error) {
          setMatrixData(prevMatrix!);
          matrixDataRef.current = prevMatrix!;
          onDataChange?.(prevMatrix!);
          setOptimisticallyHiddenIds((ids) => {
            const next = new Set(ids);
            next.delete(suggestionId);
            return next;
          });
          toast.error(res.error);
          loadPortfolioDataRef.current?.();
          return;
        }
      }

      toast.success('Suggestion accepted');
      // Delay refreshSuggestions slightly to allow accepted_suggestions write to propagate
      // before the GET query runs, preventing suggestion reappearance.
      setTimeout(() => {
        refreshSuggestions().catch(() => {});
      }, 500);
    } finally {
      // Keep the guard up briefly so a concurrent loadPortfolioData doesn't
      // overwrite the optimistic cell value with stale DB data before Supabase propagates.
      setTimeout(() => {
        editInFlightRef.current--;
      }, 1500);
    }
  }, [matrixData, fundId, documentSuggestionsList, refreshSuggestions, onDataChange]);

  /** Single reject wrapper: optimistic removal so suggestion disappears immediately. */
  const handleSuggestionReject = useCallback(
    async (suggestionId: string) => {
      const effectiveFundId = fundId ?? matrixData?.metadata?.fundId;
      if (!effectiveFundId) {
        toast.error('Unable to reject suggestion');
        return;
      }
      // Look up suggestion to get rowId + columnId for composite-key persistence
      const suggestion = documentSuggestionsList.find((s) => s.id === suggestionId);
      const context = suggestion
        ? { companyId: suggestion.rowId, columnId: suggestion.columnId }
        : undefined;
      setOptimisticallyHiddenIds((ids) => new Set([...ids, suggestionId]));
      const { success, error } = await rejectSuggestion(suggestionId, effectiveFundId, context);
      if (!success && error) {
        setOptimisticallyHiddenIds((ids) => {
          const next = new Set(ids);
          next.delete(suggestionId);
          return next;
        });
        toast.error(error);
        return;
      }
      toast.success('Suggestion rejected');
      refreshSuggestions().catch(() => {});
    },
    [fundId, matrixData, documentSuggestionsList, refreshSuggestions]
  );

  /** Apply multiple suggestions through the same accept wrapper (documents + service). */
  const handleApplySuggestions = useCallback(
    async (suggestionsToApply: typeof documentSuggestionsList) => {
      const effectiveFundId = fundId ?? matrixData?.metadata?.fundId;
      if (!matrixData || !effectiveFundId) return;
      for (const s of suggestionsToApply) {
        await handleSuggestionAccept(s.id, {
          rowId: s.rowId,
          columnId: s.columnId,
          suggestedValue: s.suggestedValue,
          sourceDocumentId: s.sourceDocumentId,
        });
      }
    },
    [matrixData, fundId, handleSuggestionAccept]
  );

  // Stable callback so AGGridMatrix's useEffect doesn't re-run on every parent re-render.
  // Prevents "Maximum update depth exceeded" when opening toolbar "More" or cell 3-dots dropdown.
  const handleStartEditingCell = useCallback((callback: (rowId: string, columnId: string) => void) => {
    setStartEditingCellRef(() => callback);
  }, []);

  // Handle document upload with auto-suggest: single refresh is enough.
  // The backend processes synchronously and emits suggestions before returning.
  // No polling loop needed — it caused 4x concurrent fetches and race conditions.
  const handleDocumentUploadWithSuggest = useCallback((_rowId: string) => {
    if (suggestPollRef.current) {
      clearTimeout(suggestPollRef.current as ReturnType<typeof setTimeout>);
      suggestPollRef.current = null;
    }
    refreshSuggestions();
  }, [refreshSuggestions]);

  useEffect(() => {
    return () => {
      if (suggestPollRef.current) {
        clearTimeout(suggestPollRef.current as ReturnType<typeof setTimeout>);
        suggestPollRef.current = null;
      }
    };
  }, []);


  const loadSavedColumns = async () => {
    if (!fundId) return;
    
    try {
      const response = await fetch(`/api/matrix/columns?fundId=${fundId}`);
      if (response.ok) {
        const data = await response.json();
        const savedColumns = (data.columns || []).map((col: any) => {
          // Defensive check: reject 'poo' as column name
          let columnName = col.name;
          if (!columnName || columnName === 'poo' || columnName.trim() === '') {
            // Try to find matching default column
            const defaultData = getDefaultMatrixData(mode, fundId);
            const defaultCol = defaultData.columns.find(dc => dc.id === (col.column_id || col.id));
            columnName = defaultCol?.name || col.column_id || col.id || 'Column';
          }
          
          return {
            id: col.column_id || col.id,
            name: columnName, // Use validated name
            type: col.type as MatrixColumn['type'],
            width: col.width || 120,
            formula: col.formula,
            editable: col.editable !== false,
          };
        });

        // Merge saved columns with existing columns - database columns are the source of truth
        if (matrixData && savedColumns.length > 0) {
          const savedColumnsMap = new Map(savedColumns.map(c => [c.id, c]));
          const existingColumnIds = new Set(matrixData.columns.map(c => c.id));
          
          // Start with database columns (they are the defaults/source of truth)
          const finalColumns: MatrixColumn[] = savedColumns.map(savedCol => {
            // If column already exists in matrix, merge but keep database name
            const existingCol = matrixData.columns.find(c => c.id === savedCol.id);
            if (existingCol) {
              return {
                ...existingCol,
                name: savedCol.name, // Database name is the source of truth
                type: savedCol.type || existingCol.type,
                width: savedCol.width || existingCol.width,
                formula: savedCol.formula || existingCol.formula,
                editable: savedCol.editable !== undefined ? savedCol.editable : existingCol.editable,
              };
            }
            return savedCol;
          });
          
          // Add any existing columns that don't exist in database (preserve user-added columns).
          // Never re-add dummy temp-company columns (e.g. "company 1247476565").
          matrixData.columns.forEach(existingCol => {
            if (!savedColumnsMap.has(existingCol.id) && !isDummyMatrixColumn(existingCol.id, existingCol.name)) {
              finalColumns.push(existingCol);
            }
          });
          
          // Only update if there were changes
          const hasChanges = finalColumns.length !== matrixData.columns.length ||
            finalColumns.some((col, idx) => {
              const orig = matrixData.columns[idx];
              return !orig || col.name !== orig.name || col.id !== orig.id;
            });
          
          if (hasChanges) {
            const updatedData: MatrixData = {
              ...matrixData,
              columns: finalColumns,
              rows: matrixData.rows.map(row => {
                const newCells = { ...row.cells };
                // Ensure all final columns have cells
                finalColumns.forEach((col: MatrixColumn) => {
                  if (!newCells[col.id]) {
                    newCells[col.id] = { value: null, source: 'manual' };
                  }
                });
                return { ...row, cells: newCells };
              }),
            };
            setMatrixData(updatedData);
            onDataChange?.(updatedData);
          }
        }
      }
    } catch (err) {
      console.warn('Could not load saved columns:', err);
    }
  };

  // Sync initialData changes to internal state
  // Only bootstrap from initialData when we have no rows yet - avoids overwriting loadPortfolioData result
  // (which may have DB columns, NAV sparklines, etc.)
  useEffect(() => {
    if (initialData) {
      setMatrixData((prev) => {
        const hasRows = prev?.rows?.length && prev.rows.length > 0;
        if (hasRows) return prev; // Already loaded - don't overwrite
        return initialData;
      });
    } else if (initialData === null && mode === 'portfolio' && fundId && loadPortfolioDataRef.current) {
      // When initialData is explicitly set to null (e.g., during refresh), reload portfolio data
      loadPortfolioDataRef.current();
    }
  }, [initialData, mode, fundId]);

  // Load portfolio data and Supabase columns on mount
  // This will be set up after loadPortfolioData is defined

  // Listen for refreshMatrix custom event
  useEffect(() => {
    const handleRefreshMatrix = async () => {
      if (editInFlightRef.current > 0) {
        console.log('[UnifiedMatrix] Skipping refresh - cell edit in flight');
        return;
      }
      if (mode === 'portfolio' && fundId) {
        console.log('[UnifiedMatrix] Refresh event received, reloading portfolio data');
        setIsLoading(true);
        try {
          // Use ref to get latest loadPortfolioData function
          if (loadPortfolioDataRef.current) {
            await loadPortfolioDataRef.current();
            console.log('[UnifiedMatrix] Portfolio data reloaded successfully');
            onRefresh?.();
          }
        } catch (err) {
          console.error('[UnifiedMatrix] Error during refresh:', err);
        }
      }
    };

    window.addEventListener('refreshMatrix', handleRefreshMatrix);
    return () => {
      window.removeEventListener('refreshMatrix', handleRefreshMatrix);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mode, fundId, onRefresh]);

  // Initialize empty matrix for custom mode
  useEffect(() => {
    if (mode === 'custom' && !matrixData) {
      const emptyMatrix: MatrixData = {
        columns: [
          { id: 'company', name: 'Company', type: 'text', editable: true },
          { id: 'sector', name: 'Sector', type: 'text', editable: true },
          { id: 'arr', name: 'ARR', type: 'currency', editable: true },
          { id: 'valuation', name: 'Valuation', type: 'currency', editable: true },
          { id: 'ownership', name: 'Ownership %', type: 'percentage', editable: true },
        ],
        rows: [],
        metadata: { dataSource: 'custom', lastUpdated: new Date().toISOString() }
      };
      setMatrixData(emptyMatrix);
      onDataChange?.(emptyMatrix);
    }
  }, [mode, matrixData, onDataChange]);

  // Initialize with preset columns immediately so grid is usable right away
  useEffect(() => {
    // Never overwrite when we already have loaded rows (from loadPortfolioData)
    if (matrixData?.rows?.length) return;
    if (mode === 'portfolio' && fundId) {
      // Always initialize immediately with preset columns - user can add rows right away
      // loadPortfolioData will update this later if needed
      const currentData = matrixData || getDefaultMatrixData(mode, fundId);
      // Ensure we always have columns, even if matrixData exists but has no columns
      if (!currentData.columns || currentData.columns.length === 0) {
        const defaultData = getDefaultMatrixData(mode, fundId);
        setMatrixData(defaultData);
        onDataChange?.(defaultData);
      } else if (!matrixData) {
        // If matrixData is null, initialize it
        setMatrixData(currentData);
        onDataChange?.(currentData);
      }
    } else if (!matrixData) {
      // For non-portfolio modes, also initialize with defaults
      const defaultData = getDefaultMatrixData(mode, fundId);
      setMatrixData(defaultData);
      onDataChange?.(defaultData);
    }
  }, [mode, fundId]); // Remove matrixData from deps to avoid re-running

  // Load saved configurations
  useEffect(() => {
    const saved = JSON.parse(localStorage.getItem('saved_matrices') || '[]');
    setSavedConfigs(saved);
  }, []);

  const loadPortfolioData = useCallback(async () => {
    if (!fundId) return;
    if (editInFlightRef.current > 0) {
      console.log('[UnifiedMatrix] Skipping loadPortfolioData - edit/accept in flight');
      return;
    }

    // Abort any previous in-flight portfolio load to prevent stale data
    portfolioAbortRef.current?.abort();
    const controller = new AbortController();
    portfolioAbortRef.current = controller;

    setIsLoading(true);
    setError(null);

    try {
      // Load columns and companies in parallel for faster initial load
      let columns: MatrixColumn[] = [];
      const defaultData = getDefaultMatrixData(mode, fundId);
      const defaultColumns = defaultData.columns;

      // Retry helper for transient network failures
      const fetchWithRetry = async (url: string, opts: RequestInit, retries = 1): Promise<Response> => {
        for (let attempt = 0; attempt <= retries; attempt++) {
          try {
            const res = await fetch(url, opts);
            return res;
          } catch (err) {
            if (err instanceof DOMException && err.name === 'AbortError') throw err;
            if (attempt === retries) throw err;
            console.warn(`[UnifiedMatrix] Transient fetch failure for ${url}, retrying...`);
            await new Promise(r => setTimeout(r, 500));
          }
        }
        throw new Error('Unreachable');
      };

      const [columnsResponse, companiesResponse] = await Promise.all([
        fetchWithRetry(`/api/matrix/columns?fundId=${fundId}`, { signal: controller.signal }),
        fetchWithRetry(`/api/portfolio/${fundId}/companies`, { signal: controller.signal }),
      ]);
      
      try {
        // Core columns first (fixed order, mostly empty until company data fills them)
        columns = defaultColumns.map((c) => ({ ...c }));

        if (columnsResponse.ok) {
          const columnsData = await columnsResponse.json();
          if (columnsData.error) {
            console.warn('[UnifiedMatrix] Columns API returned error:', columnsData.error, columnsData.hint || columnsData.details);
          }
          const savedColumns = (columnsData.columns || []).map((col: any) => {
            let columnName = col.name;
            if (!columnName || columnName === 'poo' || columnName.trim() === '') {
              const defaultCol = defaultColumns.find((dc) => columnIdsMatch(dc.id, col.column_id || col.id));
              columnName = defaultCol?.name || col.column_id || col.id || 'Column';
            }
            return {
              id: col.column_id || col.id,
              name: columnName,
              type: col.type as MatrixColumn['type'],
              width: col.width || 120,
              formula: col.formula,
              editable: col.editable !== false,
            };
          });
          // Flexible merge: DB can override core column display; fund-specific columns append
          // Pre-index default columns by normalized ID for O(1) lookup instead of O(n) findIndex per saved column
          const coreIndexMap = new Map<string, number>();
          for (let i = 0; i < columns.length; i++) {
            coreIndexMap.set(normalizeColumnIdForMatch(columns[i].id), i);
          }
          for (const saved of savedColumns) {
            const normalizedId = normalizeColumnIdForMatch(saved.id);
            const coreIndex = coreIndexMap.get(normalizedId);
            if (coreIndex !== undefined) {
              columns[coreIndex] = { ...columns[coreIndex], name: saved.name, width: saved.width ?? columns[coreIndex].width, type: saved.type, editable: saved.editable, formula: saved.formula };
            } else if (saved.id) {
              columns.push(saved);
            }
          }
        } else {
          // API call failed - log and use hardcoded defaults as fallback
          const errBody = await columnsResponse.json().catch(() => ({}));
          const errMsg = errBody.error || errBody.details || columnsResponse.statusText;
          const errHint = errBody.hint || (errBody.code === '42P01' ? 'Run Supabase migrations' : '');
          console.warn('[UnifiedMatrix] Columns API failed:', columnsResponse.status, errMsg, errHint || '');
          if (errBody.error === 'Supabase service not configured') {
            setError('Database not configured. Set NEXT_PUBLIC_SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY in .env.local');
          }
          columns = defaultColumns;
        }
      } catch (err) {
        console.warn('[UnifiedMatrix] Could not load saved columns:', err);
        // On error, use hardcoded defaults as fallback
        columns = defaultColumns;
      }
      
      // Final safety check: ensure columns is never empty
      if (columns.length === 0) {
        columns = defaultColumns;
      }
      
      // Strip dummy placeholder columns and enforce company-first order
      columns = canonicalizeMatrixColumns(columns);
      
      // Companies already fetched in parallel above
      if (!companiesResponse.ok) {
        const errBody = await companiesResponse.json().catch(() => ({}));
        const msg = errBody.details || errBody.error || errBody.message || 'Failed to load portfolio data';
        throw new Error(typeof msg === 'string' ? msg : 'Failed to load portfolio data');
      }
      const companies = await companiesResponse.json();
      
      if (!companies || companies.length === 0) {
        // API returned empty - don't overwrite if we already have rows from initialData
        const prev = matrixDataRef.current;
        if (prev?.rows?.length) {
          const merged: MatrixData = { ...prev, columns, metadata: { ...prev.metadata, lastUpdated: new Date().toISOString(), dataSource: 'portfolio', fundId } };
          setMatrixData(merged);
          onDataChange?.(merged);
        } else {
          const emptyData: MatrixData = {
            columns,
            rows: [],
            metadata: { lastUpdated: new Date().toISOString(), dataSource: 'portfolio', fundId },
          };
          setMatrixData(emptyData);
          onDataChange?.(emptyData);
        }
        setIsLoading(false);
        return;
      }

      // NAV time series: load grid first without waiting; fetch NAV in background and patch sparklines later
      const companyIds = companies.map((c: any) => c.id);
      const navTimeSeriesMap = new Map<string, number[]>();

      // Map companies to rows - create cells for all columns (no NAV sparklines yet for fast first paint)
      const rows: MatrixRow[] = companies.map((company: any) => {
        const currentArr = company.currentArr ?? null;
        const investmentAmount = company.investmentAmount ?? null;
        const ownershipPercentage = company.ownershipPercentage ?? null;
        // Use persisted valuation directly; only derive from investment/ownership as last resort. Never invent multiples.
        const valuation = company.valuation ?? null;
        const ownership = ownershipPercentage != null ? ownershipPercentage / 100 : null;
        const nav = valuation != null && ownership != null ? valuation * ownership : null;
        const navTimeSeries = navTimeSeriesMap.get(company.id) || [];

        // Build cells for all columns - map common field names
        const cells: Record<string, MatrixCell> = {};
        
        columns.forEach((col) => {
          // Map column IDs to company data fields
          let value: any = null;
          let source: 'manual' | 'document' | 'api' | 'formula' = 'manual';
          let displayValue: string | undefined;
          let lastUpdated: string | undefined;
          let sourceDocumentId: string | undefined;
          let sparkline: number[] | undefined;

          // Normalize: lowercase + strip spaces so "Burn Rate" and "burn_rate" both match
          const colId = (col.id || '').toLowerCase().replace(/\s+/g, '');
          
          if (colId === 'company' || colId === 'companyname' || col.id === 'company' || col.id === 'companyName') {
            value = company.name;
            source = 'api';
          } else if (colId === 'sector') {
            value = company.sector || '-';
            source = 'api';
          } else if (colId === 'arr') {
            value = currentArr;
            displayValue = formatCurrency(currentArr);
            source = 'document';
            lastUpdated = company.revenueUpdatedAt;
            sourceDocumentId = company.revenueDocumentId;
          } else if (colId === 'burnrate' || colId === 'burn_rate') {
            value = company.burnRate ?? null;
            displayValue = formatCurrency(company.burnRate);
            source = 'document';
            lastUpdated = company.burnRateUpdatedAt;
            sourceDocumentId = company.burnRateDocumentId;
          } else if (colId === 'runway') {
            value = company.runwayMonths ?? null;
            displayValue = company.runwayMonths ? `${company.runwayMonths}m` : '-';
            source = 'document';
            lastUpdated = company.runwayUpdatedAt;
            sourceDocumentId = company.runwayDocumentId;
          } else if (colId === 'grossmargin' || colId === 'gross_margin') {
            value = company.grossMargin ?? null;
            displayValue = company.grossMargin ? `${(company.grossMargin * 100).toFixed(1)}%` : '-';
            source = 'document';
            lastUpdated = company.grossMarginUpdatedAt;
            sourceDocumentId = company.grossMarginDocumentId;
          } else if (colId === 'cashinbank' || colId === 'cash_in_bank') {
            value = company.cashInBank ?? null;
            displayValue = formatCurrency(company.cashInBank);
            source = 'document';
            lastUpdated = company.cashUpdatedAt;
            sourceDocumentId = company.cashDocumentId;
          } else if (colId === 'valuation' || colId === 'currentvaluation' || colId === 'current_valuation_usd') {
            value = valuation;
            displayValue = formatCurrency(valuation);
            source = 'formula';
          } else if (colId === 'nav') {
            value = nav;
            displayValue = formatCurrency(nav);
            source = 'formula';
            sparkline = navTimeSeries.length > 0 ? navTimeSeries : undefined;
          } else if (colId === 'ownership' || colId === 'ownership%') {
            value = ownershipPercentage;
            displayValue = ownershipPercentage ? `${ownershipPercentage.toFixed(1)}%` : '-';
            source = 'api';
          } else if (colId === 'invested') {
            value = investmentAmount;
            displayValue = formatCurrency(investmentAmount);
            source = 'api';
          } else if (colId === 'investmentdate' || colId === 'first_investment_date' || colId === 'date_announced' || col.id === 'investmentDate') {
            value = company.investmentDate || company.first_investment_date || null;
            displayValue = value ? String(value) : undefined;
            source = 'api';
          } else if (colId === 'lead' || colId === 'investment_lead') {
            value = company.investmentLead ?? company.investment_lead ?? null;
            displayValue = value != null && value !== '' ? String(value) : undefined;
            source = 'api';
          } else if (colId === 'optionpool' || col.id === 'optionPool') {
            value = company.option_pool_bps ?? company.optionPool ?? null;
            displayValue = value != null ? String(value) : undefined;
            source = 'api';
          } else if (colId === 'latestupdate' || col.id === 'latestUpdate') {
            value = company.latest_update ?? company.latestUpdate ?? null;
            displayValue = value != null ? String(value) : undefined;
            source = 'api';
          } else if (colId === 'productupdates' || col.id === 'productUpdates') {
            value = company.product_updates ?? company.productUpdates ?? null;
            displayValue = value != null ? String(value) : undefined;
            source = 'api';
          } else if (colId === 'documents') {
            const docs = company.documents;
            const docList = Array.isArray(docs) ? docs : [];
            value = docList.length > 0 ? docList : null;
            displayValue = docList.length === 0 ? undefined : docList.length === 1 ? '1 document' : `${docList.length} documents`;
            source = docList.length > 0 ? 'document' : 'manual';
          } else {
            // Flexible: try col.id, col.name, then any company key that matches when normalized (snake_case, camelCase, extra_data keys)
            const tryKeys = [col.id, col.name].filter(Boolean) as string[];
            const normalizedCol = (col.id || '').toLowerCase().replace(/\s+/g, '').replace(/_/g, '');
            if (normalizedCol && !tryKeys.some((k) => (k || '').toLowerCase().replace(/_/g, '') === normalizedCol)) {
              for (const k of Object.keys(company)) {
                if ((k || '').toLowerCase().replace(/_/g, '') === normalizedCol) tryKeys.push(k);
              }
            }
            let raw: unknown = undefined;
            for (const k of tryKeys) {
              const v = company[k as keyof typeof company];
              if (v !== undefined && v !== null && v !== '') {
                raw = v;
                break;
              }
            }
            value = raw;
            if (value != null && value !== '') {
              if (col.type === 'currency' || col.type === 'number') {
                const num = typeof value === 'number' ? value : typeof value === 'string' ? parseFloat(String(value).replace(/[$,]/g, '')) : NaN;
                displayValue = !Number.isNaN(num) ? (col.type === 'currency' ? formatCurrency(num) : String(num)) : String(value);
              } else {
                displayValue = String(value);
              }
            }
            if (value != null) source = 'api';
          }

          const docsMeta = colId === 'documents' && Array.isArray(company.documents) && company.documents.length > 0
            ? { metadata: { documents: company.documents } }
            : {};
          cells[col.id] = {
            value,
            source,
            ...(displayValue !== undefined && { displayValue }),
            ...(lastUpdated && { lastUpdated }),
            ...(sourceDocumentId && { sourceDocumentId }),
            ...(sparkline && { sparkline }),
            ...docsMeta,
          };
        });

        return {
          id: company.id,
          companyId: company.id,
          companyName: company.name,
          cells,
        };
      });

      // Preserve cells that were edited by the user or the agent — never overwrite them with stale API data.
      const prev = matrixDataRef.current;
      const prevById = prev?.rows ? new Map(prev.rows.map((r) => [r.id, r])) : new Map<string, MatrixRow>();
      const rowsWithManualPreserved: MatrixRow[] = rows.map((row) => {
        const existing = prevById.get(row.id);
        if (!existing?.cells) return row;
        const mergedCells = { ...row.cells };
        for (const [colId, cell] of Object.entries(existing.cells)) {
          if (cell?.source === 'manual' || cell?.source === 'agent') {
            mergedCells[colId] = { ...cell };
          }
        }
        return { ...row, cells: mergedCells };
      });

      const data: MatrixData = {
        columns,
        rows: rowsWithManualPreserved,
        metadata: {
          lastUpdated: new Date().toISOString(),
          dataSource: 'portfolio',
          fundId,
        },
      };

      setMatrixData(data);
      onDataChange?.(data);

      // Load NAV sparklines in background so grid stays responsive
      if (companyIds.length > 0 && fundId) {
        fetch(`/api/portfolio/${fundId}/nav-timeseries?companyIds=${companyIds.join(',')}`, { signal: controller.signal })
          .then((res) => (res.ok ? res.json() : null))
          .then((navData: Record<string, number[]> | null) => {
            if (!navData || typeof navData !== 'object') return;
            if (controller.signal.aborted) return;
            setMatrixData((prev) => {
              if (!prev?.rows?.length) return prev;
              const navMap = new Map<string, number[]>();
              Object.entries(navData).forEach(([companyId, series]: [string, unknown]) => {
                if (Array.isArray(series)) navMap.set(companyId, series);
              });
              const nextRows = prev.rows.map((row) => {
                const series = navMap.get(row.id);
                if (!series?.length || !row.cells) return row;
                const navCell = row.cells['nav'];
                if (!navCell) return row;
                return {
                  ...row,
                  cells: {
                    ...row.cells,
                    nav: { ...navCell, sparkline: series },
                  },
                };
              });
              return { ...prev, rows: nextRows };
            });
          })
          .catch((err) => {
            if (err?.name !== 'AbortError') {
              console.warn('[UnifiedMatrix] NAV sparkline fetch failed:', err);
            }
          });
      }
    } catch (err) {
      // Ignore AbortError — just means a newer request replaced this one
      if (err instanceof DOMException && err.name === 'AbortError') return;
      console.error('Error loading portfolio data:', err);
      setError(err instanceof Error ? err.message : 'Failed to load portfolio data');
    } finally {
      setIsLoading(false);
    }
  }, [fundId, mode, onDataChange, getDefaultMatrixData]);

  // Store latest loadPortfolioData in ref for event handlers
  useEffect(() => {
    loadPortfolioDataRef.current = loadPortfolioData;
  }, [loadPortfolioData]);

  // Abort in-flight portfolio fetch on unmount
  useEffect(() => () => { portfolioAbortRef.current?.abort(); }, []);

  // Load LP data for LP mode
  const loadLPData = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const { fetchLPsForMatrix } = await import('@/lib/matrix/matrix-api-service');
      const lpData = await fetchLPsForMatrix(fundId);
      if (lpData.rows.length > 0 || lpData.columns.length > 0) {
        setMatrixData(lpData);
        onDataChange?.(lpData);
      }
    } catch (err) {
      console.error('[UnifiedMatrix] Error loading LP data:', err);
      setError(err instanceof Error ? err.message : 'Failed to load LP data');
    } finally {
      setIsLoading(false);
    }
  }, [fundId, onDataChange]);

  // Load portfolio or LP data on mount or when mode/fundId changes
  useEffect(() => {
    if (mode === 'portfolio' && fundId) {
      loadPortfolioData();
    } else if (mode === 'lp') {
      loadLPData();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mode, fundId, loadPortfolioData, loadLPData]);

  // Parse @CompanyName mentions from query
  const parseCompanyMentions = (queryText: string): string[] => {
    const mentionRegex = /@([A-Za-z0-9]+(?:[A-Za-z0-9_-]*[A-Za-z0-9])?)/g;
    const mentions: string[] = [];
    let match;
    while ((match = mentionRegex.exec(queryText)) !== null) {
      mentions.push(match[1]);
    }
    return [...new Set(mentions)]; // Remove duplicates
  };

  // Handle batch company search for @CompanyName mentions
  const batchSearchAbortRef = useRef<AbortController | null>(null);
  const handleBatchCompanySearch = async (companyNames: string[]) => {
    if (!matrixData) return;

    // Abort any previous batch search polling
    batchSearchAbortRef.current?.abort();
    const controller = new AbortController();
    batchSearchAbortRef.current = controller;

    try {
      // Start batch search job
      const response = await fetch('/api/matrix/companies/search', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ companyNames }),
        signal: controller.signal,
      });

      if (!response.ok) {
        throw new Error('Failed to start batch search');
      }

      const { jobId } = await response.json();

      // Poll for results
      let completed = false;
      let attempts = 0;
      const maxAttempts = 60; // 5 minutes max (5s intervals)

      while (!completed && attempts < maxAttempts) {
        await new Promise(resolve => setTimeout(resolve, 5000)); // Poll every 5 seconds
        if (controller.signal.aborted) return;

        const statusResponse = await fetch(`/api/matrix/companies/search/${jobId}`, { signal: controller.signal });
        if (!statusResponse.ok) {
          throw new Error('Failed to check search status');
        }

        const status = await statusResponse.json();

        if (status.status === 'completed') {
          completed = true;
          // Add search results as new rows
          const newRows: MatrixRow[] = Object.entries(status.results).map(([companyName, data]: [string, any]) => {
            const companyData = data as any;
            return {
              id: `row-${Date.now()}-${Math.random().toString(36).slice(2)}`,
              companyName,
              cells: {
                company: { value: companyName, source: 'api' },
                sector: { value: companyData.sector || companyData.industry || '-', source: 'api' },
                arr: { 
                  value: companyData.arr || companyData.revenue || null, 
                  displayValue: (companyData.arr || companyData.revenue) ? formatCurrency(companyData.arr || companyData.revenue) : "-",
                  source: 'api' 
                },
                valuation: { 
                  value: companyData.valuation || companyData.latestValuation || null,
                  displayValue: (companyData.valuation || companyData.latestValuation) ? formatCurrency(companyData.valuation || companyData.latestValuation) : "-",
                  source: 'api' 
                },
                ownership: { value: 0, source: 'manual' }, // Default to 0, user can edit
              },
            };
          });

          const updatedData: MatrixData = {
            ...matrixData,
            rows: [...matrixData.rows, ...newRows],
            metadata: {
              ...matrixData.metadata,
              lastUpdated: new Date().toISOString(),
            },
          };

          setMatrixData(updatedData);
          onDataChange?.(updatedData);
        } else if (status.status === 'failed') {
          throw new Error(status.error || 'Batch search failed');
        }

        attempts++;
      }

      if (!completed) {
        throw new Error('Batch search timed out');
      }
    } catch (err) {
      if (err instanceof DOMException && err.name === 'AbortError') return;
      console.error('Error in batch company search:', err);
      setError(err instanceof Error ? err.message : 'Failed to search companies');
    }
  };

  const handleQuery = async () => {
    if (!query.trim()) return;

    setIsLoading(true);
    setError(null);

    try {
      // In custom mode, check for @CompanyName mentions and trigger batch search
      if (mode === 'custom') {
        const companyMentions = parseCompanyMentions(query);
        if (companyMentions.length > 0) {
          // Trigger batch search for mentioned companies
          await handleBatchCompanySearch(companyMentions);
          setIsLoading(false);
          return;
        }
      }

      // Use external query handler if provided
      if (onQuery) {
        const result = await onQuery(query);
        setMatrixData(result);
        onDataChange?.(result);
        // Citations should be extracted by the external handler
        // The parent (e.g. matrix control panel) will handle citation extraction
        setIsLoading(false);
        return;
      }

      // Otherwise use default query handler
      const sessionId = `matrix-${Date.now()}-${Math.random().toString(36).slice(2)}`;
      
      const response = await fetch('/api/agent/unified-brain', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          prompt: query,
          outputFormat: 'matrix',
          sessionId,
          context: {
            requireStructuredData: true,
            generateFormulas: true,
            fundId,
          },
          stream: false,
        }),
      });

      if (!response.ok) {
        throw new Error(`Request failed: ${response.status}`);
      }

      const data = await response.json();
      
      // Treat result as the matrix payload when present (unified-brain returns { result: { format, columns, rows, ... } })
      const matrixPayload = data.result?.format === 'matrix' ? data.result : data.matrix;
      const citationsList = matrixPayload?.citations ?? data.citations ?? [];

      // Extract citations from response
      const extractedCitations: Citation[] = (citationsList || []).map((cite: any, idx: number) => ({
        id: cite.id || idx + 1,
        number: idx + 1,
        source: cite.source || cite.title || 'Source',
        date: cite.date || new Date().toISOString().split('T')[0],
        title: cite.title || cite.source || 'Citation',
        content: cite.content || cite.snippet || '',
        url: cite.url || cite.link,
        metadata: cite.metadata || {},
      }));
      
      setCitations(extractedCitations);
      onCitationsChange?.(extractedCitations);
      
      if (data.success && matrixPayload?.columns && matrixPayload?.rows) {
        // Transform the response into our matrix format (same shape as matrix-api-service for AG grid)
        const rowData = (matrixPayload.rows || []).map((row: any, idx: number) => {
          const cells: Record<string, MatrixCell> = {};
          const cellSource = row.cells ?? row;
          Object.keys(cellSource).forEach((key) => {
            if (key === 'id') return;
            const cellData = cellSource[key];
            if (cellData && typeof cellData === 'object' && !Array.isArray(cellData) && 'value' in cellData) {
              cells[key] = cellData;
            } else {
              cells[key] = {
                value: cellData,
                displayValue: undefined,
                source: 'api',
              };
            }
          });
          return {
            id: row.id || `row-${idx}`,
            cells,
            ...row,
          };
        });
        const transformedData: MatrixData = {
          columns: matrixPayload.columns || [],
          rows: rowData,
          formulas: matrixPayload.formulas || {},
          metadata: {
            ...matrixPayload.metadata,
            lastUpdated: new Date().toISOString(),
            dataSource: 'query',
            query,
            fundId,
            charts: matrixPayload.charts || [],
          },
        };

        setMatrixData(transformedData);
        onDataChange?.(transformedData);
      } else {
        throw new Error(data.error || 'Failed to generate matrix');
      }
    } catch (err) {
      console.error('Error executing query:', err);
      setError(err instanceof Error ? err.message : 'Failed to execute query');
    } finally {
      setIsLoading(false);
    }
  };

  /**
   * Preset company fields from database into grid row.
   * Never overwrite a cell that was edited by the user or the agent.
   */
  const presetCompanyFields = (row: MatrixRow, companyData: any): MatrixRow => {
    const updatedCells = { ...row.cells };
    const isProtected = (colId: string) => {
      const src = updatedCells[colId]?.source;
      return src === 'manual' || src === 'agent';
    };

    if (companyData.name && !isProtected('company')) {
      updatedCells['company'] = {
        value: companyData.name,
        displayValue: companyData.name,
        source: 'api',
      };
    }
    if (companyData.sector && !isProtected('sector')) {
      updatedCells['sector'] = {
        value: companyData.sector,
        displayValue: companyData.sector,
        source: 'api',
      };
    }
    if (companyData.current_arr_usd !== undefined && !isProtected('arr')) {
      updatedCells['arr'] = {
        value: companyData.current_arr_usd,
        displayValue: formatCurrency(companyData.current_arr_usd),
        source: 'api',
      };
    }
    if (companyData.total_invested_usd !== undefined && !isProtected('invested')) {
      updatedCells['invested'] = {
        value: companyData.total_invested_usd,
        displayValue: formatCurrency(companyData.total_invested_usd),
        source: 'api',
      };
    }
    if (companyData.ownership_percentage !== undefined && !isProtected('ownership')) {
      updatedCells['ownership'] = {
        value: companyData.ownership_percentage,
        displayValue: `${companyData.ownership_percentage.toFixed(1)}%`,
        source: 'api',
      };
    }
    if (companyData.burn_rate_monthly_usd !== undefined && !isProtected('burnRate')) {
      updatedCells['burnRate'] = {
        value: companyData.burn_rate_monthly_usd,
        displayValue: formatCurrency(companyData.burn_rate_monthly_usd),
        source: 'api',
      };
    }
    if (companyData.runway_months !== undefined && !isProtected('runway')) {
      updatedCells['runway'] = {
        value: companyData.runway_months,
        displayValue: `${companyData.runway_months}m`,
        source: 'api',
      };
    }
    if (companyData.gross_margin !== undefined && !isProtected('grossMargin')) {
      updatedCells['grossMargin'] = {
        value: companyData.gross_margin,
        displayValue: `${(companyData.gross_margin * 100).toFixed(1)}%`,
        source: 'api',
      };
    }
    if (companyData.cash_in_bank_usd !== undefined && !isProtected('cashInBank')) {
      updatedCells['cashInBank'] = {
        value: companyData.cash_in_bank_usd,
        displayValue: formatCurrency(companyData.cash_in_bank_usd),
        source: 'api',
      };
    }

    return {
      ...row,
      cells: updatedCells,
      companyId: companyData.id,
      companyName: companyData.name,
    };
  };

  /**
   * Detect if a cell value is a natural language query (not a formula or number)
   */
  const isNaturalLanguageQuery = (value: any): boolean => {
    if (typeof value !== 'string') return false;
    const str = value.trim();
    if (!str) return false;
    
    // Not a formula (doesn't start with =)
    if (str.startsWith('=')) return false;
    
    // Not a pure number
    if (/^-?\d+\.?\d*$/.test(str)) return false;
    
    // Not a currency format
    if (/^\$[\d,]+\.?\d*[KMkm]?$/.test(str)) return false;
    
    // Looks like natural language (has spaces, multiple words, or question words)
    const hasSpaces = str.includes(' ');
    const hasQuestionWords = /^(what|how|when|where|why|show|find|calculate|compare|analyze)/i.test(str);
    const hasMultipleWords = str.split(/\s+/).length >= 2;
    
    return hasSpaces || hasQuestionWords || hasMultipleWords;
  };

  const handleCellEdit = async (
    rowId: string,
    columnId: string,
    newValue: any,
    options?: { sourceDocumentId?: string | number; data_source?: string; metadata?: { fromChat?: boolean; auto_applied?: boolean; [key: string]: unknown } }
  ) => {
    const currentData = matrixData || getDefaultMatrixData(mode, fundId);
    if (!currentData) return;

    const row = currentData.rows.find((r) => r.id === rowId);
    if (!row) return;

    const column = currentData.columns.find((c) => c.id === columnId);
    // Agent-initiated edits (from chat) bypass editable check; user edits respect it
    const isAgentEdit = options?.metadata?.fromChat || options?.data_source === 'agent';
    if (!column || (!column.editable && !isAgentEdit)) return;

    const formulaStr = typeof newValue === 'string' ? newValue.trim() : '';
    
    // Check for natural language query mode
    if (isNaturalLanguageQuery(newValue)) {
      try {
        setIsLoading(true);
        setError(null);
        
        // Route to unified-brain API for natural language query
        const sessionId = `cell-query-${Date.now()}-${Math.random().toString(36).slice(2)}`;
        const response = await fetch('/api/agent/unified-brain', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            prompt: formulaStr,
            outputFormat: 'cell', // Request cell-level response
            sessionId,
            context: {
              rowId,
              columnId,
              companyId: row.companyId,
              fundId,
              requireStructuredData: false, // Allow flexible responses
            },
            stream: false,
          }),
        });

        if (!response.ok) {
          throw new Error(`Query failed: ${response.status}`);
        }

        const data = await response.json();
        
        // Extract the result value
        const resultValue = data.value ?? data.result ?? data.answer ?? formulaStr;
        const displayValue = typeof resultValue === 'number' 
          ? resultValue.toLocaleString(undefined, { maximumFractionDigits: 2 })
          : String(resultValue);
        
        // Update cell with result, preserving original query in metadata
        const updatedRows = currentData.rows.map((r) => {
          if (r.id === rowId) {
            return {
              ...r,
              cells: {
                ...r.cells,
                [columnId]: {
                  ...r.cells[columnId],
                  value: resultValue,
                  displayValue,
                  source: 'api' as const,
                  lastUpdated: new Date().toISOString(),
                  metadata: {
                    ...r.cells[columnId]?.metadata,
                    query: formulaStr,
                    query_result: true,
                    citations: data.citations,
                  },
                },
              },
            };
          }
          return r;
        });

        const updatedData: MatrixData = {
          ...currentData,
          rows: updatedRows,
        };

        setMatrixData(updatedData);
        onDataChange?.(updatedData);
        
        if (onCellEdit) {
          await onCellEdit(rowId, columnId, resultValue);
        }
      } catch (err) {
        console.error('Error executing cell query:', err);
        toast.error(err instanceof Error ? err.message : 'Failed to execute query');
      } finally {
        setIsLoading(false);
      }
      return;
    }
    
    const parsed = formulaStr && formulaStr.toUpperCase().startsWith('=WORKFLOW') ? parseWorkflowFormula(formulaStr) : null;

    if (parsed) {
      // Allow empty actionIds initially - show validation error if empty when executing
      if (parsed.actionIds.length === 0) {
        setError('Workflow formula must include at least one action ID. Example: =WORKFLOW("action1,action2", "all")');
        return;
      }
      
      try {
        const wf: WorkflowRunResult = await runWorkflow({
          actionIds: parsed.actionIds,
          target: parsed.target,
          triggerRowId: rowId,
          triggerColumnId: columnId,
          matrixData: currentData,
          selectedRowIds: parsed.target === 'selected' ? Array.from(selectedRows) : undefined,
          fundId,
          mode,
        });
        let data = currentData;
        for (const { rowId: rId, columnId: cId, response } of wf.results) {
          data = applySingleActionResult(data, rId, cId, response);
        }
        const summary = wf.success
          ? `Ran ${wf.processedCount} action${wf.processedCount !== 1 ? 's' : ''}`
          : `Error: ${wf.error ?? 'unknown'}`;
        const summaryRow = data.rows.find((r) => r.id === rowId);
        if (summaryRow) {
          const cells = { ...summaryRow.cells };
          cells[columnId] = {
            ...cells[columnId],
            value: summary,
            displayValue: summary,
            formula: formulaStr,
            source: 'api',
            lastUpdated: new Date().toISOString(),
            metadata: { ...cells[columnId]?.metadata, workflow_ran: wf.processedCount > 0 },
          };
          const updatedRows = data.rows.map((r) =>
            r.id === rowId ? { ...r, cells } : r
          );
          data = { ...data, rows: updatedRows };
        }
        setMatrixData(data);
        onDataChange?.(data);

        // Persist each workflow result to the database (mirrors handleCellActionResult)
        if (onCellEdit) {
          for (const { rowId: rId, columnId: cId, response } of wf.results) {
            if (!response.success) continue;
            const value = extractCellValue(response) ?? response.value;
            try {
              await onCellEdit(rId, cId, value, {
                data_source: 'service',
                metadata: {
                  ...(response.metadata ? { explanation: response.metadata.explanation, citations: response.metadata.citations, service_name: response.action_id } : {}),
                },
              });
            } catch (err) {
              console.warn(`Workflow result persist failed for ${rId}/${cId}:`, err);
            }
          }
          // Also persist the summary cell
          try {
            await onCellEdit(rowId, columnId, summary, {
              data_source: 'service',
              metadata: { workflow_ran: wf.processedCount > 0 },
            });
          } catch (err) {
            console.warn('Workflow summary persist failed:', err);
          }
        }
      } catch (err) {
        const msg = err instanceof Error ? err.message : String(err);
        toast.error(`Workflow failed: ${msg}`);
      }
      return;
    }

    // Coerce to primitive so we never store [object Object] or blank from objects
    let valueToStore: string | number | boolean | null = newValue;
    if (valueToStore != null && typeof valueToStore === 'object' && !Array.isArray(valueToStore) && !(valueToStore as object instanceof Date)) {
      const obj = valueToStore as Record<string, unknown>;
      const extracted = obj.value ?? obj.displayValue ?? obj.display_value ?? obj.fair_value ?? '';
      valueToStore = (typeof extracted === 'string' || typeof extracted === 'number' || typeof extracted === 'boolean' ? extracted : '') as string | number | boolean | null;
      if (typeof valueToStore === 'object') valueToStore = '';
    }
    if (column.type === 'currency' || column.type === 'number') {
      const n = typeof valueToStore === 'string' ? parseFloat(String(valueToStore).replace(/[^0-9.-]/g, '')) : Number(valueToStore);
      valueToStore = !isNaN(n) ? n : (column.type === 'currency' ? 0 : valueToStore);
    } else if (column.type === 'percentage' && typeof valueToStore !== 'number') {
      const n = parseFloat(String(valueToStore));
      valueToStore = !isNaN(n) ? (n > 1 ? n / 100 : n) : 0;
    }

    // Normal cell edit — use valueToStore so display and callbacks never see [object Object]
    // When editing company name column, keep row.companyName in sync so tooltips/tree/display stay correct
    const isCompanyNameColumn = columnId === 'company' || columnId === 'companyName';
    // Never persist an id-like value as company name (fixes "companyb16366363" bug)
    const looksLikeId = (v: unknown): boolean => {
      if (v == null) return false;
      const s = String(v).trim();
      return /^company[a-z0-9]+$/i.test(s) || /^[a-f0-9-]{36}$/i.test(s) || /^[0-9a-f]{8}-[0-9a-f]{4}/i.test(s);
    };
    if (isCompanyNameColumn && valueToStore != null && valueToStore !== '' && looksLikeId(valueToStore)) {
      toast.error('Enter a real company name, not an ID');
      return;
    }
    const cellSource = (options as { sourceDocumentId?: string | number; data_source?: string; metadata?: { fromChat?: boolean } })?.metadata?.fromChat
      ? ('agent' as const)
      : (options as { sourceDocumentId?: string | number })?.sourceDocumentId != null
        ? ('document' as const)
        : ('manual' as const);
    const updatedRows = currentData.rows.map((r) => {
      if (r.id === rowId) {
        const updatedRow = {
          ...r,
          cells: {
            ...r.cells,
            [columnId]: {
              ...r.cells[columnId],
              value: valueToStore,
              displayValue: formatCellValue(valueToStore, column.type),
              source: cellSource,
              lastUpdated: new Date().toISOString(),
            },
          },
        };
        if (isCompanyNameColumn && valueToStore != null && valueToStore !== '') {
          (updatedRow as MatrixRow).companyName = String(valueToStore);
        }
        return updatedRow;
      }
      return r;
    });

    const updatedData: MatrixData = {
      ...currentData,
      rows: updatedRows,
    };

    setMatrixData(updatedData);
    onDataChange?.(updatedData);

    editInFlightRef.current++;
    try {
      if (onCellEdit) {
        try {
          const cellEditOptions = buildCellEditOptionsFromSuggestion(options?.sourceDocumentId);
          await onCellEdit(rowId, columnId, valueToStore, cellEditOptions);
        } catch (err) {
          console.error('Error saving cell edit:', err);
          toast.error(err instanceof Error ? err.message : 'Failed to save edit');
        }
      } else if (row.companyId) {
        try {
          await saveCellEditToCompany(row.companyId, columnId, valueToStore, fundId, {
            ...(options?.sourceDocumentId != null ? { sourceDocumentId: options.sourceDocumentId } : {}),
          });
        } catch (err) {
          console.error('Error saving to company:', err);
          toast.error(err instanceof Error ? err.message : 'Failed to save edit');
        }
      } else {
        toast.info('Add to portfolio to save edits');
      }
    } finally {
      editInFlightRef.current--;
    }
  };

  function applySingleActionResult(
    data: MatrixData,
    rowId: string,
    columnId: string,
    response: ActionExecutionResponse
  ): MatrixData {
    if (!response.success) return data;
    const row = data.rows.find((r) => r.id === rowId);
    const column = data.columns.find((c) => c.id === columnId);
    if (!row || !column) return data;

    const value = extractCellValue(response) ?? response.value;
    const displayValue = formatActionOutput(response, column.type);
    const explanation = extractExplanation(response);
    const meta = response.metadata ?? {};
    const chartConfig = normalizeChartConfig(meta);
    const metadata: MatrixCell['metadata'] = {
      ...row.cells[columnId]?.metadata,
      method: meta.method,
      explanation: meta.explanation ?? (explanation || undefined),
      confidence: meta.confidence,
      output_type: meta.output_type,
      time_series: meta.time_series,
      chart_config: chartConfig || undefined,
      raw_output: meta.raw_output,
      citations: meta.citations,
      ...(meta.documents != null || row.cells[columnId]?.metadata?.documents != null
        ? { documents: meta.documents ?? row.cells[columnId]?.metadata?.documents }
        : {}),
    };

    let sparkline = row.cells[columnId]?.sparkline;
    if (meta.time_series && Array.isArray(meta.time_series) && (column.type === 'sparkline' || column.id === 'nav')) {
      sparkline = meta.time_series.map((item) => {
        if (typeof item === 'number') return item;
        if (typeof item === 'object' && item !== null) {
          return item.revenue || item.value || item.nav || item.amount || 0;
        }
        return 0;
      }).filter((v) => typeof v === 'number' && !isNaN(v));
    }

    let updatedColumns = data.columns;
    const columnsToCreate = meta.output_type === 'multi_column' && Array.isArray(meta.columns_to_create)
      ? meta.columns_to_create
      : [];

    // Use helper function to create columns
    if (columnsToCreate.length > 0) {
      updatedColumns = createColumnsFromMetadata(
        columnsToCreate as ColumnDefinition[],
        data.columns,
        columnId
      );
    }

    // Update rows: first update the trigger cell, then populate new column cells
    let updatedRows = data.rows.map((r) => {
      const cells: Record<string, MatrixCell> = { ...r.cells };
      if (r.id === rowId) {
        cells[columnId] = {
          ...r.cells[columnId],
          value,
          displayValue,
          sparkline: sparkline !== undefined ? sparkline : r.cells[columnId]?.sparkline,
          source: 'api' as const,
          lastUpdated: new Date().toISOString(),
          metadata,
        };
      }
      return { ...r, cells };
    });

    // Use helper function to populate new column cells
    if (columnsToCreate.length > 0) {
      updatedRows = populateCellsForNewColumns(
        updatedRows,
        columnsToCreate as ColumnDefinition[],
        { rowId, columnId, actionId: response.action_id }
      );
    }

    return { ...data, columns: updatedColumns, rows: updatedRows };
  }

  const handleCellActionResult = async (
    rowId: string,
    columnId: string,
    response: ActionExecutionResponse
  ) => {
    const key = `${rowId}_${columnId}`;
    if (!response.success) {
      setCellActionStatus((prev) => ({ ...prev, [key]: { state: 'error', message: response.error ?? 'Action failed' } }));
      setTimeout(() => setCellActionStatus((p) => { const next = { ...p }; delete next[key]; return next; }), 6000);
      return;
    }
    if (!matrixData) return;
    const value = extractCellValue(response) ?? response.value;
    const row = matrixData.rows.find((r) => r.id === rowId || r.companyId === rowId || (r.companyName && r.companyName.toLowerCase() === rowId.toLowerCase()));
    const companyId = row?.companyId ?? row?.id ?? rowId;

    if (suggestBeforeApply && fundId) {
      const result = await addServiceSuggestion({
        fundId,
        company_id: companyId,
        column_id: columnId,
        suggested_value: value,
        source_service: response.action_id,
        reasoning: (response.metadata as Record<string, unknown>|undefined)?.explanation as string | undefined,
        metadata: response.metadata ? { explanation: response.metadata.explanation, citations: response.metadata.citations } : undefined,
      });
      setCellActionStatus((prev) => ({ ...prev, [key]: { state: 'success', message: 'Suggestion added' } }));
      setTimeout(() => setCellActionStatus((p) => { const next = { ...p }; delete next[key]; return next; }), 3000);
      if (result.success) {
        await refreshSuggestions();
        toast.success('Suggestion added — review in chat');
      } else {
        toast.error(result.error ?? 'Failed to add suggestion');
      }
      onServiceResultLog?.(rowId, columnId, response);
      return;
    }

    const updatedData = applySingleActionResult(matrixData, rowId, columnId, response);
    setMatrixData(updatedData);
    onDataChange?.(updatedData);
    setCellActionStatus((prev) => ({ ...prev, [key]: { state: 'success', message: 'Done' } }));
    setTimeout(() => setCellActionStatus((p) => { const next = { ...p }; delete next[key]; return next; }), 3000);
    if (columnId === 'documents') {
      refreshSuggestions();
    }
    if (onCellEdit) {
      try {
        const cellDocs = matrixData?.rows.find((r) => r.id === rowId)?.cells?.[columnId]?.metadata?.documents;
        const documents = (response.metadata as Record<string, unknown>|undefined)?.documents ?? cellDocs;
        await onCellEdit(rowId, columnId, value, {
          data_source: 'service',
          metadata: {
            ...(response.metadata ? { explanation: response.metadata.explanation, citations: response.metadata.citations, service_name: response.action_id } : {}),
            ...(documents != null ? { documents } : {}),
          },
        });
      } catch (err) {
        console.warn('Cell action result persist (onCellEdit) failed:', err);
        toast.error(err instanceof Error ? err.message : 'Failed to save edit');
      }
    }
    onServiceResultLog?.(rowId, columnId, response);
  };

  /** Guard: prevents refreshCells during cell action execution. */
  const actionInProgressRef = useRef(false);

  /** Single run path for any service: execute → add suggestion → refresh + toast. Grid persistence happens on accept.
   *  When isBulk=true, suppresses individual toasts/refreshes — caller handles summary.
   *  When autoApply=true (agent enrichment), apply result directly instead of creating a suggestion. */
  const runActionWrapper = useCallback(
    async (actionId: string, rowId: string, columnId: string, isBulk = false, autoApply = false) => {
      const data = matrixData ?? getDefaultMatrixData(mode, fundId);
      const row = data.rows.find((r) => r.id === rowId || r.companyId === rowId || (r.companyName && r.companyName.toLowerCase() === rowId.toLowerCase()));
      const companyId = row?.companyId ?? row?.id ?? rowId;
      const inputs = buildActionInputs(actionId, row ?? { id: rowId, companyId, companyName: '', cells: {} }, columnId, data);
      onToolCallLog?.({
        action_id: actionId,
        row_id: rowId,
        column_id: columnId,
        status: 'running',
        companyName: row?.companyName,
      });
      try {
        const response = await executeAction({
          action_id: actionId,
          row_id: rowId,
          column_id: columnId,
          inputs,
          mode,
          fund_id: fundId,
          company_id: companyId,
        });
        onToolCallLog?.({
          action_id: actionId,
          row_id: rowId,
          column_id: columnId,
          status: response.success ? 'success' : 'error',
          error: response.error,
          companyName: row?.companyName,
          explanation: response.metadata?.explanation as string | undefined,
          reasoning: response.metadata?.reasoning as string | undefined,
        });
        if (!response.success) {
          if (!isBulk) toast.error(response.error ?? 'Action failed');
          return;
        }
        const value = extractCellValue(response);

        // Agent enrichment: apply directly to grid, skip suggestion queue
        if (autoApply) {
          await handleCellEdit(rowId, columnId, value, {
            data_source: actionId,
            metadata: { fromChat: true, auto_applied: true, ...(response.metadata || {}) },
          });
          onServiceResultLog?.(rowId, columnId, response);
          return;
        }

        // Normal path: persist as suggestion for user review
        const activeFundId = fundId!;
        const { success, error } = await addServiceSuggestion({
          fundId: activeFundId,
          company_id: companyId,
          column_id: columnId,
          suggested_value: value,
          source_service: actionId,
          reasoning: (response.metadata as Record<string, unknown>|undefined)?.reasoning as string
            ?? (response.metadata as Record<string, unknown>|undefined)?.explanation as string
            ?? undefined,
          metadata: response.metadata
            ? {
                explanation: response.metadata.explanation,
                reasoning: response.metadata.reasoning,
                method: response.metadata.method,
                confidence: response.metadata.confidence,
                citations: response.metadata.citations,
                output_type: response.metadata.output_type,
              }
            : undefined,
        });
        if (success) {
          if (!isBulk) {
            await refreshSuggestions();
            toast.success('Suggestion added — review in chat');
            window.dispatchEvent(new CustomEvent('refreshSuggestionsAndOpenViewport'));
          }
        } else {
          console.error('[runActionWrapper] Suggestion persistence failed:', { actionId, companyId, columnId, error });
          if (!isBulk) toast.error(error ?? 'Failed to add suggestion');
        }
        onServiceResultLog?.(rowId, columnId, response);
      } catch (err) {
        const msg = err instanceof Error ? err.message : 'Action failed';
        onToolCallLog?.({
          action_id: actionId,
          row_id: rowId,
          column_id: columnId,
          status: 'error',
          error: msg,
          companyName: row?.companyName,
        });
        toast.error(msg);
      }
    },
    [matrixData, mode, fundId, getDefaultMatrixData, onToolCallLog, onServiceResultLog, refreshSuggestions, handleCellEdit]
  );

  /** Run cell action from parent (POST survives cell unmount). When suggestBeforeApply + fundId, route through runActionWrapper for grid persistence. */
  const onRunCellAction = useCallback(
    async (request: ActionExecutionRequest) => {
      if (suggestBeforeApply && fundId) {
        await runActionWrapper(request.action_id, request.row_id, request.column_id);
        return;
      }
      actionInProgressRef.current = true;
      const key = `${request.row_id}_${request.column_id}`;
      setCellActionStatus((prev) => ({ ...prev, [key]: { state: 'loading', message: 'Running...' } }));
      const companyName = matrixData?.rows.find((r) => r.id === request.row_id)?.companyName;
      onToolCallLog?.({
        action_id: request.action_id,
        row_id: request.row_id,
        column_id: request.column_id,
        status: 'running',
        companyName,
      });
      if (typeof window !== 'undefined') {
        console.log('[cell-action] POST', request.action_id, request.row_id, request.column_id);
      }
      try {
        const response = await executeAction(request);
        onToolCallLog?.({
          action_id: request.action_id,
          row_id: request.row_id,
          column_id: request.column_id,
          status: response.success ? 'success' : 'error',
          error: response.error,
          companyName,
          explanation: response.metadata?.explanation as string | undefined,
          reasoning: response.metadata?.reasoning as string | undefined,
        });
        await handleCellActionResult(request.row_id, request.column_id, response);
      } catch (err) {
        const msg = err instanceof Error ? err.message : 'Action failed';
        onToolCallLog?.({
          action_id: request.action_id,
          row_id: request.row_id,
          column_id: request.column_id,
          status: 'error',
          error: msg,
          companyName,
        });
        setCellActionStatus((prev) => ({ ...prev, [key]: { state: 'error', message: msg } }));
        setTimeout(() => setCellActionStatus((p) => { const next = { ...p }; delete next[key]; return next; }), 6000);
        throw err;
      } finally {
        actionInProgressRef.current = false;
      }
    },
    [suggestBeforeApply, fundId, runActionWrapper, handleCellActionResult, matrixData?.rows, onToolCallLog]
  );

  /** Grid commands from chat/backend: route through accept/reject when suggestBeforeApply, else apply directly.
   *  Supports edit, run, add_document with group-based execution ordering.
   *  Performance: Pre-computes row lookup map and batches edit commands in parallel (up to 8 concurrent).
   *  Edit commands can carry source_service, reasoning, confidence, and metadata from backend enrichment.
   *
   *  Workflow chaining: commands carry a `group` field (0=edits, 1+=run services).
   *  Groups execute sequentially; within a group, same-action commands run in parallel.
   *  Run results from group N are passed as workflow context to group N+1 for the same row. */
  const handleGridCommandsFromBackend = useCallback(
    async (commands: Array<{ action: 'edit' | 'run' | 'add_document' | 'add_row' | 'delete'; rowId?: string; columnId?: string; value?: unknown; actionId?: string; group?: number; depends_on?: string[]; provides?: string; source_service?: string; reasoning?: string; confidence?: number; metadata?: Record<string, unknown>; auto_apply?: boolean; companyName?: string; company_id?: string; cellValues?: Record<string, unknown> }>) => {
      // Pre-compute row lookup map: O(n) instead of O(n*m) per-command finds
      // Index by id, companyId, AND companyName (backend grid_commands often use name as rowId)
      const rowMap = new Map<string, typeof matrixData extends { rows: (infer R)[] } ? R : any>();
      for (const r of (matrixData?.rows || [])) {
        if (r.id) rowMap.set(r.id, r);
        if (r.companyId && r.companyId !== r.id) rowMap.set(r.companyId, r);
        if (r.companyName) {
          rowMap.set(r.companyName, r);
          rowMap.set(r.companyName.toLowerCase(), r);
        }
      }
      const findRow = (rowId?: string) => {
        if (!rowId) return null;
        return rowMap.get(rowId) ?? rowMap.get(rowId.toLowerCase()) ?? null;
      };

      // --- Group commands by execution group ---
      // Group 0 = edits + add_document (parallel batches)
      // Group 1+ = run services (sequential groups, parallel within group per row)
      const groupMap = new Map<number, typeof commands>();
      for (const cmd of commands) {
        const g = cmd.group ?? (cmd.action === 'run' ? 1 : 0);
        if (!groupMap.has(g)) groupMap.set(g, []);
        groupMap.get(g)!.push(cmd);
      }
      const sortedGroups = [...groupMap.keys()].sort((a, b) => a - b);

      // Helper: execute a single edit command.
      // When suggestBeforeApply + fundId, persist as suggestion so user can accept/reject.
      // When auto_apply=true (agent enrichment), bypass suggestion queue and apply directly.
      // Otherwise, apply directly to the grid.
      const execEdit = async (cmd: typeof commands[0]) => {
        const isDocumentsColumn = cmd.columnId === 'documents';
        const serviceSource = cmd.source_service || 'agent';
        const editMetadata = isDocumentsColumn && Array.isArray(cmd.value) ? { fromChat: true, documents: cmd.value } : { fromChat: true, ...(cmd.metadata || {}) };

        // Agent enrichment commands bypass suggestion queue entirely
        if (cmd.auto_apply) {
          await handleCellEdit(cmd.rowId!, cmd.columnId!, cmd.value, { data_source: serviceSource, metadata: editMetadata });
          return;
        }

        if (suggestBeforeApply && fundId) {
          const row = findRow(cmd.rowId);
          // MUST use the DB-level companyId (UUID), not company name — accept API looks up by companies.id
          const companyId = row?.companyId ?? row?.id;
          if (!companyId) {
            console.warn('[grid-cmd] Cannot persist suggestion: no companyId found for rowId', cmd.rowId);
            // Fallback: apply directly to grid to avoid silent data loss
            await handleCellEdit(cmd.rowId!, cmd.columnId!, cmd.value, { data_source: serviceSource, metadata: editMetadata });
            return;
          }
          const result = await addServiceSuggestion({
            fundId,
            company_id: companyId,
            column_id: cmd.columnId!,
            suggested_value: cmd.value,
            source_service: serviceSource,
            reasoning: cmd.reasoning,
            metadata: { fromChat: true, ...(cmd.metadata || {}) },
          });
          if (!result.success) {
            console.error('[grid-cmd] Edit suggestion persistence failed:', result.error);
          }
        } else {
          await handleCellEdit(cmd.rowId!, cmd.columnId!, cmd.value, { data_source: serviceSource, metadata: editMetadata });
        }
      };

      // Helper: execute a single add_document command — always persists as suggestion when fundId is set
      const execDoc = async (cmd: typeof commands[0]) => {
        const row = findRow(cmd.rowId);
        const companyId = row?.companyId ?? row?.id ?? cmd.rowId;
        const documentsCol = row?.cells?.['documents'];
        const existingDocs = Array.isArray(documentsCol?.value) ? documentsCol.value as Array<{ id?: string; name?: string }> : [];
        const newDoc = typeof cmd.value === 'object' && cmd.value !== null && !Array.isArray(cmd.value)
          ? cmd.value as { id: string; name?: string }
          : { id: String(cmd.value), name: 'Document' };
        const newList = [...existingDocs, newDoc];
        if (fundId) {
          const result = await addServiceSuggestion({
            fundId,
            company_id: companyId!,
            column_id: 'documents',
            suggested_value: newList,
            source_service: cmd.source_service || 'agent',
            reasoning: cmd.reasoning,
            metadata: { fromChat: true, documents: newList, ...(cmd.metadata || {}) },
          });
          if (!result.success) {
            console.error('[grid-cmd] Document suggestion persistence failed:', result.error);
          }
        }
        if (!suggestBeforeApply || !fundId) {
          await handleCellEdit(cmd.rowId!, 'documents', newList, { data_source: cmd.source_service || 'agent', metadata: { fromChat: true, documents: newList } as Record<string, unknown> });
        }
      };

      // Workflow context: accumulates run results per row across groups for chaining
      const workflowResults = new Map<string, Record<string, any>>();
      let totalEdits = 0;
      let bulkSuccessCount = 0;
      let bulkFailCount = 0;

      // Execute groups sequentially — within each group, batch for throughput
      for (const groupNum of sortedGroups) {
        const groupCmds = groupMap.get(groupNum)!;

        // Separate by type within group
        const edits: typeof commands = [];
        const docs: typeof commands = [];
        const runs: typeof commands = [];
        const addRows: typeof commands = [];
        const deletes: typeof commands = [];
        for (const cmd of groupCmds) {
          if (cmd.action === 'add_row' && cmd.companyName) {
            addRows.push(cmd);
          } else if (cmd.action === 'delete' && (cmd.rowId || cmd.company_id)) {
            deletes.push(cmd);
          } else if (cmd.action === 'add_document' && cmd.rowId && (cmd.columnId === 'documents' || !cmd.columnId) && cmd.value != null) {
            docs.push(cmd);
          } else if (cmd.action === 'edit' && cmd.rowId && cmd.columnId && cmd.value !== undefined) {
            edits.push(cmd);
          } else if (cmd.action === 'run' && cmd.rowId && cmd.columnId && cmd.actionId) {
            runs.push(cmd);
          }
        }

        // Handle add_row commands — create company + add to grid with pre-populated cells
        for (const cmd of addRows) {
          try {
            const cellVals = (cmd.cellValues || {}) as Record<string, any>;
            const newCompany = await createCompanyForMatrix({
              name: cmd.companyName!,
              fundId: mode === 'portfolio' ? fundId : undefined,
              mode,
              companyFields: {
                investmentAmount: 1,
                sector: cellVals.sector || '',
                stage: cellVals.stage || '',
                ownershipPercentage: 0,
                currentArr: cellVals.arr || 0,
                valuation: cellVals.valuation || 0,
              },
            });

            const currentData = matrixData || getDefaultMatrixData(mode, fundId);
            const columns = canonicalizeMatrixColumns(currentData.columns.length > 0 ? currentData.columns : getDefaultMatrixData(mode, fundId).columns);

            setMatrixData((prev) => {
              const data = prev || getDefaultMatrixData(mode, fundId);
              const newRow: MatrixRow = {
                id: newCompany.id,
                companyId: newCompany.id,
                companyName: newCompany.companyName ?? cmd.companyName!,
                cells: columns.reduce(
                  (acc, col) => {
                    const prePopulated = cellVals[col.id];
                    acc[col.id] = { value: prePopulated ?? null, source: prePopulated != null ? 'agent' as const : 'manual' as const };
                    return acc;
                  },
                  {} as Record<string, MatrixCell>
                ),
              };
              return {
                ...data,
                columns,
                rows: [...(data.rows || []), newRow],
                metadata: { ...data.metadata, lastUpdated: new Date().toISOString() },
              };
            });
            console.log(`[grid-cmd] add_row: Added '${cmd.companyName}' (id=${newCompany.id})`);
          } catch (err) {
            console.error(`[grid-cmd] add_row failed for '${cmd.companyName}':`, err);
          }
        }

        // Handle delete commands — remove row from grid
        for (const cmd of deletes) {
          const targetId = cmd.rowId || cmd.company_id;
          const row = findRow(targetId);
          const resolvedId = row?.id || row?.companyId || targetId;
          if (resolvedId) {
            setMatrixData((prev) => {
              if (!prev) return prev;
              return {
                ...prev,
                rows: prev.rows.filter(r => r.id !== resolvedId && r.companyId !== resolvedId),
                metadata: { ...prev.metadata, lastUpdated: new Date().toISOString() },
              };
            });
            console.log(`[grid-cmd] delete: Removed row '${cmd.companyName || resolvedId}'`);
          }
        }

        // Execute edits + docs in parallel batches of 8
        const allEdits = [...docs.map(c => () => execDoc(c)), ...edits.map(c => () => execEdit(c))];
        const BATCH_SIZE = 8;
        for (let i = 0; i < allEdits.length; i += BATCH_SIZE) {
          await Promise.all(allEdits.slice(i, i + BATCH_SIZE).map(fn => fn()));
        }
        totalEdits += allEdits.length;

        // Refresh after edits in this group land (so run services see fresh data)
        if (fundId && allEdits.length > 0) {
          await refreshSuggestions();
        }

        // Execute run commands — pass workflow context from previous groups
        const isBulk = runs.length > 1;
        for (const cmd of runs) {
          try {
            // Inject workflow context from previous run results for this row
            const rowCtx = workflowResults.get(cmd.rowId!) || {};
            if (Object.keys(rowCtx).length > 0 && cmd.metadata) {
              cmd.metadata._workflow_context = rowCtx;
            } else if (Object.keys(rowCtx).length > 0) {
              (cmd as any).metadata = { _workflow_context: rowCtx };
            }
            await runActionWrapper(cmd.actionId!, cmd.rowId!, cmd.columnId!, isBulk, cmd.auto_apply === true);
            bulkSuccessCount++;
            // Store result reference so next group can chain from it
            if (!workflowResults.has(cmd.rowId!)) workflowResults.set(cmd.rowId!, {});
            workflowResults.get(cmd.rowId!)![cmd.actionId!] = { success: true, group: groupNum };
          } catch {
            bulkFailCount++;
            if (!workflowResults.has(cmd.rowId!)) workflowResults.set(cmd.rowId!, {});
            workflowResults.get(cmd.rowId!)![cmd.actionId!] = { success: false, group: groupNum };
          }
        }
      }

      // Single refresh + summary toast at the end
      const hasAutoApply = commands.some(c => c.auto_apply);
      if (fundId && totalEdits > 0 && bulkSuccessCount === 0) {
        const msg = hasAutoApply
          ? `${totalEdits} field(s) enriched and applied`
          : `${totalEdits} suggestion(s) added — review in chat`;
        toast.success(msg);
        if (!hasAutoApply) window.dispatchEvent(new CustomEvent('refreshSuggestionsAndOpenViewport'));
      }
      if (bulkSuccessCount > 0 || bulkFailCount > 0) {
        await refreshSuggestions();
        const summary = bulkFailCount > 0
          ? `${bulkSuccessCount} valued, ${bulkFailCount} failed`
          : totalEdits > 0
          ? `${totalEdits} fields updated, ${bulkSuccessCount} services run`
          : `${bulkSuccessCount} companies valued`;
        toast.success(hasAutoApply ? summary : `${summary} — review suggestions`);
        if (!hasAutoApply) window.dispatchEvent(new CustomEvent('refreshSuggestionsAndOpenViewport'));
      }
    },
    [matrixData?.rows, suggestBeforeApply, fundId, runActionWrapper, refreshSuggestions, handleCellEdit]
  );

  /** Open valuation picker in parent (survives cell unmount). */
  const onOpenValuationPicker = useCallback(
    (rowId: string, columnId: string, rowData: any, matrixDataArg: MatrixData | undefined) => {
      const data = matrixDataArg ?? matrixData ?? getDefaultMatrixData(mode, fundId);
      setValuationPicker({ rowId, columnId, rowData, matrixData: data });
    },
    [matrixData, mode, fundId, getDefaultMatrixData]
  );

  /** When useAgentPanel: "Run valuation" from cell dropdown opens this matrix's picker (single entry point). */
  const handleRunValuationOpenPicker = useCallback(
    (rowId: string) => {
      const data = matrixData ?? getDefaultMatrixData(mode, fundId);
      const row = data.rows.find((r) => r.id === rowId);
      const columnId = data.columns.find((c) => /valuation/i.test(c.id))?.id ?? 'valuation';
      if (row) onOpenValuationPicker(rowId, columnId, row, data);
    },
    [matrixData, mode, fundId, getDefaultMatrixData, onOpenValuationPicker]
  );

  /** Request document upload from parent. */
  const onRequestUploadDocument = useCallback((rowId: string, columnId: string) => {
    setUploadDocumentTarget({ rowId, columnId });
    requestAnimationFrame(() => uploadFileInputRef.current?.click());
  }, []);

  const saveCellEditToCompany = async (
    companyId: string,
    columnId: string,
    value: any,
    fundId?: string,
    metadata?: Record<string, unknown>
  ) => {
    // Use the comprehensive matrix cells API which has full field mapping
    try {
      const response = await fetch('/api/matrix/cells', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          company_id: companyId,
          column_id: columnId,
          old_value: undefined, // We don't track old value here
          new_value: value,
          fund_id: fundId,
          user_id: undefined, // Will be set by API if needed
          ...(metadata && typeof metadata === 'object' ? { metadata } : {}),
        }),
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.error || 'Failed to save edit');
      }
    } catch (err) {
      console.error('Error saving cell edit to company:', err);
      throw err;
    }
  };

  // Upload file to a cell: same logic as documents page (XHR POST /api/documents) then document.extract → apply to grid
  const handleUploadDocumentToCell = useCallback(
    async (rowId: string, columnId: string, file: File) => {
      const currentData = matrixData ?? getDefaultMatrixData(mode, fundId);
      const row = currentData.rows.find((r) => r.id === rowId || r.companyId === rowId);
      const companyId = row?.companyId;
      const canonicalRowId = row?.id ?? rowId;

      const formData = new FormData();
      formData.append('file', file);
      if (companyId) formData.append('company_id', companyId);
      if (fundId) formData.append('fund_id', fundId);
      // Default to monthly_update so matrix uploads get signal-first extraction (business_updates, operational_metrics)
      formData.append('document_type', 'monthly_update');

      setCellActionStatus((prev) => ({ ...prev, [`${canonicalRowId}_${columnId}`]: { state: 'loading', message: `Uploading ${file.name}...` } }));

      const xhr = new XMLHttpRequest();
      const uploadPromise = new Promise<{ documentId: string }>((resolve, reject) => {
        xhr.addEventListener('load', () => {
          if (xhr.status >= 200 && xhr.status < 300) {
            try {
              const result = JSON.parse(xhr.responseText);
              const documentId =
                (result?.document as { id?: string })?.id ?? result?.id ?? result?.document_id;
              if (documentId) resolve({ documentId });
              else reject(new Error('Upload succeeded but no document id returned'));
            } catch (e) {
              reject(new Error('Failed to parse upload response'));
            }
          } else {
            let msg = `Upload failed: ${xhr.statusText}`;
            try {
              const err = JSON.parse(xhr.responseText);
              if (err.error) msg = err.error;
              if (xhr.status === 503 && err.details?.hasUrl === false) {
                msg = 'Database not configured. Set NEXT_PUBLIC_SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY.';
              }
            } catch (_) {}
            reject(new Error(msg));
          }
        });
        xhr.addEventListener('error', () => reject(new Error('Network error during upload')));
        xhr.addEventListener('abort', () => reject(new Error('Upload cancelled')));
      });

      xhr.open('POST', '/api/documents');
      xhr.send(formData);

      try {
        const { documentId } = await uploadPromise;
        const existingCell = row?.cells?.[columnId];
        const existingDocs = existingCell?.metadata?.documents ?? [];
        const newDoc = { id: documentId, name: file.name };
        const documents = [...existingDocs, newDoc];
        const displayValue = documents.length === 1 ? '1 document' : `${documents.length} documents`;

        // Update local matrix state immediately so the document link appears before extract completes
        const updatedRows = currentData.rows.map((r) => {
          if (r.id !== canonicalRowId && r.companyId !== canonicalRowId) return r;
          const cells = { ...r.cells };
          cells[columnId] = {
            ...existingCell,
            value: displayValue,
            displayValue,
            source: 'document',
            metadata: { ...existingCell?.metadata, documents },
          };
          return { ...r, cells };
        });
        const updatedData: MatrixData = { ...currentData, rows: updatedRows };
        setMatrixData(updatedData);
        onDataChange?.(updatedData);

        // Persist the documents cell
        if (onCellEdit) {
          try {
            await onCellEdit(canonicalRowId, columnId, displayValue, {
              data_source: 'document',
              metadata: { documents },
            });
          } catch (err) {
            console.warn('Persist documents cell (onCellEdit) failed:', err);
          }
        } else if (row?.companyId) {
          try {
            await saveCellEditToCompany(row.companyId, columnId, displayValue, fundId, { documents });
          } catch (err) {
            console.warn('Persist documents cell (saveCellEditToCompany) failed:', err);
          }
        }

        setCellActionStatus((prev) => ({ ...prev, [`${canonicalRowId}_${columnId}`]: { state: 'success', message: 'Processing started' } }));
        setTimeout(() => setCellActionStatus((p) => { const next = { ...p }; delete next[`${canonicalRowId}_${columnId}`]; return next; }), 3000);

        // Then run extraction
        onToolCallLog?.({
          action_id: 'document.extract',
          row_id: canonicalRowId,
          column_id: columnId,
          status: 'running',
          companyName: row?.companyName,
        });
        const response = await executeAction({
          action_id: 'document.extract',
          row_id: canonicalRowId,
          column_id: columnId,
          inputs: { document_id: String(documentId), extraction_type: 'structured' },
          mode: mode ?? 'portfolio',
          fund_id: fundId,
          company_id: companyId,
        });
        onToolCallLog?.({
          action_id: 'document.extract',
          row_id: canonicalRowId,
          column_id: columnId,
          status: response.success ? 'success' : 'error',
          error: response.error,
          companyName: row?.companyName,
        });
        // Don't route through handleCellActionResult — that creates a single blob
        // suggestion for the documents column. The backend already wrote per-metric
        // suggestions via emit_document_suggestions; just refresh to pick them up.
        if (!response.success) {
          const key = `${canonicalRowId}_${columnId}`;
          setCellActionStatus((prev) => ({ ...prev, [key]: { state: 'error', message: response.error ?? 'Extraction failed' } }));
          setTimeout(() => setCellActionStatus((p) => { const next = { ...p }; delete next[key]; return next; }), 6000);
        }
        await refreshSuggestions();
      } catch (err) {
        console.error('Document upload or extraction failed:', err);
        setCellActionStatus((prev) => ({ ...prev, [`${canonicalRowId}_${columnId}`]: { state: 'error', message: err instanceof Error ? err.message : 'Upload failed' } }));
        setTimeout(() => setCellActionStatus((p) => { const next = { ...p }; delete next[`${canonicalRowId}_${columnId}`]; return next; }), 6000);
      }
    },
    [
      matrixData,
      mode,
      fundId,
      getDefaultMatrixData,
      executeAction,
      refreshSuggestions,
      onCellEdit,
      onDataChange,
      setMatrixData,
      saveCellEditToCompany,
      onToolCallLog,
    ]
  );

  const handleCellDoubleClick = (rowId: string, columnId: string) => {
    const row = matrixData?.rows.find((r) => r.id === rowId);
    const column = matrixData?.columns.find((c) => c.id === columnId);
    
    if (!row || !column || !column.editable) return;

    const currentValue = row.cells[columnId]?.value;
    setEditingCell({ rowId, columnId });
    setEditValue(String(currentValue || ''));
  };

  const handleCellSave = () => {
    if (!editingCell) return;

    const { rowId, columnId } = editingCell;
    const column = matrixData?.columns.find((c) => c.id === columnId);
    
    if (!column) return;

    let parsedValue: any = editValue;
    const isFormula = column.type === 'formula' || String(editValue || '').trim().startsWith('=');

    // Formula: pass raw string so handleCellEdit stores formula and does not parse as number
    if (isFormula) {
      parsedValue = String(editValue || '').trim() || '=';
    } else if (column.type === 'number' || column.type === 'currency' || column.type === 'percentage') {
      parsedValue = parseFloat(editValue) || 0;
      if (column.type === 'percentage') {
        parsedValue = parsedValue / 100; // Store as decimal
      }
    } else if (column.type === 'boolean') {
      parsedValue = editValue.toLowerCase() === 'true' || editValue === '1';
    }

    handleCellEdit(rowId, columnId, parsedValue);
    setEditingCell(null);
    setEditValue('');
  };

  const handleCellCancel = () => {
    setEditingCell(null);
    setEditValue('');
  };


  // Handler for adding a row/company — creates real company in DB, adds empty editable row immediately
  const handleAddRowSimple = useCallback(async () => {
    try {
      setIsLoading(true);
      const companyName = `New Company ${Date.now()}`;

      // Use shared helper to create real company
      const newCompany = await createCompanyForMatrix({
        name: companyName,
        fundId: mode === 'portfolio' ? fundId : undefined,
        mode,
        companyFields: mode === 'portfolio' && fundId ? {
          investmentAmount: 1,
          sector: '',
          stage: '',
          ownershipPercentage: 0,
          currentArr: 0,
        } : {},
      });

      // Get current columns (real headers from DB for portfolio, or defaults)
      const currentData = matrixData || getDefaultMatrixData(mode, fundId);
      let columns = currentData.columns;
      
      // For portfolio mode, try to load real headers from matrix_columns if not already loaded
      if (mode === 'portfolio' && fundId && (columns.length === 0 || columns.length === getDefaultMatrixData(mode, fundId).columns.length)) {
        try {
          const columnsResponse = await fetch(`/api/matrix/columns?fundId=${fundId}`);
          if (columnsResponse.ok) {
            const columnsData = await columnsResponse.json();
            const savedColumns = (columnsData.columns || []).map((col: any) => ({
              id: col.column_id || col.id,
              name: col.name,
              type: col.type as MatrixColumn['type'],
              width: col.width || 120,
              formula: col.formula,
              editable: col.editable !== false,
            }));
            if (savedColumns.length > 0) {
              columns = savedColumns;
            }
          }
        } catch (err) {
          console.warn('Could not load saved columns:', err);
        }
      }
      
      // Fallback to defaults if still no columns
      if (columns.length === 0) {
        columns = getDefaultMatrixData(mode, fundId).columns;
      }
      columns = canonicalizeMatrixColumns(columns);

      // Always add empty row to grid immediately (no form, just empty editable row)
      setMatrixData((currentData) => {
        const data = currentData || getDefaultMatrixData(mode, fundId);

        const newRow: MatrixRow = {
          id: newCompany.id,
          companyId: newCompany.id,
          companyName: newCompany.companyName ?? companyName,
          cells: columns.reduce(
            (acc, col) => {
              acc[col.id] = { value: null, source: 'manual' as const };
              return acc;
            },
            {} as Record<string, MatrixCell>
          ),
        };

        const updated: MatrixData = {
          ...data,
          columns,
          rows: [...(data.rows || []), newRow],
          metadata: { ...data.metadata, lastUpdated: new Date().toISOString() },
        };
        onDataChange?.(updated);
        return updated;
      });

      // For portfolio mode, refresh in background to sync with API (but row is already visible and editable)
      if (mode === 'portfolio' && fundId) {
        // Refresh in background - don't wait, row is already added and editable
        if (onRefresh) {
          Promise.resolve(onRefresh()).catch(err => console.warn('Background refresh failed:', err));
        } else {
          window.dispatchEvent(new CustomEvent('refreshMatrix'));
        }
      }

      toast.success(`Empty row added - fill in the details or let the agent complete it`);
    } catch (error) {
      console.error('[handleAddRowSimple]', error);
      toast.error(error instanceof Error ? error.message : 'Failed to add company');
    } finally {
      setIsLoading(false);
    }
  }, [mode, fundId, matrixData, onDataChange, onRefresh, getDefaultMatrixData]);

  // Removed: handleAddCompanyToFund - companies are now created inline in the grid

  // Handler for adding a column
  const handleAddColumnSimple = useCallback(() => {
    // In portfolio mode with fundId: open dialog to persist column to backend
    if (mode === 'portfolio' && fundId) {
      setShowAddColumnDialog(true);
      return;
    }
    
    // In custom/query mode: add column locally only (no persistence needed)
    setMatrixData((currentData) => {
      // If no data exists, initialize with default
      const data = currentData || getDefaultMatrixData(mode, fundId);
      
      const columnId = `col-${Date.now()}-${Math.random().toString(36).slice(2)}`;
      const col: MatrixColumn = {
        id: columnId,
        name: `Column ${data.columns.length + 1}`,
        type: 'text',
        editable: true,
      };
      
      const newColumns = [...data.columns, col];
      const newRows = data.rows.map((row) => ({
        ...row,
        cells: {
          ...row.cells,
          [col.id]: { value: null, source: 'manual' as const },
        },
      }));
      
      const updatedData: MatrixData = {
        ...data,
        columns: newColumns,
        rows: newRows,
        metadata: {
          ...data.metadata,
          lastUpdated: new Date().toISOString(),
        },
      };
      
      onDataChange?.(updatedData);
      return updatedData;
    });
  }, [mode, fundId, onDataChange, getDefaultMatrixData]);

  const handleAddColumn = useCallback(async () => {
    if (!newColumn.name.trim()) return;
    setError(null);
    try {
      const col = await addMatrixColumn({
        name: newColumn.name.trim(),
        type: newColumn.type,
        service: newColumn.service?.trim() || undefined,
        fundId: mode === 'portfolio' ? fundId : undefined,
        createdBy: 'human',
      });
      const baseData = matrixData ?? getDefaultMatrixData(mode, fundId);
      const newColumns = canonicalizeMatrixColumns([...baseData.columns, col]);
      const newRows = baseData.rows.map((row) => ({
        ...row,
        cells: {
          ...row.cells,
          [col.id]: { value: null, source: 'manual' as const },
        },
      }));
      const updatedData: MatrixData = {
        ...baseData,
        columns: newColumns,
        rows: newRows,
        metadata: {
          ...baseData.metadata,
          lastUpdated: new Date().toISOString(),
        },
      };
      setMatrixData(updatedData);
      onDataChange?.(updatedData);
      setShowAddColumnDialog(false);
      setNewColumn({ name: '', type: 'text', service: '' });

      if (mode === 'portfolio' && fundId) {
        await loadPortfolioData();
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to add column';
      setError(message);
      console.warn('Failed to add column via API:', err);
    }
  }, [matrixData, newColumn, mode, fundId, onDataChange, loadPortfolioData, getDefaultMatrixData]);

  // Handle column edit
  const handleEditColumn = useCallback(async (columnId: string, updates: Partial<MatrixColumn>) => {
    if (!matrixData || !fundId) return;
    
    try {
      // Find the column in the database
      const response = await fetch(`/api/matrix/columns?fundId=${fundId}`);
      if (response.ok) {
        const data = await response.json();
        const dbColumn = (data.columns || []).find((c: any) => (c.column_id || c.id) === columnId);
        
        if (dbColumn) {
          // Update in database
          const updateResponse = await fetch(`/api/matrix/columns/${dbColumn.id}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(updates),
          });
          
          if (updateResponse.ok) {
            // Update local state
            const updatedColumns = matrixData.columns.map(col => 
              col.id === columnId ? { ...col, ...updates } : col
            );
            const updatedData: MatrixData = {
              ...matrixData,
              columns: updatedColumns,
            };
            setMatrixData(updatedData);
            onDataChange?.(updatedData);
          }
        }
      }
    } catch (err) {
      console.error('Error editing column:', err);
    }
  }, [matrixData, fundId, onDataChange]);

  // Handle row delete with confirmation and proper error handling
  const handleRowDelete = useCallback(async (rowId: string) => {
    if (!matrixData || !fundId || mode !== 'portfolio') {
      toast.error('Delete is only available in portfolio mode');
      return;
    }

    const row = matrixData.rows.find(r => r.id === rowId);
    if (!row?.companyId) {
      toast.error('Company not found');
      return;
    }

    const companyName = row.companyName || 'this company';
    
    // Confirmation dialog
    if (!confirm(`Are you sure you want to delete "${companyName}" from the portfolio?\n\nThis action cannot be undone.`)) {
      return;
    }

    try {
      const response = await fetch(`/api/portfolio/${fundId}/companies/${row.companyId}`, {
        method: 'DELETE',
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.error || errorData.message || 'Failed to delete company');
      }

      const result = await response.json();
      
      // Remove from matrix immediately
      const updatedRows = matrixData.rows.filter(r => r.id !== rowId);
      const updatedData: MatrixData = {
        ...matrixData,
        rows: updatedRows,
      };
      setMatrixData(updatedData);
      onDataChange?.(updatedData);

      toast.success(result.message || `Company "${companyName}" deleted successfully`);
      
      // Refresh data if callback provided
      onRefresh?.();
    } catch (error) {
      console.error('Error deleting company:', error);
      const errorMessage = error instanceof Error ? error.message : 'Failed to delete company';
      toast.error('Delete failed', {
        description: errorMessage,
        duration: 5000,
      });
    }
  }, [matrixData, fundId, mode, onDataChange, onRefresh]);

  // Handle column delete – same idea as delete company (row), but for columns. Persists to Supabase.
  const handleDeleteColumn = useCallback(async (columnId: string) => {
    if (!matrixData || !fundId) return;
    
    if (!confirm('Are you sure you want to delete this column? This action cannot be undone.')) {
      return;
    }
    
    try {
      const deleteResponse = await fetch(
        `/api/matrix/columns?fundId=${encodeURIComponent(fundId)}&columnId=${encodeURIComponent(columnId)}`,
        { method: 'DELETE' }
      );
      if (!deleteResponse.ok) {
        const err = await deleteResponse.json().catch(() => ({}));
        throw new Error(err?.error ?? 'Failed to delete column');
      }
      const updatedColumns = matrixData.columns.filter(col => col.id !== columnId);
      const updatedRows = matrixData.rows.map(row => {
        const newCells = { ...row.cells };
        delete newCells[columnId];
        return { ...row, cells: newCells };
      });
      const updatedData: MatrixData = {
        ...matrixData,
        columns: updatedColumns,
        rows: updatedRows,
      };
      setMatrixData(updatedData);
      onDataChange?.(updatedData);
    } catch (err) {
      console.error('Error deleting column:', err);
    }
  }, [matrixData, fundId, onDataChange]);

  const formatCellValue = (value: any, type: string): string =>
    formatCellValueShared(value, type as import('@/lib/matrix/cell-formatters').CellColumnType);

  // Enhanced CSV export with metadata, formulas, audit trail, and summary stats
  const exportToCSV = () => {
    if (!matrixData) return;

    const lines: string[] = [];

    // Metadata header
    lines.push(`Export Date: ${new Date().toISOString()}`);
    lines.push(`Data Source: ${matrixData.metadata?.dataSource || 'unknown'}`);
    if (matrixData.metadata?.fundId) {
      lines.push(`Fund ID: ${matrixData.metadata.fundId}`);
    }
    if (matrixData.metadata?.query) {
      lines.push(`Query: ${matrixData.metadata.query}`);
    }
    lines.push(`Rows: ${matrixData.rows.length}, Columns: ${matrixData.columns.length}`);
    lines.push(''); // Empty line

    // Build header row with optional formulas column
    const headerRow: string[] = [];
    const formulaRow: string[] = [];
    const auditTrailHeaders: string[] = ['Last Edited', 'Edited By', 'Source'];

    matrixData.columns.forEach((col) => {
      headerRow.push(escapeCSV(col.name));
      if (col.formula) {
        formulaRow.push(escapeCSV(col.formula));
      } else {
        formulaRow.push('');
      }
    });

    // Add audit trail columns if any cells have audit info
    const hasAuditInfo = matrixData.rows.some((row) =>
      matrixData.columns.some((col) => {
        const cell = row.cells[col.id];
        return cell?.lastUpdated || cell?.editedBy || cell?.source;
      })
    );

    if (hasAuditInfo) {
      headerRow.push(...auditTrailHeaders);
      formulaRow.push('', '', ''); // Empty for audit columns
    }

    lines.push(headerRow.join(','));

    // Formula row (if any formulas exist)
    if (formulaRow.some((f) => f)) {
      lines.push(formulaRow.join(','));
    }

    // Data rows
    matrixData.rows.forEach((row) => {
      const dataRow: string[] = [];
      const auditRow: string[] = [];

      matrixData.columns.forEach((col) => {
        const cell = row.cells[col.id];
        const value = cell?.displayValue || cell?.value || '';
        dataRow.push(escapeCSV(String(value)));
      });

      if (hasAuditInfo) {
        // Get audit info from first cell with audit data (or use row-level)
        const firstCellWithAudit = matrixData.columns.find((col) => {
          const cell = row.cells[col.id];
          return cell?.lastUpdated || cell?.editedBy || cell?.source;
        });
        const cell = firstCellWithAudit ? row.cells[firstCellWithAudit.id] : null;

        auditRow.push(
          cell?.lastUpdated ? new Date(cell.lastUpdated).toLocaleString() : '',
          cell?.editedBy || '',
          cell?.source || ''
        );
        dataRow.push(...auditRow);
      }

      lines.push(dataRow.join(','));
    });

    // Summary statistics row
    lines.push(''); // Empty line
    lines.push('Summary Statistics');
    const numericColumns = matrixData.columns.filter(
      (col) => col.type === 'currency' || col.type === 'number' || col.type === 'percentage'
    );

    numericColumns.forEach((col) => {
      const values = matrixData.rows
        .map((row) => {
          const cell = row.cells[col.id];
          return typeof cell?.value === 'number' ? cell.value : null;
        })
        .filter((v): v is number => v !== null && !isNaN(v));

      if (values.length > 0) {
        const sum = values.reduce((a, b) => a + b, 0);
        const avg = sum / values.length;
        const min = Math.min(...values);
        const max = Math.max(...values);
        lines.push(
          `${col.name}: Avg=${formatCellValue(avg, col.type)}, Min=${formatCellValue(min, col.type)}, Max=${formatCellValue(max, col.type)}, Count=${values.length}`
        );
      }
    });

    const csv = lines.join('\n');
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `matrix-export-${Date.now()}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const escapeCSV = (value: any): string => {
    if (value === null || value === undefined) return '';
    const str = String(value);
    if (str.includes(',') || str.includes('"') || str.includes('\n')) {
      return `"${str.replace(/"/g, '""')}"`;
    }
    return str;
  };

  const exportToXML = async () => {
    if (!matrixData) return;

    try {
      const response = await fetch('/api/matrix/export/annex5', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          matrixData,
          fundId,
        }),
      });

      if (!response.ok) throw new Error('Failed to export XML');

      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `matrix-annex5-${Date.now()}.xml`;
      a.click();
    } catch (err) {
      console.error('Error exporting XML:', err);
      setError('Failed to export XML');
    }
  };

  // Save matrix configuration
  const saveMatrix = () => {
    if (!matrixData) return;

    const name = prompt('Enter a name for this matrix configuration:');
    if (!name) return;

    const saved = {
      id: `matrix-${Date.now()}`,
      name,
      mode,
      fundId,
      data: matrixData,
      timestamp: new Date().toISOString(),
    };

    const savedMatrices = JSON.parse(localStorage.getItem('saved_matrices') || '[]');
    savedMatrices.push(saved);
    localStorage.setItem('saved_matrices', JSON.stringify(savedMatrices));
    setSavedConfigs(savedMatrices);
    
    toast.success('Matrix saved successfully!');
  };

  // Load matrix configuration
  const loadMatrix = (config: any) => {
    if (config.data) {
      setMatrixData(config.data);
      onDataChange?.(config.data);
      setShowLoadDialog(false);
    }
  };

  // Import CSV/Excel file (works with both file input and drag-and-drop)
  /**
   * Parse CSV line with proper quote handling
   * Handles quoted fields containing commas: "Company, Inc.",$5M
   */
  const parseCSVLine = (line: string): string[] => {
    const result: string[] = [];
    let current = '';
    let inQuotes = false;
    
    for (let i = 0; i < line.length; i++) {
      const char = line[i];
      const nextChar = line[i + 1];
      
      if (char === '"') {
        if (inQuotes && nextChar === '"') {
          // Escaped quote
          current += '"';
          i++; // Skip next quote
        } else {
          // Toggle quote state
          inQuotes = !inQuotes;
        }
      } else if (char === ',' && !inQuotes) {
        // Field separator
        result.push(current.trim());
        current = '';
      } else {
        current += char;
      }
    }
    
    // Add last field
    result.push(current.trim());
    
    return result;
  };

  const handleFileImport = useCallback(async (file: File | null, event?: React.ChangeEvent<HTMLInputElement>) => {
    // Handle file input event
    if (event) {
      file = event.target.files?.[0] || null;
    }
    
    // Allow import even if matrixData is null - we'll create it from CSV
    if (!file || mode !== 'portfolio' || !fundId) return;

    setIsImporting(true);
    setError(null);

    try {
      const isExcel = file.name.endsWith('.xlsx') || file.name.endsWith('.xls');
      let headers: string[] = [];
      let dataRows: string[][] = [];
      let dataStartIndex = 0; // Declared at function level

      if (isExcel) {
        // Handle Excel files using xlsx library
        const XLSX = await import('xlsx');
        const arrayBuffer = await file.arrayBuffer();
        const workbook = XLSX.read(arrayBuffer, { type: 'array' });
        
        // Use first sheet
        const firstSheetName = workbook.SheetNames[0];
        const worksheet = workbook.Sheets[firstSheetName];
        
        // Convert to JSON with header row
        const jsonData = XLSX.utils.sheet_to_json(worksheet, { header: 1, defval: '' }) as any[][];
        
        if (jsonData.length === 0) {
          throw new Error('Excel file is empty');
        }
        
        // First row is headers
        headers = jsonData[0].map((h: any) => String(h || '').trim());
        dataRows = jsonData.slice(1).map(row => row.map((cell: any) => String(cell || '').trim()));
        dataStartIndex = 0; // Excel: headers are first row, data starts at index 0
      } else {
        // Handle CSV files
        const text = await file.text();
        const lines = text.split('\n').filter((line) => line.trim());
      
        // Skip metadata lines (lines starting with "Export Date:", "Data Source:", etc.)
        for (let i = 0; i < lines.length; i++) {
          if (!lines[i].startsWith('Export Date:') && 
              !lines[i].startsWith('Data Source:') && 
              !lines[i].startsWith('Fund ID:') && 
              !lines[i].startsWith('Query:') && 
              !lines[i].startsWith('Rows:') &&
              !lines[i].startsWith('Summary Statistics') &&
              lines[i].includes(',')) {
            dataStartIndex = i;
            break;
          }
        }

        // Parse header row with proper CSV parsing
        const headerLine = lines[dataStartIndex];
        headers = parseCSVLine(headerLine).map((h) => h.replace(/^"|"$/g, ''));
        
        // Parse data rows with proper CSV parsing
        for (let i = dataStartIndex + 1; i < lines.length; i++) {
          const line = lines[i];
          if (!line.trim() || line.startsWith('Summary Statistics')) break;
          
          const values = parseCSVLine(line);
          if (values.length > 0 && values[0]) { // Skip empty rows
            dataRows.push(values);
          }
        }
      }
      
      // Ensure we have headers
      if (headers.length === 0) {
        throw new Error('No headers found in file');
      }
      
      // Get or create matrix data
      let currentData = matrixData;
      
      // For portfolio mode: try to load real headers from matrix_columns API
      if (mode === 'portfolio' && fundId && !currentData) {
        try {
          const columnsResponse = await fetch(`/api/matrix/columns?fundId=${fundId}`);
          if (columnsResponse.ok) {
            const columnsData = await columnsResponse.json();
            const savedColumns = (columnsData.columns || []).map((col: any) => ({
              id: col.column_id || col.id,
              name: col.name,
              type: col.type as MatrixColumn['type'],
              width: col.width || 120,
              formula: col.formula,
              editable: col.editable !== false,
            }));
            
            if (savedColumns.length > 0) {
              currentData = {
                columns: savedColumns,
                rows: [],
                metadata: {
                  dataSource: 'portfolio',
                  fundId,
                  lastUpdated: new Date().toISOString(),
                },
              };
            }
          }
        } catch (err) {
          console.warn('Could not load saved columns, using defaults:', err);
        }
      }
      
      // Fallback to defaults if no columns loaded
      if (!currentData || currentData.columns.length === 0) {
        currentData = getDefaultMatrixData(mode, fundId);
      }
      
      // Use dynamic field mapping system to intelligently map CSV headers to columns
      const existingColumns = currentData.columns.map(col => ({
        id: col.id,
        name: col.name,
        type: col.type as 'text' | 'number' | 'currency' | 'percentage' | 'date' | 'boolean',
        width: col.width,
        editable: col.editable,
        formula: col.formula,
      }));
      
      const fieldMappings = mapCsvHeadersToColumns(headers, existingColumns);
      
      // Create column map for quick lookup
      const columnMap: Record<string, string> = {};
      fieldMappings.forEach(mapping => {
        columnMap[mapping.csvHeader] = mapping.columnId;
      });
      
      // Add new columns from mappings
      const newColumnDefs = createColumnDefinitions(fieldMappings);
      const newColumns: MatrixColumn[] = newColumnDefs.map(def => ({
        id: def.id,
        name: def.name,
        type: def.type,
        width: def.width || 150,
        editable: def.editable !== false,
        formula: def.formula,
      }));
      
      // Add new columns if any
      if (newColumns.length > 0) {
        currentData = {
          ...currentData,
          columns: [...currentData.columns, ...newColumns],
        };
      }
      
      setMatrixData(currentData);
      onDataChange?.(currentData);

      // Parse data rows with error tracking
      const updates: Array<{ companyId: string; fields: Record<string, any> }> = [];
      const skippedCompanies: string[] = [];
      const updatedCompanies: string[] = [];
      const errors: Array<{ company: string; error: string }> = [];
      
      // Process data rows (unified for both CSV and Excel)
      for (const values of dataRows) {
        if (values.length === 0) continue;
        
        // Get company name from first column (remove quotes if present)
        const companyName = values[0]?.replace(/^"|"$/g, '').trim();
        if (!companyName) continue; // Skip empty rows
        
        let row = currentData.rows.find(
          (r) => (r.companyName || r.cells['company']?.value || r.cells['companyName']?.value) === companyName
        );

        // If company not found, directly create row from CSV data
        // Only create database company if in portfolio mode with fundId and investmentAmount
        if (!row || !row.companyId) {
          try {
            // Extract fields for API and prepare all CSV data for matrix using dynamic mapping
            const companyFields: Record<string, any> = {};
            const csvDataForMatrix: Record<string, any> = {}; // All CSV fields to store in matrix
              
              headers.forEach((header, idx) => {
                if (idx >= values.length) return; // Skip if no value for this column
                
                const mapping = fieldMappings.find(m => m.csvHeader === header);
                if (!mapping) return;
                
                const rawValue = values[idx]?.replace(/^"|"$/g, '').trim();
                if (!rawValue) return;
                
                // Use dynamic value mapping with proper type conversion
                const { value, error } = mapCsvValue(rawValue, mapping);
                
                if (error) {
                  console.warn(`Failed to parse ${header}:`, error);
                  csvDataForMatrix[mapping.columnId] = rawValue; // Store raw value on error
                } else {
                  // Store parsed value in matrix
                  csvDataForMatrix[mapping.columnId] = value;
                  
                  // Map to database fields if this column maps to a known DB field
                  const dbField = getDbFieldName(mapping.columnId, fieldMappings);
                  if (dbField && value !== null) {
                    // Map to company fields using database field names
                    if (dbField === 'current_arr_usd') {
                      companyFields.currentArr = value;
                    } else if (dbField === 'total_invested_usd') {
                      companyFields.investmentAmount = value;
                    } else if (dbField === 'ownership_percentage') {
                      companyFields.ownershipPercentage = typeof value === 'number' ? (value > 1 ? value : value * 100) : value;
                    } else if (dbField === 'sector') {
                      companyFields.sector = value;
                    } else if (dbField === 'stage') {
                      companyFields.stage = value;
                    } else if (dbField === 'first_investment_date') {
                      companyFields.firstInvestmentDate = value;
                    } else if (dbField === 'investment_lead') {
                      companyFields.investmentLead = value;
                    } else if (dbField === 'last_contacted_date') {
                      companyFields.lastContactedDate = value;
                    } else if (dbField === 'current_valuation_usd') {
                      companyFields.valuation = value;
                    } else if (dbField === 'burn_rate_monthly_usd') {
                      companyFields.burnRate = value;
                    } else if (dbField === 'runway_months') {
                      companyFields.runway = value;
                    } else if (dbField === 'cash_in_bank_usd') {
                      companyFields.cashInBank = value;
                    } else if (dbField === 'gross_margin') {
                      companyFields.grossMargin = value;
                    }
                  }
                }
              });
              
              // Always create a real company using shared helper (no temp rows)
              const newCompany = await createCompanyForMatrix({
                name: companyName,
                fundId: mode === 'portfolio' ? fundId : undefined,
                mode,
                companyFields,
              });
              
              // Create matrix row with companyId and CSV data
              const newRow: MatrixRow = {
                id: newCompany.id,
                companyId: newCompany.id,
                companyName: newCompany.companyName,
                cells: currentData.columns.reduce((acc, col) => {
                  // Initialize with CSV data if available, otherwise null
                  acc[col.id] = csvDataForMatrix[col.id] !== undefined
                    ? { value: csvDataForMatrix[col.id], source: 'manual' as const }
                    : { value: null, source: 'manual' as const };
                  return acc;
                }, {} as Record<string, MatrixCell>),
              };
              
              row = newRow;
              currentData.rows.push(row);
            } catch (createError) {
              errors.push({ 
                company: companyName, 
                error: createError instanceof Error ? createError.message : 'Failed to create company' 
              });
              continue;
            }
          }

        try {
          const fields: Record<string, any> = {};
          
          headers.forEach((header, idx) => {
            if (idx >= values.length) return; // Skip if no value for this column
            
            const mapping = fieldMappings.find(m => m.csvHeader === header);
            if (!mapping) return;
            
            const rawValue = values[idx]?.replace(/^"|"$/g, '').trim();
            
            // Skip company name column and empty values
            if (!rawValue || mapping.columnId === 'company' || mapping.columnId === 'companyName') {
              return;
            }
            
            const column = currentData.columns.find((c) => c.id === mapping.columnId);
            if (!column || !column.editable) {
              return;
            }
            
            // Use dynamic value mapping with proper type conversion
            const { value, error } = mapCsvValue(rawValue, mapping);
            
            if (error) {
              errors.push({ 
                company: companyName, 
                error: `${header}: ${error}` 
              });
            } else if (value !== null) {
              fields[mapping.columnId] = value;
            }
          });

          if (Object.keys(fields).length > 0 && row && row.companyId) {
            updates.push({ companyId: row.companyId, fields });
            updatedCompanies.push(companyName);
          }
        } catch (error) {
          errors.push({ 
            company: companyName, 
            error: error instanceof Error ? error.message : 'Unknown error' 
          });
        }
      }

      // Bulk update via API
      if (updates.length > 0) {
        const response = await fetch(`/api/portfolio/${fundId}/companies/bulk`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ updates }),
        });

        if (!response.ok) {
          const errorData = await response.json().catch(() => ({}));
          throw new Error(errorData.error || 'Failed to import data');
        }

        const result = await response.json();
        
        // Show detailed import summary with toast notifications
        if (updatedCompanies.length > 0) {
          toast.success(
            `Successfully updated ${updatedCompanies.length} companies`,
            {
              description: skippedCompanies.length > 0 || errors.length > 0
                ? `${skippedCompanies.length > 0 ? `${skippedCompanies.length} skipped. ` : ''}${errors.length > 0 ? `${errors.length} errors.` : ''}`
                : undefined,
              duration: 5000,
            }
          );
        }
        
        if (skippedCompanies.length > 0) {
          toast.warning(
            `${skippedCompanies.length} companies skipped`,
            {
              description: `Companies not in portfolio: ${skippedCompanies.slice(0, 5).join(', ')}${skippedCompanies.length > 5 ? ` and ${skippedCompanies.length - 5} more` : ''}. Add them manually or use @CompanyName in custom mode.`,
              duration: 6000,
            }
          );
        }
        if (errors.length > 0) {
          toast.error(
            `${errors.length} import errors`,
            {
              description: errors.slice(0, 3).map(e => `${e.company}: ${e.error}`).join('; ') + (errors.length > 3 ? ` and ${errors.length - 3} more` : ''),
              duration: 8000,
            }
          );
        }
        loadPortfolioData();
        onRefresh?.();
      } else {
        if (skippedCompanies.length > 0) {
          toast.warning(
            'No companies found in portfolio',
            {
              description: `Skipped: ${skippedCompanies.slice(0, 5).join(', ')}${skippedCompanies.length > 5 ? ` and ${skippedCompanies.length - 5} more` : ''}. Add companies to your portfolio first, or use @CompanyName in custom mode.`,
              duration: 6000,
            }
          );
        } else {
          toast.error('No valid data found to import');
        }
      }
    } catch (err) {
      console.error('Import error:', err);
      setError(err instanceof Error ? err.message : 'Failed to import file');
    } finally {
      setIsImporting(false);
      setShowImportDialog(false);
      // Reset file input if it was from an event
      if (event?.target) {
        event.target.value = '';
      }
    }
  }, [matrixData, mode, fundId, loadPortfolioData, onRefresh, onDataChange]);

  // Capture-phase: allow file drop before AG Grid can block it (must preventDefault on dragover for drop to fire)
  const handleDragOverCapture = useCallback((e: React.DragEvent) => {
    if (e.dataTransfer.types.includes('Files')) {
      e.preventDefault();
      e.dataTransfer.dropEffect = 'copy';
    }
  }, []);
  const handleDragEnterCapture = useCallback((e: React.DragEvent) => {
    if (e.dataTransfer.types.includes('Files')) {
      e.preventDefault();
      e.dataTransfer.dropEffect = 'copy';
    }
  }, []);

  // Drag and drop handlers for CSV import and document upload
  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (mode === 'portfolio' && fundId) {
      if (e.dataTransfer.types.includes('Files')) setIsDraggingDocument(true);
      else setIsDraggingCSV(true);
    }
  }, [mode, fundId]);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDraggingCSV(false);
    setIsDraggingDocument(false);
  }, []);

  const handleDrop = useCallback(async (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDraggingCSV(false);
    setIsDraggingDocument(false);

    if (mode !== 'portfolio' || !fundId) return;

    const files = Array.from(e.dataTransfer.files);
    if (files.length === 0) return;

    const csvFile = files.find(f =>
      f.name.endsWith('.csv') ||
      f.name.endsWith('.xlsx') ||
      f.name.endsWith('.xls')
    );
    if (csvFile) {
      handleFileImport(csvFile);
      return;
    }

    // Document files (PDF, docx, etc.): match to company by filename, then upload
    const docFiles = files.filter(f =>
      f.name.endsWith('.pdf') ||
      f.name.endsWith('.docx') ||
      f.name.endsWith('.doc')
    );
    if (docFiles.length > 0 && handleUploadDocumentToCell) {
      const currentData = matrixData ?? getDefaultMatrixData(mode, fundId);
      const docCol = currentData.columns?.find(c => c.id === 'documents' || c.name?.toLowerCase().includes('document')) ?? currentData.columns?.[0];
      if (!docCol || !currentData.rows?.length) {
        console.warn('[UnifiedMatrix] Document drop ignored: need at least one row and a documents column.', { hasDocCol: !!docCol, rowsCount: currentData.rows?.length ?? 0 });
        toast.error('Add a row first', { description: 'Document upload needs at least one row and a Documents column.' });
        return;
      }

      for (const file of docFiles) {
        // Try to match file to a company by name in filename
        const fileBase = file.name.replace(/\.[^.]+$/, '').toLowerCase().replace(/[_\-]+/g, ' ');
        let matchedRow = currentData.rows.find(r => {
          const compName = (r.name ?? r.companyId ?? '').toLowerCase();
          if (!compName) return false;
          // Check if company name appears in filename or first token of filename matches
          const firstToken = fileBase.split(/\s+/)[0];
          return fileBase.includes(compName) || compName.includes(firstToken) || firstToken.length > 2 && compName.startsWith(firstToken);
        });

        if (!matchedRow && currentData.rows.length === 1) {
          // Only one company — safe to default
          matchedRow = currentData.rows[0];
        }

        if (!matchedRow) {
          toast.error(`Cannot match "${file.name}" to a company`, { description: 'Drag the file onto the specific company row, or rename the file to include the company name.' });
          console.warn('[UnifiedMatrix] Document drop: no company match for', file.name, 'rows:', currentData.rows.map(r => r.name ?? r.companyId));
          continue;
        }

        const rowId = matchedRow.id ?? matchedRow.companyId;
        console.log('[UnifiedMatrix] Document drop: matched', file.name, 'to company', matchedRow.name ?? rowId);
        await handleUploadDocumentToCell(rowId!, docCol.id, file);
      }
    }
  }, [mode, fundId, handleFileImport, handleUploadDocumentToCell, matrixData, getDefaultMatrixData]);

  // Export compressed context for @ symbol queries
  const exportCompressedContext = async () => {
    if (!matrixData || mode !== 'portfolio') return;

    const context = compressPortfolioContext(matrixData);
    
    if (context.size > 2000) {
      toast.warning(
        'Context size exceeds limit',
        {
          description: `Context is ${context.size} bytes (exceeds 2KB limit). Only first ${context.companyCount} companies included.`,
          duration: 5000,
        }
      );
    }

    const copied = await copyCompressedContextToClipboard(context);
    if (copied) {
      toast.success(
        'Portfolio context copied to clipboard',
        {
          description: `${context.companyCount} companies, ${context.size} bytes`,
          duration: 3000,
        }
      );
    } else {
      // Fallback to download
      downloadCompressedContext(context, `portfolio-context-${Date.now()}.txt`);
      toast.info('Portfolio context downloaded', {
        description: 'Context saved to file',
        duration: 3000,
      });
    }
  };

  // Use ref to track previous matrixData to prevent unnecessary recalculations
  const prevMatrixDataRef = useRef<MatrixData | null>(null);
  const prevModeRef = useRef<MatrixMode>(mode);
  const prevFundIdRef = useRef<string | undefined>(fundId);

  // Always ensure matrixData exists with columns - use default if null or if columns are empty
  // Stabilized to only recalculate when actual data structure changes
  const currentMatrixData = useMemo(() => {
    // Check if mode or fundId changed (these affect defaults)
    const modeChanged = prevModeRef.current !== mode;
    const fundIdChanged = prevFundIdRef.current !== fundId;
    
    // Check if matrixData reference changed
    const dataChanged = prevMatrixDataRef.current !== matrixData;
    
    // If nothing changed, return previous result to prevent unnecessary re-renders
    if (!modeChanged && !fundIdChanged && !dataChanged && prevMatrixDataRef.current) {
      return prevMatrixDataRef.current;
    }

    const defaults = getDefaultMatrixData(mode, fundId);
    let result: MatrixData;
    
    // If matrixData is null or has no columns, use defaults
    if (!matrixData || !matrixData.columns || matrixData.columns.length === 0) {
      result = defaults;
    } else if (matrixData.columns.length === 0) {
      // Ensure columns array is never empty
      result = { ...matrixData, columns: defaults.columns };
    } else {
      // Use actual matrixData
      result = matrixData;
    }
    
    // Ensure metadata.fundId is set when in portfolio mode with a selected fund,
    // so AGGridMatrix and CellDropdownRenderer always have fundId for action execution.
    if (mode === 'portfolio' && fundId) {
      result = { ...result, metadata: { ...result.metadata, fundId } };
    }
    
    // Update refs
    prevMatrixDataRef.current = result;
    prevModeRef.current = mode;
    prevFundIdRef.current = fundId;
    
    return result;
  }, [matrixData, mode, fundId, getDefaultMatrixData]);

  return (
    <div className="flex flex-col h-full space-y-2">
      {/* Minimal toolbar: query bar only when needed, single menu for rest */}
      <div className="flex items-center gap-2 shrink-0">
        {(mode === 'query' || mode === 'custom') && showQueryBar && (
          <div className="flex items-center gap-2 flex-1 max-w-md">
            <Input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyPress={(e) => e.key === 'Enter' && handleQuery()}
              placeholder={mode === 'custom' ? "Type @CompanyName to search..." : "Enter matrix query..."}
              className="flex-1 h-8 text-sm"
            />
            <Button onClick={handleQuery} disabled={isLoading || !query.trim()} size="sm" className="h-8">
              <Sparkles className="w-4 h-4 mr-1" />
              {mode === 'custom' ? 'Search' : 'Query'}
            </Button>
          </div>
        )}
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="ghost" size="sm" className="h-8 px-2">
              <MoreVertical className="w-4 h-4" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            {matrixData && (
              <DropdownMenuItem onClick={() => setShowChartViewport((v) => !v)}>
                <BarChart3 className="w-4 h-4 mr-2" />
                {showChartViewport ? 'Hide' : 'Show'} chat
              </DropdownMenuItem>
            )}
            {(mode === 'portfolio' || mode === 'lp') && (
              <DropdownMenuItem onClick={() => { mode === 'lp' ? loadLPData() : loadPortfolioData(); onRefresh?.(); }}>
                <RefreshCw className="w-4 h-4 mr-2" />
                Refresh
              </DropdownMenuItem>
            )}
            {showExport && matrixData && (
              <DropdownMenuItem onClick={exportToCSV}>
                <FileSpreadsheet className="w-4 h-4 mr-2" />
                Export CSV
              </DropdownMenuItem>
            )}
            <DropdownMenuSeparator />
            <DropdownMenuItem onClick={() => setShowAddColumnDialog(true)}>
              <Plus className="w-4 h-4 mr-2" />
              Add Column
            </DropdownMenuItem>
            {showInsights && (
              <DropdownMenuItem onClick={() => setShowInsightsPanel(!showInsightsPanel)}>
                {showInsightsPanel ? <EyeOff className="w-4 h-4 mr-2" /> : <Eye className="w-4 h-4 mr-2" />}
                {showInsightsPanel ? 'Hide' : 'Show'} Insights
              </DropdownMenuItem>
            )}
            {mode === 'portfolio' && (
              <>
                <input type="file" accept=".csv,.xlsx,.xls" onChange={(e) => handleFileImport(null, e)} className="hidden" id="matrix-import-input" />
                <DropdownMenuItem onClick={() => document.getElementById('matrix-import-input')?.click()} disabled={isImporting}>
                  {isImporting ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <Upload className="w-4 h-4 mr-2" />}
                  Import CSV/Excel
                </DropdownMenuItem>
                <DropdownMenuItem onClick={exportCompressedContext}>
                  <Copy className="w-4 h-4 mr-2" />
                  Export Context
                </DropdownMenuItem>
              </>
            )}
            {showExport && matrixData && (
              <>
                <DropdownMenuSeparator />
                <DropdownMenuItem onClick={exportToXML}>
                  <FileCode className="w-4 h-4 mr-2" />
                  Export XML
                </DropdownMenuItem>
                <DropdownMenuItem onClick={saveMatrix}>
                  <Save className="w-4 h-4 mr-2" />
                  Save Matrix
                </DropdownMenuItem>
                {savedConfigs.length > 0 && (
                  <DropdownMenuItem onClick={() => setShowLoadDialog(true)}>
                    <FileText className="w-4 h-4 mr-2" />
                    Load Saved
                  </DropdownMenuItem>
                )}
              </>
            )}
          </DropdownMenuContent>
        </DropdownMenu>
      </div>

      {/* Error Message */}
      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-3 flex items-center">
          <AlertTriangle className="w-5 h-5 text-red-600 mr-2" />
          <span className="text-red-800">{error}</span>
        </div>
      )}

      {/* Main Content: grid first (takes space), chat on the right */}
      <div className="flex gap-3 flex-1 min-h-0 overflow-hidden">
        {/* AG Grid Matrix with Drag-and-Drop */}
        <div 
          className={`flex-1 min-w-0 ${showInsightsPanel ? 'w-2/3' : 'w-full'} relative flex flex-col`}
          style={{ height: 640, minHeight: 640 }}
          onDragOverCapture={handleDragOverCapture}
          onDragEnterCapture={handleDragEnterCapture}
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
        >
          {/* Drag overlay: document (PDF, etc.) */}
          {isDraggingDocument && (
            <div className="absolute inset-0 z-50 bg-primary/10 border-4 border-dashed border-primary rounded-lg flex items-center justify-center pointer-events-none">
              <div className="bg-white dark:bg-gray-900 rounded-lg p-6 shadow-lg text-center">
                <Upload className="h-12 w-12 mx-auto mb-4 text-primary" />
                <p className="text-lg font-semibold">Drop document to upload</p>
                <p className="text-sm text-muted-foreground mt-2">PDF, DOCX — uploads to this row and runs extraction</p>
              </div>
            </div>
          )}
          {/* Drag overlay: CSV import */}
          {isDraggingCSV && !isDraggingDocument && (
            <div className="absolute inset-0 z-50 bg-primary/10 border-4 border-dashed border-primary rounded-lg flex items-center justify-center pointer-events-none">
              <div className="bg-white dark:bg-gray-900 rounded-lg p-6 shadow-lg text-center">
                <Upload className="h-12 w-12 mx-auto mb-4 text-primary" />
                <p className="text-lg font-semibold">Drop CSV file to import</p>
                <p className="text-sm text-muted-foreground mt-2">Updates existing companies in matrix</p>
              </div>
            </div>
          )}

          {/* Hidden file input for document upload from cell dropdown (parent survives cell unmount) */}
          <input
            ref={uploadFileInputRef}
            type="file"
            className="hidden"
            accept=".pdf,.docx,.doc,.xlsx,.xls"
            onChange={async (e) => {
              const files = e.target.files;
              if (!files?.length || !uploadDocumentTarget) {
                e.target.value = '';
                return;
              }
              const { rowId, columnId } = uploadDocumentTarget;
              setUploadDocumentTarget(null);
              for (let i = 0; i < files.length; i++) {
                await handleUploadDocumentToCell(rowId, columnId, files[i]);
              }
              e.target.value = '';
            }}
          />
          
          <CellActionProvider
            value={{
              onRunCellAction,
              onOpenValuationPicker,
              onRequestUploadDocument,
              cellActionStatus,
            }}
          >
          <SuggestionsProvider
            value={{
              suggestions: visibleSuggestions,
              onAccept: handleSuggestionAccept,
              onReject: handleSuggestionReject,
            }}
          >
          {mode === 'portfolio' && isLoading && !matrixData?.rows?.length ? (
            <div className="flex-1 min-h-0 flex flex-col p-4 rounded-lg border bg-muted/30" style={{ height: 640, minHeight: 640 }}>
              <SkeletonTable rows={8} columns={12} />
            </div>
          ) : (
          <AGGridMatrix
            matrixData={currentMatrixData}
            mode={mode}
            availableActions={availableActions}
            onCellEdit={handleCellEdit}
            onStartCellEdit={handleCellDoubleClick}
            onCellActionResult={handleCellActionResult}
            onRunCellAction={onRunCellAction}
            onOpenValuationPicker={onOpenValuationPicker}
            onRequestUploadDocument={onRequestUploadDocument}
            actionInProgressRef={actionInProgressRef}
            onStartEditingCell={handleStartEditingCell}
            onWorkflowStart={(rowId, columnId, formula) => {
              // Set the cell value to the workflow formula, then trigger edit
              const currentData = matrixData || getDefaultMatrixData(mode, fundId);
              const row = currentData.rows.find((r) => r.id === rowId);
              const column = currentData.columns.find((c) => c.id === columnId);
              if (row && column) {
                // Update cell with formula
                const updatedRows = currentData.rows.map((r) => {
                  if (r.id === rowId) {
                    return {
                      ...r,
                      cells: {
                        ...r.cells,
                        [columnId]: {
                          ...r.cells[columnId],
                          value: formula,
                          displayValue: formula,
                          formula: formula,
                          source: 'formula' as const,
                          lastUpdated: new Date().toISOString(),
                        },
                      },
                    };
                  }
                  return r;
                });
                const updatedData: MatrixData = {
                  ...currentData,
                  rows: updatedRows,
                };
                setMatrixData(updatedData);
                onDataChange?.(updatedData);
                // Trigger cell edit to let user modify the formula
                setTimeout(() => {
                  if (startEditingCellRef) {
                    startEditingCellRef(rowId, columnId);
                  }
                }, 100);
              }
            }}
            onWorkflowRun={async (rowId, columnId, formula) => {
              // Run workflow immediately; handleCellEdit parses WORKFLOW, runs runWorkflow, applies results
              await handleCellEdit(rowId, columnId, formula);
            }}
            onRowEdit={onRowEdit}
            onRowDelete={onRowDelete || handleRowDelete}
            onRowDuplicate={onRowDuplicate}
            onRunValuation={useAgentPanel ? (rowId: string) => { handleRunValuationOpenPicker(rowId); return Promise.resolve(); } : onRunValuation}
            onRunPWERM={useAgentPanel ? (rowId) => {
              const colId = matrixData?.columns?.find((c) => /pwerm|valuation/i.test(c.id))?.id ?? 'valuation';
              return runActionWrapper('valuation_engine.pwerm', rowId, colId);
            } : onRunPWERM}
            onUploadDocument={onUploadDocument ?? handleDocumentUploadWithSuggest}
            onUploadDocumentToCell={handleUploadDocumentToCell}
            onEditColumn={handleEditColumn}
            onDeleteColumn={handleDeleteColumn}
            onAddRow={handleAddRowSimple}
            onAddColumn={handleAddColumnSimple}
            useAgentPanel={useAgentPanel}
            onSuggestChanges={async () => {
              await refreshSuggestions();
            }}
            onSourceChange={async (rowId, columnId, source) => {
                const currentData = matrixData || getDefaultMatrixData(mode, fundId);
                const column = currentData.columns.find((c) => c.id === columnId);

                const updatedRows = currentData.rows.map((r) => {
                  if (r.id !== rowId) return r;
                  const cell = (r.cells[columnId] || {}) as MatrixCell;
                  let value: any = cell.value;
                  let displayValue: string | undefined = cell.displayValue;

                  // When switching to manual, avoid showing [object Object] — normalize objects to a displayable value
                  if (source === 'manual' && typeof value === 'object' && value !== null && !Array.isArray(value)) {
                    const extracted =
                      (value as Record<string, unknown>).value ??
                      (value as Record<string, unknown>).fair_value ??
                      (value as Record<string, unknown>).displayValue ??
                      (value as Record<string, unknown>).display_value;
                    value =
                      typeof extracted === 'number' || typeof extracted === 'string' || extracted == null
                        ? extracted
                        : null;
                    const type = column?.type ?? 'text';
                    displayValue =
                      typeof cell.displayValue === 'string' && cell.displayValue
                        ? cell.displayValue
                        : formatCellValue(value ?? '', type);
                  }

                  return {
                    ...r,
                    cells: {
                      ...r.cells,
                      [columnId]: {
                        ...cell,
                        ...(value !== undefined && { value }),
                        ...(displayValue !== undefined && { displayValue }),
                        source: source as 'manual' | 'document' | 'api' | 'formula',
                        lastUpdated: new Date().toISOString(),
                      },
                    },
                  };
                });

                const updatedData: MatrixData = {
                  ...currentData,
                  rows: updatedRows,
                };

                setMatrixData(updatedData);
                onDataChange?.(updatedData);
              }}
              onValuationMethodChange={async (rowId, columnId, method) => {
                const currentData = matrixData || getDefaultMatrixData(mode, fundId);
                
                const row = currentData.rows.find(r => r.id === rowId);
                if (!row || !row.companyId) return;
                
                // Save valuation method preference to matrix_edits
                try {
                  await fetch('/api/matrix/cells', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                      company_id: row.companyId,
                      column_id: columnId,
                      old_value: row.cells[columnId]?.metadata?.valuationMethod || null,
                      new_value: method,
                      fund_id: fundId,
                      data_source: 'manual',
                      metadata: {
                        valuationMethod: method,
                        preference: true, // Mark as preference, not actual value change
                      },
                    }),
                  });
                } catch (err) {
                  console.warn('Failed to save valuation method preference:', err);
                }
                
                const updatedRows = matrixData.rows.map((r) => {
                  if (r.id === rowId) {
                    const existingCell = (r.cells[columnId] || {}) as MatrixCell;
                    const newCell: MatrixCell = {
                      ...existingCell,
                      value: existingCell.value,
                      metadata: {
                        ...existingCell.metadata,
                        valuationMethod: method,
                      },
                      lastUpdated: new Date().toISOString(),
                    };
                    return {
                      ...r,
                      cells: {
                        ...r.cells,
                        [columnId]: newCell,
                      },
                    };
                  }
                  return r;
                });
                
                const updatedData: MatrixData = {
                  ...matrixData,
                  rows: updatedRows,
                };
                
                setMatrixData(updatedData);
                onDataChange?.(updatedData);
                
                // Optionally trigger valuation calculation
                if (method !== 'auto') {
                  try {
                    // Call valuation API to recalculate with new method
                    const response = await fetch('/api/valuation/calculate', {
                      method: 'POST',
                      headers: { 'Content-Type': 'application/json' },
                      body: JSON.stringify({
                        companyId: row.companyId,
                        method,
                        context: { fundId },
                      }),
                    });
                    
                    if (response.ok) {
                      const result = (await response.json()) as Record<string, unknown>;
                      const v = result?.valuation as Record<string, unknown> | undefined;
                      const valuation = v?.fair_value ?? v?.valuation ?? result?.fair_value ?? result?.valuation;
                      if (valuation != null) {
                        const finalUpdatedRows = updatedRows.map((r) => {
                          if (r.id === rowId) {
                            const prev = r.cells[columnId] as MatrixCell | undefined;
                            return {
                              ...r,
                              cells: {
                                ...r.cells,
                                [columnId]: {
                                  ...prev,
                                  value: valuation,
                                  displayValue: formatCurrency(Number(valuation)),
                                  source: 'api' as const,
                                  metadata: {
                                    ...prev?.metadata,
                                    method: (result.method as string) || method,
                                  },
                                },
                              },
                            };
                          }
                          return r;
                        });
                        
                        const finalData: MatrixData = {
                          ...updatedData,
                          rows: finalUpdatedRows,
                        };
                        
                        setMatrixData(finalData);
                        onDataChange?.(finalData);
                      }
                    }
                  } catch (err) {
                    console.error('Error calculating valuation:', err);
                  }
                }
              }}
              onFormulaBuilder={(rowId, columnId) => {
                // Open formula builder dialog
                setEditingCell({ rowId, columnId });
                const currentData = matrixData || getDefaultMatrixData(mode, fundId);
                const cell = currentData.rows.find(r => r.id === rowId)?.cells[columnId];
                setEditValue(cell?.formula || '=');
              }}
              onLinkDocument={async (rowId, columnId) => {
                // Handle document linking
                const currentData = matrixData || getDefaultMatrixData(mode, fundId);
                const row = currentData.rows.find(r => r.id === rowId);
                if (row?.companyId && fundId) {
                  const { uploadDocumentInCell } = await import('@/lib/matrix/matrix-api-service');
                  // This would typically open a file picker dialog
                  // For now, we'll just log it
                  console.log('Link document for', rowId, columnId);
                }
              }}
            />
          )}
          </SuggestionsProvider>
          </CellActionProvider>
        </div>

        {/* Agent Panel (chat) — right side */}
        {showChartViewport && useAgentPanel && (
          <div className="w-[260px] min-w-[220px] max-w-[min(280px,100%)] flex-shrink-0 flex flex-col min-h-0 border-l bg-card/50 overflow-hidden">
            <AgentPanel
              matrixData={matrixData}
              fundId={fundId}
              mode={mode}
              isOpen={showChartViewport}
              onOpenChange={setShowChartViewport}
              suggestions={visibleSuggestions}
              insights={documentInsights}
              suggestionsLoading={suggestionsLoading}
              suggestionsError={suggestionsError}
              refreshSuggestions={refreshSuggestions}
              availableActions={availableActions}
              toolCallEntries={toolCallEntries}
              planSteps={planStepsState}
              onRunService={useAgentPanel ? runActionWrapper : onRunService}
              onRetrySuggestion={useAgentPanel ? (suggestion) => {
                const actionId = suggestion.sourceService ?? suggestion.sourceDocumentName ?? '';
                if (actionId && suggestion.rowId && suggestion.columnId) {
                  return runActionWrapper(actionId, suggestion.rowId, suggestion.columnId);
                }
              } : onRetrySuggestion}
              onExportRequest={handleExportRequest}
              onRequestChart={handleRequestChart}
              onUploadDocument={handleUploadDocument}
              onPlanStepsUpdate={setPlanStepsState}
              onCellEdit={handleCellEdit}
              onGridCommandsFromBackend={handleGridCommandsFromBackend}
              onToolCallLog={onToolCallLog}
              onSuggestionAccept={handleSuggestionAccept}
              onSuggestionReject={handleSuggestionReject}
              onApplySuggestions={handleApplySuggestions}
              memoSections={memoSections}
              onMemoUpdates={(updates) => {
                if (updates.action === 'append') {
                  setMemoSections(prev => [...prev, ...updates.sections as DocumentSection[]]);
                } else {
                  setMemoSections(updates.sections as DocumentSection[]);
                }
              }}
              onAnalysisReady={handleAnalysisReady}
            />
          </div>
        )}

        {/* Insights Panel */}
        {showInsightsPanel && matrixData && (
          <div className="w-1/3">
            <MatrixInsights matrixData={matrixData} />
          </div>
        )}

        {/* Right-side ChartViewport only when not using AgentPanel (charts secondary) */}
        {showChartViewport && !useAgentPanel && (
          <div className="w-[260px] min-w-[220px] flex-shrink-0 flex flex-col min-h-0 border-l bg-card/50 overflow-hidden">
            <ChartViewport
                variant="canvas"
                matrixData={matrixData}
                fundId={fundId}
                isOpen={showChartViewport}
                onOpenChange={setShowChartViewport}
                initialTab={viewportActiveTab}
                suggestions={visibleSuggestions}
                insights={documentInsights}
                suggestionsLoading={suggestionsLoading}
                suggestionsError={suggestionsError}
                refreshSuggestions={refreshSuggestions}
                onSuggestionAccept={handleSuggestionAccept}
                onSuggestionReject={handleSuggestionReject}
                onApplySuggestions={handleApplySuggestions}
                memoSections={memoSections}
                onMemoChange={setMemoSections}
                onMemoExportPdf={async () => {
                  const { exportMemoPdf } = await import('@/lib/memo-pdf-export');
                  await exportMemoPdf(memoSections, 'Investment Memo', memoContainerRef.current);
                }}
                memoContainerRef={memoContainerRef}
              />
          </div>
        )}
      </div>

      {/* Memo panel below grid — shows whenever agent has added content beyond the default heading+empty paragraph */}
      {memoSections.length > 0 && memoSections.some(s => s.type !== 'heading1' && s.content?.trim()) && (
        <div className="border-t bg-card/50">
          <button
            className="w-full flex items-center justify-between px-4 py-1.5 text-xs font-medium text-muted-foreground hover:text-foreground hover:bg-muted/50 transition-colors"
            onClick={() => setMemoPanelExpanded(prev => !prev)}
          >
            <span className="flex items-center gap-1.5">
              <FileText className="h-3 w-3" />
              {memoSections.find(s => s.type === 'heading1')?.content || 'Working Memo'}
            </span>
            <span className="flex items-center gap-2">
              <Pin
                className="h-3 w-3 cursor-pointer hover:text-primary"
                onClick={(e) => {
                  e.stopPropagation();
                  const companyName = memoPanelContext.companies?.[0]?.company || memoPanelContext.companies?.[0]?.name;
                  if (companyName && fundId) {
                    const companyRow = matrixData?.rows.find(r => r.companyName?.toLowerCase().includes(companyName.toLowerCase()));
                    if (companyRow?.companyId) {
                      fetch('/api/matrix/cell-edit', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                          company_id: companyRow.companyId,
                          column_id: 'extra_data',
                          new_value: { agent_memo: { sections: memoSections, pinned_at: new Date().toISOString() } },
                          fund_id: fundId,
                          data_source: 'agent',
                        }),
                      }).then(() => toast.success('Memo pinned to company')).catch(() => toast.error('Failed to pin'));
                    }
                  }
                }}
              />
              <span className="text-[10px] text-muted-foreground/60">{memoSections.length} sections</span>
              {memoPanelExpanded ? <ChevronDown className="h-3.5 w-3.5" /> : <ChevronUp className="h-3.5 w-3.5" />}
            </span>
          </button>
          {memoPanelExpanded && (
            <div className="max-h-[340px] overflow-y-auto">
              <MemoEditor
                sections={memoSections}
                onChange={setMemoSections}
                compact
                containerRef={memoContainerRef}
                onExportPdf={async () => {
                  const { exportMemoPdf } = await import('@/lib/memo-pdf-export');
                  await exportMemoPdf(memoSections, 'Investment Memo', memoContainerRef.current);
                }}
              />
            </div>
          )}
        </div>
      )}

      {/* Valuation method picker (parent-level, survives cell unmount) */}
      <Dialog open={!!valuationPicker} onOpenChange={(open) => !open && setValuationPicker(null)}>
        <DialogContent className="sm:max-w-md" onPointerDownOutside={(e) => e.stopPropagation()}>
          <DialogHeader>
            <DialogTitle>Run Valuation — choose method</DialogTitle>
            <DialogDescription>Select a valuation method to run for this row.</DialogDescription>
          </DialogHeader>
          <div className="grid gap-2 py-4 max-h-[60vh] overflow-y-auto">
            {(() => {
              const grouped = VALUATION_METHODS.reduce((acc, m) => {
                if (!acc[m.category]) acc[m.category] = [];
                acc[m.category].push(m);
                return acc;
              }, {} as Record<string, typeof VALUATION_METHODS>);
              return Object.entries(grouped).map(([category, methods]) => (
                <div key={category}>
                  <div className="px-0 py-1 text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                    {category}
                  </div>
                  {methods.map((method) => (
                    <Button
                      key={method.value}
                      variant="outline"
                      className="justify-start h-auto py-2 text-left w-full"
                      onClick={async () => {
                        if (!valuationPicker) return;
                        const { rowId, columnId, rowData, matrixData: md } = valuationPicker;
                        const actionId = method.value === 'auto' ? 'valuation_engine.auto' : `valuation_engine.${method.value}`;
                        const inputs = buildActionInputs(actionId, rowData, columnId, md);
                        if (method.value !== 'auto') inputs.method = method.value;
                        setValuationPicker(null);
                        try {
                          await onRunCellAction({
                            action_id: actionId,
                            row_id: rowId,
                            column_id: columnId,
                            inputs,
                            mode: mode ?? 'portfolio',
                            fund_id: fundId,
                            company_id: rowData?.companyId,
                          });
                        } catch {
                          // toast handled in onRunCellAction
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
              ));
            })()}
          </div>
        </DialogContent>
      </Dialog>

      <Dialog open={showLoadDialog} onOpenChange={setShowLoadDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Load Saved Matrix</DialogTitle>
            <DialogDescription>Select a saved matrix configuration to load</DialogDescription>
          </DialogHeader>
          <div className="space-y-2 max-h-96 overflow-y-auto">
            {savedConfigs.map((config) => (
              <div key={config.id} className="p-3 border rounded-lg cursor-pointer hover:bg-gray-50" onClick={() => loadMatrix(config)}>
                <div className="font-medium">{config.name}</div>
                <div className="text-sm text-gray-500">{new Date(config.timestamp).toLocaleString()}</div>
              </div>
            ))}
          </div>
        </DialogContent>
      </Dialog>

      {/* Add Column Dialog */}
      <Dialog open={showAddColumnDialog} onOpenChange={(open) => {
        setShowAddColumnDialog(open);
        if (!open) {
          setError(null);
          setNewColumn({ name: '', type: 'text', service: '' });
        }
      }}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Add Column</DialogTitle>
            <DialogDescription>
              Add a new column to the matrix. Columns can be persisted for portfolio mode.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            {error && (
              <div className="bg-red-50 border border-red-200 text-red-800 px-4 py-3 rounded-md flex items-center gap-2">
                <AlertTriangle className="w-5 h-5" />
                <span>{error}</span>
              </div>
            )}
            <div>
              <Label htmlFor="columnName">Column Name</Label>
              <Input
                id="columnName"
                value={newColumn.name}
                onChange={(e) => {
                  setNewColumn({ ...newColumn, name: e.target.value });
                  setError(null);
                }}
                placeholder="Enter column name"
              />
            </div>
            <div>
              <Label htmlFor="columnType">Column Type</Label>
              <Select
                value={newColumn.type}
                onValueChange={(value) => setNewColumn({ ...newColumn, type: value as MatrixColumn['type'] })}
              >
                <SelectTrigger>
                  <SelectValue placeholder="Select type" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="text">Text</SelectItem>
                  <SelectItem value="number">Number</SelectItem>
                  <SelectItem value="currency">Currency</SelectItem>
                  <SelectItem value="percentage">Percentage</SelectItem>
                  <SelectItem value="date">Date</SelectItem>
                  <SelectItem value="boolean">Boolean</SelectItem>
                  <SelectItem value="formula">Formula</SelectItem>
                  <SelectItem value="sparkline">Sparkline</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div>
              <Label htmlFor="columnService">Service (Optional)</Label>
              <Input
                id="columnService"
                value={newColumn.service}
                onChange={(e) => setNewColumn({ ...newColumn, service: e.target.value })}
                placeholder="e.g., valuation_engine, pwerm_calculator"
              />
            </div>
            <div className="flex justify-end gap-2 pt-4">
              <Button
                variant="outline"
                onClick={() => {
                  setShowAddColumnDialog(false);
                  setNewColumn({ name: '', type: 'text', service: '' });
                  setError(null);
                }}
              >
                Cancel
              </Button>
              <Button onClick={handleAddColumn} disabled={!newColumn.name.trim()}>
                <Plus className="w-4 h-4 mr-2" />
                Add Column
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>

      {/* Cell edit dialog: open when editingCell is set */}
      <Dialog
        open={!!editingCell}
        onOpenChange={(open) => {
          if (!open) handleCellCancel();
        }}
      >
        <DialogContent className="sm:max-w-lg" onPointerDownOutside={(e) => e.stopPropagation()}>
          <DialogHeader>
            <DialogTitle>{editValue.trim().startsWith('=') ? 'Formula' : 'Edit Cell'}</DialogTitle>
            <DialogDescription>
              {editValue.trim().startsWith('=') ? 'Use =SUM(...), =WORKFLOW("actionIds", "all"), or other supported functions.' : 'Enter a new value for this cell.'}
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 py-4">
            <div className="grid gap-2">
              <Label htmlFor="formula-input">Formula</Label>
              <Textarea
                id="formula-input"
                value={editValue}
                onChange={(e) => setEditValue(e.target.value)}
                placeholder="=SUM(A1:A5) or =WORKFLOW(&quot;runPWERM&quot;, &quot;current&quot;)"
                className="font-mono text-sm min-h-[80px]"
                autoFocus
              />
            </div>
            <div className="flex justify-end gap-2">
              <Button type="button" variant="outline" onClick={handleCellCancel}>
                Cancel
              </Button>
              <Button type="button" onClick={handleCellSave}>
                Apply
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>

      {/* Add Company Dialog removed - companies are now added directly in the grid */}


      {/* Citations Section */}
      {citations && citations.length > 0 && (
        <div className="mt-6 border-t pt-6">
          <div className="max-w-full mx-auto px-4 sm:px-6 lg:px-8">
            <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4 flex items-center">
              <LinkIcon className="w-5 h-5 mr-2" />
              Sources & Citations
            </h3>
            <CitationDisplay citations={citations} format="both" />
          </div>
        </div>
      )}

    </div>
  );
}
