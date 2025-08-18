import { createClient } from '@supabase/supabase-js';
import Anthropic from '@anthropic-ai/sdk';

const supabase = createClient(
  process.env.NEXT_PUBLIC_SUPABASE_URL!,
  process.env.SUPABASE_SERVICE_ROLE_KEY!
);

const anthropic = new Anthropic({
  apiKey: process.env.ANTHROPIC_API_KEY || process.env.CLAUDE_API_KEY || '',
});

/**
 * Strategic Analyst Agent - Makes decisions and orchestrates analysis
 */
export class AnalystOrchestrator {
  private state: AnalystState;
  private memory: AnalystMemory;
  private currentPage: string = '/accounts';
  
  constructor() {
    this.state = this.initializeState();
    this.memory = this.loadMemory();
  }
  
  /**
   * Main analysis entry point
   */
  async analyzeInvestment(
    company: string,
    analysisType: 'seed' | 'series_a' | 'growth' | 'exit'
  ): Promise<InvestmentRecommendation> {
    // Initialize analysis
    this.state.currentCompany = company;
    this.state.analysisType = analysisType;
    this.state.stage = 'research';
    
    // Step 1: Plan the workflow
    const workflow = await this.planWorkflow(company, analysisType);
    
    // Step 2: Execute each workflow step
    for (const step of workflow.steps) {
      await this.executeWorkflowStep(step);
    }
    
    // Step 3: Synthesize findings
    const synthesis = await this.synthesizeFindings();
    
    // Step 4: Generate recommendation
    const recommendation = await this.generateRecommendation(synthesis);
    
    // Step 5: Validate IPEV compliance
    await this.validateIPEVCompliance(recommendation);
    
    return recommendation;
  }
  
  /**
   * Plan the analysis workflow based on company and stage
   */
  private async planWorkflow(company: string, analysisType: string): Promise<Workflow> {
    const prompt = `As a senior investment analyst, create a workflow to analyze ${company} for a ${analysisType} investment.
    
Available tools/pages:
- /accounts - Financial modeling spreadsheet
- /pwerm - Scenario analysis
- /portfolio - Portfolio fit analysis  
- /documents - Document extraction
- /companies - Comparable companies
- /market-intelligence - Market research

Create a step-by-step workflow that:
1. Gathers comprehensive data
2. Builds financial models
3. Analyzes scenarios
4. Follows IPEV guidelines
5. Produces investment recommendation

Return as JSON with structure:
{
  "steps": [
    {
      "step": 1,
      "action": "navigate",
      "target": "/documents",
      "task": "Extract pitch deck data",
      "expectedOutputs": ["revenue", "growth", "team"]
    }
  ]
}`;

    const response = await anthropic.messages.create({
      model: 'claude-3-5-sonnet-20241022',
      max_tokens: 2048,
      temperature: 0,
      system: this.getSystemPrompt(),
      messages: [{ role: 'user', content: prompt }]
    });
    
    const workflowText = response.content[0].type === 'text' ? response.content[0].text : '';
    return JSON.parse(this.extractJSON(workflowText));
  }
  
  /**
   * Execute a single workflow step
   */
  private async executeWorkflowStep(step: WorkflowStep): Promise<void> {
    // Navigate to the required page
    if (step.action === 'navigate') {
      await this.navigateTo(step.target);
    }
    
    // Delegate execution to the executor agent
    const executor = new AnalystExecutor();
    const result = await executor.executeTask(step.task, step.expectedOutputs);
    
    // Store results in state
    this.state.dataCollected.push({
      step: step.step,
      page: step.target,
      task: step.task,
      data: result.data,
      citations: result.citations,
      timestamp: new Date()
    });
    
    // Update workflow stage
    this.updateStage(step);
  }
  
  /**
   * Navigate to a specific page/tool
   */
  async navigateTo(page: string): Promise<void> {
    this.currentPage = page;
    this.state.currentPage = page;
    
    // Log navigation for audit trail
    this.state.toolsUsed.push({
      tool: page,
      timestamp: new Date(),
      purpose: this.getToolPurpose(page)
    });
    
    // In real implementation, this would trigger actual navigation
    console.log(`Navigating to: ${page}`);
  }
  
  /**
   * Synthesize all findings into coherent analysis
   */
  private async synthesizeFindings(): Promise<Synthesis> {
    const prompt = `Synthesize the following data into investment insights:
    
Company: ${this.state.currentCompany}
Analysis Type: ${this.state.analysisType}

Data Collected:
${JSON.stringify(this.state.dataCollected, null, 2)}

Comparables:
${JSON.stringify(this.state.comparables, null, 2)}

Market Data:
${JSON.stringify(this.state.marketData, null, 2)}

Provide:
1. Key findings
2. Valuation range
3. Risk factors
4. Growth potential
5. Investment thesis`;

    const response = await anthropic.messages.create({
      model: 'claude-3-5-sonnet-20241022',
      max_tokens: 4096,
      temperature: 0,
      system: this.getSystemPrompt(),
      messages: [{ role: 'user', content: prompt }]
    });
    
    const synthesisText = response.content[0].type === 'text' ? response.content[0].text : '';
    return this.parseSynthesis(synthesisText);
  }
  
  /**
   * Generate final investment recommendation
   */
  private async generateRecommendation(synthesis: Synthesis): Promise<InvestmentRecommendation> {
    return {
      company: this.state.currentCompany,
      recommendation: synthesis.investmentThesis.recommendation,
      confidence: synthesis.confidence,
      valuation: {
        method: this.state.valuationMethod,
        range: synthesis.valuationRange,
        preferred: synthesis.preferredValuation,
        comparables: this.state.comparables,
        adjustments: this.state.adjustments
      },
      thesis: synthesis.investmentThesis,
      risks: synthesis.risks,
      upside: synthesis.growthPotential,
      nextSteps: this.generateNextSteps(synthesis),
      citations: this.compileCitations(),
      ipevCompliant: true,
      generatedAt: new Date()
    };
  }
  
  /**
   * Validate IPEV compliance
   */
  private async validateIPEVCompliance(recommendation: InvestmentRecommendation): Promise<void> {
    const compliance = new IPEVCompliance();
    const result = await compliance.validateValuation(recommendation.valuation);
    
    if (!result.compliant) {
      // Apply necessary adjustments
      recommendation.valuation.adjustments = result.adjustments;
      recommendation.valuation.ipevLevel = result.level;
    }
    
    recommendation.ipevCompliant = result.compliant;
    recommendation.ipevDocumentation = result.documentation;
  }
  
  /**
   * Get system prompt for orchestrator
   */
  private getSystemPrompt(): string {
    return `You are a Senior Investment Analyst at a tier-1 venture capital firm.

Your analytical approach:
1. Systematic and thorough data gathering
2. Multiple valuation methodologies (market, income, cost)
3. IPEV guideline compliance
4. Risk-adjusted return analysis
5. Clear investment recommendations

You orchestrate analysis by:
- Planning multi-step workflows
- Navigating between tools/pages
- Delegating tasks to executor agents
- Synthesizing findings
- Generating institutional-quality recommendations

Think step-by-step, cite all sources, and maintain institutional standards.`;
  }
  
  /**
   * Initialize analyst state
   */
  private initializeState(): AnalystState {
    return {
      currentCompany: '',
      analysisType: 'series_a',
      stage: 'research',
      currentPage: '/accounts',
      toolsUsed: [],
      dataCollected: [],
      valuationMethod: 'market',
      fairValueHierarchy: 2,
      adjustments: [],
      comparables: [],
      marketData: {},
      financials: {},
      decisions: [],
      assumptions: [],
      risks: [],
      findings: [],
      charts: [],
      recommendations: []
    };
  }
  
  /**
   * Load analyst memory from database
   */
  private loadMemory(): AnalystMemory {
    // In production, load from Supabase
    return {
      successfulTheses: [],
      valuationComps: {},
      sectorKnowledge: [],
      ipevGuidelines: [],
      ddChecklist: [],
      modelTemplates: []
    };
  }
  
  /**
   * Extract JSON from Claude response
   */
  private extractJSON(text: string): string {
    const match = text.match(/\{[\s\S]*\}/);
    return match ? match[0] : '{}';
  }
  
  /**
   * Parse synthesis from text
   */
  private parseSynthesis(text: string): Synthesis {
    // Parse structured synthesis from Claude response
    return {
      keyFindings: [],
      valuationRange: { low: 0, high: 0, median: 0 },
      preferredValuation: 0,
      risks: [],
      growthPotential: {},
      investmentThesis: {
        summary: '',
        strengths: [],
        concerns: [],
        recommendation: 'pass'
      },
      confidence: 0.7
    };
  }
  
  /**
   * Generate next steps based on synthesis
   */
  private generateNextSteps(synthesis: Synthesis): string[] {
    const steps = [];
    
    if (synthesis.investmentThesis.recommendation === 'invest') {
      steps.push('Schedule deep dive with management team');
      steps.push('Conduct technical due diligence');
      steps.push('Perform customer reference calls');
      steps.push('Negotiate term sheet');
    } else if (synthesis.investmentThesis.recommendation === 'monitor') {
      steps.push('Set up quarterly check-ins');
      steps.push('Monitor key metrics');
      steps.push('Track competitive landscape');
    }
    
    return steps;
  }
  
  /**
   * Compile all citations from analysis
   */
  private compileCitations(): Citation[] {
    const citations = [];
    
    for (const data of this.state.dataCollected) {
      if (data.citations) {
        citations.push(...data.citations);
      }
    }
    
    return citations;
  }
  
  /**
   * Get purpose of each tool
   */
  private getToolPurpose(page: string): string {
    const purposes = {
      '/accounts': 'Financial modeling and valuation',
      '/pwerm': 'Scenario and probability analysis',
      '/portfolio': 'Portfolio fit assessment',
      '/documents': 'Document data extraction',
      '/companies': 'Comparable company analysis',
      '/market-intelligence': 'Market research and trends'
    };
    
    return purposes[page] || 'General analysis';
  }
  
  /**
   * Update workflow stage based on step
   */
  private updateStage(step: WorkflowStep): void {
    if (step.task.includes('model') || step.task.includes('valuation')) {
      this.state.stage = 'modeling';
    } else if (step.task.includes('scenario') || step.task.includes('probability')) {
      this.state.stage = 'valuation';
    } else if (step.task.includes('recommend') || step.task.includes('synthesize')) {
      this.state.stage = 'recommendation';
    }
  }
}

// Type definitions
interface AnalystState {
  currentCompany: string;
  analysisType: 'seed' | 'series_a' | 'growth' | 'exit';
  stage: 'research' | 'modeling' | 'valuation' | 'recommendation';
  currentPage: string;
  toolsUsed: Tool[];
  dataCollected: DataPoint[];
  valuationMethod: 'market' | 'income' | 'cost';
  fairValueHierarchy: 1 | 2 | 3;
  adjustments: Adjustment[];
  comparables: Company[];
  marketData: any;
  financials: any;
  decisions: Decision[];
  assumptions: Assumption[];
  risks: Risk[];
  findings: Finding[];
  charts: Chart[];
  recommendations: Recommendation[];
}

interface AnalystMemory {
  successfulTheses: any[];
  valuationComps: any;
  sectorKnowledge: any[];
  ipevGuidelines: any[];
  ddChecklist: any[];
  modelTemplates: any[];
}

interface Workflow {
  steps: WorkflowStep[];
}

interface WorkflowStep {
  step: number;
  action: string;
  target: string;
  task: string;
  expectedOutputs: string[];
}

interface Synthesis {
  keyFindings: string[];
  valuationRange: { low: number; high: number; median: number };
  preferredValuation: number;
  risks: Risk[];
  growthPotential: any;
  investmentThesis: {
    summary: string;
    strengths: string[];
    concerns: string[];
    recommendation: 'invest' | 'pass' | 'monitor';
  };
  confidence: number;
}

interface InvestmentRecommendation {
  company: string;
  recommendation: 'invest' | 'pass' | 'monitor';
  confidence: number;
  valuation: any;
  thesis: any;
  risks: Risk[];
  upside: any;
  nextSteps: string[];
  citations: Citation[];
  ipevCompliant: boolean;
  ipevDocumentation?: any;
  generatedAt: Date;
}

interface Citation {
  text: string;
  url: string;
  relevance: number;
}

interface Tool {
  tool: string;
  timestamp: Date;
  purpose: string;
}

interface DataPoint {
  step: number;
  page: string;
  task: string;
  data: any;
  citations: Citation[];
  timestamp: Date;
}

interface Company {
  name: string;
  sector: string;
  valuation: number;
  metrics: any;
}

interface Adjustment {
  type: string;
  value: number;
  reason: string;
}

interface Decision {
  decision: string;
  rationale: string;
  confidence: number;
}

interface Assumption {
  assumption: string;
  basis: string;
  sensitivity: number;
}

interface Risk {
  risk: string;
  probability: number;
  impact: number;
  mitigation: string;
}

interface Finding {
  finding: string;
  importance: number;
  evidence: string[];
}

interface Chart {
  type: string;
  data: any;
  title: string;
}

interface Recommendation {
  recommendation: string;
  priority: number;
  rationale: string;
}

// Export classes
export class AnalystExecutor {
  async executeTask(task: string, expectedOutputs: string[]): Promise<any> {
    // Implementation in next file
    return { data: {}, citations: [] };
  }
}

export class IPEVCompliance {
  async validateValuation(valuation: any): Promise<any> {
    // Implementation in next file
    return { compliant: true, level: 2, adjustments: [], documentation: {} };
  }
}