'use client';

import React, { useMemo, useState, useCallback, useEffect } from 'react';
import dynamic from 'next/dynamic';
import { MemoSectionWrapper } from '../MemoSectionWrapper';
import { useMemoContext, type NarrativeCard } from '../MemoContext';
import { fetchCashFlow } from '@/lib/memo/api-helpers';
import { Button } from '@/components/ui/button';
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '@/components/ui/select';
import { Loader2, RefreshCw } from 'lucide-react';
import { fmtCurrency } from '@/lib/memo/format';

const TableauLevelCharts = dynamic(
  () => import('@/components/charts/TableauLevelCharts'),
  { ssr: false, loading: () => <div className="h-[300px] animate-pulse bg-muted rounded" /> }
);

type ChartMode = 'line' | 'bar' | 'stacked_bar';

interface CFRow {
  id: string;
  label: string;
  depth?: number;
  section?: string;
  isHeader?: boolean;
  values: Record<string, number | null>;
}

interface CFResponse {
  periods: string[];
  rows: CFRow[];
}

const CF_CHART_IDS = ['operating_cash_flow', 'capex', 'free_cash_flow', 'cash_balance', 'net_burn_rate'];
const CF_CHART_LABELS: Record<string, string> = {
  operating_cash_flow: 'Operating CF',
  capex: 'CapEx',
  free_cash_flow: 'Free Cash Flow',
  cash_balance: 'Cash Balance',
  net_burn_rate: 'Net Burn',
};

function buildChartFromResponse(data: CFResponse): { labels: string[]; datasets: { label: string; data: (number | null)[] }[] } | null {
  if (!data.periods?.length || !data.rows?.length) return null;
  const rowMap: Record<string, Record<string, number | null>> = {};
  for (const row of data.rows) {
    rowMap[row.id] = row.values;
  }
  const labels = data.periods;
  const datasets = CF_CHART_IDS
    .filter(id => rowMap[id])
    .map(id => ({
      label: CF_CHART_LABELS[id] || id,
      data: data.periods.map(p => rowMap[id]?.[p] ?? null),
    }));
  return datasets.length > 0 ? { labels, datasets } : null;
}

export interface CashFlowSectionProps {
  onDelete?: () => void;
  readOnly?: boolean;
}

export function CashFlowSection({ onDelete, readOnly = false }: CashFlowSectionProps) {
  const ctx = useMemoContext();
  const [chartMode, setChartMode] = useState<ChartMode>('line');
  const [narrativeCards, setNarrativeCards] = useState<NarrativeCard[]>([]);

  const [cfData, setCfData] = useState<CFResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleFetch = useCallback(async () => {
    if (!ctx.companyId) return;
    setLoading(true);
    setError(null);
    try {
      const data = await fetchCashFlow(ctx.companyId);
      setCfData(data);
    } catch (err: any) {
      console.warn('CashFlowSection fetch error:', err);
      setError(err.message || 'Failed to load Cash Flow data');
    } finally {
      setLoading(false);
    }
  }, [ctx.companyId]);

  useEffect(() => {
    handleFetch();
  }, [handleFetch]);

  const chartData = useMemo(() => cfData ? buildChartFromResponse(cfData) : null, [cfData]);

  const collapsedSummary = useMemo(() => {
    if (!chartData) return 'Cash Flow — no data';
    const lastIdx = chartData.labels.length - 1;
    const findVal = (label: string) => chartData.datasets.find(d => d.label === label)?.data[lastIdx] ?? 0;
    return `FCF: ${fmtCurrency(findVal('Free Cash Flow'))} | Cash: ${fmtCurrency(findVal('Cash Balance'))}`;
  }, [chartData]);

  const aiContext = useMemo(() => ({ cfData: chartData }), [chartData]);

  const configBar = (
    <div className="flex items-center gap-1.5">
      <span className="text-muted-foreground">Chart:</span>
      <Select value={chartMode} onValueChange={(v) => setChartMode(v as ChartMode)}>
        <SelectTrigger className="h-6 w-[100px] text-[11px]"><SelectValue /></SelectTrigger>
        <SelectContent>
          <SelectItem value="line">Line</SelectItem>
          <SelectItem value="bar">Bar</SelectItem>
          <SelectItem value="stacked_bar">Stacked Bar</SelectItem>
        </SelectContent>
      </Select>
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
    </div>
  );

  const detailGrid = cfData?.rows ? (
    <div className="overflow-x-auto mt-2">
      <table className="w-full text-[11px] border-collapse">
        <thead>
          <tr className="border-b-2 border-border bg-muted/50">
            <th className="px-2 py-1 text-left font-semibold whitespace-nowrap">Line Item</th>
            {cfData.periods.map(period => (
              <th key={period} className="px-2 py-1 text-right font-semibold whitespace-nowrap">{period}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {cfData.rows.map(row => (
            <tr key={row.id} className={`border-b border-border/50 ${row.isHeader ? 'bg-muted/30 font-semibold' : ''}`}>
              <td className="px-2 py-1 whitespace-nowrap" style={{ paddingLeft: `${8 + (row.depth || 0) * 16}px` }}>
                {row.label}
              </td>
              {cfData.periods.map(period => {
                const v = row.values[period];
                return (
                  <td key={period} className="px-2 py-1 tabular-nums text-right whitespace-nowrap">
                    {v != null ? fmtCurrency(v) : ''}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  ) : null;

  return (
    <MemoSectionWrapper
      sectionType="cf"
      title="Cash Flow"
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
        {loading ? (
          <div className="flex items-center justify-center h-full text-xs text-muted-foreground gap-2">
            <Loader2 className="h-4 w-4 animate-spin" />
            Loading Cash Flow...
          </div>
        ) : error ? (
          <div className="flex items-center justify-center h-full text-xs text-red-500">{error}</div>
        ) : chartData ? (
          <TableauLevelCharts data={chartData} type={chartMode} title="" width="100%" height={300} />
        ) : (
          <div className="flex items-center justify-center h-full text-xs text-muted-foreground">
            Upload data to populate Cash Flow
          </div>
        )}
      </div>
    </MemoSectionWrapper>
  );
}
