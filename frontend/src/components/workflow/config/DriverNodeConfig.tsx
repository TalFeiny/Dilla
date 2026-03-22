'use client';

import { useCallback, useMemo, useState } from 'react';
import { nanoid } from 'nanoid';
import {
  TrendingUp,
  Plus,
  Zap,
  Globe,
  Info,
} from 'lucide-react';
import { useWorkflowStore } from '@/lib/workflow/store';
import type { WorkflowNodeData } from '@/lib/workflow/types';
import type { NodeAssumption } from '@/lib/workflow/assumptions';
import {
  composeAssumptionCurve,
  computeExposure,
  formatExposure,
  formatCompact,
  ASSUMPTION_TEMPLATES,
  CATEGORY_COLORS,
} from '@/lib/workflow/assumptions';
import { AssumptionRow } from './AssumptionRow';
import { MiniCurveChart } from './MiniCurveChart';

// ── Driver ID → actuals category mapping ────────────────────────────────────

const DRIVER_TO_ACTUALS: Record<string, string> = {
  revenue_growth: 'revenue',
  revenue_override: 'revenue',
  gross_margin: 'gross_profit',
  churn_rate: 'revenue',
  nrr: 'revenue',
  pricing_change: 'revenue',
  new_customer_growth: 'revenue',
  avg_contract_value: 'revenue',
  rd_pct: 'opex_rd',
  sm_pct: 'opex_sm',
  ga_pct: 'opex_ga',
  headcount_change: 'headcount',
  payroll_cost_per_head: 'headcount',
  burn_rate: 'net_burn',
  cash_override: 'cash_balance',
  funding_injection: 'cash_balance',
  capex: 'capex',
  debt_service: 'debt_service',
  tax_rate: 'ebitda',
  working_capital_days: 'cash_balance',
};

const DRIVER_UNITS: Record<string, string> = {
  percent: '%',
  currency: '$',
  headcount: 'hd',
  months: 'mo',
  days: 'd',
  multiplier: 'x',
  ratio: 'x',
};

// ── Main component ──────────────────────────────────────────────────────────

interface DriverNodeConfigProps {
  nodeId: string;
  data: WorkflowNodeData;
}

export function DriverNodeConfig({ nodeId, data }: DriverNodeConfigProps) {
  const updateNodeData = useWorkflowStore((s) => s.updateNodeData);
  const companyData = useWorkflowStore((s) => s.companyData);
  const companyDataLoading = useWorkflowStore((s) => s.companyDataLoading);

  const [showTemplates, setShowTemplates] = useState(false);
  const [analyzingId, setAnalyzingId] = useState<string | null>(null);

  // ── Resolve actuals for this driver ───────────────────────────────────────

  const chipId = data.chipId || data.label?.toLowerCase().replace(/\s+/g, '_') || '';
  const actualsKey = data.actualsKey || DRIVER_TO_ACTUALS[chipId] || 'revenue';

  const actualsData = useMemo(() => {
    if (!companyData?.timeSeries?.[actualsKey]) return null;
    const ts = companyData.timeSeries[actualsKey];
    const sorted = Object.entries(ts)
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([period, amount]) => ({ period, amount: amount as number }));
    return sorted;
  }, [companyData, actualsKey]);

  const latestValue = companyData?.latest?.[actualsKey] ?? 0;
  const prevValue = actualsData && actualsData.length >= 2
    ? actualsData[actualsData.length - 2]?.amount ?? 0
    : 0;
  const trendPct = prevValue !== 0 ? ((latestValue - prevValue) / Math.abs(prevValue)) * 100 : 0;

  // ── Sparkline data (last 12 months) ───────────────────────────────────────

  const sparklineValues = useMemo(() => {
    if (!actualsData) return [];
    return actualsData.slice(-12).map((d) => d.amount);
  }, [actualsData]);

  // ── Slider range from driver registry heuristics ──────────────────────────

  const sliderConfig = useMemo(() => {
    // Sensible defaults per driver type
    const unit = data.params?.unit || 'percent';
    if (unit === 'percent' || chipId.includes('growth') || chipId.includes('margin') || chipId.includes('rate')) {
      return { min: -50, max: 100, step: 1, format: (v: number) => `${v}%` };
    }
    if (unit === 'currency' || chipId.includes('override') || chipId.includes('injection')) {
      const base = Math.max(Math.abs(latestValue), 10000);
      return { min: -base * 2, max: base * 5, step: Math.round(base / 20), format: (v: number) => formatCompact(v) };
    }
    return { min: -100, max: 200, step: 1, format: (v: number) => `${v}` };
  }, [data.params?.unit, chipId, latestValue]);

  // ── Base adjustment (slider) ──────────────────────────────────────────────

  const baseAdjustment = data.baseAdjustment ?? Math.round(trendPct);

  const handleSliderChange = useCallback((val: number) => {
    updateNodeData(nodeId, { baseAdjustment: val });
  }, [nodeId, updateNodeData]);

  // ── Assumptions CRUD ──────────────────────────────────────────────────────

  const assumptions: NodeAssumption[] = (data.assumptions as NodeAssumption[]) || [];

  const addAssumption = useCallback((template?: Partial<NodeAssumption>) => {
    const newA: NodeAssumption = {
      id: nanoid(8),
      description: '',
      probability: 0.5,
      magnitude: 0,
      magnitudeUnit: 'absolute',
      shape: 'step',
      source: template ? 'template' : 'user',
      category: 'growth',
      ...template,
    };
    updateNodeData(nodeId, { assumptions: [...assumptions, newA] });
  }, [nodeId, assumptions, updateNodeData]);

  const updateAssumption = useCallback((id: string, patch: Partial<NodeAssumption>) => {
    updateNodeData(nodeId, {
      assumptions: assumptions.map((a) => a.id === id ? { ...a, ...patch } : a),
    });
  }, [nodeId, assumptions, updateNodeData]);

  const deleteAssumption = useCallback((id: string) => {
    updateNodeData(nodeId, {
      assumptions: assumptions.filter((a) => a.id !== id),
    });
  }, [nodeId, assumptions, updateNodeData]);

  // ── Analyze assumption (calls backend) ────────────────────────────────────

  const analyzeAssumption = useCallback(async (id: string) => {
    const a = assumptions.find((x) => x.id === id);
    if (!a || !a.description.trim()) return;

    const companyId = useWorkflowStore.getState().companyId;
    if (!companyId) return;

    setAnalyzingId(id);
    try {
      const isMacro = a.category === 'market' || a.source === 'macro';
      const res = await fetch('/api/fpa/analyze-assumption', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          company_id: companyId,
          assumption_text: a.description,
          metric: chipId || actualsKey,
          mode: isMacro ? 'macro' : 'business',
        }),
      });

      if (!res.ok) throw new Error('Analysis failed');
      const result = await res.json();

      updateAssumption(id, {
        probability: result.suggested_probability ?? a.probability,
        magnitude: result.suggested_magnitude ?? a.magnitude,
        magnitudeUnit: 'percent',
        source: result.mode === 'macro' ? 'macro' : 'ai',
        aiAnalysis: {
          factors: result.factors || [],
          driverAdjustments: result.driver_adjustments || [],
          reasoning: result.reasoning || '',
        },
      });
    } catch (e) {
      console.error('[DriverNodeConfig] Analysis failed:', e);
    } finally {
      setAnalyzingId(null);
    }
  }, [assumptions, chipId, actualsKey, updateAssumption]);

  // ── Curve composition ─────────────────────────────────────────────────────

  const curveData = useMemo(() => {
    const growth = (baseAdjustment || 0) / 100 / 12; // annual → monthly
    return composeAssumptionCurve(latestValue, growth, assumptions, 12);
  }, [latestValue, baseAdjustment, assumptions]);

  const exposure = useMemo(() => {
    return computeExposure(assumptions, latestValue);
  }, [assumptions, latestValue]);

  // ── Applicable templates ──────────────────────────────────────────────────

  const driverLevel = data.chipDef?.domain || chipId.split('_')[0] || 'revenue';
  const templates = useMemo(() => {
    return ASSUMPTION_TEMPLATES.filter((t) =>
      t.applicableLevels.some((l) => driverLevel.includes(l) || actualsKey.includes(l))
    );
  }, [driverLevel, actualsKey]);

  // ── Driver ripple chain — mirrors backend driver_registry.py ──────────────

  const rippleChain = useMemo(() => {
    const DRIVER_RIPPLE: Record<string, string[]> = {
      revenue_growth:       ['Gross Profit', 'EBITDA', 'Cash', 'Runway'],
      revenue_override:     ['Gross Profit', 'EBITDA', 'Cash', 'Runway'],
      gross_margin:         ['Gross Profit', 'EBITDA', 'Cash', 'Runway'],
      churn_rate:           ['Net Revenue', 'Gross Profit', 'EBITDA', 'Cash', 'Runway'],
      nrr:                  ['Net Revenue', 'Gross Profit', 'EBITDA', 'Cash', 'Runway'],
      pricing_change:       ['Revenue', 'Gross Profit', 'EBITDA', 'Cash'],
      new_customer_growth:  ['Revenue', 'Gross Profit', 'EBITDA', 'Cash'],
      avg_contract_value:   ['Revenue', 'Gross Profit', 'EBITDA', 'Cash'],
      rd_pct:               ['Total OpEx', 'EBITDA', 'FCF', 'Cash', 'Runway'],
      sm_pct:               ['Total OpEx', 'EBITDA', 'FCF', 'Cash', 'Runway'],
      ga_pct:               ['Total OpEx', 'EBITDA', 'FCF', 'Cash', 'Runway'],
      cac:                  ['S&M Spend', 'Total OpEx', 'EBITDA', 'Cash'],
      sales_cycle:          ['Revenue Timing', 'Cash Timing'],
      headcount_change:     ['Burn Rate', 'Total OpEx', 'EBITDA', 'Cash', 'Runway'],
      payroll_cost_per_head:['Burn Rate', 'Total OpEx', 'EBITDA', 'Cash', 'Runway'],
      hiring_plan:          ['Burn Rate', 'Total OpEx', 'EBITDA', 'Cash', 'Runway'],
      funding_injection:    ['Cash', 'Runway', 'Dilution', 'Ownership'],
      burn_rate:            ['Cash', 'Runway'],
      cash_override:        ['Runway'],
      capex:                ['FCF', 'Cash', 'Runway'],
      debt_service:         ['FCF', 'Cash', 'Runway'],
      interest_rate:        ['Debt Service', 'FCF', 'Cash'],
      tax_rate:             ['Net Income', 'Cash'],
      working_capital_days: ['Cash Timing', 'Working Capital', 'Cash'],
      one_time_costs:       ['EBITDA', 'Cash', 'Runway'],
    };
    return DRIVER_RIPPLE[chipId] || ['EBITDA', 'Cash', 'Runway'];
  }, [chipId]);

  return (
    <div className="space-y-4">
      {/* ── ACTUALS SECTION ──────────────────────────────────────────────── */}
      <Section label="ACTUALS" icon={<TrendingUp className="w-3.5 h-3.5" />}>
        {companyDataLoading ? (
          <div className="h-14 flex items-center justify-center">
            <div className="w-4 h-4 border-2 border-gray-600 border-t-gray-300 rounded-full animate-spin" />
          </div>
        ) : !companyData ? (
          <div className="text-xs text-gray-500 py-2">Select a company to see actuals</div>
        ) : (
          <div className="space-y-2">
            {/* Sparkline */}
            {sparklineValues.length > 1 && (
              <div className="flex items-center gap-3">
                <div className="flex-1">
                  <MiniSparkline values={sparklineValues} />
                </div>
                <div className="text-right">
                  <div className="text-sm font-mono text-gray-200">{formatCompact(latestValue)}</div>
                  <div className={`text-xs font-medium ${trendPct >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                    {trendPct >= 0 ? '+' : ''}{trendPct.toFixed(1)}%
                  </div>
                </div>
              </div>
            )}
            {sparklineValues.length <= 1 && (
              <div className="flex items-center justify-between py-1">
                <span className="text-xs text-gray-500">Latest</span>
                <span className="text-sm font-mono text-gray-200">{formatCompact(latestValue)}</span>
              </div>
            )}
            {/* Period range */}
            {companyData.periods.length > 0 && (
              <div className="text-[10px] text-gray-600">
                {companyData.periods[0]} to {companyData.periods[companyData.periods.length - 1]}
                {' · '}{companyData.periods.length} periods
              </div>
            )}
          </div>
        )}
      </Section>

      {/* ── BASE ADJUSTMENT (deterministic slider) ───────────────────────── */}
      <Section label="BASE TRAJECTORY" hint="Set the baseline growth rate for this metric">
        <div className="space-y-2">
          <div className="flex items-center gap-3">
            <input
              type="range"
              min={sliderConfig.min}
              max={sliderConfig.max}
              step={sliderConfig.step}
              value={baseAdjustment}
              onChange={(e) => handleSliderChange(parseFloat(e.target.value))}
              className="flex-1 h-2 appearance-none bg-gray-700 rounded-full cursor-pointer
                [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-4 [&::-webkit-slider-thumb]:h-4
                [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:bg-purple-400 [&::-webkit-slider-thumb]:shadow-md
                [&::-webkit-slider-thumb]:cursor-pointer [&::-webkit-slider-thumb]:border-2 [&::-webkit-slider-thumb]:border-gray-900"
            />
            <span className="text-sm font-mono text-purple-300 w-16 text-right">
              {sliderConfig.format(baseAdjustment)}
            </span>
          </div>
          <div className="flex justify-between text-[10px] text-gray-600">
            <span>{sliderConfig.format(sliderConfig.min)}</span>
            <button
              onClick={() => handleSliderChange(Math.round(trendPct))}
              className="text-gray-500 hover:text-purple-400 transition-colors"
              title="Reset to current trend"
            >
              auto: {trendPct.toFixed(1)}%
            </button>
            <span>{sliderConfig.format(sliderConfig.max)}</span>
          </div>
        </div>
      </Section>

      {/* ── ASSUMPTIONS (NL + probability) ───────────────────────────────── */}
      <Section
        label="ASSUMPTIONS"
        hint="Describe what you think will happen"
        action={
          <div className="flex items-center gap-1">
            <button
              onClick={() => setShowTemplates(!showTemplates)}
              className="text-[10px] text-gray-500 hover:text-gray-300 flex items-center gap-0.5"
            >
              <Zap className="w-3 h-3" />
              Templates
            </button>
          </div>
        }
      >
        {/* Template quick-add */}
        {showTemplates && templates.length > 0 && (
          <div className="mb-3 p-2 bg-gray-800/80 border border-gray-700/50 rounded-lg">
            <div className="text-[10px] text-gray-500 mb-1.5 uppercase tracking-wide">Quick add</div>
            <div className="flex flex-wrap gap-1.5">
              {templates.map((t) => (
                <button
                  key={t.label}
                  onClick={() => {
                    addAssumption({ ...t.defaults, id: nanoid(8) });
                    setShowTemplates(false);
                  }}
                  className="px-2 py-1 rounded text-[11px] bg-gray-700/50 text-gray-300
                    hover:bg-gray-600/50 transition-colors border border-gray-600/30"
                  style={{ borderColor: CATEGORY_COLORS[t.category || 'operational'] + '40' }}
                >
                  {t.label}
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Assumption list */}
        <div className="space-y-2">
          {assumptions.map((a) => (
            <AssumptionRow
              key={a.id}
              assumption={a}
              baselineValue={latestValue}
              onUpdate={updateAssumption}
              onDelete={deleteAssumption}
              onAnalyze={analyzeAssumption}
              analyzing={analyzingId === a.id}
            />
          ))}
        </div>

        {/* Add assumption button */}
        <button
          onClick={() => addAssumption()}
          className="w-full mt-2 py-2 border border-dashed border-gray-700 rounded-lg
            text-xs text-gray-500 hover:text-gray-300 hover:border-gray-500
            flex items-center justify-center gap-1.5 transition-colors"
        >
          <Plus className="w-3.5 h-3.5" />
          Add assumption
        </button>

        {/* Add macro event */}
        <button
          onClick={() => addAssumption({ source: 'macro', category: 'market', description: '', magnitudeUnit: 'percent' })}
          className="w-full mt-1 py-1.5 rounded-lg text-[11px] text-gray-600 hover:text-indigo-400
            flex items-center justify-center gap-1 transition-colors"
        >
          <Globe className="w-3 h-3" />
          Add macro event
        </button>
      </Section>

      {/* ── NET EXPOSURE ─────────────────────────────────────────────────── */}
      {assumptions.length > 0 && (
        <div className="flex items-center justify-between px-1 py-2 border-t border-b border-gray-800">
          <span className="text-[10px] text-gray-500 uppercase tracking-wide">Net Exposure</span>
          <div className="flex items-center gap-3">
            {exposure.upside > 0 && (
              <span className="text-xs text-emerald-400 font-mono">{formatExposure(exposure.upside)}</span>
            )}
            {exposure.downside < 0 && (
              <span className="text-xs text-red-400 font-mono">{formatExposure(exposure.downside)}</span>
            )}
            <span className={`text-sm font-mono font-medium ${
              exposure.netMonthly >= 0 ? 'text-emerald-400' : 'text-red-400'
            }`}>
              {formatExposure(exposure.netMonthly)}
            </span>
          </div>
        </div>
      )}

      {/* ── CURVE PREVIEW ────────────────────────────────────────────────── */}
      <Section label="FORECAST CURVE">
        <MiniCurveChart data={curveData} />
        {curveData.length > 0 && (
          <div className="flex justify-between text-[10px] text-gray-600 mt-1">
            <span>
              Baseline: {formatCompact(curveData[0].baseline)} → {formatCompact(curveData[curveData.length - 1].baseline)}
            </span>
            <span className={curveData[curveData.length - 1].delta >= 0 ? 'text-emerald-500' : 'text-red-500'}>
              Scenario: {formatCompact(curveData[curveData.length - 1].scenario)}
            </span>
          </div>
        )}
      </Section>

      {/* ── RIPPLE CHAIN ─────────────────────────────────────────────────── */}
      <Section label="RIPPLE" hint="How changes cascade through the model">
        <div className="flex items-center gap-1 flex-wrap text-xs">
          {rippleChain.map((step, i) => (
            <span key={i} className="flex items-center gap-1">
              <span className={i === 0 ? 'text-purple-400 font-medium' : 'text-gray-400'}>
                {step}
              </span>
              {i < rippleChain.length - 1 && (
                <span className="text-gray-600">→</span>
              )}
            </span>
          ))}
        </div>
      </Section>
    </div>
  );
}

// ── Section wrapper ─────────────────────────────────────────────────────────

function Section({
  label,
  hint,
  icon,
  action,
  children,
}: {
  label: string;
  hint?: string;
  icon?: React.ReactNode;
  action?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <div>
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-1.5">
          {icon}
          <span className="text-[10px] font-medium text-gray-500 uppercase tracking-wider">{label}</span>
          {hint && (
            <span className="group relative">
              <Info className="w-3 h-3 text-gray-600 cursor-help" />
              <span className="absolute left-0 bottom-full mb-1 hidden group-hover:block
                bg-gray-800 text-gray-300 text-[10px] px-2 py-1 rounded shadow-lg whitespace-nowrap z-50">
                {hint}
              </span>
            </span>
          )}
        </div>
        {action}
      </div>
      {children}
    </div>
  );
}

// ── Inline SVG sparkline (reuses NAVCard pattern) ───────────────────────────

function MiniSparkline({ values }: { values: number[] }) {
  if (values.length < 2) return null;

  const max = Math.max(...values);
  const min = Math.min(...values);
  const range = max - min || 1;
  const w = 120;
  const h = 28;

  const points = values
    .map((v, i) => {
      const x = (i / (values.length - 1)) * w;
      const y = h - ((v - min) / range) * (h - 4) - 2;
      return `${x},${y}`;
    })
    .join(' ');

  const isUp = values[values.length - 1] > values[0];
  const color = isUp ? 'rgb(34,197,94)' : 'rgb(239,68,68)';

  return (
    <svg width="100%" height={h} viewBox={`0 0 ${w} ${h}`} className="overflow-visible">
      <polyline
        points={points}
        fill="none"
        stroke={color}
        strokeWidth={1.5}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <circle
        cx={w}
        cy={parseFloat(points.split(' ').pop()?.split(',')[1] || '0')}
        r={2.5}
        fill={color}
      />
    </svg>
  );
}

