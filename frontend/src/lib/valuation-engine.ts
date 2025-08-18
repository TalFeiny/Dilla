import { createClient } from '@supabase/supabase-js';

const supabase = createClient(
  process.env.NEXT_PUBLIC_SUPABASE_URL!,
  process.env.SUPABASE_SERVICE_ROLE_KEY!
);

export interface ValuationRequest {
  company_name: string;
  stage: 'seed' | 'series_a' | 'series_b' | 'series_c' | 'growth' | 'late' | 'public';
  revenue?: number;
  growth_rate?: number;
  last_round_valuation?: number;
  last_round_date?: string;
  total_raised?: number;
  preferred_shares_outstanding?: number;
  common_shares_outstanding?: number;
  liquidation_preferences?: any[];
  method?: 'auto' | 'pwerm' | 'comparables' | 'dcf' | 'opm' | 'waterfall';
}

export interface ValuationResult {
  method_used: string;
  fair_value: number;
  common_stock_value?: number;
  preferred_value?: number;
  dlom_discount?: number;
  assumptions: any;
  scenarios?: PWERMScenario[];
  comparables?: ComparableCompany[];
  waterfall?: WaterfallTier[];
  confidence: number;
  explanation: string;
}

interface PWERMScenario {
  scenario: string;
  probability: number;
  exit_value: number;
  time_to_exit: number;
  present_value: number;
}

interface ComparableCompany {
  name: string;
  revenue_multiple: number;
  growth_rate: number;
  similarity_score: number;
}

interface WaterfallTier {
  tier: number;
  description: string;
  amount: number;
  participants: string[];
}

export class ValuationEngine {
  
  /**
   * Main valuation method - automatically selects appropriate method based on stage
   */
  async calculateValuation(request: ValuationRequest): Promise<ValuationResult> {
    // Auto-select method based on stage if not specified
    const method = request.method === 'auto' ? this.selectMethod(request) : request.method;
    
    switch (method) {
      case 'pwerm':
        return await this.calculatePWERM(request);
      case 'comparables':
        return await this.calculateComparables(request);
      case 'dcf':
        return await this.calculateDCF(request);
      case 'opm':
        return await this.calculateOPM(request);
      case 'waterfall':
        return await this.calculateWaterfall(request);
      default:
        return await this.calculatePWERM(request); // Default to PWERM for startups
    }
  }
  
  /**
   * Select appropriate valuation method based on company stage
   */
  private selectMethod(request: ValuationRequest): string {
    const { stage, revenue } = request;
    
    // Early stage (Seed, Series A) - use PWERM
    if (stage === 'seed' || stage === 'series_a') {
      return 'pwerm';
    }
    
    // Growth stage (Series B/C) - use Comparables with DLOM
    if (stage === 'series_b' || stage === 'series_c') {
      return 'comparables';
    }
    
    // Late stage with significant revenue - use DCF
    if ((stage === 'growth' || stage === 'late') && revenue && revenue > 50000000) {
      return 'dcf';
    }
    
    // Default to comparables for everything else
    return 'comparables';
  }
  
  /**
   * PWERM - Probability Weighted Expected Return Method
   * For early-stage companies with multiple exit scenarios
   */
  private async calculatePWERM(request: ValuationRequest): Promise<ValuationResult> {
    const { company_name, revenue = 5000000, growth_rate = 1.0, last_round_valuation } = request;
    
    // Define exit scenarios
    const scenarios: PWERMScenario[] = [
      {
        scenario: 'IPO',
        probability: 0.10,
        exit_value: revenue * 15 * Math.pow(1 + growth_rate, 5), // 15x revenue in 5 years
        time_to_exit: 5,
        present_value: 0
      },
      {
        scenario: 'Strategic Acquisition',
        probability: 0.35,
        exit_value: revenue * 8 * Math.pow(1 + growth_rate, 3), // 8x revenue in 3 years
        time_to_exit: 3,
        present_value: 0
      },
      {
        scenario: 'Financial Acquisition',
        probability: 0.25,
        exit_value: revenue * 5 * Math.pow(1 + growth_rate, 4), // 5x revenue in 4 years
        time_to_exit: 4,
        present_value: 0
      },
      {
        scenario: 'Modest Exit',
        probability: 0.20,
        exit_value: revenue * 3 * Math.pow(1 + growth_rate, 2), // 3x revenue in 2 years
        time_to_exit: 2,
        present_value: 0
      },
      {
        scenario: 'Dissolution',
        probability: 0.10,
        exit_value: 0,
        time_to_exit: 2,
        present_value: 0
      }
    ];
    
    // Calculate present value for each scenario
    const discount_rate = 0.35; // 35% for early stage
    let total_value = 0;
    
    scenarios.forEach(scenario => {
      scenario.present_value = scenario.exit_value / Math.pow(1 + discount_rate, scenario.time_to_exit);
      total_value += scenario.present_value * scenario.probability;
    });
    
    // Apply minority discount for common stock
    const common_stock_discount = 0.30; // 30% minority discount
    const common_stock_value = total_value * (1 - common_stock_discount);
    
    return {
      method_used: 'PWERM',
      fair_value: total_value,
      common_stock_value,
      preferred_value: total_value,
      assumptions: {
        discount_rate: discount_rate * 100 + '%',
        minority_discount: common_stock_discount * 100 + '%',
        base_revenue: revenue,
        growth_rate: growth_rate * 100 + '%'
      },
      scenarios,
      confidence: 0.75,
      explanation: `PWERM valuation based on 5 probability-weighted exit scenarios. Most likely outcome is strategic acquisition (35% probability) at ${(scenarios[1].exit_value / 1000000).toFixed(1)}M in ${scenarios[1].time_to_exit} years.`
    };
  }
  
  /**
   * Comparables Method with DLOM
   * For growth-stage companies with comparable public companies
   */
  private async calculateComparables(request: ValuationRequest): Promise<ValuationResult> {
    const { company_name, revenue = 10000000, growth_rate = 0.5, stage } = request;
    
    // Get comparable companies from database
    const { data: comparables } = await supabase
      .from('companies')
      .select('name, current_arr_usd, current_valuation_usd')
      .gte('current_arr_usd', revenue * 0.5)
      .lte('current_arr_usd', revenue * 2)
      .limit(10);
    
    // Calculate median revenue multiple
    let revenue_multiples: number[] = [];
    const comparable_companies: ComparableCompany[] = [];
    
    if (comparables && comparables.length > 0) {
      comparables.forEach(comp => {
        if (comp.current_arr_usd && comp.current_valuation_usd) {
          const multiple = comp.current_valuation_usd / comp.current_arr_usd;
          revenue_multiples.push(multiple);
          comparable_companies.push({
            name: comp.name,
            revenue_multiple: multiple,
            growth_rate: 0.3, // Assumed
            similarity_score: 0.7
          });
        }
      });
    }
    
    // If no comparables, use stage-based multiples
    if (revenue_multiples.length === 0) {
      const stageMultiples: Record<string, number> = {
        'seed': 10,
        'series_a': 8,
        'series_b': 6,
        'series_c': 5,
        'growth': 4,
        'late': 3
      };
      revenue_multiples = [stageMultiples[stage || 'series_b'] || 5];
    }
    
    // Calculate median multiple
    const median_multiple = revenue_multiples.sort((a, b) => a - b)[Math.floor(revenue_multiples.length / 2)];
    
    // Adjust for growth rate
    const growth_adjusted_multiple = median_multiple * (1 + (growth_rate - 0.3) * 2); // Adjust based on growth vs 30% baseline
    
    // Calculate enterprise value
    const enterprise_value = revenue * growth_adjusted_multiple;
    
    // Apply DLOM (Discount for Lack of Marketability)
    const dlom = this.calculateDLOM(stage || 'series_b');
    const fair_value = enterprise_value * (1 - dlom);
    
    // Common stock value (additional discount for subordination)
    const common_stock_value = fair_value * 0.7; // 30% discount for common vs preferred
    
    return {
      method_used: 'Comparables with DLOM',
      fair_value,
      common_stock_value,
      preferred_value: fair_value,
      dlom_discount: dlom,
      assumptions: {
        median_revenue_multiple: median_multiple.toFixed(1) + 'x',
        growth_adjusted_multiple: growth_adjusted_multiple.toFixed(1) + 'x',
        dlom_applied: (dlom * 100).toFixed(0) + '%',
        comparable_companies_count: comparable_companies.length
      },
      comparables: comparable_companies.slice(0, 5),
      confidence: comparable_companies.length > 3 ? 0.8 : 0.6,
      explanation: `Valuation based on ${comparable_companies.length} comparable companies with median revenue multiple of ${median_multiple.toFixed(1)}x, adjusted for ${(growth_rate * 100).toFixed(0)}% growth rate. DLOM of ${(dlom * 100).toFixed(0)}% applied for lack of marketability.`
    };
  }
  
  /**
   * Calculate DLOM based on stage and time to liquidity
   */
  private calculateDLOM(stage: string): number {
    const dlomByStage: Record<string, number> = {
      'seed': 0.45,      // 45% discount
      'series_a': 0.35,   // 35% discount
      'series_b': 0.25,   // 25% discount
      'series_c': 0.20,   // 20% discount
      'growth': 0.15,     // 15% discount
      'late': 0.10,       // 10% discount
      'public': 0.0       // No discount
    };
    
    return dlomByStage[stage] || 0.25;
  }
  
  /**
   * DCF - Discounted Cash Flow
   * For mature companies with predictable cash flows
   */
  private async calculateDCF(request: ValuationRequest): Promise<ValuationResult> {
    const { revenue = 50000000, growth_rate = 0.2 } = request;
    
    // DCF assumptions
    const years = 5;
    const terminal_growth = 0.03; // 3% perpetual growth
    const wacc = 0.12; // 12% WACC for mature companies
    const fcf_margin_initial = 0.15; // 15% FCF margin
    const fcf_margin_terminal = 0.25; // 25% FCF margin at maturity
    
    let dcf_value = 0;
    let projected_revenue = revenue;
    let fcf_margin = fcf_margin_initial;
    
    // Project cash flows
    for (let year = 1; year <= years; year++) {
      projected_revenue *= (1 + growth_rate * Math.pow(0.9, year - 1)); // Declining growth
      fcf_margin += (fcf_margin_terminal - fcf_margin_initial) / years; // Improving margins
      const fcf = projected_revenue * fcf_margin;
      const pv = fcf / Math.pow(1 + wacc, year);
      dcf_value += pv;
    }
    
    // Terminal value
    const terminal_fcf = projected_revenue * fcf_margin_terminal;
    const terminal_value = terminal_fcf * (1 + terminal_growth) / (wacc - terminal_growth);
    const pv_terminal = terminal_value / Math.pow(1 + wacc, years);
    dcf_value += pv_terminal;
    
    return {
      method_used: 'DCF',
      fair_value: dcf_value,
      assumptions: {
        projection_period: years + ' years',
        wacc: (wacc * 100) + '%',
        terminal_growth: (terminal_growth * 100) + '%',
        fcf_margin_range: `${(fcf_margin_initial * 100)}% to ${(fcf_margin_terminal * 100)}%`,
        initial_revenue: revenue
      },
      confidence: 0.85,
      explanation: `DCF valuation with ${years}-year projection period, ${(wacc * 100)}% WACC, and ${(terminal_growth * 100)}% terminal growth rate. FCF margins expanding from ${(fcf_margin_initial * 100)}% to ${(fcf_margin_terminal * 100)}%.`
    };
  }
  
  /**
   * OPM - Option Pricing Model (Black-Scholes)
   * For valuing common stock in complex capital structures
   */
  private async calculateOPM(request: ValuationRequest): Promise<ValuationResult> {
    const { 
      last_round_valuation = 100000000,
      preferred_shares_outstanding = 10000000,
      common_shares_outstanding = 5000000
    } = request;
    
    // Black-Scholes parameters
    const total_shares = preferred_shares_outstanding + common_shares_outstanding;
    const share_price = last_round_valuation / total_shares;
    const strike_price = share_price * 1.5; // Liquidation preference
    const time_to_exit = 3; // years
    const volatility = 0.6; // 60% volatility for startups
    const risk_free_rate = 0.04; // 4% risk-free rate
    
    // Simplified Black-Scholes calculation
    const d1 = (Math.log(share_price / strike_price) + (risk_free_rate + volatility * volatility / 2) * time_to_exit) / (volatility * Math.sqrt(time_to_exit));
    const d2 = d1 - volatility * Math.sqrt(time_to_exit);
    
    // Normal distribution approximation
    const N = (x: number) => {
      const t = 1 / (1 + 0.2316419 * Math.abs(x));
      const d = 0.3989423 * Math.exp(-x * x / 2);
      const prob = d * t * (0.3193815 + t * (-0.3565638 + t * (1.781478 + t * (-1.821256 + t * 1.330274))));
      return x > 0 ? 1 - prob : prob;
    };
    
    const call_value = share_price * N(d1) - strike_price * Math.exp(-risk_free_rate * time_to_exit) * N(d2);
    const common_stock_value = call_value * common_shares_outstanding;
    
    return {
      method_used: 'OPM (Black-Scholes)',
      fair_value: last_round_valuation,
      common_stock_value,
      preferred_value: share_price * preferred_shares_outstanding,
      assumptions: {
        volatility: (volatility * 100) + '%',
        time_to_exit: time_to_exit + ' years',
        risk_free_rate: (risk_free_rate * 100) + '%',
        strike_price: '$' + strike_price.toFixed(2)
      },
      confidence: 0.7,
      explanation: `Option Pricing Model valuation for common stock. Based on ${(volatility * 100)}% volatility and ${time_to_exit}-year expected time to exit. Common stock valued as call option on enterprise value.`
    };
  }
  
  /**
   * Waterfall Analysis
   * For understanding distribution in liquidation events
   */
  private async calculateWaterfall(request: ValuationRequest): Promise<ValuationResult> {
    const { 
      last_round_valuation = 100000000,
      liquidation_preferences = [],
      total_raised = 30000000
    } = request;
    
    // Build waterfall tiers
    const waterfall: WaterfallTier[] = [
      {
        tier: 1,
        description: 'Senior Liquidation Preferences',
        amount: total_raised * 1.0, // 1x liquidation preference
        participants: ['Series C', 'Series B']
      },
      {
        tier: 2,
        description: 'Participating Preferred Catch-up',
        amount: total_raised * 0.2, // 20% catch-up
        participants: ['Series A']
      },
      {
        tier: 3,
        description: 'Common Stock Participation',
        amount: Math.max(0, last_round_valuation - total_raised * 1.2),
        participants: ['Common Stockholders', 'Option Holders']
      }
    ];
    
    // Calculate common stock value based on waterfall
    const total_to_common = waterfall.find(w => w.tier === 3)?.amount || 0;
    const common_percentage = 0.3; // Assume common owns 30%
    const common_stock_value = total_to_common * common_percentage;
    
    return {
      method_used: 'Waterfall Analysis',
      fair_value: last_round_valuation,
      common_stock_value,
      preferred_value: last_round_valuation - common_stock_value,
      waterfall,
      assumptions: {
        liquidation_preferences: '1x non-participating',
        common_ownership: (common_percentage * 100) + '%',
        exit_value: last_round_valuation
      },
      confidence: 0.8,
      explanation: `Waterfall analysis showing distribution across ${waterfall.length} tiers. Common stock receives ${(common_percentage * 100)}% of residual value after ${(total_raised / 1000000).toFixed(1)}M in liquidation preferences.`
    };
  }
}

// Export singleton instance
export const valuationEngine = new ValuationEngine();