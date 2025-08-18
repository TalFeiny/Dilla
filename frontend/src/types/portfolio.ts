export interface PortfolioCompany {
  id: string;
  company_id: string;
  fund_id?: string;
  investment_date: string;
  total_invested_usd: number;
  ownership_percentage: number;
  board_seat: boolean;
  board_observer: boolean;
  investment_stage?: string;
  investment_round?: string;
  valuation_at_investment_usd?: number;
  current_valuation_usd?: number;
  status: 'active' | 'exited' | 'written_off';
  exit_date?: string;
  exit_value_usd?: number;
  exit_type?: string;
  exit_multiple?: number;
  notes?: string;
  created_at: string;
  updated_at: string;
  
  // Joined company data
  company?: {
    id: string;
    name: string;
    sector?: string;
    current_arr_usd?: number;
    status: string;
  };
}

export interface PWERMAnalysis {
  id: string;
  portfolio_company_id: string;
  analysis_date: string;
  analyst_name?: string;
  base_assumptions: PWERMBaseAssumptions;
  scenarios: PWERMScenario[];
  expected_return_usd: number;
  expected_multiple: number;
  expected_irr: number;
  risk_adjusted_return: number;
  confidence_interval_lower: number;
  confidence_interval_upper: number;
  scenario_count: number;
  analysis_metadata: Record<string, any>;
  created_at: string;
}

export interface PWERMBaseAssumptions {
  graduation_rate: number; // Probability of successful graduation to next stage
  arr_growth_rate: number; // Annual ARR growth rate
  exit_multiple_range: [number, number]; // Min/max exit multiples
  dilution_per_round: number; // Expected dilution per funding round
  time_to_exit_years: number; // Expected time to exit
  sector_multiplier: number; // Sector-specific multiplier
  market_conditions: 'bull' | 'bear' | 'neutral';
  ai_monitoring_enabled: boolean;
  custom_assumptions: Record<string, any>;
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
}

export interface InvestmentRound {
  id: string;
  portfolio_company_id: string;
  round_date: string;
  round_type: string;
  amount_invested_usd: number;
  ownership_acquired_percentage: number;
  valuation_usd?: number;
  lead_investor?: string;
  other_investors?: string[];
  notes?: string;
  created_at: string;
}

export interface PortfolioMonitoring {
  id: string;
  portfolio_company_id: string;
  monitoring_date: string;
  current_arr_usd?: number;
  revenue_growth_annual_pct?: number;
  burn_rate_monthly_usd?: number;
  runway_months?: number;
  customer_count?: number;
  employee_count?: number;
  key_metrics: Record<string, any>;
  risk_factors?: string[];
  next_board_meeting?: string;
  notes?: string;
  created_at: string;
}

export interface PortfolioCompanyWithDetails extends PortfolioCompany {
  company: {
    id: string;
    name: string;
    sector?: string;
    current_arr_usd?: number;
    status: string;
  };
  investment_rounds: InvestmentRound[];
  pwerm_analyses: PWERMAnalysis[];
  monitoring_records: PortfolioMonitoring[];
}

export interface CreatePortfolioCompanyRequest {
  company_id: string;
  fund_id?: string;
  investment_date: string;
  total_invested_usd: number;
  ownership_percentage: number;
  board_seat?: boolean;
  board_observer?: boolean;
  investment_stage?: string;
  investment_round?: string;
  valuation_at_investment_usd?: number;
  notes?: string;
}

export interface UpdatePortfolioCompanyRequest {
  fund_id?: string;
  total_invested_usd?: number;
  ownership_percentage?: number;
  board_seat?: boolean;
  board_observer?: boolean;
  investment_stage?: string;
  investment_round?: string;
  valuation_at_investment_usd?: number;
  current_valuation_usd?: number;
  status?: 'active' | 'exited' | 'written_off';
  exit_date?: string;
  exit_value_usd?: number;
  exit_type?: string;
  exit_multiple?: number;
  notes?: string;
}

export interface CreatePWERMAnalysisRequest {
  portfolio_company_id: string;
  analyst_name?: string;
  base_assumptions: PWERMBaseAssumptions;
  scenarios: PWERMScenario[];
}

export interface PWERMPlaygroundConfig {
  company_id: string;
  portfolio_company_id?: string;
  base_assumptions: PWERMBaseAssumptions;
  custom_scenarios?: PWERMScenario[];
  ai_monitoring_config?: {
    enabled: boolean;
    monitoring_frequency: 'weekly' | 'monthly' | 'quarterly';
    alert_thresholds: Record<string, number>;
  };
} 