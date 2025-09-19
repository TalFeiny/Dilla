import { IFormatHandler, UnifiedBrainContext, FormatHandlerResult } from './types';

export class DocsHandler implements IFormatHandler {
  getFormat(): string {
    return 'docs';
  }

  async format(context: UnifiedBrainContext): Promise<FormatHandlerResult> {
    const { text, financialAnalyses, charts, citations, extractedCompanies } = context;
    
    // For docs, include financial analysis inline
    const result = { 
      content: text,
      financialAnalyses: financialAnalyses || [],
      charts: charts || []
    };
    
    return {
      success: true,
      result,
      citations,
      metadata: {
        companies: extractedCompanies,
        timestamp: new Date().toISOString(),
        format: 'docs'
      }
    };
  }
  
  validate(result: any): boolean {
    return result?.content !== undefined;
  }
}