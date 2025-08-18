/**
 * Bottom-Up Market Sizing Framework
 * Based on real fund formation and emerging manager data
 */

export interface MarketSizingData {
  category: string;
  totalFunds: number;
  avgTicketSize: number;
  sources: string[];
  calculation: string;
}

export const FUND_FORMATION_DATA = {
  // Total Fund Universe
  totalPrivateMarkets: {
    global: 39000, // Total private equity funds globally
    us: 18000, // US funds alone
    sub1B: 1650, // Funds under $1B raised in one year
    sources: [
      'McKinsey Private Markets Annual Review 2024',
      'Private Equity International Database',
      'Warren Senate Report on PE Statistics'
    ]
  },

  // Annual Fund Formation
  annualFormation: {
    vc: {
      2024: 1344,
      2023: 2333,
      avgTicketSize: 5000,
      totalActive: 3677, // 2023 + 2024 still fundraising
      tam: 18385000, // 3677 × $5,000
      sources: ['VentureBeat Global VC Report 2024', 'NVCA PitchBook']
    },
    pe: {
      annual: 4375,
      avgTicketSize: 20000,
      viableActive: 3000, // Conservative estimate
      tam: 60000000, // 3000 × $20,000
      sources: ['Paul Weiss PE Fundraising Q1 2024']
    },
    credit: {
      total: 1080,
      avgTicketSize: 20000,
      tam: 21600000, // 1080 × $20,000
      sources: ['BNY Mellon - The Rise of Private Credit']
    }
  },

  // TAM Calculation
  tam: {
    total: 99985000, // ~$100M TAM
    breakdown: {
      vc: 18385000,
      pe: 60000000,
      credit: 21600000
    }
  },

  // SAM - Emerging Managers
  sam: {
    vc: {
      emergingManagers: 800, // Sub $100M AUM
      viable: 600, // 400 broke + 200 slightly over
      avgTicket: 5000,
      total: 3000000,
      source: 'LTV Capital Survey of 800+ Emerging Managers'
    },
    pe: {
      emergingPerYear: 15,
      activeVintages: 3,
      total: 45,
      avgTicket: 20000,
      total_value: 900000,
      source: 'AI-CIO Emerging Manager Report'
    },
    credit: {
      estimated: 15,
      avgTicket: 20000,
      total: 300000
    },
    total: 4200000 // ~$4.2M SAM
  },

  // SOM would be based on conversion rates and go-to-market strategy
  som: {
    assumptions: {
      vcConversion: 0.10, // 10% of emerging managers
      peConversion: 0.20, // 20% of PE emerging (fewer players)
      creditConversion: 0.15 // 15% of credit funds
    },
    calculation: 'SAM × Conversion Rate × Market Share'
  }
};

/**
 * Market Sizing Instructions for Spreadsheet Agent
 */
export const MARKET_SIZING_METHODOLOGY = `
=== BOTTOM-UP MARKET SIZING FRAMEWORK ===

STEP 1: IDENTIFY TOTAL UNIVERSE
- Start with total number of potential customers
- Use industry reports, databases, regulatory filings
- Segment by geography, size, type

STEP 2: CALCULATE TAM (Total Addressable Market)
TAM = Total Customers × Average Revenue Per Customer
- For funds: Active funds × Average ticket size
- For companies: Total companies × Average contract value
- Use multi-year windows for cyclical businesses

STEP 3: CALCULATE SAM (Serviceable Addressable Market)
Filter TAM by:
- Geographic reach (where you can actually serve)
- Customer segment (who actually needs your product)
- Regulatory constraints
- Technical requirements

Example for Emerging Managers:
- TAM: 3,677 VC funds × $5K = $18.4M
- SAM: 600 emerging managers × $5K = $3M (only sub-$100M funds)

STEP 4: CALCULATE SOM (Serviceable Obtainable Market)
Apply realistic capture rates:
- Year 1: 1-3% of SAM
- Year 3: 5-10% of SAM  
- Year 5: 15-25% of SAM
- Consider competition, sales capacity, market maturity

STEP 5: TRIANGULATION CHECKS
Validate with:
- Top-down analysis (% of total market spend)
- Comparable company metrics
- Customer survey data
- Pilot program conversion rates

FUND MARKET SPECIFIC DATA (2024):
VC Funds:
- 1,344 new funds raised in 2024 (down from 2,333 in 2023)
- Average data/software spend: $5,000/year
- 3,677 active funds (2023+2024 vintages)
- TAM: $18.4M

PE Funds:
- 4,375 funds globally fundraising
- Average spend: $20,000/year
- ~3,000 viable targets
- TAM: $60M

Credit Funds:
- 1,080 active funds
- Average spend: $20,000/year
- TAM: $21.6M

Emerging Managers (KEY SEGMENT):
- 800 VC emerging managers (<$100M AUM)
- 45 PE emerging managers (3 vintages × 15/year)
- 15 Credit emerging managers
- Higher price sensitivity but easier to reach
- Total SAM: ~$4.2M

SOURCES TO CITE:
- McKinsey Global Private Markets Review 2024
- Private Equity International Fund Database
- NVCA/PitchBook Venture Monitor
- Paul Weiss PE Fundraising Reports
- BNY Mellon Private Credit Analysis
- LTV Capital Emerging Manager Survey
- Warren Senate PE Statistics Report

IMPORTANT: When building market sizing models:
1. Show your math clearly with assumptions stated
2. Use conservative estimates for SOM
3. Account for market timing and adoption curves
4. Compare bottom-up to top-down as sanity check
5. Update quarterly with new fund formation data
`;

/**
 * Generate market sizing grid for spreadsheet
 */
export function generateMarketSizingGrid(segment: string = 'all'): any[][] {
  const grid: any[][] = [];
  
  // Headers
  grid.push(['Market Sizing Analysis', '', '', '', '']);
  grid.push(['Segment', 'Total Funds', 'Avg Ticket', 'Market Size', 'Source']);
  grid.push(['', '', '', '', '']);
  
  // TAM Section
  grid.push(['TAM (Total Addressable Market)', '', '', '', '']);
  grid.push(['VC Funds', 3677, '$5,000', '=$B5*$C5', 'NVCA/PitchBook 2024']);
  grid.push(['PE Funds', 3000, '$20,000', '=$B6*$C6', 'Paul Weiss Q1 2024']);
  grid.push(['Credit Funds', 1080, '$20,000', '=$B7*$C7', 'BNY Mellon 2024']);
  grid.push(['Total TAM', '=SUM(B5:B7)', '', '=SUM(D5:D7)', '']);
  grid.push(['', '', '', '', '']);
  
  // SAM Section
  grid.push(['SAM (Serviceable Addressable Market)', '', '', '', '']);
  grid.push(['VC Emerging (<$100M)', 600, '$5,000', '=$B11*$C11', 'LTV Capital Survey']);
  grid.push(['PE Emerging', 45, '$20,000', '=$B12*$C12', 'AI-CIO Report']);
  grid.push(['Credit Emerging', 15, '$20,000', '=$B13*$C13', 'Industry Estimate']);
  grid.push(['Total SAM', '=SUM(B11:B13)', '', '=SUM(D11:D13)', '']);
  grid.push(['SAM % of TAM', '', '', '=D14/D8', '']);
  grid.push(['', '', '', '', '']);
  
  // SOM Section
  grid.push(['SOM (Serviceable Obtainable Market)', '', '', '', '']);
  grid.push(['Conversion Rate', 'Year 1', 'Year 3', 'Year 5', '']);
  grid.push(['VC', '2%', '7%', '15%', '']);
  grid.push(['PE', '5%', '15%', '25%', '']);
  grid.push(['Credit', '3%', '10%', '20%', '']);
  grid.push(['', '', '', '', '']);
  grid.push(['SOM Projection', 'Year 1', 'Year 3', 'Year 5', '']);
  grid.push(['Revenue', '=$D14*0.02', '=$D14*0.08', '=$D14*0.18', '']);
  grid.push(['Customers', '=D24/$C11', '=E24/$C11', '=F24/$C11', '']);
  
  return grid;
}

/**
 * Market sizing prompts for specific industries
 */
export const INDUSTRY_SPECIFIC_PROMPTS = {
  saas: 'Calculate seats × price per seat × companies in segment',
  marketplace: 'GMV × take rate × number of transactions',
  fintech: 'Payment volume × basis points × number of merchants',
  healthcare: 'Patients × procedures × reimbursement rate',
  edtech: 'Students × schools × price per student',
  infrastructure: 'Compute hours × price per hour × number of workloads'
};