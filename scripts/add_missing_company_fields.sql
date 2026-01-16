-- Add missing extracted fields to companies table
-- These fields are calculated/extracted but were not exposed in schemas/types

-- Add category column (e.g., "ai_first", "saas", "marketplace", etc.)
ALTER TABLE companies 
ADD COLUMN IF NOT EXISTS category TEXT;

-- Add ai_first boolean flag (indicates if company is AI-first)
ALTER TABLE companies 
ADD COLUMN IF NOT EXISTS ai_first BOOLEAN;

-- Verify gross_margin column exists (should already be in schema)
-- If not, add it
ALTER TABLE companies 
ADD COLUMN IF NOT EXISTS gross_margin DECIMAL(5,4);

-- Verify business_model column exists (should already be in CompanyBase schema)
-- If not, add it
ALTER TABLE companies 
ADD COLUMN IF NOT EXISTS business_model TEXT;

-- Create indexes for faster queries
CREATE INDEX IF NOT EXISTS idx_companies_category ON companies(category);
CREATE INDEX IF NOT EXISTS idx_companies_ai_first ON companies(ai_first);
CREATE INDEX IF NOT EXISTS idx_companies_business_model ON companies(business_model);

-- Add comments for documentation
COMMENT ON COLUMN companies.category IS 'Company category: ai_first, saas, marketplace, services, etc.';
COMMENT ON COLUMN companies.ai_first IS 'Boolean flag indicating if company is AI-first';
COMMENT ON COLUMN companies.gross_margin IS 'Gross margin as decimal (e.g., 0.75 for 75%)';
COMMENT ON COLUMN companies.business_model IS 'Description of business model';

