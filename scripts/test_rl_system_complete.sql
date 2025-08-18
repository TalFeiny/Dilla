-- =====================================================
-- COMPLETE RL SYSTEM TEST & VALIDATION
-- Tests all RL functions and features
-- =====================================================

-- SECTION 1: Populate test data for RL system
-- =====================================================

-- 1.1: Clear existing test data (optional - be careful in production!)
-- DELETE FROM experience_replay WHERE metadata->>'test_data' = 'true';

-- 1.2: Insert various RL experiences for testing
INSERT INTO experience_replay (
  state_embedding,
  next_state_embedding,
  action_embedding,
  reward,
  metadata
) VALUES 
-- Good DCF model creation experience
(
  embed_rl_feedback('Empty grid', 'grid_state'),
  embed_rl_feedback('Grid with DCF headers', 'grid_state'),
  embed_rl_feedback('write A1 DCF Model', 'action'),
  0.95,
  jsonb_build_object(
    'action_text', 'grid.write("A1", "DCF Model")',
    'action_type', 'write',
    'model_type', 'DCF',
    'company', 'Stripe',
    'user_intent', 'Create DCF model for Stripe',
    'feedback_type', 'approve',
    'test_data', 'true'
  )
),
-- Revenue formula experience
(
  embed_rl_feedback('Grid with headers', 'grid_state'),
  embed_rl_feedback('Grid with revenue formula', 'grid_state'),
  embed_rl_feedback('formula B2 =B1*1.2', 'action'),
  0.85,
  jsonb_build_object(
    'action_text', 'grid.formula("B2", "=B1*1.2")',
    'action_type', 'formula',
    'model_type', 'DCF',
    'company', 'Stripe',
    'user_intent', 'Add growth formula',
    'feedback_type', 'approve',
    'specific_feedback', 'Good 20% growth rate',
    'test_data', 'true'
  )
),
-- Poor experience - wrong formula
(
  embed_rl_feedback('Grid with revenue', 'grid_state'),
  embed_rl_feedback('Grid with wrong calculation', 'grid_state'),
  embed_rl_feedback('formula C2 =C1*10', 'action'),
  -0.5,
  jsonb_build_object(
    'action_text', 'grid.formula("C2", "=C1*10")',
    'action_type', 'formula',
    'model_type', 'DCF',
    'company', 'Databricks',
    'user_intent', 'Add growth formula',
    'feedback_type', 'wrong',
    'specific_feedback', 'Growth rate too high, should be 30%',
    'test_data', 'true'
  )
),
-- LBO model experience
(
  embed_rl_feedback('Empty grid', 'grid_state'),
  embed_rl_feedback('Grid with LBO structure', 'grid_state'),
  embed_rl_feedback('write A1 LBO Analysis', 'action'),
  0.9,
  jsonb_build_object(
    'action_text', 'grid.write("A1", "LBO Analysis")',
    'action_type', 'write',
    'model_type', 'LBO',
    'company', 'Canva',
    'user_intent', 'Create LBO model',
    'feedback_type', 'approve',
    'test_data', 'true'
  )
),
-- Formatting experience
(
  embed_rl_feedback('Grid with numbers', 'grid_state'),
  embed_rl_feedback('Grid with formatted numbers', 'grid_state'),
  embed_rl_feedback('format B2:B10 currency', 'action'),
  0.7,
  jsonb_build_object(
    'action_text', 'grid.format("B2:B10", "currency")',
    'action_type', 'format',
    'model_type', 'DCF',
    'company', 'Stripe',
    'user_intent', 'Format revenue as currency',
    'feedback_type', 'approve',
    'test_data', 'true'
  )
);

-- SECTION 2: Test RL matching functions
-- =====================================================

-- 2.1: Test match_experiences function
-- Find similar experiences to a new DCF model request
SELECT 
  '=== Testing match_experiences ===' as test_name;

SELECT 
  id,
  reward,
  metadata->>'action_text' as action,
  metadata->>'model_type' as model,
  metadata->>'company' as company,
  round(similarity::numeric, 3) as similarity_score
FROM match_experiences(
  embed_rl_feedback('Empty grid ready for DCF', 'grid_state'),  -- Current state
  0.5,  -- Minimum similarity threshold
  5,    -- Return top 5 matches
  'DCF' -- Filter to DCF models only
)
ORDER BY reward DESC;

-- 2.2: Test without model type filter
SELECT 
  '=== Testing match_experiences (all models) ===' as test_name;

SELECT 
  id,
  reward,
  metadata->>'action_text' as action,
  metadata->>'model_type' as model,
  round(similarity::numeric, 3) as similarity_score
FROM match_experiences(
  embed_rl_feedback('Empty grid', 'grid_state'),
  0.3,  -- Lower threshold
  10    -- Get more results
);

-- SECTION 3: Test best actions function
-- =====================================================

-- 3.1: Get best actions for a given state
SELECT 
  '=== Testing get_best_actions ===' as test_name;

SELECT 
  action_text,
  round(avg_reward::numeric, 2) as avg_reward,
  count as times_used
FROM get_best_actions(
  embed_rl_feedback('Grid with headers', 'grid_state'),
  0.0,  -- Minimum reward (include all)
  5     -- Top 5 actions
);

-- SECTION 4: Test learning statistics
-- =====================================================

-- 4.1: Get learning stats for last 30 days
SELECT 
  '=== Testing get_learning_stats ===' as test_name;

SELECT 
  model_type,
  total_experiences,
  round(avg_reward::numeric, 2) as avg_reward,
  round(success_rate::numeric * 100, 1) || '%' as success_rate,
  round(improvement_trend::numeric, 1) || '%' as improvement_trend
FROM get_learning_stats('30 days'::interval)
ORDER BY total_experiences DESC;

-- SECTION 5: Test the RL insights view
-- =====================================================

SELECT 
  '=== Testing rl_insights view ===' as test_name;

SELECT 
  hour,
  model_type,
  experience_count,
  round(avg_reward::numeric, 2) as avg_reward,
  round(median_reward::numeric, 2) as median_reward,
  round(success_rate::numeric * 100, 1) || '%' as success_rate
FROM rl_insights
WHERE hour > NOW() - INTERVAL '24 hours'
ORDER BY hour DESC, model_type;

-- SECTION 6: Test embedding generation functions
-- =====================================================

-- 6.1: Test different feedback embeddings
SELECT 
  '=== Testing embed_rl_feedback variations ===' as test_name;

WITH test_inputs AS (
  SELECT * FROM (VALUES 
    ('Perfect execution!', 'feedback'),
    ('Revenue should be 350M', 'feedback'),
    ('Wrong formula', 'feedback'),
    ('grid.write("A1", "Revenue")', 'action'),
    ('grid.formula("B2", "=B1*1.2")', 'action'),
    ('Grid with DCF model complete', 'grid_state')
  ) AS t(input_text, context_type)
)
SELECT 
  input_text,
  context_type,
  embed_rl_feedback(input_text, context_type) IS NOT NULL as embedding_generated,
  array_length(embed_rl_feedback(input_text, context_type)::float[], 1) as dimensions
FROM test_inputs;

-- SECTION 7: Simulate a learning session
-- =====================================================

-- 7.1: Create a new session with multiple actions
DO $$
DECLARE
  v_session_id uuid := gen_random_uuid();
  v_state_embedding vector(384);
  v_next_state_embedding vector(384);
BEGIN
  -- Initial state
  v_state_embedding := embed_rl_feedback('Empty spreadsheet for Airbnb', 'grid_state');
  
  -- Action 1: Add title
  v_next_state_embedding := embed_rl_feedback('Spreadsheet with title', 'grid_state');
  INSERT INTO experience_replay (
    session_id, state_embedding, next_state_embedding, action_embedding, reward, metadata
  ) VALUES (
    v_session_id, v_state_embedding, v_next_state_embedding,
    embed_rl_feedback('write A1 Airbnb Valuation', 'action'),
    0.8,
    jsonb_build_object('action_text', 'Add title', 'model_type', 'Comparables', 'test_data', 'true')
  );
  
  -- Action 2: Add revenue
  v_state_embedding := v_next_state_embedding;
  v_next_state_embedding := embed_rl_feedback('Spreadsheet with revenue row', 'grid_state');
  INSERT INTO experience_replay (
    session_id, state_embedding, next_state_embedding, action_embedding, reward, metadata
  ) VALUES (
    v_session_id, v_state_embedding, v_next_state_embedding,
    embed_rl_feedback('write A3 Revenue write B3 5000000000', 'action'),
    0.9,
    jsonb_build_object('action_text', 'Add revenue', 'model_type', 'Comparables', 'specific_feedback', 'Correct revenue', 'test_data', 'true')
  );
  
  -- Action 3: Add wrong growth rate (negative reward)
  v_state_embedding := v_next_state_embedding;
  v_next_state_embedding := embed_rl_feedback('Spreadsheet with wrong growth', 'grid_state');
  INSERT INTO experience_replay (
    session_id, state_embedding, next_state_embedding, action_embedding, reward, metadata
  ) VALUES (
    v_session_id, v_state_embedding, v_next_state_embedding,
    embed_rl_feedback('formula B4 =B3*2', 'action'),
    -0.6,
    jsonb_build_object('action_text', 'Wrong growth rate', 'model_type', 'Comparables', 'specific_feedback', 'Growth too high, should be 15%', 'test_data', 'true')
  );
  
  RAISE NOTICE 'Created learning session % with 3 experiences', v_session_id;
END $$;

-- SECTION 8: Query to find best next action
-- =====================================================

-- 8.1: Given current state, what should agent do next?
WITH current_state AS (
  SELECT embed_rl_feedback('Spreadsheet with revenue but no projections', 'grid_state') as embedding
)
SELECT 
  '=== Best next actions for current state ===' as analysis;

SELECT 
  metadata->>'action_text' as successful_action,
  metadata->>'specific_feedback' as feedback,
  round(reward::numeric, 2) as reward,
  round((1 - (state_embedding <=> (SELECT embedding FROM current_state)))::numeric, 3) as state_similarity
FROM experience_replay
WHERE 
  reward > 0.5  -- Only successful actions
  AND 1 - (state_embedding <=> (SELECT embedding FROM current_state)) > 0.6  -- Similar states
ORDER BY 
  reward DESC,
  state_embedding <=> (SELECT embedding FROM current_state)
LIMIT 5;

-- SECTION 9: Performance metrics
-- =====================================================

-- 9.1: Overall RL system performance
SELECT 
  '=== Overall RL System Metrics ===' as metric_type;

SELECT 
  COUNT(*) as total_experiences,
  COUNT(DISTINCT session_id) as unique_sessions,
  COUNT(DISTINCT metadata->>'company') as unique_companies,
  COUNT(DISTINCT metadata->>'model_type') as model_types,
  round(AVG(reward)::numeric, 3) as avg_reward,
  round(STDDEV(reward)::numeric, 3) as reward_stddev,
  round(MIN(reward)::numeric, 2) as worst_reward,
  round(MAX(reward)::numeric, 2) as best_reward,
  round(AVG(CASE WHEN reward > 0 THEN reward END)::numeric, 3) as avg_positive_reward,
  round(AVG(CASE WHEN reward < 0 THEN reward END)::numeric, 3) as avg_negative_reward,
  round(100.0 * COUNT(CASE WHEN reward > 0 THEN 1 END) / COUNT(*)::numeric, 1) || '%' as success_rate
FROM experience_replay;

-- 9.2: Per model type performance
SELECT 
  '=== Performance by Model Type ===' as metric_type;

SELECT 
  metadata->>'model_type' as model_type,
  COUNT(*) as experiences,
  round(AVG(reward)::numeric, 3) as avg_reward,
  round(100.0 * COUNT(CASE WHEN reward > 0 THEN 1 END) / COUNT(*)::numeric, 1) || '%' as success_rate,
  round(MAX(reward)::numeric, 2) as best_outcome
FROM experience_replay
GROUP BY metadata->>'model_type'
ORDER BY AVG(reward) DESC;

-- SECTION 10: Cleanup test data (optional)
-- =====================================================

-- Uncomment to remove test data after testing
-- DELETE FROM experience_replay WHERE metadata->>'test_data' = 'true';

-- Final status check
SELECT 
  '=== Final Status Check ===' as status;

SELECT 
  'experience_replay' as table_name,
  COUNT(*) as total_rows,
  COUNT(CASE WHEN metadata->>'test_data' = 'true' THEN 1 END) as test_rows,
  COUNT(CASE WHEN metadata->>'test_data' IS NULL OR metadata->>'test_data' != 'true' THEN 1 END) as real_rows
FROM experience_replay;