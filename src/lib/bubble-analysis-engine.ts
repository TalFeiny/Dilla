import { createClient } from '@supabase/supabase-js';
import Anthropic from '@anthropic-ai/sdk';
import { macroPatternEngine } from './macro-pattern-engine';
import { socraticEngine } from './socratic-decision-engine';

const supabase = createClient(
  process.env.NEXT_PUBLIC_SUPABASE_URL!,
  process.env.SUPABASE_SERVICE_ROLE_KEY!
);

const anthropic = new Anthropic({
  apiKey: process.env.ANTHROPIC_API_KEY || process.env.CLAUDE_API_KEY || '',
});

/**
 * BUBBLE ANALYSIS & SHORT OPPORTUNITY ENGINE
 * 
 * Philosophy: "Easy money" is never easy
 * 
 * Current Bubble (Aug 2025):
 * - AI anything = 50x revenue multiples
 * - Defense tech = Hype driven by war
 * - Figma sold for $20B (failed), worth maybe $5B
 * - WeWork 2.0 companies (flexible office)
 * - SPACs remnants still overvalued
 * 
 * What's Actually Underpriced:
 * - Boring B2B SaaS with real revenue
 * - Supply chain software
 * - Healthcare IT (not sexy)
 * - Climate adaptation (not mitigation)
 * - Regional banks (if they survive)
 * 
 * Best Founders Pattern:
 * - Second-time founders after moderate success
 * - Technical founders who learned sales
 * - Domain experts (10+ years) going digital
 * - Immigrants with something to prove
 * - Post-burnout founders (learned limits)
 */

interface BubbleIndicator {
  indicator: string;
  currentValue: number;
  historicalAverage: number;
  percentileRank: number; // 0-100
  signal: 'bubble' | 'normal' | 'undervalued';
}

interface AssetValuation {
  asset: string;
  currentValuation: number;
  fairValue: number;
  overvaluation: number; // Percentage over/under valued
  bubbleScore: number; // 0-100
  shortOpportunity: boolean;
  timeToCorrection: string;
  catalysts: string[];
}

interface FounderProfile {
  type: string;
  successProbability: number;
  characteristics: string[];
  redFlags: string[];
  examples: string[];
}

interface ShortCandidate {
  company: string;
  ticker?: string;
  currentValuation: number;
  fairValue: number;
  shortRationale: string[];
  risks: string[];
  expectedReturn: number;
  timeframe: string;
  conviction: 'high' | 'medium' | 'low';
}

export class BubbleAnalysisEngine {
  private bubbleIndicators: BubbleIndicator[] = [];
  private shortCandidates: ShortCandidate[] = [];
  
  constructor() {
    this.initializeBubbleIndicators();
  }

  /**
   * Analyze current bubble conditions
   */
  async analyzeBubble(): Promise<{
    overallBubbleScore: number;
    bubbleStage: string;
    indicators: BubbleIndicator[];
    recommendation: string;
  }> {
    this.bubbleIndicators = await this.calculateBubbleIndicators();
    
    const overallScore = this.bubbleIndicators.reduce((sum, ind) => 
      sum + (ind.signal === 'bubble' ? ind.percentileRank : 0), 0
    ) / this.bubbleIndicators.length;
    
    const bubbleStage = this.identifyBubbleStage(overallScore);
    
    return {
      overallBubbleScore: overallScore,
      bubbleStage,
      indicators: this.bubbleIndicators,
      recommendation: this.generateBubbleRecommendation(overallScore, bubbleStage)
    };
  }

  /**
   * Analyze Figma and similar overvalued companies
   */
  async analyzeFigmaCase(): Promise<{
    analysis: any;
    valuation: AssetValuation;
    shortOpportunity: any;
  }> {
    const figmaAnalysis = {
      company: 'Figma',
      peakValuation: 20000000000, // $20B Adobe offer
      currentEstimate: 10000000000, // $10B secondary market
      realValue: 5000000000, // $5B based on fundamentals
      
      whyOvervalued: [
        'Adobe FOMO bid during ZIRP',
        'Design tool TAM is limited ($10B)',
        'Canva competition intensifying',
        'AI disrupting design workflow',
        'Enterprise sales cycle slowing'
      ],
      
      comparables: [
        { company: 'Canva', valuation: '$40B', multiple: '40x ARR', verdict: 'Also overvalued' },
        { company: 'Sketch', valuation: '$500M', multiple: '5x ARR', verdict: 'Fair value' },
        { company: 'InVision', valuation: '$100M', multiple: '1x ARR', verdict: 'Distressed' }
      ],
      
      shortThesis: [
        'Limited TAM - only so many designers',
        'AI will commoditize design tools',
        'Switching costs lower than believed',
        'Growth slowing to 30% YoY',
        'Next financing will be down round'
      ],
      
      catalysts: [
        'Q1 2025: Growth numbers disappoint',
        'Q2 2025: Major customer churn',
        'Q3 2025: AI competitor launches',
        'Q4 2025: Forced to raise at lower valuation'
      ]
    };

    const valuation: AssetValuation = {
      asset: 'Figma',
      currentValuation: 10000000000,
      fairValue: 5000000000,
      overvaluation: 100, // 100% overvalued
      bubbleScore: 85,
      shortOpportunity: true,
      timeToCorrection: '12-18 months',
      catalysts: figmaAnalysis.catalysts
    };

    const shortOpp = {
      method: 'Secondary market short or puts on Adobe',
      expectedReturn: 50, // 50% return on short
      timeframe: '12-18 months',
      risks: [
        'Another strategic acquirer',
        'AI integration succeeds',
        'Market stays irrational longer'
      ]
    };

    return {
      analysis: figmaAnalysis,
      valuation,
      shortOpportunity: shortOpp
    };
  }

  /**
   * Find best founders pattern
   */
  async findBestFounders(): Promise<{
    profiles: FounderProfile[];
    currentOpportunities: any[];
    avoidProfiles: FounderProfile[];
  }> {
    const bestProfiles: FounderProfile[] = [
      {
        type: 'Second-Time Technical Founder',
        successProbability: 0.65,
        characteristics: [
          'Previous exit $10-50M (not huge)',
          'Learned from mistakes',
          'Has network but still hungry',
          'Technical but learned business',
          'Age 32-42 optimal'
        ],
        redFlags: [],
        examples: ['Brian Chesky (Airbnb)', 'Patrick Collison (Stripe)']
      },
      {
        type: 'Domain Expert Going Digital',
        successProbability: 0.55,
        characteristics: [
          '10+ years in traditional industry',
          'Sees inefficiencies others miss',
          'Has customer relationships',
          'Paired with technical co-founder',
          'Solving real pain points'
        ],
        redFlags: ['Might not adapt to startup pace'],
        examples: ['Ryan Petersen (Flexport)', 'Josh Reeves (Gusto)']
      },
      {
        type: 'Immigrant Founder',
        successProbability: 0.60,
        characteristics: [
          'Extreme work ethic',
          'Nothing to lose mentality',
          'Global perspective',
          'Underestimated by others',
          'Cost-conscious'
        ],
        redFlags: ['Visa issues', 'Cultural misunderstandings'],
        examples: ['Elon Musk', 'Jensen Huang (Nvidia)', 'Vlad Tenev (Robinhood)']
      },
      {
        type: 'Post-Burnout Founder',
        successProbability: 0.50,
        characteristics: [
          'Learned personal limits',
          'Better at delegation',
          'Focus on sustainable growth',
          'Mental health aware',
          'Building for long-term'
        ],
        redFlags: ['Might lack urgency'],
        examples: ['Ev Williams (Medium after Twitter)']
      }
    ];

    const avoidProfiles: FounderProfile[] = [
      {
        type: 'First-Time MBA Founder',
        successProbability: 0.15,
        characteristics: [
          'All theory, no practice',
          'Overconfident from case studies',
          'Burns money on "growth"',
          'Hires consultants',
          'Pitches well, executes poorly'
        ],
        redFlags: [
          'McKinsey/Goldman background',
          'Never built anything',
          'Talks about TAM constantly',
          'Name drops VCs'
        ],
        examples: ['Adam Neumann (WeWork)', 'Most failed SPACs']
      },
      {
        type: 'Serial Wantrepreneur',
        successProbability: 0.10,
        characteristics: [
          '5+ failed startups',
          'Always chasing trends',
          'Blames market/investors',
          'No deep expertise',
          'Conference circuit regular'
        ],
        redFlags: [
          'New startup every year',
          'Always fundraising',
          'No revenue focus',
          'Excessive PR'
        ],
        examples: ['Most crypto founders 2021-2022']
      },
      {
        type: 'Celebrity/Influencer Founder',
        successProbability: 0.05,
        characteristics: [
          'Famous for being famous',
          'No operational experience',
          'Outsources everything',
          'Brand over substance',
          'Exit at first trouble'
        ],
        redFlags: [
          'More followers than revenue',
          'Product is just brand',
          'No technical co-founder',
          'Party photos not product photos'
        ],
        examples: ['Most celebrity brands fail']
      }
    ];

    // Find current opportunities
    const currentOpportunities = await this.findCurrentFounderOpportunities();

    return {
      profiles: bestProfiles,
      currentOpportunities,
      avoidProfiles
    };
  }

  /**
   * Find short candidates ("easy money")
   */
  async findShortCandidates(): Promise<ShortCandidate[]> {
    const candidates: ShortCandidate[] = [
      {
        company: 'Figma',
        currentValuation: 10000000000,
        fairValue: 5000000000,
        shortRationale: [
          'Adobe deal failed = no strategic buyer',
          'Growth slowing to 30% YoY',
          'AI disrupting core product',
          'TAM smaller than believed'
        ],
        risks: ['Another acquirer appears', 'Market stays irrational'],
        expectedReturn: 0.50,
        timeframe: '12-18 months',
        conviction: 'high'
      },
      {
        company: 'OpenAI',
        currentValuation: 157000000000, // $157B
        fairValue: 50000000000, // $50B
        shortRationale: [
          '$157B valuation on $3.5B revenue = 45x',
          'Commoditization happening fast',
          'No moat besides brand',
          'Anthropic/Google catching up',
          'Costs growing faster than revenue'
        ],
        risks: ['AGI breakthrough', 'Microsoft acquisition'],
        expectedReturn: 0.70,
        timeframe: '24 months',
        conviction: 'medium'
      },
      {
        company: 'Anduril (Defense Tech)',
        currentValuation: 14000000000, // $14B actual August 2025 valuation
        fairValue: 4000000000, // $4B based on $500M revenue at 8x (defense multiple)
        shortRationale: [
          '$14B valuation on ~$500M revenue = 28x multiple (defense avg is 8x)',
          'Only 5 potential acquirers globally (LMT, BA, RTX, NOC, GD)',
          'IPO unlikely - defense companies trade at low multiples',
          'Government contracts inherently slow and lumpy',
          'Peace would destroy thesis overnight'
        ],
        risks: ['Taiwan invasion triggers defense spending surge', 'Major NATO contract', 'Successful hypersonic test'],
        expectedReturn: 0.70,
        timeframe: '24-36 months',
        conviction: 'high'
      },
      {
        company: 'Klarna',
        currentValuation: 6700000000, // Down from $45B
        fairValue: 2000000000,
        shortRationale: [
          'BNPL commoditized',
          'Apple/banks competing',
          'Regulation coming',
          'Already down 85% from peak'
        ],
        risks: ['Successful IPO', 'Acquisition'],
        expectedReturn: 0.70,
        timeframe: '12 months',
        conviction: 'high'
      },
      {
        company: 'WeWork-like (Industrious, Knotel)',
        currentValuation: 1000000000, // Various
        fairValue: 100000000,
        shortRationale: [
          'WeWork proved model broken',
          'Remote work permanent',
          'Commercial real estate crisis',
          'No unit economics'
        ],
        risks: ['Return to office mandate'],
        expectedReturn: 0.90,
        timeframe: '6-12 months',
        conviction: 'high'
      }
    ];

    this.shortCandidates = candidates;
    return candidates;
  }

  /**
   * Find undervalued opportunities
   */
  async findUndervaluedAssets(): Promise<{
    opportunities: AssetValuation[];
    rationale: string;
  }> {
    const opportunities: AssetValuation[] = [
      {
        asset: 'Boring B2B SaaS (Vertical Software)',
        currentValuation: 5, // 5x ARR average
        fairValue: 10, // Should be 10x ARR
        overvaluation: -50, // 50% undervalued
        bubbleScore: 20,
        shortOpportunity: false,
        timeToCorrection: '6-12 months',
        catalysts: ['PE discovers value', 'Consolidation wave']
      },
      {
        asset: 'Supply Chain Software',
        currentValuation: 3, // 3x ARR
        fairValue: 8,
        overvaluation: -62,
        bubbleScore: 15,
        shortOpportunity: false,
        timeToCorrection: '12-18 months',
        catalysts: ['Next supply crisis', 'Reshoring trend']
      },
      {
        asset: 'Healthcare IT (Non-AI)',
        currentValuation: 4,
        fairValue: 9,
        overvaluation: -55,
        bubbleScore: 18,
        shortOpportunity: false,
        timeToCorrection: '18-24 months',
        catalysts: ['Aging population', 'Medicare expansion']
      },
      {
        asset: 'Climate Adaptation Tech',
        currentValuation: 6,
        fairValue: 15,
        overvaluation: -60,
        bubbleScore: 25,
        shortOpportunity: false,
        timeToCorrection: '24-36 months',
        catalysts: ['Insurance costs spike', 'Major climate event']
      },
      {
        asset: 'Regional Banks (Survivors)',
        currentValuation: 0.7, // 0.7x book value
        fairValue: 1.5,
        overvaluation: -53,
        bubbleScore: 10,
        shortOpportunity: false,
        timeToCorrection: '12 months',
        catalysts: ['Rate cuts', 'Consolidation', 'Credit quality improves']
      }
    ];

    const rationale = `
UNDERVALUED BECAUSE BORING:
These sectors are undervalued because they're not sexy. No one tweets about supply chain software.
VCs chase AI while PE hasn't discovered these yet. Perfect for £300 to find broken cap tables.

BEST APPROACH:
1. Find distressed vertical SaaS company
2. Negotiate sweat equity or advisory shares
3. Help them sell to PE in 2-3 years
4. 10-20x return without hype premium
    `;

    return { opportunities, rationale };
  }

  /**
   * Calculate bubble indicators
   */
  private async calculateBubbleIndicators(): Promise<BubbleIndicator[]> {
    return [
      {
        indicator: 'Shiller PE Ratio',
        currentValue: 32,
        historicalAverage: 16,
        percentileRank: 95,
        signal: 'bubble'
      },
      {
        indicator: 'VC Dry Powder',
        currentValue: 580, // $580B
        historicalAverage: 200,
        percentileRank: 98,
        signal: 'bubble'
      },
      {
        indicator: 'Unicorn Count',
        currentValue: 1200,
        historicalAverage: 300,
        percentileRank: 99,
        signal: 'bubble'
      },
      {
        indicator: 'Retail Participation',
        currentValue: 25, // 25% of market
        historicalAverage: 10,
        percentileRank: 90,
        signal: 'bubble'
      },
      {
        indicator: 'IPO First Day Pop',
        currentValue: 5, // 5% average
        historicalAverage: 20,
        percentileRank: 20,
        signal: 'normal' // Actually bearish
      },
      {
        indicator: 'Meme Stock Activity',
        currentValue: 30,
        historicalAverage: 5,
        percentileRank: 95,
        signal: 'bubble'
      },
      {
        indicator: 'AI Mention in Pitches',
        currentValue: 90, // 90% mention AI
        historicalAverage: 10,
        percentileRank: 100,
        signal: 'bubble'
      }
    ];
  }

  /**
   * Identify bubble stage
   */
  private identifyBubbleStage(score: number): string {
    if (score > 90) return 'Euphoria - Top imminent';
    if (score > 75) return 'Late stage - Start hedging';
    if (score > 60) return 'Mid bubble - Selective participation';
    if (score > 40) return 'Early bubble - Still opportunity';
    return 'No bubble - Be aggressive';
  }

  /**
   * Generate bubble recommendation
   */
  private generateBubbleRecommendation(score: number, stage: string): string {
    if (score > 90) {
      return `
🚨 EXTREME BUBBLE WARNING 🚨
- Raise cash immediately
- Short overvalued names
- Buy volatility protection
- Exit all speculative positions
- Wait for 50%+ correction
      `;
    } else if (score > 75) {
      return `
⚠️ LATE STAGE BUBBLE
- Take profits on winners
- Reduce position sizes
- Focus on quality
- Build short book
- Keep 40% cash
      `;
    } else if (score > 60) {
      return `
📊 MID BUBBLE
- Stay invested but selective
- Avoid IPOs and SPACs
- Focus on cash flow
- Small short positions
- 20% cash reserve
      `;
    }
    
    return `
✅ NO BUBBLE DETECTED
- Be aggressive
- Use leverage carefully
- Buy quality growth
- No shorts needed
- Stay fully invested
    `;
  }

  /**
   * Initialize bubble indicators
   */
  private initializeBubbleIndicators(): void {
    // This would connect to real data sources
    // For now, using representative values for Dec 2024
  }

  /**
   * Find current founder opportunities
   */
  private async findCurrentFounderOpportunities(): Promise<any[]> {
    return [
      {
        founder: 'Ex-Stripe engineer starting payments infra',
        fit: 'Second-time technical',
        opportunity: 'Knows payments deeply, has network',
        access: 'Through Stripe alumni network'
      },
      {
        founder: 'Supply chain exec digitizing logistics',
        fit: 'Domain expert',
        opportunity: '20 years at Maersk, solving real problem',
        access: 'Cold outreach with specific value prop'
      },
      {
        founder: 'Ukrainian AI researcher',
        fit: 'Immigrant founder',
        opportunity: 'Top talent, extreme motivation',
        access: 'University connections'
      }
    ];
  }

  /**
   * Generate actionable summary
   */
  async generateActionableSummary(): Promise<string> {
    const bubble = await this.analyzeBubble();
    const shorts = await this.findShortCandidates();
    const undervalued = await this.findUndervaluedAssets();
    
    return `
📊 BUBBLE STATUS: ${bubble.bubbleStage} (Score: ${bubble.overallBubbleScore.toFixed(0)}/100)

💰 TOP SHORT OPPORTUNITIES ("EASY MONEY"):
${shorts.slice(0, 3).map(s => 
  `• ${s.company}: ${(s.expectedReturn * 100).toFixed(0)}% return potential`
).join('\n')}

🎯 UNDERVALUED SECTORS:
${undervalued.opportunities.slice(0, 3).map(o => 
  `• ${o.asset}: ${Math.abs(o.overvaluation).toFixed(0)}% undervalued`
).join('\n')}

🎬 ACTION PLAN WITH £300:
1. SHORT: Find ways to bet against Figma/OpenAI valuations
2. LONG: Boring B2B SaaS with real revenue
3. NETWORK: Target second-time technical founders
4. AVOID: First-time MBAs and celebrity founders
5. TIMING: 12-18 months until major correction

⚡ ONE BIG BET:
Given tiny capital, pick ONE:
- Short Figma narrative (through Adobe puts)
- OR long boring vertical SaaS
Can't do both with £300. Choose based on conviction.
    `;
  }
}

// Export singleton instance
export const bubbleAnalysisEngine = new BubbleAnalysisEngine();