/**
 * Agent Orchestrator - Routes tasks to specialized agents with minimal context
 */

import Anthropic from '@anthropic-ai/sdk';

const anthropic = new Anthropic({
  apiKey: process.env.CLAUDE_API_KEY!,
});

export interface Skill {
  name: string;
  description: string;
  requiredTools: string[];
  contextNeeded: string[];
  endpoint?: string;
}

export interface TaskPlan {
  steps: Array<{
    skill: string;
    inputs: any;
    expectedOutput: string;
    dependencies?: number[]; // indices of steps that must complete first
  }>;
  parallelizable: boolean;
}

/**
 * Available specialized skills (each is a focused agent)
 */
export const SKILLS: Record<string, Skill> = {
  // Data retrieval skills
  company_search: {
    name: 'Company Search',
    description: 'Find companies by name or criteria',
    requiredTools: ['search_companies', 'fetch_company_data'],
    contextNeeded: ['company_name', 'filters']
  },
  
  market_research: {
    name: 'Market Research',
    description: 'Get TAM, competitors, market data',
    requiredTools: ['fetch_market_data', 'fetch_competitors'],
    contextNeeded: ['market', 'geography']
  },
  
  // Financial modeling skills
  dcf_model: {
    name: 'DCF Model Builder',
    description: 'Build discounted cash flow model',
    requiredTools: ['calculate_dcf', 'grid.write', 'grid.formula'],
    contextNeeded: ['revenue', 'growth_rates', 'wacc']
  },
  
  waterfall_analysis: {
    name: 'Waterfall Analysis',
    description: 'Create exit/fund waterfall',
    requiredTools: ['grid.createWaterfall'],
    contextNeeded: ['exit_value', 'preferences', 'participants']
  },
  
  revenue_flow: {
    name: 'Revenue Flow Visualization',
    description: 'Create Sankey diagram for revenue/costs',
    requiredTools: ['grid.createSankey'],
    contextNeeded: ['revenue_segments', 'cost_structure']
  },
  
  // Calculation skills
  basic_math: {
    name: 'Basic Calculations',
    description: 'Simple math and formulas',
    requiredTools: ['grid.formula', 'grid.write'],
    contextNeeded: ['formula', 'cells']
  },
  
  financial_metrics: {
    name: 'Financial Metrics',
    description: 'Calculate IRR, NPV, multiples',
    requiredTools: ['calculate_irr', 'calculate_npv'],
    contextNeeded: ['cashflows', 'rate']
  },
  
  // Analysis skills
  company_analysis: {
    name: 'Company Analysis',
    description: 'Analyze company health and metrics',
    requiredTools: ['analyze_financial_health'],
    contextNeeded: ['company_data', 'financials']
  },
  
  scenario_planning: {
    name: 'Scenario Planning',
    description: 'Run multiple scenarios',
    requiredTools: ['run_scenario_analysis'],
    contextNeeded: ['base_case', 'scenarios']
  },
  
  // Document generation
  memo_writer: {
    name: 'Memo Writer',
    description: 'Generate investment memos',
    requiredTools: ['generate_investment_memo'],
    contextNeeded: ['company', 'thesis', 'data']
  },
  
  // Vision analysis
  logo_extractor: {
    name: 'Logo & Product Extractor',
    description: 'Extract logos and products from documents',
    requiredTools: ['vision_analyze'],
    contextNeeded: ['document_url', 'company_name'],
    endpoint: '/api/vision/extract'
  }
};

/**
 * Main Orchestrator Class
 */
export class AgentOrchestrator {
  /**
   * Analyze task and create execution plan
   */
  async planTask(userPrompt: string, context?: any): Promise<TaskPlan> {
    const planningPrompt = `You are a task planner for a financial analysis system.
    
User request: "${userPrompt}"

Available skills:
${Object.entries(SKILLS).map(([key, skill]) => 
  `- ${key}: ${skill.description}`
).join('\n')}

Create an execution plan with the minimal set of skills needed.
Return JSON with this structure:
{
  "steps": [
    {
      "skill": "skill_name",
      "inputs": { ... },
      "expectedOutput": "description",
      "dependencies": []
    }
  ],
  "parallelizable": true/false
}

Be efficient - only use skills that are absolutely necessary.`;

    try {
      const response = await anthropic.messages.create({
        model: 'claude-3-haiku-20240307', // Fast planning
        max_tokens: 1000,
        messages: [{
          role: 'user',
          content: planningPrompt
        }]
      });
      
      const text = response.content[0].type === 'text' ? response.content[0].text : '{}';
      return JSON.parse(text);
    } catch (error) {
      console.error('Planning failed:', error);
      // Fallback to simple plan
      return this.createFallbackPlan(userPrompt);
    }
  }
  
  /**
   * Execute a task plan
   */
  async executePlan(plan: TaskPlan, gridApi?: any): Promise<any> {
    const results: any[] = [];
    const completed = new Set<number>();
    
    // Execute steps
    for (let i = 0; i < plan.steps.length; i++) {
      const step = plan.steps[i];
      
      // Wait for dependencies
      if (step.dependencies) {
        while (!step.dependencies.every(d => completed.has(d))) {
          await new Promise(resolve => setTimeout(resolve, 100));
        }
      }
      
      // Execute skill
      const result = await this.executeSkill(
        step.skill,
        step.inputs,
        gridApi,
        results
      );
      
      results.push(result);
      completed.add(i);
    }
    
    return this.combineResults(results, plan);
  }
  
  /**
   * Execute a single skill with minimal context
   */
  private async executeSkill(
    skillName: string,
    inputs: any,
    gridApi: any,
    previousResults: any[]
  ): Promise<any> {
    const skill = SKILLS[skillName];
    if (!skill) {
      throw new Error(`Unknown skill: ${skillName}`);
    }
    
    // Custom endpoint for skill?
    if (skill.endpoint) {
      const response = await fetch(skill.endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          skill: skillName,
          inputs,
          previousResults
        })
      });
      return response.json();
    }
    
    // Build minimal context for this skill
    const context = {
      tools: skill.requiredTools,
      inputs,
      gridApi: skill.requiredTools.some(t => t.startsWith('grid.')) ? gridApi : undefined
    };
    
    // Execute with focused agent
    return this.runFocusedAgent(skillName, context);
  }
  
  /**
   * Run a focused agent for a specific skill
   */
  private async runFocusedAgent(skillName: string, context: any): Promise<any> {
    const skill = SKILLS[skillName];
    
    // Minimal prompt for focused execution
    const prompt = `Execute the ${skill.name} task.
    
Available tools: ${skill.requiredTools.join(', ')}
Inputs: ${JSON.stringify(context.inputs)}

Complete the task and return the result. Be concise.`;
    
    // Use appropriate model based on complexity
    const model = this.selectModel(skillName);
    
    const response = await anthropic.messages.create({
      model,
      max_tokens: 2000,
      messages: [{
        role: 'user',
        content: prompt
      }]
    });
    
    // Parse and execute commands if needed
    if (context.gridApi) {
      const text = response.content[0].type === 'text' ? response.content[0].text : '';
      const commands = this.extractCommands(text);
      
      for (const cmd of commands) {
        try {
          await this.executeCommand(cmd, context.gridApi);
        } catch (error) {
          console.error(`Command failed: ${cmd}`, error);
        }
      }
      
      return { success: true, commands: commands.length };
    }
    
    return response.content[0];
  }
  
  /**
   * Select appropriate model based on skill complexity
   */
  private selectModel(skillName: string): string {
    const complexSkills = ['dcf_model', 'memo_writer', 'company_analysis'];
    const visionSkills = ['logo_extractor'];
    
    if (visionSkills.includes(skillName)) {
      return 'claude-3-5-sonnet-20241022'; // Vision capable
    }
    
    if (complexSkills.includes(skillName)) {
      return 'claude-3-5-sonnet-20241022'; // More capable
    }
    
    return 'claude-3-haiku-20240307'; // Fast and cheap
  }
  
  /**
   * Extract grid commands from agent response
   */
  private extractCommands(text: string): string[] {
    const commands: string[] = [];
    const cmdPattern = /grid\.[a-zA-Z]+\([^)]+\)/g;
    let match;
    
    while ((match = cmdPattern.exec(text)) !== null) {
      commands.push(match[0]);
    }
    
    return commands;
  }
  
  /**
   * Execute a grid command
   */
  private async executeCommand(command: string, gridApi: any): Promise<any> {
    // Parse the command
    const match = command.match(/grid\.([a-zA-Z]+)\((.*)\)/);
    if (!match) return;
    
    const [, method, args] = match;
    
    // Parse arguments (simple parsing, could be improved)
    const parsedArgs = this.parseArguments(args);
    
    // Execute on grid
    if (gridApi[method]) {
      return gridApi[method](...parsedArgs);
    }
  }
  
  /**
   * Parse command arguments
   */
  private parseArguments(argsString: string): any[] {
    try {
      // Simple JSON parse attempt
      return JSON.parse(`[${argsString}]`);
    } catch {
      // Fallback to splitting by comma
      return argsString.split(',').map(arg => {
        arg = arg.trim();
        if (arg.startsWith('"') && arg.endsWith('"')) {
          return arg.slice(1, -1);
        }
        if (!isNaN(Number(arg))) {
          return Number(arg);
        }
        return arg;
      });
    }
  }
  
  /**
   * Combine results from multiple skills
   */
  private combineResults(results: any[], plan: TaskPlan): any {
    return {
      success: true,
      steps: plan.steps.map((step, i) => ({
        skill: step.skill,
        output: results[i]
      })),
      summary: this.generateSummary(results, plan)
    };
  }
  
  /**
   * Generate summary of execution
   */
  private generateSummary(results: any[], plan: TaskPlan): string {
    const successful = results.filter(r => r && r.success !== false).length;
    return `Completed ${successful}/${plan.steps.length} steps successfully`;
  }
  
  /**
   * Create fallback plan for simple tasks
   */
  private createFallbackPlan(prompt: string): TaskPlan {
    // Detect task type from keywords
    if (prompt.toLowerCase().includes('dcf')) {
      return {
        steps: [{
          skill: 'dcf_model',
          inputs: { prompt },
          expectedOutput: 'DCF model'
        }],
        parallelizable: false
      };
    }
    
    if (prompt.toLowerCase().includes('waterfall')) {
      return {
        steps: [{
          skill: 'waterfall_analysis',
          inputs: { prompt },
          expectedOutput: 'Waterfall chart'
        }],
        parallelizable: false
      };
    }
    
    if (prompt.toLowerCase().includes('sankey') || prompt.toLowerCase().includes('revenue')) {
      return {
        steps: [{
          skill: 'revenue_flow',
          inputs: { prompt },
          expectedOutput: 'Sankey diagram'
        }],
        parallelizable: false
      };
    }
    
    // Default to basic calculation
    return {
      steps: [{
        skill: 'basic_math',
        inputs: { prompt },
        expectedOutput: 'Calculation result'
      }],
      parallelizable: false
    };
  }
}

// Export singleton
export const orchestrator = new AgentOrchestrator();