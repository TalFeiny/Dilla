-- Create time-series tracking table for portfolio company metrics
-- This enables historical tracking of financial metrics over time
-- Each row represents a snapshot of a company's metrics at a specific point in time

-- Required columns in companies table are added by 20250123_add_portfolio_report_fields.sql
-- Only add current_arr_usd which is unique to this migration
ALTER TABLE companies
ADD COLUMN IF NOT EXISTS current_arr_usd NUMERIC;

-- Drop constraints if they exist (in case of previous partial migration)
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'company_metrics_history') THEN
        ALTER TABLE company_metrics_history 
        DROP CONSTRAINT IF EXISTS company_metrics_history_company_id_fkey;
        
        ALTER TABLE company_metrics_history 
        DROP CONSTRAINT IF EXISTS company_metrics_history_fund_id_fkey;
        
        ALTER TABLE company_metrics_history 
        DROP CONSTRAINT IF EXISTS company_metrics_history_source_document_id_fkey;
    END IF;
END $$;

CREATE TABLE IF NOT EXISTS company_metrics_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL,
    fund_id UUID,
    
    -- Financial metrics snapshot
    cash_in_bank_usd NUMERIC,
    burn_rate_monthly_usd NUMERIC,
    runway_months INTEGER,
    current_arr_usd NUMERIC,
    gross_margin DECIMAL(5,4),
    
    -- Source of the data
    source_type TEXT DEFAULT 'document', -- 'document', 'manual', 'api'
    source_document_id BIGINT,
    
    -- Metadata
    recorded_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    recorded_by TEXT, -- user_id or system
    CONSTRAINT company_metrics_history_company_id_fkey FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE CASCADE,
    CONSTRAINT company_metrics_history_fund_id_fkey FOREIGN KEY (fund_id) REFERENCES funds(id) ON DELETE SET NULL,
    CONSTRAINT company_metrics_history_source_document_id_fkey FOREIGN KEY (source_document_id) REFERENCES processed_documents(id) ON DELETE SET NULL
);

-- Create indexes for efficient time-series queries
CREATE INDEX IF NOT EXISTS idx_company_metrics_history_company_id 
ON company_metrics_history (company_id, recorded_at DESC);

CREATE INDEX IF NOT EXISTS idx_company_metrics_history_fund_id 
ON company_metrics_history (fund_id, recorded_at DESC) 
WHERE fund_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_company_metrics_history_recorded_at 
ON company_metrics_history (recorded_at DESC);

-- Composite index for common query: get all metrics for a company in a fund over time
CREATE INDEX IF NOT EXISTS idx_company_metrics_history_fund_company_time 
ON company_metrics_history (fund_id, company_id, recorded_at DESC) 
WHERE fund_id IS NOT NULL;

-- Function to automatically create history entry when company metrics are updated
CREATE OR REPLACE FUNCTION create_company_metrics_snapshot()
RETURNS TRIGGER AS $$
BEGIN
    -- Only create snapshot if this is a portfolio company (has fund_id)
    -- and if any of the tracked metrics changed
    IF NEW.fund_id IS NOT NULL AND (
        OLD.cash_in_bank_usd IS DISTINCT FROM NEW.cash_in_bank_usd OR
        OLD.burn_rate_monthly_usd IS DISTINCT FROM NEW.burn_rate_monthly_usd OR
        OLD.runway_months IS DISTINCT FROM NEW.runway_months OR
        OLD.current_arr_usd IS DISTINCT FROM NEW.current_arr_usd OR
        OLD.gross_margin IS DISTINCT FROM NEW.gross_margin
    ) THEN
        INSERT INTO company_metrics_history (
            company_id,
            fund_id,
            cash_in_bank_usd,
            burn_rate_monthly_usd,
            runway_months,
            current_arr_usd,
            gross_margin,
            source_type,
            recorded_at
        ) VALUES (
            NEW.id,
            NEW.fund_id,
            NEW.cash_in_bank_usd,
            NEW.burn_rate_monthly_usd,
            NEW.runway_months,
            NEW.current_arr_usd,
            NEW.gross_margin,
            'document',
            NOW()
        );
    END IF;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create trigger to automatically snapshot metrics on update
DROP TRIGGER IF EXISTS trigger_company_metrics_snapshot ON companies;
CREATE TRIGGER trigger_company_metrics_snapshot
    AFTER UPDATE ON companies
    FOR EACH ROW
    WHEN (
        OLD.cash_in_bank_usd IS DISTINCT FROM NEW.cash_in_bank_usd OR
        OLD.burn_rate_monthly_usd IS DISTINCT FROM NEW.burn_rate_monthly_usd OR
        OLD.runway_months IS DISTINCT FROM NEW.runway_months OR
        OLD.current_arr_usd IS DISTINCT FROM NEW.current_arr_usd OR
        OLD.gross_margin IS DISTINCT FROM NEW.gross_margin
    )
    EXECUTE FUNCTION create_company_metrics_snapshot();

-- Add comments for documentation
COMMENT ON TABLE company_metrics_history IS 'Time-series history of portfolio company financial metrics. Each row represents a snapshot at a point in time.';
COMMENT ON COLUMN company_metrics_history.source_type IS 'Source of the data: document (from document extraction), manual (user input), or api (external API)';
COMMENT ON COLUMN company_metrics_history.recorded_at IS 'Timestamp when this metric snapshot was recorded';

-- View for easy querying of latest metrics with history
CREATE OR REPLACE VIEW company_metrics_with_history AS
SELECT 
    c.id AS company_id,
    c.name AS company_name,
    c.fund_id,
    c.cash_in_bank_usd AS current_cash,
    c.burn_rate_monthly_usd AS current_burn_rate,
    c.runway_months AS current_runway,
    c.current_arr_usd AS current_revenue,
    c.gross_margin AS current_gross_margin,
    c.cash_updated_at,
    c.burn_rate_updated_at,
    c.runway_updated_at,
    c.revenue_updated_at,
    c.gross_margin_updated_at,
    -- Get previous values for percentage change calculation
    (
        SELECT cash_in_bank_usd 
        FROM company_metrics_history 
        WHERE company_id = c.id 
        AND recorded_at < c.cash_updated_at 
        ORDER BY recorded_at DESC 
        LIMIT 1
    ) AS previous_cash,
    (
        SELECT current_arr_usd 
        FROM company_metrics_history 
        WHERE company_id = c.id 
        AND recorded_at < c.revenue_updated_at 
        ORDER BY recorded_at DESC 
        LIMIT 1
    ) AS previous_revenue,
    (
        SELECT gross_margin 
        FROM company_metrics_history 
        WHERE company_id = c.id 
        AND recorded_at < c.gross_margin_updated_at 
        ORDER BY recorded_at DESC 
        LIMIT 1
    ) AS previous_gross_margin
FROM companies c
WHERE c.fund_id IS NOT NULL;

COMMENT ON VIEW company_metrics_with_history IS 'View combining current company metrics with previous values for percentage change calculations';
