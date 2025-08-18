# Pure Analyst Agent Architecture

## Vision
An AI analyst that thinks and works like a top-tier investment analyst - navigating between tools, following methodologies, building models, and producing investment recommendations with full citations.

## Core Philosophy
**Not a chatbot, but a colleague** - The agent should work like an analyst at Goldman Sachs or Sequoia Capital, using multiple tools, following standard methodologies, and producing institutional-quality analysis.

## Agent Architecture

### 1. Two-Agent System

```typescript
// Agent 1: Orchestrator (Strategic Thinking)
class AnalystOrchestrator {
  role: "Investment Analyst - Strategic Layer"
  model: "claude-3-5-sonnet-20241022"  // Best reasoning
  
  responsibilities: [
    "Understand investment thesis",
    "Plan analysis workflow", 
    "Decide which tools/pages to use",
    "Synthesize findings into recommendations",
    "Ensure IPEV compliance"
  ]
  
  tools: [
    "navigation",      // Navigate between pages
    "workflow_planning", // Create analysis plans
    "synthesis",       // Combine multi-source data
    "report_generation" // Create final deliverables
  ]
}

// Agent 2: Executor (Task Execution)  
class AnalystExecutor {
  role: "Investment Analyst - Execution Layer"
  model: "claude-3-haiku-20240307"  // Fast, cheap for data tasks
  
  responsibilities: [
    "Extract data from pages",
    "Perform calculations",
    "Fill spreadsheets",
    "Run searches",
    "Format outputs"
  ]
  
  tools: [
    "grid_api",        // Spreadsheet manipulation
    "search_api",      // Tavily/web search
    "calculator",      // Financial calculations
    "data_extraction"  // Parse documents/pages
  ]
}
```

### 2. State Management

```typescript
// Analyst Working Memory
interface AnalystState {
  // Current Analysis
  currentCompany: string;
  analysisType: 'seed' | 'series_a' | 'growth' | 'exit';
  stage: 'research' | 'modeling' | 'valuation' | 'recommendation';
  
  // Workflow State
  currentPage: string;
  toolsUsed: Tool[];
  dataCollected: DataPoint[];
  
  // IPEV Compliance
  valuationMethod: 'market' | 'income' | 'cost';
  fairValueHierarchy: 1 | 2 | 3;  // Level 1/2/3 inputs
  adjustments: Adjustment[];
  
  // Working Data
  comparables: Company[];
  marketData: MarketMetrics;
  financials: FinancialStatements;
  
  // Reasoning Chain
  decisions: Decision[];
  assumptions: Assumption[];
  risks: Risk[];
  
  // Output Building
  findings: Finding[];
  charts: Chart[];
  recommendations: Recommendation[];
}

// Persistent Memory (Supabase)
interface AnalystMemory {
  // Learning from past analyses
  successfulTheses: InvestmentThesis[];
  valuationComps: ComparableDatabase;
  sectorKnowledge: SectorInsights[];
  
  // Methodologies
  ipevGuidelines: IPEVRules[];
  ddChecklist: DueDiligenceItem[];
  modelTemplates: FinancialModel[];
}
```

### 3. Page-as-Tool System

```typescript
// Each page becomes a tool the analyst can use
interface AnalystTool {
  page: string;
  purpose: string;
  inputs: string[];
  outputs: string[];
  usage: string;
}

const ANALYST_TOOLS: AnalystTool[] = [
  {
    page: '/accounts',
    purpose: 'Financial modeling and calculations',
    inputs: ['company_name', 'financials'],
    outputs: ['valuation', 'multiples', 'projections'],
    usage: 'Build DCF, comps, and financial models'
  },
  {
    page: '/pwerm',
    purpose: 'Probability-weighted scenario analysis',
    inputs: ['company', 'scenarios'],
    outputs: ['expected_return', 'risk_analysis'],
    usage: 'Calculate probability-weighted returns'
  },
  {
    page: '/portfolio',
    purpose: 'Portfolio construction and analysis',
    inputs: ['companies', 'allocations'],
    outputs: ['portfolio_metrics', 'correlations'],
    usage: 'Analyze portfolio fit and diversification'
  },
  {
    page: '/documents',
    purpose: 'Document analysis and extraction',
    inputs: ['pdf', 'pitch_deck'],
    outputs: ['extracted_data', 'key_metrics'],
    usage: 'Extract data from pitch decks and reports'
  },
  {
    page: '/companies',
    purpose: 'Company database and comparables',
    inputs: ['sector', 'stage', 'geography'],
    outputs: ['comparable_companies', 'benchmarks'],
    usage: 'Find comparables and sector benchmarks'
  },
  {
    page: '/market-intelligence',
    purpose: 'Real-time market data and news',
    inputs: ['company', 'sector', 'keywords'],
    outputs: ['market_data', 'news', 'trends'],
    usage: 'Gather market intelligence and trends'
  }
];
```

### 4. Prompting System

```typescript
// System Prompt for Orchestrator
const ORCHESTRATOR_PROMPT = `You are a Senior Investment Analyst at a top-tier venture capital firm.

Your approach to analysis:
1. Start with the investment thesis
2. Follow IPEV valuation guidelines 
3. Use multiple tools/pages to gather data
4. Build financial models with citations
5. Triangulate valuation using multiple methods
6. Document assumptions and risks
7. Provide clear investment recommendation

Available tools (pages you can navigate to):
- /accounts - Financial modeling spreadsheet
- /pwerm - Scenario analysis 
- /portfolio - Portfolio fit analysis
- /documents - Pitch deck analysis
- /companies - Comparable company data
- /market-intelligence - Market research

For each analysis, you should:
1. Plan your workflow
2. Delegate tasks to the Executor
3. Navigate between tools as needed
4. Synthesize findings
5. Generate investment memo

Remember: You're not a chatbot. You're an analyst. Think step-by-step, use tools systematically, and always cite sources.`;

// System Prompt for Executor
const EXECUTOR_PROMPT = `You are the execution layer of an Investment Analyst system.

Your responsibilities:
1. Execute specific tasks assigned by the Orchestrator
2. Extract and process data accurately
3. Perform calculations precisely
4. Format outputs properly
5. Always include citations

You have access to:
- Grid API for spreadsheet operations
- Search API for web/database queries
- Calculator for financial computations
- Parser for document extraction

Be fast, accurate, and always cite your sources with clickable links.`;
```

### 5. Workflow Example

```typescript
// Example: Analyzing a Series A Investment
class SeriesAAnalysis {
  async analyze(company: string) {
    // Step 1: Orchestrator plans the analysis
    const workflow = await orchestrator.plan({
      company,
      stage: 'series_a',
      objective: 'investment_decision'
    });
    
    // Step 2: Navigate to documents page
    await orchestrator.navigateTo('/documents');
    
    // Step 3: Executor extracts pitch deck data
    const pitchData = await executor.extractFromDocument({
      type: 'pitch_deck',
      extract: ['revenue', 'growth', 'team', 'product']
    });
    
    // Step 4: Navigate to companies page
    await orchestrator.navigateTo('/companies');
    
    // Step 5: Find comparables
    const comparables = await executor.findComparables({
      sector: pitchData.sector,
      stage: 'series_a',
      revenue_range: pitchData.revenue * [0.5, 2.0]
    });
    
    // Step 6: Navigate to accounts (spreadsheet)
    await orchestrator.navigateTo('/accounts');
    
    // Step 7: Build financial model
    await executor.buildModel({
      company: pitchData,
      comparables: comparables,
      method: 'multiples'
    });
    
    // Step 8: Navigate to PWERM
    await orchestrator.navigateTo('/pwerm');
    
    // Step 9: Run scenario analysis
    const scenarios = await executor.runScenarios({
      base: pitchData,
      upside: { probability: 0.3, multiple: 2.5 },
      downside: { probability: 0.2, multiple: 0.5 }
    });
    
    // Step 10: Synthesize and recommend
    const recommendation = await orchestrator.synthesize({
      pitchData,
      comparables,
      model: modelResults,
      scenarios,
      ipevCompliance: true
    });
    
    return recommendation;
  }
}
```

### 6. IPEV Integration

```typescript
// IPEV Valuation Guidelines Implementation
class IPEVCompliance {
  guidelines = {
    fairValue: {
      definition: "Price received to sell an asset in orderly transaction",
      hierarchy: {
        level1: "Quoted prices in active markets",
        level2: "Inputs other than quoted prices that are observable",
        level3: "Unobservable inputs"
      }
    },
    
    methods: {
      market: {
        multiples: ['EV/Revenue', 'EV/EBITDA', 'P/E'],
        comparable_transactions: true,
        quoted_prices: true
      },
      income: {
        dcf: true,
        dividend_discount: true,
        capitalized_earnings: true
      },
      replacement_cost: {
        net_assets: true,
        liquidation_value: true
      }
    },
    
    adjustments: {
      liquidity_discount: [0.2, 0.35],
      control_premium: [0.15, 0.30],
      marketability_discount: [0.25, 0.40]
    }
  };
  
  async validateValuation(valuation: Valuation): Promise<ComplianceResult> {
    // Check if methodology follows IPEV
    const methodCompliant = this.checkMethod(valuation.method);
    
    // Verify fair value hierarchy
    const hierarchyLevel = this.determineHierarchy(valuation.inputs);
    
    // Apply appropriate adjustments
    const adjustments = this.calculateAdjustments(valuation);
    
    // Document compliance
    return {
      compliant: methodCompliant,
      level: hierarchyLevel,
      adjustments,
      documentation: this.generateIPEVDocs(valuation)
    };
  }
}
```

### 7. Implementation Plan

```typescript
// Phase 1: Core Infrastructure (Week 1)
- [ ] Set up two-agent architecture
- [ ] Implement state management
- [ ] Create page navigation system
- [ ] Build tool registry

// Phase 2: IPEV & Methodologies (Week 2)
- [ ] Implement IPEV guidelines
- [ ] Add valuation methods
- [ ] Create compliance checker
- [ ] Build adjustment calculator

// Phase 3: Workflow Automation (Week 3)
- [ ] Create workflow templates
- [ ] Implement multi-step reasoning
- [ ] Add citation system
- [ ] Build report generator

// Phase 4: Intelligence Layer (Week 4)
- [ ] Add learning from past analyses
- [ ] Implement pattern recognition
- [ ] Create recommendation engine
- [ ] Add portfolio optimization
```

## Key Differentiators

1. **True Analyst Behavior**: Not Q&A, but active analysis
2. **Multi-Page Navigation**: Uses entire platform as toolset
3. **IPEV Compliant**: Follows institutional standards
4. **Full Citations**: Every data point traced to source
5. **Two-Agent Architecture**: Strategic + Execution layers
6. **Workflow Memory**: Maintains context across tools
7. **Institutional Quality**: Produces GP-ready memos

## Example Commands

```javascript
// Start a full analysis
analyst.analyze('Stripe', {
  type: 'growth_equity',
  methodology: 'ipev_compliant',
  output: 'investment_memo'
});

// Navigate between tools
analyst.goto('/accounts');
analyst.buildDCF('Stripe');
analyst.goto('/companies');
analyst.findComps('payments', 'series_c+');

// Generate reports
analyst.generateMemo({
  format: 'ic_presentation',
  sections: ['thesis', 'valuation', 'risks', 'recommendation']
});
```

## Success Metrics

- Time to complete analysis: <5 minutes
- Data points with citations: 100%
- IPEV compliance: 100%
- Accuracy vs human analyst: >90%
- Cost per analysis: <$1

This is an analyst that **thinks**, not just responds.