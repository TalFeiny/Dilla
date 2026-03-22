-- accounting_connections: credentials for all P&L data sources.
-- Providers: quickbooks, netsuite, xero, sap_s4, sap_b1, salesforce, workday, bamboohr

CREATE TABLE IF NOT EXISTS accounting_connections (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    provider TEXT NOT NULL,

    tenant_id TEXT,
    tenant_name TEXT,

    access_token TEXT NOT NULL,
    refresh_token TEXT,
    token_expires_at TIMESTAMPTZ,

    extra_data JSONB DEFAULT '{}',

    sync_status TEXT DEFAULT 'idle',
    sync_error TEXT,
    last_sync_at TIMESTAMPTZ,

    fund_id UUID,
    company_id UUID,
    scopes TEXT[],

    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now(),

    UNIQUE(user_id, provider, tenant_id)
);

CREATE INDEX IF NOT EXISTS idx_accounting_connections_user
    ON accounting_connections(user_id);
CREATE INDEX IF NOT EXISTS idx_accounting_connections_provider
    ON accounting_connections(provider);
