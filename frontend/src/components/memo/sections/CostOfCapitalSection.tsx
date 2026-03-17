'use client';

import React, { useMemo, useState, useCallback } from 'react';
import dynamic from 'next/dynamic';
import { MemoSectionWrapper } from '../MemoSectionWrapper';
import { useMemoContext, type NarrativeCard } from '../MemoContext';
import { Button } from '@/components/ui/button';
import { Loader2, Play } from 'lucide-react';
import { getClientBackendUrl } from '@/lib/backend-url';

const TableauLevelCharts = dynamic(
  () => import('@/components/charts/TableauLevelCharts'),
  { ssr: false, loading: () => <div className="h-[300px] animate-pulse bg-muted rounded" /> }
);

interface WACCResult {
  wacc: number;
  cost_of_equity: number;
  cost_of_debt: number;
  equity_weight: number;
  debt_weight: number;
  tax_rate: number;
  risk_free_rate: number;
  equity_risk_premium: number;
  beta?: number;
  size_premium?: number;
  components?: Array<{ name: string; value: number; weight: number }>;
}

function fmtPct(v: number): string {
  return `${(v * 100).toFixed(2)}%`;
}

function fmtCurrency(v: number): string {
  if (Math.abs(v) >= 1e9) return `$${(v / 1e9).toFixed(1)}B`;
  if (Math.abs(v) >= 1e6) return `$${(v / 1e6).toFixed(1)}M`;
  if (Math.abs(v) >= 1e3) return `$${(v / 1e3).toFixed(0)}K`;
  return `$${v.toLocaleString()}`;
}

export interface CostOfCapitalSectionProps {
  onDelete?: () => void;
  readOnly?: boolean;
}

export function CostOfCapitalSection({ onDelete, readOnly = false }: CostOfCapitalSectionProps) {
  const ctx = useMemoContext();
  const backendUrl = getClientBackendUrl();
  const [narrativeCards, setNarrativeCards] = useState<NarrativeCard[]>([]);
  const [result, setResult] = useState<WACCResult | null>(null);
  const [loading, setLoading] = useState(false);

  const handleCalculate = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch(`${backendUrl}/api/advanced-analytics/analyze`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          company_id: ctx.companyId,
          analysis_type: 'cost_of_capital',
        }),
      });
      if (res.ok) {
        const data = await res.json();
        setResult(data);
      }
    } finally {
      setLoading(false);
    }
  }, [backendUrl, ctx.companyId]);

  const chartData = useMemo(() => {
    if (!result) return [];
    return [
      { name: 'Cost of Equity', value: result.cost_of_equity, weight: result.equity_weight },
      { name: 'Cost of Debt (AT)', value: result.cost_of_debt * (1 - result.tax_rate), weight: result.debt_weight },
      { name: 'WACC', value: result.wacc, weight: 1 },
    ];
  }, [result]);

  const collapsedSummary = result
    ? `WACC: ${fmtPct(result.wacc)} | Ke: ${fmtPct(result.cost_of_equity)} | Kd: ${fmtPct(result.cost_of_debt)}`
    : 'Cost of Capital — calculate WACC';

  const aiContext = useMemo(() => ({ result }), [result]);

  const configBar = !readOnly ? (
    <Button variant="outline" size="sm" className="h-6 text-[11px] gap-1 ml-auto" onClick={handleCalculate} disabled={loading}>
      {loading ? <Loader2 className="h-3 w-3 animate-spin" /> : <Play className="h-3 w-3" />}
      Calculate WACC
    </Button>
  ) : undefined;

  return (
    <MemoSectionWrapper
      sectionType="cost_of_capital"
      title="Cost of Capital"
      collapsedSummary={collapsedSummary}
      configContent={configBar}
      narrativeCards={narrativeCards}
      onNarrativeCardsChange={setNarrativeCards}
      aiDataContext={aiContext}
      onDelete={onDelete}
      readOnly={readOnly}
    >
      {result ? (
        <div className="space-y-3">
          {/* WACC headline */}
          <div className="flex items-center gap-4 p-3 rounded-lg border border-primary/20 bg-primary/5">
            <div>
              <div className="text-[10px] text-muted-foreground uppercase tracking-wider">WACC</div>
              <div className="text-2xl font-bold tabular-nums">{fmtPct(result.wacc)}</div>
            </div>
            <div className="h-8 w-px bg-border" />
            <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-[11px]">
              <div><span className="text-muted-foreground">Cost of Equity:</span> <span className="font-semibold tabular-nums">{fmtPct(result.cost_of_equity)}</span></div>
              <div><span className="text-muted-foreground">Equity Weight:</span> <span className="font-semibold tabular-nums">{fmtPct(result.equity_weight)}</span></div>
              <div><span className="text-muted-foreground">Cost of Debt:</span> <span className="font-semibold tabular-nums">{fmtPct(result.cost_of_debt)}</span></div>
              <div><span className="text-muted-foreground">Debt Weight:</span> <span className="font-semibold tabular-nums">{fmtPct(result.debt_weight)}</span></div>
            </div>
          </div>

          {/* Build-up cards */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-1.5">
            <div className="rounded-md border border-border/50 bg-muted/30 p-2">
              <div className="text-[9px] text-muted-foreground uppercase font-mono">Risk-Free</div>
              <div className="text-sm font-semibold tabular-nums">{fmtPct(result.risk_free_rate)}</div>
            </div>
            <div className="rounded-md border border-border/50 bg-muted/30 p-2">
              <div className="text-[9px] text-muted-foreground uppercase font-mono">ERP</div>
              <div className="text-sm font-semibold tabular-nums">{fmtPct(result.equity_risk_premium)}</div>
            </div>
            {result.beta != null && (
              <div className="rounded-md border border-border/50 bg-muted/30 p-2">
                <div className="text-[9px] text-muted-foreground uppercase font-mono">Beta</div>
                <div className="text-sm font-semibold tabular-nums">{result.beta.toFixed(2)}</div>
              </div>
            )}
            <div className="rounded-md border border-border/50 bg-muted/30 p-2">
              <div className="text-[9px] text-muted-foreground uppercase font-mono">Tax Rate</div>
              <div className="text-sm font-semibold tabular-nums">{fmtPct(result.tax_rate)}</div>
            </div>
          </div>

          {/* Chart */}
          <div className="w-full" style={{ height: 200 }}>
            <TableauLevelCharts data={chartData} type="bar" title="" width="100%" height={180} />
          </div>
        </div>
      ) : (
        <div className="flex items-center justify-center h-[200px] text-xs text-muted-foreground">
          Calculate WACC to view cost of capital components
        </div>
      )}
    </MemoSectionWrapper>
  );
}
