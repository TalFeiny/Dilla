'use client';

import { useCallback, useRef, useMemo } from 'react';
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  ReactFlowProvider,
  type ReactFlowInstance,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';

import { useWorkflowStore, type WorkflowNode } from '@/lib/workflow/store';
import type { PaletteItem, WorkflowNodeData } from '@/lib/workflow/types';
import { DOMAIN_META } from '@/lib/chips/types';
import { useWorkflowExecution } from '@/hooks/useWorkflowExecution';

import { ToolNode } from './nodes/ToolNode';
import { OperatorNode } from './nodes/OperatorNode';
import { OutputNode } from './nodes/OutputNode';
import { DriverNode } from './nodes/DriverNode';
import { FormulaNode } from './nodes/FormulaNode';
import { FundingNode } from './nodes/FundingNode';
import { WorkflowEdge } from './edges/WorkflowEdge';
import { NodePalette } from './NodePalette';
import { WorkflowPanel } from './WorkflowPanel';
import { WorkflowToolbar } from './WorkflowToolbar';

// ── Node type registry for React Flow ────────────────────────────────────
const nodeTypes = {
  tool: ToolNode,
  operator: OperatorNode,
  output: OutputNode,
  driver: DriverNode,
  formula: FormulaNode,
  funding: FundingNode,
};

const edgeTypes = {
  workflow: WorkflowEdge,
};

const defaultEdgeOptions = {
  type: 'workflow',
  animated: false,
};

// ── Canvas component ─────────────────────────────────────────────────────

function WorkflowCanvasInner() {
  const reactFlowWrapper = useRef<HTMLDivElement>(null);
  const reactFlowInstance = useRef<ReactFlowInstance | null>(null);

  const nodes = useWorkflowStore((s) => s.nodes);
  const edges = useWorkflowStore((s) => s.edges);
  const onNodesChange = useWorkflowStore((s) => s.onNodesChange);
  const onEdgesChange = useWorkflowStore((s) => s.onEdgesChange);
  const onConnect = useWorkflowStore((s) => s.onConnect);
  const addNode = useWorkflowStore((s) => s.addNode);
  const selectNode = useWorkflowStore((s) => s.selectNode);
  const isPanelOpen = useWorkflowStore((s) => s.isPanelOpen);
  const paletteOpen = useWorkflowStore((s) => s.isPaletteOpen);
  const isExecuting = useWorkflowStore((s) => s.isExecuting);

  // ── Output dispatch ──────────────────────────────────────────────────────
  const handleOutputReady = useCallback((nodeId: string, format: string, data: any) => {
    console.log(`[WorkflowBuilder] Output ready: ${nodeId} (${format})`, data);

    // Dispatch to appropriate UI target based on format
    switch (format) {
      case 'chart':
        // Emit custom event for ChartViewport to pick up
        window.dispatchEvent(new CustomEvent('workflow:output', {
          detail: { format: 'chart', nodeId, data },
        }));
        break;
      case 'memo-section':
        window.dispatchEvent(new CustomEvent('workflow:output', {
          detail: { format: 'memo-section', nodeId, sections: data?.sections },
        }));
        break;
      case 'deck-slide':
        window.dispatchEvent(new CustomEvent('workflow:output', {
          detail: { format: 'deck-slide', nodeId, slides: data?.slides },
        }));
        break;
      case 'grid':
        window.dispatchEvent(new CustomEvent('workflow:output', {
          detail: { format: 'grid', nodeId, data },
        }));
        break;
      case 'export':
        window.dispatchEvent(new CustomEvent('workflow:output', {
          detail: { format: 'export', nodeId, data },
        }));
        break;
      default:
        // narrative, table, scenario-branch — rendered in panel
        break;
    }
  }, []);

  // ── Execution hook ──────────────────────────────────────────────────────
  const { execute, stop } = useWorkflowExecution({
    onError: (error) => console.error('[WorkflowBuilder] Execution error:', error),
    onOutputReady: handleOutputReady,
  });

  const handleRun = useCallback(() => {
    if (isExecuting) {
      stop();
    } else {
      execute();
    }
  }, [isExecuting, execute, stop]);

  const handleSave = useCallback(async () => {
    const { nodes: currentNodes, edges: currentEdges } = useWorkflowStore.getState();
    if (currentNodes.length === 0) return;

    try {
      const res = await fetch('/api/workflow', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: `Workflow ${new Date().toLocaleDateString()}`,
          nodes: currentNodes,
          edges: currentEdges,
        }),
      });
      if (!res.ok) throw new Error('Save failed');
      const data = await res.json();
      console.log('[WorkflowBuilder] Saved:', data.id);
    } catch (err) {
      console.error('[WorkflowBuilder] Save error:', err);
    }
  }, []);

  const onInit = useCallback((instance: ReactFlowInstance) => {
    reactFlowInstance.current = instance;
  }, []);

  const onNodeClick = useCallback((_: React.MouseEvent, node: any) => {
    selectNode(node.id);
  }, [selectNode]);

  const onPaneClick = useCallback(() => {
    selectNode(null);
  }, [selectNode]);

  // ── Drop handler — palette drag → canvas ─────────────────────────────
  const onDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.dataTransfer.dropEffect = 'move';
  }, []);

  const onDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();

      const raw = e.dataTransfer.getData('application/workflow-node');
      if (!raw) return;

      const item: PaletteItem = JSON.parse(raw);
      const rfInstance = reactFlowInstance.current;
      if (!rfInstance || !reactFlowWrapper.current) return;

      const bounds = reactFlowWrapper.current.getBoundingClientRect();
      const position = rfInstance.screenToFlowPosition({
        x: e.clientX - bounds.left,
        y: e.clientY - bounds.top,
      });

      // Determine node type for React Flow
      let type: string = item.kind;
      if (item.kind === 'tool' && item.chipDef?.domain === 'funding') {
        type = 'funding';
      }

      const meta = DOMAIN_META[item.domain] || { color: 'gray', icon: '?' };

      const nodeData: WorkflowNodeData = {
        kind: item.kind,
        label: item.label,
        icon: item.icon,
        domain: item.domain,
        color: item.color || meta.color,
        chipId: item.chipId,
        chipDef: item.chipDef,
        params: { ...(item.defaultParams || {}) },
        operatorType: item.operatorType,
        outputFormat: item.kind === 'output' ? (item.defaultParams?.format || 'memo-section') : undefined,
        status: 'idle',
      };

      addNode({
        type,
        position,
        data: nodeData as any,
      });
    },
    [addNode]
  );

  return (
    <div className="flex flex-col h-screen bg-gray-950">
      <WorkflowToolbar onRun={handleRun} onSave={handleSave} />
      <div className="flex flex-1 overflow-hidden">
        {paletteOpen && <NodePalette />}
        <div ref={reactFlowWrapper} className="flex-1 relative">
          <ReactFlow
            nodes={nodes}
            edges={edges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onConnect={onConnect}
            onInit={onInit}
            onNodeClick={onNodeClick}
            onPaneClick={onPaneClick}
            onDragOver={onDragOver}
            onDrop={onDrop}
            nodeTypes={nodeTypes}
            edgeTypes={edgeTypes}
            defaultEdgeOptions={defaultEdgeOptions}
            fitView
            proOptions={{ hideAttribution: true }}
            className="bg-gray-950"
            deleteKeyCode={['Backspace', 'Delete']}
            snapToGrid
            snapGrid={[16, 16]}
          >
            <Background color="#1f2937" gap={16} size={1} />
            <Controls
              className="!bg-gray-900 !border-gray-700 !rounded-lg [&>button]:!bg-gray-800 [&>button]:!border-gray-700 [&>button]:!text-gray-400 [&>button:hover]:!bg-gray-700"
              position="bottom-right"
            />
            <MiniMap
              className="!bg-gray-900 !border-gray-700 !rounded-lg"
              nodeColor={(node) => {
                const d = node.data as unknown as WorkflowNodeData;
                const colors: Record<string, string> = {
                  emerald: '#10b981', blue: '#3b82f6', amber: '#f59e0b',
                  purple: '#a855f7', teal: '#14b8a6', indigo: '#6366f1',
                  red: '#ef4444', lime: '#84cc16', slate: '#64748b',
                  sky: '#0ea5e9', pink: '#ec4899', fuchsia: '#d946ef',
                };
                return colors[d?.color] || '#4b5563';
              }}
              position="bottom-left"
              pannable
              zoomable
            />
          </ReactFlow>
        </div>
        {isPanelOpen && <WorkflowPanel />}
      </div>
    </div>
  );
}

export function WorkflowCanvas() {
  return (
    <ReactFlowProvider>
      <WorkflowCanvasInner />
    </ReactFlowProvider>
  );
}
