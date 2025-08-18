import { NextRequest, NextResponse } from 'next/server';
import Anthropic from '@anthropic-ai/sdk';

const anthropic = new Anthropic({
  apiKey: process.env.CLAUDE_API_KEY!,
});

// Data source configuration with API access patterns
interface DataSourceConfig {
  provider: string;
  type: 'api' | 'web_scrape' | 'hybrid';
  reliability: number;
  cost: 'free' | 'low' | 'medium' | 'high';
  api_config?: APIConfig;
  web_config?: WebConfig;
}

interface APIConfig {
  base_url: string;
  auth_type: 'api_key' | 'oauth' | 'basic';
  rate_limit: number;
  requires_key: boolean;
  key_env_var?: string;
}

interface WebConfig {
  search_via: 'tavily' | 'serper' | 'brave' | 'you';
  domains: string[];
  selectors?: Record<string, string>;
}

// Available data sources ranked by quality
const DATA_SOURCES: DataSourceConfig[] = [
  // Tier 1: Direct API Access (Best Quality)
  {
    provider: 'PitchBook',
    type: 'api',
    reliability: 0.95,
    cost: 'high',
    api_config: {
      base_url: 'https://api.pitchbook.com/v1',
      auth_type: 'api_key',
      rate_limit: 100,
      requires_key: true,
      key_env_var: 'PITCHBOOK_API_KEY'
    }
  },
  {
    provider: 'Crunchbase',
    type: 'api',
    reliability: 0.90,
    cost: 'medium',
    api_config: {
      base_url: 'https://api.crunchbase.com/v4',
      auth_type: 'api_key',
      rate_limit: 200,
      requires_key: true,
      key_env_var: 'CRUNCHBASE_API_KEY'
    }
  },
  {
    provider: 'CB Insights',
    type: 'api',
    reliability: 0.92,
    cost: 'high',
    api_config: {
      base_url: 'https://api.cbinsights.com/v1',
      auth_type: 'api_key',
      rate_limit: 50,
      requires_key: true,
      key_env_var: 'CBINSIGHTS_API_KEY'
    }
  },
  
  // Tier 2: Financial Data APIs
  {
    provider: 'Alpha Vantage',
    type: 'api',
    reliability: 0.85,
    cost: 'free',
    api_config: {
      base_url: 'https://www.alphavantage.co/query',
      auth_type: 'api_key',
      rate_limit: 5, // 5 per minute for free tier
      requires_key: true,
      key_env_var: 'ALPHA_VANTAGE_API_KEY'
    }
  },
  {
    provider: 'Yahoo Finance',
    type: 'api',
    reliability: 0.80,
    cost: 'free',
    api_config: {
      base_url: 'https://query2.finance.yahoo.com/v10',
      auth_type: 'basic',
      rate_limit: 100,
      requires_key: false
    }
  },
  {
    provider: 'IEX Cloud',
    type: 'api',
    reliability: 0.88,
    cost: 'low',
    api_config: {
      base_url: 'https://cloud.iexapis.com/stable',
      auth_type: 'api_key',
      rate_limit: 100,
      requires_key: true,
      key_env_var: 'IEX_CLOUD_API_KEY'
    }
  },
  
  // Tier 3: Alternative Data APIs
  {
    provider: 'Clearbit',
    type: 'api',
    reliability: 0.82,
    cost: 'medium',
    api_config: {
      base_url: 'https://company.clearbit.com/v2',
      auth_type: 'api_key',
      rate_limit: 600,
      requires_key: true,
      key_env_var: 'CLEARBIT_API_KEY'
    }
  },
  {
    provider: 'Diffbot',
    type: 'api',
    reliability: 0.78,
    cost: 'medium',
    api_config: {
      base_url: 'https://api.diffbot.com/v3',
      auth_type: 'api_key',
      rate_limit: 25,
      requires_key: true,
      key_env_var: 'DIFFBOT_API_KEY'
    }
  },
  
  // Tier 4: Web Scraping via Search APIs (Tavily is good here)
  {
    provider: 'Tavily Enhanced',
    type: 'hybrid',
    reliability: 0.75,
    cost: 'low',
    web_config: {
      search_via: 'tavily',
      domains: [
        'pitchbook.com',
        'cbinsights.com',
        'crunchbase.com',
        'techcrunch.com',
        'bloomberg.com',
        'reuters.com',
        'seekingalpha.com',
        'yahoo.com/finance'
      ]
    }
  },
  {
    provider: 'Serper',
    type: 'web_scrape',
    reliability: 0.73,
    cost: 'low',
    api_config: {
      base_url: 'https://google.serper.dev/search',
      auth_type: 'api_key',
      rate_limit: 100,
      requires_key: true,
      key_env_var: 'SERPER_API_KEY'
    }
  },
  {
    provider: 'Brave Search',
    type: 'web_scrape',
    reliability: 0.70,
    cost: 'free',
    api_config: {
      base_url: 'https://api.search.brave.com/res/v1',
      auth_type: 'api_key',
      rate_limit: 2000,
      requires_key: true,
      key_env_var: 'BRAVE_SEARCH_API_KEY'
    }
  },
  {
    provider: 'You.com',
    type: 'web_scrape',
    reliability: 0.72,
    cost: 'low',
    api_config: {
      base_url: 'https://api.you.com/search',
      auth_type: 'api_key',
      rate_limit: 100,
      requires_key: true,
      key_env_var: 'YOU_API_KEY'
    }
  },
  
  // Tier 5: Secondary Market Data
  {
    provider: 'Forge',
    type: 'api',
    reliability: 0.85,
    cost: 'high',
    api_config: {
      base_url: 'https://api.forge.com/v1',
      auth_type: 'oauth',
      rate_limit: 50,
      requires_key: true,
      key_env_var: 'FORGE_CLIENT_ID'
    }
  },
  {
    provider: 'EquityZen',
    type: 'web_scrape',
    reliability: 0.80,
    cost: 'medium',
    web_config: {
      search_via: 'tavily',
      domains: ['equityzen.com']
    }
  }
];

// Fetch data using direct API
async function fetchViaAPI(source: DataSourceConfig, query: any): Promise<any> {
  if (!source.api_config) return null;
  
  const apiKey = source.api_config.key_env_var ? 
    process.env[source.api_config.key_env_var] : null;
  
  if (source.api_config.requires_key && !apiKey) {
    console.log(`Skipping ${source.provider}: API key not configured`);
    return null;
  }

  try {
    // Provider-specific API calls
    switch (source.provider) {
      case 'Crunchbase':
        return await fetchCrunchbase(apiKey!, query);
      
      case 'Alpha Vantage':
        return await fetchAlphaVantage(apiKey!, query);
      
      case 'Yahoo Finance':
        return await fetchYahooFinance(query);
      
      case 'IEX Cloud':
        return await fetchIEXCloud(apiKey!, query);
      
      case 'Clearbit':
        return await fetchClearbit(apiKey!, query);
      
      default:
        return null;
    }
  } catch (error) {
    console.error(`API fetch failed for ${source.provider}:`, error);
    return null;
  }
}

// Crunchbase API integration
async function fetchCrunchbase(apiKey: string, query: any): Promise<any> {
  const response = await fetch(
    `https://api.crunchbase.com/v4/entities/organizations/${query.company}?user_key=${apiKey}`,
    {
      headers: {
        'Content-Type': 'application/json'
      }
    }
  );
  
  if (!response.ok) return null;
  
  const data = await response.json();
  
  return {
    name: data.properties.name,
    valuation: data.properties.valuation_amount,
    revenue: data.properties.revenue_range,
    funding_total: data.properties.funding_total,
    last_funding: data.properties.last_funding_at,
    employees: data.properties.num_employees_enum,
    founded: data.properties.founded_on,
    source: 'Crunchbase API'
  };
}

// Alpha Vantage for public company data
async function fetchAlphaVantage(apiKey: string, query: any): Promise<any> {
  if (!query.ticker) return null;
  
  const response = await fetch(
    `https://www.alphavantage.co/query?function=OVERVIEW&symbol=${query.ticker}&apikey=${apiKey}`
  );
  
  if (!response.ok) return null;
  
  const data = await response.json();
  
  return {
    name: data.Name,
    market_cap: parseFloat(data.MarketCapitalization),
    revenue: parseFloat(data.RevenueTTM),
    ebitda: parseFloat(data.EBITDA),
    pe_ratio: parseFloat(data.PERatio),
    growth_rate: parseFloat(data.QuarterlyRevenueGrowthYOY),
    source: 'Alpha Vantage API'
  };
}

// Yahoo Finance (no key required)
async function fetchYahooFinance(query: any): Promise<any> {
  if (!query.ticker) return null;
  
  const response = await fetch(
    `https://query2.finance.yahoo.com/v10/finance/quoteSummary/${query.ticker}?modules=financialData,defaultKeyStatistics`
  );
  
  if (!response.ok) return null;
  
  const data = await response.json();
  const result = data.quoteSummary.result[0];
  
  return {
    ticker: query.ticker,
    market_cap: result.defaultKeyStatistics?.marketCap?.raw,
    revenue: result.financialData?.totalRevenue?.raw,
    ebitda: result.financialData?.ebitda?.raw,
    current_price: result.financialData?.currentPrice?.raw,
    source: 'Yahoo Finance API'
  };
}

// IEX Cloud
async function fetchIEXCloud(apiKey: string, query: any): Promise<any> {
  if (!query.ticker) return null;
  
  const response = await fetch(
    `https://cloud.iexapis.com/stable/stock/${query.ticker}/stats?token=${apiKey}`
  );
  
  if (!response.ok) return null;
  
  const data = await response.json();
  
  return {
    ticker: query.ticker,
    market_cap: data.marketcap,
    revenue: data.revenue,
    pe_ratio: data.peRatio,
    week52_high: data.week52high,
    week52_low: data.week52low,
    source: 'IEX Cloud API'
  };
}

// Clearbit for company enrichment
async function fetchClearbit(apiKey: string, query: any): Promise<any> {
  if (!query.domain) return null;
  
  const response = await fetch(
    `https://company.clearbit.com/v2/companies/find?domain=${query.domain}`,
    {
      headers: {
        'Authorization': `Bearer ${apiKey}`
      }
    }
  );
  
  if (!response.ok) return null;
  
  const data = await response.json();
  
  return {
    name: data.name,
    employees: data.metrics.employees,
    revenue: data.metrics.estimatedAnnualRevenue,
    funding: data.metrics.raised,
    tags: data.tags,
    industry: data.category.industry,
    source: 'Clearbit API'
  };
}

// Fetch via web search (Tavily or alternatives)
async function fetchViaWeb(source: DataSourceConfig, query: any): Promise<any> {
  if (!source.web_config) return null;
  
  switch (source.web_config.search_via) {
    case 'tavily':
      return await searchViaTavily(query, source.web_config.domains);
    
    case 'serper':
      return await searchViaSerper(query, source.web_config.domains);
    
    case 'brave':
      return await searchViaBrave(query, source.web_config.domains);
    
    case 'you':
      return await searchViaYou(query, source.web_config.domains);
    
    default:
      return null;
  }
}

// Tavily search
async function searchViaTavily(query: any, domains: string[]): Promise<any> {
  const tavilyKey = process.env.TAVILY_API_KEY;
  if (!tavilyKey) return null;
  
  const searchQuery = `${query.company} ${query.metrics || 'valuation revenue funding'} site:${domains.join(' OR site:')}`;
  
  const response = await fetch('https://api.tavily.com/search', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      api_key: tavilyKey,
      query: searchQuery,
      search_depth: 'advanced',
      max_results: 10,
      include_answer: true,
      include_raw_content: true
    })
  });
  
  if (!response.ok) return null;
  
  return await response.json();
}

// Serper search (Google results)
async function searchViaSerper(query: any, domains: string[]): Promise<any> {
  const serperKey = process.env.SERPER_API_KEY;
  if (!serperKey) return null;
  
  const response = await fetch('https://google.serper.dev/search', {
    method: 'POST',
    headers: {
      'X-API-KEY': serperKey,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      q: `${query.company} ${query.metrics || 'valuation revenue'}`,
      num: 10
    })
  });
  
  if (!response.ok) return null;
  
  return await response.json();
}

// Brave search
async function searchViaBrave(query: any, domains: string[]): Promise<any> {
  const braveKey = process.env.BRAVE_SEARCH_API_KEY;
  if (!braveKey) return null;
  
  const response = await fetch(
    `https://api.search.brave.com/res/v1/web/search?q=${encodeURIComponent(query.company + ' ' + query.metrics)}`,
    {
      headers: {
        'X-Subscription-Token': braveKey
      }
    }
  );
  
  if (!response.ok) return null;
  
  return await response.json();
}

// You.com search
async function searchViaYou(query: any, domains: string[]): Promise<any> {
  const youKey = process.env.YOU_API_KEY;
  if (!youKey) return null;
  
  const response = await fetch('https://api.you.com/search', {
    method: 'POST',
    headers: {
      'X-API-Key': youKey,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      query: `${query.company} ${query.metrics}`,
      num_results: 10
    })
  });
  
  if (!response.ok) return null;
  
  return await response.json();
}

// Aggregate data from multiple sources
async function aggregateData(query: any): Promise<any> {
  const results = [];
  
  // Try API sources first (higher quality)
  const apiSources = DATA_SOURCES.filter(s => s.type === 'api' || s.type === 'hybrid');
  
  for (const source of apiSources) {
    const data = await fetchViaAPI(source, query);
    if (data) {
      results.push({
        source: source.provider,
        reliability: source.reliability,
        data
      });
    }
  }
  
  // If not enough API data, try web sources
  if (results.length < 3) {
    const webSources = DATA_SOURCES.filter(s => s.type === 'web_scrape' || s.type === 'hybrid');
    
    for (const source of webSources) {
      const data = await fetchViaWeb(source, query);
      if (data) {
        results.push({
          source: source.provider,
          reliability: source.reliability,
          data
        });
      }
    }
  }
  
  return results;
}

// Extract and consolidate metrics using Claude
async function consolidateWithClaude(aggregatedData: any[]): Promise<any> {
  const prompt = `Consolidate these data points into accurate metrics:
${JSON.stringify(aggregatedData, null, 2)}

Weight by reliability score. Return JSON with:
- company_name
- valuation (number)
- revenue (number)
- growth_rate (decimal)
- funding_total (number)
- employees (number)
- confidence_score (0-1)
- sources_used (array)`;

  const response = await anthropic.messages.create({
    model: 'claude-3-5-sonnet-20241022',
    max_tokens: 1000,
    messages: [{ role: 'user', content: prompt }]
  });

  const content = response.content[0].type === 'text' ? response.content[0].text : '';
  const jsonMatch = content.match(/\{[\s\S]*\}/);
  
  return jsonMatch ? JSON.parse(jsonMatch[0]) : null;
}

// Main handler
export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const { company, ticker, domain, metrics = 'all' } = body;
    
    const query = {
      company,
      ticker,
      domain,
      metrics
    };
    
    // Aggregate data from multiple sources
    const aggregatedData = await aggregateData(query);
    
    // Consolidate with Claude
    const consolidated = await consolidateWithClaude(aggregatedData);
    
    return NextResponse.json({
      success: true,
      query,
      sources_checked: aggregatedData.length,
      consolidated_data: consolidated,
      raw_sources: aggregatedData,
      recommendations: {
        best_sources: DATA_SOURCES.filter(s => s.reliability > 0.85).map(s => s.provider),
        missing_apis: DATA_SOURCES.filter(s => 
          s.api_config?.requires_key && 
          s.api_config.key_env_var &&
          !process.env[s.api_config.key_env_var]
        ).map(s => s.provider)
      }
    });
    
  } catch (error) {
    console.error('Data source aggregation error:', error);
    return NextResponse.json(
      { error: 'Failed to aggregate data', details: error instanceof Error ? error.message : 'Unknown error' },
      { status: 500 }
    );
  }
}

// GET endpoint to list available sources
export async function GET() {
  const configured = DATA_SOURCES.map(source => ({
    provider: source.provider,
    type: source.type,
    reliability: source.reliability,
    cost: source.cost,
    configured: source.api_config?.requires_key ? 
      !!process.env[source.api_config.key_env_var!] : true
  }));
  
  return NextResponse.json({
    total_sources: DATA_SOURCES.length,
    configured_count: configured.filter(s => s.configured).length,
    sources: configured,
    recommendations: [
      'For best results, configure Crunchbase or PitchBook API keys',
      'Tavily is good for web scraping but direct APIs provide better data',
      'Consider Alpha Vantage (free) for public company data',
      'Use multiple sources and weight by reliability'
    ]
  });
}