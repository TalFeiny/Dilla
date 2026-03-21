'use client';

import { memo } from 'react';
import { Handle, Position, type NodeProps } from '@xyflow/react';
import type { WorkflowNodeData } from '@/lib/workflow/types';
import { Loader2, CheckCircle2, XCircle } from 'lucide-react';

const STATUS_ICON = {
  idle: null,
  running: <Loader2 className="w-3 h-3 text-blue-400 animate-spin" />,
  done: <CheckCircle2 className="w-3 h-3 text-emerald-400" />,
  error: <XCircle className="w-3 h-3 text-red-400" />,
} as const;

function FundingNodeComponent({ data, selected }: NodeProps) {
  const d = data as unknown as WorkflowNodeData;
  const isDebt = d.params.type === 'debt';

  return (
    <div
      className={`
        relative bg-gray-900 rounded-lg border-2 px-4 py-3 min-w-[180px] max-w-[260px]
        transition-all duration-200 cursor-pointer
        ${d.status === 'running' ? 'border-blue-500 shadow-blue-500/20 shadow-lg' :
          d.status === 'done' ? 'border-emerald-500' :
          d.status === 'error' ? 'border-red-500' :
          'border-teal-500/60'}
        ${selected ? 'ring-2 ring-white/30' : ''}
      `}
    >
      <div className={`absolute top-0 left-3 right-3 h-0.5 rounded-b ${isDebt ? 'bg-orange-500' : 'bg-teal-500'}`} />

      <div className="flex items-center gap-2">
        <span className={`text-sm ${isDebt ? 'text-orange-400' : 'text-teal-400'}`}>
          {isDebt ? '🏦' : '💰'}
        </span>
        <span className="text-sm font-medium text-gray-100">{d.label}</span>
        {STATUS_ICON[d.status]}
      </div>

      {/* Key terms preview */}
      <div className="mt-1.5 flex flex-wrap gap-1">
        {d.params.round && (
          <span className="text-[10px] px-1.5 py-0.5 bg-teal-900/40 rounded text-teal-300">
            {d.params.round}
          </span>
        )}
        {d.params.amount && (
          <span className="text-[10px] px-1.5 py-0.5 bg-gray-800 rounded text-gray-300">
            ${typeof d.params.amount === 'number' ? (d.params.amount >= 1e6 ? `${d.params.amount / 1e6}M` : `${d.params.amount / 1e3}K`) : d.params.amount}
          </span>
        )}
        {d.params.rate && (
          <span className="text-[10px] px-1.5 py-0.5 bg-gray-800 rounded text-gray-300">
            {d.params.rate}%
          </span>
        )}
      </div>

      <Handle
        type="target"
        position={Position.Left}
        className="!w-2.5 !h-2.5 !bg-teal-500 !border-2 !border-gray-800 hover:!bg-teal-300"
      />
      <Handle
        type="source"
        position={Position.Right}
        className="!w-2.5 !h-2.5 !bg-teal-500 !border-2 !border-gray-800 hover:!bg-teal-300"
      />
    </div>
  );
}

export const FundingNode = memo(FundingNodeComponent);
