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
    
    // Try multiple paths to find docs sections
    const sections = 
      parsedData?.sections ||                    // Direct structure from skill
      parsedData?.memo?.sections ||             // Nested in memo (old format)
      parsedData?.docs?.sections ||             // Nested in docs
      parsedData?.result?.sections ||           // In result
      parsedData?.results?.sections ||          // In results (streaming)
      parsedData?.result?.memo?.sections ||     // Nested in result.memo
      [];
    
    // Check if we found sections
    if (sections && sections.length > 0) {
      console.log('[DocsHandler] Found', sections.length, 'sections');
      
      // Extract exit modeling data if available
      const exitModeling = parsedData.exit_modeling || parsedData.results?.exit_modeling;
      let additionalSections = [];
      const additionalCharts = [];
      
      if (exitModeling) {
        // Add fund-level executive summary section
        if (exitModeling.portfolio_metrics || exitModeling.deployment_discipline) {
          additionalSections.push({
            title: 'Executive Summary - Fund Analysis',
            content: `
## Fund Portfolio Metrics

**Current Performance:**
- Total Expected DPI: ${exitModeling.portfolio_metrics?.total_expected_dpi?.toFixed(2) || 'N/A'}
- Average Expected Multiple: ${exitModeling.portfolio_metrics?.avg_expected_multiple?.toFixed(1) || 'N/A'}x
- Average Expected IRR: ${exitModeling.portfolio_metrics?.avg_expected_irr?.toFixed(1) || 'N/A'}%

**Deployment Status:**
- Remaining Capital: $${(exitModeling.deployment_discipline?.remaining_capital / 1000000)?.toFixed(0) || 'N/A'}M
- Monthly Deployment Target: $${(exitModeling.deployment_discipline?.capital_per_month / 1000000)?.toFixed(1) || 'N/A'}M
- Deployment Pace: ${exitModeling.deployment_discipline?.deployment_pace_rating || 'N/A'}

**Portfolio Construction:**
- Diversification: ${exitModeling.portfolio_construction?.sector_diversity_score?.toFixed(2) || 'N/A'} sector score, ${exitModeling.portfolio_construction?.stage_diversity_score?.toFixed(2) || 'N/A'} stage score
- Concentration Risk: ${exitModeling.portfolio_construction?.concentration_risk || 'N/A'}
- Loss Rate Expectation: ${exitModeling.portfolio_construction?.loss_rate_expectation || 'Standard VC portfolio'}
            `,
            level: 1
          });
          
          // Add portfolio distribution chart
          additionalCharts.push({
            type: 'pie',
            title: 'Expected Portfolio Outcomes',
            data: {
              segments: [
                { name: 'Failures', value: 50, color: '#e15759' },
                { name: 'Return Capital', value: 30, color: '#f28e2c' },
                { name: 'Moderate Winners (3-5x)', value: 15, color: '#76b7b2' },
                { name: 'Home Runs (10x+)', value: 5, color: '#59a14f' }
              ]
            }
          });
        }
        
        // Add individual company analysis sections
        if (exitModeling.scenarios) {
          additionalSections.push({
            title: 'Individual Company Analysis',
            content: `
## Company-by-Company Investment Analysis
            `,
            level: 1
          });
          
          exitModeling.scenarios.forEach((scenario: any) => {
            additionalSections.push({
              title: scenario.company,
              content: `
### ${scenario.company}

**Investment Metrics:**
- Entry Valuation: ${scenario.entry_valuation ? `$${(scenario.entry_valuation / 1000000).toFixed(0)}M` : 'N/A'}
- Initial Check Size: ${scenario.initial_check ? `$${(scenario.initial_check / 1000000).toFixed(0)}M` : 'N/A'}
- Initial Ownership: ${scenario.initial_ownership?.toFixed(1)}%
- Current Diluted Ownership: ${scenario.diluted_ownership?.toFixed(1)}%

**Expected Returns:**
- Expected Multiple: ${scenario.expected_multiple?.toFixed(1)}x
- Expected IRR: ${scenario.expected_irr?.toFixed(1)}%
- DPI Contribution: ${(scenario.expected_dpi_contribution * 100)?.toFixed(1)}%
- Portfolio Fit Score: ${(scenario.portfolio_fit_score * 100)?.toFixed(0)}%

**Recommendation:** ${scenario.investment_recommendation || 'No recommendation available'}
              `,
              level: 2
            });
            
            // Add ownership waterfall data if available
            if (scenario.ownership_evolution?.exit_waterfall) {
              const waterfallTable = scenario.ownership_evolution.exit_waterfall.map((point: any) => 
                `| ${point.exit_value_formatted} | ${point.our_multiple?.toFixed(1)}x | ${point.effective_ownership?.toFixed(1)}% |`
              ).join('\n');
              
              additionalSections.push({
                title: `${scenario.company} - Exit Scenarios`,
                content: `
| Exit Value | Our Multiple | Effective Ownership |
|------------|--------------|-------------------|
${waterfallTable}
                `,
                level: 3
              });
            }
          });
        }
      }
      
      const allCharts = [...(parsedData?.charts || parsedData?.result?.charts || charts || []), ...additionalCharts];
      
      const result = {
        content: parsedData?.content || parsedData?.result?.content || '',
        sections: [...sections, ...additionalSections],
        title: parsedData?.title || parsedData?.result?.title || 'Investment Analysis',
        date: parsedData?.date || parsedData?.result?.date || new Date().toISOString(),
        toc: parsedData?.toc || parsedData?.result?.toc || [],
        charts: allCharts,
        chartBatch: true, // Always batch process charts
        chartPositions: allCharts.map((_: any, index: number) => ({
          afterParagraph: Math.floor((index + 1) * 3),
          inline: true
        })),
        financialAnalyses: parsedData?.financialAnalyses || financialAnalyses || [],
        metadata: parsedData?.metadata || parsedData?.result?.metadata || {},
        exitModeling: exitModeling
      };
      
      return {
        success: true,
        result,
        citations: parsedData?.citations || parsedData?.result?.citations || citations || [],
        metadata: {
          companies: parsedData?.companies || parsedData?.result?.companies || extractedCompanies || [],
          timestamp: result.metadata.timestamp || new Date().toISOString(),
          format: 'docs',
          hasCharts: result.charts.length > 0,
          hasExitModeling: Boolean(exitModeling)
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