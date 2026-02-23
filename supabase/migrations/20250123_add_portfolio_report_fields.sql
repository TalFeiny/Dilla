-- Add comprehensive portfolio report fields to companies table
-- This migration adds all fields needed for a complete portfolio report view
-- matching the benchmark image requirements

-- Add cash in bank field
ALTER TABLE companies 
ADD COLUMN IF NOT EXISTS cash_in_bank_usd NUMERIC;

-- Add investment lead (can be user_id or name)
ALTER TABLE companies 
ADD COLUMN IF NOT EXISTS investment_lead TEXT;

-- Add last contacted date (if not exists)
ALTER TABLE companies 
ADD COLUMN IF NOT EXISTS last_contacted_date TIMESTAMP WITH TIME ZONE;

-- Add field update timestamps for tracking when each metric was last updated
ALTER TABLE companies 
ADD COLUMN IF NOT EXISTS cash_updated_at TIMESTAMP WITH TIME ZONE;

ALTER TABLE companies 
ADD COLUMN IF NOT EXISTS burn_rate_updated_at TIMESTAMP WITH TIME ZONE;

ALTER TABLE companies 
ADD COLUMN IF NOT EXISTS runway_updated_at TIMESTAMP WITH TIME ZONE;

ALTER TABLE companies 
ADD COLUMN IF NOT EXISTS revenue_updated_at TIMESTAMP WITH TIME ZONE;

ALTER TABLE companies 
ADD COLUMN IF NOT EXISTS gross_margin_updated_at TIMESTAMP WITH TIME ZONE;

-- Ensure burn_rate_monthly_usd exists (should already exist)
ALTER TABLE companies 
ADD COLUMN IF NOT EXISTS burn_rate_monthly_usd NUMERIC;

-- Ensure runway_months exists (should already exist)
ALTER TABLE companies 
ADD COLUMN IF NOT EXISTS runway_months INTEGER;

-- Ensure gross_margin exists (should already exist)
ALTER TABLE companies 
ADD COLUMN IF NOT EXISTS gross_margin DECIMAL(5,4);

-- Create indexes for efficient queries
CREATE INDEX IF NOT EXISTS idx_companies_fund_id_cash ON companies(fund_id, cash_in_bank_usd) WHERE fund_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_companies_investment_lead ON companies(investment_lead) WHERE investment_lead IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_companies_last_contacted ON companies(last_contacted_date) WHERE last_contacted_date IS NOT NULL;

-- Add comments for documentation
COMMENT ON COLUMN companies.cash_in_bank_usd IS 'Current cash balance in USD';
COMMENT ON COLUMN companies.investment_lead IS 'Name or ID of the investment lead/portfolio manager';
COMMENT ON COLUMN companies.last_contacted_date IS 'Date of last contact with the company';
COMMENT ON COLUMN companies.cash_updated_at IS 'Timestamp when cash_in_bank_usd was last updated';
COMMENT ON COLUMN companies.burn_rate_updated_at IS 'Timestamp when burn_rate_monthly_usd was last updated';
COMMENT ON COLUMN companies.runway_updated_at IS 'Timestamp when runway_months was last updated';
COMMENT ON COLUMN companies.revenue_updated_at IS 'Timestamp when current_arr_usd or revenue was last updated';
COMMENT ON COLUMN companies.gross_margin_updated_at IS 'Timestamp when gross_margin was last updated';
