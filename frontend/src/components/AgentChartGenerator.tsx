/**
 * Agent Chart Generator Component
 * Allows agents to generate and embed charts in their responses
 */

'use client';

import React, { useState, useEffect } from 'react';
import dynamic from 'next/dynamic';
import { ChartGenerator } from '@/lib/chart-generator';

// Dynamic imports for chart libraries
const Line = dynamic(() => import('react-chartjs-2').then(mod => mod.Line), { ssr: false });
const Bar = dynamic(() => import('react-chartjs-2').then(mod => mod.Bar), { ssr: false });
const Doughnut = dynamic(() => import('react-chartjs-2').then(mod => mod.Doughnut), { ssr: false });
const Scatter = dynamic(() => import('react-chartjs-2').then(mod => mod.Scatter), { ssr: false });
const Pie = dynamic(() => import('react-chartjs-2').then(mod => mod.Pie), { ssr: false });
const Radar = dynamic(() => import('react-chartjs-2').then(mod => mod.Radar), { ssr: false });

interface AgentChartProps {
  data: any[];
  type?: 'bar' | 'line' | 'pie' | 'doughnut' | 'radar' | 'scatter' | 'area';
  xField?: string;
  yField?: string | string[];
  groupBy?: string;
  title?: string;
  width?: number;
  height?: number;
  theme?: 'light' | 'dark' | 'professional';
  interactive?: boolean;
}

export function AgentChart({
  data,
  type = 'bar',
  xField = 'label',
  yField = 'value',
  groupBy,
  title,
  width = 600,
  height = 400,
  theme = 'professional',
  interactive = true
}: AgentChartProps) {
  const [chartConfig, setChartConfig] = useState<any>(null);

  useEffect(() => {
    if (!data || data.length === 0) return;

    const config = ChartGenerator.generateChartConfig(data, {
      type,
      title,
      xField,
      yField,
      groupBy,
      theme,
      interactive
    });

    setChartConfig(config);
  }, [data, type, xField, yField, groupBy, title, theme, interactive]);

  if (!chartConfig) {
    return (
      <div className="flex items-center justify-center p-8 bg-gray-50 dark:bg-gray-800 rounded-lg">
        <p className="text-gray-500 dark:text-gray-400">Loading chart...</p>
      </div>
    );
  }

  const ChartComponent = {
    line: Line,
    bar: Bar,
    pie: Pie,
    doughnut: Doughnut,
    radar: Radar,
    scatter: Scatter,
    area: Line
  }[type] || Bar;

  return (
    <div 
      className="chart-container bg-white dark:bg-gray-900 p-4 rounded-lg shadow-lg"
      style={{ width: `${width}px`, height: `${height}px` }}
    >
      <ChartComponent data={chartConfig.data} options={chartConfig.options} />
    </div>
  );
}

interface AgentChartGeneratorProps {
  prompt: string;
  data?: any[];
  onChartGenerated?: (chart: any) => void;
}

export default function AgentChartGenerator({
  prompt,
  data: initialData,
  onChartGenerated
}: AgentChartGeneratorProps) {
  const [isGenerating, setIsGenerating] = useState(false);
  const [chartData, setChartData] = useState<any>(initialData || null);
  const [error, setError] = useState<string | null>(null);
  const [hasGeneratedForPrompt, setHasGeneratedForPrompt] = useState<string | null>(null);

  const generateChart = async () => {
    // Prevent multiple generations for the same prompt
    if (hasGeneratedForPrompt === prompt) return;
    
    setIsGenerating(true);
    setError(null);
    setHasGeneratedForPrompt(prompt);

    try {
      // Call the unified brain API to generate chart data
      const response = await fetch('/api/agent/unified-brain', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          prompt: `Generate chart data for: ${prompt}`,
          outputFormat: 'chart',
          data: initialData
        })
      });

      if (!response.ok) throw new Error('Failed to generate chart');
      
      const result = await response.json();
      
      if (result.chart) {
        setChartData(result.chart);
        onChartGenerated?.(result.chart);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to generate chart');
    } finally {
      setIsGenerating(false);
    }
  };

  useEffect(() => {
    // If initial data is provided, use it directly without generating
    if (initialData) {
      setChartData(initialData);
      onChartGenerated?.(initialData);
      return;
    }
    
    // Only generate if we have a prompt and haven't generated for this prompt yet
    if (prompt && hasGeneratedForPrompt !== prompt && !chartData) {
      generateChart();
    }
  }, [prompt, hasGeneratedForPrompt, initialData]); // Track prompt, generation status, and initial data

  if (error) {
    return (
      <div className="p-4 bg-red-50 dark:bg-red-900/20 rounded-lg">
        <p className="text-red-600 dark:text-red-400">Error: {error}</p>
      </div>
    );
  }

  if (isGenerating) {
    return (
      <div className="flex items-center justify-center p-8 bg-gray-50 dark:bg-gray-800 rounded-lg">
        <div className="flex items-center space-x-2">
          <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-blue-600"></div>
          <p className="text-gray-600 dark:text-gray-400">Generating chart...</p>
        </div>
      </div>
    );
  }

  if (!chartData) {
    return null;
  }

  return <AgentChart {...chartData} />;
}

/**
 * Hook for agents to generate charts programmatically
 */
export function useAgentChart() {
  const generateChart = async (
    data: any[],
    options: {
      type?: string;
      xField?: string;
      yField?: string | string[];
      groupBy?: string;
      title?: string;
    }
  ) => {
    const config = ChartGenerator.generateChartConfig(data, {
      type: options.type as any || 'bar',
      title: options.title,
      xField: options.xField,
      yField: options.yField,
      groupBy: options.groupBy,
      theme: 'professional'
    });

    return config;
  };

  const generateAdvancedChart = async (
    data: any[],
    type: 'sankey' | 'treemap' | 'waterfall' | 'funnel' | 'heatmap',
    options: any
  ) => {
    return ChartGenerator.generateAdvancedChart(data, type, options);
  };

  const generateHTMLChart = (data: any[], options: any) => {
    return ChartGenerator.generateChartHTML(data, options);
  };

  return {
    generateChart,
    generateAdvancedChart,
    generateHTMLChart
  };
}