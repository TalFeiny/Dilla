-- Migration: Add FPA (Financial Planning & Analysis) tables
-- Supports natural language FP&A queries, models, and ephemeral graphs

-- FPA Models table
CREATE TABLE IF NOT EXISTS fpa_models (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name TEXT NOT NULL,
  model_type TEXT NOT NULL, -- 'scenario' | 'forecast' | 'valuation' | 'impact' | 'sensitivity' | 'comparison' | 'regression' | 'growth_decay'
  model_definition JSONB NOT NULL DEFAULT '{}', -- Parsed query structure
  formulas JSONB NOT NULL DEFAULT '{}', -- { step_id: formula_string }
  assumptions JSONB NOT NULL DEFAULT '{}', -- { step_id: assumptions_dict }
  created_by TEXT, -- User ID or email
  fund_id UUID REFERENCES funds(id) ON DELETE CASCADE,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- FPA Model Versions table
CREATE TABLE IF NOT EXISTS fpa_model_versions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  model_id UUID REFERENCES fpa_models(id) ON DELETE CASCADE,
  version_number INTEGER NOT NULL,
  model_definition JSONB NOT NULL DEFAULT '{}',
  changed_by TEXT, -- User ID or email
  change_description TEXT,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  UNIQUE(model_id, version_number)
);

-- FPA Queries table (for query history)
CREATE TABLE IF NOT EXISTS fpa_queries (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  query_text TEXT NOT NULL,
  parsed_query JSONB NOT NULL DEFAULT '{}',
  workflow JSONB NOT NULL DEFAULT '[]',
  results JSONB NOT NULL DEFAULT '{}',
  execution_time INTEGER, -- milliseconds
  created_by TEXT, -- User ID or email
  fund_id UUID REFERENCES funds(id) ON DELETE CASCADE,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Ephemeral Graphs table (optional - for temporary chart configs)
CREATE TABLE IF NOT EXISTS ephemeral_graphs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  session_id TEXT NOT NULL,
  graph_type TEXT NOT NULL, -- 'forecast_curve' | 'regression' | 'tornado' | 'sensitivity' | etc.
  graph_config JSONB NOT NULL DEFAULT '{}', -- Chart configuration
  data JSONB NOT NULL DEFAULT '{}', -- Chart data
  expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes for fast lookups
CREATE INDEX IF NOT EXISTS idx_fpa_models_fund_id ON fpa_models(fund_id);
CREATE INDEX IF NOT EXISTS idx_fpa_models_created_by ON fpa_models(created_by);
CREATE INDEX IF NOT EXISTS idx_fpa_models_created_at ON fpa_models(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_fpa_model_versions_model_id ON fpa_model_versions(model_id);
CREATE INDEX IF NOT EXISTS idx_fpa_queries_fund_id ON fpa_queries(fund_id);
CREATE INDEX IF NOT EXISTS idx_fpa_queries_created_by ON fpa_queries(created_by);
CREATE INDEX IF NOT EXISTS idx_fpa_queries_created_at ON fpa_queries(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_ephemeral_graphs_session_id ON ephemeral_graphs(session_id);
CREATE INDEX IF NOT EXISTS idx_ephemeral_graphs_expires_at ON ephemeral_graphs(expires_at);

-- GIN indexes for JSONB queries
CREATE INDEX IF NOT EXISTS idx_fpa_models_model_definition ON fpa_models USING GIN(model_definition);
CREATE INDEX IF NOT EXISTS idx_fpa_models_formulas ON fpa_models USING GIN(formulas);
CREATE INDEX IF NOT EXISTS idx_fpa_models_assumptions ON fpa_models USING GIN(assumptions);
CREATE INDEX IF NOT EXISTS idx_fpa_queries_parsed_query ON fpa_queries USING GIN(parsed_query);
CREATE INDEX IF NOT EXISTS idx_fpa_queries_workflow ON fpa_queries USING GIN(workflow);
CREATE INDEX IF NOT EXISTS idx_fpa_queries_results ON fpa_queries USING GIN(results);

-- Functions to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_fpa_model_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Triggers to auto-update updated_at
CREATE TRIGGER fpa_models_updated_at
  BEFORE UPDATE ON fpa_models
  FOR EACH ROW
  EXECUTE FUNCTION update_fpa_model_updated_at();

-- Enable RLS (Row Level Security)
ALTER TABLE fpa_models ENABLE ROW LEVEL SECURITY;
ALTER TABLE fpa_model_versions ENABLE ROW LEVEL SECURITY;
ALTER TABLE fpa_queries ENABLE ROW LEVEL SECURITY;
ALTER TABLE ephemeral_graphs ENABLE ROW LEVEL SECURITY;

-- Policies: Users can view/create/update their own models and queries
CREATE POLICY "Users can view FPA models for their funds"
  ON fpa_models
  FOR SELECT
  USING (true); -- TODO: Add proper auth check

CREATE POLICY "Users can create FPA models for their funds"
  ON fpa_models
  FOR INSERT
  WITH CHECK (true); -- TODO: Add proper auth check

CREATE POLICY "Users can update FPA models for their funds"
  ON fpa_models
  FOR UPDATE
  USING (true); -- TODO: Add proper auth check

CREATE POLICY "Users can view FPA model versions for their funds"
  ON fpa_model_versions
  FOR SELECT
  USING (true); -- TODO: Add proper auth check

CREATE POLICY "Users can create FPA model versions for their funds"
  ON fpa_model_versions
  FOR INSERT
  WITH CHECK (true); -- TODO: Add proper auth check

CREATE POLICY "Users can view FPA queries for their funds"
  ON fpa_queries
  FOR SELECT
  USING (true); -- TODO: Add proper auth check

CREATE POLICY "Users can create FPA queries for their funds"
  ON fpa_queries
  FOR INSERT
  WITH CHECK (true); -- TODO: Add proper auth check

CREATE POLICY "Users can view ephemeral graphs for their sessions"
  ON ephemeral_graphs
  FOR SELECT
  USING (true); -- TODO: Add proper auth check

CREATE POLICY "Users can create ephemeral graphs for their sessions"
  ON ephemeral_graphs
  FOR INSERT
  WITH CHECK (true); -- TODO: Add proper auth check

-- Comments
COMMENT ON TABLE fpa_models IS 'Stores FPA models with formulas and assumptions';
COMMENT ON TABLE fpa_model_versions IS 'Version history for FPA models';
COMMENT ON TABLE fpa_queries IS 'History of FPA queries and their results';
COMMENT ON TABLE ephemeral_graphs IS 'Temporary chart configurations (optional, can be client-side only)';
