-- Accepted legal clauses extracted from contracts, term sheets, vendor agreements, etc.
-- Source of truth for legal mode grid. Populated when user accepts clause suggestions
-- from pending_suggestions (column_id LIKE 'legal:%').
-- One row per clause per document per company.

CREATE TABLE IF NOT EXISTS document_clauses (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  fund_id UUID NOT NULL REFERENCES funds(id) ON DELETE CASCADE,
  company_id UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
  document_id TEXT,                                    -- FK to processed_documents.id (text for flexibility)
  document_name TEXT,                                  -- Human-readable source doc name

  -- Clause identity
  clause_id TEXT NOT NULL,                             -- Hierarchical ID: "4", "4.1", "4.1.a"
  title TEXT,
  clause_type TEXT NOT NULL DEFAULT 'other',           -- termination, auto_renewal, liability_cap, ip_assignment, etc.
  clause_text TEXT,                                    -- Verbatim extracted text (up to 500 chars)

  -- Parties & obligations
  party TEXT,                                          -- Counterparty name
  flags TEXT[],                                        -- Array: unfavorable, above_market, non_standard, auto_renew_risk, missing, material, favorable
  obligation_desc TEXT,
  obligation_deadline DATE,

  -- Cross-references to financial services
  cross_ref_service TEXT,                              -- cap_table, waterfall, pnl, cash_flow
  cross_ref_field TEXT,
  cross_ref_value TEXT,

  -- ERP attribution
  erp_category TEXT,                                   -- cogs, opex_rd, opex_sm, opex_ga
  erp_subcategory TEXT,
  annual_value NUMERIC,
  monthly_amount NUMERIC,

  -- Reasoning & provenance
  reasoning TEXT,                                      -- Evidence chain: quote → flags → impact
  confidence NUMERIC DEFAULT 0.8,
  source_service TEXT,                                 -- e.g. "document:123"
  suggestion_id UUID,                                  -- Original pending_suggestion ID for audit trail
  metadata JSONB,                                      -- Overflow: all_obligations, all_cross_references, parent/child clause IDs

  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),

  -- One clause per document per company (re-extraction replaces)
  UNIQUE(fund_id, company_id, clause_id, document_id)
);

CREATE INDEX IF NOT EXISTS idx_document_clauses_fund ON document_clauses(fund_id);
CREATE INDEX IF NOT EXISTS idx_document_clauses_company ON document_clauses(company_id);
CREATE INDEX IF NOT EXISTS idx_document_clauses_type ON document_clauses(clause_type);
CREATE INDEX IF NOT EXISTS idx_document_clauses_document ON document_clauses(document_id);
CREATE INDEX IF NOT EXISTS idx_document_clauses_flags ON document_clauses USING GIN(flags);

ALTER TABLE document_clauses ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Allow read document_clauses" ON document_clauses FOR SELECT USING (true);
CREATE POLICY "Allow insert document_clauses" ON document_clauses FOR INSERT WITH CHECK (true);
CREATE POLICY "Allow update document_clauses" ON document_clauses FOR UPDATE USING (true) WITH CHECK (true);
CREATE POLICY "Allow delete document_clauses" ON document_clauses FOR DELETE USING (true);

COMMENT ON TABLE document_clauses IS 'Accepted legal clauses from contract extraction. Source of truth for legal mode grid. Populated via suggestion accept flow.';
