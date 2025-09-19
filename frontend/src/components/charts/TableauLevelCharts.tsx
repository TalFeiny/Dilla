'use client';

import React, { useState, useMemo } from 'react';
import {
  ResponsiveContainer,
  Sankey,
  Tooltip,
  Rectangle,
  Layer,
  Treemap,
  Cell,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Legend,
  ComposedChart,
  Line,
  Area,
  Scatter,
  ZAxis,
  ReferenceLine,
  ReferenceArea,
  Brush,
  RadialBarChart,
  RadialBar,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  FunnelChart,
  Funnel,
  LabelList
} from 'recharts';
import * as d3 from 'd3';
import { sankey as d3Sankey, sankeyLinkHorizontal } from 'd3-sankey';

interface Citation {
  id: number;
  number: number;
  source: string;
  date: string;
  title: string;
  content: string;
  url?: string;
  metadata?: Record<string, any>;
}

interface TableauChartProps {
  type: 'sankey' | 'sunburst' | 'heatmap' | 'waterfall' | 'boxplot' | 'candlestick' | 
        'bubble' | 'gantt' | 'funnel' | 'radialBar' | 'streamgraph' | 'chord' | 'force';
  data: any;
  title?: string;
  interactive?: boolean;
  colors?: string[];
  width?: number | string;
  height?: number;
  citations?: Citation[];
  showCitations?: boolean;
}

// Professional color schemes
const COLOR_SCHEMES = {
  tableau10: ['#4e79a7', '#f28e2c', '#e15759', '#76b7b2', '#59a14f', '#edc949', '#af7aa1', '#ff9da7', '#9c755f', '#bab0ab'],
  tableau20: ['#4e79a7', '#a0cbe8', '#f28e2c', '#ffbe7d', '#59a14f', '#8cd17d', '#b6992d', '#f1ce63', '#499894', '#86bcb6'],
  financialBlue: ['#08519c', '#3182bd', '#6baed6', '#9ecae1', '#c6dbef', '#deebf7', '#f7fbff'],
  financialGreen: ['#00441b', '#006d2c', '#238b45', '#41ab5d', '#74c476', '#a1d99b', '#c7e9c0'],
  heatmap: ['#ffffcc', '#ffeda0', '#fed976', '#feb24c', '#fd8d3c', '#fc4e2a', '#e31a1c', '#bd0026', '#800026'],
  diverging: ['#d73027', '#f46d43', '#fdae61', '#fee090', '#ffffbf', '#e0f3f8', '#abd9e9', '#74add1', '#4575b4'],
};

export default function TableauLevelCharts({
  type,
  data,
  title,
  interactive = true,
  colors = COLOR_SCHEMES.tableau10,
  width = '100%',
  height = 400,
  citations = [],
  showCitations = true
}: TableauChartProps) {

  const [selectedNode, setSelectedNode] = useState<any>(null);
  const [hoveredElement, setHoveredElement] = useState<any>(null);
  const [zoomLevel, setZoomLevel] = useState(1);
  const [filterValue, setFilterValue] = useState<string | null>(null);

  // Format financial numbers
  const formatValue = (value: number): string => {
    if (value >= 1e9) return `$${(value / 1e9).toFixed(2)}B`;
    if (value >= 1e6) return `$${(value / 1e6).toFixed(2)}M`;
    if (value >= 1e3) return `$${(value / 1e3).toFixed(0)}K`;
    return `$${value.toLocaleString()}`;
  };

  // Validate and normalize chart data
  const validateChartData = (chartType: string, rawData: any): { valid: boolean; data: any; error?: string } => {
    try {
      switch (chartType) {
        case 'sankey':
          if (!rawData || typeof rawData !== 'object') {
            return { valid: false, data: null, error: 'Data must be an object' };
          }
          // Handle both direct data and nested data.data structure
          const sankeyData = rawData.data || rawData;
          if (!sankeyData.nodes || !sankeyData.links || !Array.isArray(sankeyData.nodes) || !Array.isArray(sankeyData.links)) {
            return { valid: false, data: null, error: 'Expected { nodes: [...], links: [...] }' };
          }
          return { valid: true, data: sankeyData };
          
        case 'waterfall':
          // Accept both array format and object with data array
          const waterfallData = Array.isArray(rawData) ? rawData : (rawData.data || rawData);
          if (!Array.isArray(waterfallData)) {
            return { valid: false, data: null, error: 'Expected array of {name, value}' };
          }
          return { valid: true, data: waterfallData };
          
        case 'heatmap':
          const heatmapData = Array.isArray(rawData) ? rawData : (rawData.data || rawData);
          if (!Array.isArray(heatmapData) || (heatmapData.length > 0 && (!heatmapData[0].x || !heatmapData[0].y))) {
            return { valid: false, data: null, error: 'Expected array of {x, y, value}' };
          }
          return { valid: true, data: heatmapData };
          
        default:
          return { valid: true, data: rawData };
      }
    } catch (error) {
      return { valid: false, data: null, error: String(error) };
    }
  };

  // Custom Sankey implementation using D3
  const renderSankey = () => {
    // Validate data structure
    const validation = validateChartData('sankey', data);
    if (!validation.valid) {
      return (
        <div className="flex items-center justify-center h-full text-gray-500">
          <div className="text-center">
            <p>Invalid data format for Sankey chart</p>
            <p className="text-sm mt-2">{validation.error}</p>
          </div>
        </div>
      );
    }
    
    const validData = validation.data;

    const sankeyGenerator = d3Sankey()
      .nodeWidth(15)
      .nodePadding(10)
      .extent([[1, 1], [800 - 1, height - 6]]);

    let nodes, links;
    try {
      const result = sankeyGenerator({
        nodes: validData.nodes.map((d: any) => ({ ...d })),
        links: validData.links.map((d: any) => ({ ...d }))
      });
      nodes = result.nodes;
      links = result.links;
    } catch (error) {
      console.error('Sankey chart error:', error);
      return (
        <div className="flex items-center justify-center h-full text-gray-500">
          <div className="text-center">
            <p>Error rendering Sankey chart</p>
            <p className="text-sm mt-2">Check console for details</p>
          </div>
        </div>
      );
    }

    return (
      <svg width="100%" height={height} viewBox={`0 0 800 ${height}`}>
        <defs>
          {links.map((link: any, i: number) => (
            <linearGradient
              key={`gradient-${i}`}
              id={`gradient-${i}`}
              gradientUnits="userSpaceOnUse"
              x1={link.source.x1}
              x2={link.target.x0}
            >
              <stop offset="0%" stopColor={colors[link.source.index % colors.length]} stopOpacity={0.7} />
              <stop offset="100%" stopColor={colors[link.target.index % colors.length]} stopOpacity={0.7} />
            </linearGradient>
          ))}
        </defs>
        
        {/* Links */}
        <g className="links">
          {links.map((link: any, i: number) => (
            <path
              key={i}
              d={sankeyLinkHorizontal()(link) || ''}
              fill="none"
              stroke={`url(#gradient-${i})`}
              strokeWidth={Math.max(1, link.width)}
              opacity={hoveredElement === link ? 1 : 0.6}
              onMouseEnter={() => setHoveredElement(link)}
              onMouseLeave={() => setHoveredElement(null)}
              style={{ cursor: 'pointer', transition: 'opacity 0.3s' }}
            >
              <title>{`${link.source.name} → ${link.target.name}: ${formatValue(link.value)}`}</title>
            </path>
          ))}
        </g>
        
        {/* Nodes */}
        <g className="nodes">
          {nodes.map((node: any, i: number) => (
            <g key={i} transform={`translate(${node.x0},${node.y0})`}>
              <rect
                width={node.x1 - node.x0}
                height={node.y1 - node.y0}
                fill={colors[i % colors.length]}
                opacity={hoveredElement === node ? 1 : 0.8}
                stroke="#fff"
                strokeWidth={1}
                onMouseEnter={() => setHoveredElement(node)}
                onMouseLeave={() => setHoveredElement(null)}
                onClick={() => interactive && setSelectedNode(node)}
                style={{ cursor: 'pointer', transition: 'opacity 0.3s' }}
              >
                <title>{`${node.name}: ${formatValue(node.value)}`}</title>
              </rect>
              <text
                x={(node.x1 - node.x0) / 2}
                y={(node.y1 - node.y0) / 2}
                dy="0.35em"
                textAnchor="middle"
                fontSize="12"
                fill="#fff"
                fontWeight="600"
              >
                {node.name}
              </text>
              <text
                x={(node.x1 - node.x0) / 2}
                y={(node.y1 - node.y0) / 2 + 15}
                dy="0.35em"
                textAnchor="middle"
                fontSize="10"
                fill="#fff"
                opacity={0.9}
              >
                {formatValue(node.value)}
              </text>
            </g>
          ))}
        </g>
        
        {/* Interactive tooltip */}
        {hoveredElement && hoveredElement.source && (
          <g className="tooltip">
            <rect
              x={10}
              y={10}
              width={250}
              height={60}
              fill="white"
              stroke="#ccc"
              rx={5}
              opacity={0.95}
            />
            <text x={20} y={30} fontSize="12" fontWeight="bold">
              {hoveredElement.source.name} → {hoveredElement.target.name}
            </text>
            <text x={20} y={50} fontSize="14" fill={colors[0]}>
              {formatValue(hoveredElement.value)}
            </text>
          </g>
        )}
      </svg>
    );
  };

  // Sunburst Chart using D3
  const renderSunburst = () => {
    const radius = Math.min(400, height) / 2;
    
    const partition = d3.partition()
      .size([2 * Math.PI, radius]);
    
    const root = d3.hierarchy(data)
      .sum((d: any) => d.value)
      .sort((a: any, b: any) => b.value - a.value);
    
    partition(root);
    
    const arc = d3.arc()
      .startAngle((d: any) => d.x0)
      .endAngle((d: any) => d.x1)
      .innerRadius((d: any) => d.y0)
      .outerRadius((d: any) => d.y1);

    return (
      <svg width="100%" height={height} viewBox={`-${radius} -${radius} ${radius * 2} ${radius * 2}`}>
        <g>
          {root.descendants().map((d: any, i: number) => (
            <path
              key={i}
              d={arc(d) || ''}
              fill={colors[d.depth % colors.length]}
              opacity={hoveredElement === d ? 1 : 0.8}
              stroke="#fff"
              strokeWidth={2}
              onMouseEnter={() => setHoveredElement(d)}
              onMouseLeave={() => setHoveredElement(null)}
              onClick={() => interactive && setZoomLevel(d.depth + 1)}
              style={{ cursor: 'pointer', transition: 'all 0.3s' }}
            >
              <title>{`${d.data.name}: ${formatValue(d.value)}`}</title>
            </path>
          ))}
        </g>
        {root.descendants().filter((d: any) => d.depth === zoomLevel).map((d: any, i: number) => {
          const [x, y] = arc.centroid(d);
          return (
            <text
              key={`text-${i}`}
              x={x}
              y={y}
              fontSize="10"
              textAnchor="middle"
              fill="white"
              fontWeight="bold"
            >
              {d.data.name}
            </text>
          );
        })}
      </svg>
    );
  };

  // Heatmap implementation
  const renderHeatmap = () => {
    const validation = validateChartData('heatmap', data);
    if (!validation.valid) {
      return (
        <div className="flex items-center justify-center h-full text-gray-500">
          <div className="text-center">
            <p>Invalid data format for Heatmap</p>
            <p className="text-sm mt-2">{validation.error}</p>
          </div>
        </div>
      );
    }
    
    const validData = validation.data;
    const xLabels = [...new Set(validData.map((d: any) => d.x))];
    const yLabels = [...new Set(validData.map((d: any) => d.y))];
    const maxValue = Math.max(...validData.map((d: any) => d.value));
    
    const colorScale = d3.scaleSequential()
      .interpolator(d3.interpolateRdYlBu)
      .domain([maxValue, 0]);

    return (
      <svg width="100%" height={height} viewBox={`0 0 800 ${height}`}>
        <g transform="translate(50, 20)">
          {validData.map((d: any, i: number) => {
            const xIndex = xLabels.indexOf(d.x);
            const yIndex = yLabels.indexOf(d.y);
            const cellWidth = 700 / xLabels.length;
            const cellHeight = (height - 70) / yLabels.length;
            
            return (
              <g key={i}>
                <rect
                  x={xIndex * cellWidth}
                  y={yIndex * cellHeight}
                  width={cellWidth}
                  height={cellHeight}
                  fill={colorScale(d.value)}
                  stroke="#fff"
                  strokeWidth={1}
                  opacity={hoveredElement === d ? 1 : 0.9}
                  onMouseEnter={() => setHoveredElement(d)}
                  onMouseLeave={() => setHoveredElement(null)}
                  style={{ cursor: 'pointer', transition: 'opacity 0.3s' }}
                >
                  <title>{`${d.x}, ${d.y}: ${formatValue(d.value)}`}</title>
                </rect>
                <text
                  x={xIndex * cellWidth + cellWidth / 2}
                  y={yIndex * cellHeight + cellHeight / 2}
                  dy="0.35em"
                  textAnchor="middle"
                  fontSize="10"
                  fill={d.value > maxValue / 2 ? '#fff' : '#000'}
                  fontWeight="600"
                >
                  {d.value.toFixed(0)}
                </text>
              </g>
            );
          })}
          
          {/* X axis labels */}
          {xLabels.map((label, i) => (
            <text
              key={`x-${i}`}
              x={i * (700 / xLabels.length) + (700 / xLabels.length) / 2}
              y={-5}
              textAnchor="middle"
              fontSize="12"
              fontWeight="500"
            >
              {label}
            </text>
          ))}
          
          {/* Y axis labels */}
          {yLabels.map((label, i) => (
            <text
              key={`y-${i}`}
              x={-10}
              y={i * ((height - 70) / yLabels.length) + ((height - 70) / yLabels.length) / 2}
              dy="0.35em"
              textAnchor="end"
              fontSize="12"
              fontWeight="500"
            >
              {label}
            </text>
          ))}
        </g>
        
        {/* Color scale legend */}
        <g transform={`translate(760, 20)`}>
          <text x={0} y={-5} fontSize="10" fontWeight="bold">Scale</text>
          {[...Array(10)].map((_, i) => (
            <rect
              key={i}
              x={0}
              y={i * ((height - 70) / 10)}
              width={20}
              height={(height - 70) / 10}
              fill={colorScale(maxValue - (i * maxValue / 10))}
            />
          ))}
          <text x={25} y={10} fontSize="9">{maxValue.toFixed(0)}</text>
          <text x={25} y={height - 60} fontSize="9">0</text>
        </g>
      </svg>
    );
  };

  // Waterfall Chart
  const renderWaterfall = () => {
    const validation = validateChartData('waterfall', data);
    if (!validation.valid) {
      return (
        <div className="flex items-center justify-center h-full text-gray-500">
          <div className="text-center">
            <p>Invalid data format for Waterfall chart</p>
            <p className="text-sm mt-2">{validation.error}</p>
          </div>
        </div>
      );
    }
    
    let cumulative = 0;
    const processedData = validation.data.map((d: any) => {
      const start = cumulative;
      cumulative += d.value;
      return {
        ...d,
        start,
        end: cumulative,
        isPositive: d.value >= 0
      };
    });

    return (
      <ResponsiveContainer width={width} height={height}>
        <ComposedChart data={processedData}>
          <CartesianGrid strokeDasharray="3 3" stroke="#e0e0e0" />
          <XAxis 
            dataKey="name" 
            angle={-45}
            textAnchor="end"
            height={80}
            fontSize={11}
          />
          <YAxis tickFormatter={formatValue} fontSize={11} />
          <Tooltip 
            formatter={formatValue}
            contentStyle={{ 
              backgroundColor: 'rgba(255,255,255,0.95)',
              border: '1px solid #ccc',
              borderRadius: '8px'
            }}
          />
          <Bar dataKey="start" stackId="stack" fill="transparent" />
          <Bar 
            dataKey="value" 
            stackId="stack"
            shape={(props: any) => {
              const { x, y, width, height, payload } = props;
              const fillColor = payload.isPositive ? '#10b981' : '#ef4444';
              
              return (
                <g>
                  <rect
                    x={x}
                    y={y}
                    width={width}
                    height={Math.abs(height)}
                    fill={fillColor}
                    opacity={0.8}
                    stroke={fillColor}
                    strokeWidth={1}
                  />
                  <text
                    x={x + width / 2}
                    y={y - 5}
                    textAnchor="middle"
                    fontSize="10"
                    fontWeight="bold"
                    fill={fillColor}
                  >
                    {formatValue(payload.value)}
                  </text>
                </g>
              );
            }}
          />
          <Line
            type="stepAfter"
            dataKey="end"
            stroke="#6366f1"
            strokeWidth={2}
            strokeDasharray="5 5"
            dot={false}
          />
        </ComposedChart>
      </ResponsiveContainer>
    );
  };

  // Bubble Chart (3D Scatter)
  const renderBubble = () => {
    return (
      <ResponsiveContainer width={width} height={height}>
        <ComposedChart data={data}>
          <CartesianGrid strokeDasharray="3 3" stroke="#e0e0e0" />
          <XAxis dataKey="x" type="number" domain={['dataMin', 'dataMax']} />
          <YAxis dataKey="y" type="number" domain={['dataMin', 'dataMax']} />
          <ZAxis dataKey="z" type="number" range={[50, 400]} />
          <Tooltip
            content={({ active, payload }) => {
              if (active && payload && payload.length) {
                const data = payload[0].payload;
                return (
                  <div className="bg-white p-3 rounded-lg shadow-lg border">
                    <p className="font-bold">{data.name}</p>
                    <p>X: {data.x}</p>
                    <p>Y: {formatValue(data.y)}</p>
                    <p>Size: {formatValue(data.z)}</p>
                  </div>
                );
              }
              return null;
            }}
          />
          <Scatter 
            data={data} 
            fill={colors[0]}
            fillOpacity={0.6}
            shape={(props: any) => {
              const { cx, cy, payload } = props;
              const size = Math.sqrt(payload.z) * 2;
              
              return (
                <g>
                  <circle
                    cx={cx}
                    cy={cy}
                    r={size}
                    fill={colors[payload.category % colors.length]}
                    fillOpacity={0.6}
                    stroke={colors[payload.category % colors.length]}
                    strokeWidth={2}
                    onMouseEnter={() => setHoveredElement(payload)}
                    onMouseLeave={() => setHoveredElement(null)}
                    style={{ cursor: 'pointer' }}
                  />
                  {hoveredElement === payload && (
                    <text
                      x={cx}
                      y={cy}
                      textAnchor="middle"
                      fontSize="10"
                      fontWeight="bold"
                      fill="#000"
                    >
                      {payload.name}
                    </text>
                  )}
                </g>
              );
            }}
          />
        </ComposedChart>
      </ResponsiveContainer>
    );
  };

  // Funnel Chart
  const renderFunnel = () => {
    return (
      <ResponsiveContainer width={width} height={height}>
        <FunnelChart>
          <Tooltip formatter={formatValue} />
          <Funnel
            dataKey="value"
            data={data}
            isAnimationActive
            animationDuration={1000}
          >
            {data.map((entry: any, index: number) => (
              <Cell key={`cell-${index}`} fill={colors[index % colors.length]} />
            ))}
            <LabelList position="center" fill="#fff" fontSize={12} fontWeight="bold" />
          </Funnel>
        </FunnelChart>
      </ResponsiveContainer>
    );
  };

  // Radial Bar Chart
  const renderRadialBar = () => {
    const processedData = data.map((d: any, i: number) => ({
      ...d,
      fill: colors[i % colors.length]
    }));

    return (
      <ResponsiveContainer width={width} height={height}>
        <RadialBarChart 
          cx="50%" 
          cy="50%" 
          innerRadius="10%" 
          outerRadius="90%" 
          data={processedData}
        >
          <PolarGrid stroke="#e0e0e0" />
          <PolarAngleAxis type="number" domain={[0, 100]} />
          <PolarRadiusAxis angle={90} domain={[0, 100]} />
          <RadialBar
            dataKey="value"
            cornerRadius={10}
            fill="#8884d8"
            label={{ position: 'insideStart', fill: '#fff', fontSize: 12 }}
          />
          <Legend iconSize={18} layout="vertical" verticalAlign="middle" align="right" />
          <Tooltip formatter={formatValue} />
        </RadialBarChart>
      </ResponsiveContainer>
    );
  };

  // Main render logic
  const renderChart = () => {
    switch (type) {
      case 'sankey':
        return renderSankey();
      case 'sunburst':
        return renderSunburst();
      case 'heatmap':
        return renderHeatmap();
      case 'waterfall':
        return renderWaterfall();
      case 'bubble':
        return renderBubble();
      case 'funnel':
        return renderFunnel();
      case 'radialBar':
        return renderRadialBar();
      default:
        return <div>Chart type not supported</div>;
    }
  };

  return (
    <div className="bg-white p-6 rounded-xl shadow-lg border border-gray-100">
      {title && (
        <div className="mb-4 flex items-center justify-between">
          <h3 className="text-xl font-bold text-gray-900">
            {title}
            {/* Citation indicators */}
            {citations.length > 0 && showCitations && (
              <sup className="ml-1 text-blue-600 text-xs">
                {citations.map(c => `[${c.number}]`).join(' ')}
              </sup>
            )}
          </h3>
          {interactive && (
            <div className="flex gap-2">
              <button 
                onClick={() => setZoomLevel(1)}
                className="px-3 py-1 text-xs bg-blue-100 text-blue-700 rounded-lg hover:bg-blue-200"
              >
                Reset
              </button>
              <button 
                onClick={() => setFilterValue(null)}
                className="px-3 py-1 text-xs bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200"
              >
                Clear Filter
              </button>
            </div>
          )}
        </div>
      )}
      
      {renderChart()}
      
      {/* Citations section */}
      {citations.length > 0 && showCitations && (
        <div className="mt-4 p-3 bg-blue-50 rounded-lg border border-blue-100">
          <div className="text-xs text-blue-700 font-medium mb-1">Data Sources:</div>
          <div className="space-y-1">
            {citations.map(citation => (
              <div key={citation.number} className="text-xs text-blue-600 flex items-start gap-1">
                <span className="font-semibold">[{citation.number}]</span>
                <span>{citation.source} - {citation.date}</span>
                {citation.url && (
                  <a href={citation.url} target="_blank" rel="noopener noreferrer" 
                     className="hover:underline">
                    🔗
                  </a>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
      
      {/* Selected node details */}
      {selectedNode && interactive && (
        <div className="mt-4 p-4 bg-gray-50 rounded-lg">
          <h4 className="font-semibold text-sm text-gray-700">Selected: {selectedNode.name}</h4>
          <p className="text-sm text-gray-600">Value: {formatValue(selectedNode.value)}</p>
          {selectedNode.details && (
            <p className="text-xs text-gray-500 mt-1">{selectedNode.details}</p>
          )}
        </div>
      )}
    </div>
  );
}