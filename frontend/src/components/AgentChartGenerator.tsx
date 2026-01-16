/**
 * Agent Chart Generator Component
 * Allows agents to generate and embed charts in their responses
 */

'use client';

import React, { useState, useEffect, useRef } from 'react';
import dynamic from 'next/dynamic';
import { ChartGenerator } from '@/lib/chart-generator';
// Register Chart.js components
import '@/lib/chart-setup';
import { ensureChartJSRegistered } from '@/lib/chart-setup';

// Dynamic imports for chart libraries with error handling
// Ensure Chart.js is registered before importing components
const Line = dynamic(
  () => {
    if (typeof window !== 'undefined') {
      ensureChartJSRegistered();
    }
    return import('react-chartjs-2').then(mod => mod.Line).catch((err) => {
      console.error('[AgentChart] Failed to load Line chart:', err);
      return null;
    });
  },
  { ssr: false }
);

const Bar = dynamic(
  () => {
    if (typeof window !== 'undefined') {
      ensureChartJSRegistered();
    }
    return import('react-chartjs-2').then(mod => mod.Bar).catch((err) => {
      console.error('[AgentChart] Failed to load Bar chart:', err);
      return null;
    });
  },
  { ssr: false }
);

const Doughnut = dynamic(
  () => {
    if (typeof window !== 'undefined') {
      ensureChartJSRegistered();
    }
    return import('react-chartjs-2').then(mod => mod.Doughnut).catch((err) => {
      console.error('[AgentChart] Failed to load Doughnut chart:', err);
      return null;
    });
  },
  { ssr: false }
);

const Scatter = dynamic(
  () => {
    if (typeof window !== 'undefined') {
      ensureChartJSRegistered();
    }
    return import('react-chartjs-2').then(mod => mod.Scatter).catch((err) => {
      console.error('[AgentChart] Failed to load Scatter chart:', err);
      return null;
    });
  },
  { ssr: false }
);

const Pie = dynamic(
  () => {
    if (typeof window !== 'undefined') {
      ensureChartJSRegistered();
    }
    return import('react-chartjs-2').then(mod => mod.Pie).catch((err) => {
      console.error('[AgentChart] Failed to load Pie chart:', err);
      return null;
    });
  },
  { ssr: false }
);

const Radar = dynamic(
  () => {
    if (typeof window !== 'undefined') {
      ensureChartJSRegistered();
    }
    return import('react-chartjs-2').then(mod => mod.Radar).catch((err) => {
      console.error('[AgentChart] Failed to load Radar chart:', err);
      return null;
    });
  },
  { ssr: false }
);

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

// Fallback component for when chart libraries fail to load
const ChartFallback = ({ title }: { title?: string }) => (
  <div className="flex items-center justify-center p-8 border border-gray-200 rounded-lg bg-gray-50">
    <div className="text-center">
      <div className="text-gray-500 mb-2">📊</div>
      <p className="text-sm text-gray-600">
        {title || 'Chart'} - Loading...
      </p>
    </div>
  </div>
);

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
  const [chartError, setChartError] = useState<string | null>(null);
  const [isClient, setIsClient] = useState(false);
  const [chartReady, setChartReady] = useState(false);
  const chartContainerRef = React.useRef<HTMLDivElement>(null);

  // Ensure we're on the client side
  useEffect(() => {
    setIsClient(true);
    if (typeof window !== 'undefined') {
      ensureChartJSRegistered();
    }
  }, []);

  useEffect(() => {
    if (!isClient) return;
    if (!data || data.length === 0) {
      setChartError('No data provided');
      return;
    }

    try {
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
      setChartError(null);
    } catch (error) {
      console.error('[AgentChart] Error generating chart config:', error);
      setChartError(error instanceof Error ? error.message : 'Failed to generate chart');
    }
  }, [data, type, xField, yField, groupBy, title, theme, interactive, isClient]);

  // Mark chart as ready when it's rendered (for PDF detection)
  useEffect(() => {
    if (!isClient || !chartConfig || !chartContainerRef.current) {
      setChartReady(false);
      return;
    }

    // Chart.js renders to canvas, so we need to check for canvas content
    const checkInterval = setInterval(() => {
      if (chartContainerRef.current) {
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
                  setChartReady(true);
                  chartContainerRef.current.setAttribute('data-chart-ready', 'true');
                  clearInterval(checkInterval);
                  return;
                }
              }
            }
          } catch (e) {
            // Security error - assume rendered if canvas exists
            setChartReady(true);
            if (chartContainerRef.current) {
              chartContainerRef.current.setAttribute('data-chart-ready', 'true');
            }
            clearInterval(checkInterval);
          }
        }
      }
    }, 100); // Check every 100ms

    // Also check after a short delay using requestAnimationFrame
    requestAnimationFrame(() => {
      requestAnimationFrame(() => {
        if (chartContainerRef.current) {
          const canvas = chartContainerRef.current.querySelector('canvas');
          if (canvas) {
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
  }, [isClient, chartConfig, type]);

  if (!isClient) {
    return (
      <div className="flex items-center justify-center p-8 bg-gray-50 dark:bg-gray-800 rounded-lg">
        <p className="text-gray-500 dark:text-gray-400">Loading chart...</p>
      </div>
    );
  }

  if (chartError) {
    return (
      <div className="flex items-center justify-center p-8 bg-red-50 dark:bg-red-900/20 rounded-lg">
        <div className="text-center">
          <p className="text-red-600 dark:text-red-400 font-semibold">Chart Error</p>
          <p className="text-red-500 dark:text-red-500 text-sm mt-1">{chartError}</p>
        </div>
      </div>
    );
  }

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

  // If ChartComponent is null (failed to load), show fallback
  if (!ChartComponent) {
    console.warn(`[AgentChart] Chart component for type "${type}" failed to load`);
    return <ChartFallback title={title} />;
  }

  return (
    <div 
      ref={chartContainerRef}
      className="chart-container bg-white dark:bg-gray-900 p-4 rounded-lg shadow-lg"
      style={{ width: `${width}px`, height: `${height}px` }}
      data-chart-type={type}
      data-chart-ready={chartReady ? 'true' : 'false'}
    >
      {title && <h3 className="text-lg font-semibold mb-2">{title}</h3>}
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