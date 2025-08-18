'use client';

export interface RewardComponents {
  correctness: number;      // -1 to 1: Is the value/formula correct?
  relevance: number;        // 0 to 1: Does it match user intent?
  efficiency: number;       // 0 to 1: How efficient was the action?
  completeness: number;     // 0 to 1: Progress toward goal
  formatting: number;       // 0 to 1: Proper formatting applied?
  consistency: number;      // 0 to 1: Consistent with existing data?
  complexity: number;       // 0 to 1: Appropriate complexity for task?
}

export interface RewardBreakdown {
  totalReward: number;      // -1 to 1 overall score
  components: RewardComponents;
  explanation: string[];
  confidence: number;       // 0 to 1: How confident in this reward
}

export class RewardCalculator {
  
  // Calculate automatic reward based on grid state changes
  calculateAutomaticReward(
    stateBefore: Record<string, any>,
    stateAfter: Record<string, any>,
    action: string,
    userIntent: string,
    modelType?: string
  ): RewardBreakdown {
    const components: RewardComponents = {
      correctness: 0,
      relevance: 0,
      efficiency: 0,
      completeness: 0,
      formatting: 0,
      consistency: 0,
      complexity: 0
    };
    
    const explanations: string[] = [];
    
    // 1. Correctness - Check if formulas are valid and values reasonable
    components.correctness = this.evaluateCorrectness(stateBefore, stateAfter, action);
    if (components.correctness < 0) {
      explanations.push('Formula errors or invalid values detected');
    } else if (components.correctness > 0.5) {
      explanations.push('Values and formulas appear correct');
    }
    
    // 2. Relevance - Does action match intent?
    components.relevance = this.evaluateRelevance(action, userIntent, modelType);
    if (components.relevance > 0.7) {
      explanations.push('Action highly relevant to user request');
    } else if (components.relevance < 0.3) {
      explanations.push('Action seems unrelated to request');
    }
    
    // 3. Efficiency - Was this the optimal action?
    components.efficiency = this.evaluateEfficiency(stateBefore, stateAfter, action);
    if (components.efficiency > 0.8) {
      explanations.push('Efficient action choice');
    }
    
    // 4. Completeness - Progress toward complete model
    components.completeness = this.evaluateCompleteness(stateAfter, modelType);
    explanations.push(`Model ${Math.round(components.completeness * 100)}% complete`);
    
    // 5. Formatting - Proper formatting applied?
    components.formatting = this.evaluateFormatting(stateAfter, modelType);
    
    // 6. Consistency - Consistent with existing patterns?
    components.consistency = this.evaluateConsistency(stateBefore, stateAfter);
    
    // 7. Complexity - Appropriate for the task?
    components.complexity = this.evaluateComplexity(action, userIntent);
    
    // Calculate weighted total reward with adaptive weights
    const weights = this.getAdaptiveWeights(modelType, components);
    const totalReward = this.calculateWeightedReward(components, weights);
    
    // Confidence based on how much data we have
    const confidence = this.calculateConfidence(stateBefore, stateAfter);
    
    return {
      totalReward,
      components,
      explanation: explanations,
      confidence
    };
  }
  
  // Evaluate if values and formulas are correct
  private evaluateCorrectness(
    stateBefore: Record<string, any>,
    stateAfter: Record<string, any>,
    action: string
  ): number {
    let score = 0.7; // Start with positive bias for valid actions
    
    // Check for formula errors - severe penalty
    const hasErrors = Object.values(stateAfter).some(cell => 
      cell?.value === '#ERROR' || cell?.value === '#DIV/0!' || cell?.value === '#REF!'
    );
    if (hasErrors) return -1.0; // Maximum penalty for errors
    
    // Check if formulas reference valid cells
    if (action.includes('formula')) {
      const formulaMatch = action.match(/=([A-Z0-9+\-*/():, ]+)/);
      if (formulaMatch) {
        const referencedCells = formulaMatch[1].match(/[A-Z]+\d+/g) || [];
        const allValid = referencedCells.every(cell => 
          stateAfter[cell]?.value !== undefined
        );
        score = allValid ? 0.8 : 0.3;
      }
    }
    
    // Check for reasonable values (not NaN, not infinite)
    const values = Object.values(stateAfter)
      .map(cell => cell?.value)
      .filter(v => typeof v === 'number');
    
    const hasInvalidNumbers = values.some(v => 
      isNaN(v) || !isFinite(v) || Math.abs(v) > 1e15
    );
    if (hasInvalidNumbers) score -= 0.3;
    
    return Math.max(-1, Math.min(1, score));
  }
  
  // Evaluate relevance to user intent
  private evaluateRelevance(
    action: string,
    userIntent: string,
    modelType?: string
  ): number {
    const intentLower = userIntent.toLowerCase();
    const actionLower = action.toLowerCase();
    
    // Check for specific model type keywords
    if (modelType === 'DCF') {
      if (intentLower.includes('discount') && actionLower.includes('0.1')) return 0.9;
      if (intentLower.includes('cash flow') && actionLower.includes('revenue')) return 0.8;
      if (intentLower.includes('terminal') && actionLower.includes('growth')) return 0.7;
    }
    
    // Check for general intent matching
    if (intentLower.includes('sum') && actionLower.includes('sum(')) return 0.9;
    if (intentLower.includes('average') && actionLower.includes('average(')) return 0.9;
    if (intentLower.includes('format') && actionLower.includes('.format')) return 0.8;
    if (intentLower.includes('style') && actionLower.includes('.style')) return 0.8;
    
    // Check for cell references matching
    const intentCells = intentLower.match(/[a-z]\d+/g) || [];
    const actionCells = actionLower.match(/[a-z]\d+/g) || [];
    const overlap = intentCells.filter(c => actionCells.includes(c)).length;
    if (overlap > 0) return 0.6 + (overlap * 0.1);
    
    return 0.3; // Default low relevance
  }
  
  // Evaluate action efficiency
  private evaluateEfficiency(
    stateBefore: Record<string, any>,
    stateAfter: Record<string, any>,
    action: string
  ): number {
    // Penalize redundant actions
    const cellsChangedBefore = Object.keys(stateBefore).length;
    const cellsChangedAfter = Object.keys(stateAfter).length;
    const delta = cellsChangedAfter - cellsChangedBefore;
    
    // No change = inefficient
    if (delta === 0 && !action.includes('format') && !action.includes('style')) {
      return 0.1;
    }
    
    // Check if action overwrote existing data unnecessarily
    const actionMatch = action.match(/grid\.\w+\("([A-Z]\d+)"/);
    if (actionMatch) {
      const targetCell = actionMatch[1];
      if (stateBefore[targetCell]?.value && !action.includes('clear')) {
        return 0.4; // Overwriting data without clear intent
      }
    }
    
    // Efficient if it changes expected amount
    if (action.includes('writeRange') && delta > 1) return 0.9;
    if (action.includes('write') && delta === 1) return 0.8;
    if (action.includes('formula') && delta === 1) return 0.85;
    
    return 0.7;
  }
  
  // Evaluate model completeness
  private evaluateCompleteness(
    state: Record<string, any>,
    modelType?: string
  ): number {
    const filledCells = Object.keys(state).length;
    
    // Expected cells for different model types
    const expectedCells: Record<string, number> = {
      'DCF': 50,      // Revenue, costs, FCF, discount, terminal value, etc.
      'LBO': 60,      // Entry, exit, debt schedule, returns, etc.
      'Comparables': 30, // Companies, multiples, median/average
      'P&L': 40,      // Revenue lines, expense categories, margins
      'General': 20   // Basic model
    };
    
    const expected = expectedCells[modelType || 'General'];
    const completeness = Math.min(1, filledCells / expected);
    
    // Bonus for having formulas (indicates dynamic model)
    const formulaCount = Object.values(state).filter(cell => cell?.formula).length;
    const formulaBonus = Math.min(0.2, formulaCount * 0.02);
    
    return Math.min(1, completeness + formulaBonus);
  }
  
  // Evaluate formatting quality
  private evaluateFormatting(
    state: Record<string, any>,
    modelType?: string
  ): number {
    let score = 0.5;
    
    // Check if currency values are formatted
    const currencyValues = Object.entries(state).filter(([_, cell]) => {
      const value = cell?.value;
      return typeof value === 'number' && value > 100;
    });
    
    const formattedCurrency = currencyValues.filter(([_, cell]) => 
      cell?.format === 'currency'
    ).length;
    
    if (currencyValues.length > 0) {
      score = formattedCurrency / currencyValues.length;
    }
    
    // Check if percentages are formatted
    const percentValues = Object.entries(state).filter(([_, cell]) => {
      const value = cell?.value;
      return typeof value === 'number' && value > 0 && value < 1;
    });
    
    const formattedPercent = percentValues.filter(([_, cell]) => 
      cell?.format === 'percentage'
    ).length;
    
    if (percentValues.length > 0) {
      const percentScore = formattedPercent / percentValues.length;
      score = (score + percentScore) / 2;
    }
    
    // Check for headers with bold styling
    const hasStyles = Object.values(state).some(cell => cell?.style?.bold);
    if (hasStyles) score += 0.1;
    
    return Math.min(1, score);
  }
  
  // Evaluate consistency with existing data
  private evaluateConsistency(
    stateBefore: Record<string, any>,
    stateAfter: Record<string, any>
  ): number {
    // Check if new data follows patterns from existing data
    const existingFormats = new Set(
      Object.values(stateBefore)
        .map(cell => cell?.format)
        .filter(Boolean)
    );
    
    const newCells = Object.entries(stateAfter).filter(([key, _]) => 
      !stateBefore[key]
    );
    
    if (newCells.length === 0) return 0.8; // No new cells, neutral consistency
    
    // Check if new cells follow existing patterns
    let consistentCount = 0;
    newCells.forEach(([_, cell]) => {
      if (cell?.format && existingFormats.has(cell.format)) {
        consistentCount++;
      }
    });
    
    const consistency = newCells.length > 0 
      ? consistentCount / newCells.length 
      : 0.5;
    
    return 0.5 + (consistency * 0.5); // Scale to 0.5-1.0
  }
  
  // Evaluate if complexity matches the task
  private evaluateComplexity(action: string, userIntent: string): number {
    const intentComplexity = this.estimateIntentComplexity(userIntent);
    const actionComplexity = this.estimateActionComplexity(action);
    
    // Perfect match = 1.0, too simple = lower, too complex = lower
    const difference = Math.abs(intentComplexity - actionComplexity);
    return Math.max(0, 1 - difference);
  }
  
  private estimateIntentComplexity(intent: string): number {
    const lower = intent.toLowerCase();
    if (lower.includes('simple') || lower.includes('basic')) return 0.2;
    if (lower.includes('complex') || lower.includes('advanced')) return 0.8;
    if (lower.includes('dcf') || lower.includes('lbo')) return 0.7;
    if (lower.length > 100) return 0.6;
    return 0.4;
  }
  
  private estimateActionComplexity(action: string): number {
    if (action.includes('writeRange')) return 0.6;
    if (action.includes('SUM') || action.includes('AVERAGE')) return 0.5;
    if (action.includes('formula')) return 0.4;
    if (action.includes('write')) return 0.2;
    if (action.includes('style') || action.includes('format')) return 0.1;
    return 0.3;
  }
  
  // Get weights based on model type
  private getWeights(modelType?: string): Record<keyof RewardComponents, number> {
    const defaultWeights = {
      correctness: 0.3,
      relevance: 0.25,
      efficiency: 0.1,
      completeness: 0.15,
      formatting: 0.05,
      consistency: 0.1,
      complexity: 0.05
    };
    
    // Adjust weights for specific model types
    if (modelType === 'DCF' || modelType === 'LBO') {
      return {
        correctness: 0.35,  // More important for financial models
        relevance: 0.2,
        efficiency: 0.1,
        completeness: 0.2,  // Complete model important
        formatting: 0.05,
        consistency: 0.05,
        complexity: 0.05
      };
    }
    
    return defaultWeights;
  }
  
  // Get adaptive weights based on component scores
  private getAdaptiveWeights(
    modelType?: string, 
    components?: RewardComponents
  ): Record<keyof RewardComponents, number> {
    const baseWeights = this.getWeights(modelType);
    
    if (!components) return baseWeights;
    
    // Adaptively adjust weights based on component scores
    const adjustedWeights = { ...baseWeights };
    
    // If correctness is very bad, make it more important
    if (components.correctness < -0.5) {
      adjustedWeights.correctness = 0.5; // Increase weight for fixing errors
      // Reduce other weights proportionally
      Object.keys(adjustedWeights).forEach(key => {
        if (key !== 'correctness') {
          adjustedWeights[key as keyof RewardComponents] *= 0.7;
        }
      });
    }
    
    // If relevance is low, prioritize it
    if (components.relevance < 0.3) {
      adjustedWeights.relevance *= 1.5;
    }
    
    // Normalize weights to sum to 1
    const sum = Object.values(adjustedWeights).reduce((a, b) => a + b, 0);
    Object.keys(adjustedWeights).forEach(key => {
      adjustedWeights[key as keyof RewardComponents] /= sum;
    });
    
    return adjustedWeights;
  }
  
  // Calculate weighted reward
  private calculateWeightedReward(
    components: RewardComponents,
    weights: Record<keyof RewardComponents, number>
  ): number {
    let totalReward = 0;
    let totalWeight = 0;
    
    for (const [key, value] of Object.entries(components)) {
      const weight = weights[key as keyof RewardComponents];
      totalReward += value * weight;
      totalWeight += weight;
    }
    
    // Normalize to -1 to 1 range
    const normalized = totalWeight > 0 ? totalReward / totalWeight : 0;
    return Math.max(-1, Math.min(1, normalized));
  }
  
  // Calculate confidence in reward assessment
  private calculateConfidence(
    stateBefore: Record<string, any>,
    stateAfter: Record<string, any>
  ): number {
    const cellsBefore = Object.keys(stateBefore).length;
    const cellsAfter = Object.keys(stateAfter).length;
    
    // More data = higher confidence
    const dataConfidence = Math.min(1, (cellsBefore + cellsAfter) / 50);
    
    // Changes made = can assess better
    const changesMade = Math.abs(cellsAfter - cellsBefore);
    const changeConfidence = Math.min(1, changesMade / 10);
    
    return (dataConfidence + changeConfidence) / 2;
  }
  
  // Combine automatic and human feedback
  combineRewards(
    automaticReward: RewardBreakdown,
    humanFeedback?: { score: number; confidence: number }
  ): number {
    if (!humanFeedback) return automaticReward.totalReward;
    
    // Weight by confidence
    const autoWeight = automaticReward.confidence;
    const humanWeight = humanFeedback.confidence;
    const totalWeight = autoWeight + humanWeight;
    
    if (totalWeight === 0) return 0;
    
    return (
      (automaticReward.totalReward * autoWeight + humanFeedback.score * humanWeight) /
      totalWeight
    );
  }
}