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
import { runValuation } from '@/lib/memo/api-helpers';
import { fmtCurrency } from '@/lib/memo/format';

const TableauLevelCharts = dynamic(
  () => import('@/components/charts/TableauLevelCharts'),
  { ssr: false, loading: () => <div className="h-[300px] animate-pulse bg-muted rounded" /> }
);

type ChartMode = 'bar_comparison' | 'waterfall' | 'breakpoint_chart' | 'tornado';
type ValuationMethod = 'pwerm' | 'dcf' | 'comparables' | 'all';

interface ValuationResult {
  method: string;
  value: number;
  range_low?: number;
  range_high?: number;
  confidence?: number;
  details?: Record<string, any>;
}

export interface ValuationSectionProps {
  onDelete?: () => void;
  readOnly?: boolean;
}

export function ValuationSection({ onDelete, readOnly = false }: ValuationSectionProps) {
  const ctx = useMemoContext();
  const [chartMode, setChartMode] = useState<ChartMode>('bar_comparison');
  const [method, setMethod] = useState<ValuationMethod>('all');
  const [narrativeCards, setNarrativeCards] = useState<NarrativeCard[]>([]);
  const [results, setResults] = useState<ValuationResult[]>([]);
  const [loading, setLoading] = useState(false);

  const handleRunValuation = useCallback(async () => {
    setLoading(true);
    try {
      const data = await runValuation(ctx.companyId, method);
      if (method === 'all') {
        setResults(data.valuations || data.results || []);
      } else {
        const result: ValuationResult = {
          method: method.toUpperCase(),
          value: data.value || data.valuation || 0,
          range_low: data.range_low || data.low,
          range_high: data.range_high || data.high,
          confidence: data.confidence,
          details: data,
        };
        setResults([result]);
      }
    } catch (err) {
      console.warn('Valuation failed:', err);
    } finally {
      setLoading(false);
    }
  }, [ctx.companyId, method]);

  const chartData = useMemo(() => {
    if (results.length === 0) return [];

    return results.map(r => ({
      name: r.method,
      value: r.value,
      low: r.range_low || r.value * 0.8,
      high: r.range_high || r.value * 1.2,
      confidence: r.confidence,
    }));
  }, [results]);

  const primaryVal = results.length > 0
    ? results.reduce((sum, r) => sum + r.value, 0) / results.length
    : 0;

  const collapsedSummary = results.length > 0
    ? `Valuation: ${fmtCurrency(primaryVal)} (${results.map(r => r.method).join(', ')})`
    : 'Valuation — run analysis';

  const aiContext = useMemo(() => ({
    results,
    method,
    averageValue: primaryVal,
  }), [results, method, primaryVal]);

  const configBar = (
    <>
      <div className="flex items-center gap-1.5">
        <span className="text-muted-foreground">Chart:</span>
        <Select value={chartMode} onValueChange={(v) => setChartMode(v as ChartMode)}>
          <SelectTrigger className="h-6 w-[120px] text-[11px]"><SelectValue /></SelectTrigger>
          <SelectContent>
            <SelectItem value="bar_comparison">Bar Comparison</SelectItem>
            <SelectItem value="waterfall">Waterfall</SelectItem>
            <SelectItem value="breakpoint_chart">Breakpoints</SelectItem>
            <SelectItem value="tornado">Tornado</SelectItem>
          </SelectContent>
        </Select>
      </div>
      <div className="flex items-center gap-1.5">
        <span className="text-muted-foreground">Method:</span>
        <Select value={method} onValueChange={(v) => setMethod(v as ValuationMethod)}>
          <SelectTrigger className="h-6 w-[110px] text-[11px]"><SelectValue /></SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Methods</SelectItem>
            <SelectItem value="pwerm">PWERM</SelectItem>
            <SelectItem value="dcf">DCF</SelectItem>
            <SelectItem value="comparables">Comparables</SelectItem>
          </SelectContent>
        </Select>
      </div>
      {!readOnly && (
        <Button variant="outline" size="sm" className="h-6 text-[11px] gap-1 ml-auto" onClick={handleRunValuation} disabled={loading}>
          {loading ? <Loader2 className="h-3 w-3 animate-spin" /> : <Play className="h-3 w-3" />}
          Run Valuation
        </Button>
      )}
    </>
  );

  const detailGrid = results.length > 0 ? (
    <div className="overflow-x-auto mt-2">
      <table className="w-full text-[11px] border-collapse">
        <thead>
          <tr className="border-b-2 border-border bg-muted/50">
            <th className="px-2 py-1 text-left font-semibold">Method</th>
            <th className="px-2 py-1 text-right font-semibold">Value</th>
            <th className="px-2 py-1 text-right font-semibold">Low</th>
            <th className="px-2 py-1 text-right font-semibold">High</th>
            <th className="px-2 py-1 text-right font-semibold">Confidence</th>
          </tr>
        </thead>
        <tbody>
          {results.map((r, i) => (
            <tr key={i} className="border-b border-border/50">
              <td className="px-2 py-1 font-medium">{r.method}</td>
              <td className="px-2 py-1 tabular-nums text-right font-semibold">{fmtCurrency(r.value)}</td>
              <td className="px-2 py-1 tabular-nums text-right text-muted-foreground">{r.range_low ? fmtCurrency(r.range_low) : '—'}</td>
              <td className="px-2 py-1 tabular-nums text-right text-muted-foreground">{r.range_high ? fmtCurrency(r.range_high) : '—'}</td>
              <td className="px-2 py-1 tabular-nums text-right">{r.confidence != null ? `${(r.confidence * 100).toFixed(0)}%` : '—'}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  ) : undefined;

  return (
    <MemoSectionWrapper
      sectionType="valuation"
      title="Valuation"
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
            Run valuation to compare methods (PWERM, DCF, Comparables)
          </div>
        )}
      </div>
    </MemoSectionWrapper>
  );
}
