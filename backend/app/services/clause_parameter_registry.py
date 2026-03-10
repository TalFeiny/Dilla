"""
Clause Parameter Registry (Layer 1)

Typed parameter extraction from legal document clauses.
Every financially-material clause gets resolved to a typed parameter
that the financial engines consume. This replaces manual inputs with
document-derived inputs.

Resolution logic:
  1. Map clause_type + cross_reference → param_type
  2. Check document lineage — does a later doc supersede this?
  3. Check DOC_PRIORITY — side letter (30) beats SHA (20), amendment (40) beats both
  4. Check effective/expiry dates — is this clause currently active?
  5. If two docs at same priority disagree — flag as conflict (don't guess)
  6. Register resolved parameter with full provenance
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from app.services.legal_cap_table_bridge import DOC_PRIORITY

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Instrument types the registry handles
# ---------------------------------------------------------------------------

INSTRUMENT_TYPES = {
    "equity", "debt", "convertible", "safe", "warrant", "option",
    "mezzanine", "revenue_based", "guarantee", "indemnity", "earnout",
    "escrow", "pik", "intercreditor", "swap", "lease",
}

# Clause types that map to financially-material parameters
CLAUSE_TO_PARAM_MAP = {
    # Equity
    "liquidation_preference": "liquidation_preference",
    "anti_dilution": "anti_dilution_method",
    "participation": "participation_rights",
    "participation_cap": "participation_cap",
    "drag_along": "drag_along",
    "tag_along": "tag_along",
    "pro_rata": "pro_rata_rights",
    "preemptive_rights": "preemptive_rights",
    "board_seat": "board_seats",
    "board_composition": "board_composition",
    "protective_provisions": "protective_provisions",
    "conversion_terms": "conversion_terms",
    "mandatory_conversion": "mandatory_conversion",
    "pay_to_play": "pay_to_play",
    "rofr": "rofr",
    "co_sale": "co_sale",
    "founder_lockup": "founder_lockup",
    "information_rights": "information_rights",
    "registration_rights": "registration_rights",
    "redemption_rights": "redemption_rights",
    "cumulative_dividends": "cumulative_dividends",
    "dividend_rate": "dividend_rate",
    # Debt
    "covenant": "covenant_threshold",
    "dscr_covenant": "covenant_dscr_threshold",
    "leverage_covenant": "covenant_leverage_threshold",
    "interest_rate": "interest_rate",
    "maturity": "maturity_date",
    "amortization": "amortization_schedule",
    "prepayment": "prepayment_terms",
    "cross_default": "cross_default",
    "acceleration": "acceleration_trigger",
    "step_in_rights": "step_in_rights",
    # Convertible instruments
    "conversion_discount": "conversion_discount",
    "valuation_cap": "valuation_cap",
    "qualified_financing": "qualified_financing_threshold",
    "most_favored_nation": "mfn",
    # Warrants
    "warrant_coverage": "warrant_coverage",
    "warrant_exercise_price": "warrant_exercise_price",
    "warrant_expiry": "warrant_expiry",
    # Guarantees & indemnities
    "personal_guarantee": "personal_guarantee",
    "parent_guarantee": "parent_guarantee",
    "indemnification": "indemnity_terms",
    "liability_cap": "liability_cap",
    "indemnity_cap": "indemnity_cap",
    "indemnity_basket": "indemnity_basket",
    "indemnity_escrow": "indemnity_escrow",
    # Change of control
    "change_of_control": "change_of_control",
    # Earnouts & escrows
    "earnout": "earnout_terms",
    "escrow": "escrow_terms",
    "clawback": "clawback_terms",
    # PIK / mezzanine
    "pik_toggle": "pik_toggle",
    "pik_rate": "pik_rate",
    # Transfer restrictions
    "transfer_restriction": "transfer_restriction",
    "lockup": "lockup_period",
    "exclusivity": "exclusivity",
    # Auto-renewal / termination
    "auto_renewal": "auto_renewal",
    "termination": "termination_terms",
    "minimum_commitment": "minimum_commitment",
    # Group structure
    "management_fee": "management_fee",
    "royalty": "royalty_rate",
    "intercompany_loan": "intercompany_loan_terms",
    "cost_recharge": "cost_recharge",
    "restricted_payment": "restricted_payment",
    "ring_fence": "ring_fence",
}


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class ClauseParameter:
    """A single financially-material clause resolved to a typed engine input."""
    param_type: str             # "liquidation_preference", "anti_dilution_method",
                                # "covenant_dscr_threshold", "conversion_discount", etc.
    value: Any                  # 2.0, "full_ratchet", 1.2, 0.20, etc.
    applies_to: str             # "series_a", "all_preferred", "founder_x", "lender_xyz"
    instrument: str             # "equity", "debt", "convertible", "safe", "warrant", etc.

    # Attribution
    source_document_id: str
    source_clause_id: str       # hierarchical ID "4.2.a"
    section_reference: str      # "Section 4.2(a)"
    source_quote: str           # verbatim from document
    document_type: str          # "sha", "side_letter", "term_sheet", "loan_agreement"
    effective_date: Optional[str] = None
    expiry_date: Optional[str] = None

    # Resolution state
    confidence: float = 1.0
    overridden_by: Optional[str] = None     # clause_id of overriding clause
    override_reason: Optional[str] = None   # "Side letter S.2 grants participation rights"


@dataclass
class ClauseConflict:
    """Two clauses that contradict each other with no clear resolution."""
    param_type: str
    clause_a: ClauseParameter
    clause_b: ClauseParameter
    conflict_description: str    # "SHA S.4.2 says 1x non-participating.
                                 #  Side letter S.2 says participating. Which governs?"
    financial_impact_range: Tuple[float, float]  # dollar range of the disagreement


@dataclass
class InstrumentSummary:
    """Summary of a single instrument in the capital structure."""
    instrument_id: str
    instrument_type: str        # "equity", "debt", "convertible", "safe", "warrant", etc.
    holder: str                 # stakeholder name
    principal_or_value: float
    terms: Dict[str, Any] = field(default_factory=dict)
    source_documents: List[str] = field(default_factory=list)
    effective_date: Optional[str] = None
    maturity_date: Optional[str] = None


@dataclass
class ResolvedParameterSet:
    """Complete resolved legal parameters for a company's capital structure.

    This is what the financial engines consume instead of manual inputs.
    """
    company_id: str
    parameters: Dict[str, ClauseParameter] = field(default_factory=dict)
    # keyed by f"{param_type}:{applies_to}"
    conflicts: List[ClauseConflict] = field(default_factory=list)
    override_chain: List[Dict[str, Any]] = field(default_factory=list)
    gaps: List[str] = field(default_factory=list)
    instruments: List[InstrumentSummary] = field(default_factory=list)
    last_resolved: datetime = field(default_factory=datetime.utcnow)

    # Convenience accessors

    def get(self, param_type: str, applies_to: str) -> Optional[ClauseParameter]:
        """Get a resolved parameter by type and target."""
        return self.parameters.get(f"{param_type}:{applies_to}")

    def get_all(self, param_type: str) -> List[ClauseParameter]:
        """Get all resolved parameters of a given type."""
        prefix = f"{param_type}:"
        return [p for k, p in self.parameters.items() if k.startswith(prefix)]

    def get_for_stakeholder(self, stakeholder: str) -> List[ClauseParameter]:
        """Get all parameters that apply to a stakeholder."""
        return [p for p in self.parameters.values() if p.applies_to == stakeholder]

    def get_instruments_by_type(self, instrument_type: str) -> List[InstrumentSummary]:
        """Get all instruments of a given type."""
        return [i for i in self.instruments if i.instrument_type == instrument_type]

    def has_conflicts(self) -> bool:
        return len(self.conflicts) > 0

    def has_gaps(self) -> bool:
        return len(self.gaps) > 0


# ---------------------------------------------------------------------------
# Vanilla defaults — what we assume when docs don't say otherwise
# ---------------------------------------------------------------------------

VANILLA_DEFAULTS: Dict[str, Dict[str, Any]] = {
    "liquidation_preference": {"value": 1.0, "reason": "Standard 1x non-participating"},
    "anti_dilution_method": {"value": "broad_weighted_average", "reason": "Most common protection"},
    "participation_rights": {"value": False, "reason": "Non-participating is standard"},
    "participation_cap": {"value": None, "reason": "N/A when non-participating"},
    "drag_along": {"value": True, "reason": "Standard in most SHAs"},
    "tag_along": {"value": True, "reason": "Standard in most SHAs"},
    "pro_rata_rights": {"value": True, "reason": "Standard for institutional investors"},
    "board_seats": {"value": 1, "reason": "One board seat per lead investor is standard"},
    "rofr": {"value": True, "reason": "Standard right of first refusal"},
    "information_rights": {"value": True, "reason": "Standard for preferred"},
    "conversion_terms": {"value": {"ratio": 1.0, "auto_on_ipo": True}, "reason": "1:1 conversion, auto on IPO"},
    "covenant_dscr_threshold": {"value": 1.2, "reason": "Standard DSCR covenant"},
    "warrant_coverage": {"value": 0.005, "reason": "0.5% warrant coverage on venture debt"},
}


# ---------------------------------------------------------------------------
# Resolution engine
# ---------------------------------------------------------------------------

class ClauseParameterRegistry:
    """Resolves extracted clause data into typed financial parameters."""

    def resolve_parameters(
        self,
        company_id: str,
        extracted_docs: List[Dict[str, Any]],
        as_of: Optional[datetime] = None,
    ) -> ResolvedParameterSet:
        """
        Walk all extracted clauses across all documents for a company.

        For each financially-material clause:
          1. Map clause_type + cross_reference → param_type
          2. Check document lineage — does a later doc supersede this?
          3. Check DOC_PRIORITY — side letter beats SHA, amendment beats both
          4. Check effective/expiry dates — is this clause currently active?
          5. If two docs at same priority disagree — flag as conflict (don't guess)
          6. Register resolved parameter with full provenance
        """
        as_of = as_of or datetime.utcnow()
        result = ResolvedParameterSet(company_id=company_id)

        # Phase 1: Extract all candidate parameters from all documents
        candidates: Dict[str, List[ClauseParameter]] = {}  # key → list of candidates
        superseded_docs: set = set()
        instruments: Dict[str, InstrumentSummary] = {}

        # Build supersession map
        for doc in extracted_docs:
            if doc.get("supersedes"):
                superseded_docs.add(doc["supersedes"])

        for doc in extracted_docs:
            doc_id = doc.get("id", doc.get("document_id", ""))

            # Skip superseded documents
            if doc_id in superseded_docs:
                logger.debug(f"Skipping superseded doc {doc_id}")
                continue

            doc_type = doc.get("document_type", "").lower()
            effective = doc.get("effective_date")
            expiry = doc.get("expiration_date") or doc.get("expiry_date")

            # Skip expired documents
            if expiry and self._is_expired(expiry, as_of):
                logger.debug(f"Skipping expired doc {doc_id} (expired {expiry})")
                continue

            clauses = doc.get("clauses", [])
            for clause in clauses:
                params = self._extract_params_from_clause(
                    clause, doc_id, doc_type, effective, expiry
                )
                for param in params:
                    key = f"{param.param_type}:{param.applies_to}"
                    candidates.setdefault(key, []).append(param)

            # Extract instrument summaries
            self._extract_instruments(doc, instruments)

        # Phase 2: Resolve conflicts using DOC_PRIORITY
        for key, param_list in candidates.items():
            if len(param_list) == 1:
                result.parameters[key] = param_list[0]
                continue

            # Sort by document priority (highest wins)
            param_list.sort(
                key=lambda p: DOC_PRIORITY.get(p.document_type, 0),
                reverse=True,
            )

            top = param_list[0]
            top_priority = DOC_PRIORITY.get(top.document_type, 0)

            # Check for same-priority conflicts
            same_priority = [
                p for p in param_list[1:]
                if DOC_PRIORITY.get(p.document_type, 0) == top_priority
                and p.value != top.value
            ]

            if same_priority:
                # Conflict: same priority, different values — don't guess
                for conflicting in same_priority:
                    result.conflicts.append(ClauseConflict(
                        param_type=top.param_type,
                        clause_a=top,
                        clause_b=conflicting,
                        conflict_description=(
                            f"{top.document_type} {top.section_reference} says "
                            f"{top.value}. {conflicting.document_type} "
                            f"{conflicting.section_reference} says {conflicting.value}. "
                            f"Same priority ({top_priority}). Which governs?"
                        ),
                        financial_impact_range=(0.0, 0.0),  # Computed by cascade later
                    ))
                # Still use the first one but mark low confidence
                top.confidence = 0.5

            # Mark overridden parameters
            for overridden in param_list[1:]:
                if overridden not in same_priority:
                    overridden.overridden_by = top.source_clause_id
                    overridden.override_reason = (
                        f"{top.document_type} (priority {top_priority}) "
                        f"overrides {overridden.document_type} "
                        f"(priority {DOC_PRIORITY.get(overridden.document_type, 0)})"
                    )

            result.parameters[key] = top
            result.override_chain.append({
                "key": key,
                "winner": {
                    "doc_type": top.document_type,
                    "doc_id": top.source_document_id,
                    "clause": top.source_clause_id,
                    "value": top.value,
                    "priority": top_priority,
                },
                "overridden": [
                    {
                        "doc_type": p.document_type,
                        "doc_id": p.source_document_id,
                        "clause": p.source_clause_id,
                        "value": p.value,
                        "priority": DOC_PRIORITY.get(p.document_type, 0),
                    }
                    for p in param_list[1:]
                ],
            })

        # Phase 3: Identify gaps — expected parameters not found
        result.gaps = self._find_gaps(result.parameters, extracted_docs)

        # Phase 3b: Inject vanilla defaults for gaps
        self._inject_defaults(result)

        # Phase 4: Set instruments
        result.instruments = list(instruments.values())

        return result

    def resolve_with_overrides(
        self,
        company_id: str,
        extracted_docs: List[Dict[str, Any]],
        overrides: Dict[str, Any],
        as_of: Optional[datetime] = None,
    ) -> ResolvedParameterSet:
        """Resolve parameters then apply manual/branch overrides on top."""
        result = self.resolve_parameters(company_id, extracted_docs, as_of)

        for key, value in overrides.items():
            if key in result.parameters:
                original = result.parameters[key]
                result.parameters[key] = ClauseParameter(
                    param_type=original.param_type,
                    value=value,
                    applies_to=original.applies_to,
                    instrument=original.instrument,
                    source_document_id="override",
                    source_clause_id="manual",
                    section_reference="Manual override",
                    source_quote="",
                    document_type="override",
                    confidence=1.0,
                    overridden_by="manual_override",
                    override_reason=f"Manual override: {original.value} → {value}",
                )

        return result

    def _inject_defaults(self, result: ResolvedParameterSet) -> None:
        """Inject VANILLA_DEFAULTS for identified gaps.

        When a gap says 'No liquidation_preference clause found for series_a',
        inject the default value so the financial engines have data to work with.
        """
        import re

        for gap_desc in result.gaps:
            # Parse the gap description to extract param_type and entity
            m = re.match(r'No (\w+) clause found for (\w+)', gap_desc)
            if not m:
                continue
            param_type = m.group(1)
            entity = m.group(2)

            default = VANILLA_DEFAULTS.get(param_type)
            if default is None:
                continue

            key = f"{param_type}:{entity}"
            if key in result.parameters:
                continue  # Already resolved — don't override

            # Inject the default with low confidence and clear attribution
            result.parameters[key] = ClauseParameter(
                param_type=param_type,
                value=default["value"],
                applies_to=entity,
                instrument="equity",
                source_document_id="vanilla_default",
                source_clause_id="default",
                section_reference=f"Default: {default['reason']}",
                source_quote="",
                document_type="default",
                confidence=0.3,
                overridden_by=None,
                override_reason=f"No clause found; using vanilla default: {default['reason']}",
            )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _extract_params_from_clause(
        self,
        clause: Dict[str, Any],
        doc_id: str,
        doc_type: str,
        effective_date: Optional[str],
        expiry_date: Optional[str],
    ) -> List[ClauseParameter]:
        """Extract typed parameters from a single clause."""
        params: List[ClauseParameter] = []
        clause_type = clause.get("clause_type", "").lower()
        clause_id = clause.get("id", "")
        clause_text = clause.get("text", "")
        title = clause.get("title", "")

        # Check cross_references for explicit mappings
        cross_refs = clause.get("cross_references", [])
        for ref in cross_refs:
            param_type = self._map_cross_ref_to_param(ref, clause_type)
            if param_type:
                params.append(ClauseParameter(
                    param_type=param_type,
                    value=ref.get("value"),
                    applies_to=ref.get("to_entity", "all"),
                    instrument=self._infer_instrument(doc_type, clause_type),
                    source_document_id=doc_id,
                    source_clause_id=clause_id,
                    section_reference=f"Section {clause_id}" if clause_id else title,
                    source_quote=clause_text[:300],
                    document_type=doc_type,
                    effective_date=effective_date,
                    expiry_date=expiry_date,
                ))

        # If no cross-refs, use clause_type direct mapping
        if not cross_refs and clause_type in CLAUSE_TO_PARAM_MAP:
            param_type = CLAUSE_TO_PARAM_MAP[clause_type]
            value = self._extract_value_from_clause(clause, clause_type)
            entity = self._extract_entity_from_clause(clause, doc_type)

            if value is not None:
                params.append(ClauseParameter(
                    param_type=param_type,
                    value=value,
                    applies_to=entity,
                    instrument=self._infer_instrument(doc_type, clause_type),
                    source_document_id=doc_id,
                    source_clause_id=clause_id,
                    section_reference=f"Section {clause_id}" if clause_id else title,
                    source_quote=clause_text[:300],
                    document_type=doc_type,
                    effective_date=effective_date,
                    expiry_date=expiry_date,
                ))

        return params

    def _map_cross_ref_to_param(
        self, ref: Dict[str, Any], clause_type: str
    ) -> Optional[str]:
        """Map a cross-reference to a parameter type."""
        field_name = ref.get("field", "").lower()
        to_service = ref.get("to_service", "").lower()

        # Direct field → param mapping
        field_map = {
            "liquidation_pref_multiple": "liquidation_preference",
            "liquidation_preference": "liquidation_preference",
            "anti_dilution_method": "anti_dilution_method",
            "anti_dilution_type": "anti_dilution_method",
            "participation": "participation_rights",
            "participating": "participation_rights",
            "participation_cap": "participation_cap",
            "conversion_ratio": "conversion_terms",
            "conversion_discount": "conversion_discount",
            "valuation_cap": "valuation_cap",
            "dscr_threshold": "covenant_dscr_threshold",
            "leverage_ratio": "covenant_leverage_threshold",
            "interest_rate": "interest_rate",
            "warrant_coverage": "warrant_coverage",
            "board_seats": "board_seats",
            "drag_along_threshold": "drag_along",
            "tag_along": "tag_along",
            "pro_rata": "pro_rata_rights",
            "dividend_rate": "dividend_rate",
        }

        if field_name in field_map:
            return field_map[field_name]

        # Fall back to clause type mapping
        if clause_type in CLAUSE_TO_PARAM_MAP:
            return CLAUSE_TO_PARAM_MAP[clause_type]

        return None

    def _extract_value_from_clause(
        self, clause: Dict[str, Any], clause_type: str
    ) -> Any:
        """Extract the value from a clause based on its type."""
        text = (clause.get("text", "") or "").lower()
        obligations = clause.get("obligations", [])

        if clause_type in ("liquidation_preference",):
            return self._parse_liq_pref_value(text)
        elif clause_type in ("anti_dilution",):
            return self._parse_anti_dilution_value(text)
        elif clause_type in ("participation", "participation_cap"):
            return self._parse_participation_value(text)
        elif clause_type in ("drag_along", "tag_along"):
            return self._parse_drag_tag_value(text, clause_type)
        elif clause_type in ("pro_rata", "preemptive_rights", "rofr", "co_sale",
                             "pay_to_play", "information_rights"):
            return True  # Boolean clause types — presence means True
        elif clause_type == "mandatory_conversion":
            return self._parse_mandatory_conversion_value(text)
        elif clause_type in ("registration_rights",):
            return True
        elif clause_type == "redemption_rights":
            return self._parse_redemption_value(text)
        elif clause_type == "cumulative_dividends":
            return True  # Presence means cumulative; rate parsed by dividend_rate
        elif clause_type in ("covenant", "dscr_covenant", "leverage_covenant"):
            return self._parse_covenant_value(text)
        elif clause_type in ("interest_rate", "dividend_rate", "pik_rate"):
            return self._parse_rate_value(text)
        elif clause_type in ("warrant_coverage",):
            return self._parse_rate_value(text)
        elif clause_type == "warrant_exercise_price":
            return self._parse_monetary_value(text)
        elif clause_type == "qualified_financing":
            return self._parse_monetary_value(text)
        elif clause_type in ("personal_guarantee", "parent_guarantee"):
            return self._parse_guarantee_value(text)
        elif clause_type in ("indemnification", "liability_cap", "indemnity_cap",
                             "indemnity_basket", "indemnity_escrow"):
            return self._parse_monetary_value(text)
        elif clause_type in ("earnout",):
            return self._parse_earnout_value(text, obligations)
        elif clause_type in ("escrow",):
            return self._parse_escrow_value(text)
        elif clause_type in ("board_seat", "board_composition"):
            return self._parse_board_value(text)
        elif clause_type in ("change_of_control",):
            return self._parse_coc_value(text)
        elif clause_type in ("auto_renewal",):
            return self._parse_auto_renewal_value(text, clause)
        elif clause_type in ("minimum_commitment",):
            return self._parse_monetary_value(text)
        elif clause_type in ("management_fee", "royalty"):
            return self._parse_rate_value(text)
        elif clause_type == "conversion_terms":
            return self._parse_conversion_terms_value(text)
        elif clause_type in ("maturity",):
            return self._parse_date_value(text)
        elif clause_type in ("lockup", "founder_lockup"):
            return self._parse_lockup_value(text)
        elif clause_type in ("amortization",):
            return self._parse_amortization_value(text)
        elif clause_type in ("prepayment",):
            return self._parse_prepayment_value(text)
        elif clause_type in ("cross_default", "acceleration", "step_in_rights"):
            return True  # Boolean — presence means the right exists
        elif clause_type in ("clawback",):
            return self._parse_clawback_value(text)
        elif clause_type in ("pik_toggle",):
            return True  # PIK toggle presence; rate parsed by pik_rate
        elif clause_type in ("conversion_discount",):
            return self._parse_rate_value(text)
        elif clause_type in ("valuation_cap",):
            return self._parse_monetary_value(text)
        elif clause_type in ("most_favored_nation",):
            return True
        elif clause_type in ("termination",):
            return self._parse_termination_value(text)
        elif clause_type in ("exclusivity",):
            return self._parse_lockup_value(text)  # Similar duration parsing
        elif clause_type in ("transfer_restriction",):
            return True
        elif clause_type in ("restricted_payment", "ring_fence"):
            return self._parse_monetary_value(text) or True
        elif clause_type in ("intercompany_loan", "cost_recharge"):
            return self._parse_monetary_value(text) or True
        else:
            # Unknown clause type — log and return True (presence-based)
            logger.debug(f"No specific parser for clause type: {clause_type}")
            return True

    def _extract_entity_from_clause(
        self, clause: Dict[str, Any], doc_type: str
    ) -> str:
        """Determine which entity/stakeholder this clause applies to."""
        cross_refs = clause.get("cross_references", [])
        for ref in cross_refs:
            entity = ref.get("to_entity")
            if entity:
                return entity

        # Infer from obligations
        for ob in clause.get("obligations", []):
            party = ob.get("party", "")
            if party:
                return party.lower().replace(" ", "_")

        return "all"

    def _infer_instrument(self, doc_type: str, clause_type: str) -> str:
        """Infer the instrument type from document and clause type."""
        debt_docs = {"loan_agreement", "credit_facility", "venture_debt"}
        convertible_docs = {"convertible_note", "safe"}
        warrant_docs = {"warrant_agreement"}

        if doc_type in debt_docs or clause_type in ("covenant", "dscr_covenant",
                                                     "leverage_covenant", "cross_default"):
            return "debt"
        elif doc_type in convertible_docs or clause_type in ("conversion_discount",
                                                              "valuation_cap",
                                                              "qualified_financing"):
            return "convertible"
        elif doc_type in warrant_docs or clause_type == "warrant_coverage":
            return "warrant"
        elif clause_type in ("personal_guarantee", "parent_guarantee"):
            return "guarantee"
        elif clause_type in ("indemnification", "indemnity_cap", "indemnity_basket"):
            return "indemnity"
        elif clause_type in ("earnout",):
            return "earnout"
        elif clause_type in ("escrow",):
            return "escrow"
        elif clause_type in ("pik_toggle", "pik_rate"):
            return "pik"
        elif clause_type in ("management_fee", "royalty", "intercompany_loan",
                             "cost_recharge"):
            return "intercompany"
        else:
            return "equity"

    def _extract_instruments(
        self, doc: Dict[str, Any], instruments: Dict[str, InstrumentSummary]
    ) -> None:
        """Extract instrument summaries from a document."""
        doc_id = doc.get("id", doc.get("document_id", ""))
        doc_type = doc.get("document_type", "").lower()
        parties = doc.get("parties", [])

        # Identify instrument holder
        holder = "unknown"
        for party in parties:
            role = (party.get("role", "") or "").lower()
            if role in ("investor", "lender", "holder", "warrantholder", "noteholder"):
                holder = party.get("name", "unknown")
                break

        # Build instrument from clauses
        clauses = doc.get("clauses", [])
        terms: Dict[str, Any] = {}
        for clause in clauses:
            clause_type = clause.get("clause_type", "")
            if clause_type in CLAUSE_TO_PARAM_MAP:
                val = self._extract_value_from_clause(clause, clause_type)
                if val is not None:
                    terms[clause_type] = val

        if terms:
            inst_type = self._infer_instrument(doc_type, "")
            key = f"{doc_id}:{holder}"
            if key not in instruments:
                instruments[key] = InstrumentSummary(
                    instrument_id=doc_id,
                    instrument_type=inst_type,
                    holder=holder,
                    principal_or_value=0.0,
                    terms=terms,
                    source_documents=[doc_id],
                    effective_date=doc.get("effective_date"),
                    maturity_date=doc.get("expiration_date"),
                )
            else:
                instruments[key].terms.update(terms)
                if doc_id not in instruments[key].source_documents:
                    instruments[key].source_documents.append(doc_id)

    def _find_gaps(
        self, params: Dict[str, ClauseParameter], docs: List[Dict[str, Any]]
    ) -> List[str]:
        """Identify expected parameters not found in any document."""
        gaps: List[str] = []

        # Check for equity investors without key protections
        equity_entities: set = set()
        for key, param in params.items():
            if param.instrument == "equity" and param.applies_to != "all":
                equity_entities.add(param.applies_to)

        expected_equity_params = [
            "liquidation_preference", "anti_dilution_method",
            "drag_along", "tag_along", "pro_rata_rights",
        ]

        for entity in equity_entities:
            for expected in expected_equity_params:
                key = f"{expected}:{entity}"
                if key not in params:
                    default = VANILLA_DEFAULTS.get(expected)
                    reason = default["reason"] if default else "No default available"
                    gaps.append(
                        f"No {expected} clause found for {entity}. "
                        f"Using default: {reason}."
                    )

        # Check for debt instruments without covenants
        debt_entities: set = set()
        for key, param in params.items():
            if param.instrument == "debt":
                debt_entities.add(param.applies_to)

        for entity in debt_entities:
            key = f"covenant_dscr_threshold:{entity}"
            if key not in params:
                gaps.append(
                    f"No DSCR covenant found for debt instrument {entity}. "
                    f"Using default: 1.2x."
                )

        return gaps

    # ------------------------------------------------------------------
    # Value parsers
    # ------------------------------------------------------------------

    def _parse_liq_pref_value(self, text: str) -> float:
        """Parse liquidation preference multiple from text."""
        import re
        # Match patterns like "2x", "2.0x", "2X", "two times"
        m = re.search(r'(\d+\.?\d*)\s*[xX]', text)
        if m:
            return float(m.group(1))
        word_map = {"one": 1.0, "two": 2.0, "three": 3.0, "four": 4.0}
        for word, val in word_map.items():
            if word in text and "times" in text:
                return val
        return 1.0  # Default

    def _parse_anti_dilution_value(self, text: str) -> str:
        if "full ratchet" in text:
            return "full_ratchet"
        elif "narrow" in text and "weighted" in text:
            return "narrow_weighted_average"
        elif "weighted" in text and "average" in text:
            return "broad_weighted_average"
        return "broad_weighted_average"  # Default

    def _parse_participation_value(self, text: str) -> Any:
        """Parse participation rights. Returns bool or cap value."""
        import re
        if "non-participating" in text or "non participating" in text:
            return False
        if "participating" in text:
            m = re.search(r'cap(?:ped)?\s+(?:at\s+)?(\d+\.?\d*)\s*[xX]', text)
            if m:
                return {"participating": True, "cap": float(m.group(1))}
            return True
        return False

    def _parse_covenant_value(self, text: str) -> Dict[str, Any]:
        """Parse covenant threshold from text."""
        import re
        result: Dict[str, Any] = {}
        dscr_match = re.search(r'(?:dscr|debt service)\s*(?:of|above|exceed|>=?)\s*(\d+\.?\d*)', text)
        if dscr_match:
            result["dscr"] = float(dscr_match.group(1))
        leverage_match = re.search(r'(?:leverage|debt.to.equity)\s*(?:below|under|<=?)\s*(\d+\.?\d*)', text)
        if leverage_match:
            result["leverage"] = float(leverage_match.group(1))
        return result or {"threshold": True}

    def _parse_rate_value(self, text: str) -> Optional[float]:
        """Parse a percentage rate from text."""
        import re
        m = re.search(r'(\d+\.?\d*)\s*%', text)
        if m:
            return float(m.group(1)) / 100
        return None

    def _parse_guarantee_value(self, text: str) -> Dict[str, Any]:
        """Parse guarantee terms."""
        import re
        result: Dict[str, Any] = {"type": "guarantee"}
        # Match patterns like "$5M", "$5 million", "$500K", "$500 thousand", "$5,000,000"
        m = re.search(r'\$\s*([\d,]+(?:\.\d+)?)\s*(million|m\b|thousand|k\b|billion|b\b)?', text, re.I)
        if m:
            val = float(m.group(1).replace(",", ""))
            suffix = (m.group(2) or "").lower().strip()
            # Only match explicit suffixes — NOT arbitrary "m" within words
            if suffix in ("million", "m"):
                val *= 1_000_000
            elif suffix in ("thousand", "k"):
                val *= 1_000
            elif suffix in ("billion", "b"):
                val *= 1_000_000_000
            result["amount"] = val
        result["unlimited"] = "unlimit" in text or "full and unconditional" in text
        return result

    def _parse_monetary_value(self, text: str) -> Optional[float]:
        """Parse a dollar amount from text."""
        import re
        m = re.search(r'\$\s*([\d,]+(?:\.\d+)?)\s*(k|m|million|thousand|billion|b)?', text, re.I)
        if m:
            val = float(m.group(1).replace(",", ""))
            suffix = (m.group(2) or "").lower()
            if suffix in ("m", "million"):
                val *= 1_000_000
            elif suffix in ("k", "thousand"):
                val *= 1_000
            elif suffix in ("b", "billion"):
                val *= 1_000_000_000
            return val
        return None

    def _parse_earnout_value(
        self, text: str, obligations: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Parse earnout terms."""
        result: Dict[str, Any] = {"type": "earnout"}
        amount = self._parse_monetary_value(text)
        if amount:
            result["max_amount"] = amount
        result["milestones"] = [
            ob.get("description", "")
            for ob in obligations
            if ob.get("description")
        ]
        return result

    def _parse_escrow_value(self, text: str) -> Dict[str, Any]:
        """Parse escrow terms."""
        import re
        result: Dict[str, Any] = {"type": "escrow"}
        amount = self._parse_monetary_value(text)
        if amount:
            result["amount"] = amount
        pct = re.search(r'(\d+\.?\d*)\s*%', text)
        if pct:
            result["percentage"] = float(pct.group(1)) / 100
        duration = re.search(r'(\d+)\s*(?:month|year)', text)
        if duration:
            result["duration_months"] = int(duration.group(1))
            if "year" in text:
                result["duration_months"] *= 12
        return result

    def _parse_board_value(self, text: str) -> Dict[str, Any]:
        """Parse board composition terms."""
        import re
        result: Dict[str, Any] = {}
        seats_match = re.search(r'(\d+)\s*(?:board)?\s*seat', text)
        if seats_match:
            result["seats"] = int(seats_match.group(1))
        if "observer" in text:
            result["observer"] = True
        if "veto" in text or "consent" in text:
            result["veto_rights"] = True
        return result or {"seats": 1}

    def _parse_coc_value(self, text: str) -> Dict[str, Any]:
        """Parse change of control terms."""
        import re
        result: Dict[str, Any] = {"type": "change_of_control"}
        threshold = re.search(r'(\d+)\s*%', text)
        if threshold:
            result["threshold_pct"] = float(threshold.group(1)) / 100
        if "single trigger" in text or "single-trigger" in text:
            result["trigger"] = "single"
        elif "double trigger" in text or "double-trigger" in text:
            result["trigger"] = "double"
        if "acceleration" in text:
            result["acceleration"] = True
        if "consent" in text:
            result["consent_required"] = True
        return result

    def _parse_auto_renewal_value(
        self, text: str, clause: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Parse auto-renewal terms."""
        import re
        result: Dict[str, Any] = {"auto_renews": True}
        notice = re.search(r'(\d+)\s*(?:day|business day)', text)
        if notice:
            result["notice_days"] = int(notice.group(1))
        term = re.search(r'(\d+)\s*(?:month|year)', text)
        if term:
            result["renewal_term_months"] = int(term.group(1))
            if "year" in text:
                result["renewal_term_months"] *= 12
        return result

    def _parse_drag_tag_value(self, text: str, clause_type: str) -> Any:
        """Parse drag-along/tag-along with threshold extraction."""
        import re
        result: Dict[str, Any] = {"enabled": True}
        # Extract voting threshold like "75%", "majority", "2/3"
        pct_match = re.search(r'(\d+)\s*%', text)
        if pct_match:
            result["threshold"] = float(pct_match.group(1)) / 100
        elif "majority" in text:
            result["threshold"] = 0.5
        elif "supermajority" in text or "super-majority" in text:
            result["threshold"] = 0.6667
        fraction = re.search(r'(\d+)/(\d+)', text)
        if fraction:
            result["threshold"] = int(fraction.group(1)) / int(fraction.group(2))
        return result if len(result) > 1 else True

    def _parse_mandatory_conversion_value(self, text: str) -> Dict[str, Any]:
        """Parse mandatory conversion terms (e.g., auto-convert on IPO)."""
        import re
        result: Dict[str, Any] = {"mandatory": True}
        if "ipo" in text.lower():
            result["trigger"] = "ipo"
        elif "qualified" in text.lower():
            result["trigger"] = "qualified_financing"
            amount = self._parse_monetary_value(text)
            if amount:
                result["threshold"] = amount
        # Conversion ratio
        ratio_match = re.search(r'(\d+\.?\d*)\s*:\s*(\d+\.?\d*)', text)
        if ratio_match:
            result["ratio"] = float(ratio_match.group(1)) / float(ratio_match.group(2))
        return result

    def _parse_redemption_value(self, text: str) -> Dict[str, Any]:
        """Parse redemption rights."""
        import re
        result: Dict[str, Any] = {"redeemable": True}
        # Look for redemption date/period
        years_match = re.search(r'(\d+)\s*years?', text)
        if years_match:
            result["after_years"] = int(years_match.group(1))
        # Redemption price multiple
        mult_match = re.search(r'(\d+\.?\d*)\s*[xX]', text)
        if mult_match:
            result["price_multiple"] = float(mult_match.group(1))
        return result

    def _parse_conversion_terms_value(self, text: str) -> Dict[str, Any]:
        """Parse conversion terms — ratio, auto-conversion triggers."""
        import re
        result: Dict[str, Any] = {}
        ratio_match = re.search(r'(\d+\.?\d*)\s*:\s*(\d+\.?\d*)', text)
        if ratio_match:
            result["ratio"] = float(ratio_match.group(1)) / float(ratio_match.group(2))
        else:
            result["ratio"] = 1.0  # Default 1:1
        if "ipo" in text.lower():
            result["auto_on_ipo"] = True
        if "qualified" in text.lower():
            result["auto_on_qualified_financing"] = True
        return result

    def _parse_date_value(self, text: str) -> Optional[str]:
        """Parse a date from text (for maturity, lockup expiry, etc.)."""
        import re
        # ISO date pattern
        date_match = re.search(r'(\d{4}-\d{2}-\d{2})', text)
        if date_match:
            return date_match.group(1)
        # Written dates: "March 15, 2027", "15 March 2027"
        month_names = {
            "january": "01", "february": "02", "march": "03", "april": "04",
            "may": "05", "june": "06", "july": "07", "august": "08",
            "september": "09", "october": "10", "november": "11", "december": "12",
        }
        for month_name, month_num in month_names.items():
            pattern = rf'{month_name}\s+(\d{{1,2}}),?\s+(\d{{4}})'
            m = re.search(pattern, text, re.I)
            if m:
                return f"{m.group(2)}-{month_num}-{int(m.group(1)):02d}"
        # Duration-based: "24 months", "2 years"
        months_match = re.search(r'(\d+)\s*months?', text)
        if months_match:
            return f"+{months_match.group(1)}m"  # Relative format
        years_match = re.search(r'(\d+)\s*years?', text)
        if years_match:
            return f"+{int(years_match.group(1)) * 12}m"
        return None

    def _parse_lockup_value(self, text: str) -> Dict[str, Any]:
        """Parse lockup/exclusivity period."""
        import re
        result: Dict[str, Any] = {"locked": True}
        months_match = re.search(r'(\d+)\s*months?', text)
        if months_match:
            result["months"] = int(months_match.group(1))
        years_match = re.search(r'(\d+)\s*years?', text)
        if years_match:
            result["months"] = int(years_match.group(1)) * 12
        days_match = re.search(r'(\d+)\s*days?', text)
        if days_match:
            result["days"] = int(days_match.group(1))
        return result

    def _parse_amortization_value(self, text: str) -> Dict[str, Any]:
        """Parse amortization schedule."""
        import re
        result: Dict[str, Any] = {}
        months_match = re.search(r'(\d+)\s*months?', text)
        if months_match:
            result["term_months"] = int(months_match.group(1))
        years_match = re.search(r'(\d+)\s*years?', text)
        if years_match:
            result["term_months"] = int(years_match.group(1)) * 12
        if "straight-line" in text or "straight line" in text:
            result["method"] = "straight_line"
        elif "bullet" in text:
            result["method"] = "bullet"
        elif "balloon" in text:
            result["method"] = "balloon"
        else:
            result["method"] = "level"
        return result

    def _parse_prepayment_value(self, text: str) -> Dict[str, Any]:
        """Parse prepayment terms."""
        import re
        result: Dict[str, Any] = {}
        if "without penalty" in text or "no penalty" in text or "no prepayment penalty" in text:
            result["penalty"] = 0
        else:
            pct_match = re.search(r'(\d+\.?\d*)\s*%', text)
            if pct_match:
                result["penalty_pct"] = float(pct_match.group(1)) / 100
        if "lockout" in text:
            months_match = re.search(r'(\d+)\s*months?.*lockout', text, re.I)
            if months_match:
                result["lockout_months"] = int(months_match.group(1))
        return result or {"allowed": True}

    def _parse_clawback_value(self, text: str) -> Dict[str, Any]:
        """Parse clawback terms."""
        result: Dict[str, Any] = {"clawback": True}
        amount = self._parse_monetary_value(text)
        if amount:
            result["cap"] = amount
        return result

    def _parse_termination_value(self, text: str) -> Dict[str, Any]:
        """Parse termination clause terms."""
        import re
        result: Dict[str, Any] = {}
        if "for convenience" in text or "without cause" in text:
            result["for_convenience"] = True
        if "for cause" in text or "material breach" in text:
            result["for_cause"] = True
        notice_match = re.search(r'(\d+)\s*(?:day|business day)', text)
        if notice_match:
            result["notice_days"] = int(notice_match.group(1))
        return result or {"terminable": True}

    def _is_expired(self, expiry: str, as_of: datetime) -> bool:
        """Check if a date string is before as_of."""
        try:
            expiry_dt = datetime.fromisoformat(expiry.replace("Z", "+00:00"))
            # Ensure both are either naive or aware to prevent TypeError
            if expiry_dt.tzinfo is not None and as_of.tzinfo is None:
                as_of = as_of.replace(tzinfo=expiry_dt.tzinfo)
            elif expiry_dt.tzinfo is None and as_of.tzinfo is not None:
                expiry_dt = expiry_dt.replace(tzinfo=as_of.tzinfo)
            return expiry_dt < as_of
        except (ValueError, AttributeError, TypeError):
            return False
