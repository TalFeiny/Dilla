/**
 * Workflow ID → Backend action_id mapping
 * Used by CellDropdownRenderer to route workflow clicks to executeAction.
 * Workflow ids from cell-workflows.ts; action_ids from backend cell_action_registry.
 * 
 * This map should include all services registered in backend/app/services/cell_action_registry.py
 */

export const WORKFLOW_TO_ACTION_ID: Record<string, string> = {
  // Financial formulas
  calculateIRR: 'financial.irr',
  calculateNPV: 'financial.npv',
  calculateMOIC: 'financial.moic',
  calculateCAGR: 'financial.cagr',
  
  // Valuation workflows
  runValuation: 'valuation_engine.auto',
  runPWERM: 'valuation_engine.pwerm',
  runDCF: 'valuation_engine.dcf',
  runOPM: 'valuation_engine.opm',
  runWaterfallValuation: 'valuation_engine.waterfall',
  runRecentTransaction: 'valuation_engine.recent_transaction',
  runCostMethod: 'valuation_engine.cost_method',
  runMilestone: 'valuation_engine.milestone',
  
  // Chart generation
  buildChart: 'chart_intelligence.generate',
  
  // Portfolio services
  valuePortfolio: 'portfolio.total_nav',
  calculateTotalInvested: 'portfolio.total_invested',
  calculateDPI: 'portfolio.dpi',
  calculateTVPI: 'portfolio.tvpi',
  generateDPISankey: 'portfolio.dpi_sankey',
  optimizePortfolio: 'portfolio.optimize',
  
  // NAV services
  calculateNAV: 'nav.calculate',
  getNAVTimeSeries: 'nav.timeseries',
  navCalculateCompany: 'nav.calculate_company',
  navCalculatePortfolio: 'nav.calculate_portfolio',
  navTimeseriesCompany: 'nav.timeseries_company',
  navForecast: 'nav.forecast',
  
  // Fund metrics
  calculateFundMetrics: 'fund_metrics.calculate',
  
  // Revenue projection
  buildRevenueProjection: 'revenue_projection.build',
  
  // Document services
  extractDocument: 'document.extract',
  analyzeDocument: 'document.analyze',
  
  // Market intelligence
  findComparables: 'market.find_comparables',
  
  // Waterfall services
  calculateWaterfall: 'waterfall.calculate',
  calculateWaterfallBreakpoints: 'waterfall.breakpoints',
  calculateExitScenarios: 'waterfall.exit_scenarios',
  
  // Cap table services
  calculateCapTable: 'cap_table.calculate',
  calculateOwnership: 'cap_table.ownership',
  calculateDilution: 'cap_table.dilution',
  
  // Ownership & Return Analysis
  analyzeOwnership: 'ownership.analyze',
  analyzeReturnScenarios: 'ownership.return_scenarios',
  
  // Follow-on strategy
  recommendFollowOn: 'followon_strategy.recommend',
  
  // M&A Workflow
  modelAcquisition: 'ma.model_acquisition',
  searchMATransactions: 'ma.transactions',
  maSynergy: 'ma.synergy',
  
  // Scenario composition
  composeScenario: 'scenario.compose',
  
  // Unified MCP Orchestrator Skills - Data Gathering
  fetchCompanyData: 'skill.company_data_fetch',
  aggregateFundingHistory: 'skill.funding_aggregation',
  marketResearch: 'skill.market_research',
  competitiveAnalysis: 'skill.competitive_analysis',
  
  // Unified MCP Orchestrator Skills - Analysis
  valuationEngine: 'skill.valuation_engine',
  pwermCalculator: 'skill.pwerm_calculator',
  financialAnalysis: 'skill.financial_analysis',
  scenarioAnalysis: 'skill.scenario_analysis',
  dealComparison: 'skill.deal_comparison',
  
  // Unified MCP Orchestrator Skills - Generation
  generateDeck: 'skill.deck_storytelling',
  generateExcel: 'skill.excel_generation',
  generateMemo: 'skill.memo_generation',
  generateChart: 'skill.chart_generation',
  
  // Unified MCP Orchestrator Skills - Portfolio & Fund
  generateCapTable: 'skill.cap_table_generation',
  portfolioAnalysis: 'skill.portfolio_analysis',
  fundMetricsCalculator: 'skill.fund_metrics_calculator',
  stageAnalysis: 'skill.stage_analysis',
  exitModeling: 'skill.exit_modeling',
};

export function getActionIdForWorkflow(workflowId: string): string | undefined {
  return WORKFLOW_TO_ACTION_ID[workflowId];
}
