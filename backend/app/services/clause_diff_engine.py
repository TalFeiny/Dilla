"""
Clause Diff Engine (Layer 4)

The redlining layer. Compare two sets of terms and compute what every change
costs, for every stakeholder, at multiple exit values.

Works for:
  - Term sheet vs term sheet
  - Pre-redline vs post-redline
  - Current structure vs proposed restructuring
  - Pre-amendment vs post-amendment

Every delta has: source clause attribution, cascade effects, per-stakeholder
dollar impact at multiple exit values, cost of capital shift, breakpoint shift.
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
    CascadeGraph,
    CascadeResult,
    CascadeStep,
)

logger = logging.getLogger(__name__)

DEFAULT_REFERENCE_EXITS = [10e6, 25e6, 50e6, 100e6, 200e6, 500e6]


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class DeltaImpact:
    """Financial impact of a single clause change across exit scenarios."""
    waterfall_delta: Dict[float, Dict[str, float]] = field(default_factory=dict)
    # exit_value → stakeholder → change in proceeds
    ownership_delta: Dict[str, float] = field(default_factory=dict)
    # stakeholder → change in ownership %
    cost_of_capital_delta: Optional[float] = None
    # change in effective cost of this instrument
    breakpoint_shift: Optional[float] = None
    # how the common-breakeven exit value moves
    constraint_changes: List[str] = field(default_factory=list)
    # new constraints added or removed


@dataclass
class ClauseDelta:
    """A single change between two clause sets."""
    param_type: str
    applies_to: str
    old_value: Any                          # None if new clause
    new_value: Any                          # None if removed clause
    change_type: str                        # "added", "removed", "modified"
    old_source: Optional[ClauseParameter] = None
    new_source: Optional[ClauseParameter] = None
    cascade_effects: List[CascadeStep] = field(default_factory=list)
    impact: DeltaImpact = field(default_factory=DeltaImpact)


@dataclass
class StakeholderImpact:
    """Per-stakeholder summary across all deltas."""
    stakeholder: str
    proceeds_delta_by_exit: Dict[float, float] = field(default_factory=dict)
    ownership_delta: float = 0.0
    new_rights_gained: List[str] = field(default_factory=list)
    rights_lost: List[str] = field(default_factory=list)
    alignment_shift: str = "unchanged"     # "better", "worse", "unchanged"
    breakeven_exit_delta: float = 0.0       # how their breakeven moves


@dataclass
class DiffResult:
    """Full comparison between two clause sets."""
    deltas: List[ClauseDelta] = field(default_factory=list)
    net_impact: DeltaImpact = field(default_factory=DeltaImpact)
    stakeholder_impacts: Dict[str, StakeholderImpact] = field(default_factory=dict)
    cascade_summary: Optional[CascadeResult] = None
    cost_of_capital_comparison: Dict[str, Any] = field(default_factory=dict)
    alignment_matrix: Dict[str, str] = field(default_factory=dict)
    # "stakeholder_a:stakeholder_b" → "aligned" / "divergent at $Xm"
    summary: str = ""


@dataclass
class TermSheetComparison:
    """Comparison of N term sheets against each other and current structure."""
    current_vs: Dict[str, DiffResult] = field(default_factory=dict)
    # term_sheet_name → DiffResult vs current
    pairwise: Dict[str, DiffResult] = field(default_factory=dict)
    # "A:B" → DiffResult
    best_for: Dict[str, str] = field(default_factory=dict)
    # stakeholder → term_sheet_name (at reference exit)
    cost_of_capital: Dict[str, float] = field(default_factory=dict)
    # term_sheet_name → effective cost
    summary: str = ""


# ---------------------------------------------------------------------------
# Rights classification — which params are "rights"
# ---------------------------------------------------------------------------

RIGHTS_PARAMS = {
    "pro_rata_rights", "information_rights", "registration_rights",
    "board_seats", "board_composition", "protective_provisions",
    "preemptive_rights", "rofr", "co_sale", "tag_along", "drag_along",
    "redemption_rights", "anti_dilution_method", "participation_rights",
}

# Params that affect cost of capital
COST_OF_CAPITAL_PARAMS = {
    "liquidation_preference", "participation_rights", "participation_cap",
    "anti_dilution_method", "cumulative_dividends", "dividend_rate",
    "warrant_coverage", "conversion_discount", "valuation_cap",
    "interest_rate", "pik_rate", "pik_toggle",
}


# ---------------------------------------------------------------------------
# Clause Diff Engine
# ---------------------------------------------------------------------------

class ClauseDiffEngine:
    """Compare two parameter sets and compute financial impact of every change."""

    def diff(
        self,
        version_a: ResolvedParameterSet,
        version_b: ResolvedParameterSet,
        reference_exits: Optional[List[float]] = None,
    ) -> DiffResult:
        """
        Compare two complete parameter sets.

        For each parameter that differs:
          1. Identify the change with full clause attribution
          2. Run cascade on the delta
          3. Estimate per-stakeholder impact at each reference exit
          4. Compute breakpoint shifts
          5. Compute effective cost of capital under each set of terms
        """
        exits = reference_exits or DEFAULT_REFERENCE_EXITS
        result = DiffResult()
        self._current_params = version_a  # Store for helper methods

        all_keys = set(version_a.parameters.keys()) | set(version_b.parameters.keys())

        for key in sorted(all_keys):
            param_a = version_a.parameters.get(key)
            param_b = version_b.parameters.get(key)

            if param_a and param_b and param_a.value == param_b.value:
                continue  # No change

            delta = self._build_delta(key, param_a, param_b)
            if delta:
                # Run cascade for this individual change
                delta.cascade_effects = self._run_delta_cascade(
                    key, param_a, param_b, version_a
                )
                # Compute impact
                delta.impact = self._compute_delta_impact(
                    delta, version_a, version_b, exits
                )
                result.deltas.append(delta)

        # Aggregate net impact
        result.net_impact = self._aggregate_impacts(result.deltas, exits)

        # Build per-stakeholder view
        result.stakeholder_impacts = self._build_stakeholder_impacts(
            result.deltas, exits
        )

        # Run combined cascade
        if result.deltas:
            result.cascade_summary = self._run_combined_cascade(
                result.deltas, version_a, version_b
            )

        # Cost of capital comparison
        result.cost_of_capital_comparison = self._compare_cost_of_capital(
            version_a, version_b
        )

        # Alignment matrix
        result.alignment_matrix = self._build_alignment_matrix(
            result.stakeholder_impacts, exits
        )

        # Summary
        result.summary = self._generate_summary(result, exits)

        return result

    def compare_term_sheets(
        self,
        term_sheets: Dict[str, List[Dict[str, Any]]],
        existing_structure: ResolvedParameterSet,
        reference_exits: Optional[List[float]] = None,
    ) -> TermSheetComparison:
        """
        Compare N term sheets against each other and against current structure.

        term_sheets: name → list of extracted document dicts
        """
        exits = reference_exits or DEFAULT_REFERENCE_EXITS
        registry = ClauseParameterRegistry()
        comparison = TermSheetComparison()

        # Resolve each term sheet layered onto existing structure
        resolved: Dict[str, ResolvedParameterSet] = {}
        for name, docs in term_sheets.items():
            resolved[name] = registry.resolve_parameters(
                existing_structure.company_id,
                docs,
            )
            # Layer on top of existing — term sheet params override existing
            merged = self._merge_onto_existing(existing_structure, resolved[name])
            resolved[name] = merged

        # Current vs each
        for name, params in resolved.items():
            comparison.current_vs[name] = self.diff(
                existing_structure, params, exits
            )

        # Pairwise
        names = list(resolved.keys())
        for i in range(len(names)):
            for j in range(i + 1, len(names)):
                key = f"{names[i]}:{names[j]}"
                comparison.pairwise[key] = self.diff(
                    resolved[names[i]], resolved[names[j]], exits
                )

        # Best for each stakeholder at median exit
        if exits:
            median_exit = exits[len(exits) // 2]
            all_stakeholders: set = set()
            for diff_result in comparison.current_vs.values():
                all_stakeholders.update(diff_result.stakeholder_impacts.keys())

            for stakeholder in all_stakeholders:
                best_name = None
                best_gain = float("-inf")
                for name, diff_result in comparison.current_vs.items():
                    si = diff_result.stakeholder_impacts.get(stakeholder)
                    if si:
                        gain = si.proceeds_delta_by_exit.get(median_exit, 0)
                        if gain > best_gain:
                            best_gain = gain
                            best_name = name
                if best_name:
                    comparison.best_for[stakeholder] = best_name

        # Cost of capital
        for name, params in resolved.items():
            comparison.cost_of_capital[name] = self._estimate_effective_cost(params)

        comparison.summary = self._generate_comparison_summary(comparison, exits)
        return comparison

    def redline_impact(
        self,
        original: Dict[str, Any],
        redlined: Dict[str, Any],
        existing_structure: ResolvedParameterSet,
        reference_exits: Optional[List[float]] = None,
    ) -> DiffResult:
        """
        Two versions of the same document (pre-redline and post-redline).
        Extract clauses from both. Diff. Show the financial impact of every change.
        """
        registry = ClauseParameterRegistry()
        exits = reference_exits or DEFAULT_REFERENCE_EXITS

        params_original = registry.resolve_parameters(
            existing_structure.company_id, [original]
        )
        params_redlined = registry.resolve_parameters(
            existing_structure.company_id, [redlined]
        )

        # Merge each onto existing structure
        merged_original = self._merge_onto_existing(existing_structure, params_original)
        merged_redlined = self._merge_onto_existing(existing_structure, params_redlined)

        return self.diff(merged_original, merged_redlined, exits)

    # ------------------------------------------------------------------
    # Internal: delta building
    # ------------------------------------------------------------------

    def _build_delta(
        self,
        key: str,
        param_a: Optional[ClauseParameter],
        param_b: Optional[ClauseParameter],
    ) -> Optional[ClauseDelta]:
        """Build a ClauseDelta from two parameter versions."""
        parts = key.split(":", 1)
        param_type = parts[0]
        applies_to = parts[1] if len(parts) > 1 else "all"

        if param_a and not param_b:
            return ClauseDelta(
                param_type=param_type,
                applies_to=applies_to,
                old_value=param_a.value,
                new_value=None,
                change_type="removed",
                old_source=param_a,
            )
        elif param_b and not param_a:
            return ClauseDelta(
                param_type=param_type,
                applies_to=applies_to,
                old_value=None,
                new_value=param_b.value,
                change_type="added",
                new_source=param_b,
            )
        elif param_a and param_b and param_a.value != param_b.value:
            return ClauseDelta(
                param_type=param_type,
                applies_to=applies_to,
                old_value=param_a.value,
                new_value=param_b.value,
                change_type="modified",
                old_source=param_a,
                new_source=param_b,
            )
        return None

    def _run_delta_cascade(
        self,
        key: str,
        param_a: Optional[ClauseParameter],
        param_b: Optional[ClauseParameter],
        base_params: ResolvedParameterSet,
    ) -> List[CascadeStep]:
        """Run cascade for a single parameter change."""
        if not param_b:
            return []

        graph = CascadeGraph()
        graph.build_from_clauses(base_params)

        new_value = param_b.value if param_b else None
        if new_value is None:
            return []

        result = graph.simulate(key, new_value, base_params)
        return result.steps

    def _compute_delta_impact(
        self,
        delta: ClauseDelta,
        version_a: ResolvedParameterSet,
        version_b: ResolvedParameterSet,
        exits: List[float],
    ) -> DeltaImpact:
        """Compute financial impact of a single delta."""
        impact = DeltaImpact()

        # Ownership delta — estimate from anti-dilution, conversion, etc.
        if delta.param_type in ("anti_dilution_method", "conversion_terms",
                                 "conversion_discount", "valuation_cap",
                                 "warrant_coverage"):
            impact.ownership_delta = self._estimate_ownership_shift(delta)

        # Waterfall delta — estimate proceeds change per exit
        if delta.param_type in ("liquidation_preference", "participation_rights",
                                 "participation_cap", "anti_dilution_method",
                                 "cumulative_dividends", "dividend_rate"):
            for exit_val in exits:
                impact.waterfall_delta[exit_val] = self._estimate_waterfall_shift(
                    delta, exit_val
                )

        # Cost of capital
        if delta.param_type in COST_OF_CAPITAL_PARAMS:
            impact.cost_of_capital_delta = self._estimate_coc_shift(delta)

        # Constraint changes
        if delta.change_type == "added" and delta.param_type in RIGHTS_PARAMS:
            ref = delta.new_source.section_reference if delta.new_source else ""
            impact.constraint_changes.append(
                f"New: {delta.param_type} for {delta.applies_to} ({ref})"
            )
        elif delta.change_type == "removed" and delta.param_type in RIGHTS_PARAMS:
            ref = delta.old_source.section_reference if delta.old_source else ""
            impact.constraint_changes.append(
                f"Removed: {delta.param_type} for {delta.applies_to} ({ref})"
            )

        return impact

    def _estimate_ownership_shift(self, delta: ClauseDelta) -> Dict[str, float]:
        """Estimate ownership shift from a parameter change."""
        shifts: Dict[str, float] = {}

        if delta.param_type == "anti_dilution_method":
            # Full ratchet vs weighted average — directional estimate
            if delta.new_value == "full_ratchet" and delta.old_value != "full_ratchet":
                shifts[delta.applies_to] = 0.05  # ~5% more dilution risk
                shifts["founders"] = -0.05
            elif delta.old_value == "full_ratchet" and delta.new_value != "full_ratchet":
                shifts[delta.applies_to] = -0.03
                shifts["founders"] = 0.03

        if delta.param_type == "warrant_coverage":
            old_cov = delta.old_value if isinstance(delta.old_value, (int, float)) else 0
            new_cov = delta.new_value if isinstance(delta.new_value, (int, float)) else 0
            shifts[delta.applies_to] = new_cov - old_cov

        return shifts

    def _estimate_waterfall_shift(
        self, delta: ClauseDelta, exit_value: float
    ) -> Dict[str, float]:
        """Estimate waterfall proceeds shift at a given exit value."""
        shifts: Dict[str, float] = {}

        if delta.param_type == "liquidation_preference":
            old_mult = delta.old_value if isinstance(delta.old_value, (int, float)) else 1.0
            new_mult = delta.new_value if isinstance(delta.new_value, (int, float)) else 1.0
            # Get actual investment amount from instruments
            investment = self._get_investment_for_entity(
                delta.applies_to, getattr(self, '_current_params', None)
            )
            pref_change = (new_mult - old_mult) * investment
            shifts[delta.applies_to] = pref_change
            shifts["common"] = -pref_change

        if delta.param_type == "participation_rights":
            old_part = _is_participating(delta.old_value)
            new_part = _is_participating(delta.new_value)
            if new_part and not old_part:
                # Participating: investor gets preference + pro-rata share of remainder
                # Impact depends on their ownership and exit value above preference stack
                investment = self._get_investment_for_entity(
                    delta.applies_to, getattr(self, '_current_params', None)
                )
                ownership = self._get_ownership_for_entity(
                    delta.applies_to, getattr(self, '_current_params', None)
                )
                # Above preference, participating preferred gets ownership_pct of remainder
                pref_stack = self._estimate_total_preference_stack(
                    getattr(self, '_current_params', None)
                )
                remainder = max(0, exit_value - pref_stack)
                extra = remainder * ownership if ownership > 0 else exit_value * 0.05
                shifts[delta.applies_to] = extra
                shifts["common"] = -extra
            elif old_part and not new_part:
                investment = self._get_investment_for_entity(
                    delta.applies_to, getattr(self, '_current_params', None)
                )
                ownership = self._get_ownership_for_entity(
                    delta.applies_to, getattr(self, '_current_params', None)
                )
                pref_stack = self._estimate_total_preference_stack(
                    getattr(self, '_current_params', None)
                )
                remainder = max(0, exit_value - pref_stack)
                extra = remainder * ownership if ownership > 0 else exit_value * 0.05
                shifts[delta.applies_to] = -extra
                shifts["common"] = extra

        return shifts

    def _get_investment_for_entity(
        self, entity: str, params: Optional[ResolvedParameterSet]
    ) -> float:
        """Get actual investment amount for an entity from instruments."""
        if params is None:
            return 0.0
        total = 0.0
        for inst in params.instruments:
            holder = (inst.holder or "").lower().replace(" ", "_")
            if holder == entity or entity in holder or holder in entity:
                total += inst.principal_or_value
        return total if total > 0 else 0.0

    def _get_ownership_for_entity(
        self, entity: str, params: Optional[ResolvedParameterSet]
    ) -> float:
        """Get ownership percentage for an entity."""
        if params is None:
            return 0.0
        # Look for ownership in instruments or compute from shares
        total_value = sum(i.principal_or_value for i in params.instruments)
        entity_value = 0.0
        for inst in params.instruments:
            holder = (inst.holder or "").lower().replace(" ", "_")
            if holder == entity or entity in holder:
                entity_value += inst.principal_or_value
        return entity_value / total_value if total_value > 0 else 0.0

    def _estimate_total_preference_stack(
        self, params: Optional[ResolvedParameterSet]
    ) -> float:
        """Estimate total liquidation preference stack from params."""
        if params is None:
            return 0.0
        total = 0.0
        liq_prefs = params.get_all("liquidation_preference")
        for lp in liq_prefs:
            mult = lp.value if isinstance(lp.value, (int, float)) else 1.0
            investment = self._get_investment_for_entity(lp.applies_to, params)
            total += mult * investment
        return total

    def _estimate_coc_shift(self, delta: ClauseDelta) -> float:
        """Estimate change in effective cost of capital."""
        shift = 0.0

        if delta.param_type == "liquidation_preference":
            old_mult = delta.old_value if isinstance(delta.old_value, (int, float)) else 1.0
            new_mult = delta.new_value if isinstance(delta.new_value, (int, float)) else 1.0
            shift += (new_mult - old_mult) * 0.05  # ~5% per 1x multiple

        if delta.param_type == "participation_rights":
            if _is_participating(delta.new_value) and not _is_participating(delta.old_value):
                shift += 0.10  # Participating adds ~10% to effective cost
            elif _is_participating(delta.old_value) and not _is_participating(delta.new_value):
                shift -= 0.10

        if delta.param_type == "anti_dilution_method":
            if delta.new_value == "full_ratchet":
                shift += 0.15  # Full ratchet significantly increases effective cost
            elif delta.old_value == "full_ratchet":
                shift -= 0.15

        if delta.param_type in ("interest_rate", "dividend_rate", "pik_rate"):
            old_rate = delta.old_value if isinstance(delta.old_value, (int, float)) else 0
            new_rate = delta.new_value if isinstance(delta.new_value, (int, float)) else 0
            shift += new_rate - old_rate

        return shift

    # ------------------------------------------------------------------
    # Internal: aggregation
    # ------------------------------------------------------------------

    def _aggregate_impacts(
        self, deltas: List[ClauseDelta], exits: List[float]
    ) -> DeltaImpact:
        """Aggregate all individual delta impacts into net impact."""
        net = DeltaImpact()

        for delta in deltas:
            # Waterfall
            for exit_val in exits:
                if exit_val in delta.impact.waterfall_delta:
                    net.waterfall_delta.setdefault(exit_val, {})
                    for stakeholder, change in delta.impact.waterfall_delta[exit_val].items():
                        net.waterfall_delta[exit_val][stakeholder] = (
                            net.waterfall_delta[exit_val].get(stakeholder, 0) + change
                        )

            # Ownership
            for stakeholder, change in delta.impact.ownership_delta.items():
                net.ownership_delta[stakeholder] = (
                    net.ownership_delta.get(stakeholder, 0) + change
                )

            # Cost of capital
            if delta.impact.cost_of_capital_delta is not None:
                if net.cost_of_capital_delta is None:
                    net.cost_of_capital_delta = 0.0
                net.cost_of_capital_delta += delta.impact.cost_of_capital_delta

            # Constraints
            net.constraint_changes.extend(delta.impact.constraint_changes)

        return net

    def _build_stakeholder_impacts(
        self, deltas: List[ClauseDelta], exits: List[float]
    ) -> Dict[str, StakeholderImpact]:
        """Build per-stakeholder impact summaries."""
        impacts: Dict[str, StakeholderImpact] = {}

        for delta in deltas:
            # Proceeds delta
            for exit_val in exits:
                for stakeholder, change in delta.impact.waterfall_delta.get(exit_val, {}).items():
                    if stakeholder not in impacts:
                        impacts[stakeholder] = StakeholderImpact(stakeholder=stakeholder)
                    impacts[stakeholder].proceeds_delta_by_exit[exit_val] = (
                        impacts[stakeholder].proceeds_delta_by_exit.get(exit_val, 0) + change
                    )

            # Ownership
            for stakeholder, change in delta.impact.ownership_delta.items():
                if stakeholder not in impacts:
                    impacts[stakeholder] = StakeholderImpact(stakeholder=stakeholder)
                impacts[stakeholder].ownership_delta += change

            # Rights
            if delta.param_type in RIGHTS_PARAMS:
                target = delta.applies_to
                if target not in impacts:
                    impacts[target] = StakeholderImpact(stakeholder=target)

                if delta.change_type == "added":
                    impacts[target].new_rights_gained.append(delta.param_type)
                elif delta.change_type == "removed":
                    impacts[target].rights_lost.append(delta.param_type)
                elif delta.change_type == "modified":
                    impacts[target].new_rights_gained.append(
                        f"{delta.param_type} (modified)"
                    )

        # Determine alignment shift
        for stakeholder, si in impacts.items():
            total_gain = sum(si.proceeds_delta_by_exit.values())
            if total_gain > 0:
                si.alignment_shift = "better"
            elif total_gain < 0:
                si.alignment_shift = "worse"

        return impacts

    def _run_combined_cascade(
        self,
        deltas: List[ClauseDelta],
        version_a: ResolvedParameterSet,
        version_b: ResolvedParameterSet,
    ) -> Optional[CascadeResult]:
        """Run cascade with ALL changes combined, not just the first."""
        if not deltas:
            return None

        graph = CascadeGraph()
        graph.build_from_clauses(version_b)

        # Run cascade for EVERY delta and merge results
        combined = CascadeResult(trigger="combined", trigger_value=None, steps=[])
        seen_params: set = set()

        for delta in deltas:
            if delta.new_value is not None:
                key = f"{delta.param_type}:{delta.applies_to}"
                result = graph.simulate(key, delta.new_value, version_a)
                if result and result.steps:
                    for step in result.steps:
                        # Deduplicate: don't add the same param_affected twice
                        if step.param_affected not in seen_params:
                            combined.steps.append(step)
                            seen_params.add(step.param_affected)
                    # Merge terminal state dicts
                    combined.cap_table_delta.update(result.cap_table_delta)
                    combined.governance_changes.extend(result.governance_changes)
                    combined.exposure_changes.update(result.exposure_changes)
                    combined.cash_flow_delta.update(result.cash_flow_delta)

        return combined if combined.steps else None

    def _compare_cost_of_capital(
        self,
        version_a: ResolvedParameterSet,
        version_b: ResolvedParameterSet,
    ) -> Dict[str, Any]:
        """Compare effective cost of capital between two parameter sets."""
        cost_a = self._estimate_effective_cost(version_a)
        cost_b = self._estimate_effective_cost(version_b)

        return {
            "version_a": cost_a,
            "version_b": cost_b,
            "delta": cost_b - cost_a,
            "description": (
                f"Effective cost shifts from {cost_a*100:.1f}% to {cost_b*100:.1f}% "
                f"({'increase' if cost_b > cost_a else 'decrease'} of "
                f"{abs(cost_b - cost_a)*100:.1f}pp)"
            ),
        }

    def _estimate_effective_cost(self, params: ResolvedParameterSet) -> float:
        """Estimate effective cost of capital from resolved parameters.

        Builds up from the instrument type's base cost, adding the incremental
        cost of each protective term. Returns an annualized percentage.
        """
        # Determine instrument mix
        has_debt = bool(params.get_all("interest_rate"))
        has_convertible = bool(params.get_all("conversion_discount") or params.get_all("valuation_cap"))

        if has_debt:
            # Debt: base is the explicit interest rate
            rates = params.get_all("interest_rate")
            base_cost = max(
                (r.value for r in rates if isinstance(r.value, (int, float))),
                default=0.08,
            )
        elif has_convertible:
            # Convertible: base is the discount rate
            discounts = params.get_all("conversion_discount")
            base_cost = max(
                (d.value for d in discounts if isinstance(d.value, (int, float))),
                default=0.20,
            )
        else:
            # Pure equity: start from risk-free + equity risk premium
            # ~4% risk-free + ~6% equity premium + ~10% venture premium = ~20%
            base_cost = 0.20

        # Liquidation preference: each additional 1x adds to effective cost
        # The economic logic: a 2x pref means the investor needs 2x their money
        # back before common sees anything. This effectively doubles the hurdle.
        # The cost per 1x above standard is proportional to investment/exit ratio.
        liq_prefs = params.get_all("liquidation_preference")
        total_invested = sum(
            self._get_investment_for_entity(lp.applies_to, params)
            for lp in liq_prefs
        )
        for lp in liq_prefs:
            if isinstance(lp.value, (int, float)) and lp.value > 1.0:
                investment = self._get_investment_for_entity(lp.applies_to, params)
                if total_invested > 0:
                    weight = investment / total_invested
                else:
                    weight = 1.0 / max(len(liq_prefs), 1)
                # Extra preference beyond 1x creates an incremental cost
                # proportional to the preference gap and the investor's weight
                base_cost += (lp.value - 1.0) * 0.05 * weight

        # Participation: participating preferred adds to cost because the
        # investor gets preference AND pro-rata share (double-dip)
        part_params = params.get_all("participation_rights")
        for pp in part_params:
            if _is_participating(pp.value):
                # Capped participation is less costly than uncapped
                if isinstance(pp.value, dict) and pp.value.get("cap"):
                    cap = pp.value["cap"]
                    base_cost += 0.03 + (0.02 / max(cap, 1))  # Lower cap = higher cost
                else:
                    base_cost += 0.08  # Uncapped participation

        # Anti-dilution: full ratchet is much more costly than weighted average
        ad_params = params.get_all("anti_dilution_method")
        for ad in ad_params:
            if ad.value == "full_ratchet":
                base_cost += 0.12  # Full ratchet: extreme downside protection
            elif ad.value == "narrow_weighted_average":
                base_cost += 0.03  # Narrow WA: moderate protection
            # Broad WA is standard — no additional cost

        # Warrants: dilutive equity kicker adds to effective cost
        warrant_params = params.get_all("warrant_coverage")
        for wp in warrant_params:
            if isinstance(wp.value, (int, float)):
                base_cost += wp.value  # 1% coverage ≈ 1% added cost

        # Dividends: cumulative dividends are a real cash/accrual cost
        div_params = params.get_all("dividend_rate")
        for dp in div_params:
            if isinstance(dp.value, (int, float)):
                base_cost += dp.value

        # PIK: compounding interest that increases principal
        pik_params = params.get_all("pik_rate")
        for pk in pik_params:
            if isinstance(pk.value, (int, float)):
                base_cost += pk.value

        return base_cost

    def _build_alignment_matrix(
        self,
        stakeholder_impacts: Dict[str, StakeholderImpact],
        exits: List[float],
    ) -> Dict[str, str]:
        """Build alignment matrix: at what exit values do interests align/diverge?"""
        matrix: Dict[str, str] = {}
        stakeholders = list(stakeholder_impacts.keys())

        for i in range(len(stakeholders)):
            for j in range(i + 1, len(stakeholders)):
                a = stakeholders[i]
                b = stakeholders[j]
                key = f"{a}:{b}"

                si_a = stakeholder_impacts[a]
                si_b = stakeholder_impacts[b]

                # Check alignment at each exit
                aligned_exits = []
                divergent_exits = []

                for exit_val in exits:
                    gain_a = si_a.proceeds_delta_by_exit.get(exit_val, 0)
                    gain_b = si_b.proceeds_delta_by_exit.get(exit_val, 0)

                    # Aligned if both gain or both lose
                    if (gain_a >= 0 and gain_b >= 0) or (gain_a <= 0 and gain_b <= 0):
                        aligned_exits.append(exit_val)
                    else:
                        divergent_exits.append(exit_val)

                if not divergent_exits:
                    matrix[key] = "aligned"
                elif not aligned_exits:
                    matrix[key] = "divergent"
                else:
                    flip_point = divergent_exits[0]
                    matrix[key] = f"diverge at ${flip_point/1e6:.0f}M"

        return matrix

    def _merge_onto_existing(
        self,
        existing: ResolvedParameterSet,
        new_params: ResolvedParameterSet,
    ) -> ResolvedParameterSet:
        """Layer new parameters onto existing structure."""
        merged = ResolvedParameterSet(
            company_id=existing.company_id,
            parameters=dict(existing.parameters),
            conflicts=list(existing.conflicts),
            override_chain=list(existing.override_chain),
            gaps=list(existing.gaps),
            instruments=list(existing.instruments),
        )

        # New params override existing
        for key, param in new_params.parameters.items():
            merged.parameters[key] = param

        # Merge instruments
        existing_ids = {i.instrument_id for i in merged.instruments}
        for inst in new_params.instruments:
            if inst.instrument_id not in existing_ids:
                merged.instruments.append(inst)

        return merged

    def _generate_summary(self, result: DiffResult, exits: List[float]) -> str:
        """Generate human-readable summary of the diff."""
        if not result.deltas:
            return "No differences found between the two parameter sets."

        parts = []
        parts.append(f"{len(result.deltas)} clause change(s) detected.")

        # Material changes
        added = [d for d in result.deltas if d.change_type == "added"]
        removed = [d for d in result.deltas if d.change_type == "removed"]
        modified = [d for d in result.deltas if d.change_type == "modified"]

        if added:
            parts.append(f"Added: {', '.join(d.param_type for d in added)}")
        if removed:
            parts.append(f"Removed: {', '.join(d.param_type for d in removed)}")
        if modified:
            for m in modified:
                src = m.new_source or m.old_source
                ref = src.section_reference if src else ""
                parts.append(
                    f"{m.param_type} for {m.applies_to}: "
                    f"{m.old_value} → {m.new_value} ({ref})"
                )

        # Cost of capital
        coc = result.cost_of_capital_comparison
        if coc.get("delta"):
            parts.append(coc["description"])

        # Winners and losers
        for stakeholder, si in result.stakeholder_impacts.items():
            if si.alignment_shift == "better":
                parts.append(f"{stakeholder}: benefits from these changes")
            elif si.alignment_shift == "worse":
                parts.append(f"{stakeholder}: harmed by these changes")

        return "\n".join(parts)

    def _generate_comparison_summary(
        self, comparison: TermSheetComparison, exits: List[float]
    ) -> str:
        """Generate summary for term sheet comparison."""
        parts = [f"Compared {len(comparison.current_vs)} term sheets."]

        for name, diff_result in comparison.current_vs.items():
            parts.append(f"\n{name}: {len(diff_result.deltas)} changes vs current.")
            coc = comparison.cost_of_capital.get(name)
            if coc is not None:
                parts.append(f"  Effective cost of capital: {coc*100:.1f}%")

        if comparison.best_for:
            parts.append("\nBest option by stakeholder:")
            for stakeholder, name in comparison.best_for.items():
                parts.append(f"  {stakeholder}: {name}")

        return "\n".join(parts)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _is_participating(value: Any) -> bool:
    """Check if a participation value means participating preferred."""
    if isinstance(value, bool):
        return value
    if isinstance(value, dict):
        return value.get("participating", False)
    return False
