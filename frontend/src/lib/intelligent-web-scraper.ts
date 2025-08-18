import Anthropic from '@anthropic-ai/sdk';

const anthropic = new Anthropic({
  apiKey: process.env.CLAUDE_API_KEY!,
});

interface IntelligentScraperResult {
  companyName: string;
  website: string;
  pagesScraped: number;
  data: {
    overview: any;
    products: any;
    team: any;
    financials: any;
    customers: any;
    market: any;
    technology: any;
  };
  sources: string[];
  confidence: number;
}

export class IntelligentWebScraper {
  private tavilyKey: string;
  
  constructor() {
    this.tavilyKey = process.env.TAVILY_API_KEY || '';
  }
  
  /**
   * Main entry point - intelligently scrape a company
   */
  async scrapeCompany(companyName: string, context?: string): Promise<IntelligentScraperResult> {
    console.log(`Starting intelligent scrape for ${companyName}`);
    
    // Step 1: Find the company's official website with context awareness
    const website = await this.findOfficialWebsite(companyName, context);
    if (!website) {
      throw new Error(`Could not find website for ${companyName}`);
    }
    
    console.log(`Found website: ${website}`);
    
    // Step 2: Use multiple strategies to gather data
    const strategies = [
      this.scrapeViaSearch(companyName, website),
      this.scrapeViaSitemap(website),
      this.scrapeViaAPI(companyName),
      this.scrapeViaLinkedIn(companyName),
      this.scrapeViaCrunchbase(companyName)
    ];
    
    // Run all strategies in parallel
    const results = await Promise.allSettled(strategies);
    
    // Step 3: Merge and deduplicate data
    const mergedData = this.mergeResults(results);
    
    // Step 4: Use Claude to structure and analyze
    const structuredData = await this.structureWithClaude(companyName, mergedData);
    
    return {
      companyName,
      website,
      pagesScraped: mergedData.pagesScraped || 0,
      data: structuredData,
      sources: mergedData.sources || [],
      confidence: this.calculateConfidence(structuredData)
    };
  }
  
  /**
   * Find the company's official website using multiple methods
   */
  private async findOfficialWebsite(companyName: string, context?: string): Promise<string | null> {
    // Method 1: Direct search for website with context
    try {
      // Build search query based on context
      let searchQuery = `${companyName} official website`;
      
      // Add context clues to search if provided
      if (context) {
        // Use the actual context to refine the search
        searchQuery = `${companyName} ${context} company website`.slice(0, 100); // Limit length
      }
      
      const response = await fetch('https://api.tavily.com/search', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          api_key: this.tavilyKey,
          query: searchQuery,
          max_results: 10, // Get more results to filter through
          search_depth: 'advanced',
          include_answer: true
        })
      });
      
      const data = await response.json();
      
      // Look for the official website in results
      for (const result of data.results || []) {
        const url = result.url.toLowerCase();
        const title = result.title?.toLowerCase() || '';
        const content = result.content?.toLowerCase() || '';
        
        // Check if this is likely the official site
        const companyNameLower = companyName.toLowerCase().replace(/\s+/g, '');
        
        // Direct domain match
        if (url.includes(companyNameLower + '.com') || 
            url.includes(companyNameLower + '.io') ||
            url.includes(companyNameLower + '.ai') ||
            url.includes(companyNameLower + '.co')) {
          return new URL(result.url).origin;
        }
        
        // Title/content indicates official site
        if ((title.includes('official') || title.includes('home')) &&
            title.includes(companyNameLower)) {
          return new URL(result.url).origin;
        }
      }
      
      // Method 2: Try to extract from answer
      if (data.answer) {
        const urlMatch = data.answer.match(/https?:\/\/[^\s]+/);
        if (urlMatch) {
          return new URL(urlMatch[0]).origin;
        }
      }
      
    } catch (error) {
      console.error('Error finding website:', error);
    }
    
    // Method 3: Try common domain patterns
    const commonDomains = ['.com', '.io', '.ai', '.co', '.app', '.dev'];
    const cleanName = companyName.toLowerCase().replace(/\s+/g, '');
    
    for (const domain of commonDomains) {
      const testUrl = `https://${cleanName}${domain}`;
      try {
        const response = await fetch(testUrl, { method: 'HEAD' });
        if (response.ok) {
          return testUrl;
        }
      } catch (e) {
        // Domain doesn't exist
      }
    }
    
    return null;
  }
  
  /**
   * Strategy 1: Scrape via intelligent search
   */
  private async scrapeViaSearch(companyName: string, website: string): Promise<any> {
    const searches = [
      `site:${new URL(website).hostname} team leadership founders executives`,
      `site:${new URL(website).hostname} about us company mission vision`,
      `site:${new URL(website).hostname} management board directors C-suite`,
      `site:${new URL(website).hostname} products services features solutions`,
      `site:${new URL(website).hostname} pricing plans customers clients`,
      `site:${new URL(website).hostname} investors funding revenue metrics`,
      `${companyName} founders CEO CTO CFO leadership background experience`,
      `${companyName} revenue ARR funding valuation employees headcount`,
      `${companyName} customers clients case studies testimonials`,
      `${companyName} technology stack architecture patents innovation`
    ];
    
    const results: any = {};
    
    for (const query of searches) {
      try {
        const response = await fetch('https://api.tavily.com/search', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            api_key: this.tavilyKey,
            query,
            max_results: 2,  // Reduced from 3
            search_depth: 'basic',  // Changed from 'advanced'
            include_answer: true,
            include_raw_content: false  // Don't get full HTML!
          })
        });
        
        const data = await response.json();
        
        // Store by category - prioritize team data
        if (query.includes('team') || query.includes('leadership') || query.includes('founders') || query.includes('executives')) {
          if (!results.team) results.team = [];
          results.team.push(data);
        } else if (query.includes('CEO') || query.includes('CTO') || query.includes('CFO')) {
          if (!results.executives) results.executives = [];
          results.executives.push(data);
        } else if (query.includes('about') || query.includes('mission')) {
          results.about = data;
        } else if (query.includes('products') || query.includes('services')) {
          results.products = data;
        } else if (query.includes('pricing')) {
          results.pricing = data;
        } else if (query.includes('revenue') || query.includes('funding')) {
          results.financials = data;
        } else if (query.includes('customers')) {
          results.customers = data;
        } else if (query.includes('technology')) {
          results.technology = data;
        }
        
      } catch (error) {
        console.error(`Search failed for ${query}:`, error);
      }
    }
    
    return results;
  }
  
  /**
   * Strategy 2: Scrape via sitemap
   */
  private async scrapeViaSitemap(website: string): Promise<any> {
    try {
      // Try to fetch sitemap
      const sitemapUrl = `${website}/sitemap.xml`;
      const response = await fetch(sitemapUrl);
      
      if (response.ok) {
        const sitemapText = await response.text();
        
        // Extract URLs from sitemap
        const urls = sitemapText.match(/<loc>(.*?)<\/loc>/g)?.map(
          match => match.replace(/<\/?loc>/g, '')
        ) || [];
        
        // Categorize URLs
        const categorizedUrls = {
          about: urls.filter(u => u.includes('/about') || u.includes('/company')),
          team: urls.filter(u => u.includes('/team') || u.includes('/leadership')),
          products: urls.filter(u => u.includes('/product') || u.includes('/solutions')),
          blog: urls.filter(u => u.includes('/blog') || u.includes('/news')),
          careers: urls.filter(u => u.includes('/careers') || u.includes('/jobs'))
        };
        
        return { sitemap: categorizedUrls, totalUrls: urls.length };
      }
    } catch (error) {
      console.error('Sitemap fetch failed:', error);
    }
    
    return null;
  }
  
  /**
   * Strategy 3: Check for public API/data
   */
  private async scrapeViaAPI(companyName: string): Promise<any> {
    // Check if company has public API endpoints
    const apiEndpoints = [
      '/api/company',
      '/api/about',
      '/.well-known/company-info',
      '/data.json',
      '/api/v1/info'
    ];
    
    // This would need actual implementation
    return null;
  }
  
  /**
   * Strategy 4: LinkedIn data
   */
  private async scrapeViaLinkedIn(companyName: string): Promise<any> {
    try {
      const response = await fetch('https://api.tavily.com/search', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          api_key: this.tavilyKey,
          query: `site:linkedin.com/company "${companyName}" employees founded industry`,
          max_results: 3,
          search_depth: 'advanced',
          include_answer: true
        })
      });
      
      const data = await response.json();
      return { linkedin: data };
      
    } catch (error) {
      console.error('LinkedIn search failed:', error);
      return null;
    }
  }
  
  /**
   * Strategy 5: Crunchbase data
   */
  private async scrapeViaCrunchbase(companyName: string): Promise<any> {
    try {
      const response = await fetch('https://api.tavily.com/search', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          api_key: this.tavilyKey,
          query: `site:crunchbase.com "${companyName}" funding rounds investors valuation`,
          max_results: 3,
          search_depth: 'advanced',
          include_answer: true
        })
      });
      
      const data = await response.json();
      return { crunchbase: data };
      
    } catch (error) {
      console.error('Crunchbase search failed:', error);
      return null;
    }
  }
  
  /**
   * Merge results from all strategies
   */
  private mergeResults(results: PromiseSettledResult<any>[]): any {
    const merged: any = {
      sources: [],
      pagesScraped: 0,
      raw: {}
    };
    
    for (const result of results) {
      if (result.status === 'fulfilled' && result.value) {
        // Merge data
        Object.assign(merged.raw, result.value);
        
        // Count sources
        if (result.value.results) {
          merged.sources.push(...result.value.results.map((r: any) => r.url));
          merged.pagesScraped += result.value.results.length;
        }
      }
    }
    
    // Deduplicate sources
    merged.sources = [...new Set(merged.sources)];
    
    return merged;
  }
  
  /**
   * Pre-filter raw data to extract only relevant text
   */
  private extractRelevantText(rawData: any): any {
    const extracted: any = {
      team: [],
      product: [],
      market: [],
      customers: []
    };
    
    // Process categorized Tavily results
    if (rawData.team) {
      for (const searchResult of rawData.team) {
        if (searchResult.results) {
          searchResult.results.forEach((r: any) => {
            extracted.team.push({
              title: r.title,
              content: r.content, // This is the snippet, not full HTML
              url: r.url
            });
          });
        }
      }
    }
    
    if (rawData.executives) {
      for (const searchResult of rawData.executives) {
        if (searchResult.results) {
          searchResult.results.forEach((r: any) => {
            extracted.team.push({
              title: r.title,
              content: r.content,
              url: r.url
            });
          });
        }
      }
    }
    
    if (rawData.products && rawData.products.results) {
      rawData.products.results.forEach((r: any) => {
        extracted.product.push({
          title: r.title,
          content: r.content,
          url: r.url
        });
      });
    }
    
    if (rawData.customers && rawData.customers.results) {
      rawData.customers.results.forEach((r: any) => {
        extracted.customers.push({
          title: r.title,
          content: r.content,
          url: r.url
        });
      });
    }
    
    if (rawData.financials && rawData.financials.results) {
      rawData.financials.results.forEach((r: any) => {
        extracted.market.push({
          title: r.title,
          content: r.content,
          url: r.url
        });
      });
    }
    
    return extracted;
  }
  
  /**
   * Use Claude to structure the scraped data
   */
  private async structureWithClaude(companyName: string, rawData: any): Promise<any> {
    // Pre-filter to only relevant text before sending to Claude
    const relevantData = this.extractRelevantText(rawData);
    
    // Truncate to avoid massive token usage
    const maxDataLength = 3000; // Reduced from 5000
    let truncatedData = JSON.stringify(relevantData, null, 2);
    if (truncatedData.length > maxDataLength) {
      truncatedData = truncatedData.substring(0, maxDataLength) + '\n... [truncated]';
    }
    
    const prompt = `Analyze the following data about ${companyName} and structure it into a comprehensive company profile.
    
Raw Data (truncated):
${truncatedData}

Extract ONLY these 4 key investment criteria:

1. TEAM
- Founders (names, backgrounds, previous exits/companies)
- Key executives (CEO, CTO, CFO with experience)
- Team size
- Notable advisors/board members

2. PRODUCT
- What they actually build (core product, not marketing fluff)
- Key differentiators
- Technology/technical moat
- Product stage (beta/launched/scaling)

3. MARKET
- TAM size in dollars
- Market growth rate
- Top 3 competitors
- Why they can win

4. CUSTOMERS
- Customer segments (SMB/Enterprise/Consumer)
- Notable logos/customers
- Customer count or usage metrics
- Pricing model

Return ONLY these 4 sections as JSON. Skip sections if no data available.`;

    try {
      const response = await anthropic.messages.create({
        model: 'claude-3-haiku-20240307', // Use Haiku for simple extraction tasks (10x cheaper, faster)
        max_tokens: 2000, // Reduced from 4000
        temperature: 0,
        messages: [{ role: 'user', content: prompt }],
        system: 'You are a business analyst. Extract and structure company information from raw data. Output valid JSON only.'
      });
      
      const content = response.content[0].type === 'text' ? response.content[0].text : '{}';
      
      // Try to parse JSON from response
      try {
        return JSON.parse(content);
      } catch (e) {
        // Extract JSON from markdown if wrapped
        const jsonMatch = content.match(/```json\n?([\s\S]*?)\n?```/);
        if (jsonMatch) {
          return JSON.parse(jsonMatch[1]);
        }
        return {};
      }
      
    } catch (error) {
      console.error('Claude analysis failed:', error);
      return {};
    }
  }
  
  /**
   * Calculate confidence score based on data completeness
   */
  private calculateConfidence(data: any): number {
    let score = 0;
    let total = 0;
    
    const checkField = (field: any, weight: number = 1) => {
      total += weight;
      if (field && field !== 'N/A' && field !== 'Not found') {
        score += weight;
      }
    };
    
    // Check key fields
    checkField(data.overview?.description, 2);
    checkField(data.overview?.founded);
    checkField(data.products?.main_product, 2);
    checkField(data.team?.founders, 2);
    checkField(data.financials?.revenue, 3);
    checkField(data.financials?.funding, 2);
    checkField(data.customers?.notable);
    checkField(data.market?.tam);
    
    return Math.round((score / total) * 100);
  }
}

export const intelligentWebScraper = new IntelligentWebScraper();