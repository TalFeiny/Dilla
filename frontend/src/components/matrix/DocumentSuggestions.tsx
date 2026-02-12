'use client';

import React, { useState, useEffect, useMemo, useCallback } from 'react';
import { Check, X, FileText, Sparkles } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '@/components/ui/popover';
import { MatrixCell, MatrixRow, MatrixData } from './UnifiedMatrix';

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
}

const NON_CURRENCY_COLUMNS = new Set(['headcount', 'optionPool', 'runway', 'runwayMonths', 'grossMargin', 'revenueGrowthAnnual', 'revenueGrowthMonthly']);
function formatSuggestionValue(value: unknown, columnId?: string): string {
  if (value === null || value === undefined) return 'N/A';
  if (typeof value === 'number') {
    if (columnId && NON_CURRENCY_COLUMNS.has(columnId)) {
      if (columnId === 'grossMargin') return `${(value <= 1 ? value * 100 : value).toFixed(1)}%`;
      if (columnId.toLowerCase().includes('growth')) return `${value.toFixed(1)}%`;
      if (columnId === 'optionPool') return `${value} bps`;
      if (columnId === 'runway' || columnId === 'runwayMonths') return `${value.toFixed(0)} mo`;
      return value.toLocaleString();
    }
    if (value >= 1000000) return `$${(value / 1000000).toFixed(2)}M`;
    if (value >= 1000) return `$${(value / 1000).toFixed(0)}K`;
    return `$${value.toFixed(2)}`;
  }
  return String(value);
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

function SuggestionCard({
  suggestion,
  onAccept,
  onReject,
}: {
  suggestion: DocumentSuggestion;
  onAccept: () => void;
  onReject: () => void;
}) {
  const getChangeIndicator = () => {
    if (!suggestion.changeType) return null;

    const isIncrease = suggestion.changeType === 'increase';
    const isDecrease = suggestion.changeType === 'decrease';
    const change = suggestion.changePercentage ?? suggestion.changeAmount;

    if (isIncrease && change != null) {
      return (
        <Badge variant="outline" className="bg-green-50 text-green-700 dark:bg-green-900/20 dark:text-green-400">
          +{typeof change === 'number' && change < 1 ? `${(change * 100).toFixed(1)}%` : formatSuggestionValue(change)}
        </Badge>
      );
    }

    if (isDecrease && change != null) {
      return (
        <Badge variant="outline" className="bg-red-50 text-red-700 dark:bg-red-900/20 dark:text-red-400">
          -{typeof change === 'number' && change < 1 ? `${(change * 100).toFixed(1)}%` : formatSuggestionValue(change)}
        </Badge>
      );
    }

    if (suggestion.changeType === 'new') {
      return (
        <Badge variant="outline" className="bg-blue-50 text-blue-700 dark:bg-blue-900/20 dark:text-blue-400">
          New
        </Badge>
      );
    }

    return null;
  };

  return (
    <div className="border rounded-lg p-3 space-y-2">
      <div className="flex items-start justify-between">
        <div className="flex-1">
          <div className="flex items-center gap-2 mb-1">
            <FileText className="w-4 h-4 text-gray-500" />
            <span className="text-xs text-gray-600 dark:text-gray-400 truncate">
              {suggestion.sourceDocumentName}
            </span>
            {getChangeIndicator()}
          </div>
          
          <div className="flex items-baseline gap-2 mb-2">
            <span className="text-xs text-gray-500">Current:</span>
            <span className="text-sm font-medium">{formatSuggestionValue(suggestion.currentValue, suggestion.columnId)}</span>
            <span className="text-xs text-gray-400">→</span>
            <span className="text-sm font-semibold text-blue-600 dark:text-blue-400">
              {formatSuggestionValue(suggestion.suggestedValue, suggestion.columnId)}
            </span>
          </div>

          <p className="text-xs text-gray-600 dark:text-gray-400 mb-2">
            {suggestion.reasoning}
            {suggestion.citationPage != null && (
              <span className="text-[10px] text-gray-400 dark:text-gray-500 ml-1">
                p.{suggestion.citationPage}{suggestion.citationSection ? ` — ${suggestion.citationSection}` : ''}
              </span>
            )}
          </p>

          {suggestion.extractedMetric && (
            <div className="text-xs text-gray-500 mb-2">
              Metric: <span className="font-medium">{suggestion.extractedMetric}</span>
            </div>
          )}

          <div className="flex items-center gap-2">
            <Badge variant="outline" className="text-xs">
              {Math.round(suggestion.confidence * 100)}% confidence
            </Badge>
          </div>
        </div>
      </div>

      <div className="flex gap-2 pt-2 border-t">
        <Button
          size="sm"
          variant="outline"
          className="flex-1 h-8 text-xs"
          onClick={onReject}
        >
          <X className="w-3 h-3 mr-1" />
          Reject
        </Button>
        <Button
          size="sm"
          className="flex-1 h-8 text-xs"
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

  const rowLookup = useMemo(() => {
    if (!matrixData?.rows?.length) return new Map<string, MatrixRow>();
    return buildRowLookup(matrixData.rows);
  }, [matrixData?.rows]);

  const fetchSuggestions = useCallback(async () => {
    const effectiveFundId = fundId ?? matrixData?.metadata?.fundId;
    if (!matrixData || !effectiveFundId || !matrixData.rows || matrixData.rows.length === 0) {
      setSuggestions([]);
      setInsights([]);
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const response = await fetch(`/api/matrix/suggestions?fundId=${effectiveFundId}`);
      if (!response.ok) throw new Error('Failed to fetch suggestions');

      const data = await response.json();
      const raw = (data.suggestions ?? []) as ApiSuggestion[];
      const rawInsights = (data.insights ?? []) as DocumentInsight[];

      const mapped: DocumentSuggestion[] = [];
      for (const s of raw) {
        if (s.rowId === 'unknown') continue;
        const row = rowLookup.get(s.rowId) ?? null;
        if (!row) continue;
        const colId = typeof s.columnId === 'string' ? s.columnId : '';
        const cell = row.cells?.[colId];
        mapped.push({
          ...s,
          cellId: `${row.id}-${colId}`,
          rowId: row.id,
          // Prefer API's currentValue (matrix value from DB); fallback to cell for backward compatibility
          currentValue: s.currentValue ?? cell?.value ?? null,
        });
      }

      // Map insight rowIds to matrix row ids for display
      const mappedInsights: DocumentInsight[] = rawInsights.map((i) => ({
        ...i,
        rowId: rowLookup.get(i.rowId)?.id ?? i.rowId,
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
  }, [matrixData, fundId, rowLookup]);

  useEffect(() => {
    fetchSuggestions();
  }, [fetchSuggestions]);

  return {
    suggestions,
    insights,
    loading,
    error,
    refresh: fetchSuggestions,
  };
}
