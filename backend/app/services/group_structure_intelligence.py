"""
Group Structure Intelligence (Layer 8 / Step 10)

For companies with holdco/subsidiary structures, SPVs, and multi-jurisdiction
entities. Maps the legal relationships between entities, determines how cash
can move, where value sits, what restructuring options exist, and validates
intercompany pricing against TP policy.

Five capabilities:
  1. resolve_group_structure() — entity map with ownership, jurisdiction, purpose
  2. map_intercompany_flows() — cash flow rules between entities from contracts
  3. identify_flow_constraints() — legal limits on cash movement (covenants,
     thin cap, ring-fencing, restricted payments)
  4. validate_tp_compliance() — feed pricing into TransferPricingEngine,
     flag where contract terms don't match arm's length
  5. find_restructuring_options() — what CAN change within legal/TP bounds

Every output is attributed to the specific clause in the specific document.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from app.services.clause_parameter_registry import (
    ClauseParameter,
    ClauseParameterRegistry,
    ResolvedParameterSet,
)
from app.services.cascade_engine import (
    CascadeEdge,
    CascadeGraph,
    CascadeResult,
    Constraint,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class Entity:
    """A legal entity in the group structure."""
    entity_id: str
    name: str
    entity_type: str            # "holdco", "opco", "spv", "subsidiary", "branch",
                                # "ip_holdco", "finance_co", "dormant"
    jurisdiction: str           # "US-DE", "UK", "IE", "SG", "KY", etc.
    tax_rate: Optional[float] = None   # effective corporate tax rate
    ownership_pct: float = 100.0       # parent's ownership %
    parent_entity_id: Optional[str] = None
    purpose: str = ""           # "operating", "ip_holding", "financing",
                                # "asset_protection", "tax_efficiency", "fundraising"
    incorporation_date: Optional[str] = None
    is_dormant: bool = False
    registered_capital: Optional[float] = None
    source_documents: List[str] = field(default_factory=list)
    # docs that define this entity's existence/ownership


@dataclass
class EntityRelationship:
    """A legal relationship between two entities."""
    from_entity_id: str
    to_entity_id: str
    relationship_type: str      # "parent_subsidiary", "branch", "joint_venture",
                                # "nominee", "trustee", "guarantor"
    ownership_pct: float = 100.0
    control_type: str = "full"  # "full", "majority", "minority", "joint", "none"
    voting_rights_pct: Optional[float] = None  # if different from ownership
    consolidation: str = "full" # "full", "equity_method", "none"
    source_clause: Optional[ClauseParameter] = None


@dataclass
class IntercompanyFlow:
    """A cash flow channel between two entities, defined by contract."""
    flow_id: str
    from_entity_id: str
    to_entity_id: str
    flow_type: str              # "management_fee", "royalty", "intercompany_loan",
                                # "cost_recharge", "dividend", "capital_contribution",
                                # "guarantee_fee", "commission"
    pricing_basis: str          # "percentage_of_revenue", "cost_plus_markup",
                                # "fixed_annual", "variable"
    current_rate: Optional[float] = None       # current pricing (e.g. 5% of revenue)
    permitted_range: Optional[Tuple[float, float]] = None  # contract-allowed range
    annual_value: Optional[float] = None       # current annual $ flow
    currency: str = "USD"
    source_clause: Optional[ClauseParameter] = None
    tp_method: Optional[str] = None            # "tnmm", "cost_plus", "cup", etc.
    arm_length_status: Optional[str] = None    # "in_range", "out_of_range", "untested"


@dataclass
class FlowConstraint:
    """A legal constraint on cash movement between entities."""
    constraint_type: str        # "restricted_payment", "thin_cap", "ring_fence",
                                # "covenant_limit", "regulatory_capital",
                                # "withholding_tax", "exchange_control",
                                # "guarantee_chain", "subordination"
    description: str
    affected_flow: Optional[str] = None  # flow_id if specific
    affected_entity_id: Optional[str] = None
    max_amount: Optional[float] = None   # dollar ceiling
    max_rate: Optional[float] = None     # rate ceiling
    condition: Optional[str] = None      # "until covenant cured", "regulatory approval"
    source_clause: Optional[ClauseParameter] = None
    binds_until: Optional[str] = None


@dataclass
class RestructuringOption:
    """A legal change that IS possible within current contract bounds."""
    option_type: str            # "adjust_management_fee", "reassign_ip",
                                # "adjust_loan_rate", "change_cost_allocation",
                                # "establish_new_entity", "redomicile",
                                # "convert_branch_to_sub", "unwind_spv"
    description: str
    current_state: str
    proposed_state: str
    annual_tax_saving: Optional[float] = None
    annual_cash_flow_impact: Optional[float] = None
    requires_amendment: bool = False     # needs doc change
    requires_consent: List[str] = field(default_factory=list)  # who needs to approve
    tp_compliant: bool = True           # within arm's length range
    tp_range: Optional[Tuple[float, float]] = None
    implementation_steps: List[str] = field(default_factory=list)
    risks: List[str] = field(default_factory=list)
    source_clauses: List[ClauseParameter] = field(default_factory=list)


@dataclass
class GroupStructure:
    """Complete group structure intelligence for a company."""
    company_id: str
    entities: Dict[str, Entity] = field(default_factory=dict)
    # entity_id → Entity
    relationships: List[EntityRelationship] = field(default_factory=list)
    flows: List[IntercompanyFlow] = field(default_factory=list)
    constraints: List[FlowConstraint] = field(default_factory=list)
    restructuring_options: List[RestructuringOption] = field(default_factory=list)
    total_entities: int = 0
    jurisdictions: List[str] = field(default_factory=list)
    consolidation_type: str = "full"  # "full", "partial", "none"

    # Computed summaries
    total_intercompany_value: float = 0.0
    max_extractable_cash: Optional[float] = None
    # how much can be moved to top holdco given all constraints
    tp_flags: List[str] = field(default_factory=list)

    def get_entity(self, entity_id: str) -> Optional[Entity]:
        return self.entities.get(entity_id)

    def get_children(self, entity_id: str) -> List[Entity]:
        """Get direct subsidiaries of an entity."""
        return [
            e for e in self.entities.values()
            if e.parent_entity_id == entity_id
        ]

    def get_flows_from(self, entity_id: str) -> List[IntercompanyFlow]:
        return [f for f in self.flows if f.from_entity_id == entity_id]

    def get_flows_to(self, entity_id: str) -> List[IntercompanyFlow]:
        return [f for f in self.flows if f.to_entity_id == entity_id]

    def get_constraints_for(self, entity_id: str) -> List[FlowConstraint]:
        return [
            c for c in self.constraints
            if c.affected_entity_id == entity_id or c.affected_entity_id is None
        ]

    def get_root_entity(self) -> Optional[Entity]:
        """Get the top-level holdco."""
        for e in self.entities.values():
            if e.parent_entity_id is None:
                return e
        return None


# ---------------------------------------------------------------------------
# Jurisdiction tax rates (statutory corporate rates)
# ---------------------------------------------------------------------------

JURISDICTION_TAX_RATES = {
    "US": 0.21, "US-DE": 0.21, "US-CA": 0.21, "US-NY": 0.21,
    "UK": 0.25, "GB": 0.25,
    "IE": 0.125, "IRELAND": 0.125,
    "NL": 0.258, "NETHERLANDS": 0.258,
    "LU": 0.249, "LUXEMBOURG": 0.249,
    "SG": 0.17, "SINGAPORE": 0.17,
    "HK": 0.165, "HONG_KONG": 0.165,
    "KY": 0.0, "CAYMAN": 0.0, "CAYMAN_ISLANDS": 0.0,
    "BVI": 0.0, "BRITISH_VIRGIN_ISLANDS": 0.0,
    "JE": 0.0, "JERSEY": 0.0,
    "GG": 0.0, "GUERNSEY": 0.0,
    "CH": 0.15, "SWITZERLAND": 0.15,
    "DE": 0.30, "GERMANY": 0.30,
    "FR": 0.25, "FRANCE": 0.25,
    "ES": 0.25, "SPAIN": 0.25,
    "IT": 0.278, "ITALY": 0.278,  # 24% IRES + 3.9% IRAP
    "AU": 0.30, "AUSTRALIA": 0.30,
    "JP": 0.30, "JAPAN": 0.30,  # ~29.74% combined (national + local + inhabitants)
    "IN": 0.252, "INDIA": 0.252,
    "AE": 0.09, "UAE": 0.09, "DUBAI": 0.09,
    "IL": 0.23, "ISRAEL": 0.23,
    "EE": 0.20, "ESTONIA": 0.20,
    "PT": 0.21, "PORTUGAL": 0.21,
    "CY": 0.125, "CYPRUS": 0.125,
    "MT": 0.05, "MALTA": 0.05,  # 35% statutory but ~5% effective (6/7ths refund)
}

# Withholding tax rates on common intercompany flows (simplified — treaty rates vary)
WITHHOLDING_TAX_DEFAULTS = {
    # (from_jurisdiction, to_jurisdiction): {"dividend": rate, "royalty": rate, "interest": rate}
    # These are illustrative defaults; real rates depend on treaty networks
    "default": {"dividend": 0.15, "royalty": 0.15, "interest": 0.10},
    "treaty_reduced": {"dividend": 0.05, "royalty": 0.0, "interest": 0.0},
}

# Thin capitalisation safe harbour ratios by jurisdiction
THIN_CAP_RATIOS = {
    "US": 1.5,    # Section 163(j) — 30% of EBITDA but also D/E guidance
    "UK": None,   # No fixed ratio — CIGA rules
    "DE": 1.5,    # German thin cap
    "FR": 1.5,    # French thin cap
    "AU": 1.5,    # Australia
    "JP": 3.0,    # Japan is more permissive
    "IN": 1.0,    # India — very restrictive
    "NL": None,   # ATAD rules, interest limitation
    "IE": None,   # No fixed ratio
    "SG": None,   # No fixed ratio
}


# ---------------------------------------------------------------------------
# Main intelligence engine
# ---------------------------------------------------------------------------

class GroupStructureIntelligence:
    """Resolves and analyzes multi-entity group structures from legal documents."""

    def __init__(self):
        self._registry = ClauseParameterRegistry()

    def resolve_group_structure(
        self,
        company_id: str,
        params: ResolvedParameterSet,
        entity_data: Optional[List[Dict[str, Any]]] = None,
    ) -> GroupStructure:
        """
        Build complete group structure from resolved clause parameters and
        entity data.

        From extracted intercompany agreements, management agreements,
        IP licenses, guarantee agreements, loan agreements:

        1. Entity relationship map
        2. Cash flow rules between entities
        3. Cash flow constraints
        4. TP validation flags
        5. Restructuring options
        """
        structure = GroupStructure(company_id=company_id)

        # Phase 1: Build entity map
        self._build_entity_map(structure, params, entity_data)

        # Phase 2: Map intercompany flows from clause parameters
        self._map_intercompany_flows(structure, params)

        # Phase 3: Identify constraints
        self._identify_flow_constraints(structure, params)

        # Phase 4: Flag TP issues
        self._flag_tp_issues(structure, params)

        # Phase 5: Find restructuring options
        self._find_restructuring_options(structure, params)

        # Phase 6: Compute summaries
        self._compute_summaries(structure)

        return structure

    # ------------------------------------------------------------------
    # Phase 1: Entity map
    # ------------------------------------------------------------------

    def _build_entity_map(
        self,
        structure: GroupStructure,
        params: ResolvedParameterSet,
        entity_data: Optional[List[Dict[str, Any]]],
    ) -> None:
        """Build entity hierarchy from documents and explicit entity data."""

        # Source 1: Explicit entity data (from company_entities table or input)
        if entity_data:
            for ed in entity_data:
                eid = ed.get("id", ed.get("entity_id", ""))
                if not eid:
                    continue
                jurisdiction = (ed.get("jurisdiction", "") or "").upper()
                entity = Entity(
                    entity_id=eid,
                    name=ed.get("name", ""),
                    entity_type=self._classify_entity_type(ed),
                    jurisdiction=jurisdiction,
                    tax_rate=ed.get("tax_rate") or JURISDICTION_TAX_RATES.get(
                        jurisdiction, None
                    ),
                    ownership_pct=float(ed.get("ownership_pct", 100)),
                    parent_entity_id=ed.get("parent_entity_id"),
                    purpose=ed.get("purpose", ed.get("functional_role", "")),
                    incorporation_date=ed.get("incorporation_date"),
                    is_dormant=ed.get("is_dormant", False),
                    registered_capital=ed.get("registered_capital"),
                    source_documents=ed.get("source_documents", []),
                )
                structure.entities[eid] = entity

        # Source 2: Infer entities from intercompany clause parameters
        intercompany_param_types = {
            "management_fee", "royalty_rate", "intercompany_loan_terms",
            "cost_recharge", "restricted_payment", "ring_fence",
            "parent_guarantee",
        }
        for key, param in params.parameters.items():
            if param.param_type in intercompany_param_types:
                entity_name = param.applies_to
                if entity_name and entity_name not in structure.entities:
                    # Create inferred entity
                    structure.entities[entity_name] = Entity(
                        entity_id=entity_name,
                        name=entity_name,
                        entity_type="subsidiary",
                        jurisdiction="unknown",
                        source_documents=[param.source_document_id],
                    )

        # Build relationships from parent_entity_id links
        for eid, entity in structure.entities.items():
            if entity.parent_entity_id and entity.parent_entity_id in structure.entities:
                structure.relationships.append(EntityRelationship(
                    from_entity_id=entity.parent_entity_id,
                    to_entity_id=eid,
                    relationship_type="parent_subsidiary",
                    ownership_pct=entity.ownership_pct,
                    control_type=self._infer_control_type(entity.ownership_pct),
                    consolidation=self._infer_consolidation(entity.ownership_pct),
                ))

        # Extract guarantee relationships
        guarantee_params = params.get_all("parent_guarantee")
        for param in guarantee_params:
            if isinstance(param.value, dict):
                guarantor = param.value.get("guarantor", "")
                beneficiary = param.applies_to
                if guarantor and beneficiary:
                    structure.relationships.append(EntityRelationship(
                        from_entity_id=guarantor,
                        to_entity_id=beneficiary,
                        relationship_type="guarantor",
                        ownership_pct=0,
                        control_type="none",
                        consolidation="none",
                        source_clause=param,
                    ))

        structure.total_entities = len(structure.entities)
        structure.jurisdictions = list({
            e.jurisdiction for e in structure.entities.values()
            if e.jurisdiction and e.jurisdiction != "unknown"
        })

    def _classify_entity_type(self, ed: Dict[str, Any]) -> str:
        """Classify entity type from data."""
        explicit = (ed.get("entity_type", "") or "").lower()
        if explicit:
            return explicit

        name = (ed.get("name", "") or "").lower()
        role = (ed.get("functional_role", "") or "").lower()

        if any(k in name for k in ("holdco", "holding", "holdings", "group")):
            return "holdco"
        if any(k in name for k in ("spv", "special purpose")):
            return "spv"
        if any(k in name for k in ("ip", "intellectual", "technology")):
            return "ip_holdco"
        if any(k in name for k in ("finance", "treasury", "funding")):
            return "finance_co"
        if "branch" in name:
            return "branch"
        if "dormant" in name or ed.get("is_dormant"):
            return "dormant"

        if "ip" in role or "licensing" in role:
            return "ip_holdco"
        if "financing" in role or "treasury" in role:
            return "finance_co"
        if "operating" in role or "services" in role or "sales" in role:
            return "opco"

        return "subsidiary"

    def _infer_control_type(self, ownership_pct: float) -> str:
        if ownership_pct > 50:
            return "full" if ownership_pct >= 95 else "majority"
        elif ownership_pct == 50:
            return "joint"
        else:
            return "minority"

    def _infer_consolidation(self, ownership_pct: float) -> str:
        if ownership_pct > 50:
            return "full"
        elif ownership_pct >= 20:
            return "equity_method"
        else:
            return "none"

    # ------------------------------------------------------------------
    # Phase 2: Intercompany flows
    # ------------------------------------------------------------------

    def _map_intercompany_flows(
        self,
        structure: GroupStructure,
        params: ResolvedParameterSet,
    ) -> None:
        """Map all intercompany cash flows from clause parameters."""
        flow_count = 0

        # Management fees
        for param in params.get_all("management_fee"):
            flow_count += 1
            rate = param.value if isinstance(param.value, (int, float)) else None
            from_eid, to_eid = self._infer_flow_direction(
                param, structure, "management_fee"
            )
            structure.flows.append(IntercompanyFlow(
                flow_id=f"mf_{flow_count}",
                from_entity_id=from_eid,
                to_entity_id=to_eid,
                flow_type="management_fee",
                pricing_basis="percentage_of_revenue",
                current_rate=rate,
                permitted_range=self._extract_permitted_range(param),
                source_clause=param,
                tp_method="tnmm",
                arm_length_status="untested",
            ))

        # Royalties
        for param in params.get_all("royalty_rate"):
            flow_count += 1
            rate = param.value if isinstance(param.value, (int, float)) else None
            from_eid, to_eid = self._infer_flow_direction(
                param, structure, "royalty"
            )
            structure.flows.append(IntercompanyFlow(
                flow_id=f"roy_{flow_count}",
                from_entity_id=from_eid,
                to_entity_id=to_eid,
                flow_type="royalty",
                pricing_basis="percentage_of_revenue",
                current_rate=rate,
                permitted_range=self._extract_permitted_range(param),
                source_clause=param,
                tp_method="cup",
                arm_length_status="untested",
            ))

        # Intercompany loans
        for param in params.get_all("intercompany_loan_terms"):
            flow_count += 1
            val = param.value if isinstance(param.value, dict) else {}
            rate = val.get("interest_rate")
            principal = val.get("principal")
            from_eid, to_eid = self._infer_flow_direction(
                param, structure, "intercompany_loan"
            )
            structure.flows.append(IntercompanyFlow(
                flow_id=f"loan_{flow_count}",
                from_entity_id=from_eid,
                to_entity_id=to_eid,
                flow_type="intercompany_loan",
                pricing_basis="interest_rate",
                current_rate=rate,
                annual_value=principal,
                permitted_range=self._extract_permitted_range(param),
                source_clause=param,
                tp_method="cup",
                arm_length_status="untested",
            ))

        # Cost recharges
        for param in params.get_all("cost_recharge"):
            flow_count += 1
            val = param.value if isinstance(param.value, dict) else {}
            markup = val.get("markup") if isinstance(val, dict) else param.value
            from_eid, to_eid = self._infer_flow_direction(
                param, structure, "cost_recharge"
            )
            structure.flows.append(IntercompanyFlow(
                flow_id=f"cr_{flow_count}",
                from_entity_id=from_eid,
                to_entity_id=to_eid,
                flow_type="cost_recharge",
                pricing_basis="cost_plus_markup",
                current_rate=markup if isinstance(markup, (int, float)) else None,
                source_clause=param,
                tp_method="cost_plus",
                arm_length_status="untested",
            ))

    def _infer_flow_direction(
        self,
        param: ClauseParameter,
        structure: GroupStructure,
        flow_type: str,
    ) -> Tuple[str, str]:
        """Infer from/to entity IDs for a flow from clause context."""
        entity_name = param.applies_to
        root = structure.get_root_entity()
        root_id = root.entity_id if root else "holdco"

        # Fees/royalties typically flow from opco → holdco/ip_holdco
        # Loans flow from finance_co/holdco → subsidiary
        # Cost recharges flow from shared_services → recipients
        if flow_type in ("management_fee", "royalty"):
            return entity_name, root_id
        elif flow_type == "intercompany_loan":
            return root_id, entity_name
        elif flow_type == "cost_recharge":
            return entity_name, root_id

        return entity_name, root_id

    def _extract_permitted_range(
        self, param: ClauseParameter
    ) -> Optional[Tuple[float, float]]:
        """Extract permitted pricing range from clause text or value."""
        if isinstance(param.value, dict):
            low = param.value.get("min") or param.value.get("minimum")
            high = param.value.get("max") or param.value.get("maximum")
            if low is not None and high is not None:
                return (float(low), float(high))
            # "up to X%" pattern
            up_to = param.value.get("up_to") or param.value.get("maximum")
            if up_to is not None:
                return (0.0, float(up_to))

        # Parse from source quote
        import re
        quote = param.source_quote or ""
        # "up to 8%" pattern
        m = re.search(r'up\s+to\s+(\d+\.?\d*)\s*%', quote, re.I)
        if m:
            return (0.0, float(m.group(1)) / 100)
        # "between X% and Y%" pattern
        m = re.search(r'between\s+(\d+\.?\d*)\s*%\s*and\s+(\d+\.?\d*)\s*%', quote, re.I)
        if m:
            return (float(m.group(1)) / 100, float(m.group(2)) / 100)
        # "not less than X% and not more than Y%"
        m = re.search(
            r'not\s+less\s+than\s+(\d+\.?\d*)\s*%.*not\s+more\s+than\s+(\d+\.?\d*)\s*%',
            quote, re.I,
        )
        if m:
            return (float(m.group(1)) / 100, float(m.group(2)) / 100)

        return None

    # ------------------------------------------------------------------
    # Phase 3: Flow constraints
    # ------------------------------------------------------------------

    def _identify_flow_constraints(
        self,
        structure: GroupStructure,
        params: ResolvedParameterSet,
    ) -> None:
        """Identify all legal constraints on intercompany cash movement."""

        # Restricted payment covenants
        for param in params.get_all("restricted_payment"):
            val = param.value if isinstance(param.value, dict) else {}
            max_amt = val.get("max_amount") if isinstance(val, dict) else None
            structure.constraints.append(FlowConstraint(
                constraint_type="restricted_payment",
                description=(
                    f"Restricted payment covenant limits distributions from "
                    f"{param.applies_to} ({param.section_reference})"
                ),
                affected_entity_id=param.applies_to,
                max_amount=max_amt,
                source_clause=param,
                binds_until=param.expiry_date,
            ))

        # Ring-fencing provisions
        for param in params.get_all("ring_fence"):
            structure.constraints.append(FlowConstraint(
                constraint_type="ring_fence",
                description=(
                    f"Ring-fencing provision isolates {param.applies_to}'s assets. "
                    f"Cash cannot be upstreamed without restriction "
                    f"({param.section_reference})"
                ),
                affected_entity_id=param.applies_to,
                source_clause=param,
            ))

        # Covenant-derived distribution limits
        for param in params.get_all("covenant_threshold"):
            if isinstance(param.value, dict):
                for metric, threshold in param.value.items():
                    structure.constraints.append(FlowConstraint(
                        constraint_type="covenant_limit",
                        description=(
                            f"Covenant on {param.applies_to}: {metric} must remain "
                            f"above {threshold}. Distributions that would breach this "
                            f"covenant are blocked ({param.section_reference})"
                        ),
                        affected_entity_id=param.applies_to,
                        condition=f"{metric} >= {threshold}",
                        source_clause=param,
                    ))

        # Thin capitalisation constraints from jurisdiction rules
        for eid, entity in structure.entities.items():
            jur = entity.jurisdiction.upper()
            thin_cap_ratio = THIN_CAP_RATIOS.get(jur)
            if thin_cap_ratio:
                # Check if intercompany loans to this entity exist
                loans_to = [
                    f for f in structure.flows
                    if f.to_entity_id == eid and f.flow_type == "intercompany_loan"
                ]
                if loans_to:
                    structure.constraints.append(FlowConstraint(
                        constraint_type="thin_cap",
                        description=(
                            f"Thin capitalisation rule in {entity.jurisdiction}: "
                            f"D/E ratio capped at {thin_cap_ratio}:1. Interest deduction "
                            f"on intercompany debt may be limited."
                        ),
                        affected_entity_id=eid,
                        max_rate=thin_cap_ratio,
                        condition=f"debt_to_equity <= {thin_cap_ratio}",
                    ))

        # Withholding tax on cross-border flows
        for flow in structure.flows:
            from_entity = structure.entities.get(flow.from_entity_id)
            to_entity = structure.entities.get(flow.to_entity_id)
            if not from_entity or not to_entity:
                continue
            if from_entity.jurisdiction != to_entity.jurisdiction:
                wht_type = {
                    "royalty": "royalty",
                    "intercompany_loan": "interest",
                    "management_fee": "royalty",  # many jurisdictions treat as royalty
                    "dividend": "dividend",
                }.get(flow.flow_type)
                if wht_type:
                    default_rate = WITHHOLDING_TAX_DEFAULTS["default"].get(wht_type, 0.15)
                    structure.constraints.append(FlowConstraint(
                        constraint_type="withholding_tax",
                        description=(
                            f"Withholding tax on {flow.flow_type} from "
                            f"{from_entity.jurisdiction} to {to_entity.jurisdiction}: "
                            f"up to {default_rate*100:.0f}% (may be reduced by treaty). "
                            f"Verify treaty rate applies."
                        ),
                        affected_flow=flow.flow_id,
                        affected_entity_id=flow.from_entity_id,
                        max_rate=default_rate,
                    ))

        # Guarantee chain exposure
        guarantee_rels = [
            r for r in structure.relationships
            if r.relationship_type == "guarantor"
        ]
        if len(guarantee_rels) > 1:
            chain = [f"{r.from_entity_id} → {r.to_entity_id}" for r in guarantee_rels]
            structure.constraints.append(FlowConstraint(
                constraint_type="guarantee_chain",
                description=(
                    f"Guarantee chain across {len(guarantee_rels)} entities: "
                    f"{', '.join(chain)}. Default at any point triggers chain. "
                    f"Review cross-guarantee exposure."
                ),
            ))

    # ------------------------------------------------------------------
    # Phase 4: TP compliance flags
    # ------------------------------------------------------------------

    def _flag_tp_issues(
        self,
        structure: GroupStructure,
        params: ResolvedParameterSet,
    ) -> None:
        """Flag transfer pricing issues without running full TP analysis.

        Full TP analysis requires comparables (via TransferPricingEngine.analyze()).
        This method flags structural issues that need attention.
        """
        for flow in structure.flows:
            # Flag 1: Cross-border flow with no TP method assigned
            from_entity = structure.entities.get(flow.from_entity_id)
            to_entity = structure.entities.get(flow.to_entity_id)
            if from_entity and to_entity:
                if from_entity.jurisdiction != to_entity.jurisdiction:
                    if flow.arm_length_status == "untested":
                        structure.tp_flags.append(
                            f"Untested cross-border {flow.flow_type} from "
                            f"{from_entity.name} ({from_entity.jurisdiction}) to "
                            f"{to_entity.name} ({to_entity.jurisdiction}). "
                            f"Current rate: {flow.current_rate}. "
                            f"Run TP benchmarking."
                        )

            # Flag 2: Flow to zero-tax jurisdiction
            if to_entity and to_entity.tax_rate is not None and to_entity.tax_rate == 0:
                structure.tp_flags.append(
                    f"{flow.flow_type} flows to {to_entity.name} in "
                    f"{to_entity.jurisdiction} (0% tax). "
                    f"High scrutiny — ensure economic substance and arm's length pricing."
                )

            # Flag 3: Management fee to holdco with no substance
            if (flow.flow_type == "management_fee"
                    and to_entity
                    and to_entity.entity_type == "holdco"):
                # Check if holdco has substance (employees, assets)
                # For now, flag for review
                structure.tp_flags.append(
                    f"Management fee to {to_entity.name} (holdco). "
                    f"Verify holdco has sufficient substance to justify fee "
                    f"(employees, decision-making, assets)."
                )

            # Flag 4: IP royalty flowing to entity that didn't develop the IP
            if flow.flow_type == "royalty" and to_entity:
                if to_entity.entity_type == "ip_holdco":
                    structure.tp_flags.append(
                        f"Royalty to {to_entity.name} (IP holdco). "
                        f"Under BEPS Action 8-10, IP income must align with DEMPE "
                        f"functions (Development, Enhancement, Maintenance, Protection, "
                        f"Exploitation). Verify DEMPE analysis supports this structure."
                    )

            # Flag 5: Intercompany loan at rate far from market
            if flow.flow_type == "intercompany_loan" and flow.current_rate:
                # Rough check — real validation needs comparables
                if flow.current_rate < 0.01 or flow.current_rate > 0.20:
                    structure.tp_flags.append(
                        f"Intercompany loan rate of {flow.current_rate*100:.1f}% "
                        f"appears outside normal range. Benchmark against "
                        f"comparable third-party lending rates."
                    )

    # ------------------------------------------------------------------
    # Phase 5: Restructuring options
    # ------------------------------------------------------------------

    def _find_restructuring_options(
        self,
        structure: GroupStructure,
        params: ResolvedParameterSet,
    ) -> None:
        """Identify what CAN be changed within current legal and TP bounds."""

        # Option 1: Adjust management fees within permitted range
        for flow in structure.flows:
            if flow.flow_type == "management_fee" and flow.permitted_range:
                low, high = flow.permitted_range
                current = flow.current_rate or 0
                if current < high:
                    from_entity = structure.entities.get(flow.from_entity_id)
                    to_entity = structure.entities.get(flow.to_entity_id)
                    if from_entity and to_entity:
                        from_rate = from_entity.tax_rate or 0.25
                        to_rate = to_entity.tax_rate or 0.25
                        if to_rate < from_rate:
                            # Moving fee higher shifts income to lower-tax entity
                            rate_diff = high - current
                            structure.restructuring_options.append(RestructuringOption(
                                option_type="adjust_management_fee",
                                description=(
                                    f"Increase management fee from {current*100:.1f}% "
                                    f"to {high*100:.1f}% (contract permits up to "
                                    f"{high*100:.1f}%). Shifts income from "
                                    f"{from_entity.jurisdiction} ({from_rate*100:.0f}%) "
                                    f"to {to_entity.jurisdiction} ({to_rate*100:.0f}%)."
                                ),
                                current_state=f"{current*100:.1f}% management fee",
                                proposed_state=f"{high*100:.1f}% management fee",
                                requires_amendment=False,
                                tp_compliant=True,  # Within contractual range; TP still needs checking
                                tp_range=flow.permitted_range,
                                source_clauses=[flow.source_clause] if flow.source_clause else [],
                                risks=[
                                    "TP authorities may challenge if rate at top of range",
                                    f"Verify {to_entity.name} has substance to justify fee",
                                ],
                            ))

            # Option 2: Adjust intercompany loan rate
            if flow.flow_type == "intercompany_loan" and flow.permitted_range:
                low, high = flow.permitted_range
                current = flow.current_rate or 0
                from_entity = structure.entities.get(flow.from_entity_id)
                to_entity = structure.entities.get(flow.to_entity_id)
                if from_entity and to_entity:
                    if (to_entity.tax_rate or 0) > (from_entity.tax_rate or 0):
                        # Higher rate at borrower = interest deduction more valuable
                        if current < high:
                            structure.restructuring_options.append(RestructuringOption(
                                option_type="adjust_loan_rate",
                                description=(
                                    f"Increase intercompany loan rate from "
                                    f"{current*100:.1f}% to {high*100:.1f}%. "
                                    f"Interest deduction at {to_entity.jurisdiction} "
                                    f"({(to_entity.tax_rate or 0)*100:.0f}% rate) is "
                                    f"more valuable than interest income at "
                                    f"{from_entity.jurisdiction} "
                                    f"({(from_entity.tax_rate or 0)*100:.0f}% rate)."
                                ),
                                current_state=f"{current*100:.1f}% interest rate",
                                proposed_state=f"{high*100:.1f}% interest rate",
                                requires_amendment=False,
                                tp_range=flow.permitted_range,
                                source_clauses=[flow.source_clause] if flow.source_clause else [],
                                risks=[
                                    "Thin cap rules may limit interest deduction",
                                    "Rate must be within arm's length range",
                                ],
                            ))

        # Option 3: Identify entities that could be consolidated/wound down
        for eid, entity in structure.entities.items():
            if entity.is_dormant:
                structure.restructuring_options.append(RestructuringOption(
                    option_type="unwind_entity",
                    description=(
                        f"Wind down dormant entity {entity.name} "
                        f"({entity.jurisdiction}). No active operations. "
                        f"Saves annual maintenance/compliance costs."
                    ),
                    current_state="Dormant entity maintained",
                    proposed_state="Entity wound down / struck off",
                    risks=["Check for residual liabilities or guarantees"],
                    implementation_steps=[
                        "Verify no outstanding contracts reference this entity",
                        "Check guarantee chains",
                        "File dissolution documents",
                    ],
                ))

            # SPV with no obvious ongoing purpose
            if entity.entity_type == "spv":
                flows_involving = [
                    f for f in structure.flows
                    if f.from_entity_id == eid or f.to_entity_id == eid
                ]
                if not flows_involving:
                    structure.restructuring_options.append(RestructuringOption(
                        option_type="unwind_spv",
                        description=(
                            f"SPV {entity.name} has no active intercompany flows. "
                            f"Consider unwinding if original purpose is complete."
                        ),
                        current_state="SPV maintained with no active flows",
                        proposed_state="SPV wound down",
                        risks=["SPV may hold ring-fenced assets — verify"],
                    ))

        # Option 4: IP reassignment opportunity
        ip_holdcos = [
            e for e in structure.entities.values()
            if e.entity_type == "ip_holdco"
        ]
        if ip_holdcos:
            # Check if there's a lower-tax jurisdiction available
            min_tax_entity = min(
                [e for e in structure.entities.values() if e.tax_rate is not None],
                key=lambda e: e.tax_rate or 1.0,
                default=None,
            )
            for ip_co in ip_holdcos:
                if (min_tax_entity
                        and min_tax_entity.entity_id != ip_co.entity_id
                        and (min_tax_entity.tax_rate or 0) < (ip_co.tax_rate or 0)):
                    structure.restructuring_options.append(RestructuringOption(
                        option_type="reassign_ip",
                        description=(
                            f"IP currently held in {ip_co.name} "
                            f"({ip_co.jurisdiction}, {(ip_co.tax_rate or 0)*100:.0f}%). "
                            f"Could be transferred to {min_tax_entity.name} "
                            f"({min_tax_entity.jurisdiction}, "
                            f"{(min_tax_entity.tax_rate or 0)*100:.0f}%). "
                            f"Requires DEMPE substance at target entity."
                        ),
                        current_state=f"IP in {ip_co.jurisdiction}",
                        proposed_state=f"IP in {min_tax_entity.jurisdiction}",
                        requires_amendment=True,
                        requires_consent=["board", "ip_licensees"],
                        risks=[
                            "BEPS Action 8-10 DEMPE requirements",
                            "Exit tax on IP transfer",
                            "Existing license agreements may restrict transfer",
                            "Substance requirements at target jurisdiction",
                        ],
                    ))

    # ------------------------------------------------------------------
    # Phase 6: Summaries
    # ------------------------------------------------------------------

    def _compute_summaries(self, structure: GroupStructure) -> None:
        """Compute aggregate summaries."""
        total_ic = 0.0
        for flow in structure.flows:
            if flow.annual_value:
                total_ic += abs(flow.annual_value)
        structure.total_intercompany_value = total_ic

        # Estimate max extractable cash to top holdco
        root = structure.get_root_entity()
        if root:
            structure.max_extractable_cash = self._estimate_max_extraction(
                structure, root.entity_id
            )

    def _estimate_max_extraction(
        self,
        structure: GroupStructure,
        target_entity_id: str,
    ) -> Optional[float]:
        """Estimate max cash that can move to target entity given constraints."""
        # Sum all flows directed to target
        inflows = sum(
            f.annual_value or 0
            for f in structure.flows
            if f.to_entity_id == target_entity_id
        )

        # Check for caps from constraints
        caps = []
        for constraint in structure.constraints:
            if constraint.constraint_type == "restricted_payment":
                if constraint.max_amount:
                    caps.append(constraint.max_amount)

        if caps:
            return min(inflows, min(caps))
        return inflows if inflows > 0 else None

    # ------------------------------------------------------------------
    # Integration: Build cascade edges for group-level dependencies
    # ------------------------------------------------------------------

    def build_group_cascade_edges(
        self,
        structure: GroupStructure,
        params: ResolvedParameterSet,
    ) -> List[CascadeEdge]:
        """Build cascade edges for group-level legal dependencies.

        These get added to the CascadeGraph alongside instrument-level edges.

        Group-level cascades:
          - Subsidiary default → parent guarantee triggered
          - Covenant breach at sub → restricted payment at holdco
          - Ring-fence → blocks upstream cash flow
          - Cross-border flow change → TP compliance shift
          - Entity restructuring → flow rerouting
        """
        edges: List[CascadeEdge] = []

        # 1. Subsidiary default → parent guarantee
        for rel in structure.relationships:
            if rel.relationship_type == "guarantor" and rel.source_clause:
                edges.append(CascadeEdge(
                    trigger_param=f"default:{rel.to_entity_id}",
                    affected_param=f"liability:{rel.from_entity_id}",
                    relationship="triggers_guarantee",
                    conditions={"when": f"default at {rel.to_entity_id}"},
                    source_clause=rel.source_clause,
                    computation="group_guarantee_cascade",
                    description=(
                        f"Default at {rel.to_entity_id} triggers guarantee "
                        f"obligation for {rel.from_entity_id}"
                    ),
                ))

        # 2. Covenant breach → restricted payments
        for constraint in structure.constraints:
            if (constraint.constraint_type == "covenant_limit"
                    and constraint.source_clause
                    and constraint.affected_entity_id):
                # Dividend/distribution flows from this entity are blocked on breach
                affected_flows = [
                    f for f in structure.flows
                    if f.from_entity_id == constraint.affected_entity_id
                ]
                for flow in affected_flows:
                    edges.append(CascadeEdge(
                        trigger_param=f"covenant_breach:{constraint.affected_entity_id}",
                        affected_param=f"flow_blocked:{flow.flow_id}",
                        relationship="blocks_flow",
                        conditions={"when": constraint.condition or "covenant breached"},
                        source_clause=constraint.source_clause,
                        computation="group_flow_block",
                        description=(
                            f"Covenant breach at {constraint.affected_entity_id} "
                            f"blocks {flow.flow_type} flow ({flow.flow_id})"
                        ),
                    ))

        # 3. Ring-fence → blocks upstream
        for constraint in structure.constraints:
            if constraint.constraint_type == "ring_fence" and constraint.affected_entity_id:
                outflows = structure.get_flows_from(constraint.affected_entity_id)
                for flow in outflows:
                    if flow.source_clause:
                        edges.append(CascadeEdge(
                            trigger_param=f"ring_fence:{constraint.affected_entity_id}",
                            affected_param=f"flow_blocked:{flow.flow_id}",
                            relationship="ring_fence_blocks",
                            conditions={"when": "ring-fence active"},
                            source_clause=flow.source_clause,
                            computation="group_ring_fence",
                            description=(
                                f"Ring-fence on {constraint.affected_entity_id} "
                                f"restricts {flow.flow_type} outflow"
                            ),
                        ))

        return edges

    # ------------------------------------------------------------------
    # Integration: Group-level decision context for DecisionEngine
    # ------------------------------------------------------------------

    def get_group_decision_context(
        self,
        structure: GroupStructure,
    ) -> Dict[str, Any]:
        """Provide group context to the DecisionEngine for capital decisions.

        The DecisionEngine uses this to:
          - Check if a raise/debt at sub level requires holdco consent
          - Understand where new capital should sit (which entity)
          - Factor in cross-border costs (WHT, TP) of moving capital
          - Identify blocked options (e.g. ring-fenced entity can't take on debt)
        """
        context: Dict[str, Any] = {
            "total_entities": structure.total_entities,
            "jurisdictions": structure.jurisdictions,
            "intercompany_value": structure.total_intercompany_value,
            "max_extractable_to_holdco": structure.max_extractable_cash,
            "tp_flags_count": len(structure.tp_flags),
        }

        # Entity-level constraints that block actions
        blocked_entities: Dict[str, List[str]] = {}
        for constraint in structure.constraints:
            if constraint.affected_entity_id:
                eid = constraint.affected_entity_id
                blocked_entities.setdefault(eid, []).append(
                    f"{constraint.constraint_type}: {constraint.description}"
                )
        context["entity_constraints"] = blocked_entities

        # Flow optimization opportunities
        context["restructuring_options_count"] = len(structure.restructuring_options)
        context["restructuring_options"] = [
            {
                "type": opt.option_type,
                "description": opt.description,
                "requires_amendment": opt.requires_amendment,
                "requires_consent": opt.requires_consent,
            }
            for opt in structure.restructuring_options
        ]

        return context

    # ------------------------------------------------------------------
    # Query interface: "Can I move $X from A to B?"
    # ------------------------------------------------------------------

    def can_move_cash(
        self,
        structure: GroupStructure,
        from_entity_id: str,
        to_entity_id: str,
        amount: float,
    ) -> Dict[str, Any]:
        """
        Answer: "Can I move $X from entity A to entity B?"

        Checks:
          1. Is there an existing intercompany flow channel?
          2. What is the permitted range for that channel?
          3. Are there covenant/restricted payment constraints?
          4. Is there a ring-fence?
          5. Withholding tax implications?
          6. TP compliance of the proposed amount?
        """
        result: Dict[str, Any] = {
            "from_entity": from_entity_id,
            "to_entity": to_entity_id,
            "requested_amount": amount,
            "can_move": True,
            "max_movable": amount,
            "channels": [],
            "blockers": [],
            "costs": [],
            "recommendations": [],
        }

        # Find available channels
        channels = [
            f for f in structure.flows
            if f.from_entity_id == from_entity_id and f.to_entity_id == to_entity_id
        ]
        if not channels:
            # Check reverse direction
            reverse = [
                f for f in structure.flows
                if f.from_entity_id == to_entity_id and f.to_entity_id == from_entity_id
            ]
            if reverse:
                result["recommendations"].append(
                    f"No direct flow from {from_entity_id} to {to_entity_id}, "
                    f"but there are flows in the reverse direction. "
                    f"Consider establishing a new intercompany agreement."
                )
            result["can_move"] = False
            result["max_movable"] = 0
            result["blockers"].append(
                f"No intercompany flow channel exists between "
                f"{from_entity_id} and {to_entity_id}. "
                f"An intercompany agreement would need to be established."
            )
            return result

        for channel in channels:
            ch_info: Dict[str, Any] = {
                "flow_id": channel.flow_id,
                "flow_type": channel.flow_type,
                "current_rate": channel.current_rate,
                "permitted_range": channel.permitted_range,
            }

            # Check permitted range
            if channel.permitted_range:
                low, high = channel.permitted_range
                # This is a rate check — need to convert amount to rate
                ch_info["max_rate"] = high
                ch_info["min_rate"] = low

            result["channels"].append(ch_info)

        # Check constraints
        constraints = structure.get_constraints_for(from_entity_id)
        for c in constraints:
            if c.constraint_type == "restricted_payment":
                if c.max_amount and amount > c.max_amount:
                    result["can_move"] = False
                    result["max_movable"] = min(result["max_movable"], c.max_amount)
                    result["blockers"].append(
                        f"Restricted payment covenant limits to "
                        f"${c.max_amount:,.0f} ({c.source_clause.section_reference if c.source_clause else 'unknown'})"
                    )
            elif c.constraint_type == "ring_fence":
                result["can_move"] = False
                result["max_movable"] = 0
                result["blockers"].append(
                    f"Ring-fence provision: {c.description}"
                )
            elif c.constraint_type == "covenant_limit":
                result["recommendations"].append(
                    f"Verify covenant headroom before transfer: {c.condition}"
                )

        # Withholding tax
        from_entity = structure.entities.get(from_entity_id)
        to_entity = structure.entities.get(to_entity_id)
        if from_entity and to_entity:
            if from_entity.jurisdiction != to_entity.jurisdiction:
                wht = WITHHOLDING_TAX_DEFAULTS["default"]
                # Pick most relevant type based on available channels
                flow_types = {c.flow_type for c in channels}
                for ft in flow_types:
                    wht_key = {
                        "royalty": "royalty",
                        "intercompany_loan": "interest",
                        "management_fee": "royalty",
                        "dividend": "dividend",
                    }.get(ft)
                    if wht_key:
                        rate = wht.get(wht_key, 0.15)
                        tax_cost = amount * rate
                        result["costs"].append({
                            "type": f"withholding_tax_{wht_key}",
                            "rate": rate,
                            "amount": tax_cost,
                            "note": (
                                f"{rate*100:.0f}% WHT on {ft} "
                                f"({from_entity.jurisdiction} → {to_entity.jurisdiction}). "
                                f"Check treaty rate."
                            ),
                        })

        return result

    # ------------------------------------------------------------------
    # Integration with TransferPricingEngine
    # ------------------------------------------------------------------

    async def validate_tp_for_flows(
        self,
        structure: GroupStructure,
        tp_engine: Any,  # TransferPricingEngine instance
    ) -> List[Dict[str, Any]]:
        """Run TP validation on all intercompany flows that have matching
        transactions in the tp system.

        This bridges group_structure_intelligence → transfer_pricing_engine:
          1. For each intercompany flow, find the matching IC transaction
          2. If a comparable search exists, run TP analysis
          3. Update flow's arm_length_status based on result
          4. Return validation results
        """
        from app.core.database import supabase_service
        client = supabase_service.get_client()

        results = []
        for flow in structure.flows:
            # Try to find matching IC transaction
            matching = client.from_("intercompany_transactions") \
                .select("id, benchmark_status") \
                .eq("from_entity_id", flow.from_entity_id) \
                .eq("to_entity_id", flow.to_entity_id) \
                .limit(1) \
                .execute().data

            if not matching:
                results.append({
                    "flow_id": flow.flow_id,
                    "flow_type": flow.flow_type,
                    "status": "no_transaction",
                    "note": "No matching IC transaction found. Create one for TP benchmarking.",
                })
                continue

            txn = matching[0]
            txn_id = txn["id"]
            current_status = txn.get("benchmark_status")

            if current_status == "in_range":
                flow.arm_length_status = "in_range"
                results.append({
                    "flow_id": flow.flow_id,
                    "flow_type": flow.flow_type,
                    "transaction_id": txn_id,
                    "status": "in_range",
                    "note": "Previously benchmarked — in arm's length range.",
                })
            elif current_status == "out_of_range":
                flow.arm_length_status = "out_of_range"
                results.append({
                    "flow_id": flow.flow_id,
                    "flow_type": flow.flow_type,
                    "transaction_id": txn_id,
                    "status": "out_of_range",
                    "note": "Previously benchmarked — OUT of arm's length range. Adjustment needed.",
                })
            else:
                # Try to run analysis
                try:
                    analysis = await tp_engine.analyze(txn_id)
                    status = analysis.get("benchmark_status", "needs_review")
                    flow.arm_length_status = status
                    results.append({
                        "flow_id": flow.flow_id,
                        "flow_type": flow.flow_type,
                        "transaction_id": txn_id,
                        "status": status,
                        "analysis_id": analysis.get("analysis_id"),
                        "arm_length": analysis.get("arm_length_assessment"),
                    })
                except Exception as e:
                    results.append({
                        "flow_id": flow.flow_id,
                        "flow_type": flow.flow_type,
                        "transaction_id": txn_id,
                        "status": "error",
                        "error": str(e),
                    })

        return results
