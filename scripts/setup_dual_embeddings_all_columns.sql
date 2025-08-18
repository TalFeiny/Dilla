-- DUAL EMBEDDING SYSTEM - RETURNS ALL COLUMNS
-- Uses SELECT * to return everything available in the companies table

-- ============================================
-- PART 1: RL EMBEDDINGS (unchanged)
-- ============================================

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
  
  CASE context_type
    WHEN 'feedback' THEN
      IF input_text ~* 'perfect|excellent|great' THEN embedding[1] := 0.9; END IF;
      IF input_text ~* 'good|correct|right' THEN embedding[2] := 0.7; END IF;
      IF input_text ~* 'wrong|incorrect|bad' THEN embedding[3] := -0.8; END IF;
      IF input_text ~* 'should be|change to|use' THEN embedding[4] := -0.3; END IF;
      IF input_text ~* 'revenue|sales|profit' THEN embedding[5] := 0.5; END IF;
      IF input_text ~* 'formula|calculation' THEN embedding[6] := 0.5; END IF;
      
    WHEN 'action' THEN
      IF input_text ~* 'write|set|update' THEN embedding[1] := 0.8; END IF;
      IF input_text ~* 'formula|calculate|sum' THEN embedding[2] := 0.8; END IF;
      IF input_text ~* 'format|style' THEN embedding[3] := 0.6; END IF;
      IF input_text ~* 'clear|delete|remove' THEN embedding[4] := -0.5; END IF;
      IF input_text ~* '[A-Z]+[0-9]+' THEN 
        embedding[5] := 0.7;
        hash_val := abs(hashtext(substring(input_text from '[A-Z]+[0-9]+')));
        embedding[6] := ((hash_val % 1000)::float / 500) - 1;
      END IF;
      
    WHEN 'grid_state' THEN
      embedding[1] := least(1.0, length(input_text)::float / 1000);
      IF input_text ~* 'revenue|sales' THEN embedding[2] := 0.8; END IF;
      IF input_text ~* 'formula|=' THEN embedding[3] := 0.7; END IF;
      IF input_text ~* 'currency|percentage' THEN embedding[4] := 0.6; END IF;
  END CASE;
  
  FOR i IN 51..384 LOOP
    hash_val := abs(hashtext(input_text || i::text || context_type));
    embedding[i] := ((hash_val % 2000)::float / 1000) - 1;
  END LOOP;
  
  FOR i IN 1..least(50, length(input_text) - 2) LOOP
    hash_val := abs(hashtext(substr(input_text, i, 3)));
    embedding[100 + (i % 100)] := embedding[100 + (i % 100)] + 
      ((hash_val % 1000)::float / 5000);
  END LOOP;
  
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

-- ============================================
-- PART 2: COMPANY EMBEDDINGS WITH FULL RETURNS
-- ============================================

ALTER TABLE companies 
ADD COLUMN IF NOT EXISTS embedding vector(768),
ADD COLUMN IF NOT EXISTS embedding_updated_at timestamp DEFAULT NOW();

CREATE OR REPLACE FUNCTION embed_company(
  company_name text,
  company_sector text DEFAULT '',
  arr_usd numeric DEFAULT 0,
  total_invested numeric DEFAULT 0,
  amount_raised text DEFAULT '',
  quarter_raised text DEFAULT ''
)
RETURNS vector(768)
LANGUAGE plpgsql
AS $$
DECLARE
  embedding float[];
  full_text text;
  i int;
  hash_val bigint;
BEGIN
  embedding := ARRAY(SELECT 0::float FROM generate_series(1, 768));
  
  full_text := lower(concat_ws(' ', 
    company_name, 
    company_sector,
    amount_raised,
    quarter_raised
  ));
  
  FOR i IN 1..least(100, length(company_name)) LOOP
    hash_val := abs(hashtext(substr(company_name, i, 3)));
    embedding[i] := ((hash_val % 1000)::float / 500) - 1;
  END LOOP;
  
  CASE lower(company_sector)
    WHEN 'fintech' THEN embedding[101] := 0.9; embedding[102] := 0.3;
    WHEN 'saas' THEN embedding[101] := 0.2; embedding[103] := 0.9;
    WHEN 'healthcare' THEN embedding[104] := 0.9; embedding[105] := 0.4;
    WHEN 'ai/ml' THEN embedding[106] := 0.9; embedding[107] := 0.8;
    WHEN 'ecommerce' THEN embedding[108] := 0.9; embedding[109] := 0.5;
    WHEN 'marketplace' THEN embedding[110] := 0.9; embedding[111] := 0.6;
    WHEN 'crypto' THEN embedding[112] := 0.9; embedding[113] := 0.7;
    WHEN 'enterprise software' THEN embedding[114] := 0.9; embedding[115] := 0.8;
    WHEN 'defense' THEN embedding[116] := 0.9; embedding[117] := 0.6;
    ELSE
      hash_val := abs(hashtext(lower(company_sector)));
      embedding[101] := ((hash_val % 1000)::float / 500) - 1;
  END CASE;
  
  IF arr_usd IS NOT NULL AND arr_usd > 0 THEN
    embedding[201] := least(1.0, arr_usd::float / 100000000);
  END IF;
  
  IF total_invested IS NOT NULL AND total_invested > 0 THEN
    embedding[202] := least(1.0, total_invested::float / 50000000);
  END IF;
  
  IF quarter_raised ~* 'Q1' THEN embedding[203] := 0.25; END IF;
  IF quarter_raised ~* 'Q2' THEN embedding[204] := 0.5; END IF;
  IF quarter_raised ~* 'Q3' THEN embedding[205] := 0.75; END IF;
  IF quarter_raised ~* 'Q4' THEN embedding[206] := 1.0; END IF;
  
  IF amount_raised ~* 'seed' THEN embedding[210] := 0.2; END IF;
  IF amount_raised ~* 'series a' THEN embedding[211] := 0.4; END IF;
  IF amount_raised ~* 'series b' THEN embedding[212] := 0.6; END IF;
  IF amount_raised ~* 'series c' THEN embedding[213] := 0.8; END IF;
  
  FOR i IN 301..768 LOOP
    hash_val := abs(hashtext(full_text || i::text));
    embedding[i] := ((hash_val % 2000)::float / 1000) - 1;
  END LOOP;
  
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

-- Update embeddings (with error handling)
CREATE OR REPLACE FUNCTION update_company_embeddings()
RETURNS TABLE (
  updated_count int,
  error_count int,
  errors text[]
)
LANGUAGE plpgsql
AS $$
DECLARE
  v_updated_count int := 0;
  v_error_count int := 0;
  v_errors text[] := '{}';
  r record;
BEGIN
  -- Process each company individually to handle errors
  FOR r IN 
    SELECT id, name, sector, current_arr_usd, total_invested_usd, 
           amount_raised, quarter_raised
    FROM companies c
    WHERE c.embedding IS NULL 
       OR c.embedding_updated_at < NOW() - INTERVAL '7 days'
    LIMIT 1000  -- Process in batches
  LOOP
    BEGIN
      UPDATE companies
      SET 
        embedding = embed_company(
          r.name,
          COALESCE(r.sector, ''),
          COALESCE(r.current_arr_usd, 0),
          COALESCE(r.total_invested_usd, 0),
          COALESCE(r.amount_raised, ''),
          COALESCE(r.quarter_raised, '')
        ),
        embedding_updated_at = NOW()
      WHERE id = r.id;
      
      v_updated_count := v_updated_count + 1;
    EXCEPTION WHEN OTHERS THEN
      v_error_count := v_error_count + 1;
      v_errors := array_append(v_errors, 
        format('Company %s (ID: %s): %s', r.name, r.id, SQLERRM)
      );
      -- Continue processing other companies
    END;
  END LOOP;
  
  RETURN QUERY SELECT v_updated_count, v_error_count, v_errors;
END;
$$;

-- ============================================
-- SEARCH FUNCTIONS RETURNING ALL COLUMNS
-- ============================================

-- Simple semantic search - returns everything as JSON
CREATE OR REPLACE FUNCTION search_similar_companies_json(
  query text,
  limit_count int DEFAULT 10,
  min_similarity float DEFAULT 0.5
)
RETURNS jsonb
LANGUAGE plpgsql
AS $$
DECLARE
  query_embedding vector(768);
  results jsonb;
BEGIN
  query_embedding := embed_company(query, query, 0, 0, '', '');
  
  SELECT jsonb_agg(row_to_json(t))
  INTO results
  FROM (
    SELECT
      c.*,
      1 - (c.embedding <=> query_embedding) as similarity
    FROM companies c
    WHERE 
      c.embedding IS NOT NULL
      AND 1 - (c.embedding <=> query_embedding) > min_similarity
    ORDER BY c.embedding <=> query_embedding
    LIMIT limit_count
  ) t;
  
  RETURN COALESCE(results, '[]'::jsonb);
END;
$$;

-- Hybrid search - returns all columns plus scores as JSON
CREATE OR REPLACE FUNCTION hybrid_company_search_json(
  query text,
  limit_count int DEFAULT 10
)
RETURNS jsonb
LANGUAGE plpgsql
AS $$
DECLARE
  query_embedding vector(768);
  results jsonb;
BEGIN
  query_embedding := embed_company(query, query, 0, 0, '', '');
  
  WITH text_search AS (
    SELECT 
      c.id,
      ts_rank(
        to_tsvector('english', c.name || ' ' || COALESCE(c.sector, '')),
        plainto_tsquery('english', query)
      ) as text_score
    FROM companies c
    WHERE 
      to_tsvector('english', c.name || ' ' || COALESCE(c.sector, '')) 
      @@ plainto_tsquery('english', query)
    LIMIT limit_count * 2
  ),
  semantic_search AS (
    SELECT
      c.id,
      1 - (c.embedding <=> query_embedding) as semantic_score
    FROM companies c
    WHERE c.embedding IS NOT NULL
    ORDER BY c.embedding <=> query_embedding
    LIMIT limit_count * 2
  ),
  combined AS (
    SELECT
      c.*,
      COALESCE(t.text_score, 0) as text_rank,
      COALESCE(s.semantic_score, 0) as semantic_rank,
      (COALESCE(t.text_score, 0) * 0.3 + COALESCE(s.semantic_score, 0) * 0.7) as combined_score
    FROM companies c
    LEFT JOIN text_search t ON c.id = t.id
    LEFT JOIN semantic_search s ON c.id = s.id
    WHERE t.id IS NOT NULL OR s.id IS NOT NULL
    ORDER BY (COALESCE(t.text_score, 0) * 0.3 + COALESCE(s.semantic_score, 0) * 0.7) DESC
    LIMIT limit_count
  )
  SELECT jsonb_agg(row_to_json(combined))
  INTO results
  FROM combined;
  
  RETURN COALESCE(results, '[]'::jsonb);
END;
$$;

-- Advanced search with filters - returns all columns
CREATE OR REPLACE FUNCTION search_companies_advanced_json(
  query text DEFAULT '',
  filters jsonb DEFAULT '{}'::jsonb
)
RETURNS jsonb
LANGUAGE plpgsql
AS $$
DECLARE
  query_embedding vector(768);
  results jsonb;
  sql_query text;
BEGIN
  -- Generate embedding if query provided
  IF query != '' THEN
    query_embedding := embed_company(query, '', 0, 0, '', '');
  END IF;
  
  -- Build dynamic query based on filters
  sql_query := 'SELECT row_to_json(t) FROM (SELECT c.*';
  
  -- Add similarity score if searching
  IF query != '' THEN
    sql_query := sql_query || ', 1 - (c.embedding <=> $1) as similarity';
  END IF;
  
  sql_query := sql_query || ' FROM companies c WHERE 1=1';
  
  -- Apply filters from JSON
  IF filters->>'sector' IS NOT NULL THEN
    sql_query := sql_query || format(' AND c.sector = %L', filters->>'sector');
  END IF;
  
  IF filters->>'min_arr' IS NOT NULL THEN
    sql_query := sql_query || format(' AND c.current_arr_usd >= %s', filters->>'min_arr');
  END IF;
  
  IF filters->>'max_arr' IS NOT NULL THEN
    sql_query := sql_query || format(' AND c.current_arr_usd <= %s', filters->>'max_arr');
  END IF;
  
  IF filters->>'min_investment' IS NOT NULL THEN
    sql_query := sql_query || format(' AND c.total_invested_usd >= %s', filters->>'min_investment');
  END IF;
  
  IF filters->>'max_investment' IS NOT NULL THEN
    sql_query := sql_query || format(' AND c.total_invested_usd <= %s', filters->>'max_investment');
  END IF;
  
  IF filters->>'fund_id' IS NOT NULL THEN
    sql_query := sql_query || format(' AND c.fund_id = %L::uuid', filters->>'fund_id');
  END IF;
  
  -- Add similarity filter if searching
  IF query != '' THEN
    sql_query := sql_query || ' AND c.embedding IS NOT NULL';
    sql_query := sql_query || format(' AND 1 - (c.embedding <=> $1) > %s', COALESCE(filters->>'min_similarity', '0.3'));
  END IF;
  
  -- Add ordering
  IF query != '' THEN
    sql_query := sql_query || ' ORDER BY c.embedding <=> $1';
  ELSE
    sql_query := sql_query || ' ORDER BY c.current_arr_usd DESC NULLS LAST';
  END IF;
  
  -- Add limit
  sql_query := sql_query || format(' LIMIT %s', COALESCE(filters->>'limit', '20'));
  sql_query := sql_query || ') t';
  
  -- Execute dynamic query
  IF query != '' THEN
    EXECUTE 'SELECT jsonb_agg(' || sql_query || ')' INTO results USING query_embedding;
  ELSE
    EXECUTE 'SELECT jsonb_agg(' || sql_query || ')' INTO results;
  END IF;
  
  RETURN COALESCE(results, '[]'::jsonb);
END;
$$;

-- Get all available columns in companies table (for UI/debugging)
CREATE OR REPLACE FUNCTION get_companies_columns()
RETURNS jsonb
LANGUAGE sql
AS $$
  SELECT jsonb_agg(
    jsonb_build_object(
      'column_name', column_name,
      'data_type', data_type,
      'is_nullable', is_nullable
    ) ORDER BY ordinal_position
  )
  FROM information_schema.columns
  WHERE table_name = 'companies'
  AND table_schema = 'public';
$$;

-- Add missing columns if they don't exist
ALTER TABLE companies 
ADD COLUMN IF NOT EXISTS latest_valuation_usd BIGINT;

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_companies_embedding 
  ON companies USING ivfflat (embedding vector_cosine_ops)
  WITH (lists = 100);

CREATE INDEX IF NOT EXISTS idx_companies_text_search
  ON companies USING GIN (to_tsvector('english', name || ' ' || COALESCE(sector, '')));

-- Only create index on columns that exist
DO $$ 
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.columns 
    WHERE table_name = 'companies' 
    AND column_name = 'latest_valuation_usd'
  ) THEN
    CREATE INDEX IF NOT EXISTS idx_companies_financial
      ON companies(current_arr_usd, total_invested_usd, latest_valuation_usd);
  ELSE
    CREATE INDEX IF NOT EXISTS idx_companies_financial
      ON companies(current_arr_usd, total_invested_usd);
  END IF;
END $$;

-- Grant permissions
GRANT EXECUTE ON FUNCTION embed_rl_feedback TO authenticated;
GRANT EXECUTE ON FUNCTION embed_company TO authenticated;
GRANT EXECUTE ON FUNCTION search_similar_companies_json TO authenticated;
GRANT EXECUTE ON FUNCTION hybrid_company_search_json TO authenticated;
GRANT EXECUTE ON FUNCTION search_companies_advanced_json TO authenticated;
GRANT EXECUTE ON FUNCTION get_companies_columns TO authenticated;
GRANT EXECUTE ON FUNCTION update_company_embeddings TO authenticated;

-- Initialize embeddings manually after setup
-- Run this separately to see results:
-- SELECT * FROM update_company_embeddings();

-- Test the functions
-- SELECT search_similar_companies_json('AI fintech startup', 5);
-- SELECT hybrid_company_search_json('Stripe', 10);
-- SELECT search_companies_advanced_json('SaaS', '{"sector": "SaaS", "min_arr": 1000000}'::jsonb);
-- SELECT get_companies_columns();