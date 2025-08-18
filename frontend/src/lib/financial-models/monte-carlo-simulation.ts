/**
 * Monte Carlo Simulation for Financial Models
 * Structured scenario generation with deterministic paths
 */

export interface MonteCarloInputs {
  baseCase: {
    revenue: number;
    growth: number;
    margin: number;
    multiple: number;
  };
  
  // Define structured variations, not random
  scenarios: {
    revenue: {
      upside: number[];    // [+5%, +10%, +15%]
      downside: number[];  // [-5%, -10%, -15%]
    };
    growth: {
      upside: number[];
      downside: number[];
    };
    margin: {
      expansion: number[];
      compression: number[];
    };
    multiple: {
      expansion: number[];
      compression: number[];
    };
  };
  
  // Correlation matrix for variables
  correlations: {
    revenueGrowth: number;
    growthMargin: number;
    marginMultiple: number;
  };
  
  // Number of structured paths (not random)
  paths: number; // e.g., 1000 deterministic scenarios
}

export interface MonteCarloOutput {
  scenarios: ScenarioResult[];
  statistics: {
    mean: number;
    median: number;
    stdDev: number;
    skewness: number;
    kurtosis: number;
    percentiles: {
      p5: number;
      p10: number;
      p25: number;
      p50: number;
      p75: number;
      p90: number;
      p95: number;
    };
    var95: number; // Value at Risk
    cvar95: number; // Conditional VaR
  };
  distribution: {
    bins: number[];
    frequencies: number[];
  };
  convergence: {
    iterations: number[];
    meanPath: number[];
    stdPath: number[];
  };
}

export interface ScenarioResult {
  id: number;
  inputs: {
    revenue: number;
    growth: number;
    margin: number;
    multiple: number;
  };
  outputs: {
    terminalValue: number;
    enterpriseValue: number;
    irr: number;
    moic: number;
  };
  probability: number;
  rank: number;
}

export class MonteCarloSimulation {
  private inputs: MonteCarloInputs;
  private scenarios: ScenarioResult[] = [];
  
  constructor(inputs: MonteCarloInputs) {
    this.inputs = inputs;
  }

  /**
   * Generate structured scenarios (not random)
   * Creates a deterministic grid of scenarios based on input variations
   */
  generateStructuredScenarios(): ScenarioResult[] {
    const scenarios: ScenarioResult[] = [];
    let scenarioId = 0;
    
    const { baseCase, scenarios: variations } = this.inputs;
    
    // Create a structured grid of scenarios
    // This is NOT random - it's a systematic exploration of the parameter space
    
    // Revenue scenarios
    const revenueScenarios = [
      baseCase.revenue, // base
      ...variations.revenue.upside.map(pct => baseCase.revenue * (1 + pct)),
      ...variations.revenue.downside.map(pct => baseCase.revenue * (1 - pct))
    ];
    
    // Growth scenarios  
    const growthScenarios = [
      baseCase.growth, // base
      ...variations.growth.upside,
      ...variations.growth.downside
    ];
    
    // Margin scenarios
    const marginScenarios = [
      baseCase.margin, // base
      ...variations.margin.expansion.map(pts => baseCase.margin + pts),
      ...variations.margin.compression.map(pts => baseCase.margin - pts)
    ];
    
    // Multiple scenarios
    const multipleScenarios = [
      baseCase.multiple, // base
      ...variations.multiple.expansion.map(x => baseCase.multiple + x),
      ...variations.multiple.compression.map(x => baseCase.multiple - x)
    ];
    
    // Generate all combinations with correlation adjustments
    for (const revenue of revenueScenarios) {
      for (const growth of growthScenarios) {
        for (const margin of marginScenarios) {
          for (const multiple of multipleScenarios) {
            // Apply correlations to create realistic scenarios
            const adjustedScenario = this.applyCorrelations(
              { revenue, growth, margin, multiple },
              baseCase
            );
            
            // Calculate outputs for this scenario
            const outputs = this.calculateScenarioOutputs(adjustedScenario);
            
            // Calculate probability based on distance from base case
            const probability = this.calculateScenarioProbability(
              adjustedScenario,
              baseCase
            );
            
            scenarios.push({
              id: scenarioId++,
              inputs: adjustedScenario,
              outputs,
              probability,
              rank: 0 // Will be set after sorting
            });
          }
        }
      }
    }
    
    // Sort by enterprise value and assign ranks
    scenarios.sort((a, b) => b.outputs.enterpriseValue - a.outputs.enterpriseValue);
    scenarios.forEach((s, i) => s.rank = i + 1);
    
    // Normalize probabilities to sum to 1
    const totalProb = scenarios.reduce((sum, s) => sum + s.probability, 0);
    scenarios.forEach(s => s.probability /= totalProb);
    
    this.scenarios = scenarios;
    return scenarios;
  }

  /**
   * Apply correlations between variables
   * This ensures realistic scenario combinations
   */
  private applyCorrelations(
    scenario: any,
    baseCase: any
  ): any {
    const { correlations } = this.inputs;
    
    // Revenue and growth correlation
    if (scenario.revenue > baseCase.revenue) {
      // Higher revenue tends to correlate with higher growth
      scenario.growth *= (1 + correlations.revenueGrowth * 
        (scenario.revenue / baseCase.revenue - 1));
    }
    
    // Growth and margin correlation (usually negative)
    if (scenario.growth > baseCase.growth) {
      // Higher growth often means lower margins
      scenario.margin *= (1 - Math.abs(correlations.growthMargin) * 
        (scenario.growth - baseCase.growth));
    }
    
    // Margin and multiple correlation
    if (scenario.margin > baseCase.margin) {
      // Higher margins justify higher multiples
      scenario.multiple *= (1 + correlations.marginMultiple * 
        (scenario.margin / baseCase.margin - 1));
    }
    
    return scenario;
  }

  /**
   * Calculate outputs for a scenario
   */
  private calculateScenarioOutputs(inputs: any): any {
    const projectionYears = 5;
    let revenue = inputs.revenue;
    const cashFlows: number[] = [];
    
    // Project cash flows
    for (let i = 0; i < projectionYears; i++) {
      revenue *= (1 + inputs.growth);
      const ebitda = revenue * inputs.margin;
      const fcf = ebitda * 0.7; // Simplified FCF conversion
      cashFlows.push(fcf);
    }
    
    // Terminal value
    const terminalValue = cashFlows[cashFlows.length - 1] * inputs.multiple;
    
    // Enterprise value (simplified - no discounting for this example)
    const enterpriseValue = cashFlows.reduce((sum, cf) => sum + cf, 0) + terminalValue;
    
    // Calculate returns (simplified)
    const initialInvestment = inputs.revenue * 5; // Assume 5x revenue entry
    const totalValue = enterpriseValue;
    const moic = totalValue / initialInvestment;
    const irr = Math.pow(moic, 1 / projectionYears) - 1;
    
    return {
      terminalValue,
      enterpriseValue,
      irr,
      moic
    };
  }

  /**
   * Calculate probability for a scenario based on distance from base case
   * Uses a multivariate normal distribution concept
   */
  private calculateScenarioProbability(
    scenario: any,
    baseCase: any
  ): number {
    // Calculate normalized distances
    const revenueDist = Math.abs(scenario.revenue - baseCase.revenue) / baseCase.revenue;
    const growthDist = Math.abs(scenario.growth - baseCase.growth) / Math.abs(baseCase.growth);
    const marginDist = Math.abs(scenario.margin - baseCase.margin) / baseCase.margin;
    const multipleDist = Math.abs(scenario.multiple - baseCase.multiple) / baseCase.multiple;
    
    // Combined distance (Euclidean)
    const totalDistance = Math.sqrt(
      revenueDist ** 2 + 
      growthDist ** 2 + 
      marginDist ** 2 + 
      multipleDist ** 2
    );
    
    // Convert distance to probability using exponential decay
    // Closer scenarios have higher probability
    const probability = Math.exp(-totalDistance * 2);
    
    return probability;
  }

  /**
   * Calculate statistics from scenarios
   */
  calculateStatistics(): MonteCarloOutput['statistics'] {
    const values = this.scenarios.map(s => s.outputs.enterpriseValue);
    const probabilities = this.scenarios.map(s => s.probability);
    
    // Weighted mean
    const mean = values.reduce((sum, val, i) => sum + val * probabilities[i], 0);
    
    // Weighted variance
    const variance = values.reduce((sum, val, i) => 
      sum + probabilities[i] * Math.pow(val - mean, 2), 0);
    const stdDev = Math.sqrt(variance);
    
    // Sort for percentiles
    const sortedScenarios = [...this.scenarios].sort(
      (a, b) => a.outputs.enterpriseValue - b.outputs.enterpriseValue
    );
    
    // Calculate percentiles
    const getPercentile = (p: number) => {
      const cumProb = sortedScenarios.reduce((acc, s) => {
        acc.push((acc[acc.length - 1] || 0) + s.probability);
        return acc;
      }, [] as number[]);
      
      const index = cumProb.findIndex(cp => cp >= p);
      return sortedScenarios[index]?.outputs.enterpriseValue || 0;
    };
    
    // Skewness
    const skewness = values.reduce((sum, val, i) => 
      sum + probabilities[i] * Math.pow((val - mean) / stdDev, 3), 0);
    
    // Kurtosis
    const kurtosis = values.reduce((sum, val, i) => 
      sum + probabilities[i] * Math.pow((val - mean) / stdDev, 4), 0) - 3;
    
    // Value at Risk (95th percentile)
    const var95 = getPercentile(0.05);
    
    // Conditional VaR (average of values below VaR)
    const belowVaR = sortedScenarios.filter(s => s.outputs.enterpriseValue <= var95);
    const cvar95 = belowVaR.reduce((sum, s) => sum + s.outputs.enterpriseValue * s.probability, 0) /
      belowVaR.reduce((sum, s) => sum + s.probability, 0);
    
    return {
      mean,
      median: getPercentile(0.5),
      stdDev,
      skewness,
      kurtosis,
      percentiles: {
        p5: getPercentile(0.05),
        p10: getPercentile(0.10),
        p25: getPercentile(0.25),
        p50: getPercentile(0.50),
        p75: getPercentile(0.75),
        p90: getPercentile(0.90),
        p95: getPercentile(0.95)
      },
      var95,
      cvar95
    };
  }

  /**
   * Create distribution histogram
   */
  createDistribution(bins: number = 20): MonteCarloOutput['distribution'] {
    const values = this.scenarios.map(s => s.outputs.enterpriseValue);
    const min = Math.min(...values);
    const max = Math.max(...values);
    const binWidth = (max - min) / bins;
    
    const binEdges: number[] = [];
    const frequencies: number[] = new Array(bins).fill(0);
    
    for (let i = 0; i <= bins; i++) {
      binEdges.push(min + i * binWidth);
    }
    
    // Count weighted frequencies
    this.scenarios.forEach(s => {
      const binIndex = Math.min(
        Math.floor((s.outputs.enterpriseValue - min) / binWidth),
        bins - 1
      );
      frequencies[binIndex] += s.probability;
    });
    
    return {
      bins: binEdges.slice(0, -1).map((edge, i) => (edge + binEdges[i + 1]) / 2),
      frequencies
    };
  }

  /**
   * Track convergence of the simulation
   */
  trackConvergence(): MonteCarloOutput['convergence'] {
    const iterations: number[] = [];
    const meanPath: number[] = [];
    const stdPath: number[] = [];
    
    // Calculate running statistics
    for (let i = 10; i <= this.scenarios.length; i += Math.floor(this.scenarios.length / 100)) {
      const subset = this.scenarios.slice(0, i);
      const values = subset.map(s => s.outputs.enterpriseValue);
      const weights = subset.map(s => s.probability);
      const totalWeight = weights.reduce((sum, w) => sum + w, 0);
      const normalizedWeights = weights.map(w => w / totalWeight);
      
      const mean = values.reduce((sum, val, j) => sum + val * normalizedWeights[j], 0);
      const variance = values.reduce((sum, val, j) => 
        sum + normalizedWeights[j] * Math.pow(val - mean, 2), 0);
      
      iterations.push(i);
      meanPath.push(mean);
      stdPath.push(Math.sqrt(variance));
    }
    
    return { iterations, meanPath, stdPath };
  }

  /**
   * Run complete simulation
   */
  run(): MonteCarloOutput {
    // Generate structured scenarios
    this.generateStructuredScenarios();
    
    // Calculate statistics
    const statistics = this.calculateStatistics();
    
    // Create distribution
    const distribution = this.createDistribution();
    
    // Track convergence
    const convergence = this.trackConvergence();
    
    return {
      scenarios: this.scenarios,
      statistics,
      distribution,
      convergence
    };
  }

  /**
   * Get scenario recommendations
   */
  getRecommendations(): {
    bestCase: ScenarioResult;
    worstCase: ScenarioResult;
    mostLikely: ScenarioResult;
    targetScenarios: ScenarioResult[];
  } {
    const sortedByValue = [...this.scenarios].sort(
      (a, b) => b.outputs.enterpriseValue - a.outputs.enterpriseValue
    );
    
    const sortedByProbability = [...this.scenarios].sort(
      (a, b) => b.probability - a.probability
    );
    
    // Find scenarios that meet target return (e.g., >20% IRR)
    const targetScenarios = this.scenarios.filter(s => s.outputs.irr > 0.20);
    
    return {
      bestCase: sortedByValue[0],
      worstCase: sortedByValue[sortedByValue.length - 1],
      mostLikely: sortedByProbability[0],
      targetScenarios: targetScenarios.sort((a, b) => b.probability - a.probability).slice(0, 10)
    };
  }
}