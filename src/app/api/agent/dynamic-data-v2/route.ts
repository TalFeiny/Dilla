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

// Helper to format currency
function formatCurrency(value: number): string {
  if (value >= 1e9) return `$${(value / 1e9).toFixed(1)}B`;
  if (value >= 1e6) return `$${(value / 1e6).toFixed(1)}M`;
  if (value >= 1e3) return `$${(value / 1e3).toFixed(0)}K`;
  return `$${value.toLocaleString()}`;
}

// Search web with Tavily - enhanced for dynamic market data
async function searchWeb(query: string, date: string = 'August 25, 2025') {
  try {
    // Dynamic query enhancement based on context
    let enhancedQuery = query;
    
    // Add context for better results - focus on current market dynamics
    if (query.toLowerCase().includes('companies') || query.toLowerCase().includes('startup')) {
      enhancedQuery = `${query} "market data" "revenue" "growth" "funding" "latest metrics" list`;
    } else if (query.toLowerCase().includes('market')) {
      enhancedQuery = `${query} "market trends" "growth rate" "market size" "TAM" "competition" analysis`;
    } else if (query.toLowerCase().includes('sector') || query.toLowerCase().includes('industry')) {
      enhancedQuery = `${query} "industry analysis" "market leaders" "growth" "trends" companies list`;
    } else {
      // Default enhancement for any query
      enhancedQuery = `${query} "market data" "financial metrics" "performance" "growth" analysis`;
    }
    
    // Add fresh date context - focus on recent data
    enhancedQuery = `${enhancedQuery} 2024 2025 "real-time" "current" "latest" "recent update"`;
    
    const response = await fetch('https://api.tavily.com/search', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        api_key: process.env.TAVILY_API_KEY,
        query: enhancedQuery,
        search_depth: 'advanced',
        max_results: 20, // Increase from 10 to 20
        include_answer: true,
        include_raw_content: true,
        include_domains: [
          'techcrunch.com',
          'crunchbase.com',
          'pitchbook.com',
          'bloomberg.com',
          'reuters.com',
          'wsj.com',
          'ft.com',
          'forbes.com',
          'businessinsider.com',
          'seekingalpha.com',
          'marketwatch.com',
          'yahoo.com',
          'cnbc.com',
          'dealroom.co',
          'cbinsights.com',
          'venturebeat.com'
        ]
      })
    });

    if (response.ok) {
      return await response.json();
    }
  } catch (error) {
    console.error('Web search error:', error);
  }
  return null;
}

// Use Claude to extract structured company data from web results
async function extractCompaniesWithClaude(webResults: any, userQuery: string) {
  if (!webResults || !webResults.results) return { companies: [], citations: {} };

  // Combine all content for Claude to analyze
  const combinedContent = webResults.results.map((r: any) => ({
    url: r.url,
    title: r.title,
    content: r.content,
    published: r.published_date
  }));

  const prompt = `Analyze these web search results and extract information about companies mentioned.
User is searching for: "${userQuery}"

Web search results:
${JSON.stringify(combinedContent, null, 2)}

Extract real companies and their CURRENT market dynamics. Dynamically include ALL relevant data you find.
Return JSON with this structure:
{
  "companies": [
    {
      "name": "Company Name",
      "sector": "string",
      "revenue": number or null,
      "funding": number or null,
      "valuation": number or null,
      "growth_rate": number (as decimal, e.g. 0.5 for 50%) or null,
      "employees": number or null,
      "market_position": "leader|challenger|emerging|niche",
      "momentum": "accelerating|steady|slowing|pivoting",
      "products": "key products/services" or null,
      "customers": "notable customers" or null,
      "competitors": ["list of main competitors"] or null,
      "recent_news": "latest developments" or null,
      "key_metrics": {
        "any_metric_you_find": "value",
        "arr": "if available",
        "burn_rate": "if available",
        "runway": "if available",
        "market_share": "if available"
      },
      "citations": [
        {
          "url": "source url",
          "title": "article title",
          "excerpt": "relevant quote about this company",
          "date": "publication date"
        }
      ]
    }
  ]
}

Focus on finding:
1. Real companies with actual market presence
2. Current financial and operational metrics
3. Market dynamics and competitive positioning
4. Growth trajectories and market opportunities
5. Innovation indicators and strategic moves
6. Fresh data from 2024-2025

Return ONLY the JSON, no explanation.`;

  try {
    const response = await anthropic.messages.create({
      model: 'claude-3-5-sonnet-20241022',
      max_tokens: 4000,
      temperature: 0,
      messages: [{
        role: 'user',
        content: prompt
      }]
    });

    const content = response.content[0].type === 'text' ? response.content[0].text : '{}';
    const parsed = JSON.parse(content);
    
    // Build citations map
    const citations: Record<string, any[]> = {};
    for (const company of (parsed.companies || [])) {
      if (company.citations) {
        citations[company.name] = company.citations.map((c: any) => ({
          id: `cite_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
          title: c.title,
          url: c.url,
          source: new URL(c.url).hostname.replace('www.', ''),
          date: c.date || 'August 25, 2025',
          excerpt: c.excerpt
        }));
      }
    }
    
    return {
      companies: parsed.companies || [],
      citations
    };
  } catch (error) {
    console.error('Claude extraction error:', error);
    return { companies: [], citations: {} };
  }
}

export async function POST(request: NextRequest) {
  try {
    const { query, includesCitations = true, date = 'August 25, 2025' } = await request.json();

    // Initialize response with base columns
    const baseColumns = [
      { id: 'company', name: 'Company', type: 'text', width: 200 },
      { id: 'sector', name: 'Sector', type: 'text', width: 150 }
    ];
    
    // Dynamically add columns based on query context
    const dynamicColumns: any[] = [];
    
    // Analyze query to determine what columns to show
    const queryLower = query.toLowerCase();
    
    // Market dynamics columns
    if (queryLower.includes('market') || queryLower.includes('position') || queryLower.includes('competitive')) {
      dynamicColumns.push(
        { id: 'market_position', name: 'Market Position', type: 'text', width: 130 },
        { id: 'momentum', name: 'Momentum', type: 'text', width: 120 }
      );
    }
    
    // Financial columns
    if (queryLower.includes('revenue') || queryLower.includes('financial') || !queryLower.includes('exclude')) {
      dynamicColumns.push({ id: 'revenue', name: 'Revenue', type: 'currency', width: 120 });
    }
    
    if (queryLower.includes('growth') || queryLower.includes('growing')) {
      dynamicColumns.push({ id: 'growth', name: 'Growth Rate', type: 'percentage', width: 100 });
    }
    
    if (queryLower.includes('funding') || queryLower.includes('investment') || queryLower.includes('raised')) {
      dynamicColumns.push({ id: 'funding', name: 'Total Funding', type: 'currency', width: 120 });
    }
    
    if (queryLower.includes('valuation') || queryLower.includes('valued')) {
      dynamicColumns.push({ id: 'valuation', name: 'Valuation', type: 'currency', width: 120 });
    }
    
    // Special interest columns
    if (queryLower.includes('employee') || queryLower.includes('team') || queryLower.includes('headcount')) {
      dynamicColumns.push({ id: 'employees', name: 'Employees', type: 'number', width: 100 });
    }
    
    if (queryLower.includes('product') || queryLower.includes('technology')) {
      dynamicColumns.push({ id: 'products', name: 'Key Products', type: 'text', width: 200 });
    }
    
    if (queryLower.includes('customer') || queryLower.includes('client')) {
      dynamicColumns.push({ id: 'customers', name: 'Key Customers', type: 'text', width: 200 });
    }
    
    // Default columns if none specifically requested
    if (dynamicColumns.length === 0) {
      dynamicColumns.push(
        { id: 'market_position', name: 'Market Position', type: 'text', width: 130 },
        { id: 'revenue', name: 'Revenue', type: 'currency', width: 120 },
        { id: 'growth', name: 'Growth', type: 'percentage', width: 100 },
        { id: 'funding', name: 'Total Funding', type: 'currency', width: 120 },
        { id: 'valuation', name: 'Valuation', type: 'currency', width: 120 }
      );
    }
    
    // Always add key metrics at the end for additional data
    dynamicColumns.push({ id: 'key_metrics', name: 'Additional Data', type: 'json', width: 250 });
    
    const response: any = {
      columns: [...baseColumns, ...dynamicColumns],
      rows: [],
      sources: []
    };

    // Only use database as a supplementary source, not primary
    let dbCompanies = [];
    
    // Only query database if explicitly requested or for specific company lookups
    if (query.toLowerCase().includes('portfolio') || query.toLowerCase().includes('our companies')) {
      const dbQuery = supabase.from('companies').select('*');
      const { data } = await dbQuery.limit(10);
      dbCompanies = data || [];
    }
    
    // Search web for real-time data
    const webResults = await searchWeb(query, date);
    
    // Use Claude to extract structured company data
    const { companies: webCompanies, citations } = await extractCompaniesWithClaude(webResults, query);
    
    // Add web sources
    if (webResults?.results) {
      const uniqueSources = new Set(webResults.results.map((r: any) => new URL(r.url).hostname));
      uniqueSources.forEach(source => {
        response.sources.push({
          type: 'web',
          name: source.replace('www.', ''),
          lastUpdated: date,
          reliability: 0.95
        });
      });
    }
    
    // Add database source if we have results
    if (dbCompanies && dbCompanies.length > 0) {
      response.sources.push({
        type: 'database',
        name: 'Company Database',
        lastUpdated: date,
        reliability: 1.0
      });
    }
    
    // Combine results - prioritize web data for freshness
    const combinedData = new Map();
    
    // Add web companies first with dynamic fields
    for (const company of webCompanies) {
      const cells: any = {};
      
      // Build cells dynamically based on columns present
      for (const column of response.columns) {
        switch (column.id) {
          case 'company':
            cells.company = {
              id: `company_${company.name}`,
              value: company.name,
              type: 'text',
              citations: citations[company.name] || []
            };
            break;
            
          case 'sector':
            cells.sector = {
              id: `sector_${company.name}`,
              value: company.sector || 'Technology',
              type: 'text'
            };
            break;
            
          case 'market_position':
            cells.market_position = {
              id: `position_${company.name}`,
              value: company.market_position || 'emerging',
              type: 'text',
              displayValue: company.market_position === 'leader' ? '👑 Market Leader' : 
                           company.market_position === 'challenger' ? '🚀 Challenger' : 
                           company.market_position === 'emerging' ? '🌱 Emerging' : '🎯 Niche'
            };
            break;
            
          case 'momentum':
            cells.momentum = {
              id: `momentum_${company.name}`,
              value: company.momentum || 'steady',
              type: 'text',
              displayValue: company.momentum === 'accelerating' ? '📈 Accelerating' : 
                           company.momentum === 'steady' ? '➡️ Steady' : 
                           company.momentum === 'slowing' ? '📉 Slowing' : '🔄 Pivoting'
            };
            break;
            
          case 'revenue':
            cells.revenue = company.revenue ? {
              id: `revenue_${company.name}`,
              value: company.revenue,
              displayValue: formatCurrency(company.revenue),
              type: 'currency',
              citations: citations[company.name] || []
            } : null;
            break;
            
          case 'growth':
            cells.growth = company.growth_rate ? {
              id: `growth_${company.name}`,
              value: company.growth_rate,
              type: 'percentage',
              citations: citations[company.name] || []
            } : null;
            break;
            
          case 'funding':
            cells.funding = company.funding ? {
              id: `funding_${company.name}`,
              value: company.funding,
              displayValue: formatCurrency(company.funding),
              type: 'currency',
              citations: citations[company.name] || []
            } : null;
            break;
            
          case 'valuation':
            cells.valuation = company.valuation ? {
              id: `valuation_${company.name}`,
              value: company.valuation,
              displayValue: formatCurrency(company.valuation),
              type: 'currency',
              citations: citations[company.name] || []
            } : null;
            break;
            
          case 'employees':
            cells.employees = company.employees ? {
              id: `employees_${company.name}`,
              value: company.employees,
              type: 'number',
              citations: citations[company.name] || []
            } : null;
            break;
            
          case 'products':
            cells.products = company.products ? {
              id: `products_${company.name}`,
              value: company.products,
              type: 'text',
              citations: citations[company.name] || []
            } : null;
            break;
            
          case 'customers':
            cells.customers = company.customers ? {
              id: `customers_${company.name}`,
              value: company.customers,
              type: 'text',
              citations: citations[company.name] || []
            } : null;
            break;
            
          case 'key_metrics':
            const allMetrics = {
              ...(company.key_metrics || {}),
              ...(company.recent_news ? { recent_news: company.recent_news } : {}),
              ...(company.competitors ? { competitors: company.competitors.join(', ') } : {})
            };
            
            cells.key_metrics = {
              id: `metrics_${company.name}`,
              value: allMetrics,
              type: 'json',
              displayValue: Object.keys(allMetrics).length > 0 ? 
                Object.entries(allMetrics).slice(0, 3).map(([k, v]) => `${k}: ${v}`).join(' | ') : 
                'Fetching...',
              citations: citations[company.name] || []
            };
            break;
        }
      }
      
      combinedData.set(company.name, {
        id: `row_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
        cells
      });
    }
    
    // Add database companies if not already present (only as supplementary data)
    if (dbCompanies && dbCompanies.length > 0) {
      for (const company of dbCompanies) {
        if (!combinedData.has(company.name)) {
          const cells: any = {};
          
          // Build cells dynamically based on columns present
          for (const column of response.columns) {
            switch (column.id) {
              case 'company':
                cells.company = {
                  id: `company_db_${company.id}`,
                  value: company.name,
                  type: 'text',
                  citations: [{
                    id: `db_cite_${company.id}`,
                    title: 'Portfolio Database',
                    url: '#',
                    source: 'Internal',
                    date: date
                  }]
                };
                break;
                
              case 'sector':
                cells.sector = {
                  id: `sector_db_${company.id}`,
                  value: company.sector || 'Technology',
                  type: 'text'
                };
                break;
                
              case 'market_position':
                cells.market_position = {
                  id: `position_db_${company.id}`,
                  value: 'emerging',
                  type: 'text',
                  displayValue: '🌱 Portfolio Company'
                };
                break;
                
              case 'momentum':
                cells.momentum = {
                  id: `momentum_db_${company.id}`,
                  value: 'steady',
                  type: 'text',
                  displayValue: '➡️ Check Latest'
                };
                break;
                
              case 'revenue':
                cells.revenue = company.current_arr_usd ? {
                  id: `revenue_db_${company.id}`,
                  value: company.current_arr_usd,
                  displayValue: formatCurrency(company.current_arr_usd),
                  type: 'currency',
                  citations: [{
                    id: `db_cite_revenue_${company.id}`,
                    title: 'Database: ARR',
                    url: '#',
                    source: 'Internal',
                    date: date
                  }]
                } : null;
                break;
                
              case 'growth':
                cells.growth = null; // Not available in DB
                break;
                
              case 'funding':
                cells.funding = company.total_funding_usd ? {
                  id: `funding_db_${company.id}`,
                  value: company.total_funding_usd,
                  displayValue: formatCurrency(company.total_funding_usd),
                  type: 'currency',
                  citations: [{
                    id: `db_cite_funding_${company.id}`,
                    title: 'Database: Total Funding',
                    url: '#',
                    source: 'Internal',
                    date: date
                  }]
                } : null;
                break;
                
              case 'valuation':
                cells.valuation = company.last_valuation_usd ? {
                  id: `valuation_db_${company.id}`,
                  value: company.last_valuation_usd,
                  displayValue: formatCurrency(company.last_valuation_usd),
                  type: 'currency',
                  citations: [{
                    id: `db_cite_valuation_${company.id}`,
                    title: 'Database: Last Valuation',
                    url: '#',
                    source: 'Internal',
                    date: date
                  }]
                } : null;
                break;
                
              case 'employees':
                cells.employees = null; // Not available in DB
                break;
                
              case 'products':
                cells.products = null; // Not available in DB
                break;
                
              case 'customers':
                cells.customers = null; // Not available in DB
                break;
                
              case 'key_metrics':
                cells.key_metrics = {
                  id: `metrics_db_${company.id}`,
                  value: { source: 'Portfolio Database', note: 'Check web for latest' },
                  type: 'json',
                  displayValue: 'Portfolio Company',
                  citations: []
                };
                break;
            }
          }
          
          combinedData.set(company.name, {
            id: `row_db_${company.id}`,
            cells
          });
        }
      }
    }
    
    // Convert to array
    response.rows = Array.from(combinedData.values()).slice(0, 50);
    
    // Add metadata
    response.metadata = {
      query,
      date,
      totalResults: combinedData.size,
      extractedByAI: true
    };
    
    return NextResponse.json(response);
    
  } catch (error) {
    console.error('Dynamic data v2 error:', error);
    return NextResponse.json(
      { error: 'Failed to fetch and process data' },
      { status: 500 }
    );
  }
}