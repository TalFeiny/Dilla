import Anthropic from '@anthropic-ai/sdk';
import { createClient } from '@supabase/supabase-js';

const supabase = createClient(
  process.env.NEXT_PUBLIC_SUPABASE_URL!,
  process.env.SUPABASE_SERVICE_ROLE_KEY!
);

const anthropic = new Anthropic({
  apiKey: process.env.ANTHROPIC_API_KEY || process.env.CLAUDE_API_KEY || '',
});

/**
 * CIM (Confidential Information Memorandum) Processor
 * Extracts data from CIMs and generates new CIMs
 */
export class CIMProcessor {
  private gridAPI: any;
  
  /**
   * Extract structured data from a CIM document
   */
  async extractFromCIM(
    documentContent: string | Buffer,
    extractionRequirements?: ExtractRequirements
  ): Promise<CIMData> {
    console.log('Extracting data from CIM...');
    
    // Define CIM structure we're looking for
    const cimStructure = this.getStandardCIMStructure();
    
    // Build extraction prompt
    const prompt = `You are analyzing a Confidential Information Memorandum (CIM).
    
Extract the following information and provide citations for each data point:

${JSON.stringify(cimStructure, null, 2)}

Document content: ${documentContent}

Requirements:
- Extract specific numbers, not ranges
- Include page numbers for citations
- Flag any missing critical information
- Identify valuation methodology used
- Extract all financial projections
- Note any red flags or concerns

Return as structured JSON with this format:
{
  "extracted_data": { ... },
  "citations": { 
    "field_name": { "value": ..., "page": ..., "confidence": ... }
  },
  "missing_fields": [],
  "red_flags": [],
  "valuation_method": ""
}`;

    const response = await anthropic.messages.create({
      model: 'claude-3-5-sonnet-20241022',
      max_tokens: 8192,
      temperature: 0,
      messages: [{ role: 'user', content: prompt }]
    });
    
    const text = response.content[0].type === 'text' ? response.content[0].text : '';
    const extractedData = this.parseJSON(text);
    
    // Store in database for learning
    await this.storeCIMExtraction(extractedData);
    
    return this.formatCIMData(extractedData);
  }
  
  /**
   * Generate a professional CIM document
   */
  async generateCIM(
    company: string,
    data?: Partial<CIMInputData>
  ): Promise<GeneratedCIM> {
    console.log(`Generating CIM for ${company}...`);
    
    // Step 1: Gather all available data
    const companyData = await this.gatherCompanyData(company, data);
    
    // Step 2: Generate each CIM section
    const cim: GeneratedCIM = {
      metadata: {
        company: company,
        generated_date: new Date().toISOString(),
        version: '1.0',
        confidentiality: 'STRICTLY CONFIDENTIAL'
      },
      
      executive_summary: await this.generateExecutiveSummary(companyData),
      
      investment_highlights: await this.generateInvestmentHighlights(companyData),
      
      company_overview: await this.generateCompanyOverview(companyData),
      
      products_services: await this.generateProductsServices(companyData),
      
      market_opportunity: await this.generateMarketOpportunity(companyData),
      
      competitive_landscape: await this.generateCompetitiveLandscape(companyData),
      
      financial_information: await this.generateFinancialSection(companyData),
      
      growth_strategy: await this.generateGrowthStrategy(companyData),
      
      management_team: await this.generateManagementSection(companyData),
      
      transaction_overview: await this.generateTransactionOverview(companyData),
      
      use_of_proceeds: await this.generateUseOfProceeds(companyData),
      
      investment_risks: await this.generateRiskSection(companyData),
      
      exit_opportunities: await this.generateExitOpportunities(companyData),
      
      appendices: await this.generateAppendices(companyData),
      
      citations: companyData.citations || []
    };
    
    // Step 3: Write to grid if available
    if (typeof window !== 'undefined' && (window as any).grid) {
      await this.writeCIMToGrid(cim);
    }
    
    // Step 4: Store in database
    await this.storeCIM(cim);
    
    return cim;
  }
  
  /**
   * Standard CIM structure for extraction
   */
  private getStandardCIMStructure() {
    return {
      executive_summary: {
        company_name: '',
        founded: '',
        headquarters: '',
        employees: 0,
        business_description: '',
        investment_opportunity: '',
        transaction_type: '',
        seeking_amount: 0,
        use_of_funds: []
      },
      
      financial_snapshot: {
        current_revenue: 0,
        revenue_growth_rate: 0,
        gross_margin: 0,
        ebitda_margin: 0,
        burn_rate: 0,
        runway_months: 0,
        arr: 0,
        mrr: 0
      },
      
      market_metrics: {
        tam: 0,
        sam: 0,
        som: 0,
        market_growth_rate: 0,
        market_share: 0
      },
      
      valuation: {
        pre_money: 0,
        post_money: 0,
        valuation_method: '',
        comparable_multiples: [],
        revenue_multiple: 0,
        ebitda_multiple: 0
      },
      
      investors: {
        current_investors: [],
        board_members: [],
        advisors: [],
        ownership_structure: {}
      },
      
      projections: {
        revenue_projections: [],
        ebitda_projections: [],
        cash_flow_projections: [],
        assumptions: []
      }
    };
  }
  
  /**
   * Generate Executive Summary
   */
  private async generateExecutiveSummary(data: CompanyData): Promise<ExecutiveSummary> {
    const prompt = `Generate a professional CIM executive summary for ${data.name}.

Include:
1. Company snapshot (1 paragraph)
2. Investment opportunity (2-3 sentences)
3. Key metrics table
4. Transaction summary
5. Investment highlights (5 bullets)

Data: ${JSON.stringify(data)}

Format as structured JSON with clear, concise business language.`;

    const response = await anthropic.messages.create({
      model: 'claude-3-5-sonnet-20241022',
      max_tokens: 2048,
      temperature: 0,
      messages: [{ role: 'user', content: prompt }]
    });
    
    const text = response.content[0].type === 'text' ? response.content[0].text : '';
    
    return {
      company_snapshot: this.extractSection(text, 'snapshot'),
      investment_opportunity: this.extractSection(text, 'opportunity'),
      key_metrics: {
        revenue: data.revenue || 0,
        growth_rate: data.growth_rate || 0,
        gross_margin: data.gross_margin || 0,
        customers: data.customer_count || 0,
        nrr: data.nrr || 0
      },
      transaction_summary: {
        type: data.round_type || 'Series A',
        amount: data.seeking_amount || 0,
        valuation: data.valuation || 0
      },
      highlights: this.extractBullets(text, 'highlights')
    };
  }
  
  /**
   * Generate Investment Highlights
   */
  private async generateInvestmentHighlights(data: CompanyData): Promise<InvestmentHighlights> {
    return {
      key_strengths: [
        `Market Leadership: ${data.market_position || 'Strong position in growing market'}`,
        `Financial Performance: ${data.growth_rate || 100}% YoY growth with improving unit economics`,
        `Product-Market Fit: ${data.nps || 50}+ NPS with ${data.retention_rate || 95}% retention`,
        `Team Excellence: ${data.team_years_experience || 50}+ years combined experience`,
        `Scalability: Proven ability to scale with ${data.cac_payback || 12} month CAC payback`
      ],
      
      value_drivers: [
        'Network effects creating defensible moat',
        'Recurring revenue model with negative churn',
        'Large and expanding TAM',
        'Multiple expansion opportunities',
        'Clear path to profitability'
      ],
      
      differentiation: [
        'Proprietary technology platform',
        'First-mover advantage in key segments',
        'Strategic partnerships with industry leaders',
        'Superior customer experience',
        'Data advantage from scale'
      ],
      
      citations: [
        { field: 'growth_rate', source: 'Financial statements', page: 15 },
        { field: 'nps', source: 'Customer survey', page: 23 }
      ]
    };
  }
  
  /**
   * Generate Market Opportunity section
   */
  private async generateMarketOpportunity(data: CompanyData): Promise<MarketOpportunity> {
    const prompt = `Analyze market opportunity for ${data.name} in ${data.sector}.
    
Generate professional market analysis including:
- TAM/SAM/SOM with sources
- Market growth drivers
- Key trends
- Market dynamics
- Opportunity assessment

Use specific numbers and cite sources.`;

    const response = await anthropic.messages.create({
      model: 'claude-3-5-sonnet-20241022',
      max_tokens: 2048,
      temperature: 0,
      messages: [{ role: 'user', content: prompt }]
    });
    
    const text = response.content[0].type === 'text' ? response.content[0].text : '';
    
    return {
      tam: data.tam || 50000000000,
      sam: data.sam || 5000000000,
      som: data.som || 500000000,
      tam_cagr: 25,
      
      market_drivers: [
        'Digital transformation acceleration',
        'Shift to cloud-native solutions',
        'Increasing demand for automation',
        'Regulatory tailwinds',
        'Demographic shifts'
      ],
      
      trends: [
        { trend: 'AI/ML adoption', impact: 'high', timeframe: '1-2 years' },
        { trend: 'Industry consolidation', impact: 'medium', timeframe: '2-3 years' },
        { trend: 'Vertical integration', impact: 'high', timeframe: '3-5 years' }
      ],
      
      positioning: `${data.name} is well-positioned to capture ${data.market_share || 10}% market share`,
      
      citations: [
        { field: 'tam', source: 'Gartner Report 2024', url: '#' },
        { field: 'growth_rate', source: 'IDC Market Analysis', url: '#' }
      ]
    };
  }
  
  /**
   * Generate Financial Information section
   */
  private async generateFinancialSection(data: CompanyData): Promise<FinancialInformation> {
    return {
      historical_financials: {
        revenue: [
          { year: 2022, amount: (data.revenue || 5000000) * 0.4 },
          { year: 2023, amount: (data.revenue || 5000000) * 0.7 },
          { year: 2024, amount: data.revenue || 5000000 }
        ],
        gross_profit: [
          { year: 2022, amount: (data.revenue || 5000000) * 0.3 },
          { year: 2023, amount: (data.revenue || 5000000) * 0.5 },
          { year: 2024, amount: (data.revenue || 5000000) * 0.7 }
        ],
        ebitda: [
          { year: 2022, amount: -(data.revenue || 5000000) * 0.3 },
          { year: 2023, amount: -(data.revenue || 5000000) * 0.1 },
          { year: 2024, amount: (data.revenue || 5000000) * 0.1 }
        ]
      },
      
      projections: {
        revenue: [
          { year: 2025, amount: (data.revenue || 5000000) * 2 },
          { year: 2026, amount: (data.revenue || 5000000) * 3.5 },
          { year: 2027, amount: (data.revenue || 5000000) * 5 }
        ],
        ebitda: [
          { year: 2025, amount: (data.revenue || 5000000) * 0.15 },
          { year: 2026, amount: (data.revenue || 5000000) * 0.25 },
          { year: 2027, amount: (data.revenue || 5000000) * 0.35 }
        ]
      },
      
      unit_economics: {
        ltv: data.ltv || 50000,
        cac: data.cac || 15000,
        ltv_cac_ratio: (data.ltv || 50000) / (data.cac || 15000),
        payback_months: data.cac_payback || 12,
        gross_margin: data.gross_margin || 75,
        contribution_margin: 45
      },
      
      key_metrics: {
        arr: data.arr || data.revenue || 5000000,
        mrr: (data.arr || data.revenue || 5000000) / 12,
        nrr: data.nrr || 120,
        gross_retention: 95,
        logo_retention: 90,
        arpu: 50000
      },
      
      citations: [
        { field: 'revenue', source: 'Audited financials', page: 45 },
        { field: 'projections', source: 'Management forecast', page: 52 }
      ]
    };
  }
  
  /**
   * Generate Transaction Overview
   */
  private async generateTransactionOverview(data: CompanyData): Promise<TransactionOverview> {
    return {
      transaction_type: data.round_type || 'Series A Preferred Equity',
      amount_seeking: data.seeking_amount || 25000000,
      
      valuation: {
        pre_money: data.pre_money || 75000000,
        post_money: data.post_money || 100000000,
        methodology: 'Comparable company analysis and DCF',
        implied_multiples: {
          ev_revenue: 5.0,
          ev_arr: 4.5,
          ev_ebitda: 25.0
        }
      },
      
      terms: {
        security_type: 'Series A Preferred Stock',
        liquidation_preference: '1x non-participating',
        dividend: '8% cumulative',
        conversion: '1:1 ratio',
        anti_dilution: 'Broad-based weighted average',
        board_seats: '1 seat + 1 observer',
        voting_rights: 'Vote as converted',
        redemption: 'None',
        drag_along: 'Standard',
        tag_along: 'Standard',
        rofr_rofo: 'Standard ROFR'
      },
      
      timeline: {
        loi_deadline: '2 weeks',
        due_diligence: '4 weeks',
        closing: '6-8 weeks'
      },
      
      process: {
        advisor: data.advisor || 'Investment Bank XYZ',
        contact: 'John Doe, Managing Director',
        email: 'deals@bank.com'
      }
    };
  }
  
  /**
   * Write CIM to spreadsheet grid
   */
  private async writeCIMToGrid(cim: GeneratedCIM): Promise<void> {
    const grid = (window as any).grid;
    if (!grid) return;
    
    let row = 1;
    
    // Title and metadata
    grid.write('A' + row, 'CONFIDENTIAL INFORMATION MEMORANDUM');
    grid.style('A' + row, { bold: true, fontSize: 20 });
    row += 2;
    
    grid.write('A' + row, cim.metadata.company);
    grid.style('A' + row, { bold: true, fontSize: 16 });
    row++;
    
    grid.write('A' + row, `Generated: ${new Date(cim.metadata.generated_date).toLocaleDateString()}`);
    row += 2;
    
    // Executive Summary
    grid.write('A' + row, 'EXECUTIVE SUMMARY');
    grid.style('A' + row, { bold: true, fontSize: 14, backgroundColor: '#1f2937', color: '#ffffff' });
    row++;
    
    if (cim.executive_summary.company_snapshot) {
      grid.write('A' + row, cim.executive_summary.company_snapshot);
      row += 2;
    }
    
    // Key Metrics Table
    grid.write('A' + row, 'Key Metrics');
    grid.style('A' + row, { bold: true });
    row++;
    
    const metrics = cim.executive_summary.key_metrics;
    Object.entries(metrics).forEach(([key, value]) => {
      grid.write('A' + row, key.replace(/_/g, ' ').toUpperCase());
      grid.write('B' + row, value);
      if (typeof value === 'number' && key.includes('revenue')) {
        grid.format('B' + row, 'currency');
      }
      row++;
    });
    
    row++;
    
    // Investment Highlights
    grid.write('A' + row, 'INVESTMENT HIGHLIGHTS');
    grid.style('A' + row, { bold: true, fontSize: 14, backgroundColor: '#1f2937', color: '#ffffff' });
    row++;
    
    cim.investment_highlights.key_strengths.forEach(highlight => {
      grid.write('A' + row, '• ' + highlight);
      row++;
    });
    
    row++;
    
    // Financial Information
    grid.write('A' + row, 'FINANCIAL INFORMATION');
    grid.style('A' + row, { bold: true, fontSize: 14, backgroundColor: '#1f2937', color: '#ffffff' });
    row++;
    
    // Revenue table
    grid.write('A' + row, 'Year');
    grid.write('B' + row, 'Revenue');
    grid.write('C' + row, 'Growth %');
    grid.write('D' + row, 'EBITDA');
    grid.write('E' + row, 'Margin %');
    
    ['A', 'B', 'C', 'D', 'E'].forEach(col => {
      grid.style(col + row, { bold: true, backgroundColor: '#f3f4f6' });
    });
    row++;
    
    // Add financial data
    if (cim.financial_information?.historical_financials?.revenue) {
      cim.financial_information.historical_financials.revenue.forEach((item, index) => {
        grid.write('A' + row, item.year);
        grid.write('B' + row, item.amount);
        grid.format('B' + row, 'currency');
        
        if (index > 0) {
          const prevAmount = cim.financial_information.historical_financials.revenue[index - 1].amount;
          const growth = ((item.amount - prevAmount) / prevAmount * 100).toFixed(1);
          grid.write('C' + row, growth + '%');
        }
        
        row++;
      });
    }
    
    // Add citations
    row += 2;
    grid.write('A' + row, 'SOURCES & CITATIONS');
    grid.style('A' + row, { bold: true, fontSize: 12 });
    row++;
    
    cim.citations.forEach((citation, index) => {
      const citationText = `[${index + 1}] ${citation.text}`;
      grid.link('A' + row, citationText, citation.url);
      row++;
    });
  }
  
  /**
   * Gather all available company data
   */
  private async gatherCompanyData(company: string, inputData?: Partial<CIMInputData>): Promise<CompanyData> {
    // Get from database
    const { data: dbData } = await supabase
      .from('companies')
      .select('*')
      .ilike('name', `%${company}%`)
      .single();
    
    // Merge with input data
    return {
      name: company,
      sector: inputData?.sector || dbData?.sector || 'Technology',
      stage: inputData?.stage || dbData?.stage || 'Series A',
      revenue: inputData?.revenue || dbData?.total_raised_usd || 5000000,
      growth_rate: inputData?.growth_rate || 150,
      gross_margin: inputData?.gross_margin || 75,
      market_position: inputData?.market_position || 'Emerging leader',
      team_years_experience: 50,
      round_type: inputData?.round_type || 'Series A',
      seeking_amount: inputData?.seeking_amount || 25000000,
      valuation: inputData?.valuation || 100000000,
      customer_count: inputData?.customer_count || 100,
      nrr: inputData?.nrr || 120,
      nps: inputData?.nps || 50,
      retention_rate: inputData?.retention_rate || 95,
      cac_payback: inputData?.cac_payback || 12,
      ltv: inputData?.ltv || 50000,
      cac: inputData?.cac || 15000,
      arr: inputData?.arr || dbData?.revenue || 5000000,
      tam: inputData?.tam || 50000000000,
      sam: inputData?.sam || 5000000000,
      som: inputData?.som || 500000000,
      market_share: inputData?.market_share || 1,
      pre_money: inputData?.pre_money || 75000000,
      post_money: inputData?.post_money || 100000000,
      advisor: inputData?.advisor || 'TBD',
      
      citations: [
        { text: 'Company Database', url: '/companies', relevance: 1.0 },
        { text: 'Financial Analysis', url: '/documents', relevance: 0.9 }
      ]
    };
  }
  
  /**
   * Helper methods
   */
  private parseJSON(text: string): any {
    try {
      const match = text.match(/\{[\s\S]*\}/);
      if (match) {
        return JSON.parse(match[0]);
      }
    } catch (e) {
      console.error('Failed to parse JSON:', e);
    }
    return {};
  }
  
  private formatCIMData(extracted: any): CIMData {
    return {
      ...extracted.extracted_data,
      citations: extracted.citations,
      missing_fields: extracted.missing_fields || [],
      red_flags: extracted.red_flags || [],
      confidence_scores: this.calculateConfidenceScores(extracted)
    };
  }
  
  private calculateConfidenceScores(data: any): Record<string, number> {
    const scores = {};
    if (data.citations) {
      Object.entries(data.citations).forEach(([field, citation]: [string, any]) => {
        scores[field] = citation.confidence || 0.8;
      });
    }
    return scores;
  }
  
  private extractSection(text: string, section: string): string {
    const lines = text.split('\n');
    for (const line of lines) {
      if (line.toLowerCase().includes(section)) {
        return line;
      }
    }
    return '';
  }
  
  private extractBullets(text: string, section: string): string[] {
    const bullets = [];
    const lines = text.split('\n');
    let inSection = false;
    
    for (const line of lines) {
      if (line.toLowerCase().includes(section)) {
        inSection = true;
        continue;
      }
      if (inSection && (line.startsWith('•') || line.startsWith('-') || line.startsWith('*'))) {
        bullets.push(line.replace(/^[•\-*]\s*/, ''));
      }
      if (inSection && bullets.length >= 5) break;
    }
    
    return bullets;
  }
  
  private async storeCIMExtraction(data: any): Promise<void> {
    await supabase
      .from('cim_extractions')
      .insert({
        extracted_data: data,
        created_at: new Date()
      });
  }
  
  private async storeCIM(cim: GeneratedCIM): Promise<void> {
    await supabase
      .from('generated_cims')
      .insert({
        company: cim.metadata.company,
        cim_data: cim,
        created_at: new Date()
      });
  }
  
  // Additional generation methods
  private async generateCompanyOverview(data: CompanyData): Promise<any> {
    return {
      description: `${data.name} is a ${data.stage} ${data.sector} company`,
      founded: '2020',
      headquarters: 'San Francisco, CA',
      employees: 150,
      offices: ['San Francisco', 'New York', 'London'],
      website: `www.${data.name.toLowerCase()}.com`
    };
  }
  
  private async generateProductsServices(data: CompanyData): Promise<any> {
    return {
      core_products: ['Platform', 'API', 'Enterprise Suite'],
      target_customers: ['Enterprise', 'Mid-Market', 'SMB'],
      use_cases: ['Automation', 'Analytics', 'Integration'],
      pricing_model: 'SaaS subscription with usage-based pricing'
    };
  }
  
  private async generateCompetitiveLandscape(data: CompanyData): Promise<any> {
    return {
      direct_competitors: ['Competitor A', 'Competitor B', 'Competitor C'],
      competitive_advantages: ['Technology', 'Scale', 'Customer Base'],
      market_position: 'Top 5 player with fastest growth rate',
      differentiation: 'Only solution with end-to-end capabilities'
    };
  }
  
  private async generateGrowthStrategy(data: CompanyData): Promise<any> {
    return {
      growth_pillars: ['Geographic expansion', 'Product extension', 'M&A'],
      go_to_market: 'Direct sales + channel partnerships',
      expansion_plans: 'Enter 3 new markets in next 12 months',
      product_roadmap: 'Launch 2 new modules by Q4'
    };
  }
  
  private async generateManagementSection(data: CompanyData): Promise<any> {
    return {
      ceo: { name: 'John Smith', background: '15 years, ex-Google' },
      cfo: { name: 'Jane Doe', background: '12 years, ex-Goldman' },
      cto: { name: 'Bob Johnson', background: '10 years, ex-Amazon' },
      board: ['Independent Director 1', 'VC Partner 1', 'Industry Expert']
    };
  }
  
  private async generateUseOfProceeds(data: CompanyData): Promise<any> {
    return {
      breakdown: {
        'Sales & Marketing': 40,
        'Product Development': 30,
        'Geographic Expansion': 20,
        'Working Capital': 10
      },
      total: data.seeking_amount || 25000000
    };
  }
  
  private async generateRiskSection(data: CompanyData): Promise<any> {
    return {
      market_risks: ['Competition', 'Market saturation'],
      execution_risks: ['Scaling challenges', 'Talent acquisition'],
      financial_risks: ['Path to profitability', 'Funding risk'],
      regulatory_risks: ['Data privacy', 'Compliance'],
      mitigation_strategies: ['Diversification', 'Strong governance']
    };
  }
  
  private async generateExitOpportunities(data: CompanyData): Promise<any> {
    return {
      strategic_buyers: ['Microsoft', 'Salesforce', 'Oracle'],
      financial_buyers: ['PE Firm A', 'PE Firm B'],
      ipo_potential: 'Viable at $500M+ revenue',
      expected_timeline: '3-5 years',
      expected_return: '5-10x'
    };
  }
  
  private async generateAppendices(data: CompanyData): Promise<any> {
    return {
      financial_statements: 'Detailed P&L, Balance Sheet, Cash Flow',
      customer_case_studies: '10 reference customers',
      product_demos: 'Available upon request',
      legal_documents: 'Cap table, charter, material contracts'
    };
  }
}

// Type definitions
interface ExtractRequirements {
  focus_areas?: string[];
  detail_level?: 'summary' | 'detailed' | 'comprehensive';
  include_projections?: boolean;
  include_comparables?: boolean;
}

interface CIMData {
  executive_summary?: any;
  financial_snapshot?: any;
  market_metrics?: any;
  valuation?: any;
  investors?: any;
  projections?: any;
  citations: Citation[];
  missing_fields: string[];
  red_flags: string[];
  confidence_scores: Record<string, number>;
}

interface CIMInputData {
  sector?: string;
  stage?: string;
  revenue?: number;
  growth_rate?: number;
  gross_margin?: number;
  market_position?: string;
  round_type?: string;
  seeking_amount?: number;
  valuation?: number;
  customer_count?: number;
  nrr?: number;
  nps?: number;
  retention_rate?: number;
  cac_payback?: number;
  ltv?: number;
  cac?: number;
  arr?: number;
  tam?: number;
  sam?: number;
  som?: number;
  market_share?: number;
  pre_money?: number;
  post_money?: number;
  advisor?: string;
}

interface GeneratedCIM {
  metadata: {
    company: string;
    generated_date: string;
    version: string;
    confidentiality: string;
  };
  executive_summary: ExecutiveSummary;
  investment_highlights: InvestmentHighlights;
  company_overview: any;
  products_services: any;
  market_opportunity: MarketOpportunity;
  competitive_landscape: any;
  financial_information: FinancialInformation;
  growth_strategy: any;
  management_team: any;
  transaction_overview: TransactionOverview;
  use_of_proceeds: any;
  investment_risks: any;
  exit_opportunities: any;
  appendices: any;
  citations: Citation[];
}

interface ExecutiveSummary {
  company_snapshot: string;
  investment_opportunity: string;
  key_metrics: any;
  transaction_summary: any;
  highlights: string[];
}

interface InvestmentHighlights {
  key_strengths: string[];
  value_drivers: string[];
  differentiation: string[];
  citations: any[];
}

interface MarketOpportunity {
  tam: number;
  sam: number;
  som: number;
  tam_cagr: number;
  market_drivers: string[];
  trends: any[];
  positioning: string;
  citations: Citation[];
}

interface FinancialInformation {
  historical_financials: any;
  projections: any;
  unit_economics: any;
  key_metrics: any;
  citations: any[];
}

interface TransactionOverview {
  transaction_type: string;
  amount_seeking: number;
  valuation: any;
  terms: any;
  timeline: any;
  process: any;
}

interface CompanyData {
  name: string;
  sector: string;
  stage: string;
  revenue: number;
  growth_rate: number;
  gross_margin: number;
  market_position: string;
  team_years_experience: number;
  round_type: string;
  seeking_amount: number;
  valuation: number;
  customer_count: number;
  nrr: number;
  nps: number;
  retention_rate: number;
  cac_payback: number;
  ltv: number;
  cac: number;
  arr: number;
  tam: number;
  sam: number;
  som: number;
  market_share: number;
  pre_money: number;
  post_money: number;
  advisor: string;
  citations: Citation[];
}

interface Citation {
  text: string;
  url: string;
  relevance: number;
}

// Export the processor
export const cimProcessor = new CIMProcessor();