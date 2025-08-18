'use client';

import * as tf from '@tensorflow/tfjs/dist/index';
import { SimpleEmbeddings as LocalEmbeddings } from './simple-embeddings';
import { Experience } from './experience-collector';

export interface PolicyAction {
  action: string;
  confidence: number;
  reasoning: string;
  source: 'learned' | 'exploration' | 'retrieval' | 'generated';
}

export class ImprovedRAGPolicyAgent {
  private embeddings: LocalEmbeddings;
  private model: tf.LayersModel | null = null;
  private epsilon: number = 0.3; // Increased exploration (was 0.1)
  private temperature: number = 1.5; // Higher temperature for more diversity
  private isTraining: boolean = false;
  private actionHistory: Set<string> = new Set(); // Track recent actions to avoid repetition
  private actionHistoryLimit = 20;
  
  // Dynamic epsilon decay
  private initialEpsilon = 0.5;
  private minEpsilon = 0.15;
  private epsilonDecay = 0.995;
  private episodeCount = 0;
  
  constructor() {
    this.embeddings = LocalEmbeddings.getInstance();
    this.initializeModel();
  }
  
  private initializeModel() {
    // Enhanced model with regularization
    this.model = tf.sequential({
      layers: [
        tf.layers.dense({ 
          inputShape: [384], 
          units: 512, // Larger hidden layer
          activation: 'relu',
          kernelInitializer: 'glorotUniform',
          kernelRegularizer: tf.regularizers.l2({ l2: 0.01 }) // L2 regularization
        }),
        tf.layers.dropout({ rate: 0.3 }), // Higher dropout
        tf.layers.batchNormalization(), // Batch normalization
        tf.layers.dense({ 
          units: 256, 
          activation: 'relu',
          kernelRegularizer: tf.regularizers.l2({ l2: 0.01 })
        }),
        tf.layers.dropout({ rate: 0.25 }),
        tf.layers.dense({ 
          units: 128, 
          activation: 'relu' 
        }),
        tf.layers.dropout({ rate: 0.2 }),
        // Output layer with more action types
        tf.layers.dense({ 
          units: 64, // More output dimensions
          activation: 'softmax' 
        })
      ]
    });
    
    // Use AdamW optimizer with weight decay
    this.model.compile({
      optimizer: tf.train.adam(0.0005), // Lower learning rate
      loss: 'categoricalCrossentropy',
      metrics: ['accuracy']
    });
  }
  
  async selectAction(
    currentGrid: Record<string, any>,
    userIntent: string,
    modelType?: string
  ): Promise<PolicyAction> {
    await this.embeddings.initialize();
    
    if (!this.model) {
      this.initializeModel();
    }
    
    // Dynamic epsilon adjustment
    this.adjustEpsilon();
    
    // Embed current state with intent
    const stateEmbedding = await this.embeddings.embedGridWithContext(
      currentGrid, 
      userIntent
    );
    
    // Exploration vs Exploitation with diversity bonus
    const shouldExplore = Math.random() < this.epsilon || this.needsDiversity();
    
    if (shouldExplore) {
      return this.generateCreativeAction(currentGrid, userIntent, modelType);
    }
    
    // Try retrieval with diversity filter
    const retrievedAction = await this.retrieveDiverseAction(
      stateEmbedding,
      modelType
    );
    
    if (retrievedAction && !this.isRepetitive(retrievedAction.action)) {
      this.trackAction(retrievedAction.action);
      return retrievedAction;
    }
    
    // Generate new action using learned policy
    return this.generateLearnedAction(stateEmbedding, currentGrid, userIntent);
  }
  
  private async generateCreativeAction(
    currentGrid: Record<string, any>,
    userIntent: string,
    modelType?: string
  ): Promise<PolicyAction> {
    const detectedModel = this.detectModelType(userIntent);
    
    // Generate action based on grid analysis, not hardcoded patterns
    const action = await this.analyzeAndGenerateAction(
      currentGrid,
      userIntent,
      detectedModel || modelType || 'Financial'
    );
    
    return {
      action: action,
      confidence: 0.6,
      reasoning: `Creative exploration for ${detectedModel} model`,
      source: 'generated'
    };
  }
  
  private async analyzeAndGenerateAction(
    grid: Record<string, any>,
    intent: string,
    modelType: string
  ): Promise<string> {
    // Analyze what's already in the grid
    const filledCells = Object.keys(grid).filter(k => grid[k]?.value);
    const gridAnalysis = this.analyzeGridContent(grid);
    
    // Parse intent for specific requirements
    const intentAnalysis = this.analyzeIntent(intent);
    
    // Generate contextual action based on analysis
    if (gridAnalysis.isEmpty) {
      return this.generateInitialAction(modelType, intentAnalysis);
    }
    
    if (gridAnalysis.hasHeaders && !gridAnalysis.hasData) {
      return this.generateDataAction(gridAnalysis, intentAnalysis);
    }
    
    if (gridAnalysis.hasData && !gridAnalysis.hasFormulas) {
      return this.generateFormulaAction(gridAnalysis, intentAnalysis);
    }
    
    if (gridAnalysis.needsFormatting) {
      return this.generateFormattingAction(gridAnalysis);
    }
    
    // Generate complementary action
    return this.generateComplementaryAction(gridAnalysis, intentAnalysis, modelType);
  }
  
  private analyzeGridContent(grid: Record<string, any>) {
    const filledCells = Object.entries(grid).filter(([_, cell]) => cell?.value);
    const formulas = filledCells.filter(([_, cell]) => cell.formula);
    const headers = filledCells.filter(([key, _]) => key.endsWith('3') || key.endsWith('1'));
    
    return {
      isEmpty: filledCells.length === 0,
      hasHeaders: headers.length > 0,
      hasData: filledCells.length > headers.length,
      hasFormulas: formulas.length > 0,
      needsFormatting: filledCells.some(([_, cell]) => !cell.format && typeof cell.value === 'number'),
      filledCells: filledCells.map(([key, _]) => key),
      lastRow: Math.max(...filledCells.map(([key, _]) => parseInt(key.slice(1)) || 0), 0),
      lastCol: Math.max(...filledCells.map(([key, _]) => key.charCodeAt(0) - 65), -1)
    };
  }
  
  private analyzeIntent(intent: string) {
    const lower = intent.toLowerCase();
    return {
      wantsGrowth: lower.includes('growth') || lower.includes('projection'),
      wantsValuation: lower.includes('valuation') || lower.includes('value'),
      wantsMetrics: lower.includes('metric') || lower.includes('kpi'),
      wantsAnalysis: lower.includes('analysis') || lower.includes('analyze'),
      hasSpecificNumber: /\d+/.test(intent),
      hasPercentage: lower.includes('%') || lower.includes('percent'),
      hasTimeframe: /\d+\s*(year|month|quarter)/.test(lower)
    };
  }
  
  private generateInitialAction(modelType: string, intentAnalysis: any): string {
    const titles = {
      'DCF': 'Discounted Cash Flow Analysis',
      'Revenue': 'Revenue Projection Model',
      'SaaS': 'SaaS Metrics Dashboard',
      'P&L': 'Profit & Loss Statement',
      'Valuation': 'Company Valuation Model',
      'UnitEconomics': 'Unit Economics Analysis',
      'Cohort': 'Cohort Retention Analysis',
      'BurnAnalysis': 'Burn Rate & Runway Analysis',
      'Financial': 'Financial Model'
    };
    
    const title = titles[modelType] || 'Financial Analysis';
    const cell = 'A1';
    
    // Vary the action structure
    const actionVariants = [
      `grid.write("${cell}", "${title}")`,
      `grid.writeWithStyle("${cell}", "${title}", {bold: true, fontSize: 18})`,
      `grid.setTitle("${cell}", "${title}")`,
      `grid.header("${cell}", "${title}")`
    ];
    
    return actionVariants[Math.floor(Math.random() * actionVariants.length)];
  }
  
  private generateDataAction(gridAnalysis: any, intentAnalysis: any): string {
    const nextRow = gridAnalysis.lastRow + 1;
    const nextCol = String.fromCharCode(65 + gridAnalysis.lastCol + 1);
    
    if (intentAnalysis.hasSpecificNumber) {
      const number = intentAnalysis.hasSpecificNumber.toString();
      return `grid.write("B${nextRow}", "${number}")`;
    }
    
    // Generate contextual data
    const dataTypes = [
      `grid.write("A${nextRow}", "Q1 2024")`,
      `grid.write("B${nextRow}", "1000000")`,
      `grid.writeRange("B${nextRow}", "F${nextRow}", [[100, 150, 200, 250, 300]])`,
      `grid.formula("B${nextRow}", "=B${nextRow-1}*1.1")`,
      `grid.write("${nextCol}${nextRow}", "0.15")`
    ];
    
    return dataTypes[Math.floor(Math.random() * dataTypes.length)];
  }
  
  private generateFormulaAction(gridAnalysis: any, intentAnalysis: any): string {
    const cells = gridAnalysis.filledCells;
    if (cells.length < 2) return `grid.write("B5", "=B3-B4")`;
    
    // Generate diverse formulas
    const formulas = [
      `grid.formula("${this.getNextEmptyCell(gridAnalysis)}", "=SUM(B3:B${gridAnalysis.lastRow})")`,
      `grid.formula("${this.getNextEmptyCell(gridAnalysis)}", "=AVERAGE(B:B)")`,
      `grid.formula("${this.getNextEmptyCell(gridAnalysis)}", "=(B${gridAnalysis.lastRow}/B3)-1")`,
      `grid.formula("${this.getNextEmptyCell(gridAnalysis)}", "=B${gridAnalysis.lastRow}*1.${Math.floor(Math.random() * 5)})")`,
      `grid.formula("${this.getNextEmptyCell(gridAnalysis)}", "=IF(B${gridAnalysis.lastRow}>1000000,'High','Low')")`
    ];
    
    return formulas[Math.floor(Math.random() * formulas.length)];
  }
  
  private generateFormattingAction(gridAnalysis: any): string {
    const formats = ['currency', 'percent', 'number', 'accounting'];
    const cell = gridAnalysis.filledCells[Math.floor(Math.random() * gridAnalysis.filledCells.length)];
    const format = formats[Math.floor(Math.random() * formats.length)];
    
    return `grid.format("${cell}", "${format}")`;
  }
  
  private generateComplementaryAction(gridAnalysis: any, intentAnalysis: any, modelType: string): string {
    const nextCell = this.getNextEmptyCell(gridAnalysis);
    
    // Generate action based on what's missing
    const actions = [
      `grid.write("${nextCell}", "Assumptions")`,
      `grid.style("A${gridAnalysis.lastRow + 2}", {bold: true, backgroundColor: "#f0f0f0"})`,
      `grid.chart("${nextCell}", "line", "B3:F${gridAnalysis.lastRow}")`,
      `grid.conditional("B3:B${gridAnalysis.lastRow}", "greaterThan", 1000000, {color: "green"})`,
      `grid.validation("${nextCell}", "number", {min: 0, max: 100})`,
      `grid.note("${nextCell}", "Source: Financial projections")`
    ];
    
    return actions[Math.floor(Math.random() * actions.length)];
  }
  
  private getNextEmptyCell(gridAnalysis: any): string {
    const col = String.fromCharCode(65 + Math.min(gridAnalysis.lastCol + 1, 5));
    const row = gridAnalysis.lastRow + 1;
    return `${col}${row}`;
  }
  
  private async retrieveDiverseAction(
    stateEmbedding: number[],
    modelType?: string
  ): Promise<PolicyAction | null> {
    try {
      const response = await fetch('/api/agent/rl-experience/match', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          embedding: stateEmbedding,
          modelType,
          minReward: 0.3, // Lower threshold for more variety
          limit: 10 // Get more options
        })
      });
      
      if (!response.ok) return null;
      
      const { experiences } = await response.json();
      if (!experiences || experiences.length === 0) return null;
      
      // Filter out repetitive actions
      const diverseExperiences = experiences.filter((exp: any) => 
        !this.isRepetitive(exp.action_text)
      );
      
      if (diverseExperiences.length === 0) return null;
      
      // Select with probability based on reward and novelty
      const selected = this.selectWithNoveltyBonus(diverseExperiences);
      
      return {
        action: selected.action_text,
        confidence: selected.similarity * selected.reward,
        reasoning: `Retrieved diverse action (similarity: ${(selected.similarity * 100).toFixed(1)}%, reward: ${selected.reward.toFixed(2)})`,
        source: 'retrieval'
      };
    } catch (error) {
      console.error('Failed to retrieve diverse actions:', error);
      return null;
    }
  }
  
  private selectWithNoveltyBonus(experiences: any[]): any {
    // Calculate novelty scores
    const scores = experiences.map(exp => {
      const baseScore = exp.similarity * exp.reward;
      const noveltyBonus = this.actionHistory.has(exp.action_text) ? 0 : 0.2;
      return baseScore + noveltyBonus;
    });
    
    // Weighted random selection
    const totalScore = scores.reduce((a, b) => a + b, 0);
    const random = Math.random() * totalScore;
    let cumSum = 0;
    
    for (let i = 0; i < scores.length; i++) {
      cumSum += scores[i];
      if (random <= cumSum) {
        return experiences[i];
      }
    }
    
    return experiences[0];
  }
  
  private needsDiversity(): boolean {
    // Check if we need more exploration based on recent action diversity
    if (this.actionHistory.size < 5) return false;
    
    // Calculate uniqueness ratio
    const uniqueRatio = this.actionHistory.size / this.actionHistoryLimit;
    return uniqueRatio < 0.5; // Need diversity if too repetitive
  }
  
  private isRepetitive(action: string): boolean {
    // Check if action is too similar to recent actions
    if (this.actionHistory.has(action)) return true;
    
    // Check for similar patterns
    for (const pastAction of this.actionHistory) {
      if (this.areSimilarActions(action, pastAction)) {
        return true;
      }
    }
    
    return false;
  }
  
  private areSimilarActions(action1: string, action2: string): boolean {
    // Extract key parts of actions
    const extract = (a: string) => {
      const match = a.match(/(\w+)\("([^"]+)"/);
      return match ? [match[1], match[2]] : ['', ''];
    };
    
    const [method1, cell1] = extract(action1);
    const [method2, cell2] = extract(action2);
    
    // Same method and same cell = repetitive
    return method1 === method2 && cell1 === cell2;
  }
  
  private trackAction(action: string) {
    this.actionHistory.add(action);
    
    // Keep history limited
    if (this.actionHistory.size > this.actionHistoryLimit) {
      const first = this.actionHistory.values().next().value;
      this.actionHistory.delete(first);
    }
  }
  
  private adjustEpsilon() {
    // Dynamic epsilon adjustment
    this.epsilon = Math.max(
      this.minEpsilon,
      this.initialEpsilon * Math.pow(this.epsilonDecay, this.episodeCount)
    );
  }
  
  private detectModelType(intent: string): string {
    const lower = intent.toLowerCase();
    
    // More flexible pattern matching
    const patterns = {
      'DCF': ['dcf', 'discounted', 'cash flow', 'npv', 'present value'],
      'Revenue': ['revenue', 'sales', 'top line', 'income'],
      'SaaS': ['saas', 'mrr', 'arr', 'subscription', 'recurring'],
      'P&L': ['p&l', 'profit', 'loss', 'income statement', 'earnings'],
      'Valuation': ['valuation', 'multiple', 'worth', 'enterprise value'],
      'UnitEconomics': ['unit', 'economics', 'ltv', 'cac', 'payback'],
      'Cohort': ['cohort', 'retention', 'churn', 'user'],
      'BurnAnalysis': ['burn', 'runway', 'cash', 'spending']
    };
    
    for (const [model, keywords] of Object.entries(patterns)) {
      if (keywords.some(keyword => lower.includes(keyword))) {
        return model;
      }
    }
    
    return 'Financial';
  }
  
  async updatePolicy(experiences: Experience[]) {
    if (experiences.length === 0) return;
    
    if (this.isTraining) {
      console.warn('Training already in progress, skipping...');
      return;
    }
    
    this.isTraining = true;
    this.episodeCount++;
    
    try {
      if (!this.model) {
        this.initializeModel();
      }
      
      // Prepare diverse training data with augmentation
      const { states, targets } = await this.prepareAugmentedTrainingData(experiences);
      
      const xTrain = tf.tensor2d(states);
      const yTrain = tf.tensor2d(targets);
      
      // Train with early stopping
      const history = await this.model.fit(xTrain, yTrain, {
        epochs: 20,
        batchSize: Math.min(32, experiences.length),
        shuffle: true,
        validationSplit: 0.2,
        callbacks: tf.callbacks.earlyStopping({
          monitor: 'val_loss',
          patience: 3,
          restoreBestWeights: true
        }),
        verbose: 0
      });
      
      // Cleanup
      xTrain.dispose();
      yTrain.dispose();
      
      console.log('Training completed with validation loss:', 
        history.history.val_loss[history.history.val_loss.length - 1]);
      
    } catch (error) {
      console.error('Training error:', error);
    } finally {
      this.isTraining = false;
    }
  }
  
  private async prepareAugmentedTrainingData(experiences: Experience[]) {
    const states: number[][] = [];
    const targets: number[][] = [];
    
    for (const exp of experiences) {
      // Original data
      states.push(exp.stateEmbedding);
      const target = this.createTarget(exp);
      targets.push(target);
      
      // Add noise for augmentation (only for successful experiences)
      if (exp.reward > 0.5) {
        const noisyState = this.addNoise(exp.stateEmbedding, 0.05);
        states.push(noisyState);
        targets.push(target);
      }
    }
    
    return { states, targets };
  }
  
  private createTarget(exp: Experience): number[] {
    const actionType = this.getActionTypeIndex(exp.metadata.actionText);
    const target = new Array(64).fill(0);
    
    // Spread reward across similar actions for generalization
    const baseIndex = actionType * 8; // 8 variations per action type
    for (let i = 0; i < 8; i++) {
      target[baseIndex + i] = exp.reward > 0 ? exp.reward * (1 - i * 0.1) : 0;
    }
    
    return target;
  }
  
  private addNoise(embedding: number[], noiseLevel: number): number[] {
    return embedding.map(val => 
      val + (Math.random() - 0.5) * 2 * noiseLevel
    );
  }
  
  private getActionTypeIndex(action: string): number {
    const actionTypes = [
      'write', 'formula', 'format', 'style', 'clear', 'link', 
      'writeRange', 'chart', 'conditional', 'validation'
    ];
    
    for (let i = 0; i < actionTypes.length; i++) {
      if (action.includes(actionTypes[i])) return i;
    }
    return 0;
  }
  
  private async generateLearnedAction(
    stateEmbedding: number[],
    currentGrid: Record<string, any>,
    userIntent: string
  ): Promise<PolicyAction> {
    if (!this.model) {
      return this.generateCreativeAction(currentGrid, userIntent);
    }
    
    try {
      const input = tf.tensor2d([stateEmbedding]);
      const output = this.model.predict(input) as tf.Tensor;
      const probs = await output.data();
      
      // Sample with temperature and diversity
      const actionIndex = this.sampleWithDiversity(Array.from(probs));
      const action = await this.decodeToAction(actionIndex, currentGrid, userIntent);
      
      input.dispose();
      output.dispose();
      
      this.trackAction(action);
      
      return {
        action,
        confidence: probs[actionIndex],
        reasoning: `Learned policy with diversity (confidence: ${(probs[actionIndex] * 100).toFixed(1)}%)`,
        source: 'learned'
      };
    } catch (error) {
      console.error('Failed to generate learned action:', error);
      return this.generateCreativeAction(currentGrid, userIntent);
    }
  }
  
  private sampleWithDiversity(probabilities: number[]): number {
    // Apply temperature with diversity bonus
    const adjustedProbs = probabilities.map((p, i) => {
      const tempAdjusted = Math.pow(p, 1 / this.temperature);
      // Bonus for less frequently used actions
      const diversityBonus = this.getActionDiversityBonus(i);
      return tempAdjusted * diversityBonus;
    });
    
    // Normalize
    const sum = adjustedProbs.reduce((a, b) => a + b, 0);
    const normalizedProbs = adjustedProbs.map(p => p / sum);
    
    // Sample
    const random = Math.random();
    let cumSum = 0;
    
    for (let i = 0; i < normalizedProbs.length; i++) {
      cumSum += normalizedProbs[i];
      if (random <= cumSum) return i;
    }
    
    return normalizedProbs.length - 1;
  }
  
  private getActionDiversityBonus(actionIndex: number): number {
    // Track action usage and give bonus to less used actions
    // This is simplified - in production, track actual usage
    const commonActions = [0, 1, 2]; // write, formula, format
    if (commonActions.includes(actionIndex % 10)) {
      return 0.8; // Penalty for overused actions
    }
    return 1.2; // Bonus for diverse actions
  }
  
  private async decodeToAction(
    index: number,
    grid: Record<string, any>,
    intent: string
  ): Promise<string> {
    // Generate more diverse actions based on index
    const actionCategory = Math.floor(index / 8);
    const variation = index % 8;
    
    const gridAnalysis = this.analyzeGridContent(grid);
    const nextCell = this.getNextEmptyCell(gridAnalysis);
    
    // Generate action based on category and variation
    return this.generateActionByCategory(
      actionCategory,
      variation,
      nextCell,
      gridAnalysis,
      intent
    );
  }
  
  private generateActionByCategory(
    category: number,
    variation: number,
    cell: string,
    gridAnalysis: any,
    intent: string
  ): string {
    const categories = [
      // Write actions
      () => `grid.write("${cell}", "${this.generateContextualValue(intent, variation)}")`,
      // Formula actions
      () => `grid.formula("${cell}", "${this.generateContextualFormula(gridAnalysis, variation)}")`,
      // Format actions
      () => `grid.format("${cell}", "${['currency', 'percent', 'number', 'accounting'][variation % 4]}")`,
      // Style actions
      () => `grid.style("${cell}", ${JSON.stringify(this.generateStyle(variation))})`,
      // Clear actions
      () => `grid.clear("${cell}")`,
      // Link actions
      () => `grid.link("${cell}", "Details", "https://example.com/data")`,
      // WriteRange actions
      () => `grid.writeRange("${cell}", "${this.getEndCell(cell, variation)}", ${this.generateRangeData(variation)})`,
      // Chart actions
      () => `grid.chart("${cell}", "${['line', 'bar', 'pie'][variation % 3]}", "${this.getDataRange(gridAnalysis)}")`,
      // Conditional formatting
      () => `grid.conditional("${this.getDataRange(gridAnalysis)}", "${['greaterThan', 'lessThan', 'between'][variation % 3]}", ${this.getConditionValue(variation)})`,
      // Validation
      () => `grid.validation("${cell}", "${['number', 'date', 'list'][variation % 3]}", ${JSON.stringify(this.getValidationRules(variation))})`
    ];
    
    const categoryIndex = category % categories.length;
    return categories[categoryIndex]();
  }
  
  private generateContextualValue(intent: string, variation: number): string {
    const values = [
      'Revenue', 'Cost', 'Profit', 'Growth Rate', 'Margin',
      '1000000', '0.15', '2024', 'Q1', 'Forecast'
    ];
    return values[variation % values.length];
  }
  
  private generateContextualFormula(gridAnalysis: any, variation: number): string {
    const formulas = [
      '=SUM(B:B)',
      '=AVERAGE(B3:B10)',
      '=B3*1.1',
      '=B3-B4',
      '=(B5/B3)-1',
      '=IF(B3>1000000,B3*0.1,B3*0.05)',
      '=VLOOKUP(A3,A:B,2,FALSE)',
      '=B3/12'
    ];
    return formulas[variation % formulas.length];
  }
  
  private generateStyle(variation: number): any {
    const styles = [
      { bold: true },
      { fontSize: 14 },
      { color: '#2563eb' },
      { backgroundColor: '#f3f4f6' },
      { border: '1px solid #e5e7eb' },
      { textAlign: 'center' },
      { fontWeight: 600 },
      { italic: true }
    ];
    return styles[variation % styles.length];
  }
  
  private getEndCell(startCell: string, variation: number): string {
    const match = startCell.match(/([A-Z]+)(\d+)/);
    if (!match) return 'D10';
    
    const col = String.fromCharCode(match[1].charCodeAt(0) + (variation % 4) + 1);
    const row = parseInt(match[2]) + (variation % 3);
    return `${col}${row}`;
  }
  
  private generateRangeData(variation: number): string {
    const data = [
      '[[100, 200, 300]]',
      '[[1, 2], [3, 4]]',
      '[["Q1", "Q2", "Q3", "Q4"]]',
      '[[0.1, 0.15, 0.2, 0.25]]'
    ];
    return data[variation % data.length];
  }
  
  private getDataRange(gridAnalysis: any): string {
    if (gridAnalysis.filledCells.length < 2) return 'B3:B10';
    
    const minRow = 3;
    const maxRow = gridAnalysis.lastRow || 10;
    return `B${minRow}:B${maxRow}`;
  }
  
  private getConditionValue(variation: number): string {
    const values = ['1000000', '0', '0.5', '100'];
    return values[variation % values.length];
  }
  
  private getValidationRules(variation: number): any {
    const rules = [
      { min: 0, max: 1000000 },
      { min: 0, max: 100 },
      { list: ['Option1', 'Option2', 'Option3'] },
      { pattern: '^[0-9]+$' }
    ];
    return rules[variation % rules.length];
  }
  
  // Enhanced stats
  getStats() {
    return {
      epsilon: this.epsilon,
      temperature: this.temperature,
      modelLoaded: this.model !== null,
      episodeCount: this.episodeCount,
      actionDiversity: this.actionHistory.size,
      explorationRate: `${(this.epsilon * 100).toFixed(1)}%`
    };
  }
  
  // Save and load methods remain the same
  async saveModel() {
    if (!this.model) return;
    await this.model.save('localstorage://improved-spreadsheet-policy');
  }
  
  async loadModel() {
    try {
      const loadedModel = await tf.loadLayersModel('localstorage://improved-spreadsheet-policy');
      
      loadedModel.compile({
        optimizer: tf.train.adam(0.0005),
        loss: 'categoricalCrossentropy',
        metrics: ['accuracy']
      });
      
      this.model = loadedModel;
      console.log('Loaded improved policy model');
    } catch (error) {
      console.log('No saved model found, initializing fresh model');
      this.initializeModel();
    }
  }
}

// Extension for LocalEmbeddings to support context
declare module './simple-embeddings' {
  interface SimpleEmbeddings {
    embedGridWithContext(grid: Record<string, any>, context: string): Promise<number[]>;
  }
}