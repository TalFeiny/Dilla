import { IFormatHandler, UnifiedBrainContext, FormatHandlerResult } from './types';

export class SpreadsheetHandler implements IFormatHandler {
  getFormat(): string {
    return 'spreadsheet';
  }

  async format(context: UnifiedBrainContext): Promise<FormatHandlerResult> {
    const { text, extractedCompanies, citations, financialAnalyses, charts } = context;
    
    let result: any;
    let parsedData: any = null;
    
    try {
      // Parse the backend response
      parsedData = text;
      if (typeof text === 'string') {
        try {
          parsedData = JSON.parse(text);
        } catch {
          // Not JSON, treat as commands
          parsedData = null;
        }
      }
      
      // Try multiple paths to find spreadsheet commands
      const commands = 
        parsedData?.commands ||                           // Direct structure from skill
        parsedData?.spreadsheet?.commands ||             // Nested in spreadsheet (old format)
        parsedData?.result?.commands ||                  // In result
        parsedData?.results?.commands ||                 // In results (streaming)
        parsedData?.result?.spreadsheet?.commands ||     // Nested in result.spreadsheet
        [];
      
      // Check if we found commands
      if (commands && commands.length > 0) {
        console.log('[SpreadsheetHandler] Found', commands.length, 'commands');
        
        // Extract exit modeling data and add to spreadsheet
        const exitModeling = parsedData.exit_modeling || parsedData.results?.exit_modeling;
        const exitCommands = [];
        
        if (exitModeling) {
          // Add fund-level metrics
          if (exitModeling.portfolio_metrics) {
            exitCommands.push(
              `grid.cell(1, 10).value("FUND METRICS").bold()`,
              `grid.cell(2, 10).value("Total Expected DPI")`,
              `grid.cell(2, 11).value(${exitModeling.portfolio_metrics.total_expected_dpi || 0})`,
              `grid.cell(3, 10).value("Avg Expected Multiple")`,
              `grid.cell(3, 11).value(${exitModeling.portfolio_metrics.avg_expected_multiple || 0})`,
              `grid.cell(4, 10).value("Avg Expected IRR %")`,
              `grid.cell(4, 11).value(${exitModeling.portfolio_metrics.avg_expected_irr || 0})`
            );
          }
          
          // Add company-level exit analysis
          if (exitModeling.scenarios) {
            let row = 7;
            exitCommands.push(`grid.cell(${row}, 10).value("COMPANY EXIT ANALYSIS").bold()`);
            row++;
            
            // Headers
            exitCommands.push(
              `grid.cell(${row}, 10).value("Company")`,
              `grid.cell(${row}, 11).value("Initial %")`,
              `grid.cell(${row}, 12).value("Current %")`,
              `grid.cell(${row}, 13).value("Expected Multiple")`,
              `grid.cell(${row}, 14).value("Expected IRR %")`,
              `grid.cell(${row}, 15).value("DPI Contribution")`
            );
            row++;
            
            // Data rows
            exitModeling.scenarios.forEach((scenario: any) => {
              exitCommands.push(
                `grid.cell(${row}, 10).value("${scenario.company}")`,
                `grid.cell(${row}, 11).value(${scenario.initial_ownership || 0})`,
                `grid.cell(${row}, 12).value(${scenario.diluted_ownership || 0})`,
                `grid.cell(${row}, 13).value(${scenario.expected_multiple || 0})`,
                `grid.cell(${row}, 14).value(${scenario.expected_irr || 0})`,
                `grid.cell(${row}, 15).value(${scenario.expected_dpi_contribution || 0})`
              );
              row++;
            });
          }
        }
        
        result = {
          commands: [...commands, ...exitCommands],
          hasFormulas: parsedData?.hasFormulas || parsedData?.result?.hasFormulas || false,
          hasCharts: parsedData?.hasCharts || parsedData?.result?.hasCharts || exitCommands.some(cmd => cmd.includes('createChart')),
          charts: parsedData?.charts || parsedData?.result?.charts || charts || [],
          metadata: parsedData?.metadata || parsedData?.result?.metadata || {
            companies: parsedData?.companies || parsedData?.result?.companies || extractedCompanies,
            timestamp: new Date().toISOString()
          },
          exitModeling: exitModeling
        };
      }
      // Legacy grid data format (for backward compatibility)
      else if (parsedData && parsedData.grid && parsedData.grid.data) {
        console.log('Converting legacy grid data to commands');
        const commands = this.convertGridDataToCommands(parsedData.grid);
        
        result = {
          commands: commands,
          hasFormulas: (parsedData.grid.formulas && Object.keys(parsedData.grid.formulas).length > 0),
          hasCharts: (parsedData.grid.charts && parsedData.grid.charts.length > 0),
          charts: parsedData.grid.charts || charts || [],
          metadata: parsedData.metadata || {
            companies: extractedCompanies,
            timestamp: new Date().toISOString()
          }
        };
      }
      // Fallback: parse text as commands
      else {
        const commands = this.parseTextCommands(text);
        
        result = {
          commands: commands,
          hasFormulas: commands.some(cmd => cmd.includes('.formula(')),
          hasCharts: commands.some(cmd => cmd.includes('.createChart(')),
          charts: charts || [],
          metadata: {
            companies: extractedCompanies,
            timestamp: new Date().toISOString()
          }
        };
      }
    } catch (e) {
      console.error('Error processing spreadsheet format:', e);
      result = {
        commands: [],
        hasFormulas: false,
        hasCharts: false,
        charts: charts || [],
        metadata: {
          companies: extractedCompanies,
          timestamp: new Date().toISOString()
        }
      };
    }
    
    return {
      success: true,
      result,
      citations: parsedData?.citations || citations || [],
      metadata: result.metadata
    };
  }
  
  private convertGridDataToCommands(grid: any): string[] {
    const commands: string[] = [];
    
    // Convert data array to write commands with citations
    if (grid.data && Array.isArray(grid.data)) {
      grid.data.forEach((row: any[], rowIndex: number) => {
        row.forEach((cell: any, colIndex: number) => {
          const cellAddress = String.fromCharCode(65 + colIndex) + (rowIndex + 1);
          let value = cell;
          let citation = null;
          
          // Check if cell has citation data
          if (typeof cell === 'object' && cell !== null && 'value' in cell) {
            value = cell.value;
            citation = cell.citation;
          }
          
          // Format the value based on type
          if (typeof value === 'string') {
            value = `"${value}"`;
          } else if (typeof value === 'number') {
            // Keep numbers as is
          } else if (value === null || value === undefined) {
            value = '""';
          } else {
            value = `"${String(value)}"`;
          }
          
          // Write command with or without citation
          if (citation) {
            commands.push(`grid.write("${cellAddress}", ${value}, {
              citation: {
                source: "${citation.source || ''}",
                url: "${citation.url || ''}",
                date: "${citation.date || ''}",
                excerpt: "${(citation.excerpt || '').replace(/"/g, '\\"')}"
              }
            })`);
          } else {
            commands.push(`grid.write("${cellAddress}", ${value})`);
          }
        });
      });
    }
    
    // Add style commands for headers (first row)
    if (grid.data && grid.data.length > 0) {
      const headerCount = grid.data[0].length;
      for (let i = 0; i < headerCount; i++) {
        const cellAddress = String.fromCharCode(65 + i) + '1';
        commands.push(`grid.style("${cellAddress}", { fontWeight: "bold", backgroundColor: "#f0f0f0" })`);
      }
    }
    
    // Convert formulas object to formula commands
    if (grid.formulas && typeof grid.formulas === 'object') {
      Object.entries(grid.formulas).forEach(([cell, formula]) => {
        // Handle both string formulas and formula objects
        if (typeof formula === 'string') {
          // If formula starts with = it's already a formula, otherwise it might be a value
          if (formula.startsWith('=')) {
            commands.push(`grid.formula("${cell}", "${formula}")`);
          } else if (formula.startsWith('"')) {
            // It's a label/text value
            commands.push(`grid.write("${cell}", ${formula})`);
          } else {
            // Assume it's a formula without the = prefix
            commands.push(`grid.formula("${cell}", "=${formula}")`);
          }
        } else {
          // Handle formula objects if needed
          commands.push(`grid.formula("${cell}", "${formula}")`);
        }
      });
    }
    
    // Convert charts array to chart commands
    if (grid.charts && Array.isArray(grid.charts)) {
      grid.charts.forEach((chart: any) => {
        // Extract chart type and create proper command
        const chartType = chart.type || 'bar';
        
        // Build chart options object
        const options: any = {
          title: chart.title || 'Chart',
          data: chart.data || {},
          colors: chart.colors || ["#4e79a7", "#f28e2c", "#e15759", "#76b7b2", "#59a14f"]
        };
        
        // Add range if available (for spreadsheet-based charts)
        if (chart.range) {
          options.range = chart.range;
        }
        
        // Create the chart command with proper formatting
        const chartConfig = JSON.stringify(options);
        commands.push(`grid.createChart("${chartType}", ${chartConfig})`);
      });
    }
    
    return commands;
  }
  
  private parseTextCommands(text: string): string[] {
    if (typeof text !== 'string') return [];
    
    // Parse commands from text format
    const lines = text.split('\n');
    const commands: string[] = [];
    
    lines.forEach(line => {
      // Convert WRITE, FORMULA, STYLE, CHART commands to grid.* format
      if (line.startsWith('WRITE ')) {
        const match = line.match(/WRITE\s+([A-Z]+\d+)\s+(.+)/);
        if (match) {
          const [, cell, value] = match;
          commands.push(`grid.write("${cell}", ${value})`);
        }
      } else if (line.startsWith('FORMULA ')) {
        const match = line.match(/FORMULA\s+([A-Z]+\d+)\s+(.+)/);
        if (match) {
          const [, cell, formula] = match;
          commands.push(`grid.formula("${cell}", "${formula}")`);
        }
      } else if (line.startsWith('STYLE ')) {
        const match = line.match(/STYLE\s+([A-Z]+\d+)\s+(.+)/);
        if (match) {
          const [, cell, style] = match;
          commands.push(`grid.style("${cell}", ${style})`);
        }
      } else if (line.startsWith('CHART ')) {
        const match = line.match(/CHART\s+(.+)/);
        if (match) {
          commands.push(`grid.createChart(${match[1]})`);
        }
      } else if (line.includes('grid.')) {
        // Already in grid.* format
        commands.push(line);
      }
    });
    
    return commands;
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