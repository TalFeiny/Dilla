/**
 * Comprehensive Valuation Service
 * Implements multiple valuation methodologies for portfolio companies
 */

import { supabaseService } from './supabase';

export interface CompanyMetrics {
  id: string;
  name: string;
  sector?: string;
  current_arr_usd?: number;
  growth_rate?: number;
  gross_margin?: number;
  ebitda_margin?: number;
  total_invested_usd?: number;
  ownership_percentage?: number;
  first_investment_date?: string;
  funding_stage?: string;
  cash_burn_rate?: number;
  runway_months?: number;
}

export interface ValuationResult {
  method: string;
  value: number;
  confidence: number;
  assumptions: Record<string, any>;
}

export interface ComprehensiveValuation {
  companyId: string;
  companyName: string;
  valuations: ValuationResult[];
  weightedValue: number;
  expectedValue: number;
  confidenceInterval: {
    low: number;
    median: number;
    high: number;
  };
}

// Public SaaS trading multiples (as of 2024)
const SAAS_MULTIPLES = {
  revenue: {
    high_growth: 8.5,  // >40% growth
    mid_growth: 5.5,   // 20-40% growth
    low_growth: 3.0,   // <20% growth
  },
  ebitda: {
    profitable: 25.0,
    breakeven: 15.0,
    unprofitable: 0,
  },
  arr: {
    enterprise: 7.0,
    mid_market: 5.0,
    smb: 3.0,
  }
};

// DLOM (Discount for Lack of Marketability)
const DLOM_RATE = 0.30; // 30% discount for private companies

// Risk-free rate and market risk premium for CAPM
const RISK_FREE_RATE = 0.045; // 4.5% (US 10-year treasury)
const MARKET_RISK_PREMIUM = 0.08; // 8% equity risk premium

export class ValuationService {
  /**
   * 1. Comparables Method with DLOM
   */
  static async calculateComparablesValuation(
    company: CompanyMetrics
  ): Promise<ValuationResult> {
    const arr = company.current_arr_usd || 0;
    const growthRate = company.growth_rate || 0.2; // Default 20% growth
    
    // Determine growth tier
    let revenueMultiple = SAAS_MULTIPLES.revenue.low_growth;
    if (growthRate > 0.4) {
      revenueMultiple = SAAS_MULTIPLES.revenue.high_growth;
    } else if (growthRate > 0.2) {
      revenueMultiple = SAAS_MULTIPLES.revenue.mid_growth;
    }
    
    // Determine market segment
    let arrMultiple = SAAS_MULTIPLES.arr.smb;
    if (arr > 10_000_000) {
      arrMultiple = SAAS_MULTIPLES.arr.enterprise;
    } else if (arr > 1_000_000) {
      arrMultiple = SAAS_MULTIPLES.arr.mid_market;
    }
    
    // Use the higher of revenue or ARR multiple
    const baseMultiple = Math.max(revenueMultiple, arrMultiple);
    
    // Calculate valuation with DLOM
    const publicComparableValue = arr * baseMultiple;
    const privateValue = publicComparableValue * (1 - DLOM_RATE);
    
    return {
      method: 'Comparables with DLOM',
      value: privateValue,
      confidence: 0.75,
      assumptions: {
        arr,
        growthRate,
        baseMultiple,
        dlomRate: DLOM_RATE,
        publicValue: publicComparableValue
      }
    };
  }

  /**
   * 2. DCF (Discounted Cash Flow) Method
   */
  static async calculateDCFValuation(
    company: CompanyMetrics
  ): Promise<ValuationResult> {
    const arr = company.current_arr_usd || 0;
    const growthRate = company.growth_rate || 0.3;
    const grossMargin = company.gross_margin || 0.7;
    const ebitdaMargin = company.ebitda_margin || -0.1; // Default negative for growth companies
    
    // Project 5 years of cash flows
    const projectionYears = 5;
    const terminalGrowthRate = 0.03; // 3% perpetual growth
    const discountRate = 0.15; // 15% for early-stage companies
    
    let cashFlows: number[] = [];
    let currentRevenue = arr;
    
    for (let year = 1; year <= projectionYears; year++) {
      // Decay growth rate over time
      const yearGrowthRate = growthRate * Math.pow(0.85, year - 1);
      currentRevenue *= (1 + yearGrowthRate);
      
      // Improve margins over time
      const yearEbitdaMargin = Math.min(
        0.25, // Cap at 25% EBITDA margin
        ebitdaMargin + (0.05 * year) // Improve 5% per year
      );
      
      const fcf = currentRevenue * Math.max(0, yearEbitdaMargin);
      cashFlows.push(fcf);
    }
    
    // Calculate terminal value
    const terminalCashFlow = cashFlows[cashFlows.length - 1] * (1 + terminalGrowthRate);
    const terminalValue = terminalCashFlow / (discountRate - terminalGrowthRate);
    
    // Discount all cash flows to present value
    let dcfValue = 0;
    cashFlows.forEach((cf, index) => {
      dcfValue += cf / Math.pow(1 + discountRate, index + 1);
    });
    
    // Add discounted terminal value
    dcfValue += terminalValue / Math.pow(1 + discountRate, projectionYears);
    
    return {
      method: 'DCF',
      value: Math.max(0, dcfValue),
      confidence: 0.65,
      assumptions: {
        arr,
        growthRate,
        discountRate,
        terminalGrowthRate,
        projectedCashFlows: cashFlows,
        terminalValue
      }
    };
  }

  /**
   * 3. CAPM (Capital Asset Pricing Model) Valuation
   */
  static async calculateCAPMValuation(
    company: CompanyMetrics
  ): Promise<ValuationResult> {
    const arr = company.current_arr_usd || 0;
    const growthRate = company.growth_rate || 0.3;
    
    // Estimate beta based on company stage and sector
    let beta = 1.5; // Default for growth tech
    if (company.sector === 'Enterprise Software') {
      beta = 1.3;
    } else if (company.sector === 'Consumer') {
      beta = 1.8;
    } else if (company.sector === 'Healthcare') {
      beta = 1.2;
    }
    
    // Add illiquidity premium for private companies
    const illiquidityPremium = 0.05; // 5%
    
    // Calculate required return using CAPM
    const requiredReturn = RISK_FREE_RATE + (beta * MARKET_RISK_PREMIUM) + illiquidityPremium;
    
    // Simple perpetuity model with growth
    const nextYearCashFlow = arr * 0.15; // Assume 15% FCF margin at maturity
    const value = nextYearCashFlow / (requiredReturn - growthRate);
    
    return {
      method: 'CAPM',
      value: Math.max(0, value),
      confidence: 0.60,
      assumptions: {
        arr,
        beta,
        requiredReturn,
        riskFreeRate: RISK_FREE_RATE,
        marketRiskPremium: MARKET_RISK_PREMIUM,
        illiquidityPremium
      }
    };
  }

  /**
   * 4. IPEV (International Private Equity and Venture Capital) Methods
   */
  static async calculateIPEVValuation(
    company: CompanyMetrics
  ): Promise<ValuationResult[]> {
    const results: ValuationResult[] = [];
    
    // 4a. Price of Recent Investment Method
    if (company.total_invested_usd && company.ownership_percentage) {
      const impliedValuation = (company.total_invested_usd / company.ownership_percentage) * 100;
      
      // Adjust for time since investment
      let timeAdjustment = 1.0;
      if (company.first_investment_date) {
        const monthsSinceInvestment = 
          (Date.now() - new Date(company.first_investment_date).getTime()) / (1000 * 60 * 60 * 24 * 30);
        
        // Assume 20% annual appreciation for successful companies
        timeAdjustment = Math.pow(1.20, monthsSinceInvestment / 12);
      }
      
      results.push({
        method: 'IPEV - Recent Investment',
        value: impliedValuation * timeAdjustment,
        confidence: 0.80,
        assumptions: {
          totalInvested: company.total_invested_usd,
          ownership: company.ownership_percentage,
          timeAdjustment
        }
      });
    }
    
    // 4b. Milestone-Based Valuation
    const arr = company.current_arr_usd || 0;
    let milestoneMultiple = 3.0; // Base multiple
    
    // Adjust based on ARR milestones
    if (arr > 10_000_000) {
      milestoneMultiple = 7.0; // Series B+ territory
    } else if (arr > 5_000_000) {
      milestoneMultiple = 5.5; // Series A+ territory
    } else if (arr > 1_000_000) {
      milestoneMultiple = 4.5; // Series A territory
    }
    
    results.push({
      method: 'IPEV - Milestone',
      value: arr * milestoneMultiple,
      confidence: 0.70,
      assumptions: {
        arr,
        milestoneMultiple,
        stage: arr > 10_000_000 ? 'Series B+' : arr > 1_000_000 ? 'Series A' : 'Seed'
      }
    });
    
    return results;
  }

  /**
   * 5. PWERM Integration for Expected Value
   */
  static async calculatePWERMValuation(
    company: CompanyMetrics
  ): Promise<ValuationResult> {
    // Define probability-weighted scenarios
    const scenarios = [
      { name: 'Bankruptcy', probability: 0.15, multiple: 0 },
      { name: 'Acquihire', probability: 0.20, multiple: 0.5 },
      { name: 'Modest Exit', probability: 0.30, multiple: 2.0 },
      { name: 'Good Exit', probability: 0.25, multiple: 5.0 },
      { name: 'Great Exit', probability: 0.08, multiple: 10.0 },
      { name: 'Unicorn', probability: 0.02, multiple: 50.0 }
    ];
    
    const baseValue = company.current_arr_usd || 0;
    
    // Adjust probabilities based on company metrics
    let adjustedScenarios = [...scenarios];
    
    // Better metrics increase upside probability
    if (company.growth_rate && company.growth_rate > 0.5) {
      adjustedScenarios[3].probability += 0.05; // Good Exit
      adjustedScenarios[4].probability += 0.03; // Great Exit
      adjustedScenarios[0].probability -= 0.08; // Less bankruptcy
    }
    
    // Calculate expected value
    const expectedValue = adjustedScenarios.reduce((sum, scenario) => {
      return sum + (scenario.probability * scenario.multiple * baseValue);
    }, 0);
    
    return {
      method: 'PWERM',
      value: expectedValue,
      confidence: 0.85,
      assumptions: {
        baseValue,
        scenarios: adjustedScenarios,
        growthRate: company.growth_rate
      }
    };
  }

  /**
   * Main valuation method that combines all approaches
   */
  static async getComprehensiveValuation(
    company: CompanyMetrics
  ): Promise<ComprehensiveValuation> {
    const valuations: ValuationResult[] = [];
    
    // Run all valuation methods in parallel
    const [comparables, dcf, capm, pwerm] = await Promise.all([
      this.calculateComparablesValuation(company),
      this.calculateDCFValuation(company),
      this.calculateCAPMValuation(company),
      this.calculatePWERMValuation(company)
    ]);
    
    valuations.push(comparables, dcf, capm, pwerm);
    
    // Add IPEV methods
    const ipevResults = await this.calculateIPEVValuation(company);
    valuations.push(...ipevResults);
    
    // Calculate weighted average based on confidence
    const totalConfidence = valuations.reduce((sum, v) => sum + v.confidence, 0);
    const weightedValue = valuations.reduce((sum, v) => {
      return sum + (v.value * v.confidence / totalConfidence);
    }, 0);
    
    // Use PWERM as the expected value (it's already probability-weighted)
    const expectedValue = pwerm.value;
    
    // Calculate confidence intervals
    const values = valuations.map(v => v.value).sort((a, b) => a - b);
    const confidenceInterval = {
      low: values[Math.floor(values.length * 0.25)],
      median: values[Math.floor(values.length * 0.5)],
      high: values[Math.floor(values.length * 0.75)]
    };
    
    return {
      companyId: company.id,
      companyName: company.name,
      valuations,
      weightedValue,
      expectedValue,
      confidenceInterval
    };
  }

  /**
   * Batch valuation for portfolio companies
   */
  static async getPortfolioValuations(
    companies: CompanyMetrics[]
  ): Promise<Map<string, ComprehensiveValuation>> {
    const valuationMap = new Map<string, ComprehensiveValuation>();
    
    // Process in batches to avoid overwhelming the system
    const batchSize = 10;
    for (let i = 0; i < companies.length; i += batchSize) {
      const batch = companies.slice(i, i + batchSize);
      const batchResults = await Promise.all(
        batch.map(company => this.getComprehensiveValuation(company))
      );
      
      batchResults.forEach(result => {
        valuationMap.set(result.companyId, result);
      });
    }
    
    return valuationMap;
  }
}