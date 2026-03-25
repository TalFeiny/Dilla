'use client';

import React, { useState, useCallback, useEffect } from 'react';
import dynamic from 'next/dynamic';
import { Button } from '@/components/ui/button';
import {
  Heading2, Bold, List, Download, Loader2, Table, X, Trash2,
  BarChart3, LineChart, DollarSign, Sliders, Activity,
  GitBranch, Link2, PieChart, TrendingUp, Gauge, Calculator,
  Users, Sparkles, Brain, ChevronDown as ChevronDownIcon,
  Play, Zap, FileText, MessageSquare, Send,
} from 'lucide-react';
import { Input } from '@/components/ui/input';
import { useMemoContextSafe } from './MemoContext';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
  DropdownMenuLabel,
} from '@/components/ui/dropdown-menu';

// Interactive section components — lazy loaded
import { PnlSection } from './sections/PnlSection';
import { BalanceSheetSection } from './sections/BalanceSheetSection';
import { CashFlowSection } from './sections/CashFlowSection';
import { DriversSection } from './sections/DriversSection';
import { MetricsSection } from './sections/MetricsSection';
import { ScenarioSection } from './sections/ScenarioSection';
import { CascadeSection } from './sections/CascadeSection';
import { CapTableSection } from './sections/CapTableSection';
import { WaterfallSection } from './sections/WaterfallSection';
import { ValuationSection } from './sections/ValuationSection';
import { MonteCarloSection } from './sections/MonteCarloSection';
import { SensitivitySection } from './sections/SensitivitySection';
import { ForecastMethodSection } from './sections/ForecastMethodSection';
import { BudgetVarianceSection } from './sections/BudgetVarianceSection';
import { HealthScoreSection } from './sections/HealthScoreSection';
import { CostOfCapitalSection } from './sections/CostOfCapitalSection';
import { StakeholderSection } from './sections/StakeholderSection';
import { AINarrativeSection } from './sections/AINarrativeSection';

/** Check if a section type is an interactive (non-text) section */
function isInteractiveSection(type: string): boolean {
  return [
    'pnl', 'balance_sheet', 'cash_flow', 'drivers', 'metrics', 'scenario', 'cascade',
    'cap_table', 'waterfall', 'valuation', 'monte_carlo', 'sensitivity',
    'forecast_method', 'budget_variance', 'health_score', 'cost_of_capital',
    'stakeholder', 'ai_narrative',
  ].includes(type);
}

const TableauLevelCharts = dynamic(
  () => import('@/components/charts/TableauLevelCharts'),
  { ssr: false, loading: () => <div className="h-[200px] animate-pulse bg-muted rounded" /> }
);

export interface TodoItem {
  id: string;
  label: string;
  status: 'pending' | 'running' | 'done' | 'failed';
  action_id?: string;
}

export interface SkillChainStep {
  id: string;
  action_id: string;
  label: string;
  parallel?: boolean;
  depends_on?: string[];
}

export interface DocumentSection {
  type: 'heading1' | 'heading2' | 'heading3' | 'paragraph' | 'chart' | 'list' | 'quote' | 'code' | 'image' | 'table' | 'todo_list' | 'skill_chain' | 'redline'
    | 'pnl' | 'balance_sheet' | 'cash_flow' | 'drivers' | 'metrics' | 'scenario' | 'cascade'
    | 'cap_table' | 'waterfall' | 'valuation' | 'monte_carlo' | 'sensitivity'
    | 'forecast_method' | 'budget_variance' | 'health_score' | 'cost_of_capital'
    | 'stakeholder' | 'ai_narrative';
  content?: string;
  chart?: {
    type: string;
    title?: string;
    data: Record<string, unknown> | unknown[];
    renderType?: string;
    responsive?: boolean;
  };
  items?: string[];
  imageUrl?: string;
  imageCaption?: string;
  table?: {
    headers: string[];
    rows: (string | number)[][];
    caption?: string;
    formatting?: Record<number, 'currency' | 'percentage' | 'number' | 'text'>;
  };
  citations?: Array<{
    type: 'source' | 'document' | 'reasoning';
    title: string;
    url?: string;
    document_id?: string;
    content?: string;
  }>;
  /** For todo_list sections */
  todos?: TodoItem[];
  /** For skill_chain sections */
  skill_chain?: SkillChainStep[];
  /** For redline sections — track changes between versions */
  redline?: {
    original: string;
    revised: string;
    reasoning: string;
    clause_type?: string;
  };
  /** Whether this section is draggable context */
  is_context?: boolean;
  /** Chart ID for live chart rebuilds (Layer 3) */
  chartId?: number;
}

export interface MemoEditorProps {
  sections: DocumentSection[];
  onChange: (sections: DocumentSection[]) => void;
  readOnly?: boolean;
  compact?: boolean;
  onExportPdf?: () => void;
  exportingPdf?: boolean;
  /** Callback when a TODO item status changes */
  onTodoToggle?: (sectionIdx: number, todoId: string, newStatus: TodoItem['status']) => void;
  /** Callback when user clicks execute on a skill chain step */
  onSkillExecute?: (sectionIdx: number, stepId: string) => void;
  /** Expose the container ref so callers can pass it to PDF export for chart capture */
  containerRef?: React.RefObject<HTMLDivElement | null>;
}

function formatTableCell(value: string | number, format?: string): string {
  if (typeof value === 'number') {
    if (format === 'currency') {
      if (Math.abs(value) >= 1e9) return `$${(value / 1e9).toFixed(1)}B`;
      if (Math.abs(value) >= 1e6) return `$${(value / 1e6).toFixed(1)}M`;
      if (Math.abs(value) >= 1e3) return `$${(value / 1e3).toFixed(0)}K`;
      return `$${value.toLocaleString()}`;
    }
    if (format === 'percentage') return `${(value * 100).toFixed(1)}%`;
    return value.toLocaleString();
  }
  return String(value ?? '');
}

/** Strip dangerous HTML (scripts, iframes, event handlers) but preserve formatting. */
function sanitizeHtml(html: string): string {
  return html
    .replace(/<script\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/script>/gi, '')
    .replace(/<iframe\b[^<]*(?:(?!<\/iframe>)<[^<]*)*<\/iframe>/gi, '')
    .replace(/\son\w+="[^"]*"/gi, '')
    .replace(/\son\w+='[^']*'/gi, '');
}

/** Extract sanitized innerHTML from a contentEditable blur event. */
function getEditableHtml(e: React.FocusEvent<HTMLElement>): string {
  return sanitizeHtml(e.currentTarget.innerHTML);
}

/** Generate a stable key for a section that survives drag-reorder. */
function sectionKey(section: DocumentSection, idx: number): string {
  const content = section.content || section.items?.join(',') || '';
  return `${section.type}-${idx}-${content.slice(0, 30)}`;
}

export function MemoEditor({ sections, onChange, readOnly = false, compact = false, onExportPdf, exportingPdf, onTodoToggle, onSkillExecute, containerRef }: MemoEditorProps) {
  const [dragOverIdx, setDragOverIdx] = useState<number | null>(null);
  const [selectedIdx, setSelectedIdx] = useState<number>(0);

  // Clamp selectedIdx when sections shrink — in useEffect to avoid setState during render
  const safeIdx = sections.length === 0 ? -1 : Math.min(selectedIdx, sections.length - 1);
  React.useEffect(() => {
    if (safeIdx !== selectedIdx && safeIdx >= 0) {
      setSelectedIdx(safeIdx);
    }
  }, [safeIdx, selectedIdx]);

  const updateSection = useCallback((idx: number, updates: Partial<DocumentSection>) => {
    const next = [...sections];
    next[idx] = { ...next[idx], ...updates };
    onChange(next);
  }, [sections, onChange]);

  const addSection = useCallback((afterIdx: number, section: DocumentSection) => {
    const next = [...sections];
    next.splice(afterIdx + 1, 0, section);
    onChange(next);
    setSelectedIdx(afterIdx + 1);
  }, [sections, onChange]);

  const removeSection = useCallback((idx: number) => {
    if (sections.length <= 1) {
      // Last section — replace with empty paragraph instead of blocking delete
      onChange([{ type: 'paragraph', content: '' }]);
      setSelectedIdx(0);
      return;
    }
    onChange(sections.filter((_, i) => i !== idx));
    setSelectedIdx(Math.max(0, idx - 1));
  }, [sections, onChange]);

  // ---- Backend-connected actions via MemoContext ----
  const ctx = useMemoContextSafe();
  const [actionLoading, setActionLoading] = useState<string | null>(null);

  /** Build Forecast — calls backend with chosen method, fills grid */
  const handleBuildForecast = useCallback(async (method: string = 'auto') => {
    if (!ctx) return;
    setActionLoading('forecast');
    try {
      await ctx.buildForecast({
        method,
        metric: 'revenue',
        forecast_periods: 12,
        granularity: 'monthly',
      });
    } finally {
      setActionLoading(null);
    }
  }, [ctx]);

  /** Fork Scenario — adds scenario section with NL input for "what if..." */
  const handleForkScenario = useCallback(() => {
    addSection(safeIdx, { type: 'scenario' });
  }, [addSection, safeIdx]);

  /** Adjust Drivers — adds interactive driver sliders connected to grid */
  const handleAdjustDrivers = useCallback(() => {
    addSection(safeIdx, { type: 'drivers' });
  }, [addSection, safeIdx]);

  /** Run Model — recomputes everything from current grid state + drivers */
  const handleRunModel = useCallback(async () => {
    if (!ctx) return;
    setActionLoading('model');
    try {
      await ctx.buildForecast({ method: 'driver-based', metric: 'revenue', forecast_periods: 12, granularity: 'monthly', recompute: true });
    } finally {
      setActionLoading(null);
    }
  }, [ctx]);

  /** Board Summary — generates AI executive summary from all grid + memo data */
  const handleBoardSummary = useCallback(async () => {
    if (!ctx) return;
    setActionLoading('summary');
    try {
      const pnlRows = ctx.getPnlRows();
      const cols = ctx.matrixData.columns.filter(c => c.id !== 'lineItem');
      const latestCol = cols[cols.length - 1];
      const summary: Record<string, any> = {};
      if (latestCol) {
        for (const row of pnlRows) {
          if (row.cells[latestCol.id]) {
            summary[row.id] = row.cells[latestCol.id].value;
          }
        }
      }
      const narrative = await ctx.requestNarrative('board_summary', {
        pnlSummary: summary,
        metrics: ctx.metrics,
        branchCount: ctx.activeBranches.length,
        periodCount: cols.length,
      });
      // Add AI narrative section with the generated content
      addSection(safeIdx, { type: 'ai_narrative', content: narrative });
    } finally {
      setActionLoading(null);
    }
  }, [ctx, addSection, safeIdx]);

  /** Compare Scenarios — triggers scenario comparison chart */
  const handleCompareScenarios = useCallback(() => {
    addSection(safeIdx, { type: 'scenario' });
  }, [addSection, safeIdx]);

  return (
    <div className={`flex flex-col h-full memo-editor ${compact ? 'text-xs' : 'text-sm'}`}>
      {/* Google Docs-level styling + print styles */}
      <style>{`
        .memo-editor {
          font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
        }
        .memo-sections-scroll {
          max-width: 816px;
          margin: 0 auto;
          width: 100%;
        }
        .memo-section-wrapper {
          transition: background-color 0.15s ease, box-shadow 0.15s ease;
        }
        .memo-section-wrapper[data-drag-over="true"] {
          box-shadow: 0 -2px 0 0 #4e79a7;
        }
        .memo-section-wrapper[draggable="true"] {
          cursor: grab;
        }
        .memo-section-wrapper[draggable="true"]:active {
          cursor: grabbing;
          opacity: 0.6;
        }
        .memo-editor h1 { font-size: 1.5rem; line-height: 1.3; letter-spacing: -0.01em; margin-bottom: 0.25rem; }
        .memo-editor h2 { font-size: 1.2rem; line-height: 1.35; letter-spacing: -0.005em; margin-top: 1.5rem; margin-bottom: 0.25rem; border-bottom: 1px solid hsl(var(--border)); padding-bottom: 0.25rem; }
        .memo-editor h3 { font-size: 1rem; line-height: 1.4; margin-top: 1rem; }
        .memo-editor p { line-height: 1.65; margin-bottom: 0.5rem; }
        .memo-editor table { border-collapse: separate; border-spacing: 0; border: 1px solid hsl(var(--border)); border-radius: 6px; overflow: hidden; }
        .memo-editor table th { background: hsl(var(--muted)); font-weight: 600; text-align: left; padding: 8px 12px; border-bottom: 2px solid hsl(var(--border)); position: sticky; top: 0; z-index: 1; }
        .memo-editor table td { padding: 6px 12px; border-bottom: 1px solid hsl(var(--border)); }
        .memo-editor table tr:last-child td { border-bottom: none; }
        .memo-editor table tr:nth-child(even) td { background: hsl(var(--muted) / 0.3); }
        .memo-editor table tr:hover td { background: hsl(var(--muted) / 0.5); }
        .memo-editor .chart-container { aspect-ratio: 16 / 9; border-radius: 8px; overflow: hidden; border: 1px solid hsl(var(--border)); }
        .memo-todo-item { display: flex; align-items: center; gap: 8px; padding: 6px 0; border-bottom: 1px solid hsl(var(--border) / 0.5); }
        .memo-todo-item:last-child { border-bottom: none; }
        .memo-todo-check { width: 18px; height: 18px; border-radius: 4px; border: 2px solid hsl(var(--muted-foreground)); cursor: pointer; display: flex; align-items: center; justify-content: center; flex-shrink: 0; }
        .memo-todo-check[data-status="done"] { background: #59a14f; border-color: #59a14f; color: white; }
        .memo-todo-check[data-status="running"] { background: #f28e2c; border-color: #f28e2c; animation: pulse 1.5s infinite; }
        .memo-todo-check[data-status="failed"] { background: #e15759; border-color: #e15759; color: white; }
        .memo-skill-chain { display: flex; align-items: center; gap: 4px; flex-wrap: wrap; }
        .memo-skill-step { padding: 6px 12px; border-radius: 6px; border: 1px solid hsl(var(--border)); font-size: 12px; cursor: pointer; transition: all 0.15s; }
        .memo-skill-step:hover { background: hsl(var(--muted)); }
        .memo-skill-arrow { color: hsl(var(--muted-foreground)); font-size: 14px; }
        .memo-context-badge { display: inline-flex; align-items: center; gap: 4px; padding: 2px 8px; background: hsl(var(--muted)); border-radius: 4px; font-size: 10px; color: hsl(var(--muted-foreground)); margin-bottom: 4px; }
        @media print {
          .memo-editor { background: white !important; color: black !important; }
          .memo-editor [data-toolbar] { display: none !important; }
          .memo-editor .group:hover { background: none !important; }
          .memo-editor .ring-1 { box-shadow: none !important; }
          .memo-editor button.absolute { display: none !important; }
          .memo-editor table { page-break-inside: avoid; }
          .memo-editor .chart-container { page-break-inside: avoid; max-height: 280px; }
          .memo-editor h1, .memo-editor h2, .memo-editor h3 { page-break-after: avoid; }
          @page { margin: 2cm; size: A4; }
        }
        @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.5; } }
      `}</style>
      {/* Toolbar — Section Catalog */}
      {!readOnly && (
        <div data-toolbar className="flex items-center gap-1 px-2 py-1 border-b shrink-0 flex-wrap print:hidden">
          {/* Text sections */}
          <Button variant="ghost" size="sm" className="h-6 w-6 p-0" title="Add heading" onClick={() => addSection(safeIdx, { type: 'heading2', content: 'New Section' })}>
            <Heading2 className="h-3 w-3" />
          </Button>
          <Button variant="ghost" size="sm" className="h-6 w-6 p-0" title="Add paragraph" onClick={() => addSection(safeIdx, { type: 'paragraph', content: '' })}>
            <Bold className="h-3 w-3" />
          </Button>
          <Button variant="ghost" size="sm" className="h-6 w-6 p-0" title="Add list" onClick={() => addSection(safeIdx, { type: 'list', items: [''] })}>
            <List className="h-3 w-3" />
          </Button>
          <Button variant="ghost" size="sm" className="h-6 w-6 p-0" title="Add table" onClick={() => addSection(safeIdx, { type: 'table', table: { headers: ['Column 1', 'Column 2'], rows: [['', '']], caption: '' } })}>
            <Table className="h-3 w-3" />
          </Button>

          <div className="w-px h-4 bg-border mx-0.5" />

          {/* Financial sections */}
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="ghost" size="sm" className="h-6 gap-1 text-[11px] px-1.5">
                <BarChart3 className="h-3 w-3" /> Financial <ChevronDownIcon className="h-2.5 w-2.5" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="start" className="w-48">
              <DropdownMenuLabel className="text-[10px]">Financial Statements</DropdownMenuLabel>
              <DropdownMenuItem onClick={() => addSection(safeIdx, { type: 'pnl' })}>
                <BarChart3 className="h-3 w-3 mr-2" /> P&L
              </DropdownMenuItem>
              <DropdownMenuItem onClick={() => addSection(safeIdx, { type: 'balance_sheet' })}>
                <DollarSign className="h-3 w-3 mr-2" /> Balance Sheet
              </DropdownMenuItem>
              <DropdownMenuItem onClick={() => addSection(safeIdx, { type: 'cash_flow' })}>
                <LineChart className="h-3 w-3 mr-2" /> Cash Flow
              </DropdownMenuItem>
              <DropdownMenuItem onClick={() => addSection(safeIdx, { type: 'metrics' })}>
                <Activity className="h-3 w-3 mr-2" /> Metrics
              </DropdownMenuItem>
              <DropdownMenuSeparator />
              <DropdownMenuLabel className="text-[10px]">Forecasting</DropdownMenuLabel>
              <DropdownMenuItem onClick={() => addSection(safeIdx, { type: 'forecast_method' })}>
                <Brain className="h-3 w-3 mr-2" /> Forecast Method
              </DropdownMenuItem>
              <DropdownMenuItem onClick={() => addSection(safeIdx, { type: 'budget_variance' })}>
                <TrendingUp className="h-3 w-3 mr-2" /> Budget Variance
              </DropdownMenuItem>
              <DropdownMenuItem onClick={() => addSection(safeIdx, { type: 'health_score' })}>
                <Gauge className="h-3 w-3 mr-2" /> Health Score
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>

          {/* Analysis sections */}
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="ghost" size="sm" className="h-6 gap-1 text-[11px] px-1.5">
                <Sliders className="h-3 w-3" /> Analysis <ChevronDownIcon className="h-2.5 w-2.5" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="start" className="w-48">
              <DropdownMenuItem onClick={() => addSection(safeIdx, { type: 'drivers' })}>
                <Sliders className="h-3 w-3 mr-2" /> Drivers
              </DropdownMenuItem>
              <DropdownMenuItem onClick={() => addSection(safeIdx, { type: 'sensitivity' })}>
                <Activity className="h-3 w-3 mr-2" /> Sensitivity
              </DropdownMenuItem>
              <DropdownMenuItem onClick={() => addSection(safeIdx, { type: 'monte_carlo' })}>
                <TrendingUp className="h-3 w-3 mr-2" /> Monte Carlo
              </DropdownMenuItem>
              <DropdownMenuSeparator />
              <DropdownMenuLabel className="text-[10px]">Scenarios</DropdownMenuLabel>
              <DropdownMenuItem onClick={() => addSection(safeIdx, { type: 'scenario' })}>
                <GitBranch className="h-3 w-3 mr-2" /> Scenario (What if...)
              </DropdownMenuItem>
              <DropdownMenuItem onClick={() => addSection(safeIdx, { type: 'cascade' })}>
                <Link2 className="h-3 w-3 mr-2" /> Cascade
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>

          {/* Capital sections */}
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="ghost" size="sm" className="h-6 gap-1 text-[11px] px-1.5">
                <PieChart className="h-3 w-3" /> Capital <ChevronDownIcon className="h-2.5 w-2.5" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="start" className="w-48">
              <DropdownMenuItem onClick={() => addSection(safeIdx, { type: 'cap_table' })}>
                <PieChart className="h-3 w-3 mr-2" /> Cap Table
              </DropdownMenuItem>
              <DropdownMenuItem onClick={() => addSection(safeIdx, { type: 'waterfall' })}>
                <BarChart3 className="h-3 w-3 mr-2" /> Waterfall
              </DropdownMenuItem>
              <DropdownMenuItem onClick={() => addSection(safeIdx, { type: 'valuation' })}>
                <DollarSign className="h-3 w-3 mr-2" /> Valuation
              </DropdownMenuItem>
              <DropdownMenuItem onClick={() => addSection(safeIdx, { type: 'cost_of_capital' })}>
                <Calculator className="h-3 w-3 mr-2" /> Cost of Capital
              </DropdownMenuItem>
              <DropdownMenuItem onClick={() => addSection(safeIdx, { type: 'stakeholder' })}>
                <Users className="h-3 w-3 mr-2" /> Stakeholder
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>

          {/* Actions — backend-connected operations that sync with AG Grid */}
          {ctx && (
            <>
              <div className="w-px h-4 bg-border mx-0.5" />
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button variant="ghost" size="sm" className="h-6 gap-1 text-[11px] px-1.5">
                    <Zap className="h-3 w-3" /> Actions <ChevronDownIcon className="h-2.5 w-2.5" />
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="start" className="w-52">
                  <DropdownMenuLabel className="text-[10px]">Build Forecast</DropdownMenuLabel>
                  <DropdownMenuItem onClick={() => handleBuildForecast('auto')} disabled={!!actionLoading}>
                    {actionLoading === 'forecast' ? <Loader2 className="h-3 w-3 mr-2 animate-spin" /> : <Play className="h-3 w-3 mr-2" />}
                    Auto (best fit)
                  </DropdownMenuItem>
                  <DropdownMenuItem onClick={() => handleBuildForecast('driver-based')} disabled={!!actionLoading}>
                    <Sliders className="h-3 w-3 mr-2" /> Driver-based
                  </DropdownMenuItem>
                  <DropdownMenuItem onClick={() => handleBuildForecast('linear')} disabled={!!actionLoading}>
                    <TrendingUp className="h-3 w-3 mr-2" /> Regression
                  </DropdownMenuItem>
                  <DropdownMenuItem onClick={() => handleBuildForecast('seasonal')} disabled={!!actionLoading}>
                    <Activity className="h-3 w-3 mr-2" /> Seasonal
                  </DropdownMenuItem>
                  <DropdownMenuSeparator />
                  <DropdownMenuLabel className="text-[10px]">Model</DropdownMenuLabel>
                  <DropdownMenuItem onClick={handleRunModel} disabled={!!actionLoading}>
                    {actionLoading === 'model' ? <Loader2 className="h-3 w-3 mr-2 animate-spin" /> : <Zap className="h-3 w-3 mr-2" />}
                    Run Model (recompute)
                  </DropdownMenuItem>
                  <DropdownMenuItem onClick={handleAdjustDrivers}>
                    <Sliders className="h-3 w-3 mr-2" /> Adjust Drivers
                  </DropdownMenuItem>
                  <DropdownMenuSeparator />
                  <DropdownMenuLabel className="text-[10px]">Scenarios</DropdownMenuLabel>
                  <DropdownMenuItem onClick={handleForkScenario}>
                    <GitBranch className="h-3 w-3 mr-2" /> Fork Scenario
                  </DropdownMenuItem>
                  <DropdownMenuItem onClick={handleCompareScenarios}>
                    <LineChart className="h-3 w-3 mr-2" /> Compare Scenarios
                  </DropdownMenuItem>
                  <DropdownMenuSeparator />
                  <DropdownMenuLabel className="text-[10px]">Reports</DropdownMenuLabel>
                  <DropdownMenuItem onClick={handleBoardSummary} disabled={actionLoading === 'summary'}>
                    {actionLoading === 'summary' ? <Loader2 className="h-3 w-3 mr-2 animate-spin" /> : <FileText className="h-3 w-3 mr-2" />}
                    Board Summary
                  </DropdownMenuItem>
                  <DropdownMenuItem onClick={() => addSection(safeIdx, { type: 'ai_narrative' })}>
                    <Sparkles className="h-3 w-3 mr-2" /> AI Narrative
                  </DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>
            </>
          )}

          <div className="flex-1" />
          {sections.length > 1 && (
            <Button
              variant="ghost"
              size="sm"
              className="h-6 w-6 p-0 hover:text-destructive"
              title="Clear all sections"
              onClick={() => onChange([{ type: 'paragraph', content: '' }])}
            >
              <Trash2 className="h-3 w-3" />
            </Button>
          )}
          {onExportPdf && (
            <Button variant="ghost" size="sm" className="h-6 gap-1 text-xs" onClick={onExportPdf} disabled={exportingPdf}>
              {exportingPdf ? <Loader2 className="h-3 w-3 animate-spin" /> : <Download className="h-3 w-3" />}
              PDF
            </Button>
          )}
        </div>
      )}

      {/* Sections */}
      <div ref={containerRef} className="flex-1 min-h-0 overflow-y-auto px-4 py-6 print:bg-white print:shadow-none print:p-0">
        <div className="memo-sections-scroll space-y-1">
        {sections.map((section, idx) => (
          <div
            key={sectionKey(section, idx)}
            className={`memo-section-wrapper group relative rounded-sm px-3 py-1.5 cursor-text ${safeIdx === idx ? 'ring-1 ring-primary/20' : ''} ${!readOnly ? 'hover:bg-muted/30' : ''}`}
            data-drag-over={dragOverIdx === idx ? 'true' : undefined}
            draggable={!readOnly}
            onClick={() => setSelectedIdx(idx)}
            onDragStart={(e) => {
              e.dataTransfer.setData('application/dilla-memo-section', JSON.stringify({ index: idx, section }));
              e.dataTransfer.setData('text/plain', section.content || section.items?.join('\n') || '');
              e.dataTransfer.effectAllowed = 'copyMove';
            }}
            onDragOver={(e) => { e.preventDefault(); setDragOverIdx(idx); }}
            onDragLeave={() => setDragOverIdx(null)}
            onDrop={(e) => {
              e.preventDefault();
              setDragOverIdx(null);
              const raw = e.dataTransfer.getData('application/dilla-memo-section');
              if (!raw) return;
              try {
                const { index: fromIdx } = JSON.parse(raw);
                if (fromIdx === idx) return;
                const next = [...sections];
                const [moved] = next.splice(fromIdx, 1);
                next.splice(idx, 0, moved);
                onChange(next);
                setSelectedIdx(idx);
              } catch {}
            }}
          >
            {/* Context badge for draggable context sections */}
            {section.is_context && (
              <span className="memo-context-badge">CONTEXT — drag to agent chat</span>
            )}
            {/* Heading 1 */}
            {section.type === 'heading1' && (
              <h1
                className={`font-bold ${compact ? 'text-base' : 'text-lg'} outline-none`}
                contentEditable={!readOnly}
                suppressContentEditableWarning
                onBlur={(e) => updateSection(idx, { content: getEditableHtml(e) })}
                dangerouslySetInnerHTML={{ __html: section.content || '' }}
              />
            )}

            {/* Heading 2 */}
            {section.type === 'heading2' && (
              <h2
                className={`font-semibold ${compact ? 'text-sm' : 'text-base'} outline-none`}
                contentEditable={!readOnly}
                suppressContentEditableWarning
                onBlur={(e) => updateSection(idx, { content: getEditableHtml(e) })}
                dangerouslySetInnerHTML={{ __html: section.content || '' }}
              />
            )}

            {/* Heading 3 */}
            {section.type === 'heading3' && (
              <h3
                className={`font-medium ${compact ? 'text-xs' : 'text-sm'} outline-none`}
                contentEditable={!readOnly}
                suppressContentEditableWarning
                onBlur={(e) => updateSection(idx, { content: getEditableHtml(e) })}
                dangerouslySetInnerHTML={{ __html: section.content || '' }}
              />
            )}

            {/* Paragraph */}
            {section.type === 'paragraph' && (
              <p
                className="outline-none leading-relaxed"
                contentEditable={!readOnly}
                suppressContentEditableWarning
                onBlur={(e) => updateSection(idx, { content: getEditableHtml(e) })}
                dangerouslySetInnerHTML={{ __html: section.content || '' }}
              />
            )}

            {/* Chart — responsive, embedded in document flow */}
            {section.type === 'chart' && section.chart && (() => {
              const chartData = section.chart!.data;
              const chartType = section.chart!.type;

              // Validate chart data: must be a non-empty array or non-empty object with valid entries
              const isValidArray = Array.isArray(chartData) && chartData.length > 0 && chartData.some(
                (d: any) => d != null && typeof d === 'object' && Object.values(d).some(v => v != null)
              );
              const isValidObject = chartData != null && !Array.isArray(chartData) && typeof chartData === 'object' && Object.keys(chartData).length > 0;
              const hasData = isValidArray || isValidObject;

              // Scenario trees need more vertical space; flow charts need width
              const isFlowChart = chartType === 'scenario_tree' || chartType === 'sankey' || chartType === 'side_by_side_sankey';
              const chartHeight = compact ? 220 : (isFlowChart ? 480 : 340);
              return hasData ? (
                <div
                  className="chart-container w-full my-3 bg-card rounded-lg overflow-hidden border border-border/40"
                  style={{ height: chartHeight }}
                >
                  <div className="w-full h-full p-3">
                    <TableauLevelCharts
                      data={chartData}
                      type={chartType as any}
                      title={section.chart!.title}
                      width="100%"
                      height={chartHeight - 32}
                    />
                  </div>
                  {section.chart!.title && (
                    <p className="text-[10px] text-muted-foreground text-center -mt-2 pb-2">{section.chart!.title}</p>
                  )}
                </div>
              ) : (
                <div className="w-full my-3 flex items-center justify-center h-16 rounded-lg border border-dashed border-gray-300 dark:border-gray-600 text-xs text-muted-foreground">
                  {section.chart!.title ? `${section.chart!.title} — awaiting data` : 'Chart — awaiting data'}
                </div>
              );
            })()}

            {/* List */}
            {section.type === 'list' && (
              <ul className="list-disc pl-4 space-y-0.5">
                {(section.items || []).map((item, j) => (
                  <li
                    key={j}
                    contentEditable={!readOnly}
                    suppressContentEditableWarning
                    onBlur={(e) => {
                      const items = [...(section.items || [])];
                      items[j] = getEditableHtml(e);
                      updateSection(idx, { items });
                    }}
                    dangerouslySetInnerHTML={{ __html: item }}
                  />
                ))}
              </ul>
            )}

            {/* Quote */}
            {section.type === 'quote' && (
              <blockquote
                className="border-l-2 border-primary/40 pl-3 italic text-muted-foreground outline-none"
                contentEditable={!readOnly}
                suppressContentEditableWarning
                onBlur={(e) => updateSection(idx, { content: getEditableHtml(e) })}
                dangerouslySetInnerHTML={{ __html: section.content || '' }}
              />
            )}

            {/* Code */}
            {section.type === 'code' && (
              <pre className="bg-muted rounded p-2 font-mono text-xs overflow-x-auto">
                <code
                  contentEditable={!readOnly}
                  suppressContentEditableWarning
                  onBlur={(e) => updateSection(idx, { content: e.currentTarget.textContent || '' })}
                >{section.content}</code>
              </pre>
            )}

            {/* Table */}
            {section.type === 'table' && section.table && (
              <div className="w-full my-2 overflow-x-auto">
                {section.table.caption && (
                  <p className="text-[10px] text-muted-foreground mb-1">{section.table.caption}</p>
                )}
                <table className="w-full text-xs border-collapse">
                  <thead>
                    <tr className="border-b-2 border-gray-300 dark:border-gray-600 bg-muted/50">
                      {section.table.headers.map((h, hi) => (
                        <th key={hi} className="px-2 py-1.5 text-left font-semibold text-foreground">{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {section.table.rows.map((row, ri) => {
                      // Scenario-type row highlights
                      const firstCell = String(row[0] || '').toLowerCase();
                      const scenarioRowClass =
                        firstCell === 'bull' ? 'bg-emerald-50 dark:bg-emerald-950/20' :
                        firstCell === 'bear' ? 'bg-red-50 dark:bg-red-950/20' :
                        firstCell === 'base' ? 'bg-blue-50 dark:bg-blue-950/20' :
                        (ri % 2 === 1 ? 'bg-muted/20' : '');
                      return (
                        <tr key={ri} className={`border-b last:border-0 hover:bg-muted/30 ${scenarioRowClass}`}>
                          {row.map((cell, ci) => (
                            <td key={ci} className="px-2 py-1 tabular-nums whitespace-nowrap">
                              {formatTableCell(cell, section.table?.formatting?.[ci])}
                            </td>
                          ))}
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}

            {/* Image */}
            {section.type === 'image' && section.imageUrl && (
              <div className="my-2">
                <img src={section.imageUrl} alt={section.imageCaption || ''} className="max-w-full rounded" />
                {section.imageCaption && (
                  <p className="text-[10px] text-muted-foreground text-center mt-1">{section.imageCaption}</p>
                )}
              </div>
            )}

            {/* TODO List */}
            {section.type === 'todo_list' && (
              <div className="my-2">
                {(section.todos || []).map((todo) => (
                  <div key={todo.id} className="memo-todo-item">
                    <div
                      className="memo-todo-check"
                      data-status={todo.status}
                      onClick={(e) => {
                        e.stopPropagation();
                        if (!onTodoToggle) return;
                        const nextStatus = todo.status === 'done' ? 'pending' : 'done';
                        onTodoToggle(idx, todo.id, nextStatus);
                      }}
                    >
                      {todo.status === 'done' && <span>✓</span>}
                      {todo.status === 'failed' && <span>✗</span>}
                      {todo.status === 'running' && <span className="text-[10px]">●</span>}
                    </div>
                    <span className={`flex-1 ${todo.status === 'done' ? 'line-through text-muted-foreground' : ''}`}>
                      {todo.label}
                    </span>
                    {todo.action_id && (
                      <span className="text-[10px] bg-muted px-1.5 py-0.5 rounded font-mono text-muted-foreground">
                        {todo.action_id}
                      </span>
                    )}
                  </div>
                ))}
              </div>
            )}

            {/* Skill Chain */}
            {section.type === 'skill_chain' && (
              <div className="memo-skill-chain my-2">
                {(section.skill_chain || []).map((step, si) => (
                  <React.Fragment key={step.id}>
                    {si > 0 && <span className="memo-skill-arrow">{step.parallel ? '∥' : '→'}</span>}
                    <button
                      className="memo-skill-step"
                      onClick={(e) => {
                        e.stopPropagation();
                        onSkillExecute?.(idx, step.id);
                      }}
                      title={`Execute: ${step.action_id}`}
                    >
                      {step.label}
                    </button>
                  </React.Fragment>
                ))}
              </div>
            )}

            {/* Redline — interactive track changes */}
            {section.type === 'redline' && section.redline && (
              <div className="my-2 space-y-2 border rounded-md p-3 bg-muted/10">
                <div className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wide flex items-center gap-2">
                  <span className="inline-block w-2 h-2 rounded-full bg-amber-500" />
                  Track Changes{section.redline.clause_type && ` — ${section.redline.clause_type}`}
                </div>
                <div className="space-y-2">
                  <div className="text-red-600 dark:text-red-400 line-through text-sm leading-relaxed bg-red-50 dark:bg-red-950/20 rounded px-2 py-1.5">
                    {section.redline.original}
                  </div>
                  {readOnly ? (
                    <div className="text-emerald-600 dark:text-emerald-400 text-sm leading-relaxed bg-emerald-50 dark:bg-emerald-950/20 rounded px-2 py-1.5">
                      {section.redline.revised}
                    </div>
                  ) : (
                    <textarea
                      className="w-full text-emerald-600 dark:text-emerald-400 text-sm leading-relaxed bg-emerald-50 dark:bg-emerald-950/20 rounded px-2 py-1.5 border border-emerald-200 dark:border-emerald-800 focus:ring-1 focus:ring-emerald-500 resize-none"
                      defaultValue={section.redline.revised}
                      rows={Math.max(2, (section.redline.revised?.split('\n').length || 1))}
                      onChange={(e) => {
                        // Debounced redline impact calculation
                        const newVal = e.target.value;
                        if ((window as any).__redlineTimer) clearTimeout((window as any).__redlineTimer);
                        (window as any).__redlineTimer = setTimeout(async () => {
                          try {
                            const res = await fetch('/api/legal/redline-impact', {
                              method: 'POST',
                              headers: { 'Content-Type': 'application/json' },
                              body: JSON.stringify({
                                company_id: (section as any).company_id || '',
                                clause_type: section.redline?.clause_type || '',
                                original_value: section.redline?.original,
                                new_value: newVal,
                                stage: (section as any).stage,
                              }),
                            });
                            if (res.ok) {
                              const impact = await res.json();
                              const impactEl = document.getElementById(`redline-impact-${idx}`);
                              if (impactEl && impact.impact?.summary) {
                                impactEl.textContent = impact.impact.summary;
                                impactEl.classList.remove('hidden');
                              }
                              const benchEl = document.getElementById(`redline-bench-${idx}`);
                              if (benchEl && impact.benchmark?.comparison) {
                                benchEl.textContent = impact.benchmark.comparison;
                                benchEl.classList.remove('hidden');
                              }
                            }
                          } catch { /* ignore fetch errors */ }
                        }, 500);
                      }}
                    />
                  )}
                </div>
                {/* Live impact display */}
                <div id={`redline-impact-${idx}`} className="hidden text-[11px] text-amber-700 dark:text-amber-400 bg-amber-50 dark:bg-amber-950/20 rounded px-2 py-1 font-medium" />
                {/* Benchmark comparison */}
                <div id={`redline-bench-${idx}`} className="hidden text-[11px] text-blue-600 dark:text-blue-400 bg-blue-50 dark:bg-blue-950/20 rounded px-2 py-1" />
                {section.redline.reasoning && (
                  <div className="text-[11px] text-muted-foreground italic border-t pt-1.5 mt-1.5">
                    {section.redline.reasoning}
                  </div>
                )}
                {/* Accept / Reject buttons */}
                {!readOnly && (
                  <div className="flex gap-2 pt-1 border-t mt-1.5">
                    <button
                      className="text-[11px] px-2.5 py-1 rounded bg-emerald-100 dark:bg-emerald-900/40 text-emerald-700 dark:text-emerald-300 hover:bg-emerald-200 dark:hover:bg-emerald-800/60 transition-colors font-medium"
                      onClick={async () => {
                        try {
                          await fetch('/api/legal/redline-accept', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({
                              company_id: (section as any).company_id || '',
                              document_id: (section as any).document_id || '',
                              clause_id: (section as any).clause_id || '',
                              clause_type: section.redline?.clause_type || '',
                              new_value: section.redline?.revised,
                            }),
                          });
                          // Visual feedback
                          removeSection(idx);
                        } catch { /* ignore */ }
                      }}
                    >
                      Accept
                    </button>
                    <button
                      className="text-[11px] px-2.5 py-1 rounded bg-red-100 dark:bg-red-900/40 text-red-700 dark:text-red-300 hover:bg-red-200 dark:hover:bg-red-800/60 transition-colors font-medium"
                      onClick={() => removeSection(idx)}
                    >
                      Reject
                    </button>
                  </div>
                )}
              </div>
            )}

            {/* Interactive sections — rendered by dedicated components */}
            {section.type === 'pnl' && <PnlSection onDelete={() => removeSection(idx)} readOnly={readOnly} />}
            {section.type === 'balance_sheet' && <BalanceSheetSection onDelete={() => removeSection(idx)} readOnly={readOnly} />}
            {section.type === 'cash_flow' && <CashFlowSection onDelete={() => removeSection(idx)} readOnly={readOnly} />}
            {section.type === 'drivers' && <DriversSection onDelete={() => removeSection(idx)} readOnly={readOnly} />}
            {section.type === 'metrics' && <MetricsSection onDelete={() => removeSection(idx)} readOnly={readOnly} />}
            {section.type === 'scenario' && <ScenarioSection onDelete={() => removeSection(idx)} readOnly={readOnly} />}
            {section.type === 'cascade' && <CascadeSection onDelete={() => removeSection(idx)} readOnly={readOnly} />}
            {section.type === 'cap_table' && <CapTableSection onDelete={() => removeSection(idx)} readOnly={readOnly} />}
            {section.type === 'waterfall' && <WaterfallSection onDelete={() => removeSection(idx)} readOnly={readOnly} />}
            {section.type === 'valuation' && <ValuationSection onDelete={() => removeSection(idx)} readOnly={readOnly} />}
            {section.type === 'monte_carlo' && <MonteCarloSection onDelete={() => removeSection(idx)} readOnly={readOnly} />}
            {section.type === 'sensitivity' && <SensitivitySection onDelete={() => removeSection(idx)} readOnly={readOnly} />}
            {section.type === 'forecast_method' && <ForecastMethodSection onDelete={() => removeSection(idx)} readOnly={readOnly} />}
            {section.type === 'budget_variance' && <BudgetVarianceSection onDelete={() => removeSection(idx)} readOnly={readOnly} />}
            {section.type === 'health_score' && <HealthScoreSection onDelete={() => removeSection(idx)} readOnly={readOnly} />}
            {section.type === 'cost_of_capital' && <CostOfCapitalSection onDelete={() => removeSection(idx)} readOnly={readOnly} />}
            {section.type === 'stakeholder' && <StakeholderSection onDelete={() => removeSection(idx)} readOnly={readOnly} />}
            {section.type === 'ai_narrative' && <AINarrativeSection onDelete={() => removeSection(idx)} readOnly={readOnly} />}

            {/* Citations */}
            {section.citations?.length ? (
              <div className="mt-1.5 flex flex-wrap gap-1">
                {section.citations.map((c, ci) => (
                  <span key={ci} className="text-[10px] bg-muted px-1.5 py-0.5 rounded text-muted-foreground">
                    {c.type === 'source' && c.url ? (
                      <a href={c.url} target="_blank" rel="noopener noreferrer" className="underline">{c.title}</a>
                    ) : (
                      c.title
                    )}
                  </span>
                ))}
              </div>
            ) : null}

            {/* Delete button */}
            {!readOnly && sections.length > 1 && (
              <button
                className="absolute -right-1 -top-1 opacity-0 group-hover:opacity-100 h-4 w-4 bg-destructive text-white rounded-full text-[10px] flex items-center justify-center print:hidden"
                onClick={(e) => { e.stopPropagation(); removeSection(idx); }}
              >
                <X className="h-2.5 w-2.5" />
              </button>
            )}
          </div>
        ))}
        </div>
      </div>
    </div>
  );
}
