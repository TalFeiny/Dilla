-- Agent scheduled tasks
-- Persists tasks the LLM creates via the schedule_task tool
-- Celery reads these to drive dynamic beat schedules via redbeat

CREATE TABLE IF NOT EXISTS agent_tasks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    fund_id UUID REFERENCES funds(id) ON DELETE CASCADE,
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    task_type TEXT NOT NULL,
    label TEXT NOT NULL,
    params JSONB NOT NULL DEFAULT '{}',
    cron_expr TEXT,
    run_at TIMESTAMP WITH TIME ZONE,
    timezone TEXT NOT NULL DEFAULT 'UTC',
    status TEXT NOT NULL DEFAULT 'active'
        CHECK (status IN ('active', 'paused', 'done', 'failed', 'cancelled')),
    last_run_at TIMESTAMP WITH TIME ZONE,
    last_run_status TEXT CHECK (last_run_status IN ('success', 'error', NULL)),
    last_run_result JSONB,
    next_run_at TIMESTAMP WITH TIME ZONE,
    run_count INTEGER NOT NULL DEFAULT 0,
    error_count INTEGER NOT NULL DEFAULT 0,
    last_error TEXT,
    notify_chat BOOLEAN NOT NULL DEFAULT true,
    notify_email BOOLEAN NOT NULL DEFAULT false,
    created_by TEXT NOT NULL DEFAULT 'agent'
        CHECK (created_by IN ('agent', 'user')),
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_agent_tasks_fund_id ON agent_tasks(fund_id);
CREATE INDEX idx_agent_tasks_status ON agent_tasks(status);
CREATE INDEX idx_agent_tasks_next_run ON agent_tasks(next_run_at) WHERE status = 'active';

CREATE OR REPLACE FUNCTION update_agent_tasks_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER agent_tasks_updated_at
    BEFORE UPDATE ON agent_tasks
    FOR EACH ROW EXECUTE FUNCTION update_agent_tasks_updated_at();

ALTER TABLE agent_tasks ENABLE ROW LEVEL SECURITY;

CREATE POLICY "agent_tasks_select" ON agent_tasks
    FOR SELECT TO authenticated
    USING (EXISTS (
        SELECT 1 FROM funds f WHERE f.id = fund_id AND f.organization_id = user_org_id()
    ));

CREATE POLICY "agent_tasks_insert" ON agent_tasks
    FOR INSERT TO authenticated
    WITH CHECK (EXISTS (
        SELECT 1 FROM funds f WHERE f.id = fund_id AND f.organization_id = user_org_id()
    ));

CREATE POLICY "agent_tasks_update" ON agent_tasks
    FOR UPDATE TO authenticated
    USING (EXISTS (
        SELECT 1 FROM funds f WHERE f.id = fund_id AND f.organization_id = user_org_id()
    ));

-- Enable Realtime so the frontend subscription fires on updates
ALTER PUBLICATION supabase_realtime ADD TABLE agent_tasks;
