-- Migration: Add World Models tables
-- Supports comprehensive world modeling with qualitative/quantitative factors, relationships, and temporal dynamics

-- World Models table (extends financial models to include full business context)
CREATE TABLE IF NOT EXISTS world_models (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name TEXT NOT NULL,
  model_type TEXT NOT NULL, -- 'company' | 'portfolio' | 'market' | 'competitive' | 'operational' | 'custom'
  model_definition JSONB NOT NULL DEFAULT '{}', -- Full model structure with entities, relationships, factors
  formulas JSONB NOT NULL DEFAULT '{}', -- { factor_id: formula_string }
  assumptions JSONB NOT NULL DEFAULT '{}', -- { factor_id: assumptions_dict }
  relationships JSONB NOT NULL DEFAULT '[]', -- [ { from: entity_id, to: entity_id, type: relationship_type, strength: float } ]
  temporal_dynamics JSONB NOT NULL DEFAULT '{}', -- How factors change over time
  created_by TEXT, -- User ID or email
  fund_id UUID REFERENCES funds(id) ON DELETE CASCADE,
  company_id UUID REFERENCES companies(id) ON DELETE CASCADE,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Model Entities table (companies, markets, competitors, etc. in the world model)
CREATE TABLE IF NOT EXISTS world_model_entities (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  model_id UUID REFERENCES world_models(id) ON DELETE CASCADE,
  entity_type TEXT NOT NULL, -- 'company' | 'market' | 'competitor' | 'investor' | 'regulator' | 'customer_segment'
  entity_id UUID, -- Reference to actual entity (company_id, etc.) if applicable
  entity_name TEXT NOT NULL,
  properties JSONB NOT NULL DEFAULT '{}', -- Entity-specific properties
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Model Factors table (qualitative and quantitative factors)
CREATE TABLE IF NOT EXISTS world_model_factors (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  model_id UUID REFERENCES world_models(id) ON DELETE CASCADE,
  entity_id UUID REFERENCES world_model_entities(id) ON DELETE CASCADE,
  factor_name TEXT NOT NULL,
  factor_type TEXT NOT NULL, -- 'qualitative' | 'quantitative' | 'composite'
  factor_category TEXT, -- 'market' | 'competitive' | 'operational' | 'financial' | 'team' | 'product'
  value_type TEXT NOT NULL, -- 'score' | 'amount' | 'percentage' | 'count' | 'boolean' | 'text'
  current_value JSONB, -- Current value (can be number, string, object)
  source TEXT, -- 'manual' | 'inferred' | 'api' | 'document' | 'formula'
  confidence_score FLOAT DEFAULT 0.5, -- 0-1 confidence in the value
  dependencies JSONB DEFAULT '[]', -- [ factor_id ] - factors this depends on
  formula TEXT, -- Formula to calculate this factor
  assumptions JSONB DEFAULT '{}', -- Assumptions used in calculation
  historical_values JSONB DEFAULT '[]', -- Time series of values
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Model Relationships table (explicit relationships between entities)
CREATE TABLE IF NOT EXISTS world_model_relationships (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  model_id UUID REFERENCES world_models(id) ON DELETE CASCADE,
  from_entity_id UUID REFERENCES world_model_entities(id) ON DELETE CASCADE,
  to_entity_id UUID REFERENCES world_model_entities(id) ON DELETE CASCADE,
  relationship_type TEXT NOT NULL, -- 'competes_with' | 'supplies' | 'invests_in' | 'regulates' | 'serves' | 'partners_with'
  strength FLOAT DEFAULT 1.0, -- 0-1 relationship strength
  properties JSONB DEFAULT '{}', -- Relationship-specific properties
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Qualitative Factor Scores table (detailed scoring for qualitative factors)
CREATE TABLE IF NOT EXISTS qualitative_factor_scores (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  factor_id UUID REFERENCES world_model_factors(id) ON DELETE CASCADE,
  dimension TEXT NOT NULL, -- 'market_sentiment' | 'team_quality' | 'competitive_position' | 'execution_quality' | 'market_timing'
  score FLOAT NOT NULL, -- 0-100 score
  weight FLOAT DEFAULT 1.0, -- Weight in composite score
  source TEXT, -- Where this score came from
  evidence JSONB DEFAULT '[]', -- Supporting evidence/citations
  scored_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  scored_by TEXT -- User ID or 'system'
);

-- Scenario Definitions table
CREATE TABLE IF NOT EXISTS world_model_scenarios (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  model_id UUID REFERENCES world_models(id) ON DELETE CASCADE,
  scenario_name TEXT NOT NULL,
  scenario_type TEXT NOT NULL, -- 'base_case' | 'upside' | 'downside' | 'stress' | 'custom'
  probability FLOAT DEFAULT 0.33, -- Probability of this scenario (should sum to 1.0 for all scenarios)
  factor_overrides JSONB DEFAULT '{}', -- { factor_id: new_value } - overrides for this scenario
  relationship_changes JSONB DEFAULT '{}', -- Changes to relationships in this scenario
  temporal_changes JSONB DEFAULT '{}', -- How temporal dynamics change
  description TEXT,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Scenario Results table
CREATE TABLE IF NOT EXISTS world_model_scenario_results (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  scenario_id UUID REFERENCES world_model_scenarios(id) ON DELETE CASCADE,
  execution_time TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  factor_results JSONB DEFAULT '{}', -- { factor_id: calculated_value }
  model_outputs JSONB DEFAULT '{}', -- Final model outputs (valuation, NAV, etc.)
  sensitivity_analysis JSONB DEFAULT '{}', -- Which factors drove the results
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Stress Test Definitions table
CREATE TABLE IF NOT EXISTS stress_test_definitions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  model_id UUID REFERENCES world_models(id) ON DELETE CASCADE,
  test_name TEXT NOT NULL,
  test_type TEXT NOT NULL, -- 'predefined' | 'custom'
  predefined_type TEXT, -- '2008_crisis' | 'covid_19' | 'rate_shock' | 'competitive_disruption'
  stress_parameters JSONB NOT NULL DEFAULT '{}', -- Parameters for the stress test
  affected_factors JSONB DEFAULT '[]', -- Which factors are affected
  affected_relationships JSONB DEFAULT '[]', -- Which relationships are affected
  recovery_scenario JSONB, -- Optional recovery scenario
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Stress Test Results table
CREATE TABLE IF NOT EXISTS stress_test_results (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  stress_test_id UUID REFERENCES stress_test_definitions(id) ON DELETE CASCADE,
  execution_time TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  baseline_outputs JSONB DEFAULT '{}', -- Model outputs before stress
  stressed_outputs JSONB DEFAULT '{}', -- Model outputs after stress
  impact_analysis JSONB DEFAULT '{}', -- Analysis of what changed and why
  recovery_analysis JSONB, -- Recovery scenario analysis if applicable
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes for fast lookups
CREATE INDEX IF NOT EXISTS idx_world_models_fund_id ON world_models(fund_id);
CREATE INDEX IF NOT EXISTS idx_world_models_company_id ON world_models(company_id);
CREATE INDEX IF NOT EXISTS idx_world_models_created_by ON world_models(created_by);
CREATE INDEX IF NOT EXISTS idx_world_models_created_at ON world_models(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_world_model_entities_model_id ON world_model_entities(model_id);
CREATE INDEX IF NOT EXISTS idx_world_model_entities_entity_type ON world_model_entities(entity_type);
CREATE INDEX IF NOT EXISTS idx_world_model_factors_model_id ON world_model_factors(model_id);
CREATE INDEX IF NOT EXISTS idx_world_model_factors_entity_id ON world_model_factors(entity_id);
CREATE INDEX IF NOT EXISTS idx_world_model_factors_factor_type ON world_model_factors(factor_type);
CREATE INDEX IF NOT EXISTS idx_world_model_factors_category ON world_model_factors(factor_category);
CREATE INDEX IF NOT EXISTS idx_world_model_relationships_model_id ON world_model_relationships(model_id);
CREATE INDEX IF NOT EXISTS idx_world_model_relationships_from ON world_model_relationships(from_entity_id);
CREATE INDEX IF NOT EXISTS idx_world_model_relationships_to ON world_model_relationships(to_entity_id);
CREATE INDEX IF NOT EXISTS idx_qualitative_factor_scores_factor_id ON qualitative_factor_scores(factor_id);
CREATE INDEX IF NOT EXISTS idx_world_model_scenarios_model_id ON world_model_scenarios(model_id);
CREATE INDEX IF NOT EXISTS idx_stress_test_definitions_model_id ON stress_test_definitions(model_id);

-- GIN indexes for JSONB queries
CREATE INDEX IF NOT EXISTS idx_world_models_model_definition ON world_models USING GIN(model_definition);
CREATE INDEX IF NOT EXISTS idx_world_models_formulas ON world_models USING GIN(formulas);
CREATE INDEX IF NOT EXISTS idx_world_models_relationships ON world_models USING GIN(relationships);
CREATE INDEX IF NOT EXISTS idx_world_model_entities_properties ON world_model_entities USING GIN(properties);
CREATE INDEX IF NOT EXISTS idx_world_model_factors_current_value ON world_model_factors USING GIN(current_value);
CREATE INDEX IF NOT EXISTS idx_world_model_factors_historical_values ON world_model_factors USING GIN(historical_values);

-- Functions to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_world_model_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Triggers to auto-update updated_at
CREATE TRIGGER world_models_updated_at
  BEFORE UPDATE ON world_models
  FOR EACH ROW
  EXECUTE FUNCTION update_world_model_updated_at();

CREATE TRIGGER world_model_factors_updated_at
  BEFORE UPDATE ON world_model_factors
  FOR EACH ROW
  EXECUTE FUNCTION update_world_model_updated_at();

-- Enable RLS (Row Level Security)
ALTER TABLE world_models ENABLE ROW LEVEL SECURITY;
ALTER TABLE world_model_entities ENABLE ROW LEVEL SECURITY;
ALTER TABLE world_model_factors ENABLE ROW LEVEL SECURITY;
ALTER TABLE world_model_relationships ENABLE ROW LEVEL SECURITY;
ALTER TABLE qualitative_factor_scores ENABLE ROW LEVEL SECURITY;
ALTER TABLE world_model_scenarios ENABLE ROW LEVEL SECURITY;
ALTER TABLE world_model_scenario_results ENABLE ROW LEVEL SECURITY;
ALTER TABLE stress_test_definitions ENABLE ROW LEVEL SECURITY;
ALTER TABLE stress_test_results ENABLE ROW LEVEL SECURITY;

-- Policies: Users can view/create/update their own models
CREATE POLICY "Users can view world models for their funds"
  ON world_models
  FOR SELECT
  USING (true); -- TODO: Add proper auth check

CREATE POLICY "Users can create world models for their funds"
  ON world_models
  FOR INSERT
  WITH CHECK (true); -- TODO: Add proper auth check

CREATE POLICY "Users can update world models for their funds"
  ON world_models
  FOR UPDATE
  USING (true); -- TODO: Add proper auth check

-- Similar policies for other tables
CREATE POLICY "Users can view world model entities for their funds"
  ON world_model_entities FOR SELECT USING (true);
CREATE POLICY "Users can create world model entities for their funds"
  ON world_model_entities FOR INSERT WITH CHECK (true);
CREATE POLICY "Users can view world model factors for their funds"
  ON world_model_factors FOR SELECT USING (true);
CREATE POLICY "Users can create world model factors for their funds"
  ON world_model_factors FOR INSERT WITH CHECK (true);
CREATE POLICY "Users can update world model factors for their funds"
  ON world_model_factors FOR UPDATE USING (true);
CREATE POLICY "Users can view world model relationships for their funds"
  ON world_model_relationships FOR SELECT USING (true);
CREATE POLICY "Users can create world model relationships for their funds"
  ON world_model_relationships FOR INSERT WITH CHECK (true);
CREATE POLICY "Users can view qualitative factor scores for their funds"
  ON qualitative_factor_scores FOR SELECT USING (true);
CREATE POLICY "Users can create qualitative factor scores for their funds"
  ON qualitative_factor_scores FOR INSERT WITH CHECK (true);
CREATE POLICY "Users can view scenarios for their funds"
  ON world_model_scenarios FOR SELECT USING (true);
CREATE POLICY "Users can create scenarios for their funds"
  ON world_model_scenarios FOR INSERT WITH CHECK (true);
CREATE POLICY "Users can view stress tests for their funds"
  ON stress_test_definitions FOR SELECT USING (true);
CREATE POLICY "Users can create stress tests for their funds"
  ON stress_test_definitions FOR INSERT WITH CHECK (true);

-- Comments
COMMENT ON TABLE world_models IS 'Comprehensive world models capturing full business context (financial, operational, market, competitive)';
COMMENT ON TABLE world_model_entities IS 'Entities in the world model (companies, markets, competitors, etc.)';
COMMENT ON TABLE world_model_factors IS 'Qualitative and quantitative factors in the world model';
COMMENT ON TABLE world_model_relationships IS 'Relationships between entities in the world model';
COMMENT ON TABLE qualitative_factor_scores IS 'Detailed scoring for qualitative factors (market sentiment, team quality, etc.)';
COMMENT ON TABLE world_model_scenarios IS 'Scenario definitions for world models';
COMMENT ON TABLE stress_test_definitions IS 'Stress test definitions for world models';
