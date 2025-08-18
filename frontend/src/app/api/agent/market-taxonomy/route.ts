import { NextRequest, NextResponse } from 'next/server';
import Anthropic from '@anthropic-ai/sdk';
import { createClient } from '@supabase/supabase-js';

const anthropic = new Anthropic({
  apiKey: process.env.ANTHROPIC_API_KEY || process.env.CLAUDE_API_KEY || '',
});

const supabase = createClient(
  process.env.NEXT_PUBLIC_SUPABASE_URL!,
  process.env.SUPABASE_SERVICE_ROLE_KEY!
);

// Global market taxonomy based on GDP and economic sectors
const GLOBAL_MARKET_TAXONOMY = {
  // Global GDP ~$100 Trillion (2024)
  totalGlobalGDP: 100000000000000, // $100T
  
  // Primary Economic Sectors (% of global GDP)
  primarySectors: {
    'Services': {
      gdpShare: 0.65, // 65% of global GDP
      size: 65000000000000,
      subsectors: {
        'Financial Services': { share: 0.20, size: 13000000000000 },
        'Healthcare': { share: 0.15, size: 9750000000000 },
        'Retail & E-commerce': { share: 0.12, size: 7800000000000 },
        'Professional Services': { share: 0.08, size: 5200000000000 },
        'Education': { share: 0.05, size: 3250000000000 },
        'Entertainment & Media': { share: 0.05, size: 3250000000000 }
      }
    },
    'Manufacturing': {
      gdpShare: 0.16, // 16% of global GDP
      size: 16000000000000,
      subsectors: {
        'Electronics & Technology': { share: 0.30, size: 4800000000000 },
        'Automotive': { share: 0.25, size: 4000000000000 },
        'Aerospace & Defense': { share: 0.15, size: 2400000000000 },
        'Consumer Goods': { share: 0.20, size: 3200000000000 },
        'Industrial Equipment': { share: 0.10, size: 1600000000000 }
      }
    },
    'Real Estate & Construction': {
      gdpShare: 0.13, // 13% of global GDP
      size: 13000000000000,
      subsectors: {
        'Residential Real Estate': { share: 0.50, size: 6500000000000 },
        'Commercial Real Estate': { share: 0.30, size: 3900000000000 },
        'Infrastructure': { share: 0.20, size: 2600000000000 }
      }
    },
    'Agriculture & Natural Resources': {
      gdpShare: 0.04, // 4% of global GDP
      size: 4000000000000,
      subsectors: {
        'Agriculture': { share: 0.40, size: 1600000000000 },
        'Energy': { share: 0.35, size: 1400000000000 },
        'Mining': { share: 0.25, size: 1000000000000 }
      }
    },
    'Information & Technology': {
      gdpShare: 0.02, // 2% direct (but 10%+ indirect impact)
      size: 2000000000000,
      subsectors: {
        'Software': { share: 0.40, size: 800000000000 },
        'Hardware': { share: 0.30, size: 600000000000 },
        'Telecommunications': { share: 0.30, size: 600000000000 }
      }
    }
  },
  
  // Geographic Distribution (% of global GDP)
  geographicDistribution: {
    'North America': { gdpShare: 0.28, size: 28000000000000 },
    'Europe': { gdpShare: 0.21, size: 21000000000000 },
    'Asia Pacific': { gdpShare: 0.35, size: 35000000000000 },
    'Latin America': { gdpShare: 0.07, size: 7000000000000 },
    'Middle East & Africa': { gdpShare: 0.09, size: 9000000000000 }
  },
  
  // Technology-Enabled Markets (Addressable for startups)
  techEnabledMarkets: {
    'Artificial Intelligence': { tam: 1500000000000, growthRate: 0.35 },
    'Fintech': { tam: 350000000000, growthRate: 0.25 },
    'Digital Health': { tam: 600000000000, growthRate: 0.20 },
    'E-commerce': { tam: 6000000000000, growthRate: 0.15 },
    'SaaS': { tam: 300000000000, growthRate: 0.18 },
    'Cybersecurity': { tam: 250000000000, growthRate: 0.12 },
    'Clean Energy': { tam: 2000000000000, growthRate: 0.22 },
    'Biotech': { tam: 450000000000, growthRate: 0.08 },
    'Robotics & Automation': { tam: 200000000000, growthRate: 0.28 },
    'Blockchain & Crypto': { tam: 150000000000, growthRate: 0.40 }
  }
};

async function discoverMarketSubcategories(market: string, depth: number = 3) {
  // Use Claude to discover actual market subcategories
  const prompt = `
# Market Taxonomy Analysis: ${market}

Analyze the global market for "${market}" and provide a comprehensive breakdown:

## Requirements:
1. Calculate Total Addressable Market (TAM) as % of global GDP ($100T)
2. Identify ALL major subcategories and niches
3. For each subcategory, estimate:
   - Market size (in USD)
   - Growth rate (CAGR)
   - Key players
   - Emerging opportunities
4. Go ${depth} levels deep in the taxonomy
5. Consider both B2B and B2C segments
6. Include geographic variations

## Output Format (Markdown):

### ${market} Market Overview
- **Global TAM**: $X trillion (X% of global GDP)
- **Growth Rate**: X% CAGR
- **Maturity**: [Nascent/Growing/Mature/Declining]

### Level 1 Subcategories
#### 1. [Subcategory Name]
- **Size**: $X billion
- **Growth**: X% CAGR
- **Description**: [Brief description]

##### Level 2: [Sub-subcategory]
- **Size**: $X billion
- **Key Players**: [List]
- **Opportunities**: [List]

[Continue for all subcategories...]

### Investment Opportunities
- **Underserved Segments**: [List with rationale]
- **Emerging Trends**: [List with timeline]
- **Geographic Arbitrage**: [Opportunities by region]

### Risk Factors
- **Market Risks**: [List]
- **Regulatory Risks**: [List]
- **Technology Risks**: [List]
`;

  try {
    const response = await anthropic.messages.create({
      model: 'claude-3-5-sonnet-20241022',
      max_tokens: 4096,
      temperature: 0,
      messages: [
        {
          role: 'user',
          content: prompt
        }
      ]
    });

    return response.content[0].type === 'text' ? response.content[0].text : '';
  } catch (error) {
    console.error('Error analyzing market:', error);
    return null;
  }
}

export async function POST(request: NextRequest) {
  try {
    const { market, depth = 3, includeGDP = true } = await request.json();

    if (!market) {
      return NextResponse.json({ error: 'Market parameter is required' }, { status: 400 });
    }

    // Get detailed market taxonomy from Claude
    const marketAnalysis = await discoverMarketSubcategories(market, depth);

    // Calculate position in global economy
    let marketContext = {};
    if (includeGDP) {
      // Find which primary sector this market belongs to
      const primarySector = Object.entries(GLOBAL_MARKET_TAXONOMY.primarySectors).find(([sector, data]) => {
        return Object.keys(data.subsectors).some(subsector => 
          subsector.toLowerCase().includes(market.toLowerCase()) ||
          market.toLowerCase().includes(subsector.toLowerCase())
        );
      });

      // Check if it's a tech-enabled market
      const techMarket = Object.entries(GLOBAL_MARKET_TAXONOMY.techEnabledMarkets).find(([name, data]) =>
        name.toLowerCase().includes(market.toLowerCase()) ||
        market.toLowerCase().includes(name.toLowerCase())
      );

      marketContext = {
        globalGDP: GLOBAL_MARKET_TAXONOMY.totalGlobalGDP,
        primarySector: primarySector ? {
          name: primarySector[0],
          totalSize: primarySector[1].size,
          gdpShare: primarySector[1].gdpShare
        } : null,
        techEnabled: techMarket ? {
          name: techMarket[0],
          tam: techMarket[1].tam,
          growthRate: techMarket[1].growthRate
        } : null,
        geographicOpportunities: GLOBAL_MARKET_TAXONOMY.geographicDistribution
      };
    }

    // Store in database for future reference
    const { error: dbError } = await supabase
      .from('agent_market_intelligence')
      .insert({
        data_type: 'market_taxonomy',
        sector: market,
        data_point: {
          analysis: marketAnalysis,
          context: marketContext,
          timestamp: new Date().toISOString()
        },
        source: 'claude_analysis',
        confidence_score: 85,
        expires_at: new Date(Date.now() + 30 * 24 * 60 * 60 * 1000) // 30 days
      });

    if (dbError) {
      console.error('Database error:', dbError);
    }

    return NextResponse.json({
      market,
      analysis: marketAnalysis,
      globalContext: marketContext,
      markdown: marketAnalysis, // Return markdown directly for agent
      timestamp: new Date().toISOString()
    });

  } catch (error) {
    console.error('Market taxonomy error:', error);
    return NextResponse.json(
      { 
        error: 'Failed to analyze market taxonomy',
        details: error instanceof Error ? error.message : 'Unknown error'
      },
      { status: 500 }
    );
  }
}

export async function GET(request: NextRequest) {
  try {
    // Return the complete global market taxonomy
    return NextResponse.json({
      globalTaxonomy: GLOBAL_MARKET_TAXONOMY,
      totalMarkets: Object.keys(GLOBAL_MARKET_TAXONOMY.primarySectors).length,
      totalTechMarkets: Object.keys(GLOBAL_MARKET_TAXONOMY.techEnabledMarkets).length,
      analysis: {
        largestSector: 'Services (65% of global GDP)',
        fastestGrowing: 'Blockchain & Crypto (40% CAGR)',
        biggestOpportunity: 'AI market - $1.5T TAM with 35% growth',
        emergingMarkets: 'Asia Pacific represents 35% of global GDP with highest growth'
      }
    });
  } catch (error) {
    return NextResponse.json(
      { error: 'Failed to retrieve market taxonomy' },
      { status: 500 }
    );
  }
}