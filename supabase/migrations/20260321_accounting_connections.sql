-- Unified accounting connections table for QuickBooks, NetSuite, Xero
-- Replaces provider-specific tables (xero_connections) with a single
-- provider-agnostic table.

CREATE TABLE IF NOT EXISTS accounting_connections (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    provider TEXT NOT NULL,  -- 'xero', 'quickbooks', 'netsuite'

    -- Provider-specific identifiers
    -- Xero: tenant_id / QBO: realm_id / NetSuite: account_id
    tenant_id TEXT,
    tenant_name TEXT,

    -- OAuth2 tokens (encrypted at rest via Supabase)
    access_token TEXT NOT NULL,
    refresh_token TEXT,
    token_expires_at TIMESTAMPTZ,

    -- NetSuite TBA-specific fields (OAuth 1.0 token-based auth)
    consumer_key TEXT,
    consumer_secret TEXT,
    token_key TEXT,
    token_secret TEXT,

    -- Sync state
    sync_status TEXT DEFAULT 'idle',  -- idle, syncing, error
    sync_error TEXT,
    last_sync_at TIMESTAMPTZ,

    -- Linking
    fund_id UUID,
    company_id UUID,         -- default company to sync to
    scopes TEXT[],

    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now(),

    UNIQUE(user_id, provider, tenant_id)
);

CREATE INDEX IF NOT EXISTS idx_accounting_connections_user
    ON accounting_connections(user_id);
CREATE INDEX IF NOT EXISTS idx_accounting_connections_provider
    ON accounting_connections(provider);
CREATE INDEX IF NOT EXISTS idx_accounting_connections_user_provider
    ON accounting_connections(user_id, provider);

-- ERP account mappings — map provider account codes to Dilla categories
-- Reusable across all providers. Supports user overrides.
CREATE TABLE IF NOT EXISTS erp_account_mappings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    connection_id UUID REFERENCES accounting_connections(id) ON DELETE CASCADE,

    erp_account_code TEXT,       -- "4000", "200", etc.
    erp_account_name TEXT,       -- "Sales Revenue", "Accounts Payable"
    erp_account_type TEXT,       -- Provider's native classification

    dilla_category TEXT,         -- revenue, cogs, opex_rd, opex_sm, opex_ga, bs_*
    dilla_subcategory TEXT,      -- engineering_salaries, hosting, etc.

    mapping_source TEXT DEFAULT 'auto',  -- 'auto' (rules/LLM), 'manual' (user override)
    confidence FLOAT,

    created_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(connection_id, erp_account_code)
);

CREATE INDEX IF NOT EXISTS idx_erp_account_mappings_connection
    ON erp_account_mappings(connection_id);

-- Migrate existing xero_connections data if the table exists
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'xero_connections') THEN
        INSERT INTO accounting_connections (
            user_id, provider, tenant_id, tenant_name,
            access_token, refresh_token, token_expires_at,
            sync_status, sync_error, last_sync_at,
            fund_id, scopes, created_at, updated_at
        )
        SELECT
            user_id, 'xero', xero_tenant_id, xero_tenant_name,
            access_token, refresh_token, token_expires_at,
            sync_status, sync_error, last_sync_at,
            fund_id, scopes, created_at, updated_at
        FROM xero_connections
        ON CONFLICT (user_id, provider, tenant_id) DO NOTHING;
    END IF;
END $$;
