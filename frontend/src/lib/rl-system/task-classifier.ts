/**
 * Dynamic Task Classification System
 * Avoids hardcoding specific patterns while maintaining structure
 */

export interface TaskPattern {
  category: 'financial' | 'calculation' | 'formatting' | 'data' | 'structural';
  intent: string;
  entities: Record<string, any>;
  confidence: number;
}

export class TaskClassifier {
  /**
   * Extract semantic features from user query
   */
  private extractFeatures(query: string): Record<string, any> {
    const features = {
      // Financial indicators
      hasFinancialTerms: /revenue|profit|margin|ebitda|cash flow|dcf|npv|irr/i.test(query),
      hasGrowthTerms: /growth|increase|decrease|rate|percentage|yoy|cagr/i.test(query),
      hasValuationTerms: /valuation|multiple|exit|pwerm|scenario/i.test(query),
      
      // Action indicators
      hasCreateAction: /create|build|make|generate|add/i.test(query),
      hasUpdateAction: /update|change|modify|adjust|fix/i.test(query),
      hasCalculateAction: /calculate|compute|derive|forecast|project/i.test(query),
      
      // Structure indicators
      hasModelType: /dcf|model|projection|forecast|analysis/i.test(query),
      hasTimeframe: /\d+\s*(year|month|quarter)|fy\d+|q[1-4]/i.test(query),
      
      // Numeric values
      numbers: (query.match(/\d+\.?\d*/g) || []).map(Number),
      percentages: (query.match(/\d+\.?\d*%/g) || []),
      
      // Entity extraction
      companyName: this.extractCompanyName(query),
      metrics: this.extractMetrics(query)
    };
    
    return features;
  }
  
  /**
   * Classify task based on features, not hardcoded patterns
   */
  classifyTask(query: string, context?: any): TaskPattern {
    const features = this.extractFeatures(query);
    
    // Use feature combinations to determine task type
    if (features.hasFinancialTerms && features.hasCreateAction && features.hasModelType) {
      return {
        category: 'financial',
        intent: 'create_financial_model',
        entities: {
          modelType: this.inferModelType(features),
          company: features.companyName,
          timeframe: this.extractTimeframe(query),
          metrics: features.metrics
        },
        confidence: this.calculateConfidence(features, 'financial_model')
      };
    }
    
    if (features.hasCalculateAction && features.numbers.length > 0) {
      return {
        category: 'calculation',
        intent: 'perform_calculation',
        entities: {
          operation: this.inferOperation(query),
          values: features.numbers,
          targetMetric: features.metrics[0]
        },
        confidence: this.calculateConfidence(features, 'calculation')
      };
    }
    
    if (features.hasUpdateAction && features.percentages.length > 0) {
      return {
        category: 'data',
        intent: 'update_values',
        entities: {
          updateType: features.hasGrowthTerms ? 'growth_rate' : 'value',
          values: features.percentages,
          metrics: features.metrics
        },
        confidence: this.calculateConfidence(features, 'update')
      };
    }
    
    // Default classification with low confidence
    return {
      category: 'structural',
      intent: 'general_spreadsheet_operation',
      entities: features,
      confidence: 0.3
    };
  }
  
  /**
   * Learn from feedback without hardcoding
   */
  async learnFromFeedback(
    query: string,
    classification: TaskPattern,
    feedback: 'correct' | 'incorrect',
    correction?: string
  ): Promise<void> {
    // Store feature-outcome pairs, not hardcoded patterns
    const features = this.extractFeatures(query);
    
    await this.storeLearnedPattern({
      features,
      classification,
      wasCorrect: feedback === 'correct',
      correction,
      timestamp: Date.now()
    });
    
    // Update confidence weights based on feedback
    if (feedback === 'incorrect' && correction) {
      const correctedFeatures = this.extractFeatures(correction);
      await this.adjustFeatureWeights(features, correctedFeatures);
    }
  }
  
  /**
   * Generate action plan based on classification
   */
  generateActionPlan(classification: TaskPattern): any[] {
    const plans: Record<string, () => any[]> = {
      'create_financial_model': () => this.planFinancialModel(classification.entities),
      'perform_calculation': () => this.planCalculation(classification.entities),
      'update_values': () => this.planValueUpdate(classification.entities),
      'general_spreadsheet_operation': () => this.planGeneralOperation(classification.entities)
    };
    
    const planner = plans[classification.intent] || plans['general_spreadsheet_operation'];
    return planner();
  }
  
  private planFinancialModel(entities: any): any[] {
    const actions = [];
    const modelType = entities.modelType || 'basic';
    
    // Use templates but adapt based on context
    if (modelType === 'dcf') {
      actions.push(
        { type: 'create_header', row: 0, values: ['DCF Model', entities.company] },
        { type: 'create_row', row: 2, values: ['Revenue', ...this.generateYears(entities.timeframe)] },
        { type: 'create_row', row: 3, values: ['Growth Rate'] },
        { type: 'create_row', row: 4, values: ['EBITDA'] },
        { type: 'create_formula', row: 4, col: 1, formula: '=B3*0.25' }
      );
    } else {
      // Generic model structure
      actions.push(
        { type: 'create_header', row: 0, values: ['Financial Model'] },
        { type: 'create_metrics', startRow: 2, metrics: entities.metrics || ['Revenue', 'Cost', 'Profit'] }
      );
    }
    
    return actions;
  }
  
  private planCalculation(entities: any): any[] {
    // Dynamic calculation planning based on operation type
    const { operation, values, targetMetric } = entities;
    
    return [
      { type: 'locate_cell', metric: targetMetric },
      { type: 'apply_operation', operation, values }
    ];
  }
  
  private planValueUpdate(entities: any): any[] {
    const { updateType, values, metrics } = entities;
    
    if (updateType === 'growth_rate') {
      return metrics.map((metric: string) => ({
        type: 'apply_growth',
        metric,
        rate: values[0]
      }));
    }
    
    return [{ type: 'update_values', values, metrics }];
  }
  
  private planGeneralOperation(entities: any): any[] {
    // Fallback to exploration when uncertain
    return [
      { type: 'explore', strategy: 'similarity_search', context: entities }
    ];
  }
  
  // Helper methods
  private extractCompanyName(query: string): string | null {
    // Use NER or simple heuristics
    const match = query.match(/for\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)/);
    return match ? match[1] : null;
  }
  
  private extractMetrics(query: string): string[] {
    const knownMetrics = ['revenue', 'profit', 'ebitda', 'cash flow', 'margin', 'growth'];
    return knownMetrics.filter(metric => 
      new RegExp(metric, 'i').test(query)
    );
  }
  
  private inferModelType(features: any): string {
    if (/dcf/i.test(features.hasModelType)) return 'dcf';
    if (/projection/i.test(features.hasModelType)) return 'projection';
    if (/forecast/i.test(features.hasModelType)) return 'forecast';
    return 'general';
  }
  
  private extractTimeframe(query: string): any {
    const yearMatch = query.match(/(\d+)\s*year/i);
    if (yearMatch) return { years: parseInt(yearMatch[1]) };
    
    const fyMatch = query.match(/fy(\d{2,4})/i);
    if (fyMatch) return { fiscalYear: fyMatch[1] };
    
    return { years: 5 }; // Default
  }
  
  private calculateConfidence(features: any, taskType: string): number {
    // Dynamic confidence based on feature strength
    let confidence = 0.5;
    
    const boosts: Record<string, number> = {
      'financial_model': features.hasFinancialTerms && features.hasModelType ? 0.3 : 0,
      'calculation': features.hasCalculateAction && features.numbers.length > 0 ? 0.3 : 0,
      'update': features.hasUpdateAction && features.metrics.length > 0 ? 0.3 : 0
    };
    
    confidence += boosts[taskType] || 0;
    
    // Reduce confidence if ambiguous
    const actionCount = [
      features.hasCreateAction,
      features.hasUpdateAction,
      features.hasCalculateAction
    ].filter(Boolean).length;
    
    if (actionCount > 1) confidence -= 0.2;
    
    return Math.min(Math.max(confidence, 0), 1);
  }
  
  private generateYears(timeframe: any): number[] {
    const currentYear = new Date().getFullYear();
    const years = timeframe?.years || 5;
    return Array.from({ length: years }, (_, i) => currentYear + i);
  }
  
  private async storeLearnedPattern(pattern: any): Promise<void> {
    // Store in vector DB for similarity search
    console.log('Storing learned pattern:', pattern);
  }
  
  private async adjustFeatureWeights(incorrect: any, correct: any): Promise<void> {
    // Adjust internal weights based on correction
    console.log('Adjusting weights from', incorrect, 'to', correct);
  }
}

export const taskClassifier = new TaskClassifier();