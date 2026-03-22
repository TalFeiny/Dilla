'use client';

import { memo, useMemo } from 'react';
import { Handle, Position, type NodeProps } from '@xyflow/react';
import type { WorkflowNodeData } from '@/lib/workflow/types';
import type { PortDef } from '@/lib/workflow/port-types';
import { PORT_COLORS } from '@/lib/workflow/port-types';
import { useWorkflowStore } from '@/lib/workflow/store';
import { computeExposure, formatExposure } from '@/lib/workflow/assumptions';
import type { NodeAssumption } from '@/lib/workflow/assumptions';
import { resolveIcon } from './icon-resolver';

// ── Static color map (Tailwind-safe, no dynamic class construction) ─────────

const COLOR_MAP: Record<string, { accent: string; text: string; iconBg: string; handle: string }> = {
  emerald: { accent: 'bg-emerald-500', text: 'text-emerald-400', iconBg: 'bg-emerald-500/15', handle: '!bg-emerald-500' },
  blue:    { accent: 'bg-blue-500',    text: 'text-blue-400',    iconBg: 'bg-blue-500/15',    handle: '!bg-blue-500' },
  amber:   { accent: 'bg-amber-500',   text: 'text-amber-400',   iconBg: 'bg-amber-500/15',   handle: '!bg-amber-500' },
  purple:  { accent: 'bg-purple-500',  text: 'text-purple-400',  iconBg: 'bg-purple-500/15',  handle: '!bg-purple-500' },
  indigo:  { accent: 'bg-indigo-500',  text: 'text-indigo-400',  iconBg: 'bg-indigo-500/15',  handle: '!bg-indigo-500' },
  red:     { accent: 'bg-red-500',     text: 'text-red-400',     iconBg: 'bg-red-500/15',     handle: '!bg-red-500' },
  cyan:    { accent: 'bg-cyan-500',    text: 'text-cyan-400',    iconBg: 'bg-cyan-500/15',    handle: '!bg-cyan-500' },
  slate:   { accent: 'bg-slate-500',   text: 'text-slate-400',   iconBg: 'bg-slate-500/15',   handle: '!bg-slate-500' },
  teal:    { accent: 'bg-teal-500',    text: 'text-teal-400',    iconBg: 'bg-teal-500/15',    handle: '!bg-teal-500' },
  violet:  { accent: 'bg-violet-500',  text: 'text-violet-400',  iconBg: 'bg-violet-500/15',  handle: '!bg-violet-500' },
  lime:    { accent: 'bg-lime-500',    text: 'text-lime-400',    iconBg: 'bg-lime-500/15',    handle: '!bg-lime-500' },
  sky:     { accent: 'bg-sky-500',     text: 'text-sky-400',     iconBg: 'bg-sky-500/15',     handle: '!bg-sky-500' },
  pink:    { accent: 'bg-pink-500',    text: 'text-pink-400',    iconBg: 'bg-pink-500/15',    handle: '!bg-pink-500' },
  zinc:    { accent: 'bg-zinc-500',    text: 'text-zinc-400',    iconBg: 'bg-zinc-500/15',    handle: '!bg-zinc-500' },
  fuchsia: { accent: 'bg-fuchsia-500', text: 'text-fuchsia-400', iconBg: 'bg-fuchsia-500/15', handle: '!bg-fuchsia-500' },
  rose:    { accent: 'bg-rose-500',    text: 'text-rose-400',    iconBg: 'bg-rose-500/15',    handle: '!bg-rose-500' },
  orange:  { accent: 'bg-orange-500',  text: 'text-orange-400',  iconBg: 'bg-orange-500/15',  handle: '!bg-orange-500' },
  yellow:  { accent: 'bg-yellow-500',  text: 'text-yellow-400',  iconBg: 'bg-yellow-500/15',  handle: '!bg-yellow-500' },
  gray:    { accent: 'bg-gray-500',    text: 'text-gray-400',    iconBg: 'bg-gray-500/15',    handle: '!bg-gray-500' },
};

const DEFAULT_COLORS = COLOR_MAP.gray;

// ── Driver → actuals key (must match DriverNodeConfig) ──────────────────────

const DRIVER_TO_ACTUALS: Record<string, string> = {
  revenue_growth: 'revenue', revenue_override: 'revenue', gross_margin: 'gross_profit',
  churn_rate: 'revenue', nrr: 'revenue', rd_pct: 'opex_rd', sm_pct: 'opex_sm',
  ga_pct: 'opex_ga', burn_rate: 'net_burn', cash_override: 'cash_balance',
  funding_injection: 'cash_balance', headcount_change: 'headcount',
};

// ── Status dot ──────────────────────────────────────────────────────────────

function StatusDot({ status }: { status: string }) {
  if (status === 'idle') return null;
  const dotClass =
    status === 'running' ? 'bg-blue-400 animate-pulse' :
    status === 'done'    ? 'bg-emerald-400' :
    status === 'error'   ? 'bg-red-400' :
    'bg-muted-foreground';

  return <div className={`absolute -top-1 -right-1 w-2.5 h-2.5 rounded-full ${dotClass} ring-2 ring-card`} />;
}

// ── Compute evenly-spaced handle positions ──────────────────────────────────

function portOffsets(count: number): number[] {
  if (count <= 1) return [50];
  const start = 25;
  const end = 75;
  return Array.from({ length: count }, (_, i) =>
    count === 1 ? 50 : start + (i * (end - start)) / (count - 1)
  );
}

// ── Tiny sparkline for driver nodes ─────────────────────────────────────────

function NodeSparkline({ values }: { values: number[] }) {
  if (values.length < 2) return null;
  const max = Math.max(...values);
  const min = Math.min(...values);
  const range = max - min || 1;
  const w = 48;
  const h = 14;
  const points = values
    .map((v, i) => `${(i / (values.length - 1)) * w},${h - ((v - min) / range) * (h - 2) - 1}`)
    .join(' ');
  const isUp = values[values.length - 1] > values[0];
  return (
    <svg width={w} height={h} className="flex-shrink-0">
      <polyline points={points} fill="none" stroke={isUp ? '#10b981' : '#ef4444'} strokeWidth={1.2} strokeLinecap="round" />
    </svg>
  );
}

// ── Compact Node ────────────────────────────────────────────────────────────

function CompactNodeComponent({ data, selected }: NodeProps) {
  const d = data as unknown as WorkflowNodeData;
  const isTrigger = d.kind === 'trigger';
  const isOutput = d.kind === 'output';
  const isDriver = d.kind === 'driver';

  // Triggers always use emerald
  const colorKey = isTrigger ? 'emerald' : d.color;
  const colors = COLOR_MAP[colorKey] || DEFAULT_COLORS;
  const Icon = resolveIcon(d.icon);

  // ── Driver enrichment: sparkline + assumption count from store ─────────
  const companyData = useWorkflowStore((s) => s.companyData);
  const assumptions = (d.assumptions as NodeAssumption[]) || [];
  const assumptionCount = assumptions.length;

  const driverInfo = useMemo(() => {
    if (!isDriver || !companyData) return null;
    const chipId = (d.chipId || d.label?.toLowerCase().replace(/\s+/g, '_') || '') as string;
    const key = DRIVER_TO_ACTUALS[chipId] || 'revenue';
    const ts = companyData.timeSeries?.[key];
    if (!ts) return null;

    const sorted = Object.entries(ts).sort(([a], [b]) => a.localeCompare(b));
    const values = sorted.slice(-8).map(([, v]) => v as number);
    const latest = values[values.length - 1] || 0;

    const exposure = assumptionCount > 0 ? computeExposure(assumptions, latest) : null;

    return { values, latest, exposure };
  }, [isDriver, companyData, d.chipId, d.label, assumptions, assumptionCount]);

  // ── Resolve ports (fall back to legacy single handle) ─────────────────
  const inputPorts: PortDef[] = useMemo(() => {
    if (isDriver || isTrigger) return [];
    return (d.inputPorts && d.inputPorts.length > 0) ? d.inputPorts as PortDef[] : [];
  }, [d.inputPorts, isDriver, isTrigger]);

  const isConditional = d.operatorType === 'conditional' || d.operatorType === 'switch';

  const allOutputPorts: PortDef[] = useMemo(() => {
    if (isOutput) return [];
    return (d.outputPorts && d.outputPorts.length > 0) ? d.outputPorts as PortDef[] : [];
  }, [d.outputPorts, isOutput]);

  const outputPorts = useMemo(() => {
    if (!isConditional) return allOutputPorts;
    return allOutputPorts.filter((p) => p.id !== 'false_out');
  }, [allOutputPorts, isConditional]);

  const falsePort = useMemo(() => {
    if (!isConditional) return null;
    return allOutputPorts.find((p) => p.id === 'false_out') ?? null;
  }, [allOutputPorts, isConditional]);

  const hasTypedInputs = inputPorts.length > 0;
  const hasTypedOutputs = outputPorts.length > 0;
  const hasLegacyTarget = !hasTypedInputs && !isDriver && !isTrigger;
  const hasLegacySource = !hasTypedOutputs && !isOutput && !falsePort;

  const inOffsets = useMemo(() => portOffsets(inputPorts.length), [inputPorts.length]);
  const outOffsets = useMemo(() => portOffsets(outputPorts.length), [outputPorts.length]);

  const minH = Math.max(inputPorts.length, outputPorts.length) > 2 ? 'min-h-[56px]' : '';

  // Driver nodes are slightly wider to accommodate sparkline
  const nodeWidth = isDriver && driverInfo ? 'w-[160px]' : 'w-[140px]';

  return (
    <div
      className={`
        relative ${nodeWidth} bg-card rounded-xl border border-border/50
        cursor-pointer transition-all duration-150 shadow-sm
        hover:border-border
        ${minH}
        ${selected ? 'ring-1 ring-foreground/20 border-border' : ''}
        ${isTrigger ? 'shadow-[0_0_12px_rgba(16,185,129,0.12)]' : ''}
      `}
    >
      {/* Colored left accent bar */}
      <div className={`absolute left-0 top-2 bottom-2 w-1 rounded-r ${colors.accent}`} />

      {/* Main row: icon + label */}
      <div className="flex items-center gap-2 pl-4 pr-2.5 py-2.5">
        <div className={`w-7 h-7 rounded-md flex items-center justify-center flex-shrink-0 ${colors.iconBg}`}>
          <Icon className={`w-4 h-4 ${colors.text}`} />
        </div>
        <span className="text-[13px] font-medium text-card-foreground truncate flex-1 leading-tight">
          {d.label}
        </span>
      </div>

      {/* Driver enrichment: sparkline + assumptions */}
      {isDriver && driverInfo && (
        <div className="px-3 pb-2 -mt-0.5 space-y-1">
          <div className="flex items-center gap-2">
            <NodeSparkline values={driverInfo.values} />
            <span className="text-[11px] font-mono text-card-foreground/80">
              {formatNodeValue(driverInfo.latest)}
            </span>
          </div>
          {assumptionCount > 0 && driverInfo.exposure && (
            <div className="flex items-center justify-between">
              <span className="text-[10px] text-muted-foreground">
                {assumptionCount} assumption{assumptionCount !== 1 ? 's' : ''}
              </span>
              <span className={`text-[10px] font-mono font-medium ${
                driverInfo.exposure.netMonthly >= 0 ? 'text-emerald-400' : 'text-red-400'
              }`}>
                {formatExposure(driverInfo.exposure.netMonthly)}
              </span>
            </div>
          )}
        </div>
      )}

      {/* Status dot */}
      <StatusDot status={d.status} />

      {/* ── Typed input handles (left side) ──────────────────────────────── */}
      {hasTypedInputs && inputPorts.map((port, i) => (
        <Handle
          key={port.id}
          id={port.id}
          type="target"
          position={Position.Left}
          style={{ top: `${inOffsets[i]}%`, background: PORT_COLORS[port.dataType] || '#6b7280', borderColor: 'var(--wf-handle-border)' }}
          className="!w-2.5 !h-2.5 !border-2 hover:!scale-125 transition-transform"
          title={`${port.label} (${port.dataType})`}
        />
      ))}

      {/* ── Typed output handles (right side) ────────────────────────────── */}
      {hasTypedOutputs && outputPorts.map((port, i) => (
        <Handle
          key={port.id}
          id={port.id}
          type="source"
          position={Position.Right}
          style={{ top: `${outOffsets[i]}%`, background: PORT_COLORS[port.dataType] || '#6b7280', borderColor: 'var(--wf-handle-border)' }}
          className="!w-2.5 !h-2.5 !border-2 hover:!scale-125 transition-transform"
          title={`${port.label} (${port.dataType})`}
        />
      ))}

      {/* ── Legacy single handles (nodes without typed ports) ────────────── */}
      {hasLegacyTarget && (
        <Handle
          type="target"
          position={Position.Left}
          style={{ borderColor: 'var(--wf-handle-border)' }}
          className={`!w-2 !h-2 !border-2 ${colors.handle} hover:!scale-125 transition-transform`}
        />
      )}
      {hasLegacySource && (
        <Handle
          type="source"
          position={Position.Right}
          style={{ borderColor: 'var(--wf-handle-border)' }}
          className={`!w-2 !h-2 !border-2 ${colors.handle} hover:!scale-125 transition-transform`}
        />
      )}

      {/* Conditional/switch: false branch handle at bottom */}
      {falsePort && (
        <Handle
          type="source"
          position={Position.Bottom}
          id={falsePort.id}
          style={{ background: '#ef4444', borderColor: 'var(--wf-handle-border)' }}
          className="!w-2.5 !h-2.5 !border-2 hover:!scale-125 transition-transform"
          title={`${falsePort.label} (${falsePort.dataType})`}
        />
      )}
    </div>
  );
}

function formatNodeValue(v: number): string {
  const abs = Math.abs(v);
  if (abs >= 1_000_000) return `$${(v / 1_000_000).toFixed(1)}M`;
  if (abs >= 1_000) return `$${(v / 1_000).toFixed(0)}k`;
  if (abs >= 1) return `$${v.toFixed(0)}`;
  return `${(v * 100).toFixed(1)}%`;
}

export const CompactNode = memo(CompactNodeComponent);
