'use client';

import React, { useMemo, useState, useCallback } from 'react';
import dynamic from 'next/dynamic';
import { MemoSectionWrapper } from '../MemoSectionWrapper';
import { useMemoContext, type NarrativeCard } from '../MemoContext';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '@/components/ui/select';
import { Loader2, Play, GitBranch, Plus, Trash2, MessageSquare } from 'lucide-react';
import { parseNLScenario } from '@/lib/memo/api-helpers';
import { fmtCurrency } from '@/lib/memo/format';

const TableauLevelCharts = dynamic(
  () => import('@/components/charts/TableauLevelCharts'),
  { ssr: false, loading: () => <div className="h-[300px] animate-pulse bg-muted rounded" /> }
);

type ChartMode = 'branched_line' | 'scenario_tree' | 'bull_bear_base';

export interface ScenarioSectionProps {
  onDelete?: () => void;
  readOnly?: boolean;
}

export function ScenarioSection({ onDelete, readOnly = false }: ScenarioSectionProps) {
  const ctx = useMemoContext();
  const [chartMode, setChartMode] = useState<ChartMode>('branched_line');
  const [narrativeCards, setNarrativeCards] = useState<NarrativeCard[]>([]);
  const [nlInput, setNlInput] = useState('');
  const [parsing, setParsing] = useState(false);
  const [comparing, setComparing] = useState(false);
  const [comparisonMetric, setComparisonMetric] = useState<string>('revenue');

  const branches = ctx.activeBranches;
  const forecasts = ctx.forecasts;
  const baseForecast = ctx.baseForecast;

  // Build branched_line data in the format the chart expects:
  // { x_axis: string[], series: Array<{ name, data, color?, style?, branch_id? }>, annotations?, format? }
  const chartData = useMemo(() => {
    // Collect periods (x_axis)
    let periods: string[] = [];
    const seriesMap: Record<string, number[]> = {};

    if (!baseForecast || baseForecast.length === 0) {
      // Fallback: derive from grid
      const pnlRows = ctx.getPnlRows();
      const cols = ctx.matrixData.columns.filter(c => c.id !== 'lineItem');
      if (cols.length === 0) return { x_axis: [], series: [] };

      periods = cols.map(c => c.id);
      const revRow = pnlRows.find(r => r.id === 'revenue' || r.id === 'total_revenue');
      seriesMap['Base'] = cols.map(col => {
        if (revRow?.cells[col.id]) {
          const v = revRow.cells[col.id].value;
          return typeof v === 'number' ? v : parseFloat(v) || 0;
        }
        return 0;
      });
    } else {
      periods = baseForecast.map(f => f.period);
      seriesMap['Base'] = baseForecast.map(
        (f: any) => f[comparisonMetric] ?? 0
      );

      for (const branch of branches) {
        const bf = forecasts[branch.id];
        if (bf && bf.length > 0) {
          seriesMap[branch.name] = periods.map(
            (_, i) => (bf[i] as any)?.[comparisonMetric] ?? 0
          );
        }
      }
    }

    const COLORS = [
      '#6366f1', '#f59e0b', '#10b981', '#ef4444', '#8b5cf6', '#06b6d4',
      '#f97316', '#ec4899', '#14b8a6', '#a855f7', '#84cc16', '#0ea5e9',
    ];
    const series = Object.entries(seriesMap).map(([name, data], idx) => ({
      name,
      data,
      color: COLORS[idx % COLORS.length],
      style: idx === 0 ? 'solid' : 'dashed',
      ...(idx > 0 ? { branch_id: branches[idx - 1]?.id } : {}),
    }));

    // Build fork_point annotations for branches
    const annotations: any[] = [];
    for (const branch of branches) {
      const bf = forecasts[branch.id];
      if (!bf || bf.length === 0) continue;
      // Find first period where branch diverges from base
      const baseData = seriesMap['Base'] || [];
      const branchData = seriesMap[branch.name] || [];
      let forkIdx = 0;
      for (let i = 0; i < baseData.length; i++) {
        if (branchData[i] !== baseData[i]) {
          forkIdx = Math.max(0, i - 1);
          break;
        }
      }
      annotations.push({
        type: 'fork_point',
        x: forkIdx,
        x_index: forkIdx,
        label: branch.name,
      });
    }

    return {
      x_axis: periods,
      series,
      annotations,
      format: '$',
    };
  }, [baseForecast, branches, forecasts, comparisonMetric, ctx]);

  // Deltas between branches and base
  const branchDeltas = useMemo(() => {
    if (!baseForecast || baseForecast.length === 0) return [];

    return branches.map(branch => {
      const branchForecast = forecasts[branch.id] || [];
      const lastBase = baseForecast[baseForecast.length - 1] as any;
      const lastBranch = branchForecast[branchForecast.length - 1] as any;

      return {
        id: branch.id,
        name: branch.name,
        probability: branch.probability,
        revenueΔ: (lastBranch?.revenue || 0) - (lastBase?.revenue || 0),
        ebitdaΔ: (lastBranch?.ebitda || 0) - (lastBase?.ebitda || 0),
        runwayΔ: (lastBranch?.runway_months || 0) - (lastBase?.runway_months || 0),
      };
    });
  }, [baseForecast, branches, forecasts]);

  // NL scenario composer — parse "what if..." into branch (correct endpoint: /what-if not /parse)
  const handleNLSubmit = useCallback(async () => {
    if (!nlInput.trim()) return;
    setParsing(true);
    try {
      const data = await parseNLScenario(nlInput, ctx.companyId);
      const scenario = data.composed_scenario || data;
      const assumptions = scenario.assumptions || scenario.drivers || data.assumptions || data.drivers || {};
      const name = scenario.scenario_name || data.name || nlInput.slice(0, 40);
      const forkPeriod = data.fork_period || null;
      await ctx.createFork(name, ctx.activeBranchId, forkPeriod, assumptions);
      setNlInput('');
    } catch (err) {
      console.warn('NL scenario parse failed:', err);
    } finally {
      setParsing(false);
    }
  }, [nlInput, ctx]);

  // Delete a branch
  const handleDeleteBranch = useCallback(async (branchId: string) => {
    await ctx.deleteFork(branchId);
  }, [ctx]);

  // Fork from an existing branch
  const handleForkFrom = useCallback(async (parentBranchId: string) => {
    await ctx.createFork(`Fork of ${branches.find(b => b.id === parentBranchId)?.name || 'branch'}`, parentBranchId, null, {});
  }, [ctx, branches]);

  const collapsedSummary = `${branches.length} branch${branches.length !== 1 ? 'es' : ''} | ${comparisonMetric}`;

  const aiContext = useMemo(() => ({
    branches: branchDeltas,
    comparisonMetric,
    branchCount: branches.length,
  }), [branchDeltas, comparisonMetric, branches.length]);

  const configBar = (
    <>
      <div className="flex items-center gap-1.5">
        <span className="text-muted-foreground">Chart:</span>
        <Select value={chartMode} onValueChange={(v) => setChartMode(v as ChartMode)}>
          <SelectTrigger className="h-6 w-[120px] text-[11px]"><SelectValue /></SelectTrigger>
          <SelectContent>
            <SelectItem value="branched_line">Branched Line</SelectItem>
            <SelectItem value="scenario_tree">Scenario Tree</SelectItem>
            <SelectItem value="bull_bear_base">Bull/Bear/Base</SelectItem>
          </SelectContent>
        </Select>
      </div>
      <div className="flex items-center gap-1.5">
        <span className="text-muted-foreground">Metric:</span>
        <Select value={comparisonMetric} onValueChange={setComparisonMetric}>
          <SelectTrigger className="h-6 w-[120px] text-[11px]"><SelectValue /></SelectTrigger>
          <SelectContent>
            <SelectItem value="revenue">Revenue</SelectItem>
            <SelectItem value="gross_profit">Gross Profit</SelectItem>
            <SelectItem value="cogs">COGS</SelectItem>
            <SelectItem value="ebitda">EBITDA</SelectItem>
            <SelectItem value="total_opex">Total Opex</SelectItem>
            <SelectItem value="rd_spend">R&D</SelectItem>
            <SelectItem value="sm_spend">S&M</SelectItem>
            <SelectItem value="ga_spend">G&A</SelectItem>
            <SelectItem value="net_income">Net Income</SelectItem>
            <SelectItem value="free_cash_flow">Free Cash Flow</SelectItem>
            <SelectItem value="cash_balance">Cash</SelectItem>
            <SelectItem value="capex">CapEx</SelectItem>
            <SelectItem value="runway_months">Runway</SelectItem>
          </SelectContent>
        </Select>
      </div>
    </>
  );

  const detailGrid = branchDeltas.length > 0 ? (
    <div className="overflow-x-auto mt-2">
      <table className="w-full text-[11px] border-collapse">
        <thead>
          <tr className="border-b-2 border-border bg-muted/50">
            <th className="px-2 py-1 text-left font-semibold">Branch</th>
            <th className="px-2 py-1 text-right font-semibold">Probability</th>
            <th className="px-2 py-1 text-right font-semibold">Revenue Δ</th>
            <th className="px-2 py-1 text-right font-semibold">EBITDA Δ</th>
            <th className="px-2 py-1 text-right font-semibold">Runway Δ</th>
            {!readOnly && <th className="px-2 py-1 text-right font-semibold">Actions</th>}
          </tr>
        </thead>
        <tbody>
          {branchDeltas.map(d => (
            <tr key={d.id} className="border-b border-border/50">
              <td className="px-2 py-1 whitespace-nowrap flex items-center gap-1">
                <GitBranch className="h-3 w-3 text-muted-foreground" />
                {d.name}
              </td>
              <td className="px-2 py-1 tabular-nums text-right">{d.probability != null ? `${(d.probability * 100).toFixed(0)}%` : '—'}</td>
              <td className={`px-2 py-1 tabular-nums text-right ${d.revenueΔ >= 0 ? 'text-emerald-600' : 'text-red-600'}`}>
                {d.revenueΔ >= 0 ? '+' : ''}{fmtCurrency(d.revenueΔ)}
              </td>
              <td className={`px-2 py-1 tabular-nums text-right ${d.ebitdaΔ >= 0 ? 'text-emerald-600' : 'text-red-600'}`}>
                {d.ebitdaΔ >= 0 ? '+' : ''}{fmtCurrency(d.ebitdaΔ)}
              </td>
              <td className={`px-2 py-1 tabular-nums text-right ${d.runwayΔ >= 0 ? 'text-emerald-600' : 'text-red-600'}`}>
                {d.runwayΔ >= 0 ? '+' : ''}{d.runwayΔ.toFixed(0)}mo
              </td>
              {!readOnly && (
                <td className="px-2 py-1 text-right">
                  <div className="flex items-center justify-end gap-1">
                    <Button variant="ghost" size="sm" className="h-5 w-5 p-0" onClick={() => handleForkFrom(d.id)} title="Fork from this branch">
                      <Plus className="h-3 w-3" />
                    </Button>
                    <Button variant="ghost" size="sm" className="h-5 w-5 p-0 hover:text-destructive" onClick={() => handleDeleteBranch(d.id)} title="Delete branch">
                      <Trash2 className="h-3 w-3" />
                    </Button>
                  </div>
                </td>
              )}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  ) : undefined;

  return (
    <MemoSectionWrapper
      sectionType="scenario"
      title="Scenarios"
      collapsedSummary={collapsedSummary}
      configContent={configBar}
      detailContent={detailGrid}
      narrativeCards={narrativeCards}
      onNarrativeCardsChange={setNarrativeCards}
      aiDataContext={aiContext}
      onDelete={onDelete}
      readOnly={readOnly}
    >
      {/* NL Input */}
      {!readOnly && (
        <div className="flex items-center gap-2 mb-3">
          <div className="relative flex-1">
            <MessageSquare className="absolute left-2 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground" />
            <Input
              className="h-8 pl-7 text-sm"
              placeholder="What if we hire 3 more engineers and raise prices 15%..."
              value={nlInput}
              onChange={e => setNlInput(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && handleNLSubmit()}
              disabled={parsing}
            />
          </div>
          <Button
            variant="outline"
            size="sm"
            className="h-8 text-[11px] gap-1"
            onClick={handleNLSubmit}
            disabled={parsing || !nlInput.trim()}
          >
            {parsing ? <Loader2 className="h-3 w-3 animate-spin" /> : <Play className="h-3 w-3" />}
            Create Branch
          </Button>
        </div>
      )}

      {/* Chart */}
      <div className="w-full" style={{ height: 320 }}>
        {chartData.x_axis.length > 0 ? (
          <TableauLevelCharts
            data={chartData}
            type={chartMode}
            title=""
            width="100%"
            height={300}
          />
        ) : (
          <div className="flex items-center justify-center h-full text-xs text-muted-foreground">
            Create a scenario branch to compare forecasts
          </div>
        )}
      </div>
    </MemoSectionWrapper>
  );
}
