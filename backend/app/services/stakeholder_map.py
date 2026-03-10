"""
Stakeholder Interaction Map (Layer 7)

Every instrument creates a stakeholder with specific rights, preferences, and
economic interests that change at different exit values. This module builds
the complete map of stakeholder positions, finds where interests align and
diverge, and identifies coalitions that can force or block outcomes.

Three outputs:
  1. StakeholderPosition — each party's complete position in the structure
  2. AlignmentMatrix — at every exit value, who wants to sell/hold/block
  3. Coalition analysis — which groups can force outcomes and at what thresholds

All derived from resolved clause parameters with full attribution.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from app.services.clause_parameter_registry import (
    ClauseParameter,
    ResolvedParameterSet,
    VANILLA_DEFAULTS,
)
from app.services.cascade_engine import (
    Breakpoint,
    CascadeGraph,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class StakeholderPosition:
    """A stakeholder's complete position in the capital structure."""
    name: str
    instruments: List[str] = field(default_factory=list)
    # what they hold: "series_a_equity", "convertible_note", etc.
    total_invested: float = 0.0
    ownership_pct: float = 0.0
    shares: float = 0.0

    # Economic rights
    liquidation_preference_total: float = 0.0
    # their total preference claim (multiple * investment)
    liquidation_multiple: float = 1.0
    participation_rights: bool = False
    participation_cap: Optional[float] = None
    cumulative_dividends: bool = False
    dividend_rate: float = 0.0
    accrued_dividends: float = 0.0

    # Protection
    anti_dilution_protection: str = "none"
    # "full_ratchet", "broad_weighted_average", "narrow_weighted_average", "none"

    # Governance
    governance_rights: List[str] = field(default_factory=list)
    # "board_seat", "observer", "protective_provisions", "veto", "information_rights"
    board_seats: int = 0
    has_protective_provisions: bool = False
    has_blocking_rights: bool = False

    # Transfer & structural
    transfer_restrictions: List[str] = field(default_factory=list)
    # "lockup", "rofr", "drag_along", "tag_along", "co_sale"
    can_be_dragged: bool = False
    can_drag: bool = False
    has_tag_along: bool = False

    # Debt-specific
    is_creditor: bool = False
    debt_principal: float = 0.0
    interest_rate: float = 0.0
    has_personal_guarantee: bool = False
    guarantee_amount: float = 0.0

    # Computed positions
    breakeven_exit: float = 0.0
    # minimum exit for them to get their money back
    optimal_exit_range: Tuple[float, float] = (0.0, 0.0)
    # where their return multiple is maximized relative to others

    # Attribution — which clauses define this position
    source_clauses: List[str] = field(default_factory=list)
    # list of "doc_type S.clause_id" references


@dataclass
class InflectionPoint:
    """An exit value where stakeholder economics or behavior changes."""
    exit_value: float
    description: str
    stakeholders_affected: List[str]
    before: str   # what happens below this value
    after: str    # what happens above this value
    clause_sources: List[str] = field(default_factory=list)


@dataclass
class ExitAnalysis:
    """Per-stakeholder economics at a single exit value."""
    exit_value: float
    proceeds: Dict[str, float] = field(default_factory=dict)
    # stakeholder → dollar proceeds
    return_multiple: Dict[str, float] = field(default_factory=dict)
    # stakeholder → proceeds / invested
    marginal_dollar: Dict[str, float] = field(default_factory=dict)
    # stakeholder → how much they get per additional $1M of exit value
    prefers_to_sell: Dict[str, bool] = field(default_factory=dict)
    # stakeholder → would they vote to sell at this price?


@dataclass
class AlignmentZone:
    """A range of exit values with consistent stakeholder alignment."""
    exit_range: Tuple[float, float]
    description: str
    aligned_stakeholders: List[str]
    # who wants the same thing in this range
    opposing_stakeholders: List[str]
    # who opposes
    conflict_type: str = ""
    # "sell_vs_hold", "block_risk", "drag_along_risk", "aligned"
    can_force_outcome: bool = False
    # can one side force their preferred outcome?
    forcing_mechanism: str = ""
    # "drag_along", "majority_vote", "creditor_acceleration"


@dataclass
class Coalition:
    """A group of stakeholders that can act together to force outcomes."""
    members: List[str]
    combined_voting_pct: float
    mechanism: str
    # "drag_along", "preferred_vote", "board_majority", "creditor_block"
    threshold_required: float
    # voting/ownership % needed to trigger mechanism
    can_trigger: bool
    # whether this coalition meets the threshold
    effective_above: float
    # exit value above which this coalition would exercise the mechanism
    effective_below: float
    # exit value below which this coalition is blocked
    description: str
    clause_sources: List[str] = field(default_factory=list)


@dataclass
class AlignmentMatrix:
    """Complete alignment analysis across all exit values."""
    positions: Dict[str, StakeholderPosition] = field(default_factory=dict)
    exit_analyses: List[ExitAnalysis] = field(default_factory=list)
    inflection_points: List[InflectionPoint] = field(default_factory=list)
    zones: List[AlignmentZone] = field(default_factory=list)
    summary: str = ""


# ---------------------------------------------------------------------------
# Governance / voting thresholds
# ---------------------------------------------------------------------------

# Default thresholds when not specified in documents
DEFAULT_DRAG_ALONG_THRESHOLD = 0.75     # 75% of preferred
DEFAULT_PREFERRED_VOTE_THRESHOLD = 0.50  # simple majority of preferred
DEFAULT_BOARD_SIZE = 3


# ---------------------------------------------------------------------------
# Stakeholder Interaction Map
# ---------------------------------------------------------------------------

class StakeholderInteractionMap:
    """
    Builds the complete map of stakeholder positions from resolved clause
    parameters, then analyzes alignment and coalition dynamics.
    """

    def __init__(self) -> None:
        self.positions: Dict[str, StakeholderPosition] = {}
        self.params: Optional[ResolvedParameterSet] = None
        self._total_preference_stack: float = 0.0
        self._total_shares: float = 0.0
        self._drag_along_threshold: float = DEFAULT_DRAG_ALONG_THRESHOLD
        self._preferred_vote_threshold: float = DEFAULT_PREFERRED_VOTE_THRESHOLD

    def build(self, params: ResolvedParameterSet) -> None:
        """Build positions for every stakeholder from resolved clause parameters."""
        self.params = params
        self.positions = {}

        # Step 1: Identify all stakeholders from parameters and instruments
        stakeholder_names = self._identify_stakeholders(params)

        # Step 2: Build position for each stakeholder
        for name in stakeholder_names:
            self.positions[name] = self._build_position(name, params)

        # Step 3: Extract governance thresholds from params
        self._extract_governance_thresholds(params)

        # Step 4: Compute derived fields (breakeven, optimal range, ownership)
        self._total_preference_stack = sum(
            p.liquidation_preference_total for p in self.positions.values()
        )
        self._total_shares = sum(
            p.shares for p in self.positions.values() if p.shares > 0
        )

        # Compute ownership_pct for every stakeholder from shares
        if self._total_shares > 0:
            for pos in self.positions.values():
                if pos.shares > 0:
                    pos.ownership_pct = pos.shares / self._total_shares
        else:
            # Fallback: estimate ownership from investment amounts
            total_invested = sum(
                p.total_invested for p in self.positions.values() if p.total_invested > 0
            )
            if total_invested > 0:
                for pos in self.positions.values():
                    if pos.total_invested > 0:
                        pos.ownership_pct = pos.total_invested / total_invested

        for pos in self.positions.values():
            pos.breakeven_exit = self._compute_breakeven(pos)
            pos.optimal_exit_range = self._compute_optimal_range(pos)

        logger.info(
            f"Built stakeholder map: {len(self.positions)} stakeholders, "
            f"preference stack: ${self._total_preference_stack:,.0f}"
        )

    def alignment_analysis(
        self,
        exit_range: Tuple[float, float] = (0, 500_000_000),
        num_points: int = 200,
    ) -> AlignmentMatrix:
        """
        At each exit value in the range, compute each stakeholder's:
          - Absolute return
          - Return multiple
          - Marginal $ per additional $1M of exit value
          - Whether they'd prefer to sell at this price

        Find inflection points where:
          - Preferences fully covered (remainder goes to common)
          - Participation caps trigger
          - Conversion beats preference for specific investors
          - Drag-along can be forced (threshold met)
          - A stakeholder's return goes to zero
          - Stakeholder A wants to sell but B wants to hold
        """
        if not self.positions:
            return AlignmentMatrix(summary="No stakeholders loaded.")

        matrix = AlignmentMatrix(positions=dict(self.positions))

        # Step 1: Compute economics at every exit point
        step = (exit_range[1] - exit_range[0]) / num_points
        exit_values = [exit_range[0] + step * i for i in range(num_points + 1)]
        # Always include the preference stack value
        exit_values.append(self._total_preference_stack)
        exit_values = sorted(set(exit_values))

        for exit_val in exit_values:
            if exit_val <= 0:
                continue
            analysis = self._analyze_at_exit(exit_val)
            matrix.exit_analyses.append(analysis)

        # Step 2: Find inflection points
        matrix.inflection_points = self._find_inflection_points(
            matrix.exit_analyses
        )

        # Step 3: Build alignment zones between inflection points
        matrix.zones = self._build_zones(matrix.exit_analyses, matrix.inflection_points)

        # Step 4: Summary
        matrix.summary = self._generate_alignment_summary(matrix)

        return matrix

    def coalition_analysis(self) -> List[Coalition]:
        """
        Which stakeholders can act together to force outcomes?

        Based on voting thresholds, consent requirements, drag-along thresholds.
        Computes effective floor/ceiling for each coalition.
        """
        if not self.positions:
            return []

        coalitions: List[Coalition] = []

        preferred = {
            n: p for n, p in self.positions.items()
            if not p.is_creditor and p.liquidation_multiple > 0 and n != "common"
        }
        all_investors = {
            n: p for n, p in self.positions.items()
            if n not in ("common", "founders", "option_pool")
        }

        # 1. Drag-along coalitions
        coalitions.extend(self._find_drag_along_coalitions(preferred))

        # 2. Preferred voting coalitions (protective provisions)
        coalitions.extend(self._find_preferred_vote_coalitions(preferred))

        # 3. Board coalitions
        coalitions.extend(self._find_board_coalitions())

        # 4. Creditor blocking coalitions
        coalitions.extend(self._find_creditor_coalitions())

        # 5. Founder + investor alignment coalitions
        coalitions.extend(self._find_alignment_coalitions(all_investors))

        return coalitions

    # ------------------------------------------------------------------
    # Build: stakeholder identification
    # ------------------------------------------------------------------

    def _identify_stakeholders(self, params: ResolvedParameterSet) -> set:
        """Identify all unique stakeholders from parameters and instruments."""
        names: set = set()

        # From parameter applies_to
        for param in params.parameters.values():
            target = param.applies_to
            if target and target != "all":
                names.add(target)

        # From instruments
        for inst in params.instruments:
            if inst.holder and inst.holder != "unknown":
                names.add(inst.holder)

        # Always include founders and common as stakeholders
        names.add("founders")
        names.add("common")

        return names

    # ------------------------------------------------------------------
    # Build: position construction
    # ------------------------------------------------------------------

    def _build_position(
        self, name: str, params: ResolvedParameterSet
    ) -> StakeholderPosition:
        """Build a complete position for a single stakeholder."""
        pos = StakeholderPosition(name=name)
        stakeholder_params = params.get_for_stakeholder(name)

        # Also check "all_preferred" and "all" params
        all_params = params.get_for_stakeholder("all")
        all_preferred_params = params.get_for_stakeholder("all_preferred")

        combined = stakeholder_params + all_params + all_preferred_params

        for param in combined:
            self._apply_param_to_position(pos, param)

        # From instruments
        for inst in params.instruments:
            holder = inst.holder.lower().replace(" ", "_") if inst.holder else ""
            if holder == name or name in holder or holder in name:
                pos.instruments.append(
                    f"{inst.instrument_type}:{inst.instrument_id}"
                )
                if inst.principal_or_value:
                    if inst.instrument_type == "debt":
                        # Only real debt (loans, credit facilities) is senior
                        pos.debt_principal += inst.principal_or_value
                        pos.is_creditor = True
                    elif inst.instrument_type in ("convertible", "safe"):
                        # SAFEs and convertible notes are equity-like — they convert
                        # at the next priced round. They are junior to real debt.
                        pos.total_invested += inst.principal_or_value
                        # Track the convertible nature for waterfall
                        pos.instruments.append(f"convertible_pending:{inst.instrument_id}")
                    else:
                        pos.total_invested += inst.principal_or_value

        # Compute preference total
        pos.liquidation_preference_total = (
            pos.liquidation_multiple * pos.total_invested
        )

        # Compute shares from instruments
        for inst in params.instruments:
            holder = inst.holder.lower().replace(" ", "_") if inst.holder else ""
            if holder == name or name in holder or holder in name:
                shares = inst.terms.get("shares", 0)
                if isinstance(shares, (int, float)) and shares > 0:
                    pos.shares += shares
                elif inst.principal_or_value > 0 and inst.instrument_type == "equity":
                    # Estimate shares from investment if no explicit share count
                    pos.shares += inst.principal_or_value

        # Accrued dividends — compute from actual effective date, not hardcoded
        if pos.cumulative_dividends and pos.dividend_rate > 0:
            years_accrued = self._compute_accrual_years(name, params)
            pos.accrued_dividends = pos.total_invested * pos.dividend_rate * years_accrued

        return pos

    def _apply_param_to_position(
        self, pos: StakeholderPosition, param: ClauseParameter
    ) -> None:
        """Apply a single clause parameter to a stakeholder position."""
        ref = f"{param.document_type} S.{param.source_clause_id}"
        pt = param.param_type

        if pt == "liquidation_preference":
            if isinstance(param.value, (int, float)):
                pos.liquidation_multiple = float(param.value)
            pos.source_clauses.append(ref)

        elif pt == "participation_rights":
            if isinstance(param.value, bool):
                pos.participation_rights = param.value
            elif isinstance(param.value, dict):
                pos.participation_rights = param.value.get("participating", False)
                if "cap" in param.value:
                    pos.participation_cap = float(param.value["cap"])
            else:
                pos.participation_rights = bool(param.value)
            pos.source_clauses.append(ref)

        elif pt == "participation_cap":
            if isinstance(param.value, (int, float)):
                pos.participation_cap = float(param.value)
            elif isinstance(param.value, dict) and "cap" in param.value:
                pos.participation_cap = float(param.value["cap"])

        elif pt == "anti_dilution_method":
            if isinstance(param.value, str):
                pos.anti_dilution_protection = param.value
            pos.source_clauses.append(ref)

        elif pt == "board_seats":
            if isinstance(param.value, (int, float)):
                pos.board_seats = int(param.value)
            elif isinstance(param.value, dict):
                pos.board_seats = param.value.get("seats", 1)
                if param.value.get("observer"):
                    pos.governance_rights.append("observer")
                if param.value.get("veto_rights"):
                    pos.governance_rights.append("veto")
                    pos.has_blocking_rights = True
            if pos.board_seats > 0:
                pos.governance_rights.append("board_seat")
            pos.source_clauses.append(ref)

        elif pt == "protective_provisions":
            pos.has_protective_provisions = True
            pos.has_blocking_rights = True
            pos.governance_rights.append("protective_provisions")
            pos.source_clauses.append(ref)

        elif pt == "drag_along":
            pos.can_drag = True
            pos.transfer_restrictions.append("drag_along")
            pos.source_clauses.append(ref)

        elif pt == "tag_along":
            pos.has_tag_along = True
            pos.transfer_restrictions.append("tag_along")
            pos.source_clauses.append(ref)

        elif pt == "rofr":
            pos.transfer_restrictions.append("rofr")

        elif pt == "co_sale":
            pos.transfer_restrictions.append("co_sale")

        elif pt in ("founder_lockup", "lockup_period"):
            pos.transfer_restrictions.append("lockup")

        elif pt == "information_rights":
            pos.governance_rights.append("information_rights")

        elif pt == "pro_rata_rights":
            pos.governance_rights.append("pro_rata")

        elif pt == "registration_rights":
            pos.governance_rights.append("registration_rights")

        elif pt == "cumulative_dividends":
            pos.cumulative_dividends = True
            pos.source_clauses.append(ref)

        elif pt == "dividend_rate":
            if isinstance(param.value, (int, float)):
                pos.dividend_rate = float(param.value)

        elif pt == "interest_rate":
            if isinstance(param.value, (int, float)):
                pos.interest_rate = float(param.value)
                pos.is_creditor = True

        elif pt == "personal_guarantee":
            pos.has_personal_guarantee = True
            if isinstance(param.value, dict):
                pos.guarantee_amount = param.value.get("amount", 0)
            pos.source_clauses.append(ref)

        elif pt == "redemption_rights":
            pos.governance_rights.append("redemption_rights")

    def _compute_accrual_years(self, name: str, params: ResolvedParameterSet) -> float:
        """Compute actual years of dividend accrual from document effective dates."""
        from datetime import datetime as _dt

        # Find the earliest effective date for this stakeholder's instruments
        earliest_date = None
        for inst in params.instruments:
            holder = inst.holder.lower().replace(" ", "_") if inst.holder else ""
            if holder == name or name in holder or holder in name:
                if inst.effective_date:
                    try:
                        dt = _dt.fromisoformat(str(inst.effective_date).replace("Z", "+00:00"))
                        if earliest_date is None or dt < earliest_date:
                            earliest_date = dt
                    except (ValueError, TypeError):
                        continue

        # Also check clause effective dates
        for param in params.parameters.values():
            if param.applies_to == name and param.effective_date:
                try:
                    dt = _dt.fromisoformat(str(param.effective_date).replace("Z", "+00:00"))
                    if earliest_date is None or dt < earliest_date:
                        earliest_date = dt
                except (ValueError, TypeError):
                    continue

        if earliest_date is not None:
            now = _dt.utcnow()
            if earliest_date.tzinfo:
                now = now.replace(tzinfo=earliest_date.tzinfo)
            years = max(0, (now - earliest_date).days / 365.25)
            return years

        # Fallback: 1 year if no date information available
        return 1.0

    # ------------------------------------------------------------------
    # Build: governance thresholds
    # ------------------------------------------------------------------

    def _extract_governance_thresholds(self, params: ResolvedParameterSet) -> None:
        """Extract drag-along and voting thresholds from params."""
        drag_params = params.get_all("drag_along")
        for dp in drag_params:
            if isinstance(dp.value, dict) and "threshold" in dp.value:
                self._drag_along_threshold = float(dp.value["threshold"])
            elif isinstance(dp.value, (int, float)):
                self._drag_along_threshold = float(dp.value)

    # ------------------------------------------------------------------
    # Compute: breakeven and optimal range
    # ------------------------------------------------------------------

    def _compute_breakeven(self, pos: StakeholderPosition) -> float:
        """
        Minimum exit value for this stakeholder to get their money back.

        For preferred: need enough to cover all senior preferences + theirs.
        For common/founders: need enough to cover entire preference stack.
        For creditors: debt repaid first, so breakeven = debt balance.
        """
        if pos.is_creditor and not pos.total_invested:
            return pos.debt_principal

        if pos.name in ("common", "founders", "option_pool"):
            # Common only gets paid after entire preference stack
            return self._total_preference_stack

        # Preferred: need to cover all preferences senior to them + theirs
        senior_prefs = 0.0
        own_pref = pos.liquidation_preference_total + pos.accrued_dividends
        found_self = False

        # Walk preferences in seniority order (later rounds = more senior)
        sorted_positions = sorted(
            self.positions.values(),
            key=lambda p: p.liquidation_multiple * p.total_invested,
            reverse=True,
        )

        for other in sorted_positions:
            if other.name == pos.name:
                found_self = True
                continue
            if other.is_creditor:
                senior_prefs += other.debt_principal
            elif other.name not in ("common", "founders", "option_pool"):
                if not found_self:
                    senior_prefs += (
                        other.liquidation_preference_total + other.accrued_dividends
                    )

        return senior_prefs + own_pref

    def _compute_optimal_range(
        self, pos: StakeholderPosition
    ) -> Tuple[float, float]:
        """
        Exit value range where this stakeholder's return multiple is
        maximized relative to other stakeholders.

        For participating preferred: between breakeven and participation cap.
        For non-participating: where conversion to common beats preference.
        For common: above the preference stack.
        """
        if pos.name in ("common", "founders", "option_pool"):
            # Common does best when exit is far above preference stack
            floor = self._total_preference_stack
            return (floor, floor * 10)

        if pos.participation_rights:
            # Participating preferred: gets both preference + pro-rata
            # Optimal until participation cap kicks in
            floor = pos.breakeven_exit
            if pos.participation_cap:
                # Capped: ceiling is where total proceeds hit cap × investment
                ceiling = pos.total_invested * pos.participation_cap
            else:
                # Uncapped participating — no natural ceiling, always benefits
                # from higher exit. Use float('inf') to indicate no ceiling.
                ceiling = float('inf')
            return (floor, ceiling)

        # Non-participating preferred: optimal near breakeven where they
        # take preference (get high multiple), before common starts
        # eroding their relative share
        floor = pos.breakeven_exit * 0.8
        # Above a certain point, converting to common gives better return
        # than taking preference — that's where their relative advantage erodes
        if pos.ownership_pct > 0:
            conversion_exit = pos.liquidation_preference_total / pos.ownership_pct
            ceiling = conversion_exit
        else:
            ceiling = pos.breakeven_exit * 3
        return (floor, ceiling)

    # ------------------------------------------------------------------
    # Analysis: per-exit economics
    # ------------------------------------------------------------------

    def _analyze_at_exit(self, exit_value: float) -> ExitAnalysis:
        """Compute per-stakeholder economics at a single exit value."""
        analysis = ExitAnalysis(exit_value=exit_value)

        # Run simplified waterfall
        proceeds = self._run_waterfall(exit_value)
        analysis.proceeds = proceeds

        # Return multiples
        for name, pos in self.positions.items():
            invested = pos.total_invested or pos.debt_principal
            if invested > 0:
                analysis.return_multiple[name] = proceeds.get(name, 0) / invested
            else:
                analysis.return_multiple[name] = 0.0

        # Marginal dollar — how much they get per additional $1M
        marginal_exit = exit_value + 1_000_000
        marginal_proceeds = self._run_waterfall(marginal_exit)
        for name in self.positions:
            analysis.marginal_dollar[name] = (
                marginal_proceeds.get(name, 0) - proceeds.get(name, 0)
            )

        # Would they sell at this price?
        for name, pos in self.positions.items():
            invested = pos.total_invested or pos.debt_principal
            ret = analysis.return_multiple.get(name, 0)
            marginal = analysis.marginal_dollar.get(name, 0)

            if pos.is_creditor:
                # Creditors want repayment; sell if fully covered
                analysis.prefers_to_sell[name] = proceeds.get(name, 0) >= pos.debt_principal
            elif invested <= 0:
                # Common/founders — sell if getting meaningful returns
                analysis.prefers_to_sell[name] = proceeds.get(name, 0) > 0
            else:
                # Investors — sell if return > 2x AND marginal benefit is declining
                # relative to other stakeholders. Below breakeven, nobody wants to sell.
                if ret < 1.0:
                    analysis.prefers_to_sell[name] = False
                elif ret >= 2.0 and marginal < 0.5:
                    # Good return and losing relative share — sell
                    analysis.prefers_to_sell[name] = True
                elif ret >= 3.0:
                    # Great return — likely willing to sell
                    analysis.prefers_to_sell[name] = True
                else:
                    analysis.prefers_to_sell[name] = False

        return analysis

    def _run_waterfall(self, exit_value: float) -> Dict[str, float]:
        """
        Simplified waterfall for alignment analysis.

        Order:
          1. Debt repayment (senior to equity)
          2. Liquidation preferences (LIFO — last in, first out)
          3. Participation (if applicable)
          4. Remainder to common (pro-rata all equity)

        For each preferred holder with non-participating preference:
          They choose max(preference, pro-rata as-converted).
        """
        remaining = exit_value
        proceeds: Dict[str, float] = {name: 0.0 for name in self.positions}

        # Phase 1: Senior debt repayment (real debt only, NOT SAFEs/convertibles)
        for name, pos in self.positions.items():
            if pos.is_creditor and pos.debt_principal > 0:
                # SAFEs and convertible notes are NOT senior debt — they convert
                is_safe_or_note = any(
                    "safe" in inst.lower() or "convertible" in inst.lower()
                    for inst in pos.instruments
                )
                if is_safe_or_note:
                    continue  # SAFEs/notes convert, they don't get debt seniority
                payment = min(remaining, pos.debt_principal)
                proceeds[name] += payment
                remaining -= payment
                if remaining <= 0:
                    return proceeds

        # Phase 2: SAFE/convertible note conversion
        # SAFEs and convertible notes convert to equity at this point
        converted_to_equity: list = []
        for name, pos in self.positions.items():
            if pos.is_creditor and pos.debt_principal > 0:
                is_safe_or_note = any(
                    "safe" in inst.lower() or "convertible" in inst.lower()
                    for inst in pos.instruments
                )
                if is_safe_or_note:
                    # Convert to equity: they participate pro-rata as equity
                    # Their ownership_pct will be used in the common distribution
                    pos.is_creditor = False  # Now equity for waterfall purposes
                    converted_to_equity.append(pos)

        # Phase 3: Liquidation preferences (LIFO — last in, first out)
        # Sort by round seniority (later rounds are senior, not bigger rounds)
        preferred = [
            (n, p) for n, p in self.positions.items()
            if p.liquidation_preference_total > 0
            and n not in ("common", "founders", "option_pool")
            and not p.is_creditor
        ]
        # Sort by seniority: use instrument names to infer round order
        # Series C > Series B > Series A > Seed (standard LIFO)
        preferred.sort(key=lambda x: self._infer_seniority(x[0], x[1]), reverse=True)

        for name, pos in preferred:
            pref_claim = pos.liquidation_preference_total + pos.accrued_dividends
            payment = min(remaining, pref_claim)
            proceeds[name] += payment
            remaining = max(0, remaining - payment)
            if remaining <= 0:
                return proceeds

        # Phase 4: Participation + common distribution
        if remaining > 0:
            participating = [
                (n, p) for n, p in preferred
                if p.participation_rights
            ]

            for name, pos in participating:
                if self._total_shares > 0 and pos.shares > 0:
                    share_pct = pos.shares / self._total_shares
                    participation = remaining * share_pct

                    # Apply cap
                    if pos.participation_cap:
                        max_total = pos.total_invested * pos.participation_cap
                        current = proceeds[name]
                        participation = min(participation, max_total - current)
                        participation = max(0, participation)

                    proceeds[name] += participation
                    remaining = max(0, remaining - participation)

            # Non-participating preferred: check if conversion is better
            for name, pos in preferred:
                if not pos.participation_rights and pos.ownership_pct > 0:
                    conversion_value = exit_value * pos.ownership_pct
                    if conversion_value > proceeds[name]:
                        # Convert — give back preference, take pro-rata
                        diff = conversion_value - proceeds[name]
                        proceeds[name] = conversion_value
                        remaining = max(0, remaining - diff)

            # Remainder to common/founders — pro-rata by ownership, not equal split
            common_positions = [
                (n, p) for n, p in self.positions.items()
                if n in ("common", "founders", "option_pool")
            ]
            if common_positions and remaining > 0:
                # Pro-rata by ownership percentage
                total_common_ownership = sum(
                    p.ownership_pct for _, p in common_positions
                )
                if total_common_ownership > 0:
                    for name, pos in common_positions:
                        share = remaining * (pos.ownership_pct / total_common_ownership)
                        proceeds[name] += share
                else:
                    # Fallback: by shares
                    total_common_shares = sum(
                        p.shares for _, p in common_positions if p.shares > 0
                    )
                    if total_common_shares > 0:
                        for name, pos in common_positions:
                            share = remaining * (pos.shares / total_common_shares)
                            proceeds[name] += share
                    else:
                        # Last resort: equal split (shouldn't happen with ownership fix)
                        per_common = remaining / len(common_positions)
                        for name, _ in common_positions:
                            proceeds[name] += per_common

        # Restore mutated is_creditor flags so future waterfall runs are clean
        for pos in converted_to_equity:
            pos.is_creditor = True

        return proceeds

    def _infer_seniority(self, name: str, pos: StakeholderPosition) -> int:
        """Infer round seniority from stakeholder name and instruments.

        Higher number = more senior (gets paid first in liquidation).
        Standard: Series C > Series B > Series A > Seed.
        """
        name_lower = name.lower()
        # Check instrument names for round info
        for inst in pos.instruments:
            inst_lower = inst.lower()
            if "series_d" in inst_lower or "series d" in inst_lower:
                return 40
            if "series_c" in inst_lower or "series c" in inst_lower:
                return 30
            if "series_b" in inst_lower or "series b" in inst_lower:
                return 20
            if "series_a" in inst_lower or "series a" in inst_lower:
                return 10
            if "seed" in inst_lower:
                return 5

        # Fall back to name
        if "series_d" in name_lower or "series d" in name_lower:
            return 40
        if "series_c" in name_lower or "series c" in name_lower:
            return 30
        if "series_b" in name_lower or "series b" in name_lower:
            return 20
        if "series_a" in name_lower or "series a" in name_lower:
            return 10
        if "seed" in name_lower:
            return 5

        # Check effective dates — later investment = more senior
        # Use instrument effective_date if available
        return 0  # Unknown seniority — treated as pari passu

    # ------------------------------------------------------------------
    # Analysis: inflection points
    # ------------------------------------------------------------------

    def _find_inflection_points(
        self, analyses: List[ExitAnalysis]
    ) -> List[InflectionPoint]:
        """Find exit values where stakeholder economics change behavior."""
        points: List[InflectionPoint] = []

        # 1. Preference stack fully paid
        if self._total_preference_stack > 0:
            points.append(InflectionPoint(
                exit_value=self._total_preference_stack,
                description="All liquidation preferences satisfied",
                stakeholders_affected=["common", "founders"],
                before="Common shareholders get nothing",
                after="Common shareholders begin receiving proceeds",
            ))

        # 2. Individual breakeven points
        for name, pos in self.positions.items():
            if pos.breakeven_exit > 0 and name not in ("common", "founders"):
                points.append(InflectionPoint(
                    exit_value=pos.breakeven_exit,
                    description=f"{name} breakeven",
                    stakeholders_affected=[name],
                    before=f"{name} below cost basis",
                    after=f"{name} recovers full investment",
                    clause_sources=pos.source_clauses[:3],
                ))

        # 3. Participation caps
        for name, pos in self.positions.items():
            if pos.participation_rights and pos.participation_cap:
                cap_exit = pos.total_invested * pos.participation_cap
                if cap_exit > 0:
                    points.append(InflectionPoint(
                        exit_value=cap_exit,
                        description=f"{name} participation cap reached ({pos.participation_cap}x)",
                        stakeholders_affected=[name, "common", "founders"],
                        before=f"{name} receives preference + pro-rata participation",
                        after=f"{name} capped, converts to common — more to other holders",
                        clause_sources=pos.source_clauses[:3],
                    ))

        # 4. Conversion beats preference (non-participating)
        for name, pos in self.positions.items():
            if (not pos.participation_rights
                    and pos.ownership_pct > 0
                    and pos.liquidation_preference_total > 0):
                # Conversion value = exit * ownership_pct
                # Preference value = liq_pref_total
                # They're equal when: exit * ownership = liq_pref
                conversion_point = pos.liquidation_preference_total / pos.ownership_pct
                if conversion_point > 0:
                    points.append(InflectionPoint(
                        exit_value=conversion_point,
                        description=(
                            f"{name} conversion beats preference "
                            f"(above ${conversion_point/1e6:.1f}M)"
                        ),
                        stakeholders_affected=[name],
                        before=f"{name} takes preference ({pos.liquidation_multiple}x)",
                        after=f"{name} converts to common ({pos.ownership_pct*100:.1f}% pro-rata)",
                        clause_sources=pos.source_clauses[:3],
                    ))

        # 5. Sell-vs-hold flips — where someone switches from hold to sell
        prev_analysis = None
        for analysis in analyses:
            if prev_analysis:
                for name in self.positions:
                    prev_sell = prev_analysis.prefers_to_sell.get(name, False)
                    curr_sell = analysis.prefers_to_sell.get(name, False)
                    if prev_sell != curr_sell:
                        points.append(InflectionPoint(
                            exit_value=analysis.exit_value,
                            description=f"{name} {'starts' if curr_sell else 'stops'} preferring to sell",
                            stakeholders_affected=[name],
                            before=f"{name} prefers to {'sell' if prev_sell else 'hold'}",
                            after=f"{name} prefers to {'sell' if curr_sell else 'hold'}",
                        ))
            prev_analysis = analysis

        # Deduplicate by exit value (keep the first of each)
        seen_values: set = set()
        unique_points: List[InflectionPoint] = []
        for pt in sorted(points, key=lambda p: p.exit_value):
            # Round to avoid float noise
            rounded = round(pt.exit_value, -3)  # nearest $1K
            key = (rounded, pt.description)
            if key not in seen_values:
                seen_values.add(key)
                unique_points.append(pt)

        return unique_points

    # ------------------------------------------------------------------
    # Analysis: alignment zones
    # ------------------------------------------------------------------

    def _build_zones(
        self,
        analyses: List[ExitAnalysis],
        inflection_points: List[InflectionPoint],
    ) -> List[AlignmentZone]:
        """Build alignment zones between inflection points."""
        if not inflection_points or not analyses:
            return []

        zones: List[AlignmentZone] = []

        # Create zone boundaries from inflection points
        boundaries = sorted(set(
            [0.0]
            + [ip.exit_value for ip in inflection_points]
            + [analyses[-1].exit_value if analyses else 500_000_000]
        ))

        for i in range(len(boundaries) - 1):
            low = boundaries[i]
            high = boundaries[i + 1]
            mid = (low + high) / 2

            # Find the analysis closest to the midpoint
            mid_analysis = min(
                analyses,
                key=lambda a: abs(a.exit_value - mid),
            )

            # Who wants to sell vs hold at this midpoint?
            sellers = [
                n for n, sell in mid_analysis.prefers_to_sell.items() if sell
            ]
            holders = [
                n for n, sell in mid_analysis.prefers_to_sell.items() if not sell
            ]

            # Determine conflict type
            if not sellers:
                conflict_type = "all_hold"
                desc = (
                    f"${low/1e6:.0f}M-${high/1e6:.0f}M: "
                    f"Nobody wants to sell. All stakeholders prefer to hold."
                )
            elif not holders:
                conflict_type = "aligned"
                desc = (
                    f"${low/1e6:.0f}M-${high/1e6:.0f}M: "
                    f"Full alignment — all stakeholders willing to sell."
                )
            else:
                # Check if sellers can force via drag-along
                seller_preferred_pct = sum(
                    self.positions[n].ownership_pct
                    for n in sellers
                    if n in self.positions and self.positions[n].can_drag
                )
                can_force = seller_preferred_pct >= self._drag_along_threshold

                if can_force:
                    conflict_type = "drag_along_risk"
                    desc = (
                        f"${low/1e6:.0f}M-${high/1e6:.0f}M: "
                        f"CONFLICT — {', '.join(sellers)} want to sell, "
                        f"{', '.join(holders)} want to hold. "
                        f"Sellers can force via drag-along "
                        f"({seller_preferred_pct*100:.0f}% >= "
                        f"{self._drag_along_threshold*100:.0f}% threshold)."
                    )
                else:
                    conflict_type = "sell_vs_hold"
                    desc = (
                        f"${low/1e6:.0f}M-${high/1e6:.0f}M: "
                        f"{', '.join(sellers)} prefer to sell, "
                        f"{', '.join(holders)} prefer to hold. "
                        f"No forcing mechanism available."
                    )

            zones.append(AlignmentZone(
                exit_range=(low, high),
                description=desc,
                aligned_stakeholders=sellers if len(sellers) > len(holders) else holders,
                opposing_stakeholders=holders if len(sellers) > len(holders) else sellers,
                conflict_type=conflict_type,
                can_force_outcome=(conflict_type == "drag_along_risk"),
                forcing_mechanism="drag_along" if conflict_type == "drag_along_risk" else "",
            ))

        return zones

    # ------------------------------------------------------------------
    # Coalition analysis
    # ------------------------------------------------------------------

    def _find_drag_along_coalitions(
        self, preferred: Dict[str, StakeholderPosition]
    ) -> List[Coalition]:
        """Find coalitions that can trigger drag-along."""
        coalitions: List[Coalition] = []
        names = list(preferred.keys())

        # Check all possible pairs and triples
        for i in range(len(names)):
            for j in range(i + 1, len(names)):
                members = [names[i], names[j]]
                combined = sum(
                    preferred[n].ownership_pct for n in members
                )
                can_trigger = combined >= self._drag_along_threshold

                # Find the exit floor — lowest value where all members
                # would want to sell
                floor = max(
                    preferred[n].breakeven_exit for n in members
                ) * 1.5  # 1.5x breakeven — need decent return to vote yes

                # Collect clause sources
                sources = []
                for n in members:
                    sources.extend(preferred[n].source_clauses[:2])

                coalitions.append(Coalition(
                    members=members,
                    combined_voting_pct=combined,
                    mechanism="drag_along",
                    threshold_required=self._drag_along_threshold,
                    can_trigger=can_trigger,
                    effective_above=floor,
                    effective_below=0,
                    description=(
                        f"{' + '.join(members)} = {combined*100:.1f}% of preferred. "
                        f"Drag-along requires {self._drag_along_threshold*100:.0f}%. "
                        f"{'CAN' if can_trigger else 'Cannot'} force sale."
                    ),
                    clause_sources=sources,
                ))

        # Check if founders are needed to reach threshold
        founders_pos = self.positions.get("founders")
        if founders_pos and founders_pos.ownership_pct > 0:
            for name, pos in preferred.items():
                combined = pos.ownership_pct + founders_pos.ownership_pct
                can_trigger = combined >= self._drag_along_threshold

                if can_trigger:
                    # Find the floor — both must want to sell
                    floor = max(
                        pos.breakeven_exit * 1.5,
                        founders_pos.breakeven_exit,
                    )

                    coalitions.append(Coalition(
                        members=[name, "founders"],
                        combined_voting_pct=combined,
                        mechanism="drag_along",
                        threshold_required=self._drag_along_threshold,
                        can_trigger=True,
                        effective_above=floor,
                        effective_below=0,
                        description=(
                            f"{name} ({pos.ownership_pct*100:.1f}%) + founders "
                            f"({founders_pos.ownership_pct*100:.1f}%) = "
                            f"{combined*100:.1f}%. Can force sale above "
                            f"~${floor/1e6:.0f}M."
                        ),
                    ))

        return coalitions

    def _find_preferred_vote_coalitions(
        self, preferred: Dict[str, StakeholderPosition]
    ) -> List[Coalition]:
        """Find coalitions that can pass preferred-class votes."""
        coalitions: List[Coalition] = []

        total_preferred_ownership = sum(p.ownership_pct for p in preferred.values())
        if total_preferred_ownership == 0:
            return coalitions

        names = list(preferred.keys())
        for i in range(len(names)):
            for j in range(i + 1, len(names)):
                members = [names[i], names[j]]
                combined_of_preferred = sum(
                    preferred[n].ownership_pct for n in members
                ) / total_preferred_ownership if total_preferred_ownership > 0 else 0

                can_trigger = combined_of_preferred >= self._preferred_vote_threshold

                if can_trigger:
                    coalitions.append(Coalition(
                        members=members,
                        combined_voting_pct=combined_of_preferred,
                        mechanism="preferred_vote",
                        threshold_required=self._preferred_vote_threshold,
                        can_trigger=True,
                        effective_above=0,
                        effective_below=float("inf"),
                        description=(
                            f"{' + '.join(members)} = "
                            f"{combined_of_preferred*100:.1f}% of preferred class. "
                            f"Can pass any preferred-class vote."
                        ),
                    ))

        return coalitions

    def _find_board_coalitions(self) -> List[Coalition]:
        """Find coalitions that control the board."""
        coalitions: List[Coalition] = []

        total_seats = sum(p.board_seats for p in self.positions.values())
        if total_seats == 0:
            total_seats = DEFAULT_BOARD_SIZE

        majority = (total_seats // 2) + 1

        # Who has board seats?
        board_holders = {
            n: p for n, p in self.positions.items()
            if p.board_seats > 0
        }

        if not board_holders:
            return coalitions

        names = list(board_holders.keys())
        for i in range(len(names)):
            for j in range(i + 1, len(names)):
                members = [names[i], names[j]]
                combined_seats = sum(board_holders[n].board_seats for n in members)
                can_trigger = combined_seats >= majority

                if can_trigger:
                    coalitions.append(Coalition(
                        members=members,
                        combined_voting_pct=combined_seats / total_seats,
                        mechanism="board_majority",
                        threshold_required=majority / total_seats,
                        can_trigger=True,
                        effective_above=0,
                        effective_below=float("inf"),
                        description=(
                            f"{' + '.join(members)} = {combined_seats}/{total_seats} "
                            f"board seats. Board majority."
                        ),
                    ))

        return coalitions

    def _find_creditor_coalitions(self) -> List[Coalition]:
        """Find creditor blocking coalitions."""
        coalitions: List[Coalition] = []

        creditors = {
            n: p for n, p in self.positions.items()
            if p.is_creditor
        }

        for name, pos in creditors.items():
            if pos.has_blocking_rights or pos.debt_principal > 0:
                # Creditors with consent rights can block M&A
                coalitions.append(Coalition(
                    members=[name],
                    combined_voting_pct=0,  # not voting-based
                    mechanism="creditor_block",
                    threshold_required=0,
                    can_trigger=True,
                    effective_above=0,
                    effective_below=pos.debt_principal,
                    description=(
                        f"{name} can block any M&A below ${pos.debt_principal/1e6:.1f}M "
                        f"(debt repayment). Consent required for change of control."
                    ),
                    clause_sources=pos.source_clauses[:3],
                ))

        return coalitions

    def _find_alignment_coalitions(
        self, investors: Dict[str, StakeholderPosition]
    ) -> List[Coalition]:
        """Find natural alignment coalitions between founders and investors."""
        coalitions: List[Coalition] = []

        founders_pos = self.positions.get("founders")
        if not founders_pos:
            return coalitions

        for name, pos in investors.items():
            # Find what they agree on
            # Both don't want a down round if both are equity holders
            if pos.anti_dilution_protection == "full_ratchet":
                # Investor has full ratchet — they're protected on downside
                # Founders are NOT protected — interests diverge on down round
                continue

            combined = pos.ownership_pct + founders_pos.ownership_pct
            if combined > 0.50:
                coalitions.append(Coalition(
                    members=[name, "founders"],
                    combined_voting_pct=combined,
                    mechanism="simple_majority",
                    threshold_required=0.50,
                    can_trigger=True,
                    effective_above=pos.breakeven_exit,
                    effective_below=float("inf"),
                    description=(
                        f"{name} + founders = {combined*100:.1f}% of total. "
                        f"Aligned on: no cheap sale, no unnecessary dilution. "
                        f"Can block any action requiring simple majority."
                    ),
                ))

        return coalitions

    # ------------------------------------------------------------------
    # Summary generation
    # ------------------------------------------------------------------

    def _generate_alignment_summary(self, matrix: AlignmentMatrix) -> str:
        """Generate human-readable alignment summary."""
        parts: List[str] = []

        parts.append(
            f"Stakeholder map: {len(matrix.positions)} parties, "
            f"preference stack: ${self._total_preference_stack/1e6:.1f}M"
        )

        # Key inflection points
        if matrix.inflection_points:
            parts.append(f"\n{len(matrix.inflection_points)} inflection points:")
            for ip in matrix.inflection_points[:10]:
                parts.append(
                    f"  ${ip.exit_value/1e6:.1f}M: {ip.description}"
                )
                if ip.clause_sources:
                    parts.append(f"    Source: {', '.join(ip.clause_sources[:2])}")

        # Zones
        if matrix.zones:
            parts.append(f"\n{len(matrix.zones)} alignment zones:")
            for zone in matrix.zones:
                parts.append(f"  {zone.description}")

        return "\n".join(parts)
