import { IFormatHandler, UnifiedBrainContext, FormatHandlerResult } from './types';

export class DeckHandler implements IFormatHandler {
  getFormat(): string {
    return 'deck';
  }

  async format(context: UnifiedBrainContext): Promise<FormatHandlerResult> {
    const { text, financialAnalyses, citations, extractedCompanies, charts } = context;
    
    try {
      // Try to parse the backend response
      let parsedData: any = text;
      if (typeof text === 'string') {
        parsedData = JSON.parse(text);
      }
      
      // Check for new unified backend structure
      if (parsedData && parsedData.format === 'deck') {
        console.log('[DeckHandler] Using unified backend deck data');
        
        const result = {
          slides: parsedData.slides || [],
          theme: parsedData.theme || 'professional',
          transitions: parsedData.transitions || 'fade',
          charts: parsedData.charts || charts || [],
          chartBatch: true, // Always batch process charts
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
            format: 'deck'
          }
        };
      }
      
      // Legacy format: Try direct JSON parse
      const result = JSON.parse(JSON.stringify(parsedData));
      
      // Enhance with additional data
      if (financialAnalyses && financialAnalyses.length > 0) {
        result.financialAnalyses = financialAnalyses;
      }
      
      if (citations && citations.length > 0) {
        result.citations = citations;
      }
      
      // Add charts to slides if available - Process as batch to prevent loops
      if (charts && charts.length > 0) {
        // Store all charts as a batch
        result.charts = charts;
        result.chartBatch = true; // Flag to indicate batch processing needed
        
        // If slides exist, embed charts into appropriate slides
        if (result.slides && Array.isArray(result.slides)) {
          // Collect all chart slides first
          const chartSlideIndices: number[] = [];
          result.slides.forEach((slide: any, index: number) => {
            if (slide.type === 'chart' && !slide.chart) {
              chartSlideIndices.push(index);
            }
          });
          
          // Batch update all chart slides at once
          if (chartSlideIndices.length > 0) {
            const updatedSlides = [...result.slides];
            chartSlideIndices.forEach((slideIndex, chartIndex) => {
              if (charts[chartIndex % charts.length]) {
                updatedSlides[slideIndex] = {
                  ...updatedSlides[slideIndex],
                  chart: charts[chartIndex % charts.length],
                  chartIndex: chartIndex // Track which chart this is
                };
              }
            });
            result.slides = updatedSlides;
          }
        }
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
    const { financialAnalyses, citations, extractedCompanies, charts } = context;
    
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
      
      const parsedResult = JSON.parse(cleanedJson);
      // Create a deep mutable copy of the parsed result to avoid readonly issues
      const result = JSON.parse(JSON.stringify(parsedResult));
      
      // Enhance with additional data
      if (financialAnalyses && financialAnalyses.length > 0) {
        result.financialAnalyses = financialAnalyses;
      }
      
      if (citations && citations.length > 0) {
        result.citations = citations;
      }
      
      // Add charts to slides if available - Process as batch to prevent loops
      if (charts && charts.length > 0) {
        // Store all charts as a batch
        result.charts = charts;
        result.chartBatch = true; // Flag to indicate batch processing needed
        
        // If slides exist, embed charts into appropriate slides
        if (result.slides && Array.isArray(result.slides)) {
          // Collect all chart slides first
          const chartSlideIndices: number[] = [];
          result.slides.forEach((slide: any, index: number) => {
            if (slide.type === 'chart' && !slide.chart) {
              chartSlideIndices.push(index);
            }
          });
          
          // Batch update all chart slides at once
          if (chartSlideIndices.length > 0) {
            const updatedSlides = [...result.slides];
            chartSlideIndices.forEach((slideIndex, chartIndex) => {
              if (charts[chartIndex % charts.length]) {
                updatedSlides[slideIndex] = {
                  ...updatedSlides[slideIndex],
                  chart: charts[chartIndex % charts.length],
                  chartIndex: chartIndex // Track which chart this is
                };
              }
            });
            result.slides = updatedSlides;
          }
        }
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