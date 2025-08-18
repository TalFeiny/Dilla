/**
 * Analyst Reasoning Engine
 * Teaches the agent to think and model like a VC analyst
 */

export class AnalystReasoningEngine {
  /**
   * Core analytical frameworks the agent should use
   */
  private analyticalFrameworks = {
    // 1. Unit Economics Analysis
    unitEconomics: {
      prompt: `Analyze unit economics:
      1. What is the CAC (Customer Acquisition Cost)?
      2. What is the LTV (Lifetime Value)?
      3. What is the LTV/CAC ratio? (Should be >3x)
      4. What is the payback period?
      5. How does this improve with scale?`,
      
      reasoning: `Think step by step:
      - First identify the revenue per customer
      - Then identify all costs to acquire that customer
      - Calculate the margin contribution
      - Project customer lifetime
      - Identify leverage points`
    },
    
    // 2. Market Sizing (TAM/SAM/SOM)
    marketSizing: {
      prompt: `Size the market opportunity:
      1. TAM: Total Addressable Market
      2. SAM: Serviceable Addressable Market  
      3. SOM: Serviceable Obtainable Market
      4. Growth rate of the market
      5. Market share capture timeline`,
      
      reasoning: `Approach:
      - Top-down: Start with total market spend
      - Bottom-up: Number of customers × price
      - Validate with comparables
      - Apply realistic capture rates (1-10% of SAM)`
    },
    
    // 3. Competitive Moat Analysis
    moatAnalysis: {
      prompt: `Evaluate competitive advantages:
      1. Network effects (does value increase with users?)
      2. Switching costs (how hard to leave?)
      3. Economies of scale (unit economics improvement?)
      4. Brand/regulatory moat
      5. Technical differentiation (how defensible?)`,
      
      reasoning: `Look for:
      - 10x better, not 10% better
      - Structural advantages vs execution advantages
      - Time to replicate
      - Capital requirements to compete`
    },
    
    // 4. Investment Return Modeling
    returnModeling: {
      prompt: `Model the investment return:
      1. Entry valuation and ownership %
      2. Revenue growth trajectory (T2D3 path?)
      3. Exit multiple based on comparables
      4. Dilution assumptions (2-3 more rounds)
      5. Probability-weighted scenarios`,
      
      reasoning: `Build scenarios:
      - Base case: 3-5x return
      - Upside case: 10x+ return  
      - Downside case: 0.5-1x return
      - Weight by probability
      - Target 3x+ net portfolio return`
    },
    
    // 5. Risk Assessment
    riskAssessment: {
      prompt: `Identify and quantify risks:
      1. Market risk (demand uncertainty)
      2. Execution risk (can team deliver?)
      3. Technology risk (will it work?)
      4. Regulatory risk
      5. Competition risk
      6. Financing risk (capital needs)`,
      
      reasoning: `For each risk:
      - Probability of occurrence
      - Impact if it occurs
      - Mitigation strategies
      - Early warning signals`
    }
  };
  
  /**
   * Pattern recognition from successful investments
   */
  private successPatterns = {
    highGrowth: {
      indicators: [
        'Triple, triple, double, double, double (T2D3)',
        'Net revenue retention >120%',
        'Organic growth >50% YoY',
        'Payback period <12 months',
        'Gross margins >70%'
      ],
      examples: ['Snowflake', 'Datadog', 'MongoDB']
    },
    
    networkEffects: {
      indicators: [
        'Viral coefficient >1',
        'User growth compounds',
        'Engagement increases with network size',
        'Winner-take-all dynamics'
      ],
      examples: ['Uber', 'Airbnb', 'LinkedIn']
    },
    
    platformShift: {
      indicators: [
        'Riding new technology wave',
        'Replacing legacy systems',
        '10x improvement in key metric',
        'Inevitable adoption curve'
      ],
      examples: ['Stripe (online payments)', 'Zoom (video)', 'Canva (design)']
    }
  };
  
  /**
   * Build a financial model like an analyst
   */
  buildFinancialModel(companyData: any): any {
    return {
      revenueModel: this.buildRevenueModel(companyData),
      costStructure: this.buildCostStructure(companyData),
      cashFlow: this.projectCashFlow(companyData),
      valuation: this.calculateValuation(companyData),
      sensitivity: this.runSensitivityAnalysis(companyData)
    };
  }
  
  /**
   * Build revenue projections
   */
  private buildRevenueModel(data: any): any {
    // Think like an analyst:
    // 1. Identify revenue drivers (users, ARPU, transactions)
    // 2. Project growth based on comparables
    // 3. Apply market constraints
    // 4. Stress test assumptions
    
    const model = {
      drivers: {
        customers: this.projectCustomerGrowth(data),
        arpu: this.projectARPU(data),
        retention: this.projectRetention(data)
      },
      
      projections: [],
      assumptions: [],
      comparables: []
    };
    
    // Build 5-year projections
    for (let year = 1; year <= 5; year++) {
      const customers = model.drivers.customers[year];
      const arpu = model.drivers.arpu[year];
      const retention = model.drivers.retention[year];
      
      model.projections.push({
        year,
        revenue: customers * arpu * retention,
        growth: year > 1 ? (customers * arpu * retention) / model.projections[year-2].revenue - 1 : 0
      });
    }
    
    return model;
  }
  
  /**
   * Make investment decision
   */
  makeInvestmentDecision(analysis: any): {
    recommendation: 'INVEST' | 'PASS' | 'FOLLOW';
    conviction: number;
    reasoning: string[];
    keyRisks: string[];
    upside: string;
  } {
    const scores = {
      market: this.scoreMarket(analysis),
      team: this.scoreTeam(analysis),
      product: this.scoreProduct(analysis),
      traction: this.scoreTraction(analysis),
      economics: this.scoreEconomics(analysis)
    };
    
    const totalScore = Object.values(scores).reduce((a, b) => a + b, 0) / 5;
    
    return {
      recommendation: totalScore > 70 ? 'INVEST' : totalScore > 50 ? 'FOLLOW' : 'PASS',
      conviction: totalScore,
      reasoning: this.generateReasoning(scores),
      keyRisks: this.identifyKeyRisks(analysis),
      upside: this.calculateUpside(analysis)
    };
  }
  
  /**
   * Think through investment memo
   */
  writeInvestmentMemo(company: string, data: any): string {
    return `
# Investment Memo: ${company}

## Executive Summary
${this.writeSummary(data)}

## Investment Thesis
${this.writeThesis(data)}

## Market Opportunity
${this.analyzeMarket(data)}

## Business Model
${this.analyzeBusinessModel(data)}

## Competitive Analysis
${this.analyzeCompetition(data)}

## Financial Analysis
${this.analyzeFinancials(data)}

## Risk Assessment
${this.assessRisks(data)}

## Return Projections
${this.projectReturns(data)}

## Recommendation
${this.makeRecommendation(data)}
    `.trim();
  }
  
  // Helper methods for scoring and analysis
  private scoreMarket(analysis: any): number {
    // Large market (>$10B) = 20 points
    // Fast growth (>20% CAGR) = 20 points
    // Early stage market = 10 points
    return 50; // Placeholder
  }
  
  private scoreTeam(analysis: any): number {
    // Repeat founders = 20 points
    // Domain expertise = 15 points
    // Technical capability = 15 points
    return 50; // Placeholder
  }
  
  private scoreProduct(analysis: any): number {
    // 10x improvement = 25 points
    // Clear differentiation = 25 points
    return 50; // Placeholder
  }
  
  private scoreTraction(analysis: any): number {
    // T2D3 growth path = 30 points
    // Strong retention = 20 points
    return 50; // Placeholder
  }
  
  private scoreEconomics(analysis: any): number {
    // LTV/CAC > 3 = 25 points
    // Gross margin > 70% = 25 points
    return 50; // Placeholder
  }
  
  private generateReasoning(scores: any): string[] {
    const reasoning = [];
    
    if (scores.market > 70) {
      reasoning.push('Large and growing market opportunity');
    }
    if (scores.economics > 70) {
      reasoning.push('Strong unit economics with improving margins');
    }
    if (scores.traction > 70) {
      reasoning.push('Exceptional growth trajectory matching T2D3');
    }
    
    return reasoning;
  }
  
  private identifyKeyRisks(analysis: any): string[] {
    return [
      'Competition from incumbents',
      'Regulatory uncertainty',
      'High burn rate requiring continuous funding'
    ];
  }
  
  private calculateUpside(analysis: any): string {
    return '10-20x return potential based on comparable exits';
  }
  
  // Projection helpers
  private projectCustomerGrowth(data: any): number[] {
    // T2D3: Triple, Triple, Double, Double, Double
    const currentCustomers = data.customers || 100;
    return [
      currentCustomers,
      currentCustomers * 3,
      currentCustomers * 9,
      currentCustomers * 18,
      currentCustomers * 36,
      currentCustomers * 72
    ];
  }
  
  private projectARPU(data: any): number[] {
    const currentARPU = data.arpu || 1000;
    const growth = 1.15; // 15% annual ARPU growth
    return Array(6).fill(0).map((_, i) => currentARPU * Math.pow(growth, i));
  }
  
  private projectRetention(data: any): number[] {
    // Assume improving retention
    return [0.85, 0.87, 0.89, 0.91, 0.93, 0.95];
  }
  
  private buildCostStructure(data: any): any {
    return {
      cogs: 0.3, // 30% COGS
      sales: 0.25, // 25% S&M
      rd: 0.2, // 20% R&D
      ga: 0.15 // 15% G&A
    };
  }
  
  private projectCashFlow(data: any): any {
    return {
      burnRate: -500000, // Monthly burn
      runway: 18, // Months
      breakeven: 36 // Months to profitability
    };
  }
  
  private calculateValuation(data: any): any {
    return {
      revenue_multiple: 10,
      comparables: ['Company A at 12x', 'Company B at 8x'],
      dcf: 100000000
    };
  }
  
  private runSensitivityAnalysis(data: any): any {
    return {
      optimistic: '15x return',
      base: '5x return',
      pessimistic: '1x return'
    };
  }
  
  // Memo writing helpers
  private writeSummary(data: any): string {
    return 'High-growth SaaS company with strong unit economics and clear path to $100M ARR.';
  }
  
  private writeThesis(data: any): string {
    return 'Platform shift opportunity with network effects and winner-take-all dynamics.';
  }
  
  private analyzeMarket(data: any): string {
    return '$50B TAM growing at 25% CAGR. Early innings with <5% penetration.';
  }
  
  private analyzeBusinessModel(data: any): string {
    return 'Subscription SaaS with 120% net revenue retention and <12 month payback.';
  }
  
  private analyzeCompetition(data: any): string {
    return '10x better product with strong technical moat. 18-month lead on competitors.';
  }
  
  private analyzeFinancials(data: any): string {
    return 'Path to $10M ARR this year, $30M next year. 70% gross margins improving to 85%.';
  }
  
  private assessRisks(data: any): string {
    return 'Primary risks: Execution, competition from BigCo, regulatory changes.';
  }
  
  private projectReturns(data: any): string {
    return 'Target 5-10x return based on $1B exit in 5-7 years.';
  }
  
  private makeRecommendation(data: any): string {
    return 'INVEST: High conviction opportunity with asymmetric risk/reward.';
  }
}

export const analystReasoning = new AnalystReasoningEngine();