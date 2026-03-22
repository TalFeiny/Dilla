'use client';

import { useCallback, useState } from 'react';
import { Trash2, Sparkles, ChevronDown, ChevronUp } from 'lucide-react';
import type { NodeAssumption, AssumptionShape, MagnitudeUnit } from '@/lib/workflow/assumptions';
import {
  formatMagnitude,
  formatExposure,
  CATEGORY_COLORS,
  SHAPE_LABELS,
  SHAPE_DESCRIPTIONS,
} from '@/lib/workflow/assumptions';

interface AssumptionRowProps {
  assumption: NodeAssumption;
  baselineValue?: number;
  onUpdate: (id: string, patch: Partial<NodeAssumption>) => void;
  onDelete: (id: string) => void;
  onAnalyze: (id: string) => void;
  analyzing?: boolean;
}

export function AssumptionRow({
  assumption,
  baselineValue,
  onUpdate,
  onDelete,
  onAnalyze,
  analyzing,
}: AssumptionRowProps) {
  const [expanded, setExpanded] = useState(false);
  const a = assumption;

  // Compute weighted exposure
  let absMag: number;
  if (a.magnitudeUnit === 'percent' && baselineValue) {
    absMag = baselineValue * (a.magnitude / 100);
  } else {
    absMag = a.magnitude;
  }
  const exposure = a.probability * absMag;
  const isPositive = exposure >= 0;
  const catColor = CATEGORY_COLORS[a.category || 'operational'] || '#6b7280';

  return (
    <div className="bg-gray-800/50 border border-gray-700/50 rounded-lg overflow-hidden">
      {/* Category accent */}
      <div className="h-0.5" style={{ backgroundColor: catColor }} />

      {/* Main row — always visible */}
      <div className="px-3 py-2.5">
        {/* Description */}
        <div className="flex items-start gap-2 mb-2">
          <input
            type="text"
            value={a.description}
            onChange={(e) => onUpdate(a.id, { description: e.target.value })}
            placeholder="Describe what happens..."
            className="flex-1 bg-transparent text-sm text-gray-200 placeholder:text-gray-500 outline-none"
          />
          <button
            onClick={() => setExpanded(!expanded)}
            className="text-gray-500 hover:text-gray-300 p-0.5"
            title={expanded ? 'Collapse' : 'Expand details'}
          >
            {expanded ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
          </button>
        </div>

        {/* Probability slider — the main control */}
        <div className="flex items-center gap-3 mb-1.5">
          <span className="text-[10px] text-gray-500 w-8 uppercase tracking-wide">Prob</span>
          <input
            type="range"
            min={0}
            max={100}
            value={Math.round(a.probability * 100)}
            onChange={(e) => onUpdate(a.id, { probability: parseInt(e.target.value, 10) / 100 })}
            className="flex-1 h-1.5 appearance-none bg-gray-700 rounded-full cursor-pointer
              [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-3.5 [&::-webkit-slider-thumb]:h-3.5
              [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:bg-white [&::-webkit-slider-thumb]:shadow-md
              [&::-webkit-slider-thumb]:cursor-pointer"
          />
          <span className="text-sm font-mono text-gray-300 w-10 text-right">
            {Math.round(a.probability * 100)}%
          </span>
        </div>

        {/* Magnitude + Exposure summary */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="text-xs font-mono text-gray-400">
              {formatMagnitude(a.magnitude, a.magnitudeUnit)}
            </span>
            <span className="text-[10px] text-gray-600">|</span>
            <span className="text-xs text-gray-500">{SHAPE_LABELS[a.shape]}</span>
          </div>
          <span className={`text-xs font-medium font-mono ${isPositive ? 'text-emerald-400' : 'text-red-400'}`}>
            {formatExposure(exposure)}
          </span>
        </div>
      </div>

      {/* Expanded details */}
      {expanded && (
        <div className="px-3 py-2.5 border-t border-gray-700/50 space-y-2.5">
          {/* Magnitude input */}
          <div className="flex items-center gap-2">
            <span className="text-[10px] text-gray-500 w-16 uppercase tracking-wide">Impact</span>
            <input
              type="number"
              value={a.magnitude}
              onChange={(e) => onUpdate(a.id, { magnitude: parseFloat(e.target.value) || 0 })}
              className="flex-1 bg-gray-900 border border-gray-700 rounded px-2 py-1 text-sm text-gray-200 font-mono"
            />
            <select
              value={a.magnitudeUnit}
              onChange={(e) => onUpdate(a.id, { magnitudeUnit: e.target.value as MagnitudeUnit })}
              className="bg-gray-900 border border-gray-700 rounded px-2 py-1 text-xs text-gray-300"
            >
              <option value="absolute">$ (absolute)</option>
              <option value="percent">% (percent)</option>
              <option value="per_month">$/mo (per month)</option>
            </select>
          </div>

          {/* Shape selector */}
          <div className="flex items-center gap-2">
            <span className="text-[10px] text-gray-500 w-16 uppercase tracking-wide">Shape</span>
            <div className="flex-1 grid grid-cols-4 gap-1">
              {(['step', 'ramp', 'decay', 'pulse'] as AssumptionShape[]).map((s) => (
                <button
                  key={s}
                  onClick={() => onUpdate(a.id, { shape: s })}
                  title={SHAPE_DESCRIPTIONS[s]}
                  className={`px-2 py-1 rounded text-[10px] font-medium transition-colors ${
                    a.shape === s
                      ? 'bg-indigo-500/20 text-indigo-300 border border-indigo-500/40'
                      : 'bg-gray-900 text-gray-500 border border-gray-700 hover:text-gray-300'
                  }`}
                >
                  {/* Mini shape icon */}
                  <ShapeMini shape={s} active={a.shape === s} />
                  <span className="mt-0.5 block">{SHAPE_LABELS[s].split(' ')[0]}</span>
                </button>
              ))}
            </div>
          </div>

          {/* Timing */}
          <div className="flex items-center gap-2">
            <span className="text-[10px] text-gray-500 w-16 uppercase tracking-wide">When</span>
            <input
              type="text"
              value={a.timing || ''}
              onChange={(e) => onUpdate(a.id, { timing: e.target.value || undefined })}
              placeholder="e.g. 2026-Q3 or month_3"
              className="flex-1 bg-gray-900 border border-gray-700 rounded px-2 py-1 text-sm text-gray-300 placeholder:text-gray-600"
            />
          </div>

          {/* Duration (for ramp/decay/pulse) */}
          {a.shape !== 'step' && (
            <div className="flex items-center gap-2">
              <span className="text-[10px] text-gray-500 w-16 uppercase tracking-wide">Duration</span>
              <input
                type="number"
                min={1}
                max={36}
                value={a.duration || 6}
                onChange={(e) => onUpdate(a.id, { duration: parseInt(e.target.value, 10) || 6 })}
                className="w-16 bg-gray-900 border border-gray-700 rounded px-2 py-1 text-sm text-gray-300 font-mono"
              />
              <span className="text-xs text-gray-500">months</span>
            </div>
          )}

          {/* Category */}
          <div className="flex items-center gap-2">
            <span className="text-[10px] text-gray-500 w-16 uppercase tracking-wide">Type</span>
            <div className="flex gap-1 flex-wrap">
              {(['growth', 'risk', 'cost', 'funding', 'market', 'operational'] as const).map((cat) => (
                <button
                  key={cat}
                  onClick={() => onUpdate(a.id, { category: cat })}
                  className={`px-2 py-0.5 rounded-full text-[10px] transition-colors ${
                    a.category === cat
                      ? 'text-white'
                      : 'text-gray-500 bg-gray-800 hover:text-gray-300'
                  }`}
                  style={a.category === cat ? { backgroundColor: CATEGORY_COLORS[cat] + '40', color: CATEGORY_COLORS[cat] } : {}}
                >
                  {cat}
                </button>
              ))}
            </div>
          </div>

          {/* AI analysis result */}
          {a.aiAnalysis && (
            <div className="bg-indigo-900/20 border border-indigo-500/20 rounded-lg px-3 py-2">
              <div className="text-[10px] text-indigo-400 font-medium mb-1 uppercase tracking-wide">AI Analysis</div>
              {a.aiAnalysis.reasoning && (
                <p className="text-xs text-gray-400 mb-1.5">{a.aiAnalysis.reasoning}</p>
              )}
              {a.aiAnalysis.factors?.slice(0, 3).map((f, i) => (
                <div key={i} className="flex items-center gap-2 text-[11px]">
                  <span className="text-gray-500">{f.order === 1 ? '1st' : f.order === 2 ? '2nd' : '3rd'}</span>
                  <span className="text-gray-300 flex-1">{f.name}</span>
                  <span className={f.magnitude >= 0 ? 'text-emerald-400' : 'text-red-400'}>
                    {f.magnitude >= 0 ? '+' : ''}{f.magnitude}%
                  </span>
                  <span className="text-gray-600 text-[10px]">{f.confidence}</span>
                </div>
              ))}
            </div>
          )}

          {/* Actions */}
          <div className="flex items-center justify-end gap-2 pt-1">
            <button
              onClick={() => onAnalyze(a.id)}
              disabled={analyzing || !a.description.trim()}
              className="flex items-center gap-1 px-2.5 py-1 rounded text-[11px] font-medium
                bg-indigo-500/10 text-indigo-400 hover:bg-indigo-500/20 disabled:opacity-40 disabled:cursor-not-allowed
                transition-colors"
            >
              <Sparkles className="w-3 h-3" />
              {analyzing ? 'Analyzing...' : 'Analyze'}
            </button>
            <button
              onClick={() => onDelete(a.id)}
              className="p-1 text-gray-600 hover:text-red-400 transition-colors"
              title="Remove assumption"
            >
              <Trash2 className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

// ── Tiny shape visualization ────────────────────────────────────────────────

function ShapeMini({ shape, active }: { shape: AssumptionShape; active: boolean }) {
  const color = active ? '#818cf8' : '#4b5563';
  const w = 28;
  const h = 12;

  const paths: Record<AssumptionShape, string> = {
    step:  `M 2 ${h} L 2 ${h} L ${w / 2} ${h} L ${w / 2} 2 L ${w - 2} 2`,
    ramp:  `M 2 ${h} L ${w - 2} 2`,
    decay: `M 2 2 Q ${w / 2} 2 ${w / 2} ${h / 2} Q ${w / 2} ${h} ${w - 2} ${h}`,
    pulse: `M 2 ${h} L 2 2 L ${w * 0.6} 2 L ${w * 0.6} ${h} L ${w - 2} ${h}`,
  };

  return (
    <svg width={w} height={h} className="mx-auto mb-0.5">
      <path d={paths[shape]} fill="none" stroke={color} strokeWidth={1.5} strokeLinecap="round" />
    </svg>
  );
}
