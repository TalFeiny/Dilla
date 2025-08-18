import { NextResponse } from 'next/server';
import { createClient } from '@supabase/supabase-js';
import { firecrawlScraper } from '@/lib/firecrawl-scraper';

const CLAUDE_API_KEY = process.env.CLAUDE_API_KEY;
const TAVILY_API_KEY = process.env.TAVILY_API_KEY;
const FIRECRAWL_API_KEY = process.env.FIRECRAWL_API_KEY;

const supabase = createClient(
  process.env.NEXT_PUBLIC_SUPABASE_URL!,
  process.env.SUPABASE_SERVICE_ROLE_KEY!
);

export async function POST(request: Request) {
  try {
    const { message, history = [], sessionId, useReasoning = true } = await request.json();
    
    if (!message) {
      return NextResponse.json(
        { error: 'Message is required' },
        { status: 400 }
      );
    }
    
    console.log('Agent received message:', message);
    
    // Use multi-step reasoning agent for better research
    if (useReasoning) {
      try {
        const baseUrl = request.url.substring(0, request.url.indexOf('/api'));
        const reasoningResponse = await fetch(`${baseUrl}/api/agent/reasoning-agent`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ message, sessionId })
        });
        
        if (reasoningResponse.ok) {
          const reasoningResult = await reasoningResponse.json();
          console.log('✅ Used multi-step reasoning agent');
          return NextResponse.json(reasoningResult);
        }
      } catch (error) {
        console.error('Reasoning agent failed, falling back:', error);
      }
    }
    
    // Step 1: Check for company mentions using @ or direct reference
    const companyPattern = /@([a-zA-Z0-9]+)|(?:about|for|analyze|research|tell me about)\s+([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)*)/gi;
    const matches = [...message.matchAll(companyPattern)];
    const companies = matches.map(m => m[1] || m[2]).filter(Boolean);
    
    console.log('Detected companies:', companies);
    
    // Initialize data containers
    let companyData: any = null;
    let cimData: any = null;
    let webSearchData: any[] = [];
    let marketIntelligence: any = null;
    
    // Step 2: Gather real data for each company
    if (companies.length > 0) {
      for (const companyName of companies) {
        console.log(`Gathering data for ${companyName}...`);
        
        // 2a. Search internal database
        try {
          const { data: dbCompanies } = await supabase
            .from('companies')
            .select('*')
            .ilike('name', `%${companyName}%`)
            .limit(1);
          
          if (dbCompanies && dbCompanies.length > 0) {
            companyData = dbCompanies[0];
            console.log(`Found ${companyName} in database:`, {
              name: companyData.name,
              sector: companyData.sector,
              funding: companyData.total_invested_usd
            });
          }
        } catch (error) {
          console.error('Database search error:', error);
        }
        
        // 2b. ALWAYS use Firecrawl for deep website scraping
        const shouldScrapeWebsite = true; // Always scrape for any company mention to get real data
        
        if (shouldScrapeWebsite) {
          // Try CIM endpoint which uses Firecrawl internally
          try {
            console.log(`🔥 Using Firecrawl via CIM scraper for ${companyName}...`);
            const baseUrl = request.url.substring(0, request.url.indexOf('/api'));
            const cimResponse = await fetch(`${baseUrl}/api/agent/company-cim`, {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ 
                company_name: companyName,
                refresh: false
              })
            });
            
            if (cimResponse.ok) {
              const cimResult = await cimResponse.json();
              cimData = cimResult.cim;
              console.log(`🔥 Firecrawl/CIM data obtained for ${companyName}`);
              
              // Log what data we got
              if (cimData) {
                console.log('🔥 CIM contains:', {
                  hasOverview: !!cimData.overview,
                  hasFunding: !!cimData.funding,
                  hasTeam: !!cimData.team,
                  hasFinancials: !!cimData.financials,
                  hasMarket: !!cimData.market
                });
              }
            } else {
              console.error('CIM generation failed:', await cimResponse.text());
            }
          } catch (error) {
            console.error('CIM/Firecrawl error:', error);
          }
        }
        
        // 2c. ALWAYS search web with Tavily for latest information
        if (TAVILY_API_KEY) {
          try {
            console.log(`🔍 Tavily: Searching web for ${companyName}...`);
            const searchResponse = await fetch('https://api.tavily.com/search', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({
                api_key: TAVILY_API_KEY,
                query: `${companyName} funding valuation revenue metrics financials latest news series funding round ${new Date().getFullYear()}`,
                search_depth: 'advanced',
                max_results: 15,
                include_answer: true,
                include_raw_content: true
              })
            });
            
            if (searchResponse.ok) {
              const searchData = await searchResponse.json();
              webSearchData = searchData.results || [];
              console.log(`🔍 Tavily found ${webSearchData.length} results with answer:`, searchData.answer?.substring(0, 100));
              
              // Also store the AI-generated answer if available
              if (searchData.answer) {
                webSearchData.push({
                  title: 'Tavily AI Summary',
                  content: searchData.answer,
                  url: 'Tavily Search AI'
                });
              }
            } else {
              console.error('Tavily API error:', await searchResponse.text());
            }
          } catch (error) {
            console.error('Tavily search error:', error);
          }
        } else {
          console.warn('⚠️ TAVILY_API_KEY not configured - cannot search web');
        }
        
        // 2d. Get market intelligence
        try {
          const baseUrl = request.url.substring(0, request.url.indexOf('/api'));
          const marketResponse = await fetch(`${baseUrl}/api/agent/market-intelligence`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ 
              prompt: `${companyName} market analysis competitors valuation`
            })
          });
          
          if (marketResponse.ok) {
            marketIntelligence = await marketResponse.json();
            console.log('Market intelligence gathered');
          }
        } catch (error) {
          console.error('Market intelligence error:', error);
        }
      }
    }
    
    // Step 3: Check if we have any real data
    const hasRealData = companyData || cimData || webSearchData.length > 0 || marketIntelligence;
    
    console.log('Data fetching results:', {
      hasCompanyData: !!companyData,
      hasCIMData: !!cimData,
      webSearchCount: webSearchData.length,
      hasMarketIntel: !!marketIntelligence,
      hasRealData
    });
    
    if (!hasRealData && companies.length > 0) {
      return NextResponse.json({
        response: `I couldn't find specific data for ${companies.join(', ')}. Please verify the company name or try a more specific search. You can also try mentioning the company with @ for a detailed profile.`,
        toolsUsed: ['search_attempted'],
        metadata: {
          searchAttempted: true,
          companiesSearched: companies
        }
      });
    }
    
    // Step 4: Build response with real data
    let responseText = '';
    
    if (CLAUDE_API_KEY && hasRealData) {
      // Build context from all available data
      let context = '# REAL DATA AVAILABLE\n\n';
      
      if (companyData) {
        context += `## Database Information\n`;
        context += `- Company: ${companyData.name}\n`;
        context += `- Sector: ${companyData.sector || 'Not specified'}\n`;
        context += `- Total Funding: $${(companyData.total_invested_usd / 1000000).toFixed(1)}M\n`;
        context += `- Stage: ${companyData.stage || 'Not specified'}\n`;
        context += `- Description: ${companyData.description || 'Not available'}\n\n`;
      }
      
      if (cimData) {
        context += `## Company CIM Profile\n`;
        context += JSON.stringify(cimData, null, 2).substring(0, 2000) + '...\n\n';
      }
      
      if (webSearchData.length > 0) {
        context += `## Latest Web Information\n`;
        webSearchData.slice(0, 3).forEach((result, idx) => {
          context += `${idx + 1}. **${result.title}**\n`;
          context += `   ${result.content.substring(0, 200)}...\n`;
          context += `   Source: ${result.url}\n\n`;
        });
      }
      
      if (marketIntelligence) {
        context += `## Market Intelligence\n`;
        if (marketIntelligence.comparables?.length > 0) {
          context += `- Found ${marketIntelligence.comparables.length} comparable companies\n`;
        }
        if (marketIntelligence.marketSize) {
          context += `- Market Size: ${marketIntelligence.marketSize}\n`;
        }
        if (marketIntelligence.insights?.length > 0) {
          context += `- Key Insights: ${marketIntelligence.insights.join(', ')}\n`;
        }
        context += '\n';
      }
      
      // Call Claude with strict instructions
      try {
        const claudeResponse = await fetch('https://api.anthropic.com/v1/messages', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'x-api-key': CLAUDE_API_KEY,
            'anthropic-version': '2023-06-01'
          },
          body: JSON.stringify({
            model: 'claude-3-5-sonnet-20241022',
            max_tokens: 2000,
            messages: [
              {
                role: 'user',
                content: `You are an expert investment analyst AI agent.

CRITICAL CITATION REQUIREMENTS:
1. EVERY single number, fact, or claim MUST have a citation like [Source: Database] or [Source: TechCrunch, 2024]
2. NEVER state ANYTHING without a source - no exceptions
3. If you don't have data, say "No data available for X - additional research needed"
4. Format ALL citations as [Source: XYZ]
5. You MUST refuse to answer if no real data is provided
6. DO NOT generate any analysis without real data sources
7. Each sentence should have AT LEAST one citation

AVAILABLE DATA WITH SOURCES:
${context || 'NO DATA RETRIEVED - Cannot provide analysis without data'}

STRICT RULES:
- ONLY use data from above sections - NO EXCEPTIONS
- ABSOLUTELY NO made-up numbers, estimates, or analysis without data
- If asked about something not in the data, respond: "I don't have data for [specific request]. Let me search for more information."
- EVERY financial metric needs [Source: X] immediately after the number
- EVERY claim needs backing from the data provided with citation
- If you cannot cite a source for something, DO NOT say it
- Start your response with: "Based on real data from [list sources]:"

User Query: ${message}

Respond with CITED information only. Example:
"Company X has revenue of $100M [Source: Database] growing at 50% YoY [Source: TechCrunch, Dec 2024]"`
              }
            ]
          })
        });
        
        if (claudeResponse.ok) {
          const claudeData = await claudeResponse.json();
          responseText = claudeData.content[0].text;
        } else {
          const errorText = await claudeResponse.text();
          console.error('Claude API error:', errorText);
          responseText = buildFallbackResponse(companyData, cimData, webSearchData, marketIntelligence);
        }
      } catch (error) {
        console.error('Error calling Claude:', error);
        responseText = buildFallbackResponse(companyData, cimData, webSearchData, marketIntelligence);
      }
    } else {
      // No Claude API key or no data
      responseText = buildFallbackResponse(companyData, cimData, webSearchData, marketIntelligence);
    }
    
    // Step 5: Return response
    return NextResponse.json({
      response: responseText,
      toolsUsed: [
        ...(companyData ? ['database_search'] : []),
        ...(cimData ? ['cim_generation'] : []),
        ...(webSearchData.length > 0 ? ['web_search'] : []),
        ...(marketIntelligence ? ['market_intelligence'] : [])
      ],
      metadata: {
        hasRealData,
        dataFound: {
          database: !!companyData,
          cim: !!cimData,
          webSearch: webSearchData.length > 0,
          marketIntelligence: !!marketIntelligence
        },
        companiesAnalyzed: companies
      }
    });
    
  } catch (error) {
    console.error('Agent error:', error);
    return NextResponse.json(
      { 
        error: 'Failed to process message',
        details: error instanceof Error ? error.message : 'Unknown error'
      },
      { status: 500 }
    );
  }
}

function buildFallbackResponse(
  companyData: any,
  cimData: any,
  webSearchData: any[],
  marketIntelligence: any
): string {
  let response = 'Based on available data sources:\n\n';
  
  if (companyData) {
    response += `## ${companyData.name}\n\n`;
    response += `**Sector:** ${companyData.sector || 'Not specified'} [Source: Internal Database]\n`;
    response += `**Total Funding:** $${(companyData.total_invested_usd / 1000000).toFixed(1)}M [Source: Internal Database]\n`;
    response += `**Stage:** ${companyData.stage || 'Not specified'} [Source: Internal Database]\n\n`;
  }
  
  if (cimData) {
    response += `**Company Profile Available**\n`;
    response += 'A detailed CIM has been generated with comprehensive business information.\n\n';
  }
  
  if (webSearchData.length > 0) {
    response += `**Latest Information (with citations):**\n`;
    webSearchData.slice(0, 5).forEach((result, idx) => {
      response += `${idx + 1}. ${result.title} [Source: ${result.url}]\n`;
      response += `   ${result.content.substring(0, 200)}...\n\n`;
    });
  }
  
  if (marketIntelligence?.insights?.length > 0) {
    response += `**Market Insights (with sources):**\n`;
    marketIntelligence.insights.forEach((insight: string, idx: number) => {
      const source = marketIntelligence.competitorData?.[idx]?.url || 'Market Analysis';
      response += `• ${insight} [Source: ${source}]\n`;
    });
  }
  
  if (response === 'Based on available data sources:\n\n') {
    response = 'No real data found. I cannot provide analysis without verified sources. Please verify the company name or provide more specific information for me to research.';
  }
  
  return response;
}