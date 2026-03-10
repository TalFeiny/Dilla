
# Contract Intelligence System — Plan

## Context

Dilla AI has a robust document extraction pipeline (`document_process_service.py`) with 7 doc types, citation tracking, cap table auto-population, and deal analysis. Contracts are the legal backbone of everything — cap tables come from SHAs, deal terms from SPAs, obligations from loan agreements, transfer pricing from intercompany agreements.

**This is company-facing.** Investors have legal teams. Companies don't. This tool gives companies the legal visibility they'd otherwise need expensive lawyers for — "what do our agreements actually say vs what we've modeled."

**Clause extraction is the universal foundation.** Everything — routing, reconciliation, drafting, multi-contract intelligence — depends on being able to read any contract and pull structured clauses with solid attribution. Nail this first.

---

## Contract Type Taxonomy & Parent Relationships

Not all contracts live in the same place. The parent relationship determines which mode owns the contract and what it reconciles against.

### FPA/ERP modes (existing infrastructure)
These are financial/transactional documents. They tie to P&L line items via subcategory/ERP code parent-child relationships.

- **Vendor contracts** → parent: subcategory + ERP code (expense side)
- **Client/customer contracts** → parent: subcategory + ERP code (revenue side)

### New "Documents" mode
These are legal/structural documents. They define the company's equity position, corporate structure, and regulatory obligations.

**Cap table / Equity:**
- SHA → cap table (ownership, share classes, rights)
- SPA → cap table (transaction terms, pricing)
- Term sheets → cap table (proposed terms)
- Option agreements → cap table (option pool, vesting)
- Warrant agreements → cap table
- Side letters → cap table (override terms for specific investors)
- SPV docs → cap table (rolled-up investor structures)
- Pro rata agreements → cap table (follow-on rights, capacity)
- Convertible notes → cap table (conversion terms, cap, discount, maturity)
- SAFEs / ASAs → cap table (conversion triggers, valuation caps)
- Subscription agreements → cap table (investor commitments, share allotment)
- Articles of association / bylaws / charter → cap table (share class definitions, voting rights, foundational governance)
- Shareholder resolutions → cap table (structural changes, approvals)

**Debt / Financial obligations:**
- Loan agreements → FPA (payment obligations, covenants)
- Credit facilities → FPA (available credit, drawdown terms)
- Lease agreements → FPA (recurring obligations by entity/location)
- Personal guarantees → FPA + risk (founder/director exposure, contingent liability)
- Parent company guarantees → FPA + risk (group exposure)
- Security/pledge agreements → FPA (collateral, encumbered assets)
- Debentures → FPA (debt instruments, fixed/floating charges)
- Shareholder loans → FPA + TP (related party lending, interest terms)

**M&A / Deal:**
- Escrow agreements → deal (earnout holdbacks, release conditions)
- Letters of intent / MOUs → deal (pre-contractual obligations, exclusivity periods)
- Joint venture agreements → deal (profit-sharing, governance, exit terms)

**Corporate / Structural:**
- Employment contracts → parent: entity/department
- Service agreements → parent: entity
- Management agreements → parent: entity (related party service arrangements)
- IP assignments/licenses → parent: entity
- Board resolutions → parent: entity
- Insurance policies → parent: entity

**Tax / Regulatory / TP:**
- Intercompany agreements → parent: entity pair → TP engine
- Tax opinions/rulings → parent: entity/jurisdiction
- Regulatory filings → parent: entity/jurisdiction
- Data processing agreements (DPAs) → parent: entity (GDPR, privacy obligations)
- Settlement agreements → parent: entity (litigation outcomes, financial obligations)
- Consent orders → parent: entity (regulatory obligations)

---

## Phase 1: Universal Clause Extraction (THE FOUNDATION)

Everything depends on this. Get extraction, reasoning, and attribution right before building anything on top.

### 1a. `CONTRACT_CLAUSE_SCHEMA` in `document_process_service.py`

One schema that handles any contract type:

```python
CONTRACT_CLAUSE_SCHEMA = {
    "document_metadata": {
        "contract_type": "string — LLM-classified from document content. Guidance types include: sha, spa, term_sheet, warrant_agreement, option_agreement, convertible_note, safe, asa, subscription_agreement, articles_of_association, bylaws, charter, shareholder_resolution, side_letter, spv_agreement, pro_rata_agreement, loan_agreement, credit_facility, lease, personal_guarantee, parent_guarantee, security_agreement, pledge_agreement, debenture, shareholder_loan, escrow_agreement, letter_of_intent, mou, joint_venture, nda, employment, service_agreement, management_agreement, vendor_agreement, client_agreement, ip_license, insurance_policy, board_resolution, intercompany_agreement, tax_opinion, dpa, settlement_agreement, consent_order, engagement_letter — but NOT exhaustive. Use best judgment for any legal document.",
        "parties": "array of {name, role}",
        "effective_date": "ISO date or null",
        "expiry_date": "ISO date or null",
        "governing_law": "string or null (jurisdiction)",
        "entity": "string or null (which company entity this belongs to)",
        "summary": "string (2-3 sentence overview)"
    },
    "clauses": "array of clause objects (see below)",
    "clause_object_schema": {
        "clause_type": "string (termination, liability_cap, indemnification, non_compete, non_solicitation, change_of_control, drag_along, tag_along, anti_dilution, liquidation_preference, vesting, ip_assignment, confidentiality, exclusivity, earn_out, warranty, covenant, representations, governing_law, dispute_resolution, force_majeure, assignment, option_pool, pro_rata, information_rights, board_composition, founder_lockup, transfer_restriction, intercompany_pricing, payment_terms, renewal, sla, data_protection, spv_structure, tax_treatment, regulatory_compliance, conversion_terms, valuation_cap, discount_rate, maturity, interest_rate, collateral, guarantee_scope, guarantee_trigger, escrow_release, escrow_conditions, exclusivity_period, profit_sharing, exit_mechanism, consent_threshold, voting_rights, share_class_rights, preemptive_rights, redemption_rights, dividend_rights, put_option, call_option, tag_along, drag_along, deadlock_resolution, non_compete_scope, data_processing_scope, data_retention, breach_notification, settlement_terms, regulatory_obligation, other)",
        "clause_text": "string (verbatim or close paraphrase)",
        "section_reference": "string (e.g. 'Section 4.2', 'Clause 7(b)', 'Schedule 3')",
        "risk_level": "string (high, medium, low)",
        "risk_reasoning": "string — WHY this risk level, not just the label",
        "financial_impact": {
            "amount": "number or null (USD)",
            "type": "string (liability_cap, penalty, earn_out, payment_obligation, etc.)",
            "recurring": "boolean",
            "period": "string or null (monthly, annually, one-time)"
        },
        "obligations": "array of {party, obligation, deadline}",
        "red_flags": "array of strings",
        "source_quote": "string — verbatim quote from document"
    },
    "key_dates": "array of {date, event, clause_reference}",
    "financial_terms": {
        "total_value": "number or null",
        "payment_schedule": "string or null",
        "penalties": "array of {trigger, amount}"
    }
}
```

### 1b. `_contract_prompt()` in `document_process_service.py`

New prompt function following existing pattern (`_signal_first_prompt()`, `_memo_prompt()`, etc.):

- System role: "Expert legal analyst and contract intelligence engine"
- Extract every material clause with verbatim quotes and section references
- Risk flagging with reasoning (not just high/medium/low — explain why)
- Financial implications for every relevant clause
- Attribution: every extracted item MUST have `section_reference` and `source_quote`
- Handle all contract types listed in the taxonomy

### 1c. Extraction router — contract as catch-all

Instead of hardcoding every contract type, treat `contract` / `legal` as a **catch-all**. Any document that isn't one of the existing 7 types routes through clause extraction. The LLM classifies the specific contract type from the document content itself.

```python
# After all existing doc type branches...
else:
    # Universal contract/legal document extraction
    # The LLM determines contract_type from the document content
    schema_desc = json.dumps(CONTRACT_CLAUSE_SCHEMA, indent=2)
    system_prompt, user_prompt = _contract_prompt(text, doc_type, schema_desc)
    empty = _empty_contract_extraction()
```

The `contract_type` field in the schema is an open classification — the LLM reads the document and determines what it is. The taxonomy list in the schema is **guidance, not exhaustive**. The prompt tells the LLM: "Classify the contract type. Common types include [list], but use your judgment for any legal document."

This means the system can handle any contract type without code changes — new types just appear in the data.

### 1d. `document_clauses` table

```sql
CREATE TABLE document_clauses (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID NOT NULL REFERENCES processed_documents(id) ON DELETE CASCADE,
    company_id UUID REFERENCES companies(id),
    fund_id UUID REFERENCES funds(id),
    clause_type TEXT NOT NULL,
    clause_text TEXT NOT NULL,
    section_reference TEXT,
    risk_level TEXT CHECK (risk_level IN ('high', 'medium', 'low')),
    risk_reasoning TEXT,
    financial_impact JSONB,
    obligations JSONB,
    red_flags TEXT[],
    source_quote TEXT,
    parent_type TEXT,        -- 'cap_table', 'fpa', 'tp', 'entity', 'erp_code'
    parent_id UUID,          -- FK to the relevant parent record
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_document_clauses_company ON document_clauses(company_id);
CREATE INDEX idx_document_clauses_type ON document_clauses(clause_type);
CREATE INDEX idx_document_clauses_risk ON document_clauses(risk_level);
CREATE INDEX idx_document_clauses_document ON document_clauses(document_id);
CREATE INDEX idx_document_clauses_parent ON document_clauses(parent_type, parent_id);
```

### 1e. Post-extraction clause persistence

After extraction in `run_document_process()`, persist individual clauses as rows. Each clause gets:
- `document_id`, `company_id` from the processed document
- `parent_type` + `parent_id` determined by contract type (vendor → erp_code, SHA → cap_table entry, intercompany → TP entity pair)
- All clause fields from the extraction

### Files to modify (Phase 1):
- `backend/app/services/document_process_service.py` — schema, prompt, router branch, post-extraction persistence
- `backend/app/api/endpoints/documents_process.py` — accept new doc types in validation
- New migration for `document_clauses` table

---

## Phase 2: Parent Routing & Reconciliation

Once extraction works, wire clauses into the right places.

### 2a. FPA routing (vendor/client contracts)
- Vendor contract clauses → link to subcategory/ERP code
- Payment terms, SLAs, renewal dates → surface in FPA views
- Uses existing ERP parent-child relationships

### 2b. Cap table routing (equity docs)
- SHA ownership → reconcile vs `company_cap_tables`
- Option agreements → reconcile vs modeled option pool
- Liquidation preferences → reconcile vs `advanced_cap_table.py`
- SPV structures → reconcile vs cap table investor records
- Pro rata rights → flag capacity for next round
- Side letters → flag overrides to standard SHA terms
- Flag discrepancies as alerts

### 2c. TP routing (intercompany agreements)
- Intercompany pricing terms → feed into `transfer_pricing_engine.py`
- Validate against arm's length via `tp_comparable_service.py`
- Flag documentation gaps for TP compliance

### 2d. Corporate routing (employment, IP, service, tax)
- Link to entity/department
- Surface obligations, deadlines, renewal dates
- Tax treatment clauses → flag compliance implications

### Files to modify (Phase 2):
- `backend/app/services/comprehensive_deal_analyzer.py` — contract risk incorporation
- `backend/app/services/transfer_pricing_engine.py` or `tp_document_service.py` — TP clause integration
- Cap table services — reconciliation checks

---

## Phase 3: New "Documents" Mode

Own mode in the agent router. Own system prompt. Own grid. For all non-FPA contract types.

### 3a. Mode definition
- System prompt: "Document intelligence engine for [company]. Extract, verify, reconcile, draft, flag."
- Tools: clause querying, reconciliation checks, template drafting
- Context: company's existing documents, clause library, cap table state, TP state

### 3b. Frontend grid
- Document list with contract type, parties, risk summary, key dates
- Clause detail view per document (type, section, risk level, financial impact, obligations)
- Risk badges (red/amber/green) with reasoning
- Source attribution: section references + verbatim quotes
- Filters by contract type, risk level, clause type, parent

### 3c. Company-level aggregation
- All clauses across all documents for a company
- Cross-document views: "all change-of-control clauses", "all payment obligations"
- Obligation timeline: what's coming due

---

## Phase 4: Contract Drafting

Templates + company context → generate contracts within the new mode.

### 4a. Template system
- Templates = structured clause blocks with variable slots
- `{{company_name}}`, `{{share_class}}`, `{{vesting_schedule}}`, etc.
- Stored in DB or flat files
- Per contract type: SHA template, option agreement template, NDA template, etc.

### 4b. Drafting tool (MCP tool in the new mode)
- Agent calls `draft_contract(type, params)`
- Pulls template for contract type
- Fills company data from DB (entities, cap table, existing terms)
- References extracted clauses from similar past contracts (clause library)
- Returns draft for review/editing

### 4c. Clause library
- Built from extracted clauses across all processed documents
- "How did we structure the non-compete in our last employment contract?"
- Reference material for drafting, not copy-paste

---

## Phase 5: Multi-Contract Intelligence (ONLY AFTER EXTRACTION IS SOLID)

Cross-document reasoning, conflict detection, reconciliation at scale. This is only possible when extraction + attribution are rock solid.

### 5a. Cross-document conflict detection
- Contradicting terms across agreements (SHA says X, side letter says Y)
- Missing standard protections
- Unusual terms relative to the company's other contracts

### 5b. VDR processing
- Batch upload company pack
- Auto-classify document types
- Cross-document summary: aggregate clauses, flag conflicts, reconstruct cap table from legal docs vs modeled
- Gap analysis: what documents are missing from the pack

### 5c. Obligation aggregation
- Across all contracts: total financial commitments, upcoming deadlines, renewal dates
- Feed into cash flow forecasting
- Alert system for approaching deadlines

### 5d. Reconciliation dashboard
- Cap table: modeled vs what contracts say
- TP: documented vs what intercompany agreements specify
- FPA: forecasted obligations vs contractual obligations
- "Here's where your numbers don't match your contracts"

---

## Implementation Order

| Step | What | Depends On |
|------|------|------------|
| 1 | CONTRACT_CLAUSE_SCHEMA + _contract_prompt() + router branch | Nothing |
| 2 | `document_clauses` table migration | Nothing |
| 3 | Post-extraction clause persistence + parent routing | 1, 2 |
| 4 | Test with sample contracts — verify extraction quality + attribution | 3 |
| 5 | Cap table reconciliation | 3 |
| 6 | TP routing | 3 |
| 7 | FPA routing (vendor/client) | 3 |
| 8 | New mode definition + system prompt | 3 |
| 9 | Frontend grid + clause views | 8 |
| 10 | Template system + drafting tool | 8 |
| 11 | Multi-contract intelligence | 4 proven solid |

**Critical gate: Step 4.** Do not proceed to multi-contract intelligence until extraction quality and attribution are verified against real contracts. Everything downstream depends on this being right.

## Verification

1. Upload sample SHA → verify clauses extracted with correct section references, risk levels with reasoning, and source quotes
2. Upload sample vendor agreement → verify it routes to FPA/ERP parent correctly
3. Upload sample option agreement → verify reconciliation against modeled cap table
4. Upload sample intercompany agreement → verify TP engine receives pricing terms
5. Test drafting: generate an NDA from template + company context
6. Multi-contract: upload 3+ docs for same company → verify cross-document conflict detection
