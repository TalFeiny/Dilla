'use client';

import { memo } from 'react';
import { Handle, Position, type NodeProps } from '@xyflow/react';
import type { WorkflowNodeData } from '@/lib/workflow/types';
import { Loader2, CheckCircle2, XCircle } from 'lucide-react';

const FORMAT_LABELS: Record<string, string> = {
  'memo-section': 'Memo',
  'deck-slide': 'Deck',
  chart: 'Chart',
  grid: 'Grid',
  table: 'Table',
  narrative: 'Text',
  export: 'Export',
  'scenario-branch': 'Scenario',
};

const STATUS_ICON = {
  idle: null,
  running: <Loader2 className="w-3 h-3 text-blue-400 animate-spin" />,
  done: <CheckCircle2 className="w-3 h-3 text-emerald-400" />,
  error: <XCircle className="w-3 h-3 text-red-400" />,
} as const;

function getResultPreview(format: string | undefined, result: any): string | null {
  if (!result) return null;
  switch (format) {
    case 'chart':
      return 'Chart ready';
    case 'memo-section': {
      const count = result?.sections?.length ?? 0;
      return `${count} section${count !== 1 ? 's' : ''}`;
    }
    case 'table': {
      const rows = result?.rows?.length ?? 0;
      return `${rows} row${rows !== 1 ? 's' : ''}`;
    }
    case 'narrative': {
      const text = result?.text || '';
      return text.length > 60 ? text.slice(0, 60) + '...' : text;
    }
    case 'deck-slide': {
      const slides = result?.slides?.length ?? 0;
      return `${slides} slide${slides !== 1 ? 's' : ''}`;
    }
    case 'grid':
      return 'Grid update ready';
    case 'export':
      return 'Export ready';
    case 'scenario-branch':
      return 'Scenario ready';
    default:
      return null;
  }
}

function OutputNodeComponent({ data, selected }: NodeProps) {
  const d = data as unknown as WorkflowNodeData;
  const preview = d.status === 'done' ? getResultPreview(d.outputFormat, d.result) : null;

  return (
    <div
      className={`
        relative bg-gray-900/80 rounded-r-2xl rounded-l-lg border-2 px-4 py-3 min-w-[140px]
        transition-all duration-200 cursor-pointer
        ${d.status === 'done' ? 'border-emerald-500' :
          d.status === 'error' ? 'border-red-500' :
          d.status === 'running' ? 'border-blue-500' :
          'border-slate-500/50'}
        ${selected ? 'ring-2 ring-white/30' : ''}
      `}
    >
      <div className="flex items-center gap-2">
        <div className="w-5 h-5 rounded bg-slate-700 flex items-center justify-center">
          <span className="text-[10px] text-slate-300">OUT</span>
        </div>
        <span className="text-sm font-medium text-gray-200">{d.label}</span>
        {STATUS_ICON[d.status]}
      </div>

      {d.outputFormat && (
        <div className="mt-1">
          <span className="text-[10px] px-1.5 py-0.5 bg-slate-800 rounded text-slate-400">
            {FORMAT_LABELS[d.outputFormat] || d.outputFormat}
          </span>
        </div>
      )}

      {preview && (
        <div className="mt-1.5 text-[10px] text-emerald-400/80 truncate max-w-[160px]">
          {preview}
        </div>
      )}

      {d.status === 'error' && d.error && (
        <div className="mt-1.5 text-[10px] text-red-400/80 truncate max-w-[160px]">
          {d.error}
        </div>
      )}

      {/* Only input handle — no output */}
      <Handle
        type="target"
        position={Position.Left}
        className="!w-2.5 !h-2.5 !bg-slate-500 !border-2 !border-gray-800 hover:!bg-slate-300"
      />
    </div>
  );
}

export const OutputNode = memo(OutputNodeComponent);
