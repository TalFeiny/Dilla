// ---------------------------------------------------------------------------
// Workflow Expression System — Variable Context + Resolution
// ---------------------------------------------------------------------------
// Provides typed variable references that flow between nodes.
// Variables use {{ path }} syntax, resolved at execution time.
//
// Sources:
//   1. Company data  — {{ row.revenue }}, {{ latest.ebitda }}, {{ periods[0] }}
//   2. Upstream nodes — {{ nodes.Forecast.revenue }}, {{ nodes.Filter.data }}
//   3. Loop vars      — {{ item }}, {{ index }}
//   4. Built-ins      — {{ company.id }}, {{ company.name }}, {{ today }}

import type { Node, Edge } from '@xyflow/react';
import type { WorkflowNodeData } from './types';
import type { CompanyDataSnapshot } from './assumptions';
import { getUpstreamFieldOptions, type FieldOption } from './upstream-fields';

// ── Variable definition ──────────────────────────────────────────────────────

export interface ExpressionVariable {
  /** Full path — e.g. "row.revenue", "nodes.Forecast.ebitda" */
  path: string;
  /** Display label */
  label: string;
  /** Source group for UI grouping */
  group: 'Company Data' | 'Upstream Nodes' | 'Loop Variables' | 'Built-in';
  /** Preview of current value */
  preview: string;
  /** Data type hint */
  type: 'number' | 'string' | 'array' | 'object' | 'boolean';
}

// ── Build all available variables for a node ─────────────────────────────────

export function buildExpressionVariables(
  nodeId: string,
  nodes: Node[],
  edges: Edge[],
  companyData: CompanyDataSnapshot | null,
  companyId: string | null,
  companyName: string | null,
): ExpressionVariable[] {
  const vars: ExpressionVariable[] = [];

  // ── 1. Company data rows ───────────────────────────────────────────────────

  if (companyData) {
    // Latest values (most common)
    for (const cat of companyData.metadata.categories) {
      const val = companyData.latest[cat];
      vars.push({
        path: `row.${cat}`,
        label: formatLabel(cat),
        group: 'Company Data',
        preview: val != null ? formatCompact(val) : 'no data',
        type: 'number',
      });
    }

    // Periods array
    if (companyData.periods.length > 0) {
      vars.push({
        path: 'periods',
        label: 'All Periods',
        group: 'Company Data',
        preview: `[${companyData.periods.length} periods]`,
        type: 'array',
      });
      vars.push({
        path: 'periods.current',
        label: 'Current Period',
        group: 'Company Data',
        preview: companyData.periods[companyData.periods.length - 1] || '',
        type: 'string',
      });
    }

    // Analytics
    for (const [key, val] of Object.entries(companyData.analytics)) {
      if (val == null) continue;
      vars.push({
        path: `analytics.${key}`,
        label: formatLabel(key),
        group: 'Company Data',
        preview: typeof val === 'number' ? formatCompact(val) : String(val),
        type: typeof val === 'number' ? 'number' : 'string',
      });
    }
  }

  // ── 2. Upstream node outputs ───────────────────────────────────────────────

  const upstreamGroups = getUpstreamFieldOptions(nodeId, nodes, edges);
  for (const group of upstreamGroups) {
    for (const field of group.fields) {
      vars.push({
        path: `nodes.${sanitizeLabel(group.sourceLabel)}.${field.path}`,
        label: `${group.sourceLabel} → ${field.label}`,
        group: 'Upstream Nodes',
        preview: field.preview,
        type: field.type,
      });
    }
  }

  // ── 3. Loop variables (if inside a loop) ───────────────────────────────────

  const loopParent = findLoopParent(nodeId, nodes, edges);
  if (loopParent) {
    const loopData = loopParent.data as unknown as WorkflowNodeData;
    const varName = loopData.params?.variable || 'item';
    vars.push({
      path: varName,
      label: `Loop item (${loopData.params?.loopOver || 'items'})`,
      group: 'Loop Variables',
      preview: `current ${loopData.params?.loopOver || 'item'}`,
      type: 'object',
    });
    vars.push({
      path: 'index',
      label: 'Loop index',
      group: 'Loop Variables',
      preview: '0, 1, 2...',
      type: 'number',
    });
  }

  // ── 4. Built-ins ───────────────────────────────────────────────────────────

  vars.push({
    path: 'company.id',
    label: 'Company ID',
    group: 'Built-in',
    preview: companyId || 'none',
    type: 'string',
  });
  vars.push({
    path: 'company.name',
    label: 'Company Name',
    group: 'Built-in',
    preview: companyName || 'none',
    type: 'string',
  });
  vars.push({
    path: 'today',
    label: 'Today',
    group: 'Built-in',
    preview: new Date().toISOString().slice(0, 10),
    type: 'string',
  });

  return vars;
}

// ── Extract {{ variable }} references from an expression string ──────────────

const VAR_REGEX = /\{\{\s*([^}]+?)\s*\}\}/g;

export function extractVariableRefs(expression: string): string[] {
  const refs: string[] = [];
  let match: RegExpExecArray | null;
  while ((match = VAR_REGEX.exec(expression)) !== null) {
    refs.push(match[1]);
  }
  return refs;
}

// ── Filter variables by search query ─────────────────────────────────────────

export function filterVariables(vars: ExpressionVariable[], query: string): ExpressionVariable[] {
  if (!query.trim()) return vars;
  const q = query.toLowerCase();
  return vars.filter(
    (v) => v.path.toLowerCase().includes(q) || v.label.toLowerCase().includes(q)
  );
}

// ── Group variables by their group field ─────────────────────────────────────

export function groupVariables(vars: ExpressionVariable[]): Map<string, ExpressionVariable[]> {
  const groups = new Map<string, ExpressionVariable[]>();
  for (const v of vars) {
    if (!groups.has(v.group)) groups.set(v.group, []);
    groups.get(v.group)!.push(v);
  }
  return groups;
}

// ── Helpers ──────────────────────────────────────────────────────────────────

function formatLabel(key: string): string {
  return key
    .replace(/_/g, ' ')
    .replace(/([a-z])([A-Z])/g, '$1 $2')
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

function formatCompact(v: number): string {
  const abs = Math.abs(v);
  const sign = v < 0 ? '-' : '';
  if (abs >= 1_000_000) return `${sign}$${(abs / 1_000_000).toFixed(1)}M`;
  if (abs >= 1_000) return `${sign}$${(abs / 1_000).toFixed(0)}k`;
  return `${sign}$${abs.toFixed(0)}`;
}

function sanitizeLabel(label: string): string {
  return label.replace(/[^a-zA-Z0-9_]/g, '_');
}

function findLoopParent(
  nodeId: string,
  nodes: Node[],
  edges: Edge[],
): Node | null {
  // Walk upstream to find a loop operator
  const visited = new Set<string>();
  const queue = [nodeId];

  while (queue.length > 0) {
    const current = queue.shift()!;
    if (visited.has(current)) continue;
    visited.add(current);

    for (const edge of edges) {
      if (edge.target === current) {
        const srcNode = nodes.find((n) => n.id === edge.source);
        if (!srcNode) continue;
        const srcData = srcNode.data as unknown as WorkflowNodeData;
        if (srcData.kind === 'operator' && srcData.operatorType === 'loop') {
          return srcNode;
        }
        queue.push(edge.source);
      }
    }
  }
  return null;
}
