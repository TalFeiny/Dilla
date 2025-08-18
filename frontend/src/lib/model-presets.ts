/**
 * Financial Model Presets for Spreadsheet Agent
 * Comprehensive templates for VC/PE analysis
 */

export interface ModelPreset {
  id: string;
  name: string;
  category: 'valuation' | 'fundraising' | 'analysis' | 'structure' | 'comparables';
  description: string;
  requiredInputs: string[];
  gridTemplate: {
    headers: string[];
    rows: Array<{
      label: string;
      values: (string | number | null)[];
      formulas?: string[];
    }>;
  };
  instructions: string;
  apiEndpoint?: string;
}

export const MODEL_PRESETS: ModelPreset[] = [
  {
    id: 'dcf',
    name: 'DCF Model',
    category: 'valuation',
    description: 'Discounted Cash Flow valuation with sensitivity analysis',
    requiredInputs: ['company_name', 'current_revenue', 'growth_rate', 'wacc'],
    gridTemplate: {
      headers: ['', 'Year 0', 'Year 1', 'Year 2', 'Year 3', 'Year 4', 'Year 5', 'Terminal'],
      rows: [
        { label: 'Revenue', values: [null, 0, 0, 0, 0, 0, 0, 0] },
        { label: 'Revenue Growth %', values: [null, null, '25%', '25%', '20%', '15%', '10%', '3%'] },
        { label: 'EBITDA', values: [null, 0, 0, 0, 0, 0, 0, 0] },
        { label: 'EBITDA Margin %', values: [null, '20%', '22%', '25%', '28%', '30%', '32%', '35%'] },
        { label: 'Tax Rate', values: [null, '21%', '21%', '21%', '21%', '21%', '21%', '21%'] },
        { label: 'NOPAT', values: [null, 0, 0, 0, 0, 0, 0, 0] },
        { label: 'Capex', values: [null, 0, 0, 0, 0, 0, 0, 0] },
        { label: 'NWC Change', values: [null, 0, 0, 0, 0, 0, 0, 0] },
        { label: 'Free Cash Flow', values: [null, 0, 0, 0, 0, 0, 0, 0] },
        { label: 'Discount Factor', values: [null, 1, 0, 0, 0, 0, 0, 0] },
        { label: 'PV of FCF', values: [null, 0, 0, 0, 0, 0, 0, 0] },
        { label: '', values: [null, null, null, null, null, null, null, null] },
        { label: 'Terminal Value', values: [null, null, null, null, null, null, null, 0] },
        { label: 'PV of Terminal', values: [null, null, null, null, null, null, null, 0] },
        { label: 'Enterprise Value', values: [0, null, null, null, null, null, null, null] },
        { label: 'Net Debt', values: [0, null, null, null, null, null, null, null] },
        { label: 'Equity Value', values: [0, null, null, null, null, null, null, null] },
      ]
    },
    instructions: 'Build a 5-year DCF model with terminal value using Gordon Growth. Calculate WACC, apply appropriate margins, and show sensitivity analysis.',
    apiEndpoint: '/api/models/dcf'
  },
  
  {
    id: 'cim',
    name: 'CIM Template',
    category: 'analysis',
    description: 'Confidential Information Memorandum structure',
    requiredInputs: ['company_name', 'sector', 'revenue', 'ebitda'],
    gridTemplate: {
      headers: ['Section', 'FY-2', 'FY-1', 'FY0', 'FY1', 'FY2', 'FY3'],
      rows: [
        { label: 'Executive Summary', values: ['', '', '', '', '', '', ''] },
        { label: 'Investment Highlights', values: ['', '', '', '', '', '', ''] },
        { label: 'Company Overview', values: ['', '', '', '', '', '', ''] },
        { label: 'Revenue', values: ['', 0, 0, 0, 0, 0, 0] },
        { label: 'Gross Profit', values: ['', 0, 0, 0, 0, 0, 0] },
        { label: 'EBITDA', values: ['', 0, 0, 0, 0, 0, 0] },
        { label: 'EBITDA Margin', values: ['', '0%', '0%', '0%', '0%', '0%', '0%'] },
        { label: 'Capex', values: ['', 0, 0, 0, 0, 0, 0] },
        { label: 'Free Cash Flow', values: ['', 0, 0, 0, 0, 0, 0] },
        { label: 'Market Analysis', values: ['', '', '', '', '', '', ''] },
        { label: 'TAM', values: ['', 0, 0, 0, 0, 0, 0] },
        { label: 'Market Share', values: ['', '0%', '0%', '0%', '0%', '0%', '0%'] },
        { label: 'Competitive Position', values: ['', '', '', '', '', '', ''] },
        { label: 'Management Team', values: ['', '', '', '', '', '', ''] },
        { label: 'Transaction Overview', values: ['', '', '', '', '', '', ''] },
        { label: 'Use of Proceeds', values: ['', '', '', '', '', '', ''] },
        { label: 'Exit Strategy', values: ['', '', '', '', '', '', ''] },
      ]
    },
    instructions: 'Create a comprehensive CIM with historical financials, projections, market analysis, competitive landscape, and transaction details.',
    apiEndpoint: '/api/models/cim'
  },

  {
    id: 'investment-memo',
    name: 'Investment Memo',
    category: 'analysis',
    description: 'VC investment committee memo template',
    requiredInputs: ['company_name', 'round_size', 'valuation', 'ownership'],
    gridTemplate: {
      headers: ['Component', 'Details', 'Score', 'Weight', 'Weighted Score'],
      rows: [
        { label: 'Executive Summary', values: ['', '', 0, '10%', 0] },
        { label: 'Investment Thesis', values: ['', '', 0, '15%', 0] },
        { label: 'Market Opportunity', values: ['', '', 0, '20%', 0] },
        { label: 'TAM Analysis', values: ['', '', 0, '10%', 0] },
        { label: 'Product/Technology', values: ['', '', 0, '15%', 0] },
        { label: 'Business Model', values: ['', '', 0, '10%', 0] },
        { label: 'Team Assessment', values: ['', '', 0, '15%', 0] },
        { label: 'Financial Analysis', values: ['', '', 0, '15%', 0] },
        { label: 'Unit Economics', values: ['', '', 0, '10%', 0] },
        { label: 'Competition', values: ['', '', 0, '10%', 0] },
        { label: 'Risks & Mitigation', values: ['', '', 0, '5%', 0] },
        { label: 'Deal Terms', values: ['', '', 0, '10%', 0] },
        { label: 'Exit Analysis', values: ['', '', 0, '10%', 0] },
        { label: 'Total Score', values: ['', '', 0, '100%', 0] },
        { label: 'Recommendation', values: ['', '', '', '', ''] },
      ]
    },
    instructions: 'Prepare investment committee memo with scoring framework, thesis, market analysis, team assessment, financials, and deal terms.',
    apiEndpoint: '/api/models/investment-memo'
  },

  {
    id: 'cap-table',
    name: 'Cap Table & Funding Trajectory',
    category: 'fundraising',
    description: 'Capitalization table with funding rounds and dilution analysis',
    requiredInputs: ['company_name', 'founders_shares', 'current_round'],
    gridTemplate: {
      headers: ['Shareholder', 'Seed', 'Series A', 'Series B', 'Series C', 'Series D', 'Exit'],
      rows: [
        { label: 'Founders', values: ['', '80%', '64%', '48%', '36%', '27%', '27%'] },
        { label: 'Employees (ESOP)', values: ['', '10%', '12%', '13%', '14%', '15%', '15%'] },
        { label: 'Seed Investors', values: ['', '10%', '8%', '6%', '4.5%', '3.4%', '3.4%'] },
        { label: 'Series A Investors', values: ['', '0%', '16%', '12%', '9%', '6.8%', '6.8%'] },
        { label: 'Series B Investors', values: ['', '0%', '0%', '21%', '15.8%', '11.8%', '11.8%'] },
        { label: 'Series C Investors', values: ['', '0%', '0%', '0%', '20.7%', '15.5%', '15.5%'] },
        { label: 'Series D Investors', values: ['', '0%', '0%', '0%', '0%', '20.5%', '20.5%'] },
        { label: 'Total', values: ['', '100%', '100%', '100%', '100%', '100%', '100%'] },
        { label: '', values: ['', '', '', '', '', '', ''] },
        { label: 'Pre-Money Valuation', values: ['', 5000000, 25000000, 100000000, 300000000, 700000000, 1500000000] },
        { label: 'Round Size', values: ['', 1000000, 8000000, 30000000, 80000000, 200000000, 0] },
        { label: 'Post-Money Valuation', values: ['', 6000000, 33000000, 130000000, 380000000, 900000000, 1500000000] },
        { label: 'Share Price', values: ['', 0.06, 0.33, 1.30, 3.80, 9.00, 15.00] },
        { label: 'Shares Outstanding', values: ['', 100000000, 100000000, 100000000, 100000000, 100000000, 100000000] },
      ]
    },
    instructions: 'Build complete cap table showing ownership evolution through funding rounds, calculate dilution, and project exit scenarios.',
    apiEndpoint: '/api/models/cap-table'
  },

  {
    id: 'warrants-ratchets',
    name: 'Warrants & Ratchets',
    category: 'structure',
    description: 'Anti-dilution provisions and warrant coverage analysis',
    requiredInputs: ['company_name', 'warrant_coverage', 'ratchet_type'],
    gridTemplate: {
      headers: ['Provision', 'Current', 'Scenario 1', 'Scenario 2', 'Scenario 3', 'Impact'],
      rows: [
        { label: 'Share Price', values: ['', 10, 8, 5, 3, ''] },
        { label: 'Shares Outstanding', values: ['', 1000000, 1000000, 1000000, 1000000, ''] },
        { label: 'Warrant Coverage', values: ['', '20%', '20%', '20%', '20%', ''] },
        { label: 'Warrant Strike Price', values: ['', 10, 10, 10, 10, ''] },
        { label: 'Warrants Outstanding', values: ['', 200000, 200000, 200000, 200000, ''] },
        { label: 'Ratchet Type', values: ['Full Ratchet', '', '', '', '', ''] },
        { label: 'Original Investment', values: ['', 5000000, 5000000, 5000000, 5000000, ''] },
        { label: 'Original Shares', values: ['', 500000, 500000, 500000, 500000, ''] },
        { label: 'Adjusted Shares (Ratchet)', values: ['', 500000, 625000, 1000000, 1666667, ''] },
        { label: 'Additional Shares Issued', values: ['', 0, 125000, 500000, 1166667, ''] },
        { label: 'Dilution to Common', values: ['', '0%', '11%', '33%', '54%', ''] },
        { label: 'Warrant Value', values: ['', 0, 0, 0, 0, ''] },
        { label: 'Total Economic Interest', values: ['', '50%', '56%', '67%', '77%', ''] },
      ]
    },
    instructions: 'Model warrant coverage and anti-dilution provisions (full ratchet, weighted average) with scenario analysis.',
    apiEndpoint: '/api/models/warrants-ratchets'
  },

  {
    id: 'private-credit',
    name: 'Private Credit Analysis',
    category: 'structure',
    description: 'Debt financing structure and covenant analysis',
    requiredInputs: ['company_name', 'loan_amount', 'interest_rate', 'term'],
    gridTemplate: {
      headers: ['Metric', 'Q1', 'Q2', 'Q3', 'Q4', 'Year 1', 'Year 2', 'Year 3'],
      rows: [
        { label: 'Revenue', values: ['', 0, 0, 0, 0, 0, 0, 0] },
        { label: 'EBITDA', values: ['', 0, 0, 0, 0, 0, 0, 0] },
        { label: 'Interest Expense', values: ['', 0, 0, 0, 0, 0, 0, 0] },
        { label: 'Debt Service', values: ['', 0, 0, 0, 0, 0, 0, 0] },
        { label: 'Free Cash Flow', values: ['', 0, 0, 0, 0, 0, 0, 0] },
        { label: '', values: ['', '', '', '', '', '', '', ''] },
        { label: 'Covenants', values: ['', '', '', '', '', '', '', ''] },
        { label: 'Debt/EBITDA', values: ['', 0, 0, 0, 0, 0, 0, 0] },
        { label: 'DSCR', values: ['', 0, 0, 0, 0, 0, 0, 0] },
        { label: 'Interest Coverage', values: ['', 0, 0, 0, 0, 0, 0, 0] },
        { label: 'Fixed Charge Coverage', values: ['', 0, 0, 0, 0, 0, 0, 0] },
        { label: 'Minimum Cash', values: ['', 0, 0, 0, 0, 0, 0, 0] },
        { label: '', values: ['', '', '', '', '', '', '', ''] },
        { label: 'Loan Balance', values: ['', 0, 0, 0, 0, 0, 0, 0] },
        { label: 'Cash Interest', values: ['', 0, 0, 0, 0, 0, 0, 0] },
        { label: 'PIK Interest', values: ['', 0, 0, 0, 0, 0, 0, 0] },
        { label: 'Principal Payment', values: ['', 0, 0, 0, 0, 0, 0, 0] },
        { label: 'Ending Balance', values: ['', 0, 0, 0, 0, 0, 0, 0] },
      ]
    },
    instructions: 'Create private credit model with loan amortization, covenant testing, DSCR calculation, and stress testing.',
    apiEndpoint: '/api/models/private-credit'
  },

  {
    id: 'forward-multiples',
    name: 'Forward Revenue Multiples',
    category: 'valuation',
    description: 'Forward-looking valuation multiples analysis',
    requiredInputs: ['company_name', 'current_revenue', 'growth_rate'],
    gridTemplate: {
      headers: ['Metric', 'Current', 'NTM', 'Year 2', 'Year 3', 'Year 4', 'Year 5'],
      rows: [
        { label: 'Revenue', values: ['', 0, 0, 0, 0, 0, 0] },
        { label: 'Growth Rate', values: ['', '0%', '0%', '0%', '0%', '0%', '0%'] },
        { label: 'EBITDA', values: ['', 0, 0, 0, 0, 0, 0] },
        { label: 'EBITDA Margin', values: ['', '0%', '0%', '0%', '0%', '0%', '0%'] },
        { label: '', values: ['', '', '', '', '', '', ''] },
        { label: 'Enterprise Value', values: ['', 0, 0, 0, 0, 0, 0] },
        { label: 'EV/Revenue', values: ['', 0, 0, 0, 0, 0, 0] },
        { label: 'EV/EBITDA', values: ['', 0, 0, 0, 0, 0, 0] },
        { label: '', values: ['', '', '', '', '', '', ''] },
        { label: 'Peer Multiples', values: ['', '', '', '', '', '', ''] },
        { label: 'Peer 1 EV/Rev', values: ['', 0, 0, 0, 0, 0, 0] },
        { label: 'Peer 2 EV/Rev', values: ['', 0, 0, 0, 0, 0, 0] },
        { label: 'Peer 3 EV/Rev', values: ['', 0, 0, 0, 0, 0, 0] },
        { label: 'Median Multiple', values: ['', 0, 0, 0, 0, 0, 0] },
        { label: 'Premium/Discount', values: ['', '0%', '0%', '0%', '0%', '0%', '0%'] },
      ]
    },
    instructions: 'Calculate forward revenue and EBITDA multiples, compare to peer group, and analyze valuation trends.',
    apiEndpoint: '/api/models/forward-multiples'
  },

  {
    id: 'comparables',
    name: 'Company Comparables',
    category: 'comparables',
    description: 'Comprehensive comparables analysis with trading and transaction multiples',
    requiredInputs: ['company_name', 'sector', 'revenue_range'],
    gridTemplate: {
      headers: ['Company', 'Revenue', 'Growth', 'EBITDA Margin', 'EV', 'EV/Rev', 'EV/EBITDA', 'Score'],
      rows: [
        { label: 'Target Company', values: ['', 0, '0%', '0%', 0, 0, 0, 0] },
        { label: '', values: ['', '', '', '', '', '', '', ''] },
        { label: 'Trading Comps', values: ['', '', '', '', '', '', '', ''] },
        { label: 'Comp 1', values: ['', 0, '0%', '0%', 0, 0, 0, 0] },
        { label: 'Comp 2', values: ['', 0, '0%', '0%', 0, 0, 0, 0] },
        { label: 'Comp 3', values: ['', 0, '0%', '0%', 0, 0, 0, 0] },
        { label: 'Comp 4', values: ['', 0, '0%', '0%', 0, 0, 0, 0] },
        { label: 'Comp 5', values: ['', 0, '0%', '0%', 0, 0, 0, 0] },
        { label: 'Median', values: ['', 0, '0%', '0%', 0, 0, 0, 0] },
        { label: 'Mean', values: ['', 0, '0%', '0%', 0, 0, 0, 0] },
        { label: '', values: ['', '', '', '', '', '', '', ''] },
        { label: 'Transaction Comps', values: ['', '', '', '', '', '', '', ''] },
        { label: 'Deal 1', values: ['', 0, '0%', '0%', 0, 0, 0, 0] },
        { label: 'Deal 2', values: ['', 0, '0%', '0%', 0, 0, 0, 0] },
        { label: 'Deal 3', values: ['', 0, '0%', '0%', 0, 0, 0, 0] },
        { label: 'Median', values: ['', 0, '0%', '0%', 0, 0, 0, 0] },
        { label: '', values: ['', '', '', '', '', '', '', ''] },
        { label: 'Implied Valuation', values: ['', 0, 0, 0, 0, 0, 0, 0] },
      ]
    },
    instructions: 'Fetch comparable companies and recent transactions, calculate multiples, and derive implied valuation ranges.',
    apiEndpoint: '/api/models/comparables'
  },

  {
    id: 'waterfall',
    name: 'Exit Waterfall',
    category: 'structure',
    description: 'Liquidation preference waterfall with participating preferred',
    requiredInputs: ['company_name', 'exit_value', 'preferred_stack'],
    gridTemplate: {
      headers: ['Exit Value', '$50M', '$100M', '$250M', '$500M', '$1B', '$2B'],
      rows: [
        { label: 'Series D Liquidation Pref', values: ['', 0, 0, 0, 0, 0, 0] },
        { label: 'Series C Liquidation Pref', values: ['', 0, 0, 0, 0, 0, 0] },
        { label: 'Series B Liquidation Pref', values: ['', 0, 0, 0, 0, 0, 0] },
        { label: 'Series A Liquidation Pref', values: ['', 0, 0, 0, 0, 0, 0] },
        { label: 'Seed Liquidation Pref', values: ['', 0, 0, 0, 0, 0, 0] },
        { label: 'Total Liquidation Prefs', values: ['', 0, 0, 0, 0, 0, 0] },
        { label: '', values: ['', '', '', '', '', '', ''] },
        { label: 'Remaining for Participation', values: ['', 0, 0, 0, 0, 0, 0] },
        { label: 'Series D Participation', values: ['', 0, 0, 0, 0, 0, 0] },
        { label: 'Series C Participation', values: ['', 0, 0, 0, 0, 0, 0] },
        { label: 'Series B Participation', values: ['', 0, 0, 0, 0, 0, 0] },
        { label: 'Series A Participation', values: ['', 0, 0, 0, 0, 0, 0] },
        { label: 'Common Stock', values: ['', 0, 0, 0, 0, 0, 0] },
        { label: '', values: ['', '', '', '', '', '', ''] },
        { label: 'Founders', values: ['', 0, 0, 0, 0, 0, 0] },
        { label: 'Employees', values: ['', 0, 0, 0, 0, 0, 0] },
        { label: 'Total Distribution', values: ['', 0, 0, 0, 0, 0, 0] },
        { label: 'Check Sum', values: ['', 0, 0, 0, 0, 0, 0] },
      ]
    },
    instructions: 'Model exit waterfall with liquidation preferences, participation rights, and distribution across stakeholders.',
    apiEndpoint: '/api/models/waterfall'
  },

  {
    id: 'revenue-comparables',
    name: 'Revenue Comparables Analysis',
    category: 'comparables',
    description: 'Side-by-side revenue comparison with growth trajectories',
    requiredInputs: ['company_names', 'time_period'],
    gridTemplate: {
      headers: ['Company', 'Y-3', 'Y-2', 'Y-1', 'Current', 'Y+1', 'Y+2', 'CAGR', 'Multiple'],
      rows: [
        { label: 'Company 1', values: ['', 0, 0, 0, 0, 0, 0, '0%', 0] },
        { label: 'Company 2', values: ['', 0, 0, 0, 0, 0, 0, '0%', 0] },
        { label: 'Company 3', values: ['', 0, 0, 0, 0, 0, 0, '0%', 0] },
        { label: 'Company 4', values: ['', 0, 0, 0, 0, 0, 0, '0%', 0] },
        { label: 'Company 5', values: ['', 0, 0, 0, 0, 0, 0, '0%', 0] },
        { label: '', values: ['', '', '', '', '', '', '', '', ''] },
        { label: 'Median', values: ['', 0, 0, 0, 0, 0, 0, '0%', 0] },
        { label: 'Mean', values: ['', 0, 0, 0, 0, 0, 0, '0%', 0] },
        { label: 'Top Quartile', values: ['', 0, 0, 0, 0, 0, 0, '0%', 0] },
        { label: 'Bottom Quartile', values: ['', 0, 0, 0, 0, 0, 0, '0%', 0] },
      ]
    },
    instructions: 'Compare revenue trajectories across multiple companies with growth rates and valuation multiples.',
    apiEndpoint: '/api/models/revenue-comparables'
  }
];

export function getPresetById(id: string): ModelPreset | undefined {
  return MODEL_PRESETS.find(preset => preset.id === id);
}

export function getPresetsByCategory(category: string): ModelPreset[] {
  return MODEL_PRESETS.filter(preset => preset.category === category);
}

export function generateInstructions(preset: ModelPreset, inputs: Record<string, any>): string {
  let instructions = preset.instructions;
  
  // Replace placeholders with actual values
  Object.keys(inputs).forEach(key => {
    instructions = instructions.replace(`{${key}}`, inputs[key]);
  });
  
  // Add specific instructions based on preset
  switch (preset.id) {
    case 'dcf':
      instructions += ` Use WACC of ${inputs.wacc || 12}%. Project ${inputs.years || 5} years.`;
      break;
    case 'cap-table':
      instructions += ` Model ${inputs.rounds || 5} funding rounds with realistic dilution.`;
      break;
    case 'comparables':
      instructions += ` Find at least ${inputs.comp_count || 5} comparable companies in ${inputs.sector}.`;
      break;
  }
  
  return instructions;
}

export function validateInputs(preset: ModelPreset, inputs: Record<string, any>): boolean {
  return preset.requiredInputs.every(input => inputs[input] !== undefined && inputs[input] !== '');
}