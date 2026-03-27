'use client';

import React, { useMemo, useState, useCallback, useEffect } from 'react';
import dynamic from 'next/dynamic';
import { MemoSectionWrapper } from '../MemoSectionWrapper';
import { useMemoContext, type NarrativeCard } from '../MemoContext';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '@/components/ui/select';
import { Loader2, Play, MessageSquare } from 'lucide-react';
import { constructForecastModel, executeForecastModel } from '@/lib/memo/api-helpers';
import { CascadeModelView, type ModelExecutionResult } from './CascadeModelView';
import { ModelSpecEditor } from './ModelSpecEditor';

const TableauLevelCharts = dynamic(
  () => import('@/components/charts/TableauLevelCharts'),
  { ssr: false, loading: () => <div className="h-[300px] animate-pulse bg-muted rounded" /> }
);

type ChartMode = 'branched_line' | 'stacked_bar' | 'treemap' | 'regression_line' | 'line' | 'bar_comparison' | 'monte_carlo_fan';
/** Maps to backend ForecastMethodRouter.METHODS */
type ForecastMethod =
  | 'auto' | 'liquidity' | 'advanced_regression' | 'model_construction'
  | 'driver_based' | 'seasonal' | 'monte_carlo'
  | 'regression' | 'budget_pct' | 'growth_rate';
type ForecastMetric = 'revenue' | 'ebitda' | 'gross_profit' | 'total_opex' | 'free_cash_flow' | 'cogs';
type ForecastGranularity = 'monthly' | 'quarterly' | 'annual';

export interface ForecastMethodSectionProps {
  onDelete?: () => void;
  readOnly?: boolean;
}

export function ForecastMethodSection({ onDelete, readOnly = false }: ForecastMethodSectionProps) {
  const ctx = useMemoContext();
  const [chartMode, setChartMode] = useState<ChartMode>('branched_line');
  const [narrativeCards, setNarrativeCards] = useState<NarrativeCard[]>([]);
  const [selectedMethod, setSelectedMethod] = useState<ForecastMethod>('auto');
  const [selectedMetric, setSelectedMetric] = useState<ForecastMetric>('revenue');
  const [forecastPeriods, setForecastPeriods] = useState(12);
  const [granularity, setGranularity] = useState<ForecastGranularity>('monthly');
  const [loading, setLoading] = useState(false);

  // Model construction state
  const [mcPrompt, setMcPrompt] = useState('');
  const [mcResult, setMcResult] = useState<ModelExecutionResult | null>(null);
  const [mcModelIds, setMcModelIds] = useState<string[]>([]);

  const isModelConstruction = selectedMethod === 'model_construction';

  // Standard forecast build
  const handleBuildForecast = useCallback(async () => {
    if (!ctx.companyId) return;
    setLoading(true);
    try {
      await ctx.buildForecast({
        method: selectedMethod,
        metric: selectedMetric,
        forecast_periods: forecastPeriods,
        granularity,
      });
    } catch (err: any) {
      console.warn('Forecast build error:', err);
    } finally {
      setLoading(false);
    }
  }, [ctx, selectedMethod, selectedMetric, forecastPeriods, granularity]);

  // Model construction: construct + execute
  const handleModelConstruction = useCallback(async (prompt?: string) => {
    if (!ctx.companyId) return;
    const p = prompt || mcPrompt;
    if (!p.trim()) return;
    setLoading(true);
    try {
      // Step 1: Construct
      const constructResult = await constructForecastModel(ctx.companyId, p);
      const data = constructResult.result || constructResult;
      const modelIds: string[] = data.model_ids || [];
      setMcModelIds(modelIds);

      if (modelIds.length === 0) {
        console.warn('No models constructed');
        return;
      }

      // Step 2: Execute
      const execResult = await executeForecastModel(
        ctx.companyId,
        modelIds[0],
        forecastPeriods,
      );
      const execData = execResult.result || execResult;
      const results = execData.results || [];

      if (results.length > 0) {
        setMcResult(results[0]);
      }
    } catch (err: any) {
      console.warn('Model construction error:', err);
    } finally {
      setLoading(false);
    }
  }, [ctx.companyId, mcPrompt, forecastPeriods]);

  // Re-run executor with current model
  const handleReRun = useCallback(async () => {
    if (!ctx.companyId || mcModelIds.length === 0) return;
    setLoading(true);
    try {
      const execResult = await executeForecastModel(
        ctx.companyId,
        mcModelIds[0],
        forecastPeriods,
      );
      const execData = execResult.result || execResult;
      const results = execData.results || [];
      if (results.length > 0) {
        setMcResult(results[0]);
      }
    } catch (err: any) {
      console.warn('Model re-execution error:', err);
    } finally {
      setLoading(false);
    }
  }, [ctx.companyId, mcModelIds, forecastPeriods]);

  // Event chain handlers for ModelSpecEditor
  const handleToggleEvent = useCallback((eventId: string, enabled: boolean) => {
    // Update local state — will re-run on next Run click
    if (!mcResult?.event_chain) return;
    const updated = { ...mcResult };
    if (updated.event_chain) {
      updated.event_chain = {
        ...updated.event_chain,
        events: updated.event_chain.events.map(e =>
          e.id === eventId ? { ...e, probability: enabled ? e.probability || 0.5 : 0 } : e
        ),
      };
      setMcResult(updated);
    }
  }, [mcResult]);

  const handleChangeProbability = useCallback((eventId: string, probability: number) => {
    if (!mcResult?.event_chain) return;
    const updated = { ...mcResult };
    if (updated.event_chain) {
      updated.event_chain = {
        ...updated.event_chain,
        events: updated.event_chain.events.map(e =>
          e.id === eventId ? { ...e, probability } : e
        ),
      };
      setMcResult(updated);
    }
  }, [mcResult]);

  const handleRePrompt = useCallback((prompt: string) => {
    setMcPrompt(prompt);
    handleModelConstruction(prompt);
  }, [handleModelConstruction]);

  const methodResult = ctx.forecastMeta;

  // Build static narrative cards from forecast metadata (no LLM call)
  useEffect(() => {
    if (!methodResult || isModelConstruction) return;
    const cards: NarrativeCard[] = [];

    if (methodResult.r_squared != null) {
      const r2 = methodResult.r_squared;
      const quality = r2 >= 0.9 ? 'High confidence' : r2 >= 0.7 ? 'Moderate confidence' : 'Low confidence';
      const severity = r2 >= 0.7 ? 'info' : 'warning';
      const mapeNote = methodResult.mape != null
        ? ` — average forecast error: ${(methodResult.mape * 100).toFixed(1)}%`
        : '';
      cards.push({
        id: 'forecast-accuracy',
        text: `${quality} forecast${mapeNote}`,
        severity,
      });
    }

    if (methodResult.description) {
      cards.push({
        id: 'forecast-description',
        text: methodResult.description,
        severity: 'info',
      });
    }

    setNarrativeCards(cards);
  }, [methodResult, isModelConstruction]);

  // Backend returns pre-built chart shapes keyed by chart type
  const chartShape = useMemo(() => {
    if (!methodResult?.fit_data) return null;
    const shapes = methodResult.fit_data;
    return shapes[chartMode] ?? shapes['line'] ?? null;
  }, [methodResult, chartMode]);

  const chartData = chartShape?.data ?? null;
  const chartCitations = chartShape?.citations ?? [];
  const chartExplanation = chartShape?.explanation ?? null;

  const collapsedSummary = isModelConstruction
    ? `Model Construction${mcResult ? ` | ${mcResult.model_id}` : ''}`
    : methodResult
      ? `Method: ${methodResult.method} | R²: ${methodResult.r_squared?.toFixed(3) || '—'} | MAPE: ${methodResult.mape ? `${(methodResult.mape * 100).toFixed(1)}%` : '—'}`
      : `Forecast Method: ${selectedMethod}`;

  const aiContext = useMemo(() => ({
    metric: selectedMetric,
    method: selectedMethod,
    granularity,
    forecast_periods: forecastPeriods,
    r_squared: methodResult?.r_squared,
    mape: methodResult?.mape,
    model_name: methodResult?.model_name,
    // Actual forecast data — requestNarrative auto-hydrates from ctx.forecastRows,
    // but also include it here so the Analyze button payload is explicit
    forecast_data: ctx.forecastRows.length > 0 ? ctx.forecastRows : undefined,
  }), [selectedMethod, selectedMetric, granularity, forecastPeriods, methodResult, ctx.forecastRows]);

  const configBar = (
    <>
      {!isModelConstruction && (
        <div className="flex items-center gap-1.5">
          <span className="text-muted-foreground">Metric:</span>
          <Select value={selectedMetric} onValueChange={(v) => setSelectedMetric(v as ForecastMetric)}>
            <SelectTrigger className="h-6 w-[130px] text-[11px]"><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value="revenue">Revenue</SelectItem>
              <SelectItem value="ebitda">EBITDA</SelectItem>
              <SelectItem value="gross_profit">Gross Profit</SelectItem>
              <SelectItem value="total_opex">Total OpEx</SelectItem>
              <SelectItem value="free_cash_flow">Free Cash Flow</SelectItem>
              <SelectItem value="cogs">COGS</SelectItem>
            </SelectContent>
          </Select>
        </div>
      )}
      <div className="flex items-center gap-1.5">
        <span className="text-muted-foreground">Method:</span>
        <Select value={selectedMethod} onValueChange={(v) => setSelectedMethod(v as ForecastMethod)}>
          <SelectTrigger className="h-6 w-[160px] text-[11px]"><SelectValue /></SelectTrigger>
          <SelectContent>
            <SelectItem value="model_construction">Custom Model</SelectItem>
            <SelectItem value="auto">Auto (best fit)</SelectItem>
            <SelectItem value="liquidity">Liquidity Model</SelectItem>
            <SelectItem value="advanced_regression">Advanced Regression</SelectItem>
            <SelectItem value="driver_based">Driver-based</SelectItem>
            <SelectItem value="seasonal">Seasonal</SelectItem>
            <SelectItem value="monte_carlo">Monte Carlo</SelectItem>
            <SelectItem value="regression">Regression</SelectItem>
            <SelectItem value="budget_pct">Budget-based</SelectItem>
            <SelectItem value="growth_rate">Growth Rate</SelectItem>
          </SelectContent>
        </Select>
      </div>
      {!isModelConstruction && (
        <div className="flex items-center gap-1.5">
          <span className="text-muted-foreground">Chart:</span>
          <Select value={chartMode} onValueChange={(v) => setChartMode(v as ChartMode)}>
            <SelectTrigger className="h-6 w-[130px] text-[11px]"><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value="branched_line">Scenario Branches</SelectItem>
              <SelectItem value="regression_line">Regression Fit</SelectItem>
              <SelectItem value="line">Line</SelectItem>
              <SelectItem value="stacked_bar">Stacked Bar</SelectItem>
              <SelectItem value="bar_comparison">Grouped Bar</SelectItem>
              <SelectItem value="monte_carlo_fan">MC Fan</SelectItem>
              <SelectItem value="treemap">Treemap</SelectItem>
            </SelectContent>
          </Select>
        </div>
      )}
      {!isModelConstruction && (
        <div className="flex items-center gap-1.5">
          <span className="text-muted-foreground">View:</span>
          <Select value={granularity} onValueChange={(v) => setGranularity(v as ForecastGranularity)}>
            <SelectTrigger className="h-6 w-[90px] text-[11px]"><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value="monthly">Monthly</SelectItem>
              <SelectItem value="quarterly">Quarterly</SelectItem>
              <SelectItem value="annual">Annual</SelectItem>
            </SelectContent>
          </Select>
        </div>
      )}
      <div className="flex items-center gap-1.5">
        <span className="text-muted-foreground">Periods:</span>
        <Select value={String(forecastPeriods)} onValueChange={(v) => setForecastPeriods(Number(v))}>
          <SelectTrigger className="h-6 w-[55px] text-[11px]"><SelectValue /></SelectTrigger>
          <SelectContent>
            <SelectItem value="3">3</SelectItem>
            <SelectItem value="6">6</SelectItem>
            <SelectItem value="12">12</SelectItem>
            <SelectItem value="18">18</SelectItem>
            <SelectItem value="24">24</SelectItem>
            <SelectItem value="36">36</SelectItem>
          </SelectContent>
        </Select>
      </div>
      {!readOnly && !isModelConstruction && (
        <Button variant="outline" size="sm" className="h-6 text-[11px] gap-1 ml-auto" onClick={handleBuildForecast} disabled={loading}>
          {loading ? <Loader2 className="h-3 w-3 animate-spin" /> : <Play className="h-3 w-3" />}
          Build
        </Button>
      )}
    </>
  );

  // Method comparison cards (standard mode only)
  const methodCards = !isModelConstruction && methodResult?.alternatives ? (
    <div className="grid grid-cols-3 gap-1.5 mb-3">
      {[
        { method: methodResult.method, r_squared: methodResult.r_squared, mape: methodResult.mape, active: true },
        ...(methodResult.alternatives || []).map(a => ({ ...a, active: false })),
      ].map(m => (
        <div key={m.method} className={`rounded-md border p-2 text-center ${m.active ? 'border-primary bg-primary/5' : 'border-border/50 bg-muted/30'}`}>
          <div className="text-[10px] text-muted-foreground uppercase font-mono">{m.method}</div>
          <div className="text-sm font-semibold tabular-nums">R² {m.r_squared?.toFixed(3) || '—'}</div>
          {m.mape != null && <div className="text-[10px] text-muted-foreground">MAPE: {(m.mape * 100).toFixed(1)}%</div>}
        </div>
      ))}
    </div>
  ) : null;

  return (
    <MemoSectionWrapper
      sectionType="forecast_method"
      title="Forecast Method"
      collapsedSummary={collapsedSummary}
      configContent={configBar}
      narrativeCards={narrativeCards}
      onNarrativeCardsChange={setNarrativeCards}
      aiDataContext={aiContext}
      showAnalyze={false}
      onDelete={onDelete}
      readOnly={readOnly}
    >
      {isModelConstruction ? (
        <>
          {/* NL Prompt input */}
          {!readOnly && (
            <div className="flex items-center gap-2 mb-3">
              <div className="relative flex-1">
                <MessageSquare className="absolute left-2 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground" />
                <Input
                  className="h-8 pl-7 text-sm"
                  placeholder="Build me a 24-month forecast assuming Series A closes Q2..."
                  value={mcPrompt}
                  onChange={e => setMcPrompt(e.target.value)}
                  onKeyDown={e => e.key === 'Enter' && handleModelConstruction()}
                  disabled={loading}
                />
              </div>
              <Button
                variant="outline"
                size="sm"
                className="h-8 text-[11px] gap-1"
                onClick={() => handleModelConstruction()}
                disabled={loading || !mcPrompt.trim()}
              >
                {loading ? <Loader2 className="h-3 w-3 animate-spin" /> : <Play className="h-3 w-3" />}
                Construct
              </Button>
            </div>
          )}

          {/* CascadeModelView — branched line + stacked bar + narrative */}
          <CascadeModelView result={mcResult} metric={selectedMetric} />

          {/* ModelSpecEditor — event chain toggles + re-prompt */}
          {mcResult?.event_chain && (
            <div className="mt-4 pt-3 border-t border-border/30">
              <ModelSpecEditor
                eventChain={mcResult.event_chain}
                onToggleEvent={handleToggleEvent}
                onChangeProbability={handleChangeProbability}
                onRePrompt={handleRePrompt}
                onRun={handleReRun}
                loading={loading}
                readOnly={readOnly}
              />
            </div>
          )}
        </>
      ) : (
        <>
          {methodCards}
          <div className="w-full">
            {chartData ? (
              <TableauLevelCharts data={chartData} type={chartMode} title="" width="100%" height={280} citations={chartCitations} />
            ) : (
              <div className="flex items-center justify-center h-[200px] text-xs text-muted-foreground">
                Build a forecast to see method fit and accuracy
              </div>
            )}
          </div>
          {chartExplanation && (
            <p className="text-[11px] text-muted-foreground mt-2 leading-relaxed">{chartExplanation}</p>
          )}
          {/* Ripple path cascade — shows how driver changes cascade through P&L */}
          {methodResult?.ripple_paths && methodResult.ripple_paths.length > 0 && (
            <div className="mt-3 pt-2 border-t border-border/30">
              <div className="text-[10px] uppercase font-mono text-muted-foreground mb-1.5">Cascade Path</div>
              <div className="flex items-center gap-1 flex-wrap text-[11px]">
                {(() => {
                  // Build ordered cascade chain from ripple_paths
                  const paths = methodResult.ripple_paths!;
                  const nodes = new Set<string>();
                  paths.forEach(p => { nodes.add(p.from); nodes.add(p.to); });
                  // Order: Revenue → COGS → GP → OpEx → EBITDA → FCF → Cash → Runway
                  const order = ['revenue', 'cogs', 'gross_profit', 'total_opex', 'ebitda', 'free_cash_flow', 'cash_balance', 'runway_months'];
                  const ordered = order.filter(n => nodes.has(n));
                  const labels: Record<string, string> = {
                    revenue: 'Revenue', cogs: 'COGS', gross_profit: 'GP',
                    total_opex: 'OpEx', ebitda: 'EBITDA', free_cash_flow: 'FCF',
                    cash_balance: 'Cash', runway_months: 'Runway',
                  };
                  return ordered.map((node, i) => {
                    const impact = paths.find(p => p.to === node)?.impact;
                    const impactStr = impact != null ? ` ${impact >= 0 ? '+' : ''}${(impact * 100).toFixed(1)}%` : '';
                    return (
                      <React.Fragment key={node}>
                        {i > 0 && <span className="text-muted-foreground/50">→</span>}
                        <span className={`px-1.5 py-0.5 rounded ${impact != null && impact >= 0 ? 'bg-emerald-500/10 text-emerald-700 dark:text-emerald-400' : impact != null ? 'bg-red-500/10 text-red-700 dark:text-red-400' : 'bg-muted'}`}>
                          {labels[node] || node}{impactStr}
                        </span>
                      </React.Fragment>
                    );
                  });
                })()}
              </div>
            </div>
          )}
        </>
      )}
    </MemoSectionWrapper>
  );
}
