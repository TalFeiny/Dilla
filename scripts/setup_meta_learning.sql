-- Meta-Learning Tables for Adaptive RL System

-- Store meta-learning history
CREATE TABLE IF NOT EXISTS meta_learning_history (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  query_features JSONB NOT NULL,
  approach TEXT NOT NULL CHECK (approach IN ('template', 'learned', 'hybrid', 'exploration')),
  success BOOLEAN NOT NULL,
  reward FLOAT NOT NULL,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Index for similarity searches
CREATE INDEX idx_meta_learning_features ON meta_learning_history USING gin(query_features);
CREATE INDEX idx_meta_learning_created ON meta_learning_history(created_at DESC);

-- Store approach preferences per category
CREATE TABLE IF NOT EXISTS approach_preferences (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  category TEXT NOT NULL,
  approach TEXT NOT NULL,
  avg_reward FLOAT NOT NULL DEFAULT 0,
  count INTEGER NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(category, approach)
);

CREATE INDEX idx_approach_category ON approach_preferences(category);

-- Store learned task patterns
CREATE TABLE IF NOT EXISTS learned_task_patterns (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  pattern_hash TEXT UNIQUE NOT NULL,
  features JSONB NOT NULL,
  classification JSONB NOT NULL,
  success_rate FLOAT DEFAULT 0,
  usage_count INTEGER DEFAULT 0,
  last_used TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_pattern_hash ON learned_task_patterns(pattern_hash);
CREATE INDEX idx_pattern_success ON learned_task_patterns(success_rate DESC);

-- Function to update approach preferences
CREATE OR REPLACE FUNCTION update_approach_preference(
  p_category TEXT,
  p_approach TEXT,
  p_reward FLOAT
) RETURNS void AS $$
BEGIN
  INSERT INTO approach_preferences (category, approach, avg_reward, count)
  VALUES (p_category, p_approach, p_reward, 1)
  ON CONFLICT (category, approach)
  DO UPDATE SET
    avg_reward = (approach_preferences.avg_reward * approach_preferences.count + p_reward) / (approach_preferences.count + 1),
    count = approach_preferences.count + 1,
    updated_at = NOW();
END;
$$ LANGUAGE plpgsql;

-- Function to get best approach for category
CREATE OR REPLACE FUNCTION get_best_approach(p_category TEXT)
RETURNS TABLE(approach TEXT, avg_reward FLOAT) AS $$
BEGIN
  RETURN QUERY
  SELECT ap.approach, ap.avg_reward
  FROM approach_preferences ap
  WHERE ap.category = p_category
  ORDER BY ap.avg_reward DESC
  LIMIT 1;
END;
$$ LANGUAGE plpgsql;

-- View for approach performance analytics
CREATE OR REPLACE VIEW approach_performance AS
SELECT 
  approach,
  COUNT(*) as total_uses,
  AVG(reward) as avg_reward,
  STDDEV(reward) as reward_stddev,
  SUM(CASE WHEN success THEN 1 ELSE 0 END)::FLOAT / COUNT(*) as success_rate,
  MAX(created_at) as last_used
FROM meta_learning_history
WHERE created_at > NOW() - INTERVAL '7 days'
GROUP BY approach
ORDER BY avg_reward DESC;