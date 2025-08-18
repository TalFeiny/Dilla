/**
 * Adaptive RL Agent
 * Combines task classification, meta-learning, and action generation
 */

import { TaskClassifier, taskClassifier } from './task-classifier';
import { MetaLearner, metaLearner } from './meta-learner';
import { spreadsheetRLAgent } from '../spreadsheet-rl-agent';

export class AdaptiveAgent {
  private taskClassifier = taskClassifier;
  private metaLearner = metaLearner;
  private rlAgent = spreadsheetRLAgent;
  
  /**
   * Process user query with adaptive approach
   */
  async processQuery(
    query: string,
    gridState: any,
    context?: any
  ): Promise<{
    actions: any[];
    approach: string;
    confidence: number;
  }> {
    // Step 1: Classify the task
    const classification = this.taskClassifier.classifyTask(query, context);
    console.log('Task classification:', classification);
    
    // Step 2: Determine approach based on meta-learning
    const approach = await this.metaLearner.selectApproach(query, {
      classification,
      gridState,
      context
    });
    console.log('Selected approach:', approach);
    
    // Step 3: Get framework level
    const frameworkLevel = this.metaLearner.getFrameworkLevel(query);
    console.log('Framework level:', frameworkLevel);
    
    // Step 4: Generate actions based on approach
    let actions: any[] = [];
    
    switch (approach) {
      case 'template':
        // Use predefined templates with high structure
        actions = await this.useTemplateApproach(classification, frameworkLevel);
        break;
        
      case 'learned':
        // Use learned patterns from RL
        actions = await this.useLearnedApproach(query, gridState, classification);
        break;
        
      case 'hybrid':
        // Combine template structure with learned adaptations
        actions = await this.useHybridApproach(query, gridState, classification, frameworkLevel);
        break;
        
      case 'exploration':
        // Explore new approaches
        actions = await this.useExplorationApproach(query, gridState);
        break;
    }
    
    return {
      actions,
      approach,
      confidence: classification.confidence
    };
  }
  
  /**
   * Template-based approach for well-defined tasks
   */
  private async useTemplateApproach(
    classification: any,
    frameworkLevel: string
  ): Promise<any[]> {
    // Generate action plan from classification
    const basePlan = this.taskClassifier.generateActionPlan(classification);
    
    if (frameworkLevel === 'strict') {
      // Use exact template
      return basePlan;
    } else if (frameworkLevel === 'flexible') {
      // Allow some adaptation
      return this.adaptTemplate(basePlan, classification);
    }
    
    return basePlan;
  }
  
  /**
   * Use learned patterns from RL experience
   */
  private async useLearnedApproach(
    query: string,
    gridState: any,
    classification: any
  ): Promise<any[]> {
    // Get action from RL agent
    const rlAction = await this.rlAgent.getNextAction({
      grid: gridState,
      metadata: {
        context: query,
        classification
      }
    });
    
    // Convert single action to action sequence
    return this.expandRLAction(rlAction, classification);
  }
  
  /**
   * Hybrid approach combining structure and learning
   */
  private async useHybridApproach(
    query: string,
    gridState: any,
    classification: any,
    frameworkLevel: string
  ): Promise<any[]> {
    // Start with template structure
    const templateActions = await this.useTemplateApproach(classification, frameworkLevel);
    
    // Get learned adjustments
    const rlAction = await this.rlAgent.getNextAction({
      grid: gridState,
      metadata: {
        context: query,
        suggestedActions: templateActions
      }
    });
    
    // Merge template and learned actions
    return this.mergeActions(templateActions, rlAction, classification);
  }
  
  /**
   * Exploration approach for novel tasks
   */
  private async useExplorationApproach(
    query: string,
    gridState: any
  ): Promise<any[]> {
    // Try multiple small actions and learn from feedback
    const exploratoryActions = [
      { type: 'analyze_grid', strategy: 'find_empty_area' },
      { type: 'suggest_structure', based_on: query },
      { type: 'create_minimal', wait_for_feedback: true }
    ];
    
    return exploratoryActions;
  }
  
  /**
   * Adapt template based on context
   */
  private adaptTemplate(template: any[], classification: any): any[] {
    const adapted = [...template];
    
    // Adapt based on entities
    if (classification.entities.company) {
      adapted.forEach(action => {
        if (action.values && action.values.includes('Company')) {
          action.values[action.values.indexOf('Company')] = classification.entities.company;
        }
      });
    }
    
    if (classification.entities.timeframe) {
      adapted.forEach(action => {
        if (action.type === 'create_header' || action.type === 'create_row') {
          // Adjust number of columns based on timeframe
          const years = classification.entities.timeframe.years || 5;
          if (action.values) {
            while (action.values.length - 1 < years) {
              action.values.push('');
            }
          }
        }
      });
    }
    
    return adapted;
  }
  
  /**
   * Expand single RL action to sequence
   */
  private expandRLAction(rlAction: any, classification: any): any[] {
    const actions = [rlAction];
    
    // Add supporting actions based on classification
    if (classification.category === 'financial') {
      // Add formatting, validation, etc.
      actions.push({
        type: 'format_cell',
        row: rlAction.row,
        col: rlAction.col,
        format: 'currency'
      });
    }
    
    return actions;
  }
  
  /**
   * Merge template and learned actions
   */
  private mergeActions(
    template: any[],
    learned: any,
    classification: any
  ): any[] {
    const merged = [...template];
    
    // Find insertion point for learned action
    const insertIndex = this.findBestInsertionPoint(template, learned, classification);
    
    // Insert learned action
    if (insertIndex >= 0) {
      merged.splice(insertIndex, 0, learned);
    } else {
      merged.push(learned);
    }
    
    return merged;
  }
  
  /**
   * Find best place to insert learned action
   */
  private findBestInsertionPoint(
    template: any[],
    learned: any,
    classification: any
  ): number {
    // Logic to find where learned action fits best
    for (let i = 0; i < template.length; i++) {
      if (template[i].type === learned.type) {
        return i + 1; // Insert after similar action
      }
    }
    
    return template.length; // Append at end
  }
  
  /**
   * Process feedback and learn
   */
  async processFeedback(
    query: string,
    approach: string,
    actions: any[],
    feedback: {
      success: boolean;
      reward: number;
      correction?: string;
    }
  ): Promise<void> {
    // Record outcome for meta-learning
    await this.metaLearner.recordOutcome(
      query,
      approach,
      feedback.success,
      feedback.reward
    );
    
    // Update task classifier if needed
    if (!feedback.success && feedback.correction) {
      const classification = this.taskClassifier.classifyTask(query);
      await this.taskClassifier.learnFromFeedback(
        query,
        classification,
        'incorrect',
        feedback.correction
      );
    }
    
    // Update RL agent
    if (approach === 'learned' || approach === 'hybrid') {
      // RL agent handles its own learning
      console.log('RL agent processing feedback:', feedback);
    }
  }
}

export const adaptiveAgent = new AdaptiveAgent();