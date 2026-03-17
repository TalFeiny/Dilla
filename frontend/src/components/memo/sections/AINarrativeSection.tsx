'use client';

import React, { useMemo, useState, useCallback } from 'react';
import { MemoSectionWrapper } from '../MemoSectionWrapper';
import { useMemoContext, type NarrativeCard } from '../MemoContext';
import { Button } from '@/components/ui/button';
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '@/components/ui/select';
import { Loader2, Sparkles, RefreshCw } from 'lucide-react';
type NarrativeStyle = 'board_summary' | 'investor_update' | 'internal_review' | 'risk_assessment';

export interface AINarrativeSectionProps {
  onDelete?: () => void;
  readOnly?: boolean;
}

export function AINarrativeSection({ onDelete, readOnly = false }: AINarrativeSectionProps) {
  const ctx = useMemoContext();
  const [narrativeCards, setNarrativeCards] = useState<NarrativeCard[]>([]);
  const [narrative, setNarrative] = useState<string>('');
  const [style, setStyle] = useState<NarrativeStyle>('board_summary');
  const [generating, setGenerating] = useState(false);

  const styleLabels: Record<NarrativeStyle, string> = {
    board_summary: 'Board Summary',
    investor_update: 'Investor Update',
    internal_review: 'Internal Review',
    risk_assessment: 'Risk Assessment',
  };

  // Context for narrative — backend resolves financials from company_id
  const dataContext = useMemo(() => {
    return {
      style,
      company_id: ctx.companyId,
      branch_id: (ctx as any).activeBranchId ?? null,
      metrics: ctx.metrics,
      signals: ctx.signals,
      branches: ctx.activeBranches.map(b => ({ name: b.name, probability: b.probability })),
      drivers: ctx.driverRegistry.map(d => d.label),
    };
  }, [ctx, style]);

  const handleGenerate = useCallback(async () => {
    setGenerating(true);
    try {
      const text = await ctx.requestNarrative('ai_narrative', dataContext);
      setNarrative(text);
    } finally {
      setGenerating(false);
    }
  }, [ctx, dataContext]);

  const collapsedSummary = narrative
    ? narrative.slice(0, 100) + (narrative.length > 100 ? '...' : '')
    : `AI Narrative — ${styleLabels[style]}`;

  const configBar = (
    <>
      <div className="flex items-center gap-1.5">
        <span className="text-muted-foreground">Style:</span>
        <Select value={style} onValueChange={(v) => setStyle(v as NarrativeStyle)}>
          <SelectTrigger className="h-6 w-[130px] text-[11px]"><SelectValue /></SelectTrigger>
          <SelectContent>
            {Object.entries(styleLabels).map(([k, v]) => (
              <SelectItem key={k} value={k}>{v}</SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>
      {!readOnly && (
        <Button variant="outline" size="sm" className="h-6 text-[11px] gap-1 ml-auto" onClick={handleGenerate} disabled={generating}>
          {generating ? <Loader2 className="h-3 w-3 animate-spin" /> : narrative ? <RefreshCw className="h-3 w-3" /> : <Sparkles className="h-3 w-3" />}
          {narrative ? 'Regenerate' : 'Generate'}
        </Button>
      )}
    </>
  );

  return (
    <MemoSectionWrapper
      sectionType="ai_narrative"
      title={styleLabels[style]}
      collapsedSummary={collapsedSummary}
      configContent={configBar}
      narrativeCards={narrativeCards}
      onNarrativeCardsChange={setNarrativeCards}
      showAnalyze={false}
      onDelete={onDelete}
      readOnly={readOnly}
    >
      {narrative ? (
        <div
          className="prose prose-sm dark:prose-invert max-w-none text-sm leading-relaxed"
          contentEditable={!readOnly}
          suppressContentEditableWarning
          onBlur={(e) => setNarrative(e.currentTarget.textContent || '')}
        >
          {narrative.split('\n').map((line, i) => (
            <p key={i} className={line.trim() === '' ? 'h-2' : ''}>
              {line}
            </p>
          ))}
        </div>
      ) : (
        <div className="flex flex-col items-center justify-center h-[160px] gap-2 text-xs text-muted-foreground">
          <Sparkles className="h-5 w-5 opacity-40" />
          <span>Generate an AI narrative from your financial data</span>
          <span className="text-[10px]">Summarizes P&L, cash flow, metrics, signals, and scenarios</span>
        </div>
      )}
    </MemoSectionWrapper>
  );
}
