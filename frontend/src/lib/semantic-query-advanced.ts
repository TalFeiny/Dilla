// Advanced Semantic Query Processing with Entity Recognition and Query Planning

import { StructuredQuery } from './semantic-query-processor';

// Enhanced query types for complex operations
export interface QueryPlan {
  steps: QueryStep[];
  dependencies: Map<string, string[]>; // step_id -> [dependent_step_ids]
  cacheStrategy: 'none' | 'aggressive' | 'smart';
  estimatedCost: number; // Relative cost estimate
}

export interface QueryStep {
  id: string;
  type: 'fetch' | 'compute' | 'aggregate' | 'join' | 'filter' | 'enrich';
  source: 'database' | 'web' | 'api' | 'cache' | 'compute';
  operation: string;
  inputs?: string[]; // IDs of steps this depends on
  output: string; // Name of the result set
  confidence?: number;
}

// Entity types for better recognition
export interface RecognizedEntity {
  text: string;
  type: 'company' | 'metric' | 'sector' | 'time' | 'comparison' | 'threshold';
  normalized: string;
  confidence: number;
  metadata?: any;
}

// Temporal query understanding
export interface TemporalContext {
  period: 'day' | 'week' | 'month' | 'quarter' | 'year';
  range?: { start: Date; end: Date };
  comparison?: 'YoY' | 'QoQ' | 'MoM' | 'WoW';
  trending?: boolean;
}

// Relationship types
export type RelationshipType = 
  | 'competitor' 
  | 'similar' 
  | 'parent' 
  | 'subsidiary' 
  | 'investor' 
  | 'portfolio';

// Advanced entity recognition with NER-like capabilities
export class EntityRecognizer {
  private companyDatabase: Set<string>;
  private sectorMap: Map<string, string[]>;
  private metricAliases: Map<string, string>;
  
  constructor() {
    // In production, load from database
    this.companyDatabase = new Set([
      'Stripe', 'OpenAI', 'Anthropic', 'SpaceX', 'Tesla', 'Apple', 'Google',
      'Microsoft', 'Amazon', 'Meta', 'Netflix', 'Uber', 'Airbnb', 'Databricks',
      'Snowflake', 'Palantir', 'Canva', 'Figma', 'Notion', 'Linear', 'Vercel'
    ]);
    
    this.sectorMap = new Map([
      ['SaaS', ['software', 'saas', 'b2b software', 'cloud']],
      ['Fintech', ['fintech', 'financial technology', 'payments', 'banking']],
      ['AI', ['artificial intelligence', 'ai', 'machine learning', 'ml', 'llm']],
      ['Biotech', ['biotech', 'biotechnology', 'pharma', 'healthcare']],
      ['Cleantech', ['cleantech', 'clean energy', 'renewable', 'sustainability']]
    ]);
    
    this.metricAliases = new Map([
      ['revenue', 'revenue'],
      ['sales', 'revenue'],
      ['turnover', 'revenue'],
      ['arr', 'annual_recurring_revenue'],
      ['mrr', 'monthly_recurring_revenue'],
      ['burn', 'burn_rate'],
      ['runway', 'cash_runway'],
      ['ltv', 'lifetime_value'],
      ['cac', 'customer_acquisition_cost'],
      ['nps', 'net_promoter_score'],
      ['churn', 'churn_rate'],
      ['retention', 'retention_rate']
    ]);
  }
  
  recognize(query: string): RecognizedEntity[] {
    const entities: RecognizedEntity[] = [];
    const words = query.split(/\s+/);
    
    // Recognize companies (with fuzzy matching)
    this.companyDatabase.forEach(company => {
      const regex = new RegExp(`\\b${company}(?:'s)?\\b`, 'gi');
      if (regex.test(query)) {
        entities.push({
          text: company,
          type: 'company',
          normalized: company,
          confidence: 1.0
        });
      }
    });
    
    // Recognize sectors
    this.sectorMap.forEach((aliases, sector) => {
      aliases.forEach(alias => {
        if (query.toLowerCase().includes(alias)) {
          entities.push({
            text: alias,
            type: 'sector',
            normalized: sector,
            confidence: 0.9
          });
        }
      });
    });
    
    // Recognize metrics
    this.metricAliases.forEach((normalized, alias) => {
      if (query.toLowerCase().includes(alias)) {
        entities.push({
          text: alias,
          type: 'metric',
          normalized: normalized,
          confidence: 0.95
        });
      }
    });
    
    // Recognize temporal expressions
    const temporalPatterns = [
      { pattern: /last\s+(\d+)\s+(year|month|quarter|week)s?/gi, type: 'time' },
      { pattern: /(?:YoY|year[\s-]over[\s-]year)/gi, type: 'comparison' },
      { pattern: /(?:QoQ|quarter[\s-]over[\s-]quarter)/gi, type: 'comparison' },
      { pattern: /(?:in|since|from)\s+(\d{4})/gi, type: 'time' },
      { pattern: /(?:Q[1-4])\s+(\d{4})/gi, type: 'time' }
    ];
    
    temporalPatterns.forEach(({ pattern, type }) => {
      const matches = Array.from(query.matchAll(pattern));
      matches.forEach(match => {
        entities.push({
          text: match[0],
          type: type as any,
          normalized: match[0],
          confidence: 0.9,
          metadata: { raw: match }
        });
      });
    });
    
    // Recognize thresholds
    const thresholdPattern = /(?:over|above|below|under|more than|less than|between)\s+([\d.]+[MBK%]?)/gi;
    const thresholdMatches = Array.from(query.matchAll(thresholdPattern));
    thresholdMatches.forEach(match => {
      entities.push({
        text: match[0],
        type: 'threshold',
        normalized: match[1],
        confidence: 0.85
      });
    });
    
    return entities;
  }
}

// Query planner for complex multi-step operations
export class QueryPlanner {
  private entityRecognizer: EntityRecognizer;
  
  constructor() {
    this.entityRecognizer = new EntityRecognizer();
  }
  
  createPlan(query: string, entities: RecognizedEntity[]): QueryPlan {
    const steps: QueryStep[] = [];
    const dependencies = new Map<string, string[]>();
    
    // Analyze query complexity
    const isComparison = /compare|versus|vs|difference/i.test(query);
    const isAggregation = /average|mean|sum|total|median/i.test(query);
    const isTrend = /trend|over time|historical|growth/i.test(query);
    const isRelationship = /competitor|similar|like|related/i.test(query);
    
    // Step 1: Fetch base data
    const fetchStep: QueryStep = {
      id: 'fetch_base',
      type: 'fetch',
      source: 'database',
      operation: 'SELECT * FROM companies',
      output: 'base_data'
    };
    steps.push(fetchStep);
    
    // Step 2: Apply filters
    if (entities.some(e => e.type === 'threshold' || e.type === 'sector')) {
      const filterStep: QueryStep = {
        id: 'filter_data',
        type: 'filter',
        source: 'compute',
        operation: 'Apply filters from entities',
        inputs: ['fetch_base'],
        output: 'filtered_data'
      };
      steps.push(filterStep);
      dependencies.set('filter_data', ['fetch_base']);
    }
    
    // Step 3: Enrich with web data if needed
    if (query.includes('latest') || query.includes('recent')) {
      const enrichStep: QueryStep = {
        id: 'enrich_web',
        type: 'enrich',
        source: 'web',
        operation: 'Fetch latest data from web',
        inputs: dependencies.has('filter_data') ? ['filter_data'] : ['fetch_base'],
        output: 'enriched_data'
      };
      steps.push(enrichStep);
    }
    
    // Step 4: Compute aggregations
    if (isAggregation) {
      const aggStep: QueryStep = {
        id: 'aggregate',
        type: 'aggregate',
        source: 'compute',
        operation: this.detectAggregationType(query),
        inputs: [steps[steps.length - 1].id],
        output: 'aggregated_result'
      };
      steps.push(aggStep);
    }
    
    // Step 5: Compute trends
    if (isTrend) {
      const trendStep: QueryStep = {
        id: 'compute_trend',
        type: 'compute',
        source: 'compute',
        operation: 'Calculate time series trends',
        inputs: [steps[steps.length - 1].id],
        output: 'trend_analysis'
      };
      steps.push(trendStep);
    }
    
    // Step 6: Find relationships
    if (isRelationship) {
      const relStep: QueryStep = {
        id: 'find_relationships',
        type: 'compute',
        source: 'compute',
        operation: 'Find similar companies or competitors',
        inputs: [steps[steps.length - 1].id],
        output: 'relationships'
      };
      steps.push(relStep);
    }
    
    // Determine cache strategy
    const cacheStrategy = this.determineCacheStrategy(query, steps);
    
    // Estimate cost
    const estimatedCost = this.estimateCost(steps);
    
    return {
      steps,
      dependencies,
      cacheStrategy,
      estimatedCost
    };
  }
  
  private detectAggregationType(query: string): string {
    if (/average|mean/i.test(query)) return 'AVG';
    if (/sum|total/i.test(query)) return 'SUM';
    if (/count|how many/i.test(query)) return 'COUNT';
    if (/median/i.test(query)) return 'MEDIAN';
    if (/max|maximum|highest/i.test(query)) return 'MAX';
    if (/min|minimum|lowest/i.test(query)) return 'MIN';
    return 'AVG'; // Default
  }
  
  private determineCacheStrategy(query: string, steps: QueryStep[]): 'none' | 'aggressive' | 'smart' {
    // Don't cache if query asks for latest/recent
    if (/latest|recent|current|today/i.test(query)) return 'none';
    
    // Aggressive cache for historical data
    if (/historical|past|previous/i.test(query)) return 'aggressive';
    
    // Smart caching for everything else
    return 'smart';
  }
  
  private estimateCost(steps: QueryStep[]): number {
    const costs = {
      fetch: 1,
      filter: 0.1,
      compute: 0.5,
      aggregate: 0.3,
      join: 2,
      enrich: 3 // Web searches are expensive
    };
    
    return steps.reduce((total, step) => total + (costs[step.type] || 1), 0);
  }
}

// Relationship finder for companies
export class RelationshipFinder {
  findRelationships(
    company: string, 
    type: RelationshipType, 
    data: any[]
  ): string[] {
    const relationships: string[] = [];
    
    switch (type) {
      case 'competitor':
        // Find companies in same sector with similar metrics
        const targetCompany = data.find(c => c.name === company);
        if (targetCompany) {
          data.forEach(c => {
            if (c.name !== company && 
                c.sector === targetCompany.sector &&
                Math.abs(c.revenue - targetCompany.revenue) / targetCompany.revenue < 0.5) {
              relationships.push(c.name);
            }
          });
        }
        break;
        
      case 'similar':
        // Find companies with similar size and growth
        const target = data.find(c => c.name === company);
        if (target) {
          data.forEach(c => {
            if (c.name !== company) {
              const revenueSimilarity = Math.abs(c.revenue - target.revenue) / target.revenue;
              const growthSimilarity = Math.abs(c.growth_rate - target.growth_rate);
              if (revenueSimilarity < 0.3 && growthSimilarity < 0.1) {
                relationships.push(c.name);
              }
            }
          });
        }
        break;
    }
    
    return relationships;
  }
}

// Confidence scoring system
export class ConfidenceScorer {
  scoreDataPoint(value: any, sources: any[]): number {
    let confidence = 0;
    
    // Base confidence by source type
    const sourceConfidence = {
      database: 0.9,
      api: 0.85,
      web: 0.7,
      compute: 0.95,
      estimate: 0.5
    };
    
    // Calculate weighted average
    sources.forEach(source => {
      confidence += sourceConfidence[source.type] || 0.5;
    });
    
    confidence = confidence / sources.length;
    
    // Adjust for data freshness
    const now = new Date();
    sources.forEach(source => {
      if (source.timestamp) {
        const age = (now.getTime() - new Date(source.timestamp).getTime()) / (1000 * 60 * 60 * 24);
        if (age > 30) confidence *= 0.9; // Reduce confidence for data older than 30 days
        if (age > 90) confidence *= 0.8; // Further reduce for data older than 90 days
      }
    });
    
    // Adjust for multiple confirming sources
    if (sources.length > 1) {
      confidence = Math.min(confidence * 1.1, 1.0); // Boost but cap at 1.0
    }
    
    return confidence;
  }
}

// Temporal analyzer for time-based queries
export class TemporalAnalyzer {
  analyzeTemporalContext(query: string): TemporalContext | null {
    const context: TemporalContext = {
      period: 'year',
      trending: false
    };
    
    // Detect period
    if (/daily|per day|each day/i.test(query)) context.period = 'day';
    else if (/weekly|per week|each week/i.test(query)) context.period = 'week';
    else if (/monthly|per month|each month/i.test(query)) context.period = 'month';
    else if (/quarterly|per quarter|each quarter/i.test(query)) context.period = 'quarter';
    else if (/yearly|annual|per year/i.test(query)) context.period = 'year';
    
    // Detect comparison type
    if (/YoY|year[\s-]over[\s-]year/i.test(query)) context.comparison = 'YoY';
    else if (/QoQ|quarter[\s-]over[\s-]quarter/i.test(query)) context.comparison = 'QoQ';
    else if (/MoM|month[\s-]over[\s-]month/i.test(query)) context.comparison = 'MoM';
    
    // Detect trending
    if (/trend|over time|historical/i.test(query)) context.trending = true;
    
    // Parse date ranges
    const rangeMatch = query.match(/from\s+(\d{4})\s+to\s+(\d{4})/i);
    if (rangeMatch) {
      context.range = {
        start: new Date(parseInt(rangeMatch[1]), 0, 1),
        end: new Date(parseInt(rangeMatch[2]), 11, 31)
      };
    }
    
    return context;
  }
  
  computeGrowth(
    data: any[], 
    metric: string, 
    comparison: 'YoY' | 'QoQ' | 'MoM'
  ): number {
    // Implementation would calculate actual growth rates
    // This is a placeholder
    return 0.15; // 15% growth
  }
}

// Query optimizer for performance
export class QueryOptimizer {
  optimize(plan: QueryPlan): QueryPlan {
    const optimizedSteps = [...plan.steps];
    
    // Optimization 1: Combine multiple fetches into one
    const fetchSteps = optimizedSteps.filter(s => s.type === 'fetch');
    if (fetchSteps.length > 1) {
      // Combine into single fetch with JOIN
      const combinedFetch: QueryStep = {
        id: 'combined_fetch',
        type: 'fetch',
        source: 'database',
        operation: 'Optimized multi-table fetch',
        output: 'combined_data'
      };
      
      // Replace multiple fetches with one
      const nonFetchSteps = optimizedSteps.filter(s => s.type !== 'fetch');
      optimizedSteps.length = 0;
      optimizedSteps.push(combinedFetch, ...nonFetchSteps);
    }
    
    // Optimization 2: Push filters down to database level
    const filterStep = optimizedSteps.find(s => s.type === 'filter');
    const fetchStep = optimizedSteps.find(s => s.type === 'fetch');
    if (filterStep && fetchStep) {
      // Merge filter into fetch operation
      fetchStep.operation += ' WHERE ' + filterStep.operation;
      // Remove separate filter step
      const filterIndex = optimizedSteps.indexOf(filterStep);
      optimizedSteps.splice(filterIndex, 1);
    }
    
    // Optimization 3: Reorder for minimal data transfer
    // Move aggregations as early as possible
    
    return {
      ...plan,
      steps: optimizedSteps
    };
  }
}

// Main orchestrator that brings everything together
export class SemanticQueryOrchestrator {
  private entityRecognizer: EntityRecognizer;
  private queryPlanner: QueryPlanner;
  private temporalAnalyzer: TemporalAnalyzer;
  private confidenceScorer: ConfidenceScorer;
  private queryOptimizer: QueryOptimizer;
  private relationshipFinder: RelationshipFinder;
  
  constructor() {
    this.entityRecognizer = new EntityRecognizer();
    this.queryPlanner = new QueryPlanner();
    this.temporalAnalyzer = new TemporalAnalyzer();
    this.confidenceScorer = new ConfidenceScorer();
    this.queryOptimizer = new QueryOptimizer();
    this.relationshipFinder = new RelationshipFinder();
  }
  
  async processQuery(query: string): Promise<any> {
    // 1. Recognize entities
    const entities = this.entityRecognizer.recognize(query);
    
    // 2. Analyze temporal context
    const temporalContext = this.temporalAnalyzer.analyzeTemporalContext(query);
    
    // 3. Create query plan
    const plan = this.queryPlanner.createPlan(query, entities);
    
    // 4. Optimize the plan
    const optimizedPlan = this.queryOptimizer.optimize(plan);
    
    // 5. Execute the plan (would be implemented with actual data fetching)
    const results = await this.executePlan(optimizedPlan);
    
    // 6. Score confidence
    const scoredResults = this.scoreResults(results);
    
    return {
      query,
      entities,
      temporalContext,
      plan: optimizedPlan,
      results: scoredResults
    };
  }
  
  private async executePlan(plan: QueryPlan): Promise<any> {
    // This would execute each step in the plan
    // For now, return mock data
    return {
      data: [],
      sources: []
    };
  }
  
  private scoreResults(results: any): any {
    // Apply confidence scoring to each result
    return {
      ...results,
      confidence: this.confidenceScorer.scoreDataPoint(results.data, results.sources)
    };
  }
}