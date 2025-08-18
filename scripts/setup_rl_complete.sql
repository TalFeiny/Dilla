-- =====================================================
-- COMPLETE RL SETUP SCRIPT FOR SPREADSHEET AGENT
-- Run this in Supabase SQL Editor step by step
-- =====================================================

-- STEP 1: Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- STEP 2: Check if companies table exists and has required columns
DO $$ 
BEGIN
  -- Add missing columns to companies table if needed
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                 WHERE table_name = 'companies' AND column_name = 'current_arr_usd') THEN
    ALTER TABLE companies ADD COLUMN current_arr_usd NUMERIC;
  END IF;
  
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                 WHERE table_name = 'companies' AND column_name = 'total_invested_usd') THEN
    ALTER TABLE companies ADD COLUMN total_invested_usd NUMERIC;
  END IF;
  
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                 WHERE table_name = 'companies' AND column_name = 'amount_raised') THEN
    ALTER TABLE companies ADD COLUMN amount_raised TEXT;
  END IF;
  
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                 WHERE table_name = 'companies' AND column_name = 'quarter_raised') THEN
    ALTER TABLE companies ADD COLUMN quarter_raised TEXT;
  END IF;
END $$;

-- STEP 3: Set up RL Experience Replay table
DROP TABLE IF EXISTS experience_replay CASCADE;

CREATE TABLE experience_replay (
  id SERIAL PRIMARY KEY,
  session_id UUID DEFAULT gen_random_uuid(),
  
  -- State representations
  state_embedding vector(384),        
  next_state_embedding vector(384),   
  action_embedding vector(384),       
  
  -- Reward and metadata
  reward FLOAT NOT NULL,              
  
  -- Structured metadata for filtering and analysis
  metadata JSONB DEFAULT '{}',
  
  -- Tracking
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create indexes for RL table
CREATE INDEX idx_experience_state_embedding 
  ON experience_replay 
  USING ivfflat (state_embedding vector_cosine_ops)
  WITH (lists = 100);

CREATE INDEX idx_experience_metadata ON experience_replay USING GIN (metadata);
CREATE INDEX idx_experience_reward ON experience_replay (reward);

-- STEP 4: Create simplified embedding function for companies
CREATE OR REPLACE FUNCTION embed_company_simple(
  company_name text,
  company_sector text DEFAULT ''
)
RETURNS vector(768)
LANGUAGE plpgsql
AS $$
DECLARE
  embedding float[];
  i int;
  hash_val bigint;
BEGIN
  -- Initialize array with zeros
  embedding := ARRAY(SELECT 0::float FROM generate_series(1, 768));
  
  -- Simple hash-based embedding for company name
  FOR i IN 1..least(100, length(company_name)) LOOP
    hash_val := abs(hashtext(substr(lower(company_name), i, 3)));
    embedding[i] := ((hash_val % 1000)::float / 500) - 1;
  END LOOP;
  
  -- Simple sector encoding
  IF lower(company_sector) LIKE '%fintech%' THEN
    embedding[101] := 0.9;
  ELSIF lower(company_sector) LIKE '%saas%' THEN
    embedding[102] := 0.9;
  ELSIF lower(company_sector) LIKE '%healthcare%' THEN
    embedding[103] := 0.9;
  ELSIF lower(company_sector) LIKE '%ai%' OR lower(company_sector) LIKE '%ml%' THEN
    embedding[104] := 0.9;
  END IF;
  
  -- Fill remaining dimensions with hash
  FOR i IN 200..768 LOOP
    hash_val := abs(hashtext(company_name || i::text));
    embedding[i] := ((hash_val % 2000)::float / 1000) - 1;
  END LOOP;
  
  -- Normalize values
  FOR i IN 1..768 LOOP
    embedding[i] := CASE 
      WHEN embedding[i] > 1 THEN 1
      WHEN embedding[i] < -1 THEN -1
      ELSE embedding[i]
    END;
  END LOOP;
  
  RETURN embedding::vector(768);
END;
$$;

-- STEP 5: Add embedding columns to companies table
ALTER TABLE companies 
ADD COLUMN IF NOT EXISTS embedding vector(768),
ADD COLUMN IF NOT EXISTS embedding_updated_at timestamp DEFAULT NOW();

-- STEP 6: Create safer update function with better error handling
CREATE OR REPLACE FUNCTION update_company_embeddings_safe()
RETURNS TABLE (
  status text,
  updated_count int,
  error_message text
)
LANGUAGE plpgsql
AS $$
DECLARE
  v_updated_count int := 0;
  v_company record;
  v_error_message text := NULL;
BEGIN
  -- Try to update embeddings for companies
  BEGIN
    FOR v_company IN 
      SELECT id, name, sector
      FROM companies 
      WHERE embedding IS NULL 
         OR embedding_updated_at < NOW() - INTERVAL '7 days'
      ORDER BY id
      LIMIT 100  -- Process in smaller batches
    LOOP
      BEGIN
        UPDATE companies
        SET 
          embedding = embed_company_simple(
            COALESCE(v_company.name, 'Unknown'),
            COALESCE(v_company.sector, '')
          ),
          embedding_updated_at = NOW()
        WHERE id = v_company.id;
        
        v_updated_count := v_updated_count + 1;
      EXCEPTION WHEN OTHERS THEN
        -- Continue processing other companies
        v_error_message := COALESCE(v_error_message || '; ', '') || 
                          'Error for ' || v_company.name || ': ' || SQLERRM;
      END;
    END LOOP;
    
    IF v_updated_count > 0 THEN
      RETURN QUERY SELECT 
        'Success'::text as status, 
        v_updated_count, 
        v_error_message;
    ELSE
      RETURN QUERY SELECT 
        'No companies to update'::text as status, 
        0, 
        v_error_message;
    END IF;
    
  EXCEPTION WHEN OTHERS THEN
    RETURN QUERY SELECT 
      'Error'::text as status, 
      v_updated_count, 
      SQLERRM::text;
  END;
END;
$$;

-- STEP 7: Create RL feedback embedding function
CREATE OR REPLACE FUNCTION embed_rl_feedback(
  input_text text,
  context_type text DEFAULT 'feedback'
)
RETURNS vector(384)
LANGUAGE plpgsql
AS $$
DECLARE
  embedding float[];
  i int;
  hash_val bigint;
BEGIN
  embedding := ARRAY(SELECT 0::float FROM generate_series(1, 384));
  
  -- Pattern matching for different contexts
  CASE context_type
    WHEN 'feedback' THEN
      IF input_text ~* 'perfect|excellent' THEN embedding[1] := 0.9; END IF;
      IF input_text ~* 'good|correct' THEN embedding[2] := 0.7; END IF;
      IF input_text ~* 'wrong|incorrect' THEN embedding[3] := -0.8; END IF;
      IF input_text ~* 'revenue|sales' THEN embedding[5] := 0.5; END IF;
      
    WHEN 'action' THEN
      IF input_text ~* 'write|set' THEN embedding[1] := 0.8; END IF;
      IF input_text ~* 'formula|calculate' THEN embedding[2] := 0.8; END IF;
      IF input_text ~* 'format|style' THEN embedding[3] := 0.6; END IF;
      
    WHEN 'grid_state' THEN
      embedding[1] := least(1.0, length(input_text)::float / 1000);
      IF input_text ~* 'revenue' THEN embedding[2] := 0.8; END IF;
      IF input_text ~* 'formula' THEN embedding[3] := 0.7; END IF;
  END CASE;
  
  -- Hash-based embedding for remaining dimensions
  FOR i IN 51..384 LOOP
    hash_val := abs(hashtext(input_text || i::text || context_type));
    embedding[i] := ((hash_val % 2000)::float / 1000) - 1;
  END LOOP;
  
  -- Normalize
  FOR i IN 1..384 LOOP
    embedding[i] := CASE 
      WHEN embedding[i] > 1 THEN 1
      WHEN embedding[i] < -1 THEN -1
      ELSE embedding[i]
    END;
  END LOOP;
  
  RETURN embedding::vector(384);
END;
$$;

-- STEP 8: Create search functions
CREATE OR REPLACE FUNCTION search_similar_companies(
  query text,
  limit_count int DEFAULT 10
)
RETURNS TABLE (
  id uuid,
  name text,
  sector text,
  similarity float
)
LANGUAGE plpgsql
AS $$
DECLARE
  query_embedding vector(768);
BEGIN
  query_embedding := embed_company_simple(query, '');
  
  RETURN QUERY
  SELECT
    c.id,
    c.name,
    c.sector,
    1 - (c.embedding <=> query_embedding) as similarity
  FROM companies c
  WHERE c.embedding IS NOT NULL
  ORDER BY c.embedding <=> query_embedding
  LIMIT limit_count;
END;
$$;

-- STEP 9: Create RL experience matching function
CREATE OR REPLACE FUNCTION match_rl_experiences(
  query_embedding vector(384),
  match_threshold float DEFAULT 0.7,
  match_count int DEFAULT 10
)
RETURNS TABLE (
  id int,
  reward float,
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
    e.metadata,
    1 - (e.state_embedding <=> query_embedding) as similarity
  FROM experience_replay e
  WHERE 
    e.state_embedding IS NOT NULL
    AND 1 - (e.state_embedding <=> query_embedding) > match_threshold
  ORDER BY 
    e.reward DESC,
    e.state_embedding <=> query_embedding
  LIMIT match_count;
END;
$$;

-- STEP 10: Grant permissions
GRANT ALL ON experience_replay TO authenticated;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO authenticated;

-- STEP 11: Create test data for RL system
INSERT INTO experience_replay (
  state_embedding,
  next_state_embedding,
  action_embedding,
  reward,
  metadata
) VALUES (
  embed_rl_feedback('Empty grid', 'grid_state'),
  embed_rl_feedback('Grid with revenue header', 'grid_state'),
  embed_rl_feedback('write A1 Revenue', 'action'),
  0.8,
  '{"action_text": "grid.write(\"A1\", \"Revenue\")", "action_type": "write", "model_type": "DCF"}'::jsonb
);

-- =====================================================
-- TEST QUERIES - Run these to verify setup
-- =====================================================

-- Test 1: Check if pgvector is installed
SELECT * FROM pg_extension WHERE extname = 'vector';

-- Test 2: Check companies table structure
SELECT column_name, data_type 
FROM information_schema.columns 
WHERE table_name = 'companies' 
ORDER BY ordinal_position;

-- Test 3: Update company embeddings (safe version)
SELECT * FROM update_company_embeddings_safe();

-- Test 4: Test company search
SELECT * FROM search_similar_companies('Stripe', 5);

-- Test 5: Check RL experience replay table
SELECT COUNT(*) as experience_count FROM experience_replay;

-- Test 6: Test RL experience matching
SELECT * FROM match_rl_experiences(
  embed_rl_feedback('Grid with revenue projections', 'grid_state'),
  0.5,
  5
);

-- =====================================================
-- DEBUGGING QUERIES
-- =====================================================

-- Debug 1: Check for companies without embeddings
SELECT COUNT(*) as companies_without_embeddings 
FROM companies 
WHERE embedding IS NULL;

-- Debug 2: Check company data quality
SELECT 
  COUNT(*) as total_companies,
  COUNT(name) as with_name,
  COUNT(sector) as with_sector,
  COUNT(embedding) as with_embedding
FROM companies;

-- Debug 3: Test embedding generation
SELECT embed_company_simple('Test Company', 'SaaS');

-- Debug 4: Check RL table
SELECT 
  COUNT(*) as total_experiences,
  AVG(reward) as avg_reward,
  MIN(reward) as min_reward,
  MAX(reward) as max_reward
FROM experience_replay;