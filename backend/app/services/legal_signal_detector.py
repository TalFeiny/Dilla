"""
Legal Signal Detector (Layer 3)

New signal source for strategic_intelligence_service.py. Uses the same
StrategicSignal data structure. Fires alongside financial signals (runway,
burn, growth) to give the CFO brain legal awareness.

Detects:
  - Covenant proximity (how close to breach)
  - Conversion triggers approaching (SAFE/note maturity, qualified financing)
  - Clause conflicts (unresolved contradictions with financial impact)
  - Governance shifts (ownership changes near protective provision thresholds)
  - Exposure alerts (personal guarantees, cross-defaults, uncapped liability)
  - Cost of capital signals (warrants, dividends, ratchets, PIK)
  - Missing protections (standard clauses absent, benchmarked by stage)
  - Expiry / renewal / deadline alerts
  - Indemnity exposure windows
  - Earnout milestone tracking
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from app.services.clause_parameter_registry import (
    ClauseParameter,
    ResolvedParameterSet,
)
from app.services.cascade_engine import CascadeGraph
from app.services.strategic_intelligence_service import StrategicSignal

logger = logging.getLogger(__name__)


# Stage benchmarks for missing protection checks
STAGE_EXPECTED_PROTECTIONS = {
    "seed": [
        "anti_dilution_method", "pro_rata_rights", "information_rights",
    ],
    "series_a": [
        "anti_dilution_method", "pro_rata_rights", "information_rights",
        "board_seats", "drag_along", "tag_along", "rofr",
    ],
    "series_b": [
        "anti_dilution_method", "pro_rata_rights", "information_rights",
        "board_seats", "drag_along", "tag_along", "rofr",
        "registration_rights", "protective_provisions",
    ],
    "series_c": [
        "anti_dilution_method", "pro_rata_rights", "information_rights",
        "board_seats", "drag_along", "tag_along", "rofr",
        "registration_rights", "protective_provisions", "redemption_rights",
    ],
}


def detect_legal_signals(
    params: ResolvedParameterSet,
    financial_state: Any,
    cascade_graph: CascadeGraph,
    as_of: Optional[datetime] = None,
    group_structure: Optional[Any] = None,
) -> List[StrategicSignal]:
    """Detect all legal signals from resolved clause parameters.

    If group_structure is provided, also detects group-level signals:
      - Guarantee chain exposure across entities
      - Intercompany flow imbalance
      - TP compliance proximity
      - Thin capitalisation warnings
      - Ring-fenced cash traps
      - Dormant entity cleanup alerts
      - Multi-jurisdiction regulatory deadlines
    """
    as_of = as_of or datetime.utcnow()
    signals: List[StrategicSignal] = []

    signals.extend(_detect_covenant_proximity(params, financial_state, as_of))
    signals.extend(_detect_conversion_triggers(params, financial_state, as_of))
    signals.extend(_detect_clause_conflicts(params))
    signals.extend(_detect_governance_shifts(params, financial_state))
    signals.extend(_detect_exposure_alerts(params, cascade_graph))
    signals.extend(_detect_cost_of_capital_signals(params, financial_state))
    signals.extend(_detect_missing_protections(params, financial_state))
    signals.extend(_detect_expiry_deadlines(params, as_of))
    signals.extend(_detect_indemnity_signals(params, as_of))
    signals.extend(_detect_earnout_signals(params, financial_state, as_of))

    # Group-level signals
    if group_structure is not None:
        signals.extend(_detect_group_guarantee_chain(group_structure, params))
        signals.extend(_detect_group_flow_imbalance(group_structure))
        signals.extend(_detect_group_tp_compliance(group_structure))
        signals.extend(_detect_group_thin_cap(group_structure))
        signals.extend(_detect_group_ring_fence(group_structure))
        signals.extend(_detect_group_dormant_entities(group_structure))
        signals.extend(_detect_group_cross_default_contagion(group_structure, params, cascade_graph))

    return signals


# ---------------------------------------------------------------------------
# Signal detectors
# ---------------------------------------------------------------------------

def _detect_covenant_proximity(
    params: ResolvedParameterSet,
    state: Any,
    as_of: datetime,
) -> List[StrategicSignal]:
    """Compare current financial metrics against covenant thresholds."""
    signals: List[StrategicSignal] = []

    covenant_params = [
        p for p in params.parameters.values()
        if p.param_type.startswith("covenant_")
    ]

    for param in covenant_params:
        threshold_val = param.value
        if isinstance(threshold_val, dict):
            for metric, threshold in threshold_val.items():
                actual = _get_financial_metric(state, metric)
                if actual is not None and threshold is not None:
                    headroom = actual - threshold if metric == "dscr" else threshold - actual
                    months_to_breach = _estimate_months_to_breach(
                        state, metric, actual, threshold
                    )

                    if months_to_breach is not None and months_to_breach < 6:
                        severity = "high" if months_to_breach < 3 else "medium"
                        signals.append(StrategicSignal(
                            signal_type="threshold_cross",
                            metric=f"covenant_{metric}",
                            description=(
                                f"{metric.upper()} at {actual:.2f}x, covenant triggers "
                                f"at {threshold:.2f}x ({param.section_reference}). "
                                f"At current trajectory, breach in {months_to_breach:.0f} months."
                            ),
                            severity=severity,
                            current_value=actual,
                            threshold=threshold,
                            data={
                                "headroom": headroom,
                                "months_to_breach": months_to_breach,
                                "source_clause": param.source_clause_id,
                                "source_doc": param.source_document_id,
                                "applies_to": param.applies_to,
                            },
                        ))
                    elif headroom is not None and abs(headroom) < 0.3:
                        signals.append(StrategicSignal(
                            signal_type="threshold_cross",
                            metric=f"covenant_{metric}",
                            description=(
                                f"{metric.upper()} at {actual:.2f}x, covenant at "
                                f"{threshold:.2f}x. Headroom: {abs(headroom):.2f}x "
                                f"({param.section_reference})"
                            ),
                            severity="medium",
                            current_value=actual,
                            threshold=threshold,
                            data={
                                "headroom": headroom,
                                "source_clause": param.source_clause_id,
                            },
                        ))

    return signals


def _detect_conversion_triggers(
    params: ResolvedParameterSet,
    state: Any,
    as_of: datetime,
) -> List[StrategicSignal]:
    """SAFE/note maturity dates, qualified financing thresholds approaching."""
    signals: List[StrategicSignal] = []

    # Maturity dates
    maturity_params = params.get_all("maturity_date")
    for param in maturity_params:
        maturity = _parse_date(param.value)
        if maturity:
            days_to_maturity = (maturity - as_of).days
            if 0 < days_to_maturity <= 180:
                severity = "high" if days_to_maturity <= 90 else "medium"
                signals.append(StrategicSignal(
                    signal_type="milestone",
                    metric="maturity_date",
                    description=(
                        f"Convertible instrument ({param.applies_to}) matures in "
                        f"{days_to_maturity} days. Lender can demand repayment or "
                        f"force conversion ({param.section_reference})"
                    ),
                    severity=severity,
                    current_value=days_to_maturity,
                    data={
                        "maturity_date": str(maturity.date()),
                        "applies_to": param.applies_to,
                        "instrument": param.instrument,
                        "source_clause": param.source_clause_id,
                    },
                ))
            elif days_to_maturity <= 0:
                signals.append(StrategicSignal(
                    signal_type="threshold_cross",
                    metric="maturity_date",
                    description=(
                        f"PAST DUE: {param.applies_to} matured {abs(days_to_maturity)} "
                        f"days ago. Lender has repayment/conversion rights "
                        f"({param.section_reference})"
                    ),
                    severity="high",
                    current_value=days_to_maturity,
                    data={
                        "maturity_date": str(maturity.date()),
                        "applies_to": param.applies_to,
                        "overdue_days": abs(days_to_maturity),
                    },
                ))

    # Qualified financing thresholds
    qf_params = params.get_all("qualified_financing_threshold")
    for param in qf_params:
        if isinstance(param.value, (int, float)):
            signals.append(StrategicSignal(
                signal_type="milestone",
                metric="qualified_financing",
                description=(
                    f"Any equity raise above ${param.value:,.0f} triggers conversion "
                    f"of {param.applies_to} ({param.section_reference}). "
                    f"Factor this into round sizing."
                ),
                severity="medium",
                threshold=param.value,
                data={
                    "applies_to": param.applies_to,
                    "threshold": param.value,
                    "instrument": param.instrument,
                },
            ))

    return signals


def _detect_clause_conflicts(
    params: ResolvedParameterSet,
) -> List[StrategicSignal]:
    """Surface unresolved clause conflicts."""
    signals: List[StrategicSignal] = []

    for conflict in params.conflicts:
        signals.append(StrategicSignal(
            signal_type="anomaly",
            metric="clause_conflict",
            description=conflict.conflict_description,
            severity="high",
            data={
                "param_type": conflict.param_type,
                "clause_a_doc": conflict.clause_a.source_document_id,
                "clause_a_ref": conflict.clause_a.section_reference,
                "clause_a_value": conflict.clause_a.value,
                "clause_b_doc": conflict.clause_b.source_document_id,
                "clause_b_ref": conflict.clause_b.section_reference,
                "clause_b_value": conflict.clause_b.value,
                "impact_range": conflict.financial_impact_range,
            },
        ))

    return signals


def _detect_governance_shifts(
    params: ResolvedParameterSet,
    state: Any,
) -> List[StrategicSignal]:
    """Ownership changes approaching protective provision thresholds."""
    signals: List[StrategicSignal] = []

    # Check board composition
    board_params = params.get_all("board_seats") + params.get_all("board_composition")
    if board_params:
        investor_seats = 0
        founder_seats = 0
        for bp in board_params:
            val = bp.value if isinstance(bp.value, dict) else {"seats": bp.value}
            seats = val.get("seats", 0) if isinstance(val, dict) else (val if isinstance(val, int) else 0)
            if "founder" in bp.applies_to.lower() or "common" in bp.applies_to.lower():
                founder_seats += seats
            else:
                investor_seats += seats

        if investor_seats >= founder_seats and founder_seats > 0:
            signals.append(StrategicSignal(
                signal_type="trend_break",
                metric="board_composition",
                description=(
                    f"Board balance: {founder_seats} founder seats vs "
                    f"{investor_seats} investor seats. "
                    f"{'Deadlock risk.' if investor_seats == founder_seats else 'Investor control.'}"
                ),
                severity="high" if investor_seats > founder_seats else "medium",
                data={
                    "founder_seats": founder_seats,
                    "investor_seats": investor_seats,
                },
            ))

    # Check drag-along power
    drag_params = params.get_all("drag_along")
    if drag_params:
        # If multiple investor classes have drag-along, they could combine
        drag_holders = [p.applies_to for p in drag_params if p.value]
        if len(drag_holders) >= 2:
            signals.append(StrategicSignal(
                signal_type="trend_break",
                metric="drag_along_coalition",
                description=(
                    f"Multiple parties hold drag-along rights: "
                    f"{', '.join(drag_holders)}. "
                    f"If they align, they can force a sale."
                ),
                severity="medium",
                data={"drag_holders": drag_holders},
            ))

    return signals


def _detect_exposure_alerts(
    params: ResolvedParameterSet,
    cascade_graph: CascadeGraph,
) -> List[StrategicSignal]:
    """Personal guarantees, cross-defaults, uncapped liability."""
    signals: List[StrategicSignal] = []

    # Personal guarantees
    guarantee_params = params.get_all("personal_guarantee")
    total_guarantee_exposure = 0.0
    guarantee_count = 0

    for param in guarantee_params:
        guarantee_count += 1
        val = param.value if isinstance(param.value, dict) else {}
        amount = val.get("amount", 0)
        unlimited = val.get("unlimited", False)

        if unlimited:
            signals.append(StrategicSignal(
                signal_type="anomaly",
                metric="personal_guarantee",
                description=(
                    f"UNLIMITED personal guarantee by {param.applies_to} "
                    f"({param.section_reference}). Full personal asset exposure "
                    f"on company default."
                ),
                severity="high",
                data={
                    "guarantor": param.applies_to,
                    "unlimited": True,
                    "source_clause": param.source_clause_id,
                },
            ))
        elif isinstance(amount, (int, float)):
            total_guarantee_exposure += amount

    if guarantee_count > 1 and total_guarantee_exposure > 0:
        signals.append(StrategicSignal(
            signal_type="anomaly",
            metric="total_guarantee_exposure",
            description=(
                f"Total personal guarantee exposure: ${total_guarantee_exposure:,.0f} "
                f"across {guarantee_count} instruments. Cross-default could trigger "
                f"full exposure simultaneously."
            ),
            severity="high",
            current_value=total_guarantee_exposure,
            data={
                "total_exposure": total_guarantee_exposure,
                "instrument_count": guarantee_count,
            },
        ))

    # Cross-defaults
    cross_default_params = params.get_all("cross_default")
    if cross_default_params:
        linked = [p.applies_to for p in cross_default_params]
        signals.append(StrategicSignal(
            signal_type="anomaly",
            metric="cross_default",
            description=(
                f"Cross-default between: {', '.join(linked)}. "
                f"Single default cascades to all linked facilities."
            ),
            severity="high",
            data={"linked_facilities": linked},
        ))

    # Uncapped indemnities
    indemnity_params = params.get_all("indemnity_terms")
    for param in indemnity_params:
        val = param.value
        # Check if there's a corresponding cap
        cap_key = f"indemnity_cap:{param.applies_to}"
        cap = params.parameters.get(cap_key)
        if not cap:
            signals.append(StrategicSignal(
                signal_type="anomaly",
                metric="uncapped_indemnity",
                description=(
                    f"Indemnification for {param.applies_to} has no cap "
                    f"({param.section_reference}). Unlimited exposure."
                ),
                severity="medium",
                data={
                    "applies_to": param.applies_to,
                    "source_clause": param.source_clause_id,
                },
            ))

    return signals


def _detect_cost_of_capital_signals(
    params: ResolvedParameterSet,
    state: Any,
) -> List[StrategicSignal]:
    """Terms that materially affect effective cost of capital."""
    signals: List[StrategicSignal] = []

    # Cumulative dividends accruing
    dividend_params = params.get_all("cumulative_dividends")
    for param in dividend_params:
        if param.value:
            rate_param = params.get("dividend_rate", param.applies_to)
            rate = rate_param.value if rate_param and isinstance(
                rate_param.value, (int, float)
            ) else None

            rate_desc = f"at {rate*100:.0f}%" if rate is not None else "(rate not specified)"
            signals.append(StrategicSignal(
                signal_type="trend_break",
                metric="cumulative_dividends",
                description=(
                    f"Cumulative dividends on {param.applies_to} accruing "
                    f"{rate_desc}. Unpaid dividends add to preference stack "
                    f"before common sees anything. "
                    f"Effective cost of this equity is NOT the headline valuation "
                    f"({param.section_reference})"
                ),
                severity="medium",
                data={
                    "applies_to": param.applies_to,
                    "rate": rate,
                    "source_clause": param.source_clause_id,
                },
            ))

    # Warrant coverage on debt
    warrant_params = params.get_all("warrant_coverage")
    for param in warrant_params:
        if isinstance(param.value, (int, float)) and param.value > 0:
            signals.append(StrategicSignal(
                signal_type="trend_break",
                metric="warrant_coverage",
                description=(
                    f"Warrant coverage on {param.applies_to}: "
                    f"{param.value*100:.1f}% fully diluted. "
                    f"This is free equity to the lender — "
                    f"effective interest rate is higher than headline "
                    f"({param.section_reference})"
                ),
                severity="low",
                current_value=param.value,
                data={
                    "applies_to": param.applies_to,
                    "coverage_pct": param.value,
                },
            ))

    # PIK interest compounding
    pik_params = params.get_all("pik_toggle")
    for param in pik_params:
        if param.value:
            rate_param = params.get("pik_rate", param.applies_to)
            rate = rate_param.value if rate_param and isinstance(
                rate_param.value, (int, float)
            ) else 0
            signals.append(StrategicSignal(
                signal_type="trend_break",
                metric="pik_compounding",
                description=(
                    f"PIK toggle on {param.applies_to}: interest capitalizes each period. "
                    f"Rate: {rate*100:.1f}%. Debt balance grows via compounding "
                    f"({param.section_reference})"
                ),
                severity="medium",
                data={
                    "applies_to": param.applies_to,
                    "pik_rate": rate,
                },
            ))

    # Full ratchet anti-dilution exposure
    ad_params = params.get_all("anti_dilution_method")
    for param in ad_params:
        if param.value == "full_ratchet":
            signals.append(StrategicSignal(
                signal_type="anomaly",
                metric="full_ratchet_exposure",
                description=(
                    f"FULL RATCHET anti-dilution for {param.applies_to} "
                    f"({param.section_reference}). Any down round — even one share "
                    f"sold at a lower price — reprices ALL their shares. "
                    f"Maximum dilution risk to founders."
                ),
                severity="high",
                data={
                    "applies_to": param.applies_to,
                    "method": "full_ratchet",
                    "source_clause": param.source_clause_id,
                },
            ))

    return signals


def _detect_missing_protections(
    params: ResolvedParameterSet,
    state: Any,
) -> List[StrategicSignal]:
    """Standard clauses absent, benchmarked by stage."""
    signals: List[StrategicSignal] = []

    stage = getattr(state, "stage", None) if state else None
    if not stage:
        return signals

    stage_lower = stage.lower().replace(" ", "_")
    expected = STAGE_EXPECTED_PROTECTIONS.get(stage_lower, [])

    missing: List[str] = []
    for protection in expected:
        found = any(
            p.param_type == protection
            for p in params.parameters.values()
        )
        if not found:
            missing.append(protection)

    if missing:
        signals.append(StrategicSignal(
            signal_type="anomaly",
            metric="missing_protections",
            description=(
                f"Missing standard protections for {stage} stage: "
                f"{', '.join(missing)}. These are standard at this stage."
            ),
            severity="medium",
            data={
                "stage": stage,
                "missing": missing,
            },
        ))

    return signals


def _detect_expiry_deadlines(
    params: ResolvedParameterSet,
    as_of: datetime,
) -> List[StrategicSignal]:
    """Option exercise windows, exclusivity periods, auto-renewals."""
    signals: List[StrategicSignal] = []

    # Auto-renewal deadlines
    renewal_params = params.get_all("auto_renewal")
    for param in renewal_params:
        if not isinstance(param.value, dict):
            continue
        notice_days = param.value.get("notice_days")
        if not notice_days:
            continue

        # Check if expiry_date is set on the parameter
        if param.expiry_date:
            expiry = _parse_date(param.expiry_date)
            if expiry:
                notice_deadline = expiry - timedelta(days=notice_days)
                days_to_deadline = (notice_deadline - as_of).days

                if 0 < days_to_deadline <= 60:
                    renewal_months = param.value.get("renewal_term_months", 12)
                    signals.append(StrategicSignal(
                        signal_type="milestone",
                        metric="auto_renewal_deadline",
                        description=(
                            f"Contract auto-renews in {days_to_deadline} days "
                            f"with {renewal_months}-month lock-in. "
                            f"{notice_days}-day notice window closing "
                            f"({param.section_reference})"
                        ),
                        severity="high" if days_to_deadline <= 30 else "medium",
                        current_value=days_to_deadline,
                        data={
                            "applies_to": param.applies_to,
                            "notice_days": notice_days,
                            "renewal_months": renewal_months,
                            "deadline": str(notice_deadline.date()),
                        },
                    ))
                elif days_to_deadline <= 0:
                    signals.append(StrategicSignal(
                        signal_type="threshold_cross",
                        metric="auto_renewal_missed",
                        description=(
                            f"Auto-renewal notice period MISSED for "
                            f"{param.applies_to}. Locked in for another "
                            f"{param.value.get('renewal_term_months', 12)} months "
                            f"({param.section_reference})"
                        ),
                        severity="high",
                        data={
                            "applies_to": param.applies_to,
                            "days_past": abs(days_to_deadline),
                        },
                    ))

    # Warrant expiry
    warrant_expiry_params = params.get_all("warrant_expiry")
    for param in warrant_expiry_params:
        expiry = _parse_date(param.value)
        if expiry:
            days_to_expiry = (expiry - as_of).days
            if 0 < days_to_expiry <= 90:
                signals.append(StrategicSignal(
                    signal_type="milestone",
                    metric="warrant_expiry",
                    description=(
                        f"Warrant for {param.applies_to} expires in "
                        f"{days_to_expiry} days ({param.section_reference})"
                    ),
                    severity="medium",
                    current_value=days_to_expiry,
                    data={
                        "applies_to": param.applies_to,
                        "expiry_date": str(expiry.date()),
                    },
                ))

    # Redemption dates
    redemption_params = params.get_all("redemption_rights")
    for param in redemption_params:
        if param.value and param.expiry_date:
            redemption_date = _parse_date(param.expiry_date)
            if redemption_date:
                days_to = (redemption_date - as_of).days
                if 0 < days_to <= 180:
                    signals.append(StrategicSignal(
                        signal_type="milestone",
                        metric="redemption_window",
                        description=(
                            f"Redemption window opens for {param.applies_to} in "
                            f"{days_to} days. Investor can force buyback "
                            f"({param.section_reference})"
                        ),
                        severity="high" if days_to <= 90 else "medium",
                        current_value=days_to,
                        data={
                            "applies_to": param.applies_to,
                            "redemption_date": str(redemption_date.date()),
                        },
                    ))

    return signals


def _detect_indemnity_signals(
    params: ResolvedParameterSet,
    as_of: datetime,
) -> List[StrategicSignal]:
    """Indemnity escrow release dates, basket thresholds, survival periods."""
    signals: List[StrategicSignal] = []

    escrow_params = params.get_all("indemnity_escrow") + params.get_all("escrow_terms")
    for param in escrow_params:
        val = param.value if isinstance(param.value, dict) else {}
        duration_months = val.get("duration_months")
        amount = val.get("amount") or val.get("percentage")

        if duration_months and param.effective_date:
            start = _parse_date(param.effective_date)
            if start:
                release_date = start + timedelta(days=duration_months * 30)
                days_to = (release_date - as_of).days

                if 0 < days_to <= 90:
                    signals.append(StrategicSignal(
                        signal_type="milestone",
                        metric="escrow_release",
                        description=(
                            f"Indemnity escrow for {param.applies_to} releases in "
                            f"{days_to} days. Amount: {amount} "
                            f"({param.section_reference})"
                        ),
                        severity="low",
                        current_value=days_to,
                        data={
                            "applies_to": param.applies_to,
                            "release_date": str(release_date.date()),
                            "amount": amount,
                        },
                    ))

    return signals


def _detect_earnout_signals(
    params: ResolvedParameterSet,
    state: Any,
    as_of: datetime,
) -> List[StrategicSignal]:
    """Earnout milestone tracking and buyer control warnings."""
    signals: List[StrategicSignal] = []

    earnout_params = params.get_all("earnout_terms")
    for param in earnout_params:
        val = param.value if isinstance(param.value, dict) else {}
        max_amount = val.get("max_amount", 0)
        milestones = val.get("milestones", [])

        if max_amount and milestones:
            signals.append(StrategicSignal(
                signal_type="milestone",
                metric="earnout_tracking",
                description=(
                    f"Active earnout for {param.applies_to}: up to "
                    f"${max_amount:,.0f} contingent on {len(milestones)} milestones. "
                    f"Buyer controls operations — moral hazard risk "
                    f"({param.section_reference})"
                ),
                severity="medium",
                current_value=max_amount,
                data={
                    "applies_to": param.applies_to,
                    "max_amount": max_amount,
                    "milestones": milestones,
                },
            ))

    return signals


# ---------------------------------------------------------------------------
# Group-level signal detectors
# ---------------------------------------------------------------------------

def _detect_group_guarantee_chain(
    group_structure: Any,
    params: ResolvedParameterSet,
) -> List[StrategicSignal]:
    """Guarantee chain exposure — parent liable for subsidiary defaults."""
    signals: List[StrategicSignal] = []

    guarantee_rels = [
        r for r in group_structure.relationships
        if r.relationship_type == "guarantor"
    ]

    if not guarantee_rels:
        return signals

    # Total guaranteed exposure
    total_exposure = 0.0
    chain_desc: List[str] = []
    for rel in guarantee_rels:
        # Find debt at the subsidiary level
        sub_debt_params = [
            p for p in params.parameters.values()
            if p.instrument == "debt" and p.applies_to == rel.to_entity_id
        ]
        sub_exposure = 0.0
        for p in sub_debt_params:
            if p.param_type == "interest_rate":
                # Find principal from instruments
                for inst in params.instruments:
                    if inst.holder == rel.to_entity_id:
                        sub_exposure += inst.principal_or_value
                        break

        if sub_exposure > 0:
            total_exposure += sub_exposure
            chain_desc.append(
                f"{rel.from_entity_id} guarantees {rel.to_entity_id} "
                f"(${sub_exposure:,.0f})"
            )

    if total_exposure > 0:
        signals.append(StrategicSignal(
            signal_type="anomaly",
            metric="group_guarantee_chain",
            description=(
                f"Group guarantee chain: total exposure ${total_exposure:,.0f} "
                f"across {len(guarantee_rels)} guarantees. "
                + "; ".join(chain_desc[:3])
                + (f" (+{len(chain_desc)-3} more)" if len(chain_desc) > 3 else "")
                + ". Single subsidiary default cascades to parent."
            ),
            severity="high" if len(guarantee_rels) >= 3 else "medium",
            current_value=total_exposure,
            data={
                "total_exposure": total_exposure,
                "guarantee_count": len(guarantee_rels),
                "chain": chain_desc,
            },
        ))

    return signals


def _detect_group_flow_imbalance(
    group_structure: Any,
) -> List[StrategicSignal]:
    """Intercompany flow imbalance — entity paying out more than it receives."""
    signals: List[StrategicSignal] = []

    entity_net_flow: Dict[str, float] = {}

    for flow in group_structure.flows:
        val = flow.annual_value or 0
        entity_net_flow.setdefault(flow.from_entity_id, 0.0)
        entity_net_flow.setdefault(flow.to_entity_id, 0.0)
        entity_net_flow[flow.from_entity_id] -= val  # outflow
        entity_net_flow[flow.to_entity_id] += val     # inflow

    for entity_id, net in entity_net_flow.items():
        entity = group_structure.entities.get(entity_id)
        if not entity or entity.is_dormant:
            continue

        # Large negative = entity is hemorrhaging cash to group
        if net < -500_000:  # $500K threshold
            signals.append(StrategicSignal(
                signal_type="trend_break",
                metric="group_flow_imbalance",
                description=(
                    f"Entity {entity.name or entity_id} ({entity.jurisdiction}): "
                    f"net intercompany outflow of ${abs(net):,.0f}/yr. "
                    f"Check if this entity has sufficient operating cash flow "
                    f"to sustain these payments."
                ),
                severity="medium",
                current_value=net,
                data={
                    "entity_id": entity_id,
                    "jurisdiction": entity.jurisdiction,
                    "net_flow": net,
                },
            ))

    return signals


def _detect_group_tp_compliance(
    group_structure: Any,
) -> List[StrategicSignal]:
    """Transfer pricing compliance proximity — flows near arm's length boundaries."""
    signals: List[StrategicSignal] = []

    for flow in group_structure.flows:
        if flow.arm_length_status == "out_of_range":
            signals.append(StrategicSignal(
                signal_type="anomaly",
                metric="tp_non_compliance",
                description=(
                    f"TP NON-COMPLIANT: {flow.flow_type} from "
                    f"{flow.from_entity_id} to {flow.to_entity_id} "
                    f"at {flow.current_rate} — outside arm's length range"
                    + (f" ({flow.permitted_range[0]}-{flow.permitted_range[1]})"
                       if flow.permitted_range else "")
                    + f". Method: {flow.tp_method or 'unspecified'}. "
                    f"Tax authority risk."
                ),
                severity="high",
                data={
                    "flow_id": flow.flow_id,
                    "flow_type": flow.flow_type,
                    "current_rate": flow.current_rate,
                    "permitted_range": flow.permitted_range,
                    "tp_method": flow.tp_method,
                },
            ))
        elif flow.arm_length_status == "untested":
            signals.append(StrategicSignal(
                signal_type="anomaly",
                metric="tp_untested",
                description=(
                    f"UNTESTED: {flow.flow_type} from {flow.from_entity_id} to "
                    f"{flow.to_entity_id} ({flow.current_rate}) has no TP analysis. "
                    f"Intercompany flows should have documented arm's length basis."
                ),
                severity="medium",
                data={
                    "flow_id": flow.flow_id,
                    "flow_type": flow.flow_type,
                    "annual_value": flow.annual_value,
                },
            ))
        elif (flow.arm_length_status == "in_range" and flow.permitted_range
              and flow.current_rate is not None):
            # Check if near boundary
            low, high = flow.permitted_range
            if isinstance(flow.current_rate, (int, float)):
                range_width = high - low if high > low else 1
                distance_to_boundary = min(
                    abs(flow.current_rate - low),
                    abs(flow.current_rate - high),
                )
                if range_width > 0 and (distance_to_boundary / range_width) < 0.15:
                    signals.append(StrategicSignal(
                        signal_type="threshold_cross",
                        metric="tp_boundary_proximity",
                        description=(
                            f"TP boundary proximity: {flow.flow_type} "
                            f"{flow.from_entity_id}→{flow.to_entity_id} "
                            f"at {flow.current_rate:.2%} near arm's length "
                            f"boundary ({low:.2%}-{high:.2%}). "
                            f"Small market changes could push out of range."
                        ),
                        severity="low",
                        current_value=flow.current_rate,
                        data={
                            "flow_id": flow.flow_id,
                            "range": flow.permitted_range,
                            "distance_to_boundary": distance_to_boundary,
                        },
                    ))

    # Flag if any TP flags exist on the structure itself
    for flag in getattr(group_structure, "tp_flags", []):
        signals.append(StrategicSignal(
            signal_type="anomaly",
            metric="tp_flag",
            description=flag,
            severity="medium",
            data={"source": "group_structure_analysis"},
        ))

    return signals


def _detect_group_thin_cap(
    group_structure: Any,
) -> List[StrategicSignal]:
    """Thin capitalisation warnings — debt/equity exceeds jurisdiction safe harbour."""
    signals: List[StrategicSignal] = []

    for constraint in group_structure.constraints:
        if constraint.constraint_type == "thin_cap":
            entity = group_structure.entities.get(constraint.affected_entity_id)
            entity_name = entity.name if entity else constraint.affected_entity_id

            signals.append(StrategicSignal(
                signal_type="threshold_cross",
                metric="thin_capitalisation",
                description=(
                    f"Thin capitalisation: {entity_name} "
                    f"({entity.jurisdiction if entity else 'unknown'}). "
                    f"{constraint.description}. "
                    f"Excess intercompany interest may be non-deductible."
                ),
                severity="high" if "breach" in constraint.description.lower() else "medium",
                data={
                    "entity_id": constraint.affected_entity_id,
                    "jurisdiction": entity.jurisdiction if entity else None,
                    "constraint": constraint.description,
                },
            ))

    return signals


def _detect_group_ring_fence(
    group_structure: Any,
) -> List[StrategicSignal]:
    """Ring-fenced entities — cash trapped, cannot be extracted."""
    signals: List[StrategicSignal] = []

    for constraint in group_structure.constraints:
        if constraint.constraint_type == "ring_fence" and constraint.affected_entity_id:
            entity = group_structure.entities.get(constraint.affected_entity_id)
            entity_name = entity.name if entity else constraint.affected_entity_id

            signals.append(StrategicSignal(
                signal_type="anomaly",
                metric="ring_fenced_entity",
                description=(
                    f"Ring-fenced: {entity_name} cash cannot be freely "
                    f"extracted to parent. {constraint.description}"
                    + (f" Binds until {constraint.binds_until}."
                       if constraint.binds_until else "")
                ),
                severity="medium",
                data={
                    "entity_id": constraint.affected_entity_id,
                    "constraint": constraint.description,
                    "binds_until": constraint.binds_until,
                },
            ))

    return signals


def _detect_group_dormant_entities(
    group_structure: Any,
) -> List[StrategicSignal]:
    """Dormant entity cleanup alerts — unnecessary holding costs."""
    signals: List[StrategicSignal] = []

    dormant = [
        e for e in group_structure.entities.values()
        if e.is_dormant
    ]

    if dormant:
        total_dormant = len(dormant)
        jurisdictions = list(set(e.jurisdiction for e in dormant))
        names = [e.name or e.entity_id for e in dormant[:5]]

        signals.append(StrategicSignal(
            signal_type="anomaly",
            metric="dormant_entities",
            description=(
                f"{total_dormant} dormant entities in group: "
                f"{', '.join(names)}"
                + (f" (+{total_dormant-5} more)" if total_dormant > 5 else "")
                + f". Jurisdictions: {', '.join(jurisdictions)}. "
                f"Each carries annual filing/maintenance costs. "
                f"Consider striking off or dissolving."
            ),
            severity="low",
            data={
                "dormant_count": total_dormant,
                "entities": [e.entity_id for e in dormant],
                "jurisdictions": jurisdictions,
            },
        ))

    return signals


def _detect_group_cross_default_contagion(
    group_structure: Any,
    params: ResolvedParameterSet,
    cascade_graph: CascadeGraph,
) -> List[StrategicSignal]:
    """Cross-default contagion risk across group entities."""
    signals: List[StrategicSignal] = []

    # Count entities with cross-default clauses
    cross_default_entities = set()
    for key, param in params.parameters.items():
        if param.param_type == "cross_default":
            cross_default_entities.add(param.applies_to)

    # Check which of those are in the group structure
    group_cd_entities = cross_default_entities.intersection(
        set(group_structure.entities.keys())
    )

    if len(group_cd_entities) >= 2:
        # Multiple group entities with cross-default = contagion risk
        entity_names = []
        for eid in group_cd_entities:
            entity = group_structure.entities.get(eid)
            entity_names.append(entity.name if entity else eid)

        signals.append(StrategicSignal(
            signal_type="anomaly",
            metric="group_cross_default_contagion",
            description=(
                f"Cross-default contagion: {len(group_cd_entities)} group entities "
                f"have cross-default clauses ({', '.join(entity_names[:4])}). "
                f"Default at ANY entity cascades to ALL linked entities. "
                f"Group-wide exposure."
            ),
            severity="high",
            data={
                "entities": list(group_cd_entities),
                "entity_names": entity_names,
                "contagion_count": len(group_cd_entities),
            },
        ))

    return signals


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_financial_metric(state: Any, metric: str) -> Optional[float]:
    """Get a financial metric value from the unified state."""
    if state is None:
        return None

    metric_lower = metric.lower()

    # Direct attributes
    for attr in ("dscr", "leverage_ratio", "current_ratio"):
        if metric_lower == attr:
            return getattr(state, attr, None)

    # Try KPIs
    kpis = getattr(state, "kpis", None)
    if kpis and hasattr(kpis, "get"):
        return kpis.get(metric)

    # Try drivers
    drivers = getattr(state, "drivers", {})
    if metric in drivers:
        driver = drivers[metric]
        return getattr(driver, "effective", None)

    return None


def _estimate_months_to_breach(
    state: Any,
    metric: str,
    current: float,
    threshold: float,
) -> Optional[float]:
    """Estimate months until a metric breaches its threshold.

    Uses actual monthly change data from the state object.
    Returns None when insufficient data to estimate.
    """
    if state is None:
        return None

    headroom = abs(current - threshold)
    if headroom <= 0:
        return 0.0

    # Look for actual monthly change data on the state
    monthly_change = (
        getattr(state, f"{metric}_monthly_change", None)
        or getattr(state, f"monthly_{metric}_change", None)
    )

    if monthly_change is not None and isinstance(monthly_change, (int, float)):
        # For DSCR: negative change means deteriorating (approaching breach from above)
        # For leverage: positive change means deteriorating (approaching breach from below)
        if metric == "dscr":
            deterioration = -monthly_change  # declining DSCR = positive deterioration
        else:
            deterioration = monthly_change   # rising leverage = positive deterioration

        if deterioration <= 0:
            return None  # Moving away from breach

        return headroom / deterioration

    # Fall back to period-over-period history if available
    history = getattr(state, f"{metric}_history", None)
    if history and isinstance(history, (list, tuple)) and len(history) >= 2:
        recent = history[-1]
        prior = history[-2]
        if isinstance(recent, (int, float)) and isinstance(prior, (int, float)):
            delta = recent - prior
            if metric == "dscr":
                deterioration = -delta
            else:
                deterioration = delta

            if deterioration <= 0:
                return None

            return headroom / deterioration

    return None


def _parse_date(value: Any) -> Optional[datetime]:
    """Parse a date from various formats."""
    if isinstance(value, datetime):
        return value
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        pass
    # Try common date formats
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    return None
