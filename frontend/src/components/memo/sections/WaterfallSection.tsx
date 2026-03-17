'use client';

import React, { useMemo, useState } from 'react';
import dynamic from 'next/dynamic';
import { MemoSectionWrapper } from '../MemoSectionWrapper';
import { useMemoContext, type NarrativeCard } from '../MemoContext';
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '@/components/ui/select';

const TableauLevelCharts = dynamic(
  () => import('@/components/charts/TableauLevelCharts'),
  { ssr: false, loading: () => <div className="h-[300px] animate-pulse bg-muted rounded" /> }
);

type ChartMode = 'cash_flow_waterfall' | 'waterfall' | 'bar';
type WaterfallSource = 'pnl' | 'cash_flow' | 'custom';

function fmtCurrency(v: number): string {
  if (Math.abs(v) >= 1e9) return `$${(v / 1e9).toFixed(1)}B`;
  if (Math.abs(v) >= 1e6) return `$${(v / 1e6).toFixed(1)}M`;
  if (Math.abs(v) >= 1e3) return `$${(v / 1e3).toFixed(0)}K`;
  return `$${v.toLocaleString()}`;
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

  const columns = ctx.matrixData.columns.filter(c => c.id !== 'lineItem');
  const colId = periodIndex === 'latest'
    ? columns[columns.length - 1]?.id
    : periodIndex;

  // Build waterfall steps from grid
  const chartData = useMemo(() => {
    if (!colId) return [];

    const getVal = (rowId: string) => {
      const row = ctx.matrixData.rows.find(r => r.id === rowId);
      if (!row?.cells[colId]) return 0;
      const v = row.cells[colId].value;
      return typeof v === 'number' ? v : parseFloat(v) || 0;
    };

    if (source === 'pnl') {
      return [
        { name: 'Revenue', value: getVal('revenue') || getVal('total_revenue'), type: 'increase' },
        { name: 'COGS', value: -(getVal('cogs') || getVal('total_cogs')), type: 'decrease' },
        { name: 'Gross Profit', value: getVal('gross_profit'), type: 'subtotal' },
        { name: 'R&D', value: -getVal('opex_rd'), type: 'decrease' },
        { name: 'S&M', value: -getVal('opex_sm'), type: 'decrease' },
        { name: 'G&A', value: -getVal('opex_ga'), type: 'decrease' },
        { name: 'EBITDA', value: getVal('ebitda'), type: 'subtotal' },
        { name: 'Debt Service', value: -getVal('debt_service'), type: 'decrease' },
        { name: 'Tax', value: -getVal('tax_expense'), type: 'decrease' },
        { name: 'Net Income', value: getVal('net_income'), type: 'total' },
      ].filter(d => d.value !== 0);
    }

    if (source === 'cash_flow') {
      return [
        { name: 'Net Income', value: getVal('net_income'), type: 'increase' },
        { name: 'Working Capital Δ', value: getVal('working_capital_delta'), type: getVal('working_capital_delta') >= 0 ? 'increase' : 'decrease' },
        { name: 'Operating CF', value: getVal('operating_cash_flow'), type: 'subtotal' },
        { name: 'CapEx', value: -getVal('capex'), type: 'decrease' },
        { name: 'Debt Service', value: -getVal('debt_service'), type: 'decrease' },
        { name: 'Free Cash Flow', value: getVal('free_cash_flow'), type: 'total' },
      ].filter(d => d.value !== 0);
    }

    return [];
  }, [ctx.matrixData, colId, source]);

  const lastStep = chartData[chartData.length - 1];
  const collapsedSummary = lastStep
    ? `${source === 'pnl' ? 'P&L' : 'CF'} Waterfall → ${lastStep.name}: ${fmtCurrency(lastStep.value)}`
    : 'Waterfall — no data';

  const aiContext = useMemo(() => ({
    waterfallData: chartData,
    source,
    period: colId,
  }), [chartData, source, colId]);

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
            {columns.map(c => (
              <SelectItem key={c.id} value={c.id}>{c.name || c.id}</SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>
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
        {chartData.length > 0 ? (
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
