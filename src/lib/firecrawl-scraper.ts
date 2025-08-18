import FirecrawlApp from '@mendable/firecrawl-js';
import { createClient } from '@supabase/supabase-js';

const FIRECRAWL_API_KEY = process.env.FIRECRAWL_API_KEY || '';
const CLAUDE_API_KEY = process.env.CLAUDE_API_KEY;

const supabase = createClient(
  process.env.NEXT_PUBLIC_SUPABASE_URL!,
  process.env.SUPABASE_SERVICE_ROLE_KEY!
);

interface ScrapedData {
  title?: string;
  description?: string;
  content: string;
  metadata?: any;
  links?: string[];
}

interface CompanyProfile {
  name: string;
  website: string;
  description: string;
  funding?: {
    total?: string;
    lastRound?: string;
    investors?: string[];
    valuation?: string;
  };
  team?: {
    founders?: string[];
    size?: string;
    keyPeople?: any[];
  };
  product?: {
    description?: string;
    features?: string[];
    customers?: string[];
  };
  financials?: {
    revenue?: string;
    growth?: string;
    metrics?: any;
  };
  news?: any[];
  sources: string[];
}

export class FirecrawlScraper {
  private firecrawl: FirecrawlApp | null = null;
  
  constructor() {
    if (FIRECRAWL_API_KEY) {
      this.firecrawl = new FirecrawlApp({ apiKey: FIRECRAWL_API_KEY });
    }
  }
  
  /**
   * Scrape a company website using Firecrawl
   */
  async scrapeCompanyWebsite(companyName: string, websiteUrl?: string): Promise<CompanyProfile> {
    console.log(`🔥 Firecrawl: Scraping ${companyName}...`);
    
    // Step 1: Find website if not provided
    if (!websiteUrl) {
      websiteUrl = await this.findCompanyWebsite(companyName);
    }
    
    // Step 2: Scrape with Firecrawl (much more powerful than basic scraping)
    let scrapedData: ScrapedData | null = null;
    
    if (this.firecrawl) {
      try {
        console.log(`🔥 Scraping ${websiteUrl} with Firecrawl...`);
        
        // Scrape the main page - updated for new Firecrawl API
        const mainPage = await this.firecrawl.scrapeUrl(websiteUrl, {
          formats: ['markdown', 'html'],
          waitFor: 2000 // Wait for dynamic content
        });
        
        scrapedData = {
          title: mainPage.data?.metadata?.title,
          description: mainPage.data?.metadata?.description,
          content: mainPage.data?.markdown || mainPage.data?.content || '',
          metadata: mainPage.data?.metadata,
          links: mainPage.data?.links
        };
        
        // Try to crawl important pages
        const importantPaths = ['/about', '/team', '/investors', '/funding', '/products', '/pricing'];
        const crawledPages: any[] = [];
        
        for (const path of importantPaths) {
          try {
            const url = new URL(path, websiteUrl).toString();
            console.log(`🔥 Crawling ${url}...`);
            const page = await this.firecrawl.scrapeUrl(url, {
              formats: ['markdown'],
              waitFor: 1000
            });
            if (page.data?.markdown) {
              crawledPages.push({
                url,
                content: page.data.markdown,
                title: page.data?.metadata?.title
              });
            }
          } catch (error) {
            // Page might not exist, continue
            console.log(`Could not crawl ${path}`);
          }
        }
        
        // Combine all content
        if (crawledPages.length > 0) {
          scrapedData.content += '\n\n' + crawledPages.map(p => 
            `## ${p.title || p.url}\n${p.content}`
          ).join('\n\n');
        }
        
      } catch (error) {
        console.error('Firecrawl error:', error);
      }
    }
    
    // Step 3: If Firecrawl fails or not available, fallback to basic fetch
    if (!scrapedData) {
      console.log('Falling back to basic scraping...');
      scrapedData = await this.basicScrape(websiteUrl);
    }
    
    // Step 4: Extract structured data using Claude
    const profile = await this.extractCompanyProfile(companyName, websiteUrl, scrapedData);
    
    // Step 5: Store in database
    await this.storeProfile(profile);
    
    return profile;
  }
  
  /**
   * Find company website using search
   */
  private async findCompanyWebsite(companyName: string): Promise<string> {
    // First check database
    const { data: company } = await supabase
      .from('companies')
      .select('website_url')
      .ilike('name', `%${companyName}%`)
      .limit(1)
      .single();
    
    if (company?.website_url) {
      return company.website_url;
    }
    
    // Default to common pattern
    const cleanName = companyName.toLowerCase().replace(/\s+/g, '');
    return `https://${cleanName}.com`;
  }
  
  /**
   * Basic scraping fallback
   */
  private async basicScrape(url: string): Promise<ScrapedData> {
    try {
      const response = await fetch(url);
      const html = await response.text();
      
      // Extract text content (very basic)
      const textContent = html
        .replace(/<script\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/script>/gi, '')
        .replace(/<style\b[^<]*(?:(?!<\/style>)<[^<]*)*<\/style>/gi, '')
        .replace(/<[^>]+>/g, ' ')
        .replace(/\s+/g, ' ')
        .trim();
      
      return {
        content: textContent.substring(0, 10000), // Limit size
        metadata: { url }
      };
    } catch (error) {
      console.error('Basic scrape error:', error);
      return { content: '', metadata: { url, error: error.message } };
    }
  }
  
  /**
   * Extract structured company profile using Claude
   */
  private async extractCompanyProfile(
    companyName: string,
    websiteUrl: string,
    scrapedData: ScrapedData
  ): Promise<CompanyProfile> {
    if (!CLAUDE_API_KEY || !scrapedData.content) {
      return {
        name: companyName,
        website: websiteUrl,
        description: scrapedData.description || 'No description available',
        sources: [websiteUrl]
      };
    }
    
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
          max_tokens: 2000,
          messages: [{
            role: 'user',
            content: `Extract company information from this website content for ${companyName}.

Website Content:
${scrapedData.content.substring(0, 8000)}

Extract the following in JSON format:
{
  "name": "company name",
  "description": "brief company description",
  "funding": {
    "total": "total funding raised",
    "lastRound": "last funding round details",
    "investors": ["list of investors"],
    "valuation": "latest valuation if mentioned"
  },
  "team": {
    "founders": ["founder names"],
    "size": "team size",
    "keyPeople": [{"name": "...", "role": "..."}]
  },
  "product": {
    "description": "what they build",
    "features": ["key features"],
    "customers": ["notable customers"]
  },
  "financials": {
    "revenue": "revenue if mentioned",
    "growth": "growth rate",
    "metrics": {}
  },
  "news": ["recent news or updates"]
}

IMPORTANT: Only include information explicitly found in the content. Use null for missing fields.`
          }]
        })
      });
      
      if (response.ok) {
        const data = await response.json();
        const content = data.content[0].text;
        
        // Try to parse JSON from response
        const jsonMatch = content.match(/\{[\s\S]*\}/);
        if (jsonMatch) {
          const extracted = JSON.parse(jsonMatch[0]);
          return {
            name: extracted.name || companyName,
            website: websiteUrl,
            description: extracted.description || '',
            funding: extracted.funding,
            team: extracted.team,
            product: extracted.product,
            financials: extracted.financials,
            news: extracted.news,
            sources: [websiteUrl]
          };
        }
      }
    } catch (error) {
      console.error('Claude extraction error:', error);
    }
    
    // Fallback
    return {
      name: companyName,
      website: websiteUrl,
      description: scrapedData.description || 'Company information',
      sources: [websiteUrl]
    };
  }
  
  /**
   * Store profile in database
   */
  private async storeProfile(profile: CompanyProfile): Promise<void> {
    try {
      await supabase
        .from('company_profiles')
        .upsert({
          company_name: profile.name,
          website_url: profile.website,
          profile_data: profile,
          scraped_at: new Date().toISOString()
        });
      
      console.log(`✅ Stored profile for ${profile.name}`);
    } catch (error) {
      console.error('Error storing profile:', error);
    }
  }
  
  /**
   * Scrape news and updates about a company
   */
  async scrapeCompanyNews(companyName: string): Promise<any[]> {
    if (!this.firecrawl) {
      return [];
    }
    
    try {
      // Search for news
      const newsUrls = [
        `https://www.google.com/search?q=${encodeURIComponent(companyName)}+news+funding`,
        `https://techcrunch.com/search/${encodeURIComponent(companyName)}`,
        `https://www.crunchbase.com/organization/${companyName.toLowerCase().replace(/\s+/g, '-')}`
      ];
      
      const news = [];
      for (const url of newsUrls) {
        try {
          const result = await this.firecrawl.scrapeUrl(url, {
            formats: ['markdown'],
            waitFor: 1000
          });
          
          if (result.data?.markdown) {
            // Extract news items (simplified)
            const lines = result.data.markdown.split('\n');
            const newsItems = lines
              .filter(line => line.includes(companyName))
              .slice(0, 5)
              .map(line => ({
                text: line.trim(),
                source: url
              }));
            news.push(...newsItems);
          }
        } catch (error) {
          console.log(`Could not scrape news from ${url}`);
        }
      }
      
      return news;
    } catch (error) {
      console.error('News scraping error:', error);
      return [];
    }
  }
}

export const firecrawlScraper = new FirecrawlScraper();