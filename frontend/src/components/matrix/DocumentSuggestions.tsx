'use client';

import React, { useState, useEffect, useMemo, useCallback, useRef } from 'react';
import { Check, X, FileText, Sparkles, ChevronDown, ChevronUp, Zap, ArrowRight } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '@/components/ui/popover';
import { MatrixCell, MatrixRow, MatrixData } from './UnifiedMatrix';
import { formatSuggestionValue } from '@/lib/matrix/cell-formatters';

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
      <PopoverContent className="w-96" align="start">
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <h4 className="font-semibold text-sm">Document Suggestions</h4>
            <Badge variant="secondary" className="text-xs">
              {pendingSuggestions.length} pending
            </Badge>
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

function SuggestionCard({
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
  const hasChain = !!signal || steps.length > 1;

  const changeBadge = useMemo(() => {
    if (!suggestion.changeType) return null;
    const change = suggestion.changePercentage ?? suggestion.changeAmount;

    if (suggestion.changeType === 'new') {
      return { label: 'New', cls: 'bg-blue-50 text-blue-700 dark:bg-blue-900/20 dark:text-blue-400' };
    }
    if (change == null) return null;

    const formatted = typeof change === 'number' && change < 1
      ? `${(change * 100).toFixed(1)}%`
      : formatSuggestionValue(change);
    if (suggestion.changeType === 'increase') {
      return { label: `+${formatted}`, cls: 'bg-green-50 text-green-700 dark:bg-green-900/20 dark:text-green-400' };
    }
    if (suggestion.changeType === 'decrease') {
      return { label: `-${formatted}`, cls: 'bg-red-50 text-red-700 dark:bg-red-900/20 dark:text-red-400' };
    }
    return null;
  }, [suggestion.changeType, suggestion.changePercentage, suggestion.changeAmount]);

  const confidencePct = Math.round(suggestion.confidence * 100);
  const confColor = confidencePct >= 75
    ? 'text-green-700 dark:text-green-400 bg-green-50 dark:bg-green-900/20'
    : confidencePct >= 50
      ? 'text-yellow-700 dark:text-yellow-400 bg-yellow-50 dark:bg-yellow-900/20'
      : 'text-red-700 dark:text-red-400 bg-red-50 dark:bg-red-900/20';

  return (
    <div className="border rounded-lg p-3 space-y-2">
      {/* Header: source doc + change badge */}
      <div className="flex items-center gap-2">
        <FileText className="w-3.5 h-3.5 text-gray-400 shrink-0" />
        <span className="text-xs text-gray-500 dark:text-gray-400 truncate flex-1">
          {suggestion.sourceDocumentName}
        </span>
        {changeBadge && (
          <Badge variant="outline" className={`text-[10px] shrink-0 ${changeBadge.cls}`}>
            {changeBadge.label}
          </Badge>
        )}
      </div>

      {/* Value change: current → suggested */}
      <div className="flex items-baseline gap-1.5 px-1">
        <span className="text-sm text-gray-500 dark:text-gray-400 font-medium tabular-nums">
          {formatSuggestionValue(suggestion.currentValue, suggestion.columnId)}
        </span>
        <ArrowRight className="w-3 h-3 text-gray-400 shrink-0" />
        <span className="text-sm font-semibold text-blue-600 dark:text-blue-400 tabular-nums">
          {formatSuggestionValue(suggestion.suggestedValue, suggestion.columnId)}
        </span>
      </div>

      {/* Reasoning chain — collapsed: first step only; expanded: full chain */}
      {hasChain ? (
        <div className="space-y-1">
          {/* Signal line */}
          {signal && (
            <div className="flex items-start gap-1.5 px-1">
              <Zap className="w-3 h-3 text-amber-500 mt-0.5 shrink-0" />
              <span className="text-xs text-gray-700 dark:text-gray-300 leading-snug">
                &ldquo;{signal}&rdquo;
              </span>
            </div>
          )}

          {/* Steps — show first always, rest only when expanded */}
          {steps.slice(0, expanded ? steps.length : 1).map((step, i) => (
            <div key={i} className="flex items-start gap-1.5 px-1 pl-3">
              <ArrowRight className="w-3 h-3 text-gray-400 mt-0.5 shrink-0" />
              <span className="text-xs text-gray-600 dark:text-gray-400 leading-snug">{step}</span>
            </div>
          ))}

          {/* Expand/collapse toggle */}
          {steps.length > 1 && (
            <button
              type="button"
              onClick={() => setExpanded(e => !e)}
              className="flex items-center gap-1 px-1 pl-3 text-[11px] text-blue-600 dark:text-blue-400 hover:text-blue-700 dark:hover:text-blue-300"
            >
              {expanded ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
              {expanded ? 'Less' : `${steps.length - 1} more step${steps.length - 1 > 1 ? 's' : ''}`}
            </button>
          )}
        </div>
      ) : (
        /* Fallback: single-line reasoning (no chain structure) */
        <p className="text-xs text-gray-600 dark:text-gray-400 px-1 leading-snug">
          {steps[0] ?? suggestion.reasoning}
        </p>
      )}

      {/* Metadata row: confidence + inferred tag + citation */}
      <div className="flex items-center gap-1.5 flex-wrap px-1">
        <Badge variant="outline" className={`text-[10px] ${confColor}`}>
          {confidencePct}%
        </Badge>
        {inferred && (
          <Badge variant="outline" className="text-[10px] bg-orange-50 text-orange-600 dark:bg-orange-900/20 dark:text-orange-400">
            inferred
          </Badge>
        )}
        {suggestion.citationPage != null && (
          <span className="text-[10px] text-gray-400 dark:text-gray-500">
            p.{suggestion.citationPage}{suggestion.citationSection ? ` — ${suggestion.citationSection}` : ''}
          </span>
        )}
        {suggestion.extractedMetric && (
          <span className="text-[10px] text-gray-400 dark:text-gray-500">
            {suggestion.extractedMetric}
          </span>
        )}
      </div>

      {/* Actions */}
      <div className="flex gap-2 pt-1.5 border-t">
        <Button
          size="sm"
          variant="outline"
          className="flex-1 h-7 text-xs"
          onClick={onReject}
        >
          <X className="w-3 h-3 mr-1" />
          Reject
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
