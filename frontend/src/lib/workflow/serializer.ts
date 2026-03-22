// ---------------------------------------------------------------------------
// Workflow Builder — Graph Serializer
// ---------------------------------------------------------------------------
// Topo-sorts the React Flow graph → ComposedWorkflow (same shape the backend
// already handles via chip_workflow).

import type { WorkflowNode, WorkflowEdge } from './store';
import type { WorkflowNodeData } from './types';
import type { ComposedWorkflow, WorkflowStep, ActiveChip, InputSegment } from '../chips/types';


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

/** Detailed upstream edge info for port-aware wiring */
interface UpstreamLink {
  sourceId: string;
  sourceHandle: string | null;
  targetHandle: string | null;
}

function getUpstreamLinks(nodeId: string, edges: WorkflowEdge[]): UpstreamLink[] {
  return edges
    .filter((e) => e.target === nodeId)
    .map((e) => ({
      sourceId: e.source,
      sourceHandle: (e.sourceHandle as string) ?? null,
      targetHandle: (e.targetHandle as string) ?? null,
    }));
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
      transform: 'tool',
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

    // Skip trigger nodes — they define the entry point, not an executable step
    if (data.kind === 'trigger') continue;

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
    const upstreamLinks = getUpstreamLinks(nodeId, edges);
    const driverOverrides: Record<string, any> = {};
    for (const upId of upstream) {
      const dv = driverValues.get(upId);
      if (dv) Object.assign(driverOverrides, dv);
    }

    const inputs: Record<string, any> = { ...data.params };

    // ── Port-aware input mapping ──────────────────────────────────────────
    // For each incoming edge, record which upstream node feeds which input port.
    // The backend uses `port_map` to route upstream step results into the
    // correct input parameter slots (e.g. forecast_in ← step_abc).
    const portMap: Record<string, string> = {};
    for (const link of upstreamLinks) {
      const upNode = nodeMap.get(link.sourceId);
      if (!upNode) continue;
      const upData = upNode.data as unknown as WorkflowNodeData;
      // Skip drivers — they're merged as driver_overrides, not port-mapped
      if (upData.kind === 'driver') continue;

      if (link.targetHandle) {
        // Map target handle id → upstream node id (so backend knows which
        // step result to pipe into which input param)
        portMap[link.targetHandle] = link.sourceId;
      }
    }
    if (Object.keys(portMap).length > 0) {
      inputs._port_map = portMap;
    }

    // Merge inline lever overrides from the node itself
    if (data.driverOverrides && Object.keys(data.driverOverrides).length > 0) {
      Object.assign(driverOverrides, data.driverOverrides);
    }
    if (Object.keys(driverOverrides).length > 0) {
      inputs.driver_overrides = driverOverrides;
    }

    // Row/subcategory targeting
    if (data.targetRows && data.targetRows.length > 0) {
      inputs.target_rows = data.targetRows;
    }

    // Period targeting
    if (data.targetPeriods && data.targetPeriods.length > 0) {
      inputs.target_periods = data.targetPeriods;
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

    // Separate _port_map from params — it's routing metadata, not a tool param
    const { _port_map, ...cleanParams } = step.inputs;

    const backendStep: Record<string, any> = {
      kind,
      tool: step.chip.def.tool,
      params: cleanParams,
      chip_id: step.id,  // node ID for result mapping
      depends_on: step.dependsOn || null,
    };

    // Port map tells the backend which upstream step result feeds each input slot
    if (_port_map && Object.keys(_port_map).length > 0) {
      backendStep.port_map = _port_map;
    }

    // Preserve operator_type so backend can distinguish data operators
    if (data?.kind === 'operator' && data.operatorType) {
      backendStep.operator_type = data.operatorType;
    }

    // Operator-specific fields the backend expects
    if (data?.operatorType === 'loop') {
      backendStep.loop_over = data.params.loopOver || 'companies';
      backendStep.loop_variable = data.params.variable || 'item';
    }
    if (data?.operatorType === 'conditional' || data?.operatorType === 'switch') {
      backendStep.condition_metric = data.params.metric || data.params.field || '';
      backendStep.condition_op = data.params.op || '>';
      if (data?.operatorType === 'conditional') {
        backendStep.condition_threshold = data.params.threshold ?? 0;
      }
      if (data?.operatorType === 'switch') {
        backendStep.switch_cases = data.params.cases || [];
      }
    }
    if (data?.operatorType === 'filter') {
      backendStep.filter_field = data.params.field || '';
      backendStep.filter_op = data.params.op || '>';
      backendStep.filter_value = data.params.value ?? 0;
    }
    if (data?.operatorType === 'aggregate') {
      backendStep.aggregate_fn = data.params.fn || 'sum';
      backendStep.aggregate_field = data.params.field || '';
      backendStep.aggregate_group_by = data.params.groupBy || null;
    }
    if (data?.operatorType === 'map') {
      backendStep.map_expression = data.params.expression || '';
      backendStep.map_output_field = data.params.outputField || null;
    }
    if (data?.operatorType === 'merge') {
      backendStep.merge_strategy = data.params.strategy || 'concat';
      backendStep.merge_join_key = data.params.joinKey || null;
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
    if (data?.operatorType === 'prior') {
      backendStep.prior_parameter = data.params.parameter || '';
      backendStep.prior_distribution = data.params.distribution || 'normal';
      backendStep.prior_low = data.params.low ?? 0;
      backendStep.prior_high = data.params.high ?? 0;
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
