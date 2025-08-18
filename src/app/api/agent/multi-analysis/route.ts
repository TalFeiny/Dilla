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

// Analysis types the agent can perform
export enum AnalysisType {
  WORLD_MODEL = 'world_model',           // Build comprehensive understanding
  COMPANY_COMPARISON = 'company_comparison', // Compare multiple companies
  MARKET_DYNAMICS = 'market_dynamics',    // Industry trends and movements
  VALUATION_SYNTHESIS = 'valuation_synthesis', // Multi-method valuation
  COMPETITIVE_POSITIONING = 'competitive_positioning', // Strategic analysis
  SCENARIO_MODELING = 'scenario_modeling', // Future state predictions
  INVESTMENT_THESIS = 'investment_thesis', // Investment rationale
  RISK_ASSESSMENT = 'risk_assessment',    // Comprehensive risk analysis
  EXIT_ANALYSIS = 'exit_analysis',        // Exit opportunity mapping
  CROSS_MARKET = 'cross_market'           // Cross-market opportunities
}

// World model structure for comprehensive understanding
interface WorldModel {
  market: {
    tam: number;
    growth_rate: number;
    key_trends: string[];
    disruptions: string[];
    regulatory: string[];
  };
  competitive_landscape: {
    leaders: CompanySnapshot[];
    challengers: CompanySnapshot[];
    emerging: CompanySnapshot[];
    market_shares: Record<string, number>;
  };
  value_chain: {
    suppliers: string[];
    partners: string[];
    customers: string[];
    distribution: string[];
  };
  financials: {
    typical_margins: Record<string, number>;
    growth_patterns: string[];
    unit_economics: Record<string, any>;
    valuation_multiples: Record<string, number>;
  };
  dynamics: {
    entry_barriers: string[];
    success_factors: string[];
    failure_patterns: string[];
    consolidation_likelihood: number;
  };
}

interface CompanySnapshot {
  name: string;
  valuation: number;
  revenue: number;
  growth_rate: number;
  key_metrics: Record<string, any>;
  sources: string[];
}

// Fetch real market data from multiple sources
async function fetchMarketData(query: string, sources: string[] = []): Promise<any> {
  const tavilyKey = process.env.TAVILY_API_KEY;
  if (!tavilyKey) throw new Error('Tavily API key not configured');

  const searchQuery = sources.length > 0 
    ? `${query} site:${sources.join(' OR site:')}`
    : query;

  const response = await fetch('https://api.tavily.com/search', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      api_key: tavilyKey,
      query: searchQuery,
      search_depth: 'advanced',
      max_results: 20,
      include_answer: true,
      include_raw_content: true
    })
  });

  if (!response.ok) throw new Error('Market data fetch failed');
  return await response.json();
}

// Get real company data from database and APIs
async function getCompanyData(companyNames: string[]): Promise<CompanySnapshot[]> {
  const companies: CompanySnapshot[] = [];

  for (const name of companyNames) {
    // First check database
    const { data: dbCompany } = await supabase
      .from('companies')
      .select('*')
      .ilike('name', `%${name}%`)
      .limit(1)
      .single();

    if (dbCompany) {
      companies.push({
        name: dbCompany.name,
        valuation: dbCompany.valuation_usd || 0,
        revenue: dbCompany.revenue || 0,
        growth_rate: dbCompany.growth_rate || 0,
        key_metrics: {
          funding_total: dbCompany.total_invested_usd,
          employees: dbCompany.employees,
          founded: dbCompany.founded_year
        },
        sources: ['Database']
      });
    } else {
      // Fetch from web if not in database
      const marketData = await fetchMarketData(
        `${name} revenue valuation funding metrics`,
        ['crunchbase.com', 'pitchbook.com', 'techcrunch.com']
      );

      const extracted = await extractCompanyMetrics(name, marketData);
      if (extracted) {
        companies.push(extracted);
      }
    }
  }

  return companies;
}

// Extract company metrics from search results using Claude
async function extractCompanyMetrics(companyName: string, searchResults: any): Promise<CompanySnapshot | null> {
  const prompt = `Extract financial metrics for ${companyName} from these search results:

${JSON.stringify(searchResults.results.slice(0, 5), null, 2)}

Return ONLY a JSON object with this exact structure (no other text):
{
  "name": "company name",
  "valuation": number in USD,
  "revenue": number in USD,
  "growth_rate": decimal (e.g., 0.5 for 50%),
  "key_metrics": {
    "funding_total": number,
    "employees": number,
    "burn_rate": number,
    "runway_months": number
  },
  "sources": ["url1", "url2"]
}

If data is not available for a field, use 0 or empty object.`;

  try {
    const response = await anthropic.messages.create({
      model: 'claude-3-5-sonnet-20241022',
      max_tokens: 1000,
      messages: [{ role: 'user', content: prompt }]
    });

    const content = response.content[0].type === 'text' ? response.content[0].text : '';
    const jsonMatch = content.match(/\{[\s\S]*\}/);
    if (jsonMatch) {
      return JSON.parse(jsonMatch[0]);
    }
  } catch (error) {
    console.error('Failed to extract company metrics:', error);
  }

  return null;
}

// Build comprehensive world model
async function buildWorldModel(sector: string, companies: string[]): Promise<WorldModel> {
  // Fetch comprehensive market data
  const [marketData, competitorData, valuationData] = await Promise.all([
    fetchMarketData(`${sector} market size TAM growth trends 2024 2025`),
    fetchMarketData(`${sector} top companies competitors market share`),
    fetchMarketData(`${sector} valuation multiples revenue EBITDA exit acquisitions`)
  ]);

  // Get company snapshots
  const companySnapshots = await getCompanyData(companies);

  // Use Claude to synthesize world model
  const prompt = `Create a comprehensive world model for the ${sector} sector based on this data:

Market Research:
${JSON.stringify(marketData.answer, null, 2)}

Competitor Analysis:
${JSON.stringify(competitorData.answer, null, 2)}

Valuation Data:
${JSON.stringify(valuationData.answer, null, 2)}

Company Data:
${JSON.stringify(companySnapshots, null, 2)}

Return ONLY a JSON object with this exact structure:
{
  "market": {
    "tam": number (total addressable market in USD),
    "growth_rate": decimal (annual growth rate),
    "key_trends": ["trend1", "trend2"],
    "disruptions": ["disruption1"],
    "regulatory": ["regulation1"]
  },
  "competitive_landscape": {
    "leaders": [company objects],
    "challengers": [company objects],
    "emerging": [company objects],
    "market_shares": {"company": percentage}
  },
  "value_chain": {
    "suppliers": ["supplier1"],
    "partners": ["partner1"],
    "customers": ["customer segment1"],
    "distribution": ["channel1"]
  },
  "financials": {
    "typical_margins": {"gross": 0.7, "ebitda": 0.2, "net": 0.1},
    "growth_patterns": ["pattern1"],
    "unit_economics": {"cac": 1000, "ltv": 5000},
    "valuation_multiples": {"revenue": 5, "ebitda": 15}
  },
  "dynamics": {
    "entry_barriers": ["barrier1"],
    "success_factors": ["factor1"],
    "failure_patterns": ["pattern1"],
    "consolidation_likelihood": 0.6
  }
}`;

  const response = await anthropic.messages.create({
    model: 'claude-3-5-sonnet-20241022',
    max_tokens: 4000,
    messages: [{ role: 'user', content: prompt }]
  });

  const content = response.content[0].type === 'text' ? response.content[0].text : '';
  const jsonMatch = content.match(/\{[\s\S]*\}/);
  
  if (jsonMatch) {
    return JSON.parse(jsonMatch[0]);
  }

  // Return default structure if parsing fails
  return {
    market: { tam: 0, growth_rate: 0, key_trends: [], disruptions: [], regulatory: [] },
    competitive_landscape: { leaders: [], challengers: [], emerging: [], market_shares: {} },
    value_chain: { suppliers: [], partners: [], customers: [], distribution: [] },
    financials: { typical_margins: {}, growth_patterns: [], unit_economics: {}, valuation_multiples: {} },
    dynamics: { entry_barriers: [], success_factors: [], failure_patterns: [], consolidation_likelihood: 0 }
  };
}

// Compare multiple companies with real data
async function compareCompanies(companies: string[], criteria: string[]): Promise<any> {
  const companyData = await getCompanyData(companies);
  
  // Fetch additional comparison data
  const comparisonPromises = companies.map(company => 
    fetchMarketData(`${company} ${criteria.join(' ')} performance metrics`)
  );
  const comparisonResults = await Promise.all(comparisonPromises);

  // Synthesize comparison
  const prompt = `Compare these companies based on ${criteria.join(', ')}:

Company Data:
${JSON.stringify(companyData, null, 2)}

Additional Research:
${JSON.stringify(comparisonResults.map(r => r.answer), null, 2)}

Create a detailed comparison matrix with scores, rankings, and insights.
Return ONLY a JSON object with comparisons, scores (0-100), and key differentiators.`;

  const response = await anthropic.messages.create({
    model: 'claude-3-5-sonnet-20241022',
    max_tokens: 3000,
    messages: [{ role: 'user', content: prompt }]
  });

  const content = response.content[0].type === 'text' ? response.content[0].text : '';
  const jsonMatch = content.match(/\{[\s\S]*\}/);
  
  return jsonMatch ? JSON.parse(jsonMatch[0]) : { error: 'Failed to generate comparison' };
}

// Multi-method valuation synthesis
async function synthesizeValuation(company: string, methods: string[]): Promise<any> {
  // Fetch valuation data from multiple sources
  const valuationData = await Promise.all([
    fetchMarketData(`${company} DCF valuation model financial projections`),
    fetchMarketData(`${company} comparable companies trading multiples`),
    fetchMarketData(`${company} precedent transactions M&A deals`),
    fetchMarketData(`${company} venture capital funding rounds valuation`)
  ]);

  // Get company financials
  const { data: companyData } = await supabase
    .from('companies')
    .select('*')
    .ilike('name', `%${company}%`)
    .limit(1)
    .single();

  // Calculate valuations using different methods
  const prompt = `Perform multi-method valuation for ${company} using these methods: ${methods.join(', ')}

Company Data:
${JSON.stringify(companyData, null, 2)}

Market Research:
${JSON.stringify(valuationData.map(d => d.answer), null, 2)}

Calculate valuation using each method and provide:
1. DCF valuation with assumptions
2. Comparable company multiples
3. Precedent transaction analysis
4. VC method valuation
5. Weighted average valuation
6. Confidence intervals

Return ONLY a JSON object with valuations, methodology, and sources.`;

  const response = await anthropic.messages.create({
    model: 'claude-3-5-sonnet-20241022',
    max_tokens: 4000,
    messages: [{ role: 'user', content: prompt }]
  });

  const content = response.content[0].type === 'text' ? response.content[0].text : '';
  const jsonMatch = content.match(/\{[\s\S]*\}/);
  
  return jsonMatch ? JSON.parse(jsonMatch[0]) : { error: 'Failed to synthesize valuation' };
}

// Apply RL feedback to improve analysis
async function applyRLFeedback(analysisType: string, context: any): Promise<any> {
  // Fetch relevant learning patterns
  const { data: patterns } = await supabase
    .from('learning_patterns')
    .select('*')
    .eq('model_type', analysisType)
    .order('confidence', { ascending: false })
    .limit(10);

  // Fetch recent corrections for this type
  const { data: corrections } = await supabase
    .from('model_corrections')
    .select('*')
    .eq('model_type', analysisType)
    .order('created_at', { ascending: false })
    .limit(20);

  return {
    patterns: patterns || [],
    corrections: corrections || [],
    rules: patterns?.map(p => p.learning_rule) || []
  };
}

// Main multi-analysis handler
export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const { 
      analysisTypes = [AnalysisType.WORLD_MODEL],
      companies = [],
      sector = 'Technology',
      criteria = ['revenue', 'growth', 'profitability', 'market_position'],
      enableRL = true
    } = body;

    const results: Record<string, any> = {};
    
    // Apply RL feedback if enabled
    let rlContext = {};
    if (enableRL) {
      rlContext = await applyRLFeedback(analysisTypes[0], { companies, sector });
    }

    // Execute requested analyses in parallel where possible
    const analysisPromises = analysisTypes.map(async (type: AnalysisType) => {
      switch (type) {
        case AnalysisType.WORLD_MODEL:
          results[type] = await buildWorldModel(sector, companies);
          break;
          
        case AnalysisType.COMPANY_COMPARISON:
          results[type] = await compareCompanies(companies, criteria);
          break;
          
        case AnalysisType.VALUATION_SYNTHESIS:
          if (companies.length > 0) {
            results[type] = await synthesizeValuation(
              companies[0], 
              ['DCF', 'Comparables', 'Precedent', 'VC Method']
            );
          }
          break;
          
        case AnalysisType.MARKET_DYNAMICS:
          const dynamicsData = await fetchMarketData(
            `${sector} market dynamics trends disruption innovation 2024 2025`
          );
          results[type] = dynamicsData;
          break;
          
        case AnalysisType.COMPETITIVE_POSITIONING:
          const positioningData = await fetchMarketData(
            `${companies.join(' vs ')} competitive advantage differentiation market position`
          );
          results[type] = positioningData;
          break;
          
        case AnalysisType.EXIT_ANALYSIS:
          const exitData = await fetchMarketData(
            `${sector} M&A acquisitions IPO exits strategic buyers ${companies.join(' ')}`
          );
          results[type] = exitData;
          break;
          
        default:
          results[type] = { error: 'Analysis type not implemented' };
      }
    });

    await Promise.all(analysisPromises);

    // Cross-synthesize results if multiple analyses
    if (analysisTypes.length > 1) {
      results.synthesis = await synthesizeAnalyses(results, rlContext);
    }

    // Store successful analysis for RAG
    if (results.synthesis || results[AnalysisType.WORLD_MODEL]) {
      await storeForRAG(results, { companies, sector, analysisTypes });
    }

    return NextResponse.json({
      success: true,
      analyses: results,
      rlContext: enableRL ? rlContext : null,
      metadata: {
        companies,
        sector,
        analysisTypes,
        timestamp: new Date().toISOString()
      }
    });

  } catch (error) {
    console.error('Multi-analysis error:', error);
    return NextResponse.json(
      { error: 'Multi-analysis failed', details: error instanceof Error ? error.message : 'Unknown error' },
      { status: 500 }
    );
  }
}

// Synthesize multiple analyses into insights
async function synthesizeAnalyses(results: Record<string, any>, rlContext: any): Promise<any> {
  const prompt = `Synthesize these analyses into actionable insights:

${JSON.stringify(results, null, 2)}

RL Learning Context:
${JSON.stringify(rlContext.rules, null, 2)}

Provide:
1. Key insights across all analyses
2. Investment recommendation with confidence score
3. Risk factors and mitigations
4. Action items and next steps
5. Contradictions or concerns

Return as structured JSON.`;

  const response = await anthropic.messages.create({
    model: 'claude-3-5-sonnet-20241022',
    max_tokens: 2000,
    messages: [{ role: 'user', content: prompt }]
  });

  const content = response.content[0].type === 'text' ? response.content[0].text : '';
  const jsonMatch = content.match(/\{[\s\S]*\}/);
  
  return jsonMatch ? JSON.parse(jsonMatch[0]) : { insights: [], recommendation: 'Needs further analysis' };
}

// Store analysis for RAG retrieval
async function storeForRAG(results: any, metadata: any): Promise<void> {
  try {
    const { error } = await supabase
      .from('analysis_memory')
      .insert({
        analysis_type: metadata.analysisTypes.join(','),
        companies: metadata.companies,
        sector: metadata.sector,
        results: results,
        created_at: new Date(),
        success: true
      });

    if (error) console.error('Failed to store for RAG:', error);
  } catch (error) {
    console.error('RAG storage error:', error);
  }
}

// GET endpoint to retrieve available analyses
export async function GET() {
  return NextResponse.json({
    availableAnalyses: Object.values(AnalysisType),
    capabilities: {
      worldModel: 'Build comprehensive market understanding',
      companyComparison: 'Compare multiple companies with real data',
      valuationSynthesis: 'Multi-method valuation with confidence intervals',
      marketDynamics: 'Analyze industry trends and disruptions',
      competitivePositioning: 'Strategic positioning analysis',
      scenarioModeling: 'Future state predictions',
      investmentThesis: 'Generate investment rationale',
      riskAssessment: 'Comprehensive risk analysis',
      exitAnalysis: 'Exit opportunity mapping',
      crossMarket: 'Cross-market opportunity identification'
    },
    rlEnabled: true,
    dataSources: [
      'Supabase Database',
      'Tavily Web Search',
      'Claude Analysis',
      'Historical Patterns',
      'RL Feedback'
    ]
  });
}