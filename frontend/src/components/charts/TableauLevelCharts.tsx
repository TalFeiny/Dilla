'use client';

import React, { useState, useMemo, useEffect, useRef } from 'react';
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
  LineChart,
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
  LabelList,
  Dot,
  PieChart,
  Pie
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
        'bubble' | 'gantt' | 'funnel' | 'radialBar' | 'streamgraph' | 'chord' | 'force' | 'side_by_side_sankey' | 'timeline_valuation' | 'probability_cloud' | 'pie';
  data: any;
  title?: string;
  subtitle?: string;
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
  subtitle,
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
  const [isClient, setIsClient] = useState(false);
  const [chartError, setChartError] = useState<string | null>(null);
  const [libsLoaded, setLibsLoaded] = useState(false);
  const [chartReady, setChartReady] = useState(false);
  const chartContainerRef = React.useRef<HTMLDivElement>(null);

  // Ensure we're on the client side and libraries are loaded
  useEffect(() => {
    setIsClient(true);
    
    // Check if D3 is available (it's imported as ES module, so it should be available if import succeeded)
    if (typeof window !== 'undefined') {
      try {
        // Since d3 is imported at module level, if the import succeeded, it will be available
        // Check if d3 is actually available and has expected properties
        if (!d3 || typeof d3 !== 'object') {
          setChartError('D3.js library not loaded. Please refresh the page.');
          return;
        }
        
        // Check if d3-sankey is available (for sankey charts)
        if (type === 'sankey' || type === 'side_by_side_sankey') {
          if (!d3Sankey || typeof d3Sankey !== 'function') {
            setChartError('D3-Sankey library not loaded. Please refresh the page.');
            return;
          }
        }
        
        setLibsLoaded(true);
        setChartError(null);
        console.log('[TableauLevelCharts] Libraries loaded successfully');
      } catch (error) {
        console.error('[TableauLevelCharts] Error checking libraries:', error);
        setChartError(`Library loading error: ${error instanceof Error ? error.message : 'Unknown error'}`);
      }
    }
  }, [type]);

  // Mark chart as ready when it's rendered
  useEffect(() => {
    if (!libsLoaded || chartError || !data || !chartContainerRef.current) {
      setChartReady(false);
      return;
    }

    // Use multiple checks with delays to ensure chart is fully rendered
    const checkInterval = setInterval(() => {
      if (chartContainerRef.current) {
        const hasContent = checkChartContent();
        if (hasContent) {
          setChartReady(true);
          chartContainerRef.current.setAttribute('data-chart-ready', 'true');
          clearInterval(checkInterval);
        }
      }
    }, 100); // Check every 100ms

    // Also check after a short delay using requestAnimationFrame
    requestAnimationFrame(() => {
      requestAnimationFrame(() => {
        if (chartContainerRef.current) {
          const hasContent = checkChartContent();
          if (hasContent) {
            setChartReady(true);
            chartContainerRef.current.setAttribute('data-chart-ready', 'true');
            clearInterval(checkInterval);
          }
        }
      });
    });

    // Timeout after 5 seconds
    const timeout = setTimeout(() => {
      clearInterval(checkInterval);
      // Even if content check fails, mark as ready after timeout to avoid blocking PDF generation
      if (chartContainerRef.current) {
        setChartReady(true);
        chartContainerRef.current.setAttribute('data-chart-ready', 'true');
      }
    }, 5000);

    return () => {
      clearInterval(checkInterval);
      clearTimeout(timeout);
    };
  }, [libsLoaded, chartError, data, type]);

  // Helper function to check if chart has rendered content
  const checkChartContent = (): boolean => {
    if (!chartContainerRef.current) return false;
    
    try {
      // Check for SVG charts (D3-based)
      if (['sankey', 'sunburst', 'heatmap', 'side_by_side_sankey', 'probability_cloud'].includes(type)) {
        const svg = chartContainerRef.current.querySelector('svg');
        if (svg && svg.children.length > 0) {
          // Check for actual content elements
          const hasContent = svg.querySelector('path, circle, rect, line, text, g') !== null;
          return hasContent;
        }
      }
      
      // Check for Recharts (SVG-based)
      if (['waterfall', 'bubble', 'funnel', 'radialBar', 'timeline_valuation'].includes(type)) {
        const svg = chartContainerRef.current.querySelector('.recharts-wrapper svg') || 
                    chartContainerRef.current.querySelector('svg');
        if (svg && svg.children.length > 0) {
          return true;
        }
      }
      
      // Check for canvas charts
      const canvas = chartContainerRef.current.querySelector('canvas');
      if (canvas) {
        try {
          const ctx = canvas.getContext('2d');
          if (ctx) {
            const imageData = ctx.getImageData(0, 0, Math.min(canvas.width, 10), Math.min(canvas.height, 10));
            const data = imageData.data;
            // Check if any pixels are non-transparent
            for (let i = 3; i < data.length; i += 4) {
              if (data[i] > 0) {
                return true;
              }
            }
          }
        } catch (e) {
          // Security error - assume rendered if canvas exists
          return true;
        }
      }
      
      return false;
    } catch (error) {
      console.error('[TableauLevelCharts] Error checking chart content:', error);
      return false;
    }
  };

  // Format financial numbers
  const formatValue = (value: number): string => {
    if (value >= 1e9) return `$${(value / 1e9).toFixed(2)}B`;
    if (value >= 1e6) return `$${(value / 1e6).toFixed(2)}M`;
    if (value >= 1e3) return `$${(value / 1e3).toFixed(0)}K`;
    return `$${value.toLocaleString()}`;
  };

  // Validate and normalize chart data to handle various input formats
  const validateChartData = (chartType: string, rawData: any): { valid: boolean; data: any; error?: string } => {
    try {
      // Handle null/undefined data
      if (!rawData) {
        return { valid: false, data: null, error: 'No data provided' };
      }

      // Normalize: extract data from nested structures like { data: {...} } or { chart_data: {...} }
      let normalizedData = rawData;
      if (typeof rawData === 'object' && !Array.isArray(rawData)) {
        normalizedData = rawData.data || rawData.chart_data || rawData;
      }

      switch (chartType) {
        case 'sankey':
        case 'side_by_side_sankey':
          if (typeof normalizedData !== 'object' || Array.isArray(normalizedData)) {
            return { valid: false, data: null, error: 'Sankey data must be an object with nodes and links' };
          }
          // Ensure nodes and links are arrays
          if (!normalizedData.nodes || !Array.isArray(normalizedData.nodes)) {
            return { valid: false, data: null, error: 'Sankey data must have nodes array' };
          }
          if (!normalizedData.links || !Array.isArray(normalizedData.links)) {
            return { valid: false, data: null, error: 'Sankey data must have links array' };
          }
          // Normalize nodes to ensure they have required properties
          const normalizedNodes = normalizedData.nodes.map((node: any, idx: number) => ({
            id: node.id || node.name || `node-${idx}`,
            name: node.name || node.id || `Node ${idx}`,
            ...node
          }));
          // Normalize links to ensure they reference node indices correctly
          const normalizedLinks = normalizedData.links.map((link: any) => ({
            source: typeof link.source === 'number' ? link.source : 
                   normalizedNodes.findIndex((n: any) => n.id === link.source || n.name === link.source),
            target: typeof link.target === 'number' ? link.target :
                   normalizedNodes.findIndex((n: any) => n.id === link.target || n.name === link.target),
            value: typeof link.value === 'number' ? link.value : parseFloat(link.value) || 0,
            ...link
          })).filter((link: any) => link.source >= 0 && link.target >= 0);
          
          return { 
            valid: true, 
            data: { nodes: normalizedNodes, links: normalizedLinks } 
          };
          
        case 'waterfall':
          // Accept both array format and object with data array
          const waterfallData = Array.isArray(normalizedData) ? normalizedData : 
                                (normalizedData.data || normalizedData);
          if (!Array.isArray(waterfallData)) {
            return { valid: false, data: null, error: 'Waterfall data must be an array of {name, value}' };
          }
          // Normalize values to numbers
          const normalizedWaterfall = waterfallData.map((item: any) => ({
            name: item.name || item.label || String(item),
            value: typeof item.value === 'number' ? item.value : parseFloat(item.value) || 0,
            ...item
          }));
          return { valid: true, data: normalizedWaterfall };
          
        case 'heatmap':
          // Handle backend format: {dimensions: [], companies: [], scores: [[]]}
          if (normalizedData && typeof normalizedData === 'object' && normalizedData.dimensions && normalizedData.companies && normalizedData.scores) {
            // Transform backend format to frontend format
            const dimensions = normalizedData.dimensions || [];
            const companies = normalizedData.companies || [];
            const scores = normalizedData.scores || [];
            
            const transformedData: Array<{x: string, y: string, value: number}> = [];
            for (let i = 0; i < companies.length; i++) {
              const companyScores = scores[i] || [];
              for (let j = 0; j < dimensions.length; j++) {
                transformedData.push({
                  x: companies[i],
                  y: dimensions[j],
                  value: typeof companyScores[j] === 'number' ? companyScores[j] : parseFloat(companyScores[j]) || 0
                });
              }
            }
            return { valid: true, data: transformedData };
          }
          
          // Handle frontend format: [{x, y, value}]
          const heatmapData = Array.isArray(normalizedData) ? normalizedData : 
                             (normalizedData.data || normalizedData);
          if (!Array.isArray(heatmapData)) {
            return { valid: false, data: null, error: 'Heatmap data must be an array of {x, y, value} or {dimensions, companies, scores} object' };
          }
          if (heatmapData.length > 0 && (!heatmapData[0].x || !heatmapData[0].y)) {
            return { valid: false, data: null, error: 'Heatmap data must have x, y, and value properties' };
          }
          // Normalize values
          const normalizedHeatmap = heatmapData.map((item: any) => ({
            x: item.x,
            y: item.y,
            value: typeof item.value === 'number' ? item.value : parseFloat(item.value) || 0,
            ...item
          }));
          return { valid: true, data: normalizedHeatmap };
          
        case 'pie':
          // Handle Chart.js format: {labels: [...], datasets: [{data: [...]}]}
          if (normalizedData && typeof normalizedData === 'object' && normalizedData.labels && normalizedData.datasets) {
            return { valid: true, data: normalizedData };
          }
          // Handle array format: [{name, value}]
          const pieData = Array.isArray(normalizedData) ? normalizedData : 
                         (normalizedData.data || normalizedData);
          if (!Array.isArray(pieData)) {
            return { valid: false, data: null, error: 'Pie chart data must be an array or Chart.js format' };
          }
          // Normalize values
          const normalizedPie = pieData.map((item: any) => ({
            name: item.name || item.label || String(item),
            value: typeof item.value === 'number' ? item.value : parseFloat(item.value) || 0,
            ...item
          }));
          return { valid: true, data: normalizedPie };
          
        case 'probability_cloud':
          // Validate probability cloud data structure
          if (!normalizedData || typeof normalizedData !== 'object') {
            return { valid: false, data: null, error: 'Probability cloud data must be an object' };
          }
          // Check for required fields
          const scenarios = normalizedData.scenario_curves || normalizedData.scenarios || [];
          if (!Array.isArray(scenarios) || scenarios.length === 0) {
            return { valid: false, data: null, error: 'Probability cloud must have at least one scenario curve' };
          }
          // Validate scenario structure
          for (const scenario of scenarios) {
            if (!scenario.return_curve || !scenario.return_curve.exit_values || !scenario.return_curve.return_multiples) {
              return { valid: false, data: null, error: 'Each scenario must have return_curve with exit_values and return_multiples' };
            }
            if (scenario.return_curve.exit_values.length !== scenario.return_curve.return_multiples.length) {
              return { valid: false, data: null, error: 'Scenario exit_values and return_multiples arrays must have same length' };
            }
          }
          // Validate breakpoint clouds if present
          const breakpointClouds = normalizedData.breakpoint_clouds || [];
          if (Array.isArray(breakpointClouds)) {
            for (const cloud of breakpointClouds) {
              if (cloud && (!cloud.p10_p90 || !cloud.p25_p75 || !cloud.median)) {
                return { valid: false, data: null, error: 'Breakpoint clouds must have p10_p90, p25_p75, and median' };
              }
            }
          }
          return { valid: true, data: normalizedData };
          
        default:
          // For other chart types, try to normalize common structures
          if (Array.isArray(normalizedData)) {
            return { valid: true, data: normalizedData };
          }
          if (typeof normalizedData === 'object' && normalizedData.data) {
            return { valid: true, data: normalizedData.data };
          }
          return { valid: true, data: normalizedData };
      }
    } catch (error) {
      return { valid: false, data: null, error: `Validation error: ${error instanceof Error ? error.message : String(error)}` };
    }
  };

  // Custom Sankey implementation using D3
  const renderSankey = (sankeyData?: any) => {
    // Check if D3 libraries are available (they're imported as ES modules)
    if (typeof window === 'undefined' || !d3 || !d3Sankey) {
      return (
        <div className="flex items-center justify-center h-full text-gray-500">
          <div className="text-center">
            <p>D3.js libraries not loaded</p>
            <p className="text-sm mt-2">Please refresh the page</p>
          </div>
        </div>
      );
    }

    // Use provided data or fall back to prop data
    const dataToUse = sankeyData || data;
    
    // Log the raw data for debugging
    console.log('[TableauLevelCharts] Sankey raw data:', JSON.stringify(dataToUse, null, 2));
    
    // Validate data structure
    const validation = validateChartData('sankey', dataToUse);
    console.log('[TableauLevelCharts] Sankey validation result:', validation);
    
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

    try {
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
        console.error('[TableauLevelCharts] Sankey chart generation error:', error);
        return (
          <div className="flex items-center justify-center h-full text-gray-500">
            <div className="text-center">
              <p>Error generating Sankey chart layout</p>
              <p className="text-sm mt-2">{error instanceof Error ? error.message : 'Unknown error'}</p>
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
    } catch (error) {
      console.error('[TableauLevelCharts] Sankey chart rendering error:', error);
      return (
        <div className="flex items-center justify-center h-full text-gray-500">
          <div className="text-center">
            <p>Error rendering Sankey chart</p>
            <p className="text-sm mt-2">{error instanceof Error ? error.message : 'Unknown error'}</p>
          </div>
        </div>
      );
    }
  };

  // Sunburst Chart using D3
  const renderSunburst = () => {
    // Check if D3 is available (imported as ES module)
    if (typeof window === 'undefined' || !d3) {
      return (
        <div className="flex items-center justify-center h-full text-gray-500">
          <div className="text-center">
            <p>D3.js library not loaded</p>
            <p className="text-sm mt-2">Please refresh the page</p>
          </div>
        </div>
      );
    }

    try {
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
    } catch (error) {
      console.error('[TableauLevelCharts] Sunburst chart error:', error);
      return (
        <div className="flex items-center justify-center h-full text-gray-500">
          <div className="text-center">
            <p>Error rendering Sunburst chart</p>
            <p className="text-sm mt-2">{error instanceof Error ? error.message : 'Unknown error'}</p>
          </div>
        </div>
      );
    }
  };

  // Heatmap implementation
  const renderHeatmap = () => {
    // Check if D3 is available (imported as ES module)
    if (typeof window === 'undefined' || !d3) {
      return (
        <div className="flex items-center justify-center h-full text-gray-500">
          <div className="text-center">
            <p>D3.js library not loaded</p>
            <p className="text-sm mt-2">Please refresh the page</p>
          </div>
        </div>
      );
    }

    // Log the raw data for debugging
    console.log('[TableauLevelCharts] Heatmap raw data:', JSON.stringify(data, null, 2));
    
    const validation = validateChartData('heatmap', data);
    console.log('[TableauLevelCharts] Heatmap validation result:', validation);
    
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
    
    try {
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
          
          {/* X axis labels - rotated to prevent cut-off */}
          {xLabels.map((label, i) => {
            const labelText = String(label);
            const needsRotation = labelText.length > 10;
            return (
              <text
                key={`x-${i}`}
                x={i * (700 / xLabels.length) + (700 / xLabels.length) / 2}
                y={needsRotation ? -15 : -5}
                textAnchor="middle"
                fontSize={needsRotation ? "10" : "12"}
                fontWeight="500"
                transform={needsRotation ? `rotate(-45 ${i * (700 / xLabels.length) + (700 / xLabels.length) / 2} -15)` : ''}
              >
                {labelText.length > 15 ? labelText.substring(0, 12) + '...' : labelText}
              </text>
            );
          })}
          
          {/* Y axis labels - with better spacing to prevent cut-off */}
          {yLabels.map((label, i) => {
            const labelText = String(label);
            return (
              <text
                key={`y-${i}`}
                x={-15}
                y={i * ((height - 70) / yLabels.length) + ((height - 70) / yLabels.length) / 2}
                dy="0.35em"
                textAnchor="end"
                fontSize={labelText.length > 15 ? "10" : "12"}
                fontWeight="500"
              >
                {labelText.length > 20 ? labelText.substring(0, 17) + '...' : labelText}
              </text>
            );
          })}
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
    } catch (error) {
      console.error('[TableauLevelCharts] Heatmap chart error:', error);
      return (
        <div className="flex items-center justify-center h-full text-gray-500">
          <div className="text-center">
            <p>Error rendering Heatmap chart</p>
            <p className="text-sm mt-2">{error instanceof Error ? error.message : 'Unknown error'}</p>
          </div>
        </div>
      );
    }
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

  // Pie Chart
  const renderPie = () => {
    const validation = validateChartData('pie', data);
    if (!validation.valid) {
      return (
        <div className="flex items-center justify-center h-full text-gray-500">
          <div className="text-center">
            <p>Invalid data format for Pie chart</p>
            <p className="text-sm mt-2">{validation.error}</p>
          </div>
        </div>
      );
    }
    
    try {
      const validData = validation.data;
      // Handle both Chart.js format (labels + datasets) and simple array format
      let pieData: Array<{name: string, value: number}> = [];
      
      if (validData.labels && validData.datasets && validData.datasets[0]) {
        // Chart.js format: {labels: [...], datasets: [{data: [...]}]}
        pieData = validData.labels.map((label: string, idx: number) => ({
          name: label,
          value: validData.datasets[0].data[idx] || 0
        }));
      } else if (Array.isArray(validData)) {
        // Array format: [{name, value}]
        pieData = validData.map((item: any) => ({
          name: item.name || item.label || String(item),
          value: typeof item.value === 'number' ? item.value : parseFloat(item.value) || 0
        }));
      } else {
        return (
          <div className="flex items-center justify-center h-full text-gray-500">
            <div className="text-center">
              <p>Pie chart data must be in Chart.js format or array format</p>
            </div>
          </div>
        );
      }
      
      return (
        <ResponsiveContainer width={width} height={height}>
          <PieChart>
            <Pie
              data={pieData}
              cx="50%"
              cy="50%"
              labelLine={false}
              label={({ name, percent }) => `${name}: ${(percent * 100).toFixed(1)}%`}
              outerRadius={Math.min(width === '100%' ? 150 : typeof width === 'number' ? width / 3 : 150, height / 2 - 20)}
              fill="#8884d8"
              dataKey="value"
            >
              {pieData.map((entry: any, index: number) => (
                <Cell key={`cell-${index}`} fill={colors[index % colors.length]} />
              ))}
            </Pie>
            <Tooltip formatter={(value: number, name: string) => `${value.toFixed(1)}%`} />
            <Legend />
          </PieChart>
        </ResponsiveContainer>
      );
    } catch (error) {
      console.error('[TableauLevelCharts] Pie chart error:', error);
      return (
        <div className="flex items-center justify-center h-full text-gray-500">
          <div className="text-center">
            <p>Error rendering Pie chart</p>
            <p className="text-sm mt-2">{error instanceof Error ? error.message : 'Unknown error'}</p>
          </div>
        </div>
      );
    }
  };

  // Render side-by-side Sankey diagrams
  const renderSideBySideSankey = () => {
    if (!data || !data.company1_data || !data.company2_data) {
      return (
        <div className="text-center p-8 bg-gray-50 rounded-lg">
          <p>No cap table data available</p>
        </div>
      );
    }

    return (
      <div className="grid grid-cols-2 gap-6">
        <div>
          <h4 className="text-center font-semibold mb-2">{data.company1_name || 'Company 1'}</h4>
          <div className="h-96">
            {renderSankey(data.company1_data)}
          </div>
        </div>
        <div>
          <h4 className="text-center font-semibold mb-2">{data.company2_name || 'Company 2'}</h4>
          <div className="h-96">
            {renderSankey(data.company2_data)}
          </div>
        </div>
      </div>
    );
  };

  // Render Probability Cloud Chart
  const renderProbabilityCloud = () => {
    // Extract data using correct keys from backend
    const scenarios = data?.scenario_curves || [];
    const breakpointClouds = data?.breakpoint_clouds || [];
    const decisionZones = data?.decision_zones || [];
    const insights = data?.insights || {};
    const config = data?.config || {};
    
    // Validate data - if no scenarios, show error
    if (!scenarios || scenarios.length === 0) {
      return (
        <div className="flex items-center justify-center h-full text-gray-500">
          <div className="text-center">
            <p>Probability cloud chart data is missing</p>
            <p className="text-sm mt-2">No scenario curves available</p>
          </div>
        </div>
      );
    }
    
    // Use props for dimensions instead of hardcoded values
    const chartWidth = typeof width === 'number' ? width : 800;
    const chartHeight = typeof height === 'number' ? height : 500;
    const margin = { top: 40, right: 120, bottom: 60, left: 80 };
    const innerWidth = chartWidth - margin.left - margin.right;
    const innerHeight = chartHeight - margin.top - margin.bottom;
    
    // Calculate dynamic domain from actual data if not provided in config
    const xConfig = config.x_axis || {};
    const yConfig = config.y_axis || {};
    
    // Extract exit values from scenarios to calculate domain
    let minExitValue = xConfig.min;
    let maxExitValue = xConfig.max;
    let minMultiple = yConfig.min;
    let maxMultiple = yConfig.max;
    
    if (!minExitValue || !maxExitValue) {
      const allExitValues: number[] = [];
      scenarios.forEach((scenario: any) => {
        if (scenario.return_curve?.exit_values) {
          allExitValues.push(...scenario.return_curve.exit_values);
        }
      });
      if (allExitValues.length > 0) {
        minExitValue = minExitValue || Math.min(...allExitValues) * 0.5;
        maxExitValue = maxExitValue || Math.max(...allExitValues) * 1.5;
      }
    }
    
    if (!minMultiple || !maxMultiple) {
      const allMultiples: number[] = [];
      scenarios.forEach((scenario: any) => {
        if (scenario.return_curve?.return_multiples) {
          allMultiples.push(...scenario.return_curve.return_multiples);
        }
      });
      if (allMultiples.length > 0) {
        minMultiple = minMultiple || Math.max(0, Math.min(...allMultiples) * 0.8);
        maxMultiple = maxMultiple || Math.max(...allMultiples) * 1.2;
      }
    }
    
    // Use calculated or default values
    const xMin = minExitValue || 10_000_000;
    const xMax = maxExitValue || 10_000_000_000;
    const yMin = minMultiple || 0;
    const yMax = maxMultiple || 50;
    
    const xScale = xConfig.type === 'log' ? d3.scaleLog() : d3.scaleLinear();
    xScale
      .domain([xMin, xMax])
      .range([0, innerWidth]);
    
    const yScale = d3.scaleLinear()
      .domain([yMin, yMax])
      .range([innerHeight, 0]);
    
    // Format functions
    const formatValue = (d: number) => {
      if (d >= 1e9) return `$${(d/1e9).toFixed(1)}B`;
      if (d >= 1e6) return `$${(d/1e6).toFixed(0)}M`;
      return `$${(d/1e3).toFixed(0)}K`;
    };
    
    const formatMultiple = (d: number) => `${d.toFixed(1)}x`;
    
    // Use scenario color from backend or calculate based on name
    const getScenarioColor = (scenario: any) => {
      if (scenario.color) return scenario.color;
      const name = scenario.name || '';
      if (name.includes('Unicorn') || name.includes('IPO')) return '#10B981'; // green
      if (name.includes('Strong') || name.includes('Strategic')) return '#3B82F6'; // blue
      if (name.includes('Base') || name.includes('PE')) return '#6366F1'; // indigo
      if (name.includes('Modest') || name.includes('Acquihire')) return '#F59E0B'; // amber
      if (name.includes('Downside') || name.includes('Distressed')) return '#EF4444'; // red
      return '#9CA3AF'; // gray
    };
    
    return (
      <div className="relative">
        <svg width={chartWidth} height={chartHeight}>
          <defs>
            {/* Gradient for probability bands */}
            <linearGradient id="prob-gradient" x1="0%" y1="0%" x2="0%" y2="100%">
              <stop offset="0%" stopColor="#3B82F6" stopOpacity="0.1" />
              <stop offset="50%" stopColor="#3B82F6" stopOpacity="0.3" />
              <stop offset="100%" stopColor="#3B82F6" stopOpacity="0.1" />
            </linearGradient>
          </defs>
          
          <g transform={`translate(${margin.left},${margin.top})`}>
            {/* Grid lines */}
            <g className="grid">
              {xScale.ticks(5).map(tick => (
                <line
                  key={tick}
                  x1={xScale(tick)}
                  x2={xScale(tick)}
                  y1={0}
                  y2={innerHeight}
                  stroke="#E5E7EB"
                  strokeDasharray="2,2"
                />
              ))}
              {yScale.ticks(5).map(tick => (
                <line
                  key={tick}
                  x1={0}
                  x2={innerWidth}
                  y1={yScale(tick)}
                  y2={yScale(tick)}
                  stroke="#E5E7EB"
                  strokeDasharray="2,2"
                />
              ))}
            </g>
            
            {/* Decision zones */}
            {decisionZones && Array.isArray(decisionZones) && decisionZones.map((zone: any, idx: number) => {
              if (!zone || !zone.range || !Array.isArray(zone.range) || zone.range.length < 2) return null;
              return (
                <rect
                  key={idx}
                  x={xScale(zone.range[0])}
                  y={0}
                  width={xScale(zone.range[1]) - xScale(zone.range[0])}
                  height={innerHeight}
                  fill={zone.color || '#9CA3AF'}
                  opacity={zone.opacity || 0.1}
                />
              );
            })}
            
            {/* Breakpoint probability bands */}
            {breakpointClouds && Array.isArray(breakpointClouds) && breakpointClouds.map((cloud: any) => {
              if (!cloud) return null;
              const [p10, p90] = cloud.p10_p90 || [0, 0];
              const [p25, p75] = cloud.p25_p75 || [0, 0];
              
              if (!p10 || !p90 || !p25 || !p75 || !cloud.median) return null;
              
              return (
                <g key={cloud.type} className="breakpoint-band">
                  {/* Wide band (p10-p90) */}
                  <rect
                    x={xScale(p10)}
                    y={0}
                    width={xScale(p90) - xScale(p10)}
                    height={innerHeight}
                    fill={cloud.color || '#3B82F6'}
                    opacity={0.05}
                  />
                  {/* Narrow band (p25-p75) */}
                  <rect
                    x={xScale(p25)}
                    y={0}
                    width={xScale(p75) - xScale(p25)}
                    height={innerHeight}
                    fill={cloud.color || '#3B82F6'}
                    opacity={0.1}
                  />
                  {/* Median line */}
                  <line
                    x1={xScale(cloud.median)}
                    x2={xScale(cloud.median)}
                    y1={0}
                    y2={innerHeight}
                    stroke={cloud.color || '#3B82F6'}
                    strokeWidth={2}
                    strokeDasharray="5,3"
                    opacity={0.5}
                  />
                  {/* Label */}
                  <text
                    x={xScale(cloud.median)}
                    y={-5}
                    textAnchor="middle"
                    fontSize="11"
                    fill={cloud.color}
                    fontWeight="600"
                  >
                    {cloud.label}
                  </text>
                </g>
              );
            })}
            
            {/* Scenario return curves */}
            {scenarios.map((scenario: any, idx: number) => {
              if (!scenario || !scenario.return_curve) return null;
              
              const exitValues = scenario.return_curve.exit_values;
              const returnMultiples = scenario.return_curve.return_multiples;
              
              if (!exitValues || !returnMultiples || exitValues.length !== returnMultiples.length) {
                return null;
              }
              
              const lineData = exitValues.map((exitVal: number, i: number) => ({
                x: exitVal,
                y: returnMultiples[i]
              }));
              
              if (lineData.length === 0) return null;
              
              const line = d3.line<any>()
                .x(d => xScale(d.x))
                .y(d => yScale(d.y))
                .curve(d3.curveMonotoneX);
              
              const pathData = line(lineData);
              if (!pathData) return null;
              
              return (
                <g key={idx} className="scenario-curve">
                  <path
                    d={pathData}
                    fill="none"
                    stroke={getScenarioColor(scenario)}
                    strokeWidth={2}
                    opacity={scenario.opacity || (0.3 + ((scenario.probability || 0.5) * 0.7))}
                  />
                  {/* Endpoint label if we have return curve data */}
                  {lineData.length > 0 && (
                    <g transform={`translate(${xScale(exitValues[exitValues.length - 1])},${yScale(lineData[lineData.length - 1]?.y || 0)})`}>
                      <circle
                        r={4}
                        fill={getScenarioColor(scenario)}
                        opacity={scenario.probability || 0.5}
                      />
                      <text
                        x={8}
                        y={0}
                        dy="0.3em"
                        fontSize="10"
                        fill={getScenarioColor(scenario)}
                        opacity={0.8}
                      >
                        {(scenario.name || '').split(' ').slice(0, 2).join(' ')}
                      </text>
                    </g>
                  )}
                </g>
              );
            })}
            
            {/* Axes */}
            <g className="x-axis" transform={`translate(0,${innerHeight})`}>
              {xScale.ticks(5).map(tick => (
                <g key={tick} transform={`translate(${xScale(tick)},0)`}>
                  <line y1={0} y2={6} stroke="#374151" />
                  <text y={20} textAnchor="middle" fontSize="12" fill="#374151">
                    {formatValue(tick)}
                  </text>
                </g>
              ))}
              <text x={innerWidth / 2} y={50} textAnchor="middle" fontSize="14" fontWeight="600" fill="#111827">
                Exit Value
              </text>
            </g>
            
            <g className="y-axis">
              {yScale.ticks(5).map(tick => (
                <g key={tick} transform={`translate(0,${yScale(tick)})`}>
                  <line x1={-6} x2={0} stroke="#374151" />
                  <text x={-10} dy="0.3em" textAnchor="end" fontSize="12" fill="#374151">
                    {formatMultiple(tick)}
                  </text>
                </g>
              ))}
              <text
                transform={`rotate(-90) translate(${-innerHeight/2},-50)`}
                textAnchor="middle"
                fontSize="14"
                fontWeight="600"
                fill="#111827"
              >
                Return Multiple
              </text>
            </g>
            
            {/* Legend */}
            <g transform={`translate(${innerWidth + 10}, 20)`}>
              <text fontSize="12" fontWeight="600" fill="#374151">Scenario Types</text>
              {[
                { color: '#10B981', label: 'IPO/Unicorn' },
                { color: '#3B82F6', label: 'Strategic Exit' },
                { color: '#6366F1', label: 'Base Case' },
                { color: '#F59E0B', label: 'Modest Exit' },
                { color: '#EF4444', label: 'Downside' }
              ].map((item, i) => (
                <g key={item.label} transform={`translate(0, ${20 + i * 20})`}>
                  <rect width={12} height={12} fill={item.color} opacity={0.7} />
                  <text x={16} y={9} fontSize="11" fill="#6B7280">{item.label}</text>
                </g>
              ))}
            </g>
          </g>
        </svg>
        
        {/* Key insights */}
        {insights && (
          <div className="mt-4 p-4 bg-blue-50 rounded-lg">
            <h4 className="font-semibold text-sm text-blue-900 mb-2">Key Insights</h4>
            <div className="grid grid-cols-3 gap-4 text-xs">
              {insights.probability_of_3x && (
                <div>
                  <span className="text-blue-700">P(3x return):</span>
                  <span className="ml-1 font-semibold">{(insights.probability_of_3x * 100).toFixed(0)}%</span>
                </div>
              )}
              {insights.expected_breakeven && (
                <div>
                  <span className="text-blue-700">Expected breakeven:</span>
                  <span className="ml-1 font-semibold">{formatValue(insights.expected_breakeven)}</span>
                </div>
              )}
              {insights.median_return && (
                <div>
                  <span className="text-blue-700">Median return:</span>
                  <span className="ml-1 font-semibold">{formatMultiple(insights.median_return)}</span>
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    );
  };

  // Render Timeline Valuation Chart
  const renderTimelineValuation = () => {
    // Prepare data for time-based chart
    const datasets = data?.datasets || [];
    const annotations = data?.annotations || [];
    
    // Combine all data points from all datasets for the chart
    const combinedData: any[] = [];
    const dateSet = new Set<string>();
    
    // Collect all unique dates
    datasets.forEach((dataset: any) => {
      dataset.data?.forEach((point: any) => {
        dateSet.add(point.x);
      });
    });
    
    // Sort dates chronologically
    const sortedDates = Array.from(dateSet).sort();
    
    // Create data points for each date
    sortedDates.forEach(date => {
      const dataPoint: any = { date };
      
      datasets.forEach((dataset: any) => {
        const point = dataset.data?.find((p: any) => p.x === date);
        if (point) {
          const key = dataset.label.replace(/\s+/g, '_');
          dataPoint[key] = point.y;
          dataPoint[`${key}_tooltip`] = point.tooltip || `${point.round}: $${point.y}M`;
          dataPoint[`${key}_ownership`] = point.ownership;
          dataPoint[`${key}_prorata`] = point.pro_rata;
          dataPoint[`${key}_historical`] = point.historical;
        }
      });
      
      combinedData.push(dataPoint);
    });
    
    // Custom dot for showing ownership percentage
    const CustomDot = (props: any) => {
      const { cx, cy, payload, dataKey } = props;
      const ownershipKey = dataKey.replace(/_/g, ' ').replace(' tooltip', '_ownership');
      const ownership = payload[ownershipKey];
      const historical = payload[`${dataKey.replace(/_/g, ' ').replace(' tooltip', '_historical')}`];
      
      if (ownership !== null && ownership !== undefined) {
        return (
          <g>
            <circle 
              cx={cx} 
              cy={cy} 
              r={6} 
              fill={historical ? "#4e79a7" : "#f28e2c"} 
              stroke="#fff" 
              strokeWidth={2}
            />
            <text 
              x={cx} 
              y={cy - 10} 
              fill="#333" 
              textAnchor="middle" 
              fontSize="10" 
              fontWeight="bold"
            >
              {ownership.toFixed(1)}%
            </text>
          </g>
        );
      }
      return <circle cx={cx} cy={cy} r={4} fill={historical ? "#4e79a7" : "#f28e2c"} />;
    };
    
    // Format date for display
    const formatDate = (dateStr: string) => {
      const date = new Date(dateStr);
      return date.toLocaleDateString('en-US', { month: 'short', year: 'numeric' });
    };
    
    // Custom tooltip
    const CustomTooltip = ({ active, payload, label }: any) => {
      if (active && payload && payload.length) {
        return (
          <div className="bg-white p-3 rounded-lg shadow-lg border border-gray-200">
            <p className="font-semibold text-sm mb-2">{formatDate(label)}</p>
            {payload.map((entry: any, index: number) => {
              const tooltipKey = `${entry.dataKey}_tooltip`;
              const ownershipKey = `${entry.dataKey}_ownership`;
              const prorataKey = `${entry.dataKey}_prorata`;
              const tooltipText = entry.payload[tooltipKey];
              const ownership = entry.payload[ownershipKey];
              const prorata = entry.payload[prorataKey];
              
              return (
                <div key={index} className="text-xs space-y-1">
                  <p style={{ color: entry.color }}>
                    <span className="font-semibold">{entry.name}:</span> ${entry.value}M
                  </p>
                  {tooltipText && <p className="text-gray-600">{tooltipText}</p>}
                  {ownership !== null && ownership !== undefined && (
                    <p className="text-gray-600">Ownership: {ownership.toFixed(1)}%</p>
                  )}
                  {prorata > 0 && (
                    <p className="text-gray-600">Pro-rata needed: ${(prorata / 1e6).toFixed(1)}M</p>
                  )}
                </div>
              );
            })}
          </div>
        );
      }
      return null;
    };
    
    return (
      <ResponsiveContainer width={width} height={height}>
        <LineChart data={combinedData} margin={{ top: 20, right: 30, left: 20, bottom: 60 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#e0e0e0" />
          <XAxis 
            dataKey="date" 
            tickFormatter={formatDate}
            angle={-45}
            textAnchor="end"
            height={60}
            style={{ fontSize: '12px' }}
          />
          <YAxis 
            label={{ 
              value: data?.y_axis_label || 'Valuation ($M)', 
              angle: -90, 
              position: 'insideLeft',
              style: { fontSize: '12px' }
            }}
            style={{ fontSize: '12px' }}
          />
          <Tooltip content={<CustomTooltip />} />
          <Legend 
            wrapperStyle={{ paddingTop: '20px' }}
            iconType="line"
          />
          
          {/* Render a line for each company */}
          {datasets.map((dataset: any, index: number) => {
            const dataKey = dataset.label.replace(/\s+/g, '_');
            return (
              <Line
                key={dataKey}
                type="monotone"
                dataKey={dataKey}
                name={dataset.label}
                stroke={dataset.borderColor || colors[index % colors.length]}
                strokeWidth={2}
                dot={<CustomDot />}
                activeDot={{ r: 8 }}
                connectNulls={true}
              />
            );
          })}
          
          {/* Add today marker if present in annotations */}
          {annotations?.map((annotation: any, index: number) => {
            if (annotation.type === 'line' && annotation.label?.content === 'Today') {
              return (
                <ReferenceLine
                  key={index}
                  x={annotation.value}
                  stroke={annotation.borderColor}
                  strokeDasharray={annotation.borderDash?.join(' ')}
                  label={{ value: annotation.label.content, position: 'top' }}
                />
              );
            }
            return null;
          })}
        </LineChart>
      </ResponsiveContainer>
    );
  };

  // Main render logic
  const renderChart = () => {
    // Validate data before rendering
    if (!data) {
      return (
        <div className="flex items-center justify-center h-full text-gray-500">
          <div className="text-center">
            <p>No data provided for chart</p>
          </div>
        </div>
      );
    }

    try {
      switch (type) {
        case 'sankey':
          return renderSankey();
        case 'side_by_side_sankey':
          return renderSideBySideSankey();
        case 'timeline_valuation':
          return renderTimelineValuation();
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
        case 'probability_cloud':
          return renderProbabilityCloud();
        default:
          return (
            <div className="flex items-center justify-center h-full text-gray-500">
              <div className="text-center">
                <p>Chart type "{type}" not supported</p>
              </div>
            </div>
          );
      }
    } catch (error) {
      console.error('[TableauLevelCharts] Error rendering chart:', error);
      return (
        <div className="flex items-center justify-center h-full text-red-500">
          <div className="text-center">
            <p className="font-semibold">Chart Rendering Error</p>
            <p className="text-sm mt-1">{error instanceof Error ? error.message : 'Unknown error'}</p>
          </div>
        </div>
      );
    }
  };

  // Show loading state while checking client-side
  if (!isClient) {
    return (
      <div className="bg-white p-6 rounded-xl shadow-lg border border-gray-100">
        <div className="flex items-center justify-center h-64">
          <div className="text-center">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mx-auto mb-2"></div>
            <p className="text-gray-500">Loading chart...</p>
          </div>
        </div>
      </div>
    );
  }

  // Show error if libraries failed to load
  if (chartError) {
    return (
      <div className="bg-white p-6 rounded-xl shadow-lg border border-red-200">
        {title && (
          <h3 className="text-xl font-bold text-gray-900 mb-4">{title}</h3>
        )}
        <div className="flex items-center justify-center h-64">
          <div className="text-center">
            <p className="text-red-600 font-semibold mb-2">Chart Library Error</p>
            <p className="text-red-500 text-sm">{chartError}</p>
            <p className="text-gray-500 text-xs mt-2">Please refresh the page or check your browser console.</p>
          </div>
        </div>
      </div>
    );
  }

  // Show loading state while libraries are being checked
  if (!libsLoaded) {
    return (
      <div className="bg-white p-6 rounded-xl shadow-lg border border-gray-100">
        {title && (
          <h3 className="text-xl font-bold text-gray-900 mb-4">{title}</h3>
        )}
        <div className="flex items-center justify-center h-64">
          <div className="text-center">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mx-auto mb-2"></div>
            <p className="text-gray-500">Loading chart libraries...</p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div 
      ref={chartContainerRef}
      className="bg-white p-6 rounded-xl shadow-lg border border-gray-100" 
      data-chart-type={type}
      data-chart-ready={chartReady ? 'true' : 'false'}
    >
      {title && (
        <div className="mb-4 flex items-center justify-between">
          <div>
            <h3 className="text-xl font-bold text-gray-900">
              {title}
              {/* Citation indicators */}
              {citations.length > 0 && showCitations && (
                <sup className="ml-1 text-blue-600 text-xs">
                  {citations.map(c => `[${c.number}]`).join(' ')}
                </sup>
              )}
            </h3>
            {subtitle && (
              <p className="text-sm text-gray-600 mt-1">{subtitle}</p>
            )}
          </div>
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