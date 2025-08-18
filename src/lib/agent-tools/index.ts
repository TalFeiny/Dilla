/**
 * Comprehensive Agent Tools Library
 * Provides all tools needed for financial analysis and spreadsheet manipulation
 */

import { createClient } from '@supabase/supabase-js';
import Anthropic from '@anthropic-ai/sdk';

const supabase = createClient(
  process.env.NEXT_PUBLIC_SUPABASE_URL!,
  process.env.SUPABASE_SERVICE_ROLE_KEY!
);

const anthropic = new Anthropic({
  apiKey: process.env.CLAUDE_API_KEY!,
});

export interface Tool {
  name: string;
  description: string;
  parameters: Record<string, any>;
  execute: (params: any) => Promise<any>;
}

/**
 * Financial Data Tools
 */
export const financialTools: Tool[] = [
  {
    name: 'fetch_stock_price',
    description: 'Get current and historical stock prices',
    parameters: {
      ticker: 'string',
      date: 'string?',
      period: 'string?' // 1d, 1w, 1m, 3m, 1y, 5y
    },
    execute: async ({ ticker, date, period }) => {
      // Use Yahoo Finance or Alpha Vantage API
      const response = await fetch(`/api/tools/stock-price?ticker=${ticker}&period=${period || '1d'}`);
      return response.json();
    }
  },
  
  {
    name: 'fetch_financial_statements',
    description: 'Get income statement, balance sheet, cash flow',
    parameters: {
      ticker: 'string',
      statement: 'income|balance|cashflow',
      period: 'annual|quarterly'
    },
    execute: async ({ ticker, statement, period }) => {
      const response = await fetch(`/api/tools/financials?ticker=${ticker}&statement=${statement}&period=${period}`);
      return response.json();
    }
  },
  
  {
    name: 'calculate_dcf',
    description: 'Run a full DCF valuation model',
    parameters: {
      revenue: 'number',
      growth_rates: 'number[]',
      margins: 'number[]',
      wacc: 'number',
      terminal_growth: 'number'
    },
    execute: async (params) => {
      // Implement DCF calculation
      const { revenue, growth_rates, margins, wacc, terminal_growth } = params;
      const projections = [];
      let currentRevenue = revenue;
      
      for (let i = 0; i < growth_rates.length; i++) {
        currentRevenue *= (1 + growth_rates[i]);
        const fcf = currentRevenue * margins[i];
        const pv = fcf / Math.pow(1 + wacc, i + 1);
        projections.push({ year: i + 1, revenue: currentRevenue, fcf, pv });
      }
      
      const terminalValue = (currentRevenue * margins[margins.length - 1] * (1 + terminal_growth)) / (wacc - terminal_growth);
      const pvTerminal = terminalValue / Math.pow(1 + wacc, growth_rates.length);
      
      return {
        projections,
        terminalValue,
        pvTerminal,
        enterpriseValue: projections.reduce((sum, p) => sum + p.pv, 0) + pvTerminal
      };
    }
  },
  
  {
    name: 'fetch_market_multiples',
    description: 'Get valuation multiples for comparable companies',
    parameters: {
      industry: 'string',
      metrics: 'string[]' // ['EV/Revenue', 'P/E', 'EV/EBITDA']
    },
    execute: async ({ industry, metrics }) => {
      // Query database for comparables
      const { data } = await supabase
        .from('companies')
        .select('*')
        .eq('sector', industry)
        .limit(20);
      
      // Calculate multiples
      return data?.map(company => ({
        name: company.name,
        metrics: {
          'EV/Revenue': company.last_valuation_usd / company.revenue_usd,
          'P/E': company.last_valuation_usd / (company.revenue_usd * 0.15), // Assume 15% margin
          'EV/EBITDA': company.last_valuation_usd / (company.revenue_usd * 0.25)
        }
      }));
    }
  },
  
  {
    name: 'calculate_irr',
    description: 'Calculate IRR for investment cash flows',
    parameters: {
      cashflows: 'number[]',
      dates: 'string[]?'
    },
    execute: async ({ cashflows, dates }) => {
      // Newton's method for IRR
      let rate = 0.1;
      for (let i = 0; i < 100; i++) {
        let npv = 0;
        let dnpv = 0;
        
        cashflows.forEach((cf, t) => {
          const factor = Math.pow(1 + rate, t);
          npv += cf / factor;
          dnpv -= t * cf / (factor * (1 + rate));
        });
        
        const newRate = rate - npv / dnpv;
        if (Math.abs(newRate - rate) < 0.0001) break;
        rate = newRate;
      }
      
      return { irr: rate, annualized: rate * 100 };
    }
  }
];

/**
 * Data Retrieval Tools
 */
export const dataTools: Tool[] = [
  {
    name: 'search_companies',
    description: 'Search for companies in database with filters',
    parameters: {
      query: 'string',
      filters: {
        sector: 'string?',
        min_revenue: 'number?',
        max_revenue: 'number?',
        funding_stage: 'string?',
        geography: 'string?'
      }
    },
    execute: async ({ query, filters }) => {
      let dbQuery = supabase.from('companies').select('*');
      
      if (query) {
        dbQuery = dbQuery.or(`name.ilike.%${query}%,description.ilike.%${query}%`);
      }
      
      if (filters.sector) {
        dbQuery = dbQuery.eq('sector', filters.sector);
      }
      
      if (filters.min_revenue) {
        dbQuery = dbQuery.gte('revenue_usd', filters.min_revenue);
      }
      
      if (filters.max_revenue) {
        dbQuery = dbQuery.lte('revenue_usd', filters.max_revenue);
      }
      
      if (filters.funding_stage) {
        dbQuery = dbQuery.eq('funding_stage', filters.funding_stage);
      }
      
      const { data, error } = await dbQuery.limit(50);
      return { companies: data, error };
    }
  },
  
  {
    name: 'fetch_funding_rounds',
    description: 'Get funding history for a company',
    parameters: {
      company_name: 'string'
    },
    execute: async ({ company_name }) => {
      // Search web for funding rounds
      const response = await fetch('https://api.tavily.com/search', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          api_key: process.env.TAVILY_API_KEY,
          query: `${company_name} funding rounds series seed investment history`,
          max_results: 5
        })
      });
      
      const data = await response.json();
      // Parse and structure the funding data
      return data;
    }
  },
  
  {
    name: 'fetch_competitors',
    description: 'Find and analyze competitor companies',
    parameters: {
      company_name: 'string',
      industry: 'string?'
    },
    execute: async ({ company_name, industry }) => {
      // Use AI to identify competitors
      const response = await anthropic.messages.create({
        model: 'claude-3-haiku-20240307',
        max_tokens: 1000,
        messages: [{
          role: 'user',
          content: `List the top 10 competitors of ${company_name} in the ${industry || 'tech'} industry. For each, provide: name, estimated revenue, key differentiator. Return as JSON array.`
        }]
      });
      
      const text = response.content[0].type === 'text' ? response.content[0].text : '[]';
      return JSON.parse(text);
    }
  },
  
  {
    name: 'fetch_market_data',
    description: 'Get TAM, SAM, SOM for a market',
    parameters: {
      market: 'string',
      geography: 'string?'
    },
    execute: async ({ market, geography }) => {
      const query = `${market} market size TAM SAM SOM ${geography || 'global'} 2024 2025`;
      const response = await fetch('https://api.tavily.com/search', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          api_key: process.env.TAVILY_API_KEY,
          query,
          max_results: 5
        })
      });
      
      return response.json();
    }
  }
];

/**
 * Spreadsheet Manipulation Tools
 */
export const spreadsheetTools: Tool[] = [
  {
    name: 'create_table',
    description: 'Create a formatted table with headers',
    parameters: {
      start_cell: 'string',
      headers: 'string[]',
      data: 'any[][]'
    },
    execute: async ({ start_cell, headers, data }) => {
      const commands = [];
      const [col, row] = parseCell(start_cell);
      
      // Write headers
      headers.forEach((header, i) => {
        const cell = cellAddress(col + i, row);
        commands.push(`grid.write("${cell}", "${header}")`);
        commands.push(`grid.style("${cell}", {bold: true, backgroundColor: "#f3f4f6"})`);
      });
      
      // Write data
      data.forEach((rowData, rowIndex) => {
        rowData.forEach((value, colIndex) => {
          const cell = cellAddress(col + colIndex, row + rowIndex + 1);
          commands.push(`grid.write("${cell}", ${JSON.stringify(value)})`);
        });
      });
      
      return { commands };
    }
  },
  
  {
    name: 'apply_formulas',
    description: 'Apply common financial formulas to a range',
    parameters: {
      formula_type: 'growth|margin|returns|valuation',
      range: 'string',
      params: 'any'
    },
    execute: async ({ formula_type, range, params }) => {
      const commands = [];
      
      switch (formula_type) {
        case 'growth':
          // CAGR formula
          commands.push(`grid.formula("${range}", "=CAGR(${params.start}, ${params.end}, ${params.years})")`);
          break;
        case 'margin':
          // Margin calculations
          commands.push(`grid.formula("${range}", "=(${params.revenue}-${params.costs})/${params.revenue}")`);
          break;
        case 'returns':
          // IRR/NPV
          commands.push(`grid.formula("${range}", "=IRR(${params.cashflow_range})")`);
          break;
        case 'valuation':
          // Multiple-based valuation
          commands.push(`grid.formula("${range}", "=${params.metric}*${params.multiple}")`);
          break;
      }
      
      return { commands };
    }
  },
  
  {
    name: 'create_chart',
    description: 'Generate a chart from spreadsheet data',
    parameters: {
      chart_type: 'line|bar|pie|waterfall|sankey',
      data_range: 'string',
      options: 'any'
    },
    execute: async ({ chart_type, data_range, options }) => {
      // This would integrate with the charting components
      return {
        command: `grid.createChart("${chart_type}", "${data_range}", ${JSON.stringify(options)})`
      };
    }
  },
  
  {
    name: 'format_range',
    description: 'Apply formatting to a range of cells',
    parameters: {
      range: 'string',
      format: 'currency|percentage|number|date',
      decimal_places: 'number?'
    },
    execute: async ({ range, format, decimal_places }) => {
      const [start, end] = range.split(':');
      const commands = [];
      
      // Generate format commands for range
      const [startCol, startRow] = parseCell(start);
      const [endCol, endRow] = parseCell(end);
      
      for (let row = startRow; row <= endRow; row++) {
        for (let col = startCol; col <= endCol; col++) {
          const cell = cellAddress(col, row);
          commands.push(`grid.format("${cell}", "${format}")`);
        }
      }
      
      return { commands };
    }
  }
];

/**
 * AI Analysis Tools
 */
export const aiTools: Tool[] = [
  {
    name: 'analyze_financial_health',
    description: 'AI analysis of company financial health',
    parameters: {
      company_data: 'any',
      focus_areas: 'string[]?'
    },
    execute: async ({ company_data, focus_areas }) => {
      const prompt = `Analyze the financial health of this company. Focus on: ${focus_areas?.join(', ') || 'all aspects'}.
      
Company data: ${JSON.stringify(company_data)}

Provide:
1. Financial health score (0-100)
2. Key strengths
3. Key risks
4. Growth potential
5. Investment recommendation`;

      const response = await anthropic.messages.create({
        model: 'claude-3-5-sonnet-20241022',
        max_tokens: 2000,
        messages: [{ role: 'user', content: prompt }]
      });
      
      return response.content[0];
    }
  },
  
  {
    name: 'generate_investment_memo',
    description: 'Create a detailed investment memo',
    parameters: {
      company: 'string',
      data: 'any',
      thesis: 'string?'
    },
    execute: async ({ company, data, thesis }) => {
      const prompt = `Generate a professional investment memo for ${company}.

Data: ${JSON.stringify(data)}
Investment thesis: ${thesis || 'To be determined'}

Include:
1. Executive Summary
2. Company Overview
3. Market Analysis
4. Financial Analysis
5. Competition
6. Risks & Mitigations
7. Investment Recommendation
8. Exit Scenarios`;

      const response = await anthropic.messages.create({
        model: 'claude-3-5-sonnet-20241022',
        max_tokens: 4000,
        messages: [{ role: 'user', content: prompt }]
      });
      
      return response.content[0];
    }
  },
  
  {
    name: 'predict_metrics',
    description: 'AI prediction of future metrics',
    parameters: {
      historical_data: 'number[]',
      periods_forward: 'number',
      include_confidence: 'boolean?'
    },
    execute: async ({ historical_data, periods_forward, include_confidence }) => {
      // Use simple regression or call to a more sophisticated model
      const trend = calculateTrend(historical_data);
      const predictions = [];
      
      for (let i = 1; i <= periods_forward; i++) {
        const value = historical_data[historical_data.length - 1] * Math.pow(1 + trend, i);
        predictions.push({
          period: i,
          value,
          confidence: include_confidence ? 0.95 - (i * 0.05) : undefined
        });
      }
      
      return { predictions, trend };
    }
  }
];

/**
 * Workflow Tools
 */
export const workflowTools: Tool[] = [
  {
    name: 'run_scenario_analysis',
    description: 'Run multiple scenarios with different assumptions',
    parameters: {
      base_case: 'any',
      scenarios: 'any[]',
      metrics_to_track: 'string[]'
    },
    execute: async ({ base_case, scenarios, metrics_to_track }) => {
      const results = [];
      
      for (const scenario of scenarios) {
        // Apply scenario assumptions to base case
        const scenarioResult = { ...base_case, ...scenario.assumptions };
        
        // Calculate metrics
        const metrics = {};
        for (const metric of metrics_to_track) {
          // Calculate each metric based on scenario
          metrics[metric] = calculateMetric(metric, scenarioResult);
        }
        
        results.push({
          name: scenario.name,
          assumptions: scenario.assumptions,
          metrics
        });
      }
      
      return { scenarios: results };
    }
  },
  
  {
    name: 'build_model_template',
    description: 'Create a complete financial model template',
    parameters: {
      model_type: 'dcf|lbo|startup|real_estate|three_statement',
      company_name: 'string?',
      assumptions: 'any?'
    },
    execute: async ({ model_type, company_name, assumptions }) => {
      const templates = {
        dcf: generateDCFTemplate,
        lbo: generateLBOTemplate,
        startup: generateStartupTemplate,
        real_estate: generateRealEstateTemplate,
        three_statement: generateThreeStatementTemplate
      };
      
      const generator = templates[model_type];
      if (!generator) {
        throw new Error(`Unknown model type: ${model_type}`);
      }
      
      return generator(company_name, assumptions);
    }
  }
];

/**
 * Helper functions
 */
function parseCell(cell: string): [number, number] {
  const match = cell.match(/^([A-Z]+)(\d+)$/);
  if (!match) throw new Error(`Invalid cell: ${cell}`);
  
  const col = match[1].split('').reduce((acc, char) => 
    acc * 26 + (char.charCodeAt(0) - 64), 0) - 1;
  const row = parseInt(match[2]) - 1;
  
  return [col, row];
}

function cellAddress(col: number, row: number): string {
  let colStr = '';
  col += 1;
  while (col > 0) {
    col -= 1;
    colStr = String.fromCharCode(65 + (col % 26)) + colStr;
    col = Math.floor(col / 26);
  }
  return colStr + (row + 1);
}

function calculateTrend(data: number[]): number {
  if (data.length < 2) return 0;
  
  // Simple linear regression
  const n = data.length;
  const sumX = (n * (n + 1)) / 2;
  const sumY = data.reduce((a, b) => a + b, 0);
  const sumXY = data.reduce((sum, y, x) => sum + (x + 1) * y, 0);
  const sumX2 = (n * (n + 1) * (2 * n + 1)) / 6;
  
  const slope = (n * sumXY - sumX * sumY) / (n * sumX2 - sumX * sumX);
  return slope / (sumY / n); // Return as growth rate
}

function calculateMetric(metric: string, data: any): number {
  // Implement metric calculations
  switch (metric) {
    case 'revenue':
      return data.revenue || 0;
    case 'ebitda':
      return data.revenue * (data.ebitda_margin || 0.2);
    case 'fcf':
      return data.ebitda * 0.7; // Simplified
    default:
      return 0;
  }
}

function generateDCFTemplate(company: string, assumptions: any) {
  const commands = [];
  
  // Headers
  commands.push(`grid.write("A1", "DCF Model - ${company || 'Company'}")`);
  commands.push(`grid.style("A1", {bold: true, fontSize: 16})`);
  
  // Revenue projections
  commands.push(`grid.write("A3", "Revenue Projections")`);
  commands.push(`grid.write("A4", "Year")`);
  
  for (let i = 0; i < 5; i++) {
    commands.push(`grid.write("${cellAddress(i + 1, 3)}", ${new Date().getFullYear() + i})`);
  }
  
  // Add formulas
  commands.push(`grid.write("A5", "Revenue")`);
  commands.push(`grid.write("B5", ${assumptions?.revenue || 1000000})`);
  
  for (let i = 1; i < 5; i++) {
    const prevCell = cellAddress(i, 4);
    const currentCell = cellAddress(i + 1, 4);
    commands.push(`grid.formula("${currentCell}", "=${prevCell}*1.2")`); // 20% growth
  }
  
  return { commands };
}

function generateLBOTemplate(company: string, assumptions: any) {
  // LBO model template
  return { commands: [] };
}

function generateStartupTemplate(company: string, assumptions: any) {
  // Startup model template
  return { commands: [] };
}

function generateRealEstateTemplate(company: string, assumptions: any) {
  // Real estate model template
  return { commands: [] };
}

function generateThreeStatementTemplate(company: string, assumptions: any) {
  // Three statement model template
  return { commands: [] };
}

/**
 * Export all tools
 */
export const allTools: Tool[] = [
  ...financialTools,
  ...dataTools,
  ...spreadsheetTools,
  ...aiTools,
  ...workflowTools
];

/**
 * Tool executor for agent
 */
export class ToolExecutor {
  private tools: Map<string, Tool>;
  
  constructor() {
    this.tools = new Map();
    allTools.forEach(tool => {
      this.tools.set(tool.name, tool);
    });
  }
  
  async execute(toolName: string, params: any): Promise<any> {
    const tool = this.tools.get(toolName);
    if (!tool) {
      throw new Error(`Tool not found: ${toolName}`);
    }
    
    try {
      return await tool.execute(params);
    } catch (error) {
      console.error(`Tool execution failed: ${toolName}`, error);
      throw error;
    }
  }
  
  getAvailableTools(): string[] {
    return Array.from(this.tools.keys());
  }
  
  getToolDescription(toolName: string): string {
    const tool = this.tools.get(toolName);
    return tool?.description || '';
  }
}

export const toolExecutor = new ToolExecutor();