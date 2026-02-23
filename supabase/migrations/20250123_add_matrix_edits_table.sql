-- Migration: Add matrix_edits table for audit trail
-- Tracks all manual edits to matrix cells with full audit trail

CREATE TABLE IF NOT EXISTS matrix_edits (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  matrix_id TEXT, -- session or saved matrix identifier (optional)
  company_id UUID REFERENCES companies(id) ON DELETE CASCADE,
  column_id TEXT NOT NULL, -- Column/field that was edited
  old_value JSONB, -- Previous value
  new_value JSONB NOT NULL, -- New value
  edited_by TEXT, -- User ID or email
  edited_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  data_source TEXT DEFAULT 'manual', -- 'manual', 'document', 'api', 'formula'
  source_document_id BIGINT REFERENCES processed_documents(id) ON DELETE SET NULL,
  fund_id UUID REFERENCES funds(id) ON DELETE CASCADE,
  metadata JSONB -- Additional metadata (confidence, citation, etc.)
);

-- Indexes for fast lookups
CREATE INDEX IF NOT EXISTS idx_matrix_edits_company_id ON matrix_edits(company_id);
CREATE INDEX IF NOT EXISTS idx_matrix_edits_fund_id ON matrix_edits(fund_id);
CREATE INDEX IF NOT EXISTS idx_matrix_edits_edited_at ON matrix_edits(edited_at DESC);
CREATE INDEX IF NOT EXISTS idx_matrix_edits_matrix_id ON matrix_edits(matrix_id) WHERE matrix_id IS NOT NULL;

-- Enable RLS (Row Level Security)
ALTER TABLE matrix_edits ENABLE ROW LEVEL SECURITY;

-- Policy: Users can view their own edits and edits for their funds
CREATE POLICY "Users can view matrix edits for their funds"
  ON matrix_edits
  FOR SELECT
  USING (
    -- Allow if user is viewing edits for a fund they have access to
    -- This is a simplified policy - adjust based on your auth system
    true -- TODO: Add proper auth check
  );

-- Policy: Users can insert edits for companies in their funds
CREATE POLICY "Users can insert matrix edits for their funds"
  ON matrix_edits
  FOR INSERT
  WITH CHECK (
    -- Allow if editing a company in a fund they have access to
    true -- TODO: Add proper auth check
  );

-- Comments
COMMENT ON TABLE matrix_edits IS 'Audit trail for all manual edits to matrix cells';
COMMENT ON COLUMN matrix_edits.matrix_id IS 'Optional identifier for saved matrix views';
COMMENT ON COLUMN matrix_edits.column_id IS 'Column/field identifier (e.g., currentArr, burnRate)';
COMMENT ON COLUMN matrix_edits.data_source IS 'Source of the edit: manual, document, api, or formula';
COMMENT ON COLUMN matrix_edits.metadata IS 'Additional metadata like confidence scores, citations, etc.';
