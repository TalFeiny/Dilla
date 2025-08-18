import { NextResponse } from 'next/server';
import { mcpClient } from '@/lib/mcp/mcp-client';

/**
 * Enhanced MCP-powered Agent Endpoint
 * Uses MCP for all tool coordination and agent-to-agent communication
 */
export async function POST(request: Request) {
  try {
    const { message, sessionId, mode = 'auto' } = await request.json();
    
    if (!message) {
      return NextResponse.json(
        { error: 'Message is required' },
        { status: 400 }
      );
    }
    
    console.log('🤖 MCP Enhanced Agent:', message);
    
    // Connect to MCP server
    await mcpClient.connect();
    
    // Detect query type and route appropriately
    const queryType = detectQueryType(message);
    
    let result;
    
    switch (queryType) {
      case 'company_mention':
        // Extract company name from @mention
        const companyMatch = message.match(/@?([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)*)/);
        const companyName = companyMatch ? companyMatch[1] : message;
        
        console.log(`📊 Company research for: ${companyName}`);
        result = await mcpClient.researchCompany(companyName);
        break;
        
      case 'market_research':
        console.log('📈 Market research query');
        result = await mcpClient.executeChain({
          query: message,
          steps: [
            { tool: 'web_search', params: { query: message, depth: 'advanced' }, useOutput: 'search' },
            { tool: 'synthesize', params: { sources: ['search'], question: message }, useOutput: 'final' }
          ]
        });
        break;
        
      case 'comparison':
        console.log('⚖️ Comparison query');
        // Extract entities to compare
        const entities = extractEntities(message);
        
        const steps = entities.map((entity, i) => ({
          tool: 'comprehensive_research',
          params: { companyName: entity },
          useOutput: `company_${i}`
        }));
        
        steps.push({
          tool: 'synthesize',
          params: {
            sources: entities.map((_, i) => `company_${i}`),
            question: message,
            format: 'comparison'
          },
          useOutput: 'comparison'
        });
        
        result = await mcpClient.executeChain({
          query: message,
          steps
        });
        break;
        
      case 'financial_analysis':
        console.log('💰 Financial analysis');
        result = await executeFinancialAnalysis(message);
        break;
        
      default:
        console.log('🔍 General query - using chain reasoning');
        // Auto-generate reasoning chain
        result = await mcpClient.executeChain({
          query: message,
          steps: [
            { tool: 'web_search', params: { query: message }, useOutput: 'web' },
            { tool: 'database_lookup', params: { query: extractKeyTerms(message) }, useOutput: 'db' },
            { tool: 'synthesize', params: { sources: ['web', 'db'], question: message }, useOutput: 'final' }
          ]
        });
    }
    
    // Format response
    const formattedResponse = formatResponse(result, queryType);
    
    return NextResponse.json({
      response: formattedResponse,
      metadata: {
        queryType,
        mode: 'mcp-enhanced',
        timestamp: new Date().toISOString(),
        sources: extractSources(result)
      }
    });
    
  } catch (error) {
    console.error('MCP Enhanced Agent error:', error);
    return NextResponse.json(
      { 
        error: 'Failed to process request',
        details: error instanceof Error ? error.message : 'Unknown error'
      },
      { status: 500 }
    );
  }
}

/**
 * Detect query type
 */
function detectQueryType(message: string): string {
  const lowerMessage = message.toLowerCase();
  
  if (message.includes('@') || /^[A-Z][a-zA-Z]+(\s+[A-Z][a-zA-Z]+)*$/.test(message.trim())) {
    return 'company_mention';
  }
  
  if (lowerMessage.includes('compare') || lowerMessage.includes('vs') || lowerMessage.includes('versus')) {
    return 'comparison';
  }
  
  if (lowerMessage.includes('market') || lowerMessage.includes('industry') || lowerMessage.includes('sector')) {
    return 'market_research';
  }
  
  if (lowerMessage.includes('valuation') || lowerMessage.includes('dcf') || lowerMessage.includes('revenue')) {
    return 'financial_analysis';
  }
  
  return 'general';
}

/**
 * Extract entities from message
 */
function extractEntities(message: string): string[] {
  const entities: string[] = [];
  
  // Look for @mentions
  const mentions = message.match(/@([\w\s]+?)(?=\s|$|@)/g);
  if (mentions) {
    entities.push(...mentions.map(m => m.substring(1).trim()));
  }
  
  // Look for "X vs Y" or "X and Y" patterns
  const vsPattern = /(\w+(?:\s+\w+)*)\s+(?:vs|versus|and)\s+(\w+(?:\s+\w+)*)/i;
  const vsMatch = message.match(vsPattern);
  if (vsMatch && entities.length === 0) {
    entities.push(vsMatch[1], vsMatch[2]);
  }
  
  // Look for capitalized company names
  if (entities.length === 0) {
    const capPattern = /\b[A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)*\b/g;
    const capMatches = message.match(capPattern);
    if (capMatches) {
      entities.push(...capMatches);
    }
  }
  
  return [...new Set(entities)]; // Remove duplicates
}

/**
 * Extract key terms for database search
 */
function extractKeyTerms(message: string): string {
  // Remove common words and extract key terms
  const stopWords = ['the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 'from', 'about', 'what', 'which', 'who', 'when', 'where', 'why', 'how'];
  
  const words = message.toLowerCase().split(/\s+/);
  const keyWords = words.filter(word => !stopWords.includes(word) && word.length > 2);
  
  return keyWords.slice(0, 3).join(' ');
}

/**
 * Execute financial analysis
 */
async function executeFinancialAnalysis(message: string): Promise<any> {
  const entities = extractEntities(message);
  const company = entities[0] || extractKeyTerms(message);
  
  return await mcpClient.executeChain({
    query: message,
    steps: [
      { tool: 'database_lookup', params: { query: company }, useOutput: 'company_data' },
      { tool: 'web_search', params: { query: `${company} financial metrics revenue valuation` }, useOutput: 'financials' },
      { tool: 'deep_scrape', params: { companyName: company }, useOutput: 'detailed' },
      { tool: 'synthesize', params: { sources: ['company_data', 'financials', 'detailed'], question: message }, useOutput: 'analysis' }
    ]
  });
}

/**
 * Format response based on query type
 */
function formatResponse(result: any, queryType: string): string {
  if (!result) return 'No data available';
  
  // Handle different result structures
  if (result.synthesis) {
    return result.synthesis;
  }
  
  if (result.final) {
    if (typeof result.final === 'string') {
      return result.final;
    }
    if (result.final.synthesis) {
      return result.final.synthesis;
    }
    if (result.final.answer) {
      return result.final.answer;
    }
  }
  
  if (result.answer) {
    return result.answer;
  }
  
  if (result.steps && result.steps.length > 0) {
    const lastStep = result.steps[result.steps.length - 1];
    if (lastStep.output) {
      try {
        const parsed = JSON.parse(lastStep.output);
        if (parsed.synthesis) return parsed.synthesis;
        if (parsed.answer) return parsed.answer;
      } catch {
        return lastStep.output;
      }
    }
  }
  
  // Format based on query type
  switch (queryType) {
    case 'company_mention':
      return formatCompanyProfile(result);
    case 'comparison':
      return formatComparison(result);
    case 'financial_analysis':
      return formatFinancialAnalysis(result);
    default:
      return JSON.stringify(result, null, 2);
  }
}

/**
 * Format company profile
 */
function formatCompanyProfile(data: any): string {
  if (!data.company) return JSON.stringify(data, null, 2);
  
  let response = `## ${data.company}\n\n`;
  
  if (data.database) {
    const db = data.database;
    response += `### Company Overview\n`;
    response += `- **Sector**: ${db.companies?.[0]?.sector || 'N/A'}\n`;
    response += `- **Founded**: ${db.companies?.[0]?.founded_year || 'N/A'}\n`;
    response += `- **Description**: ${db.companies?.[0]?.description || 'N/A'}\n\n`;
  }
  
  if (data.web_search) {
    response += `### Latest Information\n`;
    response += data.web_search.answer || 'No recent information available';
    response += '\n\n';
    
    if (data.web_search.sources) {
      response += `### Sources\n`;
      data.web_search.sources.forEach((source: any) => {
        response += `- [${source.title}](${source.url})\n`;
      });
    }
  }
  
  return response;
}

/**
 * Format comparison
 */
function formatComparison(data: any): string {
  if (data.comparison) {
    if (typeof data.comparison === 'string') {
      return data.comparison;
    }
    if (data.comparison.synthesis) {
      return data.comparison.synthesis;
    }
  }
  
  return JSON.stringify(data, null, 2);
}

/**
 * Format financial analysis
 */
function formatFinancialAnalysis(data: any): string {
  if (data.analysis) {
    if (typeof data.analysis === 'string') {
      return data.analysis;
    }
    if (data.analysis.synthesis) {
      return data.analysis.synthesis;
    }
  }
  
  return JSON.stringify(data, null, 2);
}

/**
 * Extract sources from result
 */
function extractSources(result: any): string[] {
  const sources: string[] = [];
  
  if (result.sources) {
    if (Array.isArray(result.sources)) {
      sources.push(...result.sources);
    }
  }
  
  if (result.web_search?.sources) {
    result.web_search.sources.forEach((s: any) => {
      sources.push(s.url || s.title);
    });
  }
  
  if (result.steps) {
    result.steps.forEach((step: any) => {
      if (step.output) {
        try {
          const parsed = JSON.parse(step.output);
          if (parsed.sources) {
            sources.push(...parsed.sources);
          }
        } catch {}
      }
    });
  }
  
  return [...new Set(sources)];
}

/**
 * GET endpoint to show capabilities
 */
export async function GET() {
  try {
    await mcpClient.connect();
    const tools = await mcpClient.listTools();
    
    return NextResponse.json({
      name: 'MCP Enhanced Agent',
      description: 'Advanced agent using Model Context Protocol for tool coordination',
      capabilities: [
        'Multi-tool orchestration via MCP',
        'Agent-to-agent communication',
        'Parallel and sequential execution',
        'Result caching and chaining',
        'Automatic query routing',
        'Comprehensive company research',
        'Market analysis',
        'Financial modeling'
      ],
      availableTools: tools,
      queryTypes: [
        'company_mention - Research specific companies',
        'market_research - Analyze markets and industries',
        'comparison - Compare multiple entities',
        'financial_analysis - Financial metrics and valuation',
        'general - Any other query'
      ]
    });
  } catch (error) {
    return NextResponse.json({
      error: 'Failed to connect to MCP server',
      details: error instanceof Error ? error.message : 'Unknown error'
    });
  }
}