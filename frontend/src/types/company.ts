export interface Company {
    id: string;
    organization_id?: string;
    fund_id?: string;
    name: string;
    website?: string;
    sector?: string;
    revenue_model?: string;
    kpi_framework?: string;
    current_arr_usd?: number;
    current_mrr_usd?: number;
    revenue_growth_monthly_pct?: number;
    revenue_growth_annual_pct?: number;
    burn_rate_monthly_usd?: number;
    runway_months?: number;
    current_option_pool_bps?: number;
    location?: Record<string, any>;
    status: string;
    created_at: string;
    updated_at: string;
    round_size?: Record<string, any>;
    amount_raised?: Record<string, any>;
    quarter_raised?: any;
    funnel_status: string;
    thesis_match_score?: number;
    recommendation_reason?: Record<string, any>;
    added_to_watchlist_at?: string;
    watchlist_priority?: string;
    term_sheet_sent_at?: string;
    term_sheet_status?: string;
    term_sheet_expiry_date?: string;
    first_investment_date?: string;
    latest_investment_date?: string;
    total_invested_usd?: number;
    ownership_percentage?: number;
    exit_date?: string;
    exit_type?: string;
    exit_value_usd?: number;
    exit_multiple?: number;
    customer_segment_enterprise_pct?: number;
    customer_segment_midmarket_pct?: number;
    customer_segment_sme_pct?: number;
    latest_update?: string;
    latest_update_date?: string;
    update_frequency_days?: number;
    has_pwerm_model?: boolean;
    latest_pwerm_run_at?: string;
    pwerm_scenarios_count?: number;
    gross_margin?: number;
    category?: string;
    ai_first?: boolean;
    business_model?: string;
    // Portfolio report fields
    cash_in_bank_usd?: number;
    investment_lead?: string;
    last_contacted_date?: string;
    // Field update timestamps
    cash_updated_at?: string;
    burn_rate_updated_at?: string;
    runway_updated_at?: string;
    revenue_updated_at?: string;
    gross_margin_updated_at?: string;
    // Recent migration fields
    current_valuation_usd?: number;
    extra_data?: Record<string, any>;
    currency_mix?: Record<string, number>;
  }

export interface PortfolioCompany {
  id: string;
  company_id: string;
  company_name: string;
  investment_date: string;
  investment_amount_usd: number;
  ownership_percentage: number;
  current_valuation_usd: number;
  status: 'active' | 'exited' | 'written_off';
  exit_date?: string;
  exit_value_usd?: number;
  exit_multiple?: number;
  notes?: string;
  created_at: string;
  updated_at: string;
}

export interface PWERMScenario {
  scenario_name: string;
  probability: number;
  exit_value_usd: number;
  exit_multiple: number;
  exit_year: number;
  exit_type: string;
  assumptions: Record<string, any>;
  description: string;
  waterfall_adjusted_value: number;
  dilution_adjusted_ownership: number;
}

export interface WaterfallAssumptions {
  preferred_return_rate: number;
  catch_up_percentage: number;
  carried_interest_rate: number;
  management_fee_rate: number;
  hurdle_rate: number;
  gp_commitment_percentage: number;
}

export interface OptionsDilutionAssumptions {
  current_esop_percentage: number;
  future_esop_grants_per_year: number;
  vesting_schedule_years: number;
  cliff_percentage: number;
  anti_dilution_protection: boolean;
  future_funding_rounds: number;
  dilution_per_round: number;
}

export interface PWERMResult {
  company_id: string;
  company_name: string;
  analysis_date: string;
  total_invested_usd: number;
  ownership_percentage: number;
  scenarios: PWERMScenario[];
  expected_return_usd: number;
  expected_multiple: number;
  expected_irr: number;
  risk_adjusted_return: number;
  confidence_interval_95: [number, number];
  scenario_count: number;
  analysis_metadata: Record<string, any>;
  waterfall_assumptions: WaterfallAssumptions;
  dilution_assumptions: OptionsDilutionAssumptions;
  waterfall_adjusted_returns?: Record<string, number>;
  dilution_adjusted_ownership: number;
}

export interface PWERMPlaygroundConfig {
  company_id: string;
  base_assumptions: {
    graduation_rate: number;
    arr_growth_rate: number;
    exit_multiple_range: [number, number];
    dilution_per_round: number;
    time_to_exit_years: number;
    sector_multiplier: number;
    market_conditions: 'bull' | 'neutral' | 'bear';
  };
  waterfall_assumptions: WaterfallAssumptions;
  dilution_assumptions: OptionsDilutionAssumptions;
  ai_monitoring?: boolean;
}