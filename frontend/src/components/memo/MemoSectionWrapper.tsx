'use client';

import React, { useState, useCallback, type ReactNode } from 'react';
import { ChevronDown, ChevronUp, Settings2, X, Sparkles, Loader2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { useMemoContextSafe, type NarrativeCard } from './MemoContext';

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

export interface MemoSectionWrapperProps {
  /** Section type label shown in the header badge */
  sectionType: string;
  /** Display title */
  title: string;
  /** One-line summary shown when collapsed */
  collapsedSummary?: string;
  /** Main content renderer */
  children: ReactNode;
  /** Config bar content (chart type pickers, toggles, dropdowns) */
  configContent?: ReactNode;
  /** Expandable detail content (grid rows, subcategories, derivations) */
  detailContent?: ReactNode;
  /** Narrative cards overlaid on the section (AI text annotations) */
  narrativeCards?: NarrativeCard[];
  /** Called when narrative cards change (add/edit/remove) */
  onNarrativeCardsChange?: (cards: NarrativeCard[]) => void;
  /** Data context to pass to AI when "Analyze" is clicked */
  aiDataContext?: Record<string, any>;
  /** Whether to show the Analyze button */
  showAnalyze?: boolean;
  /** Called when user deletes this section */
  onDelete?: () => void;
  /** Read-only mode */
  readOnly?: boolean;
  /** Custom className */
  className?: string;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function MemoSectionWrapper({
  sectionType,
  title,
  collapsedSummary,
  children,
  configContent,
  detailContent,
  narrativeCards,
  onNarrativeCardsChange,
  aiDataContext,
  showAnalyze = true,
  onDelete,
  readOnly = false,
  className = '',
}: MemoSectionWrapperProps) {
  const [collapsed, setCollapsed] = useState(false);
  const [showConfig, setShowConfig] = useState(false);
  const [showDetail, setShowDetail] = useState(false);
  const [analyzing, setAnalyzing] = useState(false);
  const memo = useMemoContextSafe();

  // ---- AI Analyze ----
  const handleAnalyze = useCallback(async () => {
    if (!memo || !aiDataContext) return;
    setAnalyzing(true);
    try {
      const narrative = await memo.requestNarrative(sectionType, aiDataContext);
      if (narrative && onNarrativeCardsChange) {
        const card: NarrativeCard = {
          id: `narr-${Date.now()}`,
          text: narrative,
          position: 'bottom-right',
          severity: 'info',
        };
        onNarrativeCardsChange([...(narrativeCards || []), card]);
      }
    } finally {
      setAnalyzing(false);
    }
  }, [memo, sectionType, aiDataContext, narrativeCards, onNarrativeCardsChange]);

  // ---- Remove narrative card ----
  const removeNarrativeCard = useCallback((cardId: string) => {
    if (!onNarrativeCardsChange || !narrativeCards) return;
    onNarrativeCardsChange(narrativeCards.filter(c => c.id !== cardId));
  }, [narrativeCards, onNarrativeCardsChange]);

  return (
    <div className={`memo-section-interactive group/section relative rounded-lg border border-border/50 bg-card/50 my-3 ${className}`}>
      {/* Header bar */}
      <div className="flex items-center gap-2 px-3 py-2 border-b border-border/30">
        {/* Type badge */}
        <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-muted text-muted-foreground uppercase tracking-wider shrink-0">
          {sectionType}
        </span>

        {/* Title */}
        <span className="text-sm font-medium flex-1 truncate">{title}</span>

        {/* Action buttons */}
        <div className="flex items-center gap-0.5 opacity-0 group-hover/section:opacity-100 transition-opacity print:hidden">
          {/* Collapse */}
          <Button
            variant="ghost"
            size="sm"
            className="h-6 w-6 p-0"
            onClick={() => setCollapsed(!collapsed)}
            title={collapsed ? 'Expand' : 'Collapse'}
          >
            {collapsed ? <ChevronDown className="h-3 w-3" /> : <ChevronUp className="h-3 w-3" />}
          </Button>

          {/* Config toggle */}
          {configContent && (
            <Button
              variant="ghost"
              size="sm"
              className={`h-6 w-6 p-0 ${showConfig ? 'text-primary' : ''}`}
              onClick={() => setShowConfig(!showConfig)}
              title="Settings"
            >
              <Settings2 className="h-3 w-3" />
            </Button>
          )}

          {/* Analyze (AI) */}
          {showAnalyze && memo && !readOnly && (
            <Button
              variant="ghost"
              size="sm"
              className="h-6 px-1.5 gap-1 text-[10px]"
              onClick={handleAnalyze}
              disabled={analyzing}
              title="AI Analysis"
            >
              {analyzing ? <Loader2 className="h-3 w-3 animate-spin" /> : <Sparkles className="h-3 w-3" />}
              Analyze
            </Button>
          )}

          {/* Delete */}
          {!readOnly && onDelete && (
            <Button
              variant="ghost"
              size="sm"
              className="h-6 w-6 p-0 hover:text-destructive"
              onClick={onDelete}
              title="Remove section"
            >
              <X className="h-3 w-3" />
            </Button>
          )}
        </div>
      </div>

      {/* Config bar (inline, toggled) */}
      {showConfig && configContent && !collapsed && (
        <div className="px-3 py-2 border-b border-border/20 bg-muted/30 flex items-center gap-3 flex-wrap text-xs">
          {configContent}
        </div>
      )}

      {/* Main content or collapsed summary */}
      {collapsed ? (
        <div
          className="px-3 py-2 text-xs text-muted-foreground cursor-pointer"
          onClick={() => setCollapsed(false)}
        >
          {collapsedSummary || `${title} — click to expand`}
        </div>
      ) : (
        <div className="relative">
          {/* Main content */}
          <div className="px-3 py-3">
            {children}
          </div>

          {/* Narrative cards overlaid */}
          {narrativeCards && narrativeCards.length > 0 && (
            <div className="px-3 pb-3 space-y-2">
              {narrativeCards.map(card => (
                <div
                  key={card.id}
                  className={`relative rounded-md px-3 py-2 text-xs leading-relaxed border ${
                    card.severity === 'critical'
                      ? 'bg-red-50 dark:bg-red-950/20 border-red-200 dark:border-red-800 text-red-800 dark:text-red-200'
                      : card.severity === 'warning'
                        ? 'bg-amber-50 dark:bg-amber-950/20 border-amber-200 dark:border-amber-800 text-amber-800 dark:text-amber-200'
                        : 'bg-blue-50 dark:bg-blue-950/20 border-blue-200 dark:border-blue-800 text-blue-800 dark:text-blue-200'
                  }`}
                >
                  <span className="text-[9px] font-mono uppercase tracking-wider opacity-60 block mb-0.5">AI Analysis</span>
                  <p
                    contentEditable={!readOnly}
                    suppressContentEditableWarning
                    className="outline-none"
                    onBlur={(e) => {
                      if (!onNarrativeCardsChange || !narrativeCards) return;
                      const updated = narrativeCards.map(c =>
                        c.id === card.id ? { ...c, text: e.currentTarget.textContent || '' } : c
                      );
                      onNarrativeCardsChange(updated);
                    }}
                  >
                    {card.text}
                  </p>
                  {!readOnly && (
                    <button
                      className="absolute top-1 right-1 opacity-0 group-hover/section:opacity-100 h-4 w-4 rounded-full bg-muted text-muted-foreground text-[10px] flex items-center justify-center hover:bg-destructive hover:text-white transition-colors"
                      onClick={() => removeNarrativeCard(card.id)}
                    >
                      <X className="h-2.5 w-2.5" />
                    </button>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Expandable detail */}
      {detailContent && !collapsed && (
        <>
          <button
            className="w-full px-3 py-1.5 text-[10px] text-muted-foreground hover:text-foreground border-t border-border/20 hover:bg-muted/20 transition-colors text-left flex items-center gap-1"
            onClick={() => setShowDetail(!showDetail)}
          >
            {showDetail ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
            {showDetail ? 'Hide details' : 'Show details'}
          </button>
          {showDetail && (
            <div className="px-3 pb-3 border-t border-border/20">
              {detailContent}
            </div>
          )}
        </>
      )}
    </div>
  );
}
