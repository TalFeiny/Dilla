'use client';

import React, { useMemo, useState, useCallback } from 'react';
import dynamic from 'next/dynamic';
import { MemoSectionWrapper } from '../MemoSectionWrapper';
import { useMemoContext, type NarrativeCard, type ForecastMeta } from '../MemoContext';
import { Button } from '@/components/ui/button';
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '@/components/ui/select';
import { Loader2, Play, BarChart3 } from 'lucide-react';

const TableauLevelCharts = dynamic(
  () => import('@/components/charts/TableauLevelCharts'),
  { ssr: false, loading: () => <div className="h-[300px] animate-pulse bg-muted rounded" /> }
);

type ChartMode = 'regression_line' | 'line' | 'bar_comparison';
type ForecastMethod = 'driver-based' | 'regression' | 'seasonal' | 'auto';

export interface ForecastMethodSectionProps {
  onDelete?: () => void;
  readOnly?: boolean;
}

export function ForecastMethodSection({ onDelete, readOnly = false }: ForecastMethodSectionProps) {
  const ctx = useMemoContext();
  const [chartMode, setChartMode] = useState<ChartMode>('regression_line');
  const [narrativeCards, setNarrativeCards] = useState<NarrativeCard[]>([]);
  const [selectedMethod, setSelectedMethod] = useState<ForecastMethod>('auto');
  const [loading, setLoading] = useState(false);

  // Read forecast metadata from context — populated by buildForecast()
  const methodResult = ctx.forecastMeta;

  const handleBuildForecast = useCallback(async () => {
    setLoading(true);
    try {
      await ctx.buildForecast({ method: selectedMethod });
      // forecastMeta is now set in context by buildForecast — no local fetch needed
    } finally {
      setLoading(false);
    }
  }, [ctx, selectedMethod]);

  // Build chart data: actuals + fitted line
  const chartData = useMemo(() => {
    if (methodResult?.fit_data) return methodResult.fit_data;

    // Fallback: build from grid data (actual vs forecast overlay)
    const pnlRows = ctx.getPnlRows();
    const cols = ctx.matrixData.columns.filter(c => c.id !== 'lineItem');
    const revRow = pnlRows.find(r => r.id === 'revenue' || r.id === 'total_revenue');
    if (!revRow || cols.length === 0) return [];

    const forecastStart = ctx.matrixData.metadata?.forecastStartIndex;
    return cols.map((col, i) => {
      const v = revRow.cells[col.id]?.value;
      const value = typeof v === 'number' ? v : parseFloat(v) || 0;
      const isForecast = forecastStart != null && i >= forecastStart;
      return {
        period: col.name || col.id,
        actual: isForecast ? null : value,
        forecast: isForecast ? value : null,
        value,
      };
    });
  }, [methodResult, ctx]);

  const collapsedSummary = methodResult
    ? `Method: ${methodResult.method} | R²: ${methodResult.r_squared?.toFixed(3) || '—'} | MAPE: ${methodResult.mape ? `${(methodResult.mape * 100).toFixed(1)}%` : '—'}`
    : `Forecast Method: ${selectedMethod}`;

  const aiContext = useMemo(() => ({
    method: selectedMethod,
    result: methodResult,
  }), [selectedMethod, methodResult]);

  const configBar = (
    <>
      <div className="flex items-center gap-1.5">
        <span className="text-muted-foreground">Chart:</span>
        <Select value={chartMode} onValueChange={(v) => setChartMode(v as ChartMode)}>
          <SelectTrigger className="h-6 w-[120px] text-[11px]"><SelectValue /></SelectTrigger>
          <SelectContent>
            <SelectItem value="regression_line">Regression</SelectItem>
            <SelectItem value="line">Line</SelectItem>
            <SelectItem value="bar_comparison">Comparison</SelectItem>
          </SelectContent>
        </Select>
      </div>
      <div className="flex items-center gap-1.5">
        <span className="text-muted-foreground">Method:</span>
        <Select value={selectedMethod} onValueChange={(v) => setSelectedMethod(v as ForecastMethod)}>
          <SelectTrigger className="h-6 w-[110px] text-[11px]"><SelectValue /></SelectTrigger>
          <SelectContent>
            <SelectItem value="auto">Auto</SelectItem>
            <SelectItem value="driver-based">Driver-based</SelectItem>
            <SelectItem value="regression">Regression</SelectItem>
            <SelectItem value="seasonal">Seasonal</SelectItem>
          </SelectContent>
        </Select>
      </div>
      {!readOnly && (
        <Button variant="outline" size="sm" className="h-6 text-[11px] gap-1 ml-auto" onClick={handleBuildForecast} disabled={loading}>
          {loading ? <Loader2 className="h-3 w-3 animate-spin" /> : <Play className="h-3 w-3" />}
          Build Forecast
        </Button>
      )}
    </>
  );

  // Method comparison cards
  const methodCards = methodResult?.alternatives ? (
    <div className="grid grid-cols-3 gap-1.5 mb-3">
      {[
        { method: methodResult.method, r_squared: methodResult.r_squared, mape: methodResult.mape, active: true },
        ...(methodResult.alternatives || []).map(a => ({ ...a, active: false })),
      ].map(m => (
        <div key={m.method} className={`rounded-md border p-2 text-center ${m.active ? 'border-primary bg-primary/5' : 'border-border/50 bg-muted/30'}`}>
          <div className="text-[10px] text-muted-foreground uppercase font-mono">{m.method}</div>
          <div className="text-sm font-semibold tabular-nums">R² {m.r_squared?.toFixed(3) || '—'}</div>
          {m.mape != null && <div className="text-[10px] text-muted-foreground">MAPE: {(m.mape * 100).toFixed(1)}%</div>}
        </div>
      ))}
    </div>
  ) : null;

  return (
    <MemoSectionWrapper
      sectionType="forecast_method"
      title="Forecast Method"
      collapsedSummary={collapsedSummary}
      configContent={configBar}
      narrativeCards={narrativeCards}
      onNarrativeCardsChange={setNarrativeCards}
      aiDataContext={aiContext}
      onDelete={onDelete}
      readOnly={readOnly}
    >
      {methodCards}
      <div className="w-full" style={{ height: 280 }}>
        {chartData.length > 0 ? (
          <TableauLevelCharts data={chartData} type={chartMode} title="" width="100%" height={260} />
        ) : (
          <div className="flex items-center justify-center h-full text-xs text-muted-foreground">
            Build a forecast to see method fit and accuracy
          </div>
        )}
      </div>
      {methodResult?.description && (
        <p className="text-[11px] text-muted-foreground mt-2 leading-relaxed">{methodResult.description}</p>
      )}
    </MemoSectionWrapper>
  );
}
