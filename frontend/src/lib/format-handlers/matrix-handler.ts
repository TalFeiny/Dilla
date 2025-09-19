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
    
    // Check for enhanced matrix structure from backend
    try {
      const jsonMatch = text.match(/\{[\s\S]*"matrix"[\s\S]*\}/);
      if (jsonMatch) {
        const result = JSON.parse(jsonMatch[0]);
        
        // Enhance with additional context
        if (!result.visualizations && charts && charts.length > 0) {
          result.visualizations = charts.filter((c: any) => 
            c.type === 'heatmap' || c.type === 'spider' || c.type === 'comparison'
          );
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
    
    // Generate dynamic columns based on available data
    const allKeys = new Set<string>();
    companyData.forEach(company => {
      Object.keys(company).forEach(key => {
        if (key !== 'name' && key !== 'companyName') {
          allKeys.add(key);
        }
      });
    });
    
    const headers = ['Company', ...Array.from(allKeys)];
    const rows = companyData.map(company => {
      const name = company.name || company.companyName || 'Unknown';
      return [name, ...Array.from(allKeys).map(key => company[key] || 'N/A')];
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
            source: 'dynamic-skill-results'
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