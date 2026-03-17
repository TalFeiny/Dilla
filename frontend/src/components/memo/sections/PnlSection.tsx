'use client';

import React, { useMemo, useState, useCallback } from 'react';
import dynamic from 'next/dynamic';
import { MemoSectionWrapper } from '../MemoSectionWrapper';
import { useMemoContext, type NarrativeCard } from '../MemoContext';
import type { MatrixRow } from '@/components/matrix/UnifiedMatrix';
import { Button } from '@/components/ui/button';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Loader2, Play } from 'lucide-react';

const TableauLevelCharts = dynamic(
  () => import('@/components/charts/TableauLevelCharts'),
  { ssr: false, loading: () => <div className="h-[300px] animate-pulse bg-muted rounded" /> }
);

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type ChartMode = 'stacked_bar' | 'line' | 'bar';
type TimeRange = 'all' | '6m' | '12m' | 'ytd';
type ForecastMethod = 'driver-based' | 'regression' | 'seasonal' | 'auto';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Build stacked bar data from P&L rows for Recharts */
function buildStackedBarData(
  rows: MatrixRow[],
  columns: string[],
  forecastStartIndex?: number,
): Record<string, any>[] {
  const periodCols = columns.filter(c => c !== 'lineItem');

  return periodCols.map((colId, idx) => {
    const entry: Record<string, any> = {
      period: colId,
      isForecast: forecastStartIndex != null && idx >= forecastStartIndex,
    };

    // Revenue
    const revRow = rows.find(r => r.id === 'revenue' || r.id === 'total_revenue');
    if (revRow?.cells[colId]) {
      const v = revRow.cells[colId].value;
      entry.Revenue = typeof v === 'number' ? v : parseFloat(v) || 0;
    }

    // COGS
    const cogsRow = rows.find(r => r.id === 'cogs' || r.id === 'total_cogs');
    if (cogsRow?.cells[colId]) {
      const v = cogsRow.cells[colId].value;
      entry.COGS = typeof v === 'number' ? v : parseFloat(v) || 0;
    }

    // OpEx breakdown
    for (const [rowId, label] of [['opex_rd', 'R&D'], ['opex_sm', 'S&M'], ['opex_ga', 'G&A']] as const) {
      const r = rows.find(row => row.id === rowId);
      if (r?.cells[colId]) {
        const v = r.cells[colId].value;
        entry[label] = typeof v === 'number' ? v : parseFloat(v) || 0;
      }
    }

    // EBITDA as line overlay
    const ebitdaRow = rows.find(r => r.id === 'ebitda');
    if (ebitdaRow?.cells[colId]) {
      const v = ebitdaRow.cells[colId].value;
      entry.EBITDA = typeof v === 'number' ? v : parseFloat(v) || 0;
    }

    // Net Income
    const niRow = rows.find(r => r.id === 'net_income');
    if (niRow?.cells[colId]) {
      const v = niRow.cells[colId].value;
      entry['Net Income'] = typeof v === 'number' ? v : parseFloat(v) || 0;
    }

    return entry;
  });
}

/** Format currency for display */
function fmtCurrency(v: number): string {
  if (Math.abs(v) >= 1e9) return `$${(v / 1e9).toFixed(1)}B`;
  if (Math.abs(v) >= 1e6) return `$${(v / 1e6).toFixed(1)}M`;
  if (Math.abs(v) >= 1e3) return `$${(v / 1e3).toFixed(0)}K`;
  return `$${v.toLocaleString()}`;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export interface PnlSectionProps {
  onDelete?: () => void;
  readOnly?: boolean;
}

export function PnlSection({ onDelete, readOnly = false }: PnlSectionProps) {
  const ctx = useMemoContext();
  const [chartMode, setChartMode] = useState<ChartMode>('stacked_bar');
  const [timeRange, setTimeRange] = useState<TimeRange>('all');
  const [forecastMethod, setForecastMethod] = useState<ForecastMethod>('auto');
  const [showBranches, setShowBranches] = useState(true);
  const [narrativeCards, setNarrativeCards] = useState<NarrativeCard[]>([]);
  const [forecasting, setForecasting] = useState(false);

  const pnlRows = ctx.getPnlRows();
  const columns = ctx.matrixData.columns.map(c => c.id);
  const forecastStartIndex = ctx.matrixData.metadata?.forecastStartIndex;

  // Filter columns by time range
  const filteredColumns = useMemo(() => {
    const periodCols = columns.filter(c => c !== 'lineItem');
    if (timeRange === 'all' || periodCols.length === 0) return columns;

    const now = new Date();
    const currentYM = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`;

    if (timeRange === '6m') {
      const idx = periodCols.indexOf(currentYM);
      const start = Math.max(0, (idx >= 0 ? idx : periodCols.length) - 3);
      const end = Math.min(periodCols.length, start + 6);
      return ['lineItem', ...periodCols.slice(start, end)];
    }
    if (timeRange === '12m') {
      const idx = periodCols.indexOf(currentYM);
      const start = Math.max(0, (idx >= 0 ? idx : periodCols.length) - 6);
      const end = Math.min(periodCols.length, start + 12);
      return ['lineItem', ...periodCols.slice(start, end)];
    }
    if (timeRange === 'ytd') {
      const yearPrefix = `${now.getFullYear()}-`;
      return ['lineItem', ...periodCols.filter(c => c.startsWith(yearPrefix))];
    }
    return columns;
  }, [columns, timeRange]);

  // Build chart data — always, even if zero. Chart renders instantly.
  const chartData = useMemo(
    () => buildStackedBarData(pnlRows, filteredColumns, forecastStartIndex),
    [pnlRows, filteredColumns, forecastStartIndex]
  );

  // Latest period summary for collapsed state
  const latestPeriod = chartData[chartData.length - 1];
  const collapsedSummary = latestPeriod
    ? `Revenue: ${fmtCurrency(latestPeriod.Revenue || 0)} | EBITDA: ${fmtCurrency(latestPeriod.EBITDA || 0)} | Net: ${fmtCurrency(latestPeriod['Net Income'] || 0)}`
    : 'P&L — no periods loaded';

  // Build forecast action — passes selected method
  const handleBuildForecast = useCallback(async () => {
    setForecasting(true);
    try {
      await ctx.buildForecast({ method: forecastMethod });
    } finally {
      setForecasting(false);
    }
  }, [ctx, forecastMethod]);

  // AI data context
  const aiContext = useMemo(() => ({
    pnlData: chartData,
    latestPeriod,
    forecastStartIndex,
    forecastMethod,
    branchCount: ctx.activeBranches.length,
  }), [chartData, latestPeriod, forecastStartIndex, forecastMethod, ctx.activeBranches.length]);

  // ---- Config bar ----
  const configBar = (
    <>
      <div className="flex items-center gap-1.5">
        <span className="text-muted-foreground">Chart:</span>
        <Select value={chartMode} onValueChange={(v) => setChartMode(v as ChartMode)}>
          <SelectTrigger className="h-6 w-[100px] text-[11px]">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="stacked_bar">Stacked Bar</SelectItem>
            <SelectItem value="bar">Grouped Bar</SelectItem>
            <SelectItem value="line">Line</SelectItem>
          </SelectContent>
        </Select>
      </div>
      <div className="flex items-center gap-1.5">
        <span className="text-muted-foreground">Range:</span>
        <Select value={timeRange} onValueChange={(v) => setTimeRange(v as TimeRange)}>
          <SelectTrigger className="h-6 w-[80px] text-[11px]">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All</SelectItem>
            <SelectItem value="6m">6 Months</SelectItem>
            <SelectItem value="12m">12 Months</SelectItem>
            <SelectItem value="ytd">YTD</SelectItem>
          </SelectContent>
        </Select>
      </div>
      <div className="flex items-center gap-1.5">
        <span className="text-muted-foreground">Method:</span>
        <Select value={forecastMethod} onValueChange={(v) => setForecastMethod(v as ForecastMethod)}>
          <SelectTrigger className="h-6 w-[110px] text-[11px]">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="auto">Auto</SelectItem>
            <SelectItem value="driver-based">Driver-based</SelectItem>
            <SelectItem value="regression">Regression</SelectItem>
            <SelectItem value="seasonal">Seasonal</SelectItem>
          </SelectContent>
        </Select>
      </div>
      {ctx.activeBranches.length > 0 && (
        <label className="flex items-center gap-1 cursor-pointer">
          <input
            type="checkbox"
            checked={showBranches}
            onChange={e => setShowBranches(e.target.checked)}
            className="h-3 w-3 rounded"
          />
          <span className="text-muted-foreground">Branches</span>
        </label>
      )}
      {!readOnly && (
        <Button
          variant="outline"
          size="sm"
          className="h-6 text-[11px] gap-1 ml-auto"
          onClick={handleBuildForecast}
          disabled={forecasting}
        >
          {forecasting ? <Loader2 className="h-3 w-3 animate-spin" /> : <Play className="h-3 w-3" />}
          Build Forecast
        </Button>
      )}
    </>
  );

  // ---- Detail: expandable grid rows ----
  const detailGrid = (
    <div className="overflow-x-auto mt-2">
      <table className="w-full text-[11px] border-collapse">
        <thead>
          <tr className="border-b-2 border-border bg-muted/50">
            {filteredColumns.map(colId => {
              const col = ctx.matrixData.columns.find(c => c.id === colId);
              return (
                <th key={colId} className="px-2 py-1 text-left font-semibold whitespace-nowrap">
                  {col?.name || colId}
                </th>
              );
            })}
          </tr>
        </thead>
        <tbody>
          {pnlRows.map(row => {
            const isHeader = (row as any).isHeader;
            const isTotal = (row as any).isTotal;
            const depth = (row as any).depth || 0;
            return (
              <tr
                key={row.id}
                className={`border-b border-border/50 ${isHeader ? 'bg-muted/30 font-semibold' : ''} ${isTotal ? 'font-semibold border-t border-border' : ''}`}
              >
                {filteredColumns.map(colId => {
                  if (colId === 'lineItem') {
                    return (
                      <td key={colId} className="px-2 py-1 whitespace-nowrap" style={{ paddingLeft: `${8 + depth * 16}px` }}>
                        {row.cells.lineItem?.value || row.id}
                      </td>
                    );
                  }
                  const cell = row.cells[colId];
                  const v = cell?.value;
                  const display = typeof v === 'number' ? fmtCurrency(v) : (v ?? '');
                  const isForecast = cell?.source === 'api' || cell?.source === 'formula';
                  return (
                    <td
                      key={colId}
                      className={`px-2 py-1 tabular-nums text-right whitespace-nowrap ${isForecast ? 'text-blue-600 dark:text-blue-400' : ''}`}
                    >
                      {display}
                    </td>
                  );
                })}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );

  // Always render chart — no empty state gatekeeping
  return (
    <MemoSectionWrapper
      sectionType="pnl"
      title="P&L"
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
          <TableauLevelCharts
            data={chartData}
            type={chartMode}
            title=""
            width="100%"
            height={300}
          />
        ) : (
          <div className="flex items-center justify-center h-full text-xs text-muted-foreground">
            Upload data or build a forecast to populate the P&L
          </div>
        )}
      </div>
    </MemoSectionWrapper>
  );
}
