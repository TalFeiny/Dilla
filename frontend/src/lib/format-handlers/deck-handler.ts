import { IFormatHandler, UnifiedBrainContext, FormatHandlerResult } from './types';

export class DeckHandler implements IFormatHandler {
  getFormat(): string {
    return 'deck';
  }

  async format(context: UnifiedBrainContext): Promise<FormatHandlerResult> {
    const { text, financialAnalyses, citations, extractedCompanies } = context;
    
    try {
      // Try direct JSON parse first
      const result = JSON.parse(text);
      
      // Enhance with additional data
      if (financialAnalyses && financialAnalyses.length > 0) {
        result.financialAnalyses = financialAnalyses;
      }
      
      if (citations && citations.length > 0) {
        result.citations = citations;
      }
      
      return {
        success: true,
        result,
        citations,
        metadata: {
          companies: extractedCompanies,
          timestamp: new Date().toISOString(),
          format: 'deck'
        }
      };
    } catch (parseError) {
      // If direct parse fails, try cleaning the JSON
      return this.parseWithCleaning(text, context);
    }
  }
  
  private async parseWithCleaning(
    text: string, 
    context: UnifiedBrainContext
  ): Promise<FormatHandlerResult> {
    const { financialAnalyses, citations, extractedCompanies } = context;
    
    try {
      // Extract JSON from markdown if wrapped
      let jsonText = text;
      if (text.includes('```json')) {
        const match = text.match(/```json\s*([\s\S]*?)\s*```/);
        if (match) {
          jsonText = match[1];
        }
      }
      
      // Try to find JSON object in the text
      const jsonMatch = jsonText.match(/\{[\s\S]*\}/);
      if (!jsonMatch) {
        return {
          success: false,
          result: { error: 'No JSON found in response', raw: text },
          metadata: { format: 'deck' }
        };
      }
      
      // Clean the JSON
      let cleanedJson = jsonMatch[0]
        // Remove comments
        .replace(/\/\/.*$/gm, '')
        .replace(/\/\*[\s\S]*?\*\//g, '')
        // Remove trailing commas
        .replace(/,(\s*[}\]])/g, '$1')
        // Fix unescaped characters in strings
        .replace(/"([^"\\]*(\\.[^"\\]*)*)"/g, (match, content) => {
          return '"' + content
            .replace(/\n/g, '\\n')
            .replace(/\r/g, '\\r')
            .replace(/\t/g, '\\t') + '"';
        })
        // Remove control characters
        .replace(/[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]/g, '');
      
      const result = JSON.parse(cleanedJson);
      
      // Enhance with additional data
      if (financialAnalyses && financialAnalyses.length > 0) {
        result.financialAnalyses = financialAnalyses;
      }
      
      if (citations && citations.length > 0) {
        result.citations = citations;
      }
      
      return {
        success: true,
        result,
        citations,
        metadata: {
          companies: extractedCompanies,
          timestamp: new Date().toISOString(),
          format: 'deck'
        }
      };
    } catch (error) {
      console.error('[DeckHandler] Failed to parse deck JSON:', error);
      return {
        success: false,
        result: { 
          error: 'Failed to parse deck content', 
          raw: text,
          details: (error as any).message 
        },
        metadata: { format: 'deck' }
      };
    }
  }
  
  validate(result: any): boolean {
    return result && !result.error && typeof result === 'object';
  }
}