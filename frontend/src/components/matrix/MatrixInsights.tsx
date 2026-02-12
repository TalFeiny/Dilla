'use client';

import React, { useMemo } from 'react';
import dynamic from 'next/dynamic';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { TrendingUp, TrendingDown, AlertTriangle, DollarSign, BarChart3 } from 'lucide-react';
import { MatrixData } from './UnifiedMatrix';

// Dynamic import for TableauLevelCharts to avoid SSR issues
const TableauLevelCharts = dynamic(() => import('@/components/charts/TableauLevelCharts'), { 
  ssr: false,
  loading: () => <div className="h-[300px] flex items-center justify-center text-sm text-gray-500">Loading chart...</div>
});

interface MatrixInsightsProps {
  matrixData: MatrixData;
}

export function MatrixInsights({ matrixData }: MatrixInsightsProps) {
  // Extract charts from cell metadata and matrix metadata
  const charts = useMemo(() => {
    if (!matrixData) return [];

    const cellCharts: any[] = [];
    const advancedTypes = [
      'sankey', 'sunburst', 'heatmap', 'waterfall', 'boxplot', 
      'candlestick', 'bubble', 'gantt', 'funnel', 'radialBar', 
      'streamgraph', 'chord', 'force', 'side_by_side_sankey', 
      'timeline_valuation', 'probability_cloud'
    ];

    // Extract from cell metadata
    matrixData.rows.forEach(row => {
      Object.values(row.cells).forEach(cell => {
        if (cell.metadata?.chart_config) {
          const chartConfig = cell.metadata.chart_config;
          // Include if renderType is 'tableau' or chart type is advanced
          if (chartConfig.renderType === 'tableau' || 
              advancedTypes.includes(chartConfig.type?.toLowerCase())) {
            cellCharts.push({
              ...chartConfig,
              source: 'cell',
              cellId: `${row.id}-${Object.keys(row.cells).find(k => row.cells[k] === cell)}`
            });
          }
        }
      });
    });

    // Also check matrixData.metadata.charts from unified MCP orchestrator
    const mcpCharts = (matrixData.metadata?.charts || []).filter((chart: any) => 
      chart.renderType === 'tableau' || 
      advancedTypes.includes(chart.type?.toLowerCase())
    ).map((chart: any) => ({
      ...chart,
      source: 'mcp'
    }));

    return [...cellCharts, ...mcpCharts];
  }, [matrixData]);

  const insights = useMemo(() => {
    if (!matrixData || !matrixData.rows.length) return null;

    const insights: any = {
      trends: [],
      comparisons: [],
      alerts: [],
      summary: {},
    };

    // Find numeric columns for analysis
    const numericColumns = matrixData.columns.filter(
      (col) => col.type === 'currency' || col.type === 'number' || col.type === 'percentage'
    );

    // Calculate summary statistics
    numericColumns.forEach((col) => {
      const values = matrixData.rows
        .map((row) => {
          const cell = row.cells[col.id];
          return cell?.value;
        })
        .filter((v) => typeof v === 'number' && !isNaN(v));

      if (values.length > 0) {
        const sum = values.reduce((a, b) => a + b, 0);
        const avg = sum / values.length;
        const min = Math.min(...values);
        const max = Math.max(...values);

        insights.summary[col.id] = {
          name: col.name,
          average: avg,
          min,
          max,
          count: values.length,
        };
      }
    });

    // Find alerts (e.g., high burn rate, low runway)
    matrixData.rows.forEach((row) => {
      const burnRate = row.cells['burnRate']?.value;
      const runway = row.cells['runway']?.value;
      const arr = row.cells['arr']?.value;

      if (burnRate && arr && burnRate > arr * 0.3) {
        insights.alerts.push({
          type: 'warning',
          message: `${row.companyName || row.id}: High burn rate (${((burnRate / arr) * 100).toFixed(1)}% of ARR)`,
        });
      }

      if (runway && runway < 6) {
        insights.alerts.push({
          type: 'critical',
          message: `${row.companyName || row.id}: Low runway (${runway} months)`,
        });
      }
    });

    return insights;
  }, [matrixData]);

  if (!insights) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-sm">Insights</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-gray-500">No insights available</p>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-4">
      {/* Summary Stats */}
      {Object.keys(insights.summary).length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-sm flex items-center">
              <BarChart3 className="w-4 h-4 mr-2" />
              Summary Statistics
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {Object.values(insights.summary).map((stat: any) => (
              <div key={stat.name} className="text-sm">
                <div className="flex justify-between items-center mb-1">
                  <span className="text-gray-600">{stat.name}</span>
                </div>
                <div className="text-xs text-gray-500">
                  Avg: {stat.average.toLocaleString()}, Range: {stat.min.toLocaleString()} - {stat.max.toLocaleString()}
                </div>
              </div>
            ))}
          </CardContent>
        </Card>
      )}

      {/* Alerts */}
      {insights.alerts.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-sm flex items-center">
              <AlertTriangle className="w-4 h-4 mr-2 text-yellow-600" />
              Alerts ({insights.alerts.length})
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            {insights.alerts.map((alert: any, idx: number) => (
              <div
                key={idx}
                className={`text-xs p-2 rounded ${
                  alert.type === 'critical' ? 'bg-red-50 text-red-800' : 'bg-yellow-50 text-yellow-800'
                }`}
              >
                {alert.message}
              </div>
            ))}
          </CardContent>
        </Card>
      )}

      {/* Advanced Visualizations */}
      {charts.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-sm flex items-center">
              <BarChart3 className="w-4 h-4 mr-2" />
              Advanced Visualizations ({charts.length})
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {charts.map((chart, idx) => (
              <div key={idx} className="border rounded-lg p-3 bg-white">
                {chart.title && (
                  <h4 className="text-sm font-medium mb-2 text-gray-700">{chart.title}</h4>
                )}
                <div className="w-full">
                  <TableauLevelCharts
                    type={chart.type as any}
                    data={chart.data}
                    title={chart.title}
                    subtitle={chart.subtitle}
                    height={300}
                    interactive={true}
                    citations={chart.citations}
                    showCitations={!!chart.citations}
                  />
                </div>
              </div>
            ))}
          </CardContent>
        </Card>
      )}

      {/* Portfolio-level insights for portfolio mode */}
      {matrixData.metadata?.fundId && (
        <Card>
          <CardHeader>
            <CardTitle className="text-sm flex items-center">
              <DollarSign className="w-4 h-4 mr-2" />
              Portfolio Overview
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-sm space-y-2">
              <div className="flex justify-between">
                <span className="text-gray-600">Total Companies:</span>
                <span className="font-medium">{matrixData.rows.length}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-600">Columns:</span>
                <span className="font-medium">{matrixData.columns.length}</span>
              </div>
              {matrixData.metadata?.lastUpdated && (
                <div className="flex justify-between">
                  <span className="text-gray-600">Last Updated:</span>
                  <span className="font-medium text-xs">
                    {new Date(matrixData.metadata.lastUpdated).toLocaleString()}
                  </span>
                </div>
              )}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
