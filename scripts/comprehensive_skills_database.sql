-- Comprehensive Skills Database for Financial Modeling
-- Includes all formulas, patterns, and frameworks from the VC Platform

-- Drop existing table if needed to recreate
DROP TABLE IF EXISTS modeling_skills CASCADE;

-- Create the main skills table
CREATE TABLE modeling_skills (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  category VARCHAR(50) NOT NULL, -- 'skill', 'formula', 'pattern', 'framework', 'integration'
  model_type VARCHAR(50), -- Model types from codebase
  title VARCHAR(255) NOT NULL,
  description TEXT NOT NULL,
  implementation TEXT, -- Actual grid commands
  formula_syntax TEXT, -- For formula skills
  tags TEXT[], 
  complexity_level INTEGER DEFAULT 1, -- 1=basic, 2=intermediate, 3=advanced
  requires_search BOOLEAN DEFAULT false, -- Does it need real data?
  embedding vector(384),
  usage_count INTEGER DEFAULT 0,
  created_at TIMESTAMP DEFAULT NOW()
);

-- Create indexes
CREATE INDEX idx_skills_embedding ON modeling_skills USING ivfflat (embedding vector_cosine_ops);
CREATE INDEX idx_skills_model_type ON modeling_skills(model_type);
CREATE INDEX idx_skills_category ON modeling_skills(category);
CREATE INDEX idx_skills_complexity ON modeling_skills(complexity_level);

-- RAG search function
CREATE OR REPLACE FUNCTION search_skills(
  query_text TEXT,
  model_type_filter VARCHAR(50) DEFAULT NULL,
  complexity_filter INTEGER DEFAULT NULL,
  limit_count INTEGER DEFAULT 5
)
RETURNS TABLE (
  id UUID,
  category VARCHAR(50),
  model_type VARCHAR(50),
  title VARCHAR(255),
  description TEXT,
  implementation TEXT,
  formula_syntax TEXT,
  complexity_level INTEGER,
  similarity FLOAT
)
LANGUAGE plpgsql
AS $$
DECLARE
  query_embedding vector(384);
BEGIN
  -- Generate embedding for query
  SELECT embedding INTO query_embedding
  FROM generate_embeddings(query_text);
  
  RETURN QUERY
  SELECT 
    ms.id,
    ms.category,
    ms.model_type,
    ms.title,
    ms.description,
    ms.implementation,
    ms.formula_syntax,
    ms.complexity_level,
    1 - (ms.embedding <=> query_embedding) AS similarity
  FROM modeling_skills ms
  WHERE 
    (model_type_filter IS NULL OR ms.model_type = model_type_filter)
    AND (complexity_filter IS NULL OR ms.complexity_level <= complexity_filter)
  ORDER BY ms.embedding <=> query_embedding
  LIMIT limit_count;
END;
$$;

-- =====================================
-- CORE FINANCIAL FORMULAS
-- =====================================

INSERT INTO modeling_skills (category, model_type, title, description, formula_syntax, implementation, tags, complexity_level) VALUES

-- Basic Financial Formulas
('formula', 'General', 'NPV - Net Present Value',
'Calculates present value of cash flows discounted at specified rate',
'NPV(rate, cash_flows)',
'grid.formula("B10", "=NPV(0.12, B2:B7)")',
ARRAY['npv', 'dcf', 'valuation'], 1),

('formula', 'General', 'IRR - Internal Rate of Return',
'Calculates rate at which NPV equals zero',
'IRR(cash_flows)',
'grid.formula("B11", "=IRR(B2:B7)")',
ARRAY['irr', 'returns'], 1),

('formula', 'General', 'CAGR - Compound Annual Growth Rate',
'Calculates annualized growth rate over period',
'CAGR(begin_value, end_value, years)',
'grid.formula("B12", "=CAGR(B2, B7, 5)")',
ARRAY['cagr', 'growth'], 1),

('formula', 'General', 'MOIC - Multiple on Invested Capital',
'Calculates exit value divided by investment',
'MOIC(exit_value, invested)',
'grid.formula("B13", "=MOIC(B10, B2)")',
ARRAY['moic', 'returns', 'pe'], 2),

('formula', 'General', 'PMT - Payment Calculation',
'Calculates periodic payment for loan',
'PMT(rate, periods, present_value)',
'grid.formula("B14", "=PMT(0.08/12, 360, 500000)")',
ARRAY['pmt', 'debt', 'loan'], 1),

-- =====================================
-- WATERFALL & EXIT FORMULAS
-- =====================================

('formula', 'Waterfall', 'LIQUIDPREF - Liquidation Preference',
'Calculates liquidation preference payout',
'LIQUIDPREF(investment, multiple, participating)',
'grid.formula("D5", "=LIQUIDPREF(10000000, 1, false)")',
ARRAY['liquidation', 'preference', 'exit'], 2),

('formula', 'Waterfall', 'WATERFALL - Basic Waterfall',
'Calculates distribution waterfall',
'WATERFALL(exit_value, pref_amount, common_shares, total_shares)',
'grid.formula("D6", "=WATERFALL(100000000, 20000000, 600000, 1000000)")',
ARRAY['waterfall', 'distribution', 'exit'], 2),

('formula', 'Waterfall', 'IPORATCHET - IPO Ratchet',
'Guarantees minimum return for late-stage investors',
'IPORATCHET(investment, current_value, min_return)',
'grid.formula("D7", "=IPORATCHET(50000000, 200000000, 0.20)")',
ARRAY['ipo', 'ratchet', 'protection'], 3),

('formula', 'Waterfall', 'PARTICIPATING - Participating Preferred',
'Calculates participating preferred distribution',
'PARTICIPATING(exit_value, investment, multiple, ownership, cap)',
'grid.formula("D8", "=PARTICIPATING(200000000, 20000000, 1, 0.15, 60000000)")',
ARRAY['participating', 'preferred', 'exit'], 3),

('formula', 'Waterfall', 'DOWNROUND - Downround Protection',
'Enhanced terms for downround scenarios',
'DOWNROUND(exit_value, investment, enhanced_multiple, participating)',
'grid.formula("D9", "=DOWNROUND(80000000, 30000000, 1.5, true)")',
ARRAY['downround', 'protection', 'terms'], 3),

('formula', 'Waterfall', 'MASTOCK - M&A Stock/Cash Mix',
'Calculates mixed consideration in M&A',
'MASTOCK(exit_value, cash_ratio, stock_ratio)',
'grid.formula("D10", "=MASTOCK(500000000, 0.5, 0.5)")',
ARRAY['ma', 'merger', 'stock', 'cash'], 2),

('formula', 'Waterfall', 'CUMULDIV - Cumulative Dividends',
'Calculates accrued dividends',
'CUMULDIV(investment, rate, years)',
'grid.formula("D11", "=CUMULDIV(10000000, 0.08, 3)")',
ARRAY['dividend', 'cumulative', 'preferred'], 2),

('formula', 'Waterfall', 'CATCHUP - GP Catch-up',
'Calculates catch-up provision for carried interest',
'CATCHUP(proceeds, hurdle, catchup_pct)',
'grid.formula("D12", "=CATCHUP(100000000, 8000000, 0.80)")',
ARRAY['catchup', 'carry', 'gp', 'fund'], 3),

('formula', 'Waterfall', 'CARRIEDINT - Carried Interest',
'Calculates GP carried interest',
'CARRIEDINT(profits, hurdle, carry_pct)',
'grid.formula("D13", "=CARRIEDINT(50000000, 8000000, 0.20)")',
ARRAY['carry', 'carried interest', 'gp', 'fund'], 3),

-- =====================================
-- CAP TABLE FORMULAS
-- =====================================

('formula', 'CapTable', 'DILUTION - Ownership Dilution',
'Calculates dilution percentage',
'DILUTION(old_shares, new_shares, total_shares)',
'grid.formula("C5", "=DILUTION(1000000, 250000, 1500000)")',
ARRAY['dilution', 'equity', 'ownership'], 1),

('formula', 'CapTable', 'OWNERSHIP - Ownership Percentage',
'Calculates ownership percentage',
'OWNERSHIP(shares, total_shares)',
'grid.formula("C6", "=OWNERSHIP(250000, 1500000)")',
ARRAY['ownership', 'equity', 'percentage'], 1),

('formula', 'CapTable', 'PRICEPERSHARE - Share Price',
'Calculates price per share',
'PRICEPERSHARE(valuation, shares)',
'grid.formula("C7", "=PRICEPERSHARE(100000000, 10000000)")',
ARRAY['share price', 'valuation', 'equity'], 1),

('formula', 'CapTable', 'OPTIONPOOL - Option Pool Size',
'Calculates option pool size',
'OPTIONPOOL(percentage, post_money)',
'grid.formula("C8", "=OPTIONPOOL(0.15, 100000000)")',
ARRAY['options', 'esop', 'equity'], 2),

-- =====================================
-- SCENARIO & SENSITIVITY FORMULAS
-- =====================================

('formula', 'General', 'SCENARIO - Weighted Scenarios',
'Calculates probability-weighted outcome',
'SCENARIO(base, best, worst, "probabilities")',
'grid.formula("B20", "=SCENARIO(100, 150, 50, \"0.5,0.3,0.2\")")',
ARRAY['scenario', 'probability', 'analysis'], 2),

('formula', 'General', 'SENSITIVITY - Sensitivity Analysis',
'Tests sensitivity to variable changes',
'SENSITIVITY(base_value, variable, change)',
'grid.formula("B21", "=SENSITIVITY(100000000, 0.1, 1)")',
ARRAY['sensitivity', 'analysis', 'testing'], 2),

('formula', 'General', 'MONTECARLO - Monte Carlo Simulation',
'Runs Monte Carlo simulation',
'MONTECARLO(mean, std_dev, iterations)',
'grid.formula("B22", "=MONTECARLO(100, 20, 1000)")',
ARRAY['monte carlo', 'simulation', 'risk'], 3),

('formula', 'General', 'BREAKEVEN - Breakeven Analysis',
'Calculates breakeven point',
'BREAKEVEN(fixed_costs, contribution_margin, units)',
'grid.formula("B23", "=BREAKEVEN(100000, 50, 1)")',
ARRAY['breakeven', 'analysis', 'unit economics'], 1),

-- =====================================
-- STATISTICAL FORMULAS
-- =====================================

('formula', 'General', 'Statistical Functions',
'Standard deviation, variance, median, correlation',
'STDEV, VAR, MEDIAN, PERCENTILE, CORREL',
'grid.formula("B30", "=STDEV(A1:A100)")
grid.formula("B31", "=MEDIAN(A1:A100)")
grid.formula("B32", "=PERCENTILE(A1:A100, 0.75)")
grid.formula("B33", "=CORREL(A1:A100, B1:B100)")',
ARRAY['statistics', 'analysis'], 1),

-- =====================================
-- MODEL BUILDING SKILLS
-- =====================================

('skill', 'DCF', 'Complete DCF Model with Search',
'Build full DCF model with company data search, projections, and valuation',
'// Step 1: Search for company data
// Step 2: Build revenue projections
// Step 3: Calculate free cash flows
// Step 4: Apply discount rate
// Step 5: Calculate terminal value
// Step 6: Sum to enterprise value',
'grid.write("A1", "DCF Valuation Model")
grid.style("A1", {bold: true, fontSize: 14})

// Inputs Section
grid.write("A3", "INPUTS")
grid.style("A3", {bold: true})
grid.write("A4", "Company")
grid.write("B4", "[COMPANY_NAME]")
grid.write("A5", "Current Revenue")
grid.write("B5", [SEARCH_REVENUE])
grid.format("B5", "currency")
grid.write("A6", "Revenue Growth Rate")
grid.write("B6", [SEARCH_GROWTH_OR_0.25])
grid.format("B6", "percentage")
grid.write("A7", "EBITDA Margin")
grid.write("B7", 0.20)
grid.format("B7", "percentage")
grid.write("A8", "Tax Rate")
grid.write("B8", 0.21)
grid.format("B8", "percentage")
grid.write("A9", "WACC")
grid.write("B9", 0.12)
grid.format("B9", "percentage")
grid.write("A10", "Terminal Growth")
grid.write("B10", 0.03)
grid.format("B10", "percentage")

// Projections
grid.write("A12", "PROJECTIONS")
grid.style("A12", {bold: true})
grid.write("A13", "Year")
grid.write("B13", "1")
grid.write("C13", "2")
grid.write("D13", "3")
grid.write("E13", "4")
grid.write("F13", "5")

grid.write("A14", "Revenue")
grid.formula("B14", "=$B$5*(1+$B$6)")
grid.formula("C14", "=B14*(1+$B$6*0.9)")
grid.formula("D14", "=C14*(1+$B$6*0.8)")
grid.formula("E14", "=D14*(1+$B$6*0.7)")
grid.formula("F14", "=E14*(1+$B$6*0.6)")

grid.write("A15", "EBITDA")
grid.formula("B15", "=B14*$B$7")
grid.formula("C15", "=C14*$B$7")
grid.formula("D15", "=D14*$B$7")
grid.formula("E15", "=E14*$B$7")
grid.formula("F15", "=F14*$B$7")

grid.write("A16", "Tax")
grid.formula("B16", "=B15*$B$8")
grid.formula("C16", "=C15*$B$8")
grid.formula("D16", "=D15*$B$8")
grid.formula("E16", "=E15*$B$8")
grid.formula("F16", "=F15*$B$8")

grid.write("A17", "FCF")
grid.formula("B17", "=B15-B16")
grid.formula("C17", "=C15-C16")
grid.formula("D17", "=D15-D16")
grid.formula("E17", "=E15-E16")
grid.formula("F17", "=F15-F16")

// Valuation
grid.write("A19", "VALUATION")
grid.style("A19", {bold: true})
grid.write("A20", "Terminal Value")
grid.formula("B20", "=(F17*(1+$B$10))/($B$9-$B$10)")
grid.write("A21", "PV of FCFs")
grid.formula("B21", "=NPV($B$9,B17:F17)")
grid.write("A22", "PV of Terminal")
grid.formula("B22", "=B20/POWER(1+$B$9,5)")
grid.write("A23", "Enterprise Value")
grid.formula("B23", "=B21+B22")
grid.format("B20:B23", "currency")',
ARRAY['dcf', 'valuation', 'model', 'search'], 3, true),

('skill', 'SaaS', 'SaaS Metrics Dashboard',
'Complete SaaS metrics with cohort analysis and unit economics',
'Build comprehensive SaaS metrics dashboard',
'grid.write("A1", "SaaS Metrics Dashboard")
grid.style("A1", {bold: true, fontSize: 14})

// Core Metrics
grid.write("A3", "CORE METRICS")
grid.style("A3", {bold: true})
grid.write("A4", "MRR")
grid.write("B4", [SEARCH_MRR_OR_100000])
grid.format("B4", "currency")
grid.write("A5", "ARR")
grid.formula("B5", "=B4*12")
grid.format("B5", "currency")
grid.write("A6", "Customers")
grid.write("B6", [SEARCH_CUSTOMERS_OR_1000])
grid.write("A7", "ARPU")
grid.formula("B7", "=B4/B6")
grid.format("B7", "currency")

// Growth Metrics
grid.write("A9", "GROWTH METRICS")
grid.style("A9", {bold: true})
grid.write("A10", "Monthly Growth Rate")
grid.write("B10", 0.08)
grid.format("B10", "percentage")
grid.write("A11", "Monthly Churn Rate")
grid.write("B11", 0.02)
grid.format("B11", "percentage")
grid.write("A12", "Net Growth Rate")
grid.formula("B12", "=B10-B11")
grid.format("B12", "percentage")
grid.write("A13", "Logo Retention")
grid.formula("B13", "=1-B11")
grid.format("B13", "percentage")
grid.write("A14", "Net Revenue Retention")
grid.formula("B14", "=(1-B11)*1.15")
grid.format("B14", "percentage")

// Unit Economics
grid.write("A16", "UNIT ECONOMICS")
grid.style("A16", {bold: true})
grid.write("A17", "CAC")
grid.write("B17", 1500)
grid.format("B17", "currency")
grid.write("A18", "LTV")
grid.formula("B18", "=B7/B11")
grid.format("B18", "currency")
grid.write("A19", "LTV/CAC Ratio")
grid.formula("B19", "=B18/B17")
grid.write("A20", "Payback Period (months)")
grid.formula("B20", "=B17/B7")
grid.write("A21", "Magic Number")
grid.formula("B21", "=(B5-B5*0.75)/(B17*B6*0.25)")',
ARRAY['saas', 'metrics', 'mrr', 'arr', 'ltv', 'cac'], 2, true),

('skill', 'Comparison', 'Company Comparison Analysis',
'Side-by-side comparison with multiple companies',
'Compare companies across key metrics',
'grid.write("A1", "Company Comparison Analysis")
grid.style("A1", {bold: true, fontSize: 14})

grid.write("A3", "Metric")
grid.write("B3", "[Company 1]")
grid.write("C3", "[Company 2]")
grid.write("D3", "[Company 3]")
grid.style("A3:D3", {bold: true})

// Financial Metrics
grid.write("A5", "FINANCIALS")
grid.style("A5", {bold: true})
grid.write("A6", "Revenue")
grid.write("B6", [SEARCH_COMPANY1_REVENUE])
grid.write("C6", [SEARCH_COMPANY2_REVENUE])
grid.write("D6", [SEARCH_COMPANY3_REVENUE])
grid.format("B6:D6", "currency")

grid.write("A7", "Growth Rate")
grid.write("B7", [SEARCH_COMPANY1_GROWTH])
grid.write("C7", [SEARCH_COMPANY2_GROWTH])
grid.write("D7", [SEARCH_COMPANY3_GROWTH])
grid.format("B7:D7", "percentage")

grid.write("A8", "Gross Margin")
grid.write("B8", 0.70)
grid.write("C8", 0.65)
grid.write("D8", 0.75)
grid.format("B8:D8", "percentage")

// Valuation Metrics
grid.write("A10", "VALUATION")
grid.style("A10", {bold: true})
grid.write("A11", "Valuation")
grid.write("B11", [SEARCH_COMPANY1_VALUATION])
grid.write("C11", [SEARCH_COMPANY2_VALUATION])
grid.write("D11", [SEARCH_COMPANY3_VALUATION])
grid.format("B11:D11", "currency")

grid.write("A12", "Revenue Multiple")
grid.formula("B12", "=B11/B6")
grid.formula("C12", "=C11/C6")
grid.formula("D12", "=D11/D6")

grid.write("A13", "Growth-Adjusted Multiple")
grid.formula("B13", "=B12/B7")
grid.formula("C13", "=C12/C7")
grid.formula("D13", "=D12/D7")

// Rankings
grid.write("A15", "RANKINGS")
grid.style("A15", {bold: true})
grid.write("A16", "Revenue Rank")
grid.write("A17", "Growth Rank")
grid.write("A18", "Efficiency Rank")',
ARRAY['comparison', 'analysis', 'benchmarking'], 2, true),

('skill', 'CapTable', 'Dynamic Cap Table',
'Cap table with multiple rounds and dilution tracking',
'Build dynamic cap table with dilution',
'grid.write("A1", "Capitalization Table")
grid.style("A1", {bold: true, fontSize: 14})

// Headers
grid.write("A3", "Shareholder")
grid.write("B3", "Seed")
grid.write("C3", "Series A")
grid.write("D3", "Series B")
grid.write("E3", "Current Shares")
grid.write("F3", "Ownership %")
grid.style("A3:F3", {bold: true})

// Founders
grid.write("A4", "Founders")
grid.write("B4", 1000000)
grid.write("C4", 0)
grid.write("D4", 0)
grid.formula("E4", "=SUM(B4:D4)")

// Investors
grid.write("A5", "Seed Investors")
grid.write("B5", 200000)
grid.write("C5", 0)
grid.write("D5", 0)
grid.formula("E5", "=SUM(B5:D5)")

grid.write("A6", "Series A")
grid.write("B6", 0)
grid.write("C6", 300000)
grid.write("D6", 0)
grid.formula("E6", "=SUM(B6:D6)")

grid.write("A7", "Series B")
grid.write("B7", 0)
grid.write("C7", 0)
grid.write("D7", 400000)
grid.formula("E7", "=SUM(B7:D7)")

// Option Pool
grid.write("A8", "Option Pool")
grid.write("B8", 100000)
grid.write("C8", 50000)
grid.write("D8", 50000)
grid.formula("E8", "=SUM(B8:D8)")

// Totals
grid.write("A10", "Total Shares")
grid.formula("B10", "=SUM(B4:B8)")
grid.formula("C10", "=SUM(C4:C8)")
grid.formula("D10", "=SUM(D4:D8)")
grid.formula("E10", "=SUM(E4:E8)")
grid.style("A10:E10", {bold: true})

// Ownership Calculation
grid.formula("F4", "=E4/$E$10")
grid.formula("F5", "=E5/$E$10")
grid.formula("F6", "=E6/$E$10")
grid.formula("F7", "=E7/$E$10")
grid.formula("F8", "=E8/$E$10")
grid.format("F4:F8", "percentage")

// Dilution Tracking
grid.write("A12", "DILUTION ANALYSIS")
grid.style("A12", {bold: true})
grid.write("A13", "Founder Dilution")
grid.formula("B13", "=1-(E4/$B$10)")
grid.format("B13", "percentage")',
ARRAY['captable', 'equity', 'dilution', 'ownership'], 2, false),

('skill', 'Waterfall', 'Exit Waterfall Model',
'Complete exit waterfall with all preference types',
'Model exit proceeds distribution',
'grid.write("A1", "Exit Waterfall Analysis")
grid.style("A1", {bold: true, fontSize: 14})

// Exit Scenarios
grid.write("A3", "EXIT SCENARIOS")
grid.style("A3", {bold: true})
grid.write("A4", "Exit Value")
grid.write("B4", 50000000)
grid.write("C4", 100000000)
grid.write("D4", 500000000)
grid.format("B4:D4", "currency")

// Liquidation Preferences
grid.write("A6", "LIQUIDATION PREFERENCES")
grid.style("A6", {bold: true})
grid.write("A7", "Series C (2x participating)")
grid.write("B7", 30000000)
grid.write("C7", 2)
grid.write("D7", "participating")

grid.write("A8", "Series B (1.5x)")
grid.write("B8", 20000000)
grid.write("C8", 1.5)
grid.write("D8", "non-participating")

grid.write("A9", "Series A (1x)")
grid.write("B9", 10000000)
grid.write("C9", 1)
grid.write("D9", "non-participating")

// Distribution Calculation
grid.write("A11", "DISTRIBUTION")
grid.style("A11", {bold: true})

// Scenario 1 - Low Exit
grid.write("A12", "Low Exit ($50M)")
grid.write("A13", "Series C Pref")
grid.formula("B13", "=MIN(B4, B7*C7)")
grid.write("A14", "Series B Pref")
grid.formula("B14", "=MIN(B4-B13, B8*C8)")
grid.write("A15", "Series A Pref")
grid.formula("B15", "=MIN(B4-B13-B14, B9*C9)")
grid.write("A16", "Common")
grid.formula("B16", "=B4-B13-B14-B15")

// Scenario 2 - Mid Exit
grid.write("A18", "Mid Exit ($100M)")
grid.write("A19", "Series C Pref")
grid.formula("C19", "=MIN(C4, B7*C7)")
grid.write("A20", "Series B Pref")
grid.formula("C20", "=MIN(C4-C19, B8*C8)")
grid.write("A21", "Series A Pref")
grid.formula("C21", "=MIN(C4-C19-C20, B9*C9)")
grid.write("A22", "Common")
grid.formula("C22", "=C4-C19-C20-C21")

// Format all currency
grid.format("B13:C22", "currency")',
ARRAY['waterfall', 'exit', 'liquidation', 'distribution'], 3, false),

('skill', 'P&L', 'P&L Statement Builder',
'Complete P&L with all line items',
'Build comprehensive P&L statement',
'grid.write("A1", "Profit & Loss Statement")
grid.style("A1", {bold: true, fontSize: 14})

// Time periods
grid.write("B2", "2024")
grid.write("C2", "2025E")
grid.write("D2", "2026E")
grid.style("B2:D2", {bold: true})

// Revenue
grid.write("A4", "REVENUE")
grid.style("A4", {bold: true})
grid.write("A5", "Product Revenue")
grid.write("B5", [SEARCH_REVENUE_OR_10000000])
grid.formula("C5", "=B5*1.3")
grid.formula("D5", "=C5*1.25")
grid.write("A6", "Service Revenue")
grid.formula("B6", "=B5*0.2")
grid.formula("C6", "=C5*0.2")
grid.formula("D6", "=D5*0.2")
grid.write("A7", "Total Revenue")
grid.formula("B7", "=B5+B6")
grid.formula("C7", "=C5+C6")
grid.formula("D7", "=D5+D6")
grid.style("A7:D7", {bold: true})

// COGS
grid.write("A9", "COST OF GOODS SOLD")
grid.style("A9", {bold: true})
grid.write("A10", "Direct Costs")
grid.formula("B10", "=B7*0.3")
grid.formula("C10", "=C7*0.28")
grid.formula("D10", "=D7*0.26")
grid.write("A11", "Gross Profit")
grid.formula("B11", "=B7-B10")
grid.formula("C11", "=C7-C10")
grid.formula("D11", "=D7-D10")
grid.write("A12", "Gross Margin %")
grid.formula("B12", "=B11/B7")
grid.formula("C12", "=C11/C7")
grid.formula("D12", "=D11/D7")
grid.format("B12:D12", "percentage")

// Operating Expenses
grid.write("A14", "OPERATING EXPENSES")
grid.style("A14", {bold: true})
grid.write("A15", "Sales & Marketing")
grid.formula("B15", "=B7*0.25")
grid.formula("C15", "=C7*0.23")
grid.formula("D15", "=D7*0.20")
grid.write("A16", "R&D")
grid.formula("B16", "=B7*0.20")
grid.formula("C16", "=C7*0.18")
grid.formula("D16", "=D7*0.16")
grid.write("A17", "G&A")
grid.formula("B17", "=B7*0.10")
grid.formula("C17", "=C7*0.09")
grid.formula("D17", "=D7*0.08")
grid.write("A18", "Total OpEx")
grid.formula("B18", "=SUM(B15:B17)")
grid.formula("C18", "=SUM(C15:C17)")
grid.formula("D18", "=SUM(D15:D17)")

// EBITDA
grid.write("A20", "EBITDA")
grid.formula("B20", "=B11-B18")
grid.formula("C20", "=C11-C18")
grid.formula("D20", "=D11-D18")
grid.style("A20:D20", {bold: true})
grid.write("A21", "EBITDA Margin %")
grid.formula("B21", "=B20/B7")
grid.formula("C21", "=C20/C7")
grid.formula("D21", "=D20/D7")
grid.format("B21:D21", "percentage")

// Format currency
grid.format("B5:D7", "currency")
grid.format("B10:D11", "currency")
grid.format("B15:D18", "currency")
grid.format("B20:D20", "currency")',
ARRAY['p&l', 'income', 'statement', 'ebitda'], 2, true),

-- =====================================
-- DATA INTEGRATION PATTERNS
-- =====================================

('integration', 'General', 'Company Data Search Pattern',
'Pattern for searching and integrating company data',
'1. Detect company name from prompt
2. Search database for historical data
3. Search web for latest updates
4. Combine and validate data
5. Use in model with citations',
'// Detect company
const company = detectCompanyFromPrompt(prompt);

// Search database
const dbData = await searchDatabase(company);

// Search web for latest
const webData = await searchWeb(`${company} revenue funding 2025`);

// Combine sources
const revenue = webData.revenue || dbData.revenue_usd;
const growth = webData.growth || dbData.growth_rate || 0.25;
const valuation = webData.valuation || dbData.last_valuation_usd;

// Use in model
grid.write("A1", `${company} Analysis`);
grid.write("A2", "Data Sources: Database + Web Search");
grid.write("B3", revenue);',
ARRAY['search', 'data', 'integration'], 2, true),

('integration', 'General', 'Multi-Source Data Validation',
'Validate data across multiple sources',
'Cross-reference data from multiple sources for accuracy',
'// Get data from multiple sources
const sources = {
  database: await queryDatabase(company),
  tavily: await searchTavily(company),
  scraped: await scrapeWebsite(company.website)
};

// Validate and choose best data
const revenue = validateRevenue(sources);
const employees = validateEmployees(sources);

// Track source for citation
grid.write("A10", "Sources:");
grid.write("B10", revenue.source);
grid.write("B11", employees.source);',
ARRAY['validation', 'sources', 'data quality'], 3, true),

-- =====================================
-- ADVANCED PATTERNS
-- =====================================

('pattern', 'PWERM', 'PWERM Valuation',
'Probability-weighted expected return method',
'Full PWERM analysis with scenarios',
'grid.write("A1", "PWERM Analysis")
grid.write("A3", "Scenarios")
grid.write("B3", "Probability")
grid.write("C3", "Value")
grid.write("D3", "Weighted")

grid.write("A4", "IPO")
grid.write("B4", 0.20)
grid.write("C4", 500000000)
grid.formula("D4", "=B4*C4")

grid.write("A5", "M&A")
grid.write("B5", 0.40)
grid.write("C5", 300000000)
grid.formula("D5", "=B5*C5")

grid.write("A6", "Stay Private")
grid.write("B6", 0.30)
grid.write("C6", 200000000)
grid.formula("D6", "=B6*C6")

grid.write("A7", "Dissolution")
grid.write("B7", 0.10)
grid.write("C7", 0)
grid.formula("D7", "=B7*C7")

grid.write("A9", "Expected Value")
grid.formula("C9", "=SUM(D4:D7)")
grid.format("C4:D7", "currency")
grid.format("C9", "currency")',
ARRAY['pwerm', 'valuation', 'probability'], 3, false),

('pattern', 'BurnAnalysis', 'Burn Rate & Runway Analysis',
'Calculate burn rate and runway with scenarios',
'Analyze cash burn and runway',
'grid.write("A1", "Burn Rate Analysis")

grid.write("A3", "Current Cash")
grid.write("B3", [SEARCH_CASH_OR_10000000])
grid.format("B3", "currency")

grid.write("A4", "Monthly Revenue")
grid.write("B4", [SEARCH_MRR_OR_500000])
grid.format("B4", "currency")

grid.write("A5", "Monthly Expenses")
grid.write("B5", 800000)
grid.format("B5", "currency")

grid.write("A6", "Monthly Burn")
grid.formula("B6", "=B5-B4")
grid.format("B6", "currency")

grid.write("A7", "Runway (months)")
grid.formula("B7", "=B3/B6")

grid.write("A9", "Scenarios")
grid.write("A10", "Best Case (20% cost reduction)")
grid.formula("B10", "=B3/(B5*0.8-B4)")

grid.write("A11", "Worst Case (20% revenue decline)")
grid.formula("B11", "=B3/(B5-B4*0.8)")

grid.write("A12", "Break-even Month")
grid.formula("B12", "=B5/B4")',
ARRAY['burn', 'runway', 'cash'], 2, true),

('pattern', 'UnitEconomics', 'Unit Economics Deep Dive',
'Comprehensive unit economics analysis',
'Analyze unit economics in detail',
'grid.write("A1", "Unit Economics Analysis")

// Customer Metrics
grid.write("A3", "CUSTOMER METRICS")
grid.write("A4", "Avg Contract Value")
grid.write("B4", 12000)
grid.write("A5", "Customer Lifetime (months)")
grid.write("B5", 36)
grid.write("A6", "Monthly Churn")
grid.write("B6", 0.028)
grid.format("B6", "percentage")

// Revenue Metrics
grid.write("A8", "REVENUE METRICS")
grid.write("A9", "Gross Revenue per Customer")
grid.formula("B9", "=B4")
grid.write("A10", "Gross Margin %")
grid.write("B10", 0.80)
grid.format("B10", "percentage")
grid.write("A11", "Net Revenue per Customer")
grid.formula("B11", "=B9*B10")

// Cost Metrics
grid.write("A13", "COST METRICS")
grid.write("A14", "CAC")
grid.write("B14", 3000)
grid.write("A15", "Onboarding Cost")
grid.write("B15", 500)
grid.write("A16", "Support Cost/Month")
grid.write("B16", 50)
grid.write("A17", "Total Cost to Serve")
grid.formula("B17", "=B14+B15+(B16*B5)")

// Unit Economics
grid.write("A19", "UNIT ECONOMICS")
grid.write("A20", "LTV")
grid.formula("B20", "=(B4/12)/B6")
grid.write("A21", "LTV/CAC Ratio")
grid.formula("B21", "=B20/B14")
grid.write("A22", "Payback Period")
grid.formula("B22", "=B14/(B4/12)")
grid.write("A23", "Contribution Margin")
grid.formula("B23", "=B11-B17")
grid.write("A24", "Unit Economics Score")
grid.formula("B24", "=IF(B21>3,\"Excellent\",IF(B21>2,\"Good\",IF(B21>1,\"Poor\",\"Unsustainable\")))")

grid.format("B4", "currency")
grid.format("B9", "currency")
grid.format("B11", "currency")
grid.format("B14:B17", "currency")
grid.format("B20", "currency")
grid.format("B23", "currency")',
ARRAY['unit economics', 'ltv', 'cac', 'saas'], 2, false);

-- Update all embeddings
UPDATE modeling_skills
SET embedding = generate_embeddings(
  title || ' ' || 
  description || ' ' || 
  COALESCE(model_type, '') || ' ' ||
  COALESCE(array_to_string(tags, ' '), '')
)
WHERE embedding IS NULL;

-- Create helper function to get relevant skills for a prompt
CREATE OR REPLACE FUNCTION get_relevant_skills(
  user_prompt TEXT,
  max_skills INTEGER DEFAULT 3
)
RETURNS TABLE (
  skill_id UUID,
  title VARCHAR(255),
  implementation TEXT,
  relevance_score FLOAT
)
LANGUAGE plpgsql
AS $$
BEGIN
  -- Detect model type from prompt
  DECLARE
    detected_model_type VARCHAR(50);
  BEGIN
    detected_model_type := CASE
      WHEN lower(user_prompt) LIKE '%dcf%' THEN 'DCF'
      WHEN lower(user_prompt) LIKE '%saas%' OR lower(user_prompt) LIKE '%mrr%' THEN 'SaaS'
      WHEN lower(user_prompt) LIKE '%compar%' THEN 'Comparison'
      WHEN lower(user_prompt) LIKE '%valuat%' THEN 'Valuation'
      WHEN lower(user_prompt) LIKE '%p&l%' OR lower(user_prompt) LIKE '%profit%' THEN 'P&L'
      WHEN lower(user_prompt) LIKE '%cap%table%' THEN 'CapTable'
      WHEN lower(user_prompt) LIKE '%waterfall%' OR lower(user_prompt) LIKE '%exit%' THEN 'Waterfall'
      ELSE 'General'
    END;
    
    RETURN QUERY
    SELECT 
      ms.id AS skill_id,
      ms.title,
      ms.implementation,
      similarity AS relevance_score
    FROM search_skills(user_prompt, detected_model_type, 3, max_skills) ss
    JOIN modeling_skills ms ON ms.id = ss.id
    ORDER BY relevance_score DESC;
  END;
END;
$$;

-- Track skill usage for improving recommendations
CREATE OR REPLACE FUNCTION track_skill_usage(skill_id UUID)
RETURNS VOID AS $$
BEGIN
  UPDATE modeling_skills
  SET usage_count = usage_count + 1
  WHERE id = skill_id;
END;
$$ LANGUAGE plpgsql;