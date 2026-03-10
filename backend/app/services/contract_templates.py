"""Contract drafting templates — Phase 4 of Contract Intelligence System.

Same blueprint as memo_templates.py:
- title_pattern, required_data, optional_data, sections
- Plus contract-specific: contract_type, template_variables, preamble, governing_law_default

Section types:
- "clause": LLM drafts enforceable legal language (prompt_hint gives guidance)
- "narrative": LLM drafts descriptive text (preamble, signature blocks)
- "redline": LLM generates original + revised versions with reasoning (contract review)
- "table": Data-driven table (risk flags, financial impact)
"""

from typing import Any, Dict, List


def _clause_section(
    key: str,
    heading: str,
    clause_type: str,
    prompt_hint: str = "",
    data_keys: List[str] | None = None,
    risk_level: str = "medium",
    is_standard: bool = True,
) -> Dict[str, Any]:
    """Contract clause section blueprint."""
    return {
        "key": key,
        "heading": heading,
        "type": "clause",
        "clause_type": clause_type,
        "data_keys": data_keys or [],
        "prompt_hint": prompt_hint,
        "risk_level": risk_level,
        "is_standard": is_standard,
    }


def _section(
    key: str,
    heading: str,
    type: str = "narrative",
    data_keys: List[str] | None = None,
    prompt_hint: str = "",
) -> Dict[str, Any]:
    """Standard section helper for non-clause sections."""
    return {
        "key": key,
        "heading": heading,
        "type": type,
        "data_keys": data_keys or [],
        "prompt_hint": prompt_hint,
    }


# ---------------------------------------------------------------------------
# NDA — Non-Disclosure Agreement
# ---------------------------------------------------------------------------
NDA_CONTRACT = {
    "id": "nda",
    "title_pattern": "Non-Disclosure Agreement — {company_name} & {counterparty_name}",
    "contract_type": "nda",
    "required_data": ["company_context"],
    "optional_data": ["counterparty_context"],
    "template_variables": [
        "company_name", "counterparty_name", "effective_date",
        "jurisdiction", "term_months", "company_address",
        "counterparty_address",
    ],
    "preamble": (
        'This Non-Disclosure Agreement ("Agreement") is entered into as of '
        "{{effective_date}} by and between {{company_name}}, a company organized "
        'under the laws of {{jurisdiction}} ("Disclosing Party"), and '
        '{{counterparty_name}} ("Receiving Party").'
    ),
    "governing_law_default": "Delaware",
    "sections": [
        _section("preamble", "Preamble",
                 prompt_hint=(
                     "Recitals: why the parties are entering this NDA. Reference the business "
                     "relationship or potential transaction. Use WHEREAS clauses."
                 )),
        _clause_section("definition", "1. Definition of Confidential Information",
                        clause_type="confidentiality",
                        prompt_hint=(
                            "Define 'Confidential Information' broadly to cover: technical data, trade secrets, "
                            "business plans, financial information, customer lists, proprietary software, algorithms, "
                            "know-how, and any information marked as confidential or reasonably understood to be confidential. "
                            "Exclude: (a) publicly available information, (b) information already known to Receiving Party, "
                            "(c) independently developed information, (d) information received from a third party without "
                            "restriction, (e) information required to be disclosed by law or regulation (with prompt notice)."
                        )),
        _clause_section("obligations", "2. Obligations of Receiving Party",
                        clause_type="confidentiality",
                        prompt_hint=(
                            "Standard obligations: (a) not disclose to any third party without prior written consent, "
                            "(b) use only for the Purpose defined in this Agreement, (c) protect with at least the same "
                            "degree of care as its own confidential information (but no less than reasonable care), "
                            "(d) limit internal access to employees/contractors with need-to-know who are bound by "
                            "confidentiality obligations at least as restrictive as this Agreement, "
                            "(e) promptly notify Disclosing Party of any unauthorized disclosure."
                        )),
        _clause_section("permitted_disclosures", "3. Permitted Disclosures",
                        clause_type="confidentiality",
                        prompt_hint=(
                            "Permitted disclosures: (a) to professional advisors (legal, accounting, financial) under "
                            "duty of confidentiality, (b) as required by law, regulation, or court order — provided "
                            "Receiving Party gives prompt written notice and cooperates with Disclosing Party to seek "
                            "protective order, (c) to affiliates bound by equivalent confidentiality obligations."
                        )),
        _clause_section("term", "4. Term and Termination",
                        clause_type="termination",
                        prompt_hint=(
                            "Agreement effective from {{effective_date}} for a period of {{term_months}} months, "
                            "unless terminated earlier by either party with 30 days written notice. "
                            "Confidentiality obligations survive termination for 2 years (or 5 years for trade secrets). "
                            "Upon termination: return or destroy all Confidential Information and certify destruction in writing."
                        )),
        _clause_section("remedies", "5. Remedies",
                        clause_type="indemnification",
                        prompt_hint=(
                            "Acknowledge that breach may cause irreparable harm for which monetary damages are inadequate. "
                            "Disclosing Party entitled to seek injunctive relief without posting bond, in addition to any "
                            "other remedies available at law or in equity. Prevailing party in any action to enforce this "
                            "Agreement shall recover reasonable attorneys' fees and costs."
                        )),
        _clause_section("no_license", "6. No License or Warranty",
                        clause_type="warranty",
                        prompt_hint=(
                            "No license, express or implied, granted under any patent, copyright, trademark, or trade secret. "
                            "Confidential Information provided 'AS IS' without warranty of any kind. No obligation to enter "
                            "into any further agreement. Either party may terminate discussions at any time without liability."
                        )),
        _clause_section("governing_law", "7. Governing Law & Dispute Resolution",
                        clause_type="governing_law",
                        prompt_hint=(
                            "Governed by and construed in accordance with the laws of {{jurisdiction}}, without regard to "
                            "conflict of law principles. Any dispute arising under this Agreement shall be submitted to the "
                            "exclusive jurisdiction of the courts of {{jurisdiction}}. The parties consent to personal "
                            "jurisdiction and waive any objection to venue."
                        )),
        _clause_section("miscellaneous", "8. General Provisions",
                        clause_type="other",
                        prompt_hint=(
                            "Include: (a) Entire Agreement — supersedes all prior agreements, (b) Amendments — only in writing "
                            "signed by both parties, (c) Severability — invalid provisions severed without affecting remainder, "
                            "(d) Waiver — failure to enforce not a waiver, (e) Assignment — not assignable without consent, "
                            "(f) Counterparts — may be executed in counterparts, (g) Notices — in writing to addresses below."
                        )),
        _section("signature_block", "Signature Block",
                 prompt_hint=(
                     "Signature lines for both parties:\n\n"
                     "{{company_name}}\n"
                     "By: ________________________\n"
                     "Name:\nTitle:\nDate:\n\n"
                     "{{counterparty_name}}\n"
                     "By: ________________________\n"
                     "Name:\nTitle:\nDate:"
                 )),
    ],
}


# ---------------------------------------------------------------------------
# Employment Agreement
# ---------------------------------------------------------------------------
EMPLOYMENT_CONTRACT = {
    "id": "employment",
    "title_pattern": "Employment Agreement — {company_name} & {employee_name}",
    "contract_type": "employment",
    "required_data": ["company_context"],
    "optional_data": ["employee_context", "cap_table_history"],
    "template_variables": [
        "company_name", "employee_name", "position_title", "effective_date",
        "jurisdiction", "base_salary", "company_address", "reporting_to",
        "probation_months", "notice_period_months",
    ],
    "preamble": (
        "This Employment Agreement is entered into as of {{effective_date}} "
        "by and between {{company_name}} (the \"Company\") and {{employee_name}} "
        "(the \"Employee\")."
    ),
    "governing_law_default": "Delaware",
    "sections": [
        _section("preamble", "Preamble",
                 prompt_hint="Recitals: the Company wishes to employ the Employee and the Employee wishes to accept employment."),
        _clause_section("position", "1. Position and Duties",
                        clause_type="other",
                        prompt_hint=(
                            "Employee hired as {{position_title}}, reporting to {{reporting_to}}. "
                            "Full-time position, best efforts and undivided attention. "
                            "Duties may be modified from time to time. Location and remote work terms. "
                            "No outside activities that conflict with duties."
                        )),
        _clause_section("compensation", "2. Compensation",
                        clause_type="payment_terms",
                        prompt_hint=(
                            "Base salary: {{base_salary}} per annum, payable in accordance with Company's standard "
                            "payroll schedule, subject to applicable withholdings. Annual review, no guaranteed increase. "
                            "Discretionary bonus based on individual and Company performance. "
                            "Include equity compensation reference if applicable (separate grant agreement)."
                        ),
                        data_keys=["company_context"]),
        _clause_section("benefits", "3. Benefits",
                        clause_type="other",
                        prompt_hint=(
                            "Eligible for Company benefit plans (health, dental, vision, 401k/pension). "
                            "PTO policy per Company handbook. Expense reimbursement for reasonable business expenses "
                            "with documentation. Benefits subject to plan terms and Company policies."
                        )),
        _clause_section("ip_assignment", "4. Intellectual Property Assignment",
                        clause_type="ip_assignment",
                        risk_level="high",
                        prompt_hint=(
                            "All inventions, discoveries, works of authorship, developments, and improvements conceived "
                            "or created during employment, related to Company business, or using Company resources are "
                            "Work Made for Hire and assigned to Company. Waiver of moral rights. "
                            "Obligation to disclose and assist with IP registration. Survives termination. "
                            "Prior inventions excluded per Schedule A (Employee to list any prior IP)."
                        )),
        _clause_section("confidentiality", "5. Confidentiality",
                        clause_type="confidentiality",
                        prompt_hint=(
                            "Obligation not to disclose or use Company Confidential Information except in performance of duties. "
                            "Survives termination indefinitely for trade secrets, 2 years for other confidential information. "
                            "Return all materials upon termination."
                        )),
        _clause_section("non_compete", "6. Non-Competition and Non-Solicitation",
                        clause_type="non_compete",
                        risk_level="high",
                        prompt_hint=(
                            "Non-compete: {{notice_period_months}} months post-termination, within [geographic scope], "
                            "in the same or substantially similar business. Check {{jurisdiction}} enforceability. "
                            "Non-solicitation of employees and customers: 12 months post-termination. "
                            "Non-disparagement: mutual obligation. "
                            "Note: many jurisdictions limit or ban non-competes — flag if {{jurisdiction}} has restrictions."
                        )),
        _clause_section("termination", "7. Termination",
                        clause_type="termination",
                        prompt_hint=(
                            "Termination by Company for Cause (define: material breach, gross misconduct, conviction, "
                            "failure to perform after notice). Termination without Cause with {{notice_period_months}} months "
                            "notice or pay in lieu. Termination by Employee with {{notice_period_months}} months notice. "
                            "Probationary period: first {{probation_months}} months with shortened notice. "
                            "Severance: [SPECIFY] months base salary if terminated without Cause. "
                            "Obligations on termination: return property, transition duties, exit interview."
                        )),
        _clause_section("governing_law", "8. Governing Law",
                        clause_type="governing_law",
                        prompt_hint="Governed by laws of {{jurisdiction}}. Exclusive jurisdiction of courts of {{jurisdiction}}."),
        _clause_section("miscellaneous", "9. General Provisions",
                        clause_type="other",
                        prompt_hint=(
                            "Entire agreement, amendments in writing, severability, waiver, assignment, "
                            "notices, counterparts. Reference to Employee Handbook for additional policies."
                        )),
        _section("signature_block", "Signature Block",
                 prompt_hint=(
                     "Signature lines:\n\n"
                     "{{company_name}}\n"
                     "By: ________________________\nName:\nTitle:\nDate:\n\n"
                     "EMPLOYEE\n"
                     "________________________\n{{employee_name}}\nDate:"
                 )),
    ],
}


# ---------------------------------------------------------------------------
# Shareholders Agreement (SHA)
# ---------------------------------------------------------------------------
SHA_CONTRACT = {
    "id": "sha",
    "title_pattern": "Shareholders' Agreement — {company_name}",
    "contract_type": "sha",
    "required_data": ["company_context"],
    "optional_data": ["cap_table_history", "investor_context"],
    "template_variables": [
        "company_name", "effective_date", "jurisdiction",
        "share_classes", "investor_names",
    ],
    "preamble": (
        "This Shareholders' Agreement is entered into as of {{effective_date}} "
        "by and among {{company_name}} (the \"Company\") and the shareholders "
        "listed in Schedule A (the \"Shareholders\")."
    ),
    "governing_law_default": "Delaware",
    "sections": [
        _section("preamble", "Preamble",
                 prompt_hint=(
                     "Recitals: the Company has been incorporated under the laws of {{jurisdiction}}. "
                     "The Shareholders wish to regulate their relationship and the management of the Company. "
                     "Reference the relevant share classes and capitalization."
                 )),
        _clause_section("definitions", "1. Definitions and Interpretation",
                        clause_type="other",
                        prompt_hint=(
                            "Define key terms: Affiliate, Board, Business Day, Change of Control, "
                            "Deed of Adherence, Fair Market Value, Founder, Investor, Ordinary Shares, "
                            "Preference Shares, Qualified IPO, Reserved Matters, Sale. "
                            "Interpretation rules: headings, singular/plural, statutes include amendments."
                        )),
        _clause_section("share_capital", "2. Share Capital and Classes",
                        clause_type="share_class_rights",
                        data_keys=["cap_table_history"],
                        prompt_hint=(
                            "Describe authorized share capital. Define share classes (Ordinary, Preference A, B, etc.). "
                            "Reference the cap table for current shareholding percentages. "
                            "Include ESOP/option pool reservation. "
                            "Anti-dilution protection type (weighted average vs full ratchet) for preference shares."
                        )),
        _clause_section("transfer_restrictions", "3. Transfer Restrictions",
                        clause_type="transfer_restriction",
                        risk_level="high",
                        prompt_hint=(
                            "Shares not transferable except in accordance with this Agreement. "
                            "Right of first refusal (ROFR): Company first, then existing shareholders pro rata. "
                            "30-day exercise period. Fair Market Value determination mechanism. "
                            "Permitted transfers: to Affiliates, family trusts (with Deed of Adherence). "
                            "Founder lock-up: [SPECIFY] months from effective date."
                        )),
        _clause_section("drag_tag", "4. Drag-Along and Tag-Along Rights",
                        clause_type="drag_along",
                        risk_level="high",
                        prompt_hint=(
                            "Drag-along: shareholders holding [SPECIFY]% can compel all shareholders to sell "
                            "on same terms. Minimum price threshold. Notice period: 30 days. "
                            "Tag-along: if any shareholder receives bona fide offer for [SPECIFY]% or more, "
                            "other shareholders may tag along pro rata on same terms. "
                            "Both subject to regulatory approvals."
                        )),
        _clause_section("anti_dilution", "5. Anti-Dilution Protection",
                        clause_type="anti_dilution",
                        risk_level="high",
                        data_keys=["cap_table_history"],
                        prompt_hint=(
                            "Broad-based weighted average anti-dilution for preference shareholders. "
                            "Triggered on issuance of new shares at price below the applicable preference share price. "
                            "Excluded issuances: ESOP grants (up to pool limit), shares issued in acquisition, "
                            "shares issued on conversion of convertible instruments. "
                            "Pay-to-play: investors must participate pro rata in future rounds to maintain anti-dilution."
                        )),
        _clause_section("board", "6. Board Composition and Governance",
                        clause_type="board_composition",
                        prompt_hint=(
                            "Board composition: [SPECIFY] directors. Founder/management seats, investor seats, "
                            "independent director(s). Board observer rights for [SPECIFY] investors. "
                            "Quorum requirements. Meeting frequency (at least quarterly). "
                            "Board committees: audit, compensation (if applicable)."
                        )),
        _clause_section("information_rights", "7. Information Rights",
                        clause_type="information_rights",
                        prompt_hint=(
                            "Company to provide: (a) audited annual financials within 90 days of year-end, "
                            "(b) unaudited quarterly financials within 30 days of quarter-end, "
                            "(c) monthly management accounts within 20 days, (d) annual budget/business plan "
                            "30 days before fiscal year. Inspection rights with reasonable notice. "
                            "Threshold: shareholders holding [SPECIFY]% or more."
                        )),
        _clause_section("reserved_matters", "8. Reserved Matters (Protective Provisions)",
                        clause_type="protective_provisions",
                        risk_level="high",
                        prompt_hint=(
                            "Require investor majority consent for: (a) change of control or sale, "
                            "(b) new share issuance (except ESOP), (c) incurring debt above [SPECIFY], "
                            "(d) related party transactions, (e) changes to articles/charter, "
                            "(f) declaration of dividends, (g) amendment to ESOP, "
                            "(h) change of business, (i) hiring/terminating CEO/CFO, "
                            "(j) capital expenditure above [SPECIFY]. "
                            "Separate list for founder consent requirements."
                        )),
        _clause_section("liquidation", "9. Liquidation Preference",
                        clause_type="liquidation_preference",
                        risk_level="high",
                        data_keys=["cap_table_history"],
                        prompt_hint=(
                            "Preference shareholders receive [1x/2x] non-participating liquidation preference. "
                            "Payment priority: creditors → preference shares (by seniority) → ordinary shares pro rata. "
                            "Deemed liquidation events: sale, merger, exclusive license of substantially all IP. "
                            "Carve-out for [SPECIFY]% to management incentive pool on exit."
                        )),
        _clause_section("preemptive", "10. Pre-emptive Rights",
                        clause_type="preemptive_rights",
                        prompt_hint=(
                            "Existing shareholders have right to participate pro rata in any new issuance "
                            "of equity securities. 15-day exercise period from notice. "
                            "Over-allotment rights if any shareholder does not exercise. "
                            "Excluded issuances: ESOP, conversion of existing instruments, strategic partnerships "
                            "(approved by Board)."
                        )),
        _clause_section("governing_law", "11. Governing Law and Dispute Resolution",
                        clause_type="governing_law",
                        prompt_hint=(
                            "Governed by laws of {{jurisdiction}}. Disputes first to mediation (30 days), "
                            "then arbitration under [ICC/LCIA/AAA] rules. Seat of arbitration: {{jurisdiction}}. "
                            "Confidentiality of proceedings. Interim relief from courts permitted."
                        )),
        _clause_section("miscellaneous", "12. General Provisions",
                        clause_type="other",
                        prompt_hint=(
                            "Entire agreement, amendments (require [SPECIFY]% shareholder approval + Board), "
                            "severability, waiver, notices, counterparts, deed of adherence for new shareholders, "
                            "costs (each party bears own), further assurances."
                        )),
        _section("schedules", "Schedules",
                 prompt_hint=(
                     "Schedule A — List of Shareholders (name, address, share class, number of shares, percentage)\n"
                     "Schedule B — Reserved Matters requiring Investor Consent\n"
                     "Schedule C — Reserved Matters requiring Founder Consent\n"
                     "Schedule D — Deed of Adherence (template for new shareholders)\n"
                     "Schedule E — Vesting Schedule for Founder Shares"
                 )),
    ],
}


# ---------------------------------------------------------------------------
# Vendor Agreement
# ---------------------------------------------------------------------------
VENDOR_CONTRACT = {
    "id": "vendor",
    "title_pattern": "Vendor Agreement — {company_name} & {counterparty_name}",
    "contract_type": "vendor_agreement",
    "required_data": ["company_context"],
    "optional_data": ["counterparty_context"],
    "template_variables": [
        "company_name", "counterparty_name", "effective_date",
        "jurisdiction", "contract_term_months", "service_description",
    ],
    "preamble": (
        "This Vendor Agreement is entered into as of {{effective_date}} "
        "by and between {{company_name}} (the \"Client\") and "
        "{{counterparty_name}} (the \"Vendor\")."
    ),
    "governing_law_default": "Delaware",
    "sections": [
        _section("preamble", "Preamble",
                 prompt_hint="Recitals: Client requires certain services/products, Vendor is in the business of providing them."),
        _clause_section("scope", "1. Scope of Services / Products",
                        clause_type="other",
                        prompt_hint=(
                            "Describe services/products to be provided by Vendor. Reference Statement of Work (SOW) "
                            "or Order Form. Acceptance criteria. Change order process for scope modifications. "
                            "Vendor personnel requirements and key personnel clause."
                        )),
        _clause_section("payment", "2. Fees and Payment Terms",
                        clause_type="payment_terms",
                        prompt_hint=(
                            "Fee structure (fixed, T&M, milestone-based). Payment terms: Net 30 from invoice. "
                            "Late payment interest: [SPECIFY]% per month. Expenses: pre-approved, receipts required. "
                            "Annual price escalation cap: CPI or [SPECIFY]%. Right to audit invoices."
                        )),
        _clause_section("sla", "3. Service Levels and Performance",
                        clause_type="sla",
                        prompt_hint=(
                            "SLA metrics: uptime [SPECIFY]%, response time, resolution time. "
                            "Service credits for SLA breaches: [SPECIFY]% of monthly fees per breach. "
                            "Reporting: monthly performance reports. Persistent breach (3+ months) = termination right. "
                            "Disaster recovery and business continuity requirements."
                        )),
        _clause_section("liability", "4. Limitation of Liability",
                        clause_type="liability_cap",
                        risk_level="high",
                        prompt_hint=(
                            "Aggregate liability cap: 12 months of fees paid. Exclude from cap: indemnification obligations, "
                            "willful misconduct, gross negligence, breach of confidentiality, IP infringement. "
                            "No consequential, incidental, or punitive damages (mutual). "
                            "Carve-out for data breach: [SPECIFY] liability cap."
                        )),
        _clause_section("indemnification", "5. Indemnification",
                        clause_type="indemnification",
                        risk_level="high",
                        prompt_hint=(
                            "Vendor indemnifies Client against: (a) IP infringement claims (with duty to defend), "
                            "(b) personal injury or property damage from Vendor's acts, (c) violation of law, "
                            "(d) data breach caused by Vendor. "
                            "Indemnification procedure: prompt notice, control of defense, cooperation, no settlement without consent."
                        )),
        _clause_section("ip", "6. Intellectual Property",
                        clause_type="ip_assignment",
                        prompt_hint=(
                            "Client owns all deliverables and work product created specifically for Client. "
                            "Vendor retains ownership of pre-existing IP but grants Client perpetual, irrevocable license. "
                            "No use of Client data/IP for other clients or purposes. "
                            "Open source disclosure requirements."
                        )),
        _clause_section("confidentiality", "7. Confidentiality and Data Protection",
                        clause_type="confidentiality",
                        prompt_hint=(
                            "Mutual NDA obligations (incorporate by reference or restate). "
                            "Data processing: Vendor acts as data processor, DPA attached as exhibit. "
                            "Security requirements: encryption at rest and in transit, access controls, SOC 2 compliance. "
                            "Breach notification: within 24 hours. Data return/deletion on termination."
                        )),
        _clause_section("term", "8. Term, Renewal, and Termination",
                        clause_type="termination",
                        prompt_hint=(
                            "Initial term: {{contract_term_months}} months from effective date. "
                            "Auto-renewal for successive 12-month periods unless terminated with 90 days notice. "
                            "Termination for cause: 30 days cure period. Termination for convenience: 60 days notice. "
                            "Transition assistance: 90 days at Vendor's then-current rates. "
                            "Data portability on termination."
                        )),
        _clause_section("governing_law", "9. Governing Law",
                        clause_type="governing_law",
                        prompt_hint="Governed by laws of {{jurisdiction}}. Exclusive jurisdiction of courts of {{jurisdiction}}."),
    ],
}


# ---------------------------------------------------------------------------
# Service Agreement (MSA)
# ---------------------------------------------------------------------------
SERVICE_AGREEMENT = {
    "id": "service_agreement",
    "title_pattern": "Master Service Agreement — {company_name} & {counterparty_name}",
    "contract_type": "service_agreement",
    "required_data": ["company_context"],
    "optional_data": ["counterparty_context"],
    "template_variables": [
        "company_name", "counterparty_name", "effective_date",
        "jurisdiction", "contract_term_months",
    ],
    "preamble": (
        "This Master Service Agreement is entered into as of {{effective_date}} "
        "by and between {{company_name}} (the \"Client\") and "
        "{{counterparty_name}} (the \"Service Provider\")."
    ),
    "governing_law_default": "Delaware",
    "sections": [
        _section("preamble", "Preamble",
                 prompt_hint="Recitals: framework agreement for ongoing service engagements. Individual SOWs govern specific projects."),
        _clause_section("scope", "1. Scope and Statements of Work",
                        clause_type="other",
                        prompt_hint=(
                            "MSA as framework. Services governed by individual SOWs executed under this Agreement. "
                            "SOW format: scope, deliverables, timeline, fees, acceptance criteria, assigned personnel. "
                            "Conflict between MSA and SOW: MSA prevails unless SOW expressly states otherwise. "
                            "Change order process."
                        )),
        _clause_section("deliverables", "2. Deliverables and Acceptance",
                        clause_type="other",
                        prompt_hint=(
                            "Deliverables as defined in each SOW. Acceptance testing period: 10 business days. "
                            "Acceptance criteria per SOW. Rejection notice with specific deficiencies. "
                            "Cure period: 10 business days. Two rejections = right to terminate SOW. "
                            "Deemed accepted if no rejection notice within acceptance period."
                        )),
        _clause_section("payment", "3. Fees and Payment",
                        clause_type="payment_terms",
                        prompt_hint=(
                            "Fee structure per SOW (fixed, T&M with rate card, milestone). Payment: Net 30. "
                            "Rate card attached as Exhibit A. Annual rate increases capped at CPI + [SPECIFY]%. "
                            "Expenses: pre-approved, actual cost, documented. Right to audit."
                        )),
        _clause_section("confidentiality", "4. Confidentiality",
                        clause_type="confidentiality",
                        prompt_hint=(
                            "Mutual confidentiality obligations. Standard exclusions. Survive for 3 years post-termination "
                            "(indefinitely for trade secrets). Return or certify destruction on termination."
                        )),
        _clause_section("ip", "5. Intellectual Property",
                        clause_type="ip_assignment",
                        prompt_hint=(
                            "Work product created under SOW: Client owns. Pre-existing IP: Service Provider retains, "
                            "grants Client perpetual license for deliverables incorporating pre-existing IP. "
                            "No open source without Client approval. Source code escrow if applicable."
                        )),
        _clause_section("liability", "6. Liability and Indemnification",
                        clause_type="liability_cap",
                        risk_level="high",
                        prompt_hint=(
                            "Mutual liability cap: greater of fees paid in prior 12 months or [SPECIFY]. "
                            "Carve-outs: IP infringement indemnification, data breach, willful misconduct. "
                            "Mutual indemnification for third-party claims arising from breach. "
                            "No consequential damages (mutual). Insurance requirements: [SPECIFY]."
                        )),
        _clause_section("term", "7. Term and Termination",
                        clause_type="termination",
                        prompt_hint=(
                            "MSA term: {{contract_term_months}} months, auto-renewing. "
                            "Termination for cause: 30 days cure. Termination for convenience: 90 days notice. "
                            "Effect on SOWs: active SOWs survive until completed or separately terminated. "
                            "Transition assistance."
                        )),
        _clause_section("governing_law", "8. Governing Law",
                        clause_type="governing_law",
                        prompt_hint="Governed by laws of {{jurisdiction}}."),
        _clause_section("miscellaneous", "9. General Provisions",
                        clause_type="other",
                        prompt_hint=(
                            "Entire agreement (MSA + SOWs), amendments, severability, waiver, assignment, "
                            "force majeure (pandemic, war, natural disaster, government action — cap at 90 days then termination right), "
                            "notices, independent contractor relationship (not employment), counterparts."
                        )),
    ],
}


# ---------------------------------------------------------------------------
# Contract Review — produces redlines + negotiation points
# ---------------------------------------------------------------------------
CONTRACT_REVIEW = {
    "id": "contract_review",
    "title_pattern": "Contract Review — {document_title}",
    "contract_type": "review",
    "required_data": ["document_clauses"],
    "optional_data": ["company_context", "clause_library"],
    "template_variables": ["document_title", "company_name"],
    "sections": [
        _section("summary", "Executive Summary",
                 prompt_hint=(
                     "Overview: contract type, parties, key commercial terms, effective date, term. "
                     "Overall risk assessment (high/medium/low) with 2-3 sentence justification. "
                     "Top 3 issues requiring immediate attention."
                 )),
        _section("risk_flags", "Risk Flags", type="table",
                 data_keys=["document_clauses"],
                 prompt_hint=(
                     "Table with columns: Clause | Section | Risk Level | Issue | Recommended Action. "
                     "Sort by severity (high first). Include: missing standard protections, one-sided terms, "
                     "unusual provisions, uncapped liability, broad indemnification, unreasonable restrictive covenants."
                 )),
        _section("negotiation_points", "Negotiation Priorities",
                 data_keys=["document_clauses"],
                 prompt_hint=(
                     "Top 5 clauses to negotiate, ranked by impact. For each clause provide the analysis "
                     "using this exact format on separate lines:\n"
                     "ORIGINAL: [verbatim current language]\n"
                     "REVISED: [your recommended revision]\n"
                     "REASONING: [why this change matters — market standard reference, risk reduction, commercial impact]\n\n"
                     "Separate each clause with a blank line."
                 )),
        _section("missing_protections", "Missing Protections",
                 prompt_hint=(
                     "Standard clauses that are absent from this contract. For each missing clause: "
                     "what it is, why it matters, and draft suggested language. "
                     "Common missing protections: IP assignment, data protection/DPA, force majeure, "
                     "limitation of liability, insurance requirements, audit rights, "
                     "non-solicitation, change of control, assignment restrictions."
                 )),
        _section("financial_impact", "Financial Impact Summary", type="table",
                 data_keys=["document_clauses"],
                 prompt_hint=(
                     "Table: Clause | Financial Exposure | Recurring? | Risk Mitigation. "
                     "Total maximum exposure. Recurring obligations (monthly/annual). "
                     "Penalty/termination costs. Insurance coverage gaps."
                 )),
        _section("recommendation", "Recommendation",
                 prompt_hint=(
                     "Clear recommendation: accept / accept with changes / reject. "
                     "List of non-negotiable changes (must-haves). "
                     "List of nice-to-have improvements. "
                     "Estimated negotiation leverage (high/medium/low) with reasoning."
                 )),
    ],
}


# ---------------------------------------------------------------------------
# Registries — imported by memo_templates.py
# ---------------------------------------------------------------------------
CONTRACT_TEMPLATES: Dict[str, Dict[str, Any]] = {
    "nda": NDA_CONTRACT,
    "non_disclosure": NDA_CONTRACT,
    "employment": EMPLOYMENT_CONTRACT,
    "employment_agreement": EMPLOYMENT_CONTRACT,
    "sha": SHA_CONTRACT,
    "shareholders_agreement": SHA_CONTRACT,
    "vendor": VENDOR_CONTRACT,
    "vendor_agreement": VENDOR_CONTRACT,
    "service_agreement": SERVICE_AGREEMENT,
    "msa": SERVICE_AGREEMENT,
    "contract_review": CONTRACT_REVIEW,
}

CONTRACT_INTENT_KEYWORDS: Dict[str, str] = {
    # NDA
    "nda": "nda",
    "non-disclosure": "nda",
    "non disclosure": "nda",
    "confidentiality agreement": "nda",
    "draft nda": "nda",
    "draft an nda": "nda",
    # Employment
    "employment contract": "employment",
    "employment agreement": "employment",
    "hiring agreement": "employment",
    "offer letter": "employment",
    "draft employment": "employment",
    # SHA
    "sha": "sha",
    "shareholders agreement": "sha",
    "shareholder agreement": "sha",
    "shareholders' agreement": "sha",
    "draft sha": "sha",
    # Vendor
    "vendor agreement": "vendor",
    "vendor contract": "vendor",
    "supplier agreement": "vendor",
    "procurement agreement": "vendor",
    "draft vendor": "vendor",
    # Service Agreement / MSA
    "service agreement": "service_agreement",
    "services agreement": "service_agreement",
    "msa": "service_agreement",
    "master service agreement": "service_agreement",
    "consulting agreement": "service_agreement",
    "draft msa": "service_agreement",
    "draft service agreement": "service_agreement",
    # Contract Review
    "review contract": "contract_review",
    "review this contract": "contract_review",
    "contract review": "contract_review",
    "red-line": "contract_review",
    "redline": "contract_review",
    "negotiate": "contract_review",
    "negotiate this": "contract_review",
    "review agreement": "contract_review",
}
