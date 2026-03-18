'use client';

import React, { useMemo, useState, useCallback, useEffect } from 'react';
import dynamic from 'next/dynamic';
import { MemoSectionWrapper } from '../MemoSectionWrapper';
import { useMemoContext, type NarrativeCard } from '../MemoContext';
import { fetchPnl } from '@/lib/memo/api-helpers';
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
type ForecastMethod =
  | 'auto' | 'driver-based' | 'seasonal'
  | 'linear' | 'polynomial' | 'exponential_growth'
  | 'logistic' | 'power_law' | 'gompertz'
  | 'piecewise_linear' | 'weighted_linear';

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

/** Transform backend rows into chart-ready data.
 *  Dynamic — charts all non-header, non-computed rows that have actual values.
 *  This handles any subcategory structure the backend returns. */
function buildChartFromResponse(data: PnlResponse): Record<string, any>[] {
  if (!data.periods || !data.rows) return [];

  // Pick rows worth charting: anything that has values and isn't a section header.
  // Totals (isTotal) are included because they're meaningful aggregates.
  const chartableRows = data.rows.filter(r => !r.isHeader && r.values && Object.keys(r.values).length > 0);

  return data.periods.map(period => {
    const entry: Record<string, any> = { period };
    for (const row of chartableRows) {
      const label = row.label || row.id;
      entry[label] = row.values[period] ?? 0;
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

  // Latest period summary for collapsed state — look for common keys flexibly
  const latestPeriod = chartData[chartData.length - 1];
  const collapsedSummary = useMemo(() => {
    if (!latestPeriod) return 'P&L — no periods loaded';
    // Find revenue / ebitda / net income by label, case-insensitive partial match
    const find = (keywords: string[]) => {
      for (const key of Object.keys(latestPeriod)) {
        const lower = key.toLowerCase();
        if (keywords.some(k => lower.includes(k))) return latestPeriod[key];
      }
      return null;
    };
    const rev = find(['revenue']);
    const ebitda = find(['ebitda']);
    const net = find(['net_income', 'net income']);
    const parts: string[] = [];
    if (rev != null) parts.push(`Revenue: ${fmtCurrency(rev)}`);
    if (ebitda != null) parts.push(`EBITDA: ${fmtCurrency(ebitda)}`);
    if (net != null) parts.push(`Net: ${fmtCurrency(net)}`);
    return parts.length > 0 ? parts.join(' | ') : `P&L — ${chartData.length} periods`;
  }, [latestPeriod, chartData.length]);

  // Build forecast action
  const handleBuildForecast = useCallback(async () => {
    if (!ctx.companyId) return;
    setForecasting(true);
    try {
      await ctx.buildForecast({ method: forecastMethod });
      // Re-fetch P&L to get updated data with forecast
      await handleFetch();
    } finally {
      setForecasting(false);
    }
  }, [ctx, forecastMethod, handleFetch]);

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
          <SelectTrigger className="h-6 w-[150px] text-[11px]">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="auto">Auto (best fit)</SelectItem>
            <SelectItem value="linear">Linear</SelectItem>
            <SelectItem value="polynomial">Polynomial</SelectItem>
            <SelectItem value="exponential_growth">Exponential</SelectItem>
            <SelectItem value="logistic">Logistic (S-curve)</SelectItem>
            <SelectItem value="power_law">Power Law</SelectItem>
            <SelectItem value="gompertz">Gompertz</SelectItem>
            <SelectItem value="piecewise_linear">Piecewise Linear</SelectItem>
            <SelectItem value="weighted_linear">Weighted Linear</SelectItem>
            <SelectItem value="seasonal">Seasonal</SelectItem>
            <SelectItem value="driver-based">Driver-based</SelectItem>
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
