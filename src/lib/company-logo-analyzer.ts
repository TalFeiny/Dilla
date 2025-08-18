import Anthropic from '@anthropic-ai/sdk';
import { webScraper } from './web-scraper';

const anthropic = new Anthropic({
  apiKey: process.env.ANTHROPIC_API_KEY || process.env.CLAUDE_API_KEY || '',
});

interface LogoAnalysisResult {
  totalLogos: number;
  identifiedCompanies: Array<{
    name: string;
    confidence: number;
    category: 'customer' | 'partner' | 'investor' | 'certification' | 'unknown';
    recognitionMethod: 'text' | 'logo' | 'context';
  }>;
  logoQuality: {
    overallScore: number; // 0-100
    factors: {
      visibility: number;
      prominence: number;
      recognizability: number;
      brand_strength: number;
    };
  };
  sections: Array<{
    type: string; // 'customers', 'partners', 'investors', etc.
    logoCount: number;
    companies: string[];
  }>;
  insights: {
    hasCustomerLogos: boolean;
    hasPartnerLogos: boolean;
    hasInvestorLogos: boolean;
    customerTier: 'enterprise' | 'mid-market' | 'smb' | 'mixed' | 'unknown';
    brandCredibility: 'high' | 'medium' | 'low';
  };
}

/**
 * Company Logo Analyzer - Uses Claude Vision to analyze logos on company websites
 */
export class CompanyLogoAnalyzer {
  /**
   * Analyze logos on company website using vision API
   */
  async analyzeCompanyLogos(
    companyName: string, 
    websiteUrl?: string
  ): Promise<LogoAnalysisResult> {
    console.log(`Analyzing logos for ${companyName}...`);
    
    // Step 1: Find relevant pages with logos
    const logoPages = await this.findLogoPages(companyName, websiteUrl);
    
    // Step 2: Capture screenshots of logo sections
    const screenshots = await this.captureLogoSections(logoPages);
    
    // Step 3: Analyze each screenshot with Claude Vision
    const analysisResults = await Promise.all(
      screenshots.map(screenshot => this.analyzeLogoImage(screenshot))
    );
    
    // Step 4: Aggregate and structure results
    const aggregatedResults = this.aggregateAnalysis(analysisResults);
    
    // Step 5: Generate insights
    const insights = this.generateInsights(aggregatedResults);
    
    return {
      ...aggregatedResults,
      insights
    };
  }
  
  /**
   * Find pages likely to contain logos (customers, partners, about)
   */
  private async findLogoPages(
    companyName: string,
    websiteUrl?: string
  ): Promise<string[]> {
    const baseUrl = websiteUrl || await this.findCompanyWebsite(companyName);
    const logoPages: string[] = [baseUrl];
    
    // Common pages that contain logos
    const potentialPaths = [
      '/customers',
      '/clients',
      '/partners',
      '/about',
      '/about-us',
      '/case-studies',
      '/testimonials',
      '/portfolio',
      '/our-customers',
      '/our-clients',
      '/success-stories',
      '/who-we-serve',
      '/industries'
    ];
    
    // Try to find these pages
    for (const path of potentialPaths) {
      try {
        const url = new URL(path, baseUrl).toString();
        const response = await fetch(url, { method: 'HEAD' });
        if (response.ok) {
          logoPages.push(url);
        }
      } catch (error) {
        // Page doesn't exist
      }
    }
    
    return logoPages;
  }
  
  /**
   * Capture screenshots of sections likely to contain logos
   */
  private async captureLogoSections(urls: string[]): Promise<Array<{
    url: string;
    imageData: string;
    context: string;
  }>> {
    const screenshots: Array<{
      url: string;
      imageData: string;
      context: string;
    }> = [];
    
    for (const url of urls) {
      try {
        // Scrape page content
        const pageData = await webScraper.scrapeUrl(url);
        
        // Look for logo sections in HTML
        const logoSections = this.extractLogoSections(pageData.content);
        
        // For each section, we'd capture a screenshot
        // In production, this would use Puppeteer or similar
        // For now, we'll analyze the HTML structure
        
        screenshots.push({
          url,
          imageData: '', // Would be base64 screenshot
          context: logoSections.join('\n')
        });
      } catch (error) {
        console.error(`Error capturing ${url}:`, error);
      }
    }
    
    return screenshots;
  }
  
  /**
   * Extract sections likely to contain logos from HTML
   */
  private extractLogoSections(html: string): string[] {
    const sections: string[] = [];
    
    // Patterns that indicate logo sections
    const patterns = [
      /<section[^>]*class="[^"]*(?:customer|client|partner|logo|brand)[^"]*"[^>]*>([\s\S]*?)<\/section>/gi,
      /<div[^>]*class="[^"]*(?:customer|client|partner|logo|brand)[^"]*"[^>]*>([\s\S]*?)<\/div>/gi,
      /<div[^>]*id="[^"]*(?:customer|client|partner|logo|brand)[^"]*"[^>]*>([\s\S]*?)<\/div>/gi
    ];
    
    for (const pattern of patterns) {
      const matches = html.matchAll(pattern);
      for (const match of matches) {
        sections.push(match[0]);
      }
    }
    
    // Also look for img tags with logo indicators
    const imgPattern = /<img[^>]*(?:alt|title|src)="[^"]*(?:customer|client|partner|logo)[^"]*"[^>]*>/gi;
    const imgMatches = html.matchAll(imgPattern);
    for (const match of imgMatches) {
      sections.push(match[0]);
    }
    
    return sections;
  }
  
  /**
   * Analyze logo image with Claude Vision API
   */
  private async analyzeLogoImage(screenshot: {
    url: string;
    imageData: string;
    context: string;
  }): Promise<any> {
    // If we have actual image data, use vision API
    if (screenshot.imageData) {
      const prompt = `
Analyze this image for company logos and brand marks.

For each logo you can identify:
1. Company name (if recognizable)
2. Logo position and prominence
3. Category (customer, partner, investor, certification)
4. Quality and visibility of the logo

Also evaluate:
- Total number of logos visible
- Overall presentation quality
- Brand tier (enterprise, mid-market, SMB)
- Credibility signals

Provide a structured analysis in JSON format.`;

      try {
        const response = await anthropic.messages.create({
          model: 'claude-3-5-sonnet-20241022',
          max_tokens: 4096,
          messages: [{
            role: 'user',
            content: [
              {
                type: 'image',
                source: {
                  type: 'base64',
                  media_type: 'image/png',
                  data: screenshot.imageData
                }
              },
              {
                type: 'text',
                text: prompt
              }
            ]
          }]
        });
        
        const text = response.content[0].type === 'text' ? response.content[0].text : '';
        const jsonMatch = text.match(/\{[\s\S]*\}/);
        if (jsonMatch) {
          return JSON.parse(jsonMatch[0]);
        }
      } catch (error) {
        console.error('Error analyzing with vision API:', error);
      }
    }
    
    // Fallback: Analyze HTML context
    return this.analyzeHTMLForLogos(screenshot.context);
  }
  
  /**
   * Analyze HTML for logo information (fallback when no screenshots)
   */
  private async analyzeHTMLForLogos(html: string): Promise<any> {
    const logos: Array<{
      name: string;
      confidence: number;
      category: string;
    }> = [];
    
    // Extract alt text and titles from images
    const imgPattern = /<img[^>]*(?:alt|title)="([^"]*)"[^>]*>/gi;
    const matches = html.matchAll(imgPattern);
    
    for (const match of matches) {
      const text = match[1];
      if (text && !text.toLowerCase().includes('logo') && text.length > 2) {
        logos.push({
          name: text,
          confidence: 0.6,
          category: this.categorizeFromContext(html, text)
        });
      }
    }
    
    // Look for company names in text near images
    const companyPatterns = [
      /(?:customers?|clients?|partners?|trusted by|used by|powered by)[^<]*?([A-Z][a-zA-Z0-9\s&]{2,30})/gi,
      /([A-Z][a-zA-Z0-9\s&]{2,30})(?:\s+logo|\s+brand)/gi
    ];
    
    for (const pattern of companyPatterns) {
      const textMatches = html.matchAll(pattern);
      for (const match of textMatches) {
        const companyName = match[1].trim();
        if (this.isLikelyCompanyName(companyName)) {
          logos.push({
            name: companyName,
            confidence: 0.7,
            category: this.categorizeFromContext(html, companyName)
          });
        }
      }
    }
    
    return {
      logos,
      totalCount: logos.length,
      htmlBased: true
    };
  }
  
  /**
   * Categorize logo based on surrounding context
   */
  private categorizeFromContext(html: string, name: string): string {
    const lowerHtml = html.toLowerCase();
    const lowerName = name.toLowerCase();
    const contextWindow = 200;
    
    const index = lowerHtml.indexOf(lowerName);
    if (index === -1) return 'unknown';
    
    const context = lowerHtml.substring(
      Math.max(0, index - contextWindow),
      Math.min(lowerHtml.length, index + contextWindow)
    );
    
    if (context.includes('customer') || context.includes('client')) {
      return 'customer';
    } else if (context.includes('partner') || context.includes('integration')) {
      return 'partner';
    } else if (context.includes('investor') || context.includes('backed by')) {
      return 'investor';
    } else if (context.includes('certif') || context.includes('compliance')) {
      return 'certification';
    }
    
    return 'unknown';
  }
  
  /**
   * Check if a string is likely a company name
   */
  private isLikelyCompanyName(text: string): boolean {
    // Basic heuristics for company names
    if (text.length < 3 || text.length > 50) return false;
    if (!/[A-Z]/.test(text)) return false; // Must have at least one capital
    if (/^[0-9]+$/.test(text)) return false; // Not just numbers
    
    // Common non-company words to filter out
    const excludeWords = [
      'logo', 'image', 'icon', 'banner', 'header', 'footer',
      'click', 'here', 'more', 'less', 'view', 'see'
    ];
    
    const lowerText = text.toLowerCase();
    return !excludeWords.some(word => lowerText.includes(word));
  }
  
  /**
   * Aggregate analysis from multiple sources
   */
  private aggregateAnalysis(results: any[]): any {
    const allLogos: Map<string, {
      name: string;
      confidence: number;
      category: string;
      count: number;
    }> = new Map();
    
    // Aggregate all found logos
    for (const result of results) {
      if (result.logos) {
        for (const logo of result.logos) {
          const key = logo.name.toLowerCase();
          if (allLogos.has(key)) {
            const existing = allLogos.get(key)!;
            existing.count++;
            existing.confidence = Math.max(existing.confidence, logo.confidence);
          } else {
            allLogos.set(key, {
              name: logo.name,
              confidence: logo.confidence,
              category: logo.category,
              count: 1
            });
          }
        }
      }
    }
    
    // Convert to array and sort by confidence
    const identifiedCompanies = Array.from(allLogos.values())
      .sort((a, b) => b.confidence - a.confidence)
      .map(logo => ({
        name: logo.name,
        confidence: logo.confidence,
        category: logo.category as any,
        recognitionMethod: 'context' as const
      }));
    
    // Group by sections
    const sections = this.groupByCategory(identifiedCompanies);
    
    // Calculate quality score
    const logoQuality = this.calculateQualityScore(identifiedCompanies, results);
    
    return {
      totalLogos: identifiedCompanies.length,
      identifiedCompanies,
      logoQuality,
      sections
    };
  }
  
  /**
   * Group logos by category
   */
  private groupByCategory(companies: any[]): any[] {
    const groups = new Map<string, any>();
    
    for (const company of companies) {
      if (!groups.has(company.category)) {
        groups.set(company.category, {
          type: company.category,
          logoCount: 0,
          companies: []
        });
      }
      
      const group = groups.get(company.category)!;
      group.logoCount++;
      group.companies.push(company.name);
    }
    
    return Array.from(groups.values());
  }
  
  /**
   * Calculate logo quality score
   */
  private calculateQualityScore(companies: any[], rawResults: any[]): any {
    const factors = {
      visibility: 0,
      prominence: 0,
      recognizability: 0,
      brand_strength: 0
    };
    
    // Visibility: based on number of logos found
    factors.visibility = Math.min(100, companies.length * 10);
    
    // Prominence: based on confidence scores
    const avgConfidence = companies.length > 0
      ? companies.reduce((sum, c) => sum + c.confidence, 0) / companies.length
      : 0;
    factors.prominence = avgConfidence * 100;
    
    // Recognizability: based on known company detection
    const knownCompanies = companies.filter(c => 
      c.confidence > 0.7 && c.category !== 'unknown'
    );
    factors.recognizability = companies.length > 0
      ? (knownCompanies.length / companies.length) * 100
      : 0;
    
    // Brand strength: based on customer category presence
    const customerLogos = companies.filter(c => c.category === 'customer');
    factors.brand_strength = Math.min(100, customerLogos.length * 15);
    
    const overallScore = (
      factors.visibility * 0.2 +
      factors.prominence * 0.3 +
      factors.recognizability * 0.2 +
      factors.brand_strength * 0.3
    );
    
    return {
      overallScore,
      factors
    };
  }
  
  /**
   * Generate insights from analysis
   */
  private generateInsights(analysis: any): any {
    const hasCustomerLogos = analysis.sections.some(
      (s: any) => s.type === 'customer' && s.logoCount > 0
    );
    const hasPartnerLogos = analysis.sections.some(
      (s: any) => s.type === 'partner' && s.logoCount > 0
    );
    const hasInvestorLogos = analysis.sections.some(
      (s: any) => s.type === 'investor' && s.logoCount > 0
    );
    
    // Determine customer tier based on recognized companies
    const customerTier = this.determineCustomerTier(
      analysis.identifiedCompanies.filter((c: any) => c.category === 'customer')
    );
    
    // Determine brand credibility
    let brandCredibility: 'high' | 'medium' | 'low' = 'low';
    if (analysis.logoQuality.overallScore > 70) {
      brandCredibility = 'high';
    } else if (analysis.logoQuality.overallScore > 40) {
      brandCredibility = 'medium';
    }
    
    return {
      hasCustomerLogos,
      hasPartnerLogos,
      hasInvestorLogos,
      customerTier,
      brandCredibility
    };
  }
  
  /**
   * Determine customer tier from company names
   */
  private determineCustomerTier(customers: any[]): string {
    if (customers.length === 0) return 'unknown';
    
    const enterpriseIndicators = [
      'Microsoft', 'Google', 'Amazon', 'Apple', 'IBM', 'Oracle',
      'Salesforce', 'SAP', 'Adobe', 'Intel', 'Cisco', 'Dell',
      'HP', 'VMware', 'ServiceNow', 'Workday', 'Fortune 500'
    ];
    
    const hasEnterprise = customers.some(c => 
      enterpriseIndicators.some(indicator => 
        c.name.toLowerCase().includes(indicator.toLowerCase())
      )
    );
    
    if (hasEnterprise) return 'enterprise';
    if (customers.length > 10) return 'mid-market';
    if (customers.length > 3) return 'smb';
    
    return 'mixed';
  }
  
  /**
   * Find company website (reuse from CIM scraper)
   */
  private async findCompanyWebsite(companyName: string): Promise<string> {
    // Implementation would be same as in CIM scraper
    return `https://www.${companyName.toLowerCase().replace(/\s+/g, '')}.com`;
  }
}

// Export singleton instance
export const companyLogoAnalyzer = new CompanyLogoAnalyzer();