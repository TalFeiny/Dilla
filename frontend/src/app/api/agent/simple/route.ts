import { NextResponse } from 'next/server';
import { createClient } from '@supabase/supabase-js';

const supabase = createClient(
  process.env.NEXT_PUBLIC_SUPABASE_URL!,
  process.env.SUPABASE_SERVICE_ROLE_KEY!
);

const TAVILY_API_KEY = process.env.TAVILY_API_KEY;
const CLAUDE_API_KEY = process.env.CLAUDE_API_KEY;

export async function POST(request: Request) {
  try {
    const { message } = await request.json();
    
    // Extract company name from @mention
    const companyMatch = message.match(/@(\w+)/);
    const companyName = companyMatch ? companyMatch[1] : message.trim();
    
    console.log(`🎯 Looking up: ${companyName}`);
    
    // Parallel search
    const [dbResult, webResult] = await Promise.all([
      // Database
      supabase
        .from('companies')
        .select('*')
        .ilike('name', `%${companyName}%`)
        .limit(1)
        .single(),
      
      // Tavily search
      TAVILY_API_KEY ? 
        fetch('https://api.tavily.com/search', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            api_key: TAVILY_API_KEY,
            query: `${companyName} company profile funding valuation revenue ${new Date().getFullYear()}`,
            search_depth: 'basic',
            max_results: 5,
            include_answer: true
          })
        }).then(r => r.json()) : null
    ]);
    
    // Build response
    let response = `# ${companyName}\n\n`;
    const sources = [];
    
    if (dbResult.data) {
      response += `## Database Profile\n`;
      response += `- **Sector**: ${dbResult.data.sector || 'Unknown'} [Source: Internal DB]\n`;
      response += `- **Funding**: $${(dbResult.data.total_invested_usd / 1000000).toFixed(1)}M [Source: Internal DB]\n`;
      response += `- **Stage**: ${dbResult.data.stage || 'Unknown'} [Source: Internal DB]\n\n`;
      sources.push('Internal Database');
    }
    
    if (webResult?.answer) {
      response += `## Latest Information\n`;
      response += `${webResult.answer} [Source: Web Search]\n\n`;
      
      if (webResult.results?.length > 0) {
        response += `## Sources\n`;
        webResult.results.slice(0, 3).forEach((r: any) => {
          response += `- [${r.title}](${r.url})\n`;
          sources.push(r.url);
        });
      }
    }
    
    if (!dbResult.data && !webResult?.answer) {
      response = `No information found for "${companyName}". The company may not exist in our database. Try a different spelling or provide more context.`;
    }
    
    return NextResponse.json({
      response,
      toolsUsed: sources.length > 0 ? ['database', 'web_search'] : [],
      metadata: {
        company: companyName,
        sourceCount: sources.length,
        executionTime: Date.now()
      }
    });
    
  } catch (error) {
    console.error('Simple agent error:', error);
    return NextResponse.json(
      { error: 'Lookup failed' },
      { status: 500 }
    );
  }
}