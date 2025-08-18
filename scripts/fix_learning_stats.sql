-- Fix the get_learning_stats function - simplified version
-- Run this in Supabase SQL Editor

DROP FUNCTION IF EXISTS get_learning_stats CASCADE;

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
  SELECT
    COALESCE(e.metadata->>'model_type', 'General') as model_type,
    COUNT(*) as total_experiences,
    ROUND(AVG(e.reward)::numeric, 3)::float as avg_reward,
    ROUND((SUM(CASE WHEN e.reward > 0 THEN 1 ELSE 0 END)::float / NULLIF(COUNT(*), 0))::numeric, 3)::float as success_rate,
    0.0::float as improvement_trend -- Simplified: just return 0 for now
  FROM experience_replay e
  WHERE e.created_at > NOW() - time_window::interval
  GROUP BY COALESCE(e.metadata->>'model_type', 'General')
  ORDER BY COUNT(*) DESC;
END;
$$;

GRANT EXECUTE ON FUNCTION get_learning_stats TO authenticated, anon;

-- Test the function
SELECT * FROM get_learning_stats('7 days');