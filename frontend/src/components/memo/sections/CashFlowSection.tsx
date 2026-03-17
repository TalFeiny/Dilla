'use client';

import React, { useMemo, useState } from 'react';
import dynamic from 'next/dynamic';
import { MemoSectionWrapper } from '../MemoSectionWrapper';
import { useMemoContext, type NarrativeCard } from '../MemoContext';
import type { MatrixRow } from '@/components/matrix/UnifiedMatrix';
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '@/components/ui/select';

const TableauLevelCharts = dynamic(
  () => import('@/components/charts/TableauLevelCharts'),
  { ssr: false, loading: () => <div className="h-[300px] animate-pulse bg-muted rounded" /> }
);

type ChartMode = 'line' | 'bar' | 'stacked_bar';

function fmtCurrency(v: number): string {
  if (Math.abs(v) >= 1e9) return `$${(v / 1e9).toFixed(1)}B`;
  if (Math.abs(v) >= 1e6) return `$${(v / 1e6).toFixed(1)}M`;
  if (Math.abs(v) >= 1e3) return `$${(v / 1e3).toFixed(0)}K`;
  return `$${v.toLocaleString()}`;
}

function buildCFChartData(rows: MatrixRow[], columns: string[]): Record<string, any>[] {
  const periodCols = columns.filter(c => c !== 'lineItem');
  return periodCols.map(colId => {
    const entry: Record<string, any> = { period: colId };
    const getValue = (id: string) => {
      const row = rows.find(r => r.id === id);
      if (!row?.cells[colId]) return 0;
      const v = row.cells[colId].value;
      return typeof v === 'number' ? v : parseFloat(v) || 0;
    };
    entry['Operating CF'] = getValue('operating_cash_flow');
    entry['CapEx'] = getValue('capex');
    entry['Free Cash Flow'] = getValue('free_cash_flow');
    entry['Cash Balance'] = getValue('cash_balance');
    entry['Net Burn'] = getValue('net_burn_rate');
    entry['Runway (mo)'] = getValue('runway_months');
    return entry;
  });
}

export interface CashFlowSectionProps {
  onDelete?: () => void;
  readOnly?: boolean;
}

export function CashFlowSection({ onDelete, readOnly = false }: CashFlowSectionProps) {
  const ctx = useMemoContext();
  const [chartMode, setChartMode] = useState<ChartMode>('line');
  const [narrativeCards, setNarrativeCards] = useState<NarrativeCard[]>([]);

  const cfRows = ctx.getCashFlowRows();
  const columns = ctx.matrixData.columns.map(c => c.id);

  const chartData = useMemo(() => buildCFChartData(cfRows, columns), [cfRows, columns]);

  const latest = chartData[chartData.length - 1];
  const collapsedSummary = latest
    ? `FCF: ${fmtCurrency(latest['Free Cash Flow'] || 0)} | Cash: ${fmtCurrency(latest['Cash Balance'] || 0)} | Runway: ${(latest['Runway (mo)'] || 0).toFixed(0)}mo`
    : 'Cash Flow — no data';

  const aiContext = useMemo(() => ({ cfData: chartData, latest }), [chartData, latest]);

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
    </div>
  );

  const detailGrid = (
    <div className="overflow-x-auto mt-2">
      <table className="w-full text-[11px] border-collapse">
        <thead>
          <tr className="border-b-2 border-border bg-muted/50">
            {columns.map(colId => {
              const col = ctx.matrixData.columns.find(c => c.id === colId);
              return <th key={colId} className="px-2 py-1 text-left font-semibold whitespace-nowrap">{col?.name || colId}</th>;
            })}
          </tr>
        </thead>
        <tbody>
          {cfRows.map(row => {
            const isHeader = (row as any).isHeader;
            const isTotal = (row as any).isTotal;
            const depth = (row as any).depth || 0;
            return (
              <tr key={row.id} className={`border-b border-border/50 ${isHeader ? 'bg-muted/30 font-semibold' : ''} ${isTotal ? 'font-semibold border-t border-border' : ''}`}>
                {columns.map(colId => {
                  if (colId === 'lineItem') {
                    return <td key={colId} className="px-2 py-1 whitespace-nowrap" style={{ paddingLeft: `${8 + depth * 16}px` }}>{row.cells.lineItem?.value || row.id}</td>;
                  }
                  const cell = row.cells[colId];
                  const v = cell?.value;
                  return <td key={colId} className="px-2 py-1 tabular-nums text-right whitespace-nowrap">{typeof v === 'number' ? fmtCurrency(v) : (v ?? '')}</td>;
                })}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );

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
        {chartData.length > 0 ? (
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
