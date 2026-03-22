'use client';

import { memo, useMemo } from 'react';
import { Handle, Position, type NodeProps } from '@xyflow/react';
import type { WorkflowNodeData } from '@/lib/workflow/types';
import type { PortDef } from '@/lib/workflow/port-types';
import { PORT_COLORS } from '@/lib/workflow/port-types';
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

// ── Status dot ──────────────────────────────────────────────────────────────

function StatusDot({ status }: { status: string }) {
  if (status === 'idle') return null;
  const dotClass =
    status === 'running' ? 'bg-blue-400 animate-pulse' :
    status === 'done'    ? 'bg-emerald-400' :
    status === 'error'   ? 'bg-red-400' :
    'bg-gray-500';

  return <div className={`absolute -top-1 -right-1 w-2.5 h-2.5 rounded-full ${dotClass} ring-2 ring-gray-900`} />;
}

// ── Compute evenly-spaced handle positions ──────────────────────────────────

/** Returns top-offsets (%) for N ports, centred vertically on the node */
function portOffsets(count: number): number[] {
  if (count <= 1) return [50];
  // Space handles from 25%→75% so they stay within the node body
  const start = 25;
  const end = 75;
  return Array.from({ length: count }, (_, i) =>
    count === 1 ? 50 : start + (i * (end - start)) / (count - 1)
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

  // ── Resolve ports (fall back to legacy single handle) ─────────────────
  const inputPorts: PortDef[] = useMemo(() => {
    if (isDriver || isTrigger) return [];
    return (d.inputPorts && d.inputPorts.length > 0) ? d.inputPorts as PortDef[] : [];
  }, [d.inputPorts, isDriver, isTrigger]);

  const isConditional = d.operatorType === 'conditional' || d.operatorType === 'switch';

  // For conditionals, split output ports: false_out goes to the bottom handle
  const allOutputPorts: PortDef[] = useMemo(() => {
    if (isOutput) return [];
    return (d.outputPorts && d.outputPorts.length > 0) ? d.outputPorts as PortDef[] : [];
  }, [d.outputPorts, isOutput]);

  // Right-side output ports (everything except false_out on conditionals)
  const outputPorts = useMemo(() => {
    if (!isConditional) return allOutputPorts;
    return allOutputPorts.filter((p) => p.id !== 'false_out');
  }, [allOutputPorts, isConditional]);

  // The false branch port (rendered at bottom for conditionals)
  const falsePort = useMemo(() => {
    if (!isConditional) return null;
    return allOutputPorts.find((p) => p.id === 'false_out') ?? null;
  }, [allOutputPorts, isConditional]);

  // Use typed ports if available, else legacy single handle
  const hasTypedInputs = inputPorts.length > 0;
  const hasTypedOutputs = outputPorts.length > 0;
  const hasLegacyTarget = !hasTypedInputs && !isDriver && !isTrigger;
  const hasLegacySource = !hasTypedOutputs && !isOutput && !falsePort;

  const inOffsets = useMemo(() => portOffsets(inputPorts.length), [inputPorts.length]);
  const outOffsets = useMemo(() => portOffsets(outputPorts.length), [outputPorts.length]);

  // Minimum height for multi-port nodes
  const minH = Math.max(inputPorts.length, outputPorts.length) > 2 ? 'min-h-[56px]' : '';

  return (
    <div
      className={`
        relative w-[140px] bg-gray-900 rounded-lg border border-gray-700/50
        flex items-center gap-2 pl-4 pr-2.5 py-2.5
        cursor-pointer transition-all duration-150
        hover:border-gray-600
        ${minH}
        ${selected ? 'ring-2 ring-blue-500/50 border-gray-600' : ''}
        ${isTrigger ? 'shadow-[0_0_12px_rgba(16,185,129,0.12)]' : ''}
      `}
    >
      {/* Colored left accent bar */}
      <div className={`absolute left-0 top-2 bottom-2 w-1 rounded-r ${colors.accent}`} />

      {/* Icon */}
      <div className={`w-7 h-7 rounded-md flex items-center justify-center flex-shrink-0 ${colors.iconBg}`}>
        <Icon className={`w-4 h-4 ${colors.text}`} />
      </div>

      {/* Label */}
      <span className="text-[13px] font-medium text-gray-200 truncate flex-1 leading-tight">
        {d.label}
      </span>

      {/* Status dot */}
      <StatusDot status={d.status} />

      {/* ── Typed input handles (left side) ──────────────────────────────── */}
      {hasTypedInputs && inputPorts.map((port, i) => (
        <Handle
          key={port.id}
          id={port.id}
          type="target"
          position={Position.Left}
          style={{ top: `${inOffsets[i]}%`, background: PORT_COLORS[port.dataType] || '#6b7280' }}
          className="!w-2.5 !h-2.5 !border-2 !border-gray-900 hover:!scale-125 transition-transform"
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
          style={{ top: `${outOffsets[i]}%`, background: PORT_COLORS[port.dataType] || '#6b7280' }}
          className="!w-2.5 !h-2.5 !border-2 !border-gray-900 hover:!scale-125 transition-transform"
          title={`${port.label} (${port.dataType})`}
        />
      ))}

      {/* ── Legacy single handles (nodes without typed ports) ────────────── */}
      {hasLegacyTarget && (
        <Handle
          type="target"
          position={Position.Left}
          className={`!w-2 !h-2 !border-2 !border-gray-900 ${colors.handle} hover:!scale-125 transition-transform`}
        />
      )}
      {hasLegacySource && (
        <Handle
          type="source"
          position={Position.Right}
          className={`!w-2 !h-2 !border-2 !border-gray-900 ${colors.handle} hover:!scale-125 transition-transform`}
        />
      )}

      {/* Conditional/switch: false branch handle at bottom */}
      {falsePort && (
        <Handle
          type="source"
          position={Position.Bottom}
          id={falsePort.id}
          style={{ background: '#ef4444' }}
          className="!w-2.5 !h-2.5 !border-2 !border-gray-900 hover:!scale-125 transition-transform"
          title={`${falsePort.label} (${falsePort.dataType})`}
        />
      )}
    </div>
  );
}

export const CompactNode = memo(CompactNodeComponent);
