import { NextRequest, NextResponse } from 'next/server';
import Anthropic from '@anthropic-ai/sdk';
import { webScraper } from '@/lib/web-scraper';
import { createClient } from '@supabase/supabase-js';

const anthropic = new Anthropic({
  apiKey: process.env.ANTHROPIC_API_KEY || process.env.CLAUDE_API_KEY || '',
});

const supabase = createClient(
  process.env.NEXT_PUBLIC_SUPABASE_URL!,
  process.env.SUPABASE_SERVICE_ROLE_KEY!
);

// Market segmentation definitions
const MARKET_SEGMENTS = {
  SME: {
    name: 'Small & Medium Enterprises',
    employees: '10-250',
    revenue: '$1M-$50M',
    characteristics: [
      'Local/regional focus',
      'Limited IT budget',
      'Need simple solutions',
      'Price sensitive',
      'Quick decision making'
    ],
    tam: 5000000000000, // $5T globally
    tools: ['Basic SaaS', 'Cloud storage', 'Accounting software', 'CRM']
  },
  MidMarket: {
    name: 'Mid-Market',
    employees: '250-1000',
    revenue: '$50M-$1B',
    characteristics: [
      'Multiple locations',
      'Dedicated IT team',
      'Complex workflows',
      'Integration needs',
      'Compliance requirements'
    ],
    tam: 3000000000000, // $3T globally
    tools: ['ERP', 'Advanced analytics', 'Custom integrations', 'Security solutions']
  },
  Enterprise: {
    name: 'Enterprise',
    employees: '1000+',
    revenue: '$1B+',
    characteristics: [
      'Global operations',
      'Large IT departments',
      'Custom requirements',
      'Long sales cycles',
      'Multiple stakeholders'
    ],
    tam: 8000000000000, // $8T globally
    tools: ['Enterprise platforms', 'AI/ML solutions', 'Infrastructure', 'Professional services']
  }
};

export async function POST(request: NextRequest) {
  try {
    const { url, imageUrl, analyzeMarketMap = false, segment } = await request.json();

    if (!url && !imageUrl) {
      return NextResponse.json({ error: 'URL or image URL is required' }, { status: 400 });
    }

    let analysis: any = {};

    // Scrape web content if URL provided
    if (url) {
      const scrapedContent = await webScraper.scrapeUrl(url);
      
      // Analyze for market segments
      const segmentAnalysis = analyzeMarketSegments(scrapedContent.content);
      
      // Use Claude to extract deeper insights
      const claudeAnalysis = await analyzeWithClaude(
        scrapedContent.content,
        scrapedContent.images,
        segment
      );
      
      analysis = {
        url,
        title: scrapedContent.title,
        marketMaps: scrapedContent.marketMaps,
        segments: segmentAnalysis,
        insights: claudeAnalysis,
        companies: extractCompaniesWithSegments(scrapedContent.content),
        opportunities: identifyOpportunities(segmentAnalysis, claudeAnalysis)
      };
    }

    // Analyze image if provided
    if (imageUrl || (analyzeMarketMap && analysis.marketMaps?.length > 0)) {
      const imageToAnalyze = imageUrl || analysis.marketMaps[0].imageUrl;
      const visionAnalysis = await analyzeImageWithVision(imageToAnalyze);
      
      analysis.visionInsights = visionAnalysis;
    }

    // Store analysis
    await storeAnalysis(analysis);

    return NextResponse.json({
      success: true,
      analysis,
      timestamp: new Date().toISOString()
    });

  } catch (error) {
    console.error('Scrape and analyze error:', error);
    return NextResponse.json(
      { error: 'Failed to scrape and analyze', details: error instanceof Error ? error.message : 'Unknown error' },
      { status: 500 }
    );
  }
}

/**
 * Analyze content for market segments (SME, Mid-Market, Enterprise)
 */
function analyzeMarketSegments(content: string): any {
  const segments: any = {
    sme: { count: 0, companies: [], opportunities: [] },
    midMarket: { count: 0, companies: [], opportunities: [] },
    enterprise: { count: 0, companies: [], opportunities: [] }
  };

  // Keywords for each segment
  const smeKeywords = ['SME', 'SMB', 'small business', 'startup', 'small company', 'local business'];
  const midMarketKeywords = ['mid-market', 'mid-size', 'medium business', 'growing company', 'scale-up'];
  const enterpriseKeywords = ['enterprise', 'fortune 500', 'large company', 'multinational', 'corporation'];

  // Count mentions and extract context
  const contentLower = content.toLowerCase();
  
  smeKeywords.forEach(keyword => {
    if (contentLower.includes(keyword)) {
      segments.sme.count++;
      // Extract surrounding context
      const context = extractContext(content, keyword);
      if (context) segments.sme.opportunities.push(context);
    }
  });

  midMarketKeywords.forEach(keyword => {
    if (contentLower.includes(keyword)) {
      segments.midMarket.count++;
      const context = extractContext(content, keyword);
      if (context) segments.midMarket.opportunities.push(context);
    }
  });

  enterpriseKeywords.forEach(keyword => {
    if (contentLower.includes(keyword)) {
      segments.enterprise.count++;
      const context = extractContext(content, keyword);
      if (context) segments.enterprise.opportunities.push(context);
    }
  });

  // Determine primary segment focus
  const primarySegment = 
    segments.enterprise.count > segments.midMarket.count && segments.enterprise.count > segments.sme.count ? 'enterprise' :
    segments.midMarket.count > segments.sme.count ? 'midMarket' : 'sme';

  segments.primary = primarySegment;
  segments.characteristics = MARKET_SEGMENTS[primarySegment === 'sme' ? 'SME' : primarySegment === 'midMarket' ? 'MidMarket' : 'Enterprise'];

  return segments;
}

/**
 * Extract context around a keyword
 */
function extractContext(content: string, keyword: string, windowSize: number = 100): string {
  const index = content.toLowerCase().indexOf(keyword.toLowerCase());
  if (index === -1) return '';
  
  const start = Math.max(0, index - windowSize);
  const end = Math.min(content.length, index + keyword.length + windowSize);
  
  return content.substring(start, end).trim();
}

/**
 * Extract companies with their market segments
 */
function extractCompaniesWithSegments(content: string): any[] {
  const companies: any[] = [];
  
  // Pattern to find companies with context
  const companyPattern = /([A-Z][a-zA-Z]+(?:Corp|Inc|Ltd|Labs|AI|Tech|Bio|Financial|Health|Data|Cloud|Robotics))\s+(?:is|are|provides|offers|targets|serves|focuses on)\s+([^.]+)/g;
  const matches = content.matchAll(companyPattern);
  
  for (const match of matches) {
    const companyName = match[1];
    const context = match[2].toLowerCase();
    
    // Determine segment from context
    let segment = 'unknown';
    if (context.includes('enterprise') || context.includes('fortune')) {
      segment = 'enterprise';
    } else if (context.includes('mid-market') || context.includes('mid-size')) {
      segment = 'midMarket';
    } else if (context.includes('sme') || context.includes('small business') || context.includes('startup')) {
      segment = 'sme';
    }
    
    companies.push({
      name: companyName,
      segment,
      context: match[2].substring(0, 100)
    });
  }
  
  return companies;
}

/**
 * Use Claude to analyze content with vision capabilities
 */
async function analyzeWithClaude(
  content: string,
  images: any[],
  targetSegment?: string
): Promise<any> {
  const prompt = `
Analyze this content for investment opportunities in the ${targetSegment || 'all'} market segment(s).

Content: ${content.substring(0, 5000)}

Please identify:
1. Market size and growth rate for each segment (SME, Mid-Market, Enterprise)
2. Key players and their positioning
3. Underserved areas or gaps
4. Investment opportunities with expected returns
5. Competitive dynamics
6. Technology trends affecting each segment

Focus on quantitative insights and specific opportunities.
`;

  try {
    const response = await anthropic.messages.create({
      model: 'claude-3-5-sonnet-20241022',
      max_tokens: 2048,
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
    console.error('Claude analysis error:', error);
    return 'Analysis failed';
  }
}

/**
 * Analyze image using vision capabilities
 */
async function analyzeImageWithVision(imageUrl: string): Promise<any> {
  try {
    // First, fetch the image
    const imageResponse = await fetch(imageUrl);
    const imageBuffer = await imageResponse.arrayBuffer();
    const base64Image = Buffer.from(imageBuffer).toString('base64');
    
    // Use Claude's vision capabilities
    const response = await anthropic.messages.create({
      model: 'claude-3-5-sonnet-20241022',
      max_tokens: 2048,
      temperature: 0,
      messages: [
        {
          role: 'user',
          content: [
            {
              type: 'text',
              text: `Analyze this market map image and extract:
1. All company names visible
2. Market categories/segments
3. Positioning of companies (leaders, challengers, niche)
4. Any TAM or growth data shown
5. Investment opportunities based on the landscape

Categorize companies by their target segment:
- SME (small business focused)
- Mid-Market (medium business focused)  
- Enterprise (large company focused)

Provide specific, actionable insights.`
            },
            {
              type: 'image',
              source: {
                type: 'base64',
                media_type: 'image/png',
                data: base64Image
              }
            }
          ]
        }
      ]
    });

    const analysis = response.content[0].type === 'text' ? response.content[0].text : '';
    
    // Parse the analysis to extract structured data
    return {
      raw: analysis,
      companies: extractCompaniesFromVisionAnalysis(analysis),
      segments: extractSegmentsFromVisionAnalysis(analysis),
      opportunities: extractOpportunitiesFromVisionAnalysis(analysis)
    };
  } catch (error) {
    console.error('Vision analysis error:', error);
    return {
      error: 'Vision analysis failed',
      details: error instanceof Error ? error.message : 'Unknown error'
    };
  }
}

/**
 * Extract companies from vision analysis
 */
function extractCompaniesFromVisionAnalysis(analysis: string): any[] {
  const companies: any[] = [];
  const lines = analysis.split('\n');
  
  for (const line of lines) {
    // Look for company names in various formats
    const companyMatch = line.match(/[-•]\s*([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)*)/);
    if (companyMatch) {
      companies.push({
        name: companyMatch[1],
        context: line
      });
    }
  }
  
  return companies;
}

/**
 * Extract segments from vision analysis
 */
function extractSegmentsFromVisionAnalysis(analysis: string): any {
  const segments: any = {
    categories: [],
    positioning: {}
  };
  
  // Extract categories
  if (analysis.includes('Categories:') || analysis.includes('Segments:')) {
    const categorySection = analysis.split(/Categories:|Segments:/)[1]?.split('\n')[0];
    if (categorySection) {
      segments.categories = categorySection.split(',').map(s => s.trim());
    }
  }
  
  return segments;
}

/**
 * Extract opportunities from vision analysis
 */
function extractOpportunitiesFromVisionAnalysis(analysis: string): string[] {
  const opportunities: string[] = [];
  const lines = analysis.split('\n');
  
  for (const line of lines) {
    if (line.toLowerCase().includes('opportunity') || 
        line.toLowerCase().includes('gap') ||
        line.toLowerCase().includes('underserved')) {
      opportunities.push(line.trim());
    }
  }
  
  return opportunities;
}

/**
 * Identify investment opportunities
 */
function identifyOpportunities(segmentAnalysis: any, claudeInsights: string): any[] {
  const opportunities: any[] = [];
  
  // SME opportunities
  if (segmentAnalysis.sme.count > 0) {
    opportunities.push({
      segment: 'SME',
      type: 'Market Entry',
      description: 'Simple, affordable solutions for small businesses',
      tam: MARKET_SEGMENTS.SME.tam,
      expectedIRR: '45-60%',
      timeHorizon: '3-5 years'
    });
  }
  
  // Mid-Market opportunities
  if (segmentAnalysis.midMarket.count > 0) {
    opportunities.push({
      segment: 'Mid-Market',
      type: 'Platform Play',
      description: 'Integration platforms for growing companies',
      tam: MARKET_SEGMENTS.MidMarket.tam,
      expectedIRR: '35-50%',
      timeHorizon: '4-6 years'
    });
  }
  
  // Enterprise opportunities
  if (segmentAnalysis.enterprise.count > 0) {
    opportunities.push({
      segment: 'Enterprise',
      type: 'Infrastructure',
      description: 'Mission-critical enterprise solutions',
      tam: MARKET_SEGMENTS.Enterprise.tam,
      expectedIRR: '25-40%',
      timeHorizon: '5-7 years'
    });
  }
  
  return opportunities;
}

/**
 * Store analysis in database
 */
async function storeAnalysis(analysis: any): Promise<void> {
  try {
    await supabase
      .from('agent_market_intelligence')
      .insert({
        data_type: 'web_analysis',
        data_point: analysis,
        source: analysis.url || 'image',
        confidence_score: 85,
        expires_at: new Date(Date.now() + 30 * 24 * 60 * 60 * 1000) // 30 days
      });
  } catch (error) {
    console.error('Error storing analysis:', error);
  }
}