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
import { fetchCapTable } from '@/lib/memo/api-helpers';
import { fmtPct } from '@/lib/memo/format';

const TableauLevelCharts = dynamic(
  () => import('@/components/charts/TableauLevelCharts'),
  { ssr: false, loading: () => <div className="h-[300px] animate-pulse bg-muted rounded" /> }
);

type ChartMode = 'cap_table_sankey' | 'pie' | 'treemap';

interface StakeholderRow {
  name: string;
  type: 'founder' | 'investor' | 'employee' | 'advisor' | 'other';
  shares: number;
  ownership_pct: number;
  share_class: string;
  vested_pct?: number;
  board_seat?: boolean;
  voting_rights?: number;
}

export interface StakeholderSectionProps {
  onDelete?: () => void;
  readOnly?: boolean;
}

export function StakeholderSection({ onDelete, readOnly = false }: StakeholderSectionProps) {
  const ctx = useMemoContext();
  const [chartMode, setChartMode] = useState<ChartMode>('cap_table_sankey');
  const [narrativeCards, setNarrativeCards] = useState<NarrativeCard[]>([]);
  const [stakeholders, setStakeholders] = useState<StakeholderRow[]>([]);
  const [loading, setLoading] = useState(false);
  const [groupBy, setGroupBy] = useState<'type' | 'class'>('type');

  const handleFetchStakeholders = useCallback(async () => {
    setLoading(true);
    try {
      const data = await fetchCapTable(ctx.companyId);
      setStakeholders(data.stakeholders || data.rows || []);
    } catch (err) {
      console.warn('Stakeholder fetch failed:', err);
    } finally {
      setLoading(false);
    }
  }, [ctx.companyId]);

  const chartData = useMemo(() => {
    if (stakeholders.length === 0) return [];

    if (chartMode === 'cap_table_sankey') {
      return stakeholders.map(s => ({
        source: groupBy === 'type' ? s.type : s.share_class,
        target: s.name,
        value: s.ownership_pct,
      }));
    }

    return stakeholders.map(s => ({
      name: s.name,
      value: s.ownership_pct,
      type: s.type,
      class: s.share_class,
    }));
  }, [stakeholders, chartMode, groupBy]);

  const typeLabels: Record<string, string> = { founder: 'Founders', investor: 'Investors', employee: 'Employees', advisor: 'Advisors', other: 'Other' };

  // Group summary
  const groupSummary = useMemo(() => {
    const groups: Record<string, number> = {};
    for (const s of stakeholders) {
      const key = groupBy === 'type' ? s.type : s.share_class;
      groups[key] = (groups[key] || 0) + s.ownership_pct;
    }
    return Object.entries(groups).sort((a, b) => b[1] - a[1]);
  }, [stakeholders, groupBy]);

  const collapsedSummary = stakeholders.length > 0
    ? `${stakeholders.length} stakeholders | ${groupSummary.slice(0, 3).map(([k, v]) => `${typeLabels[k] || k}: ${fmtPct(v, 1)}`).join(', ')}`
    : 'Stakeholders — load data';

  const aiContext = useMemo(() => ({
    stakeholders,
    groupSummary,
  }), [stakeholders, groupSummary]);

  const configBar = (
    <>
      <div className="flex items-center gap-1.5">
        <span className="text-muted-foreground">Chart:</span>
        <Select value={chartMode} onValueChange={(v) => setChartMode(v as ChartMode)}>
          <SelectTrigger className="h-6 w-[110px] text-[11px]"><SelectValue /></SelectTrigger>
          <SelectContent>
            <SelectItem value="cap_table_sankey">Sankey</SelectItem>
            <SelectItem value="pie">Pie</SelectItem>
            <SelectItem value="treemap">Treemap</SelectItem>
          </SelectContent>
        </Select>
      </div>
      <div className="flex items-center gap-1.5">
        <span className="text-muted-foreground">Group:</span>
        <Select value={groupBy} onValueChange={(v) => setGroupBy(v as 'type' | 'class')}>
          <SelectTrigger className="h-6 w-[80px] text-[11px]"><SelectValue /></SelectTrigger>
          <SelectContent>
            <SelectItem value="type">Type</SelectItem>
            <SelectItem value="class">Class</SelectItem>
          </SelectContent>
        </Select>
      </div>
      {!readOnly && (
        <Button variant="outline" size="sm" className="h-6 text-[11px] gap-1 ml-auto" onClick={handleFetchStakeholders} disabled={loading}>
          {loading ? <Loader2 className="h-3 w-3 animate-spin" /> : <Play className="h-3 w-3" />}
          Load Stakeholders
        </Button>
      )}
    </>
  );

  const detailGrid = stakeholders.length > 0 ? (
    <div className="overflow-x-auto mt-2">
      <table className="w-full text-[11px] border-collapse">
        <thead>
          <tr className="border-b-2 border-border bg-muted/50">
            <th className="px-2 py-1 text-left font-semibold">Name</th>
            <th className="px-2 py-1 text-left font-semibold">Type</th>
            <th className="px-2 py-1 text-left font-semibold">Class</th>
            <th className="px-2 py-1 text-right font-semibold">Shares</th>
            <th className="px-2 py-1 text-right font-semibold">Ownership</th>
            <th className="px-2 py-1 text-right font-semibold">Vested</th>
            <th className="px-2 py-1 text-center font-semibold">Board</th>
          </tr>
        </thead>
        <tbody>
          {stakeholders.map((s, i) => (
            <tr key={i} className="border-b border-border/50">
              <td className="px-2 py-1 font-medium">{s.name}</td>
              <td className="px-2 py-1">
                <span className="text-[9px] px-1.5 py-0.5 rounded bg-muted">{typeLabels[s.type] || s.type}</span>
              </td>
              <td className="px-2 py-1 text-[10px] font-mono">{s.share_class}</td>
              <td className="px-2 py-1 tabular-nums text-right">{s.shares.toLocaleString()}</td>
              <td className="px-2 py-1 tabular-nums text-right font-semibold">{fmtPct(s.ownership_pct, 1)}</td>
              <td className="px-2 py-1 tabular-nums text-right">{s.vested_pct != null ? fmtPct(s.vested_pct, 1) : '—'}</td>
              <td className="px-2 py-1 text-center">{s.board_seat ? 'Yes' : '—'}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  ) : undefined;

  return (
    <MemoSectionWrapper
      sectionType="stakeholder"
      title="Stakeholder Map"
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
            Load stakeholder data to view ownership map
          </div>
        )}
      </div>
    </MemoSectionWrapper>
  );
}
