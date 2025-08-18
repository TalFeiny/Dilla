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

// Enhanced data quality pipeline for PWERM and Waterfall analysis
interface DataQualityPipeline {
  raw_data: RawDataSources;
  validated_data: ValidatedData;
  enriched_data: EnrichedData;
  confidence_scores: ConfidenceScores;
  data_lineage: DataLineage[];
}

interface RawDataSources {
  primary: PrimarySource[];
  secondary: SecondarySource[];
  tertiary: TertiarySource[];
}

interface PrimarySource {
  type: 'sec_filing' | 'company_disclosure' | 'regulatory_filing';
  url: string;
  date: string;
  reliability: number; // 0.9-1.0
}

interface SecondarySource {
  type: 'pitchbook' | 'cbinsights' | 'crunchbase' | 'preqin';
  data: any;
  date: string;
  reliability: number; // 0.7-0.9
}

interface TertiarySource {
  type: 'news' | 'blog' | 'report';
  url: string;
  date: string;
  reliability: number; // 0.5-0.7
}

interface ValidatedData {
  revenue: ValidationResult;
  growth_rate: ValidationResult;
  valuation: ValidationResult;
  burn_rate: ValidationResult;
  runway: ValidationResult;
  market_size: ValidationResult;
}

interface ValidationResult {
  value: number;
  confidence: number;
  sources: string[];
  validation_method: string;
  anomalies: string[];
}

interface EnrichedData {
  comparables: ComparableCompany[];
  market_multiples: MarketMultiples;
  exit_scenarios: ExitScenario[];
  risk_factors: RiskFactor[];
}

interface ComparableCompany {
  name: string;
  ticker?: string;
  revenue: number;
  growth_rate: number;
  ev_revenue: number;
  similarity_score: number;
  data_quality: number;
}

interface MarketMultiples {
  sector: string;
  median_ev_revenue: number;
  quartile_1: number;
  quartile_3: number;
  sample_size: number;
  as_of_date: string;
}

interface ExitScenario {
  type: 'ipo' | 'acquisition' | 'secondary' | 'liquidation';
  probability: number;
  timeline_years: number;
  exit_multiple: number;
  expected_value: number;
  precedents: ExitPrecedent[];
}

interface ExitPrecedent {
  company: string;
  exit_type: string;
  exit_value: number;
  exit_multiple: number;
  date: string;
  acquirer?: string;
}

interface RiskFactor {
  category: string;
  description: string;
  impact: 'high' | 'medium' | 'low';
  probability: number;
  mitigation: string;
}

interface ConfidenceScores {
  overall: number;
  revenue: number;
  valuation: number;
  comparables: number;
  exit_analysis: number;
}

interface DataLineage {
  field: string;
  sources: string[];
  transformations: string[];
  timestamp: string;
  confidence: number;
}

// Fetch data from premium sources with quality scoring
async function fetchPremiumData(company: string, dataType: string): Promise<RawDataSources> {
  const sources: RawDataSources = {
    primary: [],
    secondary: [],
    tertiary: []
  };

  // Primary sources - SEC and regulatory filings
  const secData = await fetchSECFilings(company);
  if (secData) {
    sources.primary.push({
      type: 'sec_filing',
      url: secData.url,
      date: secData.date,
      reliability: 0.95
    });
  }

  // Secondary sources - Premium data providers
  const premiumProviders = [
    { name: 'pitchbook', url: 'pitchbook.com' },
    { name: 'cbinsights', url: 'cbinsights.com' },
    { name: 'crunchbase', url: 'crunchbase.com' },
    { name: 'preqin', url: 'preqin.com' },
    { name: 'dealroom', url: 'dealroom.co' },
    { name: 'tracxn', url: 'tracxn.com' }
  ];

  const tavilyKey = process.env.TAVILY_API_KEY;
  if (!tavilyKey) throw new Error('Tavily API key required');

  // Parallel fetch from all premium sources
  const fetchPromises = premiumProviders.map(async provider => {
    const response = await fetch('https://api.tavily.com/search', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        api_key: tavilyKey,
        query: `${company} ${dataType} site:${provider.url}`,
        search_depth: 'advanced',
        max_results: 5,
        include_answer: true,
        include_raw_content: true
      })
    });

    const data = await response.json();
    
    if (data.results && data.results.length > 0) {
      sources.secondary.push({
        type: provider.name as any,
        data: data.results[0],
        date: new Date().toISOString(),
        reliability: getProviderReliability(provider.name)
      });
    }
  });

  await Promise.all(fetchPromises);

  // Tertiary sources - News and reports
  const newsResponse = await fetch('https://api.tavily.com/search', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      api_key: tavilyKey,
      query: `${company} ${dataType} revenue valuation funding`,
      search_depth: 'advanced',
      max_results: 10,
      include_answer: true
    })
  });

  const newsData = await newsResponse.json();
  if (newsData.results) {
    newsData.results.forEach(result => {
      sources.tertiary.push({
        type: categorizeSource(result.url),
        url: result.url,
        date: new Date().toISOString(),
        reliability: calculateReliability(result.url)
      });
    });
  }

  return sources;
}

// Fetch SEC filings if available
async function fetchSECFilings(company: string): Promise<any> {
  // This would integrate with SEC EDGAR API
  // For now, return null for private companies
  return null;
}

// Get reliability score for data provider
function getProviderReliability(provider: string): number {
  const scores = {
    'pitchbook': 0.90,
    'cbinsights': 0.88,
    'crunchbase': 0.85,
    'preqin': 0.87,
    'dealroom': 0.83,
    'tracxn': 0.80
  };
  return scores[provider] || 0.70;
}

// Categorize source type
function categorizeSource(url: string): 'news' | 'blog' | 'report' {
  if (url.includes('techcrunch') || url.includes('reuters') || url.includes('bloomberg')) {
    return 'news';
  } else if (url.includes('blog') || url.includes('medium')) {
    return 'blog';
  }
  return 'report';
}

// Calculate source reliability
function calculateReliability(url: string): number {
  const domains = {
    'bloomberg.com': 0.85,
    'reuters.com': 0.85,
    'wsj.com': 0.85,
    'ft.com': 0.85,
    'techcrunch.com': 0.75,
    'forbes.com': 0.75,
    'businessinsider.com': 0.70,
    'venturebeat.com': 0.70
  };

  for (const [domain, score] of Object.entries(domains)) {
    if (url.includes(domain)) return score;
  }
  
  return 0.60;
}

// Validate and cross-reference data
async function validateData(rawData: RawDataSources, company: string): Promise<ValidatedData> {
  const validated: ValidatedData = {
    revenue: await validateRevenue(rawData, company),
    growth_rate: await validateGrowthRate(rawData, company),
    valuation: await validateValuation(rawData, company),
    burn_rate: await validateBurnRate(rawData, company),
    runway: await validateRunway(rawData, company),
    market_size: await validateMarketSize(rawData, company)
  };

  return validated;
}

// Validate revenue with multiple sources
async function validateRevenue(rawData: RawDataSources, company: string): Promise<ValidationResult> {
  const revenues = [];
  const sources = [];

  // Extract revenue from all sources
  for (const source of [...rawData.primary, ...rawData.secondary, ...rawData.tertiary]) {
    const extracted = await extractMetric(source, 'revenue', company);
    if (extracted) {
      revenues.push({
        value: extracted.value,
        reliability: source.reliability
      });
      sources.push(extracted.source);
    }
  }

  if (revenues.length === 0) {
    return {
      value: 0,
      confidence: 0,
      sources: [],
      validation_method: 'no_data',
      anomalies: ['No revenue data found']
    };
  }

  // Calculate weighted average
  const weightedSum = revenues.reduce((sum, r) => sum + r.value * r.reliability, 0);
  const weightSum = revenues.reduce((sum, r) => sum + r.reliability, 0);
  const weightedAverage = weightedSum / weightSum;

  // Check for anomalies
  const anomalies = [];
  const median = calculateMedian(revenues.map(r => r.value));
  
  revenues.forEach(r => {
    if (Math.abs(r.value - median) / median > 0.5) {
      anomalies.push(`Outlier value: ${r.value}`);
    }
  });

  return {
    value: weightedAverage,
    confidence: calculateConfidence(revenues),
    sources,
    validation_method: 'weighted_average',
    anomalies
  };
}

// Similar validation functions for other metrics
async function validateGrowthRate(rawData: RawDataSources, company: string): Promise<ValidationResult> {
  // Implementation similar to validateRevenue
  return {
    value: 0,
    confidence: 0,
    sources: [],
    validation_method: 'estimated',
    anomalies: []
  };
}

async function validateValuation(rawData: RawDataSources, company: string): Promise<ValidationResult> {
  // Implementation similar to validateRevenue
  return {
    value: 0,
    confidence: 0,
    sources: [],
    validation_method: 'estimated',
    anomalies: []
  };
}

async function validateBurnRate(rawData: RawDataSources, company: string): Promise<ValidationResult> {
  // Implementation similar to validateRevenue
  return {
    value: 0,
    confidence: 0,
    sources: [],
    validation_method: 'estimated',
    anomalies: []
  };
}

async function validateRunway(rawData: RawDataSources, company: string): Promise<ValidationResult> {
  // Implementation similar to validateRevenue
  return {
    value: 0,
    confidence: 0,
    sources: [],
    validation_method: 'estimated',
    anomalies: []
  };
}

async function validateMarketSize(rawData: RawDataSources, company: string): Promise<ValidationResult> {
  // Implementation similar to validateRevenue
  return {
    value: 0,
    confidence: 0,
    sources: [],
    validation_method: 'estimated',
    anomalies: []
  };
}

// Extract specific metric from source using Claude
async function extractMetric(source: any, metric: string, company: string): Promise<any> {
  let content = '';
  
  if (source.data) {
    content = JSON.stringify(source.data);
  } else if (source.url) {
    // For primary/tertiary sources, we have the URL but need to extract content
    content = source.url; // In production, would fetch and parse the URL
  }

  const prompt = `Extract ${metric} for ${company} from this content:
${content}

Return ONLY a JSON object: {"value": number, "source": "description of source"}
If not found, return {"value": null, "source": "not found"}`;

  try {
    const response = await anthropic.messages.create({
      model: 'claude-3-5-sonnet-20241022',
      max_tokens: 200,
      messages: [{ role: 'user', content: prompt }]
    });

    const text = response.content[0].type === 'text' ? response.content[0].text : '';
    const jsonMatch = text.match(/\{[\s\S]*\}/);
    
    if (jsonMatch) {
      const result = JSON.parse(jsonMatch[0]);
      if (result.value !== null) {
        return result;
      }
    }
  } catch (error) {
    console.error('Failed to extract metric:', error);
  }

  return null;
}

// Calculate median value
function calculateMedian(values: number[]): number {
  if (values.length === 0) return 0;
  
  const sorted = values.sort((a, b) => a - b);
  const mid = Math.floor(sorted.length / 2);
  
  return sorted.length % 2 === 0
    ? (sorted[mid - 1] + sorted[mid]) / 2
    : sorted[mid];
}

// Calculate confidence score
function calculateConfidence(dataPoints: any[]): number {
  if (dataPoints.length === 0) return 0;
  
  // Base confidence from number of sources
  let confidence = Math.min(0.5 + dataPoints.length * 0.1, 0.8);
  
  // Adjust for reliability
  const avgReliability = dataPoints.reduce((sum, d) => sum + d.reliability, 0) / dataPoints.length;
  confidence *= avgReliability;
  
  // Adjust for consistency
  const values = dataPoints.map(d => d.value);
  const cv = coefficientOfVariation(values);
  if (cv < 0.2) confidence *= 1.2;
  else if (cv > 0.5) confidence *= 0.8;
  
  return Math.min(confidence, 1.0);
}

// Calculate coefficient of variation
function coefficientOfVariation(values: number[]): number {
  if (values.length < 2) return 1;
  
  const mean = values.reduce((sum, val) => sum + val, 0) / values.length;
  if (mean === 0) return 1;
  
  const variance = values.reduce((sum, val) => sum + Math.pow(val - mean, 2), 0) / values.length;
  const stdDev = Math.sqrt(variance);
  
  return stdDev / mean;
}

// Enrich data with comparables and market intelligence
async function enrichData(validatedData: ValidatedData, company: string, sector: string): Promise<EnrichedData> {
  const [comparables, marketMultiples, exitScenarios] = await Promise.all([
    findComparables(company, sector, validatedData),
    getMarketMultiples(sector),
    analyzeExitScenarios(company, sector, validatedData)
  ]);

  const riskFactors = identifyRiskFactors(validatedData, comparables);

  return {
    comparables,
    market_multiples: marketMultiples,
    exit_scenarios: exitScenarios,
    risk_factors: riskFactors
  };
}

// Find comparable companies
async function findComparables(company: string, sector: string, validatedData: ValidatedData): Promise<ComparableCompany[]> {
  // Get from database
  const { data: dbComps } = await supabase
    .from('companies')
    .select('*')
    .eq('sector', sector)
    .not('revenue', 'is', null)
    .limit(50);

  const comparables: ComparableCompany[] = [];

  if (dbComps) {
    for (const comp of dbComps) {
      const similarity = calculateSimilarity(comp, validatedData);
      
      if (similarity > 0.6) {
        comparables.push({
          name: comp.name,
          ticker: comp.ticker,
          revenue: comp.revenue,
          growth_rate: comp.growth_rate || 0,
          ev_revenue: comp.valuation_usd / comp.revenue,
          similarity_score: similarity,
          data_quality: comp.data_quality || 0.7
        });
      }
    }
  }

  // Sort by similarity
  comparables.sort((a, b) => b.similarity_score - a.similarity_score);

  return comparables.slice(0, 20);
}

// Calculate similarity score
function calculateSimilarity(comp: any, targetData: ValidatedData): number {
  let score = 0;
  let factors = 0;

  // Revenue similarity
  if (comp.revenue && targetData.revenue.value) {
    const revRatio = Math.min(comp.revenue, targetData.revenue.value) / 
                     Math.max(comp.revenue, targetData.revenue.value);
    score += revRatio * 0.4;
    factors += 0.4;
  }

  // Growth rate similarity  
  if (comp.growth_rate && targetData.growth_rate.value) {
    const growthDiff = Math.abs(comp.growth_rate - targetData.growth_rate.value);
    const growthScore = Math.max(0, 1 - growthDiff / 0.5);
    score += growthScore * 0.3;
    factors += 0.3;
  }

  // Sector match
  score += 0.3;
  factors += 0.3;

  return factors > 0 ? score / factors : 0;
}

// Get market multiples for sector
async function getMarketMultiples(sector: string): Promise<MarketMultiples> {
  const { data: companies } = await supabase
    .from('companies')
    .select('revenue, valuation_usd')
    .eq('sector', sector)
    .not('revenue', 'is', null)
    .not('valuation_usd', 'is', null);

  if (!companies || companies.length === 0) {
    return {
      sector,
      median_ev_revenue: 5,
      quartile_1: 3,
      quartile_3: 8,
      sample_size: 0,
      as_of_date: new Date().toISOString()
    };
  }

  const multiples = companies.map(c => c.valuation_usd / c.revenue).sort((a, b) => a - b);
  
  return {
    sector,
    median_ev_revenue: multiples[Math.floor(multiples.length / 2)],
    quartile_1: multiples[Math.floor(multiples.length * 0.25)],
    quartile_3: multiples[Math.floor(multiples.length * 0.75)],
    sample_size: multiples.length,
    as_of_date: new Date().toISOString()
  };
}

// Analyze exit scenarios
async function analyzeExitScenarios(company: string, sector: string, validatedData: ValidatedData): Promise<ExitScenario[]> {
  // Fetch recent exits in sector
  const tavilyKey = process.env.TAVILY_API_KEY;
  
  const exitResponse = await fetch('https://api.tavily.com/search', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      api_key: tavilyKey,
      query: `${sector} acquisitions IPO exits 2023 2024 2025`,
      search_depth: 'advanced',
      max_results: 20
    })
  });

  const exitData = await exitResponse.json();
  
  // Parse exit precedents
  const precedents = await parseExitPrecedents(exitData.results);

  // Calculate exit scenarios
  const scenarios: ExitScenario[] = [
    {
      type: 'acquisition',
      probability: 0.6,
      timeline_years: 3,
      exit_multiple: calculateExitMultiple(precedents, 'acquisition'),
      expected_value: validatedData.revenue.value * calculateExitMultiple(precedents, 'acquisition'),
      precedents: precedents.filter(p => p.exit_type === 'acquisition').slice(0, 5)
    },
    {
      type: 'ipo',
      probability: 0.2,
      timeline_years: 5,
      exit_multiple: calculateExitMultiple(precedents, 'ipo'),
      expected_value: validatedData.revenue.value * calculateExitMultiple(precedents, 'ipo'),
      precedents: precedents.filter(p => p.exit_type === 'ipo').slice(0, 5)
    },
    {
      type: 'secondary',
      probability: 0.15,
      timeline_years: 2,
      exit_multiple: calculateExitMultiple(precedents, 'secondary') * 0.8,
      expected_value: validatedData.revenue.value * calculateExitMultiple(precedents, 'secondary') * 0.8,
      precedents: []
    },
    {
      type: 'liquidation',
      probability: 0.05,
      timeline_years: 1,
      exit_multiple: 0.5,
      expected_value: validatedData.revenue.value * 0.5,
      precedents: []
    }
  ];

  return scenarios;
}

// Parse exit precedents from search results
async function parseExitPrecedents(searchResults: any[]): Promise<ExitPrecedent[]> {
  const precedents: ExitPrecedent[] = [];

  for (const result of searchResults) {
    const prompt = `Extract exit transaction details from this text:
${result.content}

Return ONLY a JSON array of objects with: company, exit_type, exit_value, exit_multiple, date, acquirer`;

    try {
      const response = await anthropic.messages.create({
        model: 'claude-3-5-sonnet-20241022',
        max_tokens: 500,
        messages: [{ role: 'user', content: prompt }]
      });

      const text = response.content[0].type === 'text' ? response.content[0].text : '';
      const jsonMatch = text.match(/\[[\s\S]*\]/);
      
      if (jsonMatch) {
        const parsed = JSON.parse(jsonMatch[0]);
        precedents.push(...parsed);
      }
    } catch (error) {
      console.error('Failed to parse exit precedents:', error);
    }
  }

  return precedents;
}

// Calculate exit multiple based on precedents
function calculateExitMultiple(precedents: ExitPrecedent[], exitType: string): number {
  const relevantExits = precedents.filter(p => p.exit_type === exitType);
  
  if (relevantExits.length === 0) {
    // Default multiples
    const defaults = {
      'acquisition': 6,
      'ipo': 8,
      'secondary': 4
    };
    return defaults[exitType] || 3;
  }

  const multiples = relevantExits.map(e => e.exit_multiple).filter(m => m > 0);
  
  if (multiples.length === 0) return 5;
  
  return calculateMedian(multiples);
}

// Identify risk factors
function identifyRiskFactors(validatedData: ValidatedData, comparables: ComparableCompany[]): RiskFactor[] {
  const risks: RiskFactor[] = [];

  // Data quality risk
  if (validatedData.revenue.confidence < 0.7) {
    risks.push({
      category: 'Data Quality',
      description: 'Low confidence in revenue data',
      impact: 'high',
      probability: 0.8,
      mitigation: 'Obtain audited financials or management confirmation'
    });
  }

  // Burn rate risk
  if (validatedData.burn_rate.value > validatedData.revenue.value * 0.5) {
    risks.push({
      category: 'Financial',
      description: 'High burn rate relative to revenue',
      impact: 'high',
      probability: 0.7,
      mitigation: 'Monitor cash position and fundraising timeline'
    });
  }

  // Valuation risk
  if (comparables.length > 0) {
    const medianMultiple = calculateMedian(comparables.map(c => c.ev_revenue));
    const currentMultiple = validatedData.valuation.value / validatedData.revenue.value;
    
    if (currentMultiple > medianMultiple * 1.5) {
      risks.push({
        category: 'Valuation',
        description: 'Trading at premium to comparables',
        impact: 'medium',
        probability: 0.6,
        mitigation: 'Justify premium with superior growth or margins'
      });
    }
  }

  // Market risk
  risks.push({
    category: 'Market',
    description: 'General market volatility',
    impact: 'medium',
    probability: 0.5,
    mitigation: 'Diversify portfolio and maintain reserves'
  });

  return risks;
}

// Main handler for enhanced data pipeline
export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const { company, sector = 'Technology', analysisType = 'full' } = body;

    if (!company) {
      return NextResponse.json({ error: 'Company name required' }, { status: 400 });
    }

    console.log(`Starting enhanced data pipeline for ${company}`);

    // Step 1: Fetch raw data from multiple sources
    const rawData = await fetchPremiumData(company, 'financials valuation funding');

    // Step 2: Validate and cross-reference
    const validatedData = await validateData(rawData, company);

    // Step 3: Enrich with comparables and market data
    const enrichedData = await enrichData(validatedData, company, sector);

    // Step 4: Calculate confidence scores
    const confidenceScores: ConfidenceScores = {
      overall: calculateOverallConfidence(validatedData, enrichedData),
      revenue: validatedData.revenue.confidence,
      valuation: validatedData.valuation.confidence,
      comparables: enrichedData.comparables.length > 5 ? 0.8 : 0.5,
      exit_analysis: enrichedData.exit_scenarios.filter(s => s.precedents.length > 0).length > 2 ? 0.7 : 0.4
    };

    // Step 5: Create data lineage
    const dataLineage: DataLineage[] = [
      {
        field: 'revenue',
        sources: validatedData.revenue.sources,
        transformations: ['extraction', 'validation', 'weighted_average'],
        timestamp: new Date().toISOString(),
        confidence: validatedData.revenue.confidence
      },
      {
        field: 'valuation',
        sources: validatedData.valuation.sources,
        transformations: ['extraction', 'validation', 'cross_reference'],
        timestamp: new Date().toISOString(),
        confidence: validatedData.valuation.confidence
      }
    ];

    // Store high-quality data for future use
    await storeEnhancedData(company, validatedData, enrichedData);

    const pipeline: DataQualityPipeline = {
      raw_data: rawData,
      validated_data: validatedData,
      enriched_data: enrichedData,
      confidence_scores: confidenceScores,
      data_lineage: dataLineage
    };

    return NextResponse.json({
      success: true,
      company,
      sector,
      pipeline,
      summary: {
        revenue: validatedData.revenue.value,
        valuation: validatedData.valuation.value,
        implied_multiple: validatedData.valuation.value / validatedData.revenue.value,
        comparables_count: enrichedData.comparables.length,
        confidence: confidenceScores.overall,
        top_exit_scenario: enrichedData.exit_scenarios[0]
      }
    });

  } catch (error) {
    console.error('Enhanced data pipeline error:', error);
    return NextResponse.json(
      { error: 'Pipeline failed', details: error instanceof Error ? error.message : 'Unknown error' },
      { status: 500 }
    );
  }
}

// Calculate overall confidence
function calculateOverallConfidence(validatedData: ValidatedData, enrichedData: EnrichedData): number {
  const weights = {
    revenue: 0.3,
    valuation: 0.3,
    comparables: 0.2,
    market: 0.2
  };

  let confidence = 0;
  confidence += validatedData.revenue.confidence * weights.revenue;
  confidence += validatedData.valuation.confidence * weights.valuation;
  confidence += (enrichedData.comparables.length > 5 ? 0.8 : 0.4) * weights.comparables;
  confidence += 0.7 * weights.market; // Base market confidence

  return Math.min(confidence, 1.0);
}

// Store enhanced data for future use
async function storeEnhancedData(company: string, validatedData: ValidatedData, enrichedData: EnrichedData): Promise<void> {
  try {
    await supabase
      .from('enhanced_company_data')
      .upsert({
        company,
        revenue: validatedData.revenue.value,
        revenue_confidence: validatedData.revenue.confidence,
        valuation: validatedData.valuation.value,
        valuation_confidence: validatedData.valuation.confidence,
        growth_rate: validatedData.growth_rate.value,
        burn_rate: validatedData.burn_rate.value,
        runway_months: validatedData.runway.value,
        market_size: validatedData.market_size.value,
        comparables: enrichedData.comparables,
        market_multiples: enrichedData.market_multiples,
        exit_scenarios: enrichedData.exit_scenarios,
        risk_factors: enrichedData.risk_factors,
        updated_at: new Date()
      });
  } catch (error) {
    console.error('Failed to store enhanced data:', error);
  }
}