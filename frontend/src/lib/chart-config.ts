/**
 * Unified Chart Configuration
 * Provides consistent Chart.js options matching PDF output
 */

import { ChartOptions } from 'chart.js';
import { DECK_DESIGN_TOKENS } from '@/styles/deck-design-tokens';
import { DeckFormatter } from './formatters';

/**
 * Get unified chart options for consistent display across web and PDF
 */
export function getUnifiedChartOptions(
  maxValue: number,
  options?: {
    yAxisLabel?: string;
    xAxisLabel?: string;
    showLegend?: boolean;
    chartType?: string;
  }
): ChartOptions {
  const { yAxisLabel, xAxisLabel, showLegend = true, chartType = 'bar' } = options || {};

  const baseOptions: ChartOptions = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: {
        display: showLegend,
        position: 'bottom',
        labels: {
          padding: 16,
          font: {
            family: DECK_DESIGN_TOKENS.fonts.primary,
            size: 12,
            weight: '500',
          },
          color: DECK_DESIGN_TOKENS.colors.muted.foreground,
          usePointStyle: true,
        },
      },
      tooltip: {
        backgroundColor: DECK_DESIGN_TOKENS.colors.primary.DEFAULT,
        titleFont: {
          family: DECK_DESIGN_TOKENS.fonts.primary,
          size: 13,
          weight: '600',
        },
        bodyFont: {
          family: DECK_DESIGN_TOKENS.fonts.primary,
          size: 12,
        },
        padding: 12,
        cornerRadius: 6,
        callbacks: {
          label: (context) => {
            const value = context.parsed.y;
            const formatted = DeckFormatter.formatCurrency(value);
            return `${context.dataset.label}: ${formatted}`;
          },
        },
      },
    },
  };

  // Add scales for non-pie charts
  if (chartType !== 'pie' && chartType !== 'doughnut') {
    baseOptions.scales = {
      y: {
        beginAtZero: true,
        grid: {
          color: DECK_DESIGN_TOKENS.colors.border,
          drawBorder: false,
        },
        ticks: {
          font: {
            family: DECK_DESIGN_TOKENS.fonts.primary,
            size: 11,
          },
          color: DECK_DESIGN_TOKENS.colors.muted.foreground,
          callback: function(value) {
            // Defensive: ensure value is a number
            const numValue = typeof value === 'number' ? value : parseFloat(String(value));
            if (isNaN(numValue)) return String(value);
            return DeckFormatter.formatAxisValue(numValue, maxValue);
          },
        },
        title: {
          display: !!yAxisLabel,
          text: yAxisLabel,
          font: {
            family: DECK_DESIGN_TOKENS.fonts.primary,
            size: 12,
            weight: '600',
          },
          color: DECK_DESIGN_TOKENS.colors.foreground,
        },
      },
      x: {
        grid: {
          display: false,
        },
        ticks: {
          font: {
            family: DECK_DESIGN_TOKENS.fonts.primary,
            size: 11,
          },
          color: DECK_DESIGN_TOKENS.colors.muted.foreground,
        },
        title: {
          display: !!xAxisLabel,
          text: xAxisLabel,
          font: {
            family: DECK_DESIGN_TOKENS.fonts.primary,
            size: 12,
            weight: '600',
          },
          color: DECK_DESIGN_TOKENS.colors.foreground,
        },
      },
    };
  }

  return baseOptions;
}

/**
 * Get monochrome color for dataset
 */
export function getChartColor(index: number): string {
  const colors = DECK_DESIGN_TOKENS.colors.chart;
  return colors[index % colors.length];
}

/**
 * Get dataset defaults with monochrome styling
 */
export function getChartDatasetDefaults(index: number = 0) {
  const color = getChartColor(index);
  
  return {
    backgroundColor: color,
    borderColor: color,
    borderWidth: 2,
    tension: 0.4, // Smooth curves for line charts
  };
}

/**
 * Calculate max value from chart datasets
 */
export function calculateMaxValue(datasets: any[]): number {
  let max = 0;
  
  // Defensive: handle invalid input
  if (!datasets || !Array.isArray(datasets)) {
    return 1000000; // Default 1M for fallback
  }
  
  for (const dataset of datasets) {
    if (!dataset || !dataset.data) continue;
    
    const data = dataset.data || [];
    for (const value of data) {
      if (typeof value === 'number' && isFinite(value) && value > max) {
        max = value;
      }
    }
  }
  
  // Ensure we have a reasonable max
  return max > 0 ? max : 1000000; // Default to 1M if no valid data
}
