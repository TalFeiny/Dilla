'use client';

import React, { useMemo, useState, useCallback } from 'react';
import { MemoSectionWrapper } from '../MemoSectionWrapper';
import { useMemoContext, type NarrativeCard } from '../MemoContext';
import { Button } from '@/components/ui/button';
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '@/components/ui/select';
import { Loader2, ArrowRight, AlertTriangle, FileText, DollarSign } from 'lucide-react';
import { runCascadeAnalysis } from '@/lib/memo/api-helpers';
import { fmtCurrency } from '@/lib/memo/format';

interface CascadeStep {
  id: string;
  trigger: string;
  clause?: string;
  description: string;
  financial_impact?: number;
  impact_label?: string;
  triggers_next?: string[];
  severity?: 'info' | 'warning' | 'critical';
}

const severityColors = {
  info: 'border-blue-200 dark:border-blue-800 bg-blue-50/50 dark:bg-blue-950/20',
  warning: 'border-amber-200 dark:border-amber-800 bg-amber-50/50 dark:bg-amber-950/20',
  critical: 'border-red-200 dark:border-red-800 bg-red-50/50 dark:bg-red-950/20',
} as const;

export interface CascadeSectionProps {
  onDelete?: () => void;
  readOnly?: boolean;
}

export function CascadeSection({ onDelete, readOnly = false }: CascadeSectionProps) {
  const ctx = useMemoContext();
  const [narrativeCards, setNarrativeCards] = useState<NarrativeCard[]>([]);
  const [cascadeSteps, setCascadeSteps] = useState<CascadeStep[]>([]);
  const [triggerType, setTriggerType] = useState<string>('dilution');
  const [loading, setLoading] = useState(false);

  const triggerTypes = [
    { value: 'dilution', label: 'Dilution Event' },
    { value: 'anti_dilution', label: 'Anti-Dilution' },
    { value: 'drag_along', label: 'Drag-Along' },
    { value: 'liquidation', label: 'Liquidation Preference' },
    { value: 'conversion', label: 'Conversion Trigger' },
    { value: 'default', label: 'Covenant Default' },
  ];

  const handleRunCascade = useCallback(async () => {
    setLoading(true);
    try {
      const data = await runCascadeAnalysis(ctx.companyId, triggerType, ctx.activeBranchId);

      // The cascade engine (CascadeGraph) returns CascadeResult with:
      // { trigger, steps: CascadeStep[], cap_table_delta, cash_flow_delta, ... }
      // But it may come through unified-brain wrapped in { result: { ... } }
      const inner = data?.result ?? data;

      // Find the steps array — might be under different keys
      const rawSteps: any[] = inner?.steps
        ?? inner?.cascade
        ?? inner?.cascade_steps
        ?? data?.steps
        ?? [];

      const steps: CascadeStep[] = rawSteps.map((s: any, i: number) => ({
        id: s.id ?? `step-${s.step_number ?? s.step ?? i}`,
        trigger: s.trigger ?? s.param_affected ?? s.edge_type ?? '',
        clause: s.clause ?? s.source_clause?.clause_ref ?? s.source_clause,
        description: s.description ?? '',
        financial_impact: s.financial_impact,
        impact_label: s.impact_label,
        triggers_next: s.triggers_next ?? s.downstream_triggers ?? [],
        severity: s.severity ?? (Math.abs(s.financial_impact ?? 0) > 1000000 ? 'critical'
          : Math.abs(s.financial_impact ?? 0) > 100000 ? 'warning' : 'info'),
      }));

      setCascadeSteps(steps);
    } catch (err) {
      console.warn('Cascade failed:', err);
    } finally {
      setLoading(false);
    }
  }, [ctx.companyId, ctx.activeBranchId, triggerType]);

  const totalImpact = useMemo(
    () => cascadeSteps.reduce((sum, s) => sum + (s.financial_impact || 0), 0),
    [cascadeSteps]
  );

  const collapsedSummary = cascadeSteps.length > 0
    ? `${cascadeSteps.length} steps | Net impact: ${fmtCurrency(totalImpact)}`
    : 'Cascade — run analysis to view dependency chain';

  const aiContext = useMemo(() => ({
    triggerType,
    steps: cascadeSteps,
    totalImpact,
  }), [triggerType, cascadeSteps, totalImpact]);

  const configBar = (
    <>
      <div className="flex items-center gap-1.5">
        <span className="text-muted-foreground">Trigger:</span>
        <Select value={triggerType} onValueChange={setTriggerType}>
          <SelectTrigger className="h-6 w-[140px] text-[11px]"><SelectValue /></SelectTrigger>
          <SelectContent>
            {triggerTypes.map(t => (
              <SelectItem key={t.value} value={t.value}>{t.label}</SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>
      {!readOnly && (
        <Button
          variant="outline"
          size="sm"
          className="h-6 text-[11px] gap-1 ml-auto"
          onClick={handleRunCascade}
          disabled={loading}
        >
          {loading ? <Loader2 className="h-3 w-3 animate-spin" /> : <ArrowRight className="h-3 w-3" />}
          Run Cascade
        </Button>
      )}
    </>
  );

  return (
    <MemoSectionWrapper
      sectionType="cascade"
      title="Cascade Analysis"
      collapsedSummary={collapsedSummary}
      configContent={configBar}
      narrativeCards={narrativeCards}
      onNarrativeCardsChange={setNarrativeCards}
      aiDataContext={aiContext}
      onDelete={onDelete}
      readOnly={readOnly}
    >
      {cascadeSteps.length > 0 ? (
        <div className="space-y-2">
          {cascadeSteps.map((step, i) => (
            <div key={step.id} className="flex items-start gap-2">
              {/* Step number */}
              <div className="flex-shrink-0 w-6 h-6 rounded-full bg-muted flex items-center justify-center text-[10px] font-mono font-semibold mt-0.5">
                {i + 1}
              </div>

              {/* Step content */}
              <div className={`flex-1 rounded-md border p-2.5 ${severityColors[step.severity || 'info']}`}>
                <div className="flex items-start justify-between gap-2">
                  <div className="flex-1">
                    <div className="flex items-center gap-1.5 mb-0.5">
                      {step.severity === 'critical' && <AlertTriangle className="h-3 w-3 text-red-500" />}
                      <span className="text-xs font-semibold">{step.trigger}</span>
                    </div>
                    <p className="text-[11px] text-muted-foreground leading-relaxed">{step.description}</p>
                    {step.clause && (
                      <div className="flex items-center gap-1 mt-1 text-[10px] text-muted-foreground">
                        <FileText className="h-2.5 w-2.5" />
                        <span className="font-mono">{step.clause}</span>
                      </div>
                    )}
                  </div>
                  {step.financial_impact != null && (
                    <div className={`text-xs font-semibold tabular-nums whitespace-nowrap ${step.financial_impact >= 0 ? 'text-emerald-600' : 'text-red-600'}`}>
                      <div className="flex items-center gap-0.5">
                        <DollarSign className="h-3 w-3" />
                        {fmtCurrency(Math.abs(step.financial_impact))}
                      </div>
                      {step.impact_label && <span className="text-[9px] text-muted-foreground font-normal">{step.impact_label}</span>}
                    </div>
                  )}
                </div>
                {step.triggers_next && step.triggers_next.length > 0 && (
                  <div className="mt-1.5 flex items-center gap-1 text-[10px] text-muted-foreground">
                    <ArrowRight className="h-2.5 w-2.5" />
                    Triggers: {step.triggers_next.join(', ')}
                  </div>
                )}
              </div>

              {/* Connector arrow */}
              {i < cascadeSteps.length - 1 && (
                <div className="flex-shrink-0 w-6 flex justify-center">
                  <div className="w-px h-4 bg-border" />
                </div>
              )}
            </div>
          ))}

          {/* Total impact summary */}
          <div className="flex items-center justify-between px-3 py-2 rounded-md bg-muted/50 border border-border/50 text-xs">
            <span className="font-medium">Net Financial Impact</span>
            <span className={`font-semibold tabular-nums ${totalImpact >= 0 ? 'text-emerald-600' : 'text-red-600'}`}>
              {totalImpact >= 0 ? '+' : ''}{fmtCurrency(totalImpact)}
            </span>
          </div>
        </div>
      ) : (
        <div className="flex items-center justify-center h-[120px] text-xs text-muted-foreground">
          Select a trigger type and run cascade to view dependency chain
        </div>
      )}
    </MemoSectionWrapper>
  );
}
