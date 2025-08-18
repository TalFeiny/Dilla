-- Create funds table if it doesn't exist
CREATE TABLE IF NOT EXISTS funds (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    fund_size_usd BIGINT,
    fund_type VARCHAR(50),
    vintage_year INTEGER,
    target_net_multiple_bps INTEGER DEFAULT 30000, -- 3.0x as basis points
    status VARCHAR(50) DEFAULT 'fundraising',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Insert sample funds
INSERT INTO funds (name, fund_size_usd, fund_type, vintage_year, target_net_multiple_bps, status) 
VALUES 
    ('VC Platform Fund I', 250000000, 'venture', 2023, 30000, 'deploying'),
    ('VC Platform Fund II', 500000000, 'venture', 2024, 35000, 'fundraising'),
    ('Opportunity Fund I', 100000000, 'opportunity', 2024, 25000, 'deploying')
ON CONFLICT (id) DO NOTHING;

-- Create companies table columns if missing
ALTER TABLE companies 
ADD COLUMN IF NOT EXISTS fund_id UUID REFERENCES funds(id),
ADD COLUMN IF NOT EXISTS total_invested_usd BIGINT DEFAULT 0,
ADD COLUMN IF NOT EXISTS ownership_percentage DECIMAL(5,2),
ADD COLUMN IF NOT EXISTS current_arr_usd BIGINT DEFAULT 0,
ADD COLUMN IF NOT EXISTS latest_valuation_usd BIGINT,
ADD COLUMN IF NOT EXISTS first_investment_date DATE,
ADD COLUMN IF NOT EXISTS exit_date DATE,
ADD COLUMN IF NOT EXISTS exit_value_usd BIGINT,
ADD COLUMN IF NOT EXISTS exit_multiple DECIMAL(10,2),
ADD COLUMN IF NOT EXISTS funnel_status VARCHAR(50);

-- Update some existing companies to belong to funds (if any exist)
UPDATE companies 
SET 
    fund_id = (SELECT id FROM funds WHERE name = 'VC Platform Fund I' LIMIT 1),
    total_invested_usd = CASE 
        WHEN current_arr_usd > 10000000 THEN 15000000
        WHEN current_arr_usd > 5000000 THEN 10000000
        ELSE 5000000
    END,
    ownership_percentage = CASE
        WHEN current_arr_usd > 10000000 THEN 15.5
        WHEN current_arr_usd > 5000000 THEN 12.0
        ELSE 8.5
    END,
    first_investment_date = CURRENT_DATE - INTERVAL '18 months',
    funnel_status = 'portfolio'
WHERE fund_id IS NULL 
AND current_arr_usd > 0
LIMIT 5;