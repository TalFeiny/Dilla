-- =====================================================
-- DIAGNOSTIC & FIX SCRIPT FOR COMPANY EMBEDDINGS ERROR
-- Run each section in Supabase SQL Editor to identify the issue
-- =====================================================

-- SECTION 1: Check current state
-- =====================================================

-- 1.1: Verify pgvector is enabled
SELECT 
  CASE 
    WHEN EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'vector') 
    THEN '✅ pgvector is installed' 
    ELSE '❌ pgvector NOT installed - run: CREATE EXTENSION vector;' 
  END as pgvector_status;

-- 1.2: Check if companies table exists and has embedding columns
SELECT 
  column_name, 
  data_type,
  character_maximum_length,
  is_nullable
FROM information_schema.columns 
WHERE table_name = 'companies' 
AND column_name IN ('id', 'name', 'sector', 'current_arr_usd', 'total_invested_usd', 
                    'amount_raised', 'quarter_raised', 'embedding', 'embedding_updated_at')
ORDER BY column_name;

-- 1.3: Check if the functions exist
SELECT 
  proname as function_name,
  pronargs as arg_count
FROM pg_proc 
WHERE proname IN ('embed_company', 'update_company_embeddings', 'embed_company_simple')
ORDER BY proname;

-- 1.4: Check company data quality
SELECT 
  COUNT(*) as total_companies,
  COUNT(name) as companies_with_name,
  COUNT(sector) as companies_with_sector,
  COUNT(embedding) as companies_with_embedding,
  COUNT(CASE WHEN name IS NULL OR name = '' THEN 1 END) as empty_names,
  COUNT(CASE WHEN length(name) > 100 THEN 1 END) as very_long_names
FROM companies;

-- SECTION 2: Test the current function
-- =====================================================

-- 2.1: Try to run the function and capture the error
DO $$
DECLARE
  v_result record;
  v_error text;
BEGIN
  BEGIN
    -- Try to execute the function
    SELECT * INTO v_result FROM update_company_embeddings() LIMIT 1;
    RAISE NOTICE 'Function executed successfully: %', v_result;
  EXCEPTION WHEN OTHERS THEN
    GET STACKED DIAGNOSTICS v_error = MESSAGE_TEXT;
    RAISE NOTICE 'ERROR: %', v_error;
    RAISE NOTICE 'SQLSTATE: %', SQLSTATE;
    RAISE NOTICE 'DETAIL: %', SQLERRM;
  END;
END $$;

-- SECTION 3: Common fixes
-- =====================================================

-- 3.1: If columns are missing, add them
DO $$ 
BEGIN
  -- Check and add current_arr_usd if missing
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                 WHERE table_name = 'companies' AND column_name = 'current_arr_usd') THEN
    ALTER TABLE companies ADD COLUMN current_arr_usd NUMERIC;
    RAISE NOTICE 'Added current_arr_usd column';
  END IF;
  
  -- Check and add total_invested_usd if missing
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                 WHERE table_name = 'companies' AND column_name = 'total_invested_usd') THEN
    ALTER TABLE companies ADD COLUMN total_invested_usd NUMERIC;
    RAISE NOTICE 'Added total_invested_usd column';
  END IF;
  
  -- Check and add amount_raised if missing
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                 WHERE table_name = 'companies' AND column_name = 'amount_raised') THEN
    ALTER TABLE companies ADD COLUMN amount_raised TEXT;
    RAISE NOTICE 'Added amount_raised column';
  END IF;
  
  -- Check and add quarter_raised if missing
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                 WHERE table_name = 'companies' AND column_name = 'quarter_raised') THEN
    ALTER TABLE companies ADD COLUMN quarter_raised TEXT;
    RAISE NOTICE 'Added quarter_raised column';
  END IF;
  
  -- Check and add embedding column if missing
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                 WHERE table_name = 'companies' AND column_name = 'embedding') THEN
    ALTER TABLE companies ADD COLUMN embedding vector(768);
    RAISE NOTICE 'Added embedding column';
  END IF;
  
  -- Check and add embedding_updated_at if missing
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                 WHERE table_name = 'companies' AND column_name = 'embedding_updated_at') THEN
    ALTER TABLE companies ADD COLUMN embedding_updated_at TIMESTAMP DEFAULT NOW();
    RAISE NOTICE 'Added embedding_updated_at column';
  END IF;
END $$;

-- 3.2: Create a simpler, more robust update function
CREATE OR REPLACE FUNCTION update_company_embeddings_debug()
RETURNS TABLE (
  status text,
  message text,
  updated_count int
)
LANGUAGE plpgsql
AS $$
DECLARE
  v_count int := 0;
  v_company record;
  v_errors text[] := '{}';
  v_sample_company record;
BEGIN
  -- First, test with a single company
  SELECT * INTO v_sample_company 
  FROM companies 
  WHERE name IS NOT NULL AND name != ''
  LIMIT 1;
  
  IF v_sample_company IS NULL THEN
    RETURN QUERY SELECT 
      'ERROR'::text,
      'No valid companies found in table'::text,
      0;
    RETURN;
  END IF;
  
  -- Try to generate embedding for the sample company
  BEGIN
    PERFORM embed_company(
      v_sample_company.name,
      COALESCE(v_sample_company.sector, ''),
      COALESCE(v_sample_company.current_arr_usd, 0),
      COALESCE(v_sample_company.total_invested_usd, 0),
      COALESCE(v_sample_company.amount_raised, ''),
      COALESCE(v_sample_company.quarter_raised, '')
    );
  EXCEPTION WHEN OTHERS THEN
    RETURN QUERY SELECT 
      'ERROR'::text,
      'Failed to generate embedding: ' || SQLERRM::text,
      0;
    RETURN;
  END;
  
  -- If sample worked, proceed with batch update
  FOR v_company IN 
    SELECT id, name, sector, current_arr_usd, total_invested_usd, 
           amount_raised, quarter_raised
    FROM companies 
    WHERE name IS NOT NULL AND name != ''
      AND (embedding IS NULL OR embedding_updated_at < NOW() - INTERVAL '7 days')
    LIMIT 10  -- Start with small batch
  LOOP
    BEGIN
      UPDATE companies
      SET 
        embedding = embed_company(
          v_company.name,
          COALESCE(v_company.sector, ''),
          COALESCE(v_company.current_arr_usd, 0),
          COALESCE(v_company.total_invested_usd, 0),
          COALESCE(v_company.amount_raised, ''),
          COALESCE(v_company.quarter_raised, '')
        ),
        embedding_updated_at = NOW()
      WHERE id = v_company.id;
      
      v_count := v_count + 1;
    EXCEPTION WHEN OTHERS THEN
      v_errors := array_append(v_errors, 
        format('Company %s: %s', v_company.name, SQLERRM)
      );
    END;
  END LOOP;
  
  IF array_length(v_errors, 1) > 0 THEN
    RETURN QUERY SELECT 
      'PARTIAL'::text,
      format('Updated %s companies. Errors: %s', v_count, array_to_string(v_errors, '; '))::text,
      v_count;
  ELSE
    RETURN QUERY SELECT 
      'SUCCESS'::text,
      format('Successfully updated %s companies', v_count)::text,
      v_count;
  END IF;
END;
$$;

-- SECTION 4: Test the debug function
-- =====================================================

SELECT * FROM update_company_embeddings_debug();

-- SECTION 5: Alternative - Use the simpler embedding function
-- =====================================================

-- 5.1: Create an even simpler embedding function as fallback
CREATE OR REPLACE FUNCTION embed_company_minimal(
  company_name text
)
RETURNS vector(768)
LANGUAGE plpgsql
AS $$
DECLARE
  embedding float[];
  i int;
  hash_val bigint;
BEGIN
  -- Initialize with zeros
  embedding := ARRAY(SELECT 0::float FROM generate_series(1, 768));
  
  -- Simple hash-based embedding
  FOR i IN 1..768 LOOP
    hash_val := abs(hashtext(company_name || i::text));
    embedding[i] := ((hash_val % 2000)::float / 1000) - 1;
  END LOOP;
  
  RETURN embedding::vector(768);
END;
$$;

-- 5.2: Update using minimal function
CREATE OR REPLACE FUNCTION update_company_embeddings_minimal()
RETURNS int
LANGUAGE plpgsql
AS $$
DECLARE
  v_count int;
BEGIN
  UPDATE companies
  SET 
    embedding = embed_company_minimal(name),
    embedding_updated_at = NOW()
  WHERE name IS NOT NULL 
    AND name != ''
    AND (embedding IS NULL OR embedding_updated_at < NOW() - INTERVAL '7 days');
  
  GET DIAGNOSTICS v_count = ROW_COUNT;
  RETURN v_count;
END;
$$;

-- Test minimal update
SELECT update_company_embeddings_minimal() as companies_updated;

-- SECTION 6: Verify the fix worked
-- =====================================================

-- 6.1: Check how many companies now have embeddings
SELECT 
  COUNT(*) as total,
  COUNT(embedding) as with_embeddings,
  COUNT(*) - COUNT(embedding) as without_embeddings
FROM companies;

-- 6.2: Test search functionality
SELECT 
  id,
  name,
  sector,
  1 - (embedding <=> (SELECT embedding FROM companies WHERE name ILIKE '%stripe%' LIMIT 1)) as similarity
FROM companies
WHERE embedding IS NOT NULL
ORDER BY embedding <=> (SELECT embedding FROM companies WHERE name ILIKE '%stripe%' LIMIT 1)
LIMIT 5;

-- SECTION 7: RL System Check
-- =====================================================

-- 7.1: Check experience_replay table
SELECT 
  COUNT(*) as total_experiences,
  AVG(reward) as avg_reward,
  COUNT(DISTINCT session_id) as unique_sessions
FROM experience_replay;

-- 7.2: Test RL embedding function
SELECT embed_rl_feedback('Revenue should be 350M', 'feedback');

-- 7.3: Insert test RL experience
INSERT INTO experience_replay (
  state_embedding,
  next_state_embedding,
  action_embedding,
  reward,
  metadata
) VALUES (
  embed_rl_feedback('Empty spreadsheet', 'grid_state'),
  embed_rl_feedback('Spreadsheet with DCF model', 'grid_state'),
  embed_rl_feedback('Create DCF model', 'action'),
  0.9,
  jsonb_build_object(
    'action_text', 'Create DCF model',
    'action_type', 'model_creation',
    'model_type', 'DCF',
    'company', 'Test Company',
    'user_intent', 'Build financial model'
  )
) RETURNING id, reward, metadata;

-- SECTION 8: Final status check
-- =====================================================

SELECT 
  'Companies' as table_name,
  COUNT(*) as total_rows,
  COUNT(embedding) as rows_with_embeddings,
  ROUND(100.0 * COUNT(embedding) / NULLIF(COUNT(*), 0), 2) as percent_embedded
FROM companies
UNION ALL
SELECT 
  'Experience Replay' as table_name,
  COUNT(*) as total_rows,
  COUNT(state_embedding) as rows_with_embeddings,
  ROUND(100.0 * COUNT(state_embedding) / NULLIF(COUNT(*), 0), 2) as percent_embedded
FROM experience_replay;