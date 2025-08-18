import Anthropic from '@anthropic-ai/sdk';
import { createClient } from '@supabase/supabase-js';
import { webScraper } from './web-scraper';
import FirecrawlApp from '@mendable/firecrawl-js';

const anthropic = new Anthropic({
  apiKey: process.env.ANTHROPIC_API_KEY || process.env.CLAUDE_API_KEY || '',
});

const supabase = createClient(
  process.env.NEXT_PUBLIC_SUPABASE_URL!,
  process.env.SUPABASE_SERVICE_ROLE_KEY!
);

// APIs for web search and scraping
const TAVILY_API_KEY = process.env.TAVILY_API_KEY || '';
const FIRECRAWL_API_KEY = process.env.FIRECRAWL_API_KEY || '';

/**
 * Company CIM Scraper - Builds CIM-like profiles from company websites
 */
export class CompanyCIMScraper {
  private firecrawl: FirecrawlApp | null = null;
  
  constructor() {
    if (FIRECRAWL_API_KEY) {
      this.firecrawl = new FirecrawlApp({ apiKey: FIRECRAWL_API_KEY });
    }
  }
  
  /**
   * Main entry point - scrape company website and build CIM
   */
  async scrapeCompanyForCIM(companyName: string, companyUrl?: string): Promise<CompanyCIM> {
    console.log(`Building CIM for ${companyName}...`);
    
    // Step 1: Find company website if not provided
    const websiteUrl = companyUrl || await this.findCompanyWebsite(companyName);
    
    // Step 2: Use Tavily for market research and news
    const searchResults = await this.searchCompanyInfoWithTavily(companyName);
    
    // Step 3: Use Firecrawl for deep website scraping (with error handling)
    let websiteData: any = {};
    if (this.firecrawl && FIRECRAWL_API_KEY && !websiteUrl.includes('twitter.com') && !websiteUrl.includes('x.com')) {
      console.log(`🔥 Using Firecrawl to deep-scrape ${websiteUrl}...`);
      try {
        websiteData = await this.scrapeWithFirecrawl(websiteUrl);
      } catch (error) {
        console.error('Firecrawl failed, continuing with Tavily data only:', error);
        websiteData = { content: '', pages: [] };
      }
    } else {
      console.log(`Using basic scraping for ${websiteUrl}...`);
      websiteData = await this.scrapeCompanyWebsite(websiteUrl);
    }
    
    // Step 4: Extract structured data using Claude
    const structuredData = await this.extractStructuredData(
      companyName,
      websiteData,
      searchResults
    );
    
    // Step 5: Apply RL corrections if available
    const correctedData = await this.applyRLCorrections(companyName, structuredData);
    
    // Step 6: Build CIM structure
    const cim = this.buildCIM(companyName, websiteUrl, correctedData);
    
    // Step 7: Store in database
    await this.storeCIM(cim);
    
    return cim;
  }
  
  /**
   * Deep scrape with Firecrawl
   */
  private async scrapeWithFirecrawl(websiteUrl: string): Promise<any> {
    if (!this.firecrawl) {
      return { content: '', pages: [] };
    }
    
    try {
      // Scrape main page
      const mainPage = await this.firecrawl.scrapeUrl(websiteUrl, {
        formats: ['markdown', 'html'],
        includeTags: ['h1', 'h2', 'h3', 'p', 'span', 'div', 'li', 'a'],
        waitFor: 3000,
        onlyMainContent: true
      });
      
      const websiteData = {
        mainContent: mainPage.markdown || mainPage.content || '',
        metadata: mainPage.metadata,
        links: mainPage.links,
        pages: []
      };
      
      // Crawl important subpages for CIM
      const cimPages = [
        '/about', '/company', '/team', '/leadership',
        '/investors', '/funding', '/press',
        '/products', '/solutions', '/platform',
        '/customers', '/case-studies',
        '/pricing', '/plans'
      ];
      
      for (const path of cimPages) {
        try {
          const url = new URL(path, websiteUrl).toString();
          console.log(`🔥 Crawling ${path}...`);
          
          const page = await this.firecrawl.scrapeUrl(url, {
            formats: ['markdown'],
            waitFor: 2000,
            onlyMainContent: true
          });
          
          if (page.markdown) {
            websiteData.pages.push({
              path,
              content: page.markdown,
              title: page.metadata?.title
            });
          }
        } catch (error) {
          // Page doesn't exist, continue
        }
      }
      
      console.log(`🔥 Firecrawl scraped ${websiteData.pages.length} pages`);
      return websiteData;
      
    } catch (error) {
      console.error('Firecrawl error:', error);
      return { content: '', pages: [] };
    }
  }
  
  /**
   * Search with Tavily for market info and news
   */
  private async searchCompanyInfoWithTavily(companyName: string): Promise<any> {
    const results: any = {
      news: [],
      funding: [],
      market: [],
      competitors: []
    };
    
    if (!TAVILY_API_KEY) {
      return results;
    }
    
    try {
      // Search for latest news and funding
      const newsResponse = await fetch('https://api.tavily.com/search', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          api_key: TAVILY_API_KEY,
          query: `${companyName} latest funding news announcement ${new Date().getFullYear()}`,
          search_depth: 'advanced',
          max_results: 10
        })
      });
      
      if (newsResponse.ok) {
        const data = await newsResponse.json();
        results.news = data.results || [];
      }
      
      // Search for market and competitors
      const marketResponse = await fetch('https://api.tavily.com/search', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          api_key: TAVILY_API_KEY,
          query: `${companyName} competitors market share industry analysis`,
          search_depth: 'basic',
          max_results: 5
        })
      });
      
      if (marketResponse.ok) {
        const data = await marketResponse.json();
        results.market = data.results || [];
      }
      
    } catch (error) {
      console.error('Tavily search error:', error);
    }
    
    return results;
  }
  
  /**
   * Find company website using web search
   */
  private async findCompanyWebsite(companyName: string): Promise<string> {
    // First check if we have it in the database
    const { data: dbCompany } = await supabase
      .from('companies')
      .select('website_url')
      .ilike('name', `%${companyName}%`)
      .limit(1)
      .single();
    
    if (dbCompany?.website_url) {
      return dbCompany.website_url;
    }
    
    try {
      const response = await fetch('https://api.tavily.com/search', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          api_key: TAVILY_API_KEY,
          query: `${companyName} official website homepage company`,
          max_results: 10,
          search_depth: 'basic',
        }),
      });
      
      const data = await response.json();
      
      // Social media and sites that block scraping
      const blockedDomains = [
        'twitter.com', 'x.com', 'facebook.com', 'instagram.com', 
        'linkedin.com', 'reddit.com', 'youtube.com', 'tiktok.com',
        'pinterest.com', 'snapchat.com', 'discord.com', 'telegram.org',
        'wikipedia.org', 'medium.com', 'substack.com'
      ];
      
      // Find the most likely official website
      for (const result of data.results || []) {
        const url = result.url.toLowerCase();
        const title = result.title.toLowerCase();
        
        // Skip social media and blocked sites
        if (blockedDomains.some(domain => url.includes(domain))) {
          continue;
        }
        
        // Look for official indicators
        if (title.includes(companyName.toLowerCase()) && 
            (title.includes('official') || title.includes('home') || 
             url.includes(companyName.toLowerCase().replace(/\s+/g, '')))) {
          return result.url;
        }
      }
      
      // Try to find any non-social media URL
      for (const result of data.results || []) {
        const url = result.url.toLowerCase();
        if (!blockedDomains.some(domain => url.includes(domain))) {
          return result.url;
        }
      }
      
      // Fallback to constructing URL
      return `https://www.${companyName.toLowerCase().replace(/\s+/g, '')}.com`;
    } catch (error) {
      console.error('Error finding company website:', error);
      return `https://www.${companyName.toLowerCase().replace(/\s+/g, '')}.com`;
    }
  }
  
  /**
   * Check if search results are valid
   */
  private hasValidSearchResults(searchResults: any): boolean {
    // Check if we have meaningful data in any category
    let hasData = false;
    
    for (const category of Object.keys(searchResults)) {
      const result = searchResults[category];
      if (result && !result.error && result.answer && result.answer !== 'No results found') {
        hasData = true;
        break;
      }
    }
    
    return hasData;
  }
  
  /**
   * Alternative search strategies when initial search fails
   */
  private async alternativeSearchStrategies(companyName: string): Promise<any> {
    const results: any = {};
    
    // Strategy 1: Try different name variations
    const nameVariations = [
      companyName,
      companyName.replace(/\s+Inc\.?$/i, ''),
      companyName.replace(/\s+Corp\.?$/i, ''),
      companyName.replace(/\s+LLC$/i, ''),
      companyName.replace(/\s+Ltd\.?$/i, ''),
      companyName + ' startup',
      companyName + ' company'
    ];
    
    for (const variation of nameVariations) {
      if (variation !== companyName) {
        console.log(`Trying variation: ${variation}`);
        const searchResult = await this.singleSearch(
          `${variation} company overview business`,
          'alternative_overview'
        );
        if (searchResult && searchResult.answer) {
          results.overview = searchResult;
          break;
        }
      }
    }
    
    // Strategy 2: Use industry/sector specific searches
    const industrySearches = [
      `${companyName} technology startup`,
      `${companyName} SaaS platform`,
      `${companyName} AI company`,
      `${companyName} fintech`,
      `${companyName} healthcare`,
      `${companyName} enterprise software`
    ];
    
    for (const search of industrySearches) {
      const result = await this.singleSearch(search, 'industry_search');
      if (result && result.answer && result.answer !== 'No results found') {
        results.industry = result;
        break;
      }
    }
    
    // Strategy 3: Search on specific platforms
    const platformSearches = [
      { query: `site:crunchbase.com ${companyName}`, platform: 'crunchbase' },
      { query: `site:linkedin.com/company ${companyName}`, platform: 'linkedin' },
      { query: `site:pitchbook.com ${companyName}`, platform: 'pitchbook' },
      { query: `site:techcrunch.com ${companyName}`, platform: 'techcrunch' }
    ];
    
    for (const { query, platform } of platformSearches) {
      const result = await this.singleSearch(query, platform);
      if (result && result.answer) {
        results[platform] = result;
      }
    }
    
    return results;
  }
  
  /**
   * Single search helper
   */
  private async singleSearch(query: string, category: string): Promise<any> {
    try {
      const response = await fetch('https://api.tavily.com/search', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          api_key: TAVILY_API_KEY,
          query: query,
          max_results: 5,
          search_depth: 'basic',
          include_answer: true,
        }),
      });
      
      if (response.ok) {
        const data = await response.json();
        return {
          answer: data.answer,
          results: data.results,
          category: category
        };
      }
    } catch (error) {
      console.error(`Search failed for ${query}:`, error);
    }
    return null;
  }
  
  /**
   * Apply RL corrections based on previous feedback
   */
  private async applyRLCorrections(companyName: string, data: any): Promise<any> {
    try {
      // Fetch relevant corrections from the RL system
      const baseUrl = process.env.NEXT_PUBLIC_APP_URL || 'http://localhost:3001';
      const response = await fetch(`${baseUrl}/api/agent/corrections?company=${encodeURIComponent(companyName)}&modelType=CIM`);
      
      if (!response.ok) {
        return data; // Return original data if no corrections available
      }
      
      const corrections = await response.json();
      const correctedData = { ...data };
      
      // Apply learning patterns
      if (corrections.learningPatterns && corrections.learningPatterns.length > 0) {
        for (const pattern of corrections.learningPatterns) {
          if (pattern.confidence > 0.7) {
            // Apply high-confidence corrections
            switch (pattern.pattern_type) {
              case 'revenue':
                if (pattern.specifics?.correctValue && correctedData.traction) {
                  correctedData.traction.revenue = pattern.specifics.correctValue;
                  console.log(`Applied RL correction: Revenue set to ${pattern.specifics.correctValue}`);
                }
                break;
              
              case 'growth_rate':
                if (pattern.specifics?.targetRate && correctedData.traction) {
                  correctedData.traction.growth_rate = pattern.specifics.targetRate;
                  console.log(`Applied RL correction: Growth rate set to ${pattern.specifics.targetRate}`);
                }
                break;
              
              case 'valuation_multiple':
                if (pattern.specifics?.correctMultiple && correctedData.funding) {
                  const revenue = correctedData.traction?.revenue || correctedData.traction?.arr;
                  if (revenue && typeof revenue === 'number') {
                    correctedData.funding.last_valuation = revenue * pattern.specifics.correctMultiple;
                    console.log(`Applied RL correction: Valuation = ${revenue} * ${pattern.specifics.correctMultiple}`);
                  }
                }
                break;
            }
          }
        }
      }
      
      // Apply specific corrections for this company
      if (corrections.corrections && Object.keys(corrections.corrections).length > 0) {
        console.log(`Found ${Object.keys(corrections.corrections).length} correction categories for ${companyName}`);
        
        // Apply the most recent corrections
        for (const [type, correctionList] of Object.entries(corrections.corrections)) {
          if (Array.isArray(correctionList) && correctionList.length > 0) {
            const latestCorrection = correctionList[0]; // Most recent
            console.log(`Applying ${type} correction: ${latestCorrection.text}`);
          }
        }
      }
      
      return correctedData;
      
    } catch (error) {
      console.error('Error applying RL corrections:', error);
      return data; // Return original data on error
    }
  }
  
  /**
   * Search for company information across multiple sources with fallbacks
   */
  private async searchCompanyInfoWithFallbacks(companyName: string): Promise<any> {
    // Original searchCompanyInfo logic, renamed
    return this.searchCompanyInfo(companyName);
  }
  
  /**
   * Search for company information across multiple sources
   */
  private async searchCompanyInfo(companyName: string): Promise<any> {
    const searches = [
      // Company overview
      {
        query: `${companyName} company overview business description products services`,
        category: 'overview'
      },
      // Financial information
      {
        query: `${companyName} revenue funding valuation financial metrics ARR growth`,
        category: 'financial'
      },
      // Team and leadership
      {
        query: `${companyName} CEO founder executive team leadership board`,
        category: 'team'
      },
      // Market and competition
      {
        query: `${companyName} market size TAM competitors industry analysis`,
        category: 'market'
      },
      // News and traction
      {
        query: `${companyName} latest news funding round customer wins partnerships`,
        category: 'news'
      }
    ];
    
    const results: any = {};
    
    for (const search of searches) {
      try {
        const response = await fetch('https://api.tavily.com/search', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            api_key: TAVILY_API_KEY,
            query: search.query,
            max_results: 10,
            search_depth: 'advanced',
            include_answer: true,
            include_raw_content: true,
          }),
        });
        
        const data = await response.json();
        results[search.category] = {
          answer: data.answer,
          results: data.results,
          raw_content: data.results?.map((r: any) => r.raw_content).join('\n\n')
        };
      } catch (error) {
        console.error(`Error searching ${search.category}:`, error);
        results[search.category] = { error: true };
      }
    }
    
    return results;
  }
  
  /**
   * Scrape key pages from company website
   */
  private async scrapeCompanyWebsite(websiteUrl: string): Promise<any> {
    const scrapedData: any = {};
    
    // First, scrape the homepage to find actual links
    try {
      console.log(`Scraping homepage: ${websiteUrl}`);
      const homepageData = await webScraper.scrapeUrl(websiteUrl);
      scrapedData.homepage = {
        content: homepageData.content,
        title: homepageData.title,
        metadata: homepageData.metadata
      };
      
      // Extract actual navigation links from the homepage
      const navigationLinks = this.extractNavigationLinks(homepageData.content, websiteUrl);
      console.log(`Found ${navigationLinks.length} navigation links`);
      
      // Common page patterns to look for
      const importantPages = [
        { patterns: ['/about', '/company', '/who-we-are', '/story'], name: 'about' },
        { patterns: ['/team', '/leadership', '/people', '/founders'], name: 'team' },
        { patterns: ['/product', '/solutions', '/services', '/what-we-do'], name: 'products' },
        { patterns: ['/pricing', '/plans', '/cost'], name: 'pricing' },
        { patterns: ['/customers', '/clients', '/case-studies'], name: 'customers' },
        { patterns: ['/investors', '/funding', '/press'], name: 'investors' },
        { patterns: ['/careers', '/jobs', '/work-with-us'], name: 'careers' },
        { patterns: ['/blog', '/news', '/updates'], name: 'blog' },
        { patterns: ['/contact', '/get-in-touch'], name: 'contact' }
      ];
      
      // Scrape important pages found in navigation
      for (const pageType of importantPages) {
        const foundLink = navigationLinks.find(link => 
          pageType.patterns.some(pattern => link.toLowerCase().includes(pattern))
        );
        
        if (foundLink) {
          try {
            const fullUrl = new URL(foundLink, websiteUrl).toString();
            console.log(`Scraping ${pageType.name}: ${fullUrl}`);
            const pageData = await webScraper.scrapeUrl(fullUrl);
            scrapedData[pageType.name] = {
              url: fullUrl,
              content: pageData.content,
              title: pageData.title
            };
          } catch (error) {
            console.log(`Could not scrape ${pageType.name} page: ${error}`);
          }
        }
      }
      
      // If we didn't find enough pages, try common URL patterns
      if (Object.keys(scrapedData).length < 3) {
        console.log('Trying common URL patterns...');
        const commonPaths = ['/about', '/team', '/products', '/pricing'];
        
        for (const path of commonPaths) {
          if (!scrapedData[path.substring(1)]) {
            try {
              const url = new URL(path, websiteUrl).toString();
              const pageData = await webScraper.scrapeUrl(url);
              scrapedData[path.substring(1)] = {
                url,
                content: pageData.content,
                title: pageData.title
              };
              console.log(`Successfully scraped ${path}`);
            } catch (error) {
              // Page doesn't exist at this path
            }
          }
        }
      }
      
    } catch (error) {
      console.error(`Error scraping website ${websiteUrl}:`, error);
      // Return empty data if website can't be scraped
      return scrapedData;
    }
    
    console.log(`Total pages scraped: ${Object.keys(scrapedData).length}`);
    return scrapedData;
  }
  
  /**
   * Extract navigation links from homepage content
   */
  private extractNavigationLinks(content: string, baseUrl: string): string[] {
    const links = new Set<string>();
    
    // Look for common navigation patterns in the content
    const linkPatterns = [
      /href="([^"]+)"/gi,
      /href='([^']+)'/gi
    ];
    
    for (const pattern of linkPatterns) {
      const matches = content.matchAll(pattern);
      for (const match of matches) {
        const link = match[1];
        // Only keep internal links
        if (link.startsWith('/') || link.startsWith(baseUrl)) {
          links.add(link);
        }
      }
    }
    
    return Array.from(links);
  }
  
  /**
   * Extract text content from HTML
   */
  private extractTextFromHTML(html: string): string {
    // Remove scripts and styles
    let text = html.replace(/<script\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/script>/gi, '');
    text = text.replace(/<style\b[^<]*(?:(?!<\/style>)<[^<]*)*<\/style>/gi, '');
    
    // Extract text from important tags
    const importantTags = ['h1', 'h2', 'h3', 'p', 'li', 'span', 'div'];
    let extractedText = '';
    
    for (const tag of importantTags) {
      const pattern = new RegExp(`<${tag}[^>]*>([^<]+)<\/${tag}>`, 'gi');
      const matches = text.matchAll(pattern);
      for (const match of matches) {
        extractedText += match[1].trim() + ' ';
      }
    }
    
    // Clean up
    extractedText = extractedText.replace(/\s+/g, ' ').trim();
    
    return extractedText.substring(0, 10000); // Limit to 10k chars
  }
  
  /**
   * Extract structured data using Claude
   */
  private async extractStructuredData(
    companyName: string,
    websiteData: any,
    searchResults: any
  ): Promise<any> {
    const prompt = `
You are analyzing data about ${companyName} to create a professional CIM (Confidential Information Memorandum).

Website Data:
${JSON.stringify(websiteData, null, 2).substring(0, 5000)}

Search Results:
${JSON.stringify(searchResults, null, 2).substring(0, 10000)}

Extract the following information in a structured format:

1. COMPANY OVERVIEW
- Company name
- Founded year
- Headquarters location
- Number of employees
- Company description (2-3 sentences)
- Mission/Vision
- Core values

2. PRODUCTS & SERVICES
- Main products/services (list with descriptions)
- Key features and differentiators
- Technology stack
- Pricing model
- Target customer profile

3. MARKET OPPORTUNITY
- Total Addressable Market (TAM) - provide specific number if available
- Serviceable Addressable Market (SAM)
- Market growth rate
- Key market drivers
- Industry trends

4. BUSINESS MODEL
- Revenue model
- Pricing strategy
- Customer acquisition strategy
- Unit economics (if available)
- Gross margins

5. TRACTION & METRICS
- Annual Revenue or ARR (provide specific number if available)
- Growth rate
- Number of customers
- Key customers/logos
- NRR/retention metrics
- Other KPIs

6. COMPETITIVE LANDSCAPE
- Main competitors (list 3-5)
- Competitive advantages
- Market positioning
- Differentiation

7. TEAM
- CEO/Founder (name and background)
- Key executives (names and roles)
- Board members
- Advisors
- Team size and composition

8. FUNDING & FINANCIALS
- Total funding raised
- Last round details (amount, date, valuation if available)
- Key investors
- Use of funds
- Burn rate (if available)

9. GROWTH STRATEGY
- Expansion plans
- Product roadmap
- Go-to-market strategy
- Partnership strategy

10. INVESTMENT HIGHLIGHTS
- Top 5 reasons to invest
- Key value drivers
- Exit potential

Provide specific numbers, dates, and names wherever available. If data is not available, indicate "Not disclosed" or "Not found".

Format as JSON with clear structure.`;

    try {
      const response = await anthropic.messages.create({
        model: 'claude-3-5-sonnet-20241022',
        max_tokens: 8192,
        temperature: 0,
        messages: [{ role: 'user', content: prompt }]
      });
      
      const text = response.content[0].type === 'text' ? response.content[0].text : '';
      
      // Parse JSON from response
      const jsonMatch = text.match(/\{[\s\S]*\}/);
      if (jsonMatch) {
        return JSON.parse(jsonMatch[0]);
      }
      
      // Fallback: try to parse the entire response
      return JSON.parse(text);
    } catch (error) {
      console.error('Error extracting structured data:', error);
      return {};
    }
  }
  
  /**
   * Build CIM structure from extracted data
   */
  private buildCIM(
    companyName: string,
    websiteUrl: string,
    structuredData: any
  ): CompanyCIM {
    const now = new Date().toISOString();
    
    return {
      metadata: {
        company_name: companyName,
        website_url: websiteUrl,
        generated_date: now,
        last_updated: now,
        data_quality_score: this.calculateDataQuality(structuredData),
        sources_count: this.countSources(structuredData)
      },
      
      executive_summary: {
        company_description: structuredData.company_overview?.description || 'Not found',
        investment_thesis: this.generateInvestmentThesis(structuredData),
        key_metrics: {
          founded: structuredData.company_overview?.founded || 'Not disclosed',
          employees: structuredData.company_overview?.employees || 'Not disclosed',
          revenue: structuredData.traction?.revenue || 'Not disclosed',
          growth_rate: structuredData.traction?.growth_rate || 'Not disclosed',
          funding_total: structuredData.funding?.total_raised || 'Not disclosed',
          last_valuation: structuredData.funding?.last_valuation || 'Not disclosed'
        },
        highlights: structuredData.investment_highlights?.reasons || []
      },
      
      company_overview: {
        name: companyName,
        founded: structuredData.company_overview?.founded || 'Not disclosed',
        headquarters: structuredData.company_overview?.headquarters || 'Not disclosed',
        employees: structuredData.company_overview?.employees || 'Not disclosed',
        description: structuredData.company_overview?.description || 'Not found',
        mission: structuredData.company_overview?.mission || 'Not disclosed',
        vision: structuredData.company_overview?.vision || 'Not disclosed',
        values: structuredData.company_overview?.values || [],
        website: websiteUrl
      },
      
      products_services: {
        offerings: structuredData.products?.main_products || [],
        features: structuredData.products?.key_features || [],
        technology: structuredData.products?.technology_stack || 'Not disclosed',
        pricing_model: structuredData.products?.pricing_model || 'Not disclosed',
        target_customers: structuredData.products?.target_customers || 'Not disclosed',
        use_cases: []
      },
      
      market_analysis: {
        tam: structuredData.market?.tam || 'Not disclosed',
        sam: structuredData.market?.sam || 'Not disclosed',
        som: structuredData.market?.som || 'Not disclosed',
        growth_rate: structuredData.market?.growth_rate || 'Not disclosed',
        market_drivers: structuredData.market?.drivers || [],
        trends: structuredData.market?.trends || [],
        competitive_landscape: {
          competitors: structuredData.competitive?.competitors || [],
          advantages: structuredData.competitive?.advantages || [],
          positioning: structuredData.competitive?.positioning || 'Not disclosed',
          differentiation: structuredData.competitive?.differentiation || []
        }
      },
      
      business_model: {
        revenue_model: structuredData.business_model?.revenue_model || 'Not disclosed',
        pricing_strategy: structuredData.business_model?.pricing_strategy || 'Not disclosed',
        customer_acquisition: structuredData.business_model?.customer_acquisition || 'Not disclosed',
        unit_economics: {
          ltv: structuredData.business_model?.ltv || 'Not disclosed',
          cac: structuredData.business_model?.cac || 'Not disclosed',
          payback_period: structuredData.business_model?.payback || 'Not disclosed'
        },
        gross_margin: structuredData.business_model?.gross_margin || 'Not disclosed'
      },
      
      traction_metrics: {
        revenue: structuredData.traction?.revenue || 'Not disclosed',
        arr: structuredData.traction?.arr || 'Not disclosed',
        mrr: structuredData.traction?.mrr || 'Not disclosed',
        growth_rate: structuredData.traction?.growth_rate || 'Not disclosed',
        customer_count: structuredData.traction?.customers || 'Not disclosed',
        key_customers: structuredData.traction?.key_customers || [],
        nrr: structuredData.traction?.nrr || 'Not disclosed',
        retention_rate: structuredData.traction?.retention || 'Not disclosed',
        other_kpis: structuredData.traction?.other_kpis || {}
      },
      
      team_leadership: {
        ceo_founder: structuredData.team?.ceo || { name: 'Not disclosed', background: '' },
        executives: structuredData.team?.executives || [],
        board_members: structuredData.team?.board || [],
        advisors: structuredData.team?.advisors || [],
        team_size: structuredData.team?.size || 'Not disclosed',
        key_hires_needed: []
      },
      
      funding_financials: {
        total_raised: structuredData.funding?.total_raised || 'Not disclosed',
        funding_rounds: structuredData.funding?.rounds || [],
        last_round: structuredData.funding?.last_round || {
          amount: 'Not disclosed',
          date: 'Not disclosed',
          valuation: 'Not disclosed',
          investors: []
        },
        key_investors: structuredData.funding?.investors || [],
        use_of_funds: structuredData.funding?.use_of_funds || [],
        burn_rate: structuredData.funding?.burn_rate || 'Not disclosed',
        runway: structuredData.funding?.runway || 'Not disclosed'
      },
      
      growth_strategy: {
        expansion_plans: structuredData.growth?.expansion || [],
        product_roadmap: structuredData.growth?.roadmap || [],
        go_to_market: structuredData.growth?.gtm || 'Not disclosed',
        partnerships: structuredData.growth?.partnerships || [],
        acquisition_targets: []
      },
      
      investment_opportunity: {
        highlights: structuredData.investment_highlights?.reasons || [],
        value_drivers: structuredData.investment_highlights?.drivers || [],
        exit_potential: structuredData.investment_highlights?.exit || 'Not disclosed',
        expected_returns: 'To be determined',
        risks: structuredData.risks || [],
        mitigation_strategies: []
      },
      
      data_room_items: [
        'Financial statements',
        'Cap table',
        'Legal documents',
        'Customer contracts',
        'Product documentation',
        'Team bios',
        'Board materials'
      ],
      
      citations: this.extractCitations(structuredData)
    };
  }
  
  /**
   * Generate investment thesis
   */
  private generateInvestmentThesis(data: any): string {
    const revenue = data.traction?.revenue || 'undisclosed revenue';
    const growth = data.traction?.growth_rate || 'strong growth';
    const market = data.market?.tam || 'large market';
    
    return `${data.company_overview?.name || 'The company'} presents a compelling investment opportunity with ${revenue} and ${growth} in a ${market}. The company's ${data.competitive?.advantages?.[0] || 'unique positioning'} positions it well for continued expansion.`;
  }
  
  /**
   * Calculate data quality score
   */
  private calculateDataQuality(data: any): number {
    let score = 0;
    let total = 0;
    
    const checkField = (value: any) => {
      total++;
      if (value && value !== 'Not disclosed' && value !== 'Not found') {
        score++;
      }
    };
    
    // Check key fields
    checkField(data.company_overview?.description);
    checkField(data.traction?.revenue);
    checkField(data.traction?.growth_rate);
    checkField(data.market?.tam);
    checkField(data.team?.ceo);
    checkField(data.funding?.total_raised);
    checkField(data.products?.main_products);
    checkField(data.competitive?.competitors);
    
    return total > 0 ? Math.round((score / total) * 100) : 0;
  }
  
  /**
   * Count data sources
   */
  private countSources(data: any): number {
    let count = 0;
    if (data.company_overview) count++;
    if (data.traction) count++;
    if (data.market) count++;
    if (data.team) count++;
    if (data.funding) count++;
    return count;
  }
  
  /**
   * Extract citations from search results
   */
  private extractCitations(data: any): Citation[] {
    const citations: Citation[] = [];
    
    // Add placeholder citations - in production, these would come from search results
    citations.push({
      source: 'Company Website',
      url: data.website || '#',
      date: new Date().toISOString(),
      relevance: 1.0
    });
    
    if (data.news_sources) {
      data.news_sources.forEach((source: any) => {
        citations.push({
          source: source.title || 'News Article',
          url: source.url || '#',
          date: source.date || new Date().toISOString(),
          relevance: 0.8
        });
      });
    }
    
    return citations;
  }
  
  /**
   * Store CIM in database
   */
  private async storeCIM(cim: CompanyCIM): Promise<void> {
    try {
      await supabase
        .from('company_cims')
        .upsert({
          company_name: cim.metadata.company_name,
          website_url: cim.metadata.website_url,
          cim_data: cim,
          data_quality_score: cim.metadata.data_quality_score,
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString()
        });
    } catch (error) {
      console.error('Error storing CIM:', error);
    }
  }
}

// Type definitions
export interface CompanyCIM {
  metadata: {
    company_name: string;
    website_url: string;
    generated_date: string;
    last_updated: string;
    data_quality_score: number;
    sources_count: number;
  };
  
  executive_summary: {
    company_description: string;
    investment_thesis: string;
    key_metrics: any;
    highlights: string[];
  };
  
  company_overview: {
    name: string;
    founded: string;
    headquarters: string;
    employees: string;
    description: string;
    mission: string;
    vision: string;
    values: string[];
    website: string;
  };
  
  products_services: {
    offerings: any[];
    features: string[];
    technology: string;
    pricing_model: string;
    target_customers: string;
    use_cases: string[];
  };
  
  market_analysis: {
    tam: string;
    sam: string;
    som: string;
    growth_rate: string;
    market_drivers: string[];
    trends: string[];
    competitive_landscape: {
      competitors: string[];
      advantages: string[];
      positioning: string;
      differentiation: string[];
    };
  };
  
  business_model: {
    revenue_model: string;
    pricing_strategy: string;
    customer_acquisition: string;
    unit_economics: {
      ltv: string;
      cac: string;
      payback_period: string;
    };
    gross_margin: string;
  };
  
  traction_metrics: {
    revenue: string;
    arr: string;
    mrr: string;
    growth_rate: string;
    customer_count: string;
    key_customers: string[];
    nrr: string;
    retention_rate: string;
    other_kpis: any;
  };
  
  team_leadership: {
    ceo_founder: any;
    executives: any[];
    board_members: string[];
    advisors: string[];
    team_size: string;
    key_hires_needed: string[];
  };
  
  funding_financials: {
    total_raised: string;
    funding_rounds: any[];
    last_round: {
      amount: string;
      date: string;
      valuation: string;
      investors: string[];
    };
    key_investors: string[];
    use_of_funds: string[];
    burn_rate: string;
    runway: string;
  };
  
  growth_strategy: {
    expansion_plans: string[];
    product_roadmap: string[];
    go_to_market: string;
    partnerships: string[];
    acquisition_targets: string[];
  };
  
  investment_opportunity: {
    highlights: string[];
    value_drivers: string[];
    exit_potential: string;
    expected_returns: string;
    risks: string[];
    mitigation_strategies: string[];
  };
  
  data_room_items: string[];
  
  citations: Citation[];
}

interface Citation {
  source: string;
  url: string;
  date: string;
  relevance: number;
}

// Export singleton instance
export const companyCIMScraper = new CompanyCIMScraper();