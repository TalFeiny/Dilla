import { IFormatHandler, UnifiedBrainContext, FormatHandlerResult } from './types';

export class MarketAnalysisHandler implements IFormatHandler {
  getFormat(): string {
    return 'market-analysis';
  }

  async format(context: UnifiedBrainContext): Promise<FormatHandlerResult> {
    const { text, citations, extractedCompanies } = context;
    
    let result;
    
    // Parse JSON for market/audit/fund analysis
    try {
      result = JSON.parse(text);
    } catch {
      // If not valid JSON, try to extract it
      const jsonMatch = text.match(/\{[\s\S]*\}/);
      if (jsonMatch) {
        try {
          result = JSON.parse(jsonMatch[0]);
        } catch {
          result = { error: 'Failed to parse analysis', raw: text };
        }
      } else {
        result = { error: 'Invalid format', raw: text };
      }
    }
    
    return {
      success: true,
      result,
      citations,
      metadata: {
        companies: extractedCompanies,
        timestamp: new Date().toISOString(),
        format: 'market-analysis'
      }
    };
  }
  
  validate(result: any): boolean {
    return result !== undefined && !result.error;
  }
}