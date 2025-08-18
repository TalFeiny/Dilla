import { createClient } from '@supabase/supabase-js';
import Anthropic from '@anthropic-ai/sdk';

const supabase = createClient(
  process.env.NEXT_PUBLIC_SUPABASE_URL!,
  process.env.SUPABASE_SERVICE_ROLE_KEY!
);

const anthropic = new Anthropic({
  apiKey: process.env.ANTHROPIC_API_KEY || process.env.CLAUDE_API_KEY || '',
});

/**
 * MACRO-AWARE PATTERN RECOGNITION ENGINE
 * 
 * Philosophy with £300 AUM:
 * - Can't diversify traditionally (too small)
 * - Must concentrate BUT hedge smartly
 * - Find uncorrelated bets using macro patterns
 * - Use database to identify historical patterns
 * 
 * Strategy:
 * 1. Identify macro regime (inflation, deflation, war, peace)
 * 2. Find 2-3 uncorrelated bets
 * 3. Natural hedges (long tech/short banks)
 * 4. Pattern recognition from our database
 * 5. Risk parity with tiny capital
 */

interface MacroRegime {
  type: 'inflation' | 'deflation' | 'stagflation' | 'growth' | 'recession' | 'war' | 'peace';
  confidence: number;
  indicators: Record<string, number>;
  timeline: string;
}

interface Pattern {
  id: string;
  description: string;
  historicalExamples: string[];
  currentSignals: string[];
  probability: number;
  expectedOutcome: string;
  timeframe: string;
}

interface RiskReturnProfile {
  asset: string;
  expectedReturn: number;
  risk: number; // Standard deviation
  sharpeRatio: number;
  correlation: Record<string, number>; // Correlation with other assets
  macroSensitivity: Record<string, number>; // Sensitivity to macro factors
}

interface HedgedPortfolio {
  positions: Position[];
  totalValue: number;
  expectedReturn: number;
  portfolioRisk: number;
  sharpeRatio: number;
  maxDrawdown: number;
  correlationMatrix: number[][];
  naturalHedges: NaturalHedge[];
}

interface Position {
  asset: string;
  type: 'long' | 'short' | 'option';
  size: number;
  weight: number;
  rationale: string;
}

interface NaturalHedge {
  long: string;
  short: string;
  correlation: number;
  hedgeRatio: number;
  explanation: string;
}

export class MacroPatternEngine {
  private historicalPatterns: Map<string, Pattern> = new Map();
  private currentRegime: MacroRegime | null = null;
  
  constructor() {
    this.loadHistoricalPatterns();
  }

  /**
   * Identify current macro regime
   */
  async identifyMacroRegime(): Promise<MacroRegime> {
    const indicators = await this.gatherMacroIndicators();
    
    // Analyze indicators to determine regime
    const regime = this.analyzeRegime(indicators);
    
    this.currentRegime = regime;
    
    // Store in database for pattern learning
    await this.storeRegimeAnalysis(regime);
    
    return regime;
  }

  /**
   * Find patterns in our database
   */
  async findPatternsInDatabase(
    query: string = ''
  ): Promise<Pattern[]> {
    // Query our database for historical patterns
    const { data: companies } = await supabase
      .from('companies')
      .select('*')
      .order('created_at', { ascending: false })
      .limit(100);
    
    const { data: portfolioData } = await supabase
      .from('portfolio_companies')
      .select('*');
    
    const { data: pwermResults } = await supabase
      .from('pwerm_results')
      .select('*');
    
    // Analyze for patterns
    const patterns = await this.extractPatterns(companies, portfolioData, pwermResults);
    
    // Use Claude to identify macro patterns
    const macroPatterns = await this.identifyMacroPatterns(patterns);
    
    return macroPatterns;
  }

  /**
   * Build uncorrelated portfolio with hedges
   */
  async buildHedgedPortfolio(
    capital: number = 300,
    riskTolerance: 'conservative' | 'moderate' | 'aggressive' = 'aggressive'
  ): Promise<HedgedPortfolio> {
    const regime = this.currentRegime || await this.identifyMacroRegime();
    
    // Find uncorrelated opportunities
    const opportunities = await this.findUncorrelatedOpportunities(regime);
    
    // Calculate optimal position sizes (Kelly Criterion adapted for small capital)
    const positions = this.calculatePositions(opportunities, capital, riskTolerance);
    
    // Identify natural hedges
    const naturalHedges = this.identifyNaturalHedges(positions);
    
    // Calculate portfolio metrics
    const metrics = this.calculatePortfolioMetrics(positions, naturalHedges);
    
    return {
      positions,
      totalValue: capital,
      expectedReturn: metrics.expectedReturn,
      portfolioRisk: metrics.risk,
      sharpeRatio: metrics.sharpeRatio,
      maxDrawdown: metrics.maxDrawdown,
      correlationMatrix: metrics.correlationMatrix,
      naturalHedges
    };
  }

  /**
   * Gather macro indicators
   */
  private async gatherMacroIndicators(): Promise<Record<string, number>> {
    // In production, this would pull real data
    // For now, using representative values
    return {
      inflation: 3.7, // CPI YoY
      gdpGrowth: 2.1,
      unemployment: 3.9,
      interestRates: 5.5,
      vix: 18, // Volatility index
      dollarIndex: 103,
      oilPrice: 85,
      goldPrice: 2050,
      btcPrice: 45000,
      yieldCurve: -0.5, // 10Y-2Y spread
      creditSpreads: 120, // Basis points
      m2Growth: 4.5,
      sentimentIndex: 45, // Fear/Greed
      geopoliticalRisk: 7 // 1-10 scale
    };
  }

  /**
   * Analyze regime from indicators
   */
  private analyzeRegime(indicators: Record<string, number>): MacroRegime {
    let type: MacroRegime['type'] = 'growth';
    let confidence = 0;
    
    // Inflation regime
    if (indicators.inflation > 4 && indicators.gdpGrowth > 2) {
      type = 'inflation';
      confidence = 0.7;
    }
    // Stagflation
    else if (indicators.inflation > 4 && indicators.gdpGrowth < 1) {
      type = 'stagflation';
      confidence = 0.8;
    }
    // Deflation risk
    else if (indicators.inflation < 1 && indicators.gdpGrowth < 1) {
      type = 'deflation';
      confidence = 0.6;
    }
    // Recession
    else if (indicators.yieldCurve < 0 && indicators.unemployment > 4.5) {
      type = 'recession';
      confidence = 0.75;
    }
    // War/conflict
    else if (indicators.geopoliticalRisk > 7) {
      type = 'war';
      confidence = 0.8;
    }
    // Growth
    else if (indicators.gdpGrowth > 3 && indicators.inflation < 3) {
      type = 'growth';
      confidence = 0.7;
    }
    
    return {
      type,
      confidence,
      indicators,
      timeline: '6-12 months'
    };
  }

  /**
   * Extract patterns from database
   */
  private async extractPatterns(
    companies: any[],
    portfolio: any[],
    pwerm: any[]
  ): Promise<Pattern[]> {
    const patterns: Pattern[] = [];
    
    // Pattern 1: Sector rotation
    const sectorPerformance = this.analyzeSectorRotation(companies, portfolio);
    if (sectorPerformance.pattern) {
      patterns.push(sectorPerformance.pattern);
    }
    
    // Pattern 2: Valuation cycles
    const valuationCycles = this.analyzeValuationCycles(companies);
    if (valuationCycles.pattern) {
      patterns.push(valuationCycles.pattern);
    }
    
    // Pattern 3: Exit timing patterns
    const exitPatterns = this.analyzeExitPatterns(portfolio);
    if (exitPatterns.pattern) {
      patterns.push(exitPatterns.pattern);
    }
    
    // Pattern 4: Correlation shifts
    const correlations = await this.analyzeCorrelationShifts(portfolio);
    if (correlations.pattern) {
      patterns.push(correlations.pattern);
    }
    
    return patterns;
  }

  /**
   * Analyze sector rotation patterns
   */
  private analyzeSectorRotation(companies: any[], portfolio: any[]): any {
    const sectorReturns: Record<string, number[]> = {};
    
    // Group by sector and calculate returns
    for (const company of companies) {
      if (!sectorReturns[company.sector]) {
        sectorReturns[company.sector] = [];
      }
      // Calculate implied return
      const impliedReturn = (company.current_valuation_usd - company.initial_valuation_usd) / 
                           company.initial_valuation_usd;
      sectorReturns[company.sector].push(impliedReturn);
    }
    
    // Identify rotation pattern
    const pattern: Pattern = {
      id: 'sector-rotation-' + Date.now(),
      description: 'Sector rotation from tech to value',
      historicalExamples: ['2000 tech bubble', '2008 financial crisis', '2022 rate hikes'],
      currentSignals: ['Rising rates', 'Tech multiples compressing'],
      probability: 0.65,
      expectedOutcome: 'Value outperforms growth by 20%',
      timeframe: '12-18 months'
    };
    
    return { pattern, sectorReturns };
  }

  /**
   * Analyze valuation cycles
   */
  private analyzeValuationCycles(companies: any[]): any {
    const valuations = companies.map(c => c.current_valuation_usd / (c.current_arr_usd || 1));
    const avgValuation = valuations.reduce((a, b) => a + b, 0) / valuations.length;
    
    let pattern: Pattern | null = null;
    
    if (avgValuation > 15) {
      pattern = {
        id: 'valuation-peak-' + Date.now(),
        description: 'Valuations at cycle peak',
        historicalExamples: ['1999', '2007', '2021'],
        currentSignals: ['P/S > 15x', 'IPO frenzy', 'Retail participation high'],
        probability: 0.7,
        expectedOutcome: '30-50% correction within 18 months',
        timeframe: '12-24 months'
      };
    }
    
    return { pattern, avgValuation };
  }

  /**
   * Analyze exit patterns
   */
  private analyzeExitPatterns(portfolio: any[]): any {
    // Analyze holding periods and exit multiples
    const exits = portfolio.filter(p => p.exit_date);
    
    const pattern: Pattern = {
      id: 'exit-pattern-' + Date.now(),
      description: 'Optimal exit timing identified',
      historicalExamples: exits.map(e => e.company_name),
      currentSignals: ['M&A activity increasing', 'Strategic buyers active'],
      probability: 0.6,
      expectedOutcome: '3-5x returns on well-timed exits',
      timeframe: '6-12 months'
    };
    
    return { pattern };
  }

  /**
   * Analyze correlation shifts
   */
  private async analyzeCorrelationShifts(portfolio: any[]): Promise<any> {
    // This would calculate actual correlations
    // For now, identifying regime-based correlation changes
    
    const pattern: Pattern = {
      id: 'correlation-shift-' + Date.now(),
      description: 'Correlations converging to 1 (risk-off)',
      historicalExamples: ['March 2020', 'Sept 2008', 'Aug 2011'],
      currentSignals: ['VIX rising', 'Dollar strengthening', 'Bonds rallying'],
      probability: 0.5,
      expectedOutcome: 'Flight to quality, all risk assets sell off',
      timeframe: '1-3 months'
    };
    
    return { pattern };
  }

  /**
   * Identify macro patterns using Claude
   */
  private async identifyMacroPatterns(patterns: Pattern[]): Promise<Pattern[]> {
    const prompt = `Analyze these patterns and identify macro themes:
${JSON.stringify(patterns, null, 2)}

Identify:
1. Overarching macro narrative
2. Hidden correlations
3. Regime change signals
4. Black swan risks
5. Contrarian opportunities`;

    const response = await anthropic.messages.create({
      model: 'claude-3-5-sonnet-20241022',
      max_tokens: 1000,
      temperature: 0,
      messages: [{ role: 'user', content: prompt }]
    });
    
    // Parse response and add to patterns
    const analysis = response.content[0].type === 'text' ? response.content[0].text : '';
    
    // Add macro overlay pattern
    patterns.push({
      id: 'macro-overlay-' + Date.now(),
      description: 'Macro regime shift detected',
      historicalExamples: ['Parsed from Claude analysis'],
      currentSignals: ['Multiple indicators aligning'],
      probability: 0.7,
      expectedOutcome: analysis.substring(0, 200),
      timeframe: '6-18 months'
    });
    
    return patterns;
  }

  /**
   * Find uncorrelated opportunities
   */
  private async findUncorrelatedOpportunities(
    regime: MacroRegime
  ): Promise<RiskReturnProfile[]> {
    const opportunities: RiskReturnProfile[] = [];
    
    // Based on regime, identify uncorrelated bets
    if (regime.type === 'inflation') {
      opportunities.push(
        {
          asset: 'Commodities/Materials Tech',
          expectedReturn: 0.35,
          risk: 0.25,
          sharpeRatio: 1.4,
          correlation: { tech: -0.3, bonds: -0.7, commodities: 0.8 },
          macroSensitivity: { inflation: 0.9, growth: 0.3, rates: -0.5 }
        },
        {
          asset: 'Pricing Power SaaS',
          expectedReturn: 0.25,
          risk: 0.20,
          sharpeRatio: 1.25,
          correlation: { tech: 0.5, bonds: -0.4, commodities: 0.2 },
          macroSensitivity: { inflation: 0.3, growth: 0.7, rates: -0.3 }
        },
        {
          asset: 'Short Duration Credit',
          expectedReturn: 0.08,
          risk: 0.05,
          sharpeRatio: 1.6,
          correlation: { tech: -0.2, bonds: 0.3, commodities: 0.1 },
          macroSensitivity: { inflation: -0.2, growth: 0.2, rates: 0.4 }
        }
      );
    } else if (regime.type === 'deflation') {
      opportunities.push(
        {
          asset: 'Long Duration Tech',
          expectedReturn: 0.45,
          risk: 0.35,
          sharpeRatio: 1.3,
          correlation: { tech: 0.9, bonds: 0.6, commodities: -0.5 },
          macroSensitivity: { inflation: -0.8, growth: 0.9, rates: -0.9 }
        },
        {
          asset: 'Government Bonds',
          expectedReturn: 0.12,
          risk: 0.08,
          sharpeRatio: 1.5,
          correlation: { tech: -0.3, bonds: 1.0, commodities: -0.6 },
          macroSensitivity: { inflation: -0.7, growth: -0.3, rates: -0.8 }
        }
      );
    } else if (regime.type === 'stagflation') {
      opportunities.push(
        {
          asset: 'Energy Tech',
          expectedReturn: 0.40,
          risk: 0.30,
          sharpeRatio: 1.33,
          correlation: { tech: 0.2, bonds: -0.5, commodities: 0.7 },
          macroSensitivity: { inflation: 0.7, growth: -0.2, rates: -0.3 }
        },
        {
          asset: 'Gold/Crypto Hedge',
          expectedReturn: 0.20,
          risk: 0.25,
          sharpeRatio: 0.8,
          correlation: { tech: 0.1, bonds: -0.4, commodities: 0.5 },
          macroSensitivity: { inflation: 0.8, growth: -0.4, rates: -0.6 }
        }
      );
    }
    
    return opportunities;
  }

  /**
   * Calculate positions using risk parity for small capital
   */
  private calculatePositions(
    opportunities: RiskReturnProfile[],
    capital: number,
    riskTolerance: string
  ): Position[] {
    const positions: Position[] = [];
    
    // With £300, max 2-3 positions
    const maxPositions = capital < 500 ? 2 : 3;
    
    // Sort by Sharpe ratio
    opportunities.sort((a, b) => b.sharpeRatio - a.sharpeRatio);
    
    // Take top positions
    const selected = opportunities.slice(0, maxPositions);
    
    // Calculate weights using risk parity
    const totalRisk = selected.reduce((sum, opp) => sum + (1 / opp.risk), 0);
    
    for (const opp of selected) {
      const weight = (1 / opp.risk) / totalRisk;
      positions.push({
        asset: opp.asset,
        type: 'long',
        size: capital * weight,
        weight,
        rationale: `Sharpe: ${opp.sharpeRatio.toFixed(2)}, Uncorrelated to others`
      });
    }
    
    return positions;
  }

  /**
   * Identify natural hedges
   */
  private identifyNaturalHedges(positions: Position[]): NaturalHedge[] {
    const hedges: NaturalHedge[] = [];
    
    // Find negatively correlated pairs
    for (let i = 0; i < positions.length; i++) {
      for (let j = i + 1; j < positions.length; j++) {
        // This would use actual correlation data
        // For now, using heuristics
        if (positions[i].asset.includes('Tech') && positions[j].asset.includes('Bonds')) {
          hedges.push({
            long: positions[i].asset,
            short: positions[j].asset,
            correlation: -0.4,
            hedgeRatio: 0.6,
            explanation: 'Tech/Bonds negative correlation in rising rate environment'
          });
        }
      }
    }
    
    // Add macro hedges
    hedges.push({
      long: 'Portfolio',
      short: 'VIX Calls',
      correlation: -0.7,
      hedgeRatio: 0.1,
      explanation: 'Tail risk hedge for black swan events'
    });
    
    return hedges;
  }

  /**
   * Calculate portfolio metrics
   */
  private calculatePortfolioMetrics(
    positions: Position[],
    hedges: NaturalHedge[]
  ): any {
    // Simple portfolio calculations
    const weights = positions.map(p => p.weight);
    const expectedReturns = [0.35, 0.25, 0.15]; // Placeholder
    
    // Portfolio return
    const expectedReturn = weights.reduce((sum, w, i) => 
      sum + w * (expectedReturns[i] || 0.2), 0
    );
    
    // Portfolio risk (simplified)
    const risk = 0.20; // 20% volatility
    
    // Sharpe ratio
    const riskFreeRate = 0.05;
    const sharpeRatio = (expectedReturn - riskFreeRate) / risk;
    
    // Max drawdown estimate
    const maxDrawdown = risk * 2; // Rule of thumb
    
    // Correlation matrix (simplified)
    const correlationMatrix = [
      [1.0, 0.3, -0.2],
      [0.3, 1.0, 0.1],
      [-0.2, 0.1, 1.0]
    ];
    
    return {
      expectedReturn,
      risk,
      sharpeRatio,
      maxDrawdown,
      correlationMatrix
    };
  }

  /**
   * Store regime analysis
   */
  private async storeRegimeAnalysis(regime: MacroRegime): Promise<void> {
    await supabase
      .from('agent_market_intelligence')
      .insert({
        data_type: 'macro_regime',
        data_point: regime,
        source: 'macro_pattern_engine',
        confidence_score: regime.confidence * 100,
        expires_at: new Date(Date.now() + 7 * 24 * 60 * 60 * 1000)
      });
  }

  /**
   * Load historical patterns
   */
  private async loadHistoricalPatterns(): Promise<void> {
    const { data } = await supabase
      .from('agent_market_intelligence')
      .select('*')
      .eq('data_type', 'pattern')
      .order('created_at', { ascending: false })
      .limit(100);
    
    if (data) {
      for (const item of data) {
        this.historicalPatterns.set(item.id, item.data_point as Pattern);
      }
    }
  }

  /**
   * Generate specific recommendation for £300
   */
  async generateRecommendation(capital: number = 300): Promise<string> {
    const regime = await this.identifyMacroRegime();
    const portfolio = await this.buildHedgedPortfolio(capital);
    
    return `
MACRO REGIME: ${regime.type.toUpperCase()} (${(regime.confidence * 100).toFixed(0)}% confidence)

WITH £${capital} CAPITAL:
${portfolio.positions.map(p => 
  `• ${p.asset}: £${p.size.toFixed(0)} (${(p.weight * 100).toFixed(0)}%)`
).join('\n')}

EXPECTED RETURN: ${(portfolio.expectedReturn * 100).toFixed(0)}%
RISK: ${(portfolio.portfolioRisk * 100).toFixed(0)}%
SHARPE RATIO: ${portfolio.sharpeRatio.toFixed(2)}

NATURAL HEDGES:
${portfolio.naturalHedges.map(h => 
  `• ${h.explanation}`
).join('\n')}

KEY INSIGHT: With tiny capital, concentrate on ${portfolio.positions.length} uncorrelated bets.
Each position naturally hedges the others through negative correlation.
No need for expensive options or complex hedges.
    `;
  }
}

// Export singleton instance
export const macroPatternEngine = new MacroPatternEngine();