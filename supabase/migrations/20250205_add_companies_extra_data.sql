-- Flexible columns: store arbitrary CSV/import fields per company
ALTER TABLE companies
ADD COLUMN IF NOT EXISTS extra_data JSONB DEFAULT '{}';

CREATE INDEX IF NOT EXISTS idx_companies_extra_data_gin ON companies USING GIN (extra_data) WHERE extra_data IS NOT NULL AND extra_data != '{}';

COMMENT ON COLUMN companies.extra_data IS 'Arbitrary key-value data from CSV import or custom columns (e.g. round, lead, description).';
