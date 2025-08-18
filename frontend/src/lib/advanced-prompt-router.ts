/**
 * Advanced Prompt Router with Deep Task Analysis
 * Intelligently routes prompts to appropriate handlers with skill-based decomposition
 */

import { taskClassifier } from './rl-system/task-classifier';

export interface SkillRequirement {
  skill: string;
  complexity: 'low' | 'medium' | 'high';
  required: boolean;
  confidence: number;
}

export interface TaskDecomposition {
  mainTask: string;
  subTasks: SubTask[];
  skills: SkillRequirement[];
  estimatedComplexity: number;
  suggestedApproach: 'sequential' | 'parallel' | 'hybrid';
  context: Record<string, any>;
}

export interface SubTask {
  id: string;
  description: string;
  dependencies: string[];
  requiredSkills: string[];
  priority: number;
  estimatedDuration: number;
  output: string;
}

export interface RouteDecision {
  handler: string;
  confidence: number;
  reasoning: string;
  decomposition: TaskDecomposition;
  fallbackHandlers: string[];
}

export class AdvancedPromptRouter {
  private skillMap = new Map<string, string[]>();
  private handlerCapabilities = new Map<string, Set<string>>();
  
  constructor() {
    this.initializeSkillMappings();
    this.initializeHandlerCapabilities();
  }
  
  private initializeSkillMappings() {
    // Financial modeling skills
    this.skillMap.set('financial_modeling', [
      'dcf_analysis', 'revenue_projection', 'cost_modeling',
      'valuation', 'scenario_analysis', 'sensitivity_analysis'
    ]);
    
    // Data analysis skills
    this.skillMap.set('data_analysis', [
      'statistical_analysis', 'trend_detection', 'correlation',
      'regression', 'clustering', 'anomaly_detection'
    ]);
    
    // Market research skills
    this.skillMap.set('market_research', [
      'competitor_analysis', 'market_sizing', 'trend_analysis',
      'customer_segmentation', 'pricing_strategy'
    ]);
    
    // Document processing skills
    this.skillMap.set('document_processing', [
      'text_extraction', 'entity_recognition', 'summarization',
      'classification', 'sentiment_analysis'
    ]);
    
    // Visualization skills
    this.skillMap.set('visualization', [
      'chart_creation', 'dashboard_design', 'data_formatting',
      'interactive_viz', 'export_generation'
    ]);
  }
  
  private initializeHandlerCapabilities() {
    // Map handlers to their capabilities - using ACTUAL endpoints
    this.handlerCapabilities.set('research', new Set([
      'web_search', 'data_gathering', 'citation', 'multi_source'
    ]));
    
    this.handlerCapabilities.set('company_analysis', new Set([
      'company_research', 'cim_generation', 'deep_scraping', 'profile_creation'
    ]));
    
    this.handlerCapabilities.set('market_intelligence', new Set([
      'market_research', 'competitor_analysis', 'trend_analysis', 'industry_analysis'
    ]));
    
    this.handlerCapabilities.set('valuation', new Set([
      'financial_modeling', 'dcf_analysis', 'ipev_valuation', 'pwerm_analysis'
    ]));
    
    this.handlerCapabilities.set('data_extraction', new Set([
      'document_processing', 'text_extraction', 'data_pipeline', 'parsing'
    ]));
    
    this.handlerCapabilities.set('financial_analysis', new Set([
      'multi_analysis', 'financial_metrics', 'revenue_projection', 'cost_modeling'
    ]));
    
    this.handlerCapabilities.set('calculations', new Set([
      'python_execution', 'mathematical_computation', 'statistical_analysis'
    ]));
  }
  
  /**
   * Main routing function with deep analysis
   */
  async route(prompt: string, context?: any): Promise<RouteDecision> {
    // PRIORITY: Check for @mentions first - route to company analysis
    if (prompt.includes('@')) {
      const companyMatch = prompt.match(/@(\w+)/);
      if (companyMatch) {
        const companyName = companyMatch[1];
        console.log(`🎯 @mention detected: ${companyName} → routing to company_analysis`);
        
        return {
          handler: 'company_analysis',
          confidence: 0.95,
          reasoning: `@mention of ${companyName} requires comprehensive company analysis with CIM generation`,
          decomposition: {
            mainTask: `Comprehensive analysis of ${companyName}`,
            subTasks: [
              {
                id: '1',
                description: 'Database lookup',
                dependencies: [],
                requiredSkills: ['data_retrieval'],
                priority: 1,
                estimatedDuration: 1,
                output: 'Company database profile'
              },
              {
                id: '2',
                description: 'Web search and scraping',
                dependencies: [],
                requiredSkills: ['web_search', 'scraping'],
                priority: 1,
                estimatedDuration: 3,
                output: 'Latest company information'
              },
              {
                id: '3',
                description: 'CIM generation',
                dependencies: ['1', '2'],
                requiredSkills: ['cim_generation'],
                priority: 2,
                estimatedDuration: 5,
                output: 'Comprehensive CIM document'
              }
            ],
            skills: [
              { skill: 'company_research', complexity: 'high', required: true, confidence: 0.95 }
            ],
            estimatedComplexity: 0.8,
            suggestedApproach: 'parallel',
            context: { companyName, isAtMention: true }
          },
          fallbackHandlers: ['research', 'market_intelligence']
        };
      }
    }
    
    // Check for specific company analysis keywords
    if (/analyze|research|profile|CIM|deep dive/i.test(prompt) && /company|startup|\b[A-Z][a-z]+/i.test(prompt)) {
      return {
        handler: 'company_analysis',
        confidence: 0.85,
        reasoning: 'Company analysis request detected',
        decomposition: await this.decomposeTask(prompt, { type: 'company_analysis' }, context),
        fallbackHandlers: ['research']
      };
    }
    
    // Check for market intelligence needs
    if (/market|competitor|industry|sector|trends/i.test(prompt)) {
      return {
        handler: 'market_intelligence',
        confidence: 0.8,
        reasoning: 'Market analysis required',
        decomposition: await this.decomposeTask(prompt, { type: 'market_analysis' }, context),
        fallbackHandlers: ['research']
      };
    }
    
    // Check for valuation needs
    if (/valuation|DCF|PWERM|IPEV|pricing|worth/i.test(prompt)) {
      return {
        handler: 'valuation',
        confidence: 0.85,
        reasoning: 'Valuation analysis required',
        decomposition: await this.decomposeTask(prompt, { type: 'valuation' }, context),
        fallbackHandlers: ['financial_analysis']
      };
    }
    
    // Default: use reasoning agent for general research
    const needsData = await this.checkDataRequirements(prompt);
    
    if (needsData.required) {
      console.log('Data fetch required for:', needsData.dataTypes);
      
      // Fetch real data before routing
      const fetchedData = await this.fetchRequiredData(prompt, needsData.dataTypes);
      
      // Add fetched data to context
      context = {
        ...context,
        fetchedData,
        dataSource: 'real',
        timestamp: Date.now()
      };
    }
    
    // Step 1: Classify the task
    const classification = taskClassifier.classifyTask(prompt, context);
    
    // Step 2: Decompose into subtasks
    const decomposition = await this.decomposeTask(prompt, classification, context);
    
    // Step 3: Identify required skills
    const requiredSkills = this.identifyRequiredSkills(decomposition);
    
    // Step 4: Match to best handler
    const handler = this.selectBestHandler(requiredSkills, decomposition);
    
    // Step 5: Generate fallback options
    const fallbacks = this.generateFallbackHandlers(requiredSkills, handler.primary);
    
    return {
      handler: handler.primary,
      confidence: handler.confidence,
      reasoning: handler.reasoning,
      decomposition,
      fallbackHandlers: fallbacks
    };
  }
  
  /**
   * Check if prompt requires data fetching
   */
  private async checkDataRequirements(prompt: string): Promise<{ required: boolean; dataTypes: string[] }> {
    const dataTypes: string[] = [];
    
    // Check for company data needs
    if (/company|startup|firm|competitor|market/i.test(prompt)) {
      dataTypes.push('company_data');
    }
    
    // Check for financial data needs
    if (/revenue|profit|valuation|funding|financial|dcf|ebitda/i.test(prompt)) {
      dataTypes.push('financial_data');
    }
    
    // Check for market data needs
    if (/market size|tam|growth rate|industry|sector/i.test(prompt)) {
      dataTypes.push('market_data');
    }
    
    // Check for real-time data needs
    if (/current|latest|recent|today|now/i.test(prompt)) {
      dataTypes.push('realtime_data');
    }
    
    return {
      required: dataTypes.length > 0,
      dataTypes
    };
  }
  
  /**
   * Fetch required data from APIs/database
   */
  private async fetchRequiredData(prompt: string, dataTypes: string[]): Promise<any> {
    const fetchedData: any = {};
    
    console.log('Fetching real data for types:', dataTypes);
    
    try {
      for (const dataType of dataTypes) {
        switch (dataType) {
          case 'company_data':
            // Extract company name from prompt
            const companyName = this.extractCompanyName(prompt);
            if (companyName) {
              // Search database for company
              const response = await fetch('/api/companies/search', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ query: companyName })
              });
              
              if (response.ok) {
                const data = await response.json();
                fetchedData.company = data;
                console.log('Fetched company data:', data);
              }
            }
            break;
            
          case 'financial_data':
            // Fetch financial metrics
            const finResponse = await fetch('/api/agent/web-search', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ 
                query: `${this.extractCompanyName(prompt) || ''} revenue funding valuation financial metrics`
              })
            });
            
            if (finResponse.ok) {
              const data = await finResponse.json();
              fetchedData.financial = data;
              console.log('Fetched financial data');
            }
            break;
            
          case 'market_data':
            // Fetch market intelligence
            const marketResponse = await fetch('/api/agent/market-intelligence', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ prompt })
            });
            
            if (marketResponse.ok) {
              const data = await marketResponse.json();
              fetchedData.market = data;
              console.log('Fetched market data');
            }
            break;
            
          case 'realtime_data':
            // Fetch latest data
            console.log('Fetching real-time data...');
            fetchedData.realtime = {
              timestamp: Date.now(),
              source: 'live'
            };
            break;
        }
      }
    } catch (error) {
      console.error('Error fetching data:', error);
    }
    
    return fetchedData;
  }
  
  /**
   * Decompose prompt into subtasks with dependencies
   */
  private async decomposeTask(
    prompt: string,
    classification: any,
    context?: any
  ): Promise<TaskDecomposition> {
    const subTasks: SubTask[] = [];
    const skills: SkillRequirement[] = [];
    
    // Analyze prompt for task components
    const components = this.extractTaskComponents(prompt);
    
    // Generate subtasks based on classification
    if (classification.category === 'financial') {
      if (classification.intent === 'create_financial_model') {
        subTasks.push(
          {
            id: 'data_gathering',
            description: 'Gather required financial data',
            dependencies: [],
            requiredSkills: ['data_extraction', 'api_integration'],
            priority: 1,
            estimatedDuration: 5,
            output: 'financial_data'
          },
          {
            id: 'model_structure',
            description: 'Create model structure and layout',
            dependencies: [],
            requiredSkills: ['spreadsheet_design', 'financial_modeling'],
            priority: 2,
            estimatedDuration: 10,
            output: 'model_framework'
          },
          {
            id: 'calculations',
            description: 'Implement financial calculations',
            dependencies: ['data_gathering', 'model_structure'],
            requiredSkills: ['formula_creation', 'financial_analysis'],
            priority: 3,
            estimatedDuration: 15,
            output: 'calculated_model'
          },
          {
            id: 'validation',
            description: 'Validate model accuracy',
            dependencies: ['calculations'],
            requiredSkills: ['testing', 'validation'],
            priority: 4,
            estimatedDuration: 5,
            output: 'validated_model'
          }
        );
        
        skills.push(
          { skill: 'financial_modeling', complexity: 'high', required: true, confidence: 0.9 },
          { skill: 'data_analysis', complexity: 'medium', required: true, confidence: 0.8 },
          { skill: 'spreadsheet_automation', complexity: 'medium', required: false, confidence: 0.7 }
        );
      }
    } else if (classification.category === 'data') {
      subTasks.push(
        {
          id: 'data_identification',
          description: 'Identify data sources and locations',
          dependencies: [],
          requiredSkills: ['data_discovery'],
          priority: 1,
          estimatedDuration: 3,
          output: 'data_sources'
        },
        {
          id: 'data_processing',
          description: 'Process and transform data',
          dependencies: ['data_identification'],
          requiredSkills: ['data_transformation'],
          priority: 2,
          estimatedDuration: 8,
          output: 'processed_data'
        }
      );
      
      skills.push(
        { skill: 'data_analysis', complexity: 'medium', required: true, confidence: 0.85 }
      );
    }
    
    // Calculate complexity based on subtasks and skills
    const complexity = this.calculateComplexity(subTasks, skills);
    
    // Determine execution approach
    const approach = this.determineApproach(subTasks);
    
    return {
      mainTask: this.extractMainTask(prompt, classification),
      subTasks,
      skills,
      estimatedComplexity: complexity,
      suggestedApproach: approach,
      context: {
        ...context,
        classification,
        components
      }
    };
  }
  
  /**
   * Extract task components from prompt
   */
  private extractTaskComponents(prompt: string): Record<string, any> {
    return {
      hasCompanyName: /\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b/.test(prompt),
      hasTimeframe: /\d+\s*(year|month|quarter)|fy\d+|q[1-4]/i.test(prompt),
      hasMetrics: /revenue|profit|margin|growth|ebitda/i.test(prompt),
      hasAction: /create|build|analyze|calculate|update/i.test(prompt),
      hasComparison: /compare|versus|vs|benchmark/i.test(prompt),
      hasVisualization: /chart|graph|plot|visualize|display/i.test(prompt),
      complexity: this.assessPromptComplexity(prompt)
    };
  }
  
  /**
   * Identify required skills from decomposition
   */
  private identifyRequiredSkills(decomposition: TaskDecomposition): Set<string> {
    const skills = new Set<string>();
    
    // Add skills from skill requirements
    decomposition.skills.forEach(req => skills.add(req.skill));
    
    // Add skills from subtasks
    decomposition.subTasks.forEach(task => {
      task.requiredSkills.forEach(skill => skills.add(skill));
    });
    
    // Add inferred skills based on context
    if (decomposition.context.hasVisualization) {
      skills.add('visualization');
    }
    
    if (decomposition.context.hasComparison) {
      skills.add('comparative_analysis');
    }
    
    return skills;
  }
  
  /**
   * Select best handler based on skills and decomposition
   */
  private selectBestHandler(
    requiredSkills: Set<string>,
    decomposition: TaskDecomposition
  ): { primary: string; confidence: number; reasoning: string } {
    let bestHandler = '';
    let bestScore = 0;
    let reasoning = '';
    
    // Score each handler
    for (const [handler, capabilities] of this.handlerCapabilities) {
      let score = 0;
      let matches = 0;
      
      // Check skill coverage
      for (const skill of requiredSkills) {
        if (capabilities.has(skill)) {
          score += 1;
          matches++;
        }
        
        // Check if handler has parent skill category
        for (const [category, subSkills] of this.skillMap) {
          if (capabilities.has(category) && subSkills.includes(skill)) {
            score += 0.5;
            matches += 0.5;
          }
        }
      }
      
      // Normalize score
      const coverage = requiredSkills.size > 0 ? matches / requiredSkills.size : 0;
      
      // Apply complexity weighting
      if (decomposition.estimatedComplexity > 0.7 && handler === 'rl-agent') {
        score *= 1.2; // Boost RL agent for complex tasks
      }
      
      if (score > bestScore) {
        bestScore = score;
        bestHandler = handler;
        reasoning = `Best match with ${Math.round(coverage * 100)}% skill coverage`;
      }
    }
    
    // Default fallback
    if (!bestHandler) {
      bestHandler = 'spreadsheet-agent';
      reasoning = 'Default handler for general tasks';
    }
    
    return {
      primary: bestHandler,
      confidence: Math.min(bestScore / requiredSkills.size, 1),
      reasoning
    };
  }
  
  /**
   * Generate fallback handlers
   */
  private generateFallbackHandlers(
    requiredSkills: Set<string>,
    primaryHandler: string
  ): string[] {
    const fallbacks: Array<{ handler: string; score: number }> = [];
    
    for (const [handler, capabilities] of this.handlerCapabilities) {
      if (handler === primaryHandler) continue;
      
      let score = 0;
      for (const skill of requiredSkills) {
        if (capabilities.has(skill)) {
          score++;
        }
      }
      
      if (score > 0) {
        fallbacks.push({ handler, score });
      }
    }
    
    // Sort by score and return handler names
    return fallbacks
      .sort((a, b) => b.score - a.score)
      .map(f => f.handler)
      .slice(0, 3);
  }
  
  /**
   * Calculate task complexity
   */
  private calculateComplexity(subTasks: SubTask[], skills: SkillRequirement[]): number {
    let complexity = 0;
    
    // Factor in number of subtasks
    complexity += Math.min(subTasks.length * 0.1, 0.3);
    
    // Factor in skill complexity
    const avgSkillComplexity = skills.reduce((sum, s) => {
      const complexityScore = s.complexity === 'high' ? 1 : s.complexity === 'medium' ? 0.5 : 0.2;
      return sum + complexityScore;
    }, 0) / Math.max(skills.length, 1);
    complexity += avgSkillComplexity * 0.4;
    
    // Factor in dependencies
    const maxDependencies = Math.max(...subTasks.map(t => t.dependencies.length));
    complexity += Math.min(maxDependencies * 0.1, 0.3);
    
    return Math.min(complexity, 1);
  }
  
  /**
   * Determine execution approach
   */
  private determineApproach(subTasks: SubTask[]): 'sequential' | 'parallel' | 'hybrid' {
    // Check dependency graph
    const hasDependencies = subTasks.some(t => t.dependencies.length > 0);
    const maxDepth = this.calculateDependencyDepth(subTasks);
    
    if (!hasDependencies) {
      return 'parallel';
    } else if (maxDepth > 2) {
      return 'sequential';
    } else {
      return 'hybrid';
    }
  }
  
  /**
   * Calculate dependency depth
   */
  private calculateDependencyDepth(subTasks: SubTask[]): number {
    const taskMap = new Map(subTasks.map(t => [t.id, t]));
    const depths = new Map<string, number>();
    
    const getDepth = (taskId: string): number => {
      if (depths.has(taskId)) return depths.get(taskId)!;
      
      const task = taskMap.get(taskId);
      if (!task || task.dependencies.length === 0) {
        depths.set(taskId, 0);
        return 0;
      }
      
      const maxDepDep = Math.max(...task.dependencies.map(dep => getDepth(dep)));
      const depth = maxDepDep + 1;
      depths.set(taskId, depth);
      return depth;
    };
    
    subTasks.forEach(t => getDepth(t.id));
    return Math.max(...Array.from(depths.values()));
  }
  
  /**
   * Extract main task description
   */
  private extractMainTask(prompt: string, classification: any): string {
    const intent = classification.intent.replace(/_/g, ' ');
    const entities = classification.entities;
    
    if (entities.company) {
      return `${intent} for ${entities.company}`;
    } else if (entities.metrics && entities.metrics.length > 0) {
      return `${intent} with ${entities.metrics.join(', ')}`;
    } else {
      return intent;
    }
  }
  
  /**
   * Assess prompt complexity
   */
  private assessPromptComplexity(prompt: string): 'simple' | 'moderate' | 'complex' {
    const wordCount = prompt.split(/\s+/).length;
    const hasMultipleTasks = (prompt.match(/\band\b/gi) || []).length > 2;
    const hasConditionals = /if|when|unless|otherwise/i.test(prompt);
    const hasTechnicalTerms = /dcf|npv|irr|wacc|ebitda|cagr/i.test(prompt);
    
    const complexityScore = 
      (wordCount > 50 ? 1 : 0) +
      (hasMultipleTasks ? 1 : 0) +
      (hasConditionals ? 1 : 0) +
      (hasTechnicalTerms ? 1 : 0);
    
    if (complexityScore >= 3) return 'complex';
    if (complexityScore >= 1) return 'moderate';
    return 'simple';
  }
  
  /**
   * Learn from routing outcomes
   */
  async learnFromOutcome(
    prompt: string,
    decision: RouteDecision,
    outcome: 'success' | 'failure' | 'partial',
    feedback?: string
  ): Promise<void> {
    // Store routing decision and outcome for future learning
    const learningData = {
      prompt,
      decision,
      outcome,
      feedback,
      timestamp: Date.now()
    };
    
    // Update handler confidence scores based on outcome
    if (outcome === 'failure' && decision.fallbackHandlers.length > 0) {
      // Suggest trying fallback handler next time
      console.log(`Consider using ${decision.fallbackHandlers[0]} for similar prompts`);
    }
    
    // Store for pattern recognition
    await this.storeLearningData(learningData);
  }
  
  private async storeLearningData(data: any): Promise<void> {
    // Store in vector DB or local storage for future similarity matching
    console.log('Storing routing outcome:', data);
  }
}

export const advancedPromptRouter = new AdvancedPromptRouter();