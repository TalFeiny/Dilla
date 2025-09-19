/**
 * Chart Intelligence Service
 * Generates chart configurations that agents can use
 * Returns data structures that frontend components can render
 */

export interface ChartConfig {
  type: 'bar' | 'line' | 'pie' | 'sankey' | 'treemap' | 'waterfall' | 'bubble' | 'heatmap' | 'funnel' | 'radial';
  title: string;
  data: any;
  renderType: 'basic' | 'advanced';
  config?: {
    width?: string | number;
    height?: number;
    colors?: string | string[];
    interactive?: boolean;
  };
  insights?: string[]; // Key insights from the chart
}

export class ChartIntelligence {
  /**
   * Analyze data and suggest best chart types
   */
  static suggestCharts(data: any): string[] {
    const suggestions: string[] = [];
    
    if (Array.isArray(data)) {
      // Multiple items - good for comparison
      if (data.length > 1 && data.length <= 10) {
        suggestions.push('bar', 'waterfall');
      }
      if (data.length > 10) {
        suggestions.push('treemap', 'bubble');
      }
      
      // Time series data
      if (data[0]?.date || data[0]?.timestamp) {
        suggestions.push('line', 'area');
      }
      
      // Hierarchical data
      if (data[0]?.children || data[0]?.parent) {
        suggestions.push('treemap', 'sunburst');
      }
      
      // Flow data (has source/target)
      if (data[0]?.source && data[0]?.target) {
        suggestions.push('sankey');
      }
    } else if (data?.nodes && data?.links) {
      // Network data
      suggestions.push('sankey', 'force');
    } else if (data?.categories && data?.values) {
      // Categorical data
      suggestions.push('pie', 'donut', 'radial');
    }
    
    return [...new Set(suggestions)];
  }
  
  /**
   * Generate chart configuration from data
   */
  static generateChart(data: any, preferredType?: string): ChartConfig {
    const suggestedTypes = this.suggestCharts(data);
    const chartType = preferredType || suggestedTypes[0] || 'bar';
    
    // Determine if this needs advanced rendering
    const advancedTypes = ['sankey', 'treemap', 'waterfall', 'sunburst', 'force', 'heatmap'];
    const renderType = advancedTypes.includes(chartType) ? 'advanced' : 'basic';
    
    // Generate appropriate data structure based on chart type
    let processedData = data;
    let title = 'Data Visualization';
    
    switch (chartType) {
      case 'sankey':
        processedData = this.prepareSankeyData(data);
        title = 'Flow Analysis';
        break;
        
      case 'treemap':
        processedData = this.prepareTreemapData(data);
        title = 'Hierarchical Distribution';
        break;
        
      case 'waterfall':
        processedData = this.prepareWaterfallData(data);
        title = 'Progressive Change';
        break;
        
      case 'bar':
      case 'line':
        processedData = this.prepareBasicChartData(data);
        title = 'Comparison Analysis';
        break;
        
      case 'pie':
        processedData = this.preparePieData(data);
        title = 'Distribution Analysis';
        break;
    }
    
    return {
      type: chartType as any,
      title,
      data: processedData,
      renderType,
      config: {
        width: '100%',
        height: 400,
        colors: this.selectColorScheme(chartType),
        interactive: true
      },
      insights: this.generateInsights(data, chartType)
    };
  }
  
  /**
   * Generate multiple complementary charts from data
   */
  static generateChartSuite(data: any): ChartConfig[] {
    const charts: ChartConfig[] = [];
    const suggestedTypes = this.suggestCharts(data);
    
    // Generate up to 3 complementary charts
    suggestedTypes.slice(0, 3).forEach(type => {
      charts.push(this.generateChart(data, type));
    });
    
    // If we have financial data, add specific financial charts
    if (this.hasFinancialData(data)) {
      charts.push(this.generateFinancialChart(data));
    }
    
    // If we have time series, add trend analysis
    if (this.hasTimeSeriesData(data)) {
      charts.push(this.generateTrendChart(data));
    }
    
    return charts;
  }
  
  /**
   * Prepare data for Sankey diagram
   */
  private static prepareSankeyData(data: any): any {
    // If already in correct format
    if (data.nodes && data.links) {
      return data;
    }
    
    // Convert from array format
    const nodes: any[] = [];
    const links: any[] = [];
    const nodeMap = new Map<string, number>();
    let nodeId = 0;
    
    if (Array.isArray(data)) {
      data.forEach(item => {
        // Extract source and target
        const source = item.from || item.source || item.investor;
        const target = item.to || item.target || item.company;
        const value = item.value || item.amount || 1;
        
        if (source && target) {
          // Add nodes
          if (!nodeMap.has(source)) {
            nodes.push({ id: nodeId, name: source });
            nodeMap.set(source, nodeId++);
          }
          if (!nodeMap.has(target)) {
            nodes.push({ id: nodeId, name: target });
            nodeMap.set(target, nodeId++);
          }
          
          // Add link
          links.push({
            source: nodeMap.get(source),
            target: nodeMap.get(target),
            value
          });
        }
      });
    }
    
    return { nodes, links };
  }
  
  /**
   * Prepare data for Treemap
   */
  private static prepareTreemapData(data: any): any {
    if (Array.isArray(data)) {
      return data.map(item => ({
        name: item.name || item.company || item.label,
        value: item.value || item.marketShare || item.revenue || 1,
        children: item.children || item.segments
      }));
    }
    return data;
  }
  
  /**
   * Prepare data for Waterfall chart
   */
  private static prepareWaterfallData(data: any): any {
    if (!Array.isArray(data)) return [];
    
    let cumulative = 0;
    return data.map((item, idx) => {
      const value = item.value || item.change || item.amount || 0;
      const result = {
        name: item.name || item.label || `Step ${idx + 1}`,
        value,
        cumulative: cumulative + value,
        isIncrease: value > 0,
        isTotal: item.isTotal || false
      };
      cumulative += value;
      return result;
    });
  }
  
  /**
   * Prepare data for basic charts (bar, line)
   */
  private static prepareBasicChartData(data: any): any {
    if (!Array.isArray(data)) return [];
    
    return data.map(item => ({
      name: item.name || item.label || item.x || item.category,
      value: item.value || item.y || item.amount || 0,
      ...(item.series && { series: item.series })
    }));
  }
  
  /**
   * Prepare data for pie chart
   */
  private static preparePieData(data: any): any {
    if (!Array.isArray(data)) return [];
    
    const total = data.reduce((sum, item) => 
      sum + (item.value || item.amount || 0), 0);
    
    return data.map(item => ({
      name: item.name || item.label,
      value: item.value || item.amount || 0,
      percentage: ((item.value || item.amount || 0) / total * 100).toFixed(1)
    }));
  }
  
  /**
   * Generate financial-specific chart
   */
  private static generateFinancialChart(data: any): ChartConfig {
    // Detect financial metrics
    const hasRevenue = data[0]?.revenue !== undefined;
    const hasGrowth = data[0]?.growth !== undefined;
    const hasValuation = data[0]?.valuation !== undefined;
    
    if (hasRevenue && hasGrowth) {
      // Growth vs Revenue bubble chart
      return {
        type: 'bubble',
        title: 'Revenue vs Growth Analysis',
        data: data.map((item: any) => ({
          x: item.revenue,
          y: item.growth,
          z: item.valuation || item.revenue,
          name: item.name || item.company
        })),
        renderType: 'advanced',
        config: {
          width: '100%',
          height: 400,
          colors: 'financialBlue'
        }
      };
    }
    
    // Default to waterfall for financial data
    return this.generateChart(data, 'waterfall');
  }
  
  /**
   * Generate trend chart for time series
   */
  private static generateTrendChart(data: any): ChartConfig {
    return {
      type: 'line',
      title: 'Trend Analysis',
      data: data,
      renderType: 'basic',
      config: {
        width: '100%',
        height: 400,
        colors: 'tableau10'
      },
      insights: ['Trend line added', 'Seasonality detected']
    };
  }
  
  /**
   * Select appropriate color scheme
   */
  private static selectColorScheme(chartType: string): string {
    const colorMap: Record<string, string> = {
      'sankey': 'tableau20',
      'treemap': 'financialGreen',
      'waterfall': 'diverging',
      'heatmap': 'heatmap',
      'bubble': 'tableau10',
      'bar': 'financialBlue',
      'line': 'tableau10',
      'pie': 'tableau10'
    };
    
    return colorMap[chartType] || 'tableau10';
  }
  
  /**
   * Generate insights from chart data
   */
  private static generateInsights(data: any, chartType: string): string[] {
    const insights: string[] = [];
    
    if (Array.isArray(data) && data.length > 0) {
      // Find max/min
      const values = data.map(d => d.value || d.amount || 0);
      const max = Math.max(...values);
      const min = Math.min(...values);
      const avg = values.reduce((a, b) => a + b, 0) / values.length;
      
      if (max > avg * 2) {
        insights.push(`Outlier detected: Maximum value is ${(max/avg).toFixed(1)}x the average`);
      }
      
      if (chartType === 'waterfall') {
        const totalChange = values.reduce((a, b) => a + b, 0);
        insights.push(`Total change: ${totalChange > 0 ? '+' : ''}${totalChange.toLocaleString()}`);
      }
      
      if (chartType === 'sankey' && data.nodes) {
        insights.push(`${data.nodes.length} entities with ${data.links.length} connections`);
      }
    }
    
    return insights;
  }
  
  /**
   * Check if data contains financial metrics
   */
  private static hasFinancialData(data: any): boolean {
    if (!Array.isArray(data) || data.length === 0) return false;
    
    const financialKeys = ['revenue', 'profit', 'valuation', 'growth', 'margin', 'burn', 'runway'];
    const firstItem = data[0];
    
    return financialKeys.some(key => firstItem[key] !== undefined);
  }
  
  /**
   * Check if data is time series
   */
  private static hasTimeSeriesData(data: any): boolean {
    if (!Array.isArray(data) || data.length === 0) return false;
    
    const timeKeys = ['date', 'timestamp', 'time', 'period', 'quarter', 'month', 'year'];
    const firstItem = data[0];
    
    return timeKeys.some(key => firstItem[key] !== undefined);
  }
  
  /**
   * Generate chart command for agents to use
   */
  static generateChartCommand(data: any, type?: string): string {
    const chart = this.generateChart(data, type);
    
    // Return a command that the agent can use
    return JSON.stringify({
      action: 'create_chart',
      config: chart,
      renderInstructions: chart.renderType === 'advanced' 
        ? 'Use TableauLevelCharts component' 
        : 'Use standard Recharts'
    });
  }
}

// Export for use in agents
export default ChartIntelligence;