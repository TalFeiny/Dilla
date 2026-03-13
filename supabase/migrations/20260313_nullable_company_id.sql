-- Phase 1: Remove hard company_id requirement from tables that gate the
-- document-processing pipeline.  When company_id is unknown the app writes a
-- sentinel UUID (all zeros) so existing unique constraints / ON CONFLICT
-- upserts keep working unchanged.

ALTER TABLE pending_suggestions ALTER COLUMN company_id DROP NOT NULL;
ALTER TABLE fpa_actuals ALTER COLUMN company_id DROP NOT NULL;
ALTER TABLE document_clauses ALTER COLUMN company_id DROP NOT NULL;

-- Phase 2: Tables also reached by the document pipeline via cap-table and
-- contract-pnl bridges.  Same sentinel strategy.

ALTER TABLE company_cap_tables ALTER COLUMN company_id DROP NOT NULL;
ALTER TABLE ic_transaction_suggestions ALTER COLUMN company_id DROP NOT NULL;
