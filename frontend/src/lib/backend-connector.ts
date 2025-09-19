/**
 * Backend Connector for Advanced Analytics
 * Provides seamless integration between frontend skills and backend MCP orchestrator
 */

export interface BackendAnalyticsRequest {
  company: string;
  analysisType: 'full_research' | 'comps' | 'valuation' | 'pwerm' | 'market' | 'dd';
  depth?: 'quick' | 'standard' | 'deep' | 'exhaustive';
  context?: any;
  outputFormat?: 'json' | 'spreadsheet' | 'deck' | 'markdown';
}

export interface BackendAnalyticsResponse {
  success: boolean;
  analysisType: string;
  depth: string;
  executionTime: number;
  confidence: number;
  
  // Core outputs
  report?: any;
  comparables?: any;
  valuation?: any;
  pwerm?: any;
  marketAnalysis?: any;
  dueDiligence?: any;
  
  // Format-specific
  dataForSpreadsheet?: any;
  slidesForDeck?: any;
  markdownForDocs?: string;
  
  // Metadata
  mcpMetadata?: {
    tasksExecuted: number;
    dataSources: string[];
    toolsUsed: string[];
  };
  
  error?: string;
}

export class BackendConnector {
  private static instance: BackendConnector;
  private baseUrl: string;
  private wsConnection: WebSocket | null = null;
  
  private constructor() {
    // Use environment variable for backend URL
    this.baseUrl = process.env.NEXT_PUBLIC_FASTAPI_URL || process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000';
  }
  
  static getInstance(): BackendConnector {
    if (!BackendConnector.instance) {
      BackendConnector.instance = new BackendConnector();
    }
    return BackendConnector.instance;
  }
  
  /**
   * Perform advanced analytics via backend
   */
  async performAnalytics(request: BackendAnalyticsRequest): Promise<BackendAnalyticsResponse> {
    try {
      const response = await fetch(`${this.baseUrl}/api/advanced-analytics/analyze`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          company: request.company,
          analysis_type: request.analysisType,
          depth: request.depth || 'deep',
          context: request.context,
          output_format: request.outputFormat || 'json'
        })
      });
      
      if (!response.ok) {
        throw new Error(`Backend error: ${response.status}`);
      }
      
      const data = await response.json();
      
      // Transform snake_case to camelCase for frontend
      return this.transformResponse(data);
      
    } catch (error) {
      console.error('[Backend Connector] Analytics error:', error);
      return {
        success: false,
        analysisType: request.analysisType,
        depth: request.depth || 'standard',
        executionTime: 0,
        confidence: 0,
        error: error instanceof Error ? error.message : 'Unknown error'
      };
    }
  }
  
  /**
   * Perform comparable company analysis
   */
  async performComparableAnalysis(
    targetCompany: string,
    peerCompanies: string[],
    metrics?: string[]
  ): Promise<any> {
    try {
      const response = await fetch(`${this.baseUrl}/api/advanced-analytics/compare`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          target_company: targetCompany,
          companies: peerCompanies,
          metrics
        })
      });
      
      if (!response.ok) {
        throw new Error(`Backend error: ${response.status}`);
      }
      
      return await response.json();
      
    } catch (error) {
      console.error('[Backend Connector] Comparable analysis error:', error);
      throw error;
    }
  }
  
  /**
   * Perform PWERM analysis
   */
  async performPWERM(
    company: string,
    scenarios: number = 100,
    includeMonteCarlo: boolean = true
  ): Promise<any> {
    try {
      const response = await fetch(`${this.baseUrl}/api/advanced-analytics/pwerm`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          company,
          scenarios,
          include_monte_carlo: includeMonteCarlo
        })
      });
      
      if (!response.ok) {
        throw new Error(`Backend error: ${response.status}`);
      }
      
      return await response.json();
      
    } catch (error) {
      console.error('[Backend Connector] PWERM error:', error);
      throw error;
    }
  }
  
  /**
   * Perform valuation analysis
   */
  async performValuation(
    company: string,
    methodologies: string[] = ['dcf', 'multiples', 'precedents']
  ): Promise<any> {
    try {
      const response = await fetch(`${this.baseUrl}/api/advanced-analytics/valuation`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          company,
          methodologies
        })
      });
      
      if (!response.ok) {
        throw new Error(`Backend error: ${response.status}`);
      }
      
      return await response.json();
      
    } catch (error) {
      console.error('[Backend Connector] Valuation error:', error);
      throw error;
    }
  }
  
  /**
   * Generate investment deck with analytics
   */
  async generateDeck(
    company: string,
    deckType: string = 'pitch',
    includeAnalytics: boolean = true
  ): Promise<any> {
    try {
      const response = await fetch(`${this.baseUrl}/api/advanced-analytics/generate-deck`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          company,
          deck_type: deckType,
          include_analytics: includeAnalytics
        })
      });
      
      if (!response.ok) {
        throw new Error(`Backend error: ${response.status}`);
      }
      
      return await response.json();
      
    } catch (error) {
      console.error('[Backend Connector] Deck generation error:', error);
      throw error;
    }
  }
  
  /**
   * Get stored analytics report
   */
  async getReport(company: string): Promise<any> {
    try {
      const response = await fetch(`${this.baseUrl}/api/advanced-analytics/report/${company}`);
      
      if (!response.ok) {
        if (response.status === 404) {
          return null;
        }
        throw new Error(`Backend error: ${response.status}`);
      }
      
      return await response.json();
      
    } catch (error) {
      console.error('[Backend Connector] Get report error:', error);
      throw error;
    }
  }
  
  /**
   * Connect to WebSocket for streaming analytics
   */
  connectWebSocket(onMessage: (data: any) => void): void {
    if (this.wsConnection) {
      console.warn('[Backend Connector] WebSocket already connected');
      return;
    }
    
    const wsUrl = this.baseUrl.replace('http', 'ws') + '/ws';
    
    this.wsConnection = new WebSocket(wsUrl);
    
    this.wsConnection.onopen = () => {
      console.log('[Backend Connector] WebSocket connected');
      // Send initial message to identify as analytics client
      this.wsConnection?.send(JSON.stringify({
        type: 'identify',
        client: 'advanced_analytics'
      }));
    };
    
    this.wsConnection.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        onMessage(data);
      } catch (error) {
        console.error('[Backend Connector] WebSocket message parse error:', error);
      }
    };
    
    this.wsConnection.onerror = (error) => {
      console.error('[Backend Connector] WebSocket error:', error);
    };
    
    this.wsConnection.onclose = () => {
      console.log('[Backend Connector] WebSocket disconnected');
      this.wsConnection = null;
    };
  }
  
  /**
   * Send message via WebSocket
   */
  sendWebSocketMessage(message: any): void {
    if (!this.wsConnection || this.wsConnection.readyState !== WebSocket.OPEN) {
      console.error('[Backend Connector] WebSocket not connected');
      return;
    }
    
    this.wsConnection.send(JSON.stringify(message));
  }
  
  /**
   * Disconnect WebSocket
   */
  disconnectWebSocket(): void {
    if (this.wsConnection) {
      this.wsConnection.close();
      this.wsConnection = null;
    }
  }
  
  /**
   * Use MCP orchestrator directly
   */
  async useMCPOrchestrator(prompt: string, context?: any): Promise<any> {
    try {
      const response = await fetch(`${this.baseUrl}/api/mcp/process`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          prompt,
          context,
          auto_decompose: true,
          stream: false
        })
      });
      
      if (!response.ok) {
        throw new Error(`MCP error: ${response.status}`);
      }
      
      return await response.json();
      
    } catch (error) {
      console.error('[Backend Connector] MCP error:', error);
      throw error;
    }
  }
  
  /**
   * Transform snake_case response to camelCase
   */
  private transformResponse(data: any): BackendAnalyticsResponse {
    return {
      success: data.success,
      analysisType: data.analysis_type,
      depth: data.depth,
      executionTime: data.execution_time,
      confidence: data.confidence,
      report: data.report,
      comparables: data.comparables,
      valuation: data.valuation,
      pwerm: data.pwerm,
      marketAnalysis: data.market_analysis,
      dueDiligence: data.due_diligence,
      dataForSpreadsheet: data.data_for_spreadsheet,
      slidesForDeck: data.slides_for_deck,
      markdownForDocs: data.markdown_for_docs,
      mcpMetadata: data.mcp_metadata ? {
        tasksExecuted: data.mcp_metadata.tasks_executed,
        dataSources: data.mcp_metadata.data_sources,
        toolsUsed: data.mcp_metadata.tools_used
      } : undefined,
      error: data.error
    };
  }
  
  /**
   * Check backend health
   */
  async checkHealth(): Promise<boolean> {
    try {
      const response = await fetch(`${this.baseUrl}/health`);
      const data = await response.json();
      return data.status === 'healthy';
    } catch (error) {
      console.error('[Backend Connector] Health check failed:', error);
      return false;
    }
  }
}

// Export singleton instance
export const backendConnector = BackendConnector.getInstance();