'use client';

import React, { useMemo, useState, useCallback, useEffect } from 'react';
import dynamic from 'next/dynamic';
import { MemoSectionWrapper } from '../MemoSectionWrapper';
import { useMemoContext, type NarrativeCard } from '../MemoContext';
import { Button } from '@/components/ui/button';
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '@/components/ui/select';
import { Loader2, Play } from 'lucide-react';

const TableauLevelCharts = dynamic(
  () => import('@/components/charts/TableauLevelCharts'),
  { ssr: false, loading: () => <div className="h-[300px] animate-pulse bg-muted rounded" /> }
);

type ChartMode = 'branched_line' | 'stacked_bar' | 'treemap' | 'regression_line' | 'line' | 'bar_comparison' | 'monte_carlo_fan';
type ForecastMethod =
  | 'auto' | 'driver-based' | 'seasonal'
  | 'linear' | 'polynomial' | 'exponential_growth'
  | 'logistic' | 'power_law' | 'gompertz'
  | 'piecewise_linear' | 'weighted_linear';

export interface ForecastMethodSectionProps {
  onDelete?: () => void;
  readOnly?: boolean;
}

export function ForecastMethodSection({ onDelete, readOnly = false }: ForecastMethodSectionProps) {
  const ctx = useMemoContext();
  const [chartMode, setChartMode] = useState<ChartMode>('branched_line');
  const [narrativeCards, setNarrativeCards] = useState<NarrativeCard[]>([]);
  const [selectedMethod, setSelectedMethod] = useState<ForecastMethod>('auto');
  const [loading, setLoading] = useState(false);

  const handleBuildForecast = useCallback(async () => {
    if (!ctx.companyId) return;
    setLoading(true);
    try {
      await ctx.buildForecast({ method: selectedMethod });
    } catch (err: any) {
      console.warn('Forecast build error:', err);
    } finally {
      setLoading(false);
    }
  }, [ctx, selectedMethod]);

  const methodResult = ctx.forecastMeta;

  // Auto-generate narrative cards when forecast metadata updates
  useEffect(() => {
    if (!methodResult) return;
    const cards: NarrativeCard[] = [];

    // Model fit narrative
    if (methodResult.description) {
      cards.push({
        id: 'forecast-description',
        text: methodResult.description,
        severity: 'info',
      });
    }

    // R² / accuracy card
    if (methodResult.r_squared != null) {
      const r2 = methodResult.r_squared;
      const quality = r2 >= 0.9 ? 'strong' : r2 >= 0.7 ? 'moderate' : 'weak';
      const severity = r2 >= 0.7 ? 'info' : 'warning';
      cards.push({
        id: 'forecast-accuracy',
        text: `${methodResult.method || 'Model'} fit: R² = ${r2.toFixed(3)} (${quality})${methodResult.mape != null ? ` | MAPE: ${(methodResult.mape * 100).toFixed(1)}%` : ''}`,
        severity,
      });
    }

    // Request AI narrative for richer context
    if (ctx.requestNarrative && methodResult.method) {
      ctx.requestNarrative('forecast_method', {
        method: methodResult.method,
        r_squared: methodResult.r_squared,
        mape: methodResult.mape,
        alternatives: methodResult.alternatives,
        fit_data_points: methodResult.fit_data?.length,
      }).then(narrative => {
        if (narrative) {
          setNarrativeCards(prev => [
            ...prev.filter(c => c.id !== 'forecast-ai-narrative'),
            { id: 'forecast-ai-narrative', text: narrative, severity: 'info' as const },
          ]);
        }
      }).catch(() => {});
    }

    setNarrativeCards(cards);
  }, [methodResult, ctx]);

  // Backend returns pre-built chart shapes keyed by chart type — just pass through
  // Each shape: { data, citations, explanation }
  const chartShape = useMemo(() => {
    if (!methodResult?.fit_data) return null;
    const shapes = methodResult.fit_data;
    return shapes[chartMode] ?? shapes['line'] ?? null;
  }, [methodResult, chartMode]);

  const chartData = chartShape?.data ?? null;
  const chartCitations = chartShape?.citations ?? [];
  const chartExplanation = chartShape?.explanation ?? null;

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
          <SelectTrigger className="h-6 w-[140px] text-[11px]"><SelectValue /></SelectTrigger>
          <SelectContent>
            <SelectItem value="branched_line">Scenario Branches</SelectItem>
            <SelectItem value="stacked_bar">Stacked Bar</SelectItem>
            <SelectItem value="regression_line">Regression Fit</SelectItem>
            <SelectItem value="line">Line</SelectItem>
            <SelectItem value="treemap">Treemap</SelectItem>
            <SelectItem value="bar_comparison">Grouped Bar</SelectItem>
            <SelectItem value="monte_carlo_fan">MC Fan</SelectItem>
          </SelectContent>
        </Select>
      </div>
      <div className="flex items-center gap-1.5">
        <span className="text-muted-foreground">Method:</span>
        <Select value={selectedMethod} onValueChange={(v) => setSelectedMethod(v as ForecastMethod)}>
          <SelectTrigger className="h-6 w-[150px] text-[11px]"><SelectValue /></SelectTrigger>
          <SelectContent>
            <SelectItem value="auto">Auto (best fit)</SelectItem>
            <SelectItem value="linear">Linear</SelectItem>
            <SelectItem value="polynomial">Polynomial</SelectItem>
            <SelectItem value="exponential_growth">Exponential</SelectItem>
            <SelectItem value="logistic">Logistic (S-curve)</SelectItem>
            <SelectItem value="power_law">Power Law</SelectItem>
            <SelectItem value="gompertz">Gompertz</SelectItem>
            <SelectItem value="piecewise_linear">Piecewise Linear</SelectItem>
            <SelectItem value="weighted_linear">Weighted Linear</SelectItem>
            <SelectItem value="seasonal">Seasonal</SelectItem>
            <SelectItem value="driver-based">Driver-based</SelectItem>
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
        {chartData ? (
          <TableauLevelCharts data={chartData} type={chartMode} title="" width="100%" height={260} citations={chartCitations} />
        ) : (
          <div className="flex items-center justify-center h-full text-xs text-muted-foreground">
            Build a forecast to see method fit and accuracy
          </div>
        )}
      </div>
      {chartExplanation && (
        <p className="text-[11px] text-muted-foreground mt-2 leading-relaxed">{chartExplanation}</p>
      )}
    </MemoSectionWrapper>
  );
}
