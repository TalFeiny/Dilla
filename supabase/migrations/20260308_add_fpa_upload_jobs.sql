-- Track CSV/time-series actuals upload lifecycle.
-- Mirrors processed_documents state pattern so uploads are never a black box.

CREATE TABLE IF NOT EXISTS fpa_upload_jobs (
  id uuid DEFAULT gen_random_uuid() PRIMARY KEY,
  company_id text NOT NULL,
  fund_id text DEFAULT NULL,

  -- Source info
  source text NOT NULL DEFAULT 'csv_upload',
    -- 'csv_upload' | 'agent_tool' | 'document_extraction' | 'xero_sync'
  file_name text DEFAULT NULL,
  file_size bigint DEFAULT NULL,

  -- State machine: pending → processing → completed | failed
  status text NOT NULL DEFAULT 'pending',
  step text DEFAULT NULL,
    -- 'validating' | 'parsing_headers' | 'detecting_categories'
    -- | 'extracting_amounts' | 'upserting' | 'completed' | 'failed'
  message text DEFAULT NULL,
  error text DEFAULT NULL,

  -- Results (populated on success)
  rows_ingested int DEFAULT 0,
  periods_found text[] DEFAULT '{}',
  categories_found text[] DEFAULT '{}',
  mapped_categories jsonb DEFAULT '[]',
  unmapped_labels text[] DEFAULT '{}',
  warnings text[] DEFAULT '{}',
  skipped jsonb DEFAULT '{}',

  -- Timestamps
  created_at timestamptz DEFAULT now(),
  started_at timestamptz DEFAULT NULL,
  completed_at timestamptz DEFAULT NULL
);

CREATE INDEX IF NOT EXISTS idx_fpa_upload_jobs_company
  ON fpa_upload_jobs (company_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_fpa_upload_jobs_status
  ON fpa_upload_jobs (status) WHERE status IN ('pending', 'processing');
