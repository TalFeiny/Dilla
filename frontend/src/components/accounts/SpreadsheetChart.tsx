'use client';

import React, { useMemo } from 'react';
import {
  LineChart,
  Line,
  BarChart,
  Bar,
  PieChart,
  Pie,
  AreaChart,
  Area,
  ScatterChart,
  Scatter,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  Cell,
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  Radar,
  ComposedChart
} from 'recharts';
import { cn } from '@/lib/utils';

interface ChartData {
  [key: string]: any;
}

interface SpreadsheetChartProps {
  data: ChartData[] | any;
  type: 'line' | 'bar' | 'pie' | 'area' | 'scatter' | 'radar' | 'composed' | 'bubble' | 'waterfall' | 'heatmap' | 'sankey' | 'table';
  xKey?: string;
  yKeys?: string[];
  title?: string;
  colors?: string[];
  height?: number;
  showGrid?: boolean;
  showLegend?: boolean;
  stacked?: boolean;
  className?: string;
  config?: any;  // Accept full chart config from backend
}

const DEFAULT_COLORS = [
  '#3b82f6', // blue
  '#10b981', // emerald
  '#f59e0b', // amber
  '#ef4444', // red
  '#8b5cf6', // violet
  '#06b6d4', // cyan
  '#f97316', // orange
  '#84cc16', // lime
  '#ec4899', // pink
  '#6366f1', // indigo
];

// Format large numbers
const formatNumber = (value: number): string => {
  if (value >= 1e9) return `$${(value / 1e9).toFixed(1)}B`;
  if (value >= 1e6) return `$${(value / 1e6).toFixed(1)}M`;
  if (value >= 1e3) return `$${(value / 1e3).toFixed(0)}K`;
  return `$${value.toLocaleString()}`;
};

// Custom tooltip
const CustomTooltip = ({ active, payload, label }: any) => {
  if (active && payload && payload.length) {
    return (
      <div className="bg-white p-3 rounded-lg shadow-lg border border-gray-200">
        <p className="text-sm font-medium text-gray-900">{label}</p>
        {payload.map((entry: any, index: number) => (
          <p key={index} className="text-sm" style={{ color: entry.color }}>
            {entry.name}: {formatNumber(entry.value)}
          </p>
        ))}
      </div>
    );
  }
  return null;
};

export default function SpreadsheetChart({
  data,
  type,
  xKey = 'name',
  yKeys = [],
  title,
  colors = DEFAULT_COLORS,
  height = 300,
  showGrid = true,
  showLegend = true,
  stacked = false,
  className,
  config
}: SpreadsheetChartProps) {
  // Process data for charts - handle both regular data and chart config from backend
  const processedData = useMemo(() => {
    // If we have a config object with data, use that
    if (config?.data) {
      // Handle Chart.js style data format
      if (config.data.labels && config.data.datasets) {
        // Convert Chart.js format to Recharts format
        const labels = config.data.labels;
        const datasets = config.data.datasets;
        
        return labels.map((label: string, index: number) => {
          const item: any = { name: label };
          datasets.forEach((dataset: any) => {
            item[dataset.label || 'value'] = dataset.data[index];
          });
          return item;
        });
      }
      return config.data;
    }
    
    // Original processing logic
    if (type === 'pie') {
      // For pie charts, convert to name/value format
      if (yKeys.length > 0) {
        return data.map((item: any) => ({
          name: item[xKey],
          value: item[yKeys[0]]
        }));
      }
      return data;
    }
    return data;
  }, [data, type, xKey, yKeys, config]);

  // Detect if data contains financial metrics
  const isFinancial = useMemo(() => {
    if (data.length === 0) return false;
    const firstItem = data[0];
    const financialKeys = ['revenue', 'profit', 'cost', 'valuation', 'funding', 'arr', 'mrr'];
    return Object.keys(firstItem).some(key => 
      financialKeys.some(fk => key.toLowerCase().includes(fk))
    );
  }, [data]);

  // Auto-detect y-keys if not provided
  const actualYKeys = useMemo(() => {
    if (yKeys.length > 0) return yKeys;
    if (data.length === 0) return [];
    
    const firstItem = data[0];
    return Object.keys(firstItem).filter(key => 
      key !== xKey && typeof firstItem[key] === 'number'
    );
  }, [data, xKey, yKeys]);

  const renderChart = () => {
    switch (type) {
      case 'line':
        return (
          <LineChart data={processedData}>
            {showGrid && <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />}
            <XAxis dataKey={xKey} stroke="#6b7280" fontSize={12} />
            <YAxis stroke="#6b7280" fontSize={12} tickFormatter={isFinancial ? formatNumber : undefined} />
            <Tooltip content={<CustomTooltip />} />
            {showLegend && <Legend />}
            {actualYKeys.map((key, index) => (
              <Line
                key={key}
                type="monotone"
                dataKey={key}
                stroke={colors[index % colors.length]}
                strokeWidth={2}
                dot={{ r: 4 }}
                activeDot={{ r: 6 }}
              />
            ))}
          </LineChart>
        );

      case 'bar':
        return (
          <BarChart data={processedData}>
            {showGrid && <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />}
            <XAxis dataKey={xKey} stroke="#6b7280" fontSize={12} />
            <YAxis stroke="#6b7280" fontSize={12} tickFormatter={isFinancial ? formatNumber : undefined} />
            <Tooltip content={<CustomTooltip />} />
            {showLegend && <Legend />}
            {actualYKeys.map((key, index) => (
              <Bar
                key={key}
                dataKey={key}
                fill={colors[index % colors.length]}
                stackId={stacked ? 'stack' : undefined}
              />
            ))}
          </BarChart>
        );

      case 'pie':
        return (
          <PieChart>
            <Pie
              data={processedData}
              cx="50%"
              cy="50%"
              labelLine={false}
              label={(props: any) => {
                const { name, percent } = props;
                return `${name} ${(percent * 100).toFixed(0)}%`;
              }}
              outerRadius={80}
              fill="#8884d8"
              dataKey="value"
            >
              {processedData.map((entry, index) => (
                <Cell key={`cell-${index}`} fill={colors[index % colors.length]} />
              ))}
            </Pie>
            <Tooltip formatter={(value: any) => formatNumber(value)} />
            {showLegend && <Legend />}
          </PieChart>
        );

      case 'area':
        return (
          <AreaChart data={processedData}>
            {showGrid && <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />}
            <XAxis dataKey={xKey} stroke="#6b7280" fontSize={12} />
            <YAxis stroke="#6b7280" fontSize={12} tickFormatter={isFinancial ? formatNumber : undefined} />
            <Tooltip content={<CustomTooltip />} />
            {showLegend && <Legend />}
            {actualYKeys.map((key, index) => (
              <Area
                key={key}
                type="monotone"
                dataKey={key}
                stackId={stacked ? 'stack' : undefined}
                stroke={colors[index % colors.length]}
                fill={colors[index % colors.length]}
                fillOpacity={0.6}
              />
            ))}
          </AreaChart>
        );

      case 'scatter':
        return (
          <ScatterChart>
            {showGrid && <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />}
            <XAxis dataKey={xKey} stroke="#6b7280" fontSize={12} />
            <YAxis dataKey={actualYKeys[0]} stroke="#6b7280" fontSize={12} />
            <Tooltip content={<CustomTooltip />} cursor={{ strokeDasharray: '3 3' }} />
            {showLegend && <Legend />}
            <Scatter 
              name={actualYKeys[0]} 
              data={processedData} 
              fill={colors[0]}
            />
          </ScatterChart>
        );

      case 'radar':
        return (
          <RadarChart data={processedData}>
            <PolarGrid stroke="#e5e7eb" />
            <PolarAngleAxis dataKey={xKey} stroke="#6b7280" fontSize={12} />
            <PolarRadiusAxis stroke="#6b7280" fontSize={12} />
            <Tooltip content={<CustomTooltip />} />
            {showLegend && <Legend />}
            {actualYKeys.map((key, index) => (
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
        );

      case 'composed':
        return (
          <ComposedChart data={processedData}>
            {showGrid && <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />}
            <XAxis dataKey={xKey} stroke="#6b7280" fontSize={12} />
            <YAxis stroke="#6b7280" fontSize={12} tickFormatter={isFinancial ? formatNumber : undefined} />
            <Tooltip content={<CustomTooltip />} />
            {showLegend && <Legend />}
            {actualYKeys.map((key, index) => {
              // Alternate between bar and line
              if (index % 2 === 0) {
                return (
                  <Bar
                    key={key}
                    dataKey={key}
                    fill={colors[index % colors.length]}
                  />
                );
              } else {
                return (
                  <Line
                    key={key}
                    type="monotone"
                    dataKey={key}
                    stroke={colors[index % colors.length]}
                    strokeWidth={2}
                  />
                );
              }
            })}
          </ComposedChart>
        );

      default:
        return null;
    }
  };

  if (data.length === 0) {
    return (
      <div className={cn("flex items-center justify-center h-64 bg-gray-50 rounded-lg", className)}>
        <p className="text-gray-500">No data available for chart</p>
      </div>
    );
  }

  return (
    <div className={cn("w-full", className)}>
      {title && (
        <h3 className="text-lg font-semibold text-gray-900 mb-4">{title}</h3>
      )}
      <ResponsiveContainer width="100%" height={height}>
        {renderChart()}
      </ResponsiveContainer>
    </div>
  );
}

// Export helper to convert spreadsheet data to chart format
export function convertSpreadsheetToChartData(
  cells: Record<string, any>,
  range: string
): ChartData[] {
  const data: ChartData[] = [];
  
  // Parse range (e.g., "A1:C10")
  const [start, end] = range.split(':');
  if (!start || !end) return data;
  
  const startMatch = start.match(/^([A-Z]+)(\d+)$/);
  const endMatch = end.match(/^([A-Z]+)(\d+)$/);
  if (!startMatch || !endMatch) return data;
  
  const startCol = letterToColumn(startMatch[1]);
  const startRow = parseInt(startMatch[2]);
  const endCol = letterToColumn(endMatch[1]);
  const endRow = parseInt(endMatch[2]);
  
  // First row as headers
  const headers: string[] = [];
  for (let col = startCol; col <= endCol; col++) {
    const addr = columnToLetter(col) + startRow;
    headers.push(cells[addr]?.value || `Column${col + 1}`);
  }
  
  // Rest as data
  for (let row = startRow + 1; row <= endRow; row++) {
    const rowData: ChartData = {};
    for (let col = startCol; col <= endCol; col++) {
      const addr = columnToLetter(col) + row;
      const header = headers[col - startCol];
      const value = cells[addr]?.value;
      rowData[header] = typeof value === 'number' ? value : parseFloat(value) || value;
    }
    data.push(rowData);
  }
  
  return data;
}

function columnToLetter(col: number): string {
  let letter = '';
  while (col >= 0) {
    letter = String.fromCharCode((col % 26) + 65) + letter;
    col = Math.floor(col / 26) - 1;
  }
  return letter;
}

function letterToColumn(letter: string): number {
  let col = 0;
  for (let i = 0; i < letter.length; i++) {
    col = col * 26 + (letter.charCodeAt(i) - 64);
  }
  return col - 1;
}