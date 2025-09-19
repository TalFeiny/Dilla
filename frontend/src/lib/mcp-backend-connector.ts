/**
 * MCP Backend Connector
 * Bridges the frontend unified brain with the backend MCP orchestrator
 * Handles task decomposition, parallel execution, and result synthesis
 */

export interface MCPTask {
  id: string;
  type: string;
  description: string;
  tool: string;
  parameters: any;
  dependencies?: string[];
  priority?: number;
}

export interface MCPResponse {
  success?: boolean;
  analysis?: string;  // The final analysis from Claude
  tool_calls?: Array<{  // All tool calls made during execution
    tool: string;
    input: any;
    output: any;
  }>;
  total_tool_calls?: number;
  execution_time?: string;
  synthesis?: string;  // Backwards compatibility
  error?: string;
  // Legacy fields for backwards compatibility
  status?: string;
  plan_id?: string;
  prompt?: string;
  tasks?: MCPTask[];
  results?: any[];
  tasks_executed?: number;
  errors?: string[];
  metadata?: {
    frameworks_used?: string[];
    tools_used?: string[];
    data_sources?: string[];
  };
}

export class MCPBackendConnector {
  private static instance: MCPBackendConnector;
  private baseUrl: string = process.env.NEXT_PUBLIC_FASTAPI_URL || process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000';
  private cache = new Map<string, { data: any; timestamp: number }>();
  private cacheTimeout = 5 * 60 * 1000; // 5 minutes
  private maxCacheSize = 100; // Maximum number of cached items
  private cacheCleanupInterval: NodeJS.Timeout | null = null;

  static getInstance(): MCPBackendConnector {
    if (!MCPBackendConnector.instance) {
      MCPBackendConnector.instance = new MCPBackendConnector();
      // Start cache cleanup interval
      MCPBackendConnector.instance.startCacheCleanup();
    }
    return MCPBackendConnector.instance;
  }

  /**
   * Start periodic cache cleanup
   */
  private startCacheCleanup(): void {
    // Clean up expired cache entries every minute
    this.cacheCleanupInterval = setInterval(() => {
      const now = Date.now();
      const keysToDelete: string[] = [];
      
      // Find expired entries
      for (const [key, value] of this.cache.entries()) {
        if (now - value.timestamp > this.cacheTimeout) {
          keysToDelete.push(key);
        }
      }
      
      // Delete expired entries
      keysToDelete.forEach(key => this.cache.delete(key));
      
      // If cache is still too large, remove oldest entries
      if (this.cache.size > this.maxCacheSize) {
        const sortedEntries = Array.from(this.cache.entries())
          .sort((a, b) => a[1].timestamp - b[1].timestamp);
        
        const toRemove = sortedEntries.slice(0, this.cache.size - this.maxCacheSize);
        toRemove.forEach(([key]) => this.cache.delete(key));
      }
    }, 60000); // Run every minute
  }

  /**
   * Process a prompt through the single agent MCP orchestrator
   * Uses ONE continuous Claude conversation that:
   * 1. Internally decomposes the request
   * 2. Gathers data using tool calls
   * 3. Analyzes using tool calls  
   * 4. Formats the final output
   * All in a single API call with tool usage.
   */
  async processPrompt(
    prompt: string,
    context: any = {},
    options: {
      stream?: boolean;
      outputFormat?: string;
      useCache?: boolean;
      timeout?: number;
    } = {}
  ): Promise<MCPResponse> {
    // Check cache if enabled
    if (options.useCache) {
      const cacheKey = `${prompt}_${JSON.stringify(context)}`;
      const cached = this.cache.get(cacheKey);
      if (cached && Date.now() - cached.timestamp < this.cacheTimeout) {
        console.log('[MCP Connector] Using cached response');
        return cached.data;
      }
    }

    try {
      const controller = new AbortController();
      const timeout = options.timeout || 30000; // 30 seconds default
      const timeoutId = setTimeout(() => controller.abort(), timeout);

      // Use the new single agent endpoint
      const response = await fetch(`${this.baseUrl}/api/mcp/agent`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        signal: controller.signal,
        body: JSON.stringify({
          prompt,
          context: {
            ...context,
            output_format: options.outputFormat || 'analysis',
          },
          stream: options.stream || false,
        }),
      });

      clearTimeout(timeoutId);

      if (!response.ok) {
        const error = await response.text();
        console.error('[MCP Connector] API error:', error);
        throw new Error(`MCP API error: ${response.status}`);
      }

      if (options.stream) {
        // Handle streaming response
        return this.handleStreamingResponse(response);
      } else {
        const data = await response.json();
        
        // Normalize response - backend doesn't always return 'success' field
        if (data.success === undefined) {
          // Infer success from status or results
          data.success = data.status === 'completed' || (data.results && data.results.length > 0) || data.tasks_executed > 0;
        }
        
        // Cache successful responses with size limit
        if (options.useCache && data.success) {
          const cacheKey = `${prompt}_${JSON.stringify(context)}`;
          
          // Check cache size before adding
          if (this.cache.size >= this.maxCacheSize) {
            // Remove oldest entry
            const oldestKey = Array.from(this.cache.entries())
              .sort((a, b) => a[1].timestamp - b[1].timestamp)[0]?.[0];
            if (oldestKey) this.cache.delete(oldestKey);
          }
          
          this.cache.set(cacheKey, { data, timestamp: Date.now() });
        }

        return data;
      }
    } catch (error: any) {
      if (error.name === 'AbortError') {
        console.error('[MCP Connector] Request timeout');
        return {
          success: false,
          errors: ['Request timeout - MCP orchestrator took too long to respond'],
        };
      }
      
      console.error('[MCP Connector] Error:', error);
      return {
        success: false,
        errors: [error.message || 'Failed to connect to MCP orchestrator'],
      };
    }
  }

  /**
   * Decompose a prompt without executing
   * Useful for understanding task breakdown
   */
  async decomposePrompt(prompt: string, context: any = {}): Promise<MCPTask[]> {
    try {
      const response = await fetch(`${this.baseUrl}/api/mcp/decompose`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ prompt, context }),
      });

      if (!response.ok) {
        throw new Error(`Decompose API error: ${response.status}`);
      }

      const data = await response.json();
      return data.tasks || [];
    } catch (error) {
      console.error('[MCP Connector] Decompose error:', error);
      return [];
    }
  }

  /**
   * Execute a specific task directly
   */
  async executeTask(
    taskType: string,
    tool: string,
    parameters: any
  ): Promise<any> {
    try {
      const response = await fetch(`${this.baseUrl}/api/mcp/execute-task`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          task_type: taskType,
          tool,
          parameters,
        }),
      });

      if (!response.ok) {
        throw new Error(`Execute task API error: ${response.status}`);
      }

      return await response.json();
    } catch (error) {
      console.error('[MCP Connector] Execute task error:', error);
      return null;
    }
  }

  /**
   * Get available tools and their status
   */
  async getToolsStatus(): Promise<any> {
    try {
      const response = await fetch(`${this.baseUrl}/api/mcp/tools/status`);
      if (!response.ok) {
        throw new Error(`Tools status API error: ${response.status}`);
      }
      return await response.json();
    } catch (error) {
      console.error('[MCP Connector] Tools status error:', error);
      return null;
    }
  }

  /**
   * Call PWERM valuation API
   */
  async callPWERM(data: any): Promise<any> {
    try {
      const response = await fetch(`${this.baseUrl}/api/pwerm/calculate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data),
      });

      if (!response.ok) {
        throw new Error(`PWERM API error: ${response.status}`);
      }

      return await response.json();
    } catch (error) {
      console.error('[MCP Connector] PWERM error:', error);
      return null;
    }
  }

  /**
   * Call RL recommendation system
   */
  async getRecommendations(context: any): Promise<any> {
    try {
      const response = await fetch(`${this.baseUrl}/api/rl/recommend`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(context),
      });

      if (!response.ok) {
        throw new Error(`RL API error: ${response.status}`);
      }

      return await response.json();
    } catch (error) {
      console.error('[MCP Connector] RL recommendations error:', error);
      return null;
    }
  }

  /**
   * Handle streaming responses from MCP
   */
  private async handleStreamingResponse(response: Response): Promise<MCPResponse> {
    const reader = response.body?.getReader();
    if (!reader) {
      throw new Error('No response body');
    }

    const decoder = new TextDecoder();
    const results: any[] = [];
    let lastData: any = null;

    try {
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value);
        const lines = chunk.split('\n');

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.slice(6));
              results.push(data);
              lastData = data;
            } catch (e) {
              // Skip invalid JSON
            }
          }
        }
      }

      // Return the final synthesis or last result
      return lastData || { success: true, results };
    } catch (error) {
      console.error('[MCP Connector] Streaming error:', error);
      return { success: false, errors: ['Streaming error'] };
    }
  }

  /**
   * Transform MCP results for skill orchestrator consumption
   */
  transformForSkillOrchestrator(mcpResponse: MCPResponse): any {
    // Check if response has data
    if (!mcpResponse.success && !mcpResponse.results && !mcpResponse.tasks_executed) {
      return null;
    }

    // Extract structured data from synthesis or results
    const structuredData: any = {
      companies: {},
      markets: {},
      financials: {},
      insights: [],
      metrics: {},
      sources: [],
    };

    // Parse synthesis if available
    if (mcpResponse.synthesis) {
      // Extract company data
      const companyMatches = mcpResponse.synthesis.match(/@(\w+)/g);
      if (companyMatches) {
        companyMatches.forEach(match => {
          const company = match.slice(1);
          structuredData.companies[company] = {
            mentioned: true,
            needsData: true,
          };
        });
      }

      // Store raw synthesis
      structuredData.rawSynthesis = mcpResponse.synthesis;
    }

    // Process individual results
    if (mcpResponse.results) {
      mcpResponse.results.forEach(result => {
        if (result.tool === 'tavily' && result.data) {
          structuredData.sources.push(...(result.data.sources || []));
          structuredData.insights.push(...(result.data.insights || []));
        } else if (result.tool === 'firecrawl' && result.data) {
          // Extract structured data from Firecrawl results
          if (result.data.metrics) {
            Object.assign(structuredData.metrics, result.data.metrics);
          }
        }
      });
    }

    // Add metadata
    structuredData.metadata = mcpResponse.metadata || {};
    structuredData.executionTime = mcpResponse.execution_time;
    structuredData.tasksExecuted = mcpResponse.tasks_executed;

    return structuredData;
  }

  /**
   * Clear cache and stop cleanup interval
   */
  clearCache(): void {
    this.cache.clear();
    console.log('[MCP Connector] Cache cleared');
  }

  /**
   * Destroy the connector instance and clean up resources
   */
  destroy(): void {
    if (this.cacheCleanupInterval) {
      clearInterval(this.cacheCleanupInterval);
      this.cacheCleanupInterval = null;
    }
    this.clearCache();
  }
}

// Export singleton instance
export const mcpBackendConnector = MCPBackendConnector.getInstance();