/**
 * Enhanced CIM Scraper with Vision Capabilities
 * Extracts logos, product images, and detailed business model information
 */

import Anthropic from '@anthropic-ai/sdk';

const anthropic = new Anthropic({
  apiKey: process.env.CLAUDE_API_KEY!,
});

interface ProductInfo {
  name: string;
  description: string;
  pricing?: string;
  features?: string[];
  imageUrl?: string;
  category?: string;
}

interface CompanyVisualData {
  logo?: {
    url: string;
    colors: string[];
    style: string; // modern, classic, playful, etc.
  };
  products: ProductInfo[];
  screenshots: string[];
  brandColors: string[];
  visualIdentity: {
    style: string;
    maturity: string; // startup, growth, enterprise
    industry: string;
  };
}

interface EnhancedCIMData {
  company: {
    name: string;
    website: string;
    logo?: string;
    tagline?: string;
    founded?: string;
    headquarters?: string;
    employees?: string;
  };
  products: {
    portfolio: ProductInfo[];
    mainProduct?: string;
    productCategories: string[];
    pricingModel: string; // subscription, one-time, usage-based, freemium
    targetMarket: string;
  };
  businessModel: {
    revenueStreams: Array<{
      name: string;
      description: string;
      percentage?: number;
      growth?: string;
    }>;
    costStructure: Array<{
      category: string;
      percentage?: number;
      description?: string;
    }>;
    unitEconomics?: {
      cac?: number;
      ltv?: number;
      paybackPeriod?: number;
      grossMargin?: number;
    };
  };
  market: {
    tam?: string;
    sam?: string;
    som?: string;
    competitors: Array<{
      name: string;
      strengths: string[];
      marketShare?: string;
    }>;
    positioning: string;
  };
  technology: {
    stack: string[];
    proprietary: string[];
    patents?: string[];
    ai_ml_usage?: string;
  };
  visualData: CompanyVisualData;
}

export class EnhancedCIMScraper {
  private cache = new Map<string, EnhancedCIMData>();
  
  /**
   * Main entry point - scrapes company with vision analysis
   */
  async scrapeCompanyWithVision(
    companyName: string,
    websiteUrl?: string
  ): Promise<EnhancedCIMData> {
    // Check cache first
    const cacheKey = companyName.toLowerCase();
    if (this.cache.has(cacheKey)) {
      console.log(`Using cached data for ${companyName}`);
      return this.cache.get(cacheKey)!;
    }
    
    try {
      // Step 1: Find website if not provided
      if (!websiteUrl) {
        websiteUrl = await this.findCompanyWebsite(companyName);
      }
      
      // Step 2: Scrape website pages
      const pages = await this.scrapeWebsitePages(websiteUrl);
      
      // Step 3: Extract visual elements (logos, product images)
      const visualData = await this.extractVisualElements(pages);
      
      // Step 4: Analyze with vision API
      const visionAnalysis = await this.analyzeWithVision(visualData, companyName);
      
      // Step 5: Extract structured business data
      const businessData = await this.extractBusinessData(pages, companyName);
      
      // Step 6: Combine all data
      const enhancedData: EnhancedCIMData = {
        company: {
          name: companyName,
          website: websiteUrl,
          logo: visualData.logo?.url,
          ...businessData.company
        },
        products: {
          portfolio: visionAnalysis.products,
          mainProduct: visionAnalysis.products[0]?.name,
          productCategories: this.extractProductCategories(visionAnalysis.products),
          pricingModel: businessData.pricingModel || 'Unknown',
          targetMarket: businessData.targetMarket || 'B2B'
        },
        businessModel: {
          revenueStreams: this.extractRevenueStreams(businessData, visionAnalysis),
          costStructure: this.extractCostStructure(businessData),
          unitEconomics: businessData.unitEconomics
        },
        market: {
          tam: businessData.tam,
          sam: businessData.sam,
          som: businessData.som,
          competitors: businessData.competitors || [],
          positioning: businessData.positioning || ''
        },
        technology: {
          stack: businessData.techStack || [],
          proprietary: businessData.proprietaryTech || [],
          patents: businessData.patents,
          ai_ml_usage: businessData.aiUsage
        },
        visualData: visionAnalysis
      };
      
      // Cache the result
      this.cache.set(cacheKey, enhancedData);
      
      return enhancedData;
      
    } catch (error) {
      console.error(`Failed to scrape ${companyName}:`, error);
      throw error;
    }
  }
  
  /**
   * Find company website using search
   */
  private async findCompanyWebsite(companyName: string): Promise<string> {
    try {
      const response = await fetch('https://api.tavily.com/search', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          api_key: process.env.TAVILY_API_KEY,
          query: `${companyName} official website`,
          max_results: 3,
          search_depth: 'basic'
        })
      });
      
      if (response.ok) {
        const data = await response.json();
        // Extract the most likely official website
        const urls = data.results?.map((r: any) => r.url) || [];
        const officialUrl = urls.find((url: string) => 
          !url.includes('wikipedia') && 
          !url.includes('crunchbase') &&
          !url.includes('linkedin')
        );
        return officialUrl || urls[0];
      }
    } catch (error) {
      console.error('Failed to find website:', error);
    }
    return `https://${companyName.toLowerCase().replace(/\s+/g, '')}.com`;
  }
  
  /**
   * Scrape website pages
   */
  private async scrapeWebsitePages(websiteUrl: string): Promise<any[]> {
    const pages = [];
    const pagesToScrape = [
      '',
      '/about',
      '/products',
      '/pricing',
      '/solutions',
      '/platform',
      '/technology'
    ];
    
    for (const path of pagesToScrape) {
      try {
        const url = `${websiteUrl}${path}`;
        const response = await fetch(url);
        if (response.ok) {
          const html = await response.text();
          pages.push({
            url,
            path,
            html,
            images: this.extractImageUrls(html, websiteUrl)
          });
        }
      } catch (error) {
        // Silently skip pages that don't exist
      }
    }
    
    return pages;
  }
  
  /**
   * Extract image URLs from HTML
   */
  private extractImageUrls(html: string, baseUrl: string): string[] {
    const imageUrls: string[] = [];
    const imgRegex = /<img[^>]+src=["']([^"']+)["']/gi;
    let match;
    
    while ((match = imgRegex.exec(html)) !== null) {
      let url = match[1];
      // Convert relative URLs to absolute
      if (url.startsWith('/')) {
        url = baseUrl + url;
      } else if (!url.startsWith('http')) {
        url = baseUrl + '/' + url;
      }
      imageUrls.push(url);
    }
    
    // Also look for background images in style attributes
    const bgRegex = /background-image:\s*url\(['"]?([^'")]+)['"]?\)/gi;
    while ((match = bgRegex.exec(html)) !== null) {
      let url = match[1];
      if (url.startsWith('/')) {
        url = baseUrl + url;
      }
      imageUrls.push(url);
    }
    
    return imageUrls;
  }
  
  /**
   * Extract visual elements from pages
   */
  private async extractVisualElements(pages: any[]): Promise<CompanyVisualData> {
    const visualData: CompanyVisualData = {
      products: [],
      screenshots: [],
      brandColors: [],
      visualIdentity: {
        style: 'modern',
        maturity: 'startup',
        industry: 'technology'
      }
    };
    
    // Find logo
    for (const page of pages) {
      const logoUrls = page.images.filter((url: string) => 
        url.includes('logo') || 
        url.includes('brand') ||
        url.includes('icon')
      );
      
      if (logoUrls.length > 0) {
        visualData.logo = {
          url: logoUrls[0],
          colors: [],
          style: 'modern'
        };
        break;
      }
    }
    
    // Find product images
    for (const page of pages) {
      if (page.path.includes('product') || page.path.includes('solution')) {
        const productImages = page.images.filter((url: string) => 
          url.includes('product') ||
          url.includes('feature') ||
          url.includes('screenshot') ||
          url.includes('dashboard')
        );
        visualData.screenshots.push(...productImages.slice(0, 5));
      }
    }
    
    return visualData;
  }
  
  /**
   * Analyze images with Claude Vision
   */
  private async analyzeWithVision(
    visualData: CompanyVisualData, 
    companyName: string
  ): Promise<CompanyVisualData> {
    try {
      // Prepare images for vision analysis
      const imagesToAnalyze = [
        visualData.logo?.url,
        ...visualData.screenshots.slice(0, 3)
      ].filter(Boolean);
      
      if (imagesToAnalyze.length === 0) {
        return visualData;
      }
      
      // Use Claude to analyze the images
      const prompt = `Analyze these images from ${companyName}'s website and extract:
1. Product names and descriptions visible in screenshots
2. UI/UX style and design maturity
3. Target market based on visual design
4. Key features visible in product screenshots
5. Pricing tiers if visible
6. Brand colors and visual identity

Provide a detailed analysis of what products and services this company offers based on the visual evidence.`;
      
      const response = await anthropic.messages.create({
        model: 'claude-3-5-sonnet-20241022',
        max_tokens: 2000,
        messages: [
          {
            role: 'user',
            content: [
              { type: 'text', text: prompt },
              ...imagesToAnalyze.map(url => ({
                type: 'image' as const,
                source: {
                  type: 'url' as const,
                  url: url!
                }
              }))
            ]
          }
        ]
      });
      
      // Parse the response to extract product information
      const analysis = response.content[0].type === 'text' ? response.content[0].text : '';
      
      // Extract products from the analysis
      visualData.products = this.parseProductsFromAnalysis(analysis);
      
      // Extract visual identity
      visualData.visualIdentity = this.parseVisualIdentity(analysis);
      
      // Extract brand colors
      visualData.brandColors = this.parseBrandColors(analysis);
      
    } catch (error) {
      console.error('Vision analysis failed:', error);
    }
    
    return visualData;
  }
  
  /**
   * Parse products from vision analysis
   */
  private parseProductsFromAnalysis(analysis: string): ProductInfo[] {
    const products: ProductInfo[] = [];
    
    // Simple extraction - would be more sophisticated in production
    const productPattern = /Product:\s*([^:]+):\s*([^.]+)/gi;
    let match;
    
    while ((match = productPattern.exec(analysis)) !== null) {
      products.push({
        name: match[1].trim(),
        description: match[2].trim()
      });
    }
    
    // If no specific products found, extract from general description
    if (products.length === 0 && analysis.includes('dashboard')) {
      products.push({
        name: 'Analytics Dashboard',
        description: 'Data visualization and analytics platform',
        category: 'Analytics'
      });
    }
    
    return products;
  }
  
  /**
   * Parse visual identity from analysis
   */
  private parseVisualIdentity(analysis: string): any {
    const identity = {
      style: 'modern',
      maturity: 'growth',
      industry: 'technology'
    };
    
    // Detect style
    if (analysis.includes('minimalist') || analysis.includes('clean')) {
      identity.style = 'minimalist';
    } else if (analysis.includes('playful') || analysis.includes('colorful')) {
      identity.style = 'playful';
    } else if (analysis.includes('enterprise') || analysis.includes('professional')) {
      identity.style = 'enterprise';
    }
    
    // Detect maturity
    if (analysis.includes('startup') || analysis.includes('early-stage')) {
      identity.maturity = 'startup';
    } else if (analysis.includes('enterprise') || analysis.includes('established')) {
      identity.maturity = 'enterprise';
    }
    
    return identity;
  }
  
  /**
   * Parse brand colors from analysis
   */
  private parseBrandColors(analysis: string): string[] {
    const colors: string[] = [];
    const colorPattern = /#[0-9A-Fa-f]{6}/g;
    const matches = analysis.match(colorPattern);
    
    if (matches) {
      colors.push(...matches);
    }
    
    // Also look for color names
    const colorNames = ['blue', 'green', 'red', 'purple', 'orange', 'yellow'];
    colorNames.forEach(color => {
      if (analysis.toLowerCase().includes(color)) {
        colors.push(color);
      }
    });
    
    return [...new Set(colors)]; // Remove duplicates
  }
  
  /**
   * Extract business data from pages
   */
  private async extractBusinessData(pages: any[], companyName: string): Promise<any> {
    // Combine all page content
    const allContent = pages.map(p => p.html).join(' ');
    
    // Use Claude to extract structured data
    const prompt = `Extract the following business information from this website content for ${companyName}:
- Company founding year
- Headquarters location
- Number of employees
- Target market (B2B/B2C/B2B2C)
- Pricing model (subscription/usage-based/one-time)
- Key competitors mentioned
- Technology stack mentioned
- Revenue model
- Customer segments

Return as structured JSON.`;
    
    try {
      const response = await anthropic.messages.create({
        model: 'claude-3-haiku-20240307',
        max_tokens: 2000,
        messages: [
          {
            role: 'user',
            content: `${prompt}\n\nWebsite content:\n${allContent.substring(0, 10000)}`
          }
        ]
      });
      
      const text = response.content[0].type === 'text' ? response.content[0].text : '{}';
      return JSON.parse(text);
    } catch (error) {
      console.error('Failed to extract business data:', error);
      return {};
    }
  }
  
  /**
   * Extract product categories
   */
  private extractProductCategories(products: ProductInfo[]): string[] {
    const categories = new Set<string>();
    products.forEach(p => {
      if (p.category) categories.add(p.category);
    });
    return Array.from(categories);
  }
  
  /**
   * Extract revenue streams
   */
  private extractRevenueStreams(businessData: any, visionData: CompanyVisualData): any[] {
    const streams = [];
    
    // Add product-based revenue streams
    visionData.products.forEach(product => {
      streams.push({
        name: product.name,
        description: `Revenue from ${product.name} ${product.pricing || 'subscriptions'}`,
        percentage: Math.floor(100 / visionData.products.length)
      });
    });
    
    // Add additional streams from business data
    if (businessData.revenueStreams) {
      streams.push(...businessData.revenueStreams);
    }
    
    return streams;
  }
  
  /**
   * Extract cost structure
   */
  private extractCostStructure(businessData: any): any[] {
    // Default SaaS cost structure if not found
    return businessData.costStructure || [
      { category: 'Engineering & Product', percentage: 40 },
      { category: 'Sales & Marketing', percentage: 35 },
      { category: 'General & Administrative', percentage: 15 },
      { category: 'Infrastructure & Operations', percentage: 10 }
    ];
  }
  
  /**
   * Generate revenue segmentation data for Sankey diagram
   */
  generateSankeyData(cimData: EnhancedCIMData): {
    nodes: any[];
    links: any[];
  } {
    const nodes = [];
    const links = [];
    
    // Add revenue stream nodes
    cimData.businessModel.revenueStreams.forEach((stream, i) => {
      nodes.push({
        id: `revenue-${i}`,
        name: stream.name,
        value: stream.percentage || 25
      });
    });
    
    // Add total revenue node
    nodes.push({
      id: 'total-revenue',
      name: 'Total Revenue',
      value: 100
    });
    
    // Connect revenue streams to total
    cimData.businessModel.revenueStreams.forEach((stream, i) => {
      links.push({
        source: `revenue-${i}`,
        target: 'total-revenue',
        value: stream.percentage || 25
      });
    });
    
    // Add cost nodes
    cimData.businessModel.costStructure.forEach((cost, i) => {
      nodes.push({
        id: `cost-${i}`,
        name: cost.category,
        value: cost.percentage || 25
      });
      
      links.push({
        source: 'total-revenue',
        target: `cost-${i}`,
        value: cost.percentage || 25
      });
    });
    
    // Add profit node
    const totalCosts = cimData.businessModel.costStructure.reduce(
      (sum, cost) => sum + (cost.percentage || 0), 0
    );
    const profit = 100 - totalCosts;
    
    nodes.push({
      id: 'profit',
      name: 'Operating Profit',
      value: profit
    });
    
    links.push({
      source: 'total-revenue',
      target: 'profit',
      value: profit
    });
    
    return { nodes, links };
  }
}

// Export singleton instance
export const enhancedCIMScraper = new EnhancedCIMScraper();