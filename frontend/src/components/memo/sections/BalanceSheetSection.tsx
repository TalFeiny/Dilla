'use client';

import React, { useMemo, useState, useCallback, useEffect } from 'react';
import dynamic from 'next/dynamic';
import { MemoSectionWrapper } from '../MemoSectionWrapper';
import { useMemoContext, type NarrativeCard } from '../MemoContext';
import { fetchBalanceSheet } from '@/lib/memo/api-helpers';
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

type ChartMode = 'stacked_bar' | 'bar' | 'line';

interface BSRow {
  id: string;
  label: string;
  depth?: number;
  section?: string;
  isHeader?: boolean;
  isTotal?: boolean;
  isComputed?: boolean;
  values: Record<string, number | null>;
}

interface BSResponse {
  periods: string[];
  rows: BSRow[];
  totals?: Record<string, Record<string, number | null>>;
}

const BS_CHART_IDS = ['total_assets', 'total_liabilities', 'total_equity'];
const BS_CHART_LABELS: Record<string, string> = {
  total_assets: 'Total Assets',
  total_liabilities: 'Total Liabilities',
  total_equity: 'Total Equity',
};

function buildChartFromResponse(data: BSResponse): Record<string, any>[] {
  if (!data.periods || !data.rows) return [];
  const rowMap: Record<string, Record<string, number | null>> = {};
  for (const row of data.rows) {
    rowMap[row.id] = row.values;
  }
  return data.periods.map(period => {
    const entry: Record<string, any> = { period };
    for (const id of BS_CHART_IDS) {
      entry[BS_CHART_LABELS[id] || id] = rowMap[id]?.[period] ?? 0;
    }
    return entry;
  });
}

export interface BalanceSheetSectionProps {
  onDelete?: () => void;
  readOnly?: boolean;
}

export function BalanceSheetSection({ onDelete, readOnly = false }: BalanceSheetSectionProps) {
  const ctx = useMemoContext();
  const [chartMode, setChartMode] = useState<ChartMode>('stacked_bar');
  const [narrativeCards, setNarrativeCards] = useState<NarrativeCard[]>([]);

  const [bsData, setBsData] = useState<BSResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleFetch = useCallback(async () => {
    if (!ctx.companyId) return;
    setLoading(true);
    setError(null);
    try {
      const data = await fetchBalanceSheet(ctx.companyId);
      setBsData(data);
    } catch (err: any) {
      console.warn('BalanceSheetSection fetch error:', err);
      setError(err.message || 'Failed to load Balance Sheet data');
    } finally {
      setLoading(false);
    }
  }, [ctx.companyId]);

  useEffect(() => {
    handleFetch();
  }, [handleFetch]);

  const chartData = useMemo(() => bsData ? buildChartFromResponse(bsData) : [], [bsData]);

  const latest = chartData[chartData.length - 1];
  const collapsedSummary = latest
    ? `Assets: ${fmtCurrency(latest['Total Assets'] || 0)} | Equity: ${fmtCurrency(latest['Total Equity'] || 0)}`
    : 'Balance Sheet — no data';

  const aiContext = useMemo(() => ({ bsData: chartData, latest }), [chartData, latest]);

  const configBar = (
    <div className="flex items-center gap-1.5">
      <span className="text-muted-foreground">Chart:</span>
      <Select value={chartMode} onValueChange={(v) => setChartMode(v as ChartMode)}>
        <SelectTrigger className="h-6 w-[100px] text-[11px]"><SelectValue /></SelectTrigger>
        <SelectContent>
          <SelectItem value="stacked_bar">Stacked Bar</SelectItem>
          <SelectItem value="bar">Grouped Bar</SelectItem>
          <SelectItem value="line">Line</SelectItem>
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

  const detailGrid = bsData?.rows ? (
    <div className="overflow-x-auto mt-2">
      <table className="w-full text-[11px] border-collapse">
        <thead>
          <tr className="border-b-2 border-border bg-muted/50">
            <th className="px-2 py-1 text-left font-semibold whitespace-nowrap">Line Item</th>
            {bsData.periods.map(period => (
              <th key={period} className="px-2 py-1 text-right font-semibold whitespace-nowrap">{period}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {bsData.rows.map(row => (
            <tr key={row.id} className={`border-b border-border/50 ${row.isHeader ? 'bg-muted/30 font-semibold' : ''} ${row.isTotal ? 'font-semibold border-t border-border' : ''}`}>
              <td className="px-2 py-1 whitespace-nowrap" style={{ paddingLeft: `${8 + (row.depth || 0) * 16}px` }}>
                {row.label}
              </td>
              {bsData.periods.map(period => {
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
      sectionType="bs"
      title="Balance Sheet"
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
            Loading Balance Sheet...
          </div>
        ) : error ? (
          <div className="flex items-center justify-center h-full text-xs text-red-500">{error}</div>
        ) : chartData.length > 0 ? (
          <TableauLevelCharts data={chartData} type={chartMode} title="" width="100%" height={300} />
        ) : (
          <div className="flex items-center justify-center h-full text-xs text-muted-foreground">
            Upload data to populate the Balance Sheet
          </div>
        )}
      </div>
    </MemoSectionWrapper>
  );
}
