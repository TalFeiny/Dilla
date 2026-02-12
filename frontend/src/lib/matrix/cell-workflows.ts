/**
 * Cell Workflows
 * 
 * Prepackaged workflows accessible from cells (IRR, NPV, MOIC, charts, valuations, etc.)
 * Each workflow can operate on single cells, cell ranges, rows, or columns.
 */

import { MatrixRow, MatrixCell, MatrixColumn, MatrixData } from '@/components/matrix/UnifiedMatrix';
import { transformServiceOutput, ServiceOutput } from './service-transformer';

export type WorkflowScope = 'cell' | 'range' | 'row' | 'column' | 'matrix';

export interface WorkflowDefinition {
  id: string;
  name: string;
  description: string;
  scope: WorkflowScope[];
  icon?: string;
  category: 'financial' | 'valuation' | 'portfolio' | 'chart' | 'analysis' | 'cap_table' | 'market';
  execute: (params: WorkflowParams) => Promise<WorkflowResult>;
}

export interface WorkflowParams {
  matrixData: MatrixData;
  rowId?: string;
  columnId?: string;
  cellRange?: { startRow: string; endRow: string; startCol: string; endCol: string };
  additionalParams?: Record<string, any>;
}

export interface WorkflowResult {
  success: boolean;
  data?: any;
  rows?: MatrixRow[];
  error?: string;
  metadata?: {
    executionTime?: number;
    service?: string;
    confidence?: number;
  };
}

/**
 * Workflow Registry
 */
export const WORKFLOWS: Record<string, WorkflowDefinition> = {
  calculateIRR: {
    id: 'calculateIRR',
    name: 'Calculate IRR',
    description: 'Calculate Internal Rate of Return from cash flow array',
    scope: ['range', 'column'],
    category: 'financial',
    async execute(params) {
      const startTime = Date.now();
      try {
        const cashFlows = extractCashFlows(params);
        if (!cashFlows || cashFlows.length < 2) {
          throw new Error('Need at least 2 cash flows for IRR calculation');
        }

        const response = await fetch('/api/financial/irr', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ cash_flows: cashFlows }),
        });

        if (!response.ok) {
          const error = await response.json();
          throw new Error(error.error || 'Failed to calculate IRR');
        }

        const result = await response.json();
        const irr = result.irr || result.value || 0;

        return {
          success: true,
          data: { irr, cashFlows },
          metadata: {
            executionTime: Date.now() - startTime,
            service: 'financial_calculator',
          },
        };
      } catch (error) {
        return {
          success: false,
          error: error instanceof Error ? error.message : 'Unknown error',
          metadata: { executionTime: Date.now() - startTime },
        };
      }
    },
  },

  calculateNPV: {
    id: 'calculateNPV',
    name: 'Calculate NPV',
    description: 'Calculate Net Present Value with discount rate',
    scope: ['range', 'column'],
    category: 'financial',
    async execute(params) {
      const startTime = Date.now();
      try {
        const cashFlows = extractCashFlows(params);
        const discountRate = params.additionalParams?.discountRate || 0.1;

        if (!cashFlows || cashFlows.length < 1) {
          throw new Error('Need at least 1 cash flow for NPV calculation');
        }

        const response = await fetch('/api/financial/npv', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            cash_flows: cashFlows,
            discount_rate: discountRate,
          }),
        });

        if (!response.ok) {
          const errBody = await response.json().catch(() => ({}));
          throw new Error(errBody.error || 'Failed to calculate NPV');
        }

        const result = await response.json();
        const npv = result.npv || result.value || 0;

        return {
          success: true,
          data: { npv, discountRate, cashFlows },
          metadata: {
            executionTime: Date.now() - startTime,
            service: 'financial_calculator',
          },
        };
      } catch (error) {
        return {
          success: false,
          error: error instanceof Error ? error.message : 'Unknown error',
          metadata: { executionTime: Date.now() - startTime },
        };
      }
    },
  },

  calculateMOIC: {
    id: 'calculateMOIC',
    name: 'Calculate MOIC',
    description: 'Multiple on Invested Capital',
    scope: ['row', 'range'],
    category: 'financial',
    async execute(params) {
      const startTime = Date.now();
      try {
        const { exitValue, invested } = extractMOICParams(params);
        
        if (!invested || invested <= 0) {
          throw new Error('Invested amount must be greater than 0');
        }

        const moic = exitValue / invested;

        return {
          success: true,
          data: { moic, exitValue, invested },
          metadata: {
            executionTime: Date.now() - startTime,
            service: 'financial_calculator',
          },
        };
      } catch (error) {
        return {
          success: false,
          error: error instanceof Error ? error.message : 'Unknown error',
          metadata: { executionTime: Date.now() - startTime },
        };
      }
    },
  },

  calculateCAGR: {
    id: 'calculateCAGR',
    name: 'Calculate CAGR',
    description: 'Compound Annual Growth Rate',
    scope: ['range', 'column'],
    category: 'financial',
    async execute(params) {
      const startTime = Date.now();
      try {
        const values = extractNumericValues(params);
        if (values.length < 2) {
          throw new Error('Need at least 2 values for CAGR calculation');
        }

        const startValue = values[0];
        const endValue = values[values.length - 1];
        const periods = values.length - 1;

        if (startValue <= 0) {
          throw new Error('Start value must be greater than 0');
        }

        const cagr = Math.pow(endValue / startValue, 1 / periods) - 1;

        return {
          success: true,
          data: { cagr, startValue, endValue, periods },
          metadata: {
            executionTime: Date.now() - startTime,
            service: 'financial_calculator',
          },
        };
      } catch (error) {
        return {
          success: false,
          error: error instanceof Error ? error.message : 'Unknown error',
          metadata: { executionTime: Date.now() - startTime },
        };
      }
    },
  },

  runValuation: {
    id: 'runValuation',
    name: 'Run Valuation',
    description: 'Run valuation analysis for company',
    scope: ['row'],
    category: 'valuation',
    async execute(params) {
      const startTime = Date.now();
      try {
        if (!params.rowId) {
          throw new Error('Row ID required for valuation');
        }

        const row = params.matrixData.rows.find(r => r.id === params.rowId);
        if (!row) {
          throw new Error('Row not found');
        }

        const companyId = row.companyId;
        const method = params.additionalParams?.method || 'dcf';

        if (!companyId) {
          throw new Error('Company ID required for valuation');
        }

        const response = await fetch('/api/valuation/calculate', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            companyId,
            method,
            context: { fundId: params.matrixData.metadata?.fundId },
          }),
        });

        if (!response.ok) {
          const errBody = await response.json().catch(() => ({}));
          const msg =
            response.status === 502 || response.status === 503
              ? 'Backend unavailable. Start the backend to use valuation.'
              : errBody.error || 'Failed to run valuation';
          throw new Error(msg);
        }

        const result = await response.json();
        const valuation = result.valuation ?? result.data?.valuation ?? 0;
        const confidence = result.confidence ?? result.metadata?.confidence ?? 0.5;

        return {
          success: true,
          data: {
            valuation,
            method: result.method ?? method,
            confidence,
            explanation: result.explanation,
            details: result.details ?? result,
          },
          metadata: {
            executionTime: Date.now() - startTime,
            service: 'valuation_engine',
            confidence,
          },
        };
      } catch (error) {
        return {
          success: false,
          error: error instanceof Error ? error.message : 'Unknown error',
          metadata: { executionTime: Date.now() - startTime },
        };
      }
    },
  },

  runPWERM: {
    id: 'runPWERM',
    name: 'Run PWERM Analysis',
    description: 'Probability-Weighted Expected Return Method',
    scope: ['row'],
    category: 'valuation',
    async execute(params) {
      const startTime = Date.now();
      try {
        if (!params.rowId) {
          throw new Error('Row ID required for PWERM');
        }

        const row = params.matrixData.rows.find(r => r.id === params.rowId);
        if (!row) {
          throw new Error('Row not found');
        }

        const companyId = row.companyId;
        if (!companyId) {
          throw new Error('Company ID required for PWERM');
        }

        const response = await fetch(`/api/portfolio/${params.matrixData.metadata?.fundId}/companies/${companyId}/pwerm`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
        });

        if (!response.ok) {
          const error = await response.json();
          throw new Error(error.error || 'Failed to run PWERM');
        }

        const result = await response.json();

        return {
          success: true,
          data: result,
          metadata: {
            executionTime: Date.now() - startTime,
            service: 'pwerm_calculator',
          },
        };
      } catch (error) {
        return {
          success: false,
          error: error instanceof Error ? error.message : 'Unknown error',
          metadata: { executionTime: Date.now() - startTime },
        };
      }
    },
  },

  valuePortfolio: {
    id: 'valuePortfolio',
    name: 'Value Portfolio',
    description: 'Run valuation for all companies in portfolio',
    scope: ['matrix'],
    category: 'portfolio',
    async execute(params) {
      const startTime = Date.now();
      try {
        const fundId = params.matrixData.metadata?.fundId;
        if (!fundId) {
          throw new Error('Fund ID required for portfolio valuation');
        }

        const response = await fetch(`/api/portfolio/${fundId}/valuation`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
        });

        if (!response.ok) {
          const errBody = await response.json().catch(() => ({}));
          const msg =
            response.status === 502 || response.status === 503
              ? 'Backend unavailable. Start the backend to use portfolio valuation.'
              : errBody.error || 'Failed to value portfolio';
          throw new Error(msg);
        }

        const result = await response.json();

        // Transform result into matrix rows
        const serviceOutput: ServiceOutput = {
          type: Array.isArray(result.companies) ? 'array' : 'object',
          data: result.companies || result,
        };

        const rows = transformServiceOutput(
          serviceOutput,
          params.matrixData.columns
        );

        return {
          success: true,
          data: result,
          rows,
          metadata: {
            executionTime: Date.now() - startTime,
            service: 'valuation_engine',
          },
        };
      } catch (error) {
        return {
          success: false,
          error: error instanceof Error ? error.message : 'Unknown error',
          metadata: { executionTime: Date.now() - startTime },
        };
      }
    },
  },

  buildChart: {
    id: 'buildChart',
    name: 'Build Chart',
    description: 'Generate chart from cell/row data',
    scope: ['range', 'row', 'column'],
    category: 'chart',
    async execute(params) {
      const startTime = Date.now();
      try {
        const chartData = extractChartData(params);
        const chartType = params.additionalParams?.chartType || 'line';

        // This would integrate with chart generation service
        // For now, return the data structure
        return {
          success: true,
          data: {
            type: chartType,
            data: chartData,
          },
          metadata: {
            executionTime: Date.now() - startTime,
            service: 'chart_generator',
          },
        };
      } catch (error) {
        return {
          success: false,
          error: error instanceof Error ? error.message : 'Unknown error',
          metadata: { executionTime: Date.now() - startTime },
        };
      }
    },
  },

  generateDPISankey: {
    id: 'generateDPISankey',
    name: 'DPI Sankey Visualization',
    description: 'Generate DPI flow Sankey: Fund → Companies → Exits → Distributions',
    scope: ['row', 'matrix'],
    category: 'portfolio',
    async execute(params) {
      const startTime = Date.now();
      try {
        const fundId = params.matrixData.metadata?.fundId;
        if (!fundId) {
          throw new Error('Fund ID required for DPI Sankey visualization');
        }

        // This workflow is executed via cell-action-registry, which calls the backend
        // The actual execution happens in CellDropdownRenderer via executeAction
        // This workflow definition just enables it in the UI
        return {
          success: true,
          data: {
            message: 'DPI Sankey visualization will be generated',
            fundId,
          },
          metadata: {
            executionTime: Date.now() - startTime,
            service: 'portfolio_service',
          },
        };
      } catch (error) {
        return {
          success: false,
          error: error instanceof Error ? error.message : 'Unknown error',
          metadata: { executionTime: Date.now() - startTime },
        };
      }
    },
  },

  // Cap table services — executed via backend executeAction in cell dropdown
  calculateCapTable: {
    id: 'calculateCapTable',
    name: 'Calculate Cap Table',
    description: 'Full cap table history through all rounds',
    scope: ['row'],
    category: 'cap_table',
    async execute() {
      return { success: true, metadata: { service: 'pre_post_cap_table' } };
    },
  },
  calculateOwnership: {
    id: 'calculateOwnership',
    name: 'Calculate Ownership',
    description: 'Ownership percentages at a point in time',
    scope: ['row'],
    category: 'cap_table',
    async execute() {
      return { success: true, metadata: { service: 'advanced_cap_table' } };
    },
  },
  calculateDilution: {
    id: 'calculateDilution',
    name: 'Calculate Dilution Path',
    description: 'Dilution through funding rounds',
    scope: ['row'],
    category: 'cap_table',
    async execute() {
      return { success: true, metadata: { service: 'pre_post_cap_table' } };
    },
  },

  // Revenue projection
  buildRevenueProjection: {
    id: 'buildRevenueProjection',
    name: 'Build Revenue Projection',
    description: 'Project revenue with growth decay (year-by-year + chart)',
    scope: ['row'],
    category: 'analysis',
    async execute() {
      return { success: true, metadata: { service: 'revenue_projection_service' } };
    },
  },

  // Waterfall / liquidation
  calculateWaterfall: {
    id: 'calculateWaterfall',
    name: 'Liquidation Waterfall',
    description: 'Calculate liquidation waterfall distribution',
    scope: ['row'],
    category: 'portfolio',
    async execute() {
      return { success: true, metadata: { service: 'advanced_cap_table' } };
    },
  },
  calculateWaterfallBreakpoints: {
    id: 'calculateWaterfallBreakpoints',
    name: 'Waterfall Breakpoints',
    description: 'Breakpoints for waterfall visualization',
    scope: ['row'],
    category: 'portfolio',
    async execute() {
      return { success: true, metadata: { service: 'advanced_cap_table' } };
    },
  },
  calculateExitScenarios: {
    id: 'calculateExitScenarios',
    name: 'Exit Scenario Waterfall',
    description: 'Waterfall for specific exit scenarios',
    scope: ['row'],
    category: 'portfolio',
    async execute() {
      return { success: true, metadata: { service: 'advanced_cap_table' } };
    },
  },

  // Ownership & return analysis
  analyzeOwnership: {
    id: 'analyzeOwnership',
    name: 'Analyze Ownership Scenarios',
    description: 'Ownership scenarios with dilution',
    scope: ['row'],
    category: 'analysis',
    async execute() {
      return { success: true, metadata: { service: 'ownership_return_analyzer' } };
    },
  },
  analyzeReturnScenarios: {
    id: 'analyzeReturnScenarios',
    name: 'Return Scenarios Analysis',
    description: 'Return scenarios with different exit values',
    scope: ['row'],
    category: 'analysis',
    async execute() {
      return { success: true, metadata: { service: 'ownership_return_analyzer' } };
    },
  },

  // NAV & fund
  calculateNAV: {
    id: 'calculateNAV',
    name: 'Calculate NAV',
    description: 'Net Asset Value for company',
    scope: ['row'],
    category: 'portfolio',
    async execute() {
      return { success: true, metadata: { service: 'nav_service' } };
    },
  },
  getNAVTimeSeries: {
    id: 'getNAVTimeSeries',
    name: 'NAV Time Series',
    description: 'NAV over time',
    scope: ['row', 'matrix'],
    category: 'portfolio',
    async execute() {
      return { success: true, metadata: { service: 'nav_service' } };
    },
  },
  calculateFundMetrics: {
    id: 'calculateFundMetrics',
    name: 'Fund Metrics',
    description: 'Fund-level metrics',
    scope: ['matrix'],
    category: 'portfolio',
    async execute() {
      return { success: true, metadata: { service: 'fund_metrics_service' } };
    },
  },

  // Market intelligence
  findComparables: {
    id: 'findComparables',
    name: 'Find Comparables',
    description: 'Comparable companies by geography and sector',
    scope: ['row'],
    category: 'market',
    async execute() {
      return { success: true, metadata: { service: 'market_intelligence_service' } };
    },
  },

  // Follow-on & M&A
  recommendFollowOn: {
    id: 'recommendFollowOn',
    name: 'Follow-On Strategy',
    description: 'Recommend follow-on investment strategy',
    scope: ['row'],
    category: 'portfolio',
    async execute() {
      return { success: true, metadata: { service: 'followon_strategy_service' } };
    },
  },
  modelAcquisition: {
    id: 'modelAcquisition',
    name: 'Model M&A Transaction',
    description: 'Model M&A with synergies',
    scope: ['row'],
    category: 'analysis',
    async execute() {
      return { success: true, metadata: { service: 'ma_workflow_service' } };
    },
  },
  searchMATransactions: {
    id: 'searchMATransactions',
    name: 'M&A Transaction Search',
    description: 'Search comparable M&A transactions',
    scope: ['row'],
    category: 'market',
    async execute() {
      return { success: true, metadata: { service: 'ma_workflow_service' } };
    },
  },

  // Document services
  extractDocument: {
    id: 'extractDocument',
    name: 'Extract Document Data',
    description: 'Extract structured data from document',
    scope: ['row'],
    category: 'analysis',
    async execute() {
      return { success: true, metadata: { service: 'document_query_service' } };
    },
  },
  analyzeDocument: {
    id: 'analyzeDocument',
    name: 'Analyze Document',
    description: 'Analyze document content',
    scope: ['row'],
    category: 'analysis',
    async execute() {
      return { success: true, metadata: { service: 'document_query_service' } };
    },
  },

  // Portfolio optimization
  optimizePortfolio: {
    id: 'optimizePortfolio',
    name: 'Portfolio Optimization',
    description: 'Mean-variance optimization with efficient frontier',
    scope: ['matrix'],
    category: 'portfolio',
    async execute() {
      return { success: true, metadata: { service: 'portfolio_service' } };
    },
  },

  // Enhanced NAV
  navCalculateCompany: {
    id: 'navCalculateCompany',
    name: 'Calculate Company NAV',
    description: 'NAV for a specific company',
    scope: ['row'],
    category: 'portfolio',
    async execute() {
      return { success: true, metadata: { service: 'nav_service' } };
    },
  },
  navCalculatePortfolio: {
    id: 'navCalculatePortfolio',
    name: 'Calculate Portfolio NAV',
    description: 'Total portfolio NAV',
    scope: ['matrix'],
    category: 'portfolio',
    async execute() {
      return { success: true, metadata: { service: 'nav_service' } };
    },
  },
  navTimeseriesCompany: {
    id: 'navTimeseriesCompany',
    name: 'Company NAV Time Series',
    description: 'NAV over time for a company',
    scope: ['row'],
    category: 'portfolio',
    async execute() {
      return { success: true, metadata: { service: 'nav_service' } };
    },
  },
  navForecast: {
    id: 'navForecast',
    name: 'NAV Forecast',
    description: 'Forecast NAV using linear regression',
    scope: ['matrix'],
    category: 'portfolio',
    async execute() {
      return { success: true, metadata: { service: 'nav_service' } };
    },
  },

  // Market intelligence (additional)
  marketTimingAnalysis: {
    id: 'marketTimingAnalysis',
    name: 'Market Timing Analysis',
    description: 'Analyze market timing for investment decisions',
    scope: ['row'],
    category: 'market',
    async execute() {
      return { success: true, metadata: { service: 'market_intelligence_service' } };
    },
  },
  marketInvestmentReadiness: {
    id: 'marketInvestmentReadiness',
    name: 'Investment Readiness Scoring',
    description: 'Score companies for investment readiness',
    scope: ['row', 'matrix'],
    category: 'market',
    async execute() {
      return { success: true, metadata: { service: 'market_intelligence_service' } };
    },
  },
  marketSectorLandscape: {
    id: 'marketSectorLandscape',
    name: 'Sector Landscape',
    description: 'Generate sector landscape visualization',
    scope: ['row'],
    category: 'market',
    async execute() {
      return { success: true, metadata: { service: 'market_intelligence_service' } };
    },
  },

  // Scoring
  scoreCompany: {
    id: 'scoreCompany',
    name: 'Score Company',
    description: 'Comprehensive company scoring with scenarios',
    scope: ['row'],
    category: 'analysis',
    async execute() {
      return { success: true, metadata: { service: 'company_scoring_visualizer' } };
    },
  },
  portfolioDashboard: {
    id: 'portfolioDashboard',
    name: 'Portfolio Dashboard',
    description: 'Generate portfolio-level dashboard',
    scope: ['matrix'],
    category: 'portfolio',
    async execute() {
      return { success: true, metadata: { service: 'company_scoring_visualizer' } };
    },
  },

  // Gap filler
  gapFillerAIImpact: {
    id: 'gapFillerAIImpact',
    name: 'AI Impact Analysis',
    description: 'Analyze AI impact on company',
    scope: ['row'],
    category: 'analysis',
    async execute() {
      return { success: true, metadata: { service: 'intelligent_gap_filler' } };
    },
  },
  gapFillerAIValuation: {
    id: 'gapFillerAIValuation',
    name: 'AI-Adjusted Valuation',
    description: 'Calculate AI-adjusted valuation',
    scope: ['row'],
    category: 'valuation',
    async execute() {
      return { success: true, metadata: { service: 'intelligent_gap_filler' } };
    },
  },
  gapFillerMarketOpportunity: {
    id: 'gapFillerMarketOpportunity',
    name: 'Market Opportunity Analysis',
    description: 'Analyze market opportunity',
    scope: ['row'],
    category: 'analysis',
    async execute() {
      return { success: true, metadata: { service: 'intelligent_gap_filler' } };
    },
  },
  gapFillerMomentum: {
    id: 'gapFillerMomentum',
    name: 'Company Momentum Analysis',
    description: 'Analyze company momentum signals',
    scope: ['row'],
    category: 'analysis',
    async execute() {
      return { success: true, metadata: { service: 'intelligent_gap_filler' } };
    },
  },
  gapFillerFundFit: {
    id: 'gapFillerFundFit',
    name: 'Fund Fit Scoring',
    description: 'Score company for fund fit',
    scope: ['row'],
    category: 'portfolio',
    async execute() {
      return { success: true, metadata: { service: 'intelligent_gap_filler' } };
    },
  },

  // M&A Synergy
  maSynergy: {
    id: 'maSynergy',
    name: 'Calculate M&A Synergy',
    description: 'Calculate M&A synergy value',
    scope: ['row'],
    category: 'analysis',
    async execute() {
      return { success: true, metadata: { service: 'ma_workflow_service' } };
    },
  },

  // Scenario composition
  composeScenario: {
    id: 'composeScenario',
    name: 'Compose Scenario',
    description: "Parse 'what if' scenario query and calculate matrix cell impacts",
    scope: ['row', 'matrix', 'cell'],
    category: 'analysis',
    async execute() {
      return { success: true, metadata: { service: 'matrix_scenario_service' } };
    },
  },

  // MCP Skills - Data Gathering
  fetchCompanyData: {
    id: 'fetchCompanyData',
    name: 'Fetch Company Data',
    description: 'Fetch company metrics, funding, team',
    scope: ['row'],
    category: 'analysis',
    async execute() {
      return { success: true, metadata: { service: 'skill' } };
    },
  },
  aggregateFundingHistory: {
    id: 'aggregateFundingHistory',
    name: 'Aggregate Funding History',
    description: 'Aggregate funding history',
    scope: ['row'],
    category: 'analysis',
    async execute() {
      return { success: true, metadata: { service: 'skill' } };
    },
  },
  marketResearch: {
    id: 'marketResearch',
    name: 'Market Research',
    description: 'Market analysis, TAM, trends',
    scope: ['row'],
    category: 'market',
    async execute() {
      return { success: true, metadata: { service: 'skill' } };
    },
  },
  competitiveAnalysis: {
    id: 'competitiveAnalysis',
    name: 'Competitive Analysis',
    description: 'Competitor analysis',
    scope: ['row'],
    category: 'analysis',
    async execute() {
      return { success: true, metadata: { service: 'skill' } };
    },
  },

  // MCP Skills - Analysis
  valuationEngine: {
    id: 'valuationEngine',
    name: 'Valuation Engine',
    description: 'DCF, comparables valuation',
    scope: ['row'],
    category: 'valuation',
    async execute() {
      return { success: true, metadata: { service: 'skill' } };
    },
  },
  pwermCalculator: {
    id: 'pwermCalculator',
    name: 'PWERM Calculator',
    description: 'PWERM valuation',
    scope: ['row'],
    category: 'valuation',
    async execute() {
      return { success: true, metadata: { service: 'skill' } };
    },
  },
  financialAnalysis: {
    id: 'financialAnalysis',
    name: 'Financial Analysis',
    description: 'Ratios, projections',
    scope: ['row'],
    category: 'financial',
    async execute() {
      return { success: true, metadata: { service: 'skill' } };
    },
  },
  scenarioAnalysis: {
    id: 'scenarioAnalysis',
    name: 'Scenario Analysis',
    description: 'Monte Carlo, sensitivity',
    scope: ['row'],
    category: 'analysis',
    async execute() {
      return { success: true, metadata: { service: 'skill' } };
    },
  },
  dealComparison: {
    id: 'dealComparison',
    name: 'Deal Comparison',
    description: 'Compare deals',
    scope: ['row'],
    category: 'analysis',
    async execute() {
      return { success: true, metadata: { service: 'skill' } };
    },
  },

  // MCP Skills - Generation
  generateDeck: {
    id: 'generateDeck',
    name: 'Generate Deck',
    description: 'Deck storytelling',
    scope: ['row'],
    category: 'chart',
    async execute() {
      return { success: true, metadata: { service: 'skill' } };
    },
  },
  generateExcel: {
    id: 'generateExcel',
    name: 'Generate Excel',
    description: 'Excel generation',
    scope: ['row'],
    category: 'analysis',
    async execute() {
      return { success: true, metadata: { service: 'skill' } };
    },
  },
  generateMemo: {
    id: 'generateMemo',
    name: 'Generate Memo',
    description: 'Memo generation',
    scope: ['row'],
    category: 'analysis',
    async execute() {
      return { success: true, metadata: { service: 'skill' } };
    },
  },
  generateChart: {
    id: 'generateChart',
    name: 'Generate Chart',
    description: 'Chart generation',
    scope: ['row'],
    category: 'chart',
    async execute() {
      return { success: true, metadata: { service: 'skill' } };
    },
  },

  // MCP Skills - Portfolio & Fund
  generateCapTable: {
    id: 'generateCapTable',
    name: 'Generate Cap Table',
    description: 'Cap table generation',
    scope: ['row'],
    category: 'cap_table',
    async execute() {
      return { success: true, metadata: { service: 'skill' } };
    },
  },
  portfolioAnalysis: {
    id: 'portfolioAnalysis',
    name: 'Portfolio Analysis',
    description: 'Portfolio-level analysis',
    scope: ['matrix'],
    category: 'portfolio',
    async execute() {
      return { success: true, metadata: { service: 'skill' } };
    },
  },
  fundMetricsCalculator: {
    id: 'fundMetricsCalculator',
    name: 'Fund Metrics Calculator',
    description: 'Fund-level metrics',
    scope: ['matrix'],
    category: 'portfolio',
    async execute() {
      return { success: true, metadata: { service: 'skill' } };
    },
  },
  stageAnalysis: {
    id: 'stageAnalysis',
    name: 'Stage Analysis',
    description: 'Stage-based analysis',
    scope: ['row', 'matrix'],
    category: 'analysis',
    async execute() {
      return { success: true, metadata: { service: 'skill' } };
    },
  },
  exitModeling: {
    id: 'exitModeling',
    name: 'Exit Modeling',
    description: 'Exit scenario modeling',
    scope: ['row'],
    category: 'portfolio',
    async execute() {
      return { success: true, metadata: { service: 'skill' } };
    },
  },
};

/**
 * Helper functions to extract data from matrix
 */
function extractCashFlows(params: WorkflowParams): number[] {
  if (params.cellRange) {
    // Extract from range
    const { startRow, endRow, startCol, endCol } = params.cellRange;
    const rows = params.matrixData.rows.filter(
      r => r.id >= startRow && r.id <= endRow
    );
    const col = params.matrixData.columns.find(c => c.id === startCol);
    if (!col) return [];

    return rows
      .map(row => {
        const cell = row.cells[col.id];
        return typeof cell?.value === 'number' ? cell.value : parseFloat(String(cell?.value || 0));
      })
      .filter(v => !isNaN(v));
  }

  if (params.columnId) {
    // Extract from column
    return params.matrixData.rows
      .map(row => {
        const cell = row.cells[params.columnId!];
        return typeof cell?.value === 'number' ? cell.value : parseFloat(String(cell?.value || 0));
      })
      .filter(v => !isNaN(v));
  }

  return [];
}

function extractNumericValues(params: WorkflowParams): number[] {
  return extractCashFlows(params); // Same logic
}

function extractMOICParams(params: WorkflowParams): { exitValue: number; invested: number } {
  if (!params.rowId) {
    throw new Error('Row ID required for MOIC calculation');
  }

  const row = params.matrixData.rows.find(r => r.id === params.rowId);
  if (!row) {
    throw new Error('Row not found');
  }

  // Try to find exit value and invested columns
  const exitCol = params.matrixData.columns.find(c => 
    c.id === 'valuation' || c.id === 'exitValue' || c.name.toLowerCase().includes('exit')
  );
  const investedCol = params.matrixData.columns.find(c => 
    c.id === 'invested' || c.id === 'investmentAmount' || c.name.toLowerCase().includes('invested')
  );

  const exitValue = exitCol ? parseFloat(String(row.cells[exitCol.id]?.value || 0)) : 0;
  const invested = investedCol ? parseFloat(String(row.cells[investedCol.id]?.value || 0)) : 0;

  return { exitValue, invested };
}

function extractChartData(params: WorkflowParams): any {
  if (params.rowId) {
    const row = params.matrixData.rows.find(r => r.id === params.rowId);
    if (!row) return {};

    const data: Record<string, any> = {};
    params.matrixData.columns.forEach(col => {
      data[col.name] = row.cells[col.id]?.value;
    });
    return data;
  }

  if (params.columnId) {
    return params.matrixData.rows.map(row => ({
      label: row.companyName || row.id,
      value: row.cells[params.columnId!]?.value,
    }));
  }

  return {};
}

/**
 * Get available workflows for a scope
 */
export function getAvailableWorkflows(scope: WorkflowScope): WorkflowDefinition[] {
  return Object.values(WORKFLOWS).filter(w => w.scope.includes(scope));
}

/**
 * Get workflows by category
 */
export function getWorkflowsByCategory(category: WorkflowDefinition['category']): WorkflowDefinition[] {
  return Object.values(WORKFLOWS).filter(w => w.category === category);
}

/**
 * Execute a workflow
 */
export async function executeWorkflow(
  workflowId: string,
  params: WorkflowParams
): Promise<WorkflowResult> {
  const workflow = WORKFLOWS[workflowId];
  if (!workflow) {
    return {
      success: false,
      error: `Workflow ${workflowId} not found`,
    };
  }

  return workflow.execute(params);
}
