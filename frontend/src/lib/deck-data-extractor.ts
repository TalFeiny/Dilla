import { enhancedCimScraper } from './enhanced-cim-scraper';
import { intelligentWebScraper } from './intelligent-web-scraper';
import { fundingDataAggregator } from './funding-data-aggregator';
import { createClient } from '@supabase/supabase-js';

const supabase = createClient(
  process.env.NEXT_PUBLIC_SUPABASE_URL!,
  process.env.SUPABASE_SERVICE_ROLE_KEY!
);

interface ExtractedDeckData {
  company: string;
  market: {
    size: string;
    growth: string;
    segment: string;
    competitors: string[];
    trends: string[];
  };
  traction: {
    revenue?: string;
    arr?: string;
    growth?: string;
    customers?: number;
    nrr?: string;
    employees?: string;
    metrics?: Record<string, any>;
  };
  funding: {
    totalRaised: string;
    lastRound: string;
    valuation?: string;
    investors: string[];
    stage: string;
  };
  product: {
    description: string;
    features: string[];
    pricing?: string;
    differentiators: string[];
  };
  team: {
    founders: any[];
    size?: string;
    keyHires?: string[];
  };
  sources: {
    url: string;
    title: string;
    data: any;
  }[];
}

export class DeckDataExtractor {
  async extractComprehensiveData(companyName: string): Promise<ExtractedDeckData> {
    console.log(`🎯 Array.from(kDataExtractor) Starting comprehensive extraction for ${companyName}`);
    
    // Run all data gathering in parallel
    const [
      cimData,
      fundingData,
      webSearchData,
      ycData,
      marketData,
      dbData
    ] = await Promise.all([
      // 1. Use CIM scraper for deep company analysis
      this.extractWithCIMScraper(companyName),
      
      // 2. Get funding history
      fundingDataAggregator.aggregateFundingData(companyName),
      
      // 3. General web search
      intelligentWebScraper.scrapeCompany(`${companyName}`, 'revenue ARR growth customers metrics traction'),
      
      // 4. YC specific data if available
      this.extractFromYCombinator(companyName),
      
      // 5. Market analysis
      this.extractMarketData(companyName),
      
      // 6. Database lookup
      this.getFromDatabase(companyName)
    ]);
    
    // Merge and structure all data
    const extracted: ExtractedDeckData = {
      company: companyName,
      market: this.mergeMarketData(marketData, cimData, webSearchData),
      traction: this.mergeTractionData(cimData, ycData, webSearchData, dbData),
      funding: this.mergeFundingData(fundingData, ycData, dbData),
      product: this.mergeProductData(cimData, webSearchData),
      team: this.mergeTeamData(cimData, ycData, dbData),
      sources: this.consolidateSources([cimData, fundingData, webSearchData, ycData, marketData])
    };
    
    console.log(`✅ Array.from(kDataExtractor) Extraction complete:`, {
      hasMarketSize: !!extracted.market.size,
      hasRevenue: !!extracted.traction.revenue,
      hasFunding: !!extracted.funding.totalRaised,
      sourceCount: extracted.sources.length
    });
    
    return extracted;
  }
  
  private async extractWithCIMScraper(companyName: string) {
    try {
      console.log(`📄 [CIM Scraper] Analyzing ${companyName}...`);
      const result = await enhancedCimScraper.scrapeCompanyWithVision(companyName);
      
      if (result?.analysis) {
        console.log(`✅ [CIM Scraper] Found data:`, {
          hasRevenue: !!result.analysis.revenue,
          hasMarket: !!result.analysis.market,
          hasTraction: !!result.analysis.traction
        });
      }
      
      return result;
    } catch (error) {
      console.error(`❌ [CIM Scraper] Error:`, error);
      return null;
    }
  }
  
  private async extractFromYCombinator(companyName: string) {
    try {
      // Search YC companies
      const ycSearch = await intelligentWebScraper.scrapeCompany(
        companyName,
        `site:ycombinator.com OR site:bookface.ycombinator.com`
      );
      
      if (ycSearch?.searchResults?.length > 0) {
        console.log(`🚀 Array.from(Data) Found YC information for ${companyName}`);
        
        // Extract structured data from YC pages
        const ycData: any = {
          batch: null,
          description: null,
          market: null,
          traction: {}
        };
        
        // Parse YC data from search results
        for (const result of ycSearch.searchResults) {
          const content = result.snippet || result.content || '';
          
          // Extract batch (e.g., "W22", "S21")
          const batchMatch = content.match(/([WS]\d{2})/);
          if (batchMatch) ycData.batch = batchMatch[1];
          
          // Extract market/vertical
          const marketMatch = content.match(/(?:vertical|market|industry):\s*(Array.from(n)+)/i);
          if (marketMatch) ycData.market = marketMatch[1];
          
          // Extract employee count
          const employeeMatch = content.match(/(\d+)[\s-]*(?:employees|people|team)/i);
          if (employeeMatch) ycData.traction.employees = employeeMatch[1];
          
          // Extract funding stage
          const stageMatch = content.match(/(?:Series\s+[A-E]|Seed|Pre-seed)/i);
          if (stageMatch) ycData.stage = stageMatch[0];
        }
        
        return ycData;
      }
    } catch (error) {
      console.error(`❌ Array.from(Data) Error:`, error);
    }
    
    return null;
  }
  
  private async extractMarketData(companyName: string) {
    try {
      const marketSearch = await intelligentWebScraper.scrapeCompany(
        companyName,
        'market size TAM billion million industry growth CAGR'
      );
      
      const marketData: any = {
        size: null,
        growth: null,
        competitors: [],
        trends: []
      };
      
      if (marketSearch?.searchResults) {
        for (const result of marketSearch.searchResults) {
          const content = (result.snippet || '') + ' ' + (result.content || '');
          
          // Extract market size
          const sizeMatch = content.match(/\$?([\d.]+)\s*(billion|million)\s*(?:TAM|market|opportunity)/i);
          if (sizeMatch && !marketData.size) {
            const value = parseFloat(sizeMatch[1]);
            const unit = sizeMatch[2].toLowerCase();
            marketData.size = unit === 'billion' ? `$${value}B` : `$${value}M`;
          }
          
          // Extract growth rate
          const growthMatch = content.match(/([\d.]+)%\s*(?:CAGR|growth|annually)/i);
          if (growthMatch && !marketData.growth) {
            marketData.growth = `${growthMatch[1]}%`;
          }
          
          // Extract competitors
          const compMatch = content.match(/(?:compet(?:e|ing|itors?)|versus|vs\.?)\s*(?:with\s+)?([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+)*)/g);
          if (compMatch) {
            compMatch.forEach(match => {
              const name = match.replace(/compet\w*\s+(?:with\s+)?|versus\s+|vs\.?\s+/i, '').trim();
              if (name && name !== companyName && !marketData.competitors.includes(name)) {
                marketData.competitors.push(name);
              }
            });
          }
        }
      }
      
      console.log(`📊 [Market Data] Extracted:`, marketData);
      return marketData;
    } catch (error) {
      console.error(`❌ [Market Data] Error:`, error);
      return null;
    }
  }
  
  private async getFromDatabase(companyName: string) {
    try {
      const { data } = await supabase
        .from('companies')
        .select('*')
        .ilike('name', `%${companyName}%`)
        .single();
      
      if (data) {
        console.log(`✅ Array.from(abase) Found company data for ${companyName}`);
      }
      
      return data;
    } catch (error) {
      return null;
    }
  }
  
  private mergeMarketData(...sources: any[]): ExtractedDeckData['market'] {
    const market: ExtractedDeckData['market'] = {
      size: '',
      growth: '',
      segment: '',
      competitors: [],
      trends: []
    };
    
    for (const source of sources) {
      if (!source) continue;
      
      // Extract from different source formats
      if (source.analysis?.market) {
        market.size = market.size || source.analysis.market.tam || source.analysis.market.size;
        market.growth = market.growth || source.analysis.market.growth || source.analysis.market.cagr;
        market.segment = market.segment || source.analysis.market.segment;
      }
      
      if (source.size) market.size = market.size || source.size;
      if (source.growth) market.growth = market.growth || source.growth;
      if (source.competitors?.length) {
        market.competitors = [...new Set([...market.competitors, ...source.competitors])];
      }
      
      // Extract from web search results
      if (source.searchResults) {
        for (const result of source.searchResults) {
          const content = result.snippet || '';
          
          // Try to extract market size
          if (!market.size) {
            const sizeMatch = content.match(/\$?([\d.]+)\s*(billion|million|B|M)\s*(?:market|TAM)/i);
            if (sizeMatch) {
              market.size = `$${sizeMatch[1]}${sizeMatch[2].toUpperCase()[0]}`;
            }
          }
          
          // Try to extract growth
          if (!market.growth) {
            const growthMatch = content.match(/([\d.]+)%\s*(?:CAGR|growth)/i);
            if (growthMatch) {
              market.growth = `${growthMatch[1]}% CAGR`;
            }
          }
        }
      }
    }
    
    // Set defaults if still empty
    market.size = market.size || 'Not disclosed';
    market.growth = market.growth || 'High growth';
    market.segment = market.segment || 'Technology';
    
    return market;
  }
  
  private mergeTractionData(...sources: any[]): ExtractedDeckData['traction'] {
    const traction: ExtractedDeckData['traction'] = {
      metrics: {}
    };
    
    for (const source of sources) {
      if (!source) continue;
      
      // CIM scraper data
      if (source?.analysis?.traction) {
        const t = source.analysis.traction;
        traction.revenue = traction.revenue || t.revenue;
        traction.arr = traction.arr || t.arr;
        traction.growth = traction.growth || t.growth;
        traction.customers = traction.customers || t.customerCount;
        traction.nrr = traction.nrr || t.nrr;
      }
      
      // YC data
      if (source?.traction) {
        traction.employees = traction.employees || source.traction.employees;
        Object.assign(traction.metrics!, source.traction);
      }
      
      // Database data
      if (source?.revenue) traction.revenue = traction.revenue || source.revenue;
      if (source?.arr) traction.arr = traction.arr || source.arr;
      if (source?.employee_count) traction.employees = traction.employees || source.employee_count;
      
      // Web search extraction
      if (source?.searchResults) {
        for (const result of source.searchResults) {
          const content = result.snippet || '';
          
          // Extract revenue/ARR
          if (!traction.arr) {
            const arrMatch = content.match(/\$?([\d.]+)\s*(million|M|billion|B)\s*(?:ARR|annual\s*recurring)/i);
            if (arrMatch) {
              traction.arr = `$${arrMatch[1]}${arrMatch[2].toUpperCase()[0]}`;
            }
          }
          
          // Extract growth rate
          if (!traction.growth) {
            const growthMatch = content.match(/([\d.]+)%\s*(?:growth|increase|MoM|YoY)/i);
            if (growthMatch) {
              traction.growth = `${growthMatch[1]}%`;
            }
          }
          
          // Extract customer count
          if (!traction.customers) {
            const custMatch = content.match(/([\d,]+)\s*(?:customers|clients|users|companies)/i);
            if (custMatch) {
              traction.customers = parseInt(custMatch[1].replace(/,/g, ''));
            }
          }
        }
      }
    }
    
    return traction;
  }
  
  private mergeFundingData(...sources: any[]): ExtractedDeckData['funding'] {
    const funding: ExtractedDeckData['funding'] = {
      totalRaised: '',
      lastRound: '',
      investors: [],
      stage: ''
    };
    
    for (const source of sources) {
      if (!source) continue;
      
      if (source.totalFunding) {
        funding.totalRaised = source.totalFunding;
        funding.lastRound = source.lastRound?.amount || '';
        funding.valuation = source.lastRound?.valuation;
        funding.stage = source.lastRound?.series || source.stage || '';
        
        if (source.investors?.length) {
          funding.investors = [...new Set([...funding.investors, ...source.investors])];
        }
      }
      
      // YC data
      if (source?.batch) {
        funding.stage = funding.stage || 'Post-YC';
        funding.investors.push(`Y Combinator (${source.batch})`);
      }
      
      // Database data
      if (source?.total_raised) funding.totalRaised = funding.totalRaised || source.total_raised;
      if (source?.last_funding_round) funding.lastRound = funding.lastRound || source.last_funding_round;
    }
    
    // Set defaults
    funding.totalRaised = funding.totalRaised || 'Undisclosed';
    funding.stage = funding.stage || 'Early Stage';
    
    return funding;
  }
  
  private mergeProductData(...sources: any[]): ExtractedDeckData['product'] {
    const product: ExtractedDeckData['product'] = {
      description: '',
      features: [],
      differentiators: []
    };
    
    for (const source of sources) {
      if (!source) continue;
      
      if (source?.analysis?.product) {
        product.description = product.description || source.analysis.product.description;
        product.features = [...new Set([...product.features, ...(source.analysis.product.features || [])])];
        product.pricing = product.pricing || source.analysis.product.pricing;
        product.differentiators = [...new Set([...product.differentiators, ...(source.analysis.product.differentiators || [])])];
      }
      
      if (source?.websiteData?.product) {
        product.description = product.description || source.websiteData.product.description;
      }
    }
    
    return product;
  }
  
  private mergeTeamData(...sources: any[]): ExtractedDeckData['team'] {
    const team: ExtractedDeckData['team'] = {
      founders: []
    };
    
    for (const source of sources) {
      if (!source) continue;
      
      if (source?.analysis?.team) {
        team.founders = [...team.founders, ...(source.analysis.team.founders || [])];
        team.size = team.size || source.analysis.team.size;
        team.keyHires = [...new Set([...(team.keyHires || []), ...(source.analysis.team.keyHires || [])])];
      }
      
      if (source?.traction?.employees) {
        team.size = team.size || source.traction.employees;
      }
    }
    
    return team;
  }
  
  private consolidateSources(allData: any[]): ExtractedDeckData['sources'] {
    const sources: ExtractedDeckData['sources'] = [];
    
    for (const data of allData) {
      if (!data) continue;
      
      if (data.searchResults) {
        for (const result of data.searchResults) {
          sources.push({
            url: result.url || '',
            title: result.title || 'Web Source',
            data: result
          });
        }
      }
      
      if (data.source) {
        sources.push({
          url: data.source.url || '',
          title: data.source.name || 'Data Source',
          data: data
        });
      }
    }
    
    return sources.slice(0, 15); // Limit to top 15 sources
  }
}

export const deckDataExtractor = new DeckDataExtractor();