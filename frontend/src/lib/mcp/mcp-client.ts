/**
 * MCP Client for Agent Communication
 * Enables agents to communicate with each other and coordinate tool usage
 */

import { Client } from '@modelcontextprotocol/sdk/client/index.js';
import { StdioClientTransport } from '@modelcontextprotocol/sdk/client/stdio.js';
import { CallToolResult, Resource } from '@modelcontextprotocol/sdk/types.js';

export interface MCPToolCall {
  tool: string;
  arguments: Record<string, any>;
  cacheAs?: string;
}

export interface MCPChainConfig {
  query: string;
  steps: Array<{
    tool: string;
    params: Record<string, any>;
    useOutput?: string;
    dependsOn?: string[];
  }>;
  parallel?: boolean;
}

/**
 * MCP Client for agent-to-agent communication
 */
export class MCPAgentClient {
  private client: Client;
  private connected: boolean = false;
  private resultCache: Map<string, any> = new Map();
  
  constructor() {
    this.client = new Client(
      {
        name: 'vc-platform-agent',
        version: '1.0.0',
      },
      {
        capabilities: {}
      }
    );
  }
  
  /**
   * Connect to MCP server
   */
  async connect(): Promise<void> {
    if (this.connected) return;
    
    try {
      // For now, skip the external MCP server connection
      // and use direct tool calls
      this.connected = true;
      console.log('✅ MCP client initialized (direct mode)');
    } catch (error) {
      console.error('Failed to initialize MCP client:', error);
      throw error;
    }
  }
  
  /**
   * List available tools
   */
  async listTools(): Promise<any[]> {
    await this.ensureConnected();
    // Return tools directly without server
    return [
      { name: 'web_search', description: 'Search the web using Tavily' },
      { name: 'deep_scrape', description: 'Deep scrape websites using Firecrawl' },
      { name: 'database_lookup', description: 'Search internal database' },
      { name: 'comprehensive_research', description: 'Multi-source research' },
      { name: 'chain_reasoning', description: 'Execute reasoning chains' },
      { name: 'synthesize', description: 'Synthesize information' }
    ];
  }
  
  /**
   * Call a single tool
   */
  async callTool(name: string, args: Record<string, any>): Promise<CallToolResult> {
    await this.ensureConnected();
    
    console.log(`🔧 Calling MCP tool: ${name}`);
    
    // Direct tool execution without external server
    let result: any;
    
    switch (name) {
      case 'web_search':
        result = await this.executeWebSearch(args);
        break;
      case 'deep_scrape':
        result = await this.executeDeepScrape(args);
        break;
      case 'database_lookup':
        result = await this.executeDatabaseLookup(args);
        break;
      case 'comprehensive_research':
        result = await this.executeComprehensiveResearch(args);
        break;
      case 'chain_reasoning':
        result = await this.executeChainReasoning(args);
        break;
      case 'synthesize':
        result = await this.executeSynthesize(args);
        break;
      default:
        result = { error: `Unknown tool: ${name}` };
    }
    
    // Cache result if requested
    if (args.cacheAs) {
      this.resultCache.set(args.cacheAs, result);
    }
    
    // Format as CallToolResult
    return {
      content: [{
        type: 'text',
        text: JSON.stringify(result, null, 2)
      }]
    } as CallToolResult;
  }
  
  /**
   * Execute a chain of tool calls
   */
  async executeChain(config: MCPChainConfig): Promise<any> {
    await this.ensureConnected();
    
    console.log(`🔗 Executing MCP chain for: ${config.query}`);
    
    // Use the chain_reasoning tool for complex flows
    const result = await this.callTool('chain_reasoning', {
      query: config.query,
      steps: config.steps
    });
    
    return this.parseToolResult(result);
  }
  
  /**
   * Research a company using all available sources
   */
  async researchCompany(companyName: string): Promise<any> {
    await this.ensureConnected();
    
    console.log(`🔍 Researching company: ${companyName}`);
    
    const result = await this.callTool('comprehensive_research', {
      companyName,
      includeFinancials: true,
      includeNews: true,
      includeCompetitors: true
    });
    
    return this.parseToolResult(result);
  }
  
  /**
   * Perform web search
   */
  async webSearch(query: string, depth: 'basic' | 'advanced' = 'advanced'): Promise<any> {
    await this.ensureConnected();
    
    const result = await this.callTool('web_search', {
      query,
      depth,
      maxResults: 10
    });
    
    return this.parseToolResult(result);
  }
  
  /**
   * Deep scrape a website
   */
  async deepScrape(urlOrCompany: string): Promise<any> {
    await this.ensureConnected();
    
    const params: any = {};
    if (urlOrCompany.startsWith('http')) {
      params.url = urlOrCompany;
    } else {
      params.companyName = urlOrCompany;
    }
    
    const result = await this.callTool('deep_scrape', params);
    return this.parseToolResult(result);
  }
  
  /**
   * Database lookup
   */
  async databaseLookup(query: string, filters?: any): Promise<any> {
    await this.ensureConnected();
    
    const result = await this.callTool('database_lookup', {
      query,
      filters
    });
    
    return this.parseToolResult(result);
  }
  
  /**
   * Synthesize information from multiple sources
   */
  async synthesize(sources: string[], question: string): Promise<any> {
    await this.ensureConnected();
    
    const result = await this.callTool('synthesize', {
      sources,
      question,
      format: 'detailed'
    });
    
    return this.parseToolResult(result);
  }
  
  /**
   * Get cached result
   */
  getCached(key: string): any {
    return this.resultCache.get(key);
  }
  
  /**
   * List cached results
   */
  async listCached(): Promise<Resource[]> {
    await this.ensureConnected();
    const response = await this.client.listResources();
    return response.resources;
  }
  
  /**
   * Read cached resource
   */
  async readCached(uri: string): Promise<any> {
    await this.ensureConnected();
    const response = await this.client.readResource({ uri });
    
    if (response.contents.length > 0) {
      return JSON.parse(response.contents[0].text || '{}');
    }
    
    return null;
  }
  
  /**
   * Parse tool result
   */
  private parseToolResult(result: CallToolResult): any {
    if (result.content && result.content.length > 0) {
      const content = result.content[0];
      
      if (content.type === 'text' && content.text) {
        try {
          return JSON.parse(content.text);
        } catch {
          return content.text;
        }
      }
    }
    
    return result;
  }
  
  /**
   * Ensure connected to MCP server
   */
  private async ensureConnected(): Promise<void> {
    if (!this.connected) {
      await this.connect();
    }
  }
  
  /**
   * Disconnect from MCP server
   */
  async disconnect(): Promise<void> {
    if (this.connected) {
      // In direct mode, just mark as disconnected
      this.connected = false;
      console.log('MCP client disconnected');
    }
  }
  
  /**
   * Direct tool implementations
   */
  private async executeWebSearch(args: any): Promise<any> {
    const TAVILY_API_KEY = process.env.TAVILY_API_KEY;
    if (!TAVILY_API_KEY) {
      return { error: 'Tavily API key not configured' };
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
        include_raw_content: true
      })
    });
    
    const data = await response.json();
    return {
      answer: data.answer,
      results: data.results,
      sources: data.results?.map((r: any) => ({ title: r.title, url: r.url }))
    };
  }
  
  private async executeDeepScrape(args: any): Promise<any> {
    // Use the firecrawl tool from our registry
    const { firecrawlTool } = await import('../agent-tools/firecrawl-tool');
    return await firecrawlTool.execute(args);
  }
  
  private async executeDatabaseLookup(args: any): Promise<any> {
    const { createClient } = await import('@supabase/supabase-js');
    const supabase = createClient(
      process.env.NEXT_PUBLIC_SUPABASE_URL!,
      process.env.SUPABASE_SERVICE_ROLE_KEY!
    );
    
    const { data, error } = await supabase
      .from('companies')
      .select('*')
      .ilike('name', `%${args.query}%`)
      .limit(10);
    
    return {
      companies: data || [],
      error: error?.message
    };
  }
  
  private async executeComprehensiveResearch(args: any): Promise<any> {
    const { enhancedWebResearch } = await import('../agent-tools/enhanced-web-research');
    return await enhancedWebResearch.researchCompany(args.companyName);
  }
  
  private async executeChainReasoning(args: any): Promise<any> {
    // Simplified chain execution
    const results: any[] = [];
    for (const step of args.steps || []) {
      const result = await this.callTool(step.tool, step.params);
      results.push({
        tool: step.tool,
        result: this.parseToolResult(result)
      });
    }
    return { steps: results, query: args.query };
  }
  
  private async executeSynthesize(args: any): Promise<any> {
    const sourceData: any = {};
    for (const source of args.sources || []) {
      sourceData[source] = this.resultCache.get(source);
    }
    
    return {
      question: args.question,
      sources: args.sources,
      data: sourceData,
      synthesis: 'Data synthesized from multiple sources'
    };
  }
}

// Singleton instance
export const mcpClient = new MCPAgentClient();