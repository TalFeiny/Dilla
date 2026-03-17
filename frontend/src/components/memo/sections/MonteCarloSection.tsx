'use client';

import React, { useMemo, useState, useCallback } from 'react';
import dynamic from 'next/dynamic';
import { MemoSectionWrapper } from '../MemoSectionWrapper';
import { useMemoContext, type NarrativeCard } from '../MemoContext';
import { Button } from '@/components/ui/button';
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '@/components/ui/select';
import { Loader2, Play } from 'lucide-react';
import { runMonteCarlo } from '@/lib/memo/api-helpers';
import { fmtCurrency } from '@/lib/memo/format';

const TableauLevelCharts = dynamic(
  () => import('@/components/charts/TableauLevelCharts'),
  { ssr: false, loading: () => <div className="h-[300px] animate-pulse bg-muted rounded" /> }
);

type ChartMode = 'monte_carlo_fan' | 'monte_carlo_histogram' | 'probability_cloud';

interface MCResult {
  percentiles: Record<string, number>; // p10, p25, p50, p75, p90
  mean: number;
  std_dev: number;
  simulations: number;
  fan_data?: Array<Record<string, any>>; // time-series with percentile bands
  histogram?: Array<{ bucket: number; count: number }>;
}

export interface MonteCarloSectionProps {
  onDelete?: () => void;
  readOnly?: boolean;
}

export function MonteCarloSection({ onDelete, readOnly = false }: MonteCarloSectionProps) {
  const ctx = useMemoContext();
  const [chartMode, setChartMode] = useState<ChartMode>('monte_carlo_fan');
  const [narrativeCards, setNarrativeCards] = useState<NarrativeCard[]>([]);
  const [result, setResult] = useState<MCResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [targetMetric, setTargetMetric] = useState<string>('revenue');
  const [simCount, setSimCount] = useState<string>('1000');

  const handleRunMonteCarlo = useCallback(async () => {
    setLoading(true);
    try {
      // Backend pulls actuals from Supabase — no grid scraping needed
      const data = await runMonteCarlo(
        ctx.companyId,
        targetMetric,
        parseInt(simCount) || 1000,
        (ctx as any).activeBranchId ?? null,
      );
      setResult(data);
    } catch (err) {
      console.warn('Monte Carlo failed:', err);
    } finally {
      setLoading(false);
    }
  }, [ctx.companyId, targetMetric, simCount]);

  const chartData = useMemo(() => {
    if (!result) return [];

    if (chartMode === 'monte_carlo_histogram' && result.histogram) {
      return result.histogram.map(h => ({ name: fmtCurrency(h.bucket), value: h.count, bucket: h.bucket }));
    }

    if (chartMode === 'monte_carlo_fan' && result.fan_data) {
      return result.fan_data;
    }

    // Fallback: build from percentiles
    if (result.percentiles) {
      return Object.entries(result.percentiles).map(([k, v]) => ({
        name: k.toUpperCase(),
        value: v,
      }));
    }

    return [];
  }, [result, chartMode]);

  const collapsedSummary = result
    ? `MC: ${targetMetric} | p50: ${fmtCurrency(result.percentiles?.p50 || result.mean)} | ${result.simulations.toLocaleString()} sims`
    : 'Monte Carlo — run simulation';

  const aiContext = useMemo(() => ({
    result,
    targetMetric,
    simulations: parseInt(simCount),
  }), [result, targetMetric, simCount]);

  const configBar = (
    <>
      <div className="flex items-center gap-1.5">
        <span className="text-muted-foreground">Chart:</span>
        <Select value={chartMode} onValueChange={(v) => setChartMode(v as ChartMode)}>
          <SelectTrigger className="h-6 w-[120px] text-[11px]"><SelectValue /></SelectTrigger>
          <SelectContent>
            <SelectItem value="monte_carlo_fan">Fan Chart</SelectItem>
            <SelectItem value="monte_carlo_histogram">Histogram</SelectItem>
            <SelectItem value="probability_cloud">Probability Cloud</SelectItem>
          </SelectContent>
        </Select>
      </div>
      <div className="flex items-center gap-1.5">
        <span className="text-muted-foreground">Metric:</span>
        <Select value={targetMetric} onValueChange={setTargetMetric}>
          <SelectTrigger className="h-6 w-[100px] text-[11px]"><SelectValue /></SelectTrigger>
          <SelectContent>
            <SelectItem value="revenue">Revenue</SelectItem>
            <SelectItem value="ebitda">EBITDA</SelectItem>
            <SelectItem value="net_income">Net Income</SelectItem>
            <SelectItem value="cash_balance">Cash</SelectItem>
            <SelectItem value="valuation">Valuation</SelectItem>
          </SelectContent>
        </Select>
      </div>
      <div className="flex items-center gap-1.5">
        <span className="text-muted-foreground">Sims:</span>
        <input
          type="text"
          className="h-6 w-[60px] text-[11px] rounded border border-input bg-background px-2 tabular-nums"
          value={simCount}
          onChange={e => setSimCount(e.target.value)}
        />
      </div>
      {!readOnly && (
        <Button variant="outline" size="sm" className="h-6 text-[11px] gap-1 ml-auto" onClick={handleRunMonteCarlo} disabled={loading}>
          {loading ? <Loader2 className="h-3 w-3 animate-spin" /> : <Play className="h-3 w-3" />}
          Run Simulation
        </Button>
      )}
    </>
  );

  // Percentile summary cards
  const percentileCards = result?.percentiles ? (
    <div className="grid grid-cols-5 gap-1.5 mb-3">
      {Object.entries(result.percentiles).map(([key, val]) => (
        <div key={key} className="rounded-md border border-border/50 bg-muted/30 p-2 text-center">
          <div className="text-[9px] text-muted-foreground uppercase font-mono">{key}</div>
          <div className="text-sm font-semibold tabular-nums">{fmtCurrency(val)}</div>
        </div>
      ))}
    </div>
  ) : null;

  return (
    <MemoSectionWrapper
      sectionType="monte_carlo"
      title="Monte Carlo Simulation"
      collapsedSummary={collapsedSummary}
      configContent={configBar}
      narrativeCards={narrativeCards}
      onNarrativeCardsChange={setNarrativeCards}
      aiDataContext={aiContext}
      onDelete={onDelete}
      readOnly={readOnly}
    >
      {percentileCards}
      <div className="w-full" style={{ height: 300 }}>
        {chartData.length > 0 ? (
          <TableauLevelCharts data={chartData} type={chartMode} title="" width="100%" height={280} />
        ) : (
          <div className="flex items-center justify-center h-full text-xs text-muted-foreground">
            Run simulation to view probability distributions
          </div>
        )}
      </div>
    </MemoSectionWrapper>
  );
}
