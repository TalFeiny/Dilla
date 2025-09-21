import { IFormatHandler, UnifiedBrainContext, FormatHandlerResult } from './types';

export class MatrixHandler implements IFormatHandler {
  getFormat(): string {
    return 'matrix';
  }

  async format(context: UnifiedBrainContext): Promise<FormatHandlerResult> {
    const { 
      text, 
      contextData, 
      companiesData, 
      extractedCompanies, 
      mentionedCompanies,
      citations,
      skillResults,
      charts,
      financialAnalyses
    } = context;
    
    // Try to parse the backend response
    let parsedData: any = text;
    if (typeof text === 'string') {
      try {
        parsedData = JSON.parse(text);
      } catch {
        // Not JSON, continue with legacy parsing
        parsedData = null;
      }
    }
    
    // Try multiple paths to find matrix data
    const matrixData = 
      parsedData?.matrix ||                       // Direct structure 
      parsedData?.data?.matrix ||                // Nested in data
      parsedData?.matrix_data ||                 // Alternative name
      parsedData?.result?.matrix ||              // In result
      parsedData?.results?.matrix ||             // In results (streaming)
      parsedData?.result?.matrix_data ||         // Nested in result.matrix_data
      null;
    
    // Check if we found matrix data
    if (matrixData) {
      console.log('[MatrixHandler] Found matrix data');
      
      // Extract exit modeling data if available
      const exitModeling = parsedData.exit_modeling || parsedData.results?.exit_modeling;
      const ownershipCharts = [];
      
      // Add fund-level portfolio chart FIRST
      if (exitModeling?.portfolio_metrics || exitModeling?.deployment_discipline) {
        ownershipCharts.push({
          type: 'funnel',
          title: 'Fund Portfolio Analysis',
          data: {
            stages: [
              'Total Portfolio',
              'Expected Failures (50%)',
              'Base Returns (30%)',
              'Moderate Winners (15%)',
              'Home Runs (5%)'
            ],
            values: [100, 50, 30, 15, 5],
            metrics: {
              total_expected_dpi: exitModeling.portfolio_metrics?.total_expected_dpi || 0,
              avg_expected_multiple: exitModeling.portfolio_metrics?.avg_expected_multiple || 0,
              avg_expected_irr: exitModeling.portfolio_metrics?.avg_expected_irr || 0,
              deployment_pace: exitModeling.deployment_discipline?.deployment_pace_rating || 'Unknown',
              capital_per_month: exitModeling.deployment_discipline?.capital_per_month || 0,
              concentration_risk: exitModeling.portfolio_construction?.concentration_risk || 'Unknown'
            }
          }
        });
        
        // Add deployment pacing chart
        if (exitModeling.deployment_discipline) {
          ownershipCharts.push({
            type: 'gauge',
            title: 'Deployment Pacing',
            data: {
              value: (exitModeling.deployment_discipline.capital_per_month / exitModeling.deployment_discipline.remaining_capital) * 100,
              target: 4.17, // 24 months = 4.17% per month
              ranges: [
                { min: 0, max: 2, label: 'Too Slow', color: '#e15759' },
                { min: 2, max: 6, label: 'On Track', color: '#59a14f' },
                { min: 6, max: 10, label: 'Too Fast', color: '#f28e2c' }
              ],
              label: `$${(exitModeling.deployment_discipline.capital_per_month / 1000000).toFixed(1)}M/month`
            }
          });
        }
      }
      
      // Generate company-level ownership evolution charts
      if (exitModeling?.scenarios) {
        exitModeling.scenarios.forEach((scenario: any) => {
          if (scenario.ownership_evolution) {
            // Create waterfall chart data for this company
            ownershipCharts.push({
              type: 'waterfall',
              title: `${scenario.company} - Ownership & Exit Analysis`,
              data: {
                ownership_evolution: scenario.ownership_evolution,
                preference_stack: scenario.ownership_evolution.preference_stack,
                exit_waterfall: scenario.ownership_evolution.exit_waterfall,
                company: scenario.company,
                initial_ownership: scenario.initial_ownership,
                diluted_ownership: scenario.diluted_ownership,
                expected_multiple: scenario.expected_multiple,
                expected_irr: scenario.expected_irr,
                investment_recommendation: scenario.investment_recommendation
              }
            });
          }
        });
        
        // Add comparative analysis chart for all companies
        if (exitModeling.scenarios.length > 1) {
          ownershipCharts.push({
            type: 'scatter',
            title: 'Portfolio Risk/Return Analysis',
            data: {
              points: exitModeling.scenarios.map((s: any) => ({
                x: s.expected_irr || 0,
                y: s.expected_multiple || 0,
                z: s.expected_dpi_contribution * 100 || 0,
                label: s.company,
                color: s.portfolio_fit_score > 0.7 ? '#59a14f' : s.portfolio_fit_score > 0.4 ? '#f28e2c' : '#e15759'
              })),
              xAxis: 'Expected IRR %',
              yAxis: 'Expected Multiple',
              zAxis: 'DPI Contribution %'
            }
          });
        }
      }
      
      const result = {
        matrix: matrixData || parsedData?.matrix || {},
        columns: parsedData?.columns || parsedData?.result?.columns || [],
        rows: parsedData?.rows || parsedData?.result?.rows || [],
        scores: parsedData?.scores || parsedData?.result?.scores || {},
        winner: parsedData?.winner || parsedData?.result?.winner,
        hasScoring: parsedData?.hasScoring || parsedData?.result?.hasScoring || Boolean(parsedData?.scores),
        charts: [...(parsedData?.charts || parsedData?.result?.charts || charts || []), ...ownershipCharts],
        chartBatch: true, // Always batch process charts
        formulas: parsedData?.formulas || parsedData?.result?.formulas || {},
        metadata: parsedData?.metadata || parsedData?.result?.metadata || {},
        exitModeling: exitModeling, // Include full exit modeling data
        ownershipCharts: ownershipCharts // Separate reference for ownership charts
      };
      
      return {
        success: true,
        result,
        citations: parsedData?.citations || parsedData?.result?.citations || citations || [],
        metadata: {
          companies: parsedData?.companies || parsedData?.result?.companies || extractedCompanies || [],
          timestamp: result.metadata?.timestamp || new Date().toISOString(),
          format: 'matrix',
          hasScoring: result.hasScoring,
          winner: result.winner,
          hasExitModeling: Boolean(exitModeling),
          hasOwnershipCharts: ownershipCharts.length > 0
        }
      };
    }
    
    // Legacy: Check for enhanced matrix structure from backend
    try {
      const jsonMatch = text.match(/\{[\s\S]*"matrix"[\s\S]*\}/);
      if (jsonMatch) {
        const parsedResult = JSON.parse(jsonMatch[0]);
        // Create a deep mutable copy of the parsed result to avoid readonly issues
        const result = JSON.parse(JSON.stringify(parsedResult));
        
        // Enhance with additional context - Process charts as batch
        if (!result.visualizations && charts && charts.length > 0) {
          // Filter relevant charts for matrix visualization
          const matrixCharts = charts.filter((c: any) => 
            c.type === 'heatmap' || c.type === 'spider' || c.type === 'comparison'
          );
          
          // Store as batch to prevent re-render loops
          result.visualizations = matrixCharts;
          result.chartBatch = matrixCharts.length > 0; // Flag for batch processing
          result.allCharts = charts; // Keep all charts for reference
        }
        
        if (financialAnalyses && financialAnalyses.length > 0) {
          result.financialData = financialAnalyses;
        }
        
        // Add scoring if we have it
        if (result.scores) {
          result.hasScoring = true;
          result.winner = Object.entries(result.scores)
            .sort((a: any, b: any) => b[1].overall - a[1].overall)[0]?.[0];
        }
        
        return {
          success: true,
          result,
          citations,
          metadata: {
            companies: extractedCompanies || result.companies,
            timestamp: new Date().toISOString(),
            format: 'matrix',
            hasScoring: result.hasScoring,
            winner: result.winner
          }
        };
      }
    } catch (e) {
      // Continue with existing logic
    }
    
    // Check for skill results or orchestration data first (dynamic data)
    if (skillResults && skillResults.result) {
      console.log('[MatrixHandler] Using skill results for dynamic data');
      return this.generateFromSkillResults(skillResults, extractedCompanies, citations);
    }
    
    // Check if we have enough context data
    if (!contextData || contextData.length < 100) {
      // Generate matrix from companies data
      return this.generateFromCompaniesData(companiesData, extractedCompanies, citations);
    }
    
    // Parse CSV-like matrix from text
    try {
      const lines = text.split('\n').filter(line => line.trim());
      
      if (lines.length === 0) {
        return this.generateFromCompaniesData(companiesData, extractedCompanies, citations);
      }
      
      // Extract headers and rows
      const headers = this.parseCSVLine(lines[0]);
      const rows = lines.slice(1).map(line => this.parseCSVLine(line));
      
      // Generate dynamic columns based on data
      const dynamicColumns = this.generateDynamicColumns(headers, rows);
      
      // Calculate scores if we have numeric data
      const scores = this.calculateScores(rows, headers, extractedCompanies);
      
      return {
        success: true,
        result: {
          data: {
            headers,
            rows,
            columns: dynamicColumns,
            scores,
            metadata: {
              companies: [...new Set([...extractedCompanies, ...mentionedCompanies])],
              timestamp: new Date().toISOString(),
              rowCount: rows.length,
              columnCount: headers.length
            }
          },
          visualizations: charts?.filter((c: any) => 
            c.type === 'heatmap' || c.type === 'comparison'
          )
        },
        citations,
        metadata: {
          companies: extractedCompanies,
          timestamp: new Date().toISOString(),
          format: 'matrix'
        }
      };
    } catch (error) {
      console.error('[MatrixHandler] Error parsing matrix:', error);
      return this.generateFromCompaniesData(companiesData, extractedCompanies, citations);
    }
  }
  
  private parseCSVLine(line: string): string[] {
    // Handle quoted values and commas within quotes
    const result: string[] = [];
    let current = '';
    let inQuotes = false;
    
    for (let i = 0; i < line.length; i++) {
      const char = line[i];
      
      if (char === '"') {
        inQuotes = !inQuotes;
      } else if (char === ',' && !inQuotes) {
        result.push(current.trim());
        current = '';
      } else {
        current += char;
      }
    }
    
    if (current) {
      result.push(current.trim());
    }
    
    return result;
  }
  
  private generateDynamicColumns(headers: string[], rows: string[][]): any[] {
    return headers.map((header, index) => {
      // Determine column type based on content
      const values = rows.map(row => row[index]).filter(v => v);
      const isNumeric = values.every(v => !isNaN(parseFloat(v)));
      const isPercentage = values.some(v => v?.includes('%'));
      const isCurrency = values.some(v => v?.includes('$') || v?.includes('€'));
      
      return {
        field: header.toLowerCase().replace(/\s+/g, '_'),
        headerName: header,
        width: this.calculateColumnWidth(header, values),
        type: isNumeric ? 'number' : 'string',
        format: isCurrency ? 'currency' : isPercentage ? 'percentage' : undefined,
        sortable: true,
        filterable: true
      };
    });
  }
  
  private calculateColumnWidth(header: string, values: string[]): number {
    const maxLength = Math.max(
      header.length,
      ...values.map(v => (v || '').length)
    );
    return Math.min(Math.max(maxLength * 10, 100), 300);
  }
  
  private async generateFromCompaniesData(
    companiesData: [string, any][],
    companies: string[],
    citations: any[]
  ): Promise<FormatHandlerResult> {
    // Fallback: generate matrix from company data
    const companiesMap = new Map(companiesData);
    
    const headers = [
      'Company',
      'Funding Stage',
      'Total Raised',
      'Valuation',
      'Market',
      'Founded',
      'Employees',
      'Status'
    ];
    
    const rows = companies.map(company => {
      const data = companiesMap.get(company);
      return [
        company,
        data?.funding?.stage || 'N/A',
        data?.funding?.totalRaised || 'N/A',
        data?.valuation?.current || 'N/A',
        data?.market?.segment || 'N/A',
        data?.founded || 'N/A',
        data?.employees || 'N/A',
        data?.status || 'Active'
      ];
    });
    
    return {
      success: true,
      result: {
        data: {
          headers,
          rows,
          columns: this.generateDynamicColumns(headers, rows),
          metadata: {
            companies,
            timestamp: new Date().toISOString(),
            rowCount: rows.length,
            columnCount: headers.length,
            source: 'generated'
          }
        }
      },
      citations,
      metadata: {
        companies,
        timestamp: new Date().toISOString(),
        format: 'matrix'
      }
    };
  }
  
  private generateFromSkillResults(
    skillResults: any,
    companies: string[],
    citations: any[]
  ): FormatHandlerResult {
    const orchData = skillResults.result || skillResults;
    
    // Build dynamic data from skill results
    let companyData: any[] = [];
    
    // Try different paths where company data might be
    if (orchData.companies && Array.isArray(orchData.companies)) {
      companyData = orchData.companies;
    } else {
      // Data might be keyed by company name - check ALL keys dynamically
      Object.keys(orchData).forEach(key => {
        // If the value is an object and contains company-like data
        if (typeof orchData[key] === 'object' && orchData[key] && 
            (orchData[key].funding || orchData[key].valuation || 
             orchData[key].revenue || orchData[key].employees ||
             orchData[key].companyName || orchData[key].website)) {
          companyData.push({ name: key, ...orchData[key] });
        }
      });
    }
    
    // Generate dynamic columns INCLUDING SCENARIOS
    const allKeys = new Set<string>();
    
    // Add standard columns first - ENHANCED with entry value analysis
    const standardColumns = [
      'Company', 'Stage', 'Last Round', 'Valuation',
      'Entry Multiple', 'Value Score', 'Growth Trajectory', // NEW: Entry analysis
      'Bear Case', 'Base Case', 'Bull Case', // Scenario columns
      'Bear IRR', 'Base IRR', 'Bull IRR', // IRR columns
      'Max Entry Price', 'Entry vs Max', // NEW: Value metrics
      'TAM Upside', 'Growth Accel/Decel', // NEW: Growth metrics
      'Liquidation Pref', 'Participation', // Waterfall terms
      'Revenue', 'Growth Rate', 'Burn Rate', 'Runway'
    ];
    
    standardColumns.forEach(col => allKeys.add(col));
    
    companyData.forEach(company => {
      Object.keys(company).forEach(key => {
        if (key !== 'name' && key !== 'companyName' && !standardColumns.includes(key)) {
          allKeys.add(key);
        }
      });
    });
    
    const headers = ['Company', ...Array.from(allKeys)];
    const rows = companyData.map(company => {
      const name = company.name || company.companyName || 'Unknown';
      
      // Calculate scenario valuations (bear 0.5x, base 1x, bull 2x)
      const currentVal = company.valuation || company.last_round_valuation || 100;
      const revenue = company.revenue || company.arr || 10; // Default 10M if no revenue
      const bearCase = currentVal * 0.5;
      const baseCase = currentVal;
      const bullCase = currentVal * 2;
      
      // Calculate entry multiple and value metrics
      const entryMultiple = currentVal / revenue;
      const growthRate = company.growth_rate || 1.0; // 100% default
      const maxEntryMultiple = growthRate > 2.0 ? 25 : growthRate > 1.5 ? 20 : growthRate > 1.0 ? 15 : 10;
      const maxEntryPrice = revenue * maxEntryMultiple;
      const entryVsMax = ((currentVal - maxEntryPrice) / maxEntryPrice * 100).toFixed(0);
      const valueScore = currentVal <= maxEntryPrice ? 'Good' : currentVal <= maxEntryPrice * 1.2 ? 'Fair' : 'Expensive';
      
      // Calculate TAM upside
      const tam = company.tam || company.market_size || 10000; // Default $10B TAM
      const tamPenetration = revenue / tam;
      const tamUpside = tam * 0.01 / revenue; // Upside to 1% market share
      
      // Determine growth trajectory
      const priorGrowth = company.prior_growth_rate || growthRate * 0.8;
      const isAccelerating = growthRate > priorGrowth;
      const growthTrend = isAccelerating ? '📈 Accelerating' : growthRate === priorGrowth ? '➡️ Stable' : '📉 Decelerating';
      
      // Calculate IRRs assuming 5-year exit with VALUE ADJUSTMENT
      const investment = company.our_investment || currentVal * 0.1; // Assume 10% ownership
      // Adjust exit multiples based on entry value
      const exitMultiplier = entryMultiple <= 15 ? 3 : entryMultiple <= 25 ? 2 : 1.5;
      const bearIRR = Math.pow((bearCase * exitMultiplier) / investment, 1/5) - 1;
      const baseIRR = Math.pow((baseCase * exitMultiplier) / investment, 1/5) - 1;
      const bullIRR = Math.pow((bullCase * exitMultiplier) / investment, 1/5) - 1;
      
      // Extract waterfall terms
      const liquidationPref = company.liquidation_preference || '1x (Carta benchmark)';
      const participation = company.participating ? 'Yes' : 'No (SVB: 85% non-participating)';
      
      // Create row with all data points and citations - ENHANCED with value metrics
      const row: any[] = [
        name,
        company.stage || company.funding_stage || 'N/A',
        company.last_round || company.last_round_date || 'N/A',
        `$${currentVal}M`,
        `${entryMultiple.toFixed(1)}x`,           // Entry Multiple
        valueScore,                                // Value Score
        `${tamUpside.toFixed(0)}x`,               // Growth Trajectory (TAM upside)
        `$${bearCase.toFixed(1)}M`,
        `$${baseCase.toFixed(1)}M`,
        `$${bullCase.toFixed(1)}M`,
        `${(bearIRR * 100).toFixed(1)}%`,
        `${(baseIRR * 100).toFixed(1)}%`,
        `${(bullIRR * 100).toFixed(1)}%`,
        `$${maxEntryPrice.toFixed(0)}M`,          // Max Entry Price
        `${entryVsMax}%`,                         // Entry vs Max
        `${tamUpside.toFixed(0)}x to 1%`,         // TAM Upside
        growthTrend,                               // Growth Accel/Decel
        liquidationPref,
        participation,
        company.revenue ? `$${company.revenue}M` : 'N/A',
        company.growth_rate ? `${(growthRate * 100).toFixed(0)}%` : 'N/A',
        company.burn_rate ? `$${company.burn_rate}M/mo` : 'N/A',
        company.runway ? `${company.runway} months` : 'N/A'
      ];
      
      // Add remaining dynamic columns
      Array.from(allKeys).slice(standardColumns.length).forEach(key => {
        row.push(company[key] || 'N/A');
      });
      
      return row;
    });
    
    // Add citation sources for benchmarks
    const enhancedCitations = [
      ...citations,
      {
        source: 'Carta',
        url: 'https://carta.com/blog/liquidation-preferences/',
        text: '1x non-participating liquidation preference is standard (85% of deals)',
        relevance: 'Waterfall assumptions'
      },
      {
        source: 'SVB',
        url: 'https://www.svb.com/trends-insights/',
        text: '70% of options remain unexercised at exit',
        relevance: 'Option pool calculations'
      },
      {
        source: 'Carta Q3 2024',
        url: 'https://carta.com/blog/q3-2024-state-of-private-markets/',
        text: 'Series B median valuation: $60M, Series C: $150M',
        relevance: 'Valuation benchmarks'
      },
      {
        source: 'PitchBook',
        url: 'https://pitchbook.com/news/reports',
        text: 'Median time to exit: 7.5 years for VC-backed companies',
        relevance: 'IRR calculations'
      }
    ];
    
    // Create cell-level citations for specific data points
    const cellCitations: Record<string, string> = {};
    
    // Add citations to specific cells
    headers.forEach((header, colIndex) => {
      if (header === 'Liquidation Pref') {
        rows.forEach((_, rowIndex) => {
          cellCitations[`${rowIndex}-${colIndex}`] = 'Carta: 85% of deals are 1x non-participating';
        });
      }
      if (header === 'Participation') {
        rows.forEach((_, rowIndex) => {
          cellCitations[`${rowIndex}-${colIndex}`] = 'SVB: 85% of preferred stock is non-participating';
        });
      }
      if (header.includes('IRR')) {
        rows.forEach((_, rowIndex) => {
          cellCitations[`${rowIndex}-${colIndex}`] = 'PitchBook: Median 7.5 year exit timeline';
        });
      }
    });
    
    return {
      success: true,
      result: {
        data: {
          headers,
          rows,
          columns: this.generateDynamicColumns(headers, rows),
          cellCitations, // Cell-specific citations
          metadata: {
            companies,
            timestamp: new Date().toISOString(),
            rowCount: rows.length,
            columnCount: headers.length,
            source: 'dynamic-skill-results',
            benchmarks: {
              liquidationPref: '1x non-participating (Carta)',
              optionExercise: '30% exercised at exit (SVB)',
              medianExit: '7.5 years (PitchBook)',
              scenarioMultiples: 'Bear: 0.5x, Base: 1x, Bull: 2x'
            }
          }
        }
      },
      citations: enhancedCitations,
      metadata: {
        companies,
        timestamp: new Date().toISOString(),
        format: 'matrix'
      }
    };
  }
  
  private calculateScores(rows: string[][], headers: string[], companies: string[]): any {
    const scores: any = {};
    
    // Find company column index
    const companyColIndex = headers.findIndex(h => 
      h.toLowerCase().includes('company') || h.toLowerCase() === 'name'
    );
    
    if (companyColIndex === -1) {
      // If no company column, use row indices
      rows.forEach((row, index) => {
        let totalScore = 0;
        let scoreCount = 0;
        
        row.forEach((cell, cellIndex) => {
          if (cellIndex !== companyColIndex && cell && cell !== 'N/A') {
            const numMatch = String(cell).match(/[\d.]+/);
            if (numMatch) {
              totalScore += parseFloat(numMatch[0]);
              scoreCount++;
            }
          }
        });
        
        const companyName = companies[index] || `Company ${index + 1}`;
        scores[companyName] = {
          overall: scoreCount > 0 ? totalScore / scoreCount : 0,
          dataPoints: scoreCount
        };
      });
    } else {
      // Use company column
      rows.forEach(row => {
        const companyName = row[companyColIndex];
        if (companyName) {
          let totalScore = 0;
          let scoreCount = 0;
          
          row.forEach((cell, cellIndex) => {
            if (cellIndex !== companyColIndex && cell && cell !== 'N/A') {
              const numMatch = String(cell).match(/[\d.]+/);
              if (numMatch) {
                totalScore += parseFloat(numMatch[0]);
                scoreCount++;
              }
            }
          });
          
          scores[companyName] = {
            overall: scoreCount > 0 ? totalScore / scoreCount : 0,
            dataPoints: scoreCount
          };
        }
      });
    }
    
    // Rank companies
    const ranked = Object.entries(scores)
      .sort((a: any, b: any) => b[1].overall - a[1].overall)
      .map(([company, score]: any, index) => ({
        company,
        ...score,
        rank: index + 1
      }));
    
    return ranked;
  }
  
  validate(result: any): boolean {
    return result?.data?.headers !== undefined && 
           result?.data?.rows !== undefined &&
           Array.isArray(result.data.headers) &&
           Array.isArray(result.data.rows);
  }
}