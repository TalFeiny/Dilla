-- Add GIN indexes on extracted_data JSONB field for fast matrix queries
-- This enables efficient querying of structured document data without complex RAG infrastructure

-- Index on extracted_data for general JSONB queries
CREATE INDEX IF NOT EXISTS idx_processed_documents_extracted_data 
ON processed_documents USING GIN (extracted_data);

-- Index on document_type for filtering by document type
CREATE INDEX IF NOT EXISTS idx_processed_documents_document_type 
ON processed_documents (document_type) 
WHERE document_type IS NOT NULL;

-- Index on status for filtering completed documents
CREATE INDEX IF NOT EXISTS idx_processed_documents_status 
ON processed_documents (status) 
WHERE status = 'completed';

-- Composite index for common query patterns (document_type + status)
CREATE INDEX IF NOT EXISTS idx_processed_documents_type_status 
ON processed_documents (document_type, status) 
WHERE status = 'completed';

-- Index on processed_at for time-based queries
CREATE INDEX IF NOT EXISTS idx_processed_documents_processed_at 
ON processed_documents (processed_at DESC) 
WHERE processed_at IS NOT NULL;

-- Add indexes for portfolio relationships if they exist
-- These will be created if company_id and fund_id columns exist in processed_documents
DO $$
BEGIN
    -- Check if company_id column exists and create index
    IF EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'processed_documents' AND column_name = 'company_id'
    ) THEN
        CREATE INDEX IF NOT EXISTS idx_processed_documents_company_id 
        ON processed_documents (company_id) 
        WHERE company_id IS NOT NULL;
    END IF;

    -- Check if fund_id column exists and create index
    IF EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'processed_documents' AND column_name = 'fund_id'
    ) THEN
        CREATE INDEX IF NOT EXISTS idx_processed_documents_fund_id 
        ON processed_documents (fund_id) 
        WHERE fund_id IS NOT NULL;
    END IF;
END $$;

-- Create function to extract metrics from extracted_data for common queries
CREATE OR REPLACE FUNCTION extract_metric_from_documents(
    metric_path text[],
    document_types text[] DEFAULT NULL,
    date_from timestamp with time zone DEFAULT NULL,
    date_to timestamp with time zone DEFAULT NULL
)
RETURNS TABLE (
    document_id uuid,
    company_name text,
    metric_value jsonb,
    document_type text,
    processed_at timestamp with time zone,
    extracted_data jsonb
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        pd.id as document_id,
        pd.extracted_data->>'company' as company_name,
        jsonb_extract_path(pd.extracted_data, VARIADIC metric_path) as metric_value,
        pd.document_type,
        pd.processed_at,
        pd.extracted_data
    FROM processed_documents pd
    WHERE 
        pd.status = 'completed'
        AND pd.extracted_data IS NOT NULL
        AND jsonb_extract_path(pd.extracted_data, VARIADIC metric_path) IS NOT NULL
        AND (document_types IS NULL OR pd.document_type = ANY(document_types))
        AND (date_from IS NULL OR pd.processed_at >= date_from)
        AND (date_to IS NULL OR pd.processed_at <= date_to);
END;
$$ LANGUAGE plpgsql;
