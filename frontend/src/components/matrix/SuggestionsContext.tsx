'use client';

import React, { createContext, useContext, useCallback, useMemo, useState, type ReactNode } from 'react';
import type { DocumentSuggestion, SuggestionAcceptPayload } from './DocumentSuggestions';

export interface SuggestionsContextValue {
  suggestions: DocumentSuggestion[];
  onAccept?: (suggestionId: string, payload?: SuggestionAcceptPayload) => void;
  onReject?: (suggestionId: string) => void;
  /** Optimistic set of accepted suggestion IDs — hides suggestions instantly client-side. */
  localAcceptedIds: Set<string>;
  /** Mark a suggestion as locally accepted (hides it before the next GET refresh). */
  markLocallyAccepted: (suggestionId: string, compositeKey?: string) => void;
  /** Visible suggestions: raw list minus locally accepted. */
  visibleSuggestions: DocumentSuggestion[];
}

const SuggestionsContext = createContext<SuggestionsContextValue | null>(null);

export function SuggestionsProvider({
  children,
  value,
}: {
  children: ReactNode;
  value: Omit<SuggestionsContextValue, 'localAcceptedIds' | 'markLocallyAccepted' | 'visibleSuggestions'>;
}) {
  const [localAcceptedIds, setLocalAcceptedIds] = useState<Set<string>>(new Set());

  const markLocallyAccepted = useCallback((suggestionId: string, compositeKey?: string) => {
    setLocalAcceptedIds((prev) => {
      const next = new Set(prev);
      next.add(suggestionId);
      if (compositeKey) next.add(compositeKey);
      return next;
    });
  }, []);

  const visibleSuggestions = useMemo(
    () => value.suggestions.filter((s) => {
      if (localAcceptedIds.has(s.id)) return false;
      // Also check composite key (companyId::columnId::source)
      const compositeKey = `${s.rowId}::${s.columnId}::${s.source || 'document'}`;
      if (localAcceptedIds.has(compositeKey)) return false;
      return true;
    }),
    [value.suggestions, localAcceptedIds]
  );

  const enrichedValue: SuggestionsContextValue = useMemo(() => ({
    ...value,
    localAcceptedIds,
    markLocallyAccepted,
    visibleSuggestions,
  }), [value, localAcceptedIds, markLocallyAccepted, visibleSuggestions]);

  return (
    <SuggestionsContext.Provider value={enrichedValue}>
      {children}
    </SuggestionsContext.Provider>
  );
}

/**
 * Read suggestions from the nearest SuggestionsProvider.
 * Returns null when outside a provider (e.g. storybook / tests).
 */
export function useSuggestionsContext(): SuggestionsContextValue | null {
  return useContext(SuggestionsContext);
}
