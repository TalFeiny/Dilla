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
 * SOCRATIC DECISION ENGINE - ANTI-THOUGHT-LOOP PHILOSOPHY
 * 
 * Problem: Herd mentality leads to overvalued sectors (e.g., "everyone's doing defense tech")
 * Solution: Socratic questioning that challenges assumptions and prevents circular reasoning
 * 
 * Core Principles:
 * 1. Question the premise, not just the conclusion
 * 2. Identify hidden assumptions
 * 3. Seek disconfirming evidence
 * 4. Consider second and third-order effects
 * 5. Break thought loops with contradictory perspectives
 * 
 * Example: Defense Tech Analysis
 * - Level 1: "Is defense tech hot?" (Surface)
 * - Level 2: "Why is everyone going into defense tech?" (Motivation)
 * - Level 3: "What happens when everyone crowds into defense tech?" (Consequence)
 * - Level 4: "What are we missing while looking at defense tech?" (Opportunity cost)
 * - Level 5: "What kills defense tech thesis?" (Inversion)
 */

interface SocraticQuestion {
  level: number;
  question: string;
  category: 'premise' | 'evidence' | 'alternative' | 'consequence' | 'inversion';
  followUps: string[];
}

interface DecisionNode {
  id: string;
  statement: string;
  questions: SocraticQuestion[];
  assumptions: string[];
  contradictions: string[];
  score: number;
  timestamp: Date;
}

interface ThoughtLoop {
  pattern: string;
  frequency: number;
  breakerQuestions: string[];
  lastOccurrence: Date;
}

interface TrendAnalysis {
  trend: string;
  herdScore: number; // 0-100, how many following
  contrarian: string; // What everyone's missing
  realValue: number; // Actual opportunity score
  timing: 'too_early' | 'right_time' | 'too_late' | 'bubble';
}

export class SocraticDecisionEngine {
  private thoughtLoops: Map<string, ThoughtLoop> = new Map();
  private decisionTree: Map<string, DecisionNode> = new Map();
  private maxQuestionDepth = 5;
  private loopDetectionThreshold = 3;
  
  constructor() {
    this.initializeCommonLoops();
  }

  /**
   * Analyze a trend using Socratic method
   */
  async analyzeTrend(
    trend: string,
    context: any = {}
  ): Promise<TrendAnalysis> {
    // Example: "Everyone's going into defense tech"
    const questions = this.generateSocraticQuestions(trend);
    const answers = await this.seekAnswers(questions, context);
    
    // Detect herd mentality
    const herdScore = await this.calculateHerdScore(trend);
    
    // Find contrarian angle
    const contrarian = await this.findContrarianAngle(trend, answers);
    
    // Calculate real value
    const realValue = await this.calculateRealValue(trend, herdScore, answers);
    
    // Determine timing
    const timing = this.determineTiming(herdScore, realValue);
    
    return {
      trend,
      herdScore,
      contrarian,
      realValue,
      timing
    };
  }

  /**
   * Generate Socratic questions for a statement
   */
  generateSocraticQuestions(statement: string): SocraticQuestion[] {
    const questions: SocraticQuestion[] = [];
    
    // Level 1: Premise Questions
    questions.push({
      level: 1,
      question: `What evidence supports "${statement}"?`,
      category: 'premise',
      followUps: [
        'How reliable is this evidence?',
        'Who benefits from this narrative?',
        'What data contradicts this?'
      ]
    });
    
    // Level 2: Evidence Questions
    questions.push({
      level: 2,
      question: `Why do people believe "${statement}" now versus 2 years ago?`,
      category: 'evidence',
      followUps: [
        'What changed in the market?',
        'Is this a temporary catalyst or structural shift?',
        'How long will these conditions persist?'
      ]
    });
    
    // Level 3: Alternative Questions
    questions.push({
      level: 3,
      question: `If "${statement}" is wrong, what's the opposite bet?`,
      category: 'alternative',
      followUps: [
        'What sectors are being ignored?',
        'Where is capital flowing FROM?',
        'What\'s the non-consensus view?'
      ]
    });
    
    // Level 4: Consequence Questions
    questions.push({
      level: 4,
      question: `What happens when everyone acts on "${statement}"?`,
      category: 'consequence',
      followUps: [
        'How does supply/demand change?',
        'What gets overvalued?',
        'Where do returns compress?'
      ]
    });
    
    // Level 5: Inversion Questions
    questions.push({
      level: 5,
      question: `What would make "${statement}" completely wrong?`,
      category: 'inversion',
      followUps: [
        'What black swan kills this thesis?',
        'What assumption is most fragile?',
        'When does the music stop?'
      ]
    });
    
    return questions;
  }

  /**
   * Detect and break thought loops
   */
  async detectAndBreakLoop(
    currentThought: string,
    history: string[]
  ): Promise<{
    isLoop: boolean;
    loopType?: string;
    breakerQuestions?: string[];
    suggestion?: string;
  }> {
    // Check for circular reasoning
    const pattern = this.identifyPattern(currentThought);
    
    // Count pattern frequency in history
    const frequency = history.filter(h => this.identifyPattern(h) === pattern).length;
    
    if (frequency >= this.loopDetectionThreshold) {
      const loop = this.thoughtLoops.get(pattern) || this.createLoopBreaker(pattern);
      
      return {
        isLoop: true,
        loopType: pattern,
        breakerQuestions: loop.breakerQuestions,
        suggestion: await this.generateLoopBreakingSuggestion(pattern, currentThought)
      };
    }
    
    return { isLoop: false };
  }

  /**
   * Defense Tech specific analysis
   */
  async analyzeDefenseTech(): Promise<{
    socraticAnalysis: any;
    herdWarning: string;
    contrarian: string;
    realOpportunity: string;
  }> {
    const analysis = await this.analyzeTrend('Everyone is going into defense tech');
    
    // Socratic deep dive
    const socraticAnalysis = {
      level1_surface: {
        question: 'Is defense tech actually growing?',
        answer: 'Yes, $35B in 2024, growing 15% YoY',
        followUp: 'But is 15% exceptional compared to other sectors?'
      },
      level2_motivation: {
        question: 'Why the sudden interest in defense tech?',
        answer: 'Geopolitical tensions, Ukraine war, China concerns',
        followUp: 'Are these permanent shifts or cyclical?'
      },
      level3_competition: {
        question: 'What happens when every VC funds defense startups?',
        answer: 'Valuations inflate, talent gets expensive, returns compress',
        followUp: 'Where were these VCs investing before? What\'s now undervalued?'
      },
      level4_contrarian: {
        question: 'What if peace breaks out?',
        answer: 'Defense budgets shrink, dual-use becomes critical',
        followUp: 'Which defense techs survive peace? Which die?'
      },
      level5_inversion: {
        question: 'What\'s the opposite of defense tech?',
        answer: 'Peace tech, collaboration tools, cultural exchange, trade facilitation',
        followUp: 'Are these now undervalued because everyone\'s looking at defense?'
      }
    };
    
    // Herd warning
    const herdWarning = analysis.herdScore > 70 ? 
      '🚨 HERD ALERT: When everyone\'s in defense tech, returns go to those who aren\'t' :
      '✅ Still early enough for selective opportunities';
    
    // Contrarian view
    const contrarian = `While everyone funds defense, consider:
    1. Civilian spin-offs from defense research (internet → DARPA)
    2. Peace-building technology (undervalued)
    3. Dual-use with civilian markets (better exit options)
    4. Countries NOT increasing defense spend (different markets)
    5. Technologies that prevent wars (cyber-diplomacy, economic interdependence)`;
    
    // Real opportunity
    const realOpportunity = `The real alpha in defense tech:
    1. **Picks & shovels**: Supply chain for defense contractors (less regulated)
    2. **Dual-use AI**: Military training → corporate training
    3. **Cybersecurity**: Benefits from conflict AND peace
    4. **Space tech**: Defense adjacent but broader market
    5. **Exit strategy**: Who buys defense startups? (Limited buyers = limited exits)`;
    
    return {
      socraticAnalysis,
      herdWarning,
      contrarian,
      realOpportunity
    };
  }

  /**
   * Calculate herd score (how many following trend)
   */
  private async calculateHerdScore(trend: string): Promise<number> {
    // Analyze mentions, funding data, news frequency
    const indicators = {
      mediaMetions: 0,
      fundingRounds: 0,
      vcTweets: 0,
      conferenceTopics: 0
    };
    
    // Simulate scoring (would pull real data)
    if (trend.includes('defense tech')) {
      indicators.mediaMetions = 85;
      indicators.fundingRounds = 75;
      indicators.vcTweets = 90;
      indicators.conferenceTopics = 80;
    } else if (trend.includes('AI')) {
      indicators.mediaMetions = 95;
      indicators.fundingRounds = 90;
      indicators.vcTweets = 95;
      indicators.conferenceTopics = 95;
    }
    
    // Weight average
    const herdScore = (
      indicators.mediaMetions * 0.2 +
      indicators.fundingRounds * 0.3 +
      indicators.vcTweets * 0.2 +
      indicators.conferenceTopics * 0.3
    );
    
    return herdScore;
  }

  /**
   * Find contrarian angle
   */
  private async findContrarianAngle(trend: string, answers: any): Promise<string> {
    // Use Claude to find non-consensus view
    const prompt = `Given the trend "${trend}" and these insights: ${JSON.stringify(answers)},
    what is everyone missing? What's the contrarian investment thesis?`;
    
    const response = await anthropic.messages.create({
      model: 'claude-3-5-sonnet-20241022',
      max_tokens: 500,
      temperature: 0.7, // Higher temperature for creative thinking
      messages: [
        {
          role: 'user',
          content: prompt
        }
      ]
    });
    
    return response.content[0].type === 'text' ? response.content[0].text : '';
  }

  /**
   * Calculate real value beyond hype
   */
  private async calculateRealValue(
    trend: string,
    herdScore: number,
    answers: any
  ): Promise<number> {
    // Inverse correlation with herd score
    let realValue = 100 - herdScore;
    
    // Adjust based on fundamentals
    if (answers.hasStructuralGrowth) realValue += 20;
    if (answers.hasRegulatoryCatalyst) realValue += 15;
    if (answers.hasTechBreakthrough) realValue += 25;
    if (answers.hasLimitedCompetition) realValue += 20;
    
    // Penalties
    if (herdScore > 80) realValue -= 30; // Overcrowded
    if (answers.hasRegulatorRisk) realValue -= 20;
    if (answers.hasLimitedExits) realValue -= 25;
    
    return Math.max(0, Math.min(100, realValue));
  }

  /**
   * Determine market timing
   */
  private determineTiming(herdScore: number, realValue: number): TrendAnalysis['timing'] {
    if (herdScore < 30 && realValue > 70) return 'too_early';
    if (herdScore < 60 && realValue > 50) return 'right_time';
    if (herdScore > 80) return 'bubble';
    if (herdScore > 60 && realValue < 40) return 'too_late';
    return 'right_time';
  }

  /**
   * Seek answers to Socratic questions
   */
  private async seekAnswers(questions: SocraticQuestion[], context: any): Promise<any> {
    const answers: any = {};
    
    for (const q of questions) {
      // This would integrate with research tools
      answers[q.category] = {
        question: q.question,
        level: q.level,
        // Placeholder for actual research
        insight: `Analysis needed for: ${q.question}`
      };
    }
    
    return answers;
  }

  /**
   * Identify thought pattern
   */
  private identifyPattern(thought: string): string {
    const patterns = [
      { pattern: 'hype_following', keywords: ['everyone', 'trending', 'hot', 'FOMO'] },
      { pattern: 'recency_bias', keywords: ['just', 'recently', 'latest', 'new'] },
      { pattern: 'confirmation_bias', keywords: ['obviously', 'clearly', 'definitely'] },
      { pattern: 'herd_mentality', keywords: ['everyone\'s doing', 'consensus', 'popular'] },
      { pattern: 'availability_bias', keywords: ['saw', 'heard', 'read about'] }
    ];
    
    for (const p of patterns) {
      if (p.keywords.some(k => thought.toLowerCase().includes(k))) {
        return p.pattern;
      }
    }
    
    return 'general';
  }

  /**
   * Create loop breaker questions
   */
  private createLoopBreaker(pattern: string): ThoughtLoop {
    const breakers: Record<string, string[]> = {
      hype_following: [
        'What were the last 3 "hot" sectors and where are they now?',
        'Who benefits from promoting this narrative?',
        'What happens when tourists leave?'
      ],
      recency_bias: [
        'What did this space look like 5 years ago?',
        'Is this change structural or cyclical?',
        'What kills this trend?'
      ],
      confirmation_bias: [
        'What evidence contradicts this view?',
        'Who disagrees and why?',
        'What am I incentivized to believe?'
      ],
      herd_mentality: [
        'What\'s the opposite trade?',
        'Where is everyone NOT looking?',
        'What happens when the herd is right but too early?'
      ],
      availability_bias: [
        'What data am I missing?',
        'What\'s the base rate?',
        'How representative is this example?'
      ]
    };
    
    const loop: ThoughtLoop = {
      pattern,
      frequency: 1,
      breakerQuestions: breakers[pattern] || breakers.herd_mentality,
      lastOccurrence: new Date()
    };
    
    this.thoughtLoops.set(pattern, loop);
    return loop;
  }

  /**
   * Generate suggestion to break thought loop
   */
  private async generateLoopBreakingSuggestion(
    pattern: string,
    thought: string
  ): Promise<string> {
    const suggestions: Record<string, string> = {
      hype_following: 'Look for what\'s being neglected while everyone chases this trend',
      recency_bias: 'Study the historical cycles of this sector',
      confirmation_bias: 'Actively seek disconfirming evidence',
      herd_mentality: 'Find the contrarian position with equal conviction',
      availability_bias: 'Gather comprehensive data, not just memorable anecdotes'
    };
    
    return suggestions[pattern] || 'Challenge your assumptions with opposing evidence';
  }

  /**
   * Initialize common thought loops
   */
  private initializeCommonLoops(): void {
    const commonLoops = [
      'hype_following',
      'recency_bias',
      'confirmation_bias',
      'herd_mentality',
      'availability_bias'
    ];
    
    for (const pattern of commonLoops) {
      this.createLoopBreaker(pattern);
    }
  }

  /**
   * Decision tree analysis
   */
  async analyzeDecision(
    decision: string,
    options: string[]
  ): Promise<{
    bestOption: string;
    reasoning: string;
    risks: string[];
    secondOrder: string[];
  }> {
    const nodes: DecisionNode[] = [];
    
    for (const option of options) {
      const questions = this.generateSocraticQuestions(option);
      const assumptions = this.extractAssumptions(option);
      const contradictions = await this.findContradictions(option);
      
      nodes.push({
        id: `node-${Date.now()}`,
        statement: option,
        questions,
        assumptions,
        contradictions,
        score: await this.scoreOption(option, questions, assumptions, contradictions),
        timestamp: new Date()
      });
    }
    
    // Sort by score
    nodes.sort((a, b) => b.score - a.score);
    
    const bestNode = nodes[0];
    
    // Calculate second-order effects
    const secondOrder = await this.calculateSecondOrderEffects(bestNode.statement);
    
    return {
      bestOption: bestNode.statement,
      reasoning: `Highest score (${bestNode.score}) with fewest unexamined assumptions`,
      risks: bestNode.contradictions,
      secondOrder
    };
  }

  /**
   * Extract assumptions from statement
   */
  private extractAssumptions(statement: string): string[] {
    // This would use NLP, for now using heuristics
    const assumptions: string[] = [];
    
    if (statement.includes('will')) {
      assumptions.push('Future prediction assumes continuity');
    }
    if (statement.includes('everyone')) {
      assumptions.push('Assumes uniform behavior');
    }
    if (statement.includes('always') || statement.includes('never')) {
      assumptions.push('Assumes no exceptions');
    }
    
    return assumptions;
  }

  /**
   * Find contradictions
   */
  private async findContradictions(statement: string): Promise<string[]> {
    // Would search for contradictory evidence
    return [
      `Historical precedent may not apply`,
      `Market conditions could change`,
      `Regulatory environment uncertain`
    ];
  }

  /**
   * Score option based on Socratic analysis
   */
  private async scoreOption(
    option: string,
    questions: SocraticQuestion[],
    assumptions: string[],
    contradictions: string[]
  ): Promise<number> {
    let score = 50; // Base score
    
    // Penalize unexamined assumptions
    score -= assumptions.length * 5;
    
    // Penalize contradictions
    score -= contradictions.length * 3;
    
    // Bonus for depth of questioning
    score += questions.length * 2;
    
    return Math.max(0, Math.min(100, score));
  }

  /**
   * Calculate second-order effects
   */
  private async calculateSecondOrderEffects(decision: string): Promise<string[]> {
    return [
      `If ${decision}, then competitors will respond by...`,
      `This creates incentive for...`,
      `Unintended consequence could be...`,
      `This assumes stability in...`
    ];
  }

  /**
   * Generate anti-FOMO analysis
   */
  async antiFOMOAnalysis(opportunity: string): Promise<{
    FOMOScore: number;
    realityCheck: string;
    missedOpportunities: string[];
    betterAlternatives: string[];
  }> {
    const FOMOIndicators = {
      urgency: opportunity.includes('now') || opportunity.includes('quickly'),
      scarcity: opportunity.includes('limited') || opportunity.includes('exclusive'),
      social: opportunity.includes('everyone') || opportunity.includes('missing out'),
      hype: opportunity.includes('hot') || opportunity.includes('exploding')
    };
    
    const FOMOScore = Object.values(FOMOIndicators).filter(Boolean).length * 25;
    
    const realityCheck = FOMOScore > 50 ? 
      '⚠️ High FOMO detected. Step back and evaluate rationally.' :
      '✅ Low FOMO. Decision can be made objectively.';
    
    const missedOpportunities = [
      'What you miss while chasing this',
      'Opportunity cost of capital',
      'Time cost of due diligence',
      'Reputational cost if wrong'
    ];
    
    const betterAlternatives = await this.findBetterAlternatives(opportunity);
    
    return {
      FOMOScore,
      realityCheck,
      missedOpportunities,
      betterAlternatives
    };
  }

  /**
   * Find better alternatives
   */
  private async findBetterAlternatives(opportunity: string): Promise<string[]> {
    return [
      'The opposite bet (contrarian)',
      'The picks and shovels play',
      'The infrastructure enabler',
      'The second-order beneficiary',
      'The hedged position'
    ];
  }
}

// Export singleton instance
export const socraticEngine = new SocraticDecisionEngine();