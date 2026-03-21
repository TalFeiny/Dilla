'use client';

import { memo } from 'react';
import { Handle, Position, type NodeProps } from '@xyflow/react';
import type { WorkflowNodeData } from '@/lib/workflow/types';

function DriverNodeComponent({ data, selected }: NodeProps) {
  const d = data as unknown as WorkflowNodeData;

  return (
    <div
      className={`
        relative bg-gray-900 rounded-lg border-2 px-3 py-2 min-w-[150px]
        transition-all duration-200 cursor-pointer
        border-purple-500/50
        ${selected ? 'ring-2 ring-white/30 border-purple-400' : ''}
      `}
    >
      <div className="absolute top-0 left-2 right-2 h-0.5 rounded-b bg-purple-500" />
      <div className="flex items-center gap-2">
        <span className="text-purple-400 text-sm">{d.icon}</span>
        <span className="text-sm font-medium text-gray-200">{d.label}</span>
      </div>

      {d.params.value !== undefined && (
        <div className="mt-1">
          <span className="text-xs font-mono text-purple-300">
            {typeof d.params.value === 'number' && d.params.value > 0 ? '+' : ''}
            {d.params.value}
            {d.params.unit === 'percent' ? '%' : ''}
          </span>
        </div>
      )}

      {/* Only output — drivers feed into tool nodes */}
      <Handle
        type="source"
        position={Position.Right}
        className="!w-2.5 !h-2.5 !bg-purple-500 !border-2 !border-gray-800 hover:!bg-purple-300"
      />
    </div>
  );
}

export const DriverNode = memo(DriverNodeComponent);
