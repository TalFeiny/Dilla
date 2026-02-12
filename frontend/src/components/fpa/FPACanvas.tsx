'use client';

import React from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import TableauLevelCharts from '@/components/charts/TableauLevelCharts';
import FinancialChartStudio from '@/components/charts/FinancialChartStudio';

interface FPACanvasProps {
  workflow?: any[];
  results?: any;
  onNodeClick?: (nodeId: string) => void;
}

/**
 * FPACanvas - Canvas for visualizing FPA scenarios and cascading impacts
 * Reuses existing charting components (TableauLevelCharts, FinancialChartStudio)
 */
export function FPACanvas({ workflow, results, onNodeClick }: FPACanvasProps) {
  // TODO: Implement React Flow or D3-based canvas visualization
  // For now, render charts based on workflow/results type

  if (!workflow || workflow.length === 0) {
    return (
      <Card>
        <CardContent className="py-8 text-center text-gray-500">
          No workflow data to visualize
        </CardContent>
      </Card>
    );
  }

  // Determine chart type based on workflow
  const hasExitScenarios = workflow.some((step: any) => 
    step.type === 'exit_event' || step.service_call?.service === 'pwerm'
  );
  const hasRevenueProjection = workflow.some((step: any) => 
    step.type === 'revenue_projection' || step.service_call?.service === 'revenue_projection'
  );

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle>Scenario Visualization</CardTitle>
          <CardDescription>
            Interactive canvas showing workflow steps and impacts
          </CardDescription>
        </CardHeader>
        <CardContent>
          {/* TODO: Implement React Flow canvas */}
          <div className="p-8 border-2 border-dashed rounded-lg text-center text-gray-500">
            Canvas visualization coming soon
            <br />
            <span className="text-sm">Will show workflow steps, connections, and cascading impacts</span>
          </div>
        </CardContent>
      </Card>

      {/* Render appropriate charts based on data */}
      {hasExitScenarios && results && (
        <Card>
          <CardHeader>
            <CardTitle>Exit Scenarios</CardTitle>
          </CardHeader>
          <CardContent>
            <TableauLevelCharts
              type="probability_cloud"
              data={results}
              title="Exit Scenario Probability Cloud"
            />
          </CardContent>
        </Card>
      )}

      {hasRevenueProjection && results && (
        <Card>
          <CardHeader>
            <CardTitle>Revenue Projection</CardTitle>
          </CardHeader>
          <CardContent>
            <TableauLevelCharts
              type="line"
              data={results}
              title="Revenue Forecast"
            />
          </CardContent>
        </Card>
      )}
    </div>
  );
}
