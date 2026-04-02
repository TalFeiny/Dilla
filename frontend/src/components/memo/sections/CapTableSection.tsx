'use client';

import React, { useMemo, useState, useCallback, useRef, useEffect } from 'react';
import dynamic from 'next/dynamic';
import { MemoSectionWrapper } from '../MemoSectionWrapper';
import { useMemoContext, type NarrativeCard } from '../MemoContext';
import { Button } from '@/components/ui/button';
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '@/components/ui/select';
import { Loader2, Play } from 'lucide-react';
import { fetchCapTable } from '@/lib/memo/api-helpers';
import { fmtCurrency, fmtPct } from '@/lib/memo/format';

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

export interface CapTableSectionProps {
  onDelete?: () => void;
  readOnly?: boolean;
}

function EditableCell({ value, align, className, readOnly, onCommit }: {
  value: string; align: 'left' | 'right'; className?: string; readOnly?: boolean;
  onCommit: (v: string) => void;
}) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(value);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => { if (editing) { setDraft(value); inputRef.current?.select(); } }, [editing, value]);

  if (editing && !readOnly) {
    return (
      <td className={`px-2 py-0.5 ${align === 'right' ? 'text-right' : 'text-left'}`}>
        <input
          ref={inputRef}
          autoFocus
          className={`w-full bg-transparent outline-none border-b border-primary text-[11px] tabular-nums ${align === 'right' ? 'text-right' : 'text-left'} ${className ?? ''}`}
          value={draft}
          onChange={e => setDraft(e.target.value)}
          onKeyDown={e => {
            if (e.key === 'Enter') { onCommit(draft); setEditing(false); }
            if (e.key === 'Escape') setEditing(false);
          }}
          onBlur={() => { onCommit(draft); setEditing(false); }}
        />
      </td>
    );
  }

  return (
    <td
      className={`px-2 py-1 whitespace-nowrap tabular-nums ${align === 'right' ? 'text-right' : 'text-left'} ${className ?? ''} ${readOnly ? '' : 'cursor-text hover:bg-muted/40'}`}
      onDoubleClick={() => { if (!readOnly) setEditing(true); }}
    >
      {value}
    </td>
  );
}

export function CapTableSection({ onDelete, readOnly = false }: CapTableSectionProps) {
  const ctx = useMemoContext();
  const [chartMode, setChartMode] = useState<ChartMode>('cap_table_waterfall');
  const [narrativeCards, setNarrativeCards] = useState<NarrativeCard[]>([]);
  const [capTableData, setCapTableData] = useState<CapTableRow[]>([]);
  const [loading, setLoading] = useState(false);
  const [exitValuation, setExitValuation] = useState<string>('50000000');

  const handleFetchCapTable = useCallback(async () => {
    setLoading(true);
    try {
      const data = await fetchCapTable(ctx.companyId, ctx.fundId || undefined);

      // Flexibly map whatever shape the backend returns.
      const raw: any[] = data.share_entries
        || data.cap_table
        || data.ownership
        || data.stakeholders
        || data.rows
        || (Array.isArray(data) ? data : []);

      // Separate ownership array for cross-referencing if present alongside share_entries
      const ownershipMap = new Map<string, number>();
      if (data.ownership && Array.isArray(data.ownership) && data.share_entries) {
        for (const o of data.ownership) {
          const key = o.shareholder_name ?? o.shareholder ?? o.name ?? '';
          ownershipMap.set(key, o.ownership_pct ?? o.percentage ?? o.pct ?? 0);
        }
      }

      const mapped: CapTableRow[] = raw.map((entry: any) => {
        const name = entry.shareholder_name ?? entry.shareholder ?? entry.name ?? entry.stakeholder ?? '';
        return {
          stakeholder: name,
          shares: typeof entry.num_shares === 'string' ? parseInt(entry.num_shares) || 0
            : (entry.num_shares ?? entry.shares ?? 0),
          ownership_pct: entry.ownership_pct ?? entry.percentage ?? entry.pct
            ?? ownershipMap.get(name) ?? 0,
          share_class: entry.share_class ?? entry.class ?? entry.type ?? '',
          liquidation_pref: entry.liquidation_pref ?? entry.liquidation_preference ?? entry.liq_pref,
          invested: entry.invested ?? entry.investment_amount ?? entry.amount_invested,
          value_at_exit: entry.value_at_exit ?? entry.exit_value,
        };
      });

      setCapTableData(mapped);
    } catch (err) {
      console.warn('Cap table fetch failed:', err);
    } finally {
      setLoading(false);
    }
  }, [ctx.companyId, ctx.fundId]);

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

  const updateRow = useCallback((index: number, field: keyof CapTableRow, raw: string) => {
    setCapTableData(prev => prev.map((r, i) => {
      if (i !== index) return r;
      if (field === 'stakeholder' || field === 'share_class') return { ...r, [field]: raw };
      const n = parseFloat(raw.replace(/[^0-9.-]/g, ''));
      return { ...r, [field]: isNaN(n) ? r[field] : n };
    }));
  }, []);

  const totalOwnership = capTableData.reduce((sum, r) => sum + r.ownership_pct, 0);
  const collapsedSummary = capTableData.length > 0
    ? `${capTableData.length} stakeholders | ${fmtPct(totalOwnership, 1)} allocated`
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
              <EditableCell value={row.stakeholder} align="left" className="font-medium" readOnly={readOnly} onCommit={v => updateRow(i, 'stakeholder', v)} />
              <EditableCell value={row.share_class} align="left" readOnly={readOnly} onCommit={v => updateRow(i, 'share_class', v)} />
              <EditableCell value={row.shares.toLocaleString()} align="right" readOnly={readOnly} onCommit={v => updateRow(i, 'shares', v)} />
              <EditableCell value={fmtPct(row.ownership_pct, 1)} align="right" readOnly={readOnly} onCommit={v => updateRow(i, 'ownership_pct', v)} />
              <EditableCell value={row.liquidation_pref != null ? `${row.liquidation_pref}x` : '—'} align="right" readOnly={readOnly} onCommit={v => updateRow(i, 'liquidation_pref', v)} />
              <EditableCell value={row.invested ? fmtCurrency(row.invested) : '—'} align="right" readOnly={readOnly} onCommit={v => updateRow(i, 'invested', v)} />
              <EditableCell value={fmtCurrency(row.value_at_exit || row.ownership_pct * (parseFloat(exitValuation) || 50000000))} align="right" className="font-medium" readOnly={readOnly} onCommit={v => updateRow(i, 'value_at_exit', v)} />
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
