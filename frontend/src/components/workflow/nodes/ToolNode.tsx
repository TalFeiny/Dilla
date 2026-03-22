'use client';

import { memo } from 'react';
import { Handle, Position, type NodeProps } from '@xyflow/react';
import type { WorkflowNodeData } from '@/lib/workflow/types';
import { Loader2, CheckCircle2, XCircle, Sliders } from 'lucide-react';

const STATUS_STYLES = {
  idle: 'border-gray-600/40',
  running: 'border-blue-500 shadow-blue-500/20 shadow-lg',
  done: 'border-emerald-500 shadow-emerald-500/10 shadow-md',
  error: 'border-red-500 shadow-red-500/10 shadow-md',
} as const;

const STATUS_ICON = {
  idle: null,
  running: <Loader2 className="w-3.5 h-3.5 text-blue-400 animate-spin" />,
  done: <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />,
  error: <XCircle className="w-3.5 h-3.5 text-red-400" />,
} as const;

/** Format a row path for display on the node face */
function shortRowLabel(path: string): string {
  const ROW_LABELS: Record<string, string> = {
    revenue: 'Rev', cogs: 'COGS', opex_rd: 'R&D', opex_sm: 'S&M',
    opex_ga: 'G&A', gross_profit: 'GP', ebitda: 'EBITDA',
  };
  const parts = path.split('/');
  const parent = ROW_LABELS[parts[0]] || parts[0];
  if (parts.length === 1) return parent;
  return `${parent}/${parts[1]}`;
}

/** Format a lever value compactly */
function shortLeverLabel(key: string, value: number): string {
  const LEVER_SHORT: Record<string, { label: string; unit: string }> = {
    revenue_growth: { label: 'Growth', unit: '%' },
    gross_margin: { label: 'Margin', unit: '%' },
    burn_rate: { label: 'Burn', unit: '$' },
    churn_rate: { label: 'Churn', unit: '%' },
    headcount_growth: { label: 'HC', unit: '%' },
    pricing_change: { label: 'Price', unit: '%' },
    cac: { label: 'CAC', unit: '$' },
    ltv: { label: 'LTV', unit: '$' },
    avg_salary: { label: 'Salary', unit: '$' },
    rd_pct: { label: 'R&D%', unit: '%' },
    sm_pct: { label: 'S&M%', unit: '%' },
    ga_pct: { label: 'G&A%', unit: '%' },
  };
  const def = LEVER_SHORT[key] || { label: key, unit: '' };
  if (def.unit === '%') return `${def.label} ${value > 0 ? '+' : ''}${value}%`;
  if (def.unit === '$') {
    const abs = Math.abs(value);
    const formatted = abs >= 1e6 ? `$${(value / 1e6).toFixed(1)}M` : abs >= 1e3 ? `$${(value / 1e3).toFixed(0)}k` : `$${value}`;
    return `${def.label} ${formatted}`;
  }
  return `${def.label} ${value}`;
}

function ToolNodeComponent({ data, selected }: NodeProps) {
  const d = data as unknown as WorkflowNodeData;
  const statusStyle = STATUS_STYLES[d.status] || STATUS_STYLES.idle;

  const targetRows = d.targetRows || [];
  const driverOverrides = d.driverOverrides || {};
  const hasTargeting = targetRows.length > 0;
  const hasLevers = Object.keys(driverOverrides).length > 0;
  return (
    <div
      className={`
        relative bg-gray-900 rounded-lg border-2 px-4 py-3 min-w-[180px] max-w-[260px]
        transition-all duration-200 cursor-pointer
        ${statusStyle}
        ${selected ? 'ring-2 ring-white/30' : ''}
      `}
    >
      {/* Accent bar */}
      <div className={`absolute top-0 left-3 right-3 h-0.5 rounded-b bg-${d.color}-500`} />

      {/* Header */}
      <div className="flex items-center gap-2">
        <span className={`text-${d.color}-400 text-sm`}>{d.icon}</span>
        <span className="text-sm font-medium text-gray-100 truncate flex-1">{d.label}</span>
        {STATUS_ICON[d.status]}
      </div>

      {/* Params preview */}
      {Object.keys(d.params).length > 0 && (
        <div className="mt-1.5 flex flex-wrap gap-1">
          {Object.entries(d.params).slice(0, 3).map(([key, val]) => (
            <span
              key={key}
              className="text-[10px] px-1.5 py-0.5 bg-gray-800 rounded text-gray-400 truncate max-w-[100px]"
            >
              {key}: {String(val)}
            </span>
          ))}
        </div>
      )}

      {/* Target rows pills */}
      {hasTargeting && (
        <div className="mt-1.5 flex flex-wrap gap-1">
          {targetRows.slice(0, 3).map((row) => (
            <span
              key={row}
              className="text-[9px] px-1.5 py-0.5 bg-blue-500/15 text-blue-300 rounded-full border border-blue-500/20"
            >
              {shortRowLabel(row)}
            </span>
          ))}
          {targetRows.length > 3 && (
            <span className="text-[9px] px-1 py-0.5 text-blue-400">+{targetRows.length - 3}</span>
          )}
        </div>
      )}

      {/* Lever overrides */}
      {hasLevers && (
        <div className="mt-1 flex flex-wrap gap-1">
          {Object.entries(driverOverrides).slice(0, 2).map(([key, val]) => (
            <span
              key={key}
              className="text-[9px] px-1.5 py-0.5 bg-purple-500/15 text-purple-300 rounded-full border border-purple-500/20 flex items-center gap-0.5"
            >
              <Sliders className="w-2 h-2" />
              {shortLeverLabel(key, val)}
            </span>
          ))}
          {Object.keys(driverOverrides).length > 2 && (
            <span className="text-[9px] px-1 py-0.5 text-purple-400">+{Object.keys(driverOverrides).length - 2}</span>
          )}
        </div>
      )}

      {/* Duration */}
      {d.durationMs !== undefined && (
        <div className="mt-1 text-[10px] text-gray-500">{(d.durationMs / 1000).toFixed(1)}s</div>
      )}

      {/* Handles */}
      <Handle
        type="target"
        position={Position.Left}
        className="!w-2.5 !h-2.5 !bg-gray-600 !border-2 !border-gray-800 hover:!bg-gray-400"
      />
      <Handle
        type="source"
        position={Position.Right}
        className="!w-2.5 !h-2.5 !bg-gray-600 !border-2 !border-gray-800 hover:!bg-gray-400"
      />
    </div>
  );
}

export const ToolNode = memo(ToolNodeComponent);
