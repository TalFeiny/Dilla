'use client';

import React, { useMemo } from 'react';
import dynamic from 'next/dynamic';
import { fmtCurrency } from '@/lib/memo/format';

const TableauLevelCharts = dynamic(
  () => import('@/components/charts/TableauLevelCharts'),
  { ssr: false, loading: () => <div className="h-[280px] animate-pulse bg-muted rounded" /> }
);

// ---------------------------------------------------------------------------
// Types — mirror backend ExecutionResult shape
// ---------------------------------------------------------------------------

export interface EventNode {
  id: string;
  event: string;
  category: string;
  probability: number;
  timing?: string;
  reasoning?: string;
}

export interface CausalLink {
  source: string;
  target: string;
  effect: string;
  magnitude?: number;
  delay_months?: number;
  reasoning?: string;
}

export interface EventChain {
  events: EventNode[];
  links: CausalLink[];
  param_origins: Record<string, string[]>;
}

export interface CascadeRippleEntry {
  period: string;
  delta: number;
  source?: string;
}

export interface ModelExecutionResult {
  model_id: string;
  narrative: string;
  forecast: Array<Record<string, any>>;
  confidence_bands: Record<string, number[]>;
  cascade_ripple: Record<string, CascadeRippleEntry[]>;
  event_chain: EventChain | null;
  milestones?: Array<Record<string, any>>;
  curves?: Record<string, number[]>;
}

interface CascadeModelViewProps {
  result: ModelExecutionResult | null;
  metric?: string;
}

// ---------------------------------------------------------------------------
// Chart builders
// ---------------------------------------------------------------------------

function buildBranchedLineData(result: ModelExecutionResult, metric: string) {
  const forecast = result.forecast;
  if (!forecast || forecast.length === 0) return null;

  const periods = forecast.map(f => f.period || '');
  const baseValues = forecast.map(f => f[metric] ?? 0);

  const series: Array<{ name: string; data: number[]; color: string; style: string }> = [
    { name: 'Base (p50)', data: baseValues, color: '#4e79a7', style: 'solid' },
  ];

  // Add confidence bands as dashed lines
  const bands = result.confidence_bands;
  if (bands) {
    if (bands.p75) {
      series.push({ name: 'p75', data: bands.p75, color: '#10b981', style: 'dashed' });
    }
    if (bands.p25) {
      series.push({ name: 'p25', data: bands.p25, color: '#f28e2c', style: 'dashed' });
    }
    if (bands.p90) {
      series.push({ name: 'p90', data: bands.p90, color: '#76b7b2', style: 'dashed' });
    }
    if (bands.p10) {
      series.push({ name: 'p10', data: bands.p10, color: '#e15759', style: 'dashed' });
    }
  }

  // Add milestone annotations
  const annotations: Array<Record<string, any>> = [];
  if (result.milestones) {
    for (const ms of result.milestones) {
      const idx = periods.indexOf(ms.period);
      if (idx >= 0) {
        annotations.push({
          type: 'fork_point',
          x: idx,
          x_index: idx,
          label: ms.target || ms.label || 'Milestone',
        });
      }
    }
  }

  return { x_axis: periods, series, annotations, format: '$' };
}

function buildCascadeStackedBar(result: ModelExecutionResult) {
  const ripple = result.cascade_ripple;
  if (!ripple || Object.keys(ripple).length === 0) return null;

  // Show cumulative delta per metric across all periods
  const METRIC_COLORS: Record<string, string> = {
    revenue: '#4e79a7',
    cogs: '#e15759',
    gross_profit: '#59a14f',
    total_opex: '#f28e2c',
    ebitda: '#76b7b2',
    cash_balance: '#af7aa1',
    runway_months: '#edc949',
  };

  const metrics = Object.keys(ripple);
  const labels = metrics.map(m => m.replace(/_/g, ' '));
  const values = metrics.map(m => {
    const entries = ripple[m];
    if (!entries || entries.length === 0) return 0;
    return entries[entries.length - 1]?.delta ?? 0;
  });
  const colors = metrics.map(m => METRIC_COLORS[m] || '#bab0ab');

  return {
    labels,
    datasets: [{
      label: 'Cascade Impact',
      data: values,
      backgroundColor: colors,
    }],
  };
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function CascadeModelView({ result, metric = 'revenue' }: CascadeModelViewProps) {
  const lineData = useMemo(
    () => result ? buildBranchedLineData(result, metric) : null,
    [result, metric],
  );

  const stackedData = useMemo(
    () => result ? buildCascadeStackedBar(result) : null,
    [result],
  );

  const eventChain = result?.event_chain;

  if (!result) {
    return (
      <div className="flex items-center justify-center h-[200px] text-xs text-muted-foreground">
        Run model construction to see cascade view
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* 1. Branched line with confidence bands */}
      {lineData && (
        <div>
          <div className="text-[11px] font-medium text-muted-foreground mb-1 uppercase tracking-wide">
            Forecast trajectory with confidence bands
          </div>
          <TableauLevelCharts
            data={lineData}
            type="branched_line"
            title=""
            width="100%"
            height={240}
          />
        </div>
      )}

      {/* 2. Cascade ripple stacked bar */}
      {stackedData && (
        <div>
          <div className="text-[11px] font-medium text-muted-foreground mb-1 uppercase tracking-wide">
            Cascade ripple — P&L impact propagation
          </div>
          <TableauLevelCharts
            data={stackedData}
            type="stacked_bar"
            title=""
            width="100%"
            height={180}
          />
        </div>
      )}

      {/* 3. Event chain narrative */}
      {eventChain && eventChain.events.length > 0 && (
        <div>
          <div className="text-[11px] font-medium text-muted-foreground mb-1.5 uppercase tracking-wide">
            Event chain — why these numbers
          </div>
          <div className="space-y-1.5">
            {eventChain.events.map(evt => (
              <div key={evt.id} className="rounded border border-border/50 bg-muted/20 px-3 py-2">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-medium">{evt.event}</span>
                  <span className="text-[10px] tabular-nums text-muted-foreground">
                    p={evt.probability.toFixed(2)}
                    {evt.timing && ` | ${evt.timing}`}
                  </span>
                </div>
                {evt.reasoning && (
                  <p className="text-[10px] text-muted-foreground mt-0.5 leading-relaxed">{evt.reasoning}</p>
                )}
              </div>
            ))}
          </div>

          {/* Causal links */}
          {eventChain.links.length > 0 && (
            <div className="mt-2">
              <div className="text-[10px] font-medium text-muted-foreground mb-1">Impact chains</div>
              <div className="text-[10px] text-muted-foreground space-y-0.5">
                {eventChain.links.map((link, i) => (
                  <div key={i} className="flex items-center gap-1">
                    <span className="font-mono">{link.source}</span>
                    <span className="text-muted-foreground/60">&rarr;</span>
                    <span className="font-mono">{link.target}</span>
                    <span className="text-muted-foreground/80">
                      ({link.effect}{link.magnitude != null && `, ${link.magnitude > 0 ? '+' : ''}${link.magnitude}`})
                    </span>
                    {link.delay_months != null && link.delay_months > 0 && (
                      <span className="text-muted-foreground/50">[{link.delay_months}mo delay]</span>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Narrative */}
      {result.narrative && (
        <p className="text-[11px] text-muted-foreground leading-relaxed border-t border-border/30 pt-2">
          {result.narrative}
        </p>
      )}
    </div>
  );
}
