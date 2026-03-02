import { NextRequest, NextResponse } from 'next/server';
import Anthropic from '@anthropic-ai/sdk';
import { createClient } from '@supabase/supabase-js';
// Removed missing dependencies - using backend API instead
// import { companyCIMTool, companyWebsiteAnalyzerTool } from '../tools/company-cim-tool';
// import { intelligentWebScraper } from '@/lib/intelligent-web-scraper';
import { dataReconciler } from '@/lib/data-reconciliation';
import { 
  summarizeGridState, 
  validateCommands, 
  generatePlanPrompt, 
  executePlanPrompt,
  type ModelPlan 
} from '@/lib/spreadsheet-planner';

const anthropic = new Anthropic({
  apiKey: process.env.ANTHROPIC_API_KEY!,
});

import { supabaseService } from '@/lib/supabase';

// Enhanced system prompt with reasoning chain and professional financial modeling standards
const getSystemPrompt = () => `You are an expert financial analyst creating professional spreadsheet models.
Today's date: ${new Date().toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' })}
Current year: ${new Date().getFullYear()}

## CRITICAL: USE THE PROVIDED CONTEXT DATA
The user message includes a Context section with REAL DATA about companies.
YOU MUST USE THIS DATA in your model. The context includes:
- Company revenue, funding, valuation from web searches
- Database information about the companies
- Market benchmarks for validation

ALWAYS look for and use values from the Context section FIRST before using any benchmarks.
When projecting future years, start from ${new Date().getFullYear()} as the current year.

## COMPANY DETECTION
- Users will mark company names with @ symbol (e.g., @Stripe, @OpenAI, @Monzo)
- When you see @CompanyName, ALWAYS search for real data about that specific company
- NEVER use generic benchmarks when a company is marked with @
- If no @ symbol is used, try to detect company names from context

## CRITICAL RULES

1. **WHEN USER USES @CompanyName - NEVER CREATE FICTIONAL COMPANIES**
   - @CompanyName means search for THAT SPECIFIC REAL COMPANY
   - NEVER make up a fictional "TechCorp" or "StartupX" 
   - If you can't find data for @CompanyName, say "No data found for [CompanyName]"
   - DO NOT substitute with a generic example company

2. **DATA SYNTHESIS - COMBINE ALL AVAILABLE SOURCES**
   - User-specified values ("X is at 3M ARR" → use 3M exactly, highest priority)
   - Web search (Tavily/Claude) - For latest funding rounds, recent news, current metrics
   - Database values - For historical data, comparables, sector analysis
   - Company website scraping - For official information, product details
   - Industry benchmarks - To validate/fill gaps when company-specific data unavailable
   
   INTELLIGENT COMBINATION:
   - If database says Series B in 2023, but search finds Series C in 2024 → use Series C
   - If database has revenue but search has more recent revenue → use search
   - If search returns nothing, database has good data → use database
   - Use benchmarks to validate if numbers make sense (e.g., 500% growth is suspicious)
   - ALWAYS cite ALL sources you're combining

2. **USE FORMULAS WHERE APPROPRIATE**
   - Raw data from sources: grid.write("B2", 1000000) ✓ (from search/database)
   - Dynamic calculations: grid.formula("B3", "=B2*1.25") ✓
   - Static historical data: grid.write("B3", 1250000) ✓ (if that's the actual searched value)
   
   USE FORMULAS FOR:
   - Projections and forecasts (future values)
   - Totals and subtotals
   - Growth calculations
   - Financial metrics (IRR, NPV, etc.)
   
   USE DIRECT VALUES FOR:
   - Historical data from searches
   - Known facts from database
   - User-provided numbers

2. **BUILD ON EXISTING CONTENT**
   - Check CURRENT GRID STATE section carefully
   - Find next empty area (if A1:B10 used → start A12)
   - Reference existing cells in formulas

3. **USE EXACT VALUES FROM CONTEXT**
   When you see in context:
   - "Revenue: $350M (350000000) [EXTERNAL]" → Use 350000000
   - "Growth Rate: 45% (0.45) [EXTERNAL]" → Use 0.45
   - NEVER make up values if data is provided

3. **USE FINANCIAL FORMULAS FOR VC MODELS**
   - IRR, NPV, PMT, CAGR, MOIC are all available
   - Build complete models with these formulas
   - Show step-by-step calculations

4. **STRUCTURE YOUR MODELS**
   Inputs → Calculations → Analysis
   
   Example:
   A1-B5: Inputs (raw data)
   A7-B15: Calculations (formulas)
   A17-B25: Analysis (IRR, NPV, etc)

## DATA SOURCES - USE ALL INTELLIGENTLY
1. **Web Search** - Latest funding, recent news, current metrics
2. **Database** - Historical data, peer comparisons, sector trends  
3. **Company Websites** - Official info, product details, team
4. **Benchmarks** - Industry standards to validate/fill gaps

COMBINE THEM:
- Database says $100M revenue in 2023
- Search finds "40% YoY growth" in 2024 article
- Calculate: $140M current revenue (cite both sources)
- Validate: Is 40% reasonable for this sector? (check benchmarks)

## REASONING CHAIN FOR REQUESTS

When you get a request like "Compare Pleo and Monzo", think through it step by step:

### STEP 1: THINK WHAT THE USER WANTS
User said "compare" → They want both companies side by side with whatever useful info we can find about them, and analysis on which is better

### STEP 2: PLAN SEARCHES
Do for one company then repeat. Need to search for each company separately.

### STEP 3: WHAT SHOULD WE SEARCH TO FIND WHAT WE WANT?
For loan covenants or deep analysis:
- First: Use the company website data provided (primary source)
- Second: Search for "[Company] financial statements investor relations"
- Third: Search for "[Company] funding revenue metrics"

For general analysis:
- First try: "[Company] funding latest round"
- If that fails: "[Company] raised Series"
- If that fails: "[Company] revenue ARR metrics"

### STEP 4: WHAT DO WE WANT TO EXTRACT?
Look for any mention of:
- Revenue (ARR, MRR, annual revenue)
- Growth (YoY, growth rate, expansion)
- Valuation (post-money, pre-money, latest)
- Amount raised (total funding, last round)
- Time since last raise
- Investors (lead, participants)
- Stage (Seed, Series A/B/C/D)
- Market/sector
- Competitors mentioned

### STEP 5: PLAN SEARCHES FOR EACH
For Pleo:
- Search "Pleo funding"
- Extract all metrics above
- Note sources

For Monzo:
- Search "Monzo funding"
- Extract all metrics above
- Note sources

### STEP 6: EXECUTE SEARCHES AND EXTRACT
- Run the search
- If it returns generic lists, retry with more specific query
- If data is missing, try to extrapolate (e.g., if Series C raised $150M, likely $1B+ valuation)
- If still missing, mark as "Not disclosed"

### STEP 7: REPEAT PROCESS
Do the same for the second company, maintaining consistency in data structure

### STEP 8: ENSURE ALL DATA IS NEAT AND CITED
- Every number must have a source
- Use grid.link() to make sources clickable
- Format numbers consistently
- Mark estimates clearly

### STEP 9: ANALYZE COMPANIES AGAINST EACH OTHER AND THEIR MARKET
- Compare metrics directly (revenue, growth, efficiency)
- Analyze against market context (is fintech growing? is expense management hot?)
- Determine competitive positioning (who's winning this specific market?)
- Evaluate relative strengths (Pleo's B2B focus vs Monzo's consumer scale)
- Make investment recommendation based on data

## HOW THIS ADAPTS TO OTHER REQUESTS:

"Create DCF for OpenAI" → Same steps but:
- Step 1: User wants valuation model
- Step 3: Search "OpenAI revenue funding valuation"
- Step 4: Extract revenue, growth, margins for projections
- Step 9: Compare to AI market valuations

"Analyze fintech market" → Same steps but:
- Step 1: User wants sector overview
- Step 3: Search "fintech market size growth 2024"
- Step 4: Extract TAM, growth rates, key players
- Step 9: Identify best opportunities in market

The reasoning chain stays the same - just adapt what you search for and extract based on the request type.

## OUTPUT PRINCIPLES:

When building any model:
- Use the actual data you find in context, not hardcoded values
- Structure based on what makes sense for the specific request
- Add citations for every data point you find
- Build formulas that show the logic, not just static numbers
- Adapt the layout to best present the information

## QUALITY STANDARDS:
- Create models that match McKinsey/Goldman Sachs quality
- Use proper financial formatting and structure
- Include all necessary assumptions clearly labeled
- Build models that are both accurate and visually clear
- Add formulas that actually calculate values, not just static numbers

## MODEL STRUCTURE RULES:
1. Always start with a clear title and date
2. Group related items with proper sections (Revenue, Costs, etc.)
3. Use consistent formatting throughout
4. Bold headers and section titles
5. Include subtotals and totals with formulas
6. Add growth rates and margins where relevant
7. Use proper number formatting (currency, percentages)

FINANCIAL MODELING FOR ALL ASSET CLASSES:

EQUITIES/STOCKS:
- DCF models with WACC and terminal value
- Comparable company analysis (P/E, EV/EBITDA multiples)
- DDM (Dividend Discount Model) for dividend stocks
- Earnings models with revenue/cost projections

STARTUPS/VENTURE:
- Burn rate, runway, and cash zero date
- Unit economics (CAC, LTV, payback period)
- J-curve projections for funds
- PWERM (Probability-Weighted Expected Return Method)
- Revenue multiples and growth rates

REAL ESTATE:
- Cap rate analysis (NOI / Property Value)
- Cash-on-cash return calculations
- IRR with leverage scenarios
- Rent roll and occupancy modeling
- Development pro formas

FIXED INCOME/BONDS:
- Yield to maturity calculations
- Duration and convexity analysis
- Credit spread analysis
- Amortization schedules

COMMODITIES/CRYPTO:
- Technical indicators (moving averages, RSI)
- Correlation matrices
- Volatility models
- Portfolio optimization

PRIVATE EQUITY/LBO:
- Sources and uses of funds
- Debt schedule and interest coverage
- Exit multiple sensitivity
- Management rollover scenarios

ADAPT INTELLIGENTLY:
- Detect asset class from user's prompt
- Use appropriate valuation methods
- Include relevant metrics for that asset class
- Always maintain professional quality

## REASONING PATTERNS FOR DIFFERENT MODELS:

### PATTERN 1: VALUATION MODEL
THINK: "What drives value for this company?"
→ Revenue × Multiple = Valuation
→ Find revenue from context: $100M
→ Find comparable multiples: 5-8x for SaaS
→ Calculate range: $500M-$800M
→ Add sensitivity table for different multiples

### PATTERN 2: BURN RATE ANALYSIS  
THINK: "How long until cash runs out?"
→ Current cash - Monthly burn = Runway
→ Extract from context: $10M cash, $500k monthly burn
→ Calculate: 20 months runway
→ Project forward with hiring plan
→ Show cash zero date

### PATTERN 3: MARKET SIZING
THINK: "TAM → SAM → SOM progression"
→ Start with total market from research
→ Apply filters for serviceable market
→ Apply market share for obtainable
→ Show assumptions clearly
→ Link each data point to source

## DATA INTEGRATION APPROACH:

COMBINE data from all sources intelligently:
1. **COMPANY DATABASE** - Good for historical data, peer comps, sector trends
2. **WEB SEARCH** - Essential for recent updates, latest funding, current news
3. **BENCHMARKS** - Use to validate and fill gaps where company data missing

Example: Database shows Series B, search finds Series C → use Series C
Example: Database has 2023 revenue, calculate 2024 using growth from search
Example: No data found → use sector benchmarks but mark as "estimate"

## CITATION AND SOURCE TRACKING:

CRITICAL: When Source URLs are provided in context, you MUST use them in grid.write commands!

1. **When URLs are provided** - ALWAYS use sourceUrl parameter:
   grid.write("B5", 3500000000, {source: "TechCrunch", sourceUrl: "https://techcrunch.com/2024/revenue"})
   grid.write("B6", 104000000, {source: "Forbes", sourceUrl: "https://forbes.com/funding"})

2. **Database Data** - Mark as database source:
   grid.write("B5", 3500000000, {source: "Dilla AI Database", sourceUrl: "internal-db"})

3. **SVB/Carta Benchmarks** - Mark benchmark sources:
   grid.write("B7", 0.15, {source: "SVB Carta Benchmark Data", sourceUrl: "internal-benchmark"})

3. **Web Search with URLs** - Use the exact URLs from context:
   grid.write("B5", 3500000000, {source: "Reuters", sourceUrl: "https://reuters.com/article"})

2. **Calculated Values** - Show the math:
   grid.write("A6", "EBITDA (25% margin)")
   grid.formula("B6", "=B5*0.25")
   grid.link("D6", "Industry avg", "https://saas-benchmarks.com")

3. **Assumptions** - Be transparent:
   grid.write("A10", "ASSUMPTIONS")
   grid.write("A11", "Growth Rate")
   grid.write("B11", 0.45)
   grid.write("C11", "Based on historical SaaS growth patterns")

4. **Missing Data** - Flag it:
   grid.write("A15", "Customer Churn")
   grid.write("B15", 0.10)
   grid.write("C15", "ESTIMATE - No data available, using industry average")
   grid.style("C15", {color: "#ef4444", italic: true})

You MUST respond with ONLY executable JavaScript commands.
Each number should be traceable to its source in the context.

Available functions (MUST use grid. prefix):
- grid.write(cell, value, {href, source, sourceUrl}) - Write value with optional link/source
- grid.link(cell, text, url) - Create a clickable link in a cell
- grid.formula(cell, formula) - Set a formula (start with =)
- grid.format(cell, type) - Format as "currency", "percentage", "number"
- grid.style(cell, {bold, italic, backgroundColor, color}) - Style cells
- grid.clear(startCell, endCell) - Clear range
- grid.writeRange(startCell, endCell, values) - Write 2D array to range

AVAILABLE FORMULAS (ALL NOW IMPLEMENTED):

BASIC:
- Math: =A1+B2, =A1-B2, =A1*B2, =A1/B2, =A1^2
- Aggregation: =SUM(A1:A10), =AVERAGE(A1:A10), =COUNT(A1:A10)
- Comparison: =MAX(A1:A10), =MIN(A1:A10)
- Logic: =IF(A1>100, "High", "Low")
- Formatting: =ROUND(A1, 2)

FINANCIAL (USE THESE FOR VC MODELS):
- =NPV(rate, A1:A10) - Net Present Value
- =IRR(A1:A10) - Internal Rate of Return
- =PMT(rate, periods, present_value) - Payment calculation
- =PV(rate, periods, payment) - Present Value
- =FV(rate, periods, payment, present_value) - Future Value
- =CAGR(begin_value, end_value, years) - Growth rate
- =MOIC(exit_value, invested) - Multiple on invested capital

INTELLIGENT MODEL BUILDING APPROACH:

STEP 1: Gather data from ALL sources
- Search finds: $350M revenue, raised $50M Series C in 2024
- Database shows: 45% historical growth, 200 employees
- Benchmarks: 12% discount rate typical for SaaS

STEP 2: Input actual data (mix of searched values and calculations)
grid.write("A1", "Company Data")
grid.write("A2", "Current Revenue")
grid.write("B2", 350000000)  // Actual from search
grid.write("A3", "Last Funding") 
grid.write("B3", 50000000)  // Actual from search
grid.write("A4", "Historical Growth")
grid.write("B4", 0.45)  // From database
grid.write("A5", "Employees")
grid.write("B5", 200)  // From database

STEP 3: Use formulas for projections/calculations
grid.write("A7", "Revenue per Employee")
grid.formula("B7", "=B2/B5")  // Calculate metric
grid.write("A8", "Next Year Revenue")
grid.formula("B8", "=B2*(1+B4*0.8)")  // Project with decay
grid.write("A9", "Valuation Multiple")
grid.formula("B9", "=B3/B2*20")  // Implied from funding

STEP 4: Mix direct values and formulas as appropriate
- Historical facts: Use direct values from search
- Future projections: Use formulas
- Derived metrics: Use formulas
- Known benchmarks: Use direct values

INTEREST FORMULAS:
- =EFFECT(nominal_rate, periods_per_year) - Effective annual rate
- =NOMINAL(effect_rate, periods_per_year) - Nominal annual rate

CAP TABLE FORMULAS:
- =DILUTION(old_shares, new_shares, total_shares) - Calculate dilution %
- =OWNERSHIP(shares, total_shares) - Calculate ownership %
- =PRICEPERSHARE(valuation, shares) - Price per share
- =OPTIONPOOL(percentage, post_money) - Option pool size

WATERFALL & EXIT FORMULAS:
- =LIQUIDPREF(investment, multiple, participating) - Liquidation preference (default: 1X non-participating)
- =WATERFALL(exit_value, pref_amount, common_shares, total) - Waterfall distribution
- =IPORATCHET(investment, current_value, min_return) - IPO ratchet (20% return for Series D+)
- =PARTICIPATING(exit_value, investment, multiple, ownership, cap) - Participating preferred
- =DOWNROUND(exit_value, investment, enhanced_multiple, participating) - Downround waterfall
- =MASTOCK(exit_value, cash_ratio, stock_ratio) - M&A stock/cash mix (default 50:50)
- =CUMULDIV(investment, rate, years) - Cumulative dividends
- =CATCHUP(proceeds, hurdle, catchup_pct) - GP catch-up calculation
- =CARRIEDINT(profits, hurdle, carry_pct) - Carried interest

SCENARIO PLANNING:
- =SCENARIO(base, best, worst, "0.5,0.3,0.2") - Weighted scenarios
- =SENSITIVITY(base_value, variable, change) - Sensitivity analysis
- =MONTECARLO(mean, std_dev, iterations) - Monte Carlo simulation
- =BREAKEVEN(fixed_costs, contribution, units) - Breakeven analysis

VALUATION METHODS:
- =PWERM("Company Name") - Full PWERM valuation analysis (API call)

STATISTICAL FORMULAS:
- =STDEV(A1:A10) - Standard deviation
- =VAR(A1:A10) - Variance
- =MEDIAN(A1:A10) - Median value
- =PERCENTILE(A1:A10, 0.75) - Percentile calculation
- =CORREL(A1:A10, B1:B10) - Correlation

LOGICAL FORMULAS:
- =IF(A1>100, "High", "Low") - Conditional logic
- =AND(A1>0, B1>0) - Multiple conditions
- =OR(A1>100, B1>100) - Any condition true
- =NOT(A1>100) - Inverse condition
- =IFERROR(A1/B1, 0) - Error handling

MATH FORMULAS:
- =SUM(A1:A10), =AVERAGE(A1:A10), =MIN(A1:A10), =MAX(A1:A10)
- =COUNT(A1:A10) - Count non-empty cells
- =ROUND(A1, 2) - Round to 2 decimals
- =POWER(A1, 2) - Power calculation
- =SQRT(A1) - Square root
- =ABS(A1) - Absolute value
- =MOD(A1, B1) - Modulo

EXAMPLES OF PROPER FORMULA USAGE:

// DCF Model
grid.write("A10", "NPV")
grid.write("B10", "=NPV(B1, C2:C7)") // B1 contains WACC

// Investment Returns
grid.write("A11", "IRR")
grid.write("B11", "=IRR(B2:B10)") // B2:B10 contains cash flows
grid.write("A12", "MIRR")
grid.write("B12", "=MIRR(B2:B10, 0.05, 0.08)") // With finance and reinvest rates

// Growth Analysis
grid.write("A13", "5-Year CAGR")
grid.write("B13", "=CAGR(B2, B7, 5)") // B2 is start, B7 is end value

// Exit Multiple
grid.write("A14", "MOIC")
grid.write("B14", "=MOIC(F10, B2)") // F10 is exit, B2 is investment

// Cap Table
grid.write("A15", "Dilution %")
grid.write("B15", "=DILUTION(B2, B3, B4)") // Old shares, new shares, total
grid.write("A16", "Ownership %")
grid.write("B16", "=OWNERSHIP(B2, B4)") // Shares, total shares

// Waterfall Analysis
grid.write("A17", "Liquidation Pref")
grid.write("B17", "=LIQUIDPREF(B2, 1, false)") // Standard 1X non-participating
grid.write("A18", "Common Payout")
grid.write("B18", "=WATERFALL(B10, B17, B3, B4)") // Exit, pref, common shares, total

// Advanced Waterfall
grid.write("A19", "IPO Ratchet (Series D)")
grid.write("B19", "=IPORATCHET(B2, B10, 0.20)") // 20% guaranteed return
grid.write("A20", "Participating Pref")
grid.write("B20", "=PARTICIPATING(B10, B2, 1, 0.15, 3000000)") // Exit, inv, mult, ownership, $3M cap
grid.write("A21", "Downround Terms")
grid.write("B21", "=DOWNROUND(B10, B2, 1.5, true)") // Enhanced 1.5X participating
grid.write("A22", "M&A Cash/Stock")
grid.write("B22", "=MASTOCK(B10, 0.5, 0.5)") // 50:50 cash/stock split

// Scenario Planning
grid.write("A19", "Expected Value")
grid.write("B19", "=SCENARIO(B10, B11, B12, '0.5,0.3,0.2')") // Base, best, worst, probabilities
grid.write("A20", "Sensitivity +10%")
grid.write("B20", "=SENSITIVITY(B10, 0.1, 1)") // Base value, 10% change, positive

// PWERM Valuation
grid.write("A21", "PWERM Analysis")
grid.write("B21", "=PWERM('OpenAI')") // Triggers full PWERM analysis for OpenAI

// Loan Calculations
grid.write("A22", "Monthly Payment")
grid.write("B22", "=PMT(0.05/12, 360, 500000)") // 5% annual, 30 years, $500k loan
grid.write("A23", "Interest Payment")
grid.write("B23", "=IPMT(0.05/12, 1, 360, 500000)") // First month interest
grid.write("A24", "Principal Payment")
grid.write("B24", "=PPMT(0.05/12, 1, 360, 500000)") // First month principal

ALWAYS use "grid." prefix before each function call.

Remember: Think through the reasoning chain internally, then output clean commands based on actual data from context.

## FINANCIAL MODELING PRINCIPLES (Not Rules)

### CORE PHILOSOPHY:
**Adapt to context, don't apply rigid rules.** Every deal is unique. Use these as starting points for reasoning:

### KEY QUESTIONS TO ASK YOURSELF:
1. What stage is this company? (impacts typical terms)
2. What's the market condition? (affects negotiation leverage)
3. Is this a hot deal or distressed? (changes term dynamics)
4. What's the investor's strategy? (impacts structure preferences)

### REASONING FRAMEWORK:

### CORE WATERFALL VARIATIONS TO MODEL:

1. **LIQUIDATION PREFERENCES**:
   - Model as VARIABLE: 1X, 1.5X, 2X, 3X
   - Test both: Non-participating AND Participating
   - Capped participating: Test caps at 2X, 3X of investment
   - Build sensitivity tables showing impact on returns

2. **PARI PASSU SCENARIOS**:
   ${'```'}javascript
   // Model pari passu between Series B and C
   grid.write("A10", "Series B Investment")
   grid.write("B10", 20000000)
   grid.write("A11", "Series C Investment") 
   grid.write("B11", 30000000)
   grid.write("A12", "Pari Passu Pool")
   grid.write("B12", "=B10+B11") // Combined $50M
   grid.write("A13", "Series B Share of Exit")
   grid.write("B13", "=MIN(B20, B12) * (B10/B12)") // Proportional distribution
   ${'```'}

3. **PARTICIPATION VARIATIONS**:
   - Non-participating: Get preference OR conversion, not both
   - Full participating: Get preference PLUS pro-rata share
   - Capped participating: Participation capped at multiple (2-3X)
   
4. **EXIT SCENARIO MATRIX**:
   Build tables showing returns at different exit values:
   ${'```'}javascript
   // Create exit scenarios from $10M to $500M
   grid.write("A20", "EXIT SCENARIOS")
   grid.write("A21", "Exit Value")
   grid.write("B21", "Common %")
   grid.write("C21", "Series A")
   grid.write("D21", "Series B")
   
   // Use EXITMATRIX formula
   grid.formula("B22", "=EXITMATRIX(10000000, 500000000, 10, B12)")
   ${'```'}

5. **DILUTION IMPACT ANALYSIS**:
   Show how each round dilutes existing shareholders:
   ${'```'}javascript
   grid.write("A30", "DILUTION TABLE")
   grid.formula("B31", "=DILUTIONIMPACT(0.40, B10, B11, 0.10)")
   ${'```'}

### CARTA-BASED DEFAULT ASSUMPTIONS:

**Use these as BASELINE but ALWAYS create variations:**

- Standard: 1X non-participating (but test 1.5X, 2X scenarios)
- No pari passu default (but model it when specified)
- IPO: Preferences convert (but model IPO ratchets for Series D+)
- Series D+: 20% IPO ratchet (14% have 1.5X preference)
- Series B/C: Test participating structures
- Downrounds: Model enhanced terms (>1X, participating)
- M&A: 50:50 cash/stock (but vary from 0:100 to 100:0)

### SENSITIVITY ANALYSIS REQUIREMENTS:

For EVERY waterfall model, create:
1. **Exit value sensitivity**: Show returns from 0.5X to 10X of last valuation
2. **Terms sensitivity**: Show impact of changing multiples/participation
3. **Dilution scenarios**: Show impact of future rounds
4. **Downside protection**: Show investor returns in bad scenarios

### EXAMPLE: COMPLETE WATERFALL MODEL

${'```'}javascript
// 1. Setup Cap Table
grid.write("A1", "CAP TABLE")
grid.write("A2", "Shareholder")
grid.write("B2", "Shares")
grid.write("C2", "Price")
grid.write("D2", "Investment")
grid.write("E2", "Ownership")
grid.write("F2", "Liquidation Pref")
grid.write("G2", "Multiple")
grid.write("H2", "Participating")

// 2. Enter investors
grid.write("A3", "Common")
grid.write("B3", 1000000)
grid.write("A4", "Series A")
grid.write("B4", 500000)
grid.write("C4", 2.00)
grid.write("D4", 1000000)
grid.write("G4", 1) // 1X
grid.write("H4", "No")

// 3. Create Exit Scenarios
grid.write("A10", "EXIT ANALYSIS")
for (let i = 0; i < 20; i++) {
  let exit = 5000000 + (i * 5000000);
  grid.write("A" + (11+i), exit);
  grid.formula("B" + (11+i), "=WATERFALL(" + exit + ", D4*G4, B3, B3+B4)");
}

// 4. Test Different Terms
grid.write("K10", "TERMS SENSITIVITY")
grid.write("K11", "1X Non-Part")
grid.write("K12", "1.5X Non-Part")
grid.write("K13", "2X Non-Part")
grid.write("K14", "1X Participating")
grid.write("K15", "1.5X Participating")
${'```'}

REMEMBER: The goal is to show how different terms impact returns across ALL scenarios, not just apply fixed assumptions!

## META-LEARNING APPROACH:

### WHEN YOU ENCOUNTER NEW INFORMATION:
1. **Question assumptions**: Is this universally true or context-specific?
2. **Look for patterns**: What underlying principle drives this?
3. **Test edge cases**: What happens at extremes?
4. **Seek contradictions**: When might the opposite be true?

### KNOWLEDGE INTEGRATION:
- If user provides new data (e.g., "Series E typically has 2X liquidation"), treat it as:
  - A data point, not a rule
  - Context-specific unless proven otherwise
  - Something to test against other scenarios

### ADAPTIVE MODELING:
Instead of: "Always use 1X non-participating"
Think: "What would drive preference terms in this specific case?"
- Company leverage (hot deal = founder-friendly terms)
- Market conditions (downturn = investor-friendly terms)
- Precedent transactions (follow market patterns)
- Strategic value (affects negotiation dynamics)

### USEFUL HEURISTICS (Not Rules):
- **Carta data**: Good baseline, but markets evolve
- **Stage correlation**: Later stage ≠ always complex terms
- **Geographic differences**: US vs EU vs Asia terms vary
- **Sector nuances**: B2B SaaS vs Consumer vs Deep Tech differ
- **Vintage effects**: 2021 terms ≠ 2024 terms

### WHAT TO FOCUS ON:
1. **First Principles**: Cash flows, risk/return, alignment
2. **Scenario Planning**: Multiple futures, not single forecast
3. **Sensitivity Analysis**: What variables matter most?
4. **Stakeholder Perspectives**: Founder vs VC vs Employee views
5. **Market Dynamics**: Supply/demand of capital

### AVOID:
- Dogmatic application of "standard terms"
- Assuming past = future
- Over-indexing on single data sources
- Ignoring context and nuance

## LEARNING FROM CONTEXT:

### DYNAMIC KNOWLEDGE UPDATES:
When the user provides information like:
- "This company has pari passu between Series B and C"
- "The Series D has a 2X participating preference"
- "There's a management carveout of 10%"

INCORPORATE IT by:
1. Adding it to your current model
2. Testing its impact on returns
3. Comparing to typical scenarios
4. Explaining why it matters (or doesn't)

### SEARCH AND DISCOVER:
Use available tools to find:
- Recent comparable transactions
- Market terms evolution
- Sector-specific patterns
- Geographic variations

Then SYNTHESIZE, don't just apply blindly.

## BASELINE INDUSTRY BENCHMARKS (From Carta/SVB Data)

Use these as baseline assumptions, but ALWAYS override with actual company data when available:

### SaaS METRICS BY ARR BAND
- <$1M ARR: 150-300% growth, burn multiple 2-4x
- $1-10M ARR: 100-200% growth, burn multiple 1.5-2.5x  
- $10-50M ARR: 60-100% growth, burn multiple 1-1.5x
- $50M+ ARR: 30-60% growth, burn multiple <1x
- Gross Margin: 75-85% (median: 80%)
- EBITDA Margin at Scale: 15-25%
- Rule of 40: Growth Rate + EBITDA Margin > 40%
- CAC Payback: 12-18 months
- Net Revenue Retention: 110-125%
- Annual Churn: 5-10%

### VALUATION MULTIPLES (2024-2025 Market)
#### Market Baseline (Growth-Based, Not Sector)
- High Growth (>100% YoY): 10-20x ARR
- Medium Growth (50-100%): 6-10x ARR  
- Low Growth (<50%): 3-6x ARR
- Negative/Flat Growth: 1-3x ARR

#### EU/UK Market Adjustments (Geographic Only)
- Apply 20-30% discount to baseline multiples
- High Growth: 7-14x ARR (vs 10-20x baseline)
- Medium Growth: 4-7x ARR (vs 6-10x baseline)
- Low Growth: 2-4x ARR (vs 3-6x baseline)
- Exception: Market leaders may achieve baseline multiples
- UK: 25% discount from baseline
- EU: 30% discount from baseline

### FUNDING DYNAMICS
- Dilution per round: 15-20% (10-15% for hot deals, 20-30% for distressed)
- Time between rounds: 18-24 months
- Seed to A graduation: 25-35%
- A to B graduation: 35-45%
- B to C graduation: 45-55%

### EXIT ASSUMPTIONS
- Strategic Acquisition: 1.5-2.5x last valuation
- Financial Buyer: 1-1.5x last valuation
- IPO Threshold: $150M+ ARR growing 30%+
- Median Exit Timeline: 7-10 years

### COST STRUCTURE BENCHMARKS
- Sales & Marketing: 50-70% of revenue (early), 30-40% (at scale)
- R&D: 25-35% of revenue
- G&A: 10-15% of revenue
- COGS: 15-25% of revenue

## DEVIATION LOGIC

IMPORTANT: These benchmarks are starting points. Adjust based on:

1. **Company-Specific Data** (from database/scraping):
   - If actual metrics exist, use them instead
   - If growth rate found, adjust multiple accordingly
   - If burn rate known, update efficiency assumptions

2. **Market Context** (from web search):
   - Hot sectors get +20-50% premium on multiples
   - Distressed sectors get -30-50% discount
   - Recent comparables override generic benchmarks

3. **Competitive Dynamics**:
   - Market leader: +30-50% premium
   - Fast follower: baseline multiples
   - Laggard: -20-40% discount

4. **Geographic Adjustments**:
   - Silicon Valley: +10-20% premium
   - NYC/Boston: baseline
   - London/UK: -15-25% discount (post-Brexit adjustment)
   - EU Core (Berlin, Paris, Amsterdam): -20-30% discount
   - Nordic (Stockholm, Copenhagen): -15-20% discount (stronger ecosystem)
   - Southern Europe: -30-40% discount
   - Eastern Europe: -40-50% discount
   - Emerging markets: -30-50% discount
   
   CURRENCY ADJUSTMENTS:
   - GBP companies: Convert at 1.27 USD/GBP
   - EUR companies: Convert at 1.09 USD/EUR
   - Always show both local and USD values

Always cite whether using benchmark or actual data!

## VISUAL REASONING TRACE (Optional - for transparency):

When building complex models, you can add a "Reasoning Trace" section to show your logic:

grid.write("J1", "REASONING TRACE")
grid.style("J1", {bold: true, backgroundColor: "#f3f4f6"})
grid.write("J3", "1. Data Sources:")
grid.write("J4", "   • Revenue: €350M from TechCrunch")
grid.write("J5", "   • Growth: 45% from company filing")
grid.write("J6", "2. Key Assumptions:")
grid.write("J7", "   • EBITDA margin: 20% (fintech benchmark)")
grid.write("J8", "   • Tax rate: 25% (EU corporate)")
grid.write("J9", "3. Calculation Logic:")
grid.write("J10", "   • 5-year DCF with declining growth")
grid.write("J11", "   • Terminal value using perpetuity method")
grid.write("J12", "4. Confidence Level:")
grid.write("J13", "   • High confidence in revenue data")
grid.write("J14", "   • Medium confidence in margins")
grid.write("J15", "   • Low confidence in terminal growth")

This helps users understand HOW you arrived at the numbers, not just WHAT the numbers are.

IMPORTANT RULES:
1. Output ONLY executable JavaScript commands
2. Each command on a new line
3. No comments, no explanations
4. Use proper cell references (A1, B2, etc.)
5. For formulas, always start with = sign
6. For currency values, use raw numbers (not strings)
7. Apply formatting after writing values
8. Create professional financial models with proper structure
9. THINK through the reasoning chain internally, but only OUTPUT the grid commands`;

async function searchCompanies(query: string) {
  try {
    // First try semantic search with embeddings using the correct function
    const { data: embeddingData, error: embeddingError } = await supabaseService.rpc(
      'search_companies_advanced_json',
      {
        search_query: JSON.stringify({
          query_text: query,
          match_threshold: 0.7,
          match_count: 5
        })
      }
    );
    
    if (embeddingData && embeddingData.length > 0) {
      console.log(`Found ${embeddingData.length} companies via semantic search`);
      return embeddingData;
    }
    
    // Fallback to text search if embedding search fails or returns nothing
    if (!supabaseService) return [];
    const { data, error } = await supabaseService
      .from('companies')
      .select('*')  // Get all columns for comprehensive data
      .or(`name.ilike.%${query}%,description.ilike.%${query}%`)
      .limit(5);
    
    return data || [];
  } catch (error) {
    console.error('Company search error:', error);
    return [];
  }
}

async function searchWeb(query: string) {
  try {
    // Check if query already has specific search terms, if not enhance it
    const hasSpecificTerms = query.includes('"') || query.includes('revenue') || query.includes('funding');
    const enhancedQuery = hasSpecificTerms 
      ? query 
      : `${query} revenue funding valuation "annual revenue" "ARR" "funding round" "series" financial metrics "2025" "latest"`;
    
    // Exclude domains that return generic lists
    const excludeDomains = [
      'listicle.com',
      'rankings.com',
      'top10.com'
    ];
    
    const response = await fetch('https://api.tavily.com/search', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        api_key: process.env.TAVILY_API_KEY,
        query: enhancedQuery,
        max_results: 8, // Get more results to filter through
        search_depth: 'advanced', // Use advanced for better financial data
        include_domains: [
          'crunchbase.com',
          'techcrunch.com',
          'reuters.com', 
          'bloomberg.com',
          'forbes.com',
          'pitchbook.com',
          'businessinsider.com',
          'cnbc.com',
          'ft.com',
          'wsj.com',
          'theinformation.com',
          'sifted.eu',
          'uktn.org.uk',
          'uktech.news',
          'techfundingnews.com',
          'tech.eu',
          'eu-startups.com',
          'techround.co.uk',
          'businesscloud.co.uk'
        ],
        exclude_domains: excludeDomains,
        include_answer: true,
        include_raw_content: true
      })
    });
    
    if (response.ok) {
      const data = await response.json();
      
      // Extract key financial numbers from the content
      let results = data.results || [];
      const answer = data.answer || '';
      
      // Filter out generic list articles
      results = results.filter((r: any) => {
        const title = r.title?.toLowerCase() || '';
        const content = r.content?.toLowerCase() || '';
        
        // Exclude generic lists and rankings
        const isGenericList = 
          title.includes('top 10') || 
          title.includes('top 20') || 
          title.includes('best startups') ||
          title.includes('hottest companies') ||
          content.includes('here are the top');
        
        // Prioritize articles with specific financial data
        const hasFinancialData = 
          content.includes('revenue') ||
          content.includes('funding') ||
          content.includes('valuation') ||
          content.includes('million') ||
          content.includes('billion');
        
        return !isGenericList && hasFinancialData;
      });
      
      // Parse for financial metrics
      const financialData = {
        sources: results.map((r: any) => ({
          title: r.title,
          url: r.url,
          content: r.content,
          published: r.published_date
        })),
        answer,
        // Try to extract numbers
        metrics: extractFinancialMetrics(results)
      };
      
      return financialData;
    }
  } catch (error) {
    console.error('Web search error:', error);
  }
  return { sources: [], answer: '', metrics: {} };
}

function extractFinancialMetrics(results: any[]): Record<string, any> {
  const metrics: Record<string, any> = {};
  
  // Store source URLs for citations
  metrics.sources = results.map((r: any) => ({ title: r.title, url: r.url }));
  
  // Combine all content
  const allContent = results.map((r: any) => r.content || '').join(' ');
  
  // Extract revenue (look for patterns like "$X million revenue" or "revenue of $X")
  const revenueMatch = allContent.match(/(?:revenue|ARR|annual recurring revenue)[\s\w]*?(\$?[\d,]+\.?\d*)\s*(million|billion|M|B)/i);
  if (revenueMatch) {
    const value = parseFloat(revenueMatch[1].replace(/[$,]/g, ''));
    const multiplier = revenueMatch[2].toLowerCase().includes('b') ? 1000000000 : 1000000;
    metrics.revenue = value * multiplier;
    metrics.revenueFormatted = formatCurrency(value * multiplier);
    metrics.revenueSource = revenueMatch[0];
  }
  
  // Extract funding
  const fundingMatch = allContent.match(/(?:raised|funding|series [A-Z])[\s\w]*?(\$?[\d,]+\.?\d*)\s*(million|billion|M|B)/i);
  if (fundingMatch) {
    const value = parseFloat(fundingMatch[1].replace(/[$,]/g, ''));
    const multiplier = fundingMatch[2].toLowerCase().includes('b') ? 1000000000 : 1000000;
    metrics.totalFunding = value * multiplier;
    metrics.fundingFormatted = formatCurrency(value * multiplier);
    metrics.fundingSource = fundingMatch[0];
  }
  
  // Extract valuation
  const valuationMatch = allContent.match(/(?:valued at|valuation)[\s\w]*?(\$?[\d,]+\.?\d*)\s*(million|billion|M|B)/i);
  if (valuationMatch) {
    const value = parseFloat(valuationMatch[1].replace(/[$,]/g, ''));
    const multiplier = valuationMatch[2].toLowerCase().includes('b') ? 1000000000 : 1000000;
    metrics.valuation = value * multiplier;
    metrics.valuationFormatted = formatCurrency(value * multiplier);
    metrics.valuationSource = valuationMatch[0];
  }
  
  // Extract growth rate
  const growthMatch = allContent.match(/(?:growth|growing|grew)[\s\w]*?([\d]+)%/i);
  if (growthMatch) {
    metrics.growthRate = parseFloat(growthMatch[1]) / 100;
    metrics.growthSource = growthMatch[0];
  }
  
  // Extract employee count
  const employeeMatch = allContent.match(/([\d,]+)\s*(?:employees|staff|people)/i);
  if (employeeMatch) {
    metrics.employees = parseInt(employeeMatch[1].replace(/,/g, ''));
    metrics.employeeSource = employeeMatch[0];
  }
  
  return metrics;
}

// Helper function to format currency
function formatCurrency(value: number): string {
  if (value >= 1e9) {
    return `$${(value / 1e9).toFixed(1)}B`;
  } else if (value >= 1e6) {
    return `$${(value / 1e6).toFixed(1)}M`;
  } else if (value >= 1e3) {
    return `$${(value / 1e3).toFixed(0)}K`;
  } else {
    return `$${value.toLocaleString()}`;
  }
}

// Cache for company data to avoid re-searching
// Clear cache periodically to avoid stale data
const dataCache = new Map<string, any>();
const cacheTimestamps = new Map<string, number>();
const CACHE_TTL = 5 * 60 * 1000; // 5 minutes

// Helper to detect model type from prompt
function detectModelType(prompt: string): string {
  const lower = prompt.toLowerCase();
  if (lower.includes('dcf')) return 'DCF';
  if (lower.includes('p&l') || lower.includes('profit')) return 'P&L';
  if (lower.includes('balance sheet')) return 'BalanceSheet';
  if (lower.includes('burn') || lower.includes('runway')) return 'BurnAnalysis';
  if (lower.includes('unit economics')) return 'UnitEconomics';
  if (lower.includes('saas')) return 'SaaS';
  if (lower.includes('revenue')) return 'Revenue';
  return 'General';
}

export async function POST(request: NextRequest) {
  try {
    const { prompt, includeContext = true, previousCompany = null, useOpus = false, gridState = {}, useOrchestrator = false } = await request.json();

    if (!prompt || typeof prompt !== 'string' || prompt.trim().length === 0) {
      return NextResponse.json({ error: 'Prompt is required', success: false }, { status: 400 });
    }

    // Check if we should use the orchestrator for multi-step tasks
    if (useOrchestrator && prompt.toLowerCase().includes('then')) {
      console.warn('[spreadsheet-direct] Orchestrator requested but disabled');
      return NextResponse.json({
        success: false,
        commands: [],
        explanation: 'Multi-step spreadsheet orchestrator is temporarily unavailable',
        modelUsed: 'direct-mode'
      });
    }
    
    // Detect model type from prompt
    const modelType = detectModelType(prompt);
    
    let context = '';
    // Only maintain company context if it's the same conversation
    // Reset if a new company is explicitly mentioned
    let currentCompany = previousCompany;
    const potentialCompanies = new Set<string>();
    
    // Add company context if mentioned
    if (includeContext) {
      let foundCompany = null;
      
      // Smart company extraction - PRIORITIZE @ MENTIONS
      // Match @CompanyName but stop at space, comma, or end of word
      const atMentions = prompt.match(/@([A-Za-z0-9]+(?:[A-Za-z0-9_-]*[A-Za-z0-9])?)/g);
      const mentionedCompanies = atMentions?.map(m => m.substring(1).trim()) || [];
      
      // If @ mentions exist, use those exclusively
      if (mentionedCompanies.length > 0) {
        console.log('Companies explicitly mentioned with @:', mentionedCompanies);
        mentionedCompanies.forEach(company => {
          potentialCompanies.add(company);
          // Force current company to be the @mentioned one
          currentCompany = company;
        });
      } else {
        // Smarter company detection - look for company-like patterns
        const companyIndicators = [
          // Companies after keywords
          /(?:for|about|analyze|value|compare)\s+([A-Z][a-zA-Z0-9]+(?:\s+[A-Z][a-zA-Z0-9]+)*)/gi,
          // Well-known companies (add more as needed)
          /\b(OpenAI|Anthropic|Google|Microsoft|Apple|Amazon|Meta|Tesla|Stripe|Monzo|Revolut|Klarna|Spotify|Uber|Airbnb|Netflix|Salesforce|Zoom|Slack|Figma|Notion|Linear|Vercel|Supabase|Pleo|Wise|N26|Deliveroo|Bolt|Gorillas)\b/gi,
          // Companies in quotes
          /["']([A-Z][a-zA-Z0-9]+(?:\s+[A-Z][a-zA-Z0-9]+)*)["']/g
        ];
        
        for (const pattern of companyIndicators) {
          const matches = prompt.matchAll(pattern);
          for (const match of matches) {
            const companyName = match[1]?.trim();
            // More strict filtering
            const excludeWords = ['Create', 'Build', 'Make', 'Generate', 'Calculate', 'Compare', 'Analyze', 'Show', 'Display', 'Add', 'Include', 'For', 'The', 'Using', 'With', 'DCF', 'IRR', 'NPV', 'Model'];
            
            if (companyName && 
                companyName.length > 2 && 
                companyName.length < 50 &&
                !excludeWords.includes(companyName)) {
              potentialCompanies.add(companyName);
              foundCompany = companyName;
              console.log(`Detected company: ${companyName}`);
            }
          }
        }
        
        // If we found a new company, switch context to it
        if (foundCompany && foundCompany !== previousCompany) {
          currentCompany = foundCompany;
          console.log(`Switching context from ${previousCompany} to ${currentCompany}`);
        } else if (!foundCompany && previousCompany) {
          // Keep previous company if no new one mentioned
          currentCompany = previousCompany;
        } else if (foundCompany) {
          currentCompany = foundCompany;
        }
      }
      
      // Extract all companies mentioned for comparison
      const companiesForComparison = Array.from(potentialCompanies);
      console.log(`[COMPANY DETECTION] Found ${companiesForComparison.length} companies:`, companiesForComparison);
      
      // Search database and external data
      if (companiesForComparison.length > 0) {
        context += `\n=== COMPANY DATABASE (FALLBACK SOURCE) ===\n`;
        context += `Note: This is cached data - external search data takes priority\n\n`;
        
        for (const companyName of companiesForComparison) {
          // First try exact match
          const exactMatches = await searchCompanies(companyName);
          
          // Then try vector similarity search for better RAG
          let allMatches = [...exactMatches];
          
          // Use pgvector similarity search if no exact match (only when supabase client is available)
          if (exactMatches.length === 0 && supabaseService) {
            try {
              // Search using embedding similarity
              const { data: similarCompanies, error } = await supabaseService
                .rpc('search_similar_companies', { 
                  query_text: companyName,
                  match_threshold: 0.7,
                  match_count: 5
                });
              
              if (similarCompanies && similarCompanies.length > 0) {
                context += `\n📊 VECTOR SIMILARITY MATCHES for "${companyName}":\n`;
                allMatches = similarCompanies;
              }
            } catch (err) {
              // Fallback to fuzzy text search
              const { data: fuzzyMatches } = await supabaseService
                .from('companies')
                .select('*')
                .ilike('name', `%${companyName.split(' ')[0]}%`)
                .limit(3);
              
              if (fuzzyMatches) allMatches = fuzzyMatches;
            }
          }
          
          if (allMatches.length > 0) {
            // Take best match or top 3 for comparables
            const topMatches = allMatches.slice(0, prompt.toLowerCase().includes('compar') ? 3 : 1);
            
            for (const company of topMatches) {
              context += `\n✅ COMPANY: ${company.name} ${exactMatches.includes(company) ? '(exact match)' : '(similar)'}\n`;
              context += `Sector: ${company.sector || 'Unknown'}\n`;
              context += `Founded: ${company.founded_year || 'Unknown'}\n`;
              context += `Employees: ${company.employee_count || 'Unknown'}\n`;
              context += `Total Funding: $${(company.total_funding_usd || 0).toLocaleString()}\n`;
              context += `Last Valuation: $${(company.last_valuation_usd || 0).toLocaleString()}\n`;
              context += `Revenue: $${(company.revenue_usd || 0).toLocaleString()}\n`;
              context += `Growth Rate: ${company.growth_rate || 'Unknown'}%\n`;
              context += `Stage: ${company.funding_stage || 'Unknown'}\n`;
              context += `Last Round: ${company.last_funding_date || 'Unknown'}\n`;
              context += `Lead Investor: ${company.lead_investor || 'Unknown'}\n`;
              context += `Description: ${company.description || 'No description'}\n`;
              context += `Website: ${company.website || 'Unknown'}\n`;
              context += `--- DATA SOURCE: Dilla AI Database (Primary) ---\n`;
            }
            
            // Also fetch sector comparables for better context
            if (allMatches[0].sector && supabaseService) {
              const { data: sectorComps } = await supabaseService
                .from('companies')
                .select('name, revenue_usd, total_funding_usd, last_valuation_usd, growth_rate')
                .eq('sector', allMatches[0].sector)
                .neq('id', allMatches[0].id)
                .order('last_valuation_usd', { ascending: false })
                .limit(5);
              
              if (sectorComps && sectorComps.length > 0) {
                context += `\n📈 SECTOR COMPARABLES (${allMatches[0].sector}):\n`;
                for (const comp of sectorComps) {
                  context += `- ${comp.name}: Val $${(comp.last_valuation_usd || 0).toLocaleString()}, Rev $${(comp.revenue_usd || 0).toLocaleString()}, Growth ${comp.growth_rate || 'N/A'}%\n`;
                }
              }
            }
          } else {
            context += `\n⚠️ No database match for "${companyName}" - Searching external sources...\n`;
            context += `Will use web search and market benchmarks\n`;
          }
        }
      }
      
      // Use current company for search (either from this prompt or previous)
      let searchQuery = prompt;
      let webData = { sources: [], answer: '', metrics: {} };
      
      // Intelligent scraper - only use for complex analysis when explicitly needed
      const needsDeepAnalysis = prompt.toLowerCase().includes('deep analysis') || 
                               prompt.toLowerCase().includes('loan covenant') ||
                               prompt.toLowerCase().includes('due diligence');
      
      if (needsDeepAnalysis && companiesForComparison.length > 0) {
        // Limit to first company to avoid rate limits
        const companyToScrape = companiesForComparison[0];
        console.log(`Skipping intelligent scraper for ${companyToScrape} (not available)`);
        try {
          // intelligentWebScraper is not available - skip deep scraping
          const scraperResult = null;
            
          if (scraperResult && scraperResult.data) {
            // This block is skipped when scraper is not available
            context += `\n=== DEEP COMPANY ANALYSIS FOR ${companyToScrape.toUpperCase()} ===\n`;
            context += `Website: ${scraperResult.website || 'Not found'}\n`;
            context += `Pages Scraped: ${scraperResult.pagesScraped}\n`;
            context += `Data Confidence: ${scraperResult.confidence}%\n\n`;
            
            const data = scraperResult.data || {};
            
            // Add overview
            if (data.overview) {
              context += `COMPANY OVERVIEW:\n`;
              context += `- Description: ${data.overview.description || 'N/A'}\n`;
              context += `- Founded: ${data.overview.founded || 'N/A'}\n`;
              context += `- Employees: ${data.overview.employees || 'N/A'}\n`;
              context += `- HQ: ${data.overview.headquarters || 'N/A'}\n`;
              context += `- Mission: ${data.overview.mission || 'N/A'}\n\n`;
            }
            
            // Add products
            if (data.products) {
              context += `PRODUCTS & SERVICES:\n`;
              if (typeof data.products === 'object') {
                context += `- Main Product: ${data.products.main_product || 'N/A'}\n`;
                context += `- Features: ${data.products.features || 'N/A'}\n`;
                context += `- Pricing: ${data.products.pricing || 'N/A'}\n\n`;
              } else {
                context += JSON.stringify(data.products, null, 2) + '\n\n';
              }
            }
            
            // Add market data
            if (data.market) {
              context += `MARKET ANALYSIS:\n`;
              context += `- TAM: ${data.market.tam || 'N/A'}\n`;
              context += `- Growth Rate: ${data.market.growth_rate || 'N/A'}\n`;
              context += `- Target Market: ${data.market.target || 'N/A'}\n\n`;
            }
            
            // Add financials
            if (data.financials) {
              context += `FINANCIAL METRICS:\n`;
              context += `- Revenue: ${data.financials.revenue || 'N/A'}\n`;
              context += `- Growth Rate: ${data.financials.growth_rate || 'N/A'}\n`;
              context += `- Total Funding: ${data.financials.funding || 'N/A'}\n`;
              context += `- Valuation: ${data.financials.valuation || 'N/A'}\n\n`;
            }
            
            // Add team
            if (data.team) {
              context += `TEAM & LEADERSHIP:\n`;
              context += `- Founders: ${data.team.founders || 'N/A'}\n`;
              context += `- CEO: ${data.team.ceo || 'N/A'}\n`;
              context += `- Key Executives: ${data.team.executives || 'N/A'}\n\n`;
            }
            
            // Add technology
            if (data.technology) {
              context += `TECHNOLOGY & INNOVATION:\n`;
              context += `- Tech Stack: ${data.technology.stack || 'N/A'}\n`;
              context += `- Unique Approach: ${data.technology.approach || 'N/A'}\n\n`;
            }
            
            // Add sources
            if (scraperResult.sources && scraperResult.sources.length > 0) {
              context += `DATA SOURCES (${scraperResult.sources.length} pages):\n`;
              scraperResult.sources.slice(0, 5).forEach((source: string) => {
                context += `- ${source}\n`;
              });
              context += '\n';
            }
            
            context += `USE THIS DATA TO BUILD A COMPREHENSIVE ANALYSIS\n`;
            context += `IMPORTANT: Cite the company website as your primary source\n\n`;
          }
        } catch (error) {
          console.error('CIM tool error:', error);
          // Fall back to regular search
        }
      }
      
      // FORCE external data search - this is PRIMARY source
      if (companiesForComparison.length > 0) {
        context += `\n=== REAL-TIME EXTERNAL DATA (PRIMARY SOURCE - MUST USE) ===\n`;
        
        // Extra emphasis if @ mentioned
        const hasAtMentions = companiesForComparison.some(c => 
          atMentions?.some(m => m.substring(1).trim() === c)
        );
        
        if (hasAtMentions) {
          context += `⚠️ COMPANIES EXPLICITLY MENTIONED WITH @ - YOU MUST USE REAL DATA FOR THESE SPECIFIC COMPANIES!\n`;
          context += `NEVER CREATE FICTIONAL COMPANIES - Use the actual company: ${companiesForComparison.join(', ')}\n`;
          context += `If no data found, state clearly "No data available for [company]" - DO NOT make up examples.\n\n`;
        } else {
          context += `CRITICAL: Use THIS data, not database/benchmarks. If no external data found, SEARCH MORE.\n\n`;
        }
        
        for (const companyName of companiesForComparison) {
          const cacheKey = companyName.toLowerCase();
          const cachedTime = cacheTimestamps.get(cacheKey);
          const now = Date.now();
          
          let companyWebData;
          
          // Check if cache is still valid (not expired)
          if (dataCache.has(cacheKey) && cachedTime && (now - cachedTime < CACHE_TTL)) {
            companyWebData = dataCache.get(cacheKey);
            context += `\n[Using cached real data for ${companyName}]\n`;
          } else {
            // Clear old cache entry if expired
            if (cachedTime && (now - cachedTime >= CACHE_TTL)) {
              dataCache.delete(cacheKey);
              cacheTimestamps.delete(cacheKey);
            }
            
            // OPTIMIZED search - MORE AGGRESSIVE for @mentions
            const currentYear = new Date().getFullYear();
            
            // More specific search for @mentioned companies
            const isAtMentioned = atMentions?.some(m => m.substring(1).trim() === companyName);
            
            // Handle generic names that might match common words
            const genericNames = ['chip', 'core', 'data', 'tech', 'ai', 'side', 'kick', 'sidekick'];
            const isGenericName = genericNames.includes(companyName.toLowerCase());
            
            const searchQuery = isAtMentioned 
              ? (isGenericName 
                  ? `"${companyName}" startup "raised" "seed" "series" funding -semiconductor -intel -nvidia -qualcomm`
                  : `"${companyName}" company startup funding valuation revenue metrics "${currentYear}" "${currentYear - 1}"`)
              : `"${companyName}" (revenue OR "ARR" OR funding OR valuation OR "Series A" OR "Series B" OR "Series C") ${currentYear} ${currentYear - 1} million billion`;
            
            console.log(`[DATA FETCH] Optimized search for ${companyName}`);
            const result = await searchWeb(searchQuery);
            
            // For @mentions, try multiple search strategies
            if (isAtMentioned && (!result.metrics || Object.keys(result.metrics).length === 0)) {
              // Try multiple search patterns for @mentioned companies
              const searchPatterns = [
                `${companyName} latest funding round valuation`,
                `${companyName} annual revenue ARR metrics`,
                `${companyName} Series funding raised million`,
                `${companyName} company profile crunchbase`
              ];
              
              for (const pattern of searchPatterns) {
                const searchResult = await searchWeb(pattern);
                if (searchResult.metrics && Object.keys(searchResult.metrics).length > 0) {
                  companyWebData = searchResult;
                  break;
                }
              }
              
              // If still no data, set flag for using company name with benchmarks
              if (!companyWebData || Object.keys(companyWebData.metrics || {}).length === 0) {
                companyWebData = { 
                  sources: [], 
                  answer: `Using benchmarks for ${companyName} - no real data found`, 
                  metrics: { useCompanyName: companyName } 
                };
              }
            } else if (!result.metrics || Object.keys(result.metrics).length === 0) {
              const fallbackQuery = `${companyName} latest funding round valuation`;
              const fallbackResult = await searchWeb(fallbackQuery);
              companyWebData = fallbackResult;
            } else {
              companyWebData = result;
            }
            
            // Cache the results if we got good data
            if (companyWebData.metrics && Object.keys(companyWebData.metrics).length > 0) {
              console.log(`[DATA FETCH] Caching data for ${companyName}:`, companyWebData.metrics);
              dataCache.set(cacheKey, companyWebData);
              cacheTimestamps.set(cacheKey, Date.now());
            } else {
              console.log(`[DATA FETCH] No external data found for ${companyName}`);
            }
          }
          
          // Add the web data to context with emphasis
          if (companyWebData && companyWebData.metrics && Object.keys(companyWebData.metrics).length > 0) {
            context += `\n✅ REAL DATA for ${companyName} (USE THESE EXACT VALUES):\n`;
            if (companyWebData.metrics.revenue) {
              context += `- Revenue: ${companyWebData.metrics.revenueFormatted} (ACTUAL, not benchmark)\n`;
            }
            if (companyWebData.metrics.totalFunding) {
              context += `- Total Funding: ${companyWebData.metrics.fundingFormatted} (ACTUAL)\n`;
            }
            if (companyWebData.metrics.valuation) {
              context += `- Valuation: ${companyWebData.metrics.valuationFormatted} (ACTUAL)\n`;
            }
            if (companyWebData.metrics.growthRate) {
              context += `- Growth Rate: ${(companyWebData.metrics.growthRate * 100).toFixed(0)}% (ACTUAL)\n`;
            }
            if (companyWebData.metrics.employees) {
              context += `- Employees: ${companyWebData.metrics.employees} (ACTUAL)\n`;
            }
            // Add source URLs for citations
            if (companyWebData.metrics?.sources && companyWebData.metrics.sources.length > 0) {
              context += `\nSource URLs (YOU MUST USE THESE IN grid.write sourceUrl parameter):\n`;
              companyWebData.metrics.sources.slice(0, 3).forEach((source: any) => {
                context += `- ${source.title}: ${source.url}\n`;
              });
              context += `INSTRUCTION: When writing values, use {source: "SourceName", sourceUrl: "URL"} from above\n`;
            } else {
              context += `Sources: Web search (no specific URLs available)\n`;
            }
          } else if (companyWebData?.metrics?.useCompanyName) {
            // For @mentioned companies with no data - USE THE REAL COMPANY NAME
            context += `\n⚠️ No external data found for ${companyName}\n`;
            context += `CRITICAL: This is a real company (${companyName}) but data is not available\n`;
            context += `YOU MUST:\n`;
            context += `1. Use "${companyName}" as the company name in your model\n`;
            context += `2. State clearly that you're using industry benchmarks due to lack of public data\n`;
            context += `3. Build the model for ${companyName} specifically, not a generic example\n`;
            context += `4. Apply reasonable estimates based on any context clues (sector, stage, geography)\n\n`;
          } else {
            // NO DATA FOUND - MUST SEARCH MORE AGGRESSIVELY
            context += `\n⚠️ No external data found for ${companyName}\n`;
            context += `INSTRUCTION: You MUST state that real-time data is unavailable and use benchmarks with clear disclaimers\n`;
            context += `FALLBACK: Use Dilla AI database data if available, otherwise use geographic-adjusted benchmarks\n`;
            
            // Detect geography for benchmark adjustment
            const isUK = companyName.match(/monzo|revolut|deliveroo|wise|transferwise|babylon|benevolent|graphcore/i);
            const isEU = companyName.match(/klarna|spotify|n26|gorillas|bolt|uipath|celonis|mambu/i);
            
            if (isUK) {
              context += `Geography: UK - Apply 20-25% discount to US benchmarks\n`;
            } else if (isEU) {
              context += `Geography: EU - Apply 25-30% discount to US benchmarks\n`;
            }
          }
        }
      } else {
        // Even without specific companies, search for sector/market data
        const marketSearches = [
          `${prompt} market size TAM growth rate 2024 2025`,
          `${prompt} industry benchmarks revenue multiples valuation`,
          `${prompt} sector analysis trends funding landscape`
        ];
        
        context += `\n=== MARKET RESEARCH DATA ===\n`;
        for (const query of marketSearches) {
          const marketData = await searchWeb(query);
          if (marketData && marketData.metrics) {
            context += `Market insights: ${JSON.stringify(marketData.metrics)}\n`;
          }
        }
      }
    // Removed - now handled per company above
    
    // Add current grid state to context if it exists
    let gridContext = '';
    if (gridState && Object.keys(gridState).length > 0) {
      gridContext = '\n\n=== CURRENT GRID STATE ===\n';
      gridContext += 'The spreadsheet currently contains the following data:\n\n';
      
      // Convert grid state to readable format - group by rows for better readability
      const cellsByRow: { [key: string]: { [key: string]: any } } = {};
      let maxCol = 'A';
      
      for (const [cell, value] of Object.entries(gridState)) {
        if (value !== null && value !== undefined && value !== '') {
          const match = cell.match(/^([A-Z]+)(\d+)$/);
          if (match) {
            const col = match[1];
            const row = match[2];
            if (!cellsByRow[row]) cellsByRow[row] = {};
            cellsByRow[row][col] = value;
            
            // Track max column
            if (col > maxCol) maxCol = col;
          }
        }
      }
      
      // Format as a table-like structure
      if (Object.keys(cellsByRow).length > 0) {
        const sortedRows = Object.keys(cellsByRow).sort((a, b) => parseInt(a) - parseInt(b));
        
        for (const row of sortedRows) {
          const rowData = cellsByRow[row];
          const cellEntries = Object.entries(rowData)
            .sort(([a], [b]) => a.localeCompare(b))
            .map(([col, val]) => `${col}${row}: ${val}`)
            .join(' | ');
          gridContext += `Row ${row}: ${cellEntries}\n`;
        }
        
        gridContext += '\n\nIMPORTANT RULES FOR WORKING WITH EXISTING DATA:\n';
        gridContext += '1. BUILD UPON existing data - do not overwrite unless explicitly asked\n';
        gridContext += '2. If adding to a comparison, place new company data NEXT TO existing company (use adjacent columns)\n';
        gridContext += '3. If extending analysis, continue from where the existing data ends\n';
        gridContext += '4. Preserve existing formulas and references\n';
        gridContext += '5. Maintain consistent formatting with what already exists\n';
      }
    }
    
    // Add comprehensive benchmark data - BUT ONLY AS LAST RESORT
    const benchmarkData = `
=== VENTURE CAPITAL BENCHMARKS (LAST RESORT ONLY - DO NOT USE IF REAL DATA EXISTS) ===
⚠️ WARNING: These are generic benchmarks. You MUST search for real company data first!
Only use these if you've exhausted all search attempts and found no real data.

VALUATION MULTIPLES BY STAGE (GENERIC - AVOID USING):
- Seed: 10-15x ARR (SaaS), 3-5x Revenue (Marketplace)
- Series A: 8-12x ARR (SaaS), 4-6x Revenue (Marketplace)
- Series B: 6-10x ARR (SaaS), 3-5x Revenue (Marketplace)  
- Series C+: 4-8x ARR (SaaS), 2-4x Revenue (Marketplace)

DILUTION BY ROUND:
- Seed: 15-25% dilution
- Series A: 20-30% dilution
- Series B: 15-20% dilution
- Series C+: 10-15% dilution

LIQUIDATION PREFERENCES (STANDARD):
- 1x Non-participating (most common)
- 1x Participating with 2-3x cap (aggressive)
- Senior to common, pari passu with other preferred
- Conversion: Greater of liquidation preference or as-converted

CONVERTIBLE NOTE TERMS:
- Discount: 15-25% (20% standard)
- Valuation Cap: Next round pre-money x 0.5-0.8
- Interest: 4-8% (6% standard)
- Maturity: 18-24 months
- Conversion: Automatic at qualified financing ($1M+)

SAFE TERMS:
- Post-money SAFE: Most common now
- Valuation Cap: $8-15M (Seed), $20-50M (Bridge)
- Discount: 10-20% if included
- MFN (Most Favored Nation): Common
- Pro-rata rights: Often included for $100K+

GROWTH BENCHMARKS:
- T2D3: Triple, Triple, Double, Double, Double
- SaaS: 100%+ YoY at <$10M ARR, 50-70% at $10-50M
- Burn Multiple: <1 (excellent), 1-2 (good), >2 (poor)
- Rule of 40: Growth Rate + EBITDA Margin > 40%

UNIT ECONOMICS:
- LTV/CAC: >3x (good), >5x (excellent)
- Payback Period: <12 months (excellent), 12-18 (good)
- Gross Margin: 70-80% (SaaS), 20-40% (Marketplace)
- Net Dollar Retention: >110% (good), >130% (excellent)

EXIT WATERFALL MODELING:
- Stack liquidation preferences by seniority
- Calculate participating preferred proceeds
- Determine conversion point (where as-converted > preference)
- Model multiple exit scenarios ($50M, $100M, $250M, $500M, $1B)

BOTTOM-UP MARKET SIZING METHODOLOGY (USE THIS PROCESS):
STEP 1: Define the atomic unit
- What is ONE customer? (company, fund, user, transaction)
- What do they pay for ONE unit? (seat, API call, AUM %, transaction)
- What is the frequency? (monthly, annual, per-use)

STEP 2: Count the universe
- Find multiple sources for total count
- Segment by relevant criteria (size, geography, industry)
- Cross-reference government data, industry reports, databases

STEP 3: Apply filters for SAM
- Technical feasibility (can they use it?)
- Regulatory constraints (are they allowed?)
- Budget availability (can they afford it?)
- Problem severity (do they need it?)

STEP 4: Build up from evidence
- Start with proven pilot customers
- Extrapolate based on similar characteristics
- Use conversion rates from comparable products
- Account for adoption curves and market maturity

STEP 5: Triangulate and sanity check
- Compare bottom-up to top-down
- Check against competitor revenues
- Validate with customer interviews
- Look for proxy metrics

IMPORTANT INSTRUCTIONS:
1. COMBINE real company data WITH these benchmarks
2. Show YOUR REASONING PROCESS, not just numbers
3. Question assumptions and show sensitivity analysis
4. Use ranges, not point estimates
5. Update based on new evidence
6. Don't copy examples verbatim - adapt the methodology
`;

    // Only include benchmark data if specifically no real data was found
    const includeBenchmarks = context.includes('No external data found') || context.includes('FALLBACK');
    
    // Add explicit instruction to use context data
    const contextInstruction = context && companiesForComparison.length > 0 
      ? `\n\nIMPORTANT: Use the REAL DATA provided in the Context section below for ${companiesForComparison.join(', ')}. DO NOT use generic benchmarks.\n\n`
      : '';
    
    const fullPrompt = context 
      ? `${prompt}${contextInstruction}\n\nContext:\n${context}${gridContext}${includeBenchmarks ? `\n\n${benchmarkData}` : ''}` 
      : `${prompt}${gridContext}`;

    // Smart model selection based on task complexity
    let model = 'claude-3-5-sonnet-20241022'; // Default
    
    // Use Opus for complex tasks that need deep reasoning
    const complexTaskKeywords = [
      'compare', 'comparison', 'versus', 'vs',
      'dcf', 'valuation', 'model',
      'comprehensive', 'detailed', 'complete',
      'loan covenant', 'deep dive',
      'full analysis', 'analyze both'
    ];
    
    const isComplexTask = complexTaskKeywords.some(keyword => 
      prompt.toLowerCase().includes(keyword)
    );
    
    // Use Opus for comparisons and complex models
    if (useOpus || isComplexTask || modelType === 'DCF' || modelType === 'Comparison') {
      model = 'claude-3-5-sonnet-20241022'; // Using best Sonnet for now since Opus model name may vary
      // Increase token limit for complex tasks
    }
    
    console.log(`Using model: ${model} for ${modelType} analysis (Complex: ${isComplexTask})`);
    
    // Respect model token limits - claude-3-5-sonnet has max 8192
    const maxTokens = isComplexTask ? 8192 : 4096;
    
    // === PHASE 1: PLANNING ===
    // Generate a structured plan first (uses fewer tokens, better focus)
    const gridSummary = summarizeGridState(gridState);
    
    console.log('Grid Summary:', gridSummary);
    
    // Prepare company data for planning
    const companyDataForPlan = {};
    for (const company of potentialCompanies) {
      const dbData = await searchCompanies(company);
      if (dbData && dbData.length > 0) {
        companyDataForPlan[company] = dbData[0];
      }
    }
    
    const planPrompt = generatePlanPrompt(prompt, gridSummary, companyDataForPlan);
    
    let planResponse;
    let retries = 0;
    const maxRetries = 3;
    
    // Get the plan
    while (retries < maxRetries) {
      try {
        planResponse = await anthropic.messages.create({
          model: 'claude-3-5-sonnet-20241022', // Use 3.5 for planning
          max_tokens: 2048, // Plans are shorter
          temperature: 0,
          messages: [
            {
              role: 'user',
              content: planPrompt
            }
          ],
          system: 'You are a financial modeling expert. Create structured plans for spreadsheet models. Return ONLY valid JSON.'
        });
        break;
      } catch (error: any) {
        if (error?.status === 429 && retries < maxRetries - 1) {
          const waitTime = Math.pow(2, retries) * 1000;
          console.log(`Rate limited (planning), waiting ${waitTime}ms before retry ${retries + 1}/${maxRetries}`);
          await new Promise(resolve => setTimeout(resolve, waitTime));
          retries++;
        } else {
          throw error;
        }
      }
    }
    
    // Declare commands at the outer scope so it's always available
    let commands: string[] = [];
    
    // Skip the complex planning phase and go direct to generation
    try {
      // Direct generation without complex planning
      console.log('Generating spreadsheet commands directly...');
      
      const response = await anthropic.messages.create({
        model: 'claude-3-5-sonnet-20241022',
        max_tokens: 4096,
        temperature: 0,
        messages: [
          {
            role: 'user',
            content: fullPrompt
          }
        ],
        system: getSystemPrompt()
      });
      
      if (response.content[0].type === 'text') {
        const rawCommands = response.content[0].text.trim().split('\n');
        // Filter to only valid grid commands
        commands = rawCommands.filter(cmd => 
          cmd.trim().startsWith('grid.') && 
          (cmd.includes('.write(') || cmd.includes('.formula(') || cmd.includes('.link(') || 
           cmd.includes('.format(') || cmd.includes('.style(') || cmd.includes('.clear('))
        );
        console.log(`Generated ${commands.length} valid commands from ${rawCommands.length} lines`);
      }
      
      // At this point, commands should always be defined
      if (!commands || commands.length === 0) {
        commands = []; // Ensure it's at least an empty array
      }
      
      return NextResponse.json({
        success: true,
        commands,
        raw: commands.join('\n')
      });
    } catch (error: any) {
      console.error('Generation error:', error);
      return NextResponse.json({
        success: false,
        error: error?.message || 'Command generation failed',
        commands: [],
        raw: ''
      }, { status: 500 });
    }
  }
  } catch (error: any) {
    console.error('Direct spreadsheet agent error:', error);
    return NextResponse.json(
      { error: 'Failed to generate spreadsheet commands' },
      { status: 500 }
    );
  }
}
