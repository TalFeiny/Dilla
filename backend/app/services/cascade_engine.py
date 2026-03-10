"""
Cascade Engine (Layer 2)

Instruments don't exist in isolation. Anti-dilution reprices shares. Repricing
shifts ownership. Ownership shifts change governance thresholds. Covenant breaches
accelerate repayment. Conversion triggers create new cap table entries.

This engine builds a directed graph of legal dependencies from resolved clause
parameters, then simulates what happens when any parameter changes — tracing
every downstream effect with full attribution to the specific clause that
causes it.

It also understands what the DRAFTING means:
  - "2x participating" doesn't just mean "2x" — it means the investor gets paid
    2x their money back AND participates pro-rata in the remainder. That's a
    fundamentally different economic deal than "2x non-participating".
  - "Full ratchet anti-dilution" doesn't just mean "repricing" — it means if
    the company raises at ANY lower price, ALL shares get repriced to that new
    price. One share sold at $0.01 reprices millions of shares.
  - "Cross-default" means a default on Loan A triggers automatic default on
    Loan B — even if Loan B is performing perfectly.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from app.services.clause_parameter_registry import (
    ClauseParameter,
    ResolvedParameterSet,
    VANILLA_DEFAULTS,
)

# Lazy imports for group structure (avoids circular)
_GroupStructure = None


def _get_group_structure_type():
    global _GroupStructure
    if _GroupStructure is None:
        from app.services.group_structure_intelligence import GroupStructure
        _GroupStructure = GroupStructure
    return _GroupStructure


logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class CascadeEdge:
    """A legal dependency between two parameters."""
    trigger_param: str          # "round_price:series_c"
    affected_param: str         # "conversion_price:series_a"
    relationship: str           # "triggers_repricing", "accelerates_payment",
                                # "forces_conversion", "requires_consent", "creates_default"
    conditions: Dict[str, Any]  # {"when": "new_price < original_price"}
    source_clause: ClauseParameter
    computation: str            # which engine function computes the effect
    description: str            # human-readable: "Full ratchet anti-dilution fires"


@dataclass
class CascadeStep:
    """A single step in a cascade simulation."""
    step_number: int
    param_affected: str
    old_value: Any
    new_value: Any
    source_clause: ClauseParameter
    description: str             # "Series A price reprices from $1.00 to $0.50"
    financial_impact: Optional[float] = None  # dollar amount where computable
    downstream_triggers: List[str] = field(default_factory=list)


@dataclass
class Breakpoint:
    """A value where cascade behavior changes."""
    variable: str               # "exit_value", "round_price", "revenue"
    value: float                # the breakpoint value
    description: str            # "Preference stack fully paid"
    clauses_involved: List[str]  # clause IDs
    stakeholder_impact: Dict[str, str]  # stakeholder → what changes for them
    before_behavior: str
    after_behavior: str


@dataclass
class Constraint:
    """An actionable constraint on the company's actions."""
    constraint_type: str         # "consent_required", "covenant", "preemption",
                                 # "transfer_restriction", "restricted_payment"
    description: str             # "Cannot raise debt above $2M without lender consent"
    source_clause: ClauseParameter
    binds_until: Optional[str]   # date or condition
    current_headroom: Optional[float] = None  # how far from breach/trigger
    next_test_date: Optional[str] = None


@dataclass
class CascadeResult:
    """Complete result of a cascade simulation."""
    trigger: str
    trigger_value: Any
    steps: List[CascadeStep]
    # Terminal effects — the final state after all cascading
    cap_table_delta: Dict[str, float] = field(default_factory=dict)
    # stakeholder → ownership change
    waterfall_delta: Dict[str, Dict[str, float]] = field(default_factory=dict)
    # exit_value → stakeholder → proceeds change
    cash_flow_delta: Dict[str, float] = field(default_factory=dict)
    # category → change in periodic obligations
    governance_changes: List[str] = field(default_factory=list)
    exposure_changes: Dict[str, float] = field(default_factory=dict)
    # person → liability change


# ---------------------------------------------------------------------------
# Drafting interpretation — what legal language actually means financially
# ---------------------------------------------------------------------------

# Maps drafting patterns to their financial meaning
DRAFTING_INTERPRETATIONS = {
    "liquidation_preference": {
        # What "2x participating" actually means
        "interpretation": (
            "Liquidation preference determines the priority of payouts in an exit. "
            "{multiple}x means the investor gets {multiple} times their investment "
            "back before common shareholders see anything. "
        ),
        "participating_addendum": (
            "PARTICIPATING means after getting their preference, they ALSO share "
            "pro-rata in the remaining proceeds alongside common. This is sometimes "
            "called 'double-dipping'. "
        ),
        "non_participating_addendum": (
            "NON-PARTICIPATING means the investor chooses: take the preference OR "
            "convert to common and share pro-rata. Not both. This is founder-friendlier. "
        ),
        "cap_addendum": (
            "CAPPED at {cap}x means participation stops once the investor has received "
            "{cap}x their investment total (preference + participation combined). "
            "Above this point they convert to common. "
        ),
    },
    "anti_dilution": {
        "full_ratchet": (
            "FULL RATCHET means if ANY shares are sold at a lower price — even one share — "
            "ALL of this investor's shares get repriced to that lower price. This is the most "
            "aggressive anti-dilution protection. A single down-round share reprices millions. "
            "Cost to founders: maximum dilution."
        ),
        "broad_weighted_average": (
            "BROAD-BASED WEIGHTED AVERAGE adjusts the conversion price based on the "
            "weighted average of old price and new (lower) price, using all outstanding shares "
            "(including options, warrants, convertibles) as the denominator. This is the "
            "standard, founder-friendlier protection. Dilution is proportional to the size "
            "of the down round."
        ),
        "narrow_weighted_average": (
            "NARROW WEIGHTED AVERAGE is the same formula as broad-based, but only counts "
            "preferred shares in the denominator — not all outstanding. This gives MORE "
            "anti-dilution protection than broad-based (closer to full ratchet). "
            "Watch for this in side letters."
        ),
    },
    "cross_default": (
        "CROSS-DEFAULT means a default on THIS instrument automatically triggers "
        "default on the cross-defaulted instrument — even if that instrument is "
        "performing perfectly. This creates contagion risk: one breach cascades."
    ),
    "drag_along": (
        "DRAG-ALONG forces minority shareholders to sell if majority approves. "
        "The threshold matters: at 50%+1 it's easy to trigger; at 75% preferred "
        "it requires alignment between investor classes. "
        "Below the drag-along floor, minorities can block a sale."
    ),
    "pik_toggle": (
        "PIK (Payment in Kind) TOGGLE lets the borrower choose to pay interest "
        "in cash or capitalize it (add to principal). Each PIK period increases "
        "the debt balance — compounding. After several PIK periods, the total "
        "owed can be significantly more than original principal."
    ),
    "personal_guarantee": (
        "PERSONAL GUARANTEE means the founder's personal assets (house, savings, etc.) "
        "are on the line if the company defaults. This is NOT limited to their equity "
        "in the company. Cross-default with personal guarantees = personal exposure "
        "triggered by any facility default."
    ),
    "earnout": (
        "EARNOUT means part of the purchase price is contingent on post-close "
        "performance. The buyer controls operations post-close, creating moral hazard: "
        "they can arguably run the business in ways that prevent earnout milestones. "
        "Look for: how milestones are measured, who controls the business, "
        "dispute resolution, acceleration on change of control."
    ),
    "indemnification": (
        "INDEMNIFICATION is the obligation to compensate the other party for losses. "
        "Key terms: basket (threshold before claims start), cap (maximum exposure), "
        "escrow (holdback from proceeds), survival period (how long claims last). "
        "Uncapped indemnification = unlimited exposure."
    ),
}


# ---------------------------------------------------------------------------
# Cascade Graph
# ---------------------------------------------------------------------------

class CascadeGraph:
    """Directed graph of parameter dependencies built from legal clauses.

    Each node is a ClauseParameter. Each edge is a legal relationship
    between instruments that can trigger downstream effects.
    """

    def __init__(self):
        self.edges: List[CascadeEdge] = []
        self.nodes: Dict[str, ClauseParameter] = {}
        self._adjacency: Dict[str, List[CascadeEdge]] = {}
        self._build_params: Optional[ResolvedParameterSet] = None

    def build_from_clauses(self, params: ResolvedParameterSet) -> None:
        """Build the dependency graph from resolved clause parameters."""
        self.nodes = dict(params.parameters)
        self.edges = []
        self._adjacency = {}
        self._build_params = params  # Store for find_breakpoints

        self._build_anti_dilution_edges(params)
        self._build_conversion_trigger_edges(params)
        self._build_covenant_edges(params)
        self._build_cross_default_edges(params)
        self._build_change_of_control_edges(params)
        self._build_drag_tag_edges(params)
        self._build_guarantee_edges(params)
        self._build_preemption_rofr_edges(params)
        self._build_pik_edges(params)
        self._build_indemnity_edges(params)
        self._build_earnout_edges(params)
        self._build_warrant_edges(params)
        self._build_safe_conversion_edges(params)

        # Build adjacency index
        for edge in self.edges:
            self._adjacency.setdefault(edge.trigger_param, []).append(edge)

        logger.info(
            f"Cascade graph built: {len(self.nodes)} nodes, "
            f"{len(self.edges)} edges"
        )

    def simulate(
        self,
        trigger: str,
        new_value: Any,
        current_params: ResolvedParameterSet,
        financial_state: Optional[Any] = None,
        max_depth: int = 20,
    ) -> CascadeResult:
        """Fire a trigger and trace every downstream effect through the graph."""
        result = CascadeResult(trigger=trigger, trigger_value=new_value, steps=[])
        visited: Set[str] = set()
        step_num = 0

        queue: List[Tuple[str, Any, int]] = [(trigger, new_value, 0)]

        while queue:
            current_trigger, current_value, depth = queue.pop(0)
            if depth > max_depth or current_trigger in visited:
                continue
            visited.add(current_trigger)

            edges = self._adjacency.get(current_trigger, [])
            for edge in edges:
                # Evaluate conditions
                if not self._evaluate_condition(
                    edge.conditions, current_value, current_params, financial_state
                ):
                    continue

                step_num += 1
                old_value = self._get_current_value(edge.affected_param, current_params)
                computed_new = self._compute_effect(
                    edge, current_value, old_value, current_params
                )

                step = CascadeStep(
                    step_number=step_num,
                    param_affected=edge.affected_param,
                    old_value=old_value,
                    new_value=computed_new,
                    source_clause=edge.source_clause,
                    description=self._describe_step(edge, old_value, computed_new),
                    financial_impact=self._estimate_impact(
                        edge, old_value, computed_new, current_params
                    ),
                )

                # Find what this step triggers next
                downstream = self._adjacency.get(edge.affected_param, [])
                step.downstream_triggers = [e.affected_param for e in downstream]

                result.steps.append(step)

                # Queue downstream effects
                if computed_new is not None:
                    queue.append((edge.affected_param, computed_new, depth + 1))

        # Compute terminal effects
        self._compute_terminal_effects(result, current_params)
        return result

    def identify_constraints(self) -> List[Constraint]:
        """Walk the graph and surface all constraints on the company's actions."""
        constraints: List[Constraint] = []

        for key, param in self.nodes.items():
            param_type = param.param_type

            # Consent requirements
            if param_type in ("protective_provisions", "change_of_control"):
                constraints.append(Constraint(
                    constraint_type="consent_required",
                    description=self._describe_consent_constraint(param),
                    source_clause=param,
                ))

            # Covenant constraints
            if param_type.startswith("covenant_"):
                constraints.append(Constraint(
                    constraint_type="covenant",
                    description=self._describe_covenant_constraint(param),
                    source_clause=param,
                    current_headroom=None,  # Populated by signal detector with actuals
                ))

            # Preemption rights
            if param_type == "preemptive_rights" and param.value:
                constraints.append(Constraint(
                    constraint_type="preemption",
                    description=(
                        f"Any new share issuance requires pro-rata offer to "
                        f"{param.applies_to} ({param.section_reference})"
                    ),
                    source_clause=param,
                ))

            # Transfer restrictions
            if param_type in ("rofr", "transfer_restriction", "lockup_period"):
                constraints.append(Constraint(
                    constraint_type="transfer_restriction",
                    description=self._describe_transfer_constraint(param),
                    source_clause=param,
                ))

            # Restricted payments (debt covenants on distributions)
            if param_type == "restricted_payment":
                constraints.append(Constraint(
                    constraint_type="restricted_payment",
                    description=(
                        f"Distributions restricted: {param.value} "
                        f"({param.section_reference})"
                    ),
                    source_clause=param,
                ))

            # SAFE/convertible conversion triggers
            if param_type == "qualified_financing_threshold":
                constraints.append(Constraint(
                    constraint_type="conversion_trigger",
                    description=(
                        f"Equity raise above {param.value} triggers conversion of "
                        f"{param.applies_to} ({param.section_reference})"
                    ),
                    source_clause=param,
                ))

            # Auto-renewal deadlines
            if param_type == "auto_renewal" and isinstance(param.value, dict):
                notice_days = param.value.get("notice_days")
                if notice_days:
                    constraints.append(Constraint(
                        constraint_type="deadline",
                        description=(
                            f"Auto-renewal with {notice_days}-day notice period. "
                            f"Miss it and you're locked in for another term "
                            f"({param.section_reference})"
                        ),
                        source_clause=param,
                    ))

            # Drag-along power
            if param_type == "drag_along" and param.value:
                constraints.append(Constraint(
                    constraint_type="forced_sale",
                    description=(
                        f"Drag-along: {param.applies_to} can force sale if "
                        f"threshold met ({param.section_reference})"
                    ),
                    source_clause=param,
                ))

        return constraints

    def find_breakpoints(
        self,
        variable: str,
        range_min: float,
        range_max: float,
        steps: int = 100,
        current_params: Optional[ResolvedParameterSet] = None,
    ) -> List[Breakpoint]:
        """Sweep a variable across a range and find where cascade behavior changes."""
        breakpoints: List[Breakpoint] = []
        step_size = (range_max - range_min) / steps

        # Use the params that were used to build this graph, not empty ones
        sweep_params = current_params or self._build_params
        if sweep_params is None:
            logger.warning("find_breakpoints called without params — results will be empty")
            sweep_params = ResolvedParameterSet(company_id="sweep")

        prev_cascade: Optional[CascadeResult] = None
        prev_value = range_min

        for i in range(steps + 1):
            value = range_min + (i * step_size)
            # Simulate at this value using actual params
            cascade = self.simulate(
                trigger=variable,
                new_value=value,
                current_params=sweep_params,
                max_depth=5,
            )

            if prev_cascade:
                # Compare: did the number of steps change? Did new edges fire?
                prev_steps = {s.param_affected for s in prev_cascade.steps}
                curr_steps = {s.param_affected for s in cascade.steps}

                new_triggers = curr_steps - prev_steps
                lost_triggers = prev_steps - curr_steps

                if new_triggers or lost_triggers:
                    bp_desc_parts: List[str] = []
                    clauses: List[str] = []
                    impacts: Dict[str, str] = {}

                    for step in cascade.steps:
                        if step.param_affected in new_triggers:
                            bp_desc_parts.append(step.description)
                            clauses.append(step.source_clause.source_clause_id)

                    breakpoints.append(Breakpoint(
                        variable=variable,
                        value=value,
                        description="; ".join(bp_desc_parts) or f"Behavior change at {variable}={value}",
                        clauses_involved=clauses,
                        stakeholder_impact=impacts,
                        before_behavior=f"{len(prev_cascade.steps)} cascade steps",
                        after_behavior=f"{len(cascade.steps)} cascade steps",
                    ))

            prev_cascade = cascade
            prev_value = value

        return breakpoints

    def get_drafting_interpretation(
        self, param: ClauseParameter
    ) -> str:
        """Get a plain-language explanation of what this clause drafting means financially."""
        param_type = param.param_type
        value = param.value

        if param_type == "liquidation_preference":
            interp = DRAFTING_INTERPRETATIONS["liquidation_preference"]
            base = interp["interpretation"].format(multiple=value)

            # Check for participation
            participation_key = f"participation_rights:{param.applies_to}"
            participation = self.nodes.get(participation_key)

            if participation and participation.value:
                if isinstance(participation.value, dict) and participation.value.get("cap"):
                    cap = participation.value["cap"]
                    base += interp["participating_addendum"]
                    base += interp["cap_addendum"].format(cap=cap)
                else:
                    base += interp["participating_addendum"]
            else:
                base += interp["non_participating_addendum"]

            return base

        elif param_type == "anti_dilution_method":
            interps = DRAFTING_INTERPRETATIONS["anti_dilution"]
            return interps.get(str(value), f"Anti-dilution method: {value}")

        elif param_type == "cross_default":
            return DRAFTING_INTERPRETATIONS["cross_default"]

        elif param_type == "drag_along":
            return DRAFTING_INTERPRETATIONS["drag_along"]

        elif param_type == "pik_toggle":
            return DRAFTING_INTERPRETATIONS["pik_toggle"]

        elif param_type == "personal_guarantee":
            return DRAFTING_INTERPRETATIONS["personal_guarantee"]

        elif param_type == "earnout_terms":
            return DRAFTING_INTERPRETATIONS["earnout"]

        elif param_type == "indemnity_terms":
            return DRAFTING_INTERPRETATIONS["indemnification"]

        return f"{param_type}: {value} ({param.section_reference})"

    # ------------------------------------------------------------------
    # Edge builders
    # ------------------------------------------------------------------

    def _build_anti_dilution_edges(self, params: ResolvedParameterSet) -> None:
        """Anti-dilution: new round price → conversion price repricing."""
        for key, param in params.parameters.items():
            if param.param_type != "anti_dilution_method":
                continue

            method = param.value
            entity = param.applies_to

            self.edges.append(CascadeEdge(
                trigger_param="round_price:new_round",
                affected_param=f"conversion_price:{entity}",
                relationship="triggers_repricing",
                conditions={"when": "new_price < original_price"},
                source_clause=param,
                computation="compute_anti_dilution",
                description=(
                    f"{method} anti-dilution for {entity}: "
                    f"down round reprices all shares. "
                    f"{self.get_drafting_interpretation(param)}"
                ),
            ))

            # Anti-dilution repricing → ownership recalculation
            self.edges.append(CascadeEdge(
                trigger_param=f"conversion_price:{entity}",
                affected_param=f"ownership:{entity}",
                relationship="increases_ownership",
                conditions={},
                source_clause=param,
                computation="recalculate_ownership",
                description=f"{entity} ownership increases due to anti-dilution repricing",
            ))

    def _build_conversion_trigger_edges(self, params: ResolvedParameterSet) -> None:
        """SAFE/note conversion triggers, maturity triggers."""
        for key, param in params.parameters.items():
            if param.param_type == "qualified_financing_threshold":
                entity = param.applies_to
                self.edges.append(CascadeEdge(
                    trigger_param="financing_amount:new_round",
                    affected_param=f"conversion:{entity}",
                    relationship="forces_conversion",
                    conditions={"when": f"raise_amount >= {param.value}"},
                    source_clause=param,
                    computation="compute_safe_conversion",
                    description=(
                        f"Qualified financing above {param.value} triggers conversion "
                        f"of {entity} to equity"
                    ),
                ))

                # Conversion → dilution to all existing
                self.edges.append(CascadeEdge(
                    trigger_param=f"conversion:{entity}",
                    affected_param="ownership:all_existing",
                    relationship="dilutes",
                    conditions={},
                    source_clause=param,
                    computation="compute_conversion_dilution",
                    description=f"Conversion of {entity} dilutes all existing shareholders",
                ))

            elif param.param_type == "maturity_date":
                entity = param.applies_to
                self.edges.append(CascadeEdge(
                    trigger_param=f"date:current",
                    affected_param=f"repayment_or_conversion:{entity}",
                    relationship="triggers_maturity",
                    conditions={"when": f"date >= {param.value}"},
                    source_clause=param,
                    computation="evaluate_maturity",
                    description=(
                        f"Maturity of {entity}: lender can demand repayment or "
                        f"force conversion"
                    ),
                ))

    def _build_covenant_edges(self, params: ResolvedParameterSet) -> None:
        """Financial covenants → breach → acceleration."""
        for key, param in params.parameters.items():
            if not param.param_type.startswith("covenant_"):
                continue

            entity = param.applies_to
            metric = param.param_type.replace("covenant_", "").replace("_threshold", "")

            self.edges.append(CascadeEdge(
                trigger_param=f"financial_metric:{metric}",
                affected_param=f"covenant_breach:{entity}",
                relationship="creates_default",
                conditions={"when": f"metric violates threshold {param.value}"},
                source_clause=param,
                computation="evaluate_covenant",
                description=(
                    f"Covenant breach on {entity}: {metric} violates "
                    f"threshold {param.value}"
                ),
            ))

            # Covenant breach → acceleration
            self.edges.append(CascadeEdge(
                trigger_param=f"covenant_breach:{entity}",
                affected_param=f"acceleration:{entity}",
                relationship="accelerates_payment",
                conditions={},
                source_clause=param,
                computation="compute_acceleration",
                description=(
                    f"Covenant breach accelerates repayment of {entity}. "
                    f"Full principal + accrued interest immediately due."
                ),
            ))

    def _build_cross_default_edges(self, params: ResolvedParameterSet) -> None:
        """Cross-default: default on A → automatic default on B."""
        cross_default_params = params.get_all("cross_default")
        for param in cross_default_params:
            entity = param.applies_to
            # Cross-default means default on this entity triggers default on others
            for other_key, other_param in params.parameters.items():
                if (other_param.instrument == "debt"
                        and other_param.applies_to != entity):
                    other_entity = other_param.applies_to
                    self.edges.append(CascadeEdge(
                        trigger_param=f"default:{entity}",
                        affected_param=f"default:{other_entity}",
                        relationship="cross_default",
                        conditions={"when": f"default on {entity}"},
                        source_clause=param,
                        computation="trigger_cross_default",
                        description=(
                            f"Cross-default: default on {entity} automatically "
                            f"triggers default on {other_entity}. "
                            f"{DRAFTING_INTERPRETATIONS['cross_default']}"
                        ),
                    ))

    def _build_change_of_control_edges(self, params: ResolvedParameterSet) -> None:
        """Change of control → acceleration, consent, termination."""
        for key, param in params.parameters.items():
            if param.param_type != "change_of_control":
                continue

            entity = param.applies_to
            coc_terms = param.value if isinstance(param.value, dict) else {}

            if coc_terms.get("acceleration"):
                self.edges.append(CascadeEdge(
                    trigger_param="ownership_change:any",
                    affected_param=f"acceleration:{entity}",
                    relationship="triggers_acceleration",
                    conditions={"when": "ownership transfer exceeds threshold"},
                    source_clause=param,
                    computation="compute_coc_acceleration",
                    description=(
                        f"Change of control triggers acceleration of {entity}. "
                        f"Trigger: {coc_terms.get('trigger', 'single')}"
                    ),
                ))

            if coc_terms.get("consent_required"):
                self.edges.append(CascadeEdge(
                    trigger_param="ownership_change:any",
                    affected_param=f"consent_required:{entity}",
                    relationship="requires_consent",
                    conditions={"when": "any change of control"},
                    source_clause=param,
                    computation="check_consent",
                    description=(
                        f"Change of control requires consent of {entity}"
                    ),
                ))

    def _build_drag_tag_edges(self, params: ResolvedParameterSet) -> None:
        """Drag-along / tag-along: sale vote → forced sale or right to join."""
        for key, param in params.parameters.items():
            if param.param_type == "drag_along" and param.value:
                self.edges.append(CascadeEdge(
                    trigger_param=f"sale_vote:{param.applies_to}",
                    affected_param="forced_sale:common",
                    relationship="forces_sale",
                    conditions={"when": "vote exceeds drag-along threshold"},
                    source_clause=param,
                    computation="evaluate_drag_along",
                    description=(
                        f"Drag-along: {param.applies_to} can force sale of common "
                        f"if threshold met"
                    ),
                ))

            elif param.param_type == "tag_along" and param.value:
                self.edges.append(CascadeEdge(
                    trigger_param="sale:majority",
                    affected_param=f"tag_right:{param.applies_to}",
                    relationship="grants_tag_right",
                    conditions={"when": "majority selling"},
                    source_clause=param,
                    computation="evaluate_tag_along",
                    description=(
                        f"Tag-along: {param.applies_to} can join any majority sale"
                    ),
                ))

    def _build_guarantee_edges(self, params: ResolvedParameterSet) -> None:
        """Guarantees: default → personal/parent liability."""
        for key, param in params.parameters.items():
            if param.param_type == "personal_guarantee":
                entity = param.applies_to
                guarantee_val = param.value if isinstance(param.value, dict) else {}
                amount = guarantee_val.get("amount", "unlimited")

                self.edges.append(CascadeEdge(
                    trigger_param="default:company",
                    affected_param=f"personal_liability:{entity}",
                    relationship="triggers_guarantee",
                    conditions={"when": "company default"},
                    source_clause=param,
                    computation="compute_guarantee_exposure",
                    description=(
                        f"Personal guarantee: {entity} liable up to "
                        f"{'unlimited' if guarantee_val.get('unlimited') else f'${amount:,.0f}' if isinstance(amount, (int, float)) else amount} "
                        f"on company default"
                    ),
                ))

            elif param.param_type == "parent_guarantee":
                entity = param.applies_to
                self.edges.append(CascadeEdge(
                    trigger_param=f"default:{entity}",
                    affected_param="parent_liability:holdco",
                    relationship="triggers_guarantee",
                    conditions={"when": f"{entity} default"},
                    source_clause=param,
                    computation="compute_guarantee_exposure",
                    description=f"Parent guarantee: holdco liable on {entity} default",
                ))

    def _build_preemption_rofr_edges(self, params: ResolvedParameterSet) -> None:
        """Preemption and ROFR rights."""
        for key, param in params.parameters.items():
            if param.param_type == "preemptive_rights" and param.value:
                self.edges.append(CascadeEdge(
                    trigger_param="new_issuance:any",
                    affected_param=f"preemption_right:{param.applies_to}",
                    relationship="triggers_preemption",
                    conditions={"when": "any new share issuance"},
                    source_clause=param,
                    computation="evaluate_preemption",
                    description=(
                        f"New issuance triggers preemption right for "
                        f"{param.applies_to}"
                    ),
                ))

            elif param.param_type == "rofr" and param.value:
                self.edges.append(CascadeEdge(
                    trigger_param="share_transfer:any",
                    affected_param=f"rofr:{param.applies_to}",
                    relationship="triggers_rofr",
                    conditions={"when": "any share transfer"},
                    source_clause=param,
                    computation="evaluate_rofr",
                    description=(
                        f"Share transfer triggers ROFR for {param.applies_to}"
                    ),
                ))

    def _build_pik_edges(self, params: ResolvedParameterSet) -> None:
        """PIK toggle: interest capitalization → growing principal."""
        for key, param in params.parameters.items():
            if param.param_type == "pik_toggle":
                entity = param.applies_to
                self.edges.append(CascadeEdge(
                    trigger_param=f"pik_election:{entity}",
                    affected_param=f"principal:{entity}",
                    relationship="capitalizes_interest",
                    conditions={"when": "borrower elects PIK"},
                    source_clause=param,
                    computation="compute_pik_capitalization",
                    description=(
                        f"PIK election on {entity}: interest added to principal. "
                        f"Compounds each period. "
                        f"{DRAFTING_INTERPRETATIONS['pik_toggle']}"
                    ),
                ))

    def _build_indemnity_edges(self, params: ResolvedParameterSet) -> None:
        """Indemnification: claims → exposure."""
        for key, param in params.parameters.items():
            if param.param_type == "indemnity_terms":
                entity = param.applies_to
                self.edges.append(CascadeEdge(
                    trigger_param=f"indemnity_claim:{entity}",
                    affected_param=f"indemnity_exposure:{entity}",
                    relationship="creates_liability",
                    conditions={"when": f"claim against {entity}"},
                    source_clause=param,
                    computation="compute_indemnity_exposure",
                    description=(
                        f"Indemnity claim against {entity}. "
                        f"{DRAFTING_INTERPRETATIONS['indemnification']}"
                    ),
                ))

            # Indemnity escrow: reduces available proceeds
            if param.param_type == "indemnity_escrow":
                entity = param.applies_to
                self.edges.append(CascadeEdge(
                    trigger_param="exit:any",
                    affected_param=f"escrow_holdback:{entity}",
                    relationship="reduces_proceeds",
                    conditions={"when": "any exit event"},
                    source_clause=param,
                    computation="compute_escrow_holdback",
                    description=(
                        f"Indemnity escrow holds back portion of {entity}'s proceeds "
                        f"at exit"
                    ),
                ))

    def _build_earnout_edges(self, params: ResolvedParameterSet) -> None:
        """Earnout: post-close performance → contingent payments."""
        for key, param in params.parameters.items():
            if param.param_type == "earnout_terms":
                entity = param.applies_to
                earnout_val = param.value if isinstance(param.value, dict) else {}

                self.edges.append(CascadeEdge(
                    trigger_param=f"earnout_milestone:{entity}",
                    affected_param=f"contingent_payment:{entity}",
                    relationship="triggers_payment",
                    conditions={"when": "milestone achieved"},
                    source_clause=param,
                    computation="evaluate_earnout",
                    description=(
                        f"Earnout milestone for {entity}: contingent payment up to "
                        f"${earnout_val.get('max_amount', 0):,.0f}. "
                        f"{DRAFTING_INTERPRETATIONS['earnout']}"
                    ),
                ))

    def _build_warrant_edges(self, params: ResolvedParameterSet) -> None:
        """Warrant exercise: valuation change → dilution via warrant exercise."""
        for key, param in params.parameters.items():
            if param.param_type == "warrant_coverage":
                entity = param.applies_to
                coverage = param.value if isinstance(param.value, (int, float)) else 0

                # Valuation increase → warrants go in the money → dilution
                self.edges.append(CascadeEdge(
                    trigger_param="valuation:company",
                    affected_param=f"warrant_exercise:{entity}",
                    relationship="triggers_exercise",
                    conditions={"when": "valuation > exercise_price"},
                    source_clause=param,
                    computation="compute_warrant_dilution",
                    description=(
                        f"Warrant for {entity} ({coverage*100:.2f}% coverage): "
                        f"valuation above exercise price triggers dilution to all existing"
                    ),
                ))

                # Warrant exercise → ownership dilution
                self.edges.append(CascadeEdge(
                    trigger_param=f"warrant_exercise:{entity}",
                    affected_param="ownership:all_existing",
                    relationship="dilutes",
                    conditions={},
                    source_clause=param,
                    computation="compute_conversion_dilution",
                    description=f"Warrant exercise by {entity} dilutes all existing shareholders",
                ))

            # Warrant expiry → worthless (no dilution risk after expiry)
            if param.param_type == "warrant_expiry":
                entity = param.applies_to
                self.edges.append(CascadeEdge(
                    trigger_param=f"date:current",
                    affected_param=f"warrant_expired:{entity}",
                    relationship="expires_worthless",
                    conditions={"when": f"date >= {param.value}"},
                    source_clause=param,
                    computation="evaluate_maturity",
                    description=(
                        f"Warrant for {entity} expires on {param.value}. "
                        f"Exercise or lose."
                    ),
                ))

    def _build_safe_conversion_edges(self, params: ResolvedParameterSet) -> None:
        """SAFE-specific conversion triggers (beyond qualified financing in _build_conversion_trigger_edges)."""
        for key, param in params.parameters.items():
            if param.param_type == "valuation_cap" and param.instrument == "safe":
                entity = param.applies_to

                # Dissolution event → SAFE gets paid before common
                self.edges.append(CascadeEdge(
                    trigger_param="dissolution:company",
                    affected_param=f"safe_dissolution_payment:{entity}",
                    relationship="triggers_payment",
                    conditions={"when": "dissolution or wind-down"},
                    source_clause=param,
                    computation="compute_safe_dissolution",
                    description=(
                        f"Company dissolution: SAFE holder {entity} gets "
                        f"investment back before common (capped at ${param.value:,.0f})"
                    ),
                ))

                # Change of control → SAFE converts or gets paid
                self.edges.append(CascadeEdge(
                    trigger_param="ownership_change:any",
                    affected_param=f"safe_coc_conversion:{entity}",
                    relationship="forces_conversion",
                    conditions={"when": "change of control event"},
                    source_clause=param,
                    computation="compute_safe_conversion",
                    description=(
                        f"Change of control: SAFE {entity} converts at cap "
                        f"${param.value:,.0f} or gets investment back"
                    ),
                ))

    def build_group_edges(
        self, group_structure: Any, params: ResolvedParameterSet
    ) -> None:
        """
        Add group-level cascade edges from a resolved GroupStructure.

        Links subsidiary defaults to parent guarantees, intercompany flow
        constraints to cash flow cascades, covenant breaches across entities,
        and ring-fencing provisions.

        Call AFTER build_from_clauses() to layer group edges on top.
        """
        GroupStructure = _get_group_structure_type()
        if not isinstance(group_structure, GroupStructure):
            return

        # 1. Subsidiary default → parent guarantee trigger
        for rel in group_structure.relationships:
            if rel.relationship_type == "guarantor":
                self.edges.append(CascadeEdge(
                    trigger_param=f"default:{rel.to_entity_id}",
                    affected_param=f"parent_liability:{rel.from_entity_id}",
                    relationship="triggers_guarantee",
                    conditions={"when": f"default by {rel.to_entity_id}"},
                    source_clause=rel.source_clause or self._make_synthetic_clause(
                        "parent_guarantee", rel.from_entity_id,
                        f"Parent guarantee of {rel.to_entity_id}"
                    ),
                    computation="compute_guarantee_exposure",
                    description=(
                        f"Subsidiary {rel.to_entity_id} default triggers parent "
                        f"guarantee by {rel.from_entity_id}"
                    ),
                ))

        # 2. Cross-default across group entities
        cross_default_entities = set()
        for key, param in params.parameters.items():
            if param.param_type == "cross_default":
                cross_default_entities.add(param.applies_to)

        for entity_id in cross_default_entities:
            for other_id, entity in group_structure.entities.items():
                if other_id != entity_id and not entity.is_dormant:
                    self.edges.append(CascadeEdge(
                        trigger_param=f"default:{entity_id}",
                        affected_param=f"group_cross_default:{other_id}",
                        relationship="cross_default",
                        conditions={"when": f"default at {entity_id}"},
                        source_clause=self._make_synthetic_clause(
                            "cross_default", entity_id,
                            f"Group cross-default: {entity_id} → {other_id}"
                        ),
                        computation="trigger_cross_default",
                        description=(
                            f"Group cross-default: default at {entity_id} "
                            f"cascades to {other_id}"
                        ),
                    ))

        # 3. Flow constraint cascades — covenant breach blocks intercompany flows
        for constraint in group_structure.constraints:
            if constraint.constraint_type == "covenant_limit" and constraint.affected_entity_id:
                self.edges.append(CascadeEdge(
                    trigger_param=f"covenant_breach:{constraint.affected_entity_id}",
                    affected_param=f"flow_blocked:{constraint.affected_entity_id}",
                    relationship="blocks_flow",
                    conditions={"when": f"covenant breach at {constraint.affected_entity_id}"},
                    source_clause=constraint.source_clause or self._make_synthetic_clause(
                        "restricted_payment", constraint.affected_entity_id,
                        constraint.description
                    ),
                    computation="evaluate_covenant",
                    description=(
                        f"Covenant breach at {constraint.affected_entity_id}: "
                        f"{constraint.description}"
                    ),
                ))

            # Ring-fencing: entity cash is trapped
            if constraint.constraint_type == "ring_fence" and constraint.affected_entity_id:
                self.edges.append(CascadeEdge(
                    trigger_param=f"cash_extraction:{constraint.affected_entity_id}",
                    affected_param=f"extraction_blocked:{constraint.affected_entity_id}",
                    relationship="blocks_flow",
                    conditions={"when": "extraction attempt"},
                    source_clause=constraint.source_clause or self._make_synthetic_clause(
                        "ring_fence", constraint.affected_entity_id,
                        constraint.description
                    ),
                    computation="evaluate_covenant",
                    description=(
                        f"Ring-fenced entity {constraint.affected_entity_id}: "
                        f"cash cannot be extracted. {constraint.description}"
                    ),
                ))

            # Restricted payments: dividend/distribution limits
            if constraint.constraint_type == "restricted_payment" and constraint.affected_entity_id:
                self.edges.append(CascadeEdge(
                    trigger_param=f"distribution:{constraint.affected_entity_id}",
                    affected_param=f"distribution_capped:{constraint.affected_entity_id}",
                    relationship="caps_distribution",
                    conditions={"when": f"distribution above {constraint.max_amount or 'limit'}"},
                    source_clause=constraint.source_clause or self._make_synthetic_clause(
                        "restricted_payment", constraint.affected_entity_id,
                        constraint.description
                    ),
                    computation="evaluate_covenant",
                    description=(
                        f"Restricted payment at {constraint.affected_entity_id}: "
                        f"max ${constraint.max_amount:,.0f}" if constraint.max_amount
                        else f"Restricted payment at {constraint.affected_entity_id}"
                    ),
                ))

        # 4. Thin capitalisation breach → TP non-deductibility cascade
        for constraint in group_structure.constraints:
            if constraint.constraint_type == "thin_cap" and constraint.affected_entity_id:
                self.edges.append(CascadeEdge(
                    trigger_param=f"intercompany_loan:{constraint.affected_entity_id}",
                    affected_param=f"thin_cap_breach:{constraint.affected_entity_id}",
                    relationship="creates_tax_risk",
                    conditions={"when": "debt/equity exceeds thin cap ratio"},
                    source_clause=constraint.source_clause or self._make_synthetic_clause(
                        "thin_cap", constraint.affected_entity_id,
                        constraint.description
                    ),
                    computation="evaluate_covenant",
                    description=(
                        f"Thin cap at {constraint.affected_entity_id}: "
                        f"excess interest non-deductible. {constraint.description}"
                    ),
                ))

        # Rebuild adjacency index with new edges
        self._adjacency = {}
        for edge in self.edges:
            self._adjacency.setdefault(edge.trigger_param, []).append(edge)

        logger.info(
            f"Group cascade edges added: {len(self.edges)} total edges "
            f"across {len(group_structure.entities)} entities"
        )

    def _make_synthetic_clause(
        self, param_type: str, entity: str, description: str
    ) -> ClauseParameter:
        """Create a synthetic clause parameter for group-derived edges."""
        return ClauseParameter(
            param_type=param_type,
            value=True,
            applies_to=entity,
            instrument="group_structure",
            source_document_id="group_structure",
            source_clause_id="group_derived",
            section_reference="Group structure analysis",
            source_quote=description,
            document_type="group_analysis",
        )

    # ------------------------------------------------------------------
    # Simulation helpers
    # ------------------------------------------------------------------

    def _evaluate_condition(
        self,
        conditions: Dict[str, Any],
        trigger_value: Any,
        params: ResolvedParameterSet,
        financial_state: Optional[Any],
    ) -> bool:
        """Evaluate whether a cascade edge's conditions are met."""
        if not conditions:
            return True

        when = conditions.get("when", "")

        if "new_price < original_price" in when:
            # Anti-dilution: only fires on DOWN rounds — new price must be
            # below the original conversion price
            if not isinstance(trigger_value, (int, float)) or trigger_value <= 0:
                return False
            # Get the original conversion price from the edge's target param
            target_key = conditions.get("target_param", "")
            original_price = self._get_current_value(target_key, params)
            if isinstance(original_price, (int, float)) and original_price > 0:
                return trigger_value < original_price
            # If no original price found, check source clause for reference price
            source = conditions.get("source_clause")
            if source and isinstance(source, ClauseParameter):
                if isinstance(source.value, dict):
                    ref_price = source.value.get("original_price") or source.value.get("conversion_price")
                    if isinstance(ref_price, (int, float)) and ref_price > 0:
                        return trigger_value < ref_price
            return False  # Cannot confirm it's a down round — don't fire

        if "raise_amount >=" in when or "raise_amount >" in when:
            # Qualified financing threshold
            import re
            m = re.search(r'[\d.]+', when)
            if m and isinstance(trigger_value, (int, float)):
                threshold = float(m.group())
                return trigger_value >= threshold
            return False

        if "date >= maturity" in when or "maturity" in when:
            # Maturity trigger — compare against maturity date
            from datetime import datetime as _dt
            maturity_str = conditions.get("maturity_date")
            if maturity_str:
                try:
                    maturity = _dt.fromisoformat(str(maturity_str).replace("Z", "+00:00"))
                    return _dt.utcnow().replace(tzinfo=maturity.tzinfo) >= maturity
                except (ValueError, TypeError):
                    pass
            # Check if financial_state has current date info
            if financial_state and hasattr(financial_state, "as_of_date"):
                return True  # If we have state and maturity condition, likely at/past maturity
            return False

        if "vote exceeds threshold" in when or "vote_threshold" in when:
            # Drag-along / tag-along voting threshold
            threshold = conditions.get("threshold", 0.5)
            if isinstance(trigger_value, (int, float)):
                return trigger_value >= threshold
            return False

        if "company default" in when or "default" in when:
            # Cross-default / acceleration — triggers on default event
            if isinstance(trigger_value, dict):
                return trigger_value.get("defaulted", False) or trigger_value.get("breached", False)
            if isinstance(trigger_value, bool):
                return trigger_value
            return False

        if "ownership transfer exceeds threshold" in when or "ownership_transfer" in when:
            # Change of control trigger
            threshold = conditions.get("threshold", 0.5)
            if isinstance(trigger_value, (int, float)):
                return trigger_value > threshold
            return False

        if "exercise" in when or "in_the_money" in when:
            # Warrant exercise — check if exercise price < current price
            exercise_price = conditions.get("exercise_price")
            if isinstance(trigger_value, (int, float)) and isinstance(exercise_price, (int, float)):
                return trigger_value > exercise_price
            return False

        if "covenant" in when or "breach" in when:
            # Covenant breach — compare metric against threshold
            threshold = conditions.get("threshold")
            direction = conditions.get("direction", "below")  # "below" for DSCR, "above" for leverage
            if isinstance(trigger_value, (int, float)) and isinstance(threshold, (int, float)):
                if direction == "below":
                    return trigger_value < threshold
                else:
                    return trigger_value > threshold
            return False

        # Unknown condition — do NOT default to True (audit flagged this as a bug)
        # Only fire if we can confirm the condition is actually met
        logger.debug(f"Unknown cascade condition: {when} — not firing")
        return False

    def _get_current_value(
        self, param_key: str, params: ResolvedParameterSet
    ) -> Any:
        """Get the current value of a parameter."""
        param = params.parameters.get(param_key)
        return param.value if param else None

    def _compute_effect(
        self,
        edge: CascadeEdge,
        trigger_value: Any,
        old_value: Any,
        params: ResolvedParameterSet,
    ) -> Any:
        """Compute the new value after a cascade edge fires."""
        comp = edge.computation

        if comp == "compute_anti_dilution":
            return self._compute_anti_dilution(edge, trigger_value, old_value, params)
        elif comp == "recalculate_ownership":
            return self._compute_ownership_recalculation(edge, trigger_value, old_value, params)
        elif comp == "compute_safe_conversion":
            return self._compute_safe_conversion(edge, trigger_value, params)
        elif comp == "evaluate_covenant":
            return self._evaluate_covenant_breach(edge, trigger_value, old_value, params)
        elif comp == "compute_acceleration":
            return self._compute_acceleration(edge, trigger_value, old_value, params)
        elif comp == "trigger_cross_default":
            return self._compute_cross_default(edge, trigger_value, old_value, params)
        elif comp == "compute_pik_capitalization":
            return self._compute_pik(edge, trigger_value, old_value, params)
        elif comp == "compute_guarantee_exposure":
            return self._compute_guarantee_exposure(edge, trigger_value, old_value, params)
        elif comp == "compute_conversion_dilution":
            return self._compute_conversion_dilution(edge, trigger_value, old_value, params)
        elif comp == "evaluate_maturity":
            return self._evaluate_maturity(edge, trigger_value, old_value, params)
        elif comp == "evaluate_drag_along":
            return self._evaluate_drag_along(edge, trigger_value, old_value, params)
        elif comp == "evaluate_tag_along":
            return self._evaluate_tag_along(edge, trigger_value, old_value, params)
        elif comp == "compute_warrant_dilution":
            return self._compute_warrant_dilution(edge, trigger_value, old_value, params)
        elif comp == "compute_indemnity_exposure":
            return self._compute_indemnity_exposure(edge, trigger_value, old_value, params)
        elif comp == "compute_escrow_holdback":
            return self._compute_escrow_holdback(edge, trigger_value, old_value, params)
        elif comp == "compute_earnout_payout":
            return self._compute_earnout_payout(edge, trigger_value, old_value, params)
        elif comp == "compute_dividend_accrual":
            return self._compute_dividend_accrual(edge, trigger_value, old_value, params)
        elif comp == "compute_clawback":
            return self._compute_clawback(edge, trigger_value, old_value, params)
        elif comp == "evaluate_change_of_control":
            return self._evaluate_change_of_control(edge, trigger_value, old_value, params)
        elif comp == "compute_redemption":
            return self._compute_redemption(edge, trigger_value, old_value, params)
        else:
            logger.warning(f"Unknown computation type: {comp}")
            return trigger_value

    def _compute_anti_dilution(
        self,
        edge: CascadeEdge,
        new_round_price: Any,
        current_conversion_price: Any,
        params: ResolvedParameterSet,
    ) -> Optional[float]:
        """Compute new conversion price after anti-dilution fires.

        Full ratchet: CP2 = new_round_price (all shares reprice to lowest price)

        Weighted average formula:
          CP2 = CP1 × (A + B) / (A + C)
          where:
            A = shares outstanding before new issuance
            B = shares that WOULD have been issued at the old price
                (i.e., new_money / CP1)
            C = shares actually issued at the new (lower) price
                (i.e., new_money / new_round_price)

        Broad-based WA: A includes all outstanding shares (common, preferred,
          as-converted options/warrants, SAFE/note shares)
        Narrow WA: A includes only the specific series being protected
        """
        if not isinstance(new_round_price, (int, float)):
            return current_conversion_price
        if not isinstance(current_conversion_price, (int, float)):
            return new_round_price
        if new_round_price >= current_conversion_price:
            return current_conversion_price  # Not a down round

        method = edge.source_clause.value

        if method == "full_ratchet":
            # Full ratchet: price drops to the new round price
            return min(new_round_price, current_conversion_price)

        elif method in ("broad_weighted_average", "narrow_weighted_average"):
            if current_conversion_price <= 0:
                return new_round_price

            # Get shares outstanding (A) from params
            entity = edge.source_clause.applies_to

            if method == "broad_weighted_average":
                # Broad-based: all outstanding shares (fully diluted)
                shares_outstanding = self._get_total_shares_outstanding(params)
            else:
                # Narrow: only the protected series' shares
                shares_outstanding = self._get_series_shares(params, entity)

            if shares_outstanding <= 0:
                # Fallback: estimate from instruments if share counts unavailable
                shares_outstanding = self._estimate_shares_from_instruments(params)

            if shares_outstanding <= 0:
                # Last resort: use the ratio-based approximation
                # CP2 = CP1 × new_price / CP1 = new_price (degenerate case)
                return new_round_price

            # Get the new money raised in this round
            new_money = self._get_new_round_money(params, edge)
            if new_money <= 0:
                # Without knowing the round size, we can still compute using
                # a marginal issuance (1 share) which gives the formula:
                # CP2 = CP1 × (A × CP1 + new_money) / (A × CP1 + A × new_money / new_price)
                # For marginal: CP2 approaches new_round_price
                # Use conservative estimate: assume 20% dilution round
                new_money = shares_outstanding * current_conversion_price * 0.20

            # B = shares that would have been issued at old price
            b_shares = new_money / current_conversion_price
            # C = shares actually issued at new (lower) price
            c_shares = new_money / new_round_price

            # CP2 = CP1 × (A + B) / (A + C)
            numerator = shares_outstanding + b_shares
            denominator = shares_outstanding + c_shares

            if denominator <= 0:
                return new_round_price

            new_conversion_price = current_conversion_price * (numerator / denominator)

            # Sanity: new price should be between new_round_price and current price
            new_conversion_price = max(new_round_price, min(new_conversion_price, current_conversion_price))

            return new_conversion_price

        return current_conversion_price

    def _get_total_shares_outstanding(self, params: ResolvedParameterSet) -> float:
        """Get total fully-diluted shares outstanding from instruments."""
        total = 0.0
        for inst in params.instruments:
            shares = inst.terms.get("shares", 0)
            if isinstance(shares, (int, float)):
                total += shares
            elif inst.principal_or_value > 0:
                # Estimate shares from investment value
                total += inst.principal_or_value
        return total

    def _get_series_shares(self, params: ResolvedParameterSet, entity: str) -> float:
        """Get shares for a specific series (narrow WA)."""
        total = 0.0
        for inst in params.instruments:
            holder = (inst.holder or "").lower().replace(" ", "_")
            if holder == entity or entity in holder:
                shares = inst.terms.get("shares", 0)
                if isinstance(shares, (int, float)):
                    total += shares
                elif inst.principal_or_value > 0:
                    total += inst.principal_or_value
        return total

    def _estimate_shares_from_instruments(self, params: ResolvedParameterSet) -> float:
        """Estimate total shares from instrument values when explicit counts unavailable."""
        total = 0.0
        for inst in params.instruments:
            if inst.principal_or_value > 0:
                total += inst.principal_or_value
        return total

    def _get_new_round_money(
        self, params: ResolvedParameterSet, edge: CascadeEdge
    ) -> float:
        """Get the amount of money raised in the triggering round."""
        # Check edge metadata for round size
        if hasattr(edge, 'metadata') and isinstance(edge.metadata, dict):
            amount = edge.metadata.get("round_size") or edge.metadata.get("raise_amount")
            if isinstance(amount, (int, float)):
                return amount
        # Check instruments for recent rounds
        for inst in params.instruments:
            if inst.principal_or_value > 0 and inst.instrument_type == "equity":
                return inst.principal_or_value
        return 0.0

    def _compute_safe_conversion(
        self,
        edge: CascadeEdge,
        financing_amount: Any,
        params: ResolvedParameterSet,
    ) -> Dict[str, Any]:
        """Compute SAFE/note conversion terms."""
        entity = edge.source_clause.applies_to
        cap = params.get("valuation_cap", entity)
        discount = params.get("conversion_discount", entity)

        cap_val = cap.value if cap else None
        discount_val = discount.value if discount else None

        return {
            "converts": True,
            "valuation_cap": cap_val,
            "discount": discount_val,
            "financing_amount": financing_amount,
        }

    def _compute_pik(
        self,
        edge: CascadeEdge,
        trigger_value: Any,
        old_principal: Any,
        params: ResolvedParameterSet,
    ) -> Optional[float]:
        """Compute PIK capitalization — interest added to principal."""
        entity = edge.source_clause.applies_to
        rate_param = params.get("pik_rate", entity)
        if not rate_param or not isinstance(old_principal, (int, float)):
            return old_principal

        rate = rate_param.value if isinstance(rate_param.value, (int, float)) else 0
        return old_principal * (1 + rate)

    def _compute_ownership_recalculation(
        self, edge: CascadeEdge, trigger_value: Any,
        old_value: Any, params: ResolvedParameterSet,
    ) -> Dict[str, Any]:
        """Recalculate ownership percentages after a share count change.

        When shares are issued (conversion, anti-dilution repricing, warrants),
        all existing ownership percentages change.
        """
        entity = edge.source_clause.applies_to
        total_shares = self._get_total_shares_outstanding(params)
        new_shares = 0.0

        if isinstance(trigger_value, dict):
            new_shares = trigger_value.get("new_shares", 0)
        elif isinstance(trigger_value, (int, float)):
            new_shares = trigger_value

        new_total = total_shares + new_shares
        if new_total <= 0:
            return {"ownership_pct": old_value, "dilution": 0}

        # The entity that triggered gets new_shares; everyone else is diluted
        entity_shares = self._get_series_shares(params, entity) + new_shares
        new_ownership = entity_shares / new_total
        dilution = (total_shares / new_total) if total_shares > 0 else 0

        return {
            "ownership_pct": new_ownership,
            "dilution_factor": dilution,
            "new_total_shares": new_total,
            "entity_shares": entity_shares,
        }

    def _evaluate_covenant_breach(
        self, edge: CascadeEdge, trigger_value: Any,
        old_value: Any, params: ResolvedParameterSet,
    ) -> Dict[str, Any]:
        """Evaluate whether a covenant is breached and compute consequences."""
        entity = edge.source_clause.applies_to
        covenant_val = edge.source_clause.value

        threshold = None
        metric = "unknown"
        if isinstance(covenant_val, dict):
            if "dscr" in covenant_val:
                threshold = covenant_val["dscr"]
                metric = "dscr"
            elif "leverage" in covenant_val:
                threshold = covenant_val["leverage"]
                metric = "leverage"
        elif isinstance(covenant_val, (int, float)):
            threshold = covenant_val
            metric = edge.source_clause.param_type.replace("covenant_", "")

        breached = False
        headroom = None
        if threshold is not None and isinstance(trigger_value, (int, float)):
            if metric == "leverage":
                breached = trigger_value > threshold  # leverage must stay BELOW
                headroom = threshold - trigger_value
            else:
                breached = trigger_value < threshold  # DSCR must stay ABOVE
                headroom = trigger_value - threshold

        return {
            "breached": breached,
            "metric": metric,
            "metric_value": trigger_value,
            "threshold": threshold,
            "headroom": headroom,
            "entity": entity,
            "consequences": "acceleration" if breached else "none",
        }

    def _compute_acceleration(
        self, edge: CascadeEdge, trigger_value: Any,
        old_value: Any, params: ResolvedParameterSet,
    ) -> Dict[str, Any]:
        """Compute debt acceleration — full balance becomes immediately due."""
        entity = edge.source_clause.applies_to

        # Find the outstanding debt balance for this entity
        outstanding = 0.0
        interest_rate = 0.0
        for inst in params.instruments:
            holder = (inst.holder or "").lower().replace(" ", "_")
            if holder == entity or entity in holder:
                if inst.instrument_type == "debt":
                    outstanding += inst.principal_or_value
                    rate = inst.terms.get("interest_rate")
                    if isinstance(rate, (int, float)):
                        interest_rate = rate

        # Default penalty (typically 2% over contract rate)
        default_rate = interest_rate + 0.02

        return {
            "accelerated": True,
            "trigger": edge.trigger_param,
            "outstanding_balance": outstanding,
            "default_interest_rate": default_rate,
            "immediate_cash_impact": outstanding,
            "entity": entity,
        }

    def _compute_cross_default(
        self, edge: CascadeEdge, trigger_value: Any,
        old_value: Any, params: ResolvedParameterSet,
    ) -> Dict[str, Any]:
        """Compute cross-default cascade — default on one facility triggers others."""
        entity = edge.source_clause.applies_to
        source_facility = edge.trigger_param

        # Find all linked facilities via cross-default clauses
        linked_facilities = []
        total_exposure = 0.0
        for key, param in params.parameters.items():
            if param.param_type == "cross_default":
                linked_facilities.append(param.applies_to)
                # Find the debt balance for this facility
                for inst in params.instruments:
                    holder = (inst.holder or "").lower().replace(" ", "_")
                    if holder == param.applies_to or param.applies_to in holder:
                        total_exposure += inst.principal_or_value

        return {
            "cross_defaulted": True,
            "source_facility": source_facility,
            "linked_facilities": linked_facilities,
            "total_exposure": total_exposure,
            "entity": entity,
        }

    def _compute_guarantee_exposure(
        self, edge: CascadeEdge, trigger_value: Any,
        old_value: Any, params: ResolvedParameterSet,
    ) -> Dict[str, Any]:
        """Compute personal/parent guarantee exposure on default."""
        entity = edge.source_clause.applies_to
        guarantee_val = edge.source_clause.value

        amount = 0.0
        unlimited = False
        if isinstance(guarantee_val, dict):
            amount = guarantee_val.get("amount", 0)
            unlimited = guarantee_val.get("unlimited", False)
        elif isinstance(guarantee_val, (int, float)):
            amount = guarantee_val

        # On default, the full guaranteed amount becomes personal exposure
        default_amount = 0.0
        if isinstance(trigger_value, dict):
            default_amount = trigger_value.get("outstanding_balance", 0) or trigger_value.get("total_exposure", 0)
        elif isinstance(trigger_value, (int, float)):
            default_amount = trigger_value

        exposure = default_amount if unlimited else min(amount, default_amount)

        return {
            "guarantor": entity,
            "guarantee_amount": amount,
            "unlimited": unlimited,
            "triggered_exposure": exposure,
            "default_amount": default_amount,
        }

    def _compute_conversion_dilution(
        self, edge: CascadeEdge, trigger_value: Any,
        old_value: Any, params: ResolvedParameterSet,
    ) -> Dict[str, Any]:
        """Compute dilution from convertible instrument conversion."""
        entity = edge.source_clause.applies_to

        # Get conversion terms
        discount = params.get("conversion_discount", entity)
        cap = params.get("valuation_cap", entity)

        discount_val = discount.value if discount and isinstance(discount.value, (int, float)) else 0
        cap_val = cap.value if cap and isinstance(cap.value, (int, float)) else None

        total_shares = self._get_total_shares_outstanding(params)
        principal = 0.0
        for inst in params.instruments:
            holder = (inst.holder or "").lower().replace(" ", "_")
            if (holder == entity or entity in holder) and inst.instrument_type in ("convertible", "safe"):
                principal += inst.principal_or_value

        if not isinstance(trigger_value, (int, float)) or trigger_value <= 0:
            return {"dilution_pct": 0, "new_shares": 0}

        round_price = trigger_value
        effective_price = round_price * (1 - discount_val)

        if cap_val and total_shares > 0:
            cap_price = cap_val / total_shares
            effective_price = min(effective_price, cap_price)

        if effective_price <= 0:
            return {"dilution_pct": 0, "new_shares": 0}

        new_shares = principal / effective_price
        dilution_pct = new_shares / (total_shares + new_shares) if total_shares > 0 else 0

        return {
            "new_shares": new_shares,
            "dilution_pct": dilution_pct,
            "effective_price": effective_price,
            "principal_converted": principal,
        }

    def _evaluate_maturity(
        self, edge: CascadeEdge, trigger_value: Any,
        old_value: Any, params: ResolvedParameterSet,
    ) -> Dict[str, Any]:
        """Evaluate maturity event — lender can demand repayment or force conversion."""
        entity = edge.source_clause.applies_to
        outstanding = 0.0
        for inst in params.instruments:
            holder = (inst.holder or "").lower().replace(" ", "_")
            if holder == entity or entity in holder:
                outstanding += inst.principal_or_value

        # Check if there's a conversion option at maturity
        conversion = params.get("conversion_terms", entity)
        can_convert = conversion is not None

        return {
            "matured": True,
            "outstanding_balance": outstanding,
            "entity": entity,
            "can_demand_repayment": True,
            "can_force_conversion": can_convert,
            "cash_impact": outstanding,
        }

    def _evaluate_drag_along(
        self, edge: CascadeEdge, trigger_value: Any,
        old_value: Any, params: ResolvedParameterSet,
    ) -> Dict[str, Any]:
        """Evaluate drag-along — can majority force minority to sell?"""
        entity = edge.source_clause.applies_to
        drag_val = edge.source_clause.value

        threshold = 0.5  # default majority
        if isinstance(drag_val, dict):
            threshold = drag_val.get("threshold", 0.5)
        elif isinstance(drag_val, (int, float)):
            threshold = drag_val

        # Check if the triggering ownership meets the threshold
        combined_ownership = 0.0
        if isinstance(trigger_value, (int, float)):
            combined_ownership = trigger_value
        elif isinstance(trigger_value, dict):
            combined_ownership = trigger_value.get("combined_ownership", 0)

        can_drag = combined_ownership >= threshold

        return {
            "drag_along_triggered": can_drag,
            "threshold": threshold,
            "combined_ownership": combined_ownership,
            "entity": entity,
            "forced_sale": can_drag,
        }

    def _evaluate_tag_along(
        self, edge: CascadeEdge, trigger_value: Any,
        old_value: Any, params: ResolvedParameterSet,
    ) -> Dict[str, Any]:
        """Evaluate tag-along — minority can tag onto majority sale."""
        entity = edge.source_clause.applies_to

        # Tag-along triggers when a major holder sells
        sale_pct = 0.0
        if isinstance(trigger_value, (int, float)):
            sale_pct = trigger_value
        elif isinstance(trigger_value, dict):
            sale_pct = trigger_value.get("sale_pct", 0)

        return {
            "tag_along_triggered": sale_pct > 0,
            "sale_pct": sale_pct,
            "entity_can_tag": True,
            "entity": entity,
        }

    def _compute_warrant_dilution(
        self, edge: CascadeEdge, trigger_value: Any,
        old_value: Any, params: ResolvedParameterSet,
    ) -> Dict[str, Any]:
        """Compute dilution from warrant exercise."""
        entity = edge.source_clause.applies_to

        # Get warrant terms
        coverage = params.get("warrant_coverage", entity)
        exercise_price_param = params.get("warrant_exercise_price", entity)

        coverage_pct = coverage.value if coverage and isinstance(coverage.value, (int, float)) else 0
        exercise_price = exercise_price_param.value if exercise_price_param and isinstance(
            exercise_price_param.value, (int, float)
        ) else 0

        current_price = trigger_value if isinstance(trigger_value, (int, float)) else 0
        total_shares = self._get_total_shares_outstanding(params)

        if current_price <= exercise_price or total_shares <= 0:
            return {"exercised": False, "dilution_pct": 0}

        warrant_shares = total_shares * coverage_pct
        dilution_pct = warrant_shares / (total_shares + warrant_shares)
        intrinsic_value = (current_price - exercise_price) * warrant_shares

        return {
            "exercised": True,
            "warrant_shares": warrant_shares,
            "dilution_pct": dilution_pct,
            "exercise_price": exercise_price,
            "intrinsic_value": intrinsic_value,
            "cash_received": exercise_price * warrant_shares,
        }

    def _compute_indemnity_exposure(
        self, edge: CascadeEdge, trigger_value: Any,
        old_value: Any, params: ResolvedParameterSet,
    ) -> Dict[str, Any]:
        """Compute indemnity exposure — capped or uncapped."""
        entity = edge.source_clause.applies_to

        # Check for cap
        cap_param = params.get("indemnity_cap", entity)
        basket_param = params.get("indemnity_basket", entity)

        cap = cap_param.value if cap_param and isinstance(cap_param.value, (int, float)) else None
        basket = basket_param.value if basket_param and isinstance(basket_param.value, (int, float)) else 0

        claim_amount = trigger_value if isinstance(trigger_value, (int, float)) else 0

        # Basket: claims below basket threshold are not indemnified
        net_claim = max(0, claim_amount - basket)

        # Cap: total indemnity limited
        if cap is not None:
            exposure = min(net_claim, cap)
        else:
            exposure = net_claim  # Uncapped

        return {
            "claim_amount": claim_amount,
            "basket_deductible": basket,
            "cap": cap,
            "net_exposure": exposure,
            "uncapped": cap is None,
            "entity": entity,
        }

    def _compute_escrow_holdback(
        self, edge: CascadeEdge, trigger_value: Any,
        old_value: Any, params: ResolvedParameterSet,
    ) -> Dict[str, Any]:
        """Compute escrow holdback — proceeds held back pending conditions."""
        entity = edge.source_clause.applies_to
        escrow_param = edge.source_clause.value

        amount = 0.0
        percentage = 0.0
        duration_months = 0

        if isinstance(escrow_param, dict):
            amount = escrow_param.get("amount", 0)
            percentage = escrow_param.get("percentage", 0)
            duration_months = escrow_param.get("duration_months", 0)

        # If percentage-based, compute from deal value
        deal_value = trigger_value if isinstance(trigger_value, (int, float)) else 0
        if percentage > 0 and deal_value > 0:
            amount = deal_value * percentage

        return {
            "escrow_amount": amount,
            "percentage": percentage,
            "duration_months": duration_months,
            "deal_value": deal_value,
            "net_proceeds": deal_value - amount,
            "entity": entity,
        }

    def _compute_earnout_payout(
        self, edge: CascadeEdge, trigger_value: Any,
        old_value: Any, params: ResolvedParameterSet,
    ) -> Dict[str, Any]:
        """Compute earnout payout based on milestone achievement."""
        entity = edge.source_clause.applies_to
        earnout_val = edge.source_clause.value

        max_amount = 0.0
        milestones = []
        if isinstance(earnout_val, dict):
            max_amount = earnout_val.get("max_amount", 0)
            milestones = earnout_val.get("milestones", [])

        # trigger_value represents the achievement metric
        achievement = trigger_value if isinstance(trigger_value, (int, float)) else 0

        # Simple linear payout based on achievement percentage
        payout = min(max_amount, max_amount * achievement) if max_amount > 0 else 0

        return {
            "payout": payout,
            "max_amount": max_amount,
            "achievement": achievement,
            "milestones": milestones,
            "entity": entity,
        }

    def _compute_dividend_accrual(
        self, edge: CascadeEdge, trigger_value: Any,
        old_value: Any, params: ResolvedParameterSet,
    ) -> Dict[str, Any]:
        """Compute accrued dividends on cumulative preferred."""
        entity = edge.source_clause.applies_to
        rate_param = params.get("dividend_rate", entity)
        rate = rate_param.value if rate_param and isinstance(rate_param.value, (int, float)) else 0

        # Get the investment amount for this entity
        investment = 0.0
        for inst in params.instruments:
            holder = (inst.holder or "").lower().replace(" ", "_")
            if (holder == entity or entity in holder) and inst.instrument_type == "equity":
                investment += inst.principal_or_value

        # Get effective date to compute actual accrual period
        effective_date_param = edge.source_clause.effective_date
        years_accrued = 1.0
        if effective_date_param:
            try:
                from datetime import datetime as _dt
                eff = _dt.fromisoformat(str(effective_date_param).replace("Z", "+00:00"))
                now = _dt.utcnow()
                if eff.tzinfo:
                    now = now.replace(tzinfo=eff.tzinfo)
                years_accrued = max(0, (now - eff).days / 365.25)
            except (ValueError, TypeError):
                years_accrued = 1.0

        accrued = investment * rate * years_accrued

        return {
            "accrued_dividends": accrued,
            "rate": rate,
            "investment": investment,
            "years_accrued": years_accrued,
            "entity": entity,
        }

    def _compute_clawback(
        self, edge: CascadeEdge, trigger_value: Any,
        old_value: Any, params: ResolvedParameterSet,
    ) -> Dict[str, Any]:
        """Compute clawback — previously paid amounts that must be returned."""
        entity = edge.source_clause.applies_to
        clawback_val = edge.source_clause.value

        # trigger_value represents the clawback event
        amount = 0.0
        if isinstance(trigger_value, (int, float)):
            amount = trigger_value
        elif isinstance(trigger_value, dict):
            amount = trigger_value.get("clawback_amount", 0)

        if isinstance(clawback_val, dict):
            cap = clawback_val.get("cap")
            if cap and isinstance(cap, (int, float)):
                amount = min(amount, cap)

        return {
            "clawback_amount": amount,
            "entity": entity,
            "cash_impact": -amount,
        }

    def _evaluate_change_of_control(
        self, edge: CascadeEdge, trigger_value: Any,
        old_value: Any, params: ResolvedParameterSet,
    ) -> Dict[str, Any]:
        """Evaluate change of control consequences."""
        entity = edge.source_clause.applies_to
        coc_val = edge.source_clause.value

        threshold = 0.5
        trigger_type = "single"
        acceleration = False
        consent_required = False

        if isinstance(coc_val, dict):
            threshold = coc_val.get("threshold_pct", 0.5)
            trigger_type = coc_val.get("trigger", "single")
            acceleration = coc_val.get("acceleration", False)
            consent_required = coc_val.get("consent_required", False)

        ownership_change = trigger_value if isinstance(trigger_value, (int, float)) else 0
        triggered = ownership_change > threshold

        return {
            "coc_triggered": triggered,
            "threshold": threshold,
            "ownership_change": ownership_change,
            "trigger_type": trigger_type,
            "vesting_acceleration": acceleration and triggered,
            "consent_required": consent_required,
            "entity": entity,
        }

    def _compute_redemption(
        self, edge: CascadeEdge, trigger_value: Any,
        old_value: Any, params: ResolvedParameterSet,
    ) -> Dict[str, Any]:
        """Compute redemption — investor can force company to buy back shares."""
        entity = edge.source_clause.applies_to

        # Find the investment amount for this entity
        investment = 0.0
        liq_pref = 1.0
        for inst in params.instruments:
            holder = (inst.holder or "").lower().replace(" ", "_")
            if holder == entity or entity in holder:
                investment += inst.principal_or_value

        liq_param = params.get("liquidation_preference", entity)
        if liq_param and isinstance(liq_param.value, (int, float)):
            liq_pref = liq_param.value

        # Redemption amount = investment × preference multiple + accrued dividends
        div_accrual = self._compute_dividend_accrual(edge, trigger_value, old_value, params)
        accrued = div_accrual.get("accrued_dividends", 0)

        redemption_amount = investment * liq_pref + accrued

        return {
            "redemption_amount": redemption_amount,
            "investment": investment,
            "preference_multiple": liq_pref,
            "accrued_dividends": accrued,
            "cash_impact": redemption_amount,
            "entity": entity,
        }

    def _estimate_impact(
        self,
        edge: CascadeEdge,
        old_value: Any,
        new_value: Any,
        params: ResolvedParameterSet,
    ) -> Optional[float]:
        """Estimate financial impact of a cascade step in dollars.

        Uses the instrument data and computation results to derive dollar impact.
        """
        comp = edge.computation
        entity = edge.source_clause.applies_to

        # Get entity's investment/debt balance for reference
        entity_value = 0.0
        for inst in params.instruments:
            holder = (inst.holder or "").lower().replace(" ", "_")
            if holder == entity or entity in holder:
                entity_value += inst.principal_or_value

        if isinstance(new_value, dict):
            # Many computations return dicts with explicit impact fields
            if "cash_impact" in new_value:
                return float(new_value["cash_impact"])
            if "immediate_cash_impact" in new_value:
                return float(new_value["immediate_cash_impact"])
            if "triggered_exposure" in new_value:
                return float(new_value["triggered_exposure"])
            if "net_exposure" in new_value:
                return float(new_value["net_exposure"])
            if "payout" in new_value:
                return float(new_value["payout"])
            if "escrow_amount" in new_value:
                return float(new_value["escrow_amount"])
            if "redemption_amount" in new_value:
                return float(new_value["redemption_amount"])
            if "clawback_amount" in new_value:
                return -float(new_value["clawback_amount"])
            if "outstanding_balance" in new_value:
                return float(new_value["outstanding_balance"])
            if "intrinsic_value" in new_value:
                return float(new_value["intrinsic_value"])

        # Anti-dilution: impact = shares × (old_price - new_price)
        if comp == "compute_anti_dilution":
            if isinstance(old_value, (int, float)) and isinstance(new_value, (int, float)):
                if entity_value > 0 and old_value > 0:
                    shares = entity_value / old_value
                    return shares * (old_value - new_value)

        # PIK: impact = new_principal - old_principal
        if comp == "compute_pik_capitalization":
            if isinstance(old_value, (int, float)) and isinstance(new_value, (int, float)):
                return new_value - old_value

        # Ownership recalculation: impact in terms of value shift
        if comp == "recalculate_ownership" and isinstance(new_value, dict):
            dilution = new_value.get("dilution_factor", 1.0)
            if dilution < 1.0 and entity_value > 0:
                return entity_value * (dilution - 1.0)

        return None

    def _describe_step(
        self, edge: CascadeEdge, old_value: Any, new_value: Any
    ) -> str:
        """Generate a human-readable description of a cascade step."""
        return (
            f"{edge.description} | "
            f"{old_value} → {new_value} | "
            f"Source: {edge.source_clause.document_type} "
            f"{edge.source_clause.section_reference}"
        )

    def _describe_consent_constraint(self, param: ClauseParameter) -> str:
        coc_val = param.value if isinstance(param.value, dict) else {}
        if param.param_type == "protective_provisions":
            return (
                f"Protective provisions: {param.applies_to} must consent to "
                f"M&A, new debt, new shares, etc. ({param.section_reference})"
            )
        threshold = coc_val.get("threshold_pct", 0.5)
        return (
            f"Change of control (>{threshold*100:.0f}% ownership transfer) "
            f"requires consent of {param.applies_to} ({param.section_reference})"
        )

    def _describe_covenant_constraint(self, param: ClauseParameter) -> str:
        val = param.value
        if isinstance(val, dict):
            parts: List[str] = []
            if "dscr" in val:
                parts.append(f"DSCR must exceed {val['dscr']}x")
            if "leverage" in val:
                parts.append(f"Leverage must stay below {val['leverage']}x")
            covenant_desc = "; ".join(parts)
        else:
            covenant_desc = f"Must maintain {param.param_type}: {val}"
        return f"{covenant_desc} ({param.section_reference})"

    def _describe_transfer_constraint(self, param: ClauseParameter) -> str:
        if param.param_type == "rofr":
            return (
                f"Right of first refusal on transfers by {param.applies_to} "
                f"({param.section_reference})"
            )
        elif param.param_type == "lockup_period":
            return (
                f"Transfer lockup for {param.applies_to}: {param.value} "
                f"({param.section_reference})"
            )
        return (
            f"Transfer restriction on {param.applies_to}: {param.value} "
            f"({param.section_reference})"
        )

    def _compute_terminal_effects(
        self, result: CascadeResult, params: ResolvedParameterSet
    ) -> None:
        """Compute the terminal state after all cascade steps."""
        for step in result.steps:
            entity = step.param_affected.split(":")[-1]
            nv = step.new_value

            # Track ownership changes
            if "ownership" in step.param_affected or "dilution" in step.param_affected:
                if isinstance(nv, dict):
                    # _compute_ownership_recalculation returns ownership_pct & dilution
                    if "ownership_pct" in nv:
                        result.cap_table_delta[entity] = nv["ownership_pct"]
                    elif "dilution_pct" in nv:
                        result.cap_table_delta[entity] = -nv["dilution_pct"]
                elif isinstance(nv, (int, float)):
                    result.cap_table_delta[entity] = nv

            # Track governance changes
            if any(kw in step.param_affected for kw in
                   ("forced_sale", "consent_required", "board",
                    "drag_along", "tag_right", "coc")):
                result.governance_changes.append(step.description)

            # Track exposure changes
            if "liability" in step.param_affected or "exposure" in step.param_affected:
                if isinstance(nv, dict):
                    result.exposure_changes[entity] = (
                        nv.get("triggered_exposure")
                        or nv.get("net_exposure")
                        or nv.get("guarantee_amount", 0)
                    )
                elif isinstance(nv, (int, float)):
                    result.exposure_changes[entity] = nv

            # Track cash flow impact
            if any(kw in step.param_affected for kw in
                   ("acceleration", "repayment", "principal",
                    "redemption", "escrow", "clawback", "payout")):
                if isinstance(nv, dict):
                    result.cash_flow_delta[entity] = (
                        nv.get("cash_impact")
                        or nv.get("immediate_cash_impact")
                        or nv.get("redemption_amount")
                        or nv.get("escrow_amount")
                        or nv.get("payout", 0)
                    )
                elif isinstance(nv, (int, float)):
                    result.cash_flow_delta[entity] = nv

            # Track conversion events
            if "conversion" in step.param_affected or "warrant_exercise" in step.param_affected:
                if isinstance(nv, dict):
                    if "new_shares" in nv:
                        result.cap_table_delta.setdefault(entity, 0)
                        result.cap_table_delta[entity] += nv.get("dilution_pct", 0)
