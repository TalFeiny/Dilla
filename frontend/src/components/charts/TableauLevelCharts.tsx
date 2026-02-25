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
  Pie,
  RadarChart,
  Radar,
  AreaChart,
  ScatterChart,
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
        'bubble' | 'gantt' | 'funnel' | 'radialBar' | 'streamgraph' | 'chord' | 'force' | 'side_by_side_sankey' | 'timeline_valuation' | 'probability_cloud' | 'pie' | 'line' | 'bar' | 'treemap' | 'scatter' | 'cap_table_waterfall' |
        'scatter_multiples' | 'breakpoint_chart' | 'dpi_sankey' | 'cap_table_evolution' | 'radar_comparison' | 'funnel_pipeline' |
        'scenario_tree' | 'scenario_paths' | 'tornado' | 'cash_flow_waterfall' |
        'bull_bear_base' | 'bar_comparison' | 'cap_table_sankey' | 'revenue_forecast' | 'fpa_stress_test' | 'stacked_bar' | 'nav_live' | 'market_map' |
        'sensitivity_tornado' | 'regression_line' | 'monte_carlo_histogram' | 'revenue_forecast_decay' | 'fund_scenarios' | 'multi_chart' | 'ltm_ntm_regression';
  data: any;
  title?: string;
  subtitle?: string;
  interactive?: boolean;
  colors?: string[];
  width?: number | `${number}%`;
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

/** Extracted as a proper component so hooks (useRef, useEffect) are legal. */
function CapTableWaterfallInner({ data, width, height }: { data: any; width: number | string; height?: number }) {
  const chartRef = React.useRef<HTMLDivElement>(null);

  React.useEffect(() => {
    if (!chartRef.current || !d3) return;
    const container = chartRef.current;
    d3.select(container).selectAll('*').remove();

    const evolution: any[] = Array.isArray(data) ? data : data?.cap_table_evolution || data?.evolution || [];
    if (evolution.length === 0) {
      d3.select(container).append('p').text('No cap table evolution data').attr('class', 'text-gray-500 text-center');
      return;
    }

    const margin = { top: 30, right: 20, bottom: 50, left: 50 };
    const w = (typeof width === 'number' ? width : container.clientWidth || 500) - margin.left - margin.right;
    const h = (height || 320) - margin.top - margin.bottom;

    const svg = d3.select(container).append('svg')
      .attr('width', w + margin.left + margin.right)
      .attr('height', h + margin.top + margin.bottom)
      .append('g')
      .attr('transform', `translate(${margin.left},${margin.top})`);

    const keys = ['our_ownership', 'founders_pct', 'esop_pct', 'other_investors_pct'];
    const keysPresent = keys.filter(k => evolution.some(e => e[k] != null));
    const labels: Record<string, string> = {
      our_ownership: 'Our Ownership',
      founders_pct: 'Founders',
      esop_pct: 'ESOP',
      other_investors_pct: 'Other Investors',
    };

    const stackData = evolution.map((e: any) => {
      const d: Record<string, any> = { round: e.round || e.name || '' };
      keysPresent.forEach(k => { d[k] = (e[k] ?? 0) * (e[k] > 1 ? 1 : 100); });
      return d;
    });

    const x = d3.scaleBand().domain(stackData.map(d => d.round)).range([0, w]).padding(0.3);
    const y = d3.scaleLinear().domain([0, 100]).range([h, 0]);

    const stack = d3.stack().keys(keysPresent);
    const series = stack(stackData as any);

    const colorScale = d3.scaleOrdinal<string>()
      .domain(keysPresent)
      .range(['#4e79a7', '#59a14f', '#edc949', '#e15759']);

    svg.selectAll('g.series')
      .data(series)
      .join('g')
      .attr('class', 'series')
      .attr('fill', (d: any) => colorScale(d.key))
      .selectAll('rect')
      .data((d: any) => d)
      .join('rect')
      .attr('x', (d: any) => x(d.data.round) ?? 0)
      .attr('y', (d: any) => y(d[1]))
      .attr('height', (d: any) => y(d[0]) - y(d[1]))
      .attr('width', x.bandwidth())
      .attr('rx', 2);

    svg.append('g').attr('transform', `translate(0,${h})`).call(d3.axisBottom(x))
      .selectAll('text').attr('font-size', '10px');

    svg.append('g').call(d3.axisLeft(y).ticks(5).tickFormat((d: any) => `${d}%`))
      .selectAll('text').attr('font-size', '10px');

    const legend = svg.append('g').attr('transform', `translate(0, -15)`);
    keysPresent.forEach((k, i) => {
      const g = legend.append('g').attr('transform', `translate(${i * 120}, 0)`);
      g.append('rect').attr('width', 10).attr('height', 10).attr('fill', colorScale(k)).attr('rx', 2);
      g.append('text').attr('x', 14).attr('y', 9).text(labels[k] || k).attr('font-size', '10px').attr('fill', '#666');
    });
  }, [data, width, height]);

  return <div ref={chartRef} style={{ width: '100%', height: height || 320 }} />;
}

/** DPI Sankey helper: renders a D3-based Sankey diagram for fund distribution flows. */
function TableauLevelChartsSankeyHelper({ data, width, height, colors }: { data: any; width: number | string; height?: number; colors: string[] }) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!ref.current || !d3 || !d3Sankey) return;
    const container = ref.current;
    d3.select(container).selectAll('*').remove();

    const nodes = data.nodes || [];
    const links = data.links || [];
    if (!nodes.length || !links.length) return;

    const margin = { top: 10, right: 10, bottom: 10, left: 10 };
    const w = (typeof width === 'number' ? width : container.clientWidth || 600) - margin.left - margin.right;
    const h = (height || 400) - margin.top - margin.bottom;

    const svg = d3.select(container).append('svg')
      .attr('width', w + margin.left + margin.right)
      .attr('height', h + margin.top + margin.bottom)
      .append('g')
      .attr('transform', `translate(${margin.left},${margin.top})`);

    const sankeyLayout = d3Sankey()
      .nodeWidth(20)
      .nodePadding(12)
      .extent([[0, 0], [w, h]]);

    const graph = sankeyLayout({
      nodes: nodes.map((n: any) => ({ ...n })),
      links: links.map((l: any) => ({ ...l })),
    });

    // Links
    svg.append('g')
      .selectAll('path')
      .data(graph.links)
      .join('path')
      .attr('d', sankeyLinkHorizontal())
      .attr('fill', 'none')
      .attr('stroke', (d: any) => d.color || '#4e79a7')
      .attr('stroke-opacity', 0.4)
      .attr('stroke-width', (d: any) => Math.max(1, d.width));

    // Nodes
    svg.append('g')
      .selectAll('rect')
      .data(graph.nodes)
      .join('rect')
      .attr('x', (d: any) => d.x0)
      .attr('y', (d: any) => d.y0)
      .attr('height', (d: any) => Math.max(1, d.y1 - d.y0))
      .attr('width', (d: any) => d.x1 - d.x0)
      .attr('fill', (_d: any, i: number) => colors[i % colors.length])
      .attr('rx', 2);

    // Labels
    svg.append('g')
      .selectAll('text')
      .data(graph.nodes)
      .join('text')
      .attr('x', (d: any) => d.x0 < w / 2 ? d.x1 + 6 : d.x0 - 6)
      .attr('y', (d: any) => (d.y1 + d.y0) / 2)
      .attr('dy', '0.35em')
      .attr('text-anchor', (d: any) => d.x0 < w / 2 ? 'start' : 'end')
      .attr('font-size', '10px')
      .attr('fill', '#333')
      .text((d: any) => d.name);
  }, [data, width, height, colors]);

  return <div ref={ref} style={{ width: '100%', height: height || 400 }} />;
}

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
        if (type === 'sankey' || type === 'side_by_side_sankey' || type === 'dpi_sankey') {
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
          
          // Need at least 2 nodes and 1 link for a meaningful sankey
          if (normalizedNodes.length < 2 || normalizedLinks.length < 1) {
            return { valid: false, data: null, error: 'Sankey chart requires at least 2 nodes and 1 link' };
          }

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
          
        case 'scenario_tree':
          if (!normalizedData || typeof normalizedData !== 'object') {
            return { valid: false, data: null, error: 'Scenario tree data must be an object with nodes and edges' };
          }
          const treeNodes = normalizedData.nodes || [];
          const treeEdges = normalizedData.edges || [];
          if (!Array.isArray(treeNodes) || treeNodes.length === 0) {
            return { valid: false, data: null, error: 'Scenario tree must have at least one node' };
          }
          return { valid: true, data: normalizedData };

        case 'scenario_paths':
          if (!normalizedData || typeof normalizedData !== 'object') {
            return { valid: false, data: null, error: 'Scenario paths data must be an object with series' };
          }
          const pathSeries = normalizedData.series || [];
          if (!Array.isArray(pathSeries) || pathSeries.length === 0) {
            return { valid: false, data: null, error: 'Scenario paths must have at least one series' };
          }
          return { valid: true, data: normalizedData };

        case 'tornado':
        case 'sensitivity_tornado':
          const tornadoItems = Array.isArray(normalizedData) ? normalizedData : (normalizedData.items || normalizedData.data || []);
          if (!Array.isArray(tornadoItems) || tornadoItems.length === 0) {
            return { valid: false, data: null, error: 'Tornado data must be an array of {name, low, high, base}' };
          }
          return { valid: true, data: tornadoItems };

        case 'regression_line':
        case 'monte_carlo_histogram':
        case 'revenue_forecast_decay':
          // These use labels+datasets shape — same validation as line/bar
          if (normalizedData?.labels && normalizedData?.datasets) {
            return { valid: true, data: normalizedData };
          }
          if (normalizedData?.datasets) {
            return { valid: true, data: normalizedData };
          }
          return { valid: false, data: null, error: `${chartType} data must have labels and datasets` };

        case 'cash_flow_waterfall':
          const cfwData = Array.isArray(normalizedData) ? normalizedData : (normalizedData.data || normalizedData);
          if (!Array.isArray(cfwData)) {
            return { valid: false, data: null, error: 'Cash flow waterfall data must be an array of {name, value}' };
          }
          const normalizedCFW = cfwData.map((item: any) => ({
            name: item.name || item.label || String(item),
            value: typeof item.value === 'number' ? item.value : parseFloat(item.value) || 0,
            isSubtotal: item.isSubtotal || false,
            ...item
          }));
          return { valid: true, data: normalizedCFW };

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

  // Sankey chart — delegates to the D3-based TableauLevelChartsSankeyHelper
  const renderSankey = (sankeyData?: any) => {
    const dataToUse = sankeyData || data;
    const validation = validateChartData('sankey', dataToUse);
    if (!validation.valid) {
      return (
        <div className="flex items-center justify-center h-full text-gray-500">
          <div className="text-center">
            <p>{validation.error || 'Invalid Sankey data'}</p>
          </div>
        </div>
      );
    }
    return (
      <div style={{ width: '100%', height: height, position: 'relative' }}>
        <TableauLevelChartsSankeyHelper data={validation.data} width={width} height={height} colors={colors} />
      </div>
    );
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

  // Scatter Chart (growth vs valuation multiple)
  const renderScatterChart = () => {
    const points = Array.isArray(data) ? data : (data?.data || data?.points || []);
    if (!Array.isArray(points) || !points.length) {
      return (
        <div className="flex items-center justify-center h-full text-gray-500">
          <p>No data for scatter chart</p>
        </div>
      );
    }
    return (
      <ResponsiveContainer width="100%" height={height}>
        <ComposedChart margin={{ top: 20, right: 20, bottom: 20, left: 20 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#e0e0e0" />
          <XAxis dataKey="x" type="number" name="Growth %" />
          <YAxis dataKey="y" type="number" name="Valuation Multiple" />
          <Tooltip
            content={({ active, payload }) => {
              if (active && payload && payload.length) {
                const p = payload[0].payload;
                return (
                  <div className="bg-white p-3 rounded-lg shadow-lg border text-sm">
                    <p className="font-bold">{p.name}</p>
                    <p>Growth: {p.x}%</p>
                    <p>Valuation Multiple: {p.y}x</p>
                  </div>
                );
              }
              return null;
            }}
          />
          <Scatter data={points} fill={colors[0]} fillOpacity={0.7} />
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
    const funnelData = Array.isArray(data) ? data : Array.isArray(data?.data) ? data.data : [];
    if (funnelData.length === 0) {
      return (
        <div className="flex items-center justify-center h-full text-gray-500">
          <p>Funnel chart requires an array of data items</p>
        </div>
      );
    }
    return (
      <ResponsiveContainer width={width} height={height}>
        <FunnelChart>
          <Tooltip formatter={formatValue} />
          <Funnel
            dataKey="value"
            data={funnelData}
            isAnimationActive
            animationDuration={1000}
          >
            {funnelData.map((_entry: any, index: number) => (
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
    const radialData = Array.isArray(data) ? data : Array.isArray(data?.data) ? data.data : [];
    if (radialData.length === 0) {
      return (
        <div className="flex items-center justify-center h-full text-gray-500">
          <p>Radial bar chart requires an array of data items</p>
        </div>
      );
    }
    const processedData = radialData.map((d: any, i: number) => ({
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
              label={(props: any) => {
                const { name, percent } = props;
                return `${name}: ${(percent * 100).toFixed(1)}%`;
              }}
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

  // Render Line/Bar chart (labels + datasets format from Chart.js)
  const renderLineOrBarChart = () => {
    const raw = data?.data || data;
    const labels = raw?.labels || [];
    const datasets = raw?.datasets || [];
    if (!labels.length || !datasets.length) {
      return (
        <div className="flex items-center justify-center h-full text-gray-500">
          <p>No data for chart</p>
        </div>
      );
    }
    const chartData = labels.map((label: string, i: number) => {
      const point: Record<string, any> = { name: label };
      datasets.forEach((ds: any) => {
        point[ds.label || ds.id || `Series${datasets.indexOf(ds)}`] = ds.data?.[i] ?? 0;
      });
      return point;
    });
    const isBarType = type === 'bar' || type === 'bar_comparison' || type === 'bull_bear_base' || type === 'stacked_bar' || type === 'nav_live';
    const ChartComponent = isBarType ? BarChart : LineChart;
    const DataComponent = isBarType ? Bar : Line;
    return (
      <ResponsiveContainer width="100%" height={height}>
        <ChartComponent data={chartData}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="name" />
          <YAxis />
          <Tooltip />
          <Legend />
          {datasets.map((ds: any, i: number) => (
            <DataComponent
              key={ds.label || i}
              type="monotone"
              dataKey={ds.label || ds.id || `Series${i}`}
              stroke={ds.borderColor || colors[i % colors.length]}
              fill={ds.backgroundColor || colors[i % colors.length]}
              fillOpacity={type === 'bar' ? 0.8 : 0}
              strokeDasharray={ds.strokeDasharray}
              dot={ds.backgroundColor === 'transparent' ? false : undefined}
            />
          ))}
        </ChartComponent>
      </ResponsiveContainer>
    );
  };

  // Render interactive portfolio treemap (squarify layout, sized by value, colored by alpha)
  const renderTreemapChart = () => {
    const raw = data?.data || data;
    const children: any[] = raw?.children || raw?.data || (Array.isArray(raw) ? raw : []);
    if (!Array.isArray(children) || !children.length) {
      return (
        <div className="flex items-center justify-center h-full text-gray-500">
          <p>No data for treemap</p>
        </div>
      );
    }

    // Portfolio treemap: sized by investment/stake, colored by valuation alpha
    // Primary size: investment_size ($ deployed) or stake_value or value
    const sizeKey = ['investment_size', 'stake_value', 'deployed', 'value', 'valuation', 'arr'].find(
      k => children.some((c: any) => Number(c[k]) > 0)
    ) || 'value';
    const colorKey = ['alpha', 'valuation_change', 'pct_change', 'irr', 'moic_change', 'growth_rate'].find(
      k => children.some((c: any) => c[k] != null)
    );

    const items = children
      .map((c: any) => ({
        name: c.name || c.label || 'Unknown',
        value: Math.abs(Number(c[sizeKey])) || 0,
        alpha: colorKey ? Number(c[colorKey]) || 0 : null,
        ownership: c.ownership != null ? Number(c.ownership) : null,
        valuation: c.valuation != null ? Number(c.valuation) : null,
        investmentSize: c.investment_size != null ? Number(c.investment_size) : c.deployed != null ? Number(c.deployed) : null,
        moic: c.moic != null ? Number(c.moic) : null,
        stage: c.stage || c.funding_stage || null,
        raw: c,
      }))
      .filter(c => c.value > 0)
      .sort((a, b) => b.value - a.value);

    if (!items.length) {
      return (
        <div className="flex items-center justify-center h-full text-gray-500">
          <p>No positive values for treemap</p>
        </div>
      );
    }

    // Squarify layout
    const totalValue = items.reduce((s, n) => s + n.value, 0);
    const chartW = typeof width === 'number' ? width : 600;
    const chartH = height;
    const totalArea = chartW * chartH;
    const areas = items.map(n => (n.value / totalValue) * totalArea);

    interface TRect { x: number; y: number; w: number; h: number; idx: number }
    const rects: TRect[] = [];
    let bounds = { x: 0, y: 0, w: chartW, h: chartH };
    let idx = 0;

    const worstRatio = (row: number[], side: number): number => {
      const sum = row.reduce((s, a) => s + a, 0);
      const s2 = side * side;
      let worst = 0;
      for (const a of row) {
        const r = Math.max((s2 * a) / (sum * sum), (sum * sum) / (s2 * a));
        if (r > worst) worst = r;
      }
      return worst;
    };

    while (idx < items.length) {
      const shortSide = Math.min(bounds.w, bounds.h);
      // Build row
      const row: number[] = [areas[idx]];
      let best = worstRatio(row, shortSide);
      for (let i = idx + 1; i < items.length; i++) {
        const candidate = [...row, areas[i]];
        const w = worstRatio(candidate, shortSide);
        if (w > best) break;
        row.push(areas[i]);
        best = w;
      }
      // Place row
      const rowArea = row.reduce((s, a) => s + a, 0);
      const rowLen = rowArea / shortSide;
      const horiz = bounds.w >= bounds.h;
      let offset = 0;
      for (let j = 0; j < row.length; j++) {
        const span = row[j] / rowLen;
        if (horiz) {
          rects.push({ x: bounds.x, y: bounds.y + offset, w: rowLen, h: span, idx: idx + j });
        } else {
          rects.push({ x: bounds.x + offset, y: bounds.y, w: span, h: rowLen, idx: idx + j });
        }
        offset += span;
      }
      if (horiz) {
        bounds = { x: bounds.x + rowLen, y: bounds.y, w: bounds.w - rowLen, h: bounds.h };
      } else {
        bounds = { x: bounds.x, y: bounds.y + rowLen, w: bounds.w, h: bounds.h - rowLen };
      }
      idx += row.length;
    }

    // Alpha color scale: red (negative) → gray (zero) → green (positive)
    const alphaColor = (alpha: number | null): string => {
      if (alpha == null) return colors[0] || '#4e79a7';
      const clamped = Math.max(-100, Math.min(100, alpha));
      if (clamped > 0) {
        const t = clamped / 100;
        const r = Math.round(200 - t * 170);
        const g = Math.round(200 + t * 55);
        const b = Math.round(200 - t * 170);
        return `rgb(${r},${g},${b})`;
      } else if (clamped < 0) {
        const t = -clamped / 100;
        const r = Math.round(200 + t * 55);
        const g = Math.round(200 - t * 150);
        const b = Math.round(200 - t * 150);
        return `rgb(${r},${g},${b})`;
      }
      return '#c8c8c8';
    };

    const fmtCompact = (n: number): string => {
      if (n >= 1e9) return `$${(n / 1e9).toFixed(1)}B`;
      if (n >= 1e6) return `$${(n / 1e6).toFixed(1)}M`;
      if (n >= 1e3) return `$${(n / 1e3).toFixed(0)}K`;
      return `$${n.toFixed(0)}`;
    };

    return (
      <div style={{ position: 'relative', width: chartW, height: chartH }}>
        <svg width={chartW} height={chartH}>
          {rects.map((r) => {
            const item = items[r.idx];
            const fill = alphaColor(item.alpha);
            const maxChars = Math.floor(r.w / 7.5);
            const label = item.name.length > maxChars ? item.name.slice(0, maxChars) + '…' : item.name;
            const alphaStr = item.alpha != null ? `${item.alpha >= 0 ? '+' : ''}${item.alpha.toFixed(1)}%` : '';

            // Adaptive label density based on cell size
            const lines: Array<{ text: string; size: number; fill: string; bold?: boolean }> = [];
            if (r.w > 50 && r.h > 20) {
              lines.push({ text: label, size: 12, fill: '#fff', bold: true });
            }
            if (r.w > 60 && r.h > 34 && item.investmentSize != null) {
              lines.push({ text: `${fmtCompact(item.investmentSize)} invested`, size: 10, fill: 'rgba(255,255,255,0.85)' });
            } else if (r.w > 60 && r.h > 34) {
              lines.push({ text: fmtCompact(item.value), size: 10, fill: 'rgba(255,255,255,0.85)' });
            }
            if (r.w > 60 && r.h > 48 && item.ownership != null) {
              lines.push({ text: `${item.ownership.toFixed(1)}% ownership`, size: 10, fill: 'rgba(255,255,255,0.8)' });
            }
            if (r.w > 70 && r.h > 62 && item.valuation != null) {
              lines.push({ text: `${fmtCompact(item.valuation)} val`, size: 10, fill: 'rgba(255,255,255,0.75)' });
            }
            if (r.w > 70 && r.h > 76 && item.alpha != null) {
              lines.push({
                text: alphaStr,
                size: 10,
                fill: item.alpha >= 0 ? 'rgba(200,255,200,0.95)' : 'rgba(255,200,200,0.95)',
              });
            }
            if (r.w > 70 && r.h > 90 && item.moic != null) {
              lines.push({ text: `${item.moic.toFixed(1)}x MOIC`, size: 10, fill: 'rgba(255,255,255,0.7)' });
            }

            // Build tooltip
            const tipLines = [item.name];
            if (item.investmentSize != null) tipLines.push(`Invested: ${fmtCompact(item.investmentSize)}`);
            if (item.ownership != null) tipLines.push(`Ownership: ${item.ownership.toFixed(1)}%`);
            if (item.valuation != null) tipLines.push(`Valuation: ${fmtCompact(item.valuation)}`);
            if (alphaStr) tipLines.push(`Change: ${alphaStr}`);
            if (item.moic != null) tipLines.push(`MOIC: ${item.moic.toFixed(2)}x`);
            if (item.stage) tipLines.push(`Stage: ${item.stage}`);

            return (
              <g key={r.idx}>
                <rect
                  x={r.x} y={r.y} width={r.w} height={r.h}
                  fill={fill} stroke="#fff" strokeWidth={2}
                  className="cursor-pointer transition-opacity"
                  opacity={0.9}
                  onMouseEnter={(e) => (e.currentTarget.style.opacity = '1')}
                  onMouseLeave={(e) => (e.currentTarget.style.opacity = '0.9')}
                >
                  <title>{tipLines.join('\n')}</title>
                </rect>
                {lines.map((line, li) => (
                  <text
                    key={li}
                    x={r.x + 6}
                    y={r.y + 16 + li * 14}
                    fontSize={line.size}
                    fontWeight={line.bold ? '600' : '400'}
                    fill={line.fill}
                    style={{ textShadow: '0 1px 2px rgba(0,0,0,0.6)', pointerEvents: 'none' }}
                  >
                    {line.text}
                  </text>
                ))}
              </g>
            );
          })}
        </svg>
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

  // Cap Table Evolution Waterfall: rendered via dedicated component to avoid hooks-in-render violation
  const renderCapTableWaterfall = () => {
    return <CapTableWaterfallInner data={data} width={width} height={height} />;
  };

  // ---------------------------------------------------------------------------
  // Scatter Multiples: revenue/growth vs valuation multiple with bubble sizing
  // ---------------------------------------------------------------------------
  const renderScatterMultiples = () => {
    const points = Array.isArray(data) ? data : (data?.companies || data?.points || data?.data || []);
    if (!Array.isArray(points) || !points.length) {
      return <div className="flex items-center justify-center h-full text-gray-500"><p>No data for scatter multiples chart</p></div>;
    }
    const stageColors: Record<string, string> = {
      seed: '#76b7b2', series_a: '#4e79a7', series_b: '#f28e2c',
      series_c: '#e15759', growth: '#59a14f', ipo_ready: '#edc949',
    };
    const processed = points.map((p: any) => ({
      ...p,
      x: p.x ?? p.growth ?? p.revenue_growth ?? 0,
      y: p.y ?? p.multiple ?? p.valuation_multiple ?? 0,
      z: p.z ?? p.arr ?? p.revenue ?? p.total_funding ?? 10_000_000,
      name: p.name ?? p.company ?? 'Unknown',
      stage: p.stage ?? 'series_a',
    }));
    const medianMultiple = processed.length > 0
      ? processed.map((p: any) => p.y).sort((a: number, b: number) => a - b)[Math.floor(processed.length / 2)]
      : 10;

    return (
      <ResponsiveContainer width="100%" height={height}>
        <ScatterChart margin={{ top: 20, right: 30, bottom: 20, left: 20 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#e0e0e0" />
          <XAxis dataKey="x" type="number" name="Growth %" label={{ value: 'Revenue Growth %', position: 'bottom', offset: 0 }} />
          <YAxis dataKey="y" type="number" name="Valuation Multiple" label={{ value: 'EV / Revenue', angle: -90, position: 'insideLeft' }} />
          <ZAxis dataKey="z" type="number" range={[60, 400]} />
          <ReferenceLine y={medianMultiple} stroke="#999" strokeDasharray="5 5" label={{ value: `Median ${medianMultiple.toFixed(1)}x`, position: 'right', fill: '#666', fontSize: 11 }} />
          <Tooltip content={({ active, payload }) => {
            if (!active || !payload?.length) return null;
            const p = payload[0].payload;
            return (
              <div className="bg-white p-3 rounded-lg shadow-lg border text-sm">
                <p className="font-bold text-sm">{p.name}</p>
                <p>Growth: {p.x?.toFixed?.(1) ?? p.x}%</p>
                <p>Multiple: {p.y?.toFixed?.(1) ?? p.y}x</p>
                {p.arr && <p>ARR: ${(p.arr / 1_000_000).toFixed(1)}M</p>}
                <p className="text-xs text-gray-500 mt-1">{p.stage}</p>
              </div>
            );
          }} />
          <Scatter data={processed} shape={(props: any) => {
            const { cx, cy, payload } = props;
            const size = Math.max(8, Math.min(Math.sqrt((payload.z || 10_000_000) / 500_000), 30));
            const fill = stageColors[payload.stage] || colors[0];
            return (
              <g>
                <circle cx={cx} cy={cy} r={size} fill={fill} fillOpacity={0.65} stroke={fill} strokeWidth={1.5} />
                <text x={cx} y={cy - size - 4} textAnchor="middle" fontSize={10} fill="#333">{payload.name}</text>
              </g>
            );
          }} />
        </ScatterChart>
      </ResponsiveContainer>
    );
  };

  // ---------------------------------------------------------------------------
  // Breakpoint Chart: horizontal stacked bars showing value accrual per share class
  // ---------------------------------------------------------------------------
  const renderBreakpointChart = () => {
    const breakpoints = Array.isArray(data) ? data : (data?.breakpoints || data?.share_classes || data?.data || []);
    if (!Array.isArray(breakpoints) || !breakpoints.length) {
      return <div className="flex items-center justify-center h-full text-gray-500"><p>No breakpoint data</p></div>;
    }
    // Each item: { exit_value, common, series_a, series_b, ... } or { name, segments: [{class, value}] }
    const exitValues = breakpoints.map((b: any) => b.exit_value ?? b.exitValue ?? b.name ?? '');
    const shareClasses = Object.keys(breakpoints[0]).filter((k: string) => k !== 'exit_value' && k !== 'exitValue' && k !== 'name' && k !== 'total');
    const classColors: Record<string, string> = {
      common: '#4e79a7', series_a: '#f28e2c', series_b: '#e15759',
      series_c: '#76b7b2', series_d: '#59a14f', esop: '#edc949',
      preferred: '#af7aa1', participation: '#ff9da7',
    };
    const chartData = breakpoints.map((b: any) => {
      const entry: Record<string, any> = { name: `$${((b.exit_value ?? b.exitValue ?? 0) / 1_000_000).toFixed(0)}M` };
      for (const cls of shareClasses) {
        entry[cls] = b[cls] ?? 0;
      }
      return entry;
    });

    return (
      <ResponsiveContainer width="100%" height={height}>
        <BarChart data={chartData} layout="vertical" margin={{ top: 10, right: 30, bottom: 10, left: 60 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#e0e0e0" />
          <XAxis type="number" tickFormatter={(v: number) => `$${(v / 1_000_000).toFixed(0)}M`} label={{ value: 'Value Accrual', position: 'bottom', offset: 0 }} />
          <YAxis type="category" dataKey="name" width={60} label={{ value: 'Exit Value', angle: -90, position: 'insideLeft' }} />
          <Tooltip formatter={(v: number) => `$${(v / 1_000_000).toFixed(1)}M`} />
          <Legend />
          {shareClasses.map((cls: string, i: number) => (
            <Bar key={cls} dataKey={cls} stackId="a" fill={classColors[cls] || colors[i % colors.length]} name={cls.replace(/_/g, ' ').replace(/\b\w/g, (c: string) => c.toUpperCase())} />
          ))}
        </BarChart>
      </ResponsiveContainer>
    );
  };

  // ---------------------------------------------------------------------------
  // DPI Sankey: Fund → Companies → Exits → LP Distributions
  // ---------------------------------------------------------------------------
  const renderDPISankey = () => {
    // Reuse the existing Sankey renderer but with DPI-specific coloring
    const sankeyData = data?.sankey_data || data?.nodes ? data : { nodes: data?.nodes || [], links: data?.links || [] };
    if (!sankeyData.nodes?.length || sankeyData.nodes.length < 2 || !sankeyData.links?.length) {
      return (
        <div className="flex items-center justify-center h-full text-gray-500">
          <div className="text-center">
            <p className="font-medium">No DPI flow data yet</p>
            <p className="text-sm mt-1">Add portfolio companies with investment amounts to see fund flow</p>
          </div>
        </div>
      );
    }
    // Color links by type: green = realized, blue = unrealized, red = write-offs
    const coloredData = {
      ...sankeyData,
      links: (sankeyData.links || []).map((link: any) => ({
        ...link,
        color: link.type === 'realized' ? '#59a14f' : link.type === 'writeoff' ? '#e15759' : '#4e79a7',
      })),
    };
    // Delegate to existing sankey renderer with augmented data
    const origData = data;
    try {
      // Temporarily set data reference for sankey renderer
      return (
        <div style={{ width: '100%', height: height, position: 'relative' }}>
          <TableauLevelChartsSankeyHelper data={coloredData} width={width} height={height} colors={colors} />
        </div>
      );
    } catch {
      return <div className="flex items-center justify-center h-full text-gray-500"><p>DPI Sankey rendering error</p></div>;
    }
  };

  // ---------------------------------------------------------------------------
  // Cap Table Evolution: stacked area chart of ownership % over funding rounds
  // ---------------------------------------------------------------------------
  const renderCapTableEvolution = () => {
    const evolution = Array.isArray(data) ? data : (data?.evolution || data?.rounds || data?.cap_table_evolution || []);
    if (!Array.isArray(evolution) || !evolution.length) {
      return <div className="flex items-center justify-center h-full text-gray-500"><p>No cap table evolution data</p></div>;
    }
    // Expected: [{round: 'Seed', founders: 80, esop: 10, our_fund: 5, others: 5}, ...]
    const stakeholders = Object.keys(evolution[0]).filter((k: string) => k !== 'round' && k !== 'name' && k !== 'label');
    const stakeholderColors: Record<string, string> = {
      founders: '#4e79a7', founder: '#4e79a7', founders_pct: '#4e79a7',
      esop: '#f28e2c', option_pool: '#f28e2c', esop_pct: '#f28e2c',
      our_fund: '#59a14f', our_ownership: '#59a14f', our_ownership_pct: '#59a14f',
      others: '#e15759', other_investors: '#e15759', other_investors_pct: '#e15759',
    };
    const chartData = evolution.map((e: any) => ({
      ...e,
      name: e.round || e.name || e.label || '',
    }));

    return (
      <ResponsiveContainer width="100%" height={height}>
        <AreaChart data={chartData} margin={{ top: 10, right: 30, bottom: 10, left: 10 }} stackOffset="expand">
          <CartesianGrid strokeDasharray="3 3" stroke="#e0e0e0" />
          <XAxis dataKey="name" />
          <YAxis tickFormatter={(v: number) => `${(v * 100).toFixed(0)}%`} />
          <Tooltip formatter={(v: number) => `${(v * 100).toFixed(1)}%`} />
          <Legend />
          {stakeholders.map((s: string, i: number) => (
            <Area
              key={s}
              type="monotone"
              dataKey={s}
              stackId="1"
              fill={stakeholderColors[s] || colors[i % colors.length]}
              stroke={stakeholderColors[s] || colors[i % colors.length]}
              fillOpacity={0.7}
              name={s.replace(/_/g, ' ').replace(/\b\w/g, (c: string) => c.toUpperCase())}
            />
          ))}
        </AreaChart>
      </ResponsiveContainer>
    );
  };

  // ---------------------------------------------------------------------------
  // Radar Comparison: multi-axis scoring overlay for team/moat comparison
  // ---------------------------------------------------------------------------
  const renderRadarComparison = () => {
    const radarData = data?.dimensions || data?.axes || data?.data;
    const companies = data?.companies || data?.subjects || [];
    if (!radarData?.length) {
      return <div className="flex items-center justify-center h-full text-gray-500"><p>No radar comparison data</p></div>;
    }
    // Expected: { dimensions: [{dimension: 'Technical', CompanyA: 8, CompanyB: 6}, ...], companies: ['CompanyA', 'CompanyB'] }
    // Or: [{subject: 'Technical', A: 8, B: 6, fullMark: 10}, ...]
    const companyKeys = companies.length > 0 ? companies : Object.keys(radarData[0]).filter((k: string) => k !== 'dimension' && k !== 'subject' && k !== 'fullMark' && k !== 'name');

    return (
      <ResponsiveContainer width="100%" height={height}>
        <RadarChart data={radarData} margin={{ top: 20, right: 40, bottom: 20, left: 40 }}>
          <PolarGrid stroke="#e0e0e0" />
          <PolarAngleAxis dataKey="dimension" tick={{ fontSize: 11, fill: '#333' }} />
          <PolarRadiusAxis angle={90} domain={[0, 10]} tick={{ fontSize: 10 }} />
          {companyKeys.map((company: string, i: number) => (
            <Radar
              key={company}
              name={company}
              dataKey={company}
              stroke={colors[i % colors.length]}
              fill={colors[i % colors.length]}
              fillOpacity={0.15}
              strokeWidth={2}
              dot={{ r: 4, fill: colors[i % colors.length] }}
            />
          ))}
          <Legend />
          <Tooltip />
        </RadarChart>
      </ResponsiveContainer>
    );
  };

  // ---------------------------------------------------------------------------
  // Funnel Pipeline: deal flow stages with counts and dollar values
  // ---------------------------------------------------------------------------
  const renderFunnelPipeline = () => {
    const stages = Array.isArray(data) ? data : (data?.stages || data?.pipeline || data?.data || []);
    if (!Array.isArray(stages) || !stages.length) {
      return <div className="flex items-center justify-center h-full text-gray-500"><p>No pipeline data</p></div>;
    }
    const pipelineColors = ['#4e79a7', '#59a14f', '#f28e2c', '#e15759', '#76b7b2'];
    const processedStages = stages.map((s: any, i: number) => ({
      name: s.name || s.stage || `Stage ${i + 1}`,
      value: s.value ?? s.count ?? s.deals ?? 0,
      fill: pipelineColors[i % pipelineColors.length],
      dollarValue: s.dollar_value ?? s.totalValue ?? null,
    }));

    return (
      <ResponsiveContainer width="100%" height={height}>
        <FunnelChart>
          <Tooltip content={({ active, payload }) => {
            if (!active || !payload?.length) return null;
            const p = payload[0].payload;
            return (
              <div className="bg-white p-3 rounded-lg shadow-lg border text-sm">
                <p className="font-bold">{p.name}</p>
                <p>{p.value} deals</p>
                {p.dollarValue && <p>${(p.dollarValue / 1_000_000).toFixed(1)}M total</p>}
              </div>
            );
          }} />
          <Funnel dataKey="value" data={processedStages} isAnimationActive animationDuration={800}>
            {processedStages.map((entry: any, index: number) => (
              <Cell key={`cell-${index}`} fill={entry.fill} />
            ))}
            <LabelList position="center" fill="#fff" fontSize={12} fontWeight="bold" content={({ x, y, width: w, height: h, value, name }: any) => (
              <text x={x + (w || 0) / 2} y={y + (h || 0) / 2} textAnchor="middle" dominantBaseline="middle" fill="#fff" fontSize={12} fontWeight="bold">
                {name}: {value}
              </text>
            )} />
          </Funnel>
        </FunnelChart>
      </ResponsiveContainer>
    );
  };

  // ── Scenario Tree (n8n-style flow chart with rich nodes) ────────────
  const renderScenarioTree = () => {
    const validation = validateChartData('scenario_tree', data);
    if (!validation.valid) {
      return (
        <div className="flex items-center justify-center h-full text-gray-500">
          <div className="text-center">
            <p>Invalid data for Scenario Tree</p>
            <p className="text-sm mt-2">{validation.error}</p>
          </div>
        </div>
      );
    }

    const { nodes: rawNodes, edges, paths, expected_tvpi, sensitivity } = validation.data;

    const margin = { top: 40, right: 140, bottom: 50, left: 60 };
    const chartWidth = typeof width === 'number' ? width : 900;
    const chartHeight = height || 540;
    const innerWidth = chartWidth - margin.left - margin.right;
    const innerHeight = chartHeight - margin.top - margin.bottom;

    // Build hierarchy from nodes/edges for d3.tree
    const nodeMap = new Map<string, any>();
    rawNodes.forEach((n: any) => nodeMap.set(n.id, { ...n, children: [] }));
    (edges || []).forEach((e: any) => {
      const parent = nodeMap.get(e.source);
      const child = nodeMap.get(e.target);
      if (parent && child) parent.children.push(child);
    });

    const rootNode = nodeMap.get('root') || rawNodes[0];
    if (!rootNode) return <div className="text-gray-500 text-center p-4">No root node</div>;

    const hierarchy = d3.hierarchy(rootNode, (d: any) => d.children || []);
    const treeLayout = d3.tree<any>().size([innerHeight, innerWidth]);
    const treeData = treeLayout(hierarchy);

    const allDescendants = treeData.descendants();
    const allLinks = treeData.links();

    // Scenario-type color mapping
    const SCENARIO_COLORS: Record<string, string> = {
      bull: '#10b981',   // green
      base: '#4e79a7',   // blue
      bear: '#ef4444',   // red
      custom: '#8b5cf6', // purple
      mixed: '#f59e0b',  // amber
    };

    // Determine node color from label or fund metrics
    const getNodeColor = (node: any) => {
      const label = (node.data?.label || '').toLowerCase();
      if (label.includes('bull')) return SCENARIO_COLORS.bull;
      if (label.includes('bear')) return SCENARIO_COLORS.bear;
      if (label.includes('base')) return SCENARIO_COLORS.base;
      const fund = node.data?.fund;
      if (!fund) return '#9ca3af';
      if (fund.tvpi > 2.0) return SCENARIO_COLORS.bull;
      if (fund.tvpi > 1.0) return SCENARIO_COLORS.base;
      return SCENARIO_COLORS.bear;
    };

    // n8n-style step link with rounded corners
    const linkPath = (link: any) => {
      const sx = link.source.y;
      const sy = link.source.x;
      const tx = link.target.y;
      const ty = link.target.x;
      const midX = (sx + tx) / 2;
      return `M${sx},${sy} C${midX},${sy} ${midX},${ty} ${tx},${ty}`;
    };

    // Node dimensions: leaves are larger to show final metrics
    const NODE_W = 130;
    const NODE_H = 62;
    const LEAF_W = 150;
    const LEAF_H = 78;

    const fmtVal = (v: number) => {
      if (v >= 1e9) return `$${(v / 1e9).toFixed(1)}B`;
      if (v >= 1e6) return `$${(v / 1e6).toFixed(1)}M`;
      if (v >= 1e3) return `$${(v / 1e3).toFixed(0)}K`;
      return `$${v.toFixed(0)}`;
    };

    return (
      <svg
        width="100%"
        height={chartHeight}
        viewBox={`0 0 ${chartWidth} ${chartHeight}`}
        style={{ overflow: 'visible' }}
      >
        <defs>
          <filter id="node-shadow" x="-10%" y="-10%" width="120%" height="130%">
            <feDropShadow dx="0" dy="1" stdDeviation="2" floodOpacity="0.08" />
          </filter>
        </defs>

        <g transform={`translate(${margin.left},${margin.top})`}>
          {/* Edges — smooth bezier curves */}
          {allLinks.map((link: any, i: number) => {
            const prob = link.target.data?.probability || 0.5;
            const color = getNodeColor(link.target);
            return (
              <path
                key={`link-${i}`}
                d={linkPath(link)}
                fill="none"
                stroke={color}
                strokeWidth={Math.max(1.5, prob * 5)}
                strokeOpacity={0.25 + prob * 0.45}
                strokeLinecap="round"
              />
            );
          })}

          {/* Nodes — n8n-style cards */}
          {allDescendants.map((node: any, i: number) => {
            const fund = node.data?.fund;
            const companies = node.data?.companies || {};
            const nodeColor = getNodeColor(node);
            const isLeaf = !node.children || node.children.length === 0;
            const isRoot = node.data?.year === 0;
            const nw = isLeaf ? LEAF_W : NODE_W;
            const nh = isLeaf ? LEAF_H : NODE_H;

            // Aggregate company revenue for display
            const totalRev = (Object.values(companies) as any[]).reduce(
              (sum: number, c: any) => sum + (c?.revenue || 0), 0
            ) as number;

            return (
              <g key={`node-${i}`} transform={`translate(${node.y},${node.x})`}>
                {/* Card background */}
                <rect
                  x={-nw / 2} y={-nh / 2}
                  width={nw} height={nh}
                  rx={10} ry={10}
                  fill="white"
                  stroke={nodeColor}
                  strokeWidth={isLeaf ? 2 : 1.5}
                  filter="url(#node-shadow)"
                />
                {/* Colored top accent bar */}
                <rect
                  x={-nw / 2} y={-nh / 2}
                  width={nw} height={4}
                  rx={10} ry={10}
                  fill={nodeColor}
                />
                <rect
                  x={-nw / 2} y={-nh / 2 + 2}
                  width={nw} height={2}
                  fill={nodeColor}
                />

                {/* Year / label row */}
                <text
                  textAnchor="middle" y={-nh / 2 + 18}
                  fontSize={10} fontWeight="700" fill="#374151"
                >
                  {isRoot ? 'Current State' : `Year ${node.data?.year}`}
                </text>

                {/* Revenue line */}
                <text
                  textAnchor="middle" y={-nh / 2 + 32}
                  fontSize={9} fill="#6b7280"
                >
                  Rev: {fmtVal(totalRev)}
                </text>

                {/* Fund TVPI (all nodes) */}
                {fund && (
                  <text
                    textAnchor="middle" y={-nh / 2 + 46}
                    fontSize={11} fontWeight="700" fill={nodeColor}
                  >
                    {fund.tvpi?.toFixed(2)}x TVPI
                  </text>
                )}

                {/* Leaf: show NAV */}
                {isLeaf && fund && (
                  <text
                    textAnchor="middle" y={-nh / 2 + 60}
                    fontSize={9} fill="#6b7280"
                  >
                    NAV: {fmtVal(fund.nav || 0)}
                  </text>
                )}

                {/* Leaf: per-company ownership badges (max 2 to fit within card) */}
                {isLeaf && Object.keys(companies).length <= 2 && (
                  <>
                    {Object.entries(companies).slice(0, 2).map(([cname, snap]: [string, any], ci: number) => {
                      const ownershipVal = snap?.ownership_pct ?? 0;
                      // ownership_pct may be decimal (0.10) or whole number (10); normalize for display
                      const displayPct = ownershipVal > 1 ? ownershipVal : ownershipVal * 100;
                      return (
                        <text
                          key={ci}
                          textAnchor="middle" y={-nh / 2 + 68 + ci * 10}
                          fontSize={8} fill="#9ca3af"
                        >
                          {cname}: {displayPct.toFixed(1)}% own
                        </text>
                      );
                    })}
                  </>
                )}

                {/* Probability badge — top right */}
                {!isRoot && node.data?.probability < 1 && (
                  <g transform={`translate(${nw / 2 - 8}, ${-nh / 2 - 6})`}>
                    <rect
                      x={-14} y={-6} width={28} height={14}
                      rx={7} fill={nodeColor} opacity={0.15}
                    />
                    <text
                      textAnchor="middle" dy={4}
                      fontSize={8} fontWeight="600" fill={nodeColor}
                    >
                      {(node.data.probability * 100).toFixed(0)}%
                    </text>
                  </g>
                )}
              </g>
            );
          })}

          {/* Expected TVPI annotation */}
          {expected_tvpi != null && (
            <g transform={`translate(${innerWidth}, ${innerHeight + 30})`}>
              <rect x={-120} y={-14} width={120} height={22} rx={4} fill="#f0f4ff" />
              <text
                textAnchor="end" dy={3}
                fontSize={11} fontWeight="600" fill="#4e79a7"
              >
                E[TVPI]: {expected_tvpi.toFixed(2)}x
              </text>
            </g>
          )}

          {/* Sensitivity legend */}
          {sensitivity && Object.keys(sensitivity).length > 0 && (
            <g transform={`translate(0, ${innerHeight + 30})`}>
              {Object.entries(sensitivity as Record<string, number>)
                .sort(([, a], [, b]) => (b as number) - (a as number))
                .slice(0, 3)
                .map(([name, impact], idx) => (
                <text
                  key={idx} x={idx * 160} dy={3}
                  fontSize={9} fill="#6b7280"
                >
                  {name}: {((impact as number) * 100).toFixed(0)}% of variance
                </text>
              ))}
            </g>
          )}
        </g>
      </svg>
    );
  };

  // ── Scenario Paths (multi-line chart with bull/base/bear styling) ───
  const renderScenarioPaths = () => {
    const validation = validateChartData('scenario_paths', data);
    if (!validation.valid) {
      return (
        <div className="flex items-center justify-center h-full text-gray-500">
          <div className="text-center">
            <p>Invalid data for Scenario Paths</p>
            <p className="text-sm mt-2">{validation.error}</p>
          </div>
        </div>
      );
    }

    const { series, metric: _metric } = validation.data;

    // Scenario-type color map
    const SCENARIO_LINE_COLORS: Record<string, string> = {
      bull: '#10b981',
      base: '#4e79a7',
      bear: '#ef4444',
      custom: '#8b5cf6',
      mixed: '#f59e0b',
    };
    const fallbackColors = ['#4e79a7', '#f28e2c', '#e15759', '#76b7b2', '#59a14f', '#edc949', '#af7aa1'];

    const getLineColor = (s: any, idx: number) => {
      const st = s.scenario_type || '';
      return SCENARIO_LINE_COLORS[st] || fallbackColors[idx % fallbackColors.length];
    };

    const getLineWidth = (s: any) => {
      const st = s.scenario_type || '';
      if (st === 'base') return 3;
      return 2;
    };

    const getLineDash = (s: any) => {
      const st = s.scenario_type || '';
      if (st === 'bear') return '6 3';
      if (st === 'bull') return '';
      return '';
    };

    // Build recharts-compatible data: [{year, path_0, path_1, ...}]
    const years = new Set<number>();
    (series || []).forEach((s: any) =>
      (s.data || []).forEach((d: any) => years.add(d.year))
    );
    const sortedYears = Array.from(years).sort((a, b) => a - b);

    const chartData = sortedYears.map((yr) => {
      const row: any = { year: `Y${yr}` };
      (series || []).forEach((s: any, idx: number) => {
        const pt = (s.data || []).find((d: any) => d.year === yr);
        row[`path_${idx}`] = pt?.value ?? null;
      });
      return row;
    });

    // Custom label that shows scenario type on the last point
    const renderEndLabel = (s: any, idx: number, color: string) => {
      const lastYear = sortedYears[sortedYears.length - 1];
      const lastPt = (s.data || []).find((d: any) => d.year === lastYear);
      if (!lastPt) return null;
      const st = s.scenario_type || '';
      const typeLabel = st.charAt(0).toUpperCase() + st.slice(1);
      return typeLabel || s.name || `Path ${idx + 1}`;
    };

    return (
      <ResponsiveContainer width={width} height={height}>
        <ComposedChart data={chartData} margin={{ top: 10, right: 80, bottom: 10, left: 10 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
          <XAxis dataKey="year" fontSize={11} tick={{ fill: '#6b7280' }} />
          <YAxis tickFormatter={formatValue} fontSize={11} tick={{ fill: '#6b7280' }} />
          <Tooltip
            formatter={(val: any, name: string) => {
              const idx = parseInt(name.replace('path_', ''), 10);
              const s = (series || [])[idx];
              const st = s?.scenario_type || '';
              const typeLabel = st ? ` (${st.charAt(0).toUpperCase() + st.slice(1)})` : '';
              return [formatValue(val as number), `${s?.name || name}${typeLabel}`];
            }}
            contentStyle={{
              backgroundColor: 'rgba(255,255,255,0.97)',
              border: '1px solid #d1d5db',
              borderRadius: '8px',
              boxShadow: '0 2px 8px rgba(0,0,0,0.08)',
              fontSize: '12px',
            }}
          />
          <Legend
            formatter={(value: string) => {
              const idx = parseInt(value.replace('path_', ''), 10);
              const s = (series || [])[idx];
              if (!s) return value;
              const st = s.scenario_type || '';
              const icon = st === 'bull' ? '\u25B2' : st === 'bear' ? '\u25BC' : '\u25CF';
              return `${icon} ${s.name || `Path ${idx + 1}`}`;
            }}
          />
          {(series || []).map((s: any, idx: number) => {
            const color = getLineColor(s, idx);
            const lineWidth = getLineWidth(s);
            const dash = getLineDash(s);
            return (
              <Line
                key={`path_${idx}`}
                type="monotone"
                dataKey={`path_${idx}`}
                name={`path_${idx}`}
                stroke={color}
                strokeWidth={lineWidth}
                strokeDasharray={dash || undefined}
                strokeOpacity={Math.max(0.4, s.probability || 0.5)}
                dot={{ r: 3, fill: color, strokeWidth: 0 }}
                activeDot={{ r: 5, fill: color, stroke: 'white', strokeWidth: 2 }}
                connectNulls
                label={idx < 6 ? {
                  position: 'right' as const,
                  content: (props: any) => {
                    // Only label the last data point
                    if (props.index !== sortedYears.length - 1) return null;
                    const lbl = renderEndLabel(s, idx, color);
                    return (
                      <text
                        x={props.x + 8} y={props.y + 4}
                        fontSize={10} fontWeight="600" fill={color}
                      >
                        {lbl}
                      </text>
                    );
                  },
                } : undefined}
              />
            );
          })}
        </ComposedChart>
      </ResponsiveContainer>
    );
  };

  // ── Tornado Chart (horizontal sensitivity bars) ────────────────────
  const renderTornado = () => {
    const validation = validateChartData('tornado', data);
    if (!validation.valid) {
      return (
        <div className="flex items-center justify-center h-full text-gray-500">
          <div className="text-center">
            <p>Invalid data for Tornado chart</p>
            <p className="text-sm mt-2">{validation.error}</p>
          </div>
        </div>
      );
    }

    // Data: [{name, low, high, base}] — sorted by impact range (biggest first)
    const items = [...validation.data].sort(
      (a: any, b: any) => Math.abs(b.high - b.low) - Math.abs(a.high - a.low)
    );

    const baseValue = items[0]?.base ?? 0;
    // Detect if values are multiples (TVPI) vs dollar amounts
    // TVPI values are typically 0-20x; dollar amounts are typically > 1000
    const isMultiple = Math.abs(baseValue) < 100;
    const formatTick = isMultiple
      ? (v: number) => `${v.toFixed(1)}x`
      : formatValue;
    const formatTooltipVal = isMultiple
      ? (v: number) => `${v.toFixed(2)}x`
      : (v: number) => formatValue(v);

    const processedData = items.map((item: any) => ({
      name: item.name || item.label,
      downside: (item.low ?? 0) - baseValue,
      upside: (item.high ?? 0) - baseValue,
      low: item.low ?? 0,
      high: item.high ?? 0,
      base: baseValue,
    }));

    return (
      <ResponsiveContainer width={width} height={height}>
        <BarChart data={processedData} layout="vertical">
          <CartesianGrid strokeDasharray="3 3" stroke="#e0e0e0" />
          <XAxis type="number" tickFormatter={formatTick} fontSize={11} />
          <YAxis
            type="category" dataKey="name"
            width={140} fontSize={11} tick={{ fill: '#374151' }}
          />
          <Tooltip
            formatter={(val: any, name: string) => [
              formatTooltipVal(Math.abs(val as number)),
              name === 'downside' ? 'Downside' : 'Upside',
            ]}
            contentStyle={{
              backgroundColor: 'rgba(255,255,255,0.95)',
              border: '1px solid #ccc',
              borderRadius: '8px',
            }}
          />
          <ReferenceLine x={0} stroke="#374151" strokeWidth={2} />
          <Bar dataKey="downside" fill="#ef4444" opacity={0.8} stackId="impact" />
          <Bar dataKey="upside" fill="#10b981" opacity={0.8} stackId="impact" />
        </BarChart>
      </ResponsiveContainer>
    );
  };

  // ── Cash Flow Waterfall (Revenue → COGS → EBITDA → FCF) ───────────
  const renderCashFlowWaterfall = () => {
    const validation = validateChartData('cash_flow_waterfall', data);
    if (!validation.valid) {
      return (
        <div className="flex items-center justify-center h-full text-gray-500">
          <div className="text-center">
            <p>Invalid data for Cash Flow Waterfall</p>
            <p className="text-sm mt-2">{validation.error}</p>
          </div>
        </div>
      );
    }

    let cumulative = 0;
    const processedData = validation.data.map((d: any) => {
      if (d.isSubtotal) {
        cumulative = d.value;
        return { ...d, start: 0, end: d.value, isPositive: d.value >= 0 };
      }
      const start = cumulative;
      cumulative += d.value;
      return { ...d, start: Math.min(start, cumulative), end: Math.max(start, cumulative), isPositive: d.value >= 0 };
    });

    return (
      <ResponsiveContainer width={width} height={height}>
        <ComposedChart data={processedData}>
          <CartesianGrid strokeDasharray="3 3" stroke="#e0e0e0" />
          <XAxis
            dataKey="name" angle={-30} textAnchor="end"
            height={80} fontSize={11}
          />
          <YAxis tickFormatter={formatValue} fontSize={11} />
          <Tooltip
            formatter={(val: any, name: string) => [formatValue(val as number), name]}
            contentStyle={{
              backgroundColor: 'rgba(255,255,255,0.95)',
              border: '1px solid #ccc',
              borderRadius: '8px',
            }}
          />
          <Bar dataKey="start" stackId="stack" fill="transparent" />
          <Bar
            dataKey="value"
            stackId="stack"
            shape={(props: any) => {
              const { x, y, width: barW, height: barH, payload } = props;
              const isSubtotal = payload.isSubtotal;
              const fillColor = isSubtotal
                ? (payload.value >= 0 ? '#4e79a7' : '#e15759')
                : (payload.isPositive ? '#10b981' : '#ef4444');
              return (
                <g>
                  <rect
                    x={x} y={y} width={barW} height={Math.abs(barH)}
                    fill={fillColor} opacity={isSubtotal ? 0.9 : 0.75}
                    stroke={fillColor} strokeWidth={isSubtotal ? 2 : 1}
                    rx={2}
                  />
                  <text
                    x={x + barW / 2} y={y - 5}
                    textAnchor="middle" fontSize="9" fontWeight="600"
                    fill={fillColor}
                  >
                    {formatValue(payload.value)}
                  </text>
                </g>
              );
            }}
          />
        </ComposedChart>
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
        case 'line':
          if (data?.labels && data?.datasets) {
            return renderLineOrBarChart();
          }
          return renderTimelineValuation();
        case 'bar':
          return renderLineOrBarChart();
        case 'scatter':
          return renderScatterChart();
        case 'treemap':
          return renderTreemapChart();
        case 'cap_table_waterfall':
          return renderCapTableWaterfall();
        case 'scatter_multiples':
          return renderScatterMultiples();
        case 'breakpoint_chart':
          return renderBreakpointChart();
        case 'dpi_sankey':
          return renderDPISankey();
        case 'cap_table_evolution':
          return renderCapTableEvolution();
        case 'radar_comparison':
          return renderRadarComparison();
        case 'funnel_pipeline':
          return renderFunnelPipeline();
        case 'bull_bear_base':
        case 'bar_comparison':
          // These generate bar-type data; delegate to the bar renderer
          return renderLineOrBarChart();
        case 'cap_table_sankey':
          return renderSankey();
        case 'revenue_forecast':
        case 'fpa_stress_test':
          // Line chart types: backend returns {labels, datasets}
          if (data?.labels && data?.datasets) {
            return renderLineOrBarChart();
          }
          return renderTimelineValuation();
        case 'stacked_bar':
        case 'nav_live':
          return renderLineOrBarChart();
        case 'market_map':
          return renderBubble();
        case 'scenario_tree':
          return renderScenarioTree();
        case 'scenario_paths':
          return renderScenarioPaths();
        case 'tornado':
        case 'sensitivity_tornado':
          return renderTornado();
        case 'regression_line':
        case 'monte_carlo_histogram':
        case 'revenue_forecast_decay':
        case 'ltm_ntm_regression':
          // All use labels+datasets shape — handled by the existing line/bar renderer
          return renderLineOrBarChart();
        case 'cash_flow_waterfall':
          return renderCashFlowWaterfall();
        case 'fund_scenarios':
        case 'multi_chart': {
          // Multi-chart bundle: render each sub-chart in a grid
          const charts = data?.charts || data?.data?.charts;
          if (charts && typeof charts === 'object') {
            const entries = Object.entries(charts).filter(
              ([, v]: [string, any]) => v && typeof v === 'object' && v.type
            );
            if (entries.length > 0) {
              return (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4 w-full">
                  {entries.map(([key, chartConfig]: [string, any]) => (
                    <div key={key} className="min-h-[250px]">
                      <TableauLevelCharts
                        type={chartConfig.type}
                        data={chartConfig.data || chartConfig}
                        title={chartConfig.title || key}
                        height={250}
                      />
                    </div>
                  ))}
                </div>
              );
            }
          }
          return (
            <div className="flex items-center justify-center h-full text-gray-500">
              <p>No sub-charts available</p>
            </div>
          );
        }
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