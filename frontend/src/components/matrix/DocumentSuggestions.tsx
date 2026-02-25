'use client';

import React, { useState, useEffect, useMemo, useCallback, useRef } from 'react';
import { Check, X, FileText, Sparkles, ChevronDown, ChevronUp, Zap, ArrowRight, Cpu, TrendingUp, TrendingDown, Plus } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '@/components/ui/popover';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import { MatrixCell, MatrixRow, MatrixData } from './UnifiedMatrix';
import { formatSuggestionValue, getColumnLabel } from '@/lib/matrix/cell-formatters';

export interface DocumentSuggestion {
  id: string;
  cellId: string;
  rowId: string;
  columnId: string;
  suggestedValue: unknown;
  currentValue: unknown;
  reasoning: string;
  confidence: number;
  sourceDocumentId?: number;
  sourceDocumentName: string;
  extractedMetric?: string;
  changeType?: 'increase' | 'decrease' | 'new' | 'update';
  changeAmount?: number;
  changePercentage?: number;
  /** 'document' = from processed_documents; 'service' = from pending_suggestions (valuation, PWERM, etc.) */
  source?: 'document' | 'service';
  /** When source === 'service', the action_id (e.g. valuation_engine.auto) */
  sourceService?: string;
  /** Structured citation from value_explanations */
  citationPage?: number;
  citationSection?: string;
  /** Summary of the source document (synthesized from extracted data) */
  documentSummary?: string;
}

/** Document insight from /api/matrix/suggestions */
export interface DocumentInsight {
  documentId: number;
  documentName: string;
  rowId: string;
  redFlags: string[];
  implications: string[];
  achievements: string[];
  challenges: string[];
  risks: string[];
}

/** Raw suggestion shape from /api/matrix/suggestions */
interface ApiSuggestion {
  id: string;
  rowId: string;
  columnId: string;
  suggestedValue: unknown;
  currentValue?: unknown;
  reasoning: string;
  confidence: number;
  sourceDocumentId?: number;
  sourceDocumentName: string;
  extractedMetric?: string;
  changeType?: 'increase' | 'decrease' | 'new' | 'update';
  changeAmount?: number;
  changePercentage?: number;
  source?: 'document' | 'service';
  sourceService?: string;
  documentSummary?: string;
}

export type SuggestionAcceptPayload = {
  rowId: string;
  columnId: string;
  suggestedValue: unknown;
  sourceDocumentId?: string | number;
};

interface DocumentSuggestionsProps {
  rowId: string;
  columnId: string;
  cell: MatrixCell;
  suggestions: DocumentSuggestion[];
  onAccept: (suggestionId: string, payload?: SuggestionAcceptPayload) => void;
  onReject: (suggestionId: string) => void;
}

export function DocumentSuggestionBadge({
  rowId,
  columnId,
  cell,
  suggestions,
  onAccept,
  onReject,
}: DocumentSuggestionsProps) {
  const [isOpen, setIsOpen] = useState(false);
  const cellSuggestions = suggestions.filter(
    s => s.rowId === rowId && s.columnId === columnId
      // Drop suggestions with null/empty values — would render as "N/A"
      && s.suggestedValue !== null && s.suggestedValue !== undefined
      && s.suggestedValue !== ''
  );

  if (cellSuggestions.length === 0) {
    return null;
  }

  const pendingSuggestions = cellSuggestions; // All suggestions are pending until accepted/rejected
  if (pendingSuggestions.length === 0) {
    return null;
  }

  const bestSuggestion = pendingSuggestions.reduce((best, current) => {
    return current.confidence > best.confidence ? current : best;
  }, pendingSuggestions[0]);

  return (
    <Popover open={isOpen} onOpenChange={setIsOpen}>
      <PopoverTrigger asChild>
        <Badge
          variant="outline"
          className="ml-1 cursor-pointer bg-blue-50 text-blue-700 hover:bg-blue-100 dark:bg-blue-900/20 dark:text-blue-400"
        >
          <Sparkles className="w-3 h-3 mr-1" />
          {pendingSuggestions.length} suggestion{pendingSuggestions.length > 1 ? 's' : ''}
        </Badge>
      </PopoverTrigger>
      <PopoverContent className="w-[420px] max-h-[70vh] overflow-y-auto" align="start">
        <TooltipProvider delayDuration={150}>
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <h4 className="font-semibold text-sm">Suggested Updates</h4>
              <span className="text-[11px] text-gray-500 dark:text-gray-400">
                {pendingSuggestions.length} to review
              </span>
            </div>

            {pendingSuggestions.map((suggestion) => (
              <SuggestionCard
                key={suggestion.id}
                suggestion={suggestion}
                onAccept={() => {
                  onAccept(suggestion.id, {
                    rowId: suggestion.rowId,
                    columnId: suggestion.columnId,
                    suggestedValue: suggestion.suggestedValue,
                    sourceDocumentId: suggestion.sourceDocumentId,
                  });
                  setIsOpen(false);
                }}
                onReject={() => {
                  onReject(suggestion.id);
                  setIsOpen(false);
                }}
              />
            ))}
          </div>
        </TooltipProvider>
      </PopoverContent>
    </Popover>
  );
}

/** Parse a reasoning string into signal / inference / value steps.
 *  Handles formats like:
 *    "quote" → context → metric change
 *    "quote" → metric value (was old).
 *    Correction: field was X but search found Y
 *    DocName: value (was old).
 */
function parseReasoningSteps(reasoning: string): { signal?: string; steps: string[]; inferred: boolean } {
  if (!reasoning) return { steps: [], inferred: false };

  const inferred = /inferred/i.test(reasoning);
  // Clean trailing "Inferred — verify." / "Inferred, not stated explicitly."
  const cleaned = reasoning.replace(/\s*Inferred[^.]*\.?\s*$/i, '').trim();

  // Split on → (arrow) which is the chain delimiter used in all reasoning formats
  const parts = cleaned.split(/\s*→\s*/).map(s => s.trim()).filter(Boolean);

  if (parts.length <= 1) {
    // No chain structure — treat the whole string as a single step
    return { steps: [cleaned], inferred };
  }

  // First part is the signal if it starts with a quote
  const first = parts[0];
  const isQuoted = /^[""\u201C]/.test(first);

  if (isQuoted) {
    // Strip surrounding quotes for display
    const signal = first.replace(/^[""\u201C]+|[""\u201D]+$/g, '').trim();
    return { signal, steps: parts.slice(1), inferred };
  }

  // No quoted signal — all parts are steps
  return { steps: parts, inferred };
}

export function SuggestionCard({
  suggestion,
  onAccept,
  onReject,
}: {
  suggestion: DocumentSuggestion;
  onAccept: () => void;
  onReject: () => void;
}) {
  const [expanded, setExpanded] = useState(false);
  const { signal, steps, inferred } = useMemo(
    () => parseReasoningSteps(suggestion.reasoning),
    [suggestion.reasoning]
  );
  // Determine which steps are "reasoning" vs final "extrapolation"
  const reasoningSteps = steps.length > 1 ? steps.slice(0, -1) : [];
  const extrapolation = steps.length > 1 ? steps[steps.length - 1] : steps[0] ?? '';

  /** Delta: the hero of the card — direction, magnitude, color */
  const delta = useMemo(() => {
    if (!suggestion.changeType) return null;
    if (suggestion.changeType === 'new') {
      return { label: 'New', Icon: Plus, colorCls: 'text-blue-600 dark:text-blue-400' };
    }
    const isUp = suggestion.changeType === 'increase';
    const sign = isUp ? '+' : '−';
    // Percentage and absolute shown separately when both exist
    const pct = suggestion.changePercentage;
    const amt = suggestion.changeAmount;
    let label = '';
    if (pct != null) {
      label = `${sign}${(Math.abs(pct) * 100).toFixed(1)}%`;
    } else if (amt != null) {
      label = `${sign}${formatSuggestionValue(Math.abs(amt), suggestion.columnId)}`;
    }
    if (!label) return null;
    return {
      label,
      Icon: isUp ? TrendingUp : TrendingDown,
      colorCls: isUp
        ? 'text-emerald-600 dark:text-emerald-400'
        : 'text-red-600 dark:text-red-400',
    };
  }, [suggestion.changeType, suggestion.changePercentage, suggestion.changeAmount, suggestion.columnId]);

  const confidencePct = Math.round(suggestion.confidence * 100);
  const confDots = Math.round(suggestion.confidence * 5);
  const confDotColor = confidencePct >= 75
    ? 'bg-emerald-500' : confidencePct >= 50 ? 'bg-amber-500' : 'bg-red-400';

  return (
    <div className="border rounded-lg overflow-hidden">
      {/* Header: metric label, values, delta — the hero section */}
      <div className="p-3 pb-2">
        <div className="flex items-center justify-between mb-1">
          <span className="text-[10px] uppercase tracking-wide text-gray-400 dark:text-gray-500 font-medium">
            {getColumnLabel(suggestion.columnId)}
          </span>
          {/* Confidence dots */}
          <div className="flex items-center gap-1" title={`${confidencePct}% confidence`}>
            <div className="flex gap-0.5">
              {[1, 2, 3, 4, 5].map(i => (
                <div key={i} className={`w-1.5 h-1.5 rounded-full ${i <= confDots ? confDotColor : 'bg-gray-200 dark:bg-gray-700'}`} />
              ))}
            </div>
            <span className="text-[10px] text-gray-400 tabular-nums">{confidencePct}%</span>
          </div>
        </div>
        <div className="flex items-baseline justify-between gap-2">
          <div className="flex items-baseline gap-1.5 min-w-0">
            <span className="text-sm text-gray-400 dark:text-gray-500 line-through tabular-nums">
              {formatSuggestionValue(suggestion.currentValue, suggestion.columnId)}
            </span>
            <ArrowRight className="w-3 h-3 text-gray-300 dark:text-gray-600 shrink-0 relative top-[1px]" />
            <span className="text-base font-semibold text-gray-900 dark:text-gray-100 tabular-nums">
              {formatSuggestionValue(suggestion.suggestedValue, suggestion.columnId)}
            </span>
          </div>
          {delta && (
            <div className={`flex items-center gap-1 text-sm font-semibold shrink-0 ${delta.colorCls}`}>
              <delta.Icon className="w-3.5 h-3.5" />
              {delta.label}
            </div>
          )}
        </div>
      </div>

      {/* Source + expand — always visible middle band */}
      <div className="px-3 py-2 bg-gray-50/80 dark:bg-gray-800/40 border-t">
        {/* Source line — always visible so you know where this came from */}
        <div className="flex items-center gap-1.5 min-w-0">
          {suggestion.source === 'service'
            ? <Cpu className="w-3 h-3 text-violet-500 shrink-0" />
            : <FileText className="w-3 h-3 text-gray-400 shrink-0" />}
          <span className="text-xs text-gray-600 dark:text-gray-300 truncate">
            {suggestion.sourceDocumentName}
          </span>
          {suggestion.citationPage != null && (
            <span className="text-[10px] text-gray-400 shrink-0">p.{suggestion.citationPage}</span>
          )}
          {inferred && (
            <Badge variant="outline" className="text-[9px] px-1 py-0 bg-orange-50 text-orange-600 dark:bg-orange-900/20 dark:text-orange-400 shrink-0 ml-auto">
              inferred
            </Badge>
          )}
        </div>

        {/* Expand toggle — clear affordance */}
        <button
          type="button"
          onClick={() => setExpanded(e => !e)}
          className="flex items-center gap-1 mt-1.5 text-[11px] text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 transition-colors"
        >
          {expanded ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
          <span>{expanded ? 'Hide evidence' : 'View evidence chain'}</span>
        </button>

        {/* Expanded: connected stepper — Source → Reasoning → Conclusion */}
        {expanded && (
          <div className="mt-2.5 ml-0.5" onClick={(e) => e.stopPropagation()}>
            {/* Step 1: SOURCE — signal from document/service */}
            <div className="flex gap-2.5">
              <div className="flex flex-col items-center">
                <div className="w-2 h-2 rounded-full bg-blue-500 ring-2 ring-blue-500/20 shrink-0 mt-0.5" />
                {(reasoningSteps.length > 0 || extrapolation) && (
                  <div className="w-px flex-1 bg-gray-200 dark:bg-gray-700 my-0.5" />
                )}
              </div>
              <div className="pb-2 min-w-0">
                <span className="text-[9px] font-semibold uppercase tracking-wider text-blue-500 dark:text-blue-400">
                  Source
                </span>
                {suggestion.citationSection && (
                  <span className="text-[10px] text-gray-400 ml-1.5">
                    &ldquo;{suggestion.citationSection}&rdquo;
                  </span>
                )}
                {suggestion.documentSummary && (
                  <p className="text-[10px] text-gray-400 dark:text-gray-500 mt-0.5 leading-snug line-clamp-2">
                    {suggestion.documentSummary}
                  </p>
                )}
                {signal && (
                  <div className="flex items-start gap-1 mt-1">
                    <Zap className="w-3 h-3 text-amber-500 mt-0.5 shrink-0" />
                    <span className="text-xs text-gray-600 dark:text-gray-300 leading-snug italic">
                      &ldquo;{signal}&rdquo;
                    </span>
                  </div>
                )}
              </div>
            </div>

            {/* Step 2: REASONING (only if multi-step chain) */}
            {reasoningSteps.length > 0 && (
              <div className="flex gap-2.5">
                <div className="flex flex-col items-center">
                  <div className="w-2 h-2 rounded-full bg-amber-500 ring-2 ring-amber-500/20 shrink-0 mt-0.5" />
                  {extrapolation && (
                    <div className="w-px flex-1 bg-gray-200 dark:bg-gray-700 my-0.5" />
                  )}
                </div>
                <div className="pb-2 min-w-0">
                  <span className="text-[9px] font-semibold uppercase tracking-wider text-amber-500 dark:text-amber-400">
                    Reasoning
                  </span>
                  {reasoningSteps.map((step, i) => (
                    <p key={i} className="text-xs text-gray-600 dark:text-gray-400 mt-0.5 leading-snug">{step}</p>
                  ))}
                </div>
              </div>
            )}

            {/* Step 3: CONCLUSION */}
            {extrapolation && (
              <div className="flex gap-2.5">
                <div className="flex flex-col items-center">
                  <div className="w-2 h-2 rounded-full bg-emerald-500 ring-2 ring-emerald-500/20 shrink-0 mt-0.5" />
                </div>
                <div className="min-w-0">
                  <span className="text-[9px] font-semibold uppercase tracking-wider text-emerald-600 dark:text-emerald-400">
                    {inferred ? 'Extrapolation' : 'Conclusion'}
                  </span>
                  <p className="text-xs text-gray-700 dark:text-gray-300 font-medium mt-0.5 leading-snug">{extrapolation}</p>
                  {inferred && (
                    <Badge variant="outline" className="text-[9px] px-1 py-0 mt-1 bg-orange-50 text-orange-600 dark:bg-orange-900/20 dark:text-orange-400">
                      inferred — verify manually
                    </Badge>
                  )}
                </div>
              </div>
            )}

            {suggestion.extractedMetric && (
              <div className="text-[10px] text-gray-400 dark:text-gray-500 ml-[18px] mt-1">
                Metric: {suggestion.extractedMetric}
              </div>
            )}
          </div>
        )}
      </div>

      {/* Actions */}
      <div className="flex gap-2 p-2 border-t">
        <Button
          size="sm"
          variant="ghost"
          className="flex-1 h-7 text-xs text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200"
          onClick={onReject}
        >
          <X className="w-3 h-3 mr-1" />
          Dismiss
        </Button>
        <Button
          size="sm"
          className="flex-1 h-7 text-xs"
          onClick={onAccept}
        >
          <Check className="w-3 h-3 mr-1" />
          Accept
        </Button>
      </div>
    </div>
  );
}

/** Build Map of row key (companyId | id) -> row for O(1) lookups. Portfolio matrix row id === company_id so suggestions (rowId from doc.company_id) resolve correctly. */
function buildRowLookup(rows: MatrixRow[]): Map<string, MatrixRow> {
  const map = new Map<string, MatrixRow>();
  for (const r of rows) {
    if (r.companyId) map.set(r.companyId, r);
    map.set(r.id, r);
  }
  return map;
}

/**
 * Hook to fetch suggestions for a matrix
 */
export function useDocumentSuggestions(
  matrixData: MatrixData | null,
  fundId?: string
): {
  suggestions: DocumentSuggestion[];
  insights: DocumentInsight[];
  loading: boolean;
  error: string | null;
  refresh: () => Promise<void>;
} {
  const [suggestions, setSuggestions] = useState<DocumentSuggestion[]>([]);
  const [insights, setInsights] = useState<DocumentInsight[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  /** Timestamp of last explicit refresh — skip auto-fetch if it just happened. */
  const lastManualFetchRef = React.useRef(0);
  const abortRef = useRef<AbortController | null>(null);

  // --- Stable refs so fetchSuggestions identity never changes on matrixData mutation ---
  const matrixDataRef = React.useRef(matrixData);
  matrixDataRef.current = matrixData;

  const rowLookup = useMemo(() => {
    if (!matrixData?.rows?.length) return new Map<string, MatrixRow>();
    return buildRowLookup(matrixData.rows);
  }, [matrixData?.rows]);

  const rowLookupRef = React.useRef(rowLookup);
  rowLookupRef.current = rowLookup;

  // Stable key: only changes when the set of row ids changes (not on cell edits)
  const rowKey = useMemo(() => {
    if (!matrixData?.rows?.length) return '';
    return matrixData.rows.map((r) => r.id).join(',');
  }, [matrixData?.rows]);

  const effectiveFundId = fundId ?? matrixData?.metadata?.fundId;

  // fetchSuggestions reads from refs → identity is stable (no deps on matrixData)
  const fetchSuggestions = useCallback(async () => {
    const md = matrixDataRef.current;
    const lookup = rowLookupRef.current;
    const fid = fundId ?? md?.metadata?.fundId;
    if (!md || !fid || !md.rows || md.rows.length === 0) {
      setSuggestions([]);
      setInsights([]);
      return;
    }

    // Abort any in-flight request to prevent stale data overwriting fresh
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    setLoading(true);
    setError(null);

    try {
      const response = await fetch(`/api/matrix/suggestions?fundId=${fid}`, { signal: controller.signal });
      if (!response.ok) throw new Error('Failed to fetch suggestions');

      const data = await response.json();
      const raw = (data.suggestions ?? []) as ApiSuggestion[];
      const rawInsights = (data.insights ?? []) as DocumentInsight[];

      const mapped: DocumentSuggestion[] = [];
      for (const s of raw) {
        if (s.rowId === 'unknown') continue;
        const row = lookup.get(s.rowId) ?? null;
        if (!row) continue;
        const colId = typeof s.columnId === 'string' ? s.columnId : '';
        const cell = row.cells?.[colId];
        mapped.push({
          ...s,
          cellId: `${row.id}-${colId}`,
          rowId: row.id,
          currentValue: s.currentValue ?? cell?.value ?? null,
        });
      }

      const mappedInsights: DocumentInsight[] = rawInsights.map((i) => ({
        ...i,
        rowId: lookup.get(i.rowId)?.id ?? i.rowId,
      }));

      setSuggestions(mapped);
      setInsights(mappedInsights);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
      setSuggestions([]);
      setInsights([]);
    } finally {
      setLoading(false);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fundId]);

  /** Explicit refresh (called after accept/reject). Marks timestamp to suppress the next auto-fetch. */
  const manualRefresh = useCallback(async () => {
    lastManualFetchRef.current = Date.now();
    return fetchSuggestions();
  }, [fetchSuggestions]);

  // Auto-fetch only when fundId or the set of rows changes — NOT on every cell edit
  useEffect(() => {
    if (Date.now() - lastManualFetchRef.current < 2000) return;
    fetchSuggestions();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [effectiveFundId, rowKey]);

  // Abort in-flight request on unmount
  useEffect(() => () => { abortRef.current?.abort(); }, []);

  return {
    suggestions,
    insights,
    loading,
    error,
    refresh: manualRefresh,
  };
}
