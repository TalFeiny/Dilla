-- Add company_id and fund_id columns to processed_documents table for portfolio ledger time-series tracking
-- This enables linking documents to companies and funds for revenue tracking over time

-- Add company_id column with foreign key reference
ALTER TABLE processed_documents 
ADD COLUMN IF NOT EXISTS company_id UUID REFERENCES companies(id) ON DELETE SET NULL;

-- Add fund_id column with foreign key reference (can be derived from company, but storing for performance)
ALTER TABLE processed_documents 
ADD COLUMN IF NOT EXISTS fund_id UUID REFERENCES funds(id) ON DELETE SET NULL;

-- Create indexes for efficient queries
CREATE INDEX IF NOT EXISTS idx_processed_documents_company_id 
ON processed_documents (company_id) 
WHERE company_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_processed_documents_fund_id 
ON processed_documents (fund_id) 
WHERE fund_id IS NOT NULL;

-- Composite index for common query pattern (fund + company + date)
CREATE INDEX IF NOT EXISTS idx_processed_documents_fund_company_date 
ON processed_documents (fund_id, company_id, processed_at DESC) 
WHERE fund_id IS NOT NULL AND company_id IS NOT NULL AND status = 'completed';

-- Add comment for documentation
COMMENT ON COLUMN processed_documents.company_id IS 'Links document to a portfolio company for revenue time-series tracking';
COMMENT ON COLUMN processed_documents.fund_id IS 'Links document to a fund for portfolio-level queries (can be derived from company)';
