-- Migration: Add batch_valuation_jobs table for resilient batch processing
-- Tracks batch valuation jobs with progress, results, and error handling

CREATE TABLE IF NOT EXISTS batch_valuation_jobs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  fund_id UUID REFERENCES funds(id) ON DELETE CASCADE,
  created_by TEXT, -- User ID or email
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  
  -- Job configuration
  valuation_method TEXT NOT NULL, -- 'dcf', 'comparables', 'pwerm', 'auto'
  company_ids UUID[] NOT NULL, -- Array of company IDs to process
  total_companies INTEGER NOT NULL,
  
  -- Job status
  status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'queued', 'processing', 'completed', 'failed', 'cancelled')),
  
  -- Progress tracking
  completed_count INTEGER DEFAULT 0,
  failed_count INTEGER DEFAULT 0,
  processing_count INTEGER DEFAULT 0,
  
  -- Results (stored incrementally as companies complete)
  results JSONB DEFAULT '{}', -- { companyId: { valuation, nav, method, error, completed_at } }
  
  -- Error handling
  errors JSONB DEFAULT '[]', -- Array of { companyId, error, retry_count, timestamp }
  retry_count INTEGER DEFAULT 0,
  max_retries INTEGER DEFAULT 3,
  
  -- Metadata
  metadata JSONB DEFAULT '{}', -- Additional metadata (filters applied, etc.)
  
  -- Timing
  started_at TIMESTAMP WITH TIME ZONE,
  completed_at TIMESTAMP WITH TIME ZONE,
  estimated_completion_at TIMESTAMP WITH TIME ZONE
);

-- Indexes for fast lookups
CREATE INDEX IF NOT EXISTS idx_batch_valuation_jobs_fund_id ON batch_valuation_jobs(fund_id);
CREATE INDEX IF NOT EXISTS idx_batch_valuation_jobs_status ON batch_valuation_jobs(status);
CREATE INDEX IF NOT EXISTS idx_batch_valuation_jobs_created_at ON batch_valuation_jobs(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_batch_valuation_jobs_company_ids ON batch_valuation_jobs USING GIN(company_ids);

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_batch_valuation_job_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger to auto-update updated_at
CREATE TRIGGER batch_valuation_jobs_updated_at
  BEFORE UPDATE ON batch_valuation_jobs
  FOR EACH ROW
  EXECUTE FUNCTION update_batch_valuation_job_updated_at();

-- Enable RLS (Row Level Security)
ALTER TABLE batch_valuation_jobs ENABLE ROW LEVEL SECURITY;

-- Policy: Users can view jobs for their funds
CREATE POLICY "Users can view batch valuation jobs for their funds"
  ON batch_valuation_jobs
  FOR SELECT
  USING (true); -- TODO: Add proper auth check

-- Policy: Users can create jobs for their funds
CREATE POLICY "Users can create batch valuation jobs for their funds"
  ON batch_valuation_jobs
  FOR INSERT
  WITH CHECK (true); -- TODO: Add proper auth check

-- Policy: Users can update jobs for their funds
CREATE POLICY "Users can update batch valuation jobs for their funds"
  ON batch_valuation_jobs
  FOR UPDATE
  USING (true); -- TODO: Add proper auth check

-- Comments
COMMENT ON TABLE batch_valuation_jobs IS 'Tracks batch valuation jobs with progress, results, and error handling';
COMMENT ON COLUMN batch_valuation_jobs.results IS 'Incremental results: { companyId: { valuation, nav, method, error, completed_at } }';
COMMENT ON COLUMN batch_valuation_jobs.errors IS 'Array of errors: [{ companyId, error, retry_count, timestamp }]';
COMMENT ON COLUMN batch_valuation_jobs.company_ids IS 'Array of company UUIDs to process in this batch';
