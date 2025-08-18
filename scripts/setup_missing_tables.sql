-- Combined script to create all missing tables for feedback and caching
-- Run this in Supabase SQL Editor

-- 1. Model Corrections Table (for storing user feedback)
CREATE TABLE IF NOT EXISTS public.model_corrections (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  company_name TEXT NOT NULL,
  model_type TEXT NOT NULL,
  correction_type TEXT,
  feedback TEXT,
  original_value JSONB,
  corrected_value JSONB,
  confidence FLOAT DEFAULT 0.5,
  learning_patterns JSONB,
  metadata JSONB,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc', NOW()),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc', NOW())
);

CREATE INDEX IF NOT EXISTS idx_model_corrections_company ON public.model_corrections(company_name);
CREATE INDEX IF NOT EXISTS idx_model_corrections_model_type ON public.model_corrections(model_type);

-- 2. Research Cache Table (for 15-minute caching)
CREATE TABLE IF NOT EXISTS public.research_cache (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  company_name TEXT NOT NULL,
  profile_data JSONB NOT NULL,
  sources JSONB,
  expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc', NOW())
);

CREATE INDEX IF NOT EXISTS idx_research_cache_company ON public.research_cache(company_name);
CREATE INDEX IF NOT EXISTS idx_research_cache_expires ON public.research_cache(expires_at);

-- 3. Company Profiles Table (for scraped profiles)
CREATE TABLE IF NOT EXISTS public.company_profiles (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  company_name TEXT NOT NULL,
  website_url TEXT,
  profile_data JSONB NOT NULL,
  scraped_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc', NOW()),
  created_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc', NOW()),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc', NOW())
);

CREATE INDEX IF NOT EXISTS idx_company_profiles_name ON public.company_profiles(company_name);
CREATE UNIQUE INDEX IF NOT EXISTS idx_company_profiles_name_unique ON public.company_profiles(company_name);

-- Enable RLS on all tables
ALTER TABLE public.model_corrections ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.research_cache ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.company_profiles ENABLE ROW LEVEL SECURITY;

-- Drop existing policies if they exist
DROP POLICY IF EXISTS "Enable all for service role" ON public.model_corrections;
DROP POLICY IF EXISTS "Enable all for service role" ON public.research_cache;
DROP POLICY IF EXISTS "Enable all for service role" ON public.company_profiles;

-- Create policies for service role
CREATE POLICY "Enable all for service role" ON public.model_corrections
  FOR ALL USING (true) WITH CHECK (true);

CREATE POLICY "Enable all for service role" ON public.research_cache
  FOR ALL USING (true) WITH CHECK (true);

CREATE POLICY "Enable all for service role" ON public.company_profiles
  FOR ALL USING (true) WITH CHECK (true);

-- Grant permissions
GRANT ALL ON public.model_corrections TO postgres, service_role;
GRANT SELECT, INSERT, UPDATE ON public.model_corrections TO authenticated, anon;

GRANT ALL ON public.research_cache TO postgres, service_role;
GRANT SELECT ON public.research_cache TO authenticated, anon;

GRANT ALL ON public.company_profiles TO postgres, service_role;
GRANT SELECT ON public.company_profiles TO authenticated, anon;

-- Success message
SELECT 'All missing tables created successfully!' as status;