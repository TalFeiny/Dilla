/**
 * PWERM Probability Normalizer
 * Ensures all probabilities are properly normalized to sum to 100%
 * Handles adjustments while maintaining relative weightings
 */

export interface PWERMScenario {
  id: string;
  type: string;
  exit_value: number;
  probability: number;
  description: string;
  funding_path?: string;
  time_to_exit?: number;
}

export interface ProbabilityAdjustment {
  scenario_type: string;
  original_probability: number;
  adjusted_probability: number;
  reason: string;
}

export class PWERMProbabilityNormalizer {
  private static instance: PWERMProbabilityNormalizer;
  private readonly EPSILON = 0.0001; // Tolerance for floating point comparison
  private readonly MIN_PROBABILITY = 0.001; // 0.1% minimum for any scenario
  
  private constructor() {}

  static getInstance(): PWERMProbabilityNormalizer {
    if (!PWERMProbabilityNormalizer.instance) {
      PWERMProbabilityNormalizer.instance = new PWERMProbabilityNormalizer();
    }
    return PWERMProbabilityNormalizer.instance;
  }

  /**
   * Normalize scenarios to ensure probabilities sum to 100%
   */
  normalizeScenarios(scenarios: PWERMScenario[]): {
    normalized: PWERMScenario[];
    adjustments: ProbabilityAdjustment[];
    validation: ValidationResult;
  } {
    console.log('🔄 Normalizing PWERM probabilities...');
    
    // Step 1: Validate input
    const validation = this.validateScenarios(scenarios);
    if (!validation.isValid && validation.severity === 'error') {
      throw new Error(`Invalid scenarios: ${validation.message}`);
    }
    
    // Step 2: Calculate current sum
    const currentSum = this.calculateSum(scenarios);
    console.log(`  Current sum: ${(currentSum * 100).toFixed(2)}%`);
    
    // Step 3: Check if normalization is needed
    if (Math.abs(currentSum - 1.0) < this.EPSILON) {
      console.log('  ✅ Probabilities already normalized');
      return {
        normalized: scenarios,
        adjustments: [],
        validation: { isValid: true, message: 'Already normalized', severity: 'info' }
      };
    }
    
    // Step 4: Apply normalization strategy
    const strategy = this.selectNormalizationStrategy(scenarios, currentSum);
    console.log(`  Strategy: ${strategy}`);
    
    const result = this.applyNormalization(scenarios, strategy);
    
    // Step 5: Verify normalization
    const finalSum = this.calculateSum(result.normalized);
    if (Math.abs(finalSum - 1.0) > this.EPSILON) {
      // Apply fine-tuning if needed
      result.normalized = this.fineTuneNormalization(result.normalized);
    }
    
    console.log(`  ✅ Normalized to: ${(this.calculateSum(result.normalized) * 100).toFixed(2)}%`);
    
    return {
      ...result,
      validation: { isValid: true, message: 'Normalization completed successfully', severity: 'info' }
    };
  }

  /**
   * Adjust specific scenario probabilities while maintaining normalization
   */
  adjustScenarioProbabilities(
    scenarios: PWERMScenario[],
    adjustments: Map<string, number>
  ): {
    adjusted: PWERMScenario[];
    normalizationLog: string[];
  } {
    console.log('📊 Adjusting scenario probabilities...');
    
    const log: string[] = [];
    let adjusted = [...scenarios];
    
    // Step 1: Apply requested adjustments
    let totalAdjusted = 0;
    let totalOriginal = 0;
    
    adjustments.forEach((newProb, scenarioId) => {
      const scenario = adjusted.find(s => s.id === scenarioId);
      if (scenario) {
        totalOriginal += scenario.probability;
        scenario.probability = Math.max(this.MIN_PROBABILITY, Math.min(1.0, newProb));
        totalAdjusted += scenario.probability;
        log.push(`Adjusted ${scenario.type}: ${(newProb * 100).toFixed(2)}%`);
      }
    });
    
    // Step 2: Calculate remaining probability for unadjusted scenarios
    const unadjustedScenarios = adjusted.filter(s => !adjustments.has(s.id));
    const remainingProbability = 1.0 - totalAdjusted;
    
    if (remainingProbability < 0) {
      // Adjusted scenarios exceed 100%, need to scale down
      log.push('⚠️ Adjusted probabilities exceed 100%, scaling down...');
      adjusted = this.scaleDownProbabilities(adjusted, adjustments);
    } else if (unadjustedScenarios.length > 0) {
      // Distribute remaining probability among unadjusted scenarios
      const originalUnadjustedSum = unadjustedScenarios.reduce((sum, s) => sum + s.probability, 0);
      
      if (originalUnadjustedSum > 0) {
        // Scale proportionally
        const scaleFactor = remainingProbability / originalUnadjustedSum;
        unadjustedScenarios.forEach(scenario => {
          scenario.probability *= scaleFactor;
        });
        log.push(`Scaled unadjusted scenarios by ${(scaleFactor * 100).toFixed(2)}%`);
      } else {
        // Distribute equally
        const equalShare = remainingProbability / unadjustedScenarios.length;
        unadjustedScenarios.forEach(scenario => {
          scenario.probability = equalShare;
        });
        log.push(`Distributed ${(remainingProbability * 100).toFixed(2)}% equally`);
      }
    }
    
    // Step 3: Final normalization to ensure exactly 100%
    const normalizedResult = this.normalizeScenarios(adjusted);
    
    return {
      adjusted: normalizedResult.normalized,
      normalizationLog: log
    };
  }

  /**
   * Group and normalize scenarios by category
   */
  normalizeByCategory(scenarios: PWERMScenario[]): {
    normalized: PWERMScenario[];
    categoryWeights: Map<string, number>;
  } {
    // Group scenarios by type
    const categories = this.groupByCategory(scenarios);
    const categoryWeights = new Map<string, number>();
    
    // Calculate weight for each category
    categories.forEach((categoryScenarios, category) => {
      const weight = categoryScenarios.reduce((sum, s) => sum + s.probability, 0);
      categoryWeights.set(category, weight);
    });
    
    // Normalize within each category
    const normalized: PWERMScenario[] = [];
    
    categories.forEach((categoryScenarios, category) => {
      const categoryWeight = categoryWeights.get(category)!;
      const normalizedCategory = this.normalizeWithinCategory(categoryScenarios, categoryWeight);
      normalized.push(...normalizedCategory);
    });
    
    // Final normalization across all categories
    const finalNormalized = this.normalizeScenarios(normalized);
    
    return {
      normalized: finalNormalized.normalized,
      categoryWeights
    };
  }

  /**
   * Apply Monte Carlo normalization for large scenario sets
   */
  monteCarloNormalization(
    scenarios: PWERMScenario[],
    iterations: number = 10000
  ): PWERMScenario[] {
    console.log(`🎲 Running Monte Carlo normalization (${iterations} iterations)...`);
    
    // Run simulations to find stable probability distribution
    const counts = new Map<string, number>();
    scenarios.forEach(s => counts.set(s.id, 0));
    
    for (let i = 0; i < iterations; i++) {
      const selected = this.selectScenarioMonteCarlo(scenarios);
      counts.set(selected.id, (counts.get(selected.id) || 0) + 1);
    }
    
    // Calculate normalized probabilities from simulation
    const normalized = scenarios.map(scenario => ({
      ...scenario,
      probability: (counts.get(scenario.id) || 0) / iterations
    }));
    
    // Ensure minimum probability
    return this.enforceMinimumProbabilities(normalized);
  }

  /**
   * Private helper methods
   */
  private validateScenarios(scenarios: PWERMScenario[]): ValidationResult {
    if (!scenarios || scenarios.length === 0) {
      return { isValid: false, message: 'No scenarios provided', severity: 'error' };
    }
    
    const sum = this.calculateSum(scenarios);
    
    if (sum === 0) {
      return { isValid: false, message: 'All probabilities are zero', severity: 'error' };
    }
    
    if (sum < 0) {
      return { isValid: false, message: 'Negative probabilities detected', severity: 'error' };
    }
    
    if (Math.abs(sum - 1.0) > 0.5) {
      return { isValid: false, message: `Probabilities sum to ${(sum * 100).toFixed(2)}%`, severity: 'warning' };
    }
    
    return { isValid: true, message: 'Valid scenarios', severity: 'info' };
  }

  private calculateSum(scenarios: PWERMScenario[]): number {
    return scenarios.reduce((sum, s) => sum + (s.probability || 0), 0);
  }

  private selectNormalizationStrategy(scenarios: PWERMScenario[], currentSum: number): string {
    if (currentSum === 0) return 'equal_distribution';
    if (Math.abs(currentSum - 1.0) < 0.1) return 'proportional_scaling';
    if (scenarios.length > 100) return 'monte_carlo';
    if (this.hasCategories(scenarios)) return 'category_based';
    return 'proportional_scaling';
  }

  private applyNormalization(
    scenarios: PWERMScenario[],
    strategy: string
  ): {
    normalized: PWERMScenario[];
    adjustments: ProbabilityAdjustment[];
  } {
    const adjustments: ProbabilityAdjustment[] = [];
    let normalized: PWERMScenario[];
    
    switch (strategy) {
      case 'equal_distribution':
        normalized = this.equalDistribution(scenarios);
        break;
        
      case 'proportional_scaling':
        normalized = this.proportionalScaling(scenarios);
        break;
        
      case 'monte_carlo':
        normalized = this.monteCarloNormalization(scenarios);
        break;
        
      case 'category_based':
        const result = this.normalizeByCategory(scenarios);
        normalized = result.normalized;
        break;
        
      default:
        normalized = this.proportionalScaling(scenarios);
    }
    
    // Record adjustments
    scenarios.forEach((original, idx) => {
      const adjusted = normalized[idx];
      if (Math.abs(original.probability - adjusted.probability) > this.EPSILON) {
        adjustments.push({
          scenario_type: original.type,
          original_probability: original.probability,
          adjusted_probability: adjusted.probability,
          reason: `Applied ${strategy} normalization`
        });
      }
    });
    
    return { normalized, adjustments };
  }

  private proportionalScaling(scenarios: PWERMScenario[]): PWERMScenario[] {
    const sum = this.calculateSum(scenarios);
    if (sum === 0) return this.equalDistribution(scenarios);
    
    return scenarios.map(s => ({
      ...s,
      probability: s.probability / sum
    }));
  }

  private equalDistribution(scenarios: PWERMScenario[]): PWERMScenario[] {
    const equalProb = 1.0 / scenarios.length;
    return scenarios.map(s => ({
      ...s,
      probability: equalProb
    }));
  }

  private fineTuneNormalization(scenarios: PWERMScenario[]): PWERMScenario[] {
    const sum = this.calculateSum(scenarios);
    const adjustment = 1.0 - sum;
    
    // Find the scenario with the largest probability to absorb the adjustment
    const maxScenario = scenarios.reduce((max, s) => 
      s.probability > max.probability ? s : max
    );
    
    return scenarios.map(s => ({
      ...s,
      probability: s.id === maxScenario.id 
        ? s.probability + adjustment 
        : s.probability
    }));
  }

  private scaleDownProbabilities(
    scenarios: PWERMScenario[],
    adjusted: Map<string, number>
  ): PWERMScenario[] {
    const totalAdjusted = Array.from(adjusted.values()).reduce((sum, p) => sum + p, 0);
    const scaleFactor = 1.0 / totalAdjusted;
    
    return scenarios.map(s => {
      if (adjusted.has(s.id)) {
        return {
          ...s,
          probability: adjusted.get(s.id)! * scaleFactor
        };
      }
      return { ...s, probability: 0 };
    });
  }

  private groupByCategory(scenarios: PWERMScenario[]): Map<string, PWERMScenario[]> {
    const categories = new Map<string, PWERMScenario[]>();
    
    scenarios.forEach(s => {
      const category = this.getCategory(s);
      if (!categories.has(category)) {
        categories.set(category, []);
      }
      categories.get(category)!.push(s);
    });
    
    return categories;
  }

  private getCategory(scenario: PWERMScenario): string {
    // Categorize based on exit value ranges
    if (scenario.exit_value < 10_000_000) return 'liquidation';
    if (scenario.exit_value < 50_000_000) return 'modest_exit';
    if (scenario.exit_value < 100_000_000) return 'good_exit';
    if (scenario.exit_value < 500_000_000) return 'great_exit';
    if (scenario.exit_value < 1_000_000_000) return 'mega_exit';
    return 'unicorn_exit';
  }

  private normalizeWithinCategory(
    scenarios: PWERMScenario[],
    targetWeight: number
  ): PWERMScenario[] {
    const currentSum = this.calculateSum(scenarios);
    if (currentSum === 0) return scenarios;
    
    const scaleFactor = targetWeight / currentSum;
    
    return scenarios.map(s => ({
      ...s,
      probability: s.probability * scaleFactor
    }));
  }

  private hasCategories(scenarios: PWERMScenario[]): boolean {
    const categories = new Set(scenarios.map(s => this.getCategory(s)));
    return categories.size > 1;
  }

  private selectScenarioMonteCarlo(scenarios: PWERMScenario[]): PWERMScenario {
    const random = Math.random();
    let cumulative = 0;
    
    for (const scenario of scenarios) {
      cumulative += scenario.probability;
      if (random <= cumulative) {
        return scenario;
      }
    }
    
    return scenarios[scenarios.length - 1];
  }

  private enforceMinimumProbabilities(scenarios: PWERMScenario[]): PWERMScenario[] {
    let adjusted = scenarios.map(s => ({
      ...s,
      probability: Math.max(this.MIN_PROBABILITY, s.probability)
    }));
    
    // Re-normalize after enforcing minimums
    return this.proportionalScaling(adjusted);
  }

  /**
   * Export normalized scenarios for PWERM model
   */
  exportForPWERM(scenarios: PWERMScenario[]): {
    scenarios: PWERMScenario[];
    expected_value: number;
    probability_check: boolean;
  } {
    const normalized = this.normalizeScenarios(scenarios).normalized;
    
    // Calculate expected value
    const expectedValue = normalized.reduce(
      (ev, s) => ev + (s.exit_value * s.probability),
      0
    );
    
    // Verify probabilities sum to 1
    const sum = this.calculateSum(normalized);
    const probabilityCheck = Math.abs(sum - 1.0) < this.EPSILON;
    
    return {
      scenarios: normalized,
      expected_value: expectedValue,
      probability_check: probabilityCheck
    };
  }
}

interface ValidationResult {
  isValid: boolean;
  message: string;
  severity: 'error' | 'warning' | 'info';
}

// Export singleton
export const pwermProbabilityNormalizer = PWERMProbabilityNormalizer.getInstance();

// Helper function for quick normalization
export function normalizePWERMProbabilities(scenarios: PWERMScenario[]): PWERMScenario[] {
  return pwermProbabilityNormalizer.normalizeScenarios(scenarios).normalized;
}