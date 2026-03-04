-- Xero OAuth2 connection management
-- Stores per-user, per-fund Xero tenant connections with tokens

CREATE TABLE IF NOT EXISTS xero_connections (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    fund_id UUID,
    xero_tenant_id TEXT NOT NULL,
    xero_tenant_name TEXT,
    access_token TEXT NOT NULL,
    refresh_token TEXT NOT NULL,
    token_expires_at TIMESTAMPTZ NOT NULL,
    scopes TEXT[] DEFAULT '{}',
    last_sync_at TIMESTAMPTZ,
    sync_status TEXT DEFAULT 'idle' CHECK (sync_status IN ('idle', 'syncing', 'error')),
    sync_error TEXT,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

-- One Xero tenant per user (prevent duplicate connections)
CREATE UNIQUE INDEX IF NOT EXISTS uq_xero_user_tenant
    ON xero_connections (user_id, xero_tenant_id);

-- Quick lookup by user
CREATE INDEX IF NOT EXISTS idx_xero_connections_user
    ON xero_connections (user_id);

-- Token refresh job: find connections expiring soon
CREATE INDEX IF NOT EXISTS idx_xero_connections_expiry
    ON xero_connections (token_expires_at)
    WHERE sync_status != 'error';
