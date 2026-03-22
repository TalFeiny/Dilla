// ---------------------------------------------------------------------------
// Upstream Field Extractor — powers the field picker in operator configs
// ---------------------------------------------------------------------------

import type { Node, Edge } from '@xyflow/react';
import type { WorkflowNodeData } from './types';

export interface FieldOption {
  /** Dot-path to the field (e.g. "revenue", "data.metrics.runway") */
  path: string;
  /** Human-readable label */
  label: string;
  /** Preview of the value (for context) */
  preview: string;
  /** JS type of the value */
  type: 'number' | 'string' | 'boolean' | 'object' | 'array';
}

/**
 * Extract all field paths from a result object, up to a max depth.
 * Returns flat dot-path entries with value previews.
 */
export function extractFieldPaths(
  obj: unknown,
  maxDepth = 3,
  prefix = '',
): FieldOption[] {
  if (obj == null || typeof obj !== 'object' || maxDepth <= 0) return [];

  // Don't recurse into arrays — treat them as leaf values
  if (Array.isArray(obj)) {
    return [];
  }

  const fields: FieldOption[] = [];

  for (const [key, value] of Object.entries(obj as Record<string, unknown>)) {
    // Skip internal/meta keys
    if (key.startsWith('_') || key === 'chip_id' || key === 'success') continue;

    const path = prefix ? `${prefix}.${key}` : key;
    const type = Array.isArray(value)
      ? 'array'
      : typeof value === 'number'
        ? 'number'
        : typeof value === 'boolean'
          ? 'boolean'
          : typeof value === 'string'
            ? 'string'
            : 'object';

    const preview = formatPreview(value);
    const label = formatLabel(key);

    fields.push({ path, label, preview, type });

    // Recurse into nested objects (not arrays)
    if (value && typeof value === 'object' && !Array.isArray(value)) {
      fields.push(...extractFieldPaths(value, maxDepth - 1, path));
    }
  }

  return fields;
}

/**
 * Get field options from all upstream nodes connected to a given node.
 * Returns fields grouped by source node label.
 */
export function getUpstreamFieldOptions(
  nodeId: string,
  nodes: Node[],
  edges: Edge[],
): { sourceLabel: string; sourceId: string; fields: FieldOption[] }[] {
  // Find all edges pointing into this node
  const incomingEdges = edges.filter((e) => e.target === nodeId);
  const groups: { sourceLabel: string; sourceId: string; fields: FieldOption[] }[] = [];

  for (const edge of incomingEdges) {
    const sourceNode = nodes.find((n) => n.id === edge.source);
    if (!sourceNode) continue;

    const data = sourceNode.data as unknown as WorkflowNodeData;
    if (data.status !== 'done' || !data.result) continue;

    const fields = extractFieldPaths(data.result);
    if (fields.length === 0) continue;

    groups.push({
      sourceLabel: data.label,
      sourceId: sourceNode.id,
      fields,
    });
  }

  return groups;
}

/**
 * Flatten all upstream fields into a single list for simple dropdowns.
 */
export function getUpstreamFieldsFlat(
  nodeId: string,
  nodes: Node[],
  edges: Edge[],
): FieldOption[] {
  const groups = getUpstreamFieldOptions(nodeId, nodes, edges);
  return groups.flatMap((g) => g.fields);
}

// ── Helpers ──────────────────────────────────────────────────────────────────

function formatPreview(value: unknown): string {
  if (value == null) return 'null';
  if (typeof value === 'number') {
    if (Math.abs(value) >= 1e6) return `${(value / 1e6).toFixed(1)}M`;
    if (Math.abs(value) >= 1e3) return `${(value / 1e3).toFixed(1)}K`;
    return value.toFixed(2);
  }
  if (typeof value === 'boolean') return value ? 'true' : 'false';
  if (typeof value === 'string') return value.length > 30 ? value.slice(0, 30) + '...' : value;
  if (Array.isArray(value)) return `[${value.length} items]`;
  if (typeof value === 'object') return `{${Object.keys(value as object).length} keys}`;
  return String(value);
}

function formatLabel(key: string): string {
  return key
    .replace(/_/g, ' ')
    .replace(/([a-z])([A-Z])/g, '$1 $2')
    .replace(/\b\w/g, (c) => c.toUpperCase());
}
