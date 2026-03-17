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
import { getClientBackendUrl } from '@/lib/backend-url';

const TableauLevelCharts = dynamic(
  () => import('@/components/charts/TableauLevelCharts'),
  { ssr: false, loading: () => <div className="h-[300px] animate-pulse bg-muted rounded" /> }
);

type ChartMode = 'cap_table_waterfall' | 'cap_table_sankey' | 'cap_table_evolution' | 'pie';

interface CapTableRow {
  stakeholder: string;
  shares: number;
  ownership_pct: number;
  share_class: string;
  liquidation_pref?: number;
  invested?: number;
  value_at_exit?: number;
}

function fmtPct(v: number): string {
  return `${(v * 100).toFixed(1)}%`;
}

function fmtCurrency(v: number): string {
  if (Math.abs(v) >= 1e9) return `$${(v / 1e9).toFixed(1)}B`;
  if (Math.abs(v) >= 1e6) return `$${(v / 1e6).toFixed(1)}M`;
  if (Math.abs(v) >= 1e3) return `$${(v / 1e3).toFixed(0)}K`;
  return `$${v.toLocaleString()}`;
}

export interface CapTableSectionProps {
  onDelete?: () => void;
  readOnly?: boolean;
}

export function CapTableSection({ onDelete, readOnly = false }: CapTableSectionProps) {
  const ctx = useMemoContext();
  const backendUrl = getClientBackendUrl();
  const [chartMode, setChartMode] = useState<ChartMode>('cap_table_waterfall');
  const [narrativeCards, setNarrativeCards] = useState<NarrativeCard[]>([]);
  const [capTableData, setCapTableData] = useState<CapTableRow[]>([]);
  const [loading, setLoading] = useState(false);
  const [exitValuation, setExitValuation] = useState<string>('50000000');

  const handleFetchCapTable = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch(`${backendUrl}/api/cap-table-bridge`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          company_id: ctx.companyId,
          exit_valuation: parseFloat(exitValuation) || 50000000,
        }),
      });
      if (res.ok) {
        const data = await res.json();
        setCapTableData(data.cap_table || data.stakeholders || data.rows || []);
      }
    } finally {
      setLoading(false);
    }
  }, [backendUrl, ctx.companyId, exitValuation]);

  // Build chart data for various chart types
  const chartData = useMemo(() => {
    if (capTableData.length === 0) return [];

    if (chartMode === 'pie') {
      return capTableData.map(row => ({
        name: row.stakeholder,
        value: row.ownership_pct,
        shares: row.shares,
        class: row.share_class,
      }));
    }

    if (chartMode === 'cap_table_waterfall') {
      return capTableData.map(row => ({
        name: row.stakeholder,
        value: row.value_at_exit || row.ownership_pct * (parseFloat(exitValuation) || 50000000),
        ownership: row.ownership_pct,
        invested: row.invested || 0,
        class: row.share_class,
      }));
    }

    // sankey / evolution
    return capTableData.map(row => ({
      source: row.share_class,
      target: row.stakeholder,
      value: row.ownership_pct,
      shares: row.shares,
    }));
  }, [capTableData, chartMode, exitValuation]);

  const totalOwnership = capTableData.reduce((sum, r) => sum + r.ownership_pct, 0);
  const collapsedSummary = capTableData.length > 0
    ? `${capTableData.length} stakeholders | ${fmtPct(totalOwnership)} allocated`
    : 'Cap Table — load data to view';

  const aiContext = useMemo(() => ({
    capTableData,
    exitValuation: parseFloat(exitValuation),
    stakeholderCount: capTableData.length,
  }), [capTableData, exitValuation]);

  const configBar = (
    <>
      <div className="flex items-center gap-1.5">
        <span className="text-muted-foreground">View:</span>
        <Select value={chartMode} onValueChange={(v) => setChartMode(v as ChartMode)}>
          <SelectTrigger className="h-6 w-[130px] text-[11px]"><SelectValue /></SelectTrigger>
          <SelectContent>
            <SelectItem value="cap_table_waterfall">Waterfall</SelectItem>
            <SelectItem value="cap_table_sankey">Sankey</SelectItem>
            <SelectItem value="cap_table_evolution">Evolution</SelectItem>
            <SelectItem value="pie">Pie Chart</SelectItem>
          </SelectContent>
        </Select>
      </div>
      <div className="flex items-center gap-1.5">
        <span className="text-muted-foreground">Exit $:</span>
        <input
          type="text"
          className="h-6 w-[90px] text-[11px] rounded border border-input bg-background px-2 tabular-nums"
          value={exitValuation}
          onChange={e => setExitValuation(e.target.value)}
        />
      </div>
      {!readOnly && (
        <Button variant="outline" size="sm" className="h-6 text-[11px] gap-1 ml-auto" onClick={handleFetchCapTable} disabled={loading}>
          {loading ? <Loader2 className="h-3 w-3 animate-spin" /> : <Play className="h-3 w-3" />}
          Load Cap Table
        </Button>
      )}
    </>
  );

  const detailGrid = capTableData.length > 0 ? (
    <div className="overflow-x-auto mt-2">
      <table className="w-full text-[11px] border-collapse">
        <thead>
          <tr className="border-b-2 border-border bg-muted/50">
            <th className="px-2 py-1 text-left font-semibold">Stakeholder</th>
            <th className="px-2 py-1 text-left font-semibold">Class</th>
            <th className="px-2 py-1 text-right font-semibold">Shares</th>
            <th className="px-2 py-1 text-right font-semibold">Ownership</th>
            <th className="px-2 py-1 text-right font-semibold">Liq. Pref</th>
            <th className="px-2 py-1 text-right font-semibold">Invested</th>
            <th className="px-2 py-1 text-right font-semibold">Value at Exit</th>
          </tr>
        </thead>
        <tbody>
          {capTableData.map((row, i) => (
            <tr key={i} className="border-b border-border/50">
              <td className="px-2 py-1 whitespace-nowrap font-medium">{row.stakeholder}</td>
              <td className="px-2 py-1 whitespace-nowrap">
                <span className="text-[9px] px-1.5 py-0.5 rounded bg-muted">{row.share_class}</span>
              </td>
              <td className="px-2 py-1 tabular-nums text-right">{row.shares.toLocaleString()}</td>
              <td className="px-2 py-1 tabular-nums text-right">{fmtPct(row.ownership_pct)}</td>
              <td className="px-2 py-1 tabular-nums text-right">{row.liquidation_pref != null ? `${row.liquidation_pref}x` : '—'}</td>
              <td className="px-2 py-1 tabular-nums text-right">{row.invested ? fmtCurrency(row.invested) : '—'}</td>
              <td className="px-2 py-1 tabular-nums text-right font-medium">
                {fmtCurrency(row.value_at_exit || row.ownership_pct * (parseFloat(exitValuation) || 50000000))}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  ) : undefined;

  return (
    <MemoSectionWrapper
      sectionType="cap_table"
      title="Cap Table"
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
            Load cap table data to visualize ownership
          </div>
        )}
      </div>
    </MemoSectionWrapper>
  );
}
