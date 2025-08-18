-- Create knowledge base for financial modeling patterns and frameworks
-- This uses pgvector to store and retrieve relevant modeling knowledge

-- Create table for modeling knowledge/skills
CREATE TABLE IF NOT EXISTS modeling_skills (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  category VARCHAR(50) NOT NULL, -- 'skill', 'formula', 'pattern', 'framework'
  model_type VARCHAR(50), -- 'DCF', 'Revenue', 'SaaS', 'Valuation', 'P&L', 'CapTable', 'Waterfall', 'Comparison', 'PWERM', 'General'
  title VARCHAR(255) NOT NULL,
  description TEXT NOT NULL,
  implementation TEXT, -- Actual grid commands
  tags TEXT[], -- For filtering
  embedding vector(384), -- For similarity search
  usage_count INTEGER DEFAULT 0,
  created_at TIMESTAMP DEFAULT NOW()
);

-- Create index for vector similarity search
CREATE INDEX IF NOT EXISTS idx_modeling_skills_embedding 
ON modeling_skills USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);

-- Function to search relevant skills
CREATE OR REPLACE FUNCTION search_modeling_skills(
  query_text TEXT,
  model_type_filter VARCHAR(50) DEFAULT NULL,
  limit_count INTEGER DEFAULT 5
)
RETURNS TABLE (
  id UUID,
  model_type VARCHAR(50),
  title VARCHAR(255),
  description TEXT,
  implementation TEXT,
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
    ms.model_type,
    ms.title,
    ms.description,
    ms.implementation,
    1 - (ms.embedding <=> query_embedding) AS similarity
  FROM modeling_skills ms
  WHERE 
    (model_type_filter IS NULL OR ms.model_type = model_type_filter)
  ORDER BY ms.embedding <=> query_embedding
  LIMIT limit_count;
END;
$$;

-- Insert core modeling skills
INSERT INTO modeling_skills (category, model_type, title, description, implementation, tags) VALUES

-- DCF Skills
('skill', 'DCF', 'Build DCF with real company data',
'When building a DCF, first search for company revenue and growth rate, then project cash flows and discount to present value',
'// First: Search for company data
// Then build model:
grid.write("A1", "DCF Model - [Company Name]")
grid.write("A3", "Current Revenue")
grid.write("B3", [ACTUAL_REVENUE_FROM_SEARCH])
grid.write("A4", "Growth Rate")
grid.write("B4", [ACTUAL_GROWTH_FROM_SEARCH])
grid.write("A5", "Discount Rate")
grid.write("B5", 0.12)
grid.write("A7", "Year 1")
grid.formula("B7", "=B3*(1+B4)")
grid.write("A8", "Year 2")  
grid.formula("B8", "=B7*(1+B4*0.9)")
grid.write("A10", "NPV")
grid.formula("B10", "=NPV(B5,B7:B9)")',
ARRAY['dcf', 'valuation', 'search', 'data']),

-- SaaS Skills
('skill', 'SaaS', 'SaaS metrics dashboard',
'Build comprehensive SaaS metrics including MRR, ARR, churn, CAC, LTV',
'grid.write("A1", "SaaS Metrics")
grid.write("A3", "MRR")
grid.write("B3", [SEARCH_FOR_MRR])
grid.write("A4", "Monthly Churn")
grid.write("B4", 0.02)
grid.write("A5", "Monthly Growth")
grid.write("B5", 0.08)
grid.write("A6", "Net Growth")
grid.formula("B6", "=B5-B4")
grid.write("A8", "ARR")
grid.formula("B8", "=B3*12")
grid.write("A9", "Annual Churn")
grid.formula("B9", "=1-POWER(1-B4,12)")
grid.format("B3", "currency")
grid.format("B8", "currency")',
ARRAY['saas', 'mrr', 'arr', 'metrics']),

-- Comparison Skills
('skill', 'Comparison', 'Compare multiple companies',
'Create side-by-side comparison of companies with key metrics',
'grid.write("A1", "Company Comparison")
grid.write("A3", "Metric")
grid.write("B3", "[Company 1]")
grid.write("C3", "[Company 2]")
grid.write("A4", "Revenue")
grid.write("B4", [SEARCH_COMPANY1_REVENUE])
grid.write("C4", [SEARCH_COMPANY2_REVENUE])
grid.write("A5", "Growth")
grid.write("B5", [SEARCH_COMPANY1_GROWTH])
grid.write("C5", [SEARCH_COMPANY2_GROWTH])
grid.write("A6", "Valuation")
grid.write("B6", [SEARCH_COMPANY1_VALUATION])
grid.write("C6", [SEARCH_COMPANY2_VALUATION])
grid.write("A7", "Rev Multiple")
grid.formula("B7", "=B6/B4")
grid.formula("C7", "=C6/C4")',
ARRAY['comparison', 'comps', 'analysis']),

-- Valuation Skills
('skill', 'Valuation', 'Multiple-based valuation',
'Value company using revenue and EBITDA multiples from comparables',
'grid.write("A1", "Valuation Analysis")
grid.write("A3", "Company Revenue")
grid.write("B3", [SEARCH_REVENUE])
grid.write("A4", "Sector Avg Multiple")
grid.write("B4", 6)
grid.write("A5", "Implied Valuation")
grid.formula("B5", "=B3*B4")
grid.write("A7", "Comparable Multiples")
grid.write("A8", "Company A")
grid.write("B8", 5.5)
grid.write("A9", "Company B")
grid.write("B9", 6.8)
grid.write("A10", "Median")
grid.formula("B10", "=MEDIAN(B8:B9)")',
ARRAY['valuation', 'multiples']),

-- P&L Skills
('skill', 'P&L', 'P&L statement structure',
'Build a proper P&L with revenue, COGS, opex, EBITDA',
'grid.write("A1", "P&L Statement")
grid.write("A3", "Revenue")
grid.write("B3", [SEARCH_REVENUE])
grid.write("A4", "COGS")
grid.formula("B4", "=B3*0.3")
grid.write("A5", "Gross Profit")
grid.formula("B5", "=B3-B4")
grid.write("A6", "Gross Margin %")
grid.formula("B6", "=B5/B3")
grid.write("A8", "Operating Expenses")
grid.formula("B8", "=B3*0.4")
grid.write("A9", "EBITDA")
grid.formula("B9", "=B5-B8")
grid.write("A10", "EBITDA Margin %")
grid.formula("B10", "=B9/B3")
grid.format("B6", "percentage")
grid.format("B10", "percentage")',
ARRAY['p&l', 'income', 'ebitda']),

-- CapTable Skills
('skill', 'CapTable', 'Cap table with dilution',
'Build cap table showing ownership and dilution across rounds',
'grid.write("A1", "Cap Table")
grid.write("A3", "Shareholder")
grid.write("B3", "Shares")
grid.write("C3", "Ownership %")
grid.write("A4", "Founders")
grid.write("B4", 1000000)
grid.write("A5", "Series A")
grid.write("B5", 250000)
grid.write("A6", "Series B")
grid.write("B6", 200000)
grid.write("A7", "Option Pool")
grid.write("B7", 150000)
grid.write("A8", "Total")
grid.formula("B8", "=SUM(B4:B7)")
grid.formula("C4", "=B4/$B$8")
grid.formula("C5", "=B5/$B$8")
grid.formula("C6", "=B6/$B$8")
grid.formula("C7", "=B7/$B$8")
grid.format("C4:C7", "percentage")',
ARRAY['captable', 'equity', 'dilution']),

-- Waterfall Skills
('skill', 'Waterfall', 'Exit waterfall analysis',
'Calculate distribution waterfall with liquidation preferences',
'grid.write("A1", "Exit Waterfall")
grid.write("A3", "Exit Value")
grid.write("B3", 100000000)
grid.write("A5", "Series B Pref (2x)")
grid.write("B5", 20000000)
grid.write("C5", 2)
grid.formula("D5", "=MIN(B3,B5*C5)")
grid.write("A6", "Series A Pref (1x)")
grid.write("B6", 10000000)
grid.write("C6", 1)
grid.formula("D6", "=MIN(B3-D5,B6*C6)")
grid.write("A7", "Remaining for Common")
grid.formula("D7", "=B3-D5-D6")
grid.write("A9", "Common Distribution")
grid.formula("B9", "=D7*0.6")
grid.write("A10", "Founder Payout")
grid.formula("B10", "=B9")',
ARRAY['waterfall', 'exit', 'liquidation']),

-- Formula Skills
('skill', 'General', 'Essential financial formulas',
'Core formulas every model needs: NPV, IRR, CAGR, MOIC',
'// NPV for cash flows in B2:B6, discount rate in B10
grid.formula("B11", "=NPV(B10, B2:B6)")
// IRR for cash flows
grid.formula("B12", "=IRR(B2:B6)")
// CAGR calculation
grid.formula("B13", "=CAGR(B2, B6, 5)")
// MOIC (exit/entry)
grid.formula("B14", "=MOIC(B6, B2)")
// Payment calculation
grid.formula("B15", "=PMT(0.08/12, 360, 500000)")',
ARRAY['formulas', 'npv', 'irr', 'cagr']),

-- Data Integration Skills
('skill', 'General', 'Search and integrate real data',
'Always search for real company data before building models',
'// Step 1: Detect company name from prompt
// Step 2: Search database for company data
// Step 3: Search web for latest updates
// Step 4: Combine data sources
// Step 5: Use actual values in model
grid.write("A1", "[Company] Analysis")
grid.write("A2", "Source: Database + Web Search")
grid.write("A3", "Revenue")
grid.write("B3", [ACTUAL_VALUE_FROM_SEARCH])',
ARRAY['search', 'data', 'integration']);

-- Update embeddings
UPDATE modeling_skills
SET embedding = generate_embeddings(title || ' ' || description || ' ' || COALESCE(array_to_string(tags, ' '), ''))
WHERE embedding IS NULL;