import { NextResponse } from 'next/server';
import { createClient } from '@supabase/supabase-js';

const supabase = createClient(
  process.env.NEXT_PUBLIC_SUPABASE_URL!,
  process.env.SUPABASE_SERVICE_ROLE_KEY!
);

const TAVILY_API_KEY = process.env.TAVILY_API_KEY;
const CLAUDE_API_KEY = process.env.CLAUDE_API_KEY;

// Cache for company data (15 minute TTL)
const companyCache = new Map<string, { data: any; timestamp: number }>();
const CACHE_TTL = 15 * 60 * 1000; // 15 minutes

export async function POST(request: Request) {
  try {
    const { message } = await request.json();
    
    // Extract company name from @mention or direct text
    let companyName = '';
    if (message.startsWith('@')) {
      companyName = message.substring(1).trim();
    } else {
      const match = message.match(/(?:@)?([A-Z][\w\s]+)/);
      companyName = match ? match[1].trim() : message.trim();
    }
    
    console.log(`⚡ Fast lookup for: ${companyName}`);
    
    // Check cache first
    const cached = companyCache.get(companyName.toLowerCase());
    if (cached && Date.now() - cached.timestamp < CACHE_TTL) {
      console.log('✅ Using cached data');
      return NextResponse.json({
        response: formatResponse(cached.data, companyName),
        toolsUsed: ['cache'],
        metadata: {
          cached: true,
          company: companyName,
          sources: cached.data.sources
        }
      });
    }
    
    // Parallel data fetching
    const [dbResult, webResult] = await Promise.all([
      // 1. Database lookup
      supabase
        .from('companies')
        .select('*')
        .or(`name.ilike.%${companyName}%,description.ilike.%${companyName}%`)
        .limit(1)
        .single()
        .then(({ data, error }) => ({ data, error })),
      
      // 2. Quick web search (if Tavily available)
      TAVILY_API_KEY ? 
        fetch('https://api.tavily.com/search', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            api_key: TAVILY_API_KEY,
            query: `${companyName} company funding valuation revenue latest news ${new Date().getFullYear()}`,
            search_depth: 'basic', // Use basic for speed
            max_results: 5,
            include_answer: true
          })
        }).then(r => r.json()).catch(() => null) : null
    ]);
    
    // Build response data
    const responseData: any = {
      company: companyName,
      sources: [],
      database: null,
      web: null
    };
    
    // Add database data
    if (dbResult.data) {
      responseData.database = {
        name: dbResult.data.name,
        sector: dbResult.data.sector,
        funding: dbResult.data.total_invested_usd,
        stage: dbResult.data.stage,
        description: dbResult.data.description
      };
      responseData.sources.push({
        type: 'database',
        name: 'Internal Database',
        confidence: 1.0
      });
    }
    
    // Add web search data
    if (webResult && webResult.results) {
      responseData.web = {
        answer: webResult.answer,
        results: webResult.results.slice(0, 3).map((r: any) => ({
          title: r.title,
          snippet: r.content.substring(0, 200),
          url: r.url
        }))
      };
      responseData.sources.push({
        type: 'web',
        name: 'Tavily Search',
        urls: webResult.results.map((r: any) => r.url),
        confidence: 0.8
      });
    }
    
    // Cache the results
    companyCache.set(companyName.toLowerCase(), {
      data: responseData,
      timestamp: Date.now()
    });
    
    // Format response with citations
    const response = formatResponse(responseData, companyName);
    
    return NextResponse.json({
      response,
      toolsUsed: ['database_search', 'web_search'],
      metadata: {
        cached: false,
        company: companyName,
        sources: responseData.sources,
        hasData: !!(responseData.database || responseData.web)
      }
    });
    
  } catch (error) {
    console.error('Fast lookup error:', error);
    return NextResponse.json(
      { error: 'Fast lookup failed', details: error instanceof Error ? error.message : 'Unknown error' },
      { status: 500 }
    );
  }
}

function formatResponse(data: any, companyName: string): string {
  let response = `## ${companyName}\n\n`;
  
  if (data.database) {
    response += `**Company Profile** [Source: Internal Database]\n`;
    response += `- Sector: ${data.database.sector || 'Not specified'}\n`;
    response += `- Total Funding: $${(data.database.funding / 1000000).toFixed(1)}M\n`;
    response += `- Stage: ${data.database.stage || 'Not specified'}\n`;
    if (data.database.description) {
      response += `- Description: ${data.database.description}\n`;
    }
    response += '\n';
  }
  
  if (data.web && data.web.answer) {
    response += `**Latest Information** [Source: Web Search]\n`;
    response += `${data.web.answer}\n\n`;
    
    if (data.web.results && data.web.results.length > 0) {
      response += `**Recent Coverage:**\n`;
      data.web.results.forEach((result: any, idx: number) => {
        response += `${idx + 1}. ${result.title} [Source: ${result.url}]\n`;
        response += `   ${result.snippet}...\n\n`;
      });
    }
  }
  
  if (!data.database && !data.web) {
    response = `No information found for "${companyName}". This company may not be in our database or may be too new/small for web coverage. Try searching with a different name or providing more context.`;
  }
  
  return response;
}