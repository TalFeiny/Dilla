'use client';

import { useCallback, useEffect, useRef } from 'react';
import {
  ReactFlow,
  Background,
  BackgroundVariant,
  Controls,
  MiniMap,
  ReactFlowProvider,
  useViewport,
  type ReactFlowInstance,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';

import { useWorkflowStore, type WorkflowNode } from '@/lib/workflow/store';
import type { PaletteItem, WorkflowNodeData } from '@/lib/workflow/types';
import { DOMAIN_META } from '@/lib/chips/types';
import { useWorkflowExecution } from '@/hooks/useWorkflowExecution';

import { CompactNode } from './nodes/CompactNode';
import { WorkflowEdge } from './edges/WorkflowEdge';
import { NodePalette } from './NodePalette';
import { WorkflowConfigDrawer } from './WorkflowConfigDrawer';
import { WorkflowToolbar } from './WorkflowToolbar';

// ── Node type registry — all types use the unified CompactNode ──────────────
const nodeTypes = {
  tool: CompactNode,
  operator: CompactNode,
  output: CompactNode,
  driver: CompactNode,
  formula: CompactNode,
  funding: CompactNode,
  trigger: CompactNode,
};

const edgeTypes = {
  workflow: WorkflowEdge,
};

const defaultEdgeOptions = {
  type: 'workflow',
  animated: false,
};

// ── Zoom indicator ──────────────────────────────────────────────────────────

function ZoomIndicator() {
  const { zoom } = useViewport();
  return (
    <div className="absolute bottom-4 right-20 text-[10px] text-muted-foreground font-mono pointer-events-none select-none z-10">
      {Math.round(zoom * 100)}%
    </div>
  );
}

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
  const setPanelOpen = useWorkflowStore((s) => s.setPanelOpen);
  const paletteOpen = useWorkflowStore((s) => s.isPaletteOpen);
  const isExecuting = useWorkflowStore((s) => s.isExecuting);

  // ── Output dispatch ──────────────────────────────────────────────────────
  const handleOutputReady = useCallback((nodeId: string, format: string, data: any) => {
    console.log(`[WorkflowBuilder] Output ready: ${nodeId} (${format})`, data);

    switch (format) {
      case 'chart':
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
        break;
    }
  }, []);

  // ── Company context from workflow store ─────────────────────────────────
  const companyId = useWorkflowStore((s) => s.companyId);
  const fetchCompanyData = useWorkflowStore((s) => s.fetchCompanyData);

  // ── Auto-fetch company data when companyId changes (pull_company_data) ──
  useEffect(() => {
    if (companyId) {
      fetchCompanyData(companyId);
    }
  }, [companyId, fetchCompanyData]);

  // ── Scenario branch dispatch — notify parent (UnifiedMatrix) to persist ──
  const handleScenarioBranchCreated = useCallback((result: any) => {
    window.dispatchEvent(new CustomEvent('workflow:scenario-branch', { detail: result }));
  }, []);

  // ── Execution hook ──────────────────────────────────────────────────────
  const { execute, stop } = useWorkflowExecution({
    companyId: companyId || undefined,
    onError: (error) => console.error('[WorkflowBuilder] Execution error:', error),
    onOutputReady: handleOutputReady,
    onScenarioBranchCreated: handleScenarioBranchCreated,
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

  // Single click — select + open config drawer
  const onNodeClick = useCallback((_: React.MouseEvent, node: any) => {
    selectNode(node.id);
    setPanelOpen(true);
  }, [selectNode, setPanelOpen]);

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

      // screenToFlowPosition expects screen (client) coordinates — not element-relative
      const position = rfInstance.screenToFlowPosition({
        x: e.clientX,
        y: e.clientY,
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
        triggerType: item.triggerType,
        outputFormat: item.kind === 'output' ? (item.defaultParams?.format || 'memo-section') : undefined,
        inputPorts: item.inputPorts,
        outputPorts: item.outputPorts,
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
    <div className="flex flex-col h-screen bg-background">
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
            defaultViewport={{ x: 0, y: 0, zoom: 0.8 }}
            minZoom={0.1}
            maxZoom={2}
            proOptions={{ hideAttribution: true }}
            className="bg-background"
            deleteKeyCode={['Backspace', 'Delete']}
            snapToGrid
            snapGrid={[20, 20]}
          >
            <Background variant={BackgroundVariant.Dots} color="var(--wf-dot)" gap={20} size={1} />
            <Controls
              className="!bg-card !border-border !rounded-xl [&>button]:!bg-secondary [&>button]:!border-border [&>button]:!text-muted-foreground [&>button:hover]:!bg-accent [&>button:hover]:!text-foreground"
              position="bottom-right"
              showInteractive={false}
            />
            <MiniMap
              className="!bg-card !border-border !rounded-xl"
              style={{ width: 120, height: 80 }}
              nodeColor={(node) => {
                const d = node.data as unknown as WorkflowNodeData;
                const colors: Record<string, string> = {
                  emerald: '#10b981', blue: '#3b82f6', amber: '#f59e0b',
                  purple: '#a855f7', teal: '#14b8a6', indigo: '#6366f1',
                  red: '#ef4444', lime: '#84cc16', slate: '#64748b',
                  sky: '#0ea5e9', pink: '#ec4899', fuchsia: '#d946ef',
                };
                return colors[d?.color] || '#9ca3af';
              }}
              position="bottom-left"
              pannable
              zoomable
            />
            <ZoomIndicator />
          </ReactFlow>
        </div>
      </div>
      <WorkflowConfigDrawer />
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
