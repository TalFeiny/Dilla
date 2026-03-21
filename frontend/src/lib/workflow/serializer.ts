// ---------------------------------------------------------------------------
// Workflow Builder — Graph Serializer
// ---------------------------------------------------------------------------
// Topo-sorts the React Flow graph → ComposedWorkflow (same shape the backend
// already handles via chip_workflow).

import type { WorkflowNode, WorkflowEdge } from './store';
import type { WorkflowNodeData } from './types';
import type { ComposedWorkflow, WorkflowStep, ActiveChip, InputSegment } from '../chips/types';
import { nanoid } from 'nanoid';

/**
 * Topological sort of nodes based on edges.
 * Returns node IDs in execution order.
 */
function topoSort(nodes: WorkflowNode[], edges: WorkflowEdge[]): string[] {
  const inDegree = new Map<string, number>();
  const adjacency = new Map<string, string[]>();

  for (const node of nodes) {
    inDegree.set(node.id, 0);
    adjacency.set(node.id, []);
  }

  for (const edge of edges) {
    const prev = inDegree.get(edge.target) ?? 0;
    inDegree.set(edge.target, prev + 1);
    adjacency.get(edge.source)?.push(edge.target);
  }

  const queue: string[] = [];
  for (const [id, deg] of inDegree) {
    if (deg === 0) queue.push(id);
  }

  const sorted: string[] = [];
  while (queue.length > 0) {
    const current = queue.shift()!;
    sorted.push(current);

    for (const neighbor of adjacency.get(current) || []) {
      const newDeg = (inDegree.get(neighbor) ?? 1) - 1;
      inDegree.set(neighbor, newDeg);
      if (newDeg === 0) queue.push(neighbor);
    }
  }

  // If sorted doesn't include all nodes, there's a cycle — include remaining
  if (sorted.length < nodes.length) {
    for (const node of nodes) {
      if (!sorted.includes(node.id)) sorted.push(node.id);
    }
  }

  return sorted;
}

/**
 * Get the upstream node IDs for a given node (who feeds into it).
 */
function getUpstream(nodeId: string, edges: WorkflowEdge[]): string[] {
  return edges.filter((e) => e.target === nodeId).map((e) => e.source);
}

/**
 * Map frontend node kind + operatorType → backend step "kind".
 * Backend recognises: tool, formula, loop, conditional, bridge,
 *   assumption, event, prior, chart.
 */
function resolveBackendKind(data: WorkflowNodeData): string {
  if (data.kind === 'formula') return 'formula';
  if (data.kind === 'funding') return 'tool';
  if (data.kind === 'operator') {
    const opMap: Record<string, string> = {
      loop: 'loop',
      conditional: 'conditional',
      bridge: 'bridge',
      parallel: 'parallel',
      switch: 'conditional',  // switch treated as multi-conditional
      filter: 'tool',
      aggregate: 'tool',
      map: 'tool',
      merge: 'tool',
      event_business: 'event',
      event_macro: 'event',
      event_funding: 'event',
    };
    return opMap[data.operatorType || ''] || 'tool';
  }
  return 'tool';
}

/**
 * Serialize a React Flow graph into a ComposedWorkflow.
 * This output is compatible with the backend's chip_workflow execution path.
 */
export function graphToWorkflow(
  nodes: WorkflowNode[],
  edges: WorkflowEdge[]
): ComposedWorkflow {
  const sortedIds = topoSort(nodes, edges);
  const nodeMap = new Map(nodes.map((n) => [n.id, n]));

  const steps: WorkflowStep[] = [];
  const segments: InputSegment[] = [];

  // Track driver nodes — they get merged into downstream tool nodes
  const driverValues = new Map<string, Record<string, any>>();

  for (const nodeId of sortedIds) {
    const node = nodeMap.get(nodeId);
    if (!node) continue;

    const data = node.data as unknown as WorkflowNodeData;

    // Skip output nodes — they're for result routing, not execution
    if (data.kind === 'output') continue;

    // Driver nodes: collect their values for downstream merging
    if (data.kind === 'driver') {
      driverValues.set(nodeId, {
        [data.chipId?.replace(/^driver_/, '') || data.label.toLowerCase().replace(/\s+/g, '_')]: data.params.value,
      });
      continue;
    }

    // Build ActiveChip for this node
    const chipDef = data.chipDef || {
      id: data.chipId || data.operatorType || data.kind,
      label: data.label,
      domain: data.domain,
      icon: data.icon,
      description: '',
      tool: data.operatorType || data.kind,
      params: [],
      outputRenderer: 'raw' as const,
      costTier: 'cheap' as const,
      timeoutMs: 30000,
    };

    const activeChip: ActiveChip = {
      instanceId: nodeId,
      def: chipDef,
      values: { ...data.params },
    };

    // Collect driver overrides from upstream driver nodes
    const upstream = getUpstream(nodeId, edges);
    const driverOverrides: Record<string, any> = {};
    for (const upId of upstream) {
      const dv = driverValues.get(upId);
      if (dv) Object.assign(driverOverrides, dv);
    }

    const inputs: Record<string, any> = { ...data.params };
    if (Object.keys(driverOverrides).length > 0) {
      inputs.driver_overrides = driverOverrides;
    }

    // Find the first upstream non-driver node as dependency
    const dependsOn = upstream.find((id) => {
      const upNode = nodeMap.get(id);
      return upNode && (upNode.data as unknown as WorkflowNodeData).kind !== 'driver';
    });

    steps.push({
      id: nodeId,
      chip: activeChip,
      inputs,
      dependsOn,
    });

    // Build segments for display
    segments.push({
      type: 'chip',
      chip: activeChip,
    });
  }

  return {
    steps,
    nlContext: `Workflow with ${steps.length} steps`,
    segments,
  };
}

/**
 * Serialize steps into the shape the backend chip_workflow handler expects.
 * Backend needs: { kind, tool, params, depends_on, chip_id, ... }
 */
export function stepsToBackendShape(
  steps: WorkflowStep[],
  nodes: WorkflowNode[]
): Array<Record<string, any>> {
  const nodeMap = new Map(nodes.map((n) => [n.id, n]));

  return steps.map((step) => {
    const node = nodeMap.get(step.id);
    const data = node?.data as unknown as WorkflowNodeData | undefined;
    const kind = data ? resolveBackendKind(data) : 'tool';

    const backendStep: Record<string, any> = {
      kind,
      tool: step.chip.def.tool,
      params: step.inputs,
      chip_id: step.id,  // node ID for result mapping
      depends_on: step.dependsOn || null,
    };

    // Operator-specific fields the backend expects
    if (data?.operatorType === 'loop') {
      backendStep.loop_over = data.params.loopOver || 'companies';
    }
    if (data?.operatorType === 'conditional' || data?.operatorType === 'switch') {
      backendStep.condition_metric = data.params.metric || '';
      backendStep.condition_op = data.params.op || '>';
    }
    if (data?.operatorType === 'event_business') {
      backendStep.event_category = 'business';
    }
    if (data?.operatorType === 'event_macro') {
      backendStep.event_category = 'macro';
    }
    if (data?.operatorType === 'event_funding') {
      backendStep.event_category = 'funding';
    }

    return backendStep;
  });
}

/**
 * Get the output routing config — which output nodes exist and what format they want.
 */
export function getOutputRoutes(nodes: WorkflowNode[], edges: WorkflowEdge[]) {
  return nodes
    .filter((n) => (n.data as unknown as WorkflowNodeData).kind === 'output')
    .map((n) => {
      const data = n.data as unknown as WorkflowNodeData;
      const upstream = getUpstream(n.id, edges);
      return {
        nodeId: n.id,
        format: data.outputFormat || 'memo-section',
        sourceNodeIds: upstream,
        params: data.params,
      };
    });
}
