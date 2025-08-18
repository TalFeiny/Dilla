-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Create embeddings table for financial models
CREATE TABLE IF NOT EXISTS model_embeddings (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  content TEXT NOT NULL,
  metadata JSONB,
  embedding vector(1536), -- OpenAI embedding size, use 1024 for Claude
  created_at TIMESTAMP DEFAULT NOW()
);

-- Create index for similarity search
CREATE INDEX ON model_embeddings 
USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);

-- Store successful model sessions with embeddings
CREATE TABLE IF NOT EXISTS model_memories (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  company_name TEXT,
  model_type TEXT, -- 'DCF', 'PWERM', 'Comparables', etc
  prompt TEXT,
  data_context JSONB, -- All data retrieved
  model_commands TEXT[], -- Grid commands that worked
  accuracy_score FLOAT,
  embedding vector(1536),
  searchable_text TEXT, -- Concatenated searchable content
  created_at TIMESTAMP DEFAULT NOW()
);

-- Index for vector similarity
CREATE INDEX ON model_memories 
USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);

-- Function to search similar models
CREATE OR REPLACE FUNCTION search_similar_models(
  query_embedding vector(1536),
  match_count INT DEFAULT 5,
  match_threshold FLOAT DEFAULT 0.8
)
RETURNS TABLE (
  id UUID,
  company_name TEXT,
  model_type TEXT,
  prompt TEXT,
  model_commands TEXT[],
  similarity FLOAT
)
LANGUAGE plpgsql
AS $$
BEGIN
  RETURN QUERY
  SELECT 
    m.id,
    m.company_name,
    m.model_type,
    m.prompt,
    m.model_commands,
    1 - (m.embedding <=> query_embedding) AS similarity
  FROM model_memories m
  WHERE 1 - (m.embedding <=> query_embedding) > match_threshold
  ORDER BY m.embedding <=> query_embedding
  LIMIT match_count;
END;
$$;

-- Function to search by company and model type
CREATE OR REPLACE FUNCTION search_model_patterns(
  search_company TEXT DEFAULT NULL,
  search_model_type TEXT DEFAULT NULL,
  limit_count INT DEFAULT 10
)
RETURNS TABLE (
  company_name TEXT,
  model_type TEXT,
  prompt TEXT,
  data_context JSONB,
  model_commands TEXT[],
  accuracy_score FLOAT
)
LANGUAGE plpgsql
AS $$
BEGIN
  RETURN QUERY
  SELECT 
    m.company_name,
    m.model_type,
    m.prompt,
    m.data_context,
    m.model_commands,
    m.accuracy_score
  FROM model_memories m
  WHERE 
    (search_company IS NULL OR m.company_name ILIKE '%' || search_company || '%')
    AND (search_model_type IS NULL OR m.model_type = search_model_type)
  ORDER BY m.accuracy_score DESC
  LIMIT limit_count;
END;
$$;

-- Create training data view for fine-tuning
CREATE OR REPLACE VIEW fine_tuning_dataset AS
SELECT 
  jsonb_build_object(
    'messages', jsonb_build_array(
      jsonb_build_object('role', 'system', 'content', 
        'You are a financial modeling expert. Use the provided data to build accurate models.'),
      jsonb_build_object('role', 'user', 'content', 
        prompt || E'\n\nData Context:\n' || data_context::text),
      jsonb_build_object('role', 'assistant', 'content', 
        array_to_string(model_commands, E'\n'))
    )
  ) as training_example,
  company_name,
  model_type,
  accuracy_score
FROM model_memories
WHERE accuracy_score > 85  -- Only use high-quality examples
ORDER BY created_at DESC;