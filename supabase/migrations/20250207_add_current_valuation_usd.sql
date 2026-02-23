-- Add current_valuation_usd to companies table
-- Stores the latest valuation (USD) when the company has been valued; NULL when not yet valued
ALTER TABLE companies
ADD COLUMN IF NOT EXISTS current_valuation_usd NUMERIC;

-- Add last_valuation_usd if referenced elsewhere (e.g. scenarios API fallback)
ALTER TABLE companies
ADD COLUMN IF NOT EXISTS last_valuation_usd NUMERIC;

-- Add revenue growth columns if referenced by suggestions/matrix
ALTER TABLE companies
ADD COLUMN IF NOT EXISTS revenue_growth_monthly_pct NUMERIC;

ALTER TABLE companies
ADD COLUMN IF NOT EXISTS revenue_growth_annual_pct NUMERIC;

COMMENT ON COLUMN companies.current_valuation_usd IS 'Current/latest valuation in USD; NULL when company has not yet been valued';
COMMENT ON COLUMN companies.last_valuation_usd IS 'Previous valuation in USD; used as fallback when current_valuation_usd not set';
COMMENT ON COLUMN companies.revenue_growth_monthly_pct IS 'Monthly revenue growth rate as decimal (e.g. 0.05 for 5%)';
COMMENT ON COLUMN companies.revenue_growth_annual_pct IS 'Annual revenue growth rate as decimal (e.g. 0.60 for 60%)';
