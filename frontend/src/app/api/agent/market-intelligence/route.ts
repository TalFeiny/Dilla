import { NextResponse } from 'next/server';
import { createClient } from '@supabase/supabase-js';

const supabase = createClient(
  process.env.NEXT_PUBLIC_SUPABASE_URL!,
  process.env.SUPABASE_SERVICE_ROLE_KEY!
);

const TAVILY_API_KEY = process.env.TAVILY_API_KEY;

export async function POST(request: Request) {
  try {
    const { prompt } = await request.json();
    
    if (!prompt) {
      return NextResponse.json(
        { error: 'Prompt is required' },
        { status: 400 }
      );
    }
    
    console.log('Gathering market intelligence for:', prompt);
    
    // Extract company name from prompt
    const companyMatch = prompt.match(/([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)*)/);
    const companyName = companyMatch ? companyMatch[1] : null;
    
    let comparables = [];
    let marketSize = null;
    let competitorData = [];
    let industryTrends = [];
    
    // Step 1: Find comparable companies in database
    if (companyName) {
      try {
        // First try to find the company
        const { data: targetCompany } = await supabase
          .from('companies')
          .select('sector, stage, total_invested_usd')
          .ilike('name', `%${companyName}%`)
          .limit(1)
          .single();
        
        if (targetCompany && targetCompany.sector) {
          // Find similar companies
          const { data: comps } = await supabase
            .from('companies')
            .select('name, sector, total_invested_usd, stage')
            .eq('sector', targetCompany.sector)
            .not('name', 'ilike', `%${companyName}%`)
            .order('total_invested_usd', { ascending: false })
            .limit(10);
          
          if (comps) {
            comparables = comps;
            console.log(`Found ${comps.length} comparable companies in ${targetCompany.sector}`);
          }
        }
      } catch (error) {
        console.error('Error finding comparables:', error);
      }
    }
    
    // Step 2: Search for market data using Tavily
    if (TAVILY_API_KEY) {
      try {
        // Search for market size
        const marketResponse = await fetch('https://api.tavily.com/search', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            api_key: TAVILY_API_KEY,
            query: `${prompt} market size TAM total addressable market ${new Date().getFullYear()}`,
            search_depth: 'advanced',
            max_results: 3
          })
        });
        
        if (marketResponse.ok) {
          const marketData = await marketResponse.json();
          if (marketData.results && marketData.results.length > 0) {
            // Extract market size from results with citation
            const marketText = marketData.results[0].content;
            const sizeMatch = marketText.match(/\$[\d.]+\s*(billion|million|trillion)/i);
            if (sizeMatch) {
              marketSize = {
                value: sizeMatch[0],
                source: marketData.results[0].title,
                url: marketData.results[0].url,
                confidence: marketData.results[0].score || 0.8
              };
            }
          }
        }
        
        // Search for competitors
        const competitorResponse = await fetch('https://api.tavily.com/search', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            api_key: TAVILY_API_KEY,
            query: `${companyName || prompt} competitors alternatives comparison versus`,
            search_depth: 'basic',
            max_results: 5
          })
        });
        
        if (competitorResponse.ok) {
          const compData = await competitorResponse.json();
          if (compData.results) {
            competitorData = compData.results.map((r: any) => ({
              title: r.title,
              snippet: r.content.substring(0, 200),
              url: r.url,
              source: new URL(r.url).hostname,
              date: new Date().toISOString()
            }));
          }
        }
        
        // Search for industry trends
        const trendsResponse = await fetch('https://api.tavily.com/search', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            api_key: TAVILY_API_KEY,
            query: `${prompt} industry trends growth rate forecast ${new Date().getFullYear()}`,
            search_depth: 'basic',
            max_results: 3
          })
        });
        
        if (trendsResponse.ok) {
          const trendsData = await trendsResponse.json();
          if (trendsData.results) {
            industryTrends = trendsData.results.map((r: any) => ({
              insight: r.title,
              source: r.url,
              citation: `[Source: ${new URL(r.url).hostname}]`,
              confidence: r.score || 0.75
            }));
          }
        }
      } catch (error) {
        console.error('Tavily search error:', error);
      }
    }
    
    // Step 3: Analyze funding trends in the sector
    let fundingTrends = null;
    if (comparables.length > 0) {
      const totalFunding = comparables.reduce((sum, c) => sum + (c.total_invested_usd || 0), 0);
      const avgFunding = totalFunding / comparables.length;
      
      fundingTrends = {
        totalSectorFunding: totalFunding,
        averageFunding: avgFunding,
        topFunded: comparables.slice(0, 3).map(c => ({
          name: c.name,
          funding: c.total_invested_usd
        }))
      };
    }
    
    // Step 4: Generate insights
    const insights = [];
    
    if (marketSize) {
      const citation = marketSize.source ? ` [Source: ${marketSize.source}]` : '';
      insights.push(`Market size estimated at ${marketSize.value || marketSize}${citation}`);
    }
    
    if (comparables.length > 0) {
      insights.push(`Found ${comparables.length} comparable companies in the sector`);
    }
    
    if (fundingTrends && fundingTrends.averageFunding > 0) {
      insights.push(`Average funding in sector: $${(fundingTrends.averageFunding / 1000000).toFixed(1)}M [Source: Internal Database Analysis]`);
    }
    
    if (competitorData.length > 0) {
      insights.push(`Identified ${competitorData.length} potential competitors`);
    }
    
    // Build citations summary
    const citations = [
      ...(marketSize?.url ? [{source: marketSize.source, url: marketSize.url}] : []),
      ...competitorData.map((c: any) => ({source: c.source, url: c.url})),
      ...industryTrends.map((t: any) => ({source: new URL(t.source).hostname, url: t.source}))
    ];
    
    const uniqueSources = [...new Set(citations.map(c => c.source))];
    
    return NextResponse.json({
      success: true,
      company: companyName,
      comparables,
      marketSize,
      competitorData,
      industryTrends,
      fundingTrends,
      insights,
      citations: {
        total: citations.length,
        sources: uniqueSources,
        details: citations
      },
      timestamp: new Date().toISOString()
    });
    
  } catch (error) {
    console.error('Market intelligence error:', error);
    return NextResponse.json(
      { 
        error: 'Failed to gather market intelligence',
        details: error instanceof Error ? error.message : 'Unknown error'
      },
      { status: 500 }
    );
  }
}