'use client';

import React, { useState, useEffect } from 'react';
import {
  LineChart, Line, BarChart, Bar, PieChart, Pie, ScatterChart, Scatter,
  AreaChart, Area, RadarChart, Radar, PolarGrid, PolarAngleAxis, PolarRadiusAxis,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, Cell,
  ComposedChart, Treemap, Funnel, FunnelChart, Sankey
} from 'recharts';
import { cn } from '@/lib/utils';
import {
  BarChart3, LineChart as LineChartIcon, PieChart as PieChartIcon,
  ScatterChart as ScatterIcon, Activity, TrendingUp, Grid3x3,
  BarChart2, Layers, GitBranch, Target, Package, ChevronDown,
  Settings, Download, Maximize2, X
} from 'lucide-react';

// Chart color schemes
const COLOR_SCHEMES = {
  default: ['#3b82f6', '#ef4444', '#10b981', '#f59e0b', '#8b5cf6', '#ec4899', '#06b6d4', '#f97316'],
  pastel: ['#93c5fd', '#fca5a5', '#86efac', '#fde047', '#c4b5fd', '#fbcfe8', '#a5f3fc', '#fed7aa'],
  vibrant: ['#2563eb', '#dc2626', '#059669', '#d97706', '#7c3aed', '#db2777', '#0891b2', '#ea580c'],
  monochrome: ['#111827', '#374151', '#6b7280', '#9ca3af', '#d1d5db', '#e5e7eb', '#f3f4f6', '#f9fafb'],
  ocean: ['#0c4a6e', '#0e7490', '#0891b2', '#06b6d4', '#22d3ee', '#67e8f9', '#a5f3fc', '#cffafe'],
  forest: ['#14532d', '#166534', '#15803d', '#16a34a', '#22c55e', '#4ade80', '#86efac', '#bbf7d0'],
  sunset: ['#7c2d12', '#9a3412', '#c2410c', '#ea580c', '#f97316', '#fb923c', '#fdba74', '#fed7aa'],
  berry: ['#701a75', '#86198f', '#a21caf', '#c026d3', '#d946ef', '#e879f9', '#f0abfc', '#fae8ff']
};

interface ChartData {
  labels?: string[];
  datasets?: Array<{
    label: string;
    data: number[];
    color?: string;
  }>;
  data?: Array<Record<string, any>>;
}

interface ExcelChartBuilderProps {
  cells: Record<string, any>;
  selectedRange?: string;
  onClose?: () => void;
}

export default function ExcelChartBuilder({ cells, selectedRange, onClose }: ExcelChartBuilderProps) {
  const [chartType, setChartType] = useState<string>('line');
  const [chartData, setChartData] = useState<any[]>([]);
  const [colorScheme, setColorScheme] = useState<string>('default');
  const [chartTitle, setChartTitle] = useState<string>('');
  const [showLegend, setShowLegend] = useState(true);
  const [showGrid, setShowGrid] = useState(true);
  const [stacked, setStacked] = useState(false);
  const [smooth, setSmooth] = useState(true);
  const [showDataLabels, setShowDataLabels] = useState(false);
  const [is3D, setIs3D] = useState(false);

  // Parse selected range and extract data
  useEffect(() => {
    if (!selectedRange) return;
    
    const parseRange = (range: string) => {
      const [start, end] = range.split(':');
      if (!start || !end) return null;
      
      const startMatch = start.match(/([A-Z]+)(\d+)/);
      const endMatch = end.match(/([A-Z]+)(\d+)/);
      if (!startMatch || !endMatch) return null;
      
      const startCol = startMatch[1].charCodeAt(0) - 65;
      const startRow = parseInt(startMatch[2]) - 1;
      const endCol = endMatch[1].charCodeAt(0) - 65;
      const endRow = parseInt(endMatch[2]) - 1;
      
      return { startCol, startRow, endCol, endRow };
    };
    
    const range = parseRange(selectedRange);
    if (!range) return;
    
    // Extract data from cells
    const data: any[] = [];
    const headers: string[] = [];
    
    // Get headers from first row
    for (let col = range.startCol; col <= range.endCol; col++) {
      const cellKey = `${String.fromCharCode(65 + col)}${range.startRow + 1}`;
      headers.push(cellsArray.from(lKey)?.value || `Column ${col + 1}`);
    }
    
    // Get data rows
    for (let row = range.startRow + 1; row <= range.endRow; row++) {
      const rowData: any = {};
      for (let col = range.startCol; col <= range.endCol; col++) {
        const cellKey = `${String.fromCharCode(65 + col)}${row + 1}`;
        const header = headers[col - range.startCol];
        rowDataArray.from(der) = cellsArray.from(lKey)?.value || 0;
      }
      data.push(rowData);
    }
    
    setChartData(data);
  }, [selectedRange, cells]);

  const chartTypes = [
    { id: 'line', label: 'Line Chart', icon: LineChartIcon },
    { id: 'bar', label: 'Bar Chart', icon: BarChart3 },
    { id: 'pie', label: 'Pie Chart', icon: PieChartIcon },
    { id: 'area', label: 'Area Chart', icon: Activity },
    { id: 'scatter', label: 'Scatter Plot', icon: ScatterIcon },
    { id: 'radar', label: 'Radar Chart', icon: Target },
    { id: 'composed', label: 'Combined', icon: Layers },
    { id: 'treemap', label: 'Treemap', icon: Grid3x3 },
    { id: 'funnel', label: 'Funnel', icon: GitBranch },
    { id: 'heatmap', label: 'Heatmap', icon: Package }
  ];

  const colors = COLOR_SCHEMES[colorScheme as keyof typeof COLOR_SCHEMES] || COLOR_SCHEMES.default;

  const renderChart = () => {
    if (!chartData || chartData.length === 0) {
      return (
        <div className="flex items-center justify-center h-96 text-gray-500">
          Select a data range to create a chart
        </div>
      );
    }

    const dataKeys = Object.keys(chartData[0] || {});
    const xKey = dataKeys[0];
    const valueKeys = dataKeys.slice(1);

    switch (chartType) {
      case 'line':
        return (
          <ResponsiveContainer width="100%" height={400}>
            <LineChart data={chartData}>
              {showGrid && <CartesianGrid strokeDasharray="3 3" />}
              <XAxis dataKey={xKey} />
              <YAxis />
              <Tooltip />
              {showLegend && <Legend />}
              {valueKeys.map((key, index) => (
                <Line
                  key={key}
                  type={smooth ? "monotone" : "linear"}
                  dataKey={key}
                  stroke={colors[index % colors.length]}
                  strokeWidth={2}
                  dot={showDataLabels}
                />
              ))}
            </LineChart>
          </ResponsiveContainer>
        );
      
      case 'bar':
        return (
          <ResponsiveContainer width="100%" height={400}>
            <BarChart data={chartData}>
              {showGrid && <CartesianGrid strokeDasharray="3 3" />}
              <XAxis dataKey={xKey} />
              <YAxis />
              <Tooltip />
              {showLegend && <Legend />}
              {valueKeys.map((key, index) => (
                <Bar
                  key={key}
                  dataKey={key}
                  fill={colors[index % colors.length]}
                  stackId={stacked ? 'stack' : undefined}
                />
              ))}
            </BarChart>
          </ResponsiveContainer>
        );
      
      case 'pie':
        return (
          <ResponsiveContainer width="100%" height={400}>
            <PieChart>
              <Pie
                data={chartData}
                cx="50%"
                cy="50%"
                labelLine={false}
                label={showDataLabels}
                outerRadius={120}
                fill="#8884d8"
                dataKey={valueKeys[0]}
              >
                {chartData.map((entry, index) => (
                  <Cell key={`cell-${index}`} fill={colors[index % colors.length]} />
                ))}
              </Pie>
              <Tooltip />
              {showLegend && <Legend />}
            </PieChart>
          </ResponsiveContainer>
        );
      
      case 'area':
        return (
          <ResponsiveContainer width="100%" height={400}>
            <AreaChart data={chartData}>
              {showGrid && <CartesianGrid strokeDasharray="3 3" />}
              <XAxis dataKey={xKey} />
              <YAxis />
              <Tooltip />
              {showLegend && <Legend />}
              {valueKeys.map((key, index) => (
                <Area
                  key={key}
                  type={smooth ? "monotone" : "linear"}
                  dataKey={key}
                  stackId={stacked ? 'stack' : undefined}
                  stroke={colors[index % colors.length]}
                  fill={colors[index % colors.length]}
                  fillOpacity={0.6}
                />
              ))}
            </AreaChart>
          </ResponsiveContainer>
        );
      
      case 'scatter':
        return (
          <ResponsiveContainer width="100%" height={400}>
            <ScatterChart>
              {showGrid && <CartesianGrid strokeDasharray="3 3" />}
              <XAxis dataKey={xKey} type="number" />
              <YAxis dataKey={valueKeys[0]} type="number" />
              <Tooltip cursor={{ strokeDasharray: '3 3' }} />
              {showLegend && <Legend />}
              <Scatter name={valueKeys[0]} data={chartData} fill={colors[0]} />
            </ScatterChart>
          </ResponsiveContainer>
        );
      
      case 'radar':
        return (
          <ResponsiveContainer width="100%" height={400}>
            <RadarChart data={chartData}>
              <PolarGrid />
              <PolarAngleAxis dataKey={xKey} />
              <PolarRadiusAxis />
              <Tooltip />
              {showLegend && <Legend />}
              {valueKeys.map((key, index) => (
                <Radar
                  key={key}
                  name={key}
                  dataKey={key}
                  stroke={colors[index % colors.length]}
                  fill={colors[index % colors.length]}
                  fillOpacity={0.6}
                />
              ))}
            </RadarChart>
          </ResponsiveContainer>
        );
      
      case 'treemap':
        return (
          <ResponsiveContainer width="100%" height={400}>
            <Treemap
              data={chartData}
              dataKey={valueKeys[0]}
              aspectRatio={4/3}
              stroke="#fff"
              fill={colors[0]}
            />
          </ResponsiveContainer>
        );
      
      case 'composed':
        return (
          <ResponsiveContainer width="100%" height={400}>
            <ComposedChart data={chartData}>
              {showGrid && <CartesianGrid strokeDasharray="3 3" />}
              <XAxis dataKey={xKey} />
              <YAxis />
              <Tooltip />
              {showLegend && <Legend />}
              {valueKeys.length > 0 && (
                <Bar dataKey={valueKeys[0]} fill={colors[0]} />
              )}
              {valueKeys.length > 1 && (
                <Line type="monotone" dataKey={valueKeys[1]} stroke={colors[1]} />
              )}
              {valueKeys.length > 2 && (
                <Area type="monotone" dataKey={valueKeys[2]} fill={colors[2]} fillOpacity={0.6} />
              )}
            </ComposedChart>
          </ResponsiveContainer>
        );
      
      default:
        return null;
    }
  };

  const exportChart = () => {
    // Implementation for exporting chart as image
    console.log('Export chart functionality');
  };

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg shadow-xl w-11/12 max-w-6xl h-5/6 flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b">
          <h2 className="text-xl font-semibold">Chart Builder</h2>
          <button
            onClick={onClose}
            className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="flex flex-1 overflow-hidden">
          {/* Sidebar */}
          <div className="w-64 border-r p-4 overflow-y-auto">
            <div className="space-y-4">
              {/* Chart Type Selection */}
              <div>
                <label className="text-sm font-medium text-gray-700 mb-2 block">Chart Type</label>
                <div className="grid grid-cols-2 gap-2">
                  {chartTypes.map(type => (
                    <button
                      key={type.id}
                      onClick={() => setChartType(type.id)}
                      className={cn(
                        "flex flex-col items-center p-3 rounded-lg border transition-colors",
                        chartType === type.id
                          ? "border-blue-500 bg-blue-50"
                          : "border-gray-200 hover:bg-gray-50"
                      )}
                    >
                      <type.icon className="w-5 h-5 mb-1" />
                      <span className="text-xs">{type.label}</span>
                    </button>
                  ))}
                </div>
              </div>

              {/* Color Scheme */}
              <div>
                <label className="text-sm font-medium text-gray-700 mb-2 block">Color Scheme</label>
                <select
                  value={colorScheme}
                  onChange={(e) => setColorScheme(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  {Object.keys(COLOR_SCHEMES).map(scheme => (
                    <option key={scheme} value={scheme}>
                      {scheme.charAt(0).toUpperCase() + scheme.slice(1)}
                    </option>
                  ))}
                </select>
              </div>

              {/* Chart Title */}
              <div>
                <label className="text-sm font-medium text-gray-700 mb-2 block">Chart Title</label>
                <input
                  type="text"
                  value={chartTitle}
                  onChange={(e) => setChartTitle(e.target.value)}
                  placeholder="Enter chart title"
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>

              {/* Options */}
              <div>
                <label className="text-sm font-medium text-gray-700 mb-2 block">Options</label>
                <div className="space-y-2">
                  <label className="flex items-center">
                    <input
                      type="checkbox"
                      checked={showLegend}
                      onChange={(e) => setShowLegend(e.target.checked)}
                      className="mr-2"
                    />
                    <span className="text-sm">Show Legend</span>
                  </label>
                  <label className="flex items-center">
                    <input
                      type="checkbox"
                      checked={showGrid}
                      onChange={(e) => setShowGrid(e.target.checked)}
                      className="mr-2"
                    />
                    <span className="text-sm">Show Grid</span>
                  </label>
                  <label className="flex items-center">
                    <input
                      type="checkbox"
                      checked={showDataLabels}
                      onChange={(e) => setShowDataLabels(e.target.checked)}
                      className="mr-2"
                    />
                    <span className="text-sm">Show Data Labels</span>
                  </label>
                  {['bar', 'area'].includes(chartType) && (
                    <label className="flex items-center">
                      <input
                        type="checkbox"
                        checked={stacked}
                        onChange={(e) => setStacked(e.target.checked)}
                        className="mr-2"
                      />
                      <span className="text-sm">Stacked</span>
                    </label>
                  )}
                  {['line', 'area'].includes(chartType) && (
                    <label className="flex items-center">
                      <input
                        type="checkbox"
                        checked={smooth}
                        onChange={(e) => setSmooth(e.target.checked)}
                        className="mr-2"
                      />
                      <span className="text-sm">Smooth Curves</span>
                    </label>
                  )}
                </div>
              </div>
            </div>
          </div>

          {/* Chart Display */}
          <div className="flex-1 p-8 overflow-auto">
            {chartTitle && (
              <h3 className="text-lg font-semibold text-center mb-4">{chartTitle}</h3>
            )}
            {renderChart()}
          </div>
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between p-4 border-t">
          <div className="text-sm text-gray-500">
            Data Range: {selectedRange || 'None selected'}
          </div>
          <div className="flex gap-2">
            <button
              onClick={exportChart}
              className="px-4 py-2 bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200 transition-colors flex items-center gap-2"
            >
              <Download className="w-4 h-4" />
              Export
            </button>
            <button
              onClick={onClose}
              className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
            >
              Insert Chart
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}