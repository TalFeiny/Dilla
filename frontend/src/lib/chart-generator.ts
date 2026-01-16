/**
 * Unified Chart Generator for Agents
 * NOW USES UNIFIED DESIGN SYSTEM - matches PDF output
 */

import { ChartConfiguration } from 'chart.js';
import { getUnifiedChartOptions, getChartColor, calculateMaxValue } from './chart-config';
import { DECK_DESIGN_TOKENS } from '@/styles/deck-design-tokens';

export interface ChartData {
  labels: string[];
  datasets: {
    label: string;
    data: number[];
    backgroundColor?: string | string[];
    borderColor?: string | string[];
    borderWidth?: number;
    fill?: boolean;
    tension?: number;
  }[];
}

export interface ChartGenerationOptions {
  type: 'bar' | 'line' | 'pie' | 'doughnut' | 'radar' | 'scatter' | 'bubble' | 'area' | 'waterfall' | 'sankey' | 'treemap' | 'funnel' | 'heatmap';
  title?: string;
  width?: number;
  height?: number;
  animate?: boolean;
  interactive?: boolean;
  theme?: 'light' | 'dark' | 'professional';
}

export class ChartGenerator {
  // MONOCHROME COLORS - matching design system
  private static colors = DECK_DESIGN_TOKENS.colors.chart;

  /**
   * Generate chart configuration from raw data
   */
  static generateChartConfig(
    data: any[],
    options: ChartGenerationOptions & {
      xField?: string;
      yField?: string | string[];
      groupBy?: string;
    }
  ): ChartConfiguration {
    const { type, title, xField = 'label', yField = 'value', groupBy } = options;
    
    // Process data based on chart type
    const chartData = this.processDataForChart(data, type, xField, yField, groupBy);
    
    // Apply monochrome colors to datasets
    chartData.datasets = chartData.datasets.map((dataset, i) => ({
      ...dataset,
      backgroundColor: getChartColor(i),
      borderColor: getChartColor(i),
      borderWidth: 2,
      tension: type === 'line' || type === 'area' ? 0.4 : undefined, // Smooth curves
    }));

    // Calculate max value for proper Y-axis formatting
    const maxValue = calculateMaxValue(chartData.datasets);

    // Get unified options from config
    const unifiedOptions = getUnifiedChartOptions(maxValue, {
      yAxisLabel: 'Value',
      showLegend: chartData.datasets.length > 1 || type === 'pie' || type === 'doughnut',
      chartType: type,
    });

    return {
      type: type as any,
      data: chartData,
      options: {
        ...unifiedOptions,
        animation: options.animate ? {
          duration: 1000
        } : false,
        plugins: {
          ...unifiedOptions.plugins,
          title: {
            display: !!title,
            text: title,
            font: {
              family: DECK_DESIGN_TOKENS.fonts.primary,
              size: 16,
              weight: '600',
            },
            color: DECK_DESIGN_TOKENS.colors.foreground,
          },
        },
      }
    };
  }

  /**
   * Process raw data into chart format
   */
  private static processDataForChart(
    data: any[],
    type: string,
    xField: string,
    yField: string | string[],
    groupBy?: string
  ): ChartData {
    if (!data || data.length === 0) {
      return { labels: [], datasets: [] };
    }

    // Handle grouped data
    if (groupBy) {
      return this.processGroupedData(data, xField, yField, groupBy);
    }

    // Handle multiple y fields
    if (Array.isArray(yField)) {
      return this.processMultipleFields(data, xField, yField);
    }

    // Simple single dataset
    const labels = data.map(d => String(d[xField] || ''));
    const values = data.map(d => Number(d[yField] || 0));

    return {
      labels,
      datasets: [{
        label: yField,
        data: values
      }]
    };
  }

  /**
   * Process grouped data for multi-series charts
   */
  private static processGroupedData(
    data: any[],
    xField: string,
    yField: string | string[],
    groupBy: string
  ): ChartData {
    const groups = new Map<string, any[]>();
    
    // Group data
    data.forEach(item => {
      const key = String(item[groupBy] || 'Unknown');
      if (!groups.has(key)) {
        groups.set(key, []);
      }
      groups.get(key)!.push(item);
    });

    // Extract unique x labels
    const labelsSet = new Set<string>();
    data.forEach(item => labelsSet.add(String(item[xField] || '')));
    const labels = Array.from(labelsSet);

    // Create datasets for each group
    const datasets = Array.from(groups.entries()).map(([groupName, groupData]) => {
      const dataMap = new Map(groupData.map(d => [String(d[xField]), d]));
      const values = labels.map(label => {
        const item = dataMap.get(label);
        if (!item) return 0;
        if (Array.isArray(yField)) {
          return yField.reduce((sum, field) => sum + Number(item[field] || 0), 0);
        }
        return Number(item[yField] || 0);
      });

      return {
        label: groupName,
        data: values
      };
    });

    return { labels, datasets };
  }

  /**
   * Process multiple Y fields for multi-series charts
   */
  private static processMultipleFields(
    data: any[],
    xField: string,
    yFields: string[]
  ): ChartData {
    const labels = data.map(d => String(d[xField] || ''));
    
    const datasets = yFields.map(field => ({
      label: field,
      data: data.map(d => Number(d[field] || 0))
    }));

    return { labels, datasets };
  }

  // REMOVED: Old getColorScheme and hexToRgba methods
  // Now using unified design tokens and getChartColor() from chart-config.ts

  /**
   * Generate chart HTML for embedding
   */
  static generateChartHTML(
    data: any[],
    options: ChartGenerationOptions & {
      xField?: string;
      yField?: string | string[];
      groupBy?: string;
    }
  ): string {
    const chartId = `chart-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
    const config = this.generateChartConfig(data, options);
    
    return `
      <div class="chart-container" style="width: ${options.width || 600}px; height: ${options.height || 400}px;">
        <canvas id="${chartId}"></canvas>
        <script>
          (function() {
            const ctx = document.getElementById('${chartId}').getContext('2d');
            new Chart(ctx, ${JSON.stringify(config)});
          })();
        </script>
      </div>
    `;
  }

  /**
   * Generate advanced visualizations
   */
  static generateAdvancedChart(
    data: any[],
    type: 'sankey' | 'treemap' | 'waterfall' | 'funnel' | 'heatmap',
    options: any
  ): any {
    switch (type) {
      case 'sankey':
        return this.generateSankeyChart(data, options);
      case 'treemap':
        return this.generateTreemapChart(data, options);
      case 'waterfall':
        return this.generateWaterfallChart(data, options);
      case 'funnel':
        return this.generateFunnelChart(data, options);
      case 'heatmap':
        return this.generateHeatmapChart(data, options);
      default:
        throw new Error(`Unsupported chart type: ${type}`);
    }
  }

  private static generateSankeyChart(data: any[], options: any) {
    // Sankey diagram for flow visualization
    return {
      type: 'sankey',
      data: {
        datasets: [{
          data: data.map(d => ({
            from: d.source,
            to: d.target,
            flow: d.value
          }))
        }]
      },
      options: {
        ...options,
        plugins: {
          title: {
            display: true,
            text: options.title || 'Flow Diagram'
          }
        }
      }
    };
  }

  private static generateTreemapChart(data: any[], options: any) {
    // Treemap for hierarchical data
    return {
      type: 'treemap',
      data: {
        datasets: [{
          tree: data,
          key: 'value',
          groups: options.groups || ['category'],
          spacing: 0.5,
          borderWidth: 1.5
        }]
      },
      options: {
        ...options,
        plugins: {
          title: {
            display: true,
            text: options.title || 'Treemap'
          }
        }
      }
    };
  }

  private static generateWaterfallChart(data: any[], options: any) {
    // Waterfall chart for cumulative changes
    let cumulative = 0;
    const processedData = data.map(d => {
      const start = cumulative;
      cumulative += d.value;
      return {
        x: d.label,
        y: [start, cumulative],
        backgroundColor: d.value >= 0 ? '#10B981' : '#EF4444'
      };
    });

    return {
      type: 'bar',
      data: {
        datasets: [{
          data: processedData,
          barPercentage: 0.8
        }]
      },
      options: {
        ...options,
        plugins: {
          title: {
            display: true,
            text: options.title || 'Waterfall Chart'
          }
        }
      }
    };
  }

  private static generateFunnelChart(data: any[], options: any) {
    // Funnel chart for conversion visualization
    const maxValue = Math.max(...data.map(d => d.value));
    
    return {
      type: 'bar',
      data: {
        labels: data.map(d => d.label),
        datasets: [{
          data: data.map(d => d.value),
          backgroundColor: this.colors.primary,
          barThickness: (ctx: any) => {
            const value = ctx.parsed.y;
            return (value / maxValue) * 100;
          }
        }]
      },
      options: {
        ...options,
        indexAxis: 'y',
        plugins: {
          title: {
            display: true,
            text: options.title || 'Funnel Chart'
          }
        }
      }
    };
  }

  private static generateHeatmapChart(data: any[], options: any) {
    // Heatmap for matrix visualization
    return {
      type: 'matrix',
      data: {
        datasets: [{
          data: data.map(d => ({
            x: d.x,
            y: d.y,
            v: d.value
          })),
          backgroundColor(ctx: any) {
            const value = ctx.dataset.data[ctx.dataIndex].v;
            const alpha = value / 100;
            return `rgba(59, 130, 246, ${alpha})`;
          },
          width: ({ chart }: any) => (chart.chartArea || {}).width / data.length,
          height: ({ chart }: any) => (chart.chartArea || {}).height / data.length
        }]
      },
      options: {
        ...options,
        plugins: {
          title: {
            display: true,
            text: options.title || 'Heatmap'
          }
        }
      }
    };
  }
}