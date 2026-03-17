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
import { runSensitivity } from '@/lib/memo/api-helpers';
import { fmtCurrency } from '@/lib/memo/format';

const TableauLevelCharts = dynamic(
  () => import('@/components/charts/TableauLevelCharts'),
  { ssr: false, loading: () => <div className="h-[300px] animate-pulse bg-muted rounded" /> }
);

type ChartMode = 'sensitivity_tornado' | 'tornado' | 'heatmap';

interface SensitivityResult {
  target_metric: string;
  base_value: number;
  drivers: Array<{
    driver_id: string;
    driver_label: string;
    low_value: number;
    high_value: number;
    low_impact: number;   // target metric value when driver is low
    high_impact: number;  // target metric value when driver is high
    elasticity?: number;
  }>;
}

export interface SensitivitySectionProps {
  onDelete?: () => void;
  readOnly?: boolean;
}

export function SensitivitySection({ onDelete, readOnly = false }: SensitivitySectionProps) {
  const ctx = useMemoContext();
  const [chartMode, setChartMode] = useState<ChartMode>('sensitivity_tornado');
  const [narrativeCards, setNarrativeCards] = useState<NarrativeCard[]>([]);
  const [result, setResult] = useState<SensitivityResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [targetMetric, setTargetMetric] = useState<string>('ebitda');

  const handleRunSensitivity = useCallback(async () => {
    setLoading(true);
    try {
      // Backend pulls actuals from Supabase — no grid scraping needed
      const data = await runSensitivity(
        ctx.companyId,
        targetMetric,
        (ctx as any).activeBranchId ?? null,
      );
      setResult(data);
    } catch (err) {
      console.warn('Sensitivity failed:', err);
    } finally {
      setLoading(false);
    }
  }, [ctx.companyId, targetMetric]);

  // Build tornado chart data: sorted by impact range (largest swing first)
  const chartData = useMemo(() => {
    if (!result?.drivers) return [];

    const sorted = [...result.drivers].sort((a, b) => {
      const rangeA = Math.abs(a.high_impact - a.low_impact);
      const rangeB = Math.abs(b.high_impact - b.low_impact);
      return rangeB - rangeA;
    });

    return sorted.map(d => ({
      name: d.driver_label,
      low: d.low_impact,
      high: d.high_impact,
      base: result.base_value,
      low_delta: d.low_impact - result.base_value,
      high_delta: d.high_impact - result.base_value,
      elasticity: d.elasticity,
    }));
  }, [result]);

  const collapsedSummary = result
    ? `Sensitivity: ${targetMetric} base ${fmtCurrency(result.base_value)} | ${result.drivers.length} drivers`
    : 'Sensitivity — run analysis';

  const aiContext = useMemo(() => ({
    result,
    targetMetric,
    driverCount: result?.drivers.length || 0,
  }), [result, targetMetric]);

  const configBar = (
    <>
      <div className="flex items-center gap-1.5">
        <span className="text-muted-foreground">Chart:</span>
        <Select value={chartMode} onValueChange={(v) => setChartMode(v as ChartMode)}>
          <SelectTrigger className="h-6 w-[130px] text-[11px]"><SelectValue /></SelectTrigger>
          <SelectContent>
            <SelectItem value="sensitivity_tornado">Tornado</SelectItem>
            <SelectItem value="tornado">Classic Tornado</SelectItem>
            <SelectItem value="heatmap">Heatmap</SelectItem>
          </SelectContent>
        </Select>
      </div>
      <div className="flex items-center gap-1.5">
        <span className="text-muted-foreground">Target:</span>
        <Select value={targetMetric} onValueChange={setTargetMetric}>
          <SelectTrigger className="h-6 w-[100px] text-[11px]"><SelectValue /></SelectTrigger>
          <SelectContent>
            <SelectItem value="revenue">Revenue</SelectItem>
            <SelectItem value="ebitda">EBITDA</SelectItem>
            <SelectItem value="net_income">Net Income</SelectItem>
            <SelectItem value="valuation">Valuation</SelectItem>
            <SelectItem value="runway_months">Runway</SelectItem>
          </SelectContent>
        </Select>
      </div>
      {!readOnly && (
        <Button variant="outline" size="sm" className="h-6 text-[11px] gap-1 ml-auto" onClick={handleRunSensitivity} disabled={loading}>
          {loading ? <Loader2 className="h-3 w-3 animate-spin" /> : <Play className="h-3 w-3" />}
          Run Analysis
        </Button>
      )}
    </>
  );

  const detailGrid = result?.drivers ? (
    <div className="overflow-x-auto mt-2">
      <table className="w-full text-[11px] border-collapse">
        <thead>
          <tr className="border-b-2 border-border bg-muted/50">
            <th className="px-2 py-1 text-left font-semibold">Driver</th>
            <th className="px-2 py-1 text-right font-semibold">Low Impact</th>
            <th className="px-2 py-1 text-right font-semibold">Base</th>
            <th className="px-2 py-1 text-right font-semibold">High Impact</th>
            <th className="px-2 py-1 text-right font-semibold">Swing</th>
            <th className="px-2 py-1 text-right font-semibold">Elasticity</th>
          </tr>
        </thead>
        <tbody>
          {result.drivers.map(d => {
            const swing = Math.abs(d.high_impact - d.low_impact);
            return (
              <tr key={d.driver_id} className="border-b border-border/50">
                <td className="px-2 py-1 font-medium">{d.driver_label}</td>
                <td className="px-2 py-1 tabular-nums text-right text-red-600">{fmtCurrency(d.low_impact)}</td>
                <td className="px-2 py-1 tabular-nums text-right">{fmtCurrency(result.base_value)}</td>
                <td className="px-2 py-1 tabular-nums text-right text-emerald-600">{fmtCurrency(d.high_impact)}</td>
                <td className="px-2 py-1 tabular-nums text-right font-semibold">{fmtCurrency(swing)}</td>
                <td className="px-2 py-1 tabular-nums text-right">{d.elasticity != null ? `${d.elasticity.toFixed(2)}x` : '—'}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  ) : undefined;

  return (
    <MemoSectionWrapper
      sectionType="sensitivity"
      title="Sensitivity Analysis"
      collapsedSummary={collapsedSummary}
      configContent={configBar}
      detailContent={detailGrid}
      narrativeCards={narrativeCards}
      onNarrativeCardsChange={setNarrativeCards}
      aiDataContext={aiContext}
      onDelete={onDelete}
      readOnly={readOnly}
    >
      <div className="w-full" style={{ height: 320 }}>
        {chartData.length > 0 ? (
          <TableauLevelCharts data={chartData} type={chartMode} title="" width="100%" height={300} />
        ) : (
          <div className="flex items-center justify-center h-full text-xs text-muted-foreground">
            Run sensitivity analysis to see driver impact tornado
          </div>
        )}
      </div>
    </MemoSectionWrapper>
  );
}
