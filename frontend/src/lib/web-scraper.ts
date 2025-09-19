import { createClient } from '@supabase/supabase-js';

const supabase = createClient(
  process.env.NEXT_PUBLIC_SUPABASE_URL!,
  process.env.SUPABASE_SERVICE_ROLE_KEY!
);

interface ScrapedContent {
  url: string;
  title: string;
  content: string;
  images: ImageData[];
  marketMaps: MarketMap[];
  metadata: any;
}

interface ImageData {
  url: string;
  alt: string;
  caption?: string;
  analysis?: string;
}

interface MarketMap {
  title: string;
  imageUrl: string;
  companies: string[];
  categories: string[];
  analysis: string;
}

export class WebScraper {
  constructor() {}

  /**
   * Scrape a webpage and extract content including images
   */
  async scrapeUrl(url: string): Promise<ScrapedContent> {
    try {
      // For server-side rendering, we'll use fetch to get HTML
      const response = await fetch(url, {
        headers: {
          'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
      });
      
      const html = await response.text();
      
      // Extract content from HTML
      const content = this.extractTextContent(html);
      const images = this.extractImages(html, url);
      const marketMaps = await this.identifyMarketMaps(images, content);
      
      // Extract metadata
      const title = this.extractTitle(html);
      const metadata = this.extractMetadata(html);
      
      // Store in database for caching
      await this.cacheScrapedContent(url, {
        url,
        title,
        content,
        images,
        marketMaps,
        metadata
      });
      
      return {
        url,
        title,
        content,
        images,
        marketMaps,
        metadata
      };
    } catch (error) {
      console.error('Error scraping URL:', error);
      throw error;
    }
  }

  /**
   * Extract text content from HTML
   */
  private extractTextContent(html: string): string {
    // Remove script and style tags
    let text = html.replace(/<script\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/script>/gi, '');
    text = text.replace(/<style\b[^<]*(?:(?!<\/style>)<[^<]*)*<\/style>/gi, '');
    
    // Extract text from common content tags
    const contentPatterns = [
      /<article[^>]*>([\s\S]*?)<\/article>/gi,
      /<main[^>]*>([\s\S]*?)<\/main>/gi,
      /<div[^>]*class="[^"]*content[^"]*"[^>]*>([\s\S]*?)<\/div>/gi,
      /<p[^>]*>([\s\S]*?)<\/p>/gi
    ];
    
    let extractedText = '';
    for (const pattern of contentPatterns) {
      const matches = html.matchAll(pattern);
      for (const match of matches) {
        extractedText += this.stripHtmlTags(match[1]) + '\n\n';
      }
    }
    
    return extractedText.trim();
  }

  /**
   * Extract images from HTML
   */
  private extractImages(html: string, baseUrl: string): ImageData[] {
    const images: ImageData[] = [];
    const imgPattern = /<img[^>]+src="([^"]+)"[^>]*>/gi;
    const matches = html.matchAll(imgPattern);
    
    for (const match of matches) {
      const imgTag = match[0];
      const src = match[1];
      
      // Make URL absolute
      const absoluteUrl = this.makeAbsoluteUrl(src, baseUrl);
      
      // Extract alt text and other attributes
      const altMatch = imgTag.match(/alt="([^"]*)"/);
      const alt = altMatch ? altMatch[1] : '';
      
      // Check if this might be a market map
      const isMarketMap = this.isLikelyMarketMap(imgTag, alt);
      
      if (isMarketMap || this.isRelevantImage(alt, src)) {
        images.push({
          url: absoluteUrl,
          alt,
          caption: this.extractImageCaption(html, imgTag)
        });
      }
    }
    
    return images;
  }

  /**
   * Identify market maps from images
   */
  private async identifyMarketMaps(images: ImageData[], content: string): Promise<MarketMap[]> {
    const marketMaps: MarketMap[] = [];
    
    for (const image of images) {
      if (this.isLikelyMarketMap(image.url, image.alt)) {
        // Extract companies and categories from surrounding text
        const companies = this.extractCompaniesFromContext(content, image.alt);
        const categories = this.extractCategoriesFromContext(content, image.alt);
        
        marketMaps.push({
          title: image.alt || 'Market Map',
          imageUrl: image.url,
          companies,
          categories,
          analysis: await this.analyzeMarketMapImage(image.url)
        });
      }
    }
    
    return marketMaps;
  }

  /**
   * Check if an image is likely a market map
   */
  private isLikelyMarketMap(imgTag: string, alt: string): boolean {
    const keywords = ['market map', 'landscape', 'ecosystem', 'sector map', 'competitive', 'matrix', 'quadrant'];
    const combinedText = (imgTag + ' ' + alt).toLowerCase();
    
    return keywords.some(keyword => combinedText.includes(keyword));
  }

  /**
   * Check if an image is relevant for analysis
   */
  private isRelevantImage(alt: string, src: string): boolean {
    const relevantKeywords = ['chart', 'graph', 'diagram', 'map', 'analysis', 'growth', 'market'];
    const combinedText = (alt + ' ' + src).toLowerCase();
    
    return relevantKeywords.some(keyword => combinedText.includes(keyword));
  }

  /**
   * Extract image caption from surrounding HTML
   */
  private extractImageCaption(html: string, imgTag: string): string {
    // Look for figcaption or nearby text
    const imgIndex = html.indexOf(imgTag);
    const nearbyHtml = html.substring(Math.max(0, imgIndex - 500), imgIndex + 500);
    
    const figcaptionMatch = nearbyHtml.match(/<figcaption[^>]*>([\s\S]*?)<\/figcaption>/i);
    if (figcaptionMatch) {
      return this.stripHtmlTags(figcaptionMatch[1]);
    }
    
    return '';
  }

  /**
   * Extract companies from content context
   */
  private extractCompaniesFromContext(content: string, imageContext: string): string[] {
    const companies: string[] = [];
    
    // Look for company name patterns
    const companyPattern = /\b[A-Z][a-zA-Z]+(?:Corp|Inc|Ltd|Labs|AI|Tech|Bio|Financial|Health|Data|Cloud|Robotics)\b/g;
    const matches = content.matchAll(companyPattern);
    
    for (const match of matches) {
      if (!companies.includes(match[0])) {
        companies.push(match[0]);
      }
      if (companies.length >= 20) break; // Limit to 20 companies
    }
    
    return companies;
  }

  /**
   * Extract categories from content context
   */
  private extractCategoriesFromContext(content: string, imageContext: string): string[] {
    const categories: string[] = [];
    const categoryKeywords = [
      'Infrastructure', 'Applications', 'Platform', 'Analytics',
      'Security', 'Data', 'API', 'Integration', 'Automation',
      'Intelligence', 'Management', 'Operations', 'Development'
    ];
    
    for (const keyword of categoryKeywords) {
      if (content.includes(keyword)) {
        categories.push(keyword);
      }
    }
    
    return categories;
  }

  /**
   * Analyze market map image using vision capabilities
   */
  private async analyzeMarketMapImage(imageUrl: string): Promise<string> {
    // This would integrate with vision API
    // For now, return a placeholder analysis
    return `Market map identified at ${imageUrl}. Contains sector categorization and competitive landscape. Further vision analysis required for detailed extraction.`;
  }

  /**
   * Extract title from HTML
   */
  private extractTitle(html: string): string {
    const titleMatch = html.match(/<title[^>]*>([\s\S]*?)<\/title>/i);
    if (titleMatch) {
      return this.stripHtmlTags(titleMatch[1]);
    }
    
    const h1Match = html.match(/<h1[^>]*>([\s\S]*?)<\/h1>/i);
    if (h1Match) {
      return this.stripHtmlTags(h1Match[1]);
    }
    
    return 'Untitled';
  }

  /**
   * Extract metadata from HTML
   */
  private extractMetadata(html: string): any {
    const metadata: any = {};
    
    // Extract meta tags
    const metaPattern = /<meta\s+(?:name|property)="([^"]+)"\s+content="([^"]+)"/gi;
    const matches = html.matchAll(metaPattern);
    
    for (const match of matches) {
      metadata[match[1]] = match[2];
    }
    
    // Extract author
    const authorMatch = html.match(/(?:author|by|written by)[:\s]+([^<\n]+)/i);
    if (authorMatch) {
      metadata.author = authorMatch[1].trim();
    }
    
    // Extract date
    const dateMatch = html.match(/(?:published|date)[:\s]+([^<\n]+)/i);
    if (dateMatch) {
      metadata.publishDate = dateMatch[1].trim();
    }
    
    return metadata;
  }

  /**
   * Strip HTML tags from text
   */
  private stripHtmlTags(html: string): string {
    return html.replace(/<[^>]*>/g, '').trim();
  }

  /**
   * Make URL absolute
   */
  private makeAbsoluteUrl(url: string, baseUrl: string): string {
    if (url.startsWith('http://') || url.startsWith('https://')) {
      return url;
    }
    
    if (url.startsWith('//')) {
      return 'https:' + url;
    }
    
    if (url.startsWith('/')) {
      const base = new URL(baseUrl);
      return base.origin + url;
    }
    
    // Relative URL
    const base = new URL(baseUrl);
    const pathParts = base.pathname.split('/');
    pathParts.pop(); // Remove filename
    return base.origin + pathParts.join('/') + '/' + url;
  }

  /**
   * Cache scraped content in database
   */
  private async cacheScrapedContent(url: string, content: ScrapedContent): Promise<void> {
    try {
      await supabase
        .from('agent_market_intelligence')
        .insert({
          data_type: 'scraped_content',
          data_point: content,
          source: url,
          confidence_score: 90,
          expires_at: new Date(Date.now() + 7 * 24 * 60 * 60 * 1000) // 7 days
        });
    } catch (error) {
      console.error('Error caching scraped content:', error);
    }
  }

  /**
   * Scrape Medium article for market analysis
   */
  async scrapeMediumArticle(url: string): Promise<{
    title: string;
    content: string;
    author: string;
    marketInsights: string[];
    companies: string[];
  }> {
    const scraped = await this.scrapeUrl(url);
    
    // Extract market insights
    const marketInsights: string[] = [];
    const insightPatterns = [
      /market (?:size|opportunity) (?:is|of) \$?[\d.]+[BMT]/gi,
      /growing at [\d.]+% (?:CAGR|annually)/gi,
      /valued at \$?[\d.]+[BMT]/gi,
      /TAM of \$?[\d.]+[BMT]/gi
    ];
    
    for (const pattern of insightPatterns) {
      const matches = scraped.content.matchAll(pattern);
      for (const match of matches) {
        marketInsights.push(match[0]);
      }
    }
    
    return {
      title: scraped.title,
      content: scraped.content,
      author: scraped.metadata.author || 'Unknown',
      marketInsights,
      companies: this.extractCompaniesFromContext(scraped.content, '')
    };
  }

  /**
   * Analyze a screenshot or image for market maps
   */
  async analyzeScreenshot(imagePath: string): Promise<{
    type: string;
    companies: string[];
    categories: string[];
    insights: string;
  }> {
    // This would integrate with vision API to analyze screenshots
    // For now, return structured placeholder
    return {
      type: 'market_map',
      companies: [],
      categories: [],
      insights: 'Screenshot analysis requires vision API integration'
    };
  }
}

// Export singleton instance
export const webScraper = new WebScraper();