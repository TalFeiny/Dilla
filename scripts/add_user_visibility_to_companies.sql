-- Add user visibility columns to existing companies table
-- This allows users to save companies privately

-- Add user_id column if it doesn't exist
ALTER TABLE companies 
ADD COLUMN IF NOT EXISTS user_id TEXT;

-- Add visibility column for access control
ALTER TABLE companies 
ADD COLUMN IF NOT EXISTS visibility TEXT DEFAULT 'public';

-- Add created_by to track who added the company
ALTER TABLE companies 
ADD COLUMN IF NOT EXISTS created_by TEXT;

-- Add funding_stage column
ALTER TABLE companies 
ADD COLUMN IF NOT EXISTS funding_stage TEXT;

-- Add last_funding_date column
ALTER TABLE companies 
ADD COLUMN IF NOT EXISTS last_funding_date DATE;

-- Add metrics as JSONB for scores
ALTER TABLE companies 
ADD COLUMN IF NOT EXISTS metrics JSONB DEFAULT '{}'::jsonb;

-- Add data column for full raw data
ALTER TABLE companies 
ADD COLUMN IF NOT EXISTS data JSONB;

-- Add customers column if it doesn't exist
ALTER TABLE companies 
ADD COLUMN IF NOT EXISTS customers JSONB DEFAULT '[]'::jsonb;

-- Add ai_category column
ALTER TABLE companies 
ADD COLUMN IF NOT EXISTS ai_category TEXT;

-- Create index for user-specific queries
CREATE INDEX IF NOT EXISTS idx_companies_user_id ON companies(user_id);
CREATE INDEX IF NOT EXISTS idx_companies_visibility ON companies(visibility);
CREATE INDEX IF NOT EXISTS idx_companies_created_by ON companies(created_by);

-- Enable Row Level Security (RLS)
ALTER TABLE companies ENABLE ROW LEVEL SECURITY;

-- Drop existing policies if they exist
DROP POLICY IF EXISTS "Public companies are viewable by everyone" ON companies;
DROP POLICY IF EXISTS "Private companies are viewable by owner" ON companies;
DROP POLICY IF EXISTS "Users can insert their own companies" ON companies;
DROP POLICY IF EXISTS "Users can update their own companies" ON companies;
DROP POLICY IF EXISTS "Users can delete their own companies" ON companies;

-- Create new RLS policies with proper separation

-- Policy 1: Everyone can view public companies (existing companies in database)
CREATE POLICY "Public companies are viewable by everyone" ON companies
  FOR SELECT USING (
    visibility = 'public' OR 
    visibility IS NULL OR 
    user_id IS NULL
  );

-- Policy 2: Users can only view their own private companies
CREATE POLICY "Private companies are viewable by owner only" ON companies
  FOR SELECT USING (
    visibility = 'private' AND auth.uid()::text = user_id
  );

-- Policy 3: Users can only insert private companies for themselves
CREATE POLICY "Users can insert their own private companies" ON companies
  FOR INSERT WITH CHECK (
    auth.uid()::text = user_id AND 
    visibility = 'private'
  );

-- Policy 4: Users can only update their own private companies, NOT public ones
CREATE POLICY "Users can update only their own private companies" ON companies
  FOR UPDATE USING (
    auth.uid()::text = user_id AND 
    visibility = 'private'
  );

-- Policy 5: Users can only delete their own private companies, NOT public ones
CREATE POLICY "Users can delete only their own private companies" ON companies
  FOR DELETE USING (
    auth.uid()::text = user_id AND 
    visibility = 'private'
  );

-- Note: The policies above already prevent modifying public companies
-- because UPDATE and DELETE policies only allow operations on private companies
-- owned by the current user. No additional blocking policies needed.

-- Create a view for users to easily see their saved companies
CREATE OR REPLACE VIEW my_companies AS
SELECT 
  id,
  name,
  website,
  description,
  funding_stage,
  total_raised,
  revenue,
  arr,
  growth_rate,
  employee_count,
  valuation,
  metrics,
  customers,
  ai_category,
  created_at,
  updated_at
FROM companies
WHERE user_id = auth.uid()::text AND visibility = 'private';

-- Grant permissions
GRANT ALL ON companies TO authenticated;
GRANT SELECT ON my_companies TO authenticated;

-- Comments for documentation
COMMENT ON COLUMN companies.user_id IS 'User who owns this private company record';
COMMENT ON COLUMN companies.visibility IS 'Access control: public (everyone) or private (owner only)';
COMMENT ON COLUMN companies.created_by IS 'User who originally added this company';
COMMENT ON COLUMN companies.metrics IS 'JSON object containing various score metrics';
COMMENT ON COLUMN companies.data IS 'Full raw data from the analysis';