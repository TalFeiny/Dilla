-- Self-Learning Agent Tables

-- Learning records for tracking all interactions
CREATE TABLE IF NOT EXISTS agent_learning_records (
  id TEXT PRIMARY KEY,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  
  -- Query and Response
  query TEXT NOT NULL,
  response TEXT NOT NULL,
  
  -- Feedback and Performance
  feedback JSONB DEFAULT '{"accuracy": 0.5, "usefulness": 0.5}',
  performance JSONB DEFAULT '{}',
  
  -- Context
  session_id TEXT,
  user_id TEXT,
  context JSONB,
  
  -- Learning Metadata
  pattern_type TEXT,
  confidence NUMERIC(3,2),
  learning_applied BOOLEAN DEFAULT FALSE,
  
  -- Timestamps
  timestamp TIMESTAMPTZ DEFAULT NOW()
);

-- Patterns discovered by the agent
CREATE TABLE IF NOT EXISTS agent_patterns (
  id SERIAL PRIMARY KEY,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  
  -- Pattern Information
  pattern TEXT UNIQUE NOT NULL,
  pattern_type TEXT,
  description TEXT,
  
  -- Performance Metrics
  frequency INTEGER DEFAULT 1,
  avg_accuracy NUMERIC(3,2) DEFAULT 0.5,
  avg_usefulness NUMERIC(3,2) DEFAULT 0.5,
  
  -- Best and Worst Examples
  best_response TEXT,
  best_accuracy NUMERIC(3,2),
  worst_response TEXT,
  worst_accuracy NUMERIC(3,2),
  
  -- Learning Parameters
  confidence NUMERIC(3,2),
  last_updated TIMESTAMPTZ DEFAULT NOW()
);

-- Retraining queue for poor performing queries
CREATE TABLE IF NOT EXISTS agent_retraining_queue (
  id SERIAL PRIMARY KEY,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  
  -- Original Query
  query TEXT NOT NULL,
  original_response TEXT,
  
  -- Feedback
  feedback JSONB,
  corrections TEXT[],
  
  -- Priority and Status
  priority TEXT CHECK (priority IN ('high', 'medium', 'low')) DEFAULT 'medium',
  status TEXT CHECK (status IN ('pending', 'in_progress', 'completed', 'failed')) DEFAULT 'pending',
  
  -- Retraining Results
  retrained_at TIMESTAMPTZ,
  new_response TEXT,
  improvement_score NUMERIC(3,2)
);

-- Feedback history for continuous improvement
CREATE TABLE IF NOT EXISTS agent_feedback_history (
  id SERIAL PRIMARY KEY,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  
  -- Reference
  learning_record_id TEXT REFERENCES agent_learning_records(id),
  
  -- Feedback Details
  user_rating INTEGER CHECK (user_rating >= 1 AND user_rating <= 5),
  accuracy_score NUMERIC(3,2),
  usefulness_score NUMERIC(3,2),
  
  -- Specific Feedback
  what_was_correct TEXT[],
  what_was_wrong TEXT[],
  suggestions TEXT[],
  
  -- Outcome Tracking
  predicted_outcome JSONB,
  actual_outcome JSONB,
  outcome_accuracy NUMERIC(3,2)
);

-- Cost tracking for budget management
CREATE TABLE IF NOT EXISTS agent_cost_tracking (
  id SERIAL PRIMARY KEY,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  
  -- Cost Information
  query_id TEXT,
  input_tokens INTEGER,
  output_tokens INTEGER,
  cost_usd NUMERIC(10,6),
  
  -- Model Information
  model TEXT DEFAULT 'claude-3-5-sonnet',
  
  -- Budget Tracking
  daily_total NUMERIC(10,2),
  monthly_total NUMERIC(10,2),
  
  -- Optimization Metrics
  tokens_saved INTEGER,
  cache_hit BOOLEAN DEFAULT FALSE
);

-- Knowledge base for learned facts
CREATE TABLE IF NOT EXISTS agent_knowledge_base (
  id SERIAL PRIMARY KEY,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  
  -- Knowledge Entry
  category TEXT NOT NULL,
  subcategory TEXT,
  fact TEXT NOT NULL,
  
  -- Validation
  confidence NUMERIC(3,2) DEFAULT 0.5,
  source TEXT,
  verification_count INTEGER DEFAULT 0,
  last_verified TIMESTAMPTZ,
  
  -- Usage Tracking
  usage_count INTEGER DEFAULT 0,
  last_used TIMESTAMPTZ,
  
  -- Relationships
  related_facts TEXT[],
  contradicts TEXT[]
);

-- Vision analysis cache
CREATE TABLE IF NOT EXISTS agent_vision_cache (
  id SERIAL PRIMARY KEY,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  
  -- Image Information
  image_url TEXT UNIQUE NOT NULL,
  image_hash TEXT,
  
  -- Analysis Results
  analysis JSONB,
  companies_extracted TEXT[],
  segments_identified TEXT[],
  market_size_extracted TEXT,
  
  -- Metadata
  confidence NUMERIC(3,2),
  model_version TEXT,
  expires_at TIMESTAMPTZ
);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_learning_records_query ON agent_learning_records USING gin(to_tsvector('english', query));
CREATE INDEX IF NOT EXISTS idx_learning_records_session ON agent_learning_records(session_id);
CREATE INDEX IF NOT EXISTS idx_learning_records_pattern ON agent_learning_records(pattern_type);
CREATE INDEX IF NOT EXISTS idx_learning_records_timestamp ON agent_learning_records(timestamp DESC);

CREATE INDEX IF NOT EXISTS idx_patterns_pattern ON agent_patterns(pattern);
CREATE INDEX IF NOT EXISTS idx_patterns_accuracy ON agent_patterns(avg_accuracy DESC);
CREATE INDEX IF NOT EXISTS idx_patterns_frequency ON agent_patterns(frequency DESC);

CREATE INDEX IF NOT EXISTS idx_retraining_priority ON agent_retraining_queue(priority, status);
CREATE INDEX IF NOT EXISTS idx_feedback_record ON agent_feedback_history(learning_record_id);

CREATE INDEX IF NOT EXISTS idx_cost_tracking_date ON agent_cost_tracking(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_knowledge_category ON agent_knowledge_base(category, subcategory);
CREATE INDEX IF NOT EXISTS idx_vision_cache_url ON agent_vision_cache(image_url);

-- Enable Row Level Security
ALTER TABLE agent_learning_records ENABLE ROW LEVEL SECURITY;
ALTER TABLE agent_patterns ENABLE ROW LEVEL SECURITY;
ALTER TABLE agent_retraining_queue ENABLE ROW LEVEL SECURITY;
ALTER TABLE agent_feedback_history ENABLE ROW LEVEL SECURITY;
ALTER TABLE agent_cost_tracking ENABLE ROW LEVEL SECURITY;
ALTER TABLE agent_knowledge_base ENABLE ROW LEVEL SECURITY;
ALTER TABLE agent_vision_cache ENABLE ROW LEVEL SECURITY;

-- Policies
CREATE POLICY "Enable read access for all users" ON agent_learning_records FOR SELECT USING (true);
CREATE POLICY "Enable insert for authenticated users" ON agent_learning_records FOR INSERT WITH CHECK (true);
CREATE POLICY "Enable update for authenticated users" ON agent_learning_records FOR UPDATE USING (true);

CREATE POLICY "Enable read access for all users" ON agent_patterns FOR SELECT USING (true);
CREATE POLICY "Enable all for authenticated users" ON agent_patterns FOR ALL USING (true);

CREATE POLICY "Enable all for authenticated users" ON agent_feedback_history FOR ALL USING (true);
CREATE POLICY "Enable all for authenticated users" ON agent_cost_tracking FOR ALL USING (true);
CREATE POLICY "Enable all for authenticated users" ON agent_knowledge_base FOR ALL USING (true);
CREATE POLICY "Enable all for authenticated users" ON agent_vision_cache FOR ALL USING (true);

-- Function to calculate agent improvement over time
CREATE OR REPLACE FUNCTION calculate_agent_improvement()
RETURNS TABLE (
  period TEXT,
  avg_accuracy NUMERIC,
  total_queries INTEGER,
  improvement_rate NUMERIC
) AS $$
BEGIN
  RETURN QUERY
  WITH monthly_stats AS (
    SELECT 
      date_trunc('month', created_at) as month,
      AVG((feedback->>'accuracy')::NUMERIC) as accuracy,
      COUNT(*) as queries
    FROM agent_learning_records
    WHERE created_at > NOW() - INTERVAL '12 months'
    GROUP BY month
    ORDER BY month
  )
  SELECT 
    to_char(month, 'Mon YYYY') as period,
    ROUND(accuracy, 3) as avg_accuracy,
    queries::INTEGER as total_queries,
    ROUND(
      CASE 
        WHEN LAG(accuracy) OVER (ORDER BY month) IS NOT NULL 
        THEN ((accuracy - LAG(accuracy) OVER (ORDER BY month)) / LAG(accuracy) OVER (ORDER BY month)) * 100
        ELSE 0
      END, 2
    ) as improvement_rate
  FROM monthly_stats;
END;
$$ LANGUAGE plpgsql;

-- Function to get cost analytics
CREATE OR REPLACE FUNCTION get_cost_analytics()
RETURNS TABLE (
  period TEXT,
  total_cost NUMERIC,
  queries_count INTEGER,
  avg_cost_per_query NUMERIC,
  cache_hit_rate NUMERIC
) AS $$
BEGIN
  RETURN QUERY
  SELECT 
    to_char(date_trunc('day', created_at), 'YYYY-MM-DD') as period,
    ROUND(SUM(cost_usd), 2) as total_cost,
    COUNT(*)::INTEGER as queries_count,
    ROUND(AVG(cost_usd), 4) as avg_cost_per_query,
    ROUND(SUM(CASE WHEN cache_hit THEN 1 ELSE 0 END)::NUMERIC / COUNT(*) * 100, 2) as cache_hit_rate
  FROM agent_cost_tracking
  WHERE created_at > NOW() - INTERVAL '30 days'
  GROUP BY date_trunc('day', created_at)
  ORDER BY period DESC;
END;
$$ LANGUAGE plpgsql