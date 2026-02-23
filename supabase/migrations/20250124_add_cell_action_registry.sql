-- Migration: Add cell_action_registry and cell_action_presets tables
-- Enables dynamic service registration of formulas, workflows, and document actions
-- Actions are mode-aware and can be filtered by matrix mode (portfolio/query/custom/lp)

-- Cell Action Registry: Stores all available actions that services can register
CREATE TABLE IF NOT EXISTS cell_action_registry (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  action_id TEXT UNIQUE NOT NULL, -- e.g., 'valuation_engine.pwerm', 'financial.irr', 'revenue_projection.build'
  name TEXT NOT NULL,
  description TEXT,
  category TEXT NOT NULL, -- 'formula', 'workflow', 'document'
  service_name TEXT NOT NULL, -- 'valuation_engine', 'financial_tools', 'revenue_projection_service', etc.
  service_type TEXT NOT NULL, -- 'service', 'crud', 'agentic'
  api_endpoint TEXT,
  execution_type TEXT NOT NULL, -- 'formula', 'workflow', 'document'
  required_inputs JSONB, -- Schema for required inputs (e.g., {"cash_flows": "array", "discount_rate": "number"})
  output_type TEXT, -- 'number', 'string', 'array', 'chart', 'time_series', 'object'
  mode_availability TEXT[], -- ['portfolio', 'query', 'custom', 'lp'] - which modes this action is available in
  column_compatibility TEXT[], -- Column types this action works with (e.g., ['number', 'currency'])
  config JSONB, -- Action-specific configuration
  is_active BOOLEAN DEFAULT true,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes for fast lookups
CREATE INDEX IF NOT EXISTS idx_cell_action_registry_category ON cell_action_registry(category);
CREATE INDEX IF NOT EXISTS idx_cell_action_registry_service ON cell_action_registry(service_name);
CREATE INDEX IF NOT EXISTS idx_cell_action_registry_mode ON cell_action_registry USING GIN(mode_availability);
CREATE INDEX IF NOT EXISTS idx_cell_action_registry_active ON cell_action_registry(is_active) WHERE is_active = true;
CREATE INDEX IF NOT EXISTS idx_cell_action_registry_execution_type ON cell_action_registry(execution_type);

-- Cell Action Presets: Pre-configured action sequences for common scenarios
CREATE TABLE IF NOT EXISTS cell_action_presets (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  preset_id TEXT UNIQUE NOT NULL, -- 'quick_valuation', 'revenue_forecast', 'portfolio_nav'
  name TEXT NOT NULL,
  description TEXT,
  mode TEXT, -- Which mode this preset is for (NULL = all modes)
  action_ids TEXT[] NOT NULL, -- Array of action IDs to execute (references cell_action_registry.action_id)
  execution_order JSONB, -- Order and dependencies (e.g., {"sequence": ["action1", "action2"], "parallel": ["action3", "action4"]})
  config JSONB, -- Preset-specific configuration
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes for presets
CREATE INDEX IF NOT EXISTS idx_cell_action_presets_mode ON cell_action_presets(mode);
CREATE INDEX IF NOT EXISTS idx_cell_action_presets_preset_id ON cell_action_presets(preset_id);

-- Enable RLS (Row Level Security)
ALTER TABLE cell_action_registry ENABLE ROW LEVEL SECURITY;
ALTER TABLE cell_action_presets ENABLE ROW LEVEL SECURITY;

-- Policies: Allow all authenticated users to read actions (they're service-registered, not user-specific)
CREATE POLICY "Users can view cell action registry"
  ON cell_action_registry
  FOR SELECT
  USING (true); -- Actions are public, services register them

CREATE POLICY "Services can insert actions"
  ON cell_action_registry
  FOR INSERT
  WITH CHECK (true); -- Services register on startup

CREATE POLICY "Services can update actions"
  ON cell_action_registry
  FOR UPDATE
  USING (true);

-- Policies for presets (can be user/fund-specific in future)
CREATE POLICY "Users can view cell action presets"
  ON cell_action_presets
  FOR SELECT
  USING (true);

CREATE POLICY "Users can insert cell action presets"
  ON cell_action_presets
  FOR INSERT
  WITH CHECK (true);

CREATE POLICY "Users can update cell action presets"
  ON cell_action_presets
  FOR UPDATE
  USING (true);

-- Comments
COMMENT ON TABLE cell_action_registry IS 'Dynamic registry of available cell actions (formulas, workflows, document actions) registered by backend services. Actions are mode-aware and filterable.';
COMMENT ON COLUMN cell_action_registry.action_id IS 'Unique action identifier (e.g., valuation_engine.pwerm, financial.irr)';
COMMENT ON COLUMN cell_action_registry.mode_availability IS 'Array of matrix modes where this action is available: portfolio, query, custom, lp';
COMMENT ON COLUMN cell_action_registry.column_compatibility IS 'Array of column types this action works with (e.g., number, currency, percentage)';
COMMENT ON COLUMN cell_action_registry.required_inputs IS 'JSON schema defining required inputs for this action';
COMMENT ON COLUMN cell_action_registry.config IS 'Action-specific configuration (e.g., default parameters, validation rules)';

COMMENT ON TABLE cell_action_presets IS 'Pre-configured action sequences for common scenarios (e.g., quick valuation, revenue forecast)';
COMMENT ON COLUMN cell_action_presets.action_ids IS 'Array of action IDs from cell_action_registry to execute';
COMMENT ON COLUMN cell_action_presets.execution_order IS 'JSON defining execution order and dependencies (sequence vs parallel)';
