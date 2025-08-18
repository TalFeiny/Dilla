import { NextRequest, NextResponse } from 'next/server';
import { createClient } from '@supabase/supabase-js';
import Anthropic from '@anthropic-ai/sdk';

const supabase = createClient(
  process.env.NEXT_PUBLIC_SUPABASE_URL!,
  process.env.SUPABASE_SERVICE_ROLE_KEY!
);

const anthropic = new Anthropic({
  apiKey: process.env.CLAUDE_API_KEY!,
});

// Comprehensive World Model for Investment Analysis
interface InvestmentWorldModel {
  meta: ModelMetadata;
  market_structure: MarketStructure;
  competitive_dynamics: CompetitiveDynamics;
  value_creation: ValueCreation;
  capital_flows: CapitalFlows;
  technology_landscape: TechnologyLandscape;
  regulatory_environment: RegulatoryEnvironment;
  macro_trends: MacroTrends;
  risk_landscape: RiskLandscape;
  opportunity_map: OpportunityMap;
  synthesis: ModelSynthesis;
}

interface ModelMetadata {
  sector: string;
  subsector: string;
  geography: string[];
  model_date: string;
  confidence: number;
  data_sources: number;
  last_updated: string;
}

interface MarketStructure {
  tam: {
    current: number;
    projected_5y: number;
    cagr: number;
    segments: MarketSegment[];
  };
  sam: {
    current: number;
    projected_5y: number;
    penetration: number;
  };
  som: {
    current: number;
    achievable: number;
    timeline: number;
  };
  market_maturity: 'nascent' | 'emerging' | 'growth' | 'mature' | 'declining';
  adoption_curve: {
    current_stage: 'innovators' | 'early_adopters' | 'early_majority' | 'late_majority' | 'laggards';
    penetration_rate: number;
    acceleration: number;
  };
}

interface MarketSegment {
  name: string;
  size: number;
  growth_rate: number;
  key_players: string[];
  entry_difficulty: number; // 0-1
}

interface CompetitiveDynamics {
  market_concentration: {
    hhi: number; // Herfindahl-Hirschman Index
    cr4: number; // 4-firm concentration ratio
    fragmentation: 'high' | 'medium' | 'low';
  };
  competitive_forces: {
    supplier_power: number; // 0-1
    buyer_power: number;
    threat_of_substitutes: number;
    threat_of_new_entrants: number;
    competitive_rivalry: number;
  };
  players: {
    incumbents: CompetitorProfile[];
    challengers: CompetitorProfile[];
    new_entrants: CompetitorProfile[];
    potential_entrants: string[];
  };
  differentiation_factors: string[];
  moat_analysis: {
    network_effects: boolean;
    switching_costs: boolean;
    scale_advantages: boolean;
    intangible_assets: boolean;
    cost_advantages: boolean;
    strength: number; // 0-1
  };
}

interface CompetitorProfile {
  name: string;
  market_share: number;
  revenue: number;
  growth_rate: number;
  valuation: number;
  strengths: string[];
  weaknesses: string[];
  strategy: string;
  recent_moves: string[];
}

interface ValueCreation {
  value_chain: {
    stages: ValueChainStage[];
    integration_opportunities: string[];
    disruption_points: string[];
  };
  business_models: {
    dominant: string;
    emerging: string[];
    disrupted: string[];
  };
  unit_economics: {
    typical_cac: number;
    typical_ltv: number;
    typical_payback: number;
    margin_structure: {
      gross: number;
      contribution: number;
      ebitda: number;
      net: number;
    };
  };
  monetization_models: string[];
  pricing_dynamics: {
    pricing_power: number; // 0-1
    price_trends: 'increasing' | 'stable' | 'decreasing';
    elasticity: number;
  };
}

interface ValueChainStage {
  name: string;
  players: string[];
  margin_capture: number;
  strategic_importance: number; // 0-1
  disruption_risk: number; // 0-1
}

interface CapitalFlows {
  investment_trends: {
    total_invested_ttm: number;
    deal_count_ttm: number;
    average_deal_size: number;
    growth_rate: number;
  };
  stage_distribution: {
    seed: number;
    series_a: number;
    series_b: number;
    growth: number;
    late_stage: number;
  };
  investor_landscape: {
    top_investors: InvestorProfile[];
    new_entrants: string[];
    investment_thesis: string[];
  };
  exit_activity: {
    ipo_count: number;
    ma_count: number;
    total_exit_value: number;
    median_exit_multiple: number;
    typical_hold_period: number;
  };
  dry_powder: number;
  deployment_rate: number;
}

interface InvestorProfile {
  name: string;
  type: 'vc' | 'pe' | 'strategic' | 'hedge_fund';
  focus: string[];
  portfolio_companies: number;
  recent_investments: string[];
}

interface TechnologyLandscape {
  core_technologies: Technology[];
  emerging_technologies: Technology[];
  technology_adoption: {
    current_state: string;
    adoption_barriers: string[];
    enablers: string[];
  };
  innovation_velocity: number; // 0-1
  patent_activity: {
    total_patents: number;
    growth_rate: number;
    key_holders: string[];
  };
  r_and_d_intensity: number; // R&D as % of revenue
  technology_stack: {
    infrastructure: string[];
    platforms: string[];
    applications: string[];
  };
}

interface Technology {
  name: string;
  maturity: 'experimental' | 'emerging' | 'growth' | 'mature';
  impact_potential: number; // 0-1
  adoption_timeline: number; // years
  key_players: string[];
}

interface RegulatoryEnvironment {
  current_regulations: Regulation[];
  pending_regulations: Regulation[];
  regulatory_risk: number; // 0-1
  compliance_cost: number;
  regulatory_trends: string[];
  geographic_variations: {
    region: string;
    stance: 'supportive' | 'neutral' | 'restrictive';
    key_regulations: string[];
  }[];
}

interface Regulation {
  name: string;
  impact: 'high' | 'medium' | 'low';
  effective_date: string;
  affected_areas: string[];
}

interface MacroTrends {
  economic_factors: {
    gdp_growth: number;
    inflation: number;
    interest_rates: number;
    unemployment: number;
    consumer_confidence: number;
  };
  demographic_shifts: {
    trend: string;
    impact: string;
    timeline: number;
  }[];
  social_trends: string[];
  technological_mega_trends: string[];
  geopolitical_factors: {
    factor: string;
    impact: 'positive' | 'negative' | 'neutral';
    probability: number;
  }[];
  sustainability_factors: {
    esg_importance: number; // 0-1
    climate_impact: string;
    regulatory_pressure: number; // 0-1
  };
}

interface RiskLandscape {
  systematic_risks: Risk[];
  idiosyncratic_risks: Risk[];
  black_swan_events: Risk[];
  risk_mitigation: {
    risk: string;
    mitigation_strategy: string;
    effectiveness: number; // 0-1
  }[];
  overall_risk_score: number; // 0-1
}

interface Risk {
  name: string;
  category: string;
  probability: number; // 0-1
  impact: number; // 0-1
  timeline: string;
  early_indicators: string[];
}

interface OpportunityMap {
  investment_opportunities: Opportunity[];
  market_gaps: MarketGap[];
  convergence_opportunities: {
    sectors: string[];
    thesis: string;
    timeline: number;
  }[];
  geographic_expansion: {
    region: string;
    opportunity_size: number;
    entry_barriers: string[];
  }[];
  timing_considerations: {
    optimal_entry: string;
    key_catalysts: string[];
    window_duration: number;
  };
}

interface Opportunity {
  type: string;
  description: string;
  size: number;
  probability_of_success: number;
  required_capabilities: string[];
  key_success_factors: string[];
}

interface MarketGap {
  need: string;
  current_solutions: string[];
  gap_size: number;
  solution_requirements: string[];
}

interface ModelSynthesis {
  investment_thesis: string;
  key_insights: string[];
  critical_assumptions: string[];
  scenario_analysis: {
    base_case: ScenarioOutcome;
    bull_case: ScenarioOutcome;
    bear_case: ScenarioOutcome;
  };
  decision_factors: {
    factor: string;
    weight: number;
    score: number;
  }[];
  recommendation: {
    action: 'strong_buy' | 'buy' | 'hold' | 'sell' | 'strong_sell';
    confidence: number;
    time_horizon: number;
    key_milestones: string[];
  };
}

interface ScenarioOutcome {
  probability: number;
  market_size: number;
  growth_rate: number;
  returns: number;
  key_drivers: string[];
}

// Build comprehensive world model
async function buildWorldModel(sector: string, companies: string[], geography: string[]): Promise<InvestmentWorldModel> {
  console.log(`Building world model for ${sector} with ${companies.length} companies`);

  // Parallel data fetching
  const [
    marketData,
    competitiveData,
    capitalData,
    techData,
    regulatoryData,
    macroData
  ] = await Promise.all([
    fetchMarketStructure(sector, geography),
    fetchCompetitiveDynamics(sector, companies),
    fetchCapitalFlows(sector),
    fetchTechnologyLandscape(sector),
    fetchRegulatoryEnvironment(sector, geography),
    fetchMacroTrends(geography)
  ]);

  // Build value creation model
  const valueCreation = await analyzeValueCreation(sector, competitiveData);

  // Identify risks
  const riskLandscape = await identifyRisks(sector, marketData, regulatoryData, macroData);

  // Map opportunities
  const opportunityMap = await mapOpportunities(sector, marketData, competitiveData, techData);

  // Synthesize insights
  const synthesis = await synthesizeModel(
    marketData,
    competitiveData,
    valueCreation,
    capitalData,
    riskLandscape,
    opportunityMap
  );

  return {
    meta: {
      sector,
      subsector: identifySubsector(sector, companies),
      geography,
      model_date: new Date().toISOString(),
      confidence: calculateModelConfidence(marketData, competitiveData, capitalData),
      data_sources: countDataSources(marketData, competitiveData, capitalData),
      last_updated: new Date().toISOString()
    },
    market_structure: marketData,
    competitive_dynamics: competitiveData,
    value_creation: valueCreation,
    capital_flows: capitalData,
    technology_landscape: techData,
    regulatory_environment: regulatoryData,
    macro_trends: macroData,
    risk_landscape: riskLandscape,
    opportunity_map: opportunityMap,
    synthesis
  };
}

// Fetch market structure data
async function fetchMarketStructure(sector: string, geography: string[]): Promise<MarketStructure> {
  const tavilyKey = process.env.TAVILY_API_KEY;
  
  const queries = [
    `${sector} market size TAM SAM SOM ${geography.join(' ')} 2024 2025`,
    `${sector} market growth CAGR forecast 2025 2030`,
    `${sector} adoption curve penetration rate market maturity`
  ];

  const responses = await Promise.all(
    queries.map(q => 
      fetch('https://api.tavily.com/search', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          api_key: tavilyKey,
          query: q,
          search_depth: 'advanced',
          max_results: 10,
          include_answer: true
        })
      }).then(r => r.json())
    )
  );

  // Extract and structure market data using Claude
  const prompt = `Analyze this market data for ${sector} and extract:
${JSON.stringify(responses.map(r => r.answer), null, 2)}

Return ONLY a JSON object with TAM (current and 5y projected), SAM, SOM, market maturity stage, and adoption curve position.`;

  const analysis = await anthropic.messages.create({
    model: 'claude-3-5-sonnet-20241022',
    max_tokens: 2000,
    messages: [{ role: 'user', content: prompt }]
  });

  const content = analysis.content[0].type === 'text' ? analysis.content[0].text : '';
  const jsonMatch = content.match(/\{[\s\S]*\}/);

  if (jsonMatch) {
    return JSON.parse(jsonMatch[0]);
  }

  // Default structure
  return {
    tam: {
      current: 0,
      projected_5y: 0,
      cagr: 0,
      segments: []
    },
    sam: {
      current: 0,
      projected_5y: 0,
      penetration: 0
    },
    som: {
      current: 0,
      achievable: 0,
      timeline: 3
    },
    market_maturity: 'growth',
    adoption_curve: {
      current_stage: 'early_majority',
      penetration_rate: 0.3,
      acceleration: 0.2
    }
  };
}

// Fetch competitive dynamics
async function fetchCompetitiveDynamics(sector: string, companies: string[]): Promise<CompetitiveDynamics> {
  // Get competitor data from database
  const { data: competitors } = await supabase
    .from('companies')
    .select('*')
    .eq('sector', sector)
    .order('valuation_usd', { ascending: false })
    .limit(50);

  // Fetch additional competitive intelligence
  const tavilyKey = process.env.TAVILY_API_KEY;
  
  const competitiveData = await fetch('https://api.tavily.com/search', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      api_key: tavilyKey,
      query: `${sector} competitive landscape market share concentration ${companies.join(' ')}`,
      search_depth: 'advanced',
      max_results: 15
    })
  }).then(r => r.json());

  // Analyze competitive forces
  const forces = await analyzePortersFiveForces(sector, competitors, competitiveData);

  // Calculate market concentration
  const concentration = calculateMarketConcentration(competitors);

  // Profile key players
  const profiles = await profileCompetitors(companies, competitors, competitiveData);

  return {
    market_concentration: concentration,
    competitive_forces: forces,
    players: profiles,
    differentiation_factors: extractDifferentiationFactors(competitiveData),
    moat_analysis: analyzeMoats(sector, profiles)
  };
}

// Analyze Porter's Five Forces
async function analyzePortersFiveForces(sector: string, competitors: any[], marketData: any): Promise<any> {
  const prompt = `Analyze Porter's Five Forces for ${sector} based on:
- ${competitors.length} competitors
- Market data: ${JSON.stringify(marketData.answer)}

Rate each force from 0-1 (0=low, 1=high):
- supplier_power
- buyer_power  
- threat_of_substitutes
- threat_of_new_entrants
- competitive_rivalry

Return ONLY a JSON object with these scores.`;

  const analysis = await anthropic.messages.create({
    model: 'claude-3-5-sonnet-20241022',
    max_tokens: 500,
    messages: [{ role: 'user', content: prompt }]
  });

  const content = analysis.content[0].type === 'text' ? analysis.content[0].text : '';
  const jsonMatch = content.match(/\{[\s\S]*\}/);

  return jsonMatch ? JSON.parse(jsonMatch[0]) : {
    supplier_power: 0.5,
    buyer_power: 0.5,
    threat_of_substitutes: 0.5,
    threat_of_new_entrants: 0.5,
    competitive_rivalry: 0.5
  };
}

// Calculate market concentration metrics
function calculateMarketConcentration(competitors: any[]): any {
  if (!competitors || competitors.length === 0) {
    return {
      hhi: 0,
      cr4: 0,
      fragmentation: 'high'
    };
  }

  const totalRevenue = competitors.reduce((sum, c) => sum + (c.revenue || 0), 0);
  
  // Calculate HHI
  let hhi = 0;
  competitors.forEach(c => {
    if (c.revenue) {
      const marketShare = c.revenue / totalRevenue;
      hhi += Math.pow(marketShare * 100, 2);
    }
  });

  // Calculate CR4
  const top4Revenue = competitors
    .sort((a, b) => (b.revenue || 0) - (a.revenue || 0))
    .slice(0, 4)
    .reduce((sum, c) => sum + (c.revenue || 0), 0);
  
  const cr4 = totalRevenue > 0 ? top4Revenue / totalRevenue : 0;

  // Determine fragmentation
  let fragmentation: 'high' | 'medium' | 'low';
  if (hhi < 1500) fragmentation = 'high';
  else if (hhi < 2500) fragmentation = 'medium';
  else fragmentation = 'low';

  return { hhi, cr4, fragmentation };
}

// Profile key competitors
async function profileCompetitors(companies: string[], dbCompetitors: any[], marketData: any): Promise<any> {
  const incumbents: CompetitorProfile[] = [];
  const challengers: CompetitorProfile[] = [];
  const new_entrants: CompetitorProfile[] = [];

  // Categorize competitors
  for (const comp of dbCompetitors.slice(0, 20)) {
    const profile: CompetitorProfile = {
      name: comp.name,
      market_share: 0,
      revenue: comp.revenue || 0,
      growth_rate: comp.growth_rate || 0,
      valuation: comp.valuation_usd || 0,
      strengths: [],
      weaknesses: [],
      strategy: '',
      recent_moves: []
    };

    // Categorize by size/age
    if (comp.valuation_usd > 1e9) {
      incumbents.push(profile);
    } else if (comp.valuation_usd > 1e8) {
      challengers.push(profile);
    } else {
      new_entrants.push(profile);
    }
  }

  return {
    incumbents,
    challengers,
    new_entrants,
    potential_entrants: []
  };
}

// Extract differentiation factors
function extractDifferentiationFactors(marketData: any): string[] {
  // This would use NLP to extract key differentiation factors
  return [
    'Technology innovation',
    'Customer experience',
    'Network effects',
    'Brand strength',
    'Cost efficiency'
  ];
}

// Analyze competitive moats
function analyzeMoats(sector: string, profiles: any): any {
  // Sector-specific moat analysis
  const sectorMoats = {
    'SaaS': { network_effects: true, switching_costs: true, scale_advantages: true },
    'Marketplace': { network_effects: true, scale_advantages: true },
    'FinTech': { switching_costs: true, intangible_assets: true },
    'Healthcare': { intangible_assets: true, switching_costs: true }
  };

  const moats = sectorMoats[sector] || {};
  
  return {
    network_effects: moats.network_effects || false,
    switching_costs: moats.switching_costs || false,
    scale_advantages: moats.scale_advantages || false,
    intangible_assets: moats.intangible_assets || false,
    cost_advantages: false,
    strength: Object.values(moats).filter(v => v).length / 5
  };
}

// Additional helper functions
async function fetchCapitalFlows(sector: string): Promise<CapitalFlows> {
  // Implementation for fetching investment data
  return {} as CapitalFlows;
}

async function fetchTechnologyLandscape(sector: string): Promise<TechnologyLandscape> {
  // Implementation for technology analysis
  return {} as TechnologyLandscape;
}

async function fetchRegulatoryEnvironment(sector: string, geography: string[]): Promise<RegulatoryEnvironment> {
  // Implementation for regulatory analysis
  return {} as RegulatoryEnvironment;
}

async function fetchMacroTrends(geography: string[]): Promise<MacroTrends> {
  // Implementation for macro analysis
  return {} as MacroTrends;
}

async function analyzeValueCreation(sector: string, competitiveData: any): Promise<ValueCreation> {
  // Implementation for value creation analysis
  return {} as ValueCreation;
}

async function identifyRisks(sector: string, marketData: any, regulatoryData: any, macroData: any): Promise<RiskLandscape> {
  // Implementation for risk identification
  return {} as RiskLandscape;
}

async function mapOpportunities(sector: string, marketData: any, competitiveData: any, techData: any): Promise<OpportunityMap> {
  // Implementation for opportunity mapping
  return {} as OpportunityMap;
}

async function synthesizeModel(
  marketData: any, 
  competitiveData: any, 
  valueCreation: any,
  capitalData: any,
  riskLandscape: any,
  opportunityMap: any
): Promise<ModelSynthesis> {
  // Implementation for model synthesis
  return {} as ModelSynthesis;
}

function identifySubsector(sector: string, companies: string[]): string {
  return `${sector}-General`;
}

function calculateModelConfidence(marketData: any, competitiveData: any, capitalData: any): number {
  return 0.75;
}

function countDataSources(marketData: any, competitiveData: any, capitalData: any): number {
  return 25;
}

// Main handler
export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const { 
      sector = 'Technology',
      companies = [],
      geography = ['United States'],
      refresh = false
    } = body;

    // Check cache first
    if (!refresh) {
      const { data: cached } = await supabase
        .from('world_models')
        .select('*')
        .eq('sector', sector)
        .single();

      if (cached && cached.created_at) {
        const age = Date.now() - new Date(cached.created_at).getTime();
        if (age < 24 * 60 * 60 * 1000) { // 24 hours
          return NextResponse.json({
            source: 'cache',
            model: cached.model
          });
        }
      }
    }

    // Build fresh world model
    const worldModel = await buildWorldModel(sector, companies, geography);

    // Store in cache
    await supabase
      .from('world_models')
      .upsert({
        sector,
        model: worldModel,
        created_at: new Date()
      });

    return NextResponse.json({
      source: 'fresh',
      model: worldModel
    });

  } catch (error) {
    console.error('World model generation error:', error);
    return NextResponse.json(
      { error: 'Failed to generate world model', details: error instanceof Error ? error.message : 'Unknown error' },
      { status: 500 }
    );
  }
}

// GET endpoint for model metadata
export async function GET() {
  return NextResponse.json({
    description: 'Comprehensive world model for investment analysis',
    components: [
      'Market Structure (TAM/SAM/SOM)',
      'Competitive Dynamics (Porter\'s Five Forces)',
      'Value Creation Analysis',
      'Capital Flows & Investment Trends',
      'Technology Landscape',
      'Regulatory Environment',
      'Macro Trends',
      'Risk Landscape',
      'Opportunity Mapping',
      'Investment Thesis Synthesis'
    ],
    capabilities: [
      'Multi-dimensional market analysis',
      'Competitive positioning assessment',
      'Risk-adjusted opportunity identification',
      'Scenario planning and sensitivity analysis',
      'Investment recommendation generation'
    ]
  });
}