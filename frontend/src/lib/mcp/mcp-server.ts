/**
 * MCP Server Implementation
 * Provides a unified interface for all tools and agent-to-agent communication
 */

import { Server } from '@modelcontextprotocol/sdk/server/index.js';
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';
import {
  CallToolRequestSchema,
  ListResourcesRequestSchema,
  ListToolsRequestSchema,
  ReadResourceRequestSchema,
  McpError,
  ErrorCode
} from '@modelcontextprotocol/sdk/types.js';
import { FirecrawlApp } from '@mendable/firecrawl-js';
import { createClient } from '@supabase/supabase-js';

// Initialize services
const FIRECRAWL_API_KEY = process.env.FIRECRAWL_API_KEY;
const TAVILY_API_KEY = process.env.TAVILY_API_KEY;
const CLAUDE_API_KEY = process.env.CLAUDE_API_KEY;

const supabase = createClient(
  process.env.NEXT_PUBLIC_SUPABASE_URL!,
  process.env.SUPABASE_SERVICE_ROLE_KEY!
);

const firecrawl = FIRECRAWL_API_KEY ? new FirecrawlApp({ apiKey: FIRECRAWL_API_KEY }) : null;

// Tool result cache for chaining
const resultCache = new Map<string, any>();

/**
 * MCP Server for VC Platform
 */
export class VCPlatformMCPServer {
  private server: Server;
  
  constructor() {
    this.server = new Server(
      {
        name: 'vc-platform-mcp',
        version: '1.0.0',
      },
      {
        capabilities: {
          resources: {},
          tools: {}
        }
      }
    );
    
    this.setupHandlers();
  }
  
  private setupHandlers() {
    // List available tools
    this.server.setRequestHandler(ListToolsRequestSchema, async () => ({
      tools: [
        {
          name: 'web_search',
          description: 'Search the web using Tavily for latest information',
          inputSchema: {
            type: 'object',
            properties: {
              query: { type: 'string', description: 'Search query' },
              depth: { type: 'string', enum: ['basic', 'advanced'], default: 'advanced' },
              maxResults: { type: 'number', default: 10 }
            },
            required: ['query']
          }
        },
        {
          name: 'deep_scrape',
          description: 'Deep scrape websites using Firecrawl',
          inputSchema: {
            type: 'object',
            properties: {
              url: { type: 'string', description: 'URL to scrape' },
              companyName: { type: 'string', description: 'Company name if URL unknown' },
              depth: { type: 'number', default: 3, description: 'Crawl depth' }
            }
          }
        },
        {
          name: 'database_lookup',
          description: 'Search internal database for company information',
          inputSchema: {
            type: 'object',
            properties: {
              query: { type: 'string', description: 'Company name or search term' },
              filters: {
                type: 'object',
                properties: {
                  sector: { type: 'string' },
                  minFunding: { type: 'number' },
                  maxFunding: { type: 'number' }
                }
              }
            },
            required: ['query']
          }
        },
        {
          name: 'comprehensive_research',
          description: 'Perform comprehensive multi-source research on a company',
          inputSchema: {
            type: 'object',
            properties: {
              companyName: { type: 'string', description: 'Company to research' },
              includeFinancials: { type: 'boolean', default: true },
              includeNews: { type: 'boolean', default: true },
              includeCompetitors: { type: 'boolean', default: true }
            },
            required: ['companyName']
          }
        },
        {
          name: 'chain_reasoning',
          description: 'Execute a chain of reasoning steps',
          inputSchema: {
            type: 'object',
            properties: {
              query: { type: 'string', description: 'Initial query' },
              steps: {
                type: 'array',
                items: {
                  type: 'object',
                  properties: {
                    tool: { type: 'string' },
                    params: { type: 'object' },
                    useOutput: { type: 'string', description: 'Variable name to store output' }
                  }
                }
              }
            },
            required: ['query']
          }
        },
        {
          name: 'synthesize',
          description: 'Synthesize information from multiple sources',
          inputSchema: {
            type: 'object',
            properties: {
              sources: {
                type: 'array',
                items: { type: 'string' },
                description: 'Source variable names from cache'
              },
              question: { type: 'string', description: 'Question to answer' },
              format: { type: 'string', enum: ['summary', 'detailed', 'comparison'], default: 'detailed' }
            },
            required: ['sources', 'question']
          }
        }
      ]
    }));
    
    // Handle tool execution
    this.server.setRequestHandler(CallToolRequestSchema, async (request) => {
      const { name, arguments: args } = request.params;
      
      try {
        switch (name) {
          case 'web_search':
            return await this.executeWebSearch(args);
            
          case 'deep_scrape':
            return await this.executeDeepScrape(args);
            
          case 'database_lookup':
            return await this.executeDatabaseLookup(args);
            
          case 'comprehensive_research':
            return await this.executeComprehensiveResearch(args);
            
          case 'chain_reasoning':
            return await this.executeChainReasoning(args);
            
          case 'synthesize':
            return await this.executeSynthesize(args);
            
          default:
            throw new McpError(
              ErrorCode.MethodNotFound,
              `Tool ${name} not found`
            );
        }
      } catch (error) {
        throw new McpError(
          ErrorCode.InternalError,
          error instanceof Error ? error.message : 'Tool execution failed'
        );
      }
    });
    
    // List resources (cached results)
    this.server.setRequestHandler(ListResourcesRequestSchema, async () => ({
      resources: Array.from(resultCache.keys()).map(key => ({
        uri: `cache://${key}`,
        name: key,
        mimeType: 'application/json',
        description: `Cached result: ${key}`
      }))
    }));
    
    // Read resources (get cached results)
    this.server.setRequestHandler(ReadResourceRequestSchema, async (request) => {
      const { uri } = request.params;
      
      if (uri.startsWith('cache://')) {
        const key = uri.replace('cache://', '');
        const data = resultCache.get(key);
        
        if (!data) {
          throw new McpError(
            ErrorCode.InvalidRequest,
            `Cache key ${key} not found`
          );
        }
        
        return {
          contents: [{
            uri,
            mimeType: 'application/json',
            text: JSON.stringify(data, null, 2)
          }]
        };
      }
      
      throw new McpError(
        ErrorCode.InvalidRequest,
        `Unknown resource URI: ${uri}`
      );
    });
  }
  
  /**
   * Execute web search using Tavily
   */
  private async executeWebSearch(args: any) {
    if (!TAVILY_API_KEY) {
      return {
        content: [{ type: 'text', text: 'Tavily API key not configured' }]
      };
    }
    
    const response = await fetch('https://api.tavily.com/search', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        api_key: TAVILY_API_KEY,
        query: args.query,
        search_depth: args.depth || 'advanced',
        max_results: args.maxResults || 10,
        include_answer: true,
        include_raw_content: true,
        include_domains: [
          'techcrunch.com', 'crunchbase.com', 'pitchbook.com',
          'reuters.com', 'bloomberg.com', 'forbes.com'
        ]
      })
    });
    
    const data = await response.json();
    
    // Cache result if needed
    if (args.cacheAs) {
      resultCache.set(args.cacheAs, data);
    }
    
    return {
      content: [{
        type: 'text',
        text: JSON.stringify({
          answer: data.answer,
          results: data.results?.slice(0, 5),
          sources: data.results?.map((r: any) => ({
            title: r.title,
            url: r.url
          }))
        }, null, 2)
      }]
    };
  }
  
  /**
   * Execute deep scrape using Firecrawl
   */
  private async executeDeepScrape(args: any) {
    if (!firecrawl) {
      return {
        content: [{ type: 'text', text: 'Firecrawl not configured' }]
      };
    }
    
    let url = args.url;
    
    if (!url && args.companyName) {
      // Try to find company website
      const { data } = await supabase
        .from('companies')
        .select('website_url')
        .ilike('name', `%${args.companyName}%`)
        .limit(1)
        .single();
      
      url = data?.website_url || `https://${args.companyName.toLowerCase().replace(/\s+/g, '')}.com`;
    }
    
    const result = await firecrawl.scrapeUrl(url, {
      formats: ['markdown', 'html'],
      waitFor: 2000
    });
    
    // Extract structured data
    const structuredData = {
      url,
      title: result.data?.metadata?.title,
      description: result.data?.metadata?.description,
      content: result.data?.markdown?.substring(0, 5000),
      links: result.data?.links
    };
    
    // Cache result if needed
    if (args.cacheAs) {
      resultCache.set(args.cacheAs, structuredData);
    }
    
    return {
      content: [{
        type: 'text',
        text: JSON.stringify(structuredData, null, 2)
      }]
    };
  }
  
  /**
   * Execute database lookup
   */
  private async executeDatabaseLookup(args: any) {
    let query = supabase
      .from('companies')
      .select('*')
      .ilike('name', `%${args.query}%`);
    
    if (args.filters?.sector) {
      query = query.eq('sector', args.filters.sector);
    }
    
    if (args.filters?.minFunding) {
      query = query.gte('total_funding_usd', args.filters.minFunding);
    }
    
    if (args.filters?.maxFunding) {
      query = query.lte('total_funding_usd', args.filters.maxFunding);
    }
    
    const { data, error } = await query.limit(10);
    
    if (error) {
      return {
        content: [{ type: 'text', text: `Database error: ${error.message}` }]
      };
    }
    
    // Cache result if needed
    if (args.cacheAs) {
      resultCache.set(args.cacheAs, data);
    }
    
    return {
      content: [{
        type: 'text',
        text: JSON.stringify({
          count: data?.length || 0,
          companies: data || []
        }, null, 2)
      }]
    };
  }
  
  /**
   * Execute comprehensive research
   */
  private async executeComprehensiveResearch(args: any) {
    const { companyName } = args;
    const results: any = {
      company: companyName,
      timestamp: new Date().toISOString(),
      sources: []
    };
    
    // Parallel execution of all research tasks
    const tasks = [];
    
    // Database lookup
    tasks.push(this.executeDatabaseLookup({ query: companyName, cacheAs: `${companyName}_db` }));
    
    // Web search
    tasks.push(this.executeWebSearch({
      query: `${companyName} funding valuation revenue ${new Date().getFullYear()}`,
      depth: 'advanced',
      cacheAs: `${companyName}_web`
    }));
    
    // Deep scrape if we can find URL
    tasks.push(this.executeDeepScrape({
      companyName,
      cacheAs: `${companyName}_scrape`
    }));
    
    if (args.includeNews) {
      tasks.push(this.executeWebSearch({
        query: `${companyName} latest news announcements ${new Date().getFullYear()}`,
        depth: 'basic',
        cacheAs: `${companyName}_news`
      }));
    }
    
    if (args.includeCompetitors) {
      tasks.push(this.executeWebSearch({
        query: `${companyName} competitors market share comparison`,
        depth: 'basic',
        cacheAs: `${companyName}_competitors`
      }));
    }
    
    const taskResults = await Promise.all(tasks);
    
    // Aggregate results
    taskResults.forEach((result, index) => {
      const content = JSON.parse(result.content[0].text);
      const sourceType = ['database', 'web_search', 'scraping', 'news', 'competitors'][index];
      results[sourceType] = content;
      results.sources.push(sourceType);
    });
    
    // Synthesize with Claude if available
    if (CLAUDE_API_KEY) {
      const synthesis = await this.synthesizeWithClaude(companyName, results);
      results.synthesis = synthesis;
    }
    
    return {
      content: [{
        type: 'text',
        text: JSON.stringify(results, null, 2)
      }]
    };
  }
  
  /**
   * Execute chain reasoning
   */
  private async executeChainReasoning(args: any) {
    const { query, steps = [] } = args;
    const chainResults: any[] = [];
    
    console.log(`🔗 Starting chain reasoning for: ${query}`);
    
    // If no steps provided, auto-generate them
    if (steps.length === 0) {
      // Auto-detect if it's a company query
      const isCompanyQuery = /[@A-Z][a-zA-Z]+/.test(query);
      
      if (isCompanyQuery) {
        const companyMatch = query.match(/@?([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)*)/);
        const companyName = companyMatch ? companyMatch[1] : query;
        
        steps.push(
          { tool: 'database_lookup', params: { query: companyName }, useOutput: 'db_data' },
          { tool: 'web_search', params: { query: `${companyName} funding valuation` }, useOutput: 'web_data' },
          { tool: 'deep_scrape', params: { companyName }, useOutput: 'scrape_data' },
          { tool: 'synthesize', params: { sources: ['db_data', 'web_data', 'scrape_data'], question: query }, useOutput: 'final' }
        );
      }
    }
    
    // Execute each step in sequence
    for (const step of steps) {
      console.log(`  → Executing ${step.tool}`);
      
      // Replace any variable references in params
      const processedParams = { ...step.params };
      for (const [key, value] of Object.entries(processedParams)) {
        if (typeof value === 'string' && value.startsWith('$')) {
          const varName = value.substring(1);
          processedParams[key] = resultCache.get(varName);
        }
      }
      
      // Execute the tool
      let result;
      switch (step.tool) {
        case 'web_search':
          result = await this.executeWebSearch(processedParams);
          break;
        case 'deep_scrape':
          result = await this.executeDeepScrape(processedParams);
          break;
        case 'database_lookup':
          result = await this.executeDatabaseLookup(processedParams);
          break;
        case 'synthesize':
          result = await this.executeSynthesize(processedParams);
          break;
        default:
          result = { content: [{ type: 'text', text: `Unknown tool: ${step.tool}` }] };
      }
      
      // Store output if needed
      if (step.useOutput) {
        const data = JSON.parse(result.content[0].text);
        resultCache.set(step.useOutput, data);
      }
      
      chainResults.push({
        step: step.tool,
        output: result.content[0].text
      });
    }
    
    return {
      content: [{
        type: 'text',
        text: JSON.stringify({
          query,
          steps: chainResults,
          final: resultCache.get('final') || chainResults[chainResults.length - 1]?.output
        }, null, 2)
      }]
    };
  }
  
  /**
   * Synthesize information from multiple sources
   */
  private async executeSynthesize(args: any) {
    const { sources, question, format = 'detailed' } = args;
    
    // Gather all source data
    const sourceData: any = {};
    for (const source of sources) {
      sourceData[source] = resultCache.get(source);
    }
    
    if (CLAUDE_API_KEY) {
      const synthesis = await this.synthesizeWithClaude(question, sourceData, format);
      return {
        content: [{
          type: 'text',
          text: JSON.stringify({
            question,
            synthesis,
            sources: sources
          }, null, 2)
        }]
      };
    }
    
    // Basic synthesis without Claude
    return {
      content: [{
        type: 'text',
        text: JSON.stringify({
          question,
          data: sourceData,
          sources: sources
        }, null, 2)
      }]
    };
  }
  
  /**
   * Synthesize with Claude
   */
  private async synthesizeWithClaude(question: string, data: any, format: string = 'detailed'): Promise<string> {
    const formatInstructions = {
      summary: 'Provide a brief 2-3 sentence summary',
      detailed: 'Provide a comprehensive analysis with key points and citations',
      comparison: 'Compare and contrast the different data sources'
    };
    
    const prompt = `Synthesize the following information to answer: "${question}"

Data Sources:
${JSON.stringify(data, null, 2).substring(0, 10000)}

Instructions:
- ${formatInstructions[format as keyof typeof formatInstructions]}
- Cite specific sources for each claim
- Use [Source: X] format for citations
- Focus on facts and numbers
- Highlight any conflicting information

Provide your synthesis:`;
    
    try {
      const response = await fetch('https://api.anthropic.com/v1/messages', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'x-api-key': CLAUDE_API_KEY!,
          'anthropic-version': '2023-06-01'
        },
        body: JSON.stringify({
          model: 'claude-3-5-sonnet-20241022',
          max_tokens: 2000,
          messages: [{ role: 'user', content: prompt }]
        })
      });
      
      if (response.ok) {
        const data = await response.json();
        return data.content[0].text;
      }
    } catch (error) {
      console.error('Claude synthesis failed:', error);
    }
    
    return 'Synthesis unavailable';
  }
  
  /**
   * Start the MCP server
   */
  async start() {
    const transport = new StdioServerTransport();
    await this.server.connect(transport);
    console.log('🚀 MCP Server started');
  }
}

// Export for use in other modules
export const mcpServer = new VCPlatformMCPServer();