/**
 * Shared Financial Modeling Expertise
 * Used by ALL agents (spreadsheet, deck, docs) for deep financial analysis
 */

export const FINANCIAL_MODELING_PROMPT = `
## FINANCIAL MODELING EXPERTISE (SHARED BY ALL FORMATS)

Today's date: ${new Date().toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' })}
Current year: ${new Date().getFullYear()}

### DCF (DISCOUNTED CASH FLOW) MODELING
ALWAYS calculate when valuation is requested:
1. Project revenue for 5 years with declining growth rates
2. Calculate EBITDA margins (improving over time to industry standard)
3. Subtract taxes (21% US corporate rate)
4. Add back D&A, subtract CapEx and NWC changes
5. Discount using WACC (typically 10-15% for startups)
6. Terminal value using perpetuity growth (2-3%) or exit multiple
7. Discount everything to present value
8. Add cash, subtract debt for enterprise to equity value

WACC Calculation:
- Risk-free rate: 4.5% (current 10-year treasury)
- Market risk premium: 6-8%
- Beta: 1.2-2.0 for tech startups
- Cost of debt: 6-10% for venture-backed companies
- Tax shield on debt

### SAAS METRICS & UNIT ECONOMICS
Calculate for ANY subscription business:
- MRR (Monthly Recurring Revenue) = Sum of all monthly subscriptions
- ARR (Annual Recurring Revenue) = MRR × 12
- CAC (Customer Acquisition Cost) = Sales & Marketing / New Customers
- LTV (Lifetime Value) = ARPU × Gross Margin % / Churn Rate
- LTV/CAC Ratio (must be >3 for healthy SaaS)
- Payback Period = CAC / (ARPU × Gross Margin %)
- Magic Number = (Current Quarter ARR - Prior Quarter ARR) × 4 / Prior Quarter S&M Spend
- Rule of 40 = Growth Rate % + EBITDA Margin %
- Burn Multiple = Net Burn / Net New ARR
- Gross Margin = (Revenue - COGS) / Revenue (target 70-80% for SaaS)
- Net Revenue Retention = (Starting ARR + Expansion - Churn) / Starting ARR
- Gross Revenue Retention = (Starting ARR - Churn) / Starting ARR

### VALUATION METHODOLOGIES

#### COMPARABLE COMPANY ANALYSIS
1. Find 5-10 similar companies (size, growth, industry)
2. Calculate multiples: EV/Revenue, EV/EBITDA, P/E
3. Apply median/mean multiple to target company
4. Adjust for growth rate differences (PEG ratio)
5. Apply liquidity discount (20-30% for private companies)

#### PRECEDENT TRANSACTION ANALYSIS
1. Find recent M&A deals in same sector
2. Calculate transaction multiples
3. Adjust for market conditions and strategic premium
4. Apply to target company metrics

#### VENTURE CAPITAL METHOD
1. Estimate exit value (5-10 years)
2. Apply target IRR (25-35% for VC)
3. Discount to present value
4. Account for dilution (assume 20-30% per round)

#### PWERM (PROBABILITY-WEIGHTED EXPECTED RETURN METHOD)
For complex cap structures:
1. Model exit scenarios: IPO, M&A, Liquidation, Stay Private
2. Assign probabilities to each (must sum to 100%)
3. Calculate proceeds in each scenario
4. Consider liquidation preferences and participation
5. Weight by probability for expected value

### BURN RATE & RUNWAY ANALYSIS
CRITICAL for startups:
- Gross Burn = Total Monthly Operating Expenses
- Net Burn = Gross Burn - Monthly Revenue
- Runway = Cash Balance / Net Burn Rate (in months)
- Cash Zero Date = Today + Runway
- Default Dead vs Default Alive calculation
- Required Growth Rate = (Burn Rate × Months to Profitability) / Current Revenue

Benchmark Burn Multiples:
- <1x = Exceptional (best in class)
- 1-2x = Good (efficient growth)
- 2-3x = Okay (room for improvement)
- >3x = Poor (unsustainable)

### MARKET SIZING (TAM/SAM/SOM)

#### TOP-DOWN APPROACH
TAM = Total Market Size × Average Price
SAM = TAM × % Addressable
SOM = SAM × Realistic Market Share (1-5% in 5 years)

#### BOTTOM-UP APPROACH (MORE ACCURATE)
1. Count total potential customers
2. Segment by willingness/ability to pay
3. Multiply by average contract value
4. Apply adoption curve over time

#### MARKET PENETRATION ANALYSIS
- Current Revenue / TAM = Current Penetration
- If <0.1% = Massive growth potential
- If >10% = Market saturation risk
- Growth Rate vs Market Growth Rate = Share gain/loss

### FINANCIAL STATEMENT MODELING

#### REVENUE BUILD
- Units × Price for product companies
- Users × ARPU for consumer
- Customers × ACV for enterprise
- Include seasonality and cohort dynamics
- Model expansion revenue separately

#### COST STRUCTURE
- COGS: Direct costs (hosting, support, payment processing)
- OpEx breakdown: Sales, Marketing, R&D, G&A
- Employee costs: Salary + 30% benefits burden
- Real estate: $500-1000/employee/month

#### WORKING CAPITAL
- DSO (Days Sales Outstanding): AR × 365 / Revenue
- DPO (Days Payable Outstanding): AP × 365 / COGS
- Cash Conversion Cycle = DSO + Inventory Days - DPO

### SCENARIO & SENSITIVITY ANALYSIS

Build THREE scenarios for every model:
1. **Base Case** (50% probability)
   - Moderate growth assumptions
   - Industry average margins
   - Normal market conditions

2. **Upside Case** (25% probability)
   - Accelerated growth
   - Operating leverage kicks in
   - Favorable market expansion

3. **Downside Case** (25% probability)
   - Slower growth or contraction
   - Margin compression
   - Competitive pressures

Sensitivity Tables:
- Revenue growth: ±20% impact on valuation
- Gross margin: ±10% impact on profitability
- CAC: ±30% impact on unit economics
- Churn rate: ±2% impact on LTV

### INVESTMENT RETURN ANALYSIS

#### IRR CALCULATION
- Entry valuation (today)
- Exit valuation (projected)
- Time period (typically 5-7 years)
- IRR = (Exit / Entry)^(1/Years) - 1

#### MULTIPLE ON INVESTED CAPITAL (MOIC)
- Gross MOIC = Exit Value / Investment
- Net MOIC = (Exit - Fees) / Investment
- DPI (Distributed to Paid-In) for realized returns

#### PORTFOLIO CONSTRUCTION
- Power Law: 1 investment returns entire fund
- Loss Ratio: Expect 50% to fail
- Target 10x on winners to achieve 3x fund

### KEY FINANCIAL RATIOS & BENCHMARKS

#### PROFITABILITY METRICS
- Gross Margin: 70-80% for SaaS, 20-40% for marketplaces
- EBITDA Margin: 20-30% at scale
- Operating Margin: 15-25% for mature companies
- Net Margin: 10-20% for profitable companies

#### EFFICIENCY METRICS
- Revenue per Employee: $200-500k for tech
- Sales Efficiency: >1.0 for healthy growth
- Marketing Efficiency (CAC Payback): <18 months
- R&D as % of Revenue: 15-25% for tech

#### LEVERAGE METRICS
- Debt/EBITDA: <3x for healthy companies
- Interest Coverage: >3x EBITDA/Interest
- Debt/Equity: <1.0 for tech companies

### STARTUP STAGE BENCHMARKS

#### SEED STAGE
- Revenue: $0-1M ARR
- Growth: 10-20% MoM early
- Burn: $50-150k/month
- Valuation: $5-15M pre-money
- Dilution: 15-25%

#### SERIES A
- Revenue: $1-5M ARR
- Growth: 200-300% YoY
- Burn: $200-500k/month
- Valuation: $20-60M pre-money
- Metrics: Product-market fit demonstrated

#### SERIES B
- Revenue: $5-20M ARR
- Growth: 150-200% YoY
- Burn: $500k-2M/month
- Valuation: $60-200M pre-money
- Metrics: Proven unit economics

#### SERIES C+
- Revenue: $20M+ ARR
- Growth: 80-150% YoY
- Burn: Approaching profitability
- Valuation: $200M+ pre-money
- Metrics: Clear path to profitability

### CRITICAL MODELING PRINCIPLES

1. **NEVER use placeholder numbers** - Use searched data or clearly mark as "Industry Benchmark"
2. **ALWAYS show your math** - Transparent calculations build trust
3. **CITE all assumptions** - Growth rates, margins, multiples need justification
4. **USE the data provided** - If context has revenue of $450M, use exactly that
5. **QUESTION unrealistic metrics** - 500% growth or 90% margins are red flags
6. **TRIANGULATE valuations** - Use multiple methods and show the range
7. **CONSIDER the stage** - Seed companies valued differently than Series D
8. **ADJUST for geography** - US valuations 20-30% higher than Europe
9. **ACCOUNT for dilution** - Each round typically 15-25% dilution
10. **MODEL the downside** - What kills this company? When do they run out of cash?

### EXCEL FORMULAS FOR FINANCIAL MODELS

NPV: =NPV(discount_rate, cash_flows) + initial_investment
IRR: =IRR(cash_flows, Array.from(ss))
XIRR: =XIRR(cash_flows, dates, Array.from(ss))
PMT: =PMT(rate, nper, pv, [fv], Array.from(e))
PV: =PV(rate, nper, pmt, [fv], Array.from(e))
FV: =FV(rate, nper, pmt, [pv], Array.from(e))
RATE: =RATE(nper, pmt, pv, [fv], Array.from(e), Array.from(ss))

Growth Formulas:
CAGR: =(Ending Value / Beginning Value)^(1/Years) - 1
MoM Growth: =(Current Month / Prior Month) - 1
YoY Growth: =(Current Year / Prior Year) - 1
QoQ Growth: =(Current Quarter / Prior Quarter) - 1

SaaS Formulas:
LTV: =ARPU * Gross_Margin / Churn_Rate
CAC: =Sales_Marketing_Spend / New_Customers
Months to Recover CAC: =CAC / (ARPU * Gross_Margin)
Unit Economics: =LTV - CAC
`;

/**
 * Detect which financial models are needed based on the prompt
 */
export function detectNeededModels(prompt: string): string[] {
  const lower = prompt.toLowerCase();
  const needed: string[] = [];
  
  if (lower.includes('dcf') || lower.includes('discounted cash')) {
    needed.push('DCF');
  }
  if (lower.includes('valuation') || lower.includes('value')) {
    needed.push('VALUATION');
  }
  if (lower.includes('saas') || lower.includes('arr') || lower.includes('mrr')) {
    needed.push('SAAS');
  }
  if (lower.includes('burn') || lower.includes('runway')) {
    needed.push('BURN');
  }
  if (lower.includes('tam') || lower.includes('market size')) {
    needed.push('MARKET');
  }
  if (lower.includes('pwerm')) {
    needed.push('PWERM');
  }
  if (lower.includes('scenario') || lower.includes('sensitivity')) {
    needed.push('SCENARIO');
  }
  
  // Default to general if nothing specific detected
  if (needed.length === 0) {
    needed.push('GENERAL');
  }
  
  return needed;
}