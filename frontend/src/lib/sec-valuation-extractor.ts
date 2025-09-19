/**
 * SEC Valuation Extractor
 * Extracts private company valuations from semi-liquid fund filings
 * NO API KEY REQUIRED - SEC EDGAR is completely free and public
 */

interface FundHolding {
  companyName: string;
  fairValue: number;
  costBasis?: number;
  percentOwnership?: number;
  shares?: number;
  impliedValuation?: number;
  asOfDate: string;
  fundName: string;
  fundTicker?: string;
  source: string;
}

interface ValuationData {
  company: string;
  valuations: FundHolding[];
  latestValuation: number;
  valuationDate: string;
  confidence: 'high' | 'medium' | 'low';
}

export class SECValuationExtractor {
  private static readonly SEMI_LIQUID_FUNDS = [
    {
      name: 'ARK Venture Fund',
      ticker: 'ARKVX',
      cik: '0001830305',
      filingType: 'N-Q' // Quarterly holdings
    },
    {
      name: 'Destiny Tech100',
      ticker: 'DXYZ',
      cik: '0001909746',
      filingType: 'N-Q'
    },
    {
      name: 'SharesPost 100 Fund',
      ticker: 'PRIVX',
      cik: '0001579982',
      filingType: 'N-Q'
    },
    {
      name: 'Crossover Ventures Fund',
      ticker: 'CROVX',
      filingType: 'N-Q'
    }
  ];

  /**
   * Search for company valuations in semi-liquid fund filings
   * NO API KEY NEEDED - SEC is free!
   */
  static async getCompanyValuation(companyName: string): Promise<ValuationData | null> {
    console.log(`[SEC] Searching for ${companyName} valuations in semi-liquid funds...`);
    
    const valuations: FundHolding[] = [];
    
    for (const fund of this.SEMI_LIQUID_FUNDS) {
      try {
        // Get latest N-Q filing (quarterly report with holdings)
        const filings = await this.getLatestFilings(fund.cik, fund.filingType);
        
        if (filings.length === 0) continue;
        
        // Parse holdings from filing
        const holdings = await this.parseHoldingsFromFiling(filings[0], companyName);
        
        if (holdings) {
          valuations.push({
            ...holdings,
            fundName: fund.name,
            fundTicker: fund.ticker
          });
        }
      } catch (error) {
        console.error(`[SEC] Error fetching ${fund.name}:`, error);
      }
    }
    
    // Also check Form D filings for direct valuations
    const formDData = await this.getFormDValuation(companyName);
    if (formDData) {
      valuations.push(formDData);
    }
    
    if (valuations.length === 0) {
      return null;
    }
    
    // Get most recent valuation
    valuations.sort((a, b) => new Date(b.asOfDate).getTime() - new Date(a.asOfDate).getTime());
    
    return {
      company: companyName,
      valuations,
      latestValuation: valuations[0].fairValue || valuations[0].impliedValuation || 0,
      valuationDate: valuations[0].asOfDate,
      confidence: this.calculateConfidence(valuations)
    };
  }

  /**
   * Get latest filings for a fund
   */
  private static async getLatestFilings(cik: string, formType: string): Promise<any[]> {
    const url = `https://data.sec.gov/submissions/CIK${cik.padStart(10, '0')}.json`;
    
    const response = await fetch(url, {
      headers: {
        'User-Agent': 'DillaAI/1.0 (compliance@dilla.ai)',
        'Accept': 'application/json'
      }
    });
    
    if (!response.ok) {
      throw new Error(`Failed to fetch filings: ${response.status}`);
    }
    
    const data = await response.json();
    const recentFilings = data.filings.recent;
    
    // Filter for desired form type
    const relevantFilings = [];
    for (let i = 0; i < recentFilings.form.length; i++) {
      if (recentFilings.form[i] === formType || 
          (formType === 'N-Q' && recentFilings.form[i] === 'N-CSR')) { // N-CSR also has holdings
        relevantFilings.push({
          accessionNumber: recentFilings.accessionNumber[i].replace(/-/g, ''),
          filingDate: recentFilings.filingDate[i],
          form: recentFilings.form[i],
          primaryDocument: recentFilings.primaryDocument[i]
        });
      }
    }
    
    return relevantFilings.slice(0, 3); // Get last 3 filings
  }

  /**
   * Parse holdings from a specific filing
   */
  private static async parseHoldingsFromFiling(filing: any, companyName: string): Promise<FundHolding | null> {
    const cik = filing.accessionNumber.substring(0, 10);
    const url = `https://www.sec.gov/Archives/edgar/data/${cik}/${filing.accessionNumber}/${filing.primaryDocument}`;
    
    const response = await fetch(url, {
      headers: {
        'User-Agent': 'DillaAI/1.0 (compliance@dilla.ai)',
        'Accept': 'text/html'
      }
    });
    
    if (!response.ok) {
      return null;
    }
    
    const html = await response.text();
    
    // Search for company name in holdings table
    const companyPattern = new RegExp(companyName, 'i');
    const tableMatch = html.match(/<table[^>]*>Array.from(S)*?<\/table>/gi);
    
    if (!tableMatch) return null;
    
    for (const table of tableMatch) {
      if (table.match(companyPattern)) {
        // Extract fair value
        const fairValueMatch = table.match(new RegExp(
          `${companyName}[\\s\\S]*?\\$([0-9,]+(?:\\.[0-9]+)?)[\\s]?(?:million|M)?`,
          'i'
        ));
        
        if (fairValueMatch) {
          const value = parseFloat(fairValueMatch[1].replace(/,/g, ''));
          const multiplier = fairValueMatch[0].toLowerCase().includes('million') || 
                           fairValueMatch[0].includes('M') ? 1000000 : 1;
          
          return {
            companyName,
            fairValue: value * multiplier,
            asOfDate: filing.filingDate,
            source: `SEC Filing ${filing.accessionNumber}`,
            fundName: '',
            fundTicker: ''
          };
        }
      }
    }
    
    return null;
  }

  /**
   * Get Form D (private placement) valuations
   */
  private static async getFormDValuation(companyName: string): Promise<FundHolding | null> {
    const url = `https://efts.sec.gov/LATEST/search-index?q=${encodeURIComponent(companyName)}&category=form-cat1&forms=D`;
    
    const response = await fetch(url, {
      headers: {
        'User-Agent': 'DillaAI/1.0 (compliance@dilla.ai)',
        'Accept': 'application/json'
      }
    });
    
    if (!response.ok || !response.json) {
      return null;
    }
    
    const data = await response.json();
    
    if (data.hits?.hits?.length > 0) {
      const latestFiling = data.hits.hits[0]._source;
      
      // Form D has offering amount which can imply valuation
      if (latestFiling.offering_amount) {
        return {
          companyName,
          fairValue: parseFloat(latestFiling.offering_amount),
          asOfDate: latestFiling.file_date,
          fundName: 'Direct Filing',
          source: `Form D ${latestFiling.accession_number}`,
          impliedValuation: parseFloat(latestFiling.offering_amount) * 10 // Rough estimate
        };
      }
    }
    
    return null;
  }

  /**
   * Calculate confidence based on number of sources
   */
  private static calculateConfidence(valuations: FundHolding[]): 'high' | 'medium' | 'low' {
    if (valuations.length >= 3) return 'high';
    if (valuations.length >= 2) return 'medium';
    return 'low';
  }

  /**
   * Get all known valuations for major private companies
   */
  static async getKnownPrivateValuations(): Promise<Record<string, ValuationData>> {
    const companies = [
      'SpaceX', 'Stripe', 'Databricks', 'Canva', 'Bytedance',
      'Anthropic', 'OpenAI', 'Flexport', 'Rippling', 'Figma'
    ];
    
    const valuations: Record<string, ValuationData> = {};
    
    for (const company of companies) {
      const data = await this.getCompanyValuation(company);
      if (data) {
        valuationsArray.from(pany) = data;
      }
      
      // Be respectful with rate limiting
      await new Promise(resolve => setTimeout(resolve, 1000));
    }
    
    return valuations;
  }
}