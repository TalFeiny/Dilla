import { IFormatHandler, UnifiedBrainContext, FormatHandlerResult } from './types';

export class SpreadsheetHandler implements IFormatHandler {
  getFormat(): string {
    return 'spreadsheet';
  }

  async format(context: UnifiedBrainContext): Promise<FormatHandlerResult> {
    const { text, extractedCompanies, citations, financialAnalyses, charts } = context;
    
    // Check if text contains structured spreadsheet data
    let result: any;
    
    try {
      // Try to parse as JSON first (from enhanced backend)
      const jsonMatch = text.match(/\{[\s\S]*"sheets"[\s\S]*\}/);
      if (jsonMatch) {
        result = JSON.parse(jsonMatch[0]);
        
        // Enhance with additional context data
        if (charts && charts.length > 0) {
          result.charts = charts;
        }
        if (financialAnalyses && financialAnalyses.length > 0) {
          result.financialAnalyses = financialAnalyses;
        }
      } else {
        // Fallback to command parsing
        const commands = text.split('\n').filter(cmd => 
          cmd.startsWith('WRITE ') ||
          cmd.startsWith('FORMULA ') ||
          cmd.startsWith('STYLE ') ||
          cmd.startsWith('CHART ')
        );
        
        // Separate commands by type for parallel execution
        const writeCommands = commands.filter(cmd => cmd.startsWith('WRITE '));
        const formulaCommands = commands.filter(cmd => cmd.startsWith('FORMULA '));
        const styleCommands = commands.filter(cmd => cmd.startsWith('STYLE '));
        const chartCommands = commands.filter(cmd => cmd.startsWith('CHART '));
        
        result = {
          grid: {
            commands: {
              writes: writeCommands,
              formulas: formulaCommands,
              styles: styleCommands,
              charts: chartCommands
            },
            executionOrder: ['writes', 'formulas', 'styles', 'charts'],
            metadata: {
              totalCommands: commands.length,
              companies: extractedCompanies,
              timestamp: new Date().toISOString()
            }
          },
          hasFormulas: formulaCommands.length > 0,
          hasCharts: chartCommands.length > 0,
          // Add any charts from context
          charts: charts || []
        };
      }
    } catch (e) {
      // If JSON parsing fails, use command parsing
      return this.parseCommands(text, context);
    }
    
    return {
      success: true,
      result,
      citations,
      metadata: {
        companies: extractedCompanies,
        timestamp: new Date().toISOString(),
        format: 'spreadsheet'
      }
    };
  }
  
  private parseCommands(text: string, context: UnifiedBrainContext): FormatHandlerResult {
    const { extractedCompanies, citations, charts } = context;
    
    const commands = text.split('\n').filter(cmd => 
      cmd.startsWith('WRITE ') ||
      cmd.startsWith('FORMULA ') ||
      cmd.startsWith('STYLE ') ||
      cmd.startsWith('CHART ')
    );
    
    const writeCommands = commands.filter(cmd => cmd.startsWith('WRITE '));
    const formulaCommands = commands.filter(cmd => cmd.startsWith('FORMULA '));
    const styleCommands = commands.filter(cmd => cmd.startsWith('STYLE '));
    const chartCommands = commands.filter(cmd => cmd.startsWith('CHART '));
    
    return {
      success: true,
      result: {
        grid: {
          commands: {
            writes: writeCommands,
            formulas: formulaCommands,
            styles: styleCommands,
            charts: chartCommands
          },
          executionOrder: ['writes', 'formulas', 'styles', 'charts'],
          metadata: {
            totalCommands: commands.length,
            companies: extractedCompanies,
            timestamp: new Date().toISOString()
          }
        },
        hasFormulas: formulaCommands.length > 0,
        hasCharts: chartCommands.length > 0,
        charts: charts || []
      },
      citations,
      metadata: {
        companies: extractedCompanies,
        timestamp: new Date().toISOString(),
        format: 'spreadsheet'
      }
    };
  }
  
  validate(result: any): boolean {
    return result?.grid?.commands !== undefined && 
           result?.grid?.executionOrder !== undefined;
  }
}