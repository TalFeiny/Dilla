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
import type { CompanyDataSnapshot } from './assumptions';
import { canConnect, PORTS, type PortDef } from './port-types';

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

  // ── Company context (synced from Matrix Control Panel) ────
  companyId: string | null;
  fundId: string | null;
  companyName: string | null;

  // ── Company data (fetched via pull_company_data, available to ALL nodes) ──
  companyData: CompanyDataSnapshot | null;
  companyDataLoading: boolean;
  companyDataError: string | null;

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

  // ── Company context ─────────────────────────────────────────
  setCompanyContext: (companyId: string | null, fundId: string | null, companyName: string | null) => void;

  // ── Company data (pull_company_data) ──────────────────────
  fetchCompanyData: (companyId: string) => Promise<void>;

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

  // Company context — null until synced from Matrix Control Panel
  companyId: null,
  fundId: null,
  companyName: null,

  // Company data — null until fetched via pull_company_data
  companyData: null,
  companyDataLoading: false,
  companyDataError: null,

  onNodesChange: (changes) => {
    set({ nodes: applyNodeChanges(changes, get().nodes as any) as unknown as WorkflowNode[] });
  },

  onEdgesChange: (changes) => {
    set({ edges: applyEdgeChanges(changes, get().edges) });
  },

  onConnect: (connection: Connection) => {
    const nodes = get().nodes;
    const sourceNode = nodes.find((n) => n.id === connection.source);
    const targetNode = nodes.find((n) => n.id === connection.target);

    if (!sourceNode || !targetNode) {
      set({ edges: addEdge({ ...connection, type: 'workflow' }, get().edges) });
      return;
    }

    const srcData = sourceNode.data as unknown as WorkflowNodeData;
    const tgtData = targetNode.data as unknown as WorkflowNodeData;

    // Resolve the specific ports being connected (via handle IDs)
    const srcPort: PortDef | undefined =
      (srcData.outputPorts as PortDef[] | undefined)?.find((p) => p.id === connection.sourceHandle) ??
      (srcData.outputPorts as PortDef[] | undefined)?.[0];
    const tgtPort: PortDef | undefined =
      (tgtData.inputPorts as PortDef[] | undefined)?.find((p) => p.id === connection.targetHandle) ??
      (tgtData.inputPorts as PortDef[] | undefined)?.[0];

    // If both ports exist and they're incompatible → auto-insert a Transform node
    if (srcPort && tgtPort && !canConnect(srcPort, tgtPort)) {
      const transformId = `node_${nanoid(8)}`;

      // Position the transform midway between source and target
      const sx = sourceNode.position.x;
      const sy = sourceNode.position.y;
      const tx = targetNode.position.x;
      const ty = targetNode.position.y;

      const transformNode: WorkflowNode = {
        id: transformId,
        type: 'operator',
        position: { x: (sx + tx) / 2, y: (sy + ty) / 2 },
        data: {
          kind: 'operator',
          label: 'Transform',
          icon: 'ArrowLeftRight',
          domain: 'transform' as any,
          color: 'sky',
          operatorType: 'transform',
          params: { mapping: '', outputType: tgtPort.dataType },
          inputPorts: [PORTS.dataIn(true)],
          outputPorts: [PORTS.dataOut()],
          status: 'idle',
        } as any,
      };

      // Edge: source → transform (using source's handle → transform's data_in)
      const edgeA = {
        id: `edge_${nanoid(6)}`,
        source: connection.source!,
        target: transformId,
        sourceHandle: connection.sourceHandle ?? undefined,
        targetHandle: 'data_in',
        type: 'workflow',
      };

      // Edge: transform → target (transform's data_out → target's handle)
      const edgeB = {
        id: `edge_${nanoid(6)}`,
        source: transformId,
        target: connection.target!,
        sourceHandle: 'data_out',
        targetHandle: connection.targetHandle ?? undefined,
        type: 'workflow',
      };

      set({
        nodes: [...get().nodes, transformNode],
        edges: [...get().edges, edgeA, edgeB],
      });
      return;
    }

    // Compatible or untyped — connect directly
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
    set({ selectedNodeId: id });
    // Panel is now opened explicitly via double-click (setPanelOpen),
    // not automatically on single-click selection.
  },

  removeEdge: (id) => {
    set({ edges: get().edges.filter((e) => e.id !== id) });
  },

  togglePalette: () => set({ isPaletteOpen: !get().isPaletteOpen }),
  togglePanel: () => set({ isPanelOpen: !get().isPanelOpen }),
  setPanelOpen: (open) => set({ isPanelOpen: open }),

  setCompanyContext: (companyId, fundId, companyName) => {
    set({ companyId, fundId, companyName });
  },

  // ── Fetch company data via pull_company_data ────────────────
  fetchCompanyData: async (companyId: string) => {
    // Skip if already fetched for this company and less than 5 min old
    const existing = get().companyData;
    if (existing && existing.companyId === companyId && Date.now() - existing.fetchedAt < 5 * 60 * 1000) {
      return;
    }

    set({ companyDataLoading: true, companyDataError: null });

    try {
      const res = await fetch(`/api/fpa/company-data?company_id=${encodeURIComponent(companyId)}`);
      if (!res.ok) {
        const err = await res.json().catch(() => ({ error: 'Failed to fetch company data' }));
        throw new Error(err.error || err.detail || `HTTP ${res.status}`);
      }

      const data = await res.json();
      const snapshot: CompanyDataSnapshot = {
        companyId: data.company_id,
        timeSeries: data.time_series || {},
        latest: data.latest || {},
        periods: data.periods || [],
        analytics: data.analytics || {},
        metadata: data.metadata || { row_count: 0, categories: [] },
        fetchedAt: Date.now(),
      };

      set({ companyData: snapshot, companyDataLoading: false });
    } catch (e: any) {
      console.error('[WorkflowStore] Failed to fetch company data:', e);
      set({ companyDataError: e.message, companyDataLoading: false });
    }
  },

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
