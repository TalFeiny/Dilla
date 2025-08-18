/**
 * Professional Chart Styling System
 * Beautiful, consistent charts with gradients and modern aesthetics
 */

import React from 'react';

export interface ChartTheme {
  name: string;
  colors: {
    primary: string[];
    secondary: string[];
    gradients: GradientConfig[];
    text: {
      primary: string;
      secondary: string;
      muted: string;
    };
    grid: string;
    background: string;
  };
  fonts: {
    family: string;
    sizes: {
      title: number;
      label: number;
      tick: number;
      legend: number;
    };
  };
  animation: {
    duration: number;
    easing: string;
  };
}

export interface GradientConfig {
  id: string;
  type: 'linear' | 'radial';
  stops: Array<{
    offset: string;
    color: string;
    opacity?: number;
  }>;
  x1?: string;
  y1?: string;
  x2?: string;
  y2?: string;
}

export class ChartStylingSystem {
  private static instance: ChartStylingSystem;
  private themes: Map<string, ChartTheme> = new Map();
  private currentTheme: string = 'professional';

  private constructor() {
    this.initializeThemes();
  }

  static getInstance(): ChartStylingSystem {
    if (!ChartStylingSystem.instance) {
      ChartStylingSystem.instance = new ChartStylingSystem();
    }
    return ChartStylingSystem.instance;
  }

  private initializeThemes() {
    // Professional Theme (like the reference image)
    this.themes.set('professional', {
      name: 'professional',
      colors: {
        primary: [
          '#0ea5e9', // Sky blue
          '#3b82f6', // Blue
          '#6366f1', // Indigo
          '#8b5cf6', // Purple
          '#a855f7', // Purple
          '#ec4899', // Pink
        ],
        secondary: [
          '#10b981', // Emerald
          '#14b8a6', // Teal
          '#06b6d4', // Cyan
          '#f59e0b', // Amber
          '#ef4444', // Red
          '#64748b', // Slate
        ],
        gradients: [
          {
            id: 'blue-gradient',
            type: 'linear',
            x1: '0%',
            y1: '0%',
            x2: '0%',
            y2: '100%',
            stops: [
              { offset: '0%', color: '#3b82f6', opacity: 0.8 },
              { offset: '100%', color: '#1e40af', opacity: 0.3 }
            ]
          },
          {
            id: 'green-gradient',
            type: 'linear',
            x1: '0%',
            y1: '0%',
            x2: '0%',
            y2: '100%',
            stops: [
              { offset: '0%', color: '#10b981', opacity: 0.8 },
              { offset: '100%', color: '#059669', opacity: 0.3 }
            ]
          },
          {
            id: 'purple-gradient',
            type: 'linear',
            x1: '0%',
            y1: '0%',
            x2: '0%',
            y2: '100%',
            stops: [
              { offset: '0%', color: '#8b5cf6', opacity: 0.8 },
              { offset: '100%', color: '#6d28d9', opacity: 0.3 }
            ]
          },
          {
            id: 'area-gradient',
            type: 'linear',
            x1: '0%',
            y1: '0%',
            x2: '0%',
            y2: '100%',
            stops: [
              { offset: '0%', color: '#3b82f6', opacity: 0.6 },
              { offset: '50%', color: '#3b82f6', opacity: 0.3 },
              { offset: '100%', color: '#3b82f6', opacity: 0.05 }
            ]
          }
        ],
        text: {
          primary: '#1e293b',
          secondary: '#475569',
          muted: '#94a3b8'
        },
        grid: '#e2e8f0',
        background: '#ffffff'
      },
      fonts: {
        family: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif',
        sizes: {
          title: 18,
          label: 12,
          tick: 11,
          legend: 12
        }
      },
      animation: {
        duration: 750,
        easing: 'ease-in-out'
      }
    });

    // Dark Theme
    this.themes.set('dark', {
      name: 'dark',
      colors: {
        primary: [
          '#60a5fa', // Light blue
          '#818cf8', // Light indigo
          '#a78bfa', // Light purple
          '#c084fc', // Light purple
          '#f472b6', // Light pink
          '#fb7185', // Light rose
        ],
        secondary: [
          '#34d399', // Light emerald
          '#2dd4bf', // Light teal
          '#22d3ee', // Light cyan
          '#fbbf24', // Light amber
          '#f87171', // Light red
          '#94a3b8', // Light slate
        ],
        gradients: [
          {
            id: 'dark-blue-gradient',
            type: 'linear',
            x1: '0%',
            y1: '0%',
            x2: '0%',
            y2: '100%',
            stops: [
              { offset: '0%', color: '#60a5fa', opacity: 0.8 },
              { offset: '100%', color: '#3730a3', opacity: 0.3 }
            ]
          }
        ],
        text: {
          primary: '#f1f5f9',
          secondary: '#cbd5e1',
          muted: '#64748b'
        },
        grid: '#334155',
        background: '#0f172a'
      },
      fonts: {
        family: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif',
        sizes: {
          title: 18,
          label: 12,
          tick: 11,
          legend: 12
        }
      },
      animation: {
        duration: 750,
        easing: 'ease-in-out'
      }
    });

    // Minimal Theme
    this.themes.set('minimal', {
      name: 'minimal',
      colors: {
        primary: [
          '#000000',
          '#525252',
          '#737373',
          '#a3a3a3',
          '#d4d4d4',
          '#e5e5e5'
        ],
        secondary: [
          '#dc2626', // Red accent
          '#059669', // Green accent
          '#2563eb', // Blue accent
          '#7c3aed', // Purple accent
          '#ea580c', // Orange accent
          '#0891b2', // Cyan accent
        ],
        gradients: [
          {
            id: 'mono-gradient',
            type: 'linear',
            x1: '0%',
            y1: '0%',
            x2: '0%',
            y2: '100%',
            stops: [
              { offset: '0%', color: '#000000', opacity: 0.2 },
              { offset: '100%', color: '#000000', opacity: 0.05 }
            ]
          }
        ],
        text: {
          primary: '#000000',
          secondary: '#525252',
          muted: '#a3a3a3'
        },
        grid: '#f5f5f5',
        background: '#ffffff'
      },
      fonts: {
        family: 'Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
        sizes: {
          title: 16,
          label: 11,
          tick: 10,
          legend: 11
        }
      },
      animation: {
        duration: 500,
        easing: 'ease-out'
      }
    });
  }

  /**
   * Get current theme
   */
  getTheme(): ChartTheme {
    return this.themes.get(this.currentTheme) || this.themes.get('professional')!;
  }

  /**
   * Set theme
   */
  setTheme(themeName: string) {
    if (this.themes.has(themeName)) {
      this.currentTheme = themeName;
    }
  }

  /**
   * Generate Recharts-compatible gradient definitions
   */
  getGradientDefs(): React.ReactElement[] {
    const theme = this.getTheme();
    return theme.colors.gradients.map(gradient => (
      <defs key={gradient.id}>
        <linearGradient
          id={gradient.id}
          x1={gradient.x1}
          y1={gradient.y1}
          x2={gradient.x2}
          y2={gradient.y2}
        >
          {gradient.stops.map((stop, index) => (
            <stop
              key={index}
              offset={stop.offset}
              stopColor={stop.color}
              stopOpacity={stop.opacity || 1}
            />
          ))}
        </linearGradient>
      </defs>
    ));
  }

  /**
   * Get chart configuration
   */
  getChartConfig() {
    const theme = this.getTheme();
    
    return {
      // Recharts configuration
      margin: { top: 20, right: 30, bottom: 40, left: 60 },
      
      // Axis styling
      xAxis: {
        stroke: theme.colors.grid,
        tick: { fill: theme.colors.text.secondary, fontSize: theme.fonts.sizes.tick },
        axisLine: { stroke: theme.colors.grid, strokeWidth: 1 },
        tickLine: false
      },
      
      yAxis: {
        stroke: theme.colors.grid,
        tick: { fill: theme.colors.text.secondary, fontSize: theme.fonts.sizes.tick },
        axisLine: false,
        tickLine: false,
        tickFormatter: (value: number) => this.formatAxisValue(value)
      },
      
      // Grid styling
      cartesianGrid: {
        stroke: theme.colors.grid,
        strokeDasharray: '0',
        strokeOpacity: 0.5,
        vertical: false
      },
      
      // Tooltip styling
      tooltip: {
        contentStyle: {
          backgroundColor: theme.colors.background,
          border: `1px solid ${theme.colors.grid}`,
          borderRadius: '8px',
          padding: '12px',
          boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)',
          fontSize: theme.fonts.sizes.label
        },
        labelStyle: {
          color: theme.colors.text.primary,
          fontWeight: 600,
          marginBottom: '4px'
        },
        itemStyle: {
          color: theme.colors.text.secondary
        }
      },
      
      // Legend styling
      legend: {
        iconType: 'rect' as const,
        wrapperStyle: {
          paddingTop: '20px',
          fontSize: theme.fonts.sizes.legend
        }
      },
      
      // Animation
      animationDuration: theme.animation.duration,
      animationEasing: theme.animation.easing as any
    };
  }

  /**
   * Format axis values intelligently
   */
  formatAxisValue(value: number): string {
    if (Math.abs(value) >= 1e9) {
      return `${(value / 1e9).toFixed(1)}B`;
    }
    if (Math.abs(value) >= 1e6) {
      return `${(value / 1e6).toFixed(1)}M`;
    }
    if (Math.abs(value) >= 1e3) {
      return `${(value / 1e3).toFixed(1)}K`;
    }
    return value.toFixed(0);
  }

  /**
   * Get color palette for a specific chart type
   */
  getColorPalette(type: 'line' | 'bar' | 'area' | 'pie' = 'line'): string[] {
    const theme = this.getTheme();
    
    switch (type) {
      case 'area':
        return theme.colors.gradients.map(g => `url(#${g.id})`);
      case 'pie':
        return theme.colors.primary;
      default:
        return theme.colors.primary;
    }
  }

  /**
   * Apply smooth curves to line/area charts
   */
  getCurveType(): 'monotone' | 'linear' | 'basis' | 'cardinal' {
    return 'monotone'; // Smooth curves like in the reference
  }

  /**
   * Get responsive container configuration
   */
  getResponsiveConfig() {
    return {
      width: '100%' as const,
      height: '100%' as const,
      minHeight: 300,
      aspect: 2.5 // Professional aspect ratio
    };
  }

  /**
   * Export chart styling for external use
   */
  exportStyles() {
    const theme = this.getTheme();
    
    return {
      css: `
        .recharts-wrapper {
          font-family: ${theme.fonts.family};
        }
        
        .recharts-cartesian-axis-tick-value {
          fill: ${theme.colors.text.secondary};
          font-size: ${theme.fonts.sizes.tick}px;
        }
        
        .recharts-legend-item-text {
          color: ${theme.colors.text.secondary} !important;
          font-size: ${theme.fonts.sizes.legend}px !important;
        }
        
        .recharts-tooltip-wrapper {
          outline: none !important;
        }
        
        .recharts-default-tooltip {
          background-color: ${theme.colors.background} !important;
          border: 1px solid ${theme.colors.grid} !important;
          border-radius: 8px !important;
          box-shadow: 0 10px 15px -3px rgb(0 0 0 / 0.1) !important;
        }
        
        .recharts-tooltip-label {
          color: ${theme.colors.text.primary} !important;
          font-weight: 600 !important;
        }
        
        .recharts-tooltip-item {
          color: ${theme.colors.text.secondary} !important;
        }
        
        /* Smooth animations */
        .recharts-layer {
          transition: all ${theme.animation.duration}ms ${theme.animation.easing};
        }
        
        /* Professional hover effects */
        .recharts-bar-rectangle:hover,
        .recharts-pie-sector:hover {
          filter: brightness(1.1);
          transition: filter 200ms ease;
        }
        
        /* Clean dots on line charts */
        .recharts-dot {
          r: 3;
          fill: ${theme.colors.background};
          stroke-width: 2;
        }
        
        .recharts-dot:hover {
          r: 5;
          transition: r 200ms ease;
        }
      `,
      
      theme: theme
    };
  }
}

// Export singleton
export const chartStylingSystem = ChartStylingSystem.getInstance();

// React component for gradient definitions
export const ChartGradients: React.FC = () => {
  const theme = chartStylingSystem.getTheme();
  
  return (
    <svg width="0" height="0">
      {theme.colors.gradients.map(gradient => (
        <defs key={gradient.id}>
          <linearGradient
            id={gradient.id}
            x1={gradient.x1}
            y1={gradient.y1}
            x2={gradient.x2}
            y2={gradient.y2}
          >
            {gradient.stops.map((stop, index) => (
              <stop
                key={index}
                offset={stop.offset}
                stopColor={stop.color}
                stopOpacity={stop.opacity || 1}
              />
            ))}
          </linearGradient>
        </defs>
      ))}
    </svg>
  );
};

// Helper hook for using chart styling
export function useChartStyling(type: 'line' | 'bar' | 'area' | 'pie' = 'line') {
  const config = chartStylingSystem.getChartConfig();
  const colors = chartStylingSystem.getColorPalette(type);
  const theme = chartStylingSystem.getTheme();
  
  return {
    config,
    colors,
    theme,
    formatValue: chartStylingSystem.formatAxisValue
  };
}