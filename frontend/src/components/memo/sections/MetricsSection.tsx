'use client';

import React, { useMemo, useState, useCallback, useEffect } from 'react';
import { MemoSectionWrapper } from '../MemoSectionWrapper';
import { useMemoContext, type NarrativeCard, type ComputedMetric } from '../MemoContext';
import { fetchMetrics } from '@/lib/memo/api-helpers';
import { Button } from '@/components/ui/button';
import { TrendingUp, TrendingDown, Minus, Loader2, RefreshCw } from 'lucide-react';
import { formatMetricValue } from '@/lib/memo/format';

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

  const [metricsData, setMetricsData] = useState<ComputedMetric[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleFetch = useCallback(async () => {
    if (!ctx.companyId) return;
    setLoading(true);
    setError(null);
    try {
      const data = await fetchMetrics(ctx.companyId);
      setMetricsData(data.metrics || []);
    } catch (err: any) {
      console.warn('MetricsSection fetch error:', err);
      setError(err.message || 'Failed to load metrics');
    } finally {
      setLoading(false);
    }
  }, [ctx.companyId]);

  useEffect(() => {
    handleFetch();
  }, [handleFetch]);

  const collapsedSummary = metricsData.length > 0
    ? metricsData.slice(0, 3).map(m => `${m.label}: ${formatMetricValue(m.value, m.unit)}`).join(' | ')
    : 'Metrics — no data';

  const aiContext = useMemo(() => ({
    metrics: metricsData.map(m => ({ id: m.id, label: m.label, value: m.value, unit: m.unit, trend: m.trend, severity: m.severity })),
  }), [metricsData]);

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
      configContent={
        <Button
          variant="ghost"
          size="sm"
          className="h-6 w-6 p-0"
          onClick={handleFetch}
          disabled={loading}
          title="Refresh"
        >
          <RefreshCw className={`h-3 w-3 ${loading ? 'animate-spin' : ''}`} />
        </Button>
      }
    >
      {loading ? (
        <div className="flex items-center justify-center h-[120px] text-xs text-muted-foreground gap-2">
          <Loader2 className="h-4 w-4 animate-spin" />
          Loading metrics...
        </div>
      ) : error ? (
        <div className="flex items-center justify-center h-[120px] text-xs text-red-500">{error}</div>
      ) : metricsData.length > 0 ? (
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
          {metricsData.map(metric => {
            const TrendIcon = metric.trend ? trendIcons[metric.trend] : null;
            const colorClass = metric.severity ? severityColors[metric.severity] : 'border-border bg-card';

            return (
              <div
                key={metric.id}
                className={`rounded-lg border p-2.5 ${colorClass} group/card relative`}
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
              </div>
            );
          })}
        </div>
      ) : (
        <div className="flex items-center justify-center h-[120px] text-xs text-muted-foreground">
          Upload data to see metrics
        </div>
      )}
    </MemoSectionWrapper>
  );
}
