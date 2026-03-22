'use client';

import { useMemo } from 'react';
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
} from 'recharts';
import { formatCompact, type CurvePoint } from '@/lib/workflow/assumptions';

interface MiniCurveChartProps {
  data: CurvePoint[];
  height?: number;
}

function CustomTooltip({ active, payload, label }: any) {
  if (!active || !payload?.[0]) return null;
  const d = payload[0].payload as CurvePoint;
  const isUp = d.delta >= 0;
  return (
    <div className="bg-gray-900 border border-gray-700 rounded-lg px-3 py-2 text-xs shadow-xl">
      <div className="text-gray-400 mb-1">{label}</div>
      <div className="flex items-center gap-3">
        <span className="text-gray-500">Base: {formatCompact(d.baseline)}</span>
        <span className={isUp ? 'text-emerald-400' : 'text-red-400'}>
          Scenario: {formatCompact(d.scenario)}
        </span>
      </div>
      <div className={`mt-1 font-medium ${isUp ? 'text-emerald-400' : 'text-red-400'}`}>
        {d.delta >= 0 ? '+' : ''}{formatCompact(d.delta)}
      </div>
    </div>
  );
}

export function MiniCurveChart({ data, height = 140 }: MiniCurveChartProps) {
  const { yMin, yMax } = useMemo(() => {
    if (!data.length) return { yMin: 0, yMax: 100 };
    let min = Infinity;
    let max = -Infinity;
    for (const d of data) {
      min = Math.min(min, d.baseline, d.scenario, d.lo ?? d.scenario);
      max = Math.max(max, d.baseline, d.scenario, d.hi ?? d.scenario);
    }
    const pad = (max - min) * 0.1 || 100;
    return { yMin: min - pad, yMax: max + pad };
  }, [data]);

  if (!data.length) {
    return (
      <div className="h-[140px] flex items-center justify-center text-xs text-gray-500">
        Add assumptions to see the forecast curve
      </div>
    );
  }

  return (
    <ResponsiveContainer width="100%" height={height}>
      <AreaChart data={data} margin={{ top: 4, right: 4, bottom: 0, left: 4 }}>
        <defs>
          <linearGradient id="scenarioGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#10b981" stopOpacity={0.3} />
            <stop offset="100%" stopColor="#10b981" stopOpacity={0} />
          </linearGradient>
          <linearGradient id="bandGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#6366f1" stopOpacity={0.15} />
            <stop offset="100%" stopColor="#6366f1" stopOpacity={0.05} />
          </linearGradient>
        </defs>

        <XAxis
          dataKey="label"
          tick={{ fontSize: 10, fill: '#6b7280' }}
          axisLine={false}
          tickLine={false}
          interval="preserveStartEnd"
        />
        <YAxis
          domain={[yMin, yMax]}
          tick={{ fontSize: 10, fill: '#6b7280' }}
          axisLine={false}
          tickLine={false}
          tickFormatter={formatCompact}
          width={50}
        />
        <Tooltip content={<CustomTooltip />} />

        {/* Confidence band */}
        <Area
          type="monotone"
          dataKey="hi"
          stroke="none"
          fill="url(#bandGrad)"
          fillOpacity={1}
          isAnimationActive={false}
        />
        <Area
          type="monotone"
          dataKey="lo"
          stroke="none"
          fill="#111827"
          fillOpacity={1}
          isAnimationActive={false}
        />

        {/* Baseline trend (dashed) */}
        <Area
          type="monotone"
          dataKey="baseline"
          stroke="#6b7280"
          strokeWidth={1.5}
          strokeDasharray="4 4"
          fill="none"
          isAnimationActive={false}
        />

        {/* Scenario curve (solid) */}
        <Area
          type="monotone"
          dataKey="scenario"
          stroke="#10b981"
          strokeWidth={2}
          fill="url(#scenarioGrad)"
          fillOpacity={1}
          isAnimationActive={false}
        />

        {/* Today reference line */}
        <ReferenceLine x={data[0]?.label} stroke="#374151" strokeDasharray="2 2" />
      </AreaChart>
    </ResponsiveContainer>
  );
}
