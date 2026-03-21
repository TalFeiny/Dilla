'use client';

import { memo } from 'react';
import { Handle, Position, type NodeProps } from '@xyflow/react';
import type { WorkflowNodeData } from '@/lib/workflow/types';
import { Loader2, CheckCircle2, XCircle } from 'lucide-react';

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

function ToolNodeComponent({ data, selected }: NodeProps) {
  const d = data as unknown as WorkflowNodeData;
  const statusStyle = STATUS_STYLES[d.status] || STATUS_STYLES.idle;

  return (
    <div
      className={`
        relative bg-gray-900 rounded-lg border-2 px-4 py-3 min-w-[180px] max-w-[240px]
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
