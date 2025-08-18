-- Create table for storing PWERM analysis results
CREATE TABLE IF NOT EXISTS pwerm_results (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    company_id UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    analysis_timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- Core inputs
    company_name TEXT NOT NULL,
    current_arr_usd BIGINT,
    growth_rate DECIMAL(5,2),
    sector TEXT,
    
    -- Summary results
    expected_exit_value DECIMAL(15,2),
    median_exit_value DECIMAL(15,2),
    success_probability DECIMAL(5,4),
    mega_exit_probability DECIMAL(5,4),
    total_scenarios INTEGER DEFAULT 499,
    
    -- Market research data
    market_research JSONB,
    
    -- Scenarios data
    scenarios JSONB,
    
    -- Charts paths/data
    charts JSONB,
    
    -- Expected returns by round
    expected_round_returns JSONB,
    
    -- Full analysis results
    full_results JSONB,
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create index for faster lookups
CREATE INDEX idx_pwerm_results_company_id ON pwerm_results(company_id);
CREATE INDEX idx_pwerm_results_analysis_timestamp ON pwerm_results(analysis_timestamp DESC);

-- Add trigger to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_pwerm_results_updated_at BEFORE UPDATE
    ON pwerm_results FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Grant permissions
ALTER TABLE pwerm_results ENABLE ROW LEVEL SECURITY;

-- Create policy for service role
CREATE POLICY "Service role can manage all pwerm_results" ON pwerm_results
    FOR ALL USING (true);