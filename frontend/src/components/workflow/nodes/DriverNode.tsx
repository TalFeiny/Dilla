'use client';

import { memo } from 'react';
import { Handle, Position, type NodeProps } from '@xyflow/react';
import type { WorkflowNodeData } from '@/lib/workflow/types';

/** Format the driver value with its unit for prominent display */
function formatValue(value: number, chipId?: string, unit?: string): string {
  // Detect unit from chipId or explicit unit
  const isPercent = unit === 'percent' || unit === '%' || chipId?.includes('growth') || chipId?.includes('margin') || chipId?.includes('churn') || chipId?.includes('pct');
  const isCurrency = unit === 'currency' || unit === '$' || chipId?.includes('burn') || chipId?.includes('cac') || chipId?.includes('ltv') || chipId?.includes('salary');

  if (isPercent) return `${value > 0 ? '+' : ''}${value}%`;
  if (isCurrency) {
    const abs = Math.abs(value);
    if (abs >= 1_000_000) return `$${(value / 1_000_000).toFixed(1)}M`;
    if (abs >= 1_000) return `$${(value / 1_000).toFixed(0)}k`;
    return `$${value}`;
  }
  return `${value > 0 ? '+' : ''}${value}`;
}

function DriverNodeComponent({ data, selected }: NodeProps) {
  const d = data as unknown as WorkflowNodeData;
  const hasValue = d.params.value !== undefined && d.params.value !== 0;

  return (
    <div
      className={`
        relative bg-gray-900 rounded-lg border-2 px-3 py-2.5 min-w-[150px]
        transition-all duration-200 cursor-pointer
        ${hasValue ? 'border-purple-500/70' : 'border-purple-500/30'}
        ${selected ? 'ring-2 ring-white/30 border-purple-400' : ''}
      `}
    >
      <div className="absolute top-0 left-2 right-2 h-0.5 rounded-b bg-purple-500" />

      {/* Label */}
      <div className="flex items-center gap-2">
        <span className="text-purple-400 text-sm">{d.icon}</span>
        <span className="text-xs font-medium text-gray-300 truncate">{d.label}</span>
      </div>

      {/* Value — prominently displayed */}
      {d.params.value !== undefined && (
        <div className="mt-1.5 text-center">
          <span className={`text-lg font-mono font-bold ${hasValue ? 'text-purple-300' : 'text-gray-600'}`}>
            {formatValue(d.params.value, d.chipId, d.params.unit)}
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
