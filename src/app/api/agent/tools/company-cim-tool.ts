import { companyCIMScraper } from '@/lib/company-cim-scraper';

/**
 * Company CIM Tool - Generates CIM-like profiles by scraping company websites
 */
export const companyCIMTool = {
  name: 'generate_company_cim',
  description: 'Generate a comprehensive CIM (Confidential Information Memorandum) for a company by scraping their website and gathering public information',
  
  parameters: {
    type: 'object',
    properties: {
      company_name: {
        type: 'string',
        description: 'Name of the company to analyze'
      },
      company_url: {
        type: 'string',
        description: 'Optional company website URL (will be auto-discovered if not provided)'
      },
      sections: {
        type: 'array',
        description: 'Specific sections to focus on',
        items: {
          type: 'string',
          enum: [
            'overview',
            'products',
            'market',
            'team',
            'financials',
            'competitors',
            'growth_strategy',
            'investment_opportunity'
          ]
        }
      }
    },
    required: ['company_name']
  },
  
  async execute(params: any) {
    try {
      console.log(`Executing CIM generation for ${params.company_name}...`);
      
      // Generate the CIM
      const cim = await companyCIMScraper.scrapeCompanyForCIM(
        params.company_name,
        params.company_url
      );
      
      // Format response based on requested sections
      let response = {
        company_name: params.company_name,
        website: cim.company_overview.website,
        data_quality: cim.metadata.data_quality_score,
        cim_summary: {},
        full_cim: null as any
      };
      
      // If specific sections requested, filter them
      if (params.sections && params.sections.length > 0) {
        const summary: any = {};
        
        params.sections.forEach((section: string) => {
          switch(section) {
            case 'overview':
              summary.overview = {
                description: cim.company_overview.description,
                founded: cim.company_overview.founded,
                employees: cim.company_overview.employees,
                headquarters: cim.company_overview.headquarters,
                mission: cim.company_overview.mission
              };
              break;
            case 'products':
              summary.products = cim.products_services;
              break;
            case 'market':
              summary.market = {
                tam: cim.market_analysis.tam,
                growth_rate: cim.market_analysis.growth_rate,
                trends: cim.market_analysis.trends,
                competitive_position: cim.market_analysis.competitive_landscape.positioning
              };
              break;
            case 'team':
              summary.team = {
                ceo: cim.team_leadership.ceo_founder,
                executives: cim.team_leadership.executives,
                team_size: cim.team_leadership.team_size
              };
              break;
            case 'financials':
              summary.financials = {
                revenue: cim.traction_metrics.revenue,
                growth_rate: cim.traction_metrics.growth_rate,
                funding_total: cim.funding_financials.total_raised,
                last_round: cim.funding_financials.last_round,
                burn_rate: cim.funding_financials.burn_rate
              };
              break;
            case 'competitors':
              summary.competitors = cim.market_analysis.competitive_landscape;
              break;
            case 'growth_strategy':
              summary.growth_strategy = cim.growth_strategy;
              break;
            case 'investment_opportunity':
              summary.investment_opportunity = {
                thesis: cim.executive_summary.investment_thesis,
                highlights: cim.investment_opportunity.highlights,
                value_drivers: cim.investment_opportunity.value_drivers,
                exit_potential: cim.investment_opportunity.exit_potential
              };
              break;
          }
        });
        
        response.cim_summary = summary;
      } else {
        // Return full CIM if no specific sections requested
        response.full_cim = cim;
      }
      
      return {
        success: true,
        data: response,
        message: `Generated comprehensive CIM for ${params.company_name} with ${cim.metadata.data_quality_score}% data quality score`
      };
      
    } catch (error) {
      console.error('Error in CIM tool:', error);
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Failed to generate CIM',
        data: null
      };
    }
  }
};

/**
 * Quick Company Intel Tool - Fast lookup of key company facts
 */
export const quickCompanyIntelTool = {
  name: 'get_company_intel',
  description: 'Quickly get key intelligence about a company including products, team, funding, and market position',
  
  parameters: {
    type: 'object',
    properties: {
      company_name: {
        type: 'string',
        description: 'Name of the company'
      },
      intel_type: {
        type: 'string',
        enum: ['quick_facts', 'funding_status', 'product_overview', 'competitive_intel', 'team_background'],
        description: 'Type of intelligence to gather'
      }
    },
    required: ['company_name', 'intel_type']
  },
  
  async execute(params: any) {
    try {
      // Use Tavily for quick search
      const TAVILY_API_KEY = process.env.TAVILY_API_KEY || '';
      
      let query = '';
      switch(params.intel_type) {
        case 'quick_facts':
          query = `${params.company_name} company overview founded employees headquarters revenue`;
          break;
        case 'funding_status':
          query = `${params.company_name} funding raised valuation investors series round`;
          break;
        case 'product_overview':
          query = `${params.company_name} products services features pricing customers`;
          break;
        case 'competitive_intel':
          query = `${params.company_name} competitors market share advantages differentiation`;
          break;
        case 'team_background':
          query = `${params.company_name} CEO founder executive team leadership background`;
          break;
      }
      
      const response = await fetch('https://api.tavily.com/search', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          api_key: TAVILY_API_KEY,
          query: query,
          max_results: 5,
          search_depth: 'advanced',
          include_answer: true,
        }),
      });
      
      const data = await response.json();
      
      return {
        success: true,
        data: {
          company: params.company_name,
          intel_type: params.intel_type,
          summary: data.answer,
          sources: data.results?.map((r: any) => ({
            title: r.title,
            url: r.url,
            snippet: r.snippet
          }))
        },
        message: `Retrieved ${params.intel_type} for ${params.company_name}`
      };
      
    } catch (error) {
      console.error('Error in quick intel tool:', error);
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Failed to get company intelligence',
        data: null
      };
    }
  }
};

/**
 * Company Website Analyzer Tool
 */
export const companyWebsiteAnalyzerTool = {
  name: 'analyze_company_website',
  description: 'Analyze a company website to understand what they do, their products, and business model',
  
  parameters: {
    type: 'object',
    properties: {
      company_name: {
        type: 'string',
        description: 'Name of the company'
      },
      website_url: {
        type: 'string',
        description: 'Company website URL (optional, will be auto-discovered)'
      },
      analysis_depth: {
        type: 'string',
        enum: ['quick', 'standard', 'deep'],
        description: 'Depth of analysis'
      }
    },
    required: ['company_name']
  },
  
  async execute(params: any) {
    try {
      const depth = params.analysis_depth || 'standard';
      
      // For quick analysis, just search for basic info
      if (depth === 'quick') {
        const quickIntel = await quickCompanyIntelTool.execute({
          company_name: params.company_name,
          intel_type: 'quick_facts'
        });
        return quickIntel;
      }
      
      // For standard/deep analysis, generate partial or full CIM
      const sections = depth === 'deep' 
        ? ['overview', 'products', 'market', 'team', 'financials', 'competitors', 'investment_opportunity']
        : ['overview', 'products', 'market'];
      
      const cimResult = await companyCIMTool.execute({
        company_name: params.company_name,
        company_url: params.website_url,
        sections: sections
      });
      
      if (cimResult.success) {
        return {
          success: true,
          data: {
            company_name: params.company_name,
            analysis_depth: depth,
            website: cimResult.data.website,
            key_findings: cimResult.data.cim_summary || cimResult.data.full_cim?.executive_summary,
            data_quality: cimResult.data.data_quality
          },
          message: `Completed ${depth} analysis of ${params.company_name}`
        };
      }
      
      return cimResult;
      
    } catch (error) {
      console.error('Error in website analyzer tool:', error);
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Failed to analyze website',
        data: null
      };
    }
  }
};

// Export all tools
export const companyCIMTools = [
  companyCIMTool,
  quickCompanyIntelTool,
  companyWebsiteAnalyzerTool
];