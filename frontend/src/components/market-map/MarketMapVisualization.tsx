'use client';

import React, { useEffect, useRef, useState } from 'react';
import * as d3 from 'd3';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { 
  ZoomIn, 
  ZoomOut, 
  Maximize2, 
  Download, 
  Filter,
  Layers,
  Grid3x3,
  CircleDot,
  Building2
} from 'lucide-react';

interface Company {
  name: string;
  category: string;
  subCategory?: string;
  x?: number;
  y?: number;
  size: number;
  color?: string;
  logo?: string;
  funding?: string;
  stage?: string;
  description?: string;
  tags?: string[];
}

interface Segment {
  name: string;
  companies: Company[];
  x: number;
  y: number;
  width: number;
  height: number;
  color: string;
}

interface MarketMapProps {
  data: {
    segments: Array<{
      name: string;
      companies: any[];
      description?: string;
    }>;
    title?: string;
    subtitle?: string;
  };
  width?: number;
  height?: number;
  interactive?: boolean;
  showLogos?: boolean;
  layout?: 'force' | 'grid' | 'cluster' | 'treemap';
}

export function MarketMapVisualization({
  data,
  width = 1200,
  height = 800,
  interactive = true,
  showLogos = true,
  layout = 'cluster'
}: MarketMapProps) {
  const svgRef = useRef<SVGSVGElement>(null);
  const [selectedCompany, setSelectedCompany] = useState<Company | null>(null);
  const [selectedSegment, setSelectedSegment] = useState<string | null>(null);
  const [zoomLevel, setZoomLevel] = useState(1);
  const [viewMode, setViewMode] = useState<'map' | 'list' | 'grid'>('map');

  useEffect(() => {
    if (!svgRef.current || viewMode !== 'map') return;

    // Clear previous visualization
    d3.select(svgRef.current).selectAll('*').remove();

    const svg = d3.select(svgRef.current);
    const g = svg.append('g');

    // Setup zoom
    const zoom = d3.zoom<SVGSVGElement, unknown>()
      .scaleExtent([0.5, 4])
      .on('zoom', (event) => {
        g.attr('transform', event.transform);
        setZoomLevel(event.transform.k);
      });

    svg.call(zoom);

    // Color scale for segments
    const colorScale = d3.scaleOrdinal(d3.schemeSet3);

    // Process data based on layout
    if (layout === 'force') {
      renderForceLayout(g, data, colorScale);
    } else if (layout === 'grid') {
      renderGridLayout(g, data, colorScale);
    } else if (layout === 'cluster') {
      renderClusterLayout(g, data, colorScale);
    } else if (layout === 'treemap') {
      renderTreemapLayout(g, data, colorScale);
    }

  }, [data, layout, viewMode, width, height]);

  const renderClusterLayout = (g: any, data: any, colorScale: any) => {
    const segments = data.segments;
    const padding = 50;
    const segmentWidth = (width - padding * 2) / Math.ceil(Math.sqrt(segments.length));
    const segmentHeight = (height - padding * 2) / Math.ceil(segments.length / Math.ceil(Math.sqrt(segments.length)));

    // Create segment groups
    segments.forEach((segment: any, i: number) => {
      const col = i % Math.ceil(Math.sqrt(segments.length));
      const row = Math.floor(i / Math.ceil(Math.sqrt(segments.length)));
      const x = padding + col * segmentWidth;
      const y = padding + row * segmentHeight;
      const color = colorScale(segment.name);

      // Segment background
      const segmentGroup = g.append('g')
        .attr('class', 'segment-group')
        .attr('transform', `translate(${x}, ${y})`);

      // Segment boundary
      segmentGroup.append('rect')
        .attr('width', segmentWidth - 10)
        .attr('height', segmentHeight - 10)
        .attr('rx', 10)
        .attr('fill', color)
        .attr('fill-opacity', 0.1)
        .attr('stroke', color)
        .attr('stroke-width', 2)
        .attr('stroke-dasharray', '5,5')
        .on('click', () => setSelectedSegment(segment.name));

      // Segment label
      segmentGroup.append('text')
        .attr('x', segmentWidth / 2 - 5)
        .attr('y', 20)
        .attr('text-anchor', 'middle')
        .attr('font-weight', 'bold')
        .attr('font-size', '14px')
        .attr('fill', d3.color(color)?.darker(2))
        .text(segment.name);

      // Position companies within segment
      const companies = segment.companies || [];
      const cols = Math.ceil(Math.sqrt(companies.length));
      const companySize = Math.min(30, (segmentWidth - 20) / cols / 2);

      companies.forEach((company: any, j: number) => {
        const cx = 20 + (j % cols) * (companySize * 2.5) + companySize;
        const cy = 40 + Math.floor(j / cols) * (companySize * 2.5) + companySize;

        const companyGroup = segmentGroup.append('g')
          .attr('class', 'company-node')
          .attr('transform', `translate(${cx}, ${cy})`)
          .style('cursor', 'pointer')
          .on('click', () => setSelectedCompany(company))
          .on('mouseover', function() {
            d3.select(this).select('circle')
              .transition()
              .duration(200)
              .attr('r', companySize * 1.2);
          })
          .on('mouseout', function() {
            d3.select(this).select('circle')
              .transition()
              .duration(200)
              .attr('r', companySize);
          });

        // Company circle
        companyGroup.append('circle')
          .attr('r', companySize)
          .attr('fill', showLogos && company.logo ? 'white' : color)
          .attr('stroke', color)
          .attr('stroke-width', 2);

        // Company logo or initial
        if (showLogos && company.logo) {
          companyGroup.append('image')
            .attr('xlink:href', company.logo)
            .attr('x', -companySize * 0.7)
            .attr('y', -companySize * 0.7)
            .attr('width', companySize * 1.4)
            .attr('height', companySize * 1.4)
            .attr('clip-path', `circle(${companySize}px)`);
        } else {
          companyGroup.append('text')
            .attr('text-anchor', 'middle')
            .attr('dy', '0.3em')
            .attr('font-size', `${companySize * 0.6}px`)
            .attr('fill', 'white')
            .text(company.name.substring(0, 2).toUpperCase());
        }

        // Tooltip on hover
        companyGroup.append('title')
          .text(`${company.name}\n${company.funding || 'N/A'}\n${company.stage || ''}`);
      });
    });

    // Add legend
    const legend = g.append('g')
      .attr('class', 'legend')
      .attr('transform', `translate(${width - 200}, 20)`);

    segments.forEach((segment: any, i: number) => {
      const legendItem = legend.append('g')
        .attr('transform', `translate(0, ${i * 25})`);

      legendItem.append('rect')
        .attr('width', 18)
        .attr('height', 18)
        .attr('fill', colorScale(segment.name))
        .attr('fill-opacity', 0.7);

      legendItem.append('text')
        .attr('x', 24)
        .attr('y', 9)
        .attr('dy', '0.35em')
        .attr('font-size', '12px')
        .text(`${segment.name} (${segment.companies?.length || 0})`);
    });
  };

  const renderForceLayout = (g: any, data: any, colorScale: any) => {
    const allCompanies: any[] = [];
    
    data.segments.forEach((segment: any) => {
      segment.companies?.forEach((company: any) => {
        allCompanies.push({
          ...company,
          segment: segment.name,
          color: colorScale(segment.name)
        });
      });
    });

    // Create force simulation
    const simulation = d3.forceSimulation(allCompanies)
      .force('charge', d3.forceManyBody().strength(-100))
      .force('center', d3.forceCenter(width / 2, height / 2))
      .force('collision', d3.forceCollide().radius(30))
      .force('cluster', forceCluster());

    // Custom clustering force
    function forceCluster() {
      const strength = 0.2;
      let nodes: any[];

      function force(alpha: number) {
        const centroids = d3.rollup(nodes, 
          g => ({ 
            x: d3.mean(g, d => d.x) || 0, 
            y: d3.mean(g, d => d.y) || 0 
          }), 
          d => d.segment
        );

        nodes.forEach(d => {
          const centroid = centroids.get(d.segment);
          if (centroid) {
            d.vx! -= (d.x! - centroid.x) * strength * alpha;
            d.vy! -= (d.y! - centroid.y) * strength * alpha;
          }
        });
      }

      force.initialize = (_: any[]) => nodes = _;
      return force;
    }

    // Add nodes
    const node = g.selectAll('.node')
      .data(allCompanies)
      .enter().append('g')
      .attr('class', 'node')
      .call(d3.drag<any, any>()
        .on('start', dragstarted)
        .on('drag', dragged)
        .on('end', dragended));

    node.append('circle')
      .attr('r', 25)
      .attr('fill', (d: any) => d.color)
      .attr('fill-opacity', 0.7)
      .attr('stroke', (d: any) => d.color)
      .attr('stroke-width', 2);

    node.append('text')
      .attr('text-anchor', 'middle')
      .attr('dy', '0.3em')
      .attr('font-size', '10px')
      .attr('fill', 'white')
      .text((d: any) => d.name.substring(0, 3).toUpperCase());

    // Update positions on tick
    simulation.on('tick', () => {
      node.attr('transform', (d: any) => `translate(${d.x},${d.y})`);
    });

    function dragstarted(event: any, d: any) {
      if (!event.active) simulation.alphaTarget(0.3).restart();
      d.fx = d.x;
      d.fy = d.y;
    }

    function dragged(event: any, d: any) {
      d.fx = event.x;
      d.fy = event.y;
    }

    function dragended(event: any, d: any) {
      if (!event.active) simulation.alphaTarget(0);
      d.fx = null;
      d.fy = null;
    }
  };

  const renderGridLayout = (g: any, data: any, colorScale: any) => {
    const allCompanies: any[] = [];
    
    data.segments.forEach((segment: any) => {
      segment.companies?.forEach((company: any) => {
        allCompanies.push({
          ...company,
          segment: segment.name,
          color: colorScale(segment.name)
        });
      });
    });

    const cols = Math.ceil(Math.sqrt(allCompanies.length));
    const cellSize = Math.min(80, (width - 100) / cols);

    allCompanies.forEach((company: any, i: number) => {
      const x = 50 + (i % cols) * cellSize;
      const y = 50 + Math.floor(i / cols) * cellSize;

      const companyGroup = g.append('g')
        .attr('transform', `translate(${x}, ${y})`)
        .style('cursor', 'pointer')
        .on('click', () => setSelectedCompany(company));

      companyGroup.append('rect')
        .attr('width', cellSize - 5)
        .attr('height', cellSize - 5)
        .attr('rx', 5)
        .attr('fill', company.color)
        .attr('fill-opacity', 0.3)
        .attr('stroke', company.color)
        .attr('stroke-width', 1);

      if (showLogos && company.logo) {
        companyGroup.append('image')
          .attr('xlink:href', company.logo)
          .attr('x', 5)
          .attr('y', 5)
          .attr('width', cellSize - 15)
          .attr('height', cellSize - 15);
      } else {
        companyGroup.append('text')
          .attr('x', cellSize / 2 - 2.5)
          .attr('y', cellSize / 2 - 2.5)
          .attr('text-anchor', 'middle')
          .attr('dy', '0.3em')
          .attr('font-size', '12px')
          .text(company.name.substring(0, 10));
      }
    });
  };

  const renderTreemapLayout = (g: any, data: any, colorScale: any) => {
    // Prepare hierarchical data
    const hierarchyData = {
      name: 'Market',
      children: data.segments.map((segment: any) => ({
        name: segment.name,
        children: segment.companies?.map((company: any) => ({
          name: company.name,
          value: parseFloat(company.funding?.replace(/[^0-9.]/g, '') || '1'),
          ...company
        })) || []
      }))
    };

    const root = d3.hierarchy(hierarchyData)
      .sum((d: any) => d.value || 1)
      .sort((a, b) => (b.value || 0) - (a.value || 0));

    const treemapLayout = d3.treemap()
      .size([width, height])
      .padding(2)
      .round(true);

    treemapLayout(root);

    // Draw segments
    const segments = g.selectAll('.segment')
      .data(root.children || [])
      .enter().append('g')
      .attr('class', 'segment');

    segments.append('rect')
      .attr('x', (d: any) => d.x0)
      .attr('y', (d: any) => d.y0)
      .attr('width', (d: any) => d.x1 - d.x0)
      .attr('height', (d: any) => d.y1 - d.y0)
      .attr('fill', (d: any) => colorScale(d.data.name))
      .attr('fill-opacity', 0.1)
      .attr('stroke', (d: any) => colorScale(d.data.name))
      .attr('stroke-width', 2);

    segments.append('text')
      .attr('x', (d: any) => d.x0 + 5)
      .attr('y', (d: any) => d.y0 + 20)
      .attr('font-weight', 'bold')
      .attr('font-size', '14px')
      .text((d: any) => d.data.name);

    // Draw companies
    const companies = g.selectAll('.company')
      .data(root.leaves())
      .enter().append('g')
      .attr('class', 'company')
      .attr('transform', (d: any) => `translate(${d.x0},${d.y0})`)
      .style('cursor', 'pointer')
      .on('click', (event: any, d: any) => setSelectedCompany(d.data));

    companies.append('rect')
      .attr('width', (d: any) => d.x1 - d.x0)
      .attr('height', (d: any) => d.y1 - d.y0)
      .attr('fill', (d: any) => colorScale(d.parent.data.name))
      .attr('fill-opacity', 0.6)
      .attr('stroke', 'white')
      .attr('stroke-width', 1);

    companies.append('text')
      .attr('x', 3)
      .attr('y', 15)
      .attr('font-size', '10px')
      .attr('fill', 'white')
      .text((d: any) => {
        const width = d.x1 - d.x0;
        const name = d.data.name;
        return width > 50 ? name : name.substring(0, Math.floor(width / 7));
      });
  };

  const downloadMap = () => {
    if (!svgRef.current) return;
    
    const svgData = new XMLSerializer().serializeToString(svgRef.current);
    const svgBlob = new Blob(Array.from(Data), { type: 'image/svg+xml;charset=utf-8' });
    const svgUrl = URL.createObjectURL(svgBlob);
    
    const link = document.createElement('a');
    link.href = svgUrl;
    link.download = `market-map-${Date.now()}.svg`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(svgUrl);
  };

  return (
    <div className="relative w-full">
      {/* Controls */}
      <div className="absolute top-4 right-4 z-10 flex gap-2">
        <Button
          size="sm"
          variant="outline"
          onClick={() => setViewMode('map')}
          className={viewMode === 'map' ? 'bg-blue-50' : ''}
        >
          <CircleDot className="w-4 h-4 mr-1" />
          Map
        </Button>
        <Button
          size="sm"
          variant="outline"
          onClick={() => setViewMode('grid')}
          className={viewMode === 'grid' ? 'bg-blue-50' : ''}
        >
          <Grid3x3 className="w-4 h-4 mr-1" />
          Grid
        </Button>
        <Button
          size="sm"
          variant="outline"
          onClick={() => setViewMode('list')}
          className={viewMode === 'list' ? 'bg-blue-50' : ''}
        >
          <Layers className="w-4 h-4 mr-1" />
          List
        </Button>
        <Button size="sm" variant="outline" onClick={downloadMap}>
          <Download className="w-4 h-4" />
        </Button>
      </div>

      {/* Zoom indicator */}
      {viewMode === 'map' && (
        <div className="absolute bottom-4 right-4 z-10 bg-white px-3 py-1 rounded-md shadow-md">
          <span className="text-sm text-gray-600">Zoom: {(zoomLevel * 100).toFixed(0)}%</span>
        </div>
      )}

      {/* Main visualization */}
      {viewMode === 'map' ? (
        <svg
          ref={svgRef}
          width={width}
          height={height}
          className="border rounded-lg bg-gray-50"
          style={{ cursor: interactive ? 'grab' : 'default' }}
        />
      ) : viewMode === 'grid' ? (
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4 p-4">
          {data.segments.flatMap(segment => 
            segment.companies?.map(company => (
              <Card 
                key={company.name}
                className="cursor-pointer hover:shadow-lg transition-shadow"
                onClick={() => setSelectedCompany(company)}
              >
                <CardContent className="p-4">
                  {company.logo && (
                    <img src={company.logo} alt={company.name} className="w-12 h-12 mb-2" />
                  )}
                  <h4 className="font-semibold text-sm">{company.name}</h4>
                  <p className="text-xs text-gray-600 mt-1">{company.stage}</p>
                  <p className="text-xs font-medium mt-1">{company.funding}</p>
                  <Badge variant="outline" className="mt-2 text-xs">
                    {segment.name}
                  </Badge>
                </CardContent>
              </Card>
            )) || []
          )}
        </div>
      ) : (
        <div className="space-y-6 p-4">
          {data.segments.map(segment => (
            <Card key={segment.name}>
              <CardHeader>
                <CardTitle>{segment.name}</CardTitle>
                <p className="text-sm text-gray-600">{segment.description}</p>
              </CardHeader>
              <CardContent>
                <div className="space-y-2">
                  {segment.companies?.map(company => (
                    <div 
                      key={company.name}
                      className="flex items-center justify-between p-2 hover:bg-gray-50 rounded cursor-pointer"
                      onClick={() => setSelectedCompany(company)}
                    >
                      <div className="flex items-center gap-3">
                        {company.logo && (
                          <img src={company.logo} alt={company.name} className="w-8 h-8" />
                        )}
                        <div>
                          <p className="font-medium">{company.name}</p>
                          <p className="text-sm text-gray-600">{company.description}</p>
                        </div>
                      </div>
                      <div className="text-right">
                        <p className="text-sm font-medium">{company.funding}</p>
                        <p className="text-xs text-gray-600">{company.stage}</p>
                      </div>
                    </div>
                  )) || []}
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {/* Selected company details */}
      {selectedCompany && (
        <div className="absolute top-4 left-4 z-10 bg-white p-4 rounded-lg shadow-lg max-w-sm">
          <div className="flex justify-between items-start mb-2">
            <h3 className="font-bold text-lg">{selectedCompany.name}</h3>
            <button 
              onClick={() => setSelectedCompany(null)}
              className="text-gray-400 hover:text-gray-600"
            >
              ×
            </button>
          </div>
          {selectedCompany.logo && (
            <img src={selectedCompany.logo} alt={selectedCompany.name} className="w-16 h-16 mb-2" />
          )}
          <p className="text-sm text-gray-600 mb-2">{selectedCompany.description}</p>
          <div className="space-y-1 text-sm">
            <p><strong>Funding:</strong> {selectedCompany.funding || 'N/A'}</p>
            <p><strong>Stage:</strong> {selectedCompany.stage || 'N/A'}</p>
            <p><strong>Category:</strong> {selectedCompany.category}</p>
          </div>
          {selectedCompany.tags && (
            <div className="flex flex-wrap gap-1 mt-2">
              {selectedCompany.tags.map(tag => (
                <Badge key={tag} variant="secondary" className="text-xs">
                  {tag}
                </Badge>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}