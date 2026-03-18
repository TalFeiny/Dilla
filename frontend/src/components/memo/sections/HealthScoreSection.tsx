'use client';

import React, { useMemo, useState, useCallback } from 'react';
import dynamic from 'next/dynamic';
import { MemoSectionWrapper } from '../MemoSectionWrapper';
import { useMemoContext, type NarrativeCard } from '../MemoContext';
import { Button } from '@/components/ui/button';
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '@/components/ui/select';
import { Loader2, Play, Heart } from 'lucide-react';
import { runAdvancedAnalytics } from '@/lib/memo/api-helpers';

const TableauLevelCharts = dynamic(
  () => import('@/components/charts/TableauLevelCharts'),
  { ssr: false, loading: () => <div className="h-[300px] animate-pulse bg-muted rounded" /> }
);

type ChartMode = 'radar_comparison' | 'bar' | 'heatmap';

interface HealthDimension {
  id: string;
  label: string;
  score: number;       // 0-100
  weight: number;
  grade: 'A' | 'B' | 'C' | 'D' | 'F';
  detail?: string;
}

interface HealthResult {
  overall_score: number;
  overall_grade: string;
  dimensions: HealthDimension[];
}

const gradeColors = {
  A: 'text-emerald-600 bg-emerald-50 dark:bg-emerald-950/20 border-emerald-200 dark:border-emerald-800',
  B: 'text-blue-600 bg-blue-50 dark:bg-blue-950/20 border-blue-200 dark:border-blue-800',
  C: 'text-amber-600 bg-amber-50 dark:bg-amber-950/20 border-amber-200 dark:border-amber-800',
  D: 'text-orange-600 bg-orange-50 dark:bg-orange-950/20 border-orange-200 dark:border-orange-800',
  F: 'text-red-600 bg-red-50 dark:bg-red-950/20 border-red-200 dark:border-red-800',
} as const;

export interface HealthScoreSectionProps {
  onDelete?: () => void;
  readOnly?: boolean;
}

export function HealthScoreSection({ onDelete, readOnly = false }: HealthScoreSectionProps) {
  const ctx = useMemoContext();
  const [chartMode, setChartMode] = useState<ChartMode>('radar_comparison');
  const [narrativeCards, setNarrativeCards] = useState<NarrativeCard[]>([]);
  const [result, setResult] = useState<HealthResult | null>(null);
  const [loading, setLoading] = useState(false);

  const [error, setError] = useState<string | null>(null);

  const handleRunHealth = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await runAdvancedAnalytics(ctx.companyId, 'health_score');

      // Backend wraps in AnalyticsResponse: { results: { ... } }
      // The actual data might be at data.results, or data directly.
      // Also handle "unsupported" gracefully.
      const inner = data?.results ?? data;

      if (inner?.status === 'unsupported') {
        setError(inner.message || 'Health score analysis not yet available for this company.');
        return;
      }

      // Normalize: score/grade/dimensions can be at different nesting levels
      const score = inner.overall_score ?? inner.score ?? data.overall_score ?? 0;
      const grade = inner.overall_grade ?? inner.grade ?? data.overall_grade ?? '';

      // Dimensions: could be an array under several keys
      const rawDims: any[] = inner.dimensions ?? inner.categories ?? data.dimensions ?? [];
      const dimensions: HealthDimension[] = rawDims.map((d: any, i: number) => ({
        id: d.id ?? d.name ?? `dim-${i}`,
        label: d.label ?? d.name ?? d.dimension ?? '',
        score: d.score ?? d.value ?? 0,
        weight: d.weight ?? 1,
        grade: d.grade ?? (d.score >= 80 ? 'A' : d.score >= 60 ? 'B' : d.score >= 40 ? 'C' : d.score >= 20 ? 'D' : 'F'),
        detail: d.detail ?? d.description ?? d.summary,
      }));

      setResult({ overall_score: score, overall_grade: grade, dimensions });
    } catch (err) {
      console.warn('Health score failed:', err);
      setError('Failed to run health score analysis.');
    } finally {
      setLoading(false);
    }
  }, [ctx.companyId]);

  const chartData = useMemo(() => {
    if (!result?.dimensions) return [];
    return result.dimensions.map(d => ({
      name: d.label,
      value: d.score,
      weight: d.weight,
      grade: d.grade,
    }));
  }, [result]);

  const collapsedSummary = result
    ? `Health: ${result.overall_grade} (${result.overall_score}/100) | ${result.dimensions.length} dimensions`
    : 'Health Score — run analysis';

  const aiContext = useMemo(() => ({
    result,
  }), [result]);

  const configBar = (
    <>
      <div className="flex items-center gap-1.5">
        <span className="text-muted-foreground">Chart:</span>
        <Select value={chartMode} onValueChange={(v) => setChartMode(v as ChartMode)}>
          <SelectTrigger className="h-6 w-[120px] text-[11px]"><SelectValue /></SelectTrigger>
          <SelectContent>
            <SelectItem value="radar_comparison">Radar</SelectItem>
            <SelectItem value="bar">Bar</SelectItem>
            <SelectItem value="heatmap">Heatmap</SelectItem>
          </SelectContent>
        </Select>
      </div>
      {!readOnly && (
        <Button variant="outline" size="sm" className="h-6 text-[11px] gap-1 ml-auto" onClick={handleRunHealth} disabled={loading}>
          {loading ? <Loader2 className="h-3 w-3 animate-spin" /> : <Play className="h-3 w-3" />}
          Score Health
        </Button>
      )}
    </>
  );

  return (
    <MemoSectionWrapper
      sectionType="health_score"
      title="Company Health Score"
      collapsedSummary={collapsedSummary}
      configContent={configBar}
      narrativeCards={narrativeCards}
      onNarrativeCardsChange={setNarrativeCards}
      aiDataContext={aiContext}
      onDelete={onDelete}
      readOnly={readOnly}
    >
      {/* Overall score badge */}
      {result && (
        <div className="flex items-center gap-3 mb-3">
          <div className={`flex items-center gap-2 rounded-lg border px-3 py-2 ${gradeColors[result.overall_grade as keyof typeof gradeColors] || gradeColors.C}`}>
            <Heart className="h-4 w-4" />
            <span className="text-2xl font-bold tabular-nums">{result.overall_score}</span>
            <span className="text-lg font-semibold">{result.overall_grade}</span>
          </div>
          <span className="text-xs text-muted-foreground">{result.dimensions.length} dimensions evaluated</span>
        </div>
      )}

      {/* Dimension cards */}
      {result?.dimensions && (
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-1.5 mb-3">
          {result.dimensions.map(dim => (
            <div key={dim.id} className={`rounded-md border p-2 ${gradeColors[dim.grade] || gradeColors.C}`}>
              <div className="flex items-center justify-between">
                <span className="text-[10px] font-medium uppercase tracking-wider">{dim.label}</span>
                <span className="text-xs font-bold">{dim.grade}</span>
              </div>
              <div className="text-sm font-semibold tabular-nums">{dim.score}/100</div>
              {dim.detail && <p className="text-[10px] opacity-70 mt-0.5">{dim.detail}</p>}
            </div>
          ))}
        </div>
      )}

      {/* Radar chart */}
      <div className="w-full" style={{ height: 260 }}>
        {chartData.length > 0 ? (
          <TableauLevelCharts data={chartData} type={chartMode} title="" width="100%" height={240} />
        ) : (
          <div className="flex items-center justify-center h-full text-xs text-muted-foreground">
            {error || 'Run health score analysis to evaluate company dimensions'}
          </div>
        )}
      </div>
    </MemoSectionWrapper>
  );
}
