'use client';

import React, { useMemo, useState, useCallback, useEffect } from 'react';
import dynamic from 'next/dynamic';
import { MemoSectionWrapper } from '../MemoSectionWrapper';
import { useMemoContext, type NarrativeCard } from '../MemoContext';
import { fetchPnl, fetchCashFlow } from '@/lib/memo/api-helpers';
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

type ChartMode = 'cash_flow_waterfall' | 'waterfall' | 'bar';
type WaterfallSource = 'pnl' | 'cash_flow';

interface BackendRow {
  id: string;
  label: string;
  values: Record<string, number | null>;
}

interface BackendResponse {
  periods: string[];
  rows: BackendRow[];
}

/** Derive waterfall steps from PnL backend data for a given period.
 *  Dynamically discovers OpEx subcategories from the response rows
 *  instead of hardcoding R&D / S&M / G&A. */
function buildPnlWaterfall(data: BackendResponse, period: string): Record<string, any>[] {
  const rowMap: Record<string, Record<string, number | null>> = {};
  for (const row of data.rows) {
    rowMap[row.id] = row.values;
  }
  const val = (id: string) => rowMap[id]?.[period] ?? 0;

  const steps: Record<string, any>[] = [
    { name: 'Revenue', value: val('revenue'), type: 'increase' },
    { name: 'COGS', value: -Math.abs(val('cogs')), type: 'decrease' },
    { name: 'Gross Profit', value: val('gross_profit'), type: 'subtotal' },
  ];

  // Dynamically discover OpEx rows from the response — handles both
  // standard categories (opex_rd, opex_sm, opex_ga) and arbitrary
  // subcategories (opex_rd:engineering_salaries, opex_sm:paid_acquisition, etc.)
  const opexRows = data.rows.filter(
    r => r.id.startsWith('opex_') &&
         r.id !== 'total_opex' &&
         !r.id.startsWith('opex_total') &&
         r.values?.[period] != null &&
         r.values[period] !== 0
  );

  if (opexRows.length > 0) {
    for (const row of opexRows) {
      // Skip parent rows if their children are present (avoid double-counting)
      const isParent = ['opex_rd', 'opex_sm', 'opex_ga'].includes(row.id);
      const hasChildren = isParent && opexRows.some(r => r.id.startsWith(row.id + ':'));
      if (hasChildren) continue;

      const amount = row.values[period] ?? 0;
      steps.push({
        name: row.label,
        value: -Math.abs(amount),
        type: 'decrease',
      });
    }
  }

  steps.push(
    { name: 'EBITDA', value: val('ebitda'), type: 'subtotal' },
    { name: 'Debt Service', value: -Math.abs(val('debt_service')), type: 'decrease' },
    { name: 'Tax', value: -Math.abs(val('tax_expense')), type: 'decrease' },
    { name: 'Net Income', value: val('net_income'), type: 'total' },
  );

  return steps.filter(d => d.value !== 0);
}

/** Derive waterfall steps from Cash Flow backend data for a given period */
function buildCFWaterfall(data: BackendResponse, period: string): Record<string, any>[] {
  const rowMap: Record<string, Record<string, number | null>> = {};
  for (const row of data.rows) {
    rowMap[row.id] = row.values;
  }
  const val = (id: string) => rowMap[id]?.[period] ?? 0;

  const wcDelta = val('working_capital_delta');
  return [
    { name: 'Operating CF', value: val('operating_cash_flow'), type: 'increase' },
    { name: 'Working Capital', value: wcDelta, type: wcDelta >= 0 ? 'increase' : 'decrease' },
    { name: 'CapEx', value: -Math.abs(val('capex')), type: 'decrease' },
    { name: 'Debt Service', value: -Math.abs(val('debt_service')), type: 'decrease' },
    { name: 'Free Cash Flow', value: val('free_cash_flow'), type: 'total' },
  ].filter(d => d.value !== 0);
}

export interface WaterfallSectionProps {
  onDelete?: () => void;
  readOnly?: boolean;
}

export function WaterfallSection({ onDelete, readOnly = false }: WaterfallSectionProps) {
  const ctx = useMemoContext();
  const [chartMode, setChartMode] = useState<ChartMode>('cash_flow_waterfall');
  const [source, setSource] = useState<WaterfallSource>('pnl');
  const [narrativeCards, setNarrativeCards] = useState<NarrativeCard[]>([]);
  const [periodIndex, setPeriodIndex] = useState<string>('latest');

  const [backendData, setBackendData] = useState<BackendResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleFetch = useCallback(async () => {
    if (!ctx.companyId) return;
    setLoading(true);
    setError(null);
    try {
      const data = source === 'pnl'
        ? await fetchPnl(ctx.companyId)
        : await fetchCashFlow(ctx.companyId);
      setBackendData(data);
    } catch (err: any) {
      console.warn('WaterfallSection fetch error:', err);
      setError(err.message || 'Failed to load waterfall data');
    } finally {
      setLoading(false);
    }
  }, [ctx.companyId, source]);

  useEffect(() => {
    handleFetch();
  }, [handleFetch]);

  const periods = backendData?.periods || [];
  const selectedPeriod = periodIndex === 'latest'
    ? periods[periods.length - 1]
    : periodIndex;

  const chartData = useMemo(() => {
    if (!backendData || !selectedPeriod) return [];
    return source === 'pnl'
      ? buildPnlWaterfall(backendData, selectedPeriod)
      : buildCFWaterfall(backendData, selectedPeriod);
  }, [backendData, selectedPeriod, source]);

  const lastStep = chartData[chartData.length - 1];
  const collapsedSummary = lastStep
    ? `${source === 'pnl' ? 'P&L' : 'CF'} Waterfall → ${lastStep.name}: ${fmtCurrency(lastStep.value)}`
    : 'Waterfall — no data';

  const aiContext = useMemo(() => ({
    waterfallData: chartData,
    source,
    period: selectedPeriod,
  }), [chartData, source, selectedPeriod]);

  const configBar = (
    <>
      <div className="flex items-center gap-1.5">
        <span className="text-muted-foreground">Chart:</span>
        <Select value={chartMode} onValueChange={(v) => setChartMode(v as ChartMode)}>
          <SelectTrigger className="h-6 w-[120px] text-[11px]"><SelectValue /></SelectTrigger>
          <SelectContent>
            <SelectItem value="cash_flow_waterfall">Waterfall</SelectItem>
            <SelectItem value="waterfall">Standard</SelectItem>
            <SelectItem value="bar">Bar</SelectItem>
          </SelectContent>
        </Select>
      </div>
      <div className="flex items-center gap-1.5">
        <span className="text-muted-foreground">Source:</span>
        <Select value={source} onValueChange={(v) => setSource(v as WaterfallSource)}>
          <SelectTrigger className="h-6 w-[100px] text-[11px]"><SelectValue /></SelectTrigger>
          <SelectContent>
            <SelectItem value="pnl">P&L</SelectItem>
            <SelectItem value="cash_flow">Cash Flow</SelectItem>
          </SelectContent>
        </Select>
      </div>
      <div className="flex items-center gap-1.5">
        <span className="text-muted-foreground">Period:</span>
        <Select value={periodIndex} onValueChange={setPeriodIndex}>
          <SelectTrigger className="h-6 w-[90px] text-[11px]"><SelectValue /></SelectTrigger>
          <SelectContent>
            <SelectItem value="latest">Latest</SelectItem>
            {periods.map(p => (
              <SelectItem key={p} value={p}>{p}</SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>
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
    </>
  );

  return (
    <MemoSectionWrapper
      sectionType="waterfall"
      title="Waterfall"
      collapsedSummary={collapsedSummary}
      configContent={configBar}
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
            Loading waterfall...
          </div>
        ) : error ? (
          <div className="flex items-center justify-center h-full text-xs text-red-500">{error}</div>
        ) : chartData.length > 0 ? (
          <TableauLevelCharts data={chartData} type={chartMode} title="" width="100%" height={300} />
        ) : (
          <div className="flex items-center justify-center h-full text-xs text-muted-foreground">
            Upload data to view waterfall breakdown
          </div>
        )}
      </div>
    </MemoSectionWrapper>
  );
}
