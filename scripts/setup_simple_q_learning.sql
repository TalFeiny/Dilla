-- SIMPLE Q-LEARNING FOR SPREADSHEET AGENT
-- No GPU needed - just PostgreSQL!

-- 1. Create Q-value table (this is where learning happens)
CREATE TABLE IF NOT EXISTS q_values (
  state_context TEXT,      -- Simple state description like "empty_grid" or "has_revenue_header"
  action TEXT,             -- Action like "add_formula" or "write_header"
  q_value FLOAT DEFAULT 0, -- The learned value of this action in this state
  success_count INT DEFAULT 0,
  total_count INT DEFAULT 0,
  last_updated TIMESTAMP DEFAULT NOW(),
  PRIMARY KEY (state_context, action)
);

-- 2. Function to get best action (this is the "brain")
CREATE OR REPLACE FUNCTION get_best_action(
  current_state TEXT,
  epsilon FLOAT DEFAULT 0.1  -- 10% exploration
)
RETURNS TEXT
LANGUAGE plpgsql
AS $$
DECLARE
  best_action TEXT;
  random_val FLOAT;
BEGIN
  random_val := random();
  
  -- Exploration: try random action 10% of time
  IF random_val < epsilon THEN
    -- Pick a random known action
    SELECT action INTO best_action
    FROM q_values
    WHERE state_context = current_state
    ORDER BY random()
    LIMIT 1;
    
    -- If no actions known for this state, suggest default
    IF best_action IS NULL THEN
      best_action := 'write_header';
    END IF;
  ELSE
    -- Exploitation: pick best known action
    SELECT action INTO best_action
    FROM q_values
    WHERE state_context = current_state
    ORDER BY q_value DESC
    LIMIT 1;
    
    -- Fallback if state never seen
    IF best_action IS NULL THEN
      best_action := 'explore_new';
    END IF;
  END IF;
  
  RETURN best_action;
END;
$$;

-- 3. Function to update Q-values (this is where it LEARNS)
CREATE OR REPLACE FUNCTION update_q_value(
  state TEXT,
  action_taken TEXT,
  reward FLOAT,
  next_state TEXT,
  learning_rate FLOAT DEFAULT 0.1,
  discount FLOAT DEFAULT 0.9
)
RETURNS VOID
LANGUAGE plpgsql
AS $$
DECLARE
  current_q FLOAT;
  max_next_q FLOAT;
  new_q FLOAT;
BEGIN
  -- Get current Q-value
  SELECT q_value INTO current_q
  FROM q_values
  WHERE state_context = state AND action = action_taken;
  
  -- If not found, initialize
  IF current_q IS NULL THEN
    INSERT INTO q_values (state_context, action, q_value, total_count)
    VALUES (state, action_taken, 0, 0);
    current_q := 0;
  END IF;
  
  -- Get max Q-value for next state
  SELECT COALESCE(MAX(q_value), 0) INTO max_next_q
  FROM q_values
  WHERE state_context = next_state;
  
  -- Q-Learning update rule
  new_q := current_q + learning_rate * (reward + discount * max_next_q - current_q);
  
  -- Update the table
  UPDATE q_values
  SET 
    q_value = new_q,
    success_count = success_count + CASE WHEN reward > 0 THEN 1 ELSE 0 END,
    total_count = total_count + 1,
    last_updated = NOW()
  WHERE state_context = state AND action = action_taken;
  
  RAISE NOTICE 'Updated Q(%, %) from % to %', state, action_taken, current_q, new_q;
END;
$$;

-- 4. Initialize with some basic actions
INSERT INTO q_values (state_context, action, q_value) VALUES
  ('empty_grid', 'add_title', 0.5),
  ('empty_grid', 'add_revenue_row', 0.3),
  ('has_title', 'add_revenue_row', 0.7),
  ('has_title', 'add_headers', 0.6),
  ('has_revenue', 'add_growth_formula', 0.8),
  ('has_revenue', 'add_costs', 0.6),
  ('has_formula', 'add_more_formulas', 0.5),
  ('has_formula', 'format_cells', 0.3)
ON CONFLICT (state_context, action) DO NOTHING;

-- 5. View to see what the agent has learned
CREATE OR REPLACE VIEW learning_progress AS
SELECT 
  state_context,
  action,
  ROUND(q_value::numeric, 3) as learned_value,
  success_count,
  total_count,
  CASE 
    WHEN total_count > 0 
    THEN ROUND((success_count::float / total_count * 100)::numeric, 1) 
    ELSE 0 
  END as success_rate_percent,
  last_updated
FROM q_values
ORDER BY state_context, q_value DESC;

-- 6. Test the system
SELECT '=== Current Best Actions ===' as info;
SELECT 
  state_context,
  get_best_action(state_context, 0) as best_action
FROM (VALUES ('empty_grid'), ('has_title'), ('has_revenue')) as states(state_context);

-- Grant permissions
GRANT ALL ON q_values TO authenticated;
GRANT ALL ON learning_progress TO authenticated;
GRANT EXECUTE ON FUNCTION get_best_action TO authenticated;
GRANT EXECUTE ON FUNCTION update_q_value TO authenticated;