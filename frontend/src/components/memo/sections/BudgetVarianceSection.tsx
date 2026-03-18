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
import { fetchBudgetVariance, listBudgets } from '@/lib/memo/api-helpers';
import { fmtCurrency } from '@/lib/memo/format';

const TableauLevelCharts = dynamic(
  () => import('@/components/charts/TableauLevelCharts'),
  { ssr: false, loading: () => <div className="h-[300px] animate-pulse bg-muted rounded" /> }
);

type ChartMode = 'bar_comparison' | 'stacked_bar' | 'line';

interface VarianceRow {
  line_item: string;
  budget: number;
  actual: number;
  variance: number;
  variance_pct: number;
  favorable: boolean;
}

export interface BudgetVarianceSectionProps {
  onDelete?: () => void;
  readOnly?: boolean;
}

export function BudgetVarianceSection({ onDelete, readOnly = false }: BudgetVarianceSectionProps) {
  const ctx = useMemoContext();
  const [chartMode, setChartMode] = useState<ChartMode>('bar_comparison');
  const [narrativeCards, setNarrativeCards] = useState<NarrativeCard[]>([]);
  const [varianceData, setVarianceData] = useState<VarianceRow[]>([]);
  const [loading, setLoading] = useState(false);
  const [period, setPeriod] = useState<string>('latest');

  const handleFetchVariance = useCallback(async () => {
    setLoading(true);
    try {
      // Derive start/end from grid columns so the backend doesn't 422.
      const periodCols = ctx.matrixData.columns
        .map(c => c.id)
        .filter(id => id !== 'lineItem')
        .sort();
      const start = periodCols[0] || undefined;
      const end = periodCols[periodCols.length - 1] || undefined;

      // Resolve a real budget_id if we can; don't send a period string as budget_id.
      let budgetId: string | undefined;
      try {
        const budgets = await listBudgets(ctx.companyId);
        const list: any[] = budgets?.budgets || (Array.isArray(budgets) ? budgets : []);
        if (list.length > 0) budgetId = list[0].id ?? list[0].budget_id;
      } catch { /* budget list optional */ }

      const data = await fetchBudgetVariance(ctx.companyId, budgetId, start, end);

      // Flexibly map response.
      // Possible: { variances: { by_category: [...], summary: {...}, monthly_trend: [...] } }
      //   or { variances: [...] } or { rows: [...] }
      const variances = data?.variances;
      const raw: any[] = variances?.by_category
        ?? (Array.isArray(variances) ? variances : null)
        ?? data?.rows
        ?? (Array.isArray(data) ? data : []);

      const mapped: VarianceRow[] = raw.map((entry: any) => ({
        line_item: entry.line_item ?? entry.category ?? entry.name ?? '',
        budget: entry.budget ?? 0,
        actual: entry.actual ?? 0,
        variance: entry.variance ?? (entry.actual ?? 0) - (entry.budget ?? 0),
        variance_pct: entry.variance_pct ?? entry.pct ?? 0,
        favorable: entry.favorable
          ?? (entry.status === 'under' || entry.status === 'on_track')
          ?? ((entry.variance ?? 0) >= 0),
      }));

      setVarianceData(mapped);
    } catch (err) {
      console.warn('Budget variance failed:', err);
    } finally {
      setLoading(false);
    }
  }, [ctx.companyId, ctx.matrixData.columns, period]);

  const chartData = useMemo(() => {
    if (varianceData.length === 0) return [];

    return varianceData.map(row => ({
      name: row.line_item,
      Budget: row.budget,
      Actual: row.actual,
      Variance: row.variance,
      variance_pct: row.variance_pct,
      favorable: row.favorable,
    }));
  }, [varianceData]);

  const totalVariance = varianceData.reduce((sum, r) => sum + r.variance, 0);
  const collapsedSummary = varianceData.length > 0
    ? `Budget Variance: ${fmtCurrency(totalVariance)} (${varianceData.filter(r => r.favorable).length}/${varianceData.length} favorable)`
    : 'Budget Variance — load data';

  const aiContext = useMemo(() => ({
    varianceData,
    totalVariance,
    period,
  }), [varianceData, totalVariance, period]);

  const columns = ctx.matrixData.columns.filter(c => c.id !== 'lineItem');

  const configBar = (
    <>
      <div className="flex items-center gap-1.5">
        <span className="text-muted-foreground">Chart:</span>
        <Select value={chartMode} onValueChange={(v) => setChartMode(v as ChartMode)}>
          <SelectTrigger className="h-6 w-[120px] text-[11px]"><SelectValue /></SelectTrigger>
          <SelectContent>
            <SelectItem value="bar_comparison">Bar Compare</SelectItem>
            <SelectItem value="stacked_bar">Stacked</SelectItem>
            <SelectItem value="line">Line</SelectItem>
          </SelectContent>
        </Select>
      </div>
      <div className="flex items-center gap-1.5">
        <span className="text-muted-foreground">Period:</span>
        <Select value={period} onValueChange={setPeriod}>
          <SelectTrigger className="h-6 w-[90px] text-[11px]"><SelectValue /></SelectTrigger>
          <SelectContent>
            <SelectItem value="latest">Latest</SelectItem>
            {columns.map(c => (
              <SelectItem key={c.id} value={c.id}>{c.name || c.id}</SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>
      {!readOnly && (
        <Button variant="outline" size="sm" className="h-6 text-[11px] gap-1 ml-auto" onClick={handleFetchVariance} disabled={loading}>
          {loading ? <Loader2 className="h-3 w-3 animate-spin" /> : <Play className="h-3 w-3" />}
          Load Variance
        </Button>
      )}
    </>
  );

  const detailGrid = varianceData.length > 0 ? (
    <div className="overflow-x-auto mt-2">
      <table className="w-full text-[11px] border-collapse">
        <thead>
          <tr className="border-b-2 border-border bg-muted/50">
            <th className="px-2 py-1 text-left font-semibold">Line Item</th>
            <th className="px-2 py-1 text-right font-semibold">Budget</th>
            <th className="px-2 py-1 text-right font-semibold">Actual</th>
            <th className="px-2 py-1 text-right font-semibold">Variance</th>
            <th className="px-2 py-1 text-right font-semibold">%</th>
          </tr>
        </thead>
        <tbody>
          {varianceData.map((row, i) => (
            <tr key={i} className="border-b border-border/50">
              <td className="px-2 py-1 font-medium">{row.line_item}</td>
              <td className="px-2 py-1 tabular-nums text-right">{fmtCurrency(row.budget)}</td>
              <td className="px-2 py-1 tabular-nums text-right">{fmtCurrency(row.actual)}</td>
              <td className={`px-2 py-1 tabular-nums text-right font-semibold ${row.favorable ? 'text-emerald-600' : 'text-red-600'}`}>
                {row.variance >= 0 ? '+' : ''}{fmtCurrency(row.variance)}
              </td>
              <td className={`px-2 py-1 tabular-nums text-right ${row.favorable ? 'text-emerald-600' : 'text-red-600'}`}>
                {row.variance_pct >= 0 ? '+' : ''}{(row.variance_pct * 100).toFixed(1)}%
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  ) : undefined;

  return (
    <MemoSectionWrapper
      sectionType="budget_variance"
      title="Budget vs Actual"
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
            Load budget variance data to compare budget vs actuals
          </div>
        )}
      </div>
    </MemoSectionWrapper>
  );
}
