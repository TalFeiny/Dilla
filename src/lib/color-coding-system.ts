/**
 * Dynamic Color Coding System for Waterfall Components
 * Learns from examples and applies intelligent color schemes
 */

export interface ColorRule {
  condition: (value: any, context?: any) => boolean;
  color: string;
  label?: string;
  priority?: number;
}

export interface ColorScheme {
  name: string;
  rules: ColorRule[];
  fallbackColor: string;
}

export class ColorCodingSystem {
  private schemes: Map<string, ColorScheme> = new Map();
  private learningHistory: Array<{
    context: string;
    value: any;
    color: string;
    timestamp: Date;
  }> = [];

  constructor() {
    this.initializeDefaultSchemes();
  }

  private initializeDefaultSchemes() {
    // Interest Level Scheme (for YC-style tracking)
    this.addScheme('interest', {
      name: 'interest',
      rules: [
        { 
          condition: (v) => v === 'High' || v === 'high',
          color: '#10b981', // Green
          label: 'High Interest',
          priority: 3
        },
        {
          condition: (v) => v === 'Medium' || v === 'medium' || v?.includes('Medium'),
          color: '#3b82f6', // Blue
          label: 'Medium Interest',
          priority: 2
        },
        {
          condition: (v) => v === 'Low' || v === 'low',
          color: '#6b7280', // Gray
          label: 'Low Interest',
          priority: 1
        },
        {
          condition: (v) => v?.includes('invested') || v?.includes('Invested'),
          color: '#a855f7', // Purple
          label: 'Invested',
          priority: 4
        },
        {
          condition: (v) => v?.includes('passed') || v?.includes('canceled'),
          color: '#ef4444', // Red
          label: 'Passed',
          priority: 0
        }
      ],
      fallbackColor: '#94a3b8'
    });

    // Performance Scheme (for ARR/Revenue metrics)
    this.addScheme('performance', {
      name: 'performance',
      rules: [
        {
          condition: (v, ctx) => {
            const growth = ctx?.growth || v;
            return growth > 30;
          },
          color: '#10b981', // Green - High growth
          label: 'Excellent',
          priority: 4
        },
        {
          condition: (v, ctx) => {
            const growth = ctx?.growth || v;
            return growth > 15 && growth <= 30;
          },
          color: '#3b82f6', // Blue - Good growth
          label: 'Good',
          priority: 3
        },
        {
          condition: (v, ctx) => {
            const growth = ctx?.growth || v;
            return growth > 0 && growth <= 15;
          },
          color: '#fbbf24', // Yellow - Moderate
          label: 'Moderate',
          priority: 2
        },
        {
          condition: (v, ctx) => {
            const growth = ctx?.growth || v;
            return growth <= 0;
          },
          color: '#ef4444', // Red - Negative/No growth
          label: 'Poor',
          priority: 1
        }
      ],
      fallbackColor: '#94a3b8'
    });

    // Exit Scenario Scheme (for PWERM)
    this.addScheme('exit_scenario', {
      name: 'exit_scenario',
      rules: [
        {
          condition: (v) => v?.includes('IPO') || v?.includes('ipo') || v === 'mega_exit',
          color: '#a855f7', // Purple - Best outcome
          label: 'IPO/Mega Exit',
          priority: 5
        },
        {
          condition: (v) => v?.includes('acquisition') || v === 'strategic_acquisition' || v === 'good_exit',
          color: '#10b981', // Green - Good outcome
          label: 'Strategic Acquisition',
          priority: 4
        },
        {
          condition: (v) => v === 'modest_exit' || (typeof v === 'number' && v > 10 && v < 100),
          color: '#3b82f6', // Blue - Moderate outcome
          label: 'Modest Exit',
          priority: 3
        },
        {
          condition: (v) => v === 'zombie' || v?.includes('flat'),
          color: '#fbbf24', // Yellow - Break-even
          label: 'Zombie/Flat',
          priority: 2
        },
        {
          condition: (v) => v === 'liquidation' || v === 'bankruptcy' || v?.includes('write'),
          color: '#ef4444', // Red - Loss
          label: 'Liquidation',
          priority: 1
        }
      ],
      fallbackColor: '#6b7280'
    });

    // Funding Stage Scheme
    this.addScheme('funding_stage', {
      name: 'funding_stage',
      rules: [
        {
          condition: (v) => v?.includes('Pre-seed') || v === 'pre-seed',
          color: '#f3f4f6', // Very light gray
          label: 'Pre-seed',
          priority: 1
        },
        {
          condition: (v) => v?.includes('Seed') || v === 'seed',
          color: '#e5e7eb', // Light gray
          label: 'Seed',
          priority: 2
        },
        {
          condition: (v) => v?.includes('Series A') || v === 'a',
          color: '#93c5fd', // Light blue
          label: 'Series A',
          priority: 3
        },
        {
          condition: (v) => v?.includes('Series B') || v === 'b',
          color: '#60a5fa', // Medium blue
          label: 'Series B',
          priority: 4
        },
        {
          condition: (v) => v?.includes('Series C') || v === 'c',
          color: '#3b82f6', // Blue
          label: 'Series C',
          priority: 5
        },
        {
          condition: (v) => v?.includes('Series D') || v === 'd' || v?.includes('Late'),
          color: '#1e40af', // Dark blue
          label: 'Late Stage',
          priority: 6
        }
      ],
      fallbackColor: '#94a3b8'
    });

    // Value Range Scheme (for dollar amounts)
    this.addScheme('value_range', {
      name: 'value_range',
      rules: [
        {
          condition: (v) => {
            const val = typeof v === 'string' ? parseFloat(v.replace(/[^0-9.-]/g, '')) : v;
            return val >= 1000; // $1B+
          },
          color: '#7c3aed', // Violet - Unicorn+
          label: 'Unicorn+',
          priority: 6
        },
        {
          condition: (v) => {
            const val = typeof v === 'string' ? parseFloat(v.replace(/[^0-9.-]/g, '')) : v;
            return val >= 100 && val < 1000; // $100M-$1B
          },
          color: '#2563eb', // Blue - Large
          label: 'Large',
          priority: 5
        },
        {
          condition: (v) => {
            const val = typeof v === 'string' ? parseFloat(v.replace(/[^0-9.-]/g, '')) : v;
            return val >= 10 && val < 100; // $10M-$100M
          },
          color: '#10b981', // Green - Medium
          label: 'Medium',
          priority: 4
        },
        {
          condition: (v) => {
            const val = typeof v === 'string' ? parseFloat(v.replace(/[^0-9.-]/g, '')) : v;
            return val >= 1 && val < 10; // $1M-$10M
          },
          color: '#fbbf24', // Yellow - Small
          label: 'Small',
          priority: 3
        },
        {
          condition: (v) => {
            const val = typeof v === 'string' ? parseFloat(v.replace(/[^0-9.-]/g, '')) : v;
            return val < 1; // <$1M
          },
          color: '#f87171', // Light red - Micro
          label: 'Micro',
          priority: 2
        }
      ],
      fallbackColor: '#94a3b8'
    });

    // Probability Scheme
    this.addScheme('probability', {
      name: 'probability',
      rules: [
        {
          condition: (v) => v > 0.7 || v > 70,
          color: '#10b981', // Green - High probability
          label: 'High',
          priority: 3
        },
        {
          condition: (v) => (v > 0.3 && v <= 0.7) || (v > 30 && v <= 70),
          color: '#3b82f6', // Blue - Medium probability
          label: 'Medium',
          priority: 2
        },
        {
          condition: (v) => v <= 0.3 || v <= 30,
          color: '#ef4444', // Red - Low probability
          label: 'Low',
          priority: 1
        }
      ],
      fallbackColor: '#6b7280'
    });
  }

  addScheme(name: string, scheme: ColorScheme) {
    this.schemes.set(name, scheme);
  }

  getColor(value: any, schemeName: string, context?: any): string {
    const scheme = this.schemes.get(schemeName);
    if (!scheme) {
      console.warn(`Color scheme '${schemeName}' not found`);
      return '#6b7280'; // Default gray
    }

    // Sort rules by priority (highest first)
    const sortedRules = [...scheme.rules].sort((a, b) => 
      (b.priority || 0) - (a.priority || 0)
    );

    // Find first matching rule
    for (const rule of sortedRules) {
      if (rule.condition(value, context)) {
        // Record this for learning
        this.recordColorUsage(schemeName, value, rule.color);
        return rule.color;
      }
    }

    return scheme.fallbackColor;
  }

  getColorWithLabel(value: any, schemeName: string, context?: any): { color: string; label?: string } {
    const scheme = this.schemes.get(schemeName);
    if (!scheme) {
      return { color: '#6b7280' };
    }

    const sortedRules = [...scheme.rules].sort((a, b) => 
      (b.priority || 0) - (a.priority || 0)
    );

    for (const rule of sortedRules) {
      if (rule.condition(value, context)) {
        this.recordColorUsage(schemeName, value, rule.color);
        return { color: rule.color, label: rule.label };
      }
    }

    return { color: scheme.fallbackColor };
  }

  // Learning system - record color usage patterns
  private recordColorUsage(context: string, value: any, color: string) {
    this.learningHistory.push({
      context,
      value,
      color,
      timestamp: new Date()
    });

    // Keep only last 1000 entries
    if (this.learningHistory.length > 1000) {
      this.learningHistory = this.learningHistory.slice(-1000);
    }
  }

  // Get gradient between two colors
  getGradient(startValue: number, endValue: number, schemeName: string): string {
    const startColor = this.getColor(startValue, schemeName);
    const endColor = this.getColor(endValue, schemeName);
    return `linear-gradient(90deg, ${startColor} 0%, ${endColor} 100%)`;
  }

  // Get color scale for a range of values
  getColorScale(values: number[], schemeName: string): string[] {
    return values.map(v => this.getColor(v, schemeName));
  }

  // Intelligent color suggestion based on historical patterns
  suggestColor(value: any, context: string): string {
    // Look for similar values in history
    const similarEntries = this.learningHistory.filter(entry => 
      entry.context === context && this.isSimilar(entry.value, value)
    );

    if (similarEntries.length > 0) {
      // Return most frequently used color for similar values
      const colorCounts = new Map<string, number>();
      similarEntries.forEach(entry => {
        colorCounts.set(entry.color, (colorCounts.get(entry.color) || 0) + 1);
      });

      let maxCount = 0;
      let suggestedColor = '#6b7280';
      colorCounts.forEach((count, color) => {
        if (count > maxCount) {
          maxCount = count;
          suggestedColor = color;
        }
      });

      return suggestedColor;
    }

    // Fallback to scheme if no history
    return this.getColor(value, context);
  }

  private isSimilar(value1: any, value2: any): boolean {
    if (typeof value1 === 'string' && typeof value2 === 'string') {
      return value1.toLowerCase() === value2.toLowerCase();
    }
    if (typeof value1 === 'number' && typeof value2 === 'number') {
      const ratio = value1 / value2;
      return ratio > 0.8 && ratio < 1.2; // Within 20%
    }
    return value1 === value2;
  }

  // Export learning data for agent memory
  exportLearningData(): any {
    return {
      schemes: Array.from(this.schemes.entries()).map(([name, scheme]) => ({
        name,
        rules: scheme.rules.map(r => ({
          label: r.label,
          color: r.color,
          priority: r.priority
        }))
      })),
      history: this.learningHistory.slice(-100) // Last 100 entries
    };
  }

  // Import learning data from agent memory
  importLearningData(data: any) {
    if (data.history && Array.isArray(data.history)) {
      this.learningHistory = [
        ...this.learningHistory,
        ...data.history.map((h: any) => ({
          ...h,
          timestamp: new Date(h.timestamp)
        }))
      ].slice(-1000);
    }
  }
}

// Singleton instance
export const colorCodingSystem = new ColorCodingSystem();

// Helper functions for common use cases
export const getInterestColor = (interest: string) => 
  colorCodingSystem.getColor(interest, 'interest');

export const getPerformanceColor = (growth: number) => 
  colorCodingSystem.getColor(growth, 'performance', { growth });

export const getExitScenarioColor = (scenario: string) => 
  colorCodingSystem.getColor(scenario, 'exit_scenario');

export const getFundingStageColor = (stage: string) => 
  colorCodingSystem.getColor(stage, 'funding_stage');

export const getValueRangeColor = (value: number) => 
  colorCodingSystem.getColor(value, 'value_range');

export const getProbabilityColor = (probability: number) => 
  colorCodingSystem.getColor(probability, 'probability');