'use client';

import { memo } from 'react';
import { Handle, Position, type NodeProps } from '@xyflow/react';
import type { WorkflowNodeData } from '@/lib/workflow/types';
import { Loader2, CheckCircle2, XCircle } from 'lucide-react';

const OPERATOR_SHAPES: Record<string, string> = {
  loop: 'rounded-full',
  conditional: 'rotate-45',
  switch: 'rotate-45',
  bridge: 'rounded-lg',
  parallel: 'rounded-lg',
  filter: 'rounded-lg',
  aggregate: 'rounded-lg',
  map: 'rounded-lg',
  merge: 'rounded-lg',
  event_business: 'rounded-lg',
  event_macro: 'rounded-lg',
  event_funding: 'rounded-lg',
  prior: 'rounded-lg',
};

const STATUS_ICON = {
  idle: null,
  running: <Loader2 className="w-3 h-3 text-blue-400 animate-spin" />,
  done: <CheckCircle2 className="w-3 h-3 text-emerald-400" />,
  error: <XCircle className="w-3 h-3 text-red-400" />,
} as const;

function OperatorNodeComponent({ data, selected }: NodeProps) {
  const d = data as unknown as WorkflowNodeData;
  const isDiamond = d.operatorType === 'conditional' || d.operatorType === 'switch';

  if (isDiamond) {
    return (
      <div className={`relative ${selected ? 'drop-shadow-[0_0_8px_rgba(255,255,255,0.2)]' : ''}`}>
        {/* Diamond shape */}
        <div
          className={`
            w-[80px] h-[80px] rotate-45 bg-gray-900 border-2
            ${d.status === 'running' ? 'border-blue-500 shadow-blue-500/20 shadow-lg' :
              d.status === 'done' ? 'border-emerald-500' :
              d.status === 'error' ? 'border-red-500' :
              `border-${d.color}-500/60`}
          `}
        >
          <div className="-rotate-45 flex flex-col items-center justify-center w-full h-full">
            <span className="text-xs font-medium text-gray-200">{d.label}</span>
            {STATUS_ICON[d.status]}
          </div>
        </div>
        <Handle
          type="target"
          position={Position.Left}
          className="!w-2.5 !h-2.5 !bg-gray-600 !border-2 !border-gray-800"
          style={{ left: -5, top: '50%' }}
        />
        <Handle
          type="source"
          position={Position.Right}
          className="!w-2.5 !h-2.5 !bg-gray-600 !border-2 !border-gray-800"
          style={{ right: -5, top: '50%' }}
        />
        {/* Extra handle for true/false branches */}
        <Handle
          type="source"
          position={Position.Bottom}
          id="false"
          className="!w-2.5 !h-2.5 !bg-red-600 !border-2 !border-gray-800"
          style={{ bottom: -5, left: '50%' }}
        />
      </div>
    );
  }

  // Standard operator — rounded pill shape
  return (
    <div
      className={`
        relative bg-gray-900 rounded-xl border-2 px-4 py-2.5 min-w-[140px]
        transition-all duration-200 cursor-pointer
        ${d.status === 'running' ? 'border-blue-500 shadow-blue-500/20 shadow-lg' :
          d.status === 'done' ? 'border-emerald-500' :
          d.status === 'error' ? 'border-red-500' :
          `border-${d.color}-500/60 border-dashed`}
        ${selected ? 'ring-2 ring-white/30' : ''}
      `}
    >
      <div className="flex items-center gap-2">
        <span className={`text-${d.color}-400 text-sm`}>{d.icon}</span>
        <span className="text-sm font-medium text-gray-200">{d.label}</span>
        {STATUS_ICON[d.status]}
      </div>

      {d.operatorType === 'loop' && d.params.loopOver && (
        <div className="mt-1 text-[10px] text-gray-500">over {d.params.loopOver}</div>
      )}

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

export const OperatorNode = memo(OperatorNodeComponent);
