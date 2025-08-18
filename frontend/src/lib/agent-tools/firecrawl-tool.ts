/**
 * Firecrawl Tool for Agent
 * Coordinates with Tavily for comprehensive web data gathering
 */

import FirecrawlApp from '@mendable/firecrawl-js';

const FIRECRAWL_API_KEY = process.env.FIRECRAWL_API_KEY || '';

export interface FirecrawlToolResult {
  success: boolean;
  data?: {
    content: string;
    markdown?: string;
    metadata?: any;
    links?: string[];
    funding?: any;
    team?: any;
    product?: any;
    financials?: any;
  };
  error?: string;
  source: 'firecrawl';
}

export class FirecrawlTool {
  private firecrawl: FirecrawlApp | null = null;
  
  constructor() {
    if (FIRECRAWL_API_KEY) {
      this.firecrawl = new FirecrawlApp({ apiKey: FIRECRAWL_API_KEY });
    }
  }
  
  /**
   * Tool metadata for the agent
   */
  static metadata = {
    name: 'firecrawl_scrape',
    description: 'Scrape detailed information from company websites including funding, team, and product data',
    parameters: {
      url: 'string',
      depth: 'number (optional)',
      extractStructured: 'boolean (optional)'
    },
    when_to_use: 'When you need detailed company information, funding data, or to scrape specific website content',
    coordinates_with: ['tavily_search']
  };
  
  /**
   * Main tool execution
   */
  async execute(params: {
    url?: string;
    companyName?: string;
    depth?: number;
    extractStructured?: boolean;
  }): Promise<FirecrawlToolResult> {
    if (!this.firecrawl) {
      return {
        success: false,
        error: 'Firecrawl not configured',
        source: 'firecrawl'
      };
    }
    
    try {
      let targetUrl = params.url;
      
      // If no URL provided, try to find it
      if (!targetUrl && params.companyName) {
        targetUrl = await this.findCompanyWebsite(params.companyName);
      }
      
      if (!targetUrl) {
        return {
          success: false,
          error: 'No URL provided or found',
          source: 'firecrawl'
        };
      }
      
      console.log(`🔥 Firecrawl: Scraping ${targetUrl}...`);
      
      // Scrape the website - updated for new API
      const result = await this.firecrawl.scrapeUrl(targetUrl, {
        formats: ['markdown', 'html'],
        waitFor: 2000
      });
      
      // If structured extraction requested, extract key data
      let structuredData = {};
      if (params.extractStructured && result.data?.markdown) {
        structuredData = await this.extractStructuredData(result.data.markdown);
      }
      
      // Try to crawl important subpages if depth > 1
      let additionalContent = '';
      if (params.depth && params.depth > 1) {
        const subpages = await this.crawlSubpages(targetUrl, params.depth);
        additionalContent = subpages.join('\n\n');
      }
      
      return {
        success: true,
        data: {
          content: result.data?.content || '',
          markdown: result.data?.markdown || '',
          metadata: result.data?.metadata,
          links: result.data?.links,
          ...structuredData,
          ...(additionalContent && { additionalPages: additionalContent })
        },
        source: 'firecrawl'
      };
      
    } catch (error) {
      console.error('Firecrawl error:', error);
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Scraping failed',
        source: 'firecrawl'
      };
    }
  }
  
  /**
   * Find company website
   */
  private async findCompanyWebsite(companyName: string): Promise<string> {
    const cleanName = companyName.toLowerCase().replace(/\s+/g, '');
    return `https://${cleanName}.com`;
  }
  
  /**
   * Crawl subpages
   */
  private async crawlSubpages(baseUrl: string, depth: number): Promise<string[]> {
    if (!this.firecrawl) return [];
    
    const importantPaths = ['/about', '/team', '/investors', '/pricing', '/products'];
    const contents: string[] = [];
    
    for (const path of importantPaths.slice(0, depth - 1)) {
      try {
        const url = new URL(path, baseUrl).toString();
        const result = await this.firecrawl.scrapeUrl(url, {
          formats: ['markdown'],
          waitFor: 1000
        });
        
        if (result.data?.markdown) {
          contents.push(`## ${path}\n${result.data.markdown}`);
        }
      } catch (error) {
        // Page might not exist
      }
    }
    
    return contents;
  }
  
  /**
   * Extract structured data from content
   */
  private async extractStructuredData(content: string): Promise<any> {
    // Use regex patterns to extract key information
    const structured: any = {};
    
    // Look for funding information
    const fundingPattern = /\$[\d.]+[MB]/gi;
    const fundingMatches = content.match(fundingPattern);
    if (fundingMatches) {
      structured.funding = {
        mentions: fundingMatches,
        raw: fundingMatches.join(', ')
      };
    }
    
    // Look for team size
    const teamPattern = /(\d+)\+?\s*(employees?|people|team)/gi;
    const teamMatch = content.match(teamPattern);
    if (teamMatch) {
      structured.team = {
        size: teamMatch[0]
      };
    }
    
    // Look for customer mentions
    const customerPattern = /(([\d,]+)\+?\s*(customers?|users?|companies))/gi;
    const customerMatch = content.match(customerPattern);
    if (customerMatch) {
      structured.customers = customerMatch[0];
    }
    
    return structured;
  }
}

export const firecrawlTool = new FirecrawlTool();