-- Fix performance issues in the database

-- Add missing column for latest valuation (nullable)
ALTER TABLE companies 
ADD COLUMN IF NOT EXISTS latest_valuation_usd DECIMAL(20, 2);

-- Add indexes for common queries to speed up API responses
CREATE INDEX IF NOT EXISTS idx_companies_fund_id ON companies(fund_id) WHERE fund_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_companies_created_at ON companies(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_companies_name ON companies(name);
CREATE INDEX IF NOT EXISTS idx_companies_sector ON companies(sector);

-- Index for funds
CREATE INDEX IF NOT EXISTS idx_funds_created_at ON funds(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_funds_status ON funds(status);

-- Index for limited partners
CREATE INDEX IF NOT EXISTS idx_limited_partners_created_at ON limited_partners(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_limited_partners_name ON limited_partners(name);

-- Composite index for portfolio queries
CREATE INDEX IF NOT EXISTS idx_companies_portfolio ON companies(fund_id, created_at DESC) 
WHERE fund_id IS NOT NULL;

-- Add indexes for documents
CREATE INDEX IF NOT EXISTS idx_documents_created_at ON documents(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_documents_status ON documents(status);
CREATE INDEX IF NOT EXISTS idx_documents_company_id ON documents(company_id) WHERE company_id IS NOT NULL;

-- Analyze tables to update statistics for query planner
ANALYZE companies;
ANALYZE funds;
ANALYZE limited_partners;
ANALYZE documents;