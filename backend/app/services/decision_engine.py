"""
Decision Engine (Layer 6)

Given the constraints, cascades, and branch comparisons — frame actual
decisions with quantified trade-offs per stakeholder.

Three capabilities:
  1. frame_decision() — present viable options with financial impact per stakeholder
  2. negotiate() — multi-stakeholder game theory, counter-proposal generation
  3. analyze_cost_of_capital() — true cost comparison across instrument types

Every output has: dollar amounts at multiple exit values, stakeholder preference
mapping, divergence points, cascade risks, and full clause attribution.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from app.services.clause_parameter_registry import (
    ClauseParameter,
    ClauseParameterRegistry,
    ResolvedParameterSet,
)
from app.services.cascade_engine import (
    CascadeGraph,
    CascadeResult,
    Constraint,
)
from app.services.clause_diff_engine import (
    ClauseDiffEngine,
    DiffResult,
    COST_OF_CAPITAL_PARAMS,
)
from app.services.stakeholder_map import (
    StakeholderInteractionMap,
    StakeholderPosition,
    Coalition,
)
from app.services.scenario_branch_service import LegalBranchOverride

logger = logging.getLogger(__name__)

DEFAULT_REFERENCE_EXITS = [10e6, 25e6, 50e6, 100e6, 200e6, 500e6]

# Cost model parameters — heuristic multipliers for comparing term impact.
# These are relative estimates, not pricing. Used for option comparison only.
FULL_RATCHET_COST_FRACTION = 0.5       # Full ratchet exposure as fraction of base dilution
NARROW_WA_COST_FRACTION = 0.1          # Narrow weighted average cost fraction
UNCAPPED_PARTICIPATION_FRACTION = 0.5  # Uncapped participation cost fraction
CAPPED_PARTICIPATION_SCALE = 0.15      # Per-turn cost scaling for capped participation
CAPPED_PARTICIPATION_MAX = 0.3         # Max participation cost fraction

# Negotiation classification thresholds
CONCEDE_COST_RATIO = 0.3   # cost < 30% of value to them → concede
FIGHT_COST_RATIO = 2.0     # cost > 200% of value to them → fight

# Divergence reporting
DIVERGENCE_MATERIALITY = 1_000_000  # $1M minimum for reporting divergence


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class DecisionOption:
    """A single option in a decision with full financial quantification."""
    name: str
    description: str = ""

    # Financial impact at reference exits
    waterfall_by_exit: Dict[float, Dict[str, float]] = field(default_factory=dict)
    # exit_value → stakeholder → proceeds
    ownership_impact: Dict[str, float] = field(default_factory=dict)
    # stakeholder → post-deal ownership %
    effective_cost_of_capital: float = 0.0
    runway_impact_months: float = 0.0

    # Risk and constraints
    new_constraints: List[str] = field(default_factory=list)
    cascade_risks: List[str] = field(default_factory=list)
    # downstream triggers with attribution

    # Breakpoints
    breakeven_exit: float = 0.0
    # common breakeven under this option
    pwerm_return: float = 0.0
    # probability-weighted expected return

    # Stakeholder preferences
    stakeholder_preference: Dict[str, str] = field(default_factory=dict)
    # stakeholder → "prefers" / "opposes" / "neutral"

    # Blocked?
    is_blocked: bool = False
    blocked_reason: str = ""
    # e.g. "Requires lender consent (Facility S.7.1)"


@dataclass
class Decision:
    """A framed decision with quantified trade-offs."""
    question: str
    # "Raise equity, take debt, or bridge?"
    decision_type: str
    # "raise_equity", "take_debt", "sell", "restructure", etc.
    viable_options: List[DecisionOption] = field(default_factory=list)
    blocked_options: List[DecisionOption] = field(default_factory=list)
    # options that are legally blocked with reasons
    stakeholder_alignment: Dict[str, Dict[str, str]] = field(default_factory=dict)
    # stakeholder → option_name → "prefers" / "opposes" / "neutral"
    divergence_points: List[str] = field(default_factory=list)
    # exit values where stakeholder interests flip
    recommendation: str = ""
    summary: str = ""


@dataclass
class NegotiationDelta:
    """A single clause change in a negotiation with asymmetric cost analysis."""
    param_type: str
    applies_to: str
    our_value: Any
    their_value: Any
    cost_to_us: Dict[float, float] = field(default_factory=dict)
    # exit_value → dollar impact on us
    value_to_them: Dict[float, float] = field(default_factory=dict)
    # exit_value → dollar impact on them
    classification: str = ""
    # "concede" (cheap for us, valuable to them)
    # "fight" (expensive for us)
    # "counter" (expensive but negotiable)
    rationale: str = ""
    source_clause: str = ""


@dataclass
class CounterProposal:
    """A generated counter-proposal with financial justification."""
    accept: List[NegotiationDelta] = field(default_factory=list)
    # items to concede
    counter: List[NegotiationDelta] = field(default_factory=list)
    # items to counter with alternatives
    fight: List[NegotiationDelta] = field(default_factory=list)
    # items to reject
    resulting_params: Optional[ResolvedParameterSet] = None
    meets_objectives: Dict[str, bool] = field(default_factory=dict)
    # objective → whether counter meets it
    description: str = ""


@dataclass
class NegotiationAnalysis:
    """Full negotiation analysis with game theory."""
    our_position_summary: str = ""
    their_position_summary: str = ""
    diff: Optional[DiffResult] = None
    deltas: List[NegotiationDelta] = field(default_factory=list)
    their_likely_priorities: List[str] = field(default_factory=list)
    # inferred from what they changed
    counter_proposal: Optional[CounterProposal] = None
    multi_stakeholder_dynamics: List[str] = field(default_factory=list)
    # e.g. "Series A will support our counter because..."
    summary: str = ""


@dataclass
class CostOfCapitalBreakdown:
    """Cost of capital analysis for a single instrument/option."""
    name: str
    instrument_type: str
    headline_cost: str
    # "20% dilution", "12% annual", "$3M at 20% discount"
    real_cost_components: List[str] = field(default_factory=list)
    # ["20% dilution", "anti-dilution exposure +5%", "preference stack +3%"]
    effective_annual_cost: float = 0.0
    runway_months: float = 0.0
    dilution_pct: float = 0.0
    new_constraints: List[str] = field(default_factory=list)
    description: str = ""


@dataclass
class CostOfCapitalAnalysis:
    """Comparison of cost of capital across instrument types."""
    options: List[CostOfCapitalBreakdown] = field(default_factory=list)
    cheapest: str = ""
    most_expensive: str = ""
    recommendation: str = ""
    summary: str = ""


# ---------------------------------------------------------------------------
# Decision Engine
# ---------------------------------------------------------------------------

class DecisionEngine:
    """
    Frame decisions, run negotiation game theory, and analyze cost of capital.

    Combines: cascade engine (risk), stakeholder map (alignment),
    clause diff (delta impact), legal branches (scenarios).
    """

    def __init__(self) -> None:
        self.diff_engine = ClauseDiffEngine()
        self.registry = ClauseParameterRegistry()

    def frame_decision(
        self,
        company_id: str,
        decision_type: str,
        candidates: List[LegalBranchOverride],
        current_params: ResolvedParameterSet,
        reference_exits: Optional[List[float]] = None,
    ) -> Decision:
        """
        Frame a decision with quantified options.

        1. Constraint check — which options are legally possible?
        2. For each viable option, create a legal branch
        3. Run cascade — what triggers?
        4. Run waterfall at multiple exits — who gets what?
        5. Compute effective cost of capital for each option
        6. Map stakeholder preferences
        7. Find divergence points
        """
        exits = reference_exits or DEFAULT_REFERENCE_EXITS
        decision = Decision(
            question=self._frame_question(decision_type, candidates),
            decision_type=decision_type,
        )

        # Step 1: Constraint check
        constraints = self._get_constraints(current_params)

        for candidate in candidates:
            option = self._evaluate_option(
                candidate, current_params, constraints, exits
            )
            if option.is_blocked:
                decision.blocked_options.append(option)
            else:
                decision.viable_options.append(option)

        # Step 6: Stakeholder alignment across options
        decision.stakeholder_alignment = self._map_stakeholder_alignment(
            decision.viable_options
        )

        # Step 7: Divergence points
        decision.divergence_points = self._find_divergence_points(
            decision.viable_options, exits
        )

        # Recommendation
        decision.recommendation = self._generate_recommendation(decision, exits)
        decision.summary = self._generate_decision_summary(decision)

        return decision

    def negotiate(
        self,
        company_id: str,
        our_position: ResolvedParameterSet,
        their_position: ResolvedParameterSet,
        our_objectives: List[str],
        reference_exits: Optional[List[float]] = None,
    ) -> NegotiationAnalysis:
        """
        Multi-stakeholder negotiation game theory.

        1. Diff the two positions
        2. For each delta, compute cost asymmetry
        3. Classify: concede / counter / fight
        4. Infer their priorities from what they changed
        5. Generate counter-proposal
        6. Verify counter meets our objectives
        7. Map multi-stakeholder dynamics
        """
        exits = reference_exits or DEFAULT_REFERENCE_EXITS
        analysis = NegotiationAnalysis()

        # Step 1: Diff
        analysis.diff = self.diff_engine.diff(our_position, their_position, exits)

        # Step 2-3: Analyze each delta
        for clause_delta in analysis.diff.deltas:
            neg_delta = self._analyze_negotiation_delta(
                clause_delta, our_position, their_position, exits
            )
            analysis.deltas.append(neg_delta)

        # Step 4: Infer their priorities
        analysis.their_likely_priorities = self._infer_priorities(analysis.deltas)

        # Step 5: Generate counter-proposal
        analysis.counter_proposal = self._generate_counter(
            analysis.deltas, our_position, their_position, our_objectives, exits
        )

        # Step 6: Multi-stakeholder dynamics
        analysis.multi_stakeholder_dynamics = self._analyze_dynamics(
            our_position, their_position, analysis.deltas
        )

        # Summaries
        analysis.our_position_summary = self._summarize_position(our_position, "Our")
        analysis.their_position_summary = self._summarize_position(their_position, "Their")
        analysis.summary = self._generate_negotiation_summary(analysis)

        return analysis

    def analyze_cost_of_capital(
        self,
        company_id: str,
        instrument_options: List[ResolvedParameterSet],
        option_names: Optional[List[str]] = None,
    ) -> CostOfCapitalAnalysis:
        """
        True cost of capital comparison across instrument types.

        Not just headline terms — includes preferences, anti-dilution cost,
        warrant dilution, dividend accrual, covenant cost, conversion scenarios.
        """
        analysis = CostOfCapitalAnalysis()
        names = option_names or [f"Option {i+1}" for i in range(len(instrument_options))]

        for i, params in enumerate(instrument_options):
            name = names[i] if i < len(names) else f"Option {i+1}"
            breakdown = self._compute_cost_breakdown(name, params)
            analysis.options.append(breakdown)

        # Sort by effective cost
        if analysis.options:
            sorted_opts = sorted(analysis.options, key=lambda o: o.effective_annual_cost)
            analysis.cheapest = sorted_opts[0].name
            analysis.most_expensive = sorted_opts[-1].name

            analysis.recommendation = (
                f"Cheapest capital: {analysis.cheapest} "
                f"({sorted_opts[0].effective_annual_cost*100:.1f}% effective). "
                f"Most expensive: {analysis.most_expensive} "
                f"({sorted_opts[-1].effective_annual_cost*100:.1f}% effective)."
            )

        analysis.summary = self._generate_coc_summary(analysis)
        return analysis

    # ------------------------------------------------------------------
    # Group-level decision framing
    # ------------------------------------------------------------------

    def frame_group_decision(
        self,
        company_id: str,
        decision_type: str,
        candidates: List[LegalBranchOverride],
        current_params: ResolvedParameterSet,
        group_structure: Optional[Any] = None,
        reference_exits: Optional[List[float]] = None,
    ) -> Decision:
        """
        Frame a decision with group-level cascade awareness.

        Extends frame_decision() to layer group-structure edges onto
        the cascade graph. This catches:
          - Subsidiary default → parent guarantee trigger
          - Intercompany flow blockage from covenant breach
          - Ring-fencing that traps cash in a subsidiary
          - Cross-default contagion across group entities
          - Thin cap breach → interest non-deductibility

        If no group_structure is provided, falls back to standard
        frame_decision().
        """
        if group_structure is None:
            return self.frame_decision(
                company_id, decision_type, candidates, current_params, reference_exits
            )

        exits = reference_exits or DEFAULT_REFERENCE_EXITS
        decision = Decision(
            question=self._frame_question(decision_type, candidates),
            decision_type=decision_type,
        )

        # Build cascade graph WITH group edges
        base_graph = CascadeGraph()
        base_graph.build_from_clauses(current_params)
        base_graph.build_group_edges(group_structure, current_params)
        constraints = base_graph.identify_constraints()

        # Add group-level constraints from the structure itself
        for fc in getattr(group_structure, "constraints", []):
            constraints.append(Constraint(
                constraint_type=fc.constraint_type,
                description=fc.description,
                source_clause=fc.source_clause or ClauseParameter(
                    param_type=fc.constraint_type,
                    value=True,
                    applies_to=fc.affected_entity_id or "group",
                    instrument="group_structure",
                    source_document_id="group_structure",
                    source_clause_id="group_derived",
                    section_reference="Group structure",
                    source_quote=fc.description,
                    document_type="group_analysis",
                ),
            ))

        for candidate in candidates:
            option = self._evaluate_group_option(
                candidate, current_params, constraints, exits, group_structure
            )
            if option.is_blocked:
                decision.blocked_options.append(option)
            else:
                decision.viable_options.append(option)

        decision.stakeholder_alignment = self._map_stakeholder_alignment(
            decision.viable_options
        )
        decision.divergence_points = self._find_divergence_points(
            decision.viable_options, exits
        )
        decision.recommendation = self._generate_recommendation(decision, exits)
        decision.summary = self._generate_decision_summary(decision)

        return decision

    def _evaluate_group_option(
        self,
        candidate: LegalBranchOverride,
        current_params: ResolvedParameterSet,
        constraints: List[Constraint],
        exits: List[float],
        group_structure: Any,
    ) -> DecisionOption:
        """Evaluate a single option with group-level cascade awareness."""
        option = DecisionOption(
            name=candidate.description or "Unnamed option",
        )

        # Check constraints (including group-level)
        for constraint in constraints:
            if self._option_violates_constraint(candidate, constraint):
                option.is_blocked = True
                option.blocked_reason = (
                    f"{constraint.description} "
                    f"({constraint.source_clause.section_reference})"
                )
                return option

        # Build branch params and cascade graph with group edges
        branch_params = self._apply_override(current_params, candidate)
        cascade_graph = CascadeGraph()
        cascade_graph.build_from_clauses(branch_params)
        cascade_graph.build_group_edges(group_structure, branch_params)

        # Cascade risks including group contagion
        all_constraints = cascade_graph.identify_constraints()
        option.cascade_risks = [c.description for c in all_constraints]

        current_constraint_set = {c.description for c in constraints}
        for new_c in all_constraints:
            if new_c.description not in current_constraint_set:
                option.new_constraints.append(new_c.description)

        # Waterfall analysis
        smap = StakeholderInteractionMap()
        smap.build(branch_params)

        for exit_val in exits:
            waterfall = smap._run_waterfall(exit_val)
            option.waterfall_by_exit[exit_val] = waterfall

        option.ownership_impact = {
            name: pos.ownership_pct
            for name, pos in smap.positions.items()
        }

        common_pos = smap.positions.get("common") or smap.positions.get("founders")
        if common_pos:
            option.breakeven_exit = common_pos.breakeven_exit

        option.effective_cost_of_capital = self._estimate_effective_cost(branch_params)

        # PWERM return
        option.pwerm_return = self._compute_pwerm_return(
            option.waterfall_by_exit, exits
        )

        # Runway impact
        option.runway_impact_months = self._compute_runway_months(branch_params)

        # Stakeholder preference
        diff = self.diff_engine.diff(current_params, branch_params, exits)
        for stakeholder, si in diff.stakeholder_impacts.items():
            if si.alignment_shift == "better":
                option.stakeholder_preference[stakeholder] = "prefers"
            elif si.alignment_shift == "worse":
                option.stakeholder_preference[stakeholder] = "opposes"
            else:
                option.stakeholder_preference[stakeholder] = "neutral"

        return option

    # ------------------------------------------------------------------
    # frame_decision internals
    # ------------------------------------------------------------------

    def _frame_question(
        self, decision_type: str, candidates: List[LegalBranchOverride]
    ) -> str:
        """Generate the decision question from type and candidates."""
        type_questions = {
            "raise_equity": "Which equity round terms should we accept?",
            "take_debt": "Which debt facility should we take?",
            "sell": "Should we sell, and at what terms?",
            "restructure": "How should we restructure the capital stack?",
            "refinance": "Which refinancing option is best?",
            "secondary": "Should we pursue a secondary transaction?",
            "bridge": "Which bridge financing option?",
            "down_round": "How do we structure the down round?",
        }
        base = type_questions.get(decision_type, f"Which {decision_type} option?")

        if candidates:
            options_desc = ", ".join(
                c.description or f"Option {i+1}"
                for i, c in enumerate(candidates)
            )
            return f"{base} Options: {options_desc}"

        return base

    def _get_constraints(
        self, params: ResolvedParameterSet
    ) -> List[Constraint]:
        """Get current constraints from cascade graph."""
        graph = CascadeGraph()
        graph.build_from_clauses(params)
        return graph.identify_constraints()

    def _evaluate_option(
        self,
        candidate: LegalBranchOverride,
        current_params: ResolvedParameterSet,
        constraints: List[Constraint],
        exits: List[float],
    ) -> DecisionOption:
        """Evaluate a single decision option."""
        option = DecisionOption(
            name=candidate.description or "Unnamed option",
        )

        # Check if blocked by constraints
        for constraint in constraints:
            if self._option_violates_constraint(candidate, constraint):
                option.is_blocked = True
                option.blocked_reason = (
                    f"{constraint.description} "
                    f"({constraint.source_clause.section_reference})"
                )
                return option

        # Build branch params
        branch_params = self._apply_override(current_params, candidate)

        # Run cascade
        cascade_graph = CascadeGraph()
        cascade_graph.build_from_clauses(branch_params)

        # Cascade risks
        option.cascade_risks = [
            c.description for c in cascade_graph.identify_constraints()
        ]

        # New constraints
        current_constraint_set = {c.description for c in constraints}
        for new_c in cascade_graph.identify_constraints():
            if new_c.description not in current_constraint_set:
                option.new_constraints.append(new_c.description)

        # Run stakeholder map for waterfall at each exit
        smap = StakeholderInteractionMap()
        smap.build(branch_params)

        for exit_val in exits:
            waterfall = smap._run_waterfall(exit_val)
            option.waterfall_by_exit[exit_val] = waterfall

        # Ownership impact
        option.ownership_impact = {
            name: pos.ownership_pct
            for name, pos in smap.positions.items()
        }

        # Breakeven
        common_pos = smap.positions.get("common") or smap.positions.get("founders")
        if common_pos:
            option.breakeven_exit = common_pos.breakeven_exit

        # Cost of capital
        option.effective_cost_of_capital = self._estimate_effective_cost(branch_params)

        # PWERM return
        option.pwerm_return = self._compute_pwerm_return(
            option.waterfall_by_exit, exits
        )

        # Runway impact
        option.runway_impact_months = self._compute_runway_months(branch_params)

        # Stakeholder preference
        # Compare against current params to see who benefits
        diff = self.diff_engine.diff(current_params, branch_params, exits)
        for stakeholder, si in diff.stakeholder_impacts.items():
            if si.alignment_shift == "better":
                option.stakeholder_preference[stakeholder] = "prefers"
            elif si.alignment_shift == "worse":
                option.stakeholder_preference[stakeholder] = "opposes"
            else:
                option.stakeholder_preference[stakeholder] = "neutral"

        return option

    def _option_violates_constraint(
        self, candidate: LegalBranchOverride, constraint: Constraint
    ) -> bool:
        """Check if an option violates a constraint.

        Examines override keys against the constraint scope.  A constraint
        blocks an option when the override touches parameters in the
        constrained domain and the constraint conditions are met.
        """
        ct = constraint.constraint_type
        overrides = candidate.param_overrides

        def _overrides_touch(*terms: str) -> bool:
            return any(
                any(t in k.lower() for t in terms) for k in overrides
            )

        # Consent-required: blocks when override touches the consented domain
        if ct == "consent_required":
            scope = ""
            if constraint.source_clause:
                scope = (constraint.source_clause.applies_to or "").lower()
            if _overrides_touch("debt", "loan", "facility") and (
                "debt" in scope or "lender" in scope or not scope
            ):
                return True
            if _overrides_touch("equity", "share", "issuance", "round") and (
                "equity" in scope or "investor" in scope or not scope
            ):
                return True
            if _overrides_touch("sale", "transfer", "exit", "merger") and (
                "transfer" in scope or "sale" in scope or not scope
            ):
                return True
            return False

        # Covenant: blocks when headroom is tight and option adds leverage
        if ct == "covenant":
            if constraint.current_headroom is not None and constraint.current_headroom < 0.1:
                if _overrides_touch("debt", "leverage", "loan", "facility", "borrowing"):
                    return True
            return False

        # Preemption rights — new equity issuance triggers preemption
        if ct == "preemption":
            return _overrides_touch("share", "equity", "issuance", "round", "investment_amount")

        # Transfer restriction — blocks transfers/sales
        if ct == "transfer_restriction":
            return _overrides_touch("transfer", "sale", "secondary", "assign")

        # Restricted payment — blocks dividends/distributions
        if ct == "restricted_payment":
            return _overrides_touch("dividend", "distribution", "payment", "redemption")

        # Ring-fencing — subsidiary cash trapped
        if ct == "ring_fencing":
            return _overrides_touch("intercompany", "upstream", "dividend", "distribution")

        # Cross-default — default contagion
        if ct == "cross_default":
            return _overrides_touch("default", "breach", "waiver", "acceleration")

        # Forced sale / drag-along — requires threshold consent
        if ct in ("forced_sale", "drag_along"):
            return _overrides_touch("sale", "exit", "acquisition", "merger")

        # Tag-along — may block partial transfers
        if ct == "tag_along":
            return _overrides_touch("transfer", "sale", "secondary")

        return False

    def _apply_override(
        self,
        current_params: ResolvedParameterSet,
        candidate: LegalBranchOverride,
    ) -> ResolvedParameterSet:
        """Apply a legal branch override to create hypothetical params."""
        return self.registry.resolve_with_overrides(
            current_params.company_id,
            [],  # no new docs
            candidate.param_overrides,
        ) if not current_params.parameters else self._merge_overrides(
            current_params, candidate.param_overrides
        )

    def _merge_overrides(
        self,
        current: ResolvedParameterSet,
        overrides: Dict[str, Any],
    ) -> ResolvedParameterSet:
        """Merge overrides onto existing resolved parameters."""
        merged = ResolvedParameterSet(
            company_id=current.company_id,
            parameters=dict(current.parameters),
            conflicts=list(current.conflicts),
            override_chain=list(current.override_chain),
            gaps=list(current.gaps),
            instruments=list(current.instruments),
        )

        for key, value in overrides.items():
            if key in merged.parameters:
                original = merged.parameters[key]
                merged.parameters[key] = ClauseParameter(
                    param_type=original.param_type,
                    value=value,
                    applies_to=original.applies_to,
                    instrument=original.instrument,
                    source_document_id="branch_override",
                    source_clause_id="override",
                    section_reference="Branch override",
                    source_quote="",
                    document_type="override",
                    confidence=1.0,
                )
            else:
                # New parameter
                parts = key.split(":", 1)
                param_type = parts[0]
                applies_to = parts[1] if len(parts) > 1 else "all"
                merged.parameters[key] = ClauseParameter(
                    param_type=param_type,
                    value=value,
                    applies_to=applies_to,
                    instrument="equity",
                    source_document_id="branch_override",
                    source_clause_id="override",
                    section_reference="Branch override",
                    source_quote="",
                    document_type="override",
                    confidence=1.0,
                )

        return merged

    # ------------------------------------------------------------------
    # negotiate internals
    # ------------------------------------------------------------------

    def _analyze_negotiation_delta(
        self,
        clause_delta,
        our_position: ResolvedParameterSet,
        their_position: ResolvedParameterSet,
        exits: List[float],
    ) -> NegotiationDelta:
        """Analyze a single clause change for negotiation asymmetry."""
        delta = NegotiationDelta(
            param_type=clause_delta.param_type,
            applies_to=clause_delta.applies_to,
            our_value=clause_delta.old_value,
            their_value=clause_delta.new_value,
        )

        # Compute cost to us and value to them at each exit
        for exit_val in exits:
            our_impact = clause_delta.impact.waterfall_delta.get(exit_val, {})
            # Cost to us = negative impact on founders/common
            cost = abs(our_impact.get("common", 0) + our_impact.get("founders", 0))
            delta.cost_to_us[exit_val] = cost

            # Value to them = positive impact on the investor
            value = our_impact.get(clause_delta.applies_to, 0)
            delta.value_to_them[exit_val] = max(0, value)

        # Classify
        avg_cost = sum(delta.cost_to_us.values()) / len(exits) if exits else 0
        avg_value = sum(delta.value_to_them.values()) / len(exits) if exits else 0

        if avg_cost < avg_value * CONCEDE_COST_RATIO:
            # Cheap for us, valuable to them — concede
            delta.classification = "concede"
            delta.rationale = (
                f"Low cost to us (avg ${avg_cost/1e6:.2f}M) but valuable to them "
                f"(avg ${avg_value/1e6:.2f}M). Good bargaining chip."
            )
        elif avg_cost > avg_value * FIGHT_COST_RATIO:
            # Very expensive for us — fight
            delta.classification = "fight"
            delta.rationale = (
                f"Costs us ${avg_cost/1e6:.2f}M avg across exits. "
                f"Disproportionate to value it provides them (${avg_value/1e6:.2f}M)."
            )
        else:
            # Negotiable — counter with cheaper alternative
            delta.classification = "counter"
            delta.rationale = (
                f"Material cost (${avg_cost/1e6:.2f}M) but negotiable. "
                f"Look for cheaper alternatives that meet their underlying need."
            )

        # Source attribution
        src = clause_delta.new_source or clause_delta.old_source
        if src:
            delta.source_clause = f"{src.document_type} {src.section_reference}"

        return delta

    def _infer_priorities(self, deltas: List[NegotiationDelta]) -> List[str]:
        """Infer the other party's priorities from what they changed."""
        priorities: List[str] = []

        # Group by classification and sort by their value
        fight_items = sorted(
            [d for d in deltas if d.classification == "fight"],
            key=lambda d: sum(d.value_to_them.values()),
            reverse=True,
        )
        counter_items = sorted(
            [d for d in deltas if d.classification == "counter"],
            key=lambda d: sum(d.value_to_them.values()),
            reverse=True,
        )

        # Their top priorities are what they pushed hardest on
        if fight_items:
            top_fights = fight_items[:3]
            fight_types = [d.param_type for d in top_fights]
            priorities.append(
                f"Pushed hardest on: {', '.join(fight_types)}."
            )

            # Infer pattern
            if any("anti_dilution" in ft for ft in fight_types):
                priorities.append(
                    "Pattern: downside protection focus. Worried about a down round."
                )
            if any("participation" in ft for ft in fight_types):
                priorities.append(
                    "Pattern: upside capture. Wants economics at all exit levels."
                )
            if any("board" in ft or "protective" in ft for ft in fight_types):
                priorities.append(
                    "Pattern: control focus. Wants governance influence."
                )
            if any("liquidation" in ft for ft in fight_types):
                priorities.append(
                    "Pattern: preference stacking. Securing downside at others' expense."
                )

        # What they didn't push on
        concede_types = [d.param_type for d in deltas if d.classification == "concede"]
        if concede_types:
            priorities.append(
                f"Didn't push on: {', '.join(concede_types[:5])}."
            )

        return priorities

    def _generate_counter(
        self,
        deltas: List[NegotiationDelta],
        our_position: ResolvedParameterSet,
        their_position: ResolvedParameterSet,
        objectives: List[str],
        exits: List[float],
    ) -> CounterProposal:
        """Generate a counter-proposal based on cost asymmetry analysis."""
        counter = CounterProposal()

        for delta in deltas:
            if delta.classification == "concede":
                counter.accept.append(delta)
            elif delta.classification == "fight":
                counter.fight.append(delta)
            else:
                counter.counter.append(delta)

        # Generate alternatives for counter items
        for item in counter.counter:
            item.rationale = self._suggest_alternative(item)

        # Build resulting params from counter-proposal
        overrides: Dict[str, Any] = {}
        # Accept: use their value
        for item in counter.accept:
            key = f"{item.param_type}:{item.applies_to}"
            overrides[key] = item.their_value
        # Fight: keep our value (no override needed)
        # Counter: propose middle ground
        for item in counter.counter:
            key = f"{item.param_type}:{item.applies_to}"
            middle = self._compute_middle_ground(item)
            overrides[key] = middle

        counter.resulting_params = self._merge_overrides(our_position, overrides)

        # Check if counter meets objectives
        for objective in objectives:
            counter.meets_objectives[objective] = self._check_objective(
                objective, counter.resulting_params, exits
            )

        # Description
        parts = []
        if counter.accept:
            parts.append(
                f"Accept ({len(counter.accept)}): "
                + ", ".join(d.param_type for d in counter.accept)
            )
        if counter.counter:
            parts.append(
                f"Counter ({len(counter.counter)}): "
                + ", ".join(d.param_type for d in counter.counter)
            )
        if counter.fight:
            parts.append(
                f"Reject ({len(counter.fight)}): "
                + ", ".join(d.param_type for d in counter.fight)
            )

        unmet = [obj for obj, met in counter.meets_objectives.items() if not met]
        if unmet:
            parts.append(f"WARNING: Counter may not meet: {', '.join(unmet)}")

        counter.description = "\n".join(parts)

        return counter

    def _suggest_alternative(self, delta: NegotiationDelta) -> str:
        """Suggest a cheaper alternative for a counter item."""
        pt = delta.param_type

        alternatives = {
            "anti_dilution_method": (
                f"{delta.their_value} → broad-based weighted average. "
                f"Still provides protection, much lower dilution risk to founders."
            ),
            "liquidation_preference": (
                f"{delta.their_value}x → 1x. "
                f"Standard for this stage. Saves founders significant downside."
            ),
            "participation_rights": (
                f"Participating → capped participating at 3x. "
                f"Limits double-dip while giving some upside participation."
            ),
            "board_seats": (
                f"Board seat → observer seat. "
                f"Information access without control. Low cost to us."
            ),
        }

        return alternatives.get(pt, delta.rationale)

    def _compute_middle_ground(self, delta: NegotiationDelta) -> Any:
        """Compute a reasonable middle ground for a negotiation delta."""
        pt = delta.param_type

        if pt == "liquidation_preference":
            # Split the difference on multiples
            our = delta.our_value if isinstance(delta.our_value, (int, float)) else 1.0
            their = delta.their_value if isinstance(delta.their_value, (int, float)) else 1.0
            return (our + their) / 2

        if pt == "anti_dilution_method":
            # Always counter with broad-based weighted average
            return "broad_weighted_average"

        if pt == "participation_rights":
            # Counter with capped participation
            return {"participating": True, "cap": 3.0}

        if pt == "board_seats":
            # Counter with observer
            return {"seats": 0, "observer": True}

        # Default: keep our value
        return delta.our_value

    def _check_objective(
        self,
        objective: str,
        params: ResolvedParameterSet,
        exits: List[float],
    ) -> bool:
        """Check if resolved params meet a stated objective.

        Returns True only when the objective can be verified as met.
        Returns False when not met or when verification is not possible,
        so that unverifiable objectives surface as warnings.
        """
        obj_lower = objective.lower()

        if "board control" in obj_lower or "maintain board" in obj_lower:
            founder_seats = 0
            investor_seats = 0
            for param in params.parameters.values():
                if param.param_type == "board_seats":
                    val = param.value
                    seats = val.get("seats", 1) if isinstance(val, dict) else int(val)
                    if param.applies_to in ("founders", "common"):
                        founder_seats += seats
                    else:
                        investor_seats += seats
            return founder_seats > investor_seats

        if "ratchet" in obj_lower or "anti-dilution" in obj_lower:
            ad_params = params.get_all("anti_dilution_method")
            return not any(p.value == "full_ratchet" for p in ad_params)

        if "ownership" in obj_lower or "dilution" in obj_lower:
            # Build stakeholder map to compute actual ownership
            smap = StakeholderInteractionMap()
            smap.build(params)

            target_match = re.search(r"(\d+)\s*%", objective)
            target_pct = float(target_match.group(1)) / 100 if target_match else 0.50

            founder_ownership = sum(
                pos.ownership_pct
                for name, pos in smap.positions.items()
                if name in ("founders", "common")
            )
            if "dilution" in obj_lower:
                # "limit dilution to X%" → founders keep at least (1-X)
                return founder_ownership >= (1.0 - target_pct)
            return founder_ownership >= target_pct

        if "covenant" in obj_lower or "compliance" in obj_lower:
            graph = CascadeGraph()
            graph.build_from_clauses(params)
            for c in graph.identify_constraints():
                if c.constraint_type == "covenant" and c.current_headroom is not None:
                    if c.current_headroom < 0.05:
                        return False
            return True

        if "preference" in obj_lower or "liquidation" in obj_lower:
            max_match = re.search(r"(\d+\.?\d*)x", objective)
            max_pref = float(max_match.group(1)) if max_match else 1.0
            for lp in params.get_all("liquidation_preference"):
                mult = lp.value if isinstance(lp.value, (int, float)) else 1.0
                if mult > max_pref:
                    return False
            return True

        # Unknown objective — conservative: cannot verify
        logger.warning(f"Cannot verify objective: {objective}")
        return False

    def _analyze_dynamics(
        self,
        our_position: ResolvedParameterSet,
        their_position: ResolvedParameterSet,
        deltas: List[NegotiationDelta],
    ) -> List[str]:
        """Analyze multi-stakeholder dynamics in the negotiation."""
        dynamics: List[str] = []

        # Build stakeholder map for current structure
        smap = StakeholderInteractionMap()
        smap.build(our_position)

        # Check if existing investors benefit from our counter-position
        for name, pos in smap.positions.items():
            if name in ("common", "founders", "option_pool"):
                continue

            # Existing investors generally prefer:
            # 1. Broad-based WA over full ratchet (protects them too)
            # 2. Lower preference multiples for new investors (preserves their stack)
            # 3. No new board seats (maintains their influence)

            for delta in deltas:
                if delta.classification == "fight":
                    if delta.param_type == "anti_dilution_method":
                        dynamics.append(
                            f"{name} likely supports our counter on anti-dilution — "
                            f"broad-based WA protects existing investors equally."
                        )
                    if delta.param_type == "liquidation_preference":
                        if isinstance(delta.their_value, (int, float)) and delta.their_value > 1.5:
                            dynamics.append(
                                f"{name} may support our counter on preference — "
                                f"higher new preference dilutes existing preference stack."
                            )
                    if delta.param_type == "board_seats":
                        if pos.board_seats > 0:
                            dynamics.append(
                                f"{name} holds {pos.board_seats} board seat(s). "
                                f"New board seat dilutes their governance influence."
                            )

        return dynamics

    # ------------------------------------------------------------------
    # cost of capital internals
    # ------------------------------------------------------------------

    def _compute_cost_breakdown(
        self, name: str, params: ResolvedParameterSet
    ) -> CostOfCapitalBreakdown:
        """Compute detailed cost of capital breakdown for a set of params."""
        breakdown = CostOfCapitalBreakdown(name=name, instrument_type="equity")

        components: List[str] = []
        effective_cost = 0.0

        # Identify instrument type from params
        has_debt = bool(params.get_all("interest_rate"))
        has_convertible = bool(
            params.get_all("conversion_discount") or params.get_all("valuation_cap")
        )
        has_warrants = bool(params.get_all("warrant_coverage"))

        if has_debt:
            breakdown.instrument_type = "debt"
            rates = params.get_all("interest_rate")
            if rates:
                rate = rates[0].value if isinstance(rates[0].value, (int, float)) else 0
                effective_cost = rate
                components.append(f"Interest rate: {rate*100:.1f}%")
                breakdown.headline_cost = f"{rate*100:.1f}% annual"

            if has_warrants:
                warrants = params.get_all("warrant_coverage")
                if warrants:
                    cov = warrants[0].value if isinstance(warrants[0].value, (int, float)) else 0
                    effective_cost += cov  # Warrant dilution ≈ coverage ratio
                    breakdown.dilution_pct = cov
                    components.append(f"Warrant coverage: {cov*100:.2f}% dilution")
                    breakdown.headline_cost += f" + {cov*100:.2f}% warrants"

            # List covenant constraints (operational restrictions, not quantifiable
            # as a cost without full scenario analysis)
            for cov_param in params.get_all("covenant_dscr_threshold"):
                threshold = cov_param.value if isinstance(cov_param.value, (int, float)) else None
                if threshold is not None:
                    components.append(f"DSCR covenant: {threshold}x minimum")
                breakdown.new_constraints.append(
                    f"DSCR covenant: {cov_param.value} ({cov_param.section_reference})"
                )

            for lev_param in params.get_all("covenant_leverage_ratio"):
                max_lev = lev_param.value if isinstance(lev_param.value, (int, float)) else None
                if max_lev is not None:
                    components.append(f"Leverage covenant: {max_lev}x maximum")
                breakdown.new_constraints.append(
                    f"Leverage covenant: {lev_param.value}x ({lev_param.section_reference})"
                )

        elif has_convertible:
            breakdown.instrument_type = "convertible"
            discounts = params.get_all("conversion_discount")
            caps = params.get_all("valuation_cap")

            if discounts:
                d = discounts[0].value if isinstance(discounts[0].value, (int, float)) else 0
                if d > 0:
                    components.append(f"Conversion discount: {d*100:.0f}%")
                    # Discount → effective extra dilution: d/(1-d)
                    effective_cost = d / (1 - d) if d < 1 else d
                    breakdown.headline_cost = f"{d*100:.0f}% discount"

            if caps:
                cap_val = caps[0].value if isinstance(caps[0].value, (int, float)) else 0
                components.append(f"Valuation cap: ${cap_val/1e6:.1f}M")
                if not breakdown.headline_cost:
                    breakdown.headline_cost = f"${cap_val/1e6:.1f}M cap"
                else:
                    breakdown.headline_cost += f", ${cap_val/1e6:.1f}M cap"

                # Compute implied discount from cap vs pre-money if available
                pre_money_params = params.get_all("pre_money_valuation")
                if pre_money_params and cap_val > 0:
                    pre = pre_money_params[0].value
                    pre = pre if isinstance(pre, (int, float)) else 0
                    if pre > cap_val:
                        implied = 1 - (cap_val / pre)
                        cap_cost = implied / (1 - implied) if implied < 1 else implied
                        if cap_cost > effective_cost:
                            effective_cost = cap_cost
                            components.append(
                                f"Implied discount from cap vs ${pre/1e6:.0f}M pre: "
                                f"{implied*100:.0f}%"
                            )

            # Note interest adds to total cost
            note_rates = params.get_all("interest_rate")
            for nr in note_rates:
                r = nr.value if isinstance(nr.value, (int, float)) else 0
                if r > 0:
                    effective_cost += r
                    components.append(f"Note interest: {r*100:.1f}%")

            if not effective_cost and not breakdown.headline_cost:
                breakdown.headline_cost = "Convertible (terms TBD)"

        else:
            # Equity — derive base cost from actual dilution
            breakdown.instrument_type = "equity"
            base_cost = self._compute_equity_base_dilution(params)
            if base_cost > 0:
                components.append(f"Base dilution: {base_cost*100:.1f}%")
            else:
                logger.warning(
                    "Cannot determine equity base dilution — "
                    "no valuation or ownership data available"
                )

            liq_prefs = params.get_all("liquidation_preference")
            for lp in liq_prefs:
                mult = lp.value if isinstance(lp.value, (int, float)) else 1.0
                if mult > 1.0:
                    pref_cost = (mult - 1.0) * base_cost
                    base_cost += pref_cost
                    components.append(
                        f"{mult}x preference: +{pref_cost*100:.1f}% effective cost"
                    )

            part_params = params.get_all("participation_rights")
            for pp in part_params:
                participating = False
                cap = None
                if isinstance(pp.value, bool) and pp.value:
                    participating = True
                elif isinstance(pp.value, dict):
                    participating = pp.value.get("participating", False)
                    cap = pp.value.get("cap")

                if participating:
                    if cap:
                        cap_f = float(cap)
                        part_cost = base_cost * min(
                            CAPPED_PARTICIPATION_MAX,
                            (cap_f - 1.0) * CAPPED_PARTICIPATION_SCALE,
                        )
                        base_cost += part_cost
                        components.append(
                            f"Capped participating ({cap_f}x): "
                            f"+{part_cost*100:.1f}% effective cost"
                        )
                    else:
                        part_cost = base_cost * UNCAPPED_PARTICIPATION_FRACTION
                        base_cost += part_cost
                        components.append(
                            f"Uncapped participation: "
                            f"+{part_cost*100:.1f}% effective cost"
                        )

            ad_params = params.get_all("anti_dilution_method")
            for ad in ad_params:
                if ad.value == "full_ratchet":
                    ratchet_cost = base_cost * FULL_RATCHET_COST_FRACTION
                    base_cost += ratchet_cost
                    components.append(
                        f"Full ratchet anti-dilution: "
                        f"+{ratchet_cost*100:.1f}% effective cost"
                    )
                elif ad.value == "narrow_weighted_average":
                    nwa_cost = base_cost * NARROW_WA_COST_FRACTION
                    base_cost += nwa_cost
                    components.append(
                        f"Narrow weighted average: "
                        f"+{nwa_cost*100:.1f}% effective cost"
                    )

            div_params = params.get_all("dividend_rate")
            for dp in div_params:
                rate = dp.value if isinstance(dp.value, (int, float)) else 0
                if rate > 0:
                    base_cost += rate
                    components.append(f"Cumulative dividends: +{rate*100:.1f}%")

            breakdown.dilution_pct = base_cost
            effective_cost = base_cost
            if base_cost > 0:
                breakdown.headline_cost = f"{base_cost*100:.1f}% effective equity cost"
            else:
                breakdown.headline_cost = "Equity (dilution not yet determined)"

        breakdown.effective_annual_cost = effective_cost
        breakdown.runway_months = self._compute_runway_months(params)
        breakdown.real_cost_components = components
        breakdown.description = (
            f"{name} ({breakdown.instrument_type}): "
            f"Headline: {breakdown.headline_cost}. "
            f"Effective: {effective_cost*100:.1f}% annual."
        )

        return breakdown

    def _estimate_effective_cost(self, params: ResolvedParameterSet) -> float:
        """Quick estimate of effective cost of capital."""
        breakdown = self._compute_cost_breakdown("temp", params)
        return breakdown.effective_annual_cost

    def _compute_equity_base_dilution(self, params: ResolvedParameterSet) -> float:
        """Compute base equity dilution from valuation and investment data."""
        pre_money = params.get_all("pre_money_valuation")
        post_money = params.get_all("post_money_valuation")
        investment = params.get_all("investment_amount")

        inv_val = 0.0
        for p in investment:
            if isinstance(p.value, (int, float)):
                inv_val += p.value

        if pre_money and inv_val > 0:
            pre = pre_money[0].value
            pre = pre if isinstance(pre, (int, float)) else 0
            if pre > 0:
                return inv_val / (pre + inv_val)

        if post_money and inv_val > 0:
            post = post_money[0].value
            post = post if isinstance(post, (int, float)) else 0
            if post > 0:
                return inv_val / post

        # Fall back to stakeholder positions if available
        try:
            smap = StakeholderInteractionMap()
            smap.build(params)
            total_investor = sum(
                pos.ownership_pct
                for name, pos in smap.positions.items()
                if name not in ("founders", "common", "option_pool")
            )
            if total_investor > 0:
                return total_investor
        except Exception:
            pass

        return 0.0

    def _compute_pwerm_return(
        self,
        waterfall_by_exit: Dict[float, Dict[str, float]],
        exits: List[float],
    ) -> float:
        """Compute probability-weighted expected return for founders.

        Uses inverse-rank weighting: lower exits get higher probability,
        reflecting the empirical distribution of startup outcomes.
        """
        if not exits or not waterfall_by_exit:
            return 0.0

        n = len(exits)
        rank_sum = n * (n + 1) / 2  # sum of 1..n

        weighted_return = 0.0
        for i, exit_val in enumerate(exits):
            waterfall = waterfall_by_exit.get(exit_val, {})
            founder_proceeds = (
                waterfall.get("founders", 0) + waterfall.get("common", 0)
            )
            weight = (n - i) / rank_sum
            weighted_return += founder_proceeds * weight

        return weighted_return

    def _compute_runway_months(self, params: ResolvedParameterSet) -> float:
        """Estimate runway extension from the instrument's cash flows.

        Returns months of runway the instrument provides.  Requires
        investment_amount and monthly_burn_rate params to be meaningful;
        returns 0 when burn rate is unknown.
        """
        investment = sum(
            p.value for p in params.get_all("investment_amount")
            if isinstance(p.value, (int, float))
        )
        if investment <= 0:
            return 0.0

        burn_params = params.get_all("monthly_burn_rate")
        monthly_burn = 0.0
        for bp in burn_params:
            if isinstance(bp.value, (int, float)) and bp.value > 0:
                monthly_burn = bp.value
                break

        if monthly_burn <= 0:
            return 0.0

        # Add service costs (interest + dividends) as additional monthly outflow
        annual_interest = sum(
            r.value for r in params.get_all("interest_rate")
            if isinstance(r.value, (int, float))
        ) * investment
        annual_dividends = sum(
            d.value for d in params.get_all("dividend_rate")
            if isinstance(d.value, (int, float))
        ) * investment
        monthly_service = (annual_interest + annual_dividends) / 12

        total_monthly_outflow = monthly_burn + monthly_service
        return investment / total_monthly_outflow if total_monthly_outflow > 0 else 0.0

    # ------------------------------------------------------------------
    # Alignment and divergence
    # ------------------------------------------------------------------

    def _map_stakeholder_alignment(
        self, options: List[DecisionOption]
    ) -> Dict[str, Dict[str, str]]:
        """Map each stakeholder's preference across all options."""
        alignment: Dict[str, Dict[str, str]] = {}

        all_stakeholders: set = set()
        for opt in options:
            all_stakeholders.update(opt.stakeholder_preference.keys())

        for stakeholder in all_stakeholders:
            alignment[stakeholder] = {}
            for opt in options:
                alignment[stakeholder][opt.name] = (
                    opt.stakeholder_preference.get(stakeholder, "neutral")
                )

        return alignment

    def _find_divergence_points(
        self, options: List[DecisionOption], exits: List[float]
    ) -> List[str]:
        """Find exit values where the best option changes."""
        if len(options) < 2:
            return []

        divergence: List[str] = []

        for exit_val in exits:
            # Who benefits most from each option at this exit?
            best_for_founders: Dict[str, float] = {}
            for opt in options:
                waterfall = opt.waterfall_by_exit.get(exit_val, {})
                founder_proceeds = (
                    waterfall.get("founders", 0) + waterfall.get("common", 0)
                )
                best_for_founders[opt.name] = founder_proceeds

            if best_for_founders:
                best = max(best_for_founders, key=best_for_founders.get)
                worst = min(best_for_founders, key=best_for_founders.get)
                if best != worst:
                    diff = best_for_founders[best] - best_for_founders[worst]
                    if diff > DIVERGENCE_MATERIALITY:
                        divergence.append(
                            f"At ${exit_val/1e6:.0f}M: {best} is ${diff/1e6:.1f}M "
                            f"better for founders than {worst}"
                        )

        return divergence

    # ------------------------------------------------------------------
    # Summary generation
    # ------------------------------------------------------------------

    def _generate_recommendation(
        self, decision: Decision, exits: List[float]
    ) -> str:
        """Generate a recommendation based on the analysis."""
        if not decision.viable_options:
            if decision.blocked_options:
                reasons = [o.blocked_reason for o in decision.blocked_options]
                return f"All options blocked. Reasons: {'; '.join(reasons)}"
            return "No options to evaluate."

        if len(decision.viable_options) == 1:
            opt = decision.viable_options[0]
            return (
                f"Only viable option: {opt.name}. "
                f"Effective cost: {opt.effective_cost_of_capital*100:.1f}%. "
                f"Common breakeven: ${opt.breakeven_exit/1e6:.1f}M."
            )

        # Rank by effective cost and founder outcome at median exit
        median_exit = exits[len(exits) // 2] if exits else 50e6
        ranked = sorted(
            decision.viable_options,
            key=lambda o: (
                o.waterfall_by_exit.get(median_exit, {}).get("founders", 0)
                + o.waterfall_by_exit.get(median_exit, {}).get("common", 0)
            ),
            reverse=True,
        )

        best = ranked[0]
        return (
            f"Best for founders at ${median_exit/1e6:.0f}M exit: {best.name}. "
            f"Effective cost: {best.effective_cost_of_capital*100:.1f}%. "
            f"Common breakeven: ${best.breakeven_exit/1e6:.1f}M."
        )

    def _generate_decision_summary(self, decision: Decision) -> str:
        """Generate full decision summary."""
        parts = [decision.question]

        parts.append(
            f"\n{len(decision.viable_options)} viable, "
            f"{len(decision.blocked_options)} blocked."
        )

        for opt in decision.viable_options:
            parts.append(
                f"\n{opt.name}:"
                f"\n  Cost of capital: {opt.effective_cost_of_capital*100:.1f}%"
                f"\n  Common breakeven: ${opt.breakeven_exit/1e6:.1f}M"
                f"\n  New constraints: {len(opt.new_constraints)}"
            )
            # Show who prefers/opposes
            prefers = [s for s, p in opt.stakeholder_preference.items() if p == "prefers"]
            opposes = [s for s, p in opt.stakeholder_preference.items() if p == "opposes"]
            if prefers:
                parts.append(f"  Supported by: {', '.join(prefers)}")
            if opposes:
                parts.append(f"  Opposed by: {', '.join(opposes)}")

        for opt in decision.blocked_options:
            parts.append(f"\n{opt.name}: BLOCKED — {opt.blocked_reason}")

        if decision.divergence_points:
            parts.append("\nDivergence points:")
            for dp in decision.divergence_points[:5]:
                parts.append(f"  {dp}")

        if decision.recommendation:
            parts.append(f"\nRecommendation: {decision.recommendation}")

        return "\n".join(parts)

    def _generate_negotiation_summary(self, analysis: NegotiationAnalysis) -> str:
        """Generate negotiation analysis summary."""
        parts = []

        if analysis.their_likely_priorities:
            parts.append("Their priorities:")
            for p in analysis.their_likely_priorities:
                parts.append(f"  {p}")

        if analysis.counter_proposal:
            parts.append(f"\nCounter-proposal:\n{analysis.counter_proposal.description}")

        if analysis.multi_stakeholder_dynamics:
            parts.append("\nMulti-stakeholder dynamics:")
            for d in analysis.multi_stakeholder_dynamics:
                parts.append(f"  {d}")

        return "\n".join(parts)

    def _generate_coc_summary(self, analysis: CostOfCapitalAnalysis) -> str:
        """Generate cost of capital comparison summary."""
        parts = []
        for opt in analysis.options:
            parts.append(opt.description)

        if analysis.recommendation:
            parts.append(f"\n{analysis.recommendation}")

        return "\n".join(parts)

    def _summarize_position(self, params: ResolvedParameterSet, label: str) -> str:
        """Summarize a position for display."""
        parts = [f"{label} position:"]

        liq_prefs = params.get_all("liquidation_preference")
        for lp in liq_prefs:
            parts.append(f"  {lp.applies_to}: {lp.value}x preference")

        part_params = params.get_all("participation_rights")
        for pp in part_params:
            status = "participating" if pp.value else "non-participating"
            parts.append(f"  {pp.applies_to}: {status}")

        ad_params = params.get_all("anti_dilution_method")
        for ad in ad_params:
            parts.append(f"  {ad.applies_to}: {ad.value} anti-dilution")

        return "\n".join(parts)
