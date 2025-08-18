/**
 * Dynamic Skill Discovery System
 * Allows the agent to learn new capabilities without hardcoding
 */

interface SkillPattern {
  intent: string;           // What the user wanted
  actions: string[];        // What commands achieved it
  success: boolean;         // Did it work?
  context: any;            // Grid state, company, etc
  embedding?: number[];     // Vector representation
}

interface LearnedSkill {
  name: string;
  description: string;
  triggerPhrases: string[];
  actionSequence: string[];
  requiredContext: string[];
  confidence: number;
}

export class DynamicSkillSystem {
  private patterns: SkillPattern[] = [];
  private skills: Map<string, LearnedSkill> = new Map();
  
  /**
   * Record a user interaction pattern
   */
  async recordPattern(
    userPrompt: string,
    executedCommands: string[],
    gridStateBefore: any,
    gridStateAfter: any,
    userFeedback?: { type: string; value: number }
  ) {
    // Determine success based on feedback or state change
    const success = userFeedback 
      ? userFeedback.value > 0.5 
      : this.detectPositiveChange(gridStateBefore, gridStateAfter);
    
    const pattern: SkillPattern = {
      intent: userPrompt,
      actions: executedCommands,
      success,
      context: {
        gridShape: this.getGridShape(gridStateAfter),
        hasFormulas: this.hasFormulas(gridStateAfter),
        dataTypes: this.detectDataTypes(gridStateAfter)
      }
    };
    
    this.patterns.push(pattern);
    
    // Try to discover new skills from patterns
    if (success) {
      await this.discoverSkill(pattern);
    }
  }
  
  /**
   * Discover a new skill from successful patterns
   */
  private async discoverSkill(pattern: SkillPattern) {
    // Look for similar successful patterns
    const similar = this.patterns.filter(p => 
      p.success && 
      this.similarIntent(p.intent, pattern.intent) &&
      p.actions.length > 0
    );
    
    if (similar.length >= 3) {
      // We have enough examples to learn a skill
      const commonActions = this.findCommonActionSequence(similar.map(p => p.actions));
      const triggerPhrases = similar.map(p => this.extractKeyPhrases(p.intent));
      
      const skill: LearnedSkill = {
        name: this.generateSkillName(pattern.intent),
        description: `Learned from: ${pattern.intent}`,
        triggerPhrases: [...new Set(triggerPhrases.flat())],
        actionSequence: commonActions,
        requiredContext: this.extractRequiredContext(similar),
        confidence: similar.length / 10 // More examples = higher confidence
      };
      
      this.skills.set(skill.name, skill);
      console.log(`🎯 Discovered new skill: ${skill.name}`);
    }
  }
  
  /**
   * Suggest actions based on learned skills
   */
  async suggestActions(userPrompt: string, currentContext: any): Promise<string[]> {
    // Find matching skills
    const matchingSkills = Array.from(this.skills.values()).filter(skill => 
      skill.triggerPhrases.some(phrase => 
        userPrompt.toLowerCase().includes(phrase.toLowerCase())
      ) && skill.confidence > 0.3
    );
    
    if (matchingSkills.length === 0) {
      // No exact match, try to compose from primitives
      return this.composeNewActions(userPrompt, currentContext);
    }
    
    // Return the action sequence of the best matching skill
    const bestSkill = matchingSkills.reduce((a, b) => 
      a.confidence > b.confidence ? a : b
    );
    
    console.log(`🤖 Using learned skill: ${bestSkill.name}`);
    return this.adaptActionsToContext(bestSkill.actionSequence, currentContext);
  }
  
  /**
   * Compose new action sequences from primitives
   */
  private async composeNewActions(prompt: string, context: any): Promise<string[]> {
    const actions: string[] = [];
    
    // Detect what type of output user wants
    if (prompt.includes('chart') || prompt.includes('graph') || prompt.includes('visuali')) {
      // User wants visualization
      actions.push('grid.chart("line", "B3:B10", "Data Visualization")');
    }
    
    if (prompt.includes('format') || prompt.includes('color') || prompt.includes('highlight')) {
      // User wants formatting
      actions.push('grid.conditionalFormat("B3:F10", {type: "scale", min: {value: 0}, max: {value: 100}})');
    }
    
    if (prompt.includes('scenario') || prompt.includes('sensitivity') || prompt.includes('what if')) {
      // User wants scenario analysis - compose from primitives
      actions.push('grid.write("A15", "Scenario Analysis")');
      actions.push('grid.write("A16", "Base Case")');
      actions.push('grid.write("A17", "Bull Case")'); 
      actions.push('grid.write("A18", "Bear Case")');
      actions.push('grid.formula("B16", "=B10")'); // Link to base value
      actions.push('grid.formula("B17", "=B10*1.3")'); // 30% upside
      actions.push('grid.formula("B18", "=B10*0.7")'); // 30% downside
    }
    
    if (prompt.includes('summary') || prompt.includes('memo') || prompt.includes('report')) {
      // Generate a text summary from the grid data
      actions.push('// Generating summary from grid data');
      actions.push('const summary = grid.generateSummary()');
      actions.push('grid.write("A25", "Executive Summary")');
      actions.push('grid.write("A26", summary)');
    }
    
    return actions;
  }
  
  /**
   * Adapt learned actions to current context
   */
  private adaptActionsToContext(actions: string[], context: any): string[] {
    // Replace cell references based on current grid layout
    return actions.map(action => {
      // Smart cell reference adaptation
      if (context.lastWrittenCell) {
        // Adjust relative to last action
        action = action.replace(/A1/g, context.lastWrittenCell);
      }
      return action;
    });
  }
  
  // Helper methods
  private similarIntent(a: string, b: string): boolean {
    const wordsA = a.toLowerCase().split(' ');
    const wordsB = b.toLowerCase().split(' ');
    const common = wordsA.filter(w => wordsB.includes(w));
    return common.length > Math.min(wordsA.length, wordsB.length) * 0.3;
  }
  
  private findCommonActionSequence(actionSets: string[][]): string[] {
    // Find the most common action patterns
    if (actionSets.length === 0) return [];
    
    // For now, return the most frequent pattern
    // Could be enhanced with sequence alignment algorithms
    return actionSets[0];
  }
  
  private extractKeyPhrases(intent: string): string[] {
    // Extract important phrases that trigger this skill
    const keywords = ['create', 'build', 'analyze', 'calculate', 'forecast', 'compare'];
    return intent.split(' ').filter(word => 
      keywords.some(kw => word.toLowerCase().includes(kw)) ||
      word.length > 5
    );
  }
  
  private generateSkillName(intent: string): string {
    // Generate a readable name for the skill
    const words = intent.split(' ').slice(0, 3);
    return words.join('_').toLowerCase();
  }
  
  private extractRequiredContext(patterns: SkillPattern[]): string[] {
    // Determine what context is needed for this skill
    const contexts = new Set<string>();
    patterns.forEach(p => {
      if (p.context.hasFormulas) contexts.add('formulas');
      if (p.context.dataTypes.includes('number')) contexts.add('numeric_data');
    });
    return Array.from(contexts);
  }
  
  private detectPositiveChange(before: any, after: any): boolean {
    // Simple heuristic: more cells filled = positive
    const cellsBefore = Object.keys(before || {}).length;
    const cellsAfter = Object.keys(after || {}).length;
    return cellsAfter > cellsBefore;
  }
  
  private getGridShape(state: any): [number, number] {
    const cells = Object.keys(state || {});
    let maxRow = 0, maxCol = 0;
    cells.forEach(cell => {
      const match = cell.match(/([A-Z]+)(\d+)/);
      if (match) {
        maxRow = Math.max(maxRow, parseInt(match[2]));
        maxCol = Math.max(maxCol, match[1].charCodeAt(0) - 65);
      }
    });
    return [maxRow, maxCol];
  }
  
  private hasFormulas(state: any): boolean {
    return Object.values(state || {}).some((cell: any) => 
      cell.formula && cell.formula.startsWith('=')
    );
  }
  
  private detectDataTypes(state: any): string[] {
    const types = new Set<string>();
    Object.values(state || {}).forEach((cell: any) => {
      types.add(typeof cell.value);
    });
    return Array.from(types);
  }
  
  /**
   * Export learned skills for persistence
   */
  exportSkills(): any {
    return {
      skills: Array.from(this.skills.entries()),
      patterns: this.patterns.slice(-100) // Keep last 100 patterns
    };
  }
  
  /**
   * Import previously learned skills
   */
  importSkills(data: any) {
    if (data.skills) {
      this.skills = new Map(data.skills);
    }
    if (data.patterns) {
      this.patterns = data.patterns;
    }
  }
}

// Singleton instance
export const dynamicSkills = new DynamicSkillSystem();