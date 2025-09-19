import { IFormatHandler, UnifiedBrainContext, FormatHandlerResult } from './types';

export class DocsHandler implements IFormatHandler {
  getFormat(): string {
    return 'docs';
  }

  async format(context: UnifiedBrainContext): Promise<FormatHandlerResult> {
    const { text, financialAnalyses, charts, citations, extractedCompanies } = context;
    
    // Try to parse the backend response
    let parsedData: any = text;
    if (typeof text === 'string') {
      try {
        parsedData = JSON.parse(text);
      } catch {
        // Not JSON, treat as raw content
        parsedData = null;
      }
    }
    
    // Check for new unified backend structure
    if (parsedData && parsedData.format === 'docs') {
      console.log('[DocsHandler] Using unified backend docs data');
      
      const result = {
        content: parsedData.content || '',
        sections: parsedData.sections || [],
        toc: parsedData.toc || [],
        charts: parsedData.charts || charts || [],
        chartBatch: true, // Always batch process charts
        chartPositions: (parsedData.charts || charts || []).map((_: any, index: number) => ({
          afterParagraph: Math.floor((index + 1) * 3),
          inline: true
        })),
        financialAnalyses: parsedData.financialAnalyses || financialAnalyses || [],
        metadata: parsedData.metadata || {}
      };
      
      return {
        success: true,
        result,
        citations: parsedData.citations || citations || [],
        metadata: {
          companies: parsedData.companies || extractedCompanies || [],
          timestamp: result.metadata.timestamp || new Date().toISOString(),
          format: 'docs',
          hasCharts: result.charts.length > 0
        }
      };
    }
    
    // Legacy format: treat as raw content
    // Process charts as batch to prevent re-render loops
    const processedCharts = charts && charts.length > 0 ? {
      charts: charts,
      chartBatch: true, // Flag for batch processing
      chartPositions: charts.map((_, index) => ({
        // Automatically position charts throughout the document
        afterParagraph: Math.floor((index + 1) * 3), // Every 3 paragraphs
        inline: true
      }))
    } : { charts: [] };
    
    // For docs, include financial analysis inline
    const result = { 
      content: typeof text === 'string' ? text : JSON.stringify(text),
      financialAnalyses: financialAnalyses || [],
      ...processedCharts
    };
    
    return {
      success: true,
      result,
      citations,
      metadata: {
        companies: extractedCompanies,
        timestamp: new Date().toISOString(),
        format: 'docs',
        hasCharts: charts && charts.length > 0
      }
    };
  }
  
  validate(result: any): boolean {
    return result?.content !== undefined;
  }
}