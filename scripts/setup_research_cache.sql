-- Create table for caching research results
CREATE TABLE IF NOT EXISTS public.research_cache (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  company_name TEXT NOT NULL,
  profile_data JSONB NOT NULL,
  sources JSONB,
  expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc', NOW()),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc', NOW())
);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_research_cache_company ON public.research_cache(company_name);
CREATE INDEX IF NOT EXISTS idx_research_cache_expires ON public.research_cache(expires_at);
CREATE UNIQUE INDEX IF NOT EXISTS idx_research_cache_company_unique ON public.research_cache(company_name) 
  WHERE expires_at > TIMEZONE('utc', NOW());

-- Function to clean expired cache entries
CREATE OR REPLACE FUNCTION clean_expired_research_cache()
RETURNS void AS $$
BEGIN
  DELETE FROM public.research_cache 
  WHERE expires_at < TIMEZONE('utc', NOW());
END;
$$ LANGUAGE plpgsql;

-- Enable RLS
ALTER TABLE public.research_cache ENABLE ROW LEVEL SECURITY;

-- Policies
CREATE POLICY "Enable all for service role" ON public.research_cache
  FOR ALL
  USING (true)
  WITH CHECK (true);

-- Permissions
GRANT ALL ON public.research_cache TO postgres, service_role;
GRANT SELECT ON public.research_cache TO authenticated, anon;

COMMENT ON TABLE public.research_cache IS 'Caches research results for 15 minutes to improve performance';