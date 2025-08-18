/**
 * Advanced Math Engine for Financial Modeling
 * Provides accurate calculations and financial formulas
 */

import * as math from 'mathjs';

export class AgentMathEngine {
  /**
   * Core financial formulas with step-by-step calculation
   */
  
  /**
   * NPV - Net Present Value
   * Shows each discounting step
   */
  calculateNPV(cashFlows: number[], discountRate: number): {
    npv: number;
    steps: any[];
    formula: string;
  } {
    const steps = [];
    let npv = 0;
    
    for (let t = 0; t < cashFlows.length; t++) {
      const cf = cashFlows[t];
      const discountFactor = Math.pow(1 + discountRate, t);
      const pv = cf / discountFactor;
      
      steps.push({
        period: t,
        cashFlow: cf,
        discountFactor: discountFactor.toFixed(4),
        calculation: `${cf} / (1 + ${discountRate})^${t} = ${cf} / ${discountFactor.toFixed(4)}`,
        presentValue: pv.toFixed(2)
      });
      
      npv += pv;
    }
    
    return {
      npv: Math.round(npv * 100) / 100,
      steps,
      formula: 'NPV = Σ[CFt / (1+r)^t]'
    };
  }
  
  /**
   * IRR - Internal Rate of Return
   * Uses Newton-Raphson method with detailed steps
   */
  calculateIRR(cashFlows: number[]): {
    irr: number;
    iterations: any[];
    verification: any;
  } {
    const iterations = [];
    let rate = 0.1; // Initial guess
    const maxIterations = 100;
    const tolerance = 0.0001;
    
    for (let i = 0; i < maxIterations; i++) {
      // Calculate NPV at current rate
      let npv = 0;
      let dnpv = 0; // Derivative
      
      for (let t = 0; t < cashFlows.length; t++) {
        const factor = Math.pow(1 + rate, t);
        npv += cashFlows[t] / factor;
        dnpv -= t * cashFlows[t] / Math.pow(1 + rate, t + 1);
      }
      
      iterations.push({
        iteration: i + 1,
        rate: (rate * 100).toFixed(2) + '%',
        npv: npv.toFixed(2),
        derivative: dnpv.toFixed(2)
      });
      
      // Newton-Raphson update
      const newRate = rate - npv / dnpv;
      
      if (Math.abs(newRate - rate) < tolerance) {
        // Verify the result
        const verification = this.calculateNPV(cashFlows, newRate);
        
        return {
          irr: Math.round(newRate * 10000) / 100, // As percentage
          iterations: iterations.slice(0, i + 1),
          verification: {
            npvAtIRR: verification.npv,
            shouldBeNearZero: Math.abs(verification.npv) < 1
          }
        };
      }
      
      rate = newRate;
    }
    
    throw new Error('IRR calculation did not converge');
  }
  
  /**
   * WACC - Weighted Average Cost of Capital
   * With detailed component breakdown
   */
  calculateWACC(params: {
    equityValue: number;
    debtValue: number;
    costOfEquity: number;
    costOfDebt: number;
    taxRate: number;
  }): {
    wacc: number;
    components: any;
    calculation: string;
  } {
    const { equityValue, debtValue, costOfEquity, costOfDebt, taxRate } = params;
    
    const totalValue = equityValue + debtValue;
    const equityWeight = equityValue / totalValue;
    const debtWeight = debtValue / totalValue;
    const afterTaxCostOfDebt = costOfDebt * (1 - taxRate);
    
    const wacc = (equityWeight * costOfEquity) + (debtWeight * afterTaxCostOfDebt);
    
    return {
      wacc: Math.round(wacc * 10000) / 100,
      components: {
        equityWeight: (equityWeight * 100).toFixed(1) + '%',
        debtWeight: (debtWeight * 100).toFixed(1) + '%',
        costOfEquity: (costOfEquity * 100).toFixed(1) + '%',
        costOfDebt: (costOfDebt * 100).toFixed(1) + '%',
        afterTaxCostOfDebt: (afterTaxCostOfDebt * 100).toFixed(1) + '%',
        taxShield: ((costOfDebt - afterTaxCostOfDebt) * 100).toFixed(1) + '%'
      },
      calculation: `WACC = (${equityValue}/${totalValue} × ${(costOfEquity*100).toFixed(1)}%) + (${debtValue}/${totalValue} × ${(costOfDebt*100).toFixed(1)}% × (1-${(taxRate*100).toFixed(0)}%)) = ${(wacc*100).toFixed(2)}%`
    };
  }
  
  /**
   * LTV Calculation with cohort decay
   */
  calculateLTV(params: {
    arpu: number;
    grossMargin: number;
    monthlyChurn: number;
    discountRate?: number;
  }): {
    ltv: number;
    components: any;
    cohortCurve: any[];
  } {
    const { arpu, grossMargin, monthlyChurn, discountRate = 0 } = params;
    
    // Simple LTV
    const simpleLTV = (arpu * grossMargin) / monthlyChurn;
    
    // Discounted LTV
    const monthlyDiscount = discountRate / 12;
    const discountedLTV = (arpu * grossMargin) / (monthlyChurn + monthlyDiscount);
    
    // Build cohort retention curve
    const cohortCurve = [];
    let remainingCustomers = 100;
    let cumulativeRevenue = 0;
    
    for (let month = 1; month <= 60; month++) {
      remainingCustomers *= (1 - monthlyChurn);
      const monthlyRevenue = remainingCustomers * arpu / 100;
      const discountFactor = Math.pow(1 + monthlyDiscount, month);
      const pvRevenue = monthlyRevenue / discountFactor;
      cumulativeRevenue += pvRevenue;
      
      if (month <= 24 || month % 6 === 0) {
        cohortCurve.push({
          month,
          retention: remainingCustomers.toFixed(1) + '%',
          monthlyRevenue: monthlyRevenue.toFixed(2),
          cumulativeLTV: (cumulativeRevenue * grossMargin).toFixed(2)
        });
      }
      
      if (remainingCustomers < 1) break;
    }
    
    return {
      ltv: discountRate > 0 ? discountedLTV : simpleLTV,
      components: {
        monthlyRevenue: arpu,
        monthlyGrossProfit: arpu * grossMargin,
        customerLifetimeMonths: 1 / monthlyChurn,
        monthlyChurn: (monthlyChurn * 100).toFixed(1) + '%',
        annualChurn: ((1 - Math.pow(1 - monthlyChurn, 12)) * 100).toFixed(1) + '%'
      },
      cohortCurve
    };
  }
  
  /**
   * Revenue growth modeling with S-curve
   */
  modelRevenueGrowth(params: {
    currentRevenue: number;
    marketSize: number;
    years: number;
    growthRate: number;
    decay?: number;
  }): {
    projections: any[];
    cagr: number;
    marketShare: any[];
  } {
    const { currentRevenue, marketSize, years, growthRate, decay = 0.8 } = params;
    
    const projections = [];
    const marketShare = [];
    let revenue = currentRevenue;
    let currentGrowth = growthRate;
    
    for (let year = 0; year <= years; year++) {
      // S-curve: growth slows as market share increases
      const marketPenetration = revenue / marketSize;
      const adjustedGrowth = currentGrowth * (1 - marketPenetration);
      
      projections.push({
        year,
        revenue: Math.round(revenue),
        growth: year === 0 ? 0 : (adjustedGrowth * 100).toFixed(1) + '%',
        yoyIncrease: year === 0 ? 0 : Math.round(revenue - projections[year-1].revenue)
      });
      
      marketShare.push({
        year,
        share: (marketPenetration * 100).toFixed(2) + '%',
        remaining: ((1 - marketPenetration) * 100).toFixed(2) + '%'
      });
      
      // Apply growth with decay
      revenue = revenue * (1 + adjustedGrowth);
      currentGrowth *= decay; // Growth rate decays over time
    }
    
    // Calculate CAGR
    const cagr = Math.pow(revenue / currentRevenue, 1 / years) - 1;
    
    return {
      projections,
      cagr: (cagr * 100).toFixed(1),
      marketShare
    };
  }
  
  /**
   * Monte Carlo simulation for probability modeling
   */
  runMonteCarloSimulation(params: {
    baseCase: number;
    volatility: number;
    periods: number;
    simulations: number;
  }): {
    percentiles: any;
    distribution: any[];
    statistics: any;
  } {
    const { baseCase, volatility, periods, simulations } = params;
    const results = [];
    
    for (let sim = 0; sim < simulations; sim++) {
      let value = baseCase;
      
      for (let period = 0; period < periods; period++) {
        // Generate random shock (normal distribution)
        const randomShock = this.generateNormalRandom(0, volatility);
        value = value * (1 + randomShock);
      }
      
      results.push(value);
    }
    
    // Sort for percentile calculation
    results.sort((a, b) => a - b);
    
    // Calculate percentiles
    const percentiles = {
      p5: results[Math.floor(simulations * 0.05)],
      p25: results[Math.floor(simulations * 0.25)],
      p50: results[Math.floor(simulations * 0.50)],
      p75: results[Math.floor(simulations * 0.75)],
      p95: results[Math.floor(simulations * 0.95)]
    };
    
    // Create distribution buckets
    const min = Math.min(...results);
    const max = Math.max(...results);
    const bucketSize = (max - min) / 20;
    const distribution = [];
    
    for (let i = 0; i < 20; i++) {
      const bucketMin = min + i * bucketSize;
      const bucketMax = bucketMin + bucketSize;
      const count = results.filter(r => r >= bucketMin && r < bucketMax).length;
      
      distribution.push({
        range: `${Math.round(bucketMin)}-${Math.round(bucketMax)}`,
        count,
        probability: (count / simulations * 100).toFixed(1) + '%'
      });
    }
    
    // Statistics
    const mean = results.reduce((a, b) => a + b, 0) / simulations;
    const variance = results.reduce((sum, r) => sum + Math.pow(r - mean, 2), 0) / simulations;
    const stdDev = Math.sqrt(variance);
    
    return {
      percentiles,
      distribution,
      statistics: {
        mean: Math.round(mean),
        median: percentiles.p50,
        stdDev: Math.round(stdDev),
        min: Math.round(min),
        max: Math.round(max),
        confidenceInterval95: `${Math.round(percentiles.p5)} - ${Math.round(percentiles.p95)}`
      }
    };
  }
  
  /**
   * Option pricing using Black-Scholes
   */
  calculateOptionValue(params: {
    currentPrice: number;
    strikePrice: number;
    timeToExpiry: number; // in years
    volatility: number;
    riskFreeRate: number;
  }): {
    callValue: number;
    putValue: number;
    greeks: any;
  } {
    const { currentPrice, strikePrice, timeToExpiry, volatility, riskFreeRate } = params;
    
    // Black-Scholes formula components
    const d1 = (Math.log(currentPrice / strikePrice) + 
               (riskFreeRate + 0.5 * volatility * volatility) * timeToExpiry) /
               (volatility * Math.sqrt(timeToExpiry));
    
    const d2 = d1 - volatility * Math.sqrt(timeToExpiry);
    
    // Cumulative normal distribution
    const N = (x: number) => {
      const a1 = 0.254829592;
      const a2 = -0.284496736;
      const a3 = 1.421413741;
      const a4 = -1.453152027;
      const a5 = 1.061405429;
      const p = 0.3275911;
      
      const sign = x < 0 ? -1 : 1;
      x = Math.abs(x) / Math.sqrt(2.0);
      
      const t = 1.0 / (1.0 + p * x);
      const y = 1.0 - (((((a5 * t + a4) * t) + a3) * t + a2) * t + a1) * t * Math.exp(-x * x);
      
      return 0.5 * (1.0 + sign * y);
    };
    
    // Calculate option values
    const callValue = currentPrice * N(d1) - strikePrice * Math.exp(-riskFreeRate * timeToExpiry) * N(d2);
    const putValue = strikePrice * Math.exp(-riskFreeRate * timeToExpiry) * N(-d2) - currentPrice * N(-d1);
    
    // Calculate Greeks
    const greeks = {
      delta: {
        call: N(d1),
        put: N(d1) - 1
      },
      gamma: Math.exp(-d1 * d1 / 2) / (Math.sqrt(2 * Math.PI) * currentPrice * volatility * Math.sqrt(timeToExpiry)),
      theta: {
        call: -(currentPrice * Math.exp(-d1 * d1 / 2) * volatility) / (2 * Math.sqrt(2 * Math.PI * timeToExpiry)) - 
              riskFreeRate * strikePrice * Math.exp(-riskFreeRate * timeToExpiry) * N(d2),
        put: -(currentPrice * Math.exp(-d1 * d1 / 2) * volatility) / (2 * Math.sqrt(2 * Math.PI * timeToExpiry)) + 
             riskFreeRate * strikePrice * Math.exp(-riskFreeRate * timeToExpiry) * N(-d2)
      },
      vega: currentPrice * Math.sqrt(timeToExpiry) * Math.exp(-d1 * d1 / 2) / Math.sqrt(2 * Math.PI),
      rho: {
        call: strikePrice * timeToExpiry * Math.exp(-riskFreeRate * timeToExpiry) * N(d2),
        put: -strikePrice * timeToExpiry * Math.exp(-riskFreeRate * timeToExpiry) * N(-d2)
      }
    };
    
    return {
      callValue: Math.round(callValue * 100) / 100,
      putValue: Math.round(putValue * 100) / 100,
      greeks
    };
  }
  
  /**
   * Helper: Generate normal random variable (Box-Muller)
   */
  private generateNormalRandom(mean: number, stdDev: number): number {
    let u = 0, v = 0;
    while (u === 0) u = Math.random(); // Converting [0,1) to (0,1)
    while (v === 0) v = Math.random();
    const normal = Math.sqrt(-2.0 * Math.log(u)) * Math.cos(2.0 * Math.PI * v);
    return mean + stdDev * normal;
  }
  
  /**
   * Validate calculation accuracy
   */
  validateCalculation(
    formula: string,
    inputs: Record<string, number>,
    expectedResult: number,
    tolerance: number = 0.01
  ): {
    valid: boolean;
    calculated: number;
    expected: number;
    error: number;
    errorPercent: string;
  } {
    try {
      const calculated = math.evaluate(formula, inputs);
      const error = Math.abs(calculated - expectedResult);
      const errorPercent = (error / expectedResult * 100).toFixed(2);
      
      return {
        valid: error <= tolerance * expectedResult,
        calculated,
        expected: expectedResult,
        error,
        errorPercent: errorPercent + '%'
      };
    } catch (e) {
      return {
        valid: false,
        calculated: 0,
        expected: expectedResult,
        error: expectedResult,
        errorPercent: '100%'
      };
    }
  }
}

export const mathEngine = new AgentMathEngine();