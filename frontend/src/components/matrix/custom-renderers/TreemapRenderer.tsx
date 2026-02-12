'use client';

import React, { useMemo } from 'react';
import { ICellRendererParams } from 'ag-grid-community';
import { cn } from '@/lib/utils';

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
}

export const TreemapRenderer = React.memo(function TreemapRenderer(params: TreemapRendererParams) {
  const { 
    value, 
    data, 
    hierarchyField = 'sector',
    valueField = 'arr',
    maxDepth = 2,
    colorScheme = 'default'
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

  if (!treemapData || treemapData.value <= 0) {
    return <span className="text-muted-foreground text-xs">{value || '—'}</span>;
  }

  // Calculate color based on scheme
  const getColor = (val: number, maxVal: number) => {
    const ratio = val / maxVal;
    
    switch (colorScheme) {
      case 'risk':
        // Red to green: high value = low risk (green), low value = high risk (red)
        if (ratio > 0.7) return '#4CAF50'; // green
        if (ratio > 0.4) return '#FF9800'; // orange
        return '#F44336'; // red
      case 'growth':
        // Blue gradient: higher = more growth potential
        if (ratio > 0.7) return '#2196F3'; // blue
        if (ratio > 0.4) return '#64B5F6'; // light blue
        return '#BBDEFB'; // lighter blue
      case 'custom':
        // Use metadata color if available
        return data?.metadata?.color || '#4CAF50';
      default:
        // Default: green gradient
        if (ratio > 0.7) return '#4CAF50';
        if (ratio > 0.4) return '#8BC34A';
        return '#CDDC39';
    }
  };

  // For in-cell treemap, show a mini visualization
  const maxValue = 10000000; // This would ideally come from all data
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
    return squarifyLayout(data, width, height);
  }, [data, width, height]);

  return (
    <svg width={width} height={height} className="border rounded">
      {layout.map((rect, idx) => (
        <g key={idx}>
          <rect
            x={rect.x}
            y={rect.y}
            width={rect.width}
            height={rect.height}
            fill={rect.color || '#4CAF50'}
            stroke="#fff"
            strokeWidth={2}
            className="cursor-pointer hover:opacity-80"
            onClick={() => onNodeClick?.(rect.node)}
          />
          {rect.width > 60 && rect.height > 30 && (
            <text
              x={rect.x + rect.width / 2}
              y={rect.y + rect.height / 2}
              textAnchor="middle"
              dominantBaseline="middle"
              className="text-xs font-medium fill-white pointer-events-none"
            >
              {rect.node.name}
            </text>
          )}
        </g>
      ))}
    </svg>
  );
});

// Squarify treemap layout algorithm (simplified)
function squarifyLayout(nodes: TreemapNode[], width: number, height: number): Array<{
  x: number;
  y: number;
  width: number;
  height: number;
  color: string;
  node: TreemapNode;
}> {
  const totalValue = nodes.reduce((sum, node) => sum + node.value, 0);
  const rects: Array<{
    x: number;
    y: number;
    width: number;
    height: number;
    color: string;
    node: TreemapNode;
  }> = [];

  let x = 0;
  let y = 0;
  let remainingWidth = width;
  let remainingHeight = height;

  // Simple row-based layout
  nodes.forEach((node, idx) => {
    const ratio = node.value / totalValue;
    const nodeWidth = width * ratio;
    const nodeHeight = height * 0.1; // Fixed height per row

    rects.push({
      x,
      y,
      width: nodeWidth,
      height: nodeHeight,
      color: node.color || '#4CAF50',
      node,
    });

    x += nodeWidth;
    if (x >= width) {
      x = 0;
      y += nodeHeight;
    }
  });

  return rects;
}
