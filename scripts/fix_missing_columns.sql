-- Fix missing columns in companies table
-- Run this to add missing columns for the unified brain API

-- Add last_round_date column if it doesn't exist
ALTER TABLE companies 
ADD COLUMN IF NOT EXISTS last_round_date DATE;

-- Add TAM columns for better tracking
ALTER TABLE companies 
ADD COLUMN IF NOT EXISTS tam_numeric BIGINT;

ALTER TABLE companies 
ADD COLUMN IF NOT EXISTS tam_description TEXT;

ALTER TABLE companies 
ADD COLUMN IF NOT EXISTS tam_citation TEXT;

-- Add dilution tracking columns
ALTER TABLE companies 
ADD COLUMN IF NOT EXISTS typical_dilution DECIMAL(5,4);

ALTER TABLE companies 
ADD COLUMN IF NOT EXISTS cost_of_capital DECIMAL(5,4);

-- Add business model citation
ALTER TABLE companies 
ADD COLUMN IF NOT EXISTS business_model_citation TEXT;

-- Create index for faster queries
CREATE INDEX IF NOT EXISTS idx_companies_last_round_date ON companies(last_round_date);
CREATE INDEX IF NOT EXISTS idx_companies_tam_numeric ON companies(tam_numeric);

-- Update any NULL last_round_date with funding_rounds data
UPDATE companies 
SET last_round_date = (funding_rounds->-1->>'date')::DATE
WHERE last_round_date IS NULL 
  AND funding_rounds IS NOT NULL 
  AND jsonb_array_length(funding_rounds) > 0;

-- Add comments for documentation
COMMENT ON COLUMN companies.tam_numeric IS 'TAM in dollars (e.g., 50000000000 for $50B market)';
COMMENT ON COLUMN companies.tam_description IS 'Descriptive text about the market size';
COMMENT ON COLUMN companies.tam_citation IS 'Source/citation for TAM data';
COMMENT ON COLUMN companies.typical_dilution IS 'Typical dilution per round for this stage/sector';
COMMENT ON COLUMN companies.cost_of_capital IS 'Adjusted cost of capital based on company quality';
COMMENT ON COLUMN companies.business_model_citation IS 'Source for business model classification';