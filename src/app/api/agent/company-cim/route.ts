import { NextRequest, NextResponse } from 'next/server';
import { companyCIMScraper } from '@/lib/company-cim-scraper';
import { createClient } from '@supabase/supabase-js';
import Anthropic from '@anthropic-ai/sdk';

const supabase = createClient(
  process.env.NEXT_PUBLIC_SUPABASE_URL!,
  process.env.SUPABASE_SERVICE_ROLE_KEY!
);

const anthropic = new Anthropic({
  apiKey: process.env.CLAUDE_API_KEY!,
});

const TAVILY_API_KEY = process.env.TAVILY_API_KEY;
const FIRECRAWL_API_KEY = process.env.FIRECRAWL_API_KEY;

export async function POST(request: NextRequest) {
  try {
    const { company_name, company_url, refresh = false, message, sessionId } = await request.json();
    
    if (!company_name && !message) {
      return NextResponse.json({ error: 'Company name or message is required' }, { status: 400 });
    }
    
    // Extract company name from message if needed
    const targetCompany = company_name || message?.match(/@?(\w+)/)?.[1] || message;
    console.log(`🎯 Comprehensive analysis for: ${targetCompany}`);
    
    // Step 1: Check RL experience for similar queries
    let rlContext = null;
    if (sessionId) {
      try {
        const rlResponse = await fetch(`${request.url.replace('/company-cim', '/rl-experience/match')}`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            state: { company: targetCompany, action: 'company_analysis' },
            modelType: 'CIM'
          })
        });
        if (rlResponse.ok) {
          const rlData = await rlResponse.json();
          if (rlData.matches?.length > 0) {
            rlContext = rlData.matches[0];
            console.log('📚 Found RL experience for similar company analysis');
          }
        }
      } catch (error) {
        console.log('RL lookup failed, continuing without it');
      }
    }
    
    // Step 2: Parallel data gathering
    const dataPromises = [];
    
    // 2a. Database lookup
    dataPromises.push(
      supabase
        .from('companies')
        .select('*')
        .or(`name.ilike.%${targetCompany}%,description.ilike.%${targetCompany}%`)
        .limit(1)
        .single()
        .then(({ data, error }) => ({ source: 'database', data, error }))
    );
    
    // 2b. Latest news articles (past 30 days)
    if (TAVILY_API_KEY) {
      dataPromises.push(
        fetch('https://api.tavily.com/search', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            api_key: TAVILY_API_KEY,
            query: `"${targetCompany}" latest news funding announcement ${new Date().getFullYear()}`,
            search_depth: 'advanced',
            max_results: 10,
            include_answer: true,
            include_raw_content: true,
            days: 30 // Last 30 days
          })
        })
        .then(r => r.json())
        .then(data => ({ source: 'news', data }))
        .catch(error => ({ source: 'news', error }))
      );
    }
    
    // 2c. Company website scraping
    if (FIRECRAWL_API_KEY && company_url) {
      dataPromises.push(
        fetch('https://api.firecrawl.dev/v0/scrape', {
          method: 'POST',
          headers: {
            'Authorization': `Bearer ${FIRECRAWL_API_KEY}`,
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({
            url: company_url,
            pageOptions: {
              onlyMainContent: true
            }
          })
        })
        .then(r => r.json())
        .then(data => ({ source: 'website', data }))
        .catch(error => ({ source: 'website', error }))
      );
    }
    
    // 2d. Market analysis
    dataPromises.push(
      fetch('https://api.tavily.com/search', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          api_key: TAVILY_API_KEY,
          query: `"${targetCompany}" competitors market share industry analysis`,
          search_depth: 'basic',
          max_results: 5,
          include_answer: true
        })
      })
      .then(r => r.json())
      .then(data => ({ source: 'market', data }))
      .catch(error => ({ source: 'market', error }))
    );
    
    // Execute all data gathering in parallel
    const results = await Promise.all(dataPromises);
    
    // Step 3: Generate comprehensive CIM with all data
    const dbResult = results.find(r => r.source === 'database') as any;
    const newsResult = results.find(r => r.source === 'news') as any;
    const websiteResult = results.find(r => r.source === 'website') as any;
    const marketResult = results.find(r => r.source === 'market') as any;
    
    const allData = {
      database: dbResult?.data,
      news: newsResult?.data,
      website: websiteResult?.data,
      market: marketResult?.data,
      rlContext
    };
    
    // Step 4: Use Claude to synthesize comprehensive response
    let comprehensiveResponse = '';
    
    if (process.env.CLAUDE_API_KEY) {
      const prompt = `Create a comprehensive company profile for ${targetCompany} using all available data.

DATA SOURCES:

1. DATABASE:
${JSON.stringify(allData.database, null, 2).substring(0, 2000)}

2. LATEST NEWS (Past 30 days):
${allData.news?.answer || 'No recent news'}
${allData.news?.results?.map((r: any) => `- ${r.title}: ${r.content?.substring(0, 200)}`).join('\n')}

3. WEBSITE DATA:
${allData.website?.data?.content?.substring(0, 3000) || 'No website data'}

4. MARKET ANALYSIS:
${allData.market?.answer || 'No market data'}

${rlContext ? `5. PREVIOUS ANALYSIS PATTERNS:\n${JSON.stringify(rlContext, null, 2).substring(0, 1000)}` : ''}

Create a comprehensive response with:
1. Company Overview
2. Recent Developments (last 30 days)
3. Financial Metrics
4. Market Position
5. Key People
6. Investment Thesis

IMPORTANT: Include [Source: X] citations for every claim. Use actual dates when available.`;
      
      const response = await anthropic.messages.create({
        model: 'claude-3-5-sonnet-20241022',
        max_tokens: 3000,
        messages: [{ role: 'user', content: prompt }]
      });
      
      comprehensiveResponse = response.content[0].type === 'text' ? response.content[0].text : '';
    }
    
    // Step 5: Store RL experience
    if (sessionId && comprehensiveResponse) {
      try {
        await fetch(`${request.url.replace('/company-cim', '/rl-experience')}`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            sessionId,
            state: { company: targetCompany, query: message },
            action: 'comprehensive_analysis',
            reward: 0.8, // High reward for successful comprehensive analysis
            nextState: { analysisComplete: true },
            modelType: 'CIM'
          })
        });
      } catch (error) {
        console.log('Failed to store RL experience');
      }
    }
    
    return NextResponse.json({
      success: true,
      response: comprehensiveResponse || 'Analysis complete',
      cim: allData,
      sources: {
        database: !!allData.database,
        news: allData.news?.results?.length || 0,
        website: !!allData.website?.data,
        market: !!allData.market?.answer
      },
      metadata: {
        company: targetCompany,
        timestamp: new Date().toISOString(),
        usedRL: !!rlContext
      }
    });
    
  } catch (error) {
    console.error('Company CIM generation error:', error);
    return NextResponse.json(
      { 
        error: 'Failed to generate company CIM', 
        details: error instanceof Error ? error.message : 'Unknown error' 
      },
      { status: 500 }
    );
  }
}

export async function GET(request: NextRequest) {
  try {
    const searchParams = request.nextUrl.searchParams;
    const company_name = searchParams.get('company_name');
    
    if (!company_name) {
      // Return list of available CIMs
      const { data: cims } = await supabase
        .from('company_cims')
        .select('company_name, website_url, data_quality_score, created_at')
        .order('created_at', { ascending: false })
        .limit(50);
      
      return NextResponse.json({
        success: true,
        cims: cims || []
      });
    }
    
    // Get specific company CIM
    const { data: cim } = await supabase
      .from('company_cims')
      .select('*')
      .eq('company_name', company_name)
      .order('created_at', { ascending: false })
      .limit(1)
      .single();
    
    if (!cim) {
      return NextResponse.json(
        { error: 'CIM not found for this company' },
        { status: 404 }
      );
    }
    
    return NextResponse.json({
      success: true,
      cim: cim.cim_data,
      metadata: {
        created_at: cim.created_at,
        data_quality_score: cim.data_quality_score
      }
    });
    
  } catch (error) {
    console.error('Error retrieving CIM:', error);
    return NextResponse.json(
      { 
        error: 'Failed to retrieve CIM', 
        details: error instanceof Error ? error.message : 'Unknown error' 
      },
      { status: 500 }
    );
  }
}