'use client';

import { memo } from 'react';
import { Handle, Position, type NodeProps } from '@xyflow/react';
import type { WorkflowNodeData } from '@/lib/workflow/types';

function FormulaNodeComponent({ data, selected }: NodeProps) {
  const d = data as unknown as WorkflowNodeData;

  return (
    <div
      className={`
        relative bg-gray-900 rounded-lg border-2 px-3 py-2 min-w-[160px] max-w-[240px]
        transition-all duration-200 cursor-pointer
        border-lime-500/50
        ${selected ? 'ring-2 ring-white/30 border-lime-400' : ''}
      `}
    >
      <div className="absolute top-0 left-2 right-2 h-0.5 rounded-b bg-lime-500" />
      <div className="flex items-center gap-2">
        <span className="text-lime-400 text-xs font-mono">ƒ</span>
        <span className="text-sm font-medium text-gray-200">{d.label}</span>
      </div>

      {d.params.expression && (
        <div className="mt-1.5 bg-gray-950 rounded px-2 py-1">
          <code className="text-[11px] text-lime-300 font-mono break-all">
            {d.params.expression}
          </code>
        </div>
      )}

      <Handle
        type="target"
        position={Position.Left}
        className="!w-2.5 !h-2.5 !bg-lime-600 !border-2 !border-gray-800 hover:!bg-lime-400"
      />
      <Handle
        type="source"
        position={Position.Right}
        className="!w-2.5 !h-2.5 !bg-lime-600 !border-2 !border-gray-800 hover:!bg-lime-400"
      />
    </div>
  );
}

export const FormulaNode = memo(FormulaNodeComponent);
