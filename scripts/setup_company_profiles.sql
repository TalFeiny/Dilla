-- Create table for storing detailed company profiles from scraping
CREATE TABLE IF NOT EXISTS public.company_profiles (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  company_name TEXT NOT NULL,
  website_url TEXT,
  profile_data JSONB NOT NULL,
  scraped_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc', NOW()),
  created_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc', NOW()),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc', NOW())
);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_company_profiles_name ON public.company_profiles(company_name);
CREATE INDEX IF NOT EXISTS idx_company_profiles_scraped_at ON public.company_profiles(scraped_at DESC);
CREATE UNIQUE INDEX IF NOT EXISTS idx_company_profiles_name_unique ON public.company_profiles(company_name);

-- Update trigger
CREATE OR REPLACE FUNCTION update_company_profiles_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = TIMEZONE('utc', NOW());
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_company_profiles_updated_at_trigger
BEFORE UPDATE ON public.company_profiles
FOR EACH ROW
EXECUTE FUNCTION update_company_profiles_updated_at();

-- Enable RLS
ALTER TABLE public.company_profiles ENABLE ROW LEVEL SECURITY;

-- Policies
CREATE POLICY "Enable all for service role" ON public.company_profiles
  FOR ALL
  USING (true)
  WITH CHECK (true);

-- Permissions
GRANT ALL ON public.company_profiles TO postgres, service_role;
GRANT SELECT ON public.company_profiles TO authenticated, anon;

COMMENT ON TABLE public.company_profiles IS 'Stores comprehensive company profiles from web scraping';