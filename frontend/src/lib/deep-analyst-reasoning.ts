/**
 * Deep Analyst Reasoning - Non-obvious insights and real analytical thinking
 */

export class DeepAnalystReasoning {
  /**
   * Counter-intuitive patterns that actually matter
   */
  private nonObviousSignals = {
    // The "boring" businesses that print money
    hiddenCashCows: {
      pattern: 'Unsexy vertical SaaS in regulated industries',
      signal: 'Compliance requirements create natural moat + pricing power',
      example: 'Veeva (pharma) trades at 20x revenue, not because of growth but captivity',
      insight: 'Look for industries where switching costs are regulatory, not technical'
    },
    
    // The "we're not competing" lie
    categoryCreation: {
      pattern: 'Company claims they have no competitors',
      signal: 'Either delusional OR creating genuinely new category',
      test: 'Are customers budget-shifting from different line items?',
      example: 'Databricks wasn\'t competing with databases, they competed with "hiring more data scientists"'
    },
    
    // Revenue quality > Revenue quantity
    revenueArchitecture: {
      pattern: 'How revenue compounds tells you everything',
      signal: 'Land-and-expand with negative churn > high growth with churn',
      math: 'Company A: $10M ARR growing 100% with 85% retention loses to Company B: $10M ARR growing 50% with 120% net retention',
      why: 'Company B\'s cohorts compound, Company A is filling a leaky bucket'
    },
    
    // The distribution insight everyone misses
    distributionArbitrage: {
      pattern: 'Found a channel competitors can\'t access',
      signal: 'Embedded in workflow, compliance requirement, or bundled with must-have',
      example: 'Gusto won by embedding in accountants\' workflow - Zenefits couldn\'t copy because of broker license requirements',
      insight: 'Distribution moats > product moats in commoditized markets'
    }
  };
  
  /**
   * Analyze like a first-principles thinker
   */
  async analyzeBusinessDeeply(company: string, data: any): Promise<any> {
    // 1. What expensive problem does this solve?
    const problemAnalysis = this.analyzeProblemValue(data);
    
    // 2. Why NOW? (Most important question)
    const timingAnalysis = this.analyzeWhyNow(data);
    
    // 3. What's the non-consensus insight?
    const contrarian = this.findContrarianTruth(data);
    
    // 4. Where's the leverage in the business model?
    const leverage = this.findLeveragePoints(data);
    
    // 5. What breaks this business?
    const killShots = this.identifyKillShots(data);
    
    return {
      deepInsights: {
        problemValue: problemAnalysis,
        whyNow: timingAnalysis,
        contrarianBet: contrarian,
        leverage: leverage,
        killShots: killShots
      },
      
      investmentThesis: this.synthesizeThesis(problemAnalysis, timingAnalysis, contrarian, leverage),
      
      questionsToProbe: this.generateProbeQuestions(data),
      
      patternMatch: this.matchToSuccessfulPatterns(data),
      
      probabilityOfSuccess: this.calculateRealProbability(data)
    };
  }
  
  /**
   * Analyze problem value - how expensive is the problem they solve?
   */
  private analyzeProblemValue(data: any): any {
    // Don't ask "what problem do you solve?"
    // Ask "what budget line item do you replace?"
    
    const analysis = {
      currentCost: null,
      hiddenCosts: [],
      urgency: null,
      alternativeCost: null
    };
    
    // Example: Rippling doesn't just replace HR software
    // It replaces: HR software + IT software + Finance software + 2 FTEs
    // Real value = $50k software + $200k salaries = $250k
    // They charge $30k = 88% gross margin to customer
    
    if (data.product) {
      // What's the fully-loaded cost of the status quo?
      analysis.currentCost = this.calculateStatusQuoCost(data);
      
      // What are the hidden costs? (time, errors, opportunity cost)
      analysis.hiddenCosts = [
        'Employee time wasted on manual processes',
        'Errors and compliance violations',
        'Opportunity cost of delayed decisions'
      ];
      
      // Is this a "painkiller" or "vitamin"?
      analysis.urgency = this.assessUrgency(data);
      
      // What happens if they don't buy?
      analysis.alternativeCost = 'Continue losing $X per month';
    }
    
    return analysis;
  }
  
  /**
   * Why is NOW the time for this company?
   */
  private analyzeWhyNow(data: any): any {
    // The best companies ride multiple "why nows"
    
    const catalysts = {
      regulatory: null,
      technological: null,
      behavioral: null,
      economic: null
    };
    
    // Example: Stripe's perfect timing
    // 1. Technological: AWS made starting internet companies cheap (2006)
    // 2. Behavioral: Developers became decision makers (2008)
    // 3. Economic: Financial crisis made banks pull back from startups (2009)
    // 4. Regulatory: PCI compliance became mandatory (2010)
    // Result: Stripe launches 2011 into perfect storm
    
    // Look for convergence of forces
    if (data.market) {
      catalysts.regulatory = this.findRegulatoryShifts(data);
      catalysts.technological = this.findTechShifts(data);
      catalysts.behavioral = this.findBehavioralShifts(data);
      catalysts.economic = this.findEconomicShifts(data);
    }
    
    const score = Object.values(catalysts).filter(c => c !== null).length;
    
    return {
      catalysts,
      score,
      verdict: score >= 3 ? 'Multiple tailwinds converging' : 
               score === 2 ? 'Good timing but not perfect' :
               'Timing unclear - dig deeper'
    };
  }
  
  /**
   * What's the non-consensus insight?
   */
  private findContrarianTruth(data: any): any {
    // The best investments are non-consensus and right
    
    const contrarian = {
      consensus: 'What everyone believes',
      reality: 'What\'s actually true',
      insight: 'The gap that creates opportunity',
      evidence: []
    };
    
    // Example: Airbnb
    // Consensus: "No one will let strangers sleep in their house"
    // Reality: "People will do anything to make rent in expensive cities"
    // Insight: "Supply was always there, trust layer was missing"
    
    // Look for beliefs that industry insiders think are crazy
    if (data.thesis) {
      contrarian.consensus = this.identifyConsensusView(data);
      contrarian.reality = this.identifyReality(data);
      contrarian.insight = this.articulateGap(data);
      contrarian.evidence = this.findEarlyEvidence(data);
    }
    
    return contrarian;
  }
  
  /**
   * Where's the leverage in the business?
   */
  private findLeveragePoints(data: any): any {
    // Software is leverage, but what kind?
    
    const leverage = {
      operational: null,  // Can 1 engineer serve 1M users?
      financial: null,    // Do margins expand with scale?
      strategic: null,    // Does value compound with usage?
      network: null       // Does each user make it better for others?
    };
    
    // Example: Figma's multiple leverage points
    // Operational: 1 engineer can serve millions
    // Financial: 90% gross margins
    // Strategic: Becomes system of record for design
    // Network: Collaboration makes it viral
    
    if (data.business_model) {
      leverage.operational = this.assessOperationalLeverage(data);
      leverage.financial = this.assessFinancialLeverage(data);
      leverage.strategic = this.assessStrategicLeverage(data);
      leverage.network = this.assessNetworkLeverage(data);
    }
    
    return leverage;
  }
  
  /**
   * What kills this business? (Pre-mortem)
   */
  private identifyKillShots(data: any): any {
    // Think like a short seller - what breaks this?
    
    const killShots = [];
    
    // Classic kill shots:
    // 1. Platform risk - building on someone else's land
    if (this.hasPlatformRisk(data)) {
      killShots.push({
        risk: 'Platform dependency',
        scenario: 'Platform changes rules or competes',
        probability: 0.3,
        mitigation: 'Multi-platform strategy or direct relationships'
      });
    }
    
    // 2. Regulatory guillotine
    if (this.hasRegulatoryRisk(data)) {
      killShots.push({
        risk: 'Regulatory shutdown',
        scenario: 'Regulation makes business model illegal',
        probability: 0.2,
        examples: 'Uber in many cities, crypto exchanges'
      });
    }
    
    // 3. Unit economics never work
    if (this.hasUnitEconomicsRisk(data)) {
      killShots.push({
        risk: 'Structural unprofitability',
        scenario: 'CAC never drops below LTV',
        probability: 0.4,
        redFlag: 'If year 5 projections still show negative contribution margin'
      });
    }
    
    // 4. Wrong atomic unit
    if (this.hasAtomicUnitRisk(data)) {
      killShots.push({
        risk: 'Solving wrong problem',
        scenario: 'Customers want X, company built Y',
        probability: 0.3,
        sign: 'Lots of customization requests'
      });
    }
    
    return {
      killShots,
      highestRisk: killShots.sort((a, b) => b.probability - a.probability)[0],
      composite: killShots.reduce((acc, ks) => acc * (1 - ks.probability), 1)
    };
  }
  
  /**
   * Generate non-obvious questions to probe
   */
  private generateProbeQuestions(data: any): string[] {
    // Questions that reveal truth
    return [
      // Revenue quality
      "Show me cohort revenue retention by month - not just logo retention",
      "What % of revenue comes from your oldest 20% of customers?",
      "How many customers would be screwed if you shut down tomorrow?",
      
      // True differentiation
      "What have you built that would take a competitor 18+ months to replicate?",
      "Which customers switched TO you from a competitor and why?",
      "What did you build that you thought would be valuable but customers didn't care about?",
      
      // Market dynamics
      "Who loses budget when you win?",
      "What needs to be true about the world for you to 100x?",
      "Which incumbent is most likely to copy you and when?",
      
      // Founder psychology
      "What would make you sell this company for $50M today?",
      "What metrics do you check obsessively?",
      "What's the thing about your business that keeps you up at night?"
    ];
  }
  
  /**
   * Pattern match to non-obvious success patterns
   */
  private matchToSuccessfulPatterns(data: any): any {
    const patterns = [];
    
    // Pattern 1: "System of Record" transformation
    // Boring database → Critical infrastructure
    // Examples: Salesforce, ServiceNow, Workday
    if (this.isSystemOfRecord(data)) {
      patterns.push({
        pattern: 'System of Record Play',
        match: 0.7,
        potential: '$10B+',
        playbook: 'Land as app, expand as platform, become unrippable'
      });
    }
    
    // Pattern 2: "Marketplace with SaaS wrapper"
    // Tool that happens to connect buyers/sellers
    // Examples: Toast, Faire, Flexport
    if (this.isHiddenMarketplace(data)) {
      patterns.push({
        pattern: 'Hidden Marketplace',
        match: 0.6,
        potential: '$5B+',
        playbook: 'Start as SaaS, add marketplace, take transaction fees'
      });
    }
    
    // Pattern 3: "Shift from CAPEX to OPEX"
    // Turn large upfront cost into subscription
    // Examples: AWS, Flexport, MainStreet
    if (this.isCapexToOpex(data)) {
      patterns.push({
        pattern: 'CAPEX to OPEX shift',
        match: 0.8,
        potential: '$1B+',
        playbook: 'Find expensive assets, make them rentable'
      });
    }
    
    return patterns;
  }
  
  /**
   * Calculate real probability of success
   */
  private calculateRealProbability(data: any): any {
    // Base rates matter
    const baseRate = 0.01; // 1% of startups become unicorns
    
    // Adjust based on evidence
    let multiple = 1;
    
    // Founder quality (3x if repeat successful founder)
    if (data.founders?.repeat_success) multiple *= 3;
    
    // Market timing (2x if multiple catalysts)
    if (data.timing?.score >= 3) multiple *= 2;
    
    // Traction proof (2x if growing >200% with good retention)
    if (data.growth > 2 && data.retention > 0.9) multiple *= 2;
    
    // Business model (1.5x if proven elsewhere)
    if (data.pattern_match?.length > 0) multiple *= 1.5;
    
    const adjustedProbability = Math.min(baseRate * multiple, 0.3);
    
    return {
      probability: adjustedProbability,
      confidence: this.calculateConfidence(data),
      verdict: adjustedProbability > 0.1 ? 'Above average' : 
               adjustedProbability > 0.05 ? 'Average' : 'Below average'
    };
  }
  
  /**
   * Synthesize all analysis into investment thesis
   */
  private synthesizeThesis(problem: any, timing: any, contrarian: any, leverage: any): string {
    // Don't write generic thesis
    // Write specific, falsifiable thesis
    
    // Bad: "AI-powered SaaS for enterprises"
    // Good: "Replacing McKinsey consultants with AI that reads every document in the company"
    
    return `
We believe ${contrarian.insight} will enable a new category of ${problem.alternativeCost}.
The convergence of ${timing.catalysts} creates a unique window where ${contrarian.reality}
overwhelms the previous constraint of ${contrarian.consensus}.
With ${leverage.strategic || leverage.network} as the compounding advantage,
this can capture ${problem.currentCost} of value currently spent on ${problem.alternativeCost}.
The key risk is ${this.identifyKillShots({}).highestRisk?.risk}, 
but early evidence of ${contrarian.evidence[0]} suggests this is manageable.
    `.trim();
  }
  
  // Helper methods (implement based on real data)
  private calculateStatusQuoCost(data: any): string {
    return '$500k/year in current tools + manual processes';
  }
  
  private assessUrgency(data: any): string {
    return 'Painkiller - compliance deadline creates forcing function';
  }
  
  private findRegulatoryShifts(data: any): string | null {
    return 'New SEC requirements for ESG reporting';
  }
  
  private findTechShifts(data: any): string | null {
    return 'LLMs make automation 10x cheaper';
  }
  
  private findBehavioralShifts(data: any): string | null {
    return 'Remote work made digital-first mandatory';
  }
  
  private findEconomicShifts(data: any): string | null {
    return 'High interest rates force efficiency over growth';
  }
  
  private identifyConsensusView(data: any): string {
    return 'This market is too small to matter';
  }
  
  private identifyReality(data: any): string {
    return 'Market is small because current solutions suck';
  }
  
  private articulateGap(data: any): string {
    return 'First good solution will expand the market 10x';
  }
  
  private findEarlyEvidence(data: any): string[] {
    return ['Customers paying 10x competitor prices', 'Zero churn in pilot'];
  }
  
  private assessOperationalLeverage(data: any): string {
    return 'One engineer per $10M ARR';
  }
  
  private assessFinancialLeverage(data: any): string {
    return 'Gross margins expand from 70% to 90% at scale';
  }
  
  private assessStrategicLeverage(data: any): string {
    return 'Becomes system of record after 6 months';
  }
  
  private assessNetworkLeverage(data: any): string {
    return 'Each user invites 2.3 others on average';
  }
  
  private hasPlatformRisk(data: any): boolean {
    return false; // Implement based on data
  }
  
  private hasRegulatoryRisk(data: any): boolean {
    return false; // Implement based on data
  }
  
  private hasUnitEconomicsRisk(data: any): boolean {
    return false; // Implement based on data
  }
  
  private hasAtomicUnitRisk(data: any): boolean {
    return false; // Implement based on data
  }
  
  private isSystemOfRecord(data: any): boolean {
    return false; // Implement based on data
  }
  
  private isHiddenMarketplace(data: any): boolean {
    return false; // Implement based on data
  }
  
  private isCapexToOpex(data: any): boolean {
    return false; // Implement based on data
  }
  
  private calculateConfidence(data: any): number {
    return 0.7; // Implement based on data completeness
  }
}

export const deepAnalyst = new DeepAnalystReasoning();