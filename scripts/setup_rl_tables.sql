-- Reinforcement Learning Tables for RLHF

-- Store individual feedback events
CREATE TABLE IF NOT EXISTS rl_feedback (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  trajectory_id UUID,
  step INTEGER,
  reward FLOAT,
  reason TEXT,
  state JSONB,
  created_at TIMESTAMP DEFAULT NOW()
);

-- Store complete trajectories (episodes)
CREATE TABLE IF NOT EXISTS rl_trajectories (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  company TEXT,
  model_type TEXT,
  trajectory JSONB, -- Full state-action-reward sequence
  returns FLOAT[], -- Discounted returns for each step
  final_score FLOAT,
  created_at TIMESTAMP DEFAULT NOW()
);

-- Index for querying by model type and score
CREATE INDEX idx_rl_trajectories_model_score 
ON rl_trajectories(model_type, final_score DESC);

-- Store TD errors for value function approximation
CREATE TABLE IF NOT EXISTS rl_td_errors (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  state_hash VARCHAR(32),
  action JSONB,
  td_error FLOAT,
  return_value FLOAT,
  created_at TIMESTAMP DEFAULT NOW()
);

-- Index for fast state lookup
CREATE INDEX idx_rl_td_state 
ON rl_td_errors(state_hash, return_value DESC);

-- Store successful policy examples
CREATE TABLE IF NOT EXISTS rl_policy_examples (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  pattern JSONB,
  weight FLOAT, -- Importance weight based on reward
  created_at TIMESTAMP DEFAULT NOW()
);

-- Index for policy lookup
CREATE INDEX idx_rl_policy_weight 
ON rl_policy_examples(weight DESC);

-- Aggregate learning statistics
CREATE TABLE IF NOT EXISTS rl_learning_stats (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  model_type TEXT,
  episode_count INTEGER,
  avg_reward FLOAT,
  best_reward FLOAT,
  worst_reward FLOAT,
  improvement_rate FLOAT, -- % improvement over time
  computed_at TIMESTAMP DEFAULT NOW()
);

-- View for training data generation
CREATE OR REPLACE VIEW rl_training_dataset AS
WITH ranked_trajectories AS (
  SELECT 
    *,
    ROW_NUMBER() OVER (
      PARTITION BY model_type 
      ORDER BY final_score DESC
    ) as rank
  FROM rl_trajectories
  WHERE final_score > 0.5  -- Only positive examples
)
SELECT 
  jsonb_build_object(
    'messages', jsonb_build_array(
      jsonb_build_object(
        'role', 'system', 
        'content', format('Financial model expert. Reward score: %.2f', final_score)
      ),
      jsonb_build_object(
        'role', 'user',
        'content', format('Build %s model for %s', model_type, company)
      ),
      jsonb_build_object(
        'role', 'assistant',
        'content', trajectory->'actions'
      )
    ),
    'weight', final_score  -- For importance sampling
  ) as training_example,
  model_type,
  final_score,
  rank
FROM ranked_trajectories
WHERE rank <= 20;  -- Top 20 per model type

-- Function to compute learning curve
CREATE OR REPLACE FUNCTION compute_learning_curve(
  p_model_type TEXT DEFAULT NULL,
  p_window_size INT DEFAULT 10
)
RETURNS TABLE (
  episode_num INT,
  avg_score FLOAT,
  model_type TEXT
)
LANGUAGE plpgsql
AS $$
BEGIN
  RETURN QUERY
  WITH numbered_episodes AS (
    SELECT 
      ROW_NUMBER() OVER (
        PARTITION BY t.model_type 
        ORDER BY t.created_at
      ) as episode_num,
      t.final_score,
      t.model_type
    FROM rl_trajectories t
    WHERE p_model_type IS NULL OR t.model_type = p_model_type
  ),
  windowed AS (
    SELECT 
      e1.episode_num,
      e1.model_type,
      AVG(e2.final_score) as avg_score
    FROM numbered_episodes e1
    JOIN numbered_episodes e2 
      ON e2.model_type = e1.model_type
      AND e2.episode_num BETWEEN 
        GREATEST(1, e1.episode_num - p_window_size + 1) 
        AND e1.episode_num
    GROUP BY e1.episode_num, e1.model_type
  )
  SELECT 
    w.episode_num::INT,
    w.avg_score::FLOAT,
    w.model_type::TEXT
  FROM windowed w
  ORDER BY w.model_type, w.episode_num;
END;
$$;

-- Function to get best action for a state
CREATE OR REPLACE FUNCTION get_best_action(
  p_state_hash VARCHAR(32)
)
RETURNS JSONB
LANGUAGE plpgsql
AS $$
DECLARE
  v_action JSONB;
BEGIN
  -- Get action with highest expected return
  SELECT action INTO v_action
  FROM rl_td_errors
  WHERE state_hash = p_state_hash
  ORDER BY return_value DESC
  LIMIT 1;
  
  RETURN v_action;
END;
$$;

-- Trigger to update learning stats
CREATE OR REPLACE FUNCTION update_learning_stats()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
  -- Compute stats for the model type
  INSERT INTO rl_learning_stats (
    model_type,
    episode_count,
    avg_reward,
    best_reward,
    worst_reward,
    improvement_rate
  )
  SELECT 
    NEW.model_type,
    COUNT(*),
    AVG(final_score),
    MAX(final_score),
    MIN(final_score),
    CASE 
      WHEN COUNT(*) > 10 THEN
        (AVG(final_score) FILTER (WHERE created_at > NOW() - INTERVAL '1 day') -
         AVG(final_score) FILTER (WHERE created_at < NOW() - INTERVAL '7 days')) * 100
      ELSE 0
    END
  FROM rl_trajectories
  WHERE model_type = NEW.model_type;
  
  RETURN NEW;
END;
$$;

CREATE TRIGGER trigger_update_learning_stats
AFTER INSERT ON rl_trajectories
FOR EACH ROW
EXECUTE FUNCTION update_learning_stats();