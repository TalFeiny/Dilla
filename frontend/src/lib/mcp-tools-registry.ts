/**
 * MCP Tools Registry
 * Unified interface for all agent tools using Model Context Protocol
 */

export interface MCPTool {
  name: string;
  description: string;
  inputSchema: {
    type: 'object';
    properties: Record<string, any>;
    required?: string[];
  };
  handler: (args: any) => Promise<any>;
}

export class MCPToolsRegistry {
  private tools: Map<string, MCPTool> = new Map();
  
  constructor() {
    this.registerBuiltInTools();
  }
  
  /**
   * Register all available tools
   */
  private registerBuiltInTools() {
    // 1. Tavily Search Tool
    this.registerTool({
      name: 'tavily_search',
      description: 'Search the web for latest information, news, and data about companies or topics',
      inputSchema: {
        type: 'object',
        properties: {
          query: { 
            type: 'string', 
            description: 'Search query (e.g., "Stripe funding 2024")' 
          },
          searchDepth: { 
            type: 'string', 
            enum: ['basic', 'advanced'],
            description: 'Search depth - advanced for more results'
          },
          maxResults: {
            type: 'number',
            description: 'Maximum number of results (default 5)'
          }
        },
        required: ['query']
      },
      handler: async (args) => {
        const TAVILY_API_KEY = process.env.TAVILY_API_KEY;
        if (!TAVILY_API_KEY) {
          return { error: 'Tavily not configured' };
        }
        
        const response = await fetch('https://api.tavily.com/search', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            api_key: TAVILY_API_KEY,
            query: args.query,
            search_depth: args.searchDepth || 'advanced',
            max_results: args.maxResults || 5,
            include_answer: true,
            include_raw_content: true
          })
        });
        
        const data = await response.json();
        return {
          results: data.results,
          answer: data.answer,
          sources: data.results?.map((r: any) => ({
            title: r.title,
            url: r.url,
            snippet: r.content?.substring(0, 200)
          }))
        };
      }
    });
    
    // 2. Firecrawl Scraping Tool
    this.registerTool({
      name: 'firecrawl_scrape',
      description: 'Deep scrape a website to extract structured data, funding info, team, and financials',
      inputSchema: {
        type: 'object',
        properties: {
          url: { 
            type: 'string', 
            description: 'URL to scrape' 
          },
          companyName: {
            type: 'string',
            description: 'Company name (if no URL provided, will find website)'
          },
          depth: {
            type: 'number',
            description: 'Crawl depth (1-5 pages)'
          }
        }
      },
      handler: async (args) => {
        // Call the CIM scraper which uses Firecrawl
        const response = await fetch('/api/agent/company-cim', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            company_name: args.companyName,
            company_url: args.url,
            refresh: true
          })
        });
        
        const data = await response.json();
        return {
          profile: data.cim,
          sources: [args.url || `${args.companyName}.com`]
        };
      }
    });
    
    // 3. Database Search Tool
    this.registerTool({
      name: 'database_search',
      description: 'Search internal database for company information, funding data, and metrics',
      inputSchema: {
        type: 'object',
        properties: {
          query: { 
            type: 'string', 
            description: 'Company name or search term' 
          },
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
      },
      handler: async (args) => {
        const { createClient } = await import('@supabase/supabase-js');
        const supabase = createClient(
          process.env.NEXT_PUBLIC_SUPABASE_URL!,
          process.env.SUPABASE_SERVICE_ROLE_KEY!
        );
        
        let query = supabase
          .from('companies')
          .select('*')
          .ilike('name', `%${args.query}%`);
        
        if (args.filters?.sector) {
          query = query.eq('sector', args.filters.sector);
        }
        
        const { data, error } = await query.limit(10);
        
        return {
          companies: data || [],
          source: 'Internal Database',
          count: data?.length || 0
        };
      }
    });
    
    // 4. Financial Calculation Tool
    this.registerTool({
      name: 'financial_calculator',
      description: 'Perform complex financial calculations (DCF, IRR, LTV, unit economics)',
      inputSchema: {
        type: 'object',
        properties: {
          calculation: {
            type: 'string',
            enum: ['dcf', 'irr', 'npv', 'ltv', 'cac', 'wacc', 'option_pricing'],
            description: 'Type of calculation'
          },
          inputs: {
            type: 'object',
            description: 'Calculation inputs (varies by type)'
          }
        },
        required: ['calculation', 'inputs']
      },
      handler: async (args) => {
        const { mathEngine } = await import('./agent-math-engine');
        
        switch (args.calculation) {
          case 'dcf':
            // DCF calculation with citations
            return {
              result: 'DCF calculation',
              formula: 'NPV = Σ[CFt / (1+r)^t]',
              source: 'Mathematical calculation'
            };
          case 'irr':
            return mathEngine.calculateIRR(args.inputs.cashFlows);
          case 'ltv':
            return mathEngine.calculateLTV(args.inputs);
          default:
            return { error: 'Unknown calculation type' };
        }
      }
    });
    
    // 5. Python Execution Tool
    this.registerTool({
      name: 'python_execute',
      description: 'Execute Python code for complex data analysis and modeling',
      inputSchema: {
        type: 'object',
        properties: {
          code: {
            type: 'string',
            description: 'Python code to execute'
          },
          inputs: {
            type: 'object',
            description: 'Input variables for the code'
          }
        },
        required: ['code']
      },
      handler: async (args) => {
        const response = await fetch('/api/agent/python-exec', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(args)
        });
        
        return response.json();
      }
    });
    
    // 6. Market Intelligence Tool
    this.registerTool({
      name: 'market_intelligence',
      description: 'Gather market intelligence, comparables, and competitive analysis',
      inputSchema: {
        type: 'object',
        properties: {
          company: {
            type: 'string',
            description: 'Company to analyze'
          },
          analysisType: {
            type: 'string',
            enum: ['comparables', 'competitors', 'market_size', 'all'],
            description: 'Type of market analysis'
          }
        },
        required: ['company']
      },
      handler: async (args) => {
        const response = await fetch('/api/agent/market-intelligence', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            prompt: `${args.company} ${args.analysisType || 'all'}`
          })
        });
        
        return response.json();
      }
    });
  }
  
  /**
   * Register a new tool
   */
  registerTool(tool: MCPTool) {
    this.tools.set(tool.name, tool);
    console.log(`✅ Registered MCP tool: ${tool.name}`);
  }
  
  /**
   * Get all available tools (for agent discovery)
   */
  getAvailableTools(): Array<{
    name: string;
    description: string;
    inputSchema: any;
  }> {
    return Array.from(this.tools.values()).map(tool => ({
      name: tool.name,
      description: tool.description,
      inputSchema: tool.inputSchema
    }));
  }
  
  /**
   * Execute a tool by name
   */
  async executeTool(toolName: string, args: any): Promise<any> {
    const tool = this.tools.get(toolName);
    
    if (!tool) {
      return {
        error: `Tool ${toolName} not found`,
        availableTools: Array.from(this.tools.keys())
      };
    }
    
    try {
      console.log(`🔧 Executing MCP tool: ${toolName}`, args);
      const result = await tool.handler(args);
      
      // Always include source attribution
      return {
        ...result,
        _metadata: {
          tool: toolName,
          timestamp: new Date().toISOString(),
          source: `MCP Tool: ${toolName}`
        }
      };
    } catch (error) {
      console.error(`Error executing tool ${toolName}:`, error);
      return {
        error: error.message,
        tool: toolName
      };
    }
  }
  
  /**
   * Get tool schema for Claude to understand
   */
  getToolSchemaForClaude(): string {
    const tools = this.getAvailableTools();
    
    return `You have access to the following MCP tools:

${tools.map(tool => `
Tool: ${tool.name}
Description: ${tool.description}
Input: ${JSON.stringify(tool.inputSchema, null, 2)}
`).join('\n')}

To use a tool, specify:
<tool_use>
{
  "tool": "tool_name",
  "arguments": { ... }
}
</tool_use>

IMPORTANT: Always cite the source as [Source: MCP Tool - {tool_name}] when using tool results.`;
  }
}

export const mcpRegistry = new MCPToolsRegistry();