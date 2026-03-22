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
  const companyName = useWorkflowStore((s) => s.companyName);
  const companyId = useWorkflowStore((s) => s.companyId);

  return (
    <div className="h-12 bg-card border-b border-border flex items-center justify-between px-4">
      {/* Left */}
      <div className="flex items-center gap-2">
        {!isPaletteOpen && (
          <button
            onClick={togglePalette}
            className="p-1.5 hover:bg-accent rounded-lg text-muted-foreground hover:text-foreground transition-colors"
            title="Show node palette"
          >
            <PanelLeft className="w-4 h-4" />
          </button>
        )}
        <span className="text-sm font-semibold text-foreground">Workflow Builder</span>
        {companyName ? (
          <span className="ml-2 px-2 py-0.5 rounded-md bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 text-[10px] font-medium border border-emerald-500/20">
            {companyName}
          </span>
        ) : (
          <span className="ml-2 text-[10px] text-amber-500">No company selected</span>
        )}
        <span className="text-[10px] text-muted-foreground ml-1">{nodes.length} nodes</span>
      </div>

      {/* Center */}
      <div className="flex items-center gap-1.5">
        <button
          onClick={onRun}
          disabled={isExecuting || nodes.length === 0 || !companyId}
          className={`
            flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors
            ${isExecuting
              ? 'bg-red-500/15 text-red-600 dark:text-red-400 hover:bg-red-500/25'
              : 'bg-emerald-500/15 text-emerald-600 dark:text-emerald-400 hover:bg-emerald-500/25'
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
          className="p-1.5 hover:bg-accent rounded-lg text-muted-foreground hover:text-foreground transition-colors disabled:opacity-40"
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
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium text-muted-foreground hover:bg-accent hover:text-foreground transition-colors disabled:opacity-40"
        >
          <Save className="w-3.5 h-3.5" /> Save
        </button>
        <button
          onClick={clearCanvas}
          disabled={nodes.length === 0 || isExecuting}
          className="p-1.5 hover:bg-accent rounded-lg text-muted-foreground hover:text-red-500 transition-colors disabled:opacity-40"
          title="Clear canvas"
        >
          <Trash2 className="w-3.5 h-3.5" />
        </button>
      </div>
    </div>
  );
}
