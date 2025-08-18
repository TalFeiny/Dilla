'use client';

import React from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell, LabelList } from 'recharts';

interface Scenario {
  scenario_name: string;
  exit_value: number;
  probability: number;
  reasoning: string;
}

interface OutcomeDistributionProps {
  scenarios: Scenario[];
  expectedValue: number;
}

export function OutcomeDistribution({ scenarios, expectedValue }: OutcomeDistributionProps) {
  // Process scenarios for the chart - add safety checks
  const chartData = scenarios
    .filter(s => s && s.scenario_name && s.exit_value !== undefined && s.probability !== undefined)
    .map(s => ({
      name: (s.scenario_name || '').replace(' Scenario', ''),
      value: (s.exit_value || 0) / 1000000, // Convert to millions
      probability: (s.probability || 0) * 100, // Convert to percentage
      weighted: ((s.exit_value || 0) * (s.probability || 0)) / 1000000, // Weighted contribution in millions
      fullName: s.scenario_name || 'Unknown',
      reasoning: s.reasoning || ''
    }))
    .sort((a, b) => a.value - b.value); // Sort by value ascending
  
  // Return early if no valid data
  if (chartData.length === 0) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Outcome Distribution</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-muted-foreground">No scenario data available</p>
        </CardContent>
      </Card>
    );
  }

  // Color scale from red (worst) to green (best)
  const getColor = (index: number, total: number) => {
    const colors = [
      '#ef4444', // red-500
      '#f97316', // orange-500
      '#eab308', // yellow-500
      '#22c55e', // green-500
      '#10b981', // emerald-500
    ];
    return colors[Math.floor((index / total) * colors.length)];
  };

  // Custom tooltip
  const CustomTooltip = ({ active, payload }: any) => {
    if (active && payload && payload[0]) {
      const data = payload[0].payload;
      return (
        <div className="bg-white dark:bg-gray-800 p-4 rounded-lg shadow-lg border">
          <p className="font-semibold">{data.fullName}</p>
          <p className="text-sm text-gray-600 dark:text-gray-400">
            Exit Value: ${data.value.toFixed(1)}M
          </p>
          <p className="text-sm text-gray-600 dark:text-gray-400">
            Probability: {data.probability.toFixed(1)}%
          </p>
          <p className="text-sm text-gray-600 dark:text-gray-400">
            Weighted: ${data.weighted.toFixed(1)}M
          </p>
          <p className="text-xs text-gray-500 dark:text-gray-500 mt-2 max-w-xs">
            {data.reasoning}
          </p>
        </div>
      );
    }
    return null;
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center justify-between">
          <span>Outcome Distribution (0-10B Range)</span>
          <span className="text-sm font-normal text-muted-foreground">
            Expected Value: ${(expectedValue / 1000000).toFixed(1)}M
          </span>
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="space-y-4">
          {/* Bar Chart */}
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={chartData} margin={{ top: 20, right: 30, left: 20, bottom: 60 }}>
              <CartesianGrid strokeDasharray="3 3" className="opacity-30" />
              <XAxis 
                dataKey="name" 
                angle={-45}
                textAnchor="end"
                height={100}
                className="text-xs"
              />
              <YAxis 
                label={{ value: 'Exit Value ($M)', angle: -90, position: 'insideLeft' }}
                domain={[0, 10000]} // 0 to 10B in millions
                ticks={[0, 1000, 2500, 5000, 7500, 10000]}
                tickFormatter={(value) => {
                  if (value >= 1000) return `${(value / 1000).toFixed(0)}B`;
                  return `${value}M`;
                }}
              />
              <Tooltip content={<CustomTooltip />} />
              <Bar dataKey="value" radius={[4, 4, 0, 0]}>
                <LabelList 
                  dataKey="probability" 
                  position="top" 
                  formatter={(value: number) => `${value.toFixed(0)}%`}
                  className="fill-gray-600 dark:fill-gray-400 text-xs"
                />
                {chartData.map((entry, index) => (
                  <Cell key={`cell-${index}`} fill={getColor(index, chartData.length)} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>

          {/* Probability Distribution Table */}
          <div className="mt-6">
            <h4 className="text-sm font-semibold mb-3">Scenario Breakdown</h4>
            <div className="space-y-2">
              {chartData.map((scenario, index) => (
                <div key={index} className="flex items-center justify-between p-2 rounded-lg bg-gray-50 dark:bg-gray-900">
                  <div className="flex items-center gap-3">
                    <div 
                      className="w-3 h-3 rounded-full" 
                      style={{ backgroundColor: getColor(index, chartData.length) }}
                    />
                    <span className="text-sm font-medium">{scenario.name}</span>
                  </div>
                  <div className="flex items-center gap-4 text-sm">
                    <span className="text-gray-600 dark:text-gray-400">
                      ${scenario.value.toFixed(1)}M
                    </span>
                    <span className="font-medium">
                      {scenario.probability.toFixed(1)}%
                    </span>
                    <span className="text-gray-500 dark:text-gray-500">
                      (${scenario.weighted.toFixed(1)}M weighted)
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Summary Statistics */}
          <div className="mt-4 p-4 bg-blue-50 dark:bg-blue-950 rounded-lg">
            <div className="grid grid-cols-3 gap-4 text-center">
              <div>
                <p className="text-xs text-muted-foreground">Min Outcome</p>
                <p className="text-lg font-semibold">
                  ${Math.min(...chartData.map(d => d.value)).toFixed(1)}M
                </p>
              </div>
              <div>
                <p className="text-xs text-muted-foreground">Expected Value</p>
                <p className="text-lg font-semibold text-blue-600 dark:text-blue-400">
                  ${(expectedValue / 1000000).toFixed(1)}M
                </p>
              </div>
              <div>
                <p className="text-xs text-muted-foreground">Max Outcome</p>
                <p className="text-lg font-semibold">
                  ${Math.max(...chartData.map(d => d.value)).toFixed(1)}M
                </p>
              </div>
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}