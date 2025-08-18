-- Add funding cache columns to companies table
ALTER TABLE companies 
ADD COLUMN IF NOT EXISTS cached_funding_data jsonb,
ADD COLUMN IF NOT EXISTS funding_data_updated_at timestamp with time zone,
ADD COLUMN IF NOT EXISTS total_funding_usd numeric,
ADD COLUMN IF NOT EXISTS latest_round_name text,
ADD COLUMN IF NOT EXISTS latest_round_amount_usd numeric,
ADD COLUMN IF NOT EXISTS latest_round_date date,
ADD COLUMN IF NOT EXISTS months_since_last_raise integer GENERATED ALWAYS AS (
    CASE 
        WHEN latest_round_date IS NOT NULL 
        THEN EXTRACT(MONTH FROM age(CURRENT_DATE, latest_round_date)) + 
             EXTRACT(YEAR FROM age(CURRENT_DATE, latest_round_date)) * 12
        ELSE NULL
    END
) STORED;

-- Create index for faster lookups
CREATE INDEX IF NOT EXISTS idx_companies_name_funding ON companies(name, funding_data_updated_at);

-- Create a function to update funding data
CREATE OR REPLACE FUNCTION update_company_funding_data(
    p_company_name text,
    p_total_funding numeric,
    p_latest_round jsonb
)
RETURNS void AS $$
BEGIN
    UPDATE companies
    SET 
        cached_funding_data = jsonb_build_object(
            'total_funding', p_total_funding,
            'latest_round', p_latest_round
        ),
        funding_data_updated_at = CURRENT_TIMESTAMP,
        total_funding_usd = p_total_funding,
        latest_round_name = p_latest_round->>'name',
        latest_round_amount_usd = (p_latest_round->>'amount')::numeric,
        latest_round_date = CASE 
            WHEN p_latest_round->>'year' IS NOT NULL 
            THEN make_date((p_latest_round->>'year')::integer, 1, 1)
            ELSE NULL
        END
    WHERE name = p_company_name;
    
    -- Insert if not exists
    IF NOT FOUND THEN
        INSERT INTO companies (
            name, 
            cached_funding_data, 
            funding_data_updated_at,
            total_funding_usd,
            latest_round_name,
            latest_round_amount_usd,
            latest_round_date,
            status,
            funnel_status
        ) VALUES (
            p_company_name,
            jsonb_build_object(
                'total_funding', p_total_funding,
                'latest_round', p_latest_round
            ),
            CURRENT_TIMESTAMP,
            p_total_funding,
            p_latest_round->>'name',
            (p_latest_round->>'amount')::numeric,
            CASE 
                WHEN p_latest_round->>'year' IS NOT NULL 
                THEN make_date((p_latest_round->>'year')::integer, 1, 1)
                ELSE NULL
            END,
            'active',
            'researching'
        );
    END IF;
END;
$$ LANGUAGE plpgsql;