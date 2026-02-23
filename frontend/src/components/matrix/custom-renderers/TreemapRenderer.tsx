'use client';

import React, { useMemo } from 'react';
import { ICellRendererParams } from 'ag-grid-community';

interface TreemapNode {
  name: string;
  value: number;
  children?: TreemapNode[];
  color?: string;
  metadata?: any;
}

interface TreemapRendererParams extends ICellRendererParams {
  hierarchyField?: string; // Field to use for hierarchy (e.g., 'sector', 'stage', 'fund')
  valueField?: string; // Field to use for value/size (e.g., 'arr', 'valuation')
  maxDepth?: number;
  colorScheme?: 'default' | 'risk' | 'growth' | 'custom';
  maxValue?: number; // Max value across all rows for proportional sizing
}

export const TreemapRenderer = React.memo(function TreemapRenderer(params: TreemapRendererParams) {
  const {
    value,
    data,
    api,
    hierarchyField = 'sector',
    valueField = 'arr',
    maxDepth = 2,
    colorScheme = 'default',
    maxValue: maxValueProp,
  } = params;

  // Build hierarchical structure from row data
  const treemapData = useMemo(() => {
    if (!data) return null;

    // Extract hierarchy path from data
    const hierarchyPath = data[hierarchyField]
      ? String(data[hierarchyField]).split(' > ').filter(Boolean)
      : ['Uncategorized'];

    // Get value for sizing
    const nodeValue = data[valueField]
      ? parseFloat(String(data[valueField]).replace(/[^0-9.-]/g, ''))
      : 0;

    return {
      path: hierarchyPath,
      value: nodeValue,
      name: data.companyName || value || 'Unknown',
      metadata: data,
    };
  }, [data, hierarchyField, valueField, value]);

  // Derive max value from all grid rows when not provided as prop
  const maxValue = useMemo(() => {
    if (maxValueProp && maxValueProp > 0) return maxValueProp;
    if (!api) return treemapData?.value || 1;

    let max = 0;
    api.forEachNode((node) => {
      if (node.data?.[valueField]) {
        const v = parseFloat(String(node.data[valueField]).replace(/[^0-9.-]/g, ''));
        if (v > max) max = v;
      }
    });
    return max || 1;
  }, [maxValueProp, api, valueField, treemapData?.value]);

  if (!treemapData || treemapData.value <= 0) {
    return <span className="text-muted-foreground text-xs">{value || '—'}</span>;
  }

  // Calculate color based on scheme
  const getColor = (val: number, maxVal: number) => {
    const ratio = val / maxVal;

    switch (colorScheme) {
      case 'risk':
        if (ratio > 0.7) return '#4CAF50';
        if (ratio > 0.4) return '#FF9800';
        return '#F44336';
      case 'growth':
        if (ratio > 0.7) return '#2196F3';
        if (ratio > 0.4) return '#64B5F6';
        return '#BBDEFB';
      case 'custom':
        return data?.metadata?.color || '#4CAF50';
      default:
        if (ratio > 0.7) return '#4CAF50';
        if (ratio > 0.4) return '#8BC34A';
        return '#CDDC39';
    }
  };

  const color = getColor(treemapData.value, maxValue);
  const percentage = Math.min(100, (treemapData.value / maxValue) * 100);

  return (
    <div className="flex items-center gap-2 w-full h-full px-2">
      {/* Mini treemap square */}
      <div
        className="relative rounded border-2 border-gray-300 overflow-hidden"
        style={{
          width: '32px',
          height: '32px',
          backgroundColor: color,
          opacity: 0.8,
        }}
        title={`${treemapData.name}: ${treemapData.value.toLocaleString()}`}
      >
        <div
          className="absolute inset-0 bg-white/20"
          style={{
            width: `${100 - percentage}%`,
            height: '100%',
            right: 0,
          }}
        />
      </div>

      {/* Value display */}
      <div className="flex-1 min-w-0">
        <div className="text-sm font-medium truncate">{treemapData.name}</div>
        <div className="text-xs text-muted-foreground">
          {treemapData.value.toLocaleString('en-US', {
            style: 'currency',
            currency: 'USD',
            maximumFractionDigits: 0,
          })}
        </div>
      </div>
    </div>
  );
});

// Full-page treemap component for expanded view
interface FullTreemapProps {
  data: TreemapNode[];
  width: number;
  height: number;
  onNodeClick?: (node: TreemapNode) => void;
}

export const FullTreemap = React.memo(function FullTreemap({ data, width, height, onNodeClick }: FullTreemapProps) {
  const layout = useMemo(() => {
    return squarify(data, { x: 0, y: 0, width, height });
  }, [data, width, height]);

  return (
    <svg width={width} height={height} className="border rounded">
      {layout.map((rect, idx) => {
        const showLabel = rect.width > 50 && rect.height > 24;
        const showValue = rect.width > 70 && rect.height > 38;
        return (
          <g key={idx}>
            <rect
              x={rect.x}
              y={rect.y}
              width={rect.width}
              height={rect.height}
              fill={rect.color}
              stroke="#fff"
              strokeWidth={2}
              className="cursor-pointer hover:opacity-80 transition-opacity"
              onClick={() => onNodeClick?.(rect.node)}
            />
            {showLabel && (
              <text
                x={rect.x + 6}
                y={rect.y + 16}
                className="text-xs font-medium fill-white pointer-events-none"
                style={{ textShadow: '0 1px 2px rgba(0,0,0,0.5)' }}
              >
                {rect.node.name.length > Math.floor(rect.width / 7)
                  ? rect.node.name.slice(0, Math.floor(rect.width / 7)) + '…'
                  : rect.node.name}
              </text>
            )}
            {showValue && (
              <text
                x={rect.x + 6}
                y={rect.y + 30}
                className="text-[10px] fill-white/80 pointer-events-none"
                style={{ textShadow: '0 1px 2px rgba(0,0,0,0.5)' }}
              >
                {formatCompact(rect.node.value)}
              </text>
            )}
          </g>
        );
      })}
    </svg>
  );
});

function formatCompact(n: number): string {
  if (n >= 1e9) return `$${(n / 1e9).toFixed(1)}B`;
  if (n >= 1e6) return `$${(n / 1e6).toFixed(1)}M`;
  if (n >= 1e3) return `$${(n / 1e3).toFixed(0)}K`;
  return `$${n.toFixed(0)}`;
}

// --- Squarify treemap layout (Bruls-Huizing-van Wijk) ---

interface Rect {
  x: number;
  y: number;
  width: number;
  height: number;
}

interface LayoutRect extends Rect {
  color: string;
  node: TreemapNode;
}

const DEFAULT_COLORS = [
  '#4CAF50', '#2196F3', '#FF9800', '#9C27B0', '#F44336',
  '#00BCD4', '#8BC34A', '#FF5722', '#3F51B5', '#CDDC39',
  '#E91E63', '#009688', '#FFC107', '#673AB7', '#795548',
];

function squarify(nodes: TreemapNode[], bounds: Rect): LayoutRect[] {
  if (!nodes.length || bounds.width <= 0 || bounds.height <= 0) return [];

  // Sort descending by value — squarify requires this
  const sorted = [...nodes]
    .filter((n) => n.value > 0)
    .sort((a, b) => b.value - a.value);

  if (!sorted.length) return [];

  const totalValue = sorted.reduce((s, n) => s + n.value, 0);
  const totalArea = bounds.width * bounds.height;

  // Normalize: each node gets area proportional to its value
  const areas = sorted.map((n) => (n.value / totalValue) * totalArea);

  const rects: LayoutRect[] = [];
  let remaining = { ...bounds };
  let i = 0;

  while (i < sorted.length) {
    const shortSide = Math.min(remaining.width, remaining.height);
    const { row, nextIndex } = layoutRow(areas, i, shortSide, remaining);

    // Place the row into rects
    const rowArea = row.reduce((s, a) => s + a, 0);
    const rowLength = rowArea / shortSide;
    const horizontal = remaining.width >= remaining.height;

    let offset = 0;
    for (let j = 0; j < row.length; j++) {
      const span = row[j] / rowLength;
      const nodeIdx = i + j;
      const color = sorted[nodeIdx].color || DEFAULT_COLORS[nodeIdx % DEFAULT_COLORS.length];

      if (horizontal) {
        rects.push({
          x: remaining.x,
          y: remaining.y + offset,
          width: rowLength,
          height: span,
          color,
          node: sorted[nodeIdx],
        });
      } else {
        rects.push({
          x: remaining.x + offset,
          y: remaining.y,
          width: span,
          height: rowLength,
          color,
          node: sorted[nodeIdx],
        });
      }
      offset += span;
    }

    // Shrink remaining bounds
    if (horizontal) {
      remaining = {
        x: remaining.x + rowLength,
        y: remaining.y,
        width: remaining.width - rowLength,
        height: remaining.height,
      };
    } else {
      remaining = {
        x: remaining.x,
        y: remaining.y + rowLength,
        width: remaining.width,
        height: remaining.height - rowLength,
      };
    }

    i = nextIndex;
  }

  return rects;
}

// Determine which nodes go in the current row by checking worst aspect ratio
function layoutRow(
  areas: number[],
  startIdx: number,
  shortSide: number,
  bounds: Rect,
): { row: number[]; nextIndex: number } {
  if (startIdx >= areas.length) return { row: [], nextIndex: startIdx };

  // If only one node left, take it
  if (startIdx === areas.length - 1) {
    return { row: [areas[startIdx]], nextIndex: startIdx + 1 };
  }

  const row: number[] = [areas[startIdx]];
  let bestWorst = worstAspectRatio(row, shortSide);

  for (let i = startIdx + 1; i < areas.length; i++) {
    const candidate = [...row, areas[i]];
    const candidateWorst = worstAspectRatio(candidate, shortSide);

    if (candidateWorst > bestWorst) {
      // Adding this node made aspect ratios worse — stop here
      break;
    }

    row.push(areas[i]);
    bestWorst = candidateWorst;
  }

  return { row, nextIndex: startIdx + row.length };
}

// Worst aspect ratio in a row laid along `shortSide`
function worstAspectRatio(row: number[], shortSide: number): number {
  const rowSum = row.reduce((s, a) => s + a, 0);
  const s2 = shortSide * shortSide;
  let worst = 0;

  for (const area of row) {
    // aspect ratio = max(w/h, h/w) where the row fills `shortSide`
    const r = Math.max(
      (s2 * area) / (rowSum * rowSum),
      (rowSum * rowSum) / (s2 * area),
    );
    if (r > worst) worst = r;
  }

  return worst;
}
