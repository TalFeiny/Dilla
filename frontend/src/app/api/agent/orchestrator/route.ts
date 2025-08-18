import { NextRequest, NextResponse } from 'next/server';
import { spawn } from 'child_process';
import path from 'path';
import { advancedPromptRouter } from '@/lib/advanced-prompt-router';

// Agent modes available
export enum AgentMode {
  QUICK_CHAT = 'quick_chat',           // Simple Q&A
  MARKET_RESEARCH = 'market_research', // Tavily-powered research
  FINANCIAL_ANALYSIS = 'financial_analysis', // Metrics and valuations
  PWERM_ANALYSIS = 'pwerm_analysis',   // Full PWERM calculation
  DUE_DILIGENCE = 'due_diligence',     // Complete DD process
  COMPLIANCE_KYC = 'compliance_kyc',   // KYC and compliance checks
  DOCUMENT_ANALYSIS = 'document_analysis', // Process documents
  PORTFOLIO_MONITOR = 'portfolio_monitor', // Portfolio tracking
  LP_REPORTING = 'lp_reporting',       // Generate LP reports
  MULTI_AGENT = 'multi_agent'          // CrewAI full analysis
}

// Agent capabilities mapping
const AGENT_CAPABILITIES = {
  [AgentMode.QUICK_CHAT]: {
    description: 'Quick Q&A about VC topics, portfolio, or general questions',
    tools: [],
    timeEstimate: '< 5 seconds',
    cost: 'Low'
  },
  [AgentMode.MARKET_RESEARCH]: {
    description: 'Deep market research with TAM, competitors, trends, and exits',
    tools: ['tavily_search', 'market_analysis'],
    timeEstimate: '10-30 seconds',
    cost: 'Medium'
  },
  [AgentMode.FINANCIAL_ANALYSIS]: {
    description: 'Financial metrics, valuations, and unit economics analysis',
    tools: ['calculate_metrics', 'database_query'],
    timeEstimate: '5-10 seconds',
    cost: 'Low'
  },
  [AgentMode.PWERM_ANALYSIS]: {
    description: 'Full PWERM analysis with scenarios and exit modeling',
    tools: ['pwerm_calculator', 'market_research', 'scenario_modeling'],
    timeEstimate: '30-60 seconds',
    cost: 'High'
  },
  [AgentMode.DUE_DILIGENCE]: {
    description: 'Comprehensive due diligence with all checks',
    tools: ['document_analysis', 'compliance_check', 'market_research', 'financial_analysis'],
    timeEstimate: '1-3 minutes',
    cost: 'High'
  },
  [AgentMode.COMPLIANCE_KYC]: {
    description: 'KYC checks, corporate structure mapping, and compliance screening',
    tools: ['kyc_processor', 'sanctions_check', 'pep_check', 'corporate_registry'],
    timeEstimate: '30-60 seconds',
    cost: 'Medium'
  },
  [AgentMode.DOCUMENT_ANALYSIS]: {
    description: 'Extract and analyze information from documents',
    tools: ['ocr', 'nlp_extraction', 'document_classifier'],
    timeEstimate: '20-40 seconds',
    cost: 'Medium'
  },
  [AgentMode.PORTFOLIO_MONITOR]: {
    description: 'Monitor portfolio company metrics and alerts',
    tools: ['database_query', 'metric_tracking', 'alert_generation'],
    timeEstimate: '10-20 seconds',
    cost: 'Low'
  },
  [AgentMode.LP_REPORTING]: {
    description: 'Generate LP reports and communications',
    tools: ['report_generator', 'portfolio_analytics', 'performance_calculator'],
    timeEstimate: '30-60 seconds',
    cost: 'Medium'
  },
  [AgentMode.MULTI_AGENT]: {
    description: 'Full multi-agent analysis with CrewAI',
    tools: ['all'],
    timeEstimate: '2-5 minutes',
    cost: 'Very High'
  }
};

// Use advanced router to determine best agent and approach
async function determineAgentMode(query: string, context?: any): Promise<{ mode: AgentMode; confidence: number; reasoning: string }> {
  // Get routing decision from advanced router
  const routingDecision = await advancedPromptRouter.route(query, context);
  
  console.log('Advanced routing decision:', {
    handler: routingDecision.handler,
    confidence: routingDecision.confidence,
    subtasks: routingDecision.decomposition.subTasks.length,
    complexity: routingDecision.decomposition.estimatedComplexity
  });
  
  // Map advanced router handlers to agent modes
  const handlerToMode: Record<string, AgentMode> = {
    'compliance': AgentMode.COMPLIANCE_KYC,
    'valuation': AgentMode.PWERM_ANALYSIS,
    'market_intelligence': AgentMode.MARKET_RESEARCH,
    'financial_analysis': AgentMode.FINANCIAL_ANALYSIS,
    'due_diligence': AgentMode.DUE_DILIGENCE,
    'document_processing': AgentMode.DOCUMENT_ANALYSIS,
    'portfolio': AgentMode.PORTFOLIO_MONITOR,
    'reporting': AgentMode.LP_REPORTING,
    'multi_agent': AgentMode.MULTI_AGENT,
    'company_analysis': AgentMode.FINANCIAL_ANALYSIS,
    'research': AgentMode.MARKET_RESEARCH,
    'spreadsheet': AgentMode.FINANCIAL_ANALYSIS,
    'rl-agent': AgentMode.FINANCIAL_ANALYSIS
  };
  
  const mode = handlerToMode[routingDecision.handler] || AgentMode.QUICK_CHAT;
  
  return {
    mode,
    confidence: routingDecision.confidence,
    reasoning: routingDecision.reasoning
  };
}

// Execute compliance/KYC check
async function executeComplianceKYC(params: any) {
  const pythonPath = process.env.PYTHON_PATH || 'python3';
  const scriptPath = path.join(process.cwd(), '..', 'enhanced_compliance.py');
  
  return new Promise((resolve, reject) => {
    const pythonProcess = spawn(
      pythonPath,
      [scriptPath, '--entity', params.entity_name, '--mode', params.check_type || 'full'],
      {
        env: {
          ...process.env,
          OPENAI_API_KEY: process.env.OPENAI_API_KEY || '',
          TAVILY_API_KEY: process.env.TAVILY_API_KEY || ''
        }
      }
    );
    
    let output = '';
    let error = '';
    
    pythonProcess.stdout.on('data', (data) => {
      output += data.toString();
    });
    
    pythonProcess.stderr.on('data', (data) => {
      error += data.toString();
    });
    
    pythonProcess.on('close', (code) => {
      if (code === 0) {
        try {
          const result = JSON.parse(output);
          resolve(result);
        } catch (e) {
          resolve({ raw_output: output });
        }
      } else {
        reject(new Error(error || 'Compliance check failed'));
      }
    });
  });
}

// Execute PWERM analysis
async function executePWERM(params: any) {
  const response = await fetch(`${process.env.NEXT_PUBLIC_APP_URL || 'http://localhost:3001'}/api/pwerm-analysis`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(params)
  });
  
  if (!response.ok) {
    throw new Error('PWERM analysis failed');
  }
  
  return await response.json();
}

// Execute market research
async function executeMarketResearch(query: string) {
  const tavilyKey = process.env.TAVILY_API_KEY;
  if (!tavilyKey) {
    throw new Error('Tavily API key not configured');
  }
  
  const response = await fetch('https://api.tavily.com/search', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      api_key: tavilyKey,
      query,
      search_depth: 'advanced',
      max_results: 10,
      include_answer: true
    })
  });
  
  if (!response.ok) {
    throw new Error('Market research failed');
  }
  
  return await response.json();
}

// Main orchestrator handler
export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const { 
      message, 
      mode: requestedMode, 
      parameters = {},
      context = {},
      autoSelect = true 
    } = body;
    
    if (!message && !requestedMode) {
      return NextResponse.json(
        { error: 'Message or mode is required' },
        { status: 400 }
      );
    }
    
    // Determine which agent mode to use
    let selectedMode: AgentMode;
    let routingConfidence = 1.0;
    let routingReasoning = '';
    
    if (requestedMode && Object.values(AgentMode).includes(requestedMode)) {
      selectedMode = requestedMode;
    } else if (autoSelect) {
      const routingResult = await determineAgentMode(message, context);
      selectedMode = routingResult.mode;
      routingConfidence = routingResult.confidence;
      routingReasoning = routingResult.reasoning;
      
      console.log(`Routed to ${selectedMode} with confidence ${routingConfidence}: ${routingReasoning}`);
    } else {
      selectedMode = AgentMode.QUICK_CHAT;
    }
    
    console.log(`Agent Orchestrator: Selected mode ${selectedMode} for query: ${message}`);
    
    // Execute based on selected mode
    let result: any = {};
    let executionTime = Date.now();
    
    switch (selectedMode) {
      case AgentMode.COMPLIANCE_KYC:
        // Extract entity name from message or parameters
        const entityName = parameters.entity_name || 
          message.match(/check (\w+)|kyc for (\w+)|compliance on (\w+)/i)?.[1] ||
          message.split(' ').find((word: string) => word.length > 3 && word[0] === word[0].toUpperCase());
        
        if (!entityName) {
          result = { error: 'Entity name required for compliance check' };
        } else {
          result = await executeComplianceKYC({
            entity_name: entityName,
            check_type: parameters.check_type || 'full'
          });
        }
        break;
        
      case AgentMode.PWERM_ANALYSIS:
        // Extract company details from message or use parameters
        const companyName = parameters.company_name || 
          message.match(/pwerm for (\w+)|analyze (\w+)/i)?.[1];
        
        if (!companyName) {
          result = { error: 'Company name required for PWERM analysis' };
        } else {
          result = await executePWERM({
            company_name: companyName,
            current_arr: parameters.current_arr || 10,
            growth_rate: parameters.growth_rate || 1.0,
            sector: parameters.sector || 'SaaS'
          });
        }
        break;
        
      case AgentMode.MARKET_RESEARCH:
        result = await executeMarketResearch(message);
        break;
        
      case AgentMode.FINANCIAL_ANALYSIS:
        // Use V2 agent for financial analysis
        const finResponse = await fetch(`${process.env.NEXT_PUBLIC_APP_URL || 'http://localhost:3001'}/api/agent/v2`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ message, context })
        });
        result = await finResponse.json();
        break;
        
      case AgentMode.MULTI_AGENT:
        // Use CrewAI for comprehensive analysis
        const crewResponse = await fetch(`${process.env.NEXT_PUBLIC_APP_URL || 'http://localhost:3001'}/api/agent/crew`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            company_name: parameters.company_name || 'Unknown',
            current_arr: parameters.current_arr || 10,
            growth_rate: parameters.growth_rate || 1.0,
            sector: parameters.sector || 'SaaS',
            analysis_type: 'full'
          })
        });
        result = await crewResponse.json();
        break;
        
      default:
        // Use basic chat for quick responses
        const chatResponse = await fetch(`${process.env.NEXT_PUBLIC_APP_URL || 'http://localhost:3001'}/api/agent/chat`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ message, history: context.history || [] })
        });
        result = await chatResponse.json();
    }
    
    executionTime = Date.now() - executionTime;
    
    return NextResponse.json({
      success: true,
      mode: selectedMode,
      modeDetails: AGENT_CAPABILITIES[selectedMode],
      routing: {
        confidence: routingConfidence,
        reasoning: routingReasoning,
        wasAutoRouted: autoSelect
      },
      result,
      executionTime: `${executionTime}ms`,
      timestamp: new Date().toISOString()
    });
    
  } catch (error) {
    console.error('Agent Orchestrator Error:', error);
    return NextResponse.json(
      { 
        error: 'Agent execution failed',
        details: error instanceof Error ? error.message : 'Unknown error'
      },
      { status: 500 }
    );
  }
}

// GET endpoint to list available modes
export async function GET() {
  return NextResponse.json({
    availableModes: Object.entries(AGENT_CAPABILITIES).map(([mode, details]) => ({
      mode,
      ...details
    })),
    defaultMode: AgentMode.QUICK_CHAT,
    autoSelectEnabled: true
  });
}