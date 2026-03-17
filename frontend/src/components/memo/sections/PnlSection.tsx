'use client';

import React, { useMemo, useState, useCallback, useEffect } from 'react';
import dynamic from 'next/dynamic';
import { MemoSectionWrapper } from '../MemoSectionWrapper';
import { useMemoContext, type NarrativeCard } from '../MemoContext';
import { fetchPnl, buildForecast } from '@/lib/memo/api-helpers';
import { Button } from '@/components/ui/button';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Loader2, Play, RefreshCw } from 'lucide-react';
import { fmtCurrency } from '@/lib/memo/format';

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

/** Row shape returned by /fpa/pnl backend */
interface PnlRow {
  id: string;
  label: string;
  depth?: number;
  section?: string;
  isHeader?: boolean;
  isTotal?: boolean;
  isComputed?: boolean;
  values: Record<string, number | null>;
}

interface PnlResponse {
  periods: string[];
  rows: PnlRow[];
  forecastStartIndex?: number;
  ratios?: Record<string, any>;
}

/** Chart series we want to plot from the PnlResponse rows */
const PNL_CHART_IDS = ['revenue', 'cogs', 'opex_rd', 'opex_sm', 'opex_ga', 'ebitda', 'net_income'];
const PNL_CHART_LABELS: Record<string, string> = {
  revenue: 'Revenue',
  cogs: 'COGS',
  opex_rd: 'R&D',
  opex_sm: 'S&M',
  opex_ga: 'G&A',
  ebitda: 'EBITDA',
  net_income: 'Net Income',
};

/** Transform backend rows into chart-ready data */
function buildChartFromResponse(data: PnlResponse): Record<string, any>[] {
  if (!data.periods || !data.rows) return [];

  // Build a lookup: row id → values
  const rowMap: Record<string, Record<string, number | null>> = {};
  for (const row of data.rows) {
    rowMap[row.id] = row.values;
  }

  return data.periods.map(period => {
    const entry: Record<string, any> = { period };
    for (const id of PNL_CHART_IDS) {
      const label = PNL_CHART_LABELS[id] || id;
      entry[label] = rowMap[id]?.[period] ?? 0;
    }
    return entry;
  });
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

  // --- Data from backend ---
  const [pnlData, setPnlData] = useState<PnlResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Fetch P&L data from backend on mount and when company changes
  const handleFetch = useCallback(async () => {
    if (!ctx.companyId) return;
    setLoading(true);
    setError(null);
    try {
      const data = await fetchPnl(ctx.companyId);
      setPnlData(data);
    } catch (err: any) {
      console.warn('PnlSection fetch error:', err);
      setError(err.message || 'Failed to load P&L data');
    } finally {
      setLoading(false);
    }
  }, [ctx.companyId]);

  useEffect(() => {
    handleFetch();
  }, [handleFetch]);

  // Filter periods by time range
  const filteredPeriods = useMemo(() => {
    if (!pnlData?.periods) return [];
    const periods = pnlData.periods;
    if (timeRange === 'all' || periods.length === 0) return periods;

    const now = new Date();
    const currentYM = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`;

    if (timeRange === '6m') {
      const idx = periods.indexOf(currentYM);
      const start = Math.max(0, (idx >= 0 ? idx : periods.length) - 3);
      const end = Math.min(periods.length, start + 6);
      return periods.slice(start, end);
    }
    if (timeRange === '12m') {
      const idx = periods.indexOf(currentYM);
      const start = Math.max(0, (idx >= 0 ? idx : periods.length) - 6);
      const end = Math.min(periods.length, start + 12);
      return periods.slice(start, end);
    }
    if (timeRange === 'ytd') {
      const yearPrefix = `${now.getFullYear()}-`;
      return periods.filter(p => p.startsWith(yearPrefix));
    }
    return periods;
  }, [pnlData, timeRange]);

  // Build chart data from backend response
  const chartData = useMemo(
    () => pnlData ? buildChartFromResponse(pnlData) : [],
    [pnlData]
  );

  // Latest period summary for collapsed state
  const latestPeriod = chartData[chartData.length - 1];
  const collapsedSummary = latestPeriod
    ? `Revenue: ${fmtCurrency(latestPeriod.Revenue || 0)} | EBITDA: ${fmtCurrency(latestPeriod.EBITDA || 0)} | Net: ${fmtCurrency(latestPeriod['Net Income'] || 0)}`
    : 'P&L — no periods loaded';

  // Build forecast action
  const handleBuildForecast = useCallback(async () => {
    if (!ctx.companyId) return;
    setForecasting(true);
    try {
      await buildForecast(ctx.companyId, { method: forecastMethod });
      // Re-fetch P&L to get updated data with forecast
      await handleFetch();
    } finally {
      setForecasting(false);
    }
  }, [ctx.companyId, forecastMethod, handleFetch]);

  // AI data context
  const aiContext = useMemo(() => ({
    pnlData: chartData,
    latestPeriod,
    forecastStartIndex: pnlData?.forecastStartIndex,
    forecastMethod,
    branchCount: ctx.activeBranches.length,
  }), [chartData, latestPeriod, pnlData, forecastMethod, ctx.activeBranches.length]);

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

  // ---- Detail: expandable grid rows from backend data ----
  const detailGrid = pnlData?.rows ? (
    <div className="overflow-x-auto mt-2">
      <table className="w-full text-[11px] border-collapse">
        <thead>
          <tr className="border-b-2 border-border bg-muted/50">
            <th className="px-2 py-1 text-left font-semibold whitespace-nowrap">Line Item</th>
            {filteredPeriods.map(period => (
              <th key={period} className="px-2 py-1 text-right font-semibold whitespace-nowrap">
                {period}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {pnlData.rows.map(row => (
            <tr
              key={row.id}
              className={`border-b border-border/50 ${row.isHeader ? 'bg-muted/30 font-semibold' : ''} ${row.isTotal ? 'font-semibold border-t border-border' : ''}`}
            >
              <td className="px-2 py-1 whitespace-nowrap" style={{ paddingLeft: `${8 + (row.depth || 0) * 16}px` }}>
                {row.label}
              </td>
              {filteredPeriods.map(period => {
                const v = row.values[period];
                const isForecast = pnlData.forecastStartIndex != null &&
                  pnlData.periods.indexOf(period) >= pnlData.forecastStartIndex;
                return (
                  <td
                    key={period}
                    className={`px-2 py-1 tabular-nums text-right whitespace-nowrap ${isForecast ? 'text-blue-600 dark:text-blue-400' : ''}`}
                  >
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
        {loading ? (
          <div className="flex items-center justify-center h-full text-xs text-muted-foreground gap-2">
            <Loader2 className="h-4 w-4 animate-spin" />
            Loading P&L data...
          </div>
        ) : error ? (
          <div className="flex items-center justify-center h-full text-xs text-red-500">
            {error}
          </div>
        ) : chartData.length > 0 ? (
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
