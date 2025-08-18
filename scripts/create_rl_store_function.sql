-- Create a simple function to store RL experiences directly with text
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
BEGIN
  INSERT INTO experience_replay (
    state_embedding,
    action_embedding,
    next_state_embedding,
    reward,
    metadata
  ) VALUES (
    embed_rl_feedback(state_text, 'grid_state'),
    embed_rl_feedback(action_text, 'action'),
    embed_rl_feedback(next_state_text, 'grid_state'),
    reward_value,
    meta_data
  ) RETURNING id INTO experience_id;
  
  RETURN experience_id;
END;
$$;

-- Grant permission
GRANT EXECUTE ON FUNCTION store_rl_experience TO authenticated;

-- Test it
SELECT store_rl_experience(
  'Empty spreadsheet',
  'grid.write("A1", "Revenue")',
  'Spreadsheet with Revenue header',
  0.9,
  '{"model_type": "DCF", "company": "Test"}'::jsonb
) as test_experience_id;