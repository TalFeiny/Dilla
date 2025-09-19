import { IFormatHandler, UnifiedBrainContext, FormatHandlerResult } from './types';

export class DefaultHandler implements IFormatHandler {
  getFormat(): string {
    return 'default';
  }

  async format(context: UnifiedBrainContext): Promise<FormatHandlerResult> {
    const { text, citations, extractedCompanies } = context;
    
    // For unknown formats, return as is
    const result = { content: text };
    
    return {
      success: true,
      result,
      citations,
      metadata: {
        companies: extractedCompanies,
        timestamp: new Date().toISOString(),
        format: 'default'
      }
    };
  }
  
  validate(result: any): boolean {
    return true; // Default always validates
  }
}