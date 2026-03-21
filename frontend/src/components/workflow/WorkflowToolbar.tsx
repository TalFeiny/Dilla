'use client';

import { Play, Square, RotateCcw, Save, PanelLeft, Trash2 } from 'lucide-react';
import { useWorkflowStore } from '@/lib/workflow/store';

interface WorkflowToolbarProps {
  onRun?: () => void;
  onSave?: () => void;
}

export function WorkflowToolbar({ onRun, onSave }: WorkflowToolbarProps) {
  const isExecuting = useWorkflowStore((s) => s.isExecuting);
  const isPaletteOpen = useWorkflowStore((s) => s.isPaletteOpen);
  const togglePalette = useWorkflowStore((s) => s.togglePalette);
  const resetExecution = useWorkflowStore((s) => s.resetExecution);
  const clearCanvas = useWorkflowStore((s) => s.clearCanvas);
  const nodes = useWorkflowStore((s) => s.nodes);

  return (
    <div className="h-12 bg-gray-950 border-b border-gray-800 flex items-center justify-between px-4">
      {/* Left */}
      <div className="flex items-center gap-2">
        {!isPaletteOpen && (
          <button
            onClick={togglePalette}
            className="p-1.5 hover:bg-gray-800 rounded text-gray-400 hover:text-gray-200 transition-colors"
            title="Show node palette"
          >
            <PanelLeft className="w-4 h-4" />
          </button>
        )}
        <span className="text-sm font-semibold text-gray-200">Workflow Builder</span>
        <span className="text-[10px] text-gray-600 ml-1">{nodes.length} nodes</span>
      </div>

      {/* Center */}
      <div className="flex items-center gap-1.5">
        <button
          onClick={onRun}
          disabled={isExecuting || nodes.length === 0}
          className={`
            flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-colors
            ${isExecuting
              ? 'bg-red-500/20 text-red-400 hover:bg-red-500/30'
              : 'bg-emerald-500/20 text-emerald-400 hover:bg-emerald-500/30'
            }
            disabled:opacity-40 disabled:cursor-not-allowed
          `}
        >
          {isExecuting ? (
            <>
              <Square className="w-3.5 h-3.5" /> Stop
            </>
          ) : (
            <>
              <Play className="w-3.5 h-3.5" /> Run
            </>
          )}
        </button>

        <button
          onClick={resetExecution}
          disabled={isExecuting}
          className="p-1.5 hover:bg-gray-800 rounded text-gray-500 hover:text-gray-300 transition-colors disabled:opacity-40"
          title="Reset execution state"
        >
          <RotateCcw className="w-3.5 h-3.5" />
        </button>
      </div>

      {/* Right */}
      <div className="flex items-center gap-1.5">
        <button
          onClick={onSave}
          disabled={nodes.length === 0}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium text-gray-400 hover:bg-gray-800 transition-colors disabled:opacity-40"
        >
          <Save className="w-3.5 h-3.5" /> Save
        </button>
        <button
          onClick={clearCanvas}
          disabled={nodes.length === 0 || isExecuting}
          className="p-1.5 hover:bg-gray-800 rounded text-gray-600 hover:text-red-400 transition-colors disabled:opacity-40"
          title="Clear canvas"
        >
          <Trash2 className="w-3.5 h-3.5" />
        </button>
      </div>
    </div>
  );
}
