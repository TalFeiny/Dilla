/**
 * Data Reconciliation System
 * Intelligently combines user input, external data, database, and benchmarks
 */

export interface DataSource {
  type: 'user' | 'website' | 'external' | 'database' | 'benchmark';
  value: any;
  confidence: number; // 0-1
  source: string;
  timestamp?: Date;
}

export interface CompanyMetrics {
  revenue?: DataSource[];
  growth?: DataSource[];
  valuation?: DataSource[];
  funding?: DataSource[];
  employees?: DataSource[];
  [key: string]: DataSource[] | undefined;
}

export class DataReconciler {
  /**
   * Extract user-specified metrics from prompt
   * e.g., "Company X is at 3M ARR" -> { revenue: 3000000 }
   */
  extractUserMetrics(prompt: string): Record<string, any> {
    const metrics: Record<string, any> = {};
    
    // Patterns for user-specified values
    const patterns = [
      // Revenue patterns
      /([A-Z][\w\s]+?)\s+(?:is at|has|with)\s+\$?([\d.]+)\s*(M|B|K)?\s*(?:ARR|MRR|revenue)/gi,
      /([A-Z][\w\s]+?)\s+(?:revenue|ARR|MRR)\s+(?:is|of|at)\s+\$?([\d.]+)\s*(M|B|K)?/gi,
      
      // Valuation patterns  
      /([A-Z][\w\s]+?)\s+(?:valued at|valuation of)\s+\$?([\d.]+)\s*(M|B)?/gi,
      
      // Growth patterns
      /([A-Z][\w\s]+?)\s+(?:growing|growth)\s+(?:at|of|by)\s+([\d.]+)%/gi,
      
      // Employee patterns
      /([A-Z][\w\s]+?)\s+has\s+([\d,]+)\s+(?:employees|people|staff)/gi
    ];
    
    for (const pattern of patterns) {
      const matches = [...prompt.matchAll(pattern)];
      for (const match of matches) {
        const company = match[1].trim();
        const value = parseFloat(match[2].replace(/,/g, ''));
        const unit = match[3]?.toUpperCase();
        
        let finalValue = value;
        if (unit === 'K') finalValue *= 1e3;
        if (unit === 'M') finalValue *= 1e6;
        if (unit === 'B') finalValue *= 1e9;
        
        if (!metrics[company]) metrics[company] = {};
        
        if (pattern.source?.includes('revenue') || pattern.source?.includes('ARR')) {
          metrics[company].revenue = finalValue;
        } else if (pattern.source?.includes('valuation')) {
          metrics[company].valuation = finalValue;
        } else if (pattern.source?.includes('growth')) {
          metrics[company].growth = value / 100; // Convert percentage
        } else if (pattern.source?.includes('employees')) {
          metrics[company].employees = value;
        }
      }
    }
    
    return metrics;
  }
  
  /**
   * Reconcile data from multiple sources
   */
  reconcileData(
    company: string,
    userMetrics: any,
    websiteData: any,
    externalData: any,
    databaseData: any,
    benchmarks: any
  ): CompanyMetrics {
    const reconciled: CompanyMetrics = {};
    
    // Revenue reconciliation
    reconciled.revenue = [];
    
    // Priority 1: User-specified
    if (userMetrics?.revenue) {
      reconciled.revenue.push({
        type: 'user',
        value: userMetrics.revenue,
        confidence: 1.0,
        source: 'User specified in prompt'
      });
    }
    
    // Priority 2: Company website (CIM scraper)
    if (websiteData?.financials?.revenue) {
      const value = this.parseMonetaryValue(websiteData.financials.revenue);
      if (value) {
        reconciled.revenue.push({
          type: 'website',
          value,
          confidence: 0.9,
          source: 'Company website'
        });
      }
    }
    
    // Priority 3: External search
    if (externalData?.revenue) {
      reconciled.revenue.push({
        type: 'external',
        value: externalData.revenue,
        confidence: 0.8,
        source: externalData.revenueSource || 'Web search'
      });
    }
    
    // Priority 4: Database
    if (databaseData?.revenue_usd || databaseData?.arr_usd) {
      const value = databaseData.revenue_usd || databaseData.arr_usd;
      reconciled.revenue.push({
        type: 'database',
        value,
        confidence: databaseData.revenue_usd ? 0.7 : 0.5, // Lower confidence for estimates
        source: databaseData.revenue_usd ? 'Database (actual)' : 'Database (estimated)'
      });
    }
    
    // Priority 5: Benchmarks
    if (benchmarks?.revenue) {
      reconciled.revenue.push({
        type: 'benchmark',
        value: benchmarks.revenue,
        confidence: 0.3,
        source: `Benchmark for ${benchmarks.stage || 'similar'} companies`
      });
    }
    
    // Similar for other metrics...
    this.reconcileMetric('growth', reconciled, userMetrics, websiteData, externalData, databaseData, benchmarks);
    this.reconcileMetric('valuation', reconciled, userMetrics, websiteData, externalData, databaseData, benchmarks);
    this.reconcileMetric('funding', reconciled, userMetrics, websiteData, externalData, databaseData, benchmarks);
    this.reconcileMetric('employees', reconciled, userMetrics, websiteData, externalData, databaseData, benchmarks);
    
    return reconciled;
  }
  
  private reconcileMetric(
    metric: string,
    reconciled: CompanyMetrics,
    userMetrics: any,
    websiteData: any,
    externalData: any,
    databaseData: any,
    benchmarks: any
  ) {
    reconciled[metric] = [];
    
    // Add sources in priority order
    if (userMetrics?.[metric]) {
      reconciled[metric]!.push({
        type: 'user',
        value: userMetrics[metric],
        confidence: 1.0,
        source: 'User specified'
      });
    }
    
    // Map database fields
    const dbFieldMap: Record<string, string> = {
      growth: 'growth_rate',
      valuation: 'valuation_usd',
      funding: 'total_funding_usd',
      employees: 'employee_count'
    };
    
    if (databaseData?.[dbFieldMap[metric]]) {
      reconciled[metric]!.push({
        type: 'database',
        value: databaseData[dbFieldMap[metric]],
        confidence: 0.6,
        source: 'Database'
      });
    }
  }
  
  /**
   * Get the best value for a metric
   */
  getBestValue(metrics: DataSource[]): any {
    if (!metrics || metrics.length === 0) return null;
    
    // Sort by confidence
    const sorted = [...metrics].sort((a, b) => b.confidence - a.confidence);
    
    // Return highest confidence value
    return sorted[0].value;
  }
  
  /**
   * Format reconciled data for context
   */
  formatForContext(company: string, reconciled: CompanyMetrics): string {
    let context = `\n=== ${company.toUpperCase()} DATA ===\n`;
    
    for (const [metric, sources] of Object.entries(reconciled)) {
      if (!sources || sources.length === 0) continue;
      
      const bestValue = this.getBestValue(sources);
      const bestSource = sources.find(s => s.value === bestValue);
      
      context += `\n${metric.toUpperCase()}:\n`;
      context += `  USE THIS → ${this.formatValue(metric, bestValue)} [${bestSource?.source}]\n`;
      
      // Show other sources if they differ significantly
      for (const source of sources) {
        if (source.value !== bestValue) {
          const diff = this.calculateDifference(bestValue, source.value);
          if (Math.abs(diff) > 0.2) { // More than 20% difference
            context += `  Alt: ${this.formatValue(metric, source.value)} [${source.source}] (${diff > 0 ? '+' : ''}${(diff * 100).toFixed(0)}%)\n`;
          }
        }
      }
    }
    
    return context;
  }
  
  private parseMonetaryValue(str: string): number | null {
    if (!str) return null;
    
    const match = str.match(/\$?([\d.]+)\s*(M|B|K)?/i);
    if (!match) return null;
    
    let value = parseFloat(match[1]);
    const unit = match[2]?.toUpperCase();
    
    if (unit === 'K') value *= 1e3;
    if (unit === 'M') value *= 1e6;
    if (unit === 'B') value *= 1e9;
    
    return value;
  }
  
  private formatValue(metric: string, value: any): string {
    if (value === null || value === undefined) return 'N/A';
    
    if (metric === 'revenue' || metric === 'valuation' || metric === 'funding') {
      if (value >= 1e9) return `$${(value / 1e9).toFixed(1)}B`;
      if (value >= 1e6) return `$${(value / 1e6).toFixed(1)}M`;
      if (value >= 1e3) return `$${(value / 1e3).toFixed(0)}K`;
      return `$${value.toLocaleString()}`;
    }
    
    if (metric === 'growth') {
      return `${(value * 100).toFixed(0)}%`;
    }
    
    if (metric === 'employees') {
      return value.toLocaleString();
    }
    
    return String(value);
  }
  
  private calculateDifference(value1: number, value2: number): number {
    if (!value1 || !value2) return 0;
    return (value1 - value2) / value2;
  }
  
  /**
   * Enrich benchmarks with market search
   */
  async enrichBenchmarks(
    sector: string,
    stage: string,
    geography: string,
    searchResults: any
  ): Promise<any> {
    const baseBenchmarks = this.getBaseBenchmarks(sector, stage, geography);
    
    // Extract market metrics from search results
    if (searchResults && searchResults.metrics) {
      // Adjust benchmarks based on actual market data
      if (searchResults.metrics.medianRevenue) {
        baseBenchmarks.revenue = searchResults.metrics.medianRevenue;
      }
      
      if (searchResults.metrics.medianGrowth) {
        baseBenchmarks.growth = searchResults.metrics.medianGrowth;
      }
      
      if (searchResults.metrics.medianValuation) {
        baseBenchmarks.valuationMultiple = searchResults.metrics.medianValuation / baseBenchmarks.revenue;
      }
    }
    
    return baseBenchmarks;
  }
  
  private getBaseBenchmarks(sector: string, stage: string, geography: string): any {
    // Base US benchmarks
    const benchmarks: any = {
      'seed': { revenue: 0.5e6, growth: 2.0, valuationMultiple: 20 },
      'series-a': { revenue: 2e6, growth: 1.5, valuationMultiple: 15 },
      'series-b': { revenue: 10e6, growth: 1.0, valuationMultiple: 10 },
      'series-c': { revenue: 30e6, growth: 0.7, valuationMultiple: 8 },
      'series-d': { revenue: 75e6, growth: 0.5, valuationMultiple: 6 }
    };
    
    const base = benchmarks[stage.toLowerCase()] || benchmarks['series-b'];
    
    // Geographic adjustments only (no sector multipliers)
    if (geography === 'UK') {
      base.valuationMultiple *= 0.75; // 25% discount
    } else if (geography === 'EU') {
      base.valuationMultiple *= 0.70; // 30% discount
    }
    
    return base;
  }
}

export const dataReconciler = new DataReconciler();