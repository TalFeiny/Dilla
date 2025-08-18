-- Enable pgvector extension if not already enabled
CREATE EXTENSION IF NOT EXISTS vector;

-- Drop existing table if needed for clean setup
DROP TABLE IF EXISTS experience_replay CASCADE;

-- Create experience replay table for RL system
CREATE TABLE experience_replay (
  id SERIAL PRIMARY KEY,
  session_id UUID DEFAULT gen_random_uuid(),
  
  -- State representations
  state_embedding vector(384),        -- Grid state before action
  next_state_embedding vector(384),   -- Grid state after action
  action_embedding vector(384),       -- Action taken
  
  -- Reward and metadata
  reward FLOAT NOT NULL,              -- Reward signal from user feedback
  
  -- Structured metadata for filtering and analysis
  metadata JSONB DEFAULT '{}',
  -- Expected metadata structure:
  -- {
  --   "action_text": "grid.write('A1', 'Revenue')",
  --   "action_type": "write|formula|format|style",
  --   "grid_before_size": 10,
  --   "grid_after_size": 11,
  --   "model_type": "DCF|LBO|Comparables",
  --   "company": "Stripe",
  --   "user_intent": "Create DCF model for Stripe",
  --   "feedback_type": "approve|wrong|edit|fix",
  --   "specific_feedback": "Revenue should be 350M"
  -- }
  
  -- Tracking
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create indexes for efficient similarity search
CREATE INDEX idx_experience_state_embedding 
  ON experience_replay 
  USING ivfflat (state_embedding vector_cosine_ops)
  WITH (lists = 100);

CREATE INDEX idx_experience_next_state_embedding 
  ON experience_replay 
  USING ivfflat (next_state_embedding vector_cosine_ops)
  WITH (lists = 100);

CREATE INDEX idx_experience_action_embedding 
  ON experience_replay 
  USING ivfflat (action_embedding vector_cosine_ops)
  WITH (lists = 100);

-- Index for filtering by metadata
CREATE INDEX idx_experience_metadata ON experience_replay USING GIN (metadata);
CREATE INDEX idx_experience_reward ON experience_replay (reward);
CREATE INDEX idx_experience_created_at ON experience_replay (created_at DESC);

-- Function to find similar past experiences
CREATE OR REPLACE FUNCTION match_experiences(
  query_embedding vector(384),
  match_threshold float DEFAULT 0.7,
  match_count int DEFAULT 10,
  model_type text DEFAULT NULL
)
RETURNS TABLE (
  id int,
  reward float,
  action_text text,
  metadata jsonb,
  similarity float
)
LANGUAGE plpgsql
AS $$
BEGIN
  RETURN QUERY
  SELECT
    e.id,
    e.reward,
    e.metadata->>'action_text' as action_text,
    e.metadata,
    1 - (e.state_embedding <=> query_embedding) as similarity
  FROM experience_replay e
  WHERE 
    1 - (e.state_embedding <=> query_embedding) > match_threshold
    AND (model_type IS NULL OR e.metadata->>'model_type' = model_type)
  ORDER BY 
    e.reward DESC,  -- Prioritize high-reward experiences
    e.state_embedding <=> query_embedding  -- Then by similarity
  LIMIT match_count;
END;
$$;

-- Function to get best actions for a given state
CREATE OR REPLACE FUNCTION get_best_actions(
  query_embedding vector(384),
  min_reward float DEFAULT 0.5,
  match_count int DEFAULT 5
)
RETURNS TABLE (
  action_text text,
  avg_reward float,
  count bigint
)
LANGUAGE plpgsql
AS $$
BEGIN
  RETURN QUERY
  SELECT
    e.metadata->>'action_text' as action_text,
    AVG(e.reward) as avg_reward,
    COUNT(*) as count
  FROM experience_replay e
  WHERE 
    1 - (e.state_embedding <=> query_embedding) > 0.8  -- High similarity only
    AND e.reward >= min_reward
  GROUP BY e.metadata->>'action_text'
  ORDER BY AVG(e.reward) DESC
  LIMIT match_count;
END;
$$;

-- Function to analyze learning progress
CREATE OR REPLACE FUNCTION get_learning_stats(
  time_window interval DEFAULT '7 days'
)
RETURNS TABLE (
  model_type text,
  total_experiences bigint,
  avg_reward float,
  success_rate float,
  improvement_trend float
)
LANGUAGE plpgsql
AS $$
BEGIN
  RETURN QUERY
  WITH recent_experiences AS (
    SELECT 
      e.metadata->>'model_type' as model_type,
      e.reward,
      e.created_at,
      ROW_NUMBER() OVER (PARTITION BY e.metadata->>'model_type' ORDER BY e.created_at) as experience_num
    FROM experience_replay e
    WHERE e.created_at > NOW() - time_window
  ),
  stats AS (
    SELECT
      re.model_type,
      COUNT(*) as total,
      AVG(re.reward) as avg_reward,
      SUM(CASE WHEN re.reward > 0 THEN 1 ELSE 0 END)::float / COUNT(*) as success_rate,
      -- Calculate trend: compare first half vs second half average
      AVG(CASE WHEN re.experience_num <= COUNT(*) OVER (PARTITION BY re.model_type) / 2 
          THEN re.reward END) as first_half_avg,
      AVG(CASE WHEN re.experience_num > COUNT(*) OVER (PARTITION BY re.model_type) / 2 
          THEN re.reward END) as second_half_avg
    FROM recent_experiences re
    GROUP BY re.model_type
  )
  SELECT
    s.model_type,
    s.total as total_experiences,
    s.avg_reward,
    s.success_rate,
    COALESCE((s.second_half_avg - s.first_half_avg) / NULLIF(ABS(s.first_half_avg), 0) * 100, 0) as improvement_trend
  FROM stats s
  ORDER BY total DESC;
END;
$$;

-- Create view for quick insights
CREATE OR REPLACE VIEW rl_insights AS
SELECT
  DATE_TRUNC('hour', created_at) as hour,
  metadata->>'model_type' as model_type,
  COUNT(*) as experience_count,
  AVG(reward) as avg_reward,
  PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY reward) as median_reward,
  SUM(CASE WHEN reward > 0 THEN 1 ELSE 0 END)::float / COUNT(*) as success_rate
FROM experience_replay
WHERE created_at > NOW() - INTERVAL '7 days'
GROUP BY DATE_TRUNC('hour', created_at), metadata->>'model_type'
ORDER BY hour DESC;

-- Grant permissions (adjust as needed)
GRANT ALL ON experience_replay TO authenticated;
GRANT ALL ON rl_insights TO authenticated;
GRANT EXECUTE ON FUNCTION match_experiences TO authenticated;
GRANT EXECUTE ON FUNCTION get_best_actions TO authenticated;
GRANT EXECUTE ON FUNCTION get_learning_stats TO authenticated;