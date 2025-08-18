-- Agent City Tables for Alpha Generation and Quantitative Analysis

-- Table for storing agent predictions and analysis
CREATE TABLE IF NOT EXISTS agent_predictions (
  id SERIAL PRIMARY KEY,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  
  -- Company Information
  company_id INTEGER REFERENCES companies(id),
  company_name TEXT NOT NULL,
  sector TEXT,
  
  -- Valuation Analysis
  current_valuation NUMERIC,
  intrinsic_value NUMERIC,
  hype_score NUMERIC(5,2),
  value_score NUMERIC(5,2),
  divergence_score NUMERIC(5,2),
  
  -- Predictions
  predicted_exit_date DATE,
  predicted_exit_value NUMERIC,
  predicted_irr NUMERIC(5,2),
  prediction_confidence TEXT CHECK (prediction_confidence IN ('HIGH', 'MEDIUM', 'LOW')),
  
  -- Market Analysis
  market_regime TEXT CHECK (market_regime IN ('bull', 'bear', 'neutral', 'bubble', 'crash')),
  comparable_multiples JSONB,
  
  -- Recommendation
  recommendation TEXT CHECK (recommendation IN ('STRONG_BUY', 'BUY', 'HOLD', 'SELL', 'STRONG_SELL', 'SHORT')),
  thesis TEXT,
  risk_factors JSONB,
  
  -- Alpha Metrics
  alpha_opportunity BOOLEAN DEFAULT FALSE,
  expected_alpha NUMERIC(5,2),
  alpha_source TEXT,
  
  -- Endurance Scoring
  endurance_score NUMERIC(5,2),
  is_transient BOOLEAN DEFAULT FALSE,
  moat_strength TEXT CHECK (moat_strength IN ('NONE', 'WEAK', 'MODERATE', 'STRONG', 'UNASSAILABLE')),
  
  -- Metadata
  analysis_version TEXT DEFAULT '1.0',
  model_used TEXT DEFAULT 'claude-3.5-sonnet',
  tools_used TEXT[]
);

-- Table for tracking agent conversations and insights
CREATE TABLE IF NOT EXISTS agent_conversations (
  id SERIAL PRIMARY KEY,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  
  -- Conversation Details
  session_id UUID DEFAULT gen_random_uuid(),
  user_message TEXT NOT NULL,
  agent_response TEXT NOT NULL,
  
  -- Context
  conversation_context JSONB,
  tools_called TEXT[],
  
  -- Insights Generated
  insights_generated JSONB,
  alpha_opportunities_identified INTEGER DEFAULT 0,
  
  -- Performance Tracking
  response_time_ms INTEGER,
  tokens_used INTEGER
);

-- Table for agent's market intelligence cache
CREATE TABLE IF NOT EXISTS agent_market_intelligence (
  id SERIAL PRIMARY KEY,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  
  -- Market Data
  data_type TEXT NOT NULL, -- 'exit', 'funding', 'multiple', 'trend'
  sector TEXT,
  geography TEXT,
  
  -- Intelligence
  data_point JSONB NOT NULL,
  source TEXT,
  confidence_score NUMERIC(5,2),
  
  -- Expiration
  expires_at TIMESTAMPTZ,
  is_stale BOOLEAN DEFAULT FALSE
);

-- Table for agent's portfolio optimization recommendations
CREATE TABLE IF NOT EXISTS agent_portfolio_optimizations (
  id SERIAL PRIMARY KEY,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  
  -- Portfolio Context
  fund_id INTEGER,
  optimization_type TEXT, -- 'rebalance', 'exit', 'entry', 'concentration'
  
  -- Current State
  current_portfolio JSONB,
  current_metrics JSONB, -- IRR, TVPI, concentration, etc.
  
  -- Recommended Changes
  recommended_actions JSONB,
  expected_improvement JSONB, -- Expected IRR improvement, risk reduction, etc.
  
  -- Quantitative Justification
  kelly_criterion_sizing JSONB,
  correlation_matrix JSONB,
  efficient_frontier_position JSONB,
  
  -- Execution
  urgency TEXT CHECK (urgency IN ('IMMEDIATE', 'HIGH', 'MEDIUM', 'LOW')),
  execution_notes TEXT
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_agent_predictions_company ON agent_predictions(company_id);
CREATE INDEX IF NOT EXISTS idx_agent_predictions_created ON agent_predictions(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_agent_predictions_alpha ON agent_predictions(alpha_opportunity) WHERE alpha_opportunity = TRUE;
CREATE INDEX IF NOT EXISTS idx_agent_predictions_recommendation ON agent_predictions(recommendation);

CREATE INDEX IF NOT EXISTS idx_agent_conversations_session ON agent_conversations(session_id);
CREATE INDEX IF NOT EXISTS idx_agent_conversations_created ON agent_conversations(created_at DESC);

CREATE INDEX IF NOT EXISTS idx_agent_market_intelligence_type ON agent_market_intelligence(data_type, sector);
CREATE INDEX IF NOT EXISTS idx_agent_market_intelligence_expires ON agent_market_intelligence(expires_at) WHERE is_stale = FALSE;

-- Row Level Security
ALTER TABLE agent_predictions ENABLE ROW LEVEL SECURITY;
ALTER TABLE agent_conversations ENABLE ROW LEVEL SECURITY;
ALTER TABLE agent_market_intelligence ENABLE ROW LEVEL SECURITY;
ALTER TABLE agent_portfolio_optimizations ENABLE ROW LEVEL SECURITY;

-- Policies (adjust based on your auth setup)
CREATE POLICY "Enable read access for all users" ON agent_predictions FOR SELECT USING (true);
CREATE POLICY "Enable insert for authenticated users" ON agent_predictions FOR INSERT WITH CHECK (true);
CREATE POLICY "Enable update for authenticated users" ON agent_predictions FOR UPDATE USING (true);

CREATE POLICY "Enable read access for all users" ON agent_conversations FOR SELECT USING (true);
CREATE POLICY "Enable insert for authenticated users" ON agent_conversations FOR INSERT WITH CHECK (true);

CREATE POLICY "Enable read access for all users" ON agent_market_intelligence FOR SELECT USING (true);
CREATE POLICY "Enable insert for authenticated users" ON agent_market_intelligence FOR INSERT WITH CHECK (true);
CREATE POLICY "Enable update for authenticated users" ON agent_market_intelligence FOR UPDATE USING (true);

CREATE POLICY "Enable read access for all users" ON agent_portfolio_optimizations FOR SELECT USING (true);
CREATE POLICY "Enable insert for authenticated users" ON agent_portfolio_optimizations FOR INSERT WITH CHECK (true);

-- Function to track agent performance
CREATE OR REPLACE FUNCTION calculate_agent_accuracy()
RETURNS TABLE (
  total_predictions INTEGER,
  accurate_predictions INTEGER,
  accuracy_rate NUMERIC,
  average_alpha_generated NUMERIC,
  best_call TEXT,
  worst_call TEXT
) AS $$
BEGIN
  RETURN QUERY
  SELECT 
    COUNT(*)::INTEGER as total_predictions,
    COUNT(*) FILTER (WHERE predicted_irr IS NOT NULL)::INTEGER as accurate_predictions,
    ROUND(AVG(CASE WHEN predicted_irr IS NOT NULL THEN 1 ELSE 0 END) * 100, 2) as accuracy_rate,
    ROUND(AVG(expected_alpha), 2) as average_alpha_generated,
    MAX(company_name || ' - ' || recommendation) as best_call,
    MIN(company_name || ' - ' || recommendation) as worst_call
  FROM agent_predictions
  WHERE created_at > NOW() - INTERVAL '90 days';
END;
$$ LANGUAGE plpgsql;