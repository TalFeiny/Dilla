/**
 * Format Handler Types
 * Defines the interface for handling different output formats from unified-brain
 */

export interface UnifiedBrainContext {
  text: string;                       // Claude's response text
  contextData: string;                 // Aggregated context data
  companiesData: [string, any][];     // Company research cache entries
  financialAnalyses: any[];            // Financial calculations and analyses
  charts: any[];                       // Generated charts
  advancedCharts?: any[];              // Advanced chart configurations
  citations: any[];                    // Citation entries
  requestAnalysis: any;                // Request analysis metadata
  skillResults: any;                   // Skill execution results
  extractedCompanies: string[];        // Companies extracted from @ mentions
  mentionedCompanies: string[];        // All identified companies
  rlRecommendations?: any[];           // RL system recommendations
  taskId?: string;                     // Task tracking ID
}

export interface FormatHandlerResult {
  success: boolean;
  result: any;
  citations?: any[];
  metadata?: {
    companies?: string[];
    timestamp?: string;
    format?: string;
  };
}

export interface IFormatHandler {
  /**
   * Format the unified brain context into specific output format
   */
  format(context: UnifiedBrainContext): Promise<FormatHandlerResult>;
  
  /**
   * Validate the formatted result
   */
  validate(result: any): boolean;
  
  /**
   * Get the format name this handler supports
   */
  getFormat(): string;
}