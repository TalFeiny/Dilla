import { NextRequest, NextResponse } from 'next/server';
import { socraticEngine } from '@/lib/socratic-decision-engine';
import { selfLearningAgent } from '@/lib/self-learning-agent';
import Anthropic from '@anthropic-ai/sdk';

const anthropic = new Anthropic({
  apiKey: process.env.ANTHROPIC_API_KEY || process.env.CLAUDE_API_KEY || '',
});

/**
 * DEFENSE TECH & CONCENTRATED BETS ANALYSIS
 * 
 * With £300 AUM, the strategy must be:
 * 1. Concentrated bets (2-3 positions max) for meaningful returns
 * 2. But diversified thinking to avoid hype traps
 * 3. Contrarian where consensus is expensive
 * 
 * Defense Tech Reality Check:
 * - TAM: $800B globally (seems huge)
 * - BUT: Long sales cycles (2-3 years)
 * - Limited buyers (governments)
 * - High regulatory barriers
 * - Recent exits: Anduril ($8.5B), Shield AI ($2.7B)
 * - Cognify: AI defense, raised $25M Series A (early stage)
 * 
 * The Socratic Questions:
 * 1. Why NOW for defense tech? (Ukraine war - but temporary?)
 * 2. Who profits from defense fear? (Defense contractors, not startups)
 * 3. What's the exit strategy? (Who buys defense startups?)
 * 4. What if peace breaks out? (Defense budgets shrink)
 * 5. Where's the REAL opportunity? (Dual-use, not pure defense)
 */

export async function POST(request: NextRequest) {
  try {
    const { 
      query, 
      aum = 300,
      checkHype = true,
      recentExits = []
    } = await request.json();

    // Special handling for defense tech analysis
    if (query?.toLowerCase().includes('defense tech') || query?.toLowerCase().includes('cognify')) {
      const analysis = await analyzeDefenseTechWithSocraticMethod(aum, recentExits);
      return NextResponse.json(analysis);
    }

    // General Socratic analysis
    const socraticAnalysis = await socraticEngine.analyzeTrend(query);
    
    // Check for thought loops
    const loopCheck = await socraticEngine.detectAndBreakLoop(query, []);
    
    // Anti-FOMO analysis
    const fomoAnalysis = await socraticEngine.antiFOMOAnalysis(query);
    
    // Portfolio strategy with £300
    const strategy = generateConcentratedStrategy(aum, socraticAnalysis);
    
    return NextResponse.json({
      query,
      socraticAnalysis,
      loopDetected: loopCheck.isLoop,
      loopBreaker: loopCheck.breakerQuestions,
      fomoScore: fomoAnalysis.FOMOScore,
      strategy,
      recommendation: generateRecommendation(socraticAnalysis, fomoAnalysis, aum)
    });

  } catch (error) {
    console.error('Socratic analysis error:', error);
    return NextResponse.json(
      { error: 'Failed to perform Socratic analysis' },
      { status: 500 }
    );
  }
}

/**
 * Analyze Defense Tech with Socratic Method
 */
async function analyzeDefenseTechWithSocraticMethod(
  aum: number,
  recentExits: string[]
): Promise<any> {
  
  // Layer 1: Surface Analysis
  const surfaceAnalysis = {
    market: 'Defense Tech',
    globalTAM: '$800B',
    growthRate: '5-7% CAGR',
    recentExits: [
      { company: 'Anduril', valuation: '$8.5B', multiple: '20x ARR', buyer: 'Private (Founders Fund)' },
      { company: 'Shield AI', valuation: '$2.7B', multiple: '15x ARR', buyer: 'Private' },
      { company: 'Cognify', status: 'Series A', raised: '$25M', stage: 'Early' }
    ],
    hype: 'HIGH (90/100)',
    reality: 'Complex sales, limited exits'
  };

  // Layer 2: Socratic Questioning
  const socraticQuestions = {
    level1_premise: {
      question: 'Is defense tech actually a good investment?',
      answer: 'Depends on exit strategy. Government contracts = stable revenue but slow growth',
      insight: 'Long sales cycles (18-36 months) don\'t fit VC timeline'
    },
    level2_timing: {
      question: 'Why is everyone rushing into defense tech NOW?',
      answer: 'Ukraine war, China tensions, increased budgets',
      insight: 'Wars end. When Ukraine resolves, does thesis collapse?'
    },
    level3_competition: {
      question: 'What happens when every VC funds defense startups?',
      answer: 'Valuations inflate (already at 20x ARR), talent costs spike, returns compress',
      insight: 'Anduril at $8.5B needs $85B exit for 10x. Only 5 defense primes exist globally.'
    },
    level4_exits: {
      question: 'Who actually buys defense tech startups?',
      answer: 'Lockheed, Boeing, Raytheon, BAE, Northrop - that\'s it',
      insight: 'Limited buyers = weak negotiating position = lower multiples'
    },
    level5_inversion: {
      question: 'What kills the defense tech thesis?',
      answer: 'Peace, budget cuts, China détente, technology commoditization',
      insight: 'Cybersecurity survived peace because dual-use. Pure defense doesn\'t.'
    }
  };

  // Layer 3: Concentrated Bet Analysis for £300
  const concentratedStrategy = {
    problem: 'With £300, you need 100x on one bet to matter',
    defenseTechIssues: [
      'Minimum check sizes often $100K+',
      'Can\'t get allocation in hot deals',
      'By the time you can invest, it\'s overvalued'
    ],
    betterStrategy: {
      approach: 'Dual-use technology with defense option',
      examples: [
        'Drone delivery (commercial) → surveillance (defense)',
        'Satellite imagery (commercial) → intelligence (defense)',
        'AI training (commercial) → simulation (defense)'
      ],
      advantage: 'Multiple exit paths, faster growth, civilian revenue'
    }
  };

  // Layer 4: Contrarian Opportunities
  const contrarianView = {
    whileEveryoneLooksAtDefense: [
      'Peace tech is undervalued',
      'Cybersecurity for SMBs ignored',
      'Supply chain software unsexy but critical',
      'Climate tech getting cheaper to enter'
    ],
    realAlpha: {
      thesis: 'The companies SUPPLYING defense tech, not building it',
      examples: [
        'Semiconductor testing for military chips',
        'Specialized materials for aerospace',
        'Simulation software for training',
        'Secure communications infrastructure'
      ],
      why: 'Less regulated, faster sales, multiple customers'
    }
  };

  // Layer 5: Decision Framework
  const decision = {
    verdict: 'PASS on pure defense tech',
    reasoning: [
      '❌ Long sales cycles incompatible with £300 AUM growth needs',
      '❌ Limited exit options (5 buyers globally)',
      '❌ Hype score 90/100 = overvalued entry',
      '❌ Regulatory complexity = legal costs you can\'t afford',
      '❌ Customer concentration risk (1 customer = government)'
    ],
    alternative: 'INVEST in dual-use with defense optionality',
    specificPlay: {
      target: 'Early-stage dual-use AI/robotics',
      entry: 'Seed round ($1-3M valuations)',
      thesis: 'Commercial first, defense option later',
      example: 'Agricultural drones → border surveillance',
      exitPaths: [
        'Commercial acquirer (John Deere)',
        'Defense contractor (Lockheed)',
        'PE rollup',
        'IPO if massive'
      ]
    }
  };

  // Use Claude to synthesize final recommendation
  const prompt = `Given this Socratic analysis of defense tech:
${JSON.stringify({ surfaceAnalysis, socraticQuestions, concentratedStrategy, contrarianView, decision }, null, 2)}

And the fact we have only £${aum} AUM, provide a brutal, honest assessment:
1. Is defense tech hype or real opportunity?
2. What should a £${aum} fund do instead?
3. Where's the actual alpha hiding?`;

  const response = await anthropic.messages.create({
    model: 'claude-3-5-sonnet-20241022',
    max_tokens: 1000,
    temperature: 0,
    messages: [{ role: 'user', content: prompt }]
  });

  const claudeAnalysis = response.content[0].type === 'text' ? response.content[0].text : '';

  return {
    surfaceAnalysis,
    socraticQuestions,
    concentratedStrategy,
    contrarianView,
    decision,
    claudeSynthesis: claudeAnalysis,
    finalRecommendation: {
      action: 'AVOID pure defense tech',
      instead: 'Focus on dual-use technology',
      specificOpportunities: [
        'Agricultural robotics with military applications',
        'Supply chain software for defense contractors',
        'Simulation/training platforms (gaming → military)',
        'Materials science (commercial → aerospace)',
        'Cybersecurity for critical infrastructure'
      ],
      withOnly300Pounds: {
        strategy: 'Super concentrated (1-2 bets)',
        stage: 'Pre-seed or broken cap tables',
        leverage: 'Sweat equity or advisory shares',
        timeline: '2-3 years to first markup',
        requiredReturn: '100x on at least one'
      }
    }
  };
}

/**
 * Generate concentrated strategy for small AUM
 */
function generateConcentratedStrategy(
  aum: number,
  analysis: any
): any {
  const positions = aum < 1000 ? 1 : aum < 10000 ? 2 : 3;
  
  return {
    maxPositions: positions,
    positionSize: aum / positions,
    strategy: 'Extreme concentration with diversified thinking',
    approach: [
      `Only ${positions} bet(s) with £${aum}`,
      'Each must have 100x potential',
      'Avoid hype (costs premium)',
      'Find broken cap tables',
      'Pre-seed or distressed only'
    ],
    diversificationMethod: 'Diversify by thinking, concentrate by investing',
    example: 'Research 100 companies, invest in 1'
  };
}

/**
 * Generate recommendation based on analysis
 */
function generateRecommendation(
  socraticAnalysis: any,
  fomoAnalysis: any,
  aum: number
): string {
  if (socraticAnalysis.herdScore > 80) {
    return `🚨 HERD ALERT: Too late. Find the opposite trade.`;
  }
  
  if (fomoAnalysis.FOMOScore > 75) {
    return `⚠️ FOMO DETECTED: Step back. This urgency is manufactured.`;
  }
  
  if (socraticAnalysis.timing === 'bubble') {
    return `🔴 BUBBLE: Short if possible, avoid if not.`;
  }
  
  if (socraticAnalysis.realValue > 70 && socraticAnalysis.herdScore < 40) {
    return `✅ OPPORTUNITY: Early and undervalued. With £${aum}, go all-in.`;
  }
  
  return `🤔 UNCLEAR: Need more analysis. Default to no.`;
}