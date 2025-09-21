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
        try {
          parsedData = JSON.parse(text);
        } catch (e) {
          console.error('[DeckHandler] Failed to parse text as JSON:', e);
          return this.parseWithCleaning(text, context);
        }
      }
      
      // Try multiple paths to find deck data
      const slides = 
        parsedData?.slides ||                    // Direct structure from skill
        parsedData?.deck?.slides ||             // Nested in deck (old format)
        parsedData?.result?.slides ||           // In result
        parsedData?.results?.slides ||          // In results (streaming)
        parsedData?.result?.deck?.slides ||     // Nested in result.deck
        [];
      
      // Check if we found slides
      if (slides && slides.length > 0) {
        console.log('[DeckHandler] Found', slides.length, 'slides in deck data');
        
        // Extract exit modeling data if available
        const exitModeling = parsedData?.exit_modeling || 
                           parsedData?.results?.exit_modeling ||
                           parsedData?.result?.exit_modeling;
        const ownershipSlides = [];
        
        // Generate ownership evolution slides if we have exit modeling data
        if (exitModeling?.scenarios) {
          // Add fund-level summary slide first
          if (exitModeling.portfolio_metrics || exitModeling.deployment_discipline) {
            ownershipSlides.push({
              type: 'summary',
              title: 'Fund Portfolio Analysis',
              content: `Portfolio Expected DPI: ${exitModeling.portfolio_metrics?.total_expected_dpi?.toFixed(2) || 'N/A'}`,
              bullets: [
                `Average Expected Multiple: ${exitModeling.portfolio_metrics?.avg_expected_multiple?.toFixed(1)}x`,
                `Average Expected IRR: ${exitModeling.portfolio_metrics?.avg_expected_irr?.toFixed(1)}%`,
                `Deployment Pace: ${exitModeling.deployment_discipline?.deployment_pace_rating || 'N/A'}`,
                `Monthly Capital Deployment: $${(exitModeling.deployment_discipline?.capital_per_month / 1000000)?.toFixed(1)}M`,
                `Portfolio Construction: ${exitModeling.portfolio_construction?.concentration_risk || 'N/A'} concentration risk`
              ],
              chart: {
                type: 'funnel',
                data: {
                  stages: ['Current Portfolio', 'Expected Failures', 'Base Returns', 'Winners'],
                  values: [100, 50, 30, 20],
                  labels: ['100% of companies', '50% expected to fail', '30% return 1-3x', '20% return 5x+']
                }
              }
            });
          }
          
          // Then add individual company slides with ENTRY VALUE analysis
          exitModeling.scenarios.forEach((scenario: any) => {
            if (scenario.ownership_evolution) {
              // Calculate entry value metrics
              const entryMultiple = scenario.valuation / scenario.revenue || 0;
              const maxEntryMultiple = scenario.growth_rate > 2.0 ? 25 : 
                                      scenario.growth_rate > 1.5 ? 20 : 
                                      scenario.growth_rate > 1.0 ? 15 : 10;
              const entryValue = entryMultiple <= maxEntryMultiple ? 'Good Value' :
                                entryMultiple <= maxEntryMultiple * 1.2 ? 'Fair' : 'Expensive';
              
              // Create a slide for each company's ownership evolution
              ownershipSlides.push({
                type: 'chart',
                title: `${scenario.company} - Exit Analysis`,
                content: `Entry: ${entryMultiple.toFixed(1)}x revenue (${entryValue}) | Initial: ${scenario.initial_ownership?.toFixed(1)}% → Current: ${scenario.diluted_ownership?.toFixed(1)}% | Expected ${scenario.expected_multiple?.toFixed(1)}x return`,
                chart: {
                  type: 'waterfall',
                  data: scenario.ownership_evolution,
                  title: 'Ownership Evolution & Exit Scenarios'
                },
                notes: `IRR: ${scenario.expected_irr?.toFixed(1)}% | DPI: ${(scenario.expected_dpi_contribution * 100)?.toFixed(1)}% | TAM Upside: ${scenario.tam_upside || 'N/A'}x`
              });
              
              // Add preference stack slide if available
              if (scenario.ownership_evolution?.preference_stack?.length > 0) {
                ownershipSlides.push({
                  type: 'table',
                  title: `${scenario.company} - Preference Stack`,
                  headers: ['Round', 'Amount', 'Multiple', 'Investors'],
                  rows: scenario.ownership_evolution.preference_stack.map((pref: any) => [
                    pref.round,
                    `$${(pref.amount / 1000000).toFixed(1)}M`,
                    `${pref.multiple}x`,
                    Array.isArray(pref.investors) ? pref.investors.join(', ') : pref.investors
                  ])
                });
              }
            }
          });
        }
        
        const result = {
          slides: [...slides, ...ownershipSlides],
          theme: parsedData.theme || parsedData.result?.theme || 'professional',
          transitions: parsedData.transitions || 'fade',
          charts: parsedData.charts || parsedData.result?.charts || charts || [],
          chartBatch: true, // Always batch process charts
          financialAnalyses: parsedData.financialAnalyses || financialAnalyses || [],
          metadata: parsedData.metadata || parsedData.result?.metadata || {},
          exitModeling: exitModeling
        };
        
        return {
          success: true,
          result,
          citations: parsedData.citations || citations || [],
          metadata: {
            companies: parsedData?.companies || parsedData?.result?.companies || extractedCompanies || [],
            timestamp: result.metadata.timestamp || new Date().toISOString(),
            format: 'deck',
            hasExitModeling: Boolean(exitModeling)
          }
        };
      }
      
      // If no slides found, try legacy format
      console.log('[DeckHandler] No slides found, trying legacy format');
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