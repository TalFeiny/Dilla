/**
 * Market Dynamics Context System
 * Real-time understanding of current geopolitical and market trends
 */

export interface MarketContext {
  trend: string;
  category: string;
  impact: 'high' | 'medium' | 'low';
  relevantSectors: string[];
  keyMetrics: string[];
  valuationImpact: number; // Multiplier effect on valuations
  timeframe: string;
}

export const CURRENT_MARKET_DYNAMICS: MarketContext[] = [
  {
    trend: 'Vertical AI Dominance',
    category: 'investment_thesis',
    impact: 'high',
    relevantSectors: ['LegalTech', 'HealthTech', 'FinTech', 'EdTech', 'Real Estate Tech'],
    keyMetrics: ['vertical_market_share', 'domain_expertise', 'data_moat', 'workflow_integration'],
    valuationImpact: 1.8,
    timeframe: '2024-2027'
  },
  {
    trend: 'Megafund Concentration (60% of Capital)',
    category: 'fund_dynamics',
    impact: 'high',
    relevantSectors: ['All'],
    keyMetrics: ['minimum_check_size', 'ownership_target', 'board_seats', 'follow_on_capacity'],
    valuationImpact: 1.4,
    timeframe: '2023-2025'
  },
  {
    trend: 'Defense Tech Renaissance',
    category: 'geopolitical',
    impact: 'high',
    relevantSectors: ['Defense', 'Dual-Use', 'Aerospace', 'Cybersecurity', 'Space Tech'],
    keyMetrics: ['government_contracts', 'dual_use_potential', 'export_restrictions', 'security_clearance'],
    valuationImpact: 2.2,
    timeframe: '2023-2030'
  },
  {
    trend: 'Inflated PE Multiples (Historical Highs)',
    category: 'valuation',
    impact: 'high',
    relevantSectors: ['All'],
    keyMetrics: ['ev_revenue_multiple', 'growth_adjusted_multiple', 'cash_burn_multiple'],
    valuationImpact: 1.3,
    timeframe: '2023-2024'
  },
  {
    trend: 'Vibe Coding & Developer Experience',
    category: 'emerging_category',
    impact: 'medium',
    relevantSectors: ['Developer Tools', 'DevEx', 'AI Coding', 'IDE'],
    keyMetrics: ['developer_nps', 'time_to_first_commit', 'developer_velocity', 'community_size'],
    valuationImpact: 1.6,
    timeframe: '2024-2026'
  },
  {
    trend: 'Climate Tech Capital Surge',
    category: 'thematic',
    impact: 'high',
    relevantSectors: ['Climate Tech', 'Energy', 'Carbon Markets', 'Green Hydrogen'],
    keyMetrics: ['carbon_reduction', 'energy_efficiency', 'regulatory_alignment', 'subsidy_dependence'],
    valuationImpact: 1.7,
    timeframe: '2023-2030'
  },
  {
    trend: 'B2B SaaS Efficiency Focus',
    category: 'operational',
    impact: 'high',
    relevantSectors: ['SaaS', 'Enterprise Software'],
    keyMetrics: ['rule_of_40', 'magic_number', 'ltv_cac', 'net_dollar_retention', 'payback_period'],
    valuationImpact: 0.8,
    timeframe: '2023-2025'
  },
  {
    trend: 'Agent-Based Computing',
    category: 'emerging_category',
    impact: 'high',
    relevantSectors: ['AI Agents', 'Autonomous Systems', 'RPA', 'Workflow Automation'],
    keyMetrics: ['agent_autonomy', 'task_completion_rate', 'human_in_loop_frequency', 'cost_per_task'],
    valuationImpact: 2.3,
    timeframe: '2024-2028'
  },
  {
    trend: 'Biotech/TechBio Convergence',
    category: 'frontier_tech',
    impact: 'medium',
    relevantSectors: ['Biotech', 'Synthetic Biology', 'Drug Discovery', 'Longevity'],
    keyMetrics: ['clinical_pipeline', 'platform_vs_asset', 'data_generation_rate', 'computational_advantage'],
    valuationImpact: 1.9,
    timeframe: '2024-2035'
  },
  {
    trend: 'Infrastructure Software Premium',
    category: 'investment_thesis',
    impact: 'high',
    relevantSectors: ['Infrastructure', 'DevOps', 'Cloud', 'Data Infrastructure'],
    keyMetrics: ['developer_adoption', 'enterprise_penetration', 'open_source_traction', 'cloud_spend_percentage'],
    valuationImpact: 2.1,
    timeframe: '2023-2026'
  },
  {
    trend: 'Sovereign AI & Data Localization',
    category: 'geopolitical',
    impact: 'medium',
    relevantSectors: ['AI Infrastructure', 'Cloud', 'Data Centers'],
    keyMetrics: ['data_sovereignty_compliance', 'local_compute_capacity', 'regulatory_risk', 'government_partnerships'],
    valuationImpact: 1.4,
    timeframe: '2024-2030'
  }
];

export interface MarketIntelligence {
  company: string;
  sector: string;
  relevantTrends: MarketContext[];
  marketTiming: 'early' | 'optimal' | 'late' | 'contrarian';
  adjustedValuation: number;
  keyRisks: string[];
  opportunities: string[];
}

export function analyzeMarketContext(
  company: string,
  sector: string,
  baseValuation: number
): MarketIntelligence {
  // Find relevant trends for this sector
  const relevantTrends = CURRENT_MARKET_DYNAMICS.filter(
    trend => trend.relevantSectors.includes('All') || 
             trend.relevantSectors.some(s => s.toLowerCase() === sector.toLowerCase())
  );
  
  // Calculate valuation adjustment based on trends
  const valuationMultiplier = relevantTrends.reduce(
    (acc, trend) => acc * (trend.impact === 'high' ? trend.valuationImpact : 
                           trend.impact === 'medium' ? Math.sqrt(trend.valuationImpact) : 1),
    1
  );
  
  // Determine market timing
  const marketTiming = determineMarketTiming(relevantTrends);
  
  // Identify key risks and opportunities
  const keyRisks = generateRisks(relevantTrends, sector);
  const opportunities = generateOpportunities(relevantTrends, sector);
  
  return {
    company,
    sector,
    relevantTrends,
    marketTiming,
    adjustedValuation: baseValuation * valuationMultiplier,
    keyRisks,
    opportunities
  };
}

function determineMarketTiming(trends: MarketContext[]): 'early' | 'optimal' | 'late' | 'contrarian' {
  const highImpactTrends = trends.filter(t => t.impact === 'high');
  
  if (highImpactTrends.length === 0) return 'contrarian';
  if (highImpactTrends.length > 3) return 'optimal';
  if (highImpactTrends.some(t => t.category === 'emerging_category')) return 'early';
  if (highImpactTrends.every(t => t.valuationImpact < 1)) return 'late';
  
  return 'optimal';
}

function generateRisks(trends: MarketContext[], sector: string): string[] {
  const risks: string[] = [];
  
  if (trends.some(t => t.trend.includes('Inflated PE Multiples'))) {
    risks.push('Valuation compression risk in market correction');
  }
  
  if (trends.some(t => t.trend.includes('Megafund Concentration'))) {
    risks.push('Limited exit options due to fund concentration');
  }
  
  if (sector.toLowerCase().includes('ai')) {
    risks.push('High compute costs and GPU availability constraints');
    risks.push('Regulatory uncertainty around AI governance');
  }
  
  if (trends.some(t => t.category === 'geopolitical')) {
    risks.push('Geopolitical tensions affecting market access');
  }
  
  if (trends.some(t => t.trend.includes('Efficiency Focus'))) {
    risks.push('Pressure on burn rates and path to profitability');
  }
  
  return risks;
}

function generateOpportunities(trends: MarketContext[], sector: string): string[] {
  const opportunities: string[] = [];
  
  
  if (trends.some(t => t.trend.includes('Vertical AI'))) {
    opportunities.push('Premium valuations for vertical-specific solutions');
  }
  
  if (trends.some(t => t.trend.includes('Defense Tech'))) {
    opportunities.push('Government contracts and dual-use applications');
  }
  
  if (trends.some(t => t.category === 'emerging_category')) {
    opportunities.push('First-mover advantage in emerging categories');
  }
  
  if (sector.toLowerCase().includes('infrastructure')) {
    opportunities.push('Infrastructure software commanding premium multiples');
  }
  
  return opportunities;
}

// Preset-specific market adjustments
export function adjustPresetForMarketDynamics(
  presetId: string,
  inputs: Record<string, any>
): Record<string, any> {
  const adjustedInputs = { ...inputs };
  const sector = inputs.sector || '';
  
  // Find relevant market dynamics
  const relevantTrends = CURRENT_MARKET_DYNAMICS.filter(
    trend => trend.relevantSectors.includes('All') || 
             trend.relevantSectors.some(s => s.toLowerCase() === sector.toLowerCase())
  );
  
  switch (presetId) {
    case 'dcf':
      // Adjust WACC for current market conditions
      if (relevantTrends.some(t => t.trend.includes('Inflated PE'))) {
        adjustedInputs.wacc = (adjustedInputs.wacc || 12) + 2; // Higher discount rate
      }
      if (sector.includes('AI')) {
        adjustedInputs.terminal_growth = 4; // Higher terminal growth for AI
      }
      break;
      
    case 'comparables':
      // Adjust multiple ranges based on market
      if (relevantTrends.some(t => t.trend.includes('Vertical AI'))) {
        adjustedInputs.ev_revenue_premium = 1.5;
      }
      if (relevantTrends.some(t => t.trend.includes('Defense'))) {
        adjustedInputs.include_government_contracts = true;
      }
      break;
      
    case 'private-credit':
      // Adjust terms for AI companies
      if (sector.includes('AI')) {
        adjustedInputs.interest_rate = (adjustedInputs.interest_rate || 12) + 3;
        adjustedInputs.warrant_coverage = '25%'; // Higher warrant coverage for AI
      }
      break;
      
    case 'cap-table':
      // Adjust for megafund dynamics
      if (relevantTrends.some(t => t.trend.includes('Megafund'))) {
        adjustedInputs.series_b_size = (adjustedInputs.series_b_size || 50000000) * 1.5;
        adjustedInputs.ownership_target = '20%'; // Megafunds want more ownership
      }
      break;
      
    case 'investment-memo':
      // Add market-specific scoring weights
      if (sector.includes('Defense')) {
        adjustedInputs.government_traction_weight = '15%';
      }
      if (relevantTrends.some(t => t.category === 'emerging_category')) {
        adjustedInputs.market_timing_weight = '20%';
      }
      break;
  }
  
  return adjustedInputs;
}

// Real-time market intelligence fetching
export async function fetchLatestMarketIntel(sector: string): Promise<any> {
  try {
    const response = await fetch('/api/market-intelligence', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ 
        sector,
        queries: [
          `latest ${sector} funding rounds 2024`,
          `${sector} M&A activity valuation multiples`,
          `venture capital trends ${sector} 2024`,
          `${sector} private credit deals`,
          'megafund investments recent',
          'AI infrastructure costs trends'
        ]
      })
    });
    
    if (response.ok) {
      return await response.json();
    }
  } catch (error) {
    console.error('Error fetching market intelligence:', error);
  }
  
  return null;
}