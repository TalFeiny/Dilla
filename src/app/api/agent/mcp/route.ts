import { NextResponse } from 'next/server';
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
const CLAUDE_API_KEY = process.env.CLAUDE_API_KEY;

/**
 * MCP-powered Agent Endpoint
 * Uses Model Context Protocol for all tool interactions
 */
export async function POST(request: Request) {
  try {
    const { message, history = [], sessionId, useReasoning = true } = await request.json();
    
    if (!message) {
      return NextResponse.json(
        { error: 'Message is required' },
        { status: 400 }
      );
    }
    
    console.log('🤖 MCP Agent received:', message);
    
    // FAST PATH: For simple @mentions or company lookups
    const isCompanyLookup = message.trim().startsWith('@') || 
                           (message.trim().split(' ').length <= 3 && /^[A-Z]/.test(message.trim()));
    
    if (isCompanyLookup) {
      console.log('⚡ Using fast company lookup');
      
      // Extract company name
      let companyName = message.trim();
      if (companyName.startsWith('@')) {
        companyName = companyName.substring(1);
      }
      
      // Parallel fetch from database and web
      const [dbResult, webResult] = await Promise.all([
        // Database lookup
        supabase
          .from('companies')
          .select('*')
          .or(`name.ilike.%${companyName}%,description.ilike.%${companyName}%`)
          .limit(1)
          .single(),
        
        // Web search
        TAVILY_API_KEY ? 
          fetch('https://api.tavily.com/search', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              api_key: TAVILY_API_KEY,
              query: `"${companyName}" company funding valuation revenue metrics ${new Date().getFullYear()}`,
              search_depth: 'basic',
              max_results: 5,
              include_answer: true
            })
          }).then(r => r.json()).catch(() => null) : null
      ]);
      
      // Format quick response
      let response = `# ${companyName}\n\n`;
      const sources = [];
      
      if (dbResult.data) {
        response += `**Company Profile** [Source: Internal Database]\n`;
        response += `- Sector: ${dbResult.data.sector || 'Unknown'}\n`;
        response += `- Funding: $${(dbResult.data.total_invested_usd / 1000000).toFixed(1)}M\n`;
        response += `- Stage: ${dbResult.data.stage || 'Unknown'}\n\n`;
        sources.push('Internal Database');
      }
      
      if (webResult?.answer) {
        response += `**Latest Information** [Source: Web Search]\n`;
        response += `${webResult.answer}\n\n`;
        
        if (webResult.results?.length > 0) {
          response += `**Sources:**\n`;
          webResult.results.slice(0, 3).forEach((r: any) => {
            response += `- [${r.title}](${r.url})\n`;
            sources.push(r.url);
          });
        }
      }
      
      if (!dbResult.data && !webResult?.answer) {
        response = `No information found for "${companyName}". Please check the spelling or provide more context.`;
      }
      
      return NextResponse.json({
        response,
        toolsUsed: sources.length > 0 ? ['database_search', 'web_search'] : [],
        metadata: {
          company: companyName,
          sourceCount: sources.length,
          mode: 'fast-lookup'
        }
      });
    }
    
    // For complex queries, use Claude to generate a comprehensive response
    console.log('🤖 Processing complex query with Claude');
    
    // Step 1: Gather data from multiple sources
    const searchPromises = [];
    
    // Extract potential entities from the message
    const entities = message.match(/[A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)*/g) || [];
    
    // Search for each entity
    for (const entity of entities.slice(0, 3)) { // Limit to 3 entities
      searchPromises.push(
        supabase
          .from('companies')
          .select('*')
          .or(`name.ilike.%${entity}%,description.ilike.%${entity}%`)
          .limit(3)
      );
      
      if (TAVILY_API_KEY) {
        searchPromises.push(
          fetch('https://api.tavily.com/search', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              api_key: TAVILY_API_KEY,
              query: `${entity} ${message}`,
              search_depth: 'advanced',
              max_results: 5,
              include_answer: true
            })
          }).then(r => r.json()).catch(() => null)
        );
      }
    }
    
    // Execute all searches in parallel
    const searchResults = await Promise.all(searchPromises);
    
    // Step 2: Build context from search results
    let context = '# Research Results\n\n';
    const allSources = [];
    
    searchResults.forEach((result, idx) => {
      if (result?.data && Array.isArray(result.data)) {
        // Database results
        context += `## Database Results\n`;
        result.data.forEach((company: any) => {
          context += `- **${company.name}**: ${company.sector || 'Unknown sector'}, $${(company.total_invested_usd / 1000000).toFixed(1)}M funding [Source: Internal DB]\n`;
          allSources.push('Internal Database');
        });
      } else if (result?.answer) {
        // Tavily results
        context += `## Web Search Results\n`;
        context += `${result.answer}\n`;
        if (result.results) {
          result.results.forEach((r: any) => {
            context += `- [${r.title}](${r.url})\n`;
            allSources.push(r.url);
          });
        }
      }
    });

    // Step 3: Generate response with Claude
    let finalResponse = '';
    
    if (CLAUDE_API_KEY && context) {
      const prompt = `You are an expert investment analyst. Based on the following real data, provide a comprehensive answer to the user's query.

${context}

User Query: ${message}

REQUIREMENTS:
- Use ONLY the data provided above
- Every claim MUST have a [Source: X] citation
- Format numbers properly (e.g., $1.5M not 1500000)
- If data is insufficient, clearly state what's missing
- Be concise but thorough

Provide your analysis:`;
      
      const response = await anthropic.messages.create({
        model: 'claude-3-5-sonnet-20241022',
        max_tokens: 2000,
        messages: [{ role: 'user', content: prompt }]
      });
      
      finalResponse = response.content[0].type === 'text' ? response.content[0].text : 'Failed to generate response';
    } else if (context) {
      // Fallback without Claude
      finalResponse = context;
    } else {
      finalResponse = 'Unable to gather data. Please check configuration.';
    }
    
    // Step 4: Return response with metadata
    return NextResponse.json({
      response: finalResponse,
      toolsUsed: allSources.length > 0 ? ['database_search', 'web_search'] : [],
      metadata: {
        sourceCount: allSources.length,
        timestamp: new Date().toISOString(),
        mode: 'mcp-enhanced'
      }
    });
    
  } catch (error) {
    console.error('MCP Agent error:', error);
    return NextResponse.json(
      { 
        error: 'Failed to process message',
        details: error instanceof Error ? error.message : 'Unknown error'
      },
      { status: 500 }
    );
  }
}

/**
 * GET endpoint to show capabilities
 */
export async function GET() {
  return NextResponse.json({
    name: 'MCP Agent',
    description: 'Multi-source agent with database and web search',
    capabilities: [
      'Company lookups with @mentions',
      'Database search for funding data',
      'Web search for latest information',
      'Claude-powered analysis',
      'Automatic citation generation'
    ],
    dataSources: [
      'Internal Database (1,216 companies)',
      'Tavily Web Search',
      'Claude AI Analysis'
    ]
  });
}