'use client';

import React, { useMemo, useEffect, useRef } from 'react';
import * as d3 from 'd3';
import { sankey, sankeyLinkHorizontal, sankeyLeft } from 'd3-sankey';
import { cn } from '@/lib/utils';

interface SankeyNode {
  id: string;
  name: string;
  value?: number;
  color?: string;
  level?: number;
}

interface SankeyLink {
  source: string;
  target: string;
  value: number;
  color?: string;
}

interface RevenueSegmentationProps {
  nodes: SankeyNode[];
  links: SankeyLink[];
  title?: string;
  height?: number;
  width?: number;
  className?: string;
  formatValue?: (value: number) => string;
  showPercentages?: boolean;
  colorScheme?: 'amazon' | 'modern' | 'monochrome';
}

const defaultFormatValue = (value: number): string => {
  if (Math.abs(value) >= 1e9) return `$${(value / 1e9).toFixed(1)}bn`;
  if (Math.abs(value) >= 1e6) return `$${(value / 1e6).toFixed(1)}m`;
  if (Math.abs(value) >= 1e3) return `$${(value / 1e3).toFixed(0)}k`;
  return `$${value.toLocaleString()}`;
};

const colorSchemes = {
  amazon: {
    revenue: '#FFA500',
    profit: '#FFD700',
    cost: '#2C3E50',
    positive: '#10B981',
    negative: '#EF4444',
    aws: '#FF9900',
    ecommerce: '#FFB84D',
    gradient: ['#FFA500', '#FFD700', '#FFE4B5']
  },
  modern: {
    revenue: '#3B82F6',
    profit: '#10B981',
    cost: '#6B7280',
    positive: '#10B981',
    negative: '#EF4444',
    aws: '#8B5CF6',
    ecommerce: '#06B6D4',
    gradient: ['#3B82F6', '#60A5FA', '#93C5FD']
  },
  monochrome: {
    revenue: '#1F2937',
    profit: '#4B5563',
    cost: '#9CA3AF',
    positive: '#374151',
    negative: '#D1D5DB',
    aws: '#111827',
    ecommerce: '#6B7280',
    gradient: ['#1F2937', '#4B5563', '#9CA3AF']
  }
};

export default function RevenueSegmentationChart({
  nodes,
  links,
  title = "Revenue & Profitability Flow",
  height = 600,
  width = 1200,
  className,
  formatValue = defaultFormatValue,
  showPercentages = true,
  colorScheme = 'amazon'
}: RevenueSegmentationProps) {
  const svgRef = useRef<SVGSVGElement>(null);
  const colors = colorSchemes[colorScheme];

  useEffect(() => {
    if (!svgRef.current) return;

    // Clear previous content
    d3.select(svgRef.current).selectAll("*").remove();

    const svg = d3.select(svgRef.current);
    const margin = { top: 20, right: 150, bottom: 20, left: 150 };
    const innerWidth = width - margin.left - margin.right;
    const innerHeight = height - margin.top - margin.bottom;

    const g = svg.append("g")
      .attr("transform", `translate(${margin.left},${margin.top})`);

    // Create sankey generator
    const sankeyGenerator = sankey()
      .nodeId((d: any) => d.id)
      .nodeAlign(sankeyLeft)
      .nodeWidth(20)
      .nodePadding(20)
      .extent([[0, 0], [innerWidth, innerHeight]]);

    // Prepare data
    const graph = {
      nodes: nodes.map(n => ({ ...n })),
      links: links.map(l => ({ ...l }))
    };

    // Generate layout
    const { nodes: layoutNodes, links: layoutLinks } = sankeyGenerator(graph as any);

    // Create gradient definitions
    const defs = svg.append("defs");

    layoutLinks.forEach((link: any, i: number) => {
      const gradientId = `gradient-${i}`;
      const gradient = defs.append("linearGradient")
        .attr("id", gradientId)
        .attr("gradientUnits", "userSpaceOnUse")
        .attr("x1", link.source.x1)
        .attr("y1", link.source.y0)
        .attr("x2", link.target.x0)
        .attr("y2", link.target.y0);

      gradient.append("stop")
        .attr("offset", "0%")
        .attr("stop-color", link.source.color || colors.revenue)
        .attr("stop-opacity", 0.8);

      gradient.append("stop")
        .attr("offset", "100%")
        .attr("stop-color", link.target.color || colors.profit)
        .attr("stop-opacity", 0.8);
    });

    // Draw links
    const link = g.append("g")
      .selectAll(".link")
      .data(layoutLinks)
      .enter().append("g")
      .attr("class", "link");

    link.append("path")
      .attr("d", sankeyLinkHorizontal() as any)
      .attr("stroke", (d: any, i: number) => `url(#gradient-${i})`)
      .attr("stroke-width", (d: any) => Math.max(1, d.width))
      .attr("fill", "none")
      .attr("opacity", 0.5)
      .on("mouseover", function() {
        d3.select(this).attr("opacity", 0.8);
      })
      .on("mouseout", function() {
        d3.select(this).attr("opacity", 0.5);
      });

    // Draw nodes
    const node = g.append("g")
      .selectAll(".node")
      .data(layoutNodes)
      .enter().append("g")
      .attr("class", "node")
      .attr("transform", (d: any) => `translate(${d.x0},${d.y0})`);

    // Node rectangles
    node.append("rect")
      .attr("height", (d: any) => d.y1 - d.y0)
      .attr("width", sankeyGenerator.nodeWidth())
      .attr("fill", (d: any) => {
        if (d.id.includes('AWS')) return colors.aws;
        if (d.id.includes('commerce')) return colors.ecommerce;
        if (d.id.includes('profit')) return colors.profit;
        if (d.id.includes('cost') || d.id.includes('expense')) return colors.cost;
        return d.color || colors.revenue;
      })
      .attr("stroke", "#000")
      .attr("stroke-width", 1);

    // Node labels - Left side
    node.filter((d: any) => d.x0 < innerWidth / 3)
      .append("text")
      .attr("x", -6)
      .attr("y", (d: any) => (d.y1 - d.y0) / 2)
      .attr("dy", "0.35em")
      .attr("text-anchor", "end")
      .style("font-size", "14px")
      .style("font-weight", "bold")
      .style("fill", "#1F2937")
      .text((d: any) => d.name);

    // Node values - Left side
    node.filter((d: any) => d.x0 < innerWidth / 3)
      .append("text")
      .attr("x", -6)
      .attr("y", (d: any) => (d.y1 - d.y0) / 2 + 20)
      .attr("dy", "0.35em")
      .attr("text-anchor", "end")
      .style("font-size", "16px")
      .style("fill", "#1F2937")
      .text((d: any) => formatValue(d.value || 0));

    // Node labels - Right side
    node.filter((d: any) => d.x0 >= innerWidth / 3)
      .append("text")
      .attr("x", sankeyGenerator.nodeWidth() + 6)
      .attr("y", (d: any) => (d.y1 - d.y0) / 2)
      .attr("dy", "0.35em")
      .attr("text-anchor", "start")
      .style("font-size", "14px")
      .style("font-weight", "bold")
      .style("fill", "#1F2937")
      .text((d: any) => d.name);

    // Node values and margins - Right side
    node.filter((d: any) => d.x0 >= innerWidth / 3)
      .append("text")
      .attr("x", sankeyGenerator.nodeWidth() + 6)
      .attr("y", (d: any) => (d.y1 - d.y0) / 2 + 20)
      .attr("dy", "0.35em")
      .attr("text-anchor", "start")
      .style("font-size", "16px")
      .style("fill", "#1F2937")
      .text((d: any) => {
        const value = formatValue(d.value || 0);
        if (showPercentages && d.margin) {
          return `${value} (${d.margin}% margin)`;
        }
        return value;
      });

  }, [nodes, links, width, height, formatValue, showPercentages, colors]);

  return (
    <div className={cn("w-full bg-white rounded-lg p-6", className)}>
      {title && (
        <h2 className="text-2xl font-bold text-pink-500 mb-6">{title}</h2>
      )}
      <svg
        ref={svgRef}
        width={width}
        height={height}
        className="w-full h-auto"
        viewBox={`0 0 ${width} ${height}`}
        preserveAspectRatio="xMidYMid meet"
      />
    </div>
  );
}

// Helper function to create Amazon-style profitability analysis
export function createAmazonProfitabilityData(companyData: {
  segments: Array<{
    name: string;
    revenue: number;
    operatingProfit?: number;
    margin?: number;
  }>;
  costs: {
    costOfSales: number;
    fulfillment: number;
    techContent: number;
    salesMarketing: number;
    generalAdmin: number;
  };
}): { nodes: SankeyNode[]; links: SankeyLink[] } {
  const nodes: SankeyNode[] = [];
  const links: SankeyLink[] = [];
  
  // Revenue nodes (left side)
  companyData.segments.forEach(segment => {
    nodes.push({
      id: `revenue-${segment.name}`,
      name: segment.name,
      value: segment.revenue,
      level: 0
    });
  });
  
  // Total revenue node
  const totalRevenue = companyData.segments.reduce((sum, s) => sum + s.revenue, 0);
  nodes.push({
    id: 'total-revenue',
    name: 'Revenue',
    value: totalRevenue,
    level: 1
  });
  
  // Connect segments to total revenue
  companyData.segments.forEach(segment => {
    links.push({
      source: `revenue-${segment.name}`,
      target: 'total-revenue',
      value: segment.revenue
    });
  });
  
  // Gross profit node
  const grossProfit = totalRevenue - companyData.costs.costOfSales;
  nodes.push({
    id: 'gross-profit',
    name: 'Gross profit',
    value: grossProfit,
    level: 2
  });
  
  // Cost of sales node
  nodes.push({
    id: 'cost-of-sales',
    name: 'Cost of sales',
    value: companyData.costs.costOfSales,
    level: 2
  });
  
  // Connect revenue to gross profit and cost of sales
  links.push({
    source: 'total-revenue',
    target: 'gross-profit',
    value: grossProfit
  });
  
  links.push({
    source: 'total-revenue',
    target: 'cost-of-sales',
    value: companyData.costs.costOfSales
  });
  
  // Operating profit node
  const totalOpEx = companyData.costs.fulfillment + 
                     companyData.costs.techContent + 
                     companyData.costs.salesMarketing + 
                     companyData.costs.generalAdmin;
  const operatingProfit = grossProfit - totalOpEx;
  
  nodes.push({
    id: 'operating-profit',
    name: 'Operating profit',
    value: operatingProfit,
    level: 3
  });
  
  // Operating expenses node
  nodes.push({
    id: 'operating-expenses',
    name: 'Operating expenses',
    value: totalOpEx,
    level: 3
  });
  
  // Connect gross profit to operating profit and expenses
  links.push({
    source: 'gross-profit',
    target: 'operating-profit',
    value: operatingProfit
  });
  
  links.push({
    source: 'gross-profit',
    target: 'operating-expenses',
    value: totalOpEx
  });
  
  // Individual expense nodes
  const expenses = [
    { id: 'fulfillment', name: 'Fulfillment', value: companyData.costs.fulfillment },
    { id: 'tech-content', name: 'Tech & content', value: companyData.costs.techContent },
    { id: 'sales-marketing', name: 'Sales & marketing', value: companyData.costs.salesMarketing },
    { id: 'general-admin', name: 'General & admin', value: companyData.costs.generalAdmin }
  ];
  
  expenses.forEach(expense => {
    nodes.push({
      id: expense.id,
      name: expense.name,
      value: expense.value,
      level: 4
    });
    
    links.push({
      source: 'operating-expenses',
      target: expense.id,
      value: expense.value
    });
  });
  
  // Segment profit breakdown (right side)
  companyData.segments.forEach(segment => {
    if (segment.operatingProfit) {
      nodes.push({
        id: `profit-${segment.name}`,
        name: `${segment.name}`,
        value: segment.operatingProfit,
        level: 4
      });
      
      links.push({
        source: 'operating-profit',
        target: `profit-${segment.name}`,
        value: segment.operatingProfit
      });
    }
  });
  
  return { nodes, links };
}