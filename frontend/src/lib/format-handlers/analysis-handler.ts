import { IFormatHandler, UnifiedBrainContext, FormatHandlerResult } from './types';
import { parseMarkdownToSections } from './docs-handler';

/**
 * Handler for analysis format - used by skill-orchestrator for insights
 * Optimized for skill-to-skill context preservation and data transfer
 */
export class AnalysisHandler implements IFormatHandler {
  getFormat(): string {
    return 'analysis';
  }

  async format(context: UnifiedBrainContext): Promise<FormatHandlerResult> {
    const { 
      text, 
      contextData, 
      companiesData, 
      financialAnalyses, 
      charts, 
      citations, 
      extractedCompanies,
      skillResults 
    } = context;
    
    // Extract and preserve skill context for chaining
    const skillContext = this.extractSkillContext(skillResults);
    const sharedData = this.extractSharedData(skillResults);
    
    // Structure the analysis output for optimal skill-to-skill transfer
    const structuredAnalysis = {
      // Core analysis
      summary: this.extractSummary(text),
      insights: this.extractInsights(text, skillResults),
      findings: this.extractFindings(text, companiesData),
      dataPoints: this.extractDataPoints(financialAnalyses, companiesData),
      recommendations: this.extractRecommendations(text, skillResults),
      metrics: this.extractMetrics(financialAnalyses),
      
      // Context preservation for skill chaining
      skillContext: skillContext,
      sharedData: sharedData,
      
      // Company-specific data indexed for quick access
      companiesIndex: this.buildCompanyIndex(companiesData, financialAnalyses),
      
      // Supporting data
      sources: citations || [],
      charts: charts || [],
      companies: extractedCompanies || []
    };
    
    // Format the content for display with proper sections
    const formattedContent = this.formatAnalysisContent(structuredAnalysis);

    // Parse formatted markdown into structured sections for memo rendering
    const sections = parseMarkdownToSections(formattedContent);

    // Also try to extract sections from the raw backend result
    let parsedRaw: any = null;
    try { parsedRaw = typeof text === 'string' ? JSON.parse(text) : text; } catch {}
    const backendSections = parsedRaw?.sections ?? parsedRaw?.memo?.sections ?? parsedRaw?.result?.sections ?? [];
    // Prefer backend-provided sections if they're richer
    const finalSections = Array.isArray(backendSections) && backendSections.length > sections.length
      ? backendSections : sections;

    return {
      success: true,
      result: {
        content: formattedContent,
        sections: finalSections,
        structured: structuredAnalysis,
        raw: text,

        // Preserve all context for next skill
        context: {
          companies: companiesData,
          financial: financialAnalyses,
          charts: charts || [],
          skills: skillContext,
          shared: sharedData
        },

        // Quick access data
        quickAccess: {
          latestFunding: this.extractLatestFunding(companiesData),
          keyMetrics: this.extractKeyMetrics(financialAnalyses),
          topInsights: structuredAnalysis.insights.slice(0, 3)
        }
      },
      citations,
      metadata: {
        companies: extractedCompanies,
        timestamp: new Date().toISOString(),
        format: 'analysis',
        skillsUsed: skillResults ? Object.keys(skillResults) : [],
        skillChain: this.extractSkillChain(skillResults)
      }
    };
  }
  
  validate(result: any): boolean {
    return result?.content !== undefined || result?.structured !== undefined;
  }
  
  private extractSummary(text: string): string {
    // Extract first paragraph or executive summary
    const lines = text.split('\n').filter(l => l.trim());
    const summaryIndex = lines.findIndex(l => 
      l.toLowerCase().includes('summary') || 
      l.toLowerCase().includes('overview')
    );
    
    if (summaryIndex >= 0 && summaryIndex < lines.length - 1) {
      return lines[summaryIndex + 1] || lines[0];
    }
    
    return lines[0] || 'Analysis completed.';
  }
  
  private extractInsights(text: string, skillResults: any): string[] {
    const insights: string[] = [];
    
    // Extract insights from text
    const insightPatterns = [
      /(?:key insight|insight|finding|observation):\s*(.+)/gi,
      /(?:•|▪|→)\s*(.+)/g,
      /(?:\d+\.)\s*(.+)/g
    ];
    
    for (const pattern of insightPatterns) {
      const matches = text.matchAll(pattern);
      for (const match of matches) {
        const insight = match[1].trim();
        if (insight.length > 20 && insight.length < 500) {
          insights.push(insight);
        }
      }
    }
    
    // Add insights from skill results
    if (skillResults?.insights) {
      insights.push(...(Array.isArray(skillResults.insights) ? skillResults.insights : [skillResults.insights]));
    }
    
    // Deduplicate and limit
    return [...new Set(insights)].slice(0, 10);
  }
  
  private extractFindings(text: string, companiesData: any[]): any[] {
    const findings = [];
    
    // Extract company-specific findings
    if (companiesData && companiesData.length > 0) {
      for (const [company, data] of companiesData) {
        if (data?.analysis || data?.metrics) {
          findings.push({
            company,
            type: 'company_analysis',
            data: data.analysis || data.metrics
          });
        }
      }
    }
    
    // Extract pattern findings from text
    const patternMatches = text.match(/pattern[s]?:?\s*(.+?)(?:\n|$)/gi);
    if (patternMatches) {
      patternMatches.forEach(match => {
        findings.push({
          type: 'pattern',
          description: match.replace(/pattern[s]?:?\s*/i, '').trim()
        });
      });
    }
    
    return findings.slice(0, 15);
  }
  
  private extractDataPoints(financialAnalyses: any[], companiesData: any[]): any {
    const dataPoints: any = {};
    
    // Aggregate financial metrics
    if (financialAnalyses && financialAnalyses.length > 0) {
      const metrics = financialAnalyses[0];
      dataPoints.valuation = metrics.valuation;
      dataPoints.revenue = metrics.revenue;
      dataPoints.growth = metrics.growthRate;
      dataPoints.margins = metrics.margins;
    }
    
    // Add market data
    if (companiesData && companiesData.length > 0) {
      dataPoints.companiesAnalyzed = companiesData.length;
      dataPoints.marketSize = this.calculateMarketSize(companiesData);
      dataPoints.averageValuation = this.calculateAverageValuation(companiesData);
    }
    
    return dataPoints;
  }
  
  private extractRecommendations(text: string, skillResults: any): string[] {
    const recommendations: string[] = [];
    
    // Extract recommendations from text
    const recPatterns = [
      /recommend(?:ation)?[s]?:\s*(.+?)(?:\n|$)/gi,
      /suggest(?:ion)?[s]?:\s*(.+?)(?:\n|$)/gi,
      /should\s+(.+?)(?:\n|$)/gi
    ];
    
    for (const pattern of recPatterns) {
      const matches = text.matchAll(pattern);
      for (const match of matches) {
        recommendations.push(match[1].trim());
      }
    }
    
    // Add from skill results
    if (skillResults?.recommendations) {
      recommendations.push(...(Array.isArray(skillResults.recommendations) ? 
        skillResults.recommendations : [skillResults.recommendations]));
    }
    
    return [...new Set(recommendations)].slice(0, 8);
  }
  
  private extractMetrics(financialAnalyses: any[]): any {
    if (!financialAnalyses || financialAnalyses.length === 0) {
      return {};
    }
    
    const analysis = financialAnalyses[0];
    return {
      revenue: analysis.revenue,
      growth: analysis.growthRate,
      valuation: analysis.valuation,
      efficiency: analysis.efficiency,
      burnRate: analysis.burnRate,
      runway: analysis.runway
    };
  }
  
  private calculateMarketSize(companiesData: any[]): string {
    // Aggregate market size from company data
    const sizes = companiesData
      .map(([_, data]) => data?.marketSize)
      .filter(Boolean)
      .map(s => parseFloat(s));
    
    if (sizes.length === 0) return 'N/A';
    
    const total = sizes.reduce((a, b) => a + b, 0);
    return `$${(total / 1000000000).toFixed(1)}B`;
  }
  
  private calculateAverageValuation(companiesData: any[]): string {
    const valuations = companiesData
      .map(([_, data]) => data?.valuation)
      .filter(Boolean)
      .map(v => parseFloat(v));
    
    if (valuations.length === 0) return 'N/A';
    
    const avg = valuations.reduce((a, b) => a + b, 0) / valuations.length;
    return `$${(avg / 1000000).toFixed(1)}M`;
  }
  
  private formatAnalysisContent(analysis: any): string {
    let content = '';
    
    // Executive Summary
    content += `## Executive Summary\n${analysis.summary}\n\n`;
    
    // Key Insights
    if (analysis.insights.length > 0) {
      content += `## Key Insights\n`;
      analysis.insights.forEach((insight, i) => {
        content += `${i + 1}. ${insight}\n`;
      });
      content += '\n';
    }
    
    // Data Points
    if (Object.keys(analysis.dataPoints).length > 0) {
      content += `## Key Metrics\n`;
      for (const [key, value] of Object.entries(analysis.dataPoints)) {
        if (value) {
          content += `• **${this.formatKey(key)}**: ${value}\n`;
        }
      }
      content += '\n';
    }
    
    // Findings
    if (analysis.findings.length > 0) {
      content += `## Detailed Findings\n`;
      analysis.findings.forEach((finding: any) => {
        if (finding.company) {
          content += `### ${finding.company}\n`;
          content += `${JSON.stringify(finding.data, null, 2)}\n\n`;
        } else {
          content += `• ${finding.description || JSON.stringify(finding)}\n`;
        }
      });
      content += '\n';
    }
    
    // Recommendations
    if (analysis.recommendations.length > 0) {
      content += `## Recommendations\n`;
      analysis.recommendations.forEach((rec, i) => {
        content += `${i + 1}. ${rec}\n`;
      });
      content += '\n';
    }
    
    // Sources
    if (analysis.sources.length > 0) {
      content += `## Sources\n`;
      analysis.sources.forEach((source: any) => {
        content += `• [${source.title || source.url}](${source.url})\n`;
      });
    }
    
    return content;
  }
  
  private formatKey(key: string): string {
    return key
      .replace(/([A-Z])/g, ' $1')
      .replace(/_/g, ' ')
      .trim()
      .split(' ')
      .map(word => word.charAt(0).toUpperCase() + word.slice(1).toLowerCase())
      .join(' ');
  }
  
  // New methods for skill context preservation
  
  private extractSkillContext(skillResults: any): any {
    if (!skillResults) return {};
    
    const context: any = {};
    
    // Extract results from each skill
    if (skillResults.results && skillResults.results instanceof Map) {
      skillResults.results.forEach((value: any, key: string) => {
        context[key] = {
          data: value.data,
          success: value.success,
          timing: value.timing
        };
      });
    } else if (typeof skillResults === 'object') {
      // Handle object format
      Object.entries(skillResults).forEach(([key, value]) => {
        context[key] = value;
      });
    }
    
    return context;
  }
  
  private extractSharedData(skillResults: any): any {
    if (!skillResults) return {};
    
    // Extract shared data from orchestration results
    if (skillResults.sharedData) {
      return skillResults.sharedData;
    }
    
    // Extract from raw results if available
    if (skillResults.rawResults?.sharedData) {
      return skillResults.rawResults.sharedData;
    }
    
    return {};
  }
  
  private buildCompanyIndex(companiesData: any[], financialAnalyses: any[]): any {
    const index: any = {};
    
    // Index company data by name
    if (companiesData && Array.isArray(companiesData)) {
      companiesData.forEach(([name, data]) => {
        index[name] = {
          ...data,
          financial: financialAnalyses?.find(f => f.company === name)
        };
      });
    }
    
    return index;
  }
  
  private extractLatestFunding(companiesData: any[]): any[] {
    if (!companiesData || !Array.isArray(companiesData)) return [];
    
    return companiesData
      .map(([name, data]) => ({
        company: name,
        lastRound: data?.funding?.lastRound,
        amount: data?.funding?.lastAmount,
        date: data?.funding?.lastDate,
        valuation: data?.valuation
      }))
      .filter(f => f.lastRound)
      .sort((a, b) => {
        if (!a.date || !b.date) return 0;
        return new Date(b.date).getTime() - new Date(a.date).getTime();
      })
      .slice(0, 5);
  }
  
  private extractKeyMetrics(financialAnalyses: any[]): any {
    if (!financialAnalyses || financialAnalyses.length === 0) return {};
    
    // Aggregate key metrics across all analyses
    const metrics: any = {
      avgRevenue: 0,
      avgGrowth: 0,
      avgValuation: 0,
      count: 0
    };
    
    financialAnalyses.forEach(analysis => {
      if (analysis.revenue) {
        metrics.avgRevenue += parseFloat(analysis.revenue) || 0;
        metrics.count++;
      }
      if (analysis.growthRate) {
        metrics.avgGrowth += parseFloat(analysis.growthRate) || 0;
      }
      if (analysis.valuation) {
        metrics.avgValuation += parseFloat(analysis.valuation) || 0;
      }
    });
    
    if (metrics.count > 0) {
      metrics.avgRevenue = (metrics.avgRevenue / metrics.count).toFixed(2);
      metrics.avgGrowth = (metrics.avgGrowth / metrics.count).toFixed(2);
      metrics.avgValuation = (metrics.avgValuation / metrics.count).toFixed(2);
    }
    
    return metrics;
  }
  
  private extractSkillChain(skillResults: any): string[] {
    if (!skillResults) return [];
    
    // Extract the sequence of skills executed
    if (skillResults.skillChain) {
      return skillResults.skillChain;
    }
    
    if (skillResults.results && skillResults.results instanceof Map) {
      return Array.from(skillResults.results.keys());
    }
    
    if (typeof skillResults === 'object') {
      return Object.keys(skillResults);
    }
    
    return [];
  }
}