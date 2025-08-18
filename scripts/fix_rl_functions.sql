-- Fix RL Functions - Resolves stack overflow and missing function issues
-- Run this in Supabase SQL Editor

-- 1. First, drop any existing problematic functions
DROP FUNCTION IF EXISTS embed_rl_feedback CASCADE;
DROP FUNCTION IF EXISTS store_rl_experience CASCADE;

-- 2. Create the base embedding function that doesn't call itself
CREATE OR REPLACE FUNCTION embed_rl_feedback(
  input_text text,
  context_type text DEFAULT 'feedback'
)
RETURNS vector(384)
LANGUAGE sql
IMMUTABLE PARALLEL SAFE
AS $$
  -- Generate a deterministic 384-dimensional embedding
  -- This is a placeholder that creates consistent embeddings based on input
  SELECT 
    ARRAY(
      SELECT 
        sin(hashtext(input_text || i::text) % 1000 / 100.0)::float4
      FROM generate_series(1, 384) i
    )::vector(384)
$$;

-- 3. Create the experience storage function
CREATE OR REPLACE FUNCTION store_rl_experience(
  state_text TEXT,
  action_text TEXT,
  next_state_text TEXT,
  reward_value FLOAT,
  meta_data JSONB DEFAULT '{}'
)
RETURNS INT
LANGUAGE plpgsql
AS $$
DECLARE
  experience_id INT;
  state_emb vector(384);
  action_emb vector(384);
  next_state_emb vector(384);
BEGIN
  -- Generate embeddings using our safe function
  state_emb := embed_rl_feedback(state_text, 'grid_state');
  action_emb := embed_rl_feedback(action_text, 'action');
  next_state_emb := embed_rl_feedback(next_state_text, 'grid_state');
  
  -- Store the experience
  INSERT INTO experience_replay (
    state_embedding,
    action_embedding,
    next_state_embedding,
    reward,
    metadata
  ) VALUES (
    state_emb,
    action_emb,
    next_state_emb,
    reward_value,
    meta_data || jsonb_build_object('action_text', action_text)
  ) RETURNING id INTO experience_id;
  
  RETURN experience_id;
END;
$$;

-- 4. Recreate the match_experiences function
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
    COALESCE(e.metadata->>'action_text', 'unknown') as action_text,
    e.metadata,
    1 - (e.state_embedding <=> query_embedding) as similarity
  FROM experience_replay e
  WHERE 
    1 - (e.state_embedding <=> query_embedding) > match_threshold
    AND (model_type IS NULL OR e.metadata->>'model_type' = model_type)
  ORDER BY 
    e.reward DESC,
    e.state_embedding <=> query_embedding
  LIMIT match_count;
END;
$$;

-- 5. Recreate the get_best_actions function
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
    COALESCE(e.metadata->>'action_text', 'unknown') as action_text,
    AVG(e.reward) as avg_reward,
    COUNT(*) as count
  FROM experience_replay e
  WHERE 
    1 - (e.state_embedding <=> query_embedding) > 0.8
    AND e.reward >= min_reward
    AND e.metadata->>'action_text' IS NOT NULL
  GROUP BY e.metadata->>'action_text'
  ORDER BY AVG(e.reward) DESC
  LIMIT match_count;
END;
$$;

-- 6. Recreate the get_learning_stats function (fixed window function issue)
CREATE OR REPLACE FUNCTION get_learning_stats(
  time_window text DEFAULT '7 days'
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
      COALESCE(e.metadata->>'model_type', 'General') as model_type,
      e.reward,
      e.created_at
    FROM experience_replay e
    WHERE e.created_at > NOW() - time_window::interval
  ),
  numbered_experiences AS (
    SELECT 
      model_type,
      reward,
      created_at,
      ROW_NUMBER() OVER (PARTITION BY model_type ORDER BY created_at) as experience_num
    FROM recent_experiences
  ),
  model_counts AS (
    SELECT 
      model_type,
      COUNT(*) as model_total
    FROM numbered_experiences
    GROUP BY model_type
  ),
  stats AS (
    SELECT
      ne.model_type,
      COUNT(*) as total,
      AVG(ne.reward) as avg_reward,
      SUM(CASE WHEN ne.reward > 0 THEN 1 ELSE 0 END)::float / NULLIF(COUNT(*), 0) as success_rate,
      AVG(CASE WHEN ne.experience_num <= mc.model_total / 2 
          THEN ne.reward END) as first_half_avg,
      AVG(CASE WHEN ne.experience_num > mc.model_total / 2 
          THEN ne.reward END) as second_half_avg
    FROM numbered_experiences ne
    JOIN model_counts mc ON mc.model_type = ne.model_type
    GROUP BY ne.model_type
  )
  SELECT
    s.model_type,
    s.total as total_experiences,
    ROUND(s.avg_reward::numeric, 3)::float as avg_reward,
    ROUND(s.success_rate::numeric, 3)::float as success_rate,
    ROUND(
      COALESCE(
        (s.second_half_avg - s.first_half_avg) / NULLIF(ABS(s.first_half_avg), 0) * 100, 
        0
      )::numeric, 
      2
    )::float as improvement_trend
  FROM stats s
  ORDER BY s.total DESC;
END;
$$;

-- 7. Grant permissions
GRANT EXECUTE ON FUNCTION embed_rl_feedback TO authenticated, anon;
GRANT EXECUTE ON FUNCTION store_rl_experience TO authenticated, anon;
GRANT EXECUTE ON FUNCTION match_experiences TO authenticated, anon;
GRANT EXECUTE ON FUNCTION get_best_actions TO authenticated, anon;
GRANT EXECUTE ON FUNCTION get_learning_stats TO authenticated, anon;

-- 8. Verify functions are created correctly
SELECT 
  proname as function_name,
  pronargs as num_args,
  pg_get_function_identity_arguments(oid) as arguments
FROM pg_proc 
WHERE proname IN (
  'embed_rl_feedback', 
  'store_rl_experience', 
  'match_experiences', 
  'get_best_actions', 
  'get_learning_stats'
)
AND pronamespace = (SELECT oid FROM pg_namespace WHERE nspname = 'public')
ORDER BY proname;