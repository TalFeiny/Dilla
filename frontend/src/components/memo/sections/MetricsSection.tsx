'use client';

import React, { useMemo, useState } from 'react';
import { MemoSectionWrapper } from '../MemoSectionWrapper';
import { useMemoContext, type NarrativeCard, type ComputedMetric } from '../MemoContext';
import { TrendingUp, TrendingDown, Minus } from 'lucide-react';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function formatMetricValue(v: number, unit: ComputedMetric['unit']): string {
  switch (unit) {
    case 'currency':
      if (Math.abs(v) >= 1e9) return `$${(v / 1e9).toFixed(1)}B`;
      if (Math.abs(v) >= 1e6) return `$${(v / 1e6).toFixed(1)}M`;
      if (Math.abs(v) >= 1e3) return `$${(v / 1e3).toFixed(0)}K`;
      return `$${v.toLocaleString()}`;
    case 'percentage': return `${(v * 100).toFixed(1)}%`;
    case 'months': return `${v.toFixed(0)} mo`;
    case 'ratio': return `${v.toFixed(2)}x`;
    default: return v.toLocaleString();
  }
}

const severityColors = {
  green: 'border-emerald-200 dark:border-emerald-800 bg-emerald-50/50 dark:bg-emerald-950/20',
  amber: 'border-amber-200 dark:border-amber-800 bg-amber-50/50 dark:bg-amber-950/20',
  red: 'border-red-200 dark:border-red-800 bg-red-50/50 dark:bg-red-950/20',
} as const;

const trendIcons = {
  up: TrendingUp,
  down: TrendingDown,
  flat: Minus,
} as const;

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export interface MetricsSectionProps {
  onDelete?: () => void;
  readOnly?: boolean;
}

export function MetricsSection({ onDelete, readOnly = false }: MetricsSectionProps) {
  const ctx = useMemoContext();
  const [narrativeCards, setNarrativeCards] = useState<NarrativeCard[]>([]);
  const [showAll, setShowAll] = useState(true);

  const metrics = ctx.metrics;

  // Compute from grid if no metrics from backend
  const derivedMetrics = useMemo<ComputedMetric[]>(() => {
    if (metrics.length > 0) return metrics;

    // Try to derive basic metrics from grid data
    const vals = (id: string) => {
      const row = ctx.matrixData.rows.find(r => r.id === id);
      if (!row) return [];
      return ctx.matrixData.columns
        .filter(c => c.id !== 'lineItem')
        .map(c => {
          const cell = row.cells[c.id];
          const v = cell ? (typeof cell.value === 'number' ? cell.value : parseFloat(cell.value)) : NaN;
          return isNaN(v) ? 0 : v;
        });
    };

    const revenue = vals('revenue').concat(vals('total_revenue'));
    const ebitda = vals('ebitda');
    const netIncome = vals('net_income');
    const cashBalance = vals('cash_balance');
    const netBurn = vals('net_burn_rate');
    const runway = vals('runway_months');

    const derived: ComputedMetric[] = [];
    const lastVal = (arr: number[]) => arr[arr.length - 1] || 0;
    const prevVal = (arr: number[]) => arr[arr.length - 2] || 0;

    if (revenue.length > 0 && lastVal(revenue) !== 0) {
      const curr = lastVal(revenue);
      const prev = prevVal(revenue);
      derived.push({
        id: 'revenue', label: 'Revenue', value: curr, unit: 'currency',
        trend: curr > prev ? 'up' : curr < prev ? 'down' : 'flat',
        trendValue: prev ? (curr - prev) / prev : 0,
        severity: 'green',
      });
    }
    if (ebitda.length > 0) {
      const curr = lastVal(ebitda);
      derived.push({
        id: 'ebitda', label: 'EBITDA', value: curr, unit: 'currency',
        severity: curr >= 0 ? 'green' : 'red',
        trend: curr > prevVal(ebitda) ? 'up' : 'down',
      });
    }
    if (revenue.length > 0 && ebitda.length > 0 && lastVal(revenue) !== 0) {
      const margin = lastVal(ebitda) / lastVal(revenue);
      derived.push({
        id: 'ebitda_margin', label: 'EBITDA Margin', value: margin, unit: 'percentage',
        severity: margin > 0.2 ? 'green' : margin > 0 ? 'amber' : 'red',
      });
    }
    if (cashBalance.length > 0) {
      derived.push({
        id: 'cash', label: 'Cash Balance', value: lastVal(cashBalance), unit: 'currency',
        severity: lastVal(cashBalance) > 0 ? 'green' : 'red',
      });
    }
    if (runway.length > 0) {
      const r = lastVal(runway);
      derived.push({
        id: 'runway', label: 'Runway', value: r, unit: 'months',
        severity: r > 12 ? 'green' : r > 6 ? 'amber' : 'red',
      });
    }

    return derived;
  }, [metrics, ctx.matrixData]);

  const collapsedSummary = derivedMetrics.length > 0
    ? derivedMetrics.slice(0, 3).map(m => `${m.label}: ${formatMetricValue(m.value, m.unit)}`).join(' | ')
    : 'Metrics — no data';

  const aiContext = useMemo(() => ({
    metrics: derivedMetrics.map(m => ({ id: m.id, label: m.label, value: m.value, unit: m.unit, trend: m.trend, severity: m.severity })),
  }), [derivedMetrics]);

  return (
    <MemoSectionWrapper
      sectionType="metrics"
      title="Key Metrics"
      collapsedSummary={collapsedSummary}
      narrativeCards={narrativeCards}
      onNarrativeCardsChange={setNarrativeCards}
      aiDataContext={aiContext}
      onDelete={onDelete}
      readOnly={readOnly}
    >
      {derivedMetrics.length > 0 ? (
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
          {derivedMetrics.map(metric => {
            const TrendIcon = metric.trend ? trendIcons[metric.trend] : null;
            const colorClass = metric.severity ? severityColors[metric.severity] : 'border-border bg-card';

            return (
              <div
                key={metric.id}
                className={`rounded-lg border p-2.5 ${colorClass} group/card relative`}
                title={metric.derivation}
              >
                <div className="text-[10px] text-muted-foreground font-medium uppercase tracking-wider mb-0.5">
                  {metric.label}
                </div>
                <div className="text-lg font-semibold tabular-nums leading-tight">
                  {formatMetricValue(metric.value, metric.unit)}
                </div>
                {TrendIcon && (
                  <div className={`flex items-center gap-0.5 text-[10px] mt-0.5 ${
                    metric.trend === 'up' ? 'text-emerald-600 dark:text-emerald-400' :
                    metric.trend === 'down' ? 'text-red-600 dark:text-red-400' : 'text-muted-foreground'
                  }`}>
                    <TrendIcon className="h-2.5 w-2.5" />
                    {metric.trendValue != null && (
                      <span>{(metric.trendValue * 100).toFixed(1)}%</span>
                    )}
                  </div>
                )}
                {/* Branch delta — show if branches exist */}
                {ctx.activeBranches.length > 0 && ctx.activeBranchId && (
                  <div className="text-[9px] text-muted-foreground mt-1 opacity-0 group-hover/card:opacity-100 transition-opacity">
                    Branch: {ctx.activeBranches.find(b => b.id === ctx.activeBranchId)?.name || ctx.activeBranchId}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      ) : (
        <div className="flex items-center justify-center h-[120px] text-xs text-muted-foreground">
          Build a forecast or upload data to see metrics
        </div>
      )}
    </MemoSectionWrapper>
  );
}
