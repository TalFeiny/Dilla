/**
 * Agent Learned Behaviors System
 * Enables the agent to learn and apply complex behaviors from examples
 */

import { visualFormattingAgent } from './visual-formatting';
import { colorCodingSystem } from '../color-coding-system';

export interface LearnedBehavior {
  id: string;
  name: string;
  description: string;
  examples: Example[];
  apply: (input: any, context?: any) => any;
  confidence: number;
  usage_count: number;
  last_used: Date;
}

export interface Example {
  input: any;
  output: any;
  context?: any;
  feedback?: string;
  timestamp: Date;
}

export class AgentBehaviorSystem {
  private behaviors: Map<string, LearnedBehavior> = new Map();
  private behaviorHistory: Example[] = [];
  private contextMemory: Map<string, any> = new Map();

  constructor() {
    this.initializeCoreBehaviors();
  }

  private initializeCoreBehaviors() {
    // Color coding behavior
    this.addBehavior({
      id: 'color_code',
      name: 'Color Coding',
      description: 'Apply intelligent color coding based on data patterns',
      examples: [],
      apply: (input, context) => {
        // Detect what type of data we're dealing with
        if (context?.type === 'interest_level') {
          return this.applyInterestColorCoding(input);
        } else if (context?.type === 'performance_metrics') {
          return this.applyPerformanceColorCoding(input);
        } else if (context?.type === 'exit_scenarios') {
          return this.applyExitScenarioColorCoding(input);
        } else {
          // Auto-detect based on data structure
          return this.autoDetectAndColorCode(input);
        }
      },
      confidence: 0.9,
      usage_count: 0,
      last_used: new Date()
    });

    // Dropdown creation behavior
    this.addBehavior({
      id: 'create_dropdown',
      name: 'Dropdown Creation',
      description: 'Create interactive dropdowns that maintain Excel compatibility',
      examples: [],
      apply: (input, context) => {
        if (Array.isArray(input)) {
          return visualFormattingAgent.createDropdown(input, context?.selected, context?.allowCustom);
        }
        return input;
      },
      confidence: 0.95,
      usage_count: 0,
      last_used: new Date()
    });

    // Table formatting behavior
    this.addBehavior({
      id: 'format_table',
      name: 'Smart Table Formatting',
      description: 'Format data as intelligent tables with sorting, filtering, and conditional formatting',
      examples: [],
      apply: (input, context) => {
        if (Array.isArray(input) && input.length > 0 && typeof input[0] === 'object') {
          return this.createSmartTable(input, context);
        }
        return input;
      },
      confidence: 0.85,
      usage_count: 0,
      last_used: new Date()
    });

    // Scenario generation behavior
    this.addBehavior({
      id: 'generate_scenarios',
      name: 'Scenario Generation',
      description: 'Generate funding path and exit value scenarios like PWERM',
      examples: [],
      apply: (input, context) => {
        return this.generateScenarios(input, context);
      },
      confidence: 0.8,
      usage_count: 0,
      last_used: new Date()
    });

    // Pattern recognition behavior
    this.addBehavior({
      id: 'recognize_pattern',
      name: 'Pattern Recognition',
      description: 'Recognize and apply patterns from examples',
      examples: [],
      apply: (input, context) => {
        return this.recognizeAndApplyPattern(input, context);
      },
      confidence: 0.75,
      usage_count: 0,
      last_used: new Date()
    });
  }

  /**
   * Learn from an example
   */
  learnFromExample(behaviorId: string, example: Example) {
    const behavior = this.behaviors.get(behaviorId);
    if (!behavior) {
      console.warn(`Behavior ${behaviorId} not found`);
      return;
    }

    // Add example to behavior
    behavior.examples.push(example);
    
    // Add to history
    this.behaviorHistory.push(example);
    
    // Update confidence based on feedback
    if (example.feedback) {
      if (example.feedback.includes('good') || example.feedback.includes('correct')) {
        behavior.confidence = Math.min(1, behavior.confidence + 0.01);
      } else if (example.feedback.includes('wrong') || example.feedback.includes('incorrect')) {
        behavior.confidence = Math.max(0, behavior.confidence - 0.05);
      }
    }
    
    // Keep only last 100 examples per behavior
    if (behavior.examples.length > 100) {
      behavior.examples = behavior.examples.slice(-100);
    }
  }

  /**
   * Apply a learned behavior
   */
  applyBehavior(behaviorId: string, input: any, context?: any): any {
    const behavior = this.behaviors.get(behaviorId);
    if (!behavior) {
      console.warn(`Behavior ${behaviorId} not found`);
      return input;
    }

    // Update usage stats
    behavior.usage_count++;
    behavior.last_used = new Date();

    // Store context for learning
    if (context) {
      this.contextMemory.set(`${behaviorId}_${Date.now()}`, context);
    }

    // Apply the behavior
    try {
      const result = behavior.apply(input, context);
      
      // Record this application as an example (without output yet)
      const example: Example = {
        input,
        output: result,
        context,
        timestamp: new Date()
      };
      
      // Store temporarily for potential feedback
      this.behaviorHistory.push(example);
      
      return result;
    } catch (error) {
      console.error(`Error applying behavior ${behaviorId}:`, error);
      return input;
    }
  }

  /**
   * Auto-detect data type and apply appropriate color coding
   */
  private autoDetectAndColorCode(input: any): any {
    if (typeof input === 'string') {
      // Check for interest levels
      if (['high', 'medium', 'low'].includes(input.toLowerCase())) {
        return {
          value: input,
          color: colorCodingSystem.getColor(input, 'interest')
        };
      }
      
      // Check for status
      if (['active', 'inactive', 'pending'].includes(input.toLowerCase())) {
        return {
          value: input,
          color: colorCodingSystem.getColor(input, 'status')
        };
      }
    }
    
    if (typeof input === 'number') {
      // Likely a performance metric or value
      return {
        value: input,
        color: colorCodingSystem.getColor(input, 'value_range')
      };
    }
    
    if (Array.isArray(input)) {
      return input.map(item => this.autoDetectAndColorCode(item));
    }
    
    if (typeof input === 'object' && input !== null) {
      const colored: any = {};
      for (const [key, value] of Object.entries(input)) {
        colored[key] = this.autoDetectAndColorCode(value);
      }
      return colored;
    }
    
    return input;
  }

  /**
   * Apply interest level color coding (YC-style)
   */
  private applyInterestColorCoding(input: any): any {
    const colorMap = {
      'high': '#10b981',
      'medium': '#3b82f6',
      'low': '#6b7280',
      'invested': '#a855f7',
      'passed': '#ef4444'
    };

    if (typeof input === 'string') {
      const level = input.toLowerCase();
      return {
        value: input,
        color: colorMap[level] || '#94a3b8'
      };
    }

    if (Array.isArray(input)) {
      return input.map(item => this.applyInterestColorCoding(item));
    }

    return input;
  }

  /**
   * Apply performance metric color coding
   */
  private applyPerformanceColorCoding(input: any): any {
    if (typeof input === 'number') {
      let color = '#6b7280'; // Default gray
      
      if (input > 30) color = '#10b981'; // Green
      else if (input > 15) color = '#3b82f6'; // Blue  
      else if (input > 0) color = '#fbbf24'; // Yellow
      else if (input <= 0) color = '#ef4444'; // Red
      
      return { value: input, color };
    }

    if (typeof input === 'object' && input.growth !== undefined) {
      return {
        ...input,
        color: this.applyPerformanceColorCoding(input.growth).color
      };
    }

    return input;
  }

  /**
   * Apply exit scenario color coding (PWERM-style)
   */
  private applyExitScenarioColorCoding(input: any): any {
    const scenarioColors = {
      'ipo': '#a855f7',
      'mega_exit': '#a855f7',
      'strategic_acquisition': '#10b981',
      'good_exit': '#10b981',
      'modest_exit': '#3b82f6',
      'zombie': '#fbbf24',
      'liquidation': '#ef4444',
      'bankruptcy': '#ef4444'
    };

    if (typeof input === 'string') {
      return {
        value: input,
        color: scenarioColors[input.toLowerCase()] || '#6b7280'
      };
    }

    if (typeof input === 'object' && input.type) {
      return {
        ...input,
        color: scenarioColors[input.type.toLowerCase()] || '#6b7280'
      };
    }

    return input;
  }

  /**
   * Create a smart table with learned formatting preferences
   */
  private createSmartTable(data: any[], context?: any): any {
    // Detect which columns should be color-coded
    const colorCodeColumns: { [key: string]: string } = {};
    
    if (data.length > 0) {
      const firstRow = data[0];
      
      for (const [key, value] of Object.entries(firstRow)) {
        if (key.toLowerCase().includes('interest') || key.toLowerCase().includes('level')) {
          colorCodeColumns[key] = 'interest';
        } else if (key.toLowerCase().includes('growth') || key.toLowerCase().includes('performance')) {
          colorCodeColumns[key] = 'performance';
        } else if (key.toLowerCase().includes('exit') || key.toLowerCase().includes('scenario')) {
          colorCodeColumns[key] = 'exit_scenario';
        } else if (key.toLowerCase().includes('stage') || key.toLowerCase().includes('funding')) {
          colorCodeColumns[key] = 'funding_stage';
        } else if (typeof value === 'number' && key.toLowerCase().includes('value')) {
          colorCodeColumns[key] = 'value_range';
        }
      }
    }

    return visualFormattingAgent.formatAsTable(data, {
      zebra: true,
      sortable: true,
      filterable: true,
      exportable: true,
      colorCodeColumns,
      conditionalFormatting: context?.rules || []
    });
  }

  /**
   * Generate scenarios based on learned patterns
   */
  private generateScenarios(input: any, context?: any): any {
    const baseScenarios = [
      { scenario: 'Liquidation', funding_path: 'Pre-seed only', exit_value: '$1-5M' },
      { scenario: 'Liquidation', funding_path: 'Pre-seed and seed', exit_value: '$5-10M' },
      { scenario: 'Modest Exit', funding_path: 'Pre-seed, seed', exit_value: '$10-25M' },
      { scenario: 'Good Exit', funding_path: 'Pre-seed, seed, A', exit_value: '$25-50M' },
      { scenario: 'Strategic Acquisition', funding_path: 'Pre-seed, seed, A, B', exit_value: '$50-100M' },
      { scenario: 'Great Exit', funding_path: 'Pre-seed, seed, A, B', exit_value: '$100-500M' },
      { scenario: 'IPO', funding_path: 'Pre-seed, seed, A, B, C', exit_value: '$500M-1B' },
      { scenario: 'Mega Exit', funding_path: 'Pre-seed, seed, A, B, C, D', exit_value: '$1B+' }
    ];

    // Apply learned modifications based on context
    if (context?.company_stage) {
      // Adjust scenarios based on current stage
      return baseScenarios.filter(s => 
        s.funding_path.includes(context.company_stage) || 
        baseScenarios.indexOf(s) > 3
      );
    }

    return baseScenarios;
  }

  /**
   * Recognize patterns from previous examples
   */
  private recognizeAndApplyPattern(input: any, context?: any): any {
    // Look for similar examples in history
    const similarExamples = this.behaviorHistory.filter(ex => 
      this.isSimilar(ex.input, input) && 
      (!context || this.isSimilar(ex.context, context))
    );

    if (similarExamples.length > 0) {
      // Apply the most recent similar pattern
      const mostRecent = similarExamples[similarExamples.length - 1];
      return this.applyPattern(input, mostRecent);
    }

    return input;
  }

  private isSimilar(a: any, b: any): boolean {
    if (typeof a !== typeof b) return false;
    
    if (typeof a === 'object' && a !== null) {
      const keysA = Object.keys(a);
      const keysB = Object.keys(b);
      
      if (keysA.length !== keysB.length) return false;
      
      return keysA.every(key => key in b);
    }
    
    return JSON.stringify(a) === JSON.stringify(b);
  }

  private applyPattern(input: any, example: Example): any {
    // Apply the transformation pattern from the example
    if (typeof example.output === 'object' && typeof input === 'object') {
      const result: any = {};
      
      for (const key in example.output) {
        if (key in input) {
          result[key] = input[key];
        } else if (key.startsWith('_')) {
          // Metadata keys like _color, _style
          result[key] = example.output[key];
        }
      }
      
      return result;
    }
    
    return example.output;
  }

  /**
   * Add a new behavior
   */
  addBehavior(behavior: LearnedBehavior) {
    this.behaviors.set(behavior.id, behavior);
  }

  /**
   * Get all available behaviors
   */
  getAvailableBehaviors(): LearnedBehavior[] {
    return Array.from(this.behaviors.values());
  }

  /**
   * Export learning data
   */
  exportLearning(): any {
    return {
      behaviors: Array.from(this.behaviors.entries()).map(([id, behavior]) => ({
        id,
        name: behavior.name,
        confidence: behavior.confidence,
        usage_count: behavior.usage_count,
        examples: behavior.examples.slice(-10) // Last 10 examples
      })),
      history: this.behaviorHistory.slice(-100), // Last 100 history items
      contextMemory: Array.from(this.contextMemory.entries()).slice(-50)
    };
  }

  /**
   * Import learning data
   */
  importLearning(data: any) {
    if (data.behaviors) {
      data.behaviors.forEach((b: any) => {
        const behavior = this.behaviors.get(b.id);
        if (behavior) {
          behavior.confidence = b.confidence;
          behavior.usage_count = b.usage_count;
          behavior.examples = [...behavior.examples, ...b.examples];
        }
      });
    }
    
    if (data.history) {
      this.behaviorHistory = [...this.behaviorHistory, ...data.history];
    }
    
    if (data.contextMemory) {
      data.contextMemory.forEach(([key, value]: [string, any]) => {
        this.contextMemory.set(key, value);
      });
    }
  }
}

// Export singleton instance
export const agentBehaviorSystem = new AgentBehaviorSystem();