'use client';

export interface SemanticFeedback {
  rawText: string;
  parsedIntent: 'correction' | 'suggestion' | 'praise' | 'criticism' | 'question';
  targetCell?: string;
  targetMetric?: string;
  suggestedValue?: string | number;
  suggestedAction?: string;
  confidence: number;
  reward: number;
}

export interface TrainingExample {
  context: string;
  feedback: SemanticFeedback;
  gridStateBefore: Record<string, any>;
  gridStateAfter?: Record<string, any>;
  appliedCorrection?: string;
}

export class SemanticFeedbackParser {
  
  // Parse natural language feedback into structured format
  parseFeedback(text: string, gridState?: Record<string, any>): SemanticFeedback {
    const lower = text.toLowerCase();
    
    // Detect intent
    const intent = this.detectIntent(lower);
    
    // Extract components
    const targetCell = this.extractCellReference(text);
    const targetMetric = this.extractMetric(lower);
    const suggestedValue = this.extractValue(text);
    const suggestedAction = this.generateSuggestedAction(text, targetCell, suggestedValue);
    
    // Calculate confidence based on specificity
    const confidence = this.calculateConfidence(text, targetCell, suggestedValue);
    
    // Calculate reward based on intent and specificity
    const reward = this.calculateRewardFromFeedback(intent, confidence);
    
    return {
      rawText: text,
      parsedIntent: intent,
      targetCell,
      targetMetric,
      suggestedValue,
      suggestedAction,
      confidence,
      reward
    };
  }
  
  private detectIntent(text: string): SemanticFeedback['parsedIntent'] {
    // Correction patterns
    if (text.match(/should\s+be|change\s+to|use|fix|wrong|incorrect/)) {
      return 'correction';
    }
    
    // Suggestion patterns
    if (text.match(/try|maybe|could|would|suggest|consider/)) {
      return 'suggestion';
    }
    
    // Praise patterns
    if (text.match(/good|great|perfect|excellent|correct|right|yes/)) {
      return 'praise';
    }
    
    // Criticism patterns
    if (text.match(/bad|terrible|wrong|no|incorrect|missing/)) {
      return 'criticism';
    }
    
    // Question patterns
    if (text.match(/\?|why|how|what|where|when/)) {
      return 'question';
    }
    
    return 'suggestion';
  }
  
  private extractCellReference(text: string): string | undefined {
    // Match cell references like A1, B15, AA10
    const match = text.match(/\b([A-Z]{1,2}\d{1,3})\b/);
    return match ? match[1] : undefined;
  }
  
  private extractMetric(text: string): string | undefined {
    const metrics = {
      'revenue': /revenue|sales|turnover|income/,
      'cost': /cost|expense|opex|capex/,
      'margin': /margin|ebitda|profit|gross|net/,
      'growth': /growth|cagr|increase|decrease/,
      'discount': /discount|wacc|rate|irr/,
      'multiple': /multiple|ev|enterprise|valuation/,
      'cash': /cash|fcf|flow|liquidity/,
      'debt': /debt|leverage|loan|interest/,
      'tax': /tax|rate/,
      'depreciation': /depreciation|amortization|d&a/
    };
    
    for (const [metric, pattern] of Object.entries(metrics)) {
      if (pattern.test(text)) return metric;
    }
    
    return undefined;
  }
  
  private extractValue(text: string): string | number | undefined {
    // Extract numeric values with units
    const patterns = [
      // Percentages
      /(\d+(?:\.\d+)?)\s*%/,
      // Millions/Billions
      /\$?\s*(\d+(?:\.\d+)?)\s*([MB])/i,
      // Regular numbers
      /\b(\d+(?:\.\d+)?)\b/,
      // Currency
      /\$\s*(\d+(?:,\d{3})*(?:\.\d+)?)/
    ];
    
    for (const pattern of patterns) {
      const match = text.match(pattern);
      if (match) {
        let value: string | number = match[1];
        
        // Handle units
        if (match[2]) {
          const unit = match[2].toUpperCase();
          if (unit === 'M') value = parseFloat(match[1]) * 1000000;
          else if (unit === 'B') value = parseFloat(match[1]) * 1000000000;
        } else if (text.includes('%')) {
          value = parseFloat(match[1]) / 100;
        } else {
          value = parseFloat(match[1].replace(/,/g, ''));
        }
        
        return value;
      }
    }
    
    // Extract text values in quotes
    const quotedMatch = text.match(/["']([^"']+)["']/);
    if (quotedMatch) return quotedMatch[1];
    
    return undefined;
  }
  
  private generateSuggestedAction(
    text: string,
    cell?: string,
    value?: string | number
  ): string | undefined {
    if (!cell && !value) return undefined;
    
    const lower = text.toLowerCase();
    
    // Generate grid API command based on feedback
    if (cell && value !== undefined) {
      if (lower.includes('formula')) {
        return `grid.formula("${cell}", "${value}")`;
      } else if (lower.includes('format')) {
        if (lower.includes('currency')) return `grid.format("${cell}", "currency")`;
        if (lower.includes('percent')) return `grid.format("${cell}", "percentage")`;
        return `grid.format("${cell}", "number")`;
      } else if (lower.includes('link')) {
        return `grid.link("${cell}", "${value}", "https://example.com")`;
      } else {
        return `grid.write("${cell}", ${typeof value === 'string' ? `"${value}"` : value})`;
      }
    }
    
    // Generate action for metric changes without specific cell
    if (value !== undefined) {
      const metric = this.extractMetric(lower);
      if (metric) {
        // Suggest a reasonable cell based on metric type
        const suggestedCells: Record<string, string> = {
          'revenue': 'B2',
          'cost': 'B3',
          'margin': 'B4',
          'growth': 'C2',
          'discount': 'E1',
          'tax': 'B10'
        };
        
        const targetCell = suggestedCells[metric] || 'A1';
        return `grid.write("${targetCell}", ${value})`;
      }
    }
    
    return undefined;
  }
  
  private calculateConfidence(
    text: string,
    cell?: string,
    value?: string | number
  ): number {
    let confidence = 0.3; // Base confidence
    
    // Increase confidence for specific elements
    if (cell) confidence += 0.3;
    if (value !== undefined) confidence += 0.3;
    
    // Increase for clear intent words
    if (text.match(/should\s+be|must\s+be|exactly|definitely/)) {
      confidence += 0.2;
    }
    
    // Decrease for uncertain words
    if (text.match(/maybe|perhaps|could|might|possibly/)) {
      confidence -= 0.2;
    }
    
    // Length factor (very short or very long = less confident)
    const words = text.split(' ').length;
    if (words >= 3 && words <= 20) confidence += 0.1;
    
    return Math.max(0, Math.min(1, confidence));
  }
  
  private calculateRewardFromFeedback(
    intent: SemanticFeedback['parsedIntent'],
    confidence: number
  ): number {
    const baseRewards = {
      'praise': 0.8,
      'suggestion': 0.0,
      'correction': -0.3,
      'criticism': -0.6,
      'question': 0.0
    };
    
    const baseReward = baseRewards[intent];
    
    // Scale by confidence
    return baseReward * confidence;
  }
  
  // Generate training examples from feedback
  generateTrainingExample(
    feedback: SemanticFeedback,
    gridStateBefore: Record<string, any>,
    gridStateAfter?: Record<string, any>
  ): TrainingExample {
    // Create context string from grid state
    const context = this.createContext(gridStateBefore);
    
    // Apply suggested correction if possible
    let appliedCorrection: string | undefined;
    if (feedback.suggestedAction) {
      appliedCorrection = feedback.suggestedAction;
    }
    
    return {
      context,
      feedback,
      gridStateBefore,
      gridStateAfter,
      appliedCorrection
    };
  }
  
  private createContext(gridState: Record<string, any>): string {
    // Create a text representation of the current grid state
    const entries = Object.entries(gridState)
      .slice(0, 10) // Limit to first 10 cells
      .map(([cell, data]) => {
        const value = data.formula || data.value;
        const type = data.type || 'text';
        return `${cell}:${value}[${type}]`;
      });
    
    return `Grid state: ${entries.join(', ')}`;
  }
  
  // Apply correction to grid state
  applyCorrection(
    correction: SemanticFeedback,
    gridState: Record<string, any>
  ): { newState: Record<string, any>; applied: boolean; command?: string } {
    if (!correction.suggestedAction) {
      return { newState: gridState, applied: false };
    }
    
    const newState = { ...gridState };
    
    // Parse the suggested action
    const writeMatch = correction.suggestedAction.match(/grid\.write\("([^"]+)",\s*(.+)\)/);
    const formulaMatch = correction.suggestedAction.match(/grid\.formula\("([^"]+)",\s*"([^"]+)"\)/);
    const formatMatch = correction.suggestedAction.match(/grid\.format\("([^"]+)",\s*"([^"]+)"\)/);
    
    if (writeMatch) {
      const [, cell, value] = writeMatch;
      newState[cell] = {
        ...newState[cell],
        value: JSON.parse(value),
        type: typeof JSON.parse(value) === 'number' ? 'number' : 'text'
      };
      return { newState, applied: true, command: correction.suggestedAction };
    }
    
    if (formulaMatch) {
      const [, cell, formula] = formulaMatch;
      newState[cell] = {
        ...newState[cell],
        formula: `=${formula}`,
        type: 'formula'
      };
      return { newState, applied: true, command: correction.suggestedAction };
    }
    
    if (formatMatch) {
      const [, cell, format] = formatMatch;
      if (newState[cell]) {
        newState[cell] = {
          ...newState[cell],
          format
        };
      }
      return { newState, applied: true, command: correction.suggestedAction };
    }
    
    return { newState: gridState, applied: false };
  }
  
  // Batch process feedback for training
  batchProcessFeedback(
    feedbackList: string[],
    gridStates: Record<string, any>[]
  ): TrainingExample[] {
    const examples: TrainingExample[] = [];
    
    feedbackList.forEach((text, index) => {
      const parsed = this.parseFeedback(text, gridStates[index]);
      const example = this.generateTrainingExample(
        parsed,
        gridStates[index],
        gridStates[index + 1]
      );
      examples.push(example);
    });
    
    return examples;
  }
  
  // Generate prompts for fine-tuning from examples
  generateFineTuningData(examples: TrainingExample[]): Array<{
    prompt: string;
    completion: string;
  }> {
    return examples.map(example => ({
      prompt: `Context: ${example.context}\nUser feedback: ${example.feedback.rawText}\nGenerate the appropriate grid command:`,
      completion: example.appliedCorrection || example.feedback.suggestedAction || 'No action required'
    }));
  }
}