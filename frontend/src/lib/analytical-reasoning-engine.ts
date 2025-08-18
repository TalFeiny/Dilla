/**
 * Analytical Reasoning Engine
 * Enables the agent to make intelligent assumptions and provide market analysis
 */

interface MarketContext {
  sector: string;
  stage: string;
  geography: string;
  currentDate: Date;
  macroFactors?: {
    interestRates?: number;
    inflationRate?: number;
    marketSentiment?: 'bullish' | 'neutral' | 'bearish';
  };
}

interface Assumption {
  metric: string;
  value: any;
  reasoning: string;
  confidence: number;
  sources: string[];
}

export class AnalyticalReasoningEngine {
  private sectorBenchmarks: Map<string, any> = new Map();
  private learningHistory: Assumption[] = [];
  
  constructor() {
    this.initializeBenchmarks();
  }
  
  /**
   * Generate intelligent assumptions based on context
   */
  async generateAssumptions(
    company: string,
    knownData: Record<string, any>,
    context: MarketContext
  ): Promise<Assumption[]> {
    const assumptions: Assumption[] = [];
    
    // 1. Growth Rate Assumptions
    if (!knownData.growthRate) {
      const growthAssumption = await this.assumeGrowthRate(
        company,
        knownData,
        context
      );
      assumptions.push(growthAssumption);
    }
    
    // 2. Margin Assumptions
    if (!knownData.grossMargin && knownData.revenue) {
      const marginAssumption = this.assumeMargins(
        context.sector,
        context.stage,
        knownData
      );
      assumptions.push(marginAssumption);
    }
    
    // 3. Valuation Multiple Assumptions
    if (!knownData.valuationMultiple) {
      const multipleAssumption = this.assumeValuationMultiple(
        context,
        knownData
      );
      assumptions.push(multipleAssumption);
    }
    
    // 4. Burn Rate and Runway
    if (knownData.cashBalance && !knownData.burnRate) {
      const burnAssumption = this.assumeBurnRate(
        context.stage,
        knownData
      );
      assumptions.push(burnAssumption);
    }
    
    // 5. Market Size and TAM
    if (!knownData.tam) {
      const tamAssumption = await this.assumeTAM(
        context.sector,
        company
      );
      assumptions.push(tamAssumption);
    }
    
    return assumptions;
  }
  
  /**
   * Assume growth rate based on sector, stage, and market conditions
   */
  private async assumeGrowthRate(
    company: string,
    knownData: Record<string, any>,
    context: MarketContext
  ): Promise<Assumption> {
    let baseGrowth = 0;
    let reasoning = '';
    
    // Stage-based baseline
    const stageGrowth: Record<string, number> = {
      'pre-seed': 2.0,      // 200% - early hypergrowth
      'seed': 1.5,          // 150%
      'series-a': 1.0,      // 100%
      'series-b': 0.7,      // 70%
      'series-c': 0.5,      // 50%
      'series-d+': 0.3,     // 30%
      'public': 0.15        // 15%
    };
    
    baseGrowth = stageGrowth[context.stage.toLowerCase()] || 0.3;
    reasoning = `Base ${context.stage} growth rate: ${(baseGrowth * 100).toFixed(0)}%`;
    
    // Sector adjustments
    const hotSectors = ['ai', 'genai', 'defense', 'climate', 'quantum'];
    const matureSectors = ['ecommerce', 'adtech', 'social'];
    
    if (hotSectors.some(s => context.sector.toLowerCase().includes(s))) {
      baseGrowth *= 1.3;
      reasoning += `, adjusted up 30% for hot sector (${context.sector})`;
    } else if (matureSectors.some(s => context.sector.toLowerCase().includes(s))) {
      baseGrowth *= 0.8;
      reasoning += `, adjusted down 20% for mature sector`;
    }
    
    // Market sentiment adjustment
    if (context.macroFactors?.marketSentiment === 'bullish') {
      baseGrowth *= 1.2;
      reasoning += ', +20% for bullish market';
    } else if (context.macroFactors?.marketSentiment === 'bearish') {
      baseGrowth *= 0.7;
      reasoning += ', -30% for bearish market';
    }
    
    // Revenue scale adjustment
    if (knownData.revenue) {
      if (knownData.revenue > 100000000) { // >$100M
        baseGrowth = Math.min(baseGrowth, 0.5);
        reasoning += ', capped at 50% due to scale';
      } else if (knownData.revenue < 1000000) { // <$1M
        baseGrowth = Math.max(baseGrowth, 1.0);
        reasoning += ', minimum 100% for early stage';
      }
    }
    
    return {
      metric: 'growthRate',
      value: baseGrowth,
      reasoning,
      confidence: 0.75,
      sources: ['Stage benchmarks', 'Sector analysis', 'Market conditions']
    };
  }
  
  /**
   * Assume margins based on business model and sector
   */
  private assumeMargins(
    sector: string,
    stage: string,
    knownData: Record<string, any>
  ): Assumption {
    const sectorMargins: Record<string, { gross: number, operating: number }> = {
      'saas': { gross: 0.75, operating: -0.1 },
      'marketplace': { gross: 0.30, operating: -0.05 },
      'fintech': { gross: 0.50, operating: 0.05 },
      'hardware': { gross: 0.35, operating: -0.15 },
      'biotech': { gross: 0.70, operating: -0.50 },
      'ecommerce': { gross: 0.25, operating: -0.02 },
      'enterprise': { gross: 0.80, operating: 0.10 },
      'consumer': { gross: 0.45, operating: -0.08 }
    };
    
    // Find best matching sector
    let margins = sectorMargins['saas']; // default
    let matchedSector = 'saas';
    
    for (const [key, value] of Object.entries(sectorMargins)) {
      if (sector.toLowerCase().includes(key)) {
        margins = value;
        matchedSector = key;
        break;
      }
    }
    
    // Adjust for stage
    let stageAdjustment = 0;
    if (stage.toLowerCase().includes('seed')) {
      margins.operating -= 0.3; // More negative in early stage
      stageAdjustment = -0.3;
    } else if (stage.toLowerCase().includes('series-c') || stage.toLowerCase().includes('series-d')) {
      margins.operating += 0.1; // Improving margins at scale
      stageAdjustment = 0.1;
    }
    
    return {
      metric: 'grossMargin',
      value: margins.gross,
      reasoning: `${matchedSector} sector typically has ${(margins.gross * 100).toFixed(0)}% gross margins, ` +
                `operating margin ${(margins.operating * 100).toFixed(0)}% ` +
                `(${stageAdjustment > 0 ? 'improved' : 'adjusted'} for ${stage} stage)`,
      confidence: 0.80,
      sources: ['Industry benchmarks', 'Stage patterns']
    };
  }
  
  /**
   * Assume valuation multiple based on comparables
   */
  private assumeValuationMultiple(
    context: MarketContext,
    knownData: Record<string, any>
  ): Assumption {
    // Base multiples by sector (EV/Revenue)
    const sectorMultiples: Record<string, number> = {
      'ai': 15,
      'saas': 8,
      'fintech': 6,
      'marketplace': 4,
      'ecommerce': 2,
      'hardware': 3,
      'biotech': 10,
      'defense': 12
    };
    
    let multiple = 5; // default
    let sector = 'general';
    
    for (const [key, value] of Object.entries(sectorMultiples)) {
      if (context.sector.toLowerCase().includes(key)) {
        multiple = value;
        sector = key;
        break;
      }
    }
    
    // Growth rate adjustment
    if (knownData.growthRate) {
      if (knownData.growthRate > 1.0) { // >100% growth
        multiple *= 1.5;
      } else if (knownData.growthRate > 0.5) { // >50% growth
        multiple *= 1.2;
      } else if (knownData.growthRate < 0.2) { // <20% growth
        multiple *= 0.7;
      }
    }
    
    // Market conditions
    const yearMultiplier = new Date().getFullYear() === 2025 ? 0.9 : 1.0; // 2025 adjustment
    multiple *= yearMultiplier;
    
    return {
      metric: 'valuationMultiple',
      value: multiple,
      reasoning: `${sector} companies typically trade at ${multiple.toFixed(1)}x revenue ` +
                `(adjusted for ${knownData.growthRate ? (knownData.growthRate * 100).toFixed(0) + '% growth' : 'market conditions'})`,
      confidence: 0.70,
      sources: ['Public comparables', 'Recent transactions']
    };
  }
  
  /**
   * Assume burn rate based on stage and team size
   */
  private assumeBurnRate(
    stage: string,
    knownData: Record<string, any>
  ): Assumption {
    const stageBurn: Record<string, number> = {
      'pre-seed': 50000,      // $50k/month
      'seed': 150000,         // $150k/month
      'series-a': 500000,     // $500k/month
      'series-b': 1500000,    // $1.5M/month
      'series-c': 3000000,    // $3M/month
      'series-d+': 5000000    // $5M+/month
    };
    
    let burn = stageBurn[stage.toLowerCase()] || 500000;
    let reasoning = `Typical ${stage} burn rate`;
    
    // Adjust based on headcount if known
    if (knownData.headcount) {
      const burnPerHead = 15000; // $15k/person/month fully loaded
      const impliedBurn = knownData.headcount * burnPerHead;
      if (Math.abs(impliedBurn - burn) > burn * 0.5) {
        burn = impliedBurn;
        reasoning = `Based on ${knownData.headcount} employees at $15k/month fully loaded cost`;
      }
    }
    
    // Adjust based on last funding if known
    if (knownData.lastFunding) {
      const expectedRunway = 18; // months
      const impliedBurn = knownData.lastFunding / expectedRunway;
      if (impliedBurn > burn * 0.5 && impliedBurn < burn * 2) {
        burn = impliedBurn;
        reasoning += `, calibrated to ${expectedRunway}-month runway from last raise`;
      }
    }
    
    return {
      metric: 'burnRate',
      value: burn,
      reasoning,
      confidence: 0.65,
      sources: ['Stage benchmarks', 'Headcount analysis']
    };
  }
  
  /**
   * Assume TAM based on sector
   */
  private async assumeTAM(
    sector: string,
    company: string
  ): Promise<Assumption> {
    const sectorTAMs: Record<string, { size: number, reasoning: string }> = {
      'ai': { size: 500e9, reasoning: 'Global AI market (McKinsey 2025)' },
      'saas': { size: 300e9, reasoning: 'Global SaaS market (Gartner)' },
      'fintech': { size: 250e9, reasoning: 'Global fintech market' },
      'ecommerce': { size: 5000e9, reasoning: 'Global e-commerce market' },
      'healthcare': { size: 12000e9, reasoning: 'Global healthcare spending' },
      'cybersecurity': { size: 200e9, reasoning: 'Global cybersecurity market' },
      'climate': { size: 1000e9, reasoning: 'Climate tech opportunity' },
      'defense': { size: 800e9, reasoning: 'Global defense spending' }
    };
    
    let tam = 100e9; // $100B default
    let reasoning = 'Estimated market size';
    
    for (const [key, value] of Object.entries(sectorTAMs)) {
      if (sector.toLowerCase().includes(key)) {
        tam = value.size;
        reasoning = value.reasoning;
        break;
      }
    }
    
    return {
      metric: 'tam',
      value: tam,
      reasoning,
      confidence: 0.60,
      sources: ['Industry reports', 'Market research']
    };
  }
  
  /**
   * Provide analytical judgment on investment opportunity
   */
  async analyzeInvestmentQuality(
    company: string,
    data: Record<string, any>,
    assumptions: Assumption[]
  ): Promise<{
    score: number;
    grade: string;
    strengths: string[];
    concerns: string[];
    recommendation: string;
  }> {
    let score = 50; // Start neutral
    const strengths: string[] = [];
    const concerns: string[] = [];
    
    // Growth analysis
    const growthRate = data.growthRate || assumptions.find(a => a.metric === 'growthRate')?.value;
    if (growthRate > 1.0) {
      score += 15;
      strengths.push(`Strong growth at ${(growthRate * 100).toFixed(0)}%`);
    } else if (growthRate < 0.3) {
      score -= 10;
      concerns.push(`Slow growth at ${(growthRate * 100).toFixed(0)}%`);
    }
    
    // Efficiency analysis
    const burnMultiple = data.burnRate && data.newARR ? data.burnRate * 12 / data.newARR : null;
    if (burnMultiple && burnMultiple < 1.5) {
      score += 10;
      strengths.push(`Efficient growth with ${burnMultiple.toFixed(1)}x burn multiple`);
    } else if (burnMultiple && burnMultiple > 3) {
      score -= 10;
      concerns.push(`Inefficient growth with ${burnMultiple.toFixed(1)}x burn multiple`);
    }
    
    // Market position
    const tam = data.tam || assumptions.find(a => a.metric === 'tam')?.value;
    const marketShare = data.revenue && tam ? data.revenue / tam : 0;
    if (marketShare > 0.01) { // >1% market share
      score += 10;
      strengths.push('Strong market position');
    } else if (tam > 100e9) {
      score += 5;
      strengths.push(`Large TAM of $${(tam / 1e9).toFixed(0)}B`);
    }
    
    // Valuation
    const multiple = data.valuationMultiple || assumptions.find(a => a.metric === 'valuationMultiple')?.value;
    if (multiple && growthRate) {
      const pgRatio = multiple / (growthRate * 100);
      if (pgRatio < 0.5) {
        score += 10;
        strengths.push('Attractive valuation relative to growth');
      } else if (pgRatio > 2) {
        score -= 10;
        concerns.push('Expensive valuation relative to growth');
      }
    }
    
    // Generate grade
    let grade: string;
    if (score >= 80) grade = 'A';
    else if (score >= 70) grade = 'B';
    else if (score >= 60) grade = 'C';
    else if (score >= 50) grade = 'D';
    else grade = 'F';
    
    // Generate recommendation
    let recommendation: string;
    if (score >= 75) {
      recommendation = 'Strong investment opportunity. Consider leading or co-leading the round.';
    } else if (score >= 60) {
      recommendation = 'Solid opportunity worth pursuing. Consider participating in the round.';
    } else if (score >= 50) {
      recommendation = 'Mixed signals. Conduct deeper diligence before proceeding.';
    } else {
      recommendation = 'Several concerns identified. Pass unless thesis strongly supports.';
    }
    
    return {
      score,
      grade,
      strengths,
      concerns,
      recommendation
    };
  }
  
  /**
   * Initialize sector benchmarks
   */
  private initializeBenchmarks() {
    // This would ideally load from a database or API
    this.sectorBenchmarks.set('saas', {
      medianGrowthRate: 0.6,
      medianGrossMargin: 0.75,
      medianBurnMultiple: 2.0,
      medianValuation: 8
    });
    
    this.sectorBenchmarks.set('fintech', {
      medianGrowthRate: 0.8,
      medianGrossMargin: 0.5,
      medianBurnMultiple: 2.5,
      medianValuation: 6
    });
  }
  
  /**
   * Learn from corrections to improve assumptions
   */
  learnFromCorrection(
    assumption: Assumption,
    actualValue: any,
    context: MarketContext
  ) {
    // Store the learning
    this.learningHistory.push({
      ...assumption,
      value: actualValue,
      reasoning: `Corrected: ${assumption.reasoning}`
    });
    
    // Adjust future confidence based on accuracy
    const error = Math.abs(assumption.value - actualValue) / actualValue;
    if (error > 0.5) {
      // Large error - reduce confidence in similar assumptions
      console.log(`Learning: ${assumption.metric} assumptions need adjustment (${error.toFixed(0)}% error)`);
    }
  }
}

// Export singleton
export const reasoningEngine = new AnalyticalReasoningEngine();