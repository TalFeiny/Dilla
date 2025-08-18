/**
 * Enhanced Web Research Tool
 * Intelligently combines Firecrawl deep scraping with Tavily search
 * for comprehensive company and market research
 */

import FirecrawlApp from '@mendable/firecrawl-js';
import { createClient } from '@supabase/supabase-js';

const FIRECRAWL_API_KEY = process.env.FIRECRAWL_API_KEY;
const TAVILY_API_KEY = process.env.TAVILY_API_KEY;
const CLAUDE_API_KEY = process.env.CLAUDE_API_KEY;

const supabase = createClient(
  process.env.NEXT_PUBLIC_SUPABASE_URL!,
  process.env.SUPABASE_SERVICE_ROLE_KEY!
);

interface ResearchConfig {
  maxDepth: number;
  tavilySearchDepth: 'basic' | 'advanced';
  firecrawlPages: number;
  parallelExecution: boolean;
  cacheResults: boolean;
  cacheDuration: number; // in seconds
}

interface ComprehensiveProfile {
  company: {
    name: string;
    website: string;
    description: string;
    sector: string;
  };
  funding: {
    total: string;
    lastRound: string;
    valuation: string;
    investors: string[];
    history: any[];
  };
  metrics: {
    revenue: string;
    growth: string;
    employees: string;
    customers: string;
  };
  product: {
    description: string;
    features: string[];
    pricing: any;
    competitors: string[];
  };
  team: {
    founders: any[];
    executives: any[];
    boardMembers: any[];
    advisors: any[];
  };
  news: {
    recent: any[];
    funding: any[];
    product: any[];
  };
  market: {
    size: string;
    growth: string;
    trends: string[];
    opportunities: string[];
  };
  citations: Array<{
    source: string;
    url: string;
    date: string;
    confidence: number;
  }>;
}

export class EnhancedWebResearch {
  private firecrawl: FirecrawlApp | null = null;
  private config: ResearchConfig;
  
  constructor(config?: Partial<ResearchConfig>) {
    this.config = {
      maxDepth: 3,
      tavilySearchDepth: 'advanced',
      firecrawlPages: 5,
      parallelExecution: true,
      cacheResults: true,
      cacheDuration: 900, // 15 minutes
      ...config
    };
    
    if (FIRECRAWL_API_KEY) {
      this.firecrawl = new FirecrawlApp({ apiKey: FIRECRAWL_API_KEY });
    }
  }
  
  /**
   * Main entry point for comprehensive company research
   */
  async researchCompany(companyName: string): Promise<ComprehensiveProfile> {
    console.log(`🚀 Starting enhanced research for ${companyName}`);
    
    // Check cache first
    const cached = await this.getCachedProfile(companyName);
    if (cached && this.config.cacheResults) {
      console.log(`📦 Using cached profile for ${companyName}`);
      return cached;
    }
    
    // Execute research in parallel if configured
    const tasks = [];
    
    if (this.config.parallelExecution) {
      tasks.push(
        this.searchDatabase(companyName),
        this.searchTavily(companyName),
        this.scrapeWithFirecrawl(companyName),
        this.gatherMarketIntelligence(companyName)
      );
      
      const [dbData, tavilyData, firecrawlData, marketData] = await Promise.all(tasks);
      
      // Synthesize all data sources
      const profile = await this.synthesizeProfile(
        companyName,
        dbData,
        tavilyData,
        firecrawlData,
        marketData
      );
      
      // Cache the result
      if (this.config.cacheResults) {
        await this.cacheProfile(companyName, profile);
      }
      
      return profile;
    } else {
      // Sequential execution for lower resource usage
      const dbData = await this.searchDatabase(companyName);
      const tavilyData = await this.searchTavily(companyName);
      const firecrawlData = await this.scrapeWithFirecrawl(companyName);
      const marketData = await this.gatherMarketIntelligence(companyName);
      
      const profile = await this.synthesizeProfile(
        companyName,
        dbData,
        tavilyData,
        firecrawlData,
        marketData
      );
      
      if (this.config.cacheResults) {
        await this.cacheProfile(companyName, profile);
      }
      
      return profile;
    }
  }
  
  /**
   * Search internal database
   */
  private async searchDatabase(companyName: string): Promise<any> {
    const { data } = await supabase
      .from('companies')
      .select('*')
      .ilike('name', `%${companyName}%`)
      .limit(1)
      .single();
    
    return data;
  }
  
  /**
   * Enhanced Tavily search with multiple queries
   */
  private async searchTavily(companyName: string): Promise<any> {
    if (!TAVILY_API_KEY) return null;
    
    const queries = [
      `${companyName} funding valuation revenue ${new Date().getFullYear()}`,
      `${companyName} competitors market share`,
      `${companyName} founders executives team`,
      `${companyName} product features pricing`,
      `${companyName} latest news announcements`
    ];
    
    const results = [];
    
    for (const query of queries.slice(0, 3)) { // Limit to 3 queries for speed
      try {
        const response = await fetch('https://api.tavily.com/search', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            api_key: TAVILY_API_KEY,
            query,
            search_depth: this.config.tavilySearchDepth,
            max_results: 10,
            include_answer: true,
            include_raw_content: true,
            include_domains: [
              'techcrunch.com', 'crunchbase.com', 'pitchbook.com',
              'reuters.com', 'bloomberg.com', 'forbes.com',
              'venturebeat.com', 'theinformation.com'
            ]
          })
        });
        
        const data = await response.json();
        results.push({
          query,
          answer: data.answer,
          results: data.results,
          sources: data.results?.map((r: any) => ({
            title: r.title,
            url: r.url,
            snippet: r.content?.substring(0, 200)
          }))
        });
      } catch (error) {
        console.error(`Tavily search failed for query: ${query}`, error);
      }
    }
    
    return results;
  }
  
  /**
   * Deep scrape with Firecrawl
   */
  private async scrapeWithFirecrawl(companyName: string): Promise<any> {
    if (!this.firecrawl) return null;
    
    try {
      // Find company website
      const websiteUrl = await this.findCompanyWebsite(companyName);
      
      console.log(`🔥 Firecrawl deep scraping ${websiteUrl}`);
      
      // Scrape main page
      const mainPage = await this.firecrawl.scrapeUrl(websiteUrl, {
        formats: ['markdown', 'html'],
        waitFor: 2000
      });
      
      const scrapedData = {
        main: mainPage.data,
        pages: []
      };
      
      // Scrape important subpages
      const importantPaths = ['/about', '/team', '/investors', '/products', '/pricing'];
      
      for (const path of importantPaths.slice(0, this.config.firecrawlPages)) {
        try {
          const url = new URL(path, websiteUrl).toString();
          const page = await this.firecrawl.scrapeUrl(url, {
            formats: ['markdown'],
            waitFor: 1000
          });
          
          if (page.data?.markdown) {
            scrapedData.pages.push({
              path,
              content: page.data.markdown,
              metadata: page.data.metadata
            });
          }
        } catch (error) {
          // Page might not exist
        }
      }
      
      return scrapedData;
    } catch (error) {
      console.error('Firecrawl error:', error);
      return null;
    }
  }
  
  /**
   * Gather market intelligence
   */
  private async gatherMarketIntelligence(companyName: string): Promise<any> {
    // Use both Tavily and internal data for market analysis
    const marketQueries = [
      `${companyName} industry market size TAM`,
      `${companyName} sector competitors landscape`
    ];
    
    const marketData: any = {
      competitors: [],
      marketSize: null,
      trends: []
    };
    
    if (TAVILY_API_KEY) {
      for (const query of marketQueries) {
        try {
          const response = await fetch('https://api.tavily.com/search', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              api_key: TAVILY_API_KEY,
              query,
              search_depth: 'basic',
              max_results: 5,
              include_answer: true
            })
          });
          
          const data = await response.json();
          if (data.answer) {
            // Parse market data from answer
            marketData.raw = data.answer;
            marketData.sources = data.results?.map((r: any) => r.url);
          }
        } catch (error) {
          console.error('Market intelligence gathering failed:', error);
        }
      }
    }
    
    return marketData;
  }
  
  /**
   * Find company website
   */
  private async findCompanyWebsite(companyName: string): Promise<string> {
    // Check database first
    const { data } = await supabase
      .from('companies')
      .select('website_url')
      .ilike('name', `%${companyName}%`)
      .limit(1)
      .single();
    
    if (data?.website_url) {
      return data.website_url;
    }
    
    // Try common patterns
    const cleanName = companyName.toLowerCase().replace(/\s+/g, '');
    return `https://${cleanName}.com`;
  }
  
  /**
   * Synthesize all data sources into comprehensive profile
   */
  private async synthesizeProfile(
    companyName: string,
    dbData: any,
    tavilyData: any,
    firecrawlData: any,
    marketData: any
  ): Promise<ComprehensiveProfile> {
    // Use Claude to intelligently merge and structure the data
    if (!CLAUDE_API_KEY) {
      return this.basicSynthesis(companyName, dbData, tavilyData, firecrawlData, marketData);
    }
    
    const prompt = `Synthesize the following research data into a comprehensive company profile for ${companyName}.

Database Data:
${JSON.stringify(dbData, null, 2)}

Tavily Search Results:
${JSON.stringify(tavilyData, null, 2).substring(0, 5000)}

Firecrawl Scraping:
${JSON.stringify(firecrawlData, null, 2).substring(0, 5000)}

Market Intelligence:
${JSON.stringify(marketData, null, 2)}

Create a structured profile with:
1. Company overview (name, website, description, sector)
2. Funding details (total, last round, valuation, investors, history)
3. Key metrics (revenue, growth, employees, customers)
4. Product information (description, features, pricing, competitors)
5. Team (founders, executives, board, advisors)
6. Recent news (funding, product, general)
7. Market analysis (size, growth, trends, opportunities)

IMPORTANT:
- Extract ONLY factual information from the sources
- Include specific numbers and dates when available
- List all investor names found
- Identify all competitors mentioned
- Note the source for each data point

Return as JSON.`;
    
    try {
      const response = await fetch('https://api.anthropic.com/v1/messages', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'x-api-key': CLAUDE_API_KEY,
          'anthropic-version': '2023-06-01'
        },
        body: JSON.stringify({
          model: 'claude-3-5-sonnet-20241022',
          max_tokens: 3000,
          messages: [{ role: 'user', content: prompt }]
        })
      });
      
      if (response.ok) {
        const data = await response.json();
        const content = data.content[0].text;
        const jsonMatch = content.match(/\{[\s\S]*\}/);
        
        if (jsonMatch) {
          const profile = JSON.parse(jsonMatch[0]);
          
          // Add citations
          profile.citations = this.generateCitations(tavilyData, firecrawlData);
          
          return profile;
        }
      }
    } catch (error) {
      console.error('Claude synthesis failed:', error);
    }
    
    return this.basicSynthesis(companyName, dbData, tavilyData, firecrawlData, marketData);
  }
  
  /**
   * Basic synthesis without Claude
   */
  private basicSynthesis(
    companyName: string,
    dbData: any,
    tavilyData: any,
    firecrawlData: any,
    marketData: any
  ): ComprehensiveProfile {
    return {
      company: {
        name: companyName,
        website: dbData?.website_url || `https://${companyName.toLowerCase().replace(/\s+/g, '')}.com`,
        description: dbData?.description || 'Company information',
        sector: dbData?.sector || 'Technology'
      },
      funding: {
        total: dbData?.total_funding_usd || 'Unknown',
        lastRound: dbData?.last_funding_round || 'Unknown',
        valuation: dbData?.valuation_usd || 'Unknown',
        investors: dbData?.investors || [],
        history: []
      },
      metrics: {
        revenue: dbData?.revenue || 'Unknown',
        growth: dbData?.growth_rate || 'Unknown',
        employees: dbData?.employee_count || 'Unknown',
        customers: 'Unknown'
      },
      product: {
        description: 'Product information',
        features: [],
        pricing: null,
        competitors: []
      },
      team: {
        founders: [],
        executives: [],
        boardMembers: [],
        advisors: []
      },
      news: {
        recent: [],
        funding: [],
        product: []
      },
      market: {
        size: marketData?.marketSize || 'Unknown',
        growth: 'Unknown',
        trends: marketData?.trends || [],
        opportunities: []
      },
      citations: this.generateCitations(tavilyData, firecrawlData)
    };
  }
  
  /**
   * Generate citations from sources
   */
  private generateCitations(tavilyData: any, firecrawlData: any): any[] {
    const citations = [];
    
    // Add Tavily citations
    if (tavilyData && Array.isArray(tavilyData)) {
      tavilyData.forEach((search: any) => {
        if (search.sources) {
          search.sources.forEach((source: any) => {
            citations.push({
              source: source.title || 'Web Search',
              url: source.url,
              date: new Date().toISOString(),
              confidence: 0.8
            });
          });
        }
      });
    }
    
    // Add Firecrawl citations
    if (firecrawlData?.main?.metadata?.url) {
      citations.push({
        source: 'Company Website',
        url: firecrawlData.main.metadata.url,
        date: new Date().toISOString(),
        confidence: 0.95
      });
    }
    
    return citations;
  }
  
  /**
   * Cache profile
   */
  private async cacheProfile(companyName: string, profile: ComprehensiveProfile): Promise<void> {
    try {
      await supabase
        .from('research_cache')
        .upsert({
          company_name: companyName,
          profile_data: profile,
          expires_at: new Date(Date.now() + this.config.cacheDuration * 1000).toISOString(),
          created_at: new Date().toISOString()
        });
    } catch (error) {
      console.error('Cache write failed:', error);
    }
  }
  
  /**
   * Get cached profile
   */
  private async getCachedProfile(companyName: string): Promise<ComprehensiveProfile | null> {
    try {
      const { data } = await supabase
        .from('research_cache')
        .select('profile_data')
        .eq('company_name', companyName)
        .gt('expires_at', new Date().toISOString())
        .limit(1)
        .single();
      
      return data?.profile_data || null;
    } catch (error) {
      return null;
    }
  }
}

export const enhancedWebResearch = new EnhancedWebResearch();