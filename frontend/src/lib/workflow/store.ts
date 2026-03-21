// ---------------------------------------------------------------------------
// Workflow Builder — Zustand Store
// ---------------------------------------------------------------------------

import { create } from 'zustand';
import {
  type Node,
  type Edge,
  type OnNodesChange,
  type OnEdgesChange,
  type OnConnect,
  applyNodeChanges,
  applyEdgeChanges,
  addEdge,
  type Connection,
} from '@xyflow/react';
import { nanoid } from 'nanoid';
import type { WorkflowNodeData } from './types';

export type WorkflowNode = Node<WorkflowNodeData>;
export type WorkflowEdge = Edge;

interface WorkflowStore {
  // ── State ──────────────────────────────────────────────────
  nodes: WorkflowNode[];
  edges: WorkflowEdge[];
  selectedNodeId: string | null;
  isPaletteOpen: boolean;
  isPanelOpen: boolean;
  isExecuting: boolean;

  // ── React Flow callbacks ───────────────────────────────────
  onNodesChange: OnNodesChange;
  onEdgesChange: OnEdgesChange;
  onConnect: OnConnect;

  // ── Node operations ────────────────────────────────────────
  addNode: (node: Omit<WorkflowNode, 'id'> & { id?: string }) => string;
  removeNode: (id: string) => void;
  updateNodeData: (id: string, data: Partial<WorkflowNodeData>) => void;
  selectNode: (id: string | null) => void;

  // ── Edge operations ────────────────────────────────────────
  removeEdge: (id: string) => void;

  // ── UI state ───────────────────────────────────────────────
  togglePalette: () => void;
  togglePanel: () => void;
  setPanelOpen: (open: boolean) => void;

  // ── Execution ──────────────────────────────────────────────
  setNodeStatus: (id: string, status: WorkflowNodeData['status'], result?: any, error?: string) => void;
  setExecuting: (executing: boolean) => void;
  resetExecution: () => void;

  // ── Serialization ──────────────────────────────────────────
  clearCanvas: () => void;
  loadGraph: (nodes: WorkflowNode[], edges: WorkflowEdge[]) => void;
}

export const useWorkflowStore = create<WorkflowStore>((set, get) => ({
  nodes: [],
  edges: [],
  selectedNodeId: null,
  isPaletteOpen: true,
  isPanelOpen: false,
  isExecuting: false,

  onNodesChange: (changes) => {
    set({ nodes: applyNodeChanges(changes, get().nodes as any) as unknown as WorkflowNode[] });
  },

  onEdgesChange: (changes) => {
    set({ edges: applyEdgeChanges(changes, get().edges) });
  },

  onConnect: (connection: Connection) => {
    set({ edges: addEdge({ ...connection, type: 'workflow' }, get().edges) });
  },

  addNode: (node) => {
    const id = node.id || `node_${nanoid(8)}`;
    const newNode: WorkflowNode = { ...node, id } as WorkflowNode;
    set({ nodes: [...get().nodes, newNode] });
    return id;
  },

  removeNode: (id) => {
    set({
      nodes: get().nodes.filter((n) => n.id !== id),
      edges: get().edges.filter((e) => e.source !== id && e.target !== id),
      selectedNodeId: get().selectedNodeId === id ? null : get().selectedNodeId,
    });
  },

  updateNodeData: (id, data) => {
    set({
      nodes: get().nodes.map((n) =>
        n.id === id ? { ...n, data: { ...n.data, ...data } } : n
      ),
    });
  },

  selectNode: (id) => {
    set({ selectedNodeId: id, isPanelOpen: id !== null });
  },

  removeEdge: (id) => {
    set({ edges: get().edges.filter((e) => e.id !== id) });
  },

  togglePalette: () => set({ isPaletteOpen: !get().isPaletteOpen }),
  togglePanel: () => set({ isPanelOpen: !get().isPanelOpen }),
  setPanelOpen: (open) => set({ isPanelOpen: open }),

  setNodeStatus: (id, status, result, error) => {
    set({
      nodes: get().nodes.map((n) =>
        n.id === id ? { ...n, data: { ...n.data, status, result, error } } : n
      ),
    });
  },

  setExecuting: (executing) => set({ isExecuting: executing }),

  resetExecution: () => {
    set({
      nodes: get().nodes.map((n) => ({
        ...n,
        data: { ...n.data, status: 'idle' as const, result: undefined, error: undefined, durationMs: undefined },
      })),
      isExecuting: false,
    });
  },

  clearCanvas: () => set({ nodes: [], edges: [], selectedNodeId: null }),

  loadGraph: (nodes, edges) => set({ nodes, edges, selectedNodeId: null }),
}));
