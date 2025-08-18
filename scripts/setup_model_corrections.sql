-- Create table for storing model corrections and feedback
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

-- Create indexes for efficient querying
CREATE INDEX IF NOT EXISTS idx_model_corrections_company ON public.model_corrections(company_name);
CREATE INDEX IF NOT EXISTS idx_model_corrections_model_type ON public.model_corrections(model_type);
CREATE INDEX IF NOT EXISTS idx_model_corrections_created_at ON public.model_corrections(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_model_corrections_confidence ON public.model_corrections(confidence DESC);

-- Create a function to update the updated_at timestamp
CREATE OR REPLACE FUNCTION update_model_corrections_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = TIMEZONE('utc', NOW());
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create trigger to auto-update updated_at
CREATE TRIGGER update_model_corrections_updated_at_trigger
BEFORE UPDATE ON public.model_corrections
FOR EACH ROW
EXECUTE FUNCTION update_model_corrections_updated_at();

-- Add RLS policies
ALTER TABLE public.model_corrections ENABLE ROW LEVEL SECURITY;

-- Allow all operations for service role
CREATE POLICY "Enable all for service role" ON public.model_corrections
  FOR ALL
  USING (true)
  WITH CHECK (true);

-- Grant permissions
GRANT ALL ON public.model_corrections TO postgres, service_role;
GRANT SELECT, INSERT, UPDATE ON public.model_corrections TO authenticated, anon;

-- Add comment
COMMENT ON TABLE public.model_corrections IS 'Stores user feedback and corrections for model outputs to enable learning';