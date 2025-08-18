/**
 * Investment Analysis Framework
 * Focuses on relative performance, funding dynamics, and key investor questions
 */

export interface FundingBenchmark {
  stage: string;
  medianRevenue: number;
  p25Revenue: number;
  p75Revenue: number;
  medianGrowth: number;
  requiredGrowthForNext: number; // Growth needed to raise next round
  medianValuation: number;
  medianDilution: number; // Typical dilution per round
  timeToNextRound: number; // Months
}

export interface CompanyPosition {
  currentRevenue: number;
  currentGrowth: number;
  currentValuation?: number;
  stage: string;
  lastRoundDate?: Date;
  totalRaised?: number;
  runway?: number; // Months
}

export interface CapTableImpact {
  currentOwnership: Record<string, number>;
  postMoneyValuation: number;
  dilutionPerStakeholder: Record<string, number>;
  newInvestorOwnership: number;
  optionPoolExpansion?: number;
}

export class InvestmentAnalyzer {
  
  /**
   * Key Question 1: How is this company doing relative to benchmark?
   */
  analyzeRelativePerformance(
    company: CompanyPosition,
    benchmark: FundingBenchmark
  ): {
    revenuePercentile: number;
    growthPercentile: number;
    valuationMultiple: number;
    performanceScore: number;
    analysis: string;
  } {
    // Revenue position (where does it sit in distribution?)
    let revenuePercentile = 50; // default median
    if (company.currentRevenue <= benchmark.p25Revenue) {
      revenuePercentile = 25 * (company.currentRevenue / benchmark.p25Revenue);
    } else if (company.currentRevenue >= benchmark.p75Revenue) {
      revenuePercentile = 75 + 25 * Math.min(1, (company.currentRevenue - benchmark.p75Revenue) / benchmark.p75Revenue);
    } else {
      // Linear interpolation between p25 and p75
      const range = benchmark.p75Revenue - benchmark.p25Revenue;
      const position = company.currentRevenue - benchmark.p25Revenue;
      revenuePercentile = 25 + 50 * (position / range);
    }
    
    // Growth position
    const growthPercentile = this.calculateGrowthPercentile(
      company.currentGrowth,
      benchmark.medianGrowth
    );
    
    // Valuation multiple (if we have valuation)
    const valuationMultiple = company.currentValuation 
      ? company.currentValuation / company.currentRevenue
      : benchmark.medianValuation / benchmark.medianRevenue;
    
    // Overall performance score (0-100)
    const performanceScore = (revenuePercentile * 0.4 + growthPercentile * 0.6);
    
    // Analysis text
    let analysis = `${company.currentRevenue >= benchmark.medianRevenue ? 'ABOVE' : 'BELOW'} median for ${company.stage}.\n`;
    
    if (performanceScore >= 75) {
      analysis += `Strong position - top quartile performance. Ready for next round.`;
    } else if (performanceScore >= 50) {
      analysis += `Solid position - at or above median. On track for next round with improvements.`;
    } else if (performanceScore >= 25) {
      analysis += `Below median - needs acceleration. Focus on growth to reach fundable metrics.`;
    } else {
      analysis += `Challenging position - significant improvement needed. Consider bridge or down round.`;
    }
    
    return {
      revenuePercentile,
      growthPercentile,
      valuationMultiple,
      performanceScore,
      analysis
    };
  }
  
  /**
   * Key Question 2: What growth/metrics needed for next round?
   */
  calculateNextRoundRequirements(
    company: CompanyPosition,
    currentBenchmark: FundingBenchmark,
    nextBenchmark: FundingBenchmark
  ): {
    requiredRevenue: number;
    requiredGrowth: number;
    impliedValuation: number;
    monthsToAchieve: number;
    feasibility: 'easy' | 'achievable' | 'stretch' | 'unlikely';
    specificTargets: string[];
  } {
    // What revenue is needed for next stage?
    const requiredRevenue = nextBenchmark.p25Revenue; // Minimum for next round
    
    // Required growth to get there
    const monthsToNextRound = company.runway || currentBenchmark.timeToNextRound;
    const revenueGap = requiredRevenue - company.currentRevenue;
    const requiredMonthlyGrowth = Math.pow(requiredRevenue / company.currentRevenue, 1 / monthsToNextRound) - 1;
    const requiredAnnualGrowth = Math.pow(1 + requiredMonthlyGrowth, 12) - 1;
    
    // Implied valuation at next round
    const medianMultiple = nextBenchmark.medianValuation / nextBenchmark.medianRevenue;
    const impliedValuation = requiredRevenue * medianMultiple;
    
    // Feasibility assessment
    let feasibility: 'easy' | 'achievable' | 'stretch' | 'unlikely';
    if (requiredAnnualGrowth <= company.currentGrowth) {
      feasibility = 'easy';
    } else if (requiredAnnualGrowth <= company.currentGrowth * 1.5) {
      feasibility = 'achievable';
    } else if (requiredAnnualGrowth <= company.currentGrowth * 2) {
      feasibility = 'stretch';
    } else {
      feasibility = 'unlikely';
    }
    
    // Specific targets
    const specificTargets = [
      `Reach $${(requiredRevenue / 1e6).toFixed(1)}M ARR (from current $${(company.currentRevenue / 1e6).toFixed(1)}M)`,
      `Maintain ${(requiredAnnualGrowth * 100).toFixed(0)}% growth rate`,
      `Achieve this in ${monthsToNextRound} months`,
      `Target valuation: $${(impliedValuation / 1e6).toFixed(0)}M`
    ];
    
    if (requiredAnnualGrowth > company.currentGrowth) {
      specificTargets.push(`ACCELERATE growth from ${(company.currentGrowth * 100).toFixed(0)}% to ${(requiredAnnualGrowth * 100).toFixed(0)}%`);
    }
    
    return {
      requiredRevenue,
      requiredGrowth: requiredAnnualGrowth,
      impliedValuation,
      monthsToAchieve: monthsToNextRound,
      feasibility,
      specificTargets
    };
  }
  
  /**
   * Key Question 3: What's the cap table impact of new funding?
   */
  calculateDilutionImpact(
    currentCapTable: Record<string, number>, // e.g., { "Founders": 0.60, "Series A": 0.25, "Options": 0.15 }
    newInvestment: number,
    preMoneyValuation: number,
    optionPoolIncrease: number = 0 // Additional option pool required
  ): CapTableImpact {
    const postMoneyValuation = preMoneyValuation + newInvestment;
    const newInvestorOwnership = newInvestment / postMoneyValuation;
    const dilutionFactor = 1 - newInvestorOwnership - optionPoolIncrease;
    
    // Calculate diluted ownership
    const dilutedOwnership: Record<string, number> = {};
    const dilutionPerStakeholder: Record<string, number> = {};
    
    for (const [stakeholder, ownership] of Object.entries(currentCapTable)) {
      const newOwnership = ownership * dilutionFactor;
      dilutedOwnership[stakeholder] = newOwnership;
      dilutionPerStakeholder[stakeholder] = ownership - newOwnership;
    }
    
    // Add new investor
    dilutedOwnership['New Investor'] = newInvestorOwnership;
    
    // Add to option pool if needed
    if (optionPoolIncrease > 0) {
      dilutedOwnership['Option Pool'] = (dilutedOwnership['Option Pool'] || 0) + optionPoolIncrease;
    }
    
    return {
      currentOwnership: dilutedOwnership,
      postMoneyValuation,
      dilutionPerStakeholder,
      newInvestorOwnership,
      optionPoolExpansion: optionPoolIncrease
    };
  }
  
  /**
   * Key Question 4: Multi-round dilution scenario
   */
  projectMultiRoundDilution(
    initialOwnership: Record<string, number>,
    fundingScenarios: Array<{
      round: string;
      investment: number;
      preMoneyValuation: number;
      optionPoolIncrease?: number;
    }>
  ): Array<{
    round: string;
    capTable: Record<string, number>;
    founderDilution: number;
    totalRaised: number;
  }> {
    const results = [];
    let currentCapTable = { ...initialOwnership };
    let totalRaised = 0;
    const initialFounderOwnership = currentCapTable['Founders'] || 0;
    
    for (const scenario of fundingScenarios) {
      const impact = this.calculateDilutionImpact(
        currentCapTable,
        scenario.investment,
        scenario.preMoneyValuation,
        scenario.optionPoolIncrease
      );
      
      currentCapTable = impact.currentOwnership;
      totalRaised += scenario.investment;
      
      results.push({
        round: scenario.round,
        capTable: { ...currentCapTable },
        founderDilution: initialFounderOwnership - (currentCapTable['Founders'] || 0),
        totalRaised
      });
    }
    
    return results;
  }
  
  /**
   * Generate actionable insights
   */
  generateInsights(
    performance: ReturnType<typeof this.analyzeRelativePerformance>,
    requirements: ReturnType<typeof this.calculateNextRoundRequirements>,
    dilution: CapTableImpact
  ): string[] {
    const insights = [];
    
    // Performance insights
    if (performance.revenuePercentile < 50) {
      insights.push(`📊 Revenue is ${(50 - performance.revenuePercentile).toFixed(0)} percentile points below median - focus on sales acceleration`);
    } else {
      insights.push(`✅ Revenue is ${(performance.revenuePercentile - 50).toFixed(0)} percentile points above median - strong position`);
    }
    
    // Growth insights
    if (performance.growthPercentile < 50) {
      insights.push(`📈 Growth rate below median - need to accelerate to stay competitive`);
    }
    
    // Funding timeline
    if (requirements.feasibility === 'easy' || requirements.feasibility === 'achievable') {
      insights.push(`🎯 Next round achievable at current trajectory in ${requirements.monthsToAchieve} months`);
    } else {
      insights.push(`⚠️ Next round is a ${requirements.feasibility} target - consider adjusting timeline or expectations`);
    }
    
    // Dilution insights
    const founderDilution = dilution.dilutionPerStakeholder['Founders'];
    if (founderDilution) {
      insights.push(`💰 Founders will be diluted by ${(founderDilution * 100).toFixed(1)}% in this round`);
      
      const postRoundOwnership = dilution.currentOwnership['Founders'];
      if (postRoundOwnership && postRoundOwnership < 0.5) {
        insights.push(`👥 Founders will own ${(postRoundOwnership * 100).toFixed(1)}% post-round - below 50% threshold`);
      }
    }
    
    // Valuation insights
    if (performance.valuationMultiple) {
      const benchmarkMultiple = 10; // Rough benchmark
      if (performance.valuationMultiple > benchmarkMultiple * 1.2) {
        insights.push(`💸 Valuation multiple (${performance.valuationMultiple.toFixed(1)}x) is rich - may face pressure in next round`);
      } else if (performance.valuationMultiple < benchmarkMultiple * 0.8) {
        insights.push(`💎 Valuation multiple (${performance.valuationMultiple.toFixed(1)}x) leaves room for upside`);
      }
    }
    
    return insights;
  }
  
  private calculateGrowthPercentile(actualGrowth: number, medianGrowth: number): number {
    // Simplified - assumes normal distribution around median
    const ratio = actualGrowth / medianGrowth;
    
    if (ratio >= 2) return 90;
    if (ratio >= 1.5) return 75;
    if (ratio >= 1) return 50 + (ratio - 1) * 50;
    if (ratio >= 0.5) return 25 + (ratio - 0.5) * 50;
    return Math.max(0, ratio * 50);
  }
  
  /**
   * Get stage-appropriate benchmarks
   */
  getBenchmarks(stage: string, geography: string = 'US'): FundingBenchmark {
    const benchmarks: Record<string, FundingBenchmark> = {
      'seed': {
        stage: 'Seed',
        medianRevenue: 0.5e6,
        p25Revenue: 0.1e6,
        p75Revenue: 1e6,
        medianGrowth: 3.0, // 300%
        requiredGrowthForNext: 2.0,
        medianValuation: 10e6,
        medianDilution: 0.20,
        timeToNextRound: 18
      },
      'series-a': {
        stage: 'Series A',
        medianRevenue: 2e6,
        p25Revenue: 1e6,
        p75Revenue: 4e6,
        medianGrowth: 2.0, // 200%
        requiredGrowthForNext: 1.5,
        medianValuation: 30e6,
        medianDilution: 0.20,
        timeToNextRound: 18
      },
      'series-b': {
        stage: 'Series B',
        medianRevenue: 10e6,
        p25Revenue: 5e6,
        p75Revenue: 20e6,
        medianGrowth: 1.0, // 100%
        requiredGrowthForNext: 0.8,
        medianValuation: 100e6,
        medianDilution: 0.15,
        timeToNextRound: 24
      },
      'series-c': {
        stage: 'Series C',
        medianRevenue: 30e6,
        p25Revenue: 20e6,
        p75Revenue: 50e6,
        medianGrowth: 0.7, // 70%
        requiredGrowthForNext: 0.5,
        medianValuation: 300e6,
        medianDilution: 0.12,
        timeToNextRound: 24
      }
    };
    
    const benchmark = benchmarks[stage.toLowerCase()] || benchmarks['series-b'];
    
    // Geographic adjustments (only for valuation)
    if (geography === 'UK') {
      benchmark.medianValuation *= 0.75;
    } else if (geography === 'EU') {
      benchmark.medianValuation *= 0.70;
    }
    
    return benchmark;
  }
}

export const investmentAnalyzer = new InvestmentAnalyzer();