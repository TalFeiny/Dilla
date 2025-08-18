/**
 * Scenario Modeling Engine
 * Monte Carlo simulations, sensitivity analysis, and stress testing
 */

export interface Scenario {
  id: string;
  name: string;
  probability: number;
  assumptions: Record<string, any>;
  outcomes: Record<string, number>;
}

export interface ScenarioModel {
  baseCase: Scenario;
  scenarios: Scenario[];
  monteCarloRuns?: number;
  correlations?: Record<string, number>;
}

// Pre-built scenario templates
export const SCENARIO_TEMPLATES = {
  venture: {
    exit: [
      { name: 'IPO Exit', probability: 0.05, multiple: 15, timeToExit: 7 },
      { name: 'Strategic Acquisition', probability: 0.15, multiple: 8, timeToExit: 5 },
      { name: 'PE Buyout', probability: 0.10, multiple: 5, timeToExit: 4 },
      { name: 'Acquihire', probability: 0.20, multiple: 1, timeToExit: 3 },
      { name: 'Failure', probability: 0.50, multiple: 0, timeToExit: 3 }
    ],
    growth: [
      { name: 'Hypergrowth', probability: 0.10, rate: 200, marginImprovement: 5 },
      { name: 'Strong Growth', probability: 0.25, rate: 100, marginImprovement: 3 },
      { name: 'Moderate Growth', probability: 0.40, rate: 50, marginImprovement: 2 },
      { name: 'Slow Growth', probability: 0.20, rate: 20, marginImprovement: 1 },
      { name: 'Decline', probability: 0.05, rate: -20, marginImprovement: -2 }
    ],
    market: [
      { name: 'Bull Market', probability: 0.20, multipleExpansion: 1.5, fundingAvailability: 'high' },
      { name: 'Normal Market', probability: 0.50, multipleExpansion: 1.0, fundingAvailability: 'medium' },
      { name: 'Bear Market', probability: 0.25, multipleExpansion: 0.6, fundingAvailability: 'low' },
      { name: 'Crisis', probability: 0.05, multipleExpansion: 0.3, fundingAvailability: 'none' }
    ]
  },
  
  macroeconomic: {
    interest: [
      { name: 'Rate Cuts', probability: 0.25, fedFunds: 3.0, impact: 1.3 },
      { name: 'Stable Rates', probability: 0.50, fedFunds: 5.0, impact: 1.0 },
      { name: 'Rate Hikes', probability: 0.25, fedFunds: 7.0, impact: 0.7 }
    ],
    inflation: [
      { name: 'Deflation', probability: 0.05, cpi: -1, valuationImpact: 0.8 },
      { name: 'Low Inflation', probability: 0.35, cpi: 2, valuationImpact: 1.1 },
      { name: 'Moderate Inflation', probability: 0.45, cpi: 4, valuationImpact: 0.95 },
      { name: 'High Inflation', probability: 0.15, cpi: 8, valuationImpact: 0.7 }
    ],
    recession: [
      { name: 'No Recession', probability: 0.60, gdpGrowth: 2.5, marketDecline: 0 },
      { name: 'Mild Recession', probability: 0.30, gdpGrowth: -1, marketDecline: 20 },
      { name: 'Severe Recession', probability: 0.10, gdpGrowth: -4, marketDecline: 40 }
    ]
  },
  
  regulatory: {
    ai: [
      { name: 'Light Touch', probability: 0.30, complianceCost: 0.02, growthImpact: 1.0 },
      { name: 'Moderate Regulation', probability: 0.50, complianceCost: 0.05, growthImpact: 0.85 },
      { name: 'Heavy Regulation', probability: 0.20, complianceCost: 0.15, growthImpact: 0.6 }
    ],
    tax: [
      { name: 'Tax Cuts', probability: 0.20, corporateRate: 15, capGainsRate: 15 },
      { name: 'Current Regime', probability: 0.60, corporateRate: 21, capGainsRate: 20 },
      { name: 'Tax Increases', probability: 0.20, corporateRate: 28, capGainsRate: 28 }
    ],
    antitrust: [
      { name: 'Permissive', probability: 0.25, maApproval: 0.95, breakupRisk: 0.01 },
      { name: 'Balanced', probability: 0.50, maApproval: 0.75, breakupRisk: 0.05 },
      { name: 'Aggressive', probability: 0.25, maApproval: 0.40, breakupRisk: 0.15 }
    ]
  },
  
  operational: {
    execution: [
      { name: 'Flawless Execution', probability: 0.05, efficiency: 1.3, customerChurn: 0.05 },
      { name: 'Strong Execution', probability: 0.25, efficiency: 1.1, customerChurn: 0.10 },
      { name: 'Average Execution', probability: 0.40, efficiency: 1.0, customerChurn: 0.15 },
      { name: 'Poor Execution', probability: 0.25, efficiency: 0.8, customerChurn: 0.25 },
      { name: 'Failed Execution', probability: 0.05, efficiency: 0.5, customerChurn: 0.50 }
    ],
    competition: [
      { name: 'Market Leader', probability: 0.10, marketShare: 0.40, pricingPower: 1.3 },
      { name: 'Strong Position', probability: 0.30, marketShare: 0.20, pricingPower: 1.1 },
      { name: 'Competitive', probability: 0.40, marketShare: 0.10, pricingPower: 1.0 },
      { name: 'Struggling', probability: 0.20, marketShare: 0.05, pricingPower: 0.85 }
    ],
    technology: [
      { name: 'Breakthrough Innovation', probability: 0.05, defensibility: 5, scalability: 10 },
      { name: 'Strong Tech Advantage', probability: 0.20, defensibility: 3, scalability: 5 },
      { name: 'Incremental Advantage', probability: 0.50, defensibility: 1.5, scalability: 2 },
      { name: 'Commoditized', probability: 0.25, defensibility: 1, scalability: 1 }
    ]
  }
};

/**
 * Monte Carlo Simulation Engine
 */
export class MonteCarloSimulator {
  private iterations: number;
  private random: () => number;
  
  constructor(iterations: number = 10000) {
    this.iterations = iterations;
    this.random = Math.random;
  }
  
  /**
   * Run Monte Carlo simulation for exit scenarios
   */
  simulateExits(
    initialInvestment: number,
    ownership: number,
    scenarios: any[]
  ): {
    expectedValue: number;
    irr: number[];
    multiple: number[];
    percentiles: Record<number, number>;
    probabilityOfLoss: number;
  } {
    const results: number[] = [];
    const irrs: number[] = [];
    const multiples: number[] = [];
    
    for (let i = 0; i < this.iterations; i++) {
      const scenario = this.selectScenario(scenarios);
      const exitValue = initialInvestment * scenario.multiple;
      const proceeds = exitValue * ownership;
      
      results.push(proceeds);
      multiples.push(scenario.multiple);
      
      // Calculate IRR
      const irr = this.calculateIRR(
        -initialInvestment,
        proceeds,
        scenario.timeToExit
      );
      irrs.push(irr);
    }
    
    // Calculate statistics
    results.sort((a, b) => a - b);
    const expectedValue = results.reduce((a, b) => a + b, 0) / results.length;
    const probabilityOfLoss = results.filter(r => r < initialInvestment).length / results.length;
    
    return {
      expectedValue,
      irr: this.getStatistics(irrs),
      multiple: this.getStatistics(multiples),
      percentiles: {
        5: results[Math.floor(results.length * 0.05)],
        25: results[Math.floor(results.length * 0.25)],
        50: results[Math.floor(results.length * 0.50)],
        75: results[Math.floor(results.length * 0.75)],
        95: results[Math.floor(results.length * 0.95)]
      },
      probabilityOfLoss
    };
  }
  
  /**
   * Simulate revenue growth scenarios
   */
  simulateRevenue(
    baseRevenue: number,
    years: number,
    growthScenarios: any[],
    marketScenarios: any[]
  ): number[][] {
    const simulations: number[][] = [];
    
    for (let i = 0; i < this.iterations; i++) {
      const growth = this.selectScenario(growthScenarios);
      const market = this.selectScenario(marketScenarios);
      
      const trajectory: number[] = [baseRevenue];
      let currentRevenue = baseRevenue;
      
      for (let year = 1; year <= years; year++) {
        // Add volatility
        const volatility = (this.random() - 0.5) * 0.2;
        const adjustedGrowth = (growth.rate / 100) * market.multipleExpansion * (1 + volatility);
        
        currentRevenue = currentRevenue * (1 + adjustedGrowth);
        trajectory.push(currentRevenue);
      }
      
      simulations.push(trajectory);
    }
    
    return simulations;
  }
  
  /**
   * Simulate DCF valuations with multiple variables
   */
  simulateDCF(
    revenues: number[],
    marginRange: [number, number],
    waccRange: [number, number],
    terminalGrowthRange: [number, number]
  ): {
    valuations: number[];
    sensitivityMatrix: number[][];
  } {
    const valuations: number[] = [];
    
    for (let i = 0; i < this.iterations; i++) {
      const margin = this.randomInRange(marginRange[0], marginRange[1]);
      const wacc = this.randomInRange(waccRange[0], waccRange[1]) / 100;
      const terminalGrowth = this.randomInRange(terminalGrowthRange[0], terminalGrowthRange[1]) / 100;
      
      // Calculate FCF
      const fcfs = revenues.map(r => r * margin);
      
      // Discount FCFs
      let pv = 0;
      for (let t = 0; t < fcfs.length; t++) {
        pv += fcfs[t] / Math.pow(1 + wacc, t + 1);
      }
      
      // Terminal value
      const terminalFCF = fcfs[fcfs.length - 1] * (1 + terminalGrowth);
      const terminalValue = terminalFCF / (wacc - terminalGrowth);
      const pvTerminal = terminalValue / Math.pow(1 + wacc, fcfs.length);
      
      valuations.push(pv + pvTerminal);
    }
    
    // Create sensitivity matrix
    const sensitivityMatrix = this.createSensitivityMatrix(
      revenues,
      marginRange,
      waccRange,
      terminalGrowthRange
    );
    
    return { valuations, sensitivityMatrix };
  }
  
  private selectScenario(scenarios: any[]): any {
    const r = this.random();
    let cumulative = 0;
    
    for (const scenario of scenarios) {
      cumulative += scenario.probability;
      if (r <= cumulative) {
        return scenario;
      }
    }
    
    return scenarios[scenarios.length - 1];
  }
  
  private calculateIRR(initialCF: number, finalCF: number, years: number): number {
    return Math.pow(finalCF / Math.abs(initialCF), 1 / years) - 1;
  }
  
  private randomInRange(min: number, max: number): number {
    return min + this.random() * (max - min);
  }
  
  private getStatistics(values: number[]): number[] {
    values.sort((a, b) => a - b);
    return [
      values[Math.floor(values.length * 0.05)],  // 5th percentile
      values[Math.floor(values.length * 0.25)],  // 25th percentile
      values[Math.floor(values.length * 0.50)],  // Median
      values[Math.floor(values.length * 0.75)],  // 75th percentile
      values[Math.floor(values.length * 0.95)]   // 95th percentile
    ];
  }
  
  private createSensitivityMatrix(
    revenues: number[],
    marginRange: [number, number],
    waccRange: [number, number],
    terminalGrowthRange: [number, number]
  ): number[][] {
    const matrix: number[][] = [];
    const marginSteps = 5;
    const waccSteps = 5;
    
    for (let i = 0; i < marginSteps; i++) {
      const row: number[] = [];
      const margin = marginRange[0] + (marginRange[1] - marginRange[0]) * i / (marginSteps - 1);
      
      for (let j = 0; j < waccSteps; j++) {
        const wacc = (waccRange[0] + (waccRange[1] - waccRange[0]) * j / (waccSteps - 1)) / 100;
        const terminalGrowth = (terminalGrowthRange[0] + terminalGrowthRange[1]) / 200; // Use midpoint
        
        // Simple DCF calculation
        const fcfs = revenues.map(r => r * margin);
        let pv = 0;
        for (let t = 0; t < fcfs.length; t++) {
          pv += fcfs[t] / Math.pow(1 + wacc, t + 1);
        }
        
        const terminalFCF = fcfs[fcfs.length - 1] * (1 + terminalGrowth);
        const terminalValue = terminalFCF / (wacc - terminalGrowth);
        const pvTerminal = terminalValue / Math.pow(1 + wacc, fcfs.length);
        
        row.push(pv + pvTerminal);
      }
      
      matrix.push(row);
    }
    
    return matrix;
  }
}

/**
 * Stress Testing Framework
 */
export class StressTester {
  /**
   * Generate stress test scenarios
   */
  static generateStressScenarios(modelType: string): Scenario[] {
    const scenarios: Scenario[] = [];
    
    switch (modelType) {
      case 'venture':
        scenarios.push(
          {
            id: 'black-swan',
            name: 'Black Swan Event',
            probability: 0.01,
            assumptions: {
              marketDecline: 70,
              fundingFreeze: true,
              valuationReset: 0.2,
              timeToRecovery: 36
            },
            outcomes: {
              survival: 0.1,
              dilution: 0.8,
              shutdownProb: 0.5
            }
          },
          {
            id: 'funding-winter',
            name: 'Funding Winter',
            probability: 0.15,
            assumptions: {
              valuationCompression: 0.5,
              runwayExtension: 24,
              growthReduction: 0.6,
              headcountReduction: 0.3
            },
            outcomes: {
              survival: 0.6,
              dilution: 0.4,
              pivotRequired: 0.7
            }
          },
          {
            id: 'competitor-dominance',
            name: 'Competitor Takes Market',
            probability: 0.20,
            assumptions: {
              marketShareLoss: 0.7,
              pricingPressure: 0.3,
              customerChurn: 0.5,
              talentDeparture: 0.2
            },
            outcomes: {
              acquisition: 0.4,
              pivot: 0.3,
              shutdown: 0.3
            }
          }
        );
        break;
        
      case 'credit':
        scenarios.push(
          {
            id: 'default-scenario',
            name: 'Payment Default',
            probability: 0.10,
            assumptions: {
              recoveryRate: 0.4,
              timeToRecovery: 18,
              legalCosts: 0.15,
              collateralValue: 0.6
            },
            outcomes: {
              principalRecovery: 0.4,
              interestRecovery: 0.1,
              totalLoss: 0.5
            }
          },
          {
            id: 'covenant-breach',
            name: 'Covenant Breach',
            probability: 0.25,
            assumptions: {
              dscr: 0.8,
              debtToEbitda: 6,
              amendmentFee: 0.02,
              rateIncrease: 0.03
            },
            outcomes: {
              waiver: 0.6,
              restructuring: 0.3,
              acceleration: 0.1
            }
          }
        );
        break;
    }
    
    return scenarios;
  }
  
  /**
   * Run comprehensive stress tests
   */
  static runStressTest(
    baseModel: any,
    stressScenarios: Scenario[]
  ): {
    scenario: Scenario;
    impact: number;
    breaksModel: boolean;
    mitigations: string[];
  }[] {
    const results = [];
    
    for (const scenario of stressScenarios) {
      // Apply stress to model
      const stressedModel = this.applyStress(baseModel, scenario);
      
      // Calculate impact
      const impact = (baseModel.value - stressedModel.value) / baseModel.value;
      
      // Check if model breaks
      const breaksModel = stressedModel.value < 0 || 
                          stressedModel.irr < baseModel.hurdleRate;
      
      // Generate mitigations
      const mitigations = this.generateMitigations(scenario, impact);
      
      results.push({
        scenario,
        impact,
        breaksModel,
        mitigations
      });
    }
    
    return results;
  }
  
  private static applyStress(model: any, scenario: Scenario): any {
    const stressedModel = { ...model };
    
    // Apply assumptions
    Object.entries(scenario.assumptions).forEach(([key, value]) => {
      if (stressedModel[key] !== undefined) {
        if (typeof value === 'number') {
          stressedModel[key] *= value;
        } else {
          stressedModel[key] = value;
        }
      }
    });
    
    // Recalculate value
    stressedModel.value = model.value * (1 - scenario.outcomes.totalLoss || 0);
    stressedModel.irr = model.irr * (1 - scenario.outcomes.dilution || 0);
    
    return stressedModel;
  }
  
  private static generateMitigations(scenario: Scenario, impact: number): string[] {
    const mitigations: string[] = [];
    
    if (impact > 0.5) {
      mitigations.push('Diversify portfolio to reduce concentration risk');
      mitigations.push('Implement hedging strategies');
    }
    
    if (scenario.assumptions.fundingFreeze) {
      mitigations.push('Extend runway by reducing burn rate');
      mitigations.push('Secure bridge financing or venture debt');
    }
    
    if (scenario.assumptions.marketShareLoss) {
      mitigations.push('Accelerate product differentiation');
      mitigations.push('Consider strategic partnerships or M&A');
    }
    
    if (scenario.assumptions.dscr && scenario.assumptions.dscr < 1) {
      mitigations.push('Negotiate covenant waivers proactively');
      mitigations.push('Improve working capital management');
    }
    
    return mitigations;
  }
}

/**
 * Scenario Builder for Spreadsheet Integration
 */
export function buildScenarioGrid(
  modelType: string,
  baseCase: any
): {
  headers: string[];
  rows: any[][];
} {
  const scenarios = SCENARIO_TEMPLATES[modelType as keyof typeof SCENARIO_TEMPLATES];
  if (!scenarios) return { headers: [], rows: [] };
  
  // Build grid structure
  const headers = ['Scenario', 'Probability', ...Object.keys(baseCase), 'Expected Value'];
  const rows: any[][] = [];
  
  // Add base case
  rows.push(['Base Case', '100%', ...Object.values(baseCase), baseCase.value || 0]);
  
  // Add scenarios
  Object.entries(scenarios).forEach(([category, categoryScenarios]) => {
    rows.push([category.toUpperCase(), '', '', '', '', '']);
    
    categoryScenarios.forEach((scenario: any) => {
      const scenarioValues = Object.keys(baseCase).map(key => {
        if (scenario[key] !== undefined) {
          return scenario[key];
        }
        return baseCase[key] * (scenario.impact || 1);
      });
      
      const expectedValue = scenarioValues.reduce((a: any, b: any) => 
        (typeof a === 'number' && typeof b === 'number') ? a + b : 0, 0
      ) * scenario.probability;
      
      rows.push([
        scenario.name,
        `${(scenario.probability * 100).toFixed(0)}%`,
        ...scenarioValues,
        expectedValue
      ]);
    });
  });
  
  // Add summary statistics
  rows.push(['', '', '', '', '', '']);
  rows.push(['SUMMARY', '', '', '', '', '']);
  rows.push(['Expected Value', '', '', '', '', '=SUMPRODUCT(probabilities, outcomes)']);
  rows.push(['Standard Deviation', '', '', '', '', '=STDEV(outcomes)']);
  rows.push(['95% VaR', '', '', '', '', '=PERCENTILE(outcomes, 0.05)']);
  rows.push(['Maximum Loss', '', '', '', '', '=MIN(outcomes)']);
  
  return { headers, rows };
}