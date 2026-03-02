-- ============================================================
-- Dilla AI: Supabase Auth RLS Migration
-- Run this in the Supabase SQL Editor
-- ============================================================
-- IMPORTANT: Your public.users table uses its own uuid for `id`,
-- NOT auth.uid(). All lookups use email. The helper function
-- below matches on email extracted from the JWT.
-- ============================================================

BEGIN;

-- ============================================================
-- 1. Helper: get the current user's organization_id
--    Matches on JWT email since users.id != auth.uid()
-- ============================================================
CREATE OR REPLACE FUNCTION public.user_org_id()
RETURNS uuid
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = public
AS $$
  SELECT organization_id
  FROM public.users
  WHERE email = (auth.jwt() ->> 'email')
  LIMIT 1
$$;

-- Helper: get the current user's public.users.id
CREATE OR REPLACE FUNCTION public.user_row_id()
RETURNS uuid
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = public
AS $$
  SELECT id
  FROM public.users
  WHERE email = (auth.jwt() ->> 'email')
  LIMIT 1
$$;

GRANT EXECUTE ON FUNCTION public.user_org_id() TO authenticated;
GRANT EXECUTE ON FUNCTION public.user_row_id() TO authenticated;

-- Performance index for the email lookup (used on every single query)
CREATE INDEX IF NOT EXISTS idx_users_email ON public.users (email);
CREATE INDEX IF NOT EXISTS idx_users_email_org ON public.users (email, organization_id);

-- ============================================================
-- 2. Users table
-- ============================================================
ALTER TABLE public.users ENABLE ROW LEVEL SECURITY;

-- Users can read their own row (by email from JWT)
CREATE POLICY "users_select_own" ON public.users
  FOR SELECT TO authenticated
  USING (email = (auth.jwt() ->> 'email'));

-- Users can update their own row
CREATE POLICY "users_update_own" ON public.users
  FOR UPDATE TO authenticated
  USING (email = (auth.jwt() ->> 'email'))
  WITH CHECK (email = (auth.jwt() ->> 'email'));

-- Auth callback inserts new users on first sign-in
-- (service_role bypasses RLS, but if your callback uses
--  the user's session, this policy allows it)
CREATE POLICY "users_insert_self" ON public.users
  FOR INSERT TO authenticated
  WITH CHECK (email = (auth.jwt() ->> 'email'));

-- ============================================================
-- 3. Organizations
-- ============================================================
ALTER TABLE public.organizations ENABLE ROW LEVEL SECURITY;

CREATE POLICY "orgs_select_own" ON public.organizations
  FOR SELECT TO authenticated
  USING (id = user_org_id());

-- ============================================================
-- 4. Org-scoped tables
--    Standard pattern: organization_id = user_org_id()
-- ============================================================

-- ── companies ──
ALTER TABLE public.companies ENABLE ROW LEVEL SECURITY;
CREATE POLICY "companies_select" ON public.companies FOR SELECT TO authenticated USING (organization_id = user_org_id());
CREATE POLICY "companies_insert" ON public.companies FOR INSERT TO authenticated WITH CHECK (organization_id = user_org_id());
CREATE POLICY "companies_update" ON public.companies FOR UPDATE TO authenticated USING (organization_id = user_org_id()) WITH CHECK (organization_id = user_org_id());
CREATE POLICY "companies_delete" ON public.companies FOR DELETE TO authenticated USING (organization_id = user_org_id());

-- ── funds ──
ALTER TABLE public.funds ENABLE ROW LEVEL SECURITY;
CREATE POLICY "funds_select" ON public.funds FOR SELECT TO authenticated USING (organization_id = user_org_id());
CREATE POLICY "funds_insert" ON public.funds FOR INSERT TO authenticated WITH CHECK (organization_id = user_org_id());
CREATE POLICY "funds_update" ON public.funds FOR UPDATE TO authenticated USING (organization_id = user_org_id()) WITH CHECK (organization_id = user_org_id());
CREATE POLICY "funds_delete" ON public.funds FOR DELETE TO authenticated USING (organization_id = user_org_id());

-- ── limited_partners ──
ALTER TABLE public.limited_partners ENABLE ROW LEVEL SECURITY;
CREATE POLICY "lps_select" ON public.limited_partners FOR SELECT TO authenticated USING (organization_id = user_org_id());
CREATE POLICY "lps_insert" ON public.limited_partners FOR INSERT TO authenticated WITH CHECK (organization_id = user_org_id());
CREATE POLICY "lps_update" ON public.limited_partners FOR UPDATE TO authenticated USING (organization_id = user_org_id()) WITH CHECK (organization_id = user_org_id());
CREATE POLICY "lps_delete" ON public.limited_partners FOR DELETE TO authenticated USING (organization_id = user_org_id());

-- ── investments ──
ALTER TABLE public.investments ENABLE ROW LEVEL SECURITY;
CREATE POLICY "investments_select" ON public.investments FOR SELECT TO authenticated USING (organization_id = user_org_id());
CREATE POLICY "investments_insert" ON public.investments FOR INSERT TO authenticated WITH CHECK (organization_id = user_org_id());
CREATE POLICY "investments_update" ON public.investments FOR UPDATE TO authenticated USING (organization_id = user_org_id()) WITH CHECK (organization_id = user_org_id());
CREATE POLICY "investments_delete" ON public.investments FOR DELETE TO authenticated USING (organization_id = user_org_id());

-- ── company_metrics ──
ALTER TABLE public.company_metrics ENABLE ROW LEVEL SECURITY;
CREATE POLICY "company_metrics_select" ON public.company_metrics FOR SELECT TO authenticated USING (organization_id = user_org_id());
CREATE POLICY "company_metrics_insert" ON public.company_metrics FOR INSERT TO authenticated WITH CHECK (organization_id = user_org_id());
CREATE POLICY "company_metrics_update" ON public.company_metrics FOR UPDATE TO authenticated USING (organization_id = user_org_id()) WITH CHECK (organization_id = user_org_id());

-- ── company_metrics_history (scoped via company join, has fund_id) ──
-- No organization_id column — scope through company_id
ALTER TABLE public.company_metrics_history ENABLE ROW LEVEL SECURITY;
CREATE POLICY "co_metrics_hist_select" ON public.company_metrics_history FOR SELECT TO authenticated
  USING (EXISTS (SELECT 1 FROM public.companies c WHERE c.id = company_id AND c.organization_id = user_org_id()));
CREATE POLICY "co_metrics_hist_insert" ON public.company_metrics_history FOR INSERT TO authenticated
  WITH CHECK (EXISTS (SELECT 1 FROM public.companies c WHERE c.id = company_id AND c.organization_id = user_org_id()));

-- ── company_valuations ──
ALTER TABLE public.company_valuations ENABLE ROW LEVEL SECURITY;
CREATE POLICY "company_valuations_select" ON public.company_valuations FOR SELECT TO authenticated USING (organization_id = user_org_id());
CREATE POLICY "company_valuations_insert" ON public.company_valuations FOR INSERT TO authenticated WITH CHECK (organization_id = user_org_id());
CREATE POLICY "company_valuations_update" ON public.company_valuations FOR UPDATE TO authenticated USING (organization_id = user_org_id()) WITH CHECK (organization_id = user_org_id());

-- ── company_updates ──
ALTER TABLE public.company_updates ENABLE ROW LEVEL SECURITY;
CREATE POLICY "company_updates_select" ON public.company_updates FOR SELECT TO authenticated USING (organization_id = user_org_id());
CREATE POLICY "company_updates_insert" ON public.company_updates FOR INSERT TO authenticated WITH CHECK (organization_id = user_org_id());
CREATE POLICY "company_updates_update" ON public.company_updates FOR UPDATE TO authenticated USING (organization_id = user_org_id()) WITH CHECK (organization_id = user_org_id());

-- ── deals ──
ALTER TABLE public.deals ENABLE ROW LEVEL SECURITY;
CREATE POLICY "deals_select" ON public.deals FOR SELECT TO authenticated USING (organization_id = user_org_id());
CREATE POLICY "deals_insert" ON public.deals FOR INSERT TO authenticated WITH CHECK (organization_id = user_org_id());
CREATE POLICY "deals_update" ON public.deals FOR UPDATE TO authenticated USING (organization_id = user_org_id()) WITH CHECK (organization_id = user_org_id());
CREATE POLICY "deals_delete" ON public.deals FOR DELETE TO authenticated USING (organization_id = user_org_id());

-- ── deal_sources ──
ALTER TABLE public.deal_sources ENABLE ROW LEVEL SECURITY;
CREATE POLICY "deal_sources_select" ON public.deal_sources FOR SELECT TO authenticated USING (organization_id = user_org_id());
CREATE POLICY "deal_sources_insert" ON public.deal_sources FOR INSERT TO authenticated WITH CHECK (organization_id = user_org_id());
CREATE POLICY "deal_sources_update" ON public.deal_sources FOR UPDATE TO authenticated USING (organization_id = user_org_id()) WITH CHECK (organization_id = user_org_id());

-- ── deal_documents (no org_id — scope through organization_id if present, else open for now) ──
-- deal_documents has organization_id
ALTER TABLE public.deal_documents ENABLE ROW LEVEL SECURITY;
CREATE POLICY "deal_docs_select" ON public.deal_documents FOR SELECT TO authenticated USING (organization_id = user_org_id());
CREATE POLICY "deal_docs_insert" ON public.deal_documents FOR INSERT TO authenticated WITH CHECK (organization_id = user_org_id());

-- ── lp_commitments ──
ALTER TABLE public.lp_commitments ENABLE ROW LEVEL SECURITY;
CREATE POLICY "lp_commitments_select" ON public.lp_commitments FOR SELECT TO authenticated USING (organization_id = user_org_id());
CREATE POLICY "lp_commitments_insert" ON public.lp_commitments FOR INSERT TO authenticated WITH CHECK (organization_id = user_org_id());
CREATE POLICY "lp_commitments_update" ON public.lp_commitments FOR UPDATE TO authenticated USING (organization_id = user_org_id()) WITH CHECK (organization_id = user_org_id());

-- ── kyc_records ──
ALTER TABLE public.kyc_records ENABLE ROW LEVEL SECURITY;
CREATE POLICY "kyc_records_select" ON public.kyc_records FOR SELECT TO authenticated USING (organization_id = user_org_id());
CREATE POLICY "kyc_records_insert" ON public.kyc_records FOR INSERT TO authenticated WITH CHECK (organization_id = user_org_id());
CREATE POLICY "kyc_records_update" ON public.kyc_records FOR UPDATE TO authenticated USING (organization_id = user_org_id()) WITH CHECK (organization_id = user_org_id());

-- ── investor_updates ──
ALTER TABLE public.investor_updates ENABLE ROW LEVEL SECURITY;
CREATE POLICY "investor_updates_select" ON public.investor_updates FOR SELECT TO authenticated USING (organization_id = user_org_id());
CREATE POLICY "investor_updates_insert" ON public.investor_updates FOR INSERT TO authenticated WITH CHECK (organization_id = user_org_id());
CREATE POLICY "investor_updates_update" ON public.investor_updates FOR UPDATE TO authenticated USING (organization_id = user_org_id()) WITH CHECK (organization_id = user_org_id());

-- ── cap_table_entries ──
ALTER TABLE public.cap_table_entries ENABLE ROW LEVEL SECURITY;
CREATE POLICY "cap_table_select" ON public.cap_table_entries FOR SELECT TO authenticated USING (organization_id = user_org_id());
CREATE POLICY "cap_table_insert" ON public.cap_table_entries FOR INSERT TO authenticated WITH CHECK (organization_id = user_org_id());
CREATE POLICY "cap_table_update" ON public.cap_table_entries FOR UPDATE TO authenticated USING (organization_id = user_org_id()) WITH CHECK (organization_id = user_org_id());

-- ── benchmark_data ──
ALTER TABLE public.benchmark_data ENABLE ROW LEVEL SECURITY;
CREATE POLICY "benchmark_data_select" ON public.benchmark_data FOR SELECT TO authenticated USING (organization_id = user_org_id());
CREATE POLICY "benchmark_data_insert" ON public.benchmark_data FOR INSERT TO authenticated WITH CHECK (organization_id = user_org_id());

-- ── data_quality_log ──
ALTER TABLE public.data_quality_log ENABLE ROW LEVEL SECURITY;
CREATE POLICY "data_quality_select" ON public.data_quality_log FOR SELECT TO authenticated USING (organization_id = user_org_id());
CREATE POLICY "data_quality_insert" ON public.data_quality_log FOR INSERT TO authenticated WITH CHECK (organization_id = user_org_id());

-- ── fund_entities ──
ALTER TABLE public.fund_entities ENABLE ROW LEVEL SECURITY;
CREATE POLICY "fund_entities_select" ON public.fund_entities FOR SELECT TO authenticated USING (organization_id = user_org_id());
CREATE POLICY "fund_entities_insert" ON public.fund_entities FOR INSERT TO authenticated WITH CHECK (organization_id = user_org_id());
CREATE POLICY "fund_entities_update" ON public.fund_entities FOR UPDATE TO authenticated USING (organization_id = user_org_id()) WITH CHECK (organization_id = user_org_id());

-- ── fund_admin_accounts ──
ALTER TABLE public.fund_admin_accounts ENABLE ROW LEVEL SECURITY;
CREATE POLICY "fund_admin_accounts_select" ON public.fund_admin_accounts FOR SELECT TO authenticated USING (organization_id = user_org_id());
CREATE POLICY "fund_admin_accounts_insert" ON public.fund_admin_accounts FOR INSERT TO authenticated WITH CHECK (organization_id = user_org_id());

-- ── fund_pacing_snapshots ──
ALTER TABLE public.fund_pacing_snapshots ENABLE ROW LEVEL SECURITY;
CREATE POLICY "fund_pacing_select" ON public.fund_pacing_snapshots FOR SELECT TO authenticated USING (organization_id = user_org_id());
CREATE POLICY "fund_pacing_insert" ON public.fund_pacing_snapshots FOR INSERT TO authenticated WITH CHECK (organization_id = user_org_id());

-- ── fund_profiles ──
ALTER TABLE public.fund_profiles ENABLE ROW LEVEL SECURITY;
CREATE POLICY "fund_profiles_select" ON public.fund_profiles FOR SELECT TO authenticated USING (organization_id = user_org_id());
CREATE POLICY "fund_profiles_insert" ON public.fund_profiles FOR INSERT TO authenticated WITH CHECK (organization_id = user_org_id());
CREATE POLICY "fund_profiles_update" ON public.fund_profiles FOR UPDATE TO authenticated USING (organization_id = user_org_id()) WITH CHECK (organization_id = user_org_id());

-- ── management_companies ──
ALTER TABLE public.management_companies ENABLE ROW LEVEL SECURITY;
CREATE POLICY "mgmt_companies_select" ON public.management_companies FOR SELECT TO authenticated USING (organization_id = user_org_id());
CREATE POLICY "mgmt_companies_insert" ON public.management_companies FOR INSERT TO authenticated WITH CHECK (organization_id = user_org_id());

-- ── market_maps ──
ALTER TABLE public.market_maps ENABLE ROW LEVEL SECURITY;
CREATE POLICY "market_maps_select" ON public.market_maps FOR SELECT TO authenticated USING (organization_id = user_org_id());
CREATE POLICY "market_maps_insert" ON public.market_maps FOR INSERT TO authenticated WITH CHECK (organization_id = user_org_id());

-- ── market_updates ──
ALTER TABLE public.market_updates ENABLE ROW LEVEL SECURITY;
CREATE POLICY "market_updates_select" ON public.market_updates FOR SELECT TO authenticated USING (organization_id = user_org_id());
CREATE POLICY "market_updates_insert" ON public.market_updates FOR INSERT TO authenticated WITH CHECK (organization_id = user_org_id());

-- ── annex5_reports ──
ALTER TABLE public.annex5_reports ENABLE ROW LEVEL SECURITY;
CREATE POLICY "annex5_select" ON public.annex5_reports FOR SELECT TO authenticated USING (organization_id = user_org_id());
CREATE POLICY "annex5_insert" ON public.annex5_reports FOR INSERT TO authenticated WITH CHECK (organization_id = user_org_id());

-- ── founder_outreach ──
ALTER TABLE public.founder_outreach ENABLE ROW LEVEL SECURITY;
CREATE POLICY "founder_outreach_select" ON public.founder_outreach FOR SELECT TO authenticated USING (organization_id = user_org_id());
CREATE POLICY "founder_outreach_insert" ON public.founder_outreach FOR INSERT TO authenticated WITH CHECK (organization_id = user_org_id());
CREATE POLICY "founder_outreach_update" ON public.founder_outreach FOR UPDATE TO authenticated USING (organization_id = user_org_id()) WITH CHECK (organization_id = user_org_id());

-- ── funding_rounds (no org_id — scope through company) ──
ALTER TABLE public.funding_rounds ENABLE ROW LEVEL SECURITY;
CREATE POLICY "funding_rounds_select" ON public.funding_rounds FOR SELECT TO authenticated
  USING (EXISTS (SELECT 1 FROM public.companies c WHERE c.id = company_id AND c.organization_id = user_org_id()));
CREATE POLICY "funding_rounds_insert" ON public.funding_rounds FOR INSERT TO authenticated
  WITH CHECK (EXISTS (SELECT 1 FROM public.companies c WHERE c.id = company_id AND c.organization_id = user_org_id()));

-- ── accepted_suggestions (no org_id — scope through fund) ──
ALTER TABLE public.accepted_suggestions ENABLE ROW LEVEL SECURITY;
CREATE POLICY "accepted_suggestions_select" ON public.accepted_suggestions FOR SELECT TO authenticated
  USING (EXISTS (SELECT 1 FROM public.funds f WHERE f.id = fund_id AND f.organization_id = user_org_id()));
CREATE POLICY "accepted_suggestions_insert" ON public.accepted_suggestions FOR INSERT TO authenticated
  WITH CHECK (EXISTS (SELECT 1 FROM public.funds f WHERE f.id = fund_id AND f.organization_id = user_org_id()));

-- ── batch_valuation_jobs (scope through fund) ──
ALTER TABLE public.batch_valuation_jobs ENABLE ROW LEVEL SECURITY;
CREATE POLICY "batch_val_select" ON public.batch_valuation_jobs FOR SELECT TO authenticated
  USING (EXISTS (SELECT 1 FROM public.funds f WHERE f.id = fund_id AND f.organization_id = user_org_id()));
CREATE POLICY "batch_val_insert" ON public.batch_valuation_jobs FOR INSERT TO authenticated
  WITH CHECK (EXISTS (SELECT 1 FROM public.funds f WHERE f.id = fund_id AND f.organization_id = user_org_id()));

-- ── matrix_columns (scope through fund) ──
ALTER TABLE public.matrix_columns ENABLE ROW LEVEL SECURITY;
CREATE POLICY "matrix_columns_select" ON public.matrix_columns FOR SELECT TO authenticated
  USING (fund_id IS NULL OR EXISTS (SELECT 1 FROM public.funds f WHERE f.id = fund_id AND f.organization_id = user_org_id()));
CREATE POLICY "matrix_columns_insert" ON public.matrix_columns FOR INSERT TO authenticated
  WITH CHECK (fund_id IS NULL OR EXISTS (SELECT 1 FROM public.funds f WHERE f.id = fund_id AND f.organization_id = user_org_id()));
CREATE POLICY "matrix_columns_update" ON public.matrix_columns FOR UPDATE TO authenticated
  USING (fund_id IS NULL OR EXISTS (SELECT 1 FROM public.funds f WHERE f.id = fund_id AND f.organization_id = user_org_id()));

-- ── fpa_models (scope through fund) ──
ALTER TABLE public.fpa_models ENABLE ROW LEVEL SECURITY;
CREATE POLICY "fpa_models_select" ON public.fpa_models FOR SELECT TO authenticated
  USING (fund_id IS NULL OR EXISTS (SELECT 1 FROM public.funds f WHERE f.id = fund_id AND f.organization_id = user_org_id()));
CREATE POLICY "fpa_models_insert" ON public.fpa_models FOR INSERT TO authenticated
  WITH CHECK (fund_id IS NULL OR EXISTS (SELECT 1 FROM public.funds f WHERE f.id = fund_id AND f.organization_id = user_org_id()));

-- ── fpa_model_versions (scope through model -> fund) ──
ALTER TABLE public.fpa_model_versions ENABLE ROW LEVEL SECURITY;
CREATE POLICY "fpa_versions_select" ON public.fpa_model_versions FOR SELECT TO authenticated
  USING (EXISTS (
    SELECT 1 FROM public.fpa_models m
    LEFT JOIN public.funds f ON f.id = m.fund_id
    WHERE m.id = model_id AND (m.fund_id IS NULL OR f.organization_id = user_org_id())
  ));

-- ── fpa_queries (scope through fund) ──
ALTER TABLE public.fpa_queries ENABLE ROW LEVEL SECURITY;
CREATE POLICY "fpa_queries_select" ON public.fpa_queries FOR SELECT TO authenticated
  USING (fund_id IS NULL OR EXISTS (SELECT 1 FROM public.funds f WHERE f.id = fund_id AND f.organization_id = user_org_id()));

-- ── investment_thesis (scope through company) ──
ALTER TABLE public.investment_thesis ENABLE ROW LEVEL SECURITY;
CREATE POLICY "inv_thesis_select" ON public.investment_thesis FOR SELECT TO authenticated
  USING (EXISTS (SELECT 1 FROM public.companies c WHERE c.id = company_id AND c.organization_id = user_org_id()));
CREATE POLICY "inv_thesis_insert" ON public.investment_thesis FOR INSERT TO authenticated
  WITH CHECK (EXISTS (SELECT 1 FROM public.companies c WHERE c.id = company_id AND c.organization_id = user_org_id()));

-- ============================================================
-- 5. Global / shared tables — authenticated read-only
-- ============================================================
ALTER TABLE public.market_data ENABLE ROW LEVEL SECURITY;
CREATE POLICY "market_data_read" ON public.market_data FOR SELECT TO authenticated USING (true);

ALTER TABLE public.data_sources ENABLE ROW LEVEL SECURITY;
CREATE POLICY "data_sources_read" ON public.data_sources FOR SELECT TO authenticated USING (true);

ALTER TABLE public.cell_action_registry ENABLE ROW LEVEL SECURITY;
CREATE POLICY "cell_action_registry_read" ON public.cell_action_registry FOR SELECT TO authenticated USING (true);

ALTER TABLE public.cell_action_presets ENABLE ROW LEVEL SECURITY;
CREATE POLICY "cell_action_presets_read" ON public.cell_action_presets FOR SELECT TO authenticated USING (true);

ALTER TABLE public.company_profiles ENABLE ROW LEVEL SECURITY;
CREATE POLICY "company_profiles_read" ON public.company_profiles FOR SELECT TO authenticated USING (true);

-- ============================================================
-- 6. Agent/ML tables — no user data, open to authenticated
--    (or disable RLS if only backend service role accesses them)
-- ============================================================
-- These tables are only written by the backend (service_role),
-- so RLS doesn't affect writes. Open reads for dashboard display.

ALTER TABLE public.agent_interactions ENABLE ROW LEVEL SECURITY;
CREATE POLICY "agent_interactions_read" ON public.agent_interactions FOR SELECT TO authenticated USING (true);

ALTER TABLE public.agent_cost_tracking ENABLE ROW LEVEL SECURITY;
CREATE POLICY "agent_cost_read" ON public.agent_cost_tracking FOR SELECT TO authenticated USING (true);

-- Other agent tables (agent_experiences, agent_states, agent_knowledge_base,
-- agent_patterns, agent_feedback_history, agent_learning_records,
-- agent_retraining_queue, agent_vision_cache, experience_replay,
-- ephemeral_graphs) are backend-only. Service role bypasses RLS.
-- Enable RLS with no policies = deny all non-service-role access:

ALTER TABLE public.agent_experiences ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.agent_states ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.agent_knowledge_base ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.agent_patterns ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.agent_feedback_history ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.agent_learning_records ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.agent_retraining_queue ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.agent_vision_cache ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.experience_replay ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.ephemeral_graphs ENABLE ROW LEVEL SECURITY;

COMMIT;

-- ============================================================
-- POST-MIGRATION NOTES
-- ============================================================
-- 1. Service role key (SUPABASE_SERVICE_ROLE_KEY) bypasses ALL RLS.
--    Your backend API routes and auth callback use this — no changes needed.
--
-- 2. The anon key + user JWT enforces these policies.
--    Browser clients (getSupabaseBrowser()) will be restricted.
--
-- 3. If a user has no organization_id, user_org_id() returns NULL
--    and org-scoped queries return zero rows. This is intentional —
--    you must assign an org when creating the user.
--
-- 4. To test: sign in, then run in the SQL editor:
--    SELECT user_org_id();
--    SELECT * FROM companies LIMIT 5;
--    If you get rows, RLS is working. If not, check the user's org.
