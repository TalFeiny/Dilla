-- Migration: Add matrix_columns table for dynamic column persistence
-- Enables human and agent-driven column addition with service wiring

CREATE TABLE IF NOT EXISTS matrix_columns (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  matrix_id TEXT, -- saved matrix identifier (for saved views only)
  column_id TEXT NOT NULL,
  name TEXT NOT NULL,
  type TEXT NOT NULL, -- 'text', 'number', 'currency', 'percentage', 'date', 'boolean', 'formula', 'sparkline'
  service_name TEXT, -- 'valuation_engine', 'pwerm_calculator', 'scenario_analyzer', etc.
  service_type TEXT, -- 'crud', 'agentic', 'service'
  api_endpoint TEXT,
  formula TEXT,
  config JSONB, -- Service-specific configuration
  created_by TEXT, -- 'human' | 'agent' | user_id
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  fund_id UUID REFERENCES funds(id) ON DELETE CASCADE,
  -- Only allow persistence for portfolio mode (fund_id) or saved views (matrix_id)
  -- Query/custom mode columns are ephemeral and not stored
  CONSTRAINT matrix_columns_persistence_check CHECK (
    (matrix_id IS NOT NULL) OR (fund_id IS NOT NULL)
  )
);

-- Indexes for fast lookups
CREATE INDEX IF NOT EXISTS idx_matrix_columns_matrix_id ON matrix_columns(matrix_id) WHERE matrix_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_matrix_columns_fund_id ON matrix_columns(fund_id) WHERE fund_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_matrix_columns_column_id ON matrix_columns(column_id);
CREATE INDEX IF NOT EXISTS idx_matrix_columns_service_name ON matrix_columns(service_name) WHERE service_name IS NOT NULL;

-- Partial unique indexes (PostgreSQL does not allow UNIQUE ... WHERE in CREATE TABLE)
CREATE UNIQUE INDEX IF NOT EXISTS idx_matrix_columns_matrix_column_unique
  ON matrix_columns(matrix_id, column_id) WHERE matrix_id IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS idx_matrix_columns_fund_column_unique
  ON matrix_columns(fund_id, column_id) WHERE fund_id IS NOT NULL;

-- Enable RLS (Row Level Security)
ALTER TABLE matrix_columns ENABLE ROW LEVEL SECURITY;

-- Policy: Users can view columns for their funds
CREATE POLICY "Users can view matrix columns for their funds"
  ON matrix_columns
  FOR SELECT
  USING (
    true -- TODO: Add proper auth check
  );

-- Policy: Users can insert columns for their funds
CREATE POLICY "Users can insert matrix columns for their funds"
  ON matrix_columns
  FOR INSERT
  WITH CHECK (
    true -- TODO: Add proper auth check
  );

-- Policy: Users can update columns for their funds
CREATE POLICY "Users can update matrix columns for their funds"
  ON matrix_columns
  FOR UPDATE
  USING (
    true -- TODO: Add proper auth check
  );

-- Policy: Users can delete columns for their funds
CREATE POLICY "Users can delete matrix columns for their funds"
  ON matrix_columns
  FOR DELETE
  USING (
    true -- TODO: Add proper auth check
  );

-- Comments
COMMENT ON TABLE matrix_columns IS 'Dynamic column configurations for portfolio matrices and saved matrix views. Query/custom mode columns are ephemeral and not stored.';
COMMENT ON COLUMN matrix_columns.matrix_id IS 'Saved matrix view identifier (for saved views only, not ephemeral queries)';
COMMENT ON COLUMN matrix_columns.fund_id IS 'Fund ID for portfolio mode columns (persisted per fund)';
COMMENT ON COLUMN matrix_columns.column_id IS 'Column identifier (e.g., valuation, nav, pwerm_score)';
COMMENT ON COLUMN matrix_columns.service_name IS 'Backend service name (e.g., valuation_engine, pwerm_calculator)';
COMMENT ON COLUMN matrix_columns.service_type IS 'Service type: crud (direct DB), agentic (via unified-brain), service (API endpoint)';
COMMENT ON COLUMN matrix_columns.config IS 'Service-specific configuration (methods, parameters, etc.)';
