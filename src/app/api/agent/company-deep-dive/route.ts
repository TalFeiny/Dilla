import { NextRequest, NextResponse } from 'next/server';
import Anthropic from '@anthropic-ai/sdk';

const anthropic = new Anthropic({
  apiKey: process.env.CLAUDE_API_KEY!,
});

// Step 1: Find company website
async function findCompanyWebsite(companyName: string): Promise<string | null> {
  try {
    // Search for company website
    const response = await fetch('https://api.tavily.com/search', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        api_key: process.env.TAVILY_API_KEY,
        query: `${companyName} official website`,
        max_results: 5,
        search_depth: 'basic'
      })
    });
    
    if (response.ok) {
      const data = await response.json();
      
      // Look for the official website
      for (const result of data.results || []) {
        const url = result.url.toLowerCase();
        const title = result.title?.toLowerCase() || '';
        
        // Check if this looks like the company's official site
        if (
          url.includes(companyName.toLowerCase().replace(/\s+/g, '')) ||
          title.includes('official') ||
          title.includes('home') ||
          (!url.includes('wikipedia') && 
           !url.includes('crunchbase') && 
           !url.includes('linkedin') &&
           !url.includes('facebook') &&
           !url.includes('twitter'))
        ) {
          // Extract base domain
          const urlObj = new URL(result.url);
          return urlObj.origin;
        }
      }
    }
  } catch (error) {
    console.error('Error finding company website:', error);
  }
  
  return null;
}

// Step 2: Scrape company pages
async function scrapeCompanyPages(baseUrl: string, companyName: string) {
  const pagesToScrape = [
    { path: '', name: 'Homepage' },
    { path: '/about', name: 'About' },
    { path: '/about-us', name: 'About Us' },
    { path: '/team', name: 'Team' },
    { path: '/leadership', name: 'Leadership' },
    { path: '/products', name: 'Products' },
    { path: '/services', name: 'Services' },
    { path: '/solutions', name: 'Solutions' },
    { path: '/customers', name: 'Customers' },
    { path: '/investors', name: 'Investors' },
    { path: '/press', name: 'Press' },
    { path: '/news', name: 'News' },
    { path: '/careers', name: 'Careers' },
    { path: '/contact', name: 'Contact' }
  ];
  
  const scrapedData: any[] = [];
  
  for (const page of pagesToScrape) {
    try {
      const url = baseUrl + page.path;
      console.log(`Scraping ${page.name}: ${url}`);
      
      // Use WebFetch-like API to scrape
      const response = await fetch(`${process.env.NEXT_PUBLIC_APP_URL || 'http://localhost:3001'}/api/agent/scrape-and-analyze`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          url,
          prompt: `Extract key information about ${companyName} from this ${page.name} page. Focus on:
            - Company description and mission
            - Products and services offered
            - Target market and customers
            - Team members and leadership
            - Funding and investor information
            - Company metrics (revenue, growth, employees)
            - Recent news and achievements
            - Technology stack and approach
            - Business model
            - Contact information`
        })
      });
      
      if (response.ok) {
        const data = await response.json();
        if (data.analysis) {
          scrapedData.push({
            page: page.name,
            url,
            content: data.analysis
          });
        }
      }
    } catch (error) {
      console.log(`Could not scrape ${page.name}`);
    }
  }
  
  return scrapedData;
}

// Step 3: Get supplementary news data
async function getNewsData(companyName: string) {
  try {
    const response = await fetch('https://api.tavily.com/search', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        api_key: process.env.TAVILY_API_KEY,
        query: `${companyName} funding revenue valuation metrics`,
        max_results: 5,
        search_depth: 'advanced',
        include_domains: [
          'crunchbase.com',
          'techcrunch.com',
          'reuters.com',
          'bloomberg.com',
          'forbes.com'
        ]
      })
    });
    
    if (response.ok) {
      return await response.json();
    }
  } catch (error) {
    console.error('Error getting news data:', error);
  }
  
  return null;
}

// Step 4: Analyze for loan covenant
async function analyzeLoanCovenant(companyData: any) {
  const prompt = `Based on the following information about ${companyData.companyName}, provide a comprehensive loan covenant analysis:

## Company Website Data:
${companyData.websiteData.map((p: any) => `
### ${p.page}
${p.content}
`).join('\n')}

## Additional Market Data:
${companyData.newsData ? JSON.stringify(companyData.newsData.results, null, 2) : 'No additional data'}

Please analyze and provide:

1. **Financial Health Assessment**
   - Revenue estimates and growth trajectory
   - Burn rate and runway estimates
   - Unit economics analysis
   - Cash flow patterns

2. **Covenant Compliance Risk**
   - Debt service coverage ratio (DSCR) estimate
   - Working capital requirements
   - Asset coverage analysis
   - Revenue/EBITDA covenants feasibility

3. **Business Risk Factors**
   - Market position and competition
   - Customer concentration risk
   - Technology/product risk
   - Regulatory compliance risk

4. **Loan Structure Recommendations**
   - Suggested covenant thresholds
   - Monitoring requirements
   - Reporting frequency
   - Early warning triggers

5. **Collateral Assessment**
   - Intellectual property value
   - Customer contracts value
   - Physical assets
   - Account receivables quality

Format as spreadsheet commands using grid.write() syntax.`;

  const response = await anthropic.messages.create({
    model: 'claude-3-5-sonnet-20241022',
    max_tokens: 4000,
    temperature: 0,
    messages: [
      {
        role: 'user',
        content: prompt
      }
    ],
    system: `You are a credit analyst preparing loan covenant analysis. 
    Output only grid.write() commands to populate a spreadsheet.
    Include formulas where appropriate.
    Make the analysis professional and comprehensive.`
  });

  return response.content[0].type === 'text' ? response.content[0].text : '';
}

export async function POST(request: NextRequest) {
  try {
    const { companyName } = await request.json();
    
    if (!companyName) {
      return NextResponse.json(
        { error: 'Company name required' },
        { status: 400 }
      );
    }
    
    console.log(`Starting deep dive analysis for ${companyName}`);
    
    // Step 1: Find company website
    const websiteUrl = await findCompanyWebsite(companyName);
    console.log(`Found website: ${websiteUrl}`);
    
    if (!websiteUrl) {
      return NextResponse.json({
        error: `Could not find website for ${companyName}. Please provide the company URL.`
      }, { status: 404 });
    }
    
    // Step 2: Scrape company pages
    const websiteData = await scrapeCompanyPages(websiteUrl, companyName);
    console.log(`Scraped ${websiteData.length} pages`);
    
    // Step 3: Get supplementary news
    const newsData = await getNewsData(companyName);
    
    // Step 4: Analyze for loan covenant
    const analysis = await analyzeLoanCovenant({
      companyName,
      websiteUrl,
      websiteData,
      newsData
    });
    
    // Parse commands from analysis
    const commands = analysis.trim().split('\n').filter(cmd => cmd.trim());
    
    return NextResponse.json({
      success: true,
      companyName,
      websiteUrl,
      pagesScraped: websiteData.length,
      commands,
      raw: analysis
    });
    
  } catch (error) {
    console.error('Company deep dive error:', error);
    return NextResponse.json(
      { error: 'Failed to analyze company' },
      { status: 500 }
    );
  }
}