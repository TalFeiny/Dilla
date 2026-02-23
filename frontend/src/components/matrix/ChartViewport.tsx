'use client';

import React, { useMemo, useState, useEffect, useCallback } from 'react';
import dynamic from 'next/dynamic';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import {
  Drawer,
  DrawerContent,
  DrawerHeader,
  DrawerTitle,
  DrawerDescription,
} from '@/components/ui/drawer';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { BarChart3, Sparkles, FileText, X, Check, AlertCircle, AlertTriangle, Trophy, Lightbulb, Shield, RefreshCw, TrendingUp, RotateCcw, Send } from 'lucide-react';
import { Textarea } from '@/components/ui/textarea';
import { MatrixData } from './UnifiedMatrix';
import { MemoEditor, type DocumentSection } from '@/components/memo/MemoEditor';
import { DocumentSuggestion, DocumentInsight, type SuggestionAcceptPayload } from './DocumentSuggestions';
import { formatCurrency } from '@/lib/matrix/cell-formatters';
import { cn } from '@/lib/utils';

/** Charts + Insights + Memo; suggestions live in chat (Cursor-style). */
export type ChartTab = 'charts' | 'insights' | 'memo';

/** Chart config from cell metadata or MCP orchestrator */
export interface ChartConfig {
  type?: string;
  title?: string;
  data?: Record<string, unknown> | unknown[];
  description?: string;
  renderType?: string;
  source?: 'cell' | 'mcp';
  cellId?: string;
  rowId?: string;
  columnId?: string;
  companyName?: string;
}

// Dynamic import for TableauLevelCharts to avoid SSR issues
const TableauLevelCharts = dynamic(() => import('@/components/charts/TableauLevelCharts'), { 
  ssr: false,
  loading: () => <div className="h-[300px] flex items-center justify-center text-sm text-gray-500">Loading chart...</div>
});

export type ChartViewportVariant = 'drawer' | 'canvas';

interface ChartViewportProps {
  matrixData: MatrixData | null;
  fundId?: string;
  isOpen: boolean;
  onOpenChange: (open: boolean) => void;
  /** 'drawer' = overlay pullover (default); 'canvas' = right-side panel in layout */
  variant?: ChartViewportVariant;
  /** When provided, use these instead of fetching in viewport (single source of truth from parent). */
  suggestions?: DocumentSuggestion[];
  insights?: DocumentInsight[];
  suggestionsLoading?: boolean;
  suggestionsError?: string | null;
  refreshSuggestions?: () => Promise<void>;
  onSuggestionAccept?: (suggestionId: string, payload?: SuggestionAcceptPayload) => void;
  onSuggestionReject?: (suggestionId: string) => void;
  onApplySuggestions?: (suggestions: DocumentSuggestion[]) => void;
  /** When true (e.g. embedded in AgentPanel), hide header/close so parent owns chrome */
  embedded?: boolean;
  /** Phase 6: Retry a service suggestion (re-run same action) */
  onRetrySuggestion?: (suggestion: DocumentSuggestion) => void;
  /** When provided, show an "Ask" bar so the user can request reports, memos, what-if scenarios; prompt is sent to the same agent (unified-brain) that has tools for docs/memo/modeling. */
  onAskAgent?: (prompt: string) => void;
  /** Memo sections — parent owns state, ChartViewport renders */
  memoSections?: DocumentSection[];
  onMemoChange?: (sections: DocumentSection[]) => void;
  onMemoExportPdf?: () => void;
  memoExportingPdf?: boolean;
  /** Ref to memo container for chart capture in PDF export */
  memoContainerRef?: React.RefObject<HTMLDivElement | null>;
}

export function ChartViewport({
  matrixData,
  fundId,
  isOpen,
  onOpenChange,
  variant = 'drawer',
  suggestions: suggestionsProp,
  insights: insightsProp,
  suggestionsLoading: suggestionsLoadingProp,
  suggestionsError: suggestionsErrorProp,
  refreshSuggestions: refreshSuggestionsProp,
  onSuggestionAccept,
  onSuggestionReject,
  onApplySuggestions,
  initialTab,
  embedded = false,
  onRetrySuggestion,
  onAskAgent,
  memoSections,
  onMemoChange,
  onMemoExportPdf,
  memoExportingPdf,
  memoContainerRef,
}: ChartViewportProps & { initialTab?: ChartTab }) {
  const safeInitialTab: ChartTab = (initialTab as string) === 'suggestions' || !initialTab ? 'charts' : initialTab;
  const [activeTab, setActiveTab] = useState<ChartTab>(safeInitialTab);
  const [chartError, setChartError] = useState<string | null>(null);
  const [askPrompt, setAskPrompt] = useState('');
  const [askSending, setAskSending] = useState(false);

  useEffect(() => {
    if (initialTab && (initialTab as string) !== 'suggestions') {
      setActiveTab(initialTab);
    }
  }, [initialTab]);
  const [selectedSuggestions, setSelectedSuggestions] = useState<Set<string>>(new Set());

  // Portfolio overview charts (live NAV, DPI Sankey) - fetched when fundId + matrixData
  const [portfolioCharts, setPortfolioCharts] = useState<ChartConfig[]>([]);
  const [portfolioLoading, setPortfolioLoading] = useState(false);
  const [generatedCharts, setGeneratedCharts] = useState<ChartConfig[]>([]);
  const [generateLoading, setGenerateLoading] = useState(false);

  const fetchPortfolioCharts = useCallback(async () => {
    if (!fundId || !matrixData?.rows?.length) return;
    setPortfolioLoading(true);
    try {
      const companyIds = matrixData.rows.map((r) => r.id).filter(Boolean);
      const charts: ChartConfig[] = [];

      // Fetch NAV and DPI Sankey in parallel
      const [navRes, dpiRes] = await Promise.all([
        companyIds.length > 0
          ? fetch(`/api/portfolio/${fundId}/nav-timeseries?companyIds=${companyIds.join(',')}&aggregate=true`)
          : Promise.resolve({ ok: false } as Response),
        fetch(`/api/cell-actions/actions/portfolio.dpi_sankey/execute`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ fund_id: fundId, inputs: {} }),
        }),
      ]);

      if (navRes.ok) {
        const navData = await navRes.json();
        if (navData.aggregate?.labels?.length) {
          charts.push({
            type: 'line',
            title: 'Portfolio NAV (Live)',
            source: 'mcp',
            data: {
              labels: navData.aggregate.labels,
              datasets: [{ label: 'Total NAV', data: navData.aggregate.data, borderColor: '#059669' }],
            },
            renderType: 'tableau',
          });
        }
      }

      if (dpiRes.ok) {
        const dpiJson = await dpiRes.json();
        const cfg = dpiJson.metadata?.chart_config || dpiJson.metadata?.chart_to_create || dpiJson;
        if (cfg && (cfg.type === 'sankey' || cfg.renderType === 'tableau') && cfg.data) {
          charts.push({
            type: 'sankey',
            title: cfg.title || 'DPI Flow (Follow-on Strategy)',
            source: 'mcp',
            data: cfg.data,
            renderType: 'tableau',
          });
        }
      }

      setPortfolioCharts(charts);
    } catch (err) {
      console.warn('Portfolio charts fetch failed:', err);
    } finally {
      setPortfolioLoading(false);
    }
  }, [fundId, matrixData?.rows]);

  useEffect(() => {
    if (isOpen && fundId && matrixData?.rows?.length) {
      fetchPortfolioCharts();
    }
  }, [isOpen, fundId, matrixData?.rows?.length, fetchPortfolioCharts]);

  const handleGenerateFromMatrix = useCallback(async () => {
    if (!matrixData) return;
    setGenerateLoading(true);
    setChartError(null);
    try {
      const res = await fetch('/api/matrix/charts/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          fund_id: fundId,
          matrix_data: matrixData,
          chart_type: 'auto',
        }),
      });
      if (!res.ok) throw new Error('Chart generation failed');
      const json = await res.json();
      const newCharts = (json.charts || []).map((c: ChartConfig) => ({ ...c, source: 'mcp' as const }));
      setGeneratedCharts((prev) => [...prev, ...newCharts]);
    } catch (err) {
      setChartError(err instanceof Error ? err.message : 'Failed to generate charts');
    } finally {
      setGenerateLoading(false);
    }
  }, [matrixData, fundId]);

  // Cell charts from matrix metadata
  const cellCharts = useMemo((): ChartConfig[] => {
    if (!matrixData) return [];
    const { extractChartsFromMatrix } = require('@/lib/matrix/chart-utils');
    return extractChartsFromMatrix(matrixData);
  }, [matrixData]);

  const charts = useMemo((): ChartConfig[] => {
    return [...portfolioCharts, ...generatedCharts, ...cellCharts];
  }, [portfolioCharts, generatedCharts, cellCharts]);

  // Single source of truth: use suggestions and insights from parent when provided
  const suggestions = suggestionsProp ?? [];
  const insights = insightsProp ?? [];
  const suggestionsLoading = suggestionsLoadingProp ?? false;
  const suggestionsError = suggestionsErrorProp ?? null;
  const refreshSuggestions = refreshSuggestionsProp ?? (async () => {});
  const displayError = chartError ?? suggestionsError ?? null;

  // Group suggestions by confidence
  const highConfidenceSuggestions = useMemo(() => {
    return suggestions.filter(s => s.confidence >= 0.9);
  }, [suggestions]);

  const otherSuggestions = useMemo(() => {
    return suggestions.filter(s => s.confidence < 0.9);
  }, [suggestions]);

  const handleAutoApply = async () => {
    if (!onApplySuggestions || highConfidenceSuggestions.length === 0) return;
    try {
      setChartError(null);
      onApplySuggestions(highConfidenceSuggestions);
      await refreshSuggestions();
    } catch (err) {
      setChartError(err instanceof Error ? err.message : 'Failed to apply suggestions');
    }
  };

  const handleSuggestionToggle = (suggestionId: string) => {
    const newSelected = new Set(selectedSuggestions);
    if (newSelected.has(suggestionId)) {
      newSelected.delete(suggestionId);
    } else {
      newSelected.add(suggestionId);
    }
    setSelectedSuggestions(newSelected);
  };

  const handleBatchAccept = async () => {
    const toAccept = suggestions.filter(s => selectedSuggestions.has(s.id));
    if (toAccept.length === 0) return;
    try {
      setChartError(null);
      for (const s of toAccept) {
        onSuggestionAccept?.(s.id, {
          rowId: s.rowId,
          columnId: s.columnId,
          suggestedValue: s.suggestedValue,
          sourceDocumentId: s.sourceDocumentId,
        });
      }
      setSelectedSuggestions(new Set());
      await refreshSuggestions();
    } catch (err) {
      setChartError(err instanceof Error ? err.message : 'Failed to accept suggestions');
    }
  };

  const handleAskSubmit = useCallback(() => {
    const trimmed = askPrompt.trim();
    if (!trimmed || !onAskAgent || askSending) return;
    setAskSending(true);
    try {
      onAskAgent(trimmed);
      setAskPrompt('');
    } finally {
      setAskSending(false);
    }
  }, [askPrompt, onAskAgent, askSending]);

  const tabContent = (
    <Tabs value={activeTab} onValueChange={(v) => setActiveTab(v as ChartTab)} className="flex-1 flex flex-col overflow-hidden">
      {onAskAgent && (
        <div className="shrink-0 border-b px-3 py-2 bg-muted/30">
          <p className="text-xs text-muted-foreground mb-1.5">Generate documents, reports, or what-if scenarios (uses same agent tools)</p>
          <div className="flex gap-2">
            <Textarea
              placeholder="e.g. Generate investment memo for @Acme, What if ARR doubles for Mercury…"
              value={askPrompt}
              onChange={(e) => setAskPrompt(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault();
                  handleAskSubmit();
                }
              }}
              className="min-h-[60px] resize-none text-sm"
              rows={2}
              disabled={askSending}
            />
            <Button
              size="sm"
              onClick={handleAskSubmit}
              disabled={!askPrompt.trim() || askSending}
              className="shrink-0 self-end gap-1"
            >
              {askSending ? <RefreshCw className="h-3.5 w-3.5 animate-spin" /> : <Send className="h-3.5 w-3.5" />}
              Send
            </Button>
          </div>
        </div>
      )}
      <div className="border-b px-4 shrink-0">
        <TabsList>
              <TabsTrigger value="charts" className="gap-2">
                <BarChart3 className="h-4 w-4" />
                Charts ({charts.length})
              </TabsTrigger>
              <TabsTrigger value="insights" className="gap-2">
                <Sparkles className="h-4 w-4" />
                Insights
                {insights.length > 0 && (
                  <Badge variant="secondary" className="ml-1">
                    {insights.length}
                  </Badge>
                )}
              </TabsTrigger>
              <TabsTrigger value="memo" className="gap-2">
                <FileText className="h-4 w-4" />
                Memo
              </TabsTrigger>
            </TabsList>
          </div>

          <div className="flex-1 overflow-y-auto p-4">
            {displayError && (
              <div className="mb-4 flex items-center gap-2 rounded-lg border border-destructive/50 bg-destructive/10 px-4 py-3 text-sm text-destructive">
                <AlertCircle className="h-4 w-4 shrink-0" />
                {displayError}
              </div>
            )}
            <TabsContent value="charts" className="mt-0 space-y-4">
              {fundId && matrixData?.rows?.length > 0 && (
                <div className="flex flex-wrap gap-2 mb-4">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={handleGenerateFromMatrix}
                    disabled={generateLoading}
                    className="gap-2"
                  >
                    <RefreshCw className={generateLoading ? 'h-4 w-4 animate-spin' : 'h-4 w-4'} />
                    {generateLoading ? 'Generating...' : 'Generate from matrix'}
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={fetchPortfolioCharts}
                    disabled={portfolioLoading}
                    className="gap-2"
                  >
                    <TrendingUp className={portfolioLoading ? 'h-4 w-4 animate-spin' : 'h-4 w-4'} />
                    Refresh live charts
                  </Button>
                </div>
              )}
              {charts.length === 0 ? (
                <div className="flex flex-col items-center justify-center h-full text-center py-12">
                  <BarChart3 className="h-12 w-12 text-gray-400 mb-4" />
                  <p className="text-gray-600 dark:text-gray-400">No charts available</p>
                  <p className="text-sm text-gray-500 mt-2">
                    Charts will appear here when generated from matrix data
                  </p>
                  {fundId && (
                    <p className="text-xs text-muted-foreground mt-2">
                      Use &quot;Generate from matrix&quot; for cashflow, NAV, DPI Sankey, revenue treemap, velocity ranking
                    </p>
                  )}
                </div>
              ) : (
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                  {charts.map((chart, idx) => (
                    <ChartCard key={chart.cellId ?? `chart-${idx}`} chart={chart} index={idx} onError={setChartError} />
                  ))}
                </div>
              )}
            </TabsContent>

            <TabsContent value="insights" className="mt-0">
              <div className="space-y-4">
                {insights.length === 0 ? (
                  <div className="flex flex-col items-center justify-center h-full text-center py-12">
                    <Sparkles className="h-12 w-12 text-gray-400 mb-4" />
                    <p className="text-gray-600 dark:text-gray-400">No document insights yet</p>
                    <p className="text-sm text-gray-500 mt-2">
                      Red flags, achievements, risks, and implications from uploaded documents will appear here
                    </p>
                    {matrixData && matrixData.rows.length > 0 && (
                      <p className="text-xs text-muted-foreground mt-2">
                        Upload board decks, memos, or updates to see insights
                      </p>
                    )}
                  </div>
                ) : (
                  <div className="space-y-4">
                    {insights.map((insight) => (
                      <InsightCard key={`${insight.documentId}-${insight.rowId}`} insight={insight} matrixData={matrixData} />
                    ))}
                  </div>
                )}
              </div>
            </TabsContent>

            <TabsContent value="memo" className="mt-0 h-full">
              <MemoEditor
                sections={memoSections || [{ type: 'heading1', content: 'Working Memo' }, { type: 'paragraph', content: '' }]}
                onChange={onMemoChange || (() => {})}
                compact
                onExportPdf={onMemoExportPdf}
                exportingPdf={memoExportingPdf}
                containerRef={memoContainerRef}
              />
            </TabsContent>
          </div>
        </Tabs>
  );

  // Right-side canvas panel (no pullover drawer); when embedded, no header
  if (variant === 'canvas') {
    return (
      <div className="flex flex-col h-full min-h-0 w-full border-l bg-background">
        {!embedded && (
          <div className="shrink-0 border-b px-4 py-3 flex items-center justify-between">
            <div>
              <h2 className="font-semibold text-sm">Charts & Insights</h2>
              <p className="text-xs text-muted-foreground">
                Matrix charts and AI insights
              </p>
            </div>
            <Button variant="ghost" size="sm" onClick={() => onOpenChange(false)}>
              <X className="h-4 w-4" />
            </Button>
          </div>
        )}
        {tabContent}
      </div>
    );
  }

  // Legacy drawer (pullover) - kept for any other consumers
  return (
    <Drawer open={isOpen} onOpenChange={onOpenChange}>
      <DrawerContent className="h-[85vh]">
        <DrawerHeader className="border-b">
          <div className="flex items-center justify-between">
            <div>
              <DrawerTitle>Charts & Insights</DrawerTitle>
              <DrawerDescription>
                View charts and AI insights for your matrix. Accept/reject suggestions in chat.
              </DrawerDescription>
            </div>
            <Button variant="ghost" size="sm" onClick={() => onOpenChange(false)}>
              <X className="h-4 w-4" />
            </Button>
          </div>
        </DrawerHeader>
        {tabContent}
      </DrawerContent>
    </Drawer>
  );
}

function ChartCard({ chart, index, onError }: { chart: ChartConfig; index: number; onError: (msg: string | null) => void }) {
  const dataObj = chart.data && typeof chart.data === 'object' && !Array.isArray(chart.data) ? chart.data as { title?: string } : null;
  const title = chart.title ?? dataObj?.title ?? `Chart ${index + 1}`;
  const data = chart.data ?? chart;

  // Fallback when chart data is missing or invalid
  const hasValidData = data != null && (
    (typeof data === 'object' && Object.keys(data as object).length > 0) ||
    (Array.isArray(data) && data.length > 0)
  );

  return (
    <Card className="overflow-hidden">
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <CardTitle className="text-sm font-medium">{title}</CardTitle>
          <Badge variant="outline" className="text-xs">
            {chart.source === 'cell' ? 'Cell' : 'Matrix'}
          </Badge>
        </div>
        {chart.companyName && (
          <p className="text-xs text-muted-foreground mt-1">{chart.companyName}</p>
        )}
      </CardHeader>
      <CardContent>
        <div className="min-h-[200px] h-[260px] w-full overflow-auto rounded border border-muted/50 viewport-chart">
          {!hasValidData ? (
            <div className="flex h-full min-h-[200px] items-center justify-center rounded border border-muted bg-muted/30 text-sm text-muted-foreground">
              No chart data available. Chart generation returned empty or invalid data.
            </div>
          ) : (
          <ChartErrorBoundary onError={onError}>
            <TableauLevelCharts
              type={(chart.type ?? 'pie') as 'waterfall' | 'sankey' | 'sunburst' | 'heatmap' | 'boxplot' | 'candlestick' | 'bubble' | 'gantt' | 'funnel' | 'radialBar' | 'streamgraph' | 'chord' | 'force' | 'side_by_side_sankey' | 'timeline_valuation' | 'probability_cloud' | 'pie' | 'line' | 'bar' | 'treemap' | 'scatter'}
              data={data}
              title={title}
              height={260}
              width="100%"
              interactive={true}
            />
          </ChartErrorBoundary>
          )}
        </div>
        {chart.description && (
          <p className="text-xs text-muted-foreground mt-2">{chart.description}</p>
        )}
      </CardContent>
    </Card>
  );
}

interface ChartErrorBoundaryProps {
  children: React.ReactNode;
  onError: (msg: string | null) => void;
}

class ChartErrorBoundary extends React.Component<ChartErrorBoundaryProps, { hasError: boolean; error?: Error }> {
  state = { hasError: false, error: undefined as Error | undefined };

  static getDerivedStateFromError(error: Error) {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error) {
    this.props.onError(error.message);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="flex h-full min-h-[200px] items-center justify-center rounded border border-destructive/30 bg-destructive/5 text-sm text-destructive">
          Chart failed to render
        </div>
      );
    }
    return this.props.children;
  }
}

function InsightCard({ insight, matrixData }: { insight: DocumentInsight; matrixData: MatrixData | null }) {
  const companyName = matrixData?.rows.find((r) => r.id === insight.rowId)?.companyName ?? 'Company';
  const sections = [
    { key: 'redFlags', label: 'Red flags', items: insight.redFlags, icon: AlertTriangle, className: 'border-amber-200 bg-amber-50 dark:bg-amber-900/10' },
    { key: 'implications', label: 'Implications', items: insight.implications, icon: Lightbulb, className: 'border-blue-200 bg-blue-50 dark:bg-blue-900/10' },
    { key: 'achievements', label: 'Achievements', items: insight.achievements, icon: Trophy, className: 'border-green-200 bg-green-50 dark:bg-green-900/10' },
    { key: 'challenges', label: 'Challenges', items: insight.challenges, icon: Shield, className: 'border-slate-200 bg-slate-50 dark:bg-slate-900/10' },
    { key: 'risks', label: 'Risks', items: insight.risks, icon: AlertCircle, className: 'border-red-200 bg-red-50 dark:bg-red-900/10' },
  ].filter((s) => s.items.length > 0);

  return (
    <Card>
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <CardTitle className="text-sm font-medium">{insight.documentName}</CardTitle>
          <span className="text-xs text-muted-foreground">{companyName}</span>
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        {sections.map(({ key, label, items, icon: Icon, className }) => (
          <div key={key} className={cn('rounded-lg border p-3', className)}>
            <h4 className="text-xs font-medium mb-2 flex items-center gap-2">
              <Icon className="h-3.5 w-3.5" />
              {label}
            </h4>
            <ul className="text-sm space-y-1 list-disc list-inside">
              {items.map((item, i) => (
                <li key={i} className="text-muted-foreground">{item}</li>
              ))}
            </ul>
          </div>
        ))}
      </CardContent>
    </Card>
  );
}

function SuggestionCard({
  suggestion,
  isSelected,
  onToggle,
  onAccept,
  onReject,
  onRetry,
}: {
  suggestion: DocumentSuggestion;
  isSelected: boolean;
  onToggle: () => void;
  onAccept: () => void;
  onReject: () => void;
  onRetry?: () => void;
}) {
  const formatValue = (value: unknown): string => {
    if (value === null || value === undefined) return 'N/A';
    if (typeof value === 'number') return formatCurrency(value);
    return String(value);
  };

  return (
    <div
      className={cn(
        "border rounded-lg p-3 space-y-2",
        isSelected && "border-primary bg-primary/5"
      )}
    >
      {/* Primary: value change */}
      <div className="flex items-baseline gap-2 flex-wrap">
        <span className="text-sm font-medium text-muted-foreground">{formatValue(suggestion.currentValue)}</span>
        <span className="text-xs text-muted-foreground">→</span>
        <span className="text-sm font-semibold">{formatValue(suggestion.suggestedValue)}</span>
        <Badge variant="secondary" className="text-[10px] ml-1">{Math.round(suggestion.confidence * 100)}%</Badge>
      </div>

      {/* Secondary: source & citation */}
      <div className="flex items-start gap-2">
        <FileText className="w-3.5 h-3.5 text-muted-foreground shrink-0 mt-0.5" />
        <div className="min-w-0">
          <p className="text-xs font-medium text-muted-foreground truncate">{suggestion.sourceDocumentName}</p>
          <p className="text-xs text-muted-foreground line-clamp-2">{suggestion.reasoning}</p>
        </div>
      </div>

      <div className="flex gap-2 pt-2 border-t">
        {onRetry && (
          <Button
            size="sm"
            variant="ghost"
            className="h-8 text-xs gap-1"
            onClick={(e) => {
              e.stopPropagation();
              onRetry();
            }}
          >
            <RotateCcw className="w-3 h-3" />
            Retry
          </Button>
        )}
        <Button
          size="sm"
          variant="outline"
          className="flex-1 h-8 text-xs min-w-0"
          onClick={(e) => {
            e.stopPropagation();
            onReject();
          }}
        >
          <X className="w-3 h-3 mr-1" />
          Reject
        </Button>
        <Button
          size="sm"
          className="flex-1 h-8 text-xs min-w-0"
          onClick={(e) => {
            e.stopPropagation();
            onAccept();
          }}
        >
          <Check className="w-3 h-3 mr-1" />
          Accept
        </Button>
      </div>
    </div>
  );
}
