"""PE Extraction Validator — checks LLM-extracted PE model data for sanity.

Called after _normalize() in PEModelIngestionService.ingest(). Returns a dict
with warnings (non-blocking) and errors (blocking) so the memo can surface
data quality issues instead of silently passing bad numbers to the IC.

Usage:
    from app.services.pe_extraction_validator import validate_pe_extraction
    result = validate_pe_extraction(pe_data)
    # result = {"valid": True/False, "warnings": [...], "errors": [...]}
"""

import logging
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


def validate_pe_extraction(pe_data: Dict[str, Any]) -> Dict[str, Any]:
    """Validate extracted PE model data. Returns {valid, warnings, errors}."""
    warnings: List[str] = []
    errors: List[str] = []

    txn = pe_data.get("transaction") or {}
    su = pe_data.get("sources_uses") or {}
    om = pe_data.get("operating_model") or {}
    ds = pe_data.get("debt_structure") or {}
    sched = pe_data.get("debt_schedule") or {}
    returns = pe_data.get("returns") or {}

    # ── Missing critical fields ──────────────────────────────────────
    if not txn.get("entry_ev"):
        errors.append("Missing entry enterprise value (entry_ev)")
    if not txn.get("entry_ebitda"):
        errors.append("Missing entry EBITDA (entry_ebitda)")
    if not txn.get("equity_check"):
        warnings.append("Missing equity check amount")

    tranches = ds.get("tranches") or []
    if not tranches:
        warnings.append("No debt tranches extracted — capital structure incomplete")

    periods = om.get("periods") or []
    if len(periods) < 2:
        errors.append(f"Only {len(periods)} operating periods extracted — need at least 2 for projections")

    # ── Sources = Uses ────────────────────────────────────────────────
    sources = su.get("sources") or []
    uses = su.get("uses") or []
    if sources and uses:
        sources_total = sum(s.get("amount", 0) for s in sources)
        uses_total = sum(u.get("amount", 0) for u in uses)
        if sources_total > 0 and uses_total > 0:
            diff_pct = abs(sources_total - uses_total) / max(sources_total, uses_total)
            if diff_pct > 0.01:
                errors.append(
                    f"Sources (${sources_total / 1e6:,.1f}M) ≠ Uses (${uses_total / 1e6:,.1f}M) — "
                    f"{diff_pct * 100:.1f}% gap"
                )

    # ── Debt tranches sum ≈ total_debt ────────────────────────────────
    if tranches:
        tranche_sum = sum(t.get("amount", 0) for t in tranches)
        total_debt = ds.get("total_debt", 0)
        if total_debt > 0 and tranche_sum > 0:
            diff_pct = abs(tranche_sum - total_debt) / max(tranche_sum, total_debt)
            if diff_pct > 0.01:
                warnings.append(
                    f"Debt tranches sum (${tranche_sum / 1e6:,.1f}M) ≠ total_debt "
                    f"(${total_debt / 1e6:,.1f}M) — {diff_pct * 100:.1f}% gap"
                )

    # ── Leverage sanity ───────────────────────────────────────────────
    entry_lev = ds.get("entry_leverage", 0)
    if entry_lev > 15:
        errors.append(f"Entry leverage {entry_lev:.1f}x is unrealistic (>15x)")
    elif entry_lev > 8:
        warnings.append(f"Entry leverage {entry_lev:.1f}x is high (>8x)")
    elif entry_lev < 0:
        errors.append(f"Entry leverage {entry_lev:.1f}x is negative")

    # ── Entry multiple sanity ─────────────────────────────────────────
    entry_mult = txn.get("entry_multiple", 0)
    if entry_mult > 30:
        errors.append(f"Entry multiple {entry_mult:.1f}x is unrealistic (>30x)")
    elif entry_mult > 15:
        warnings.append(f"Entry multiple {entry_mult:.1f}x is high (>15x)")

    # ── Operating model array lengths ─────────────────────────────────
    if periods:
        n_periods = len(periods)
        for key in ("revenue", "ebitda", "ebitda_margin", "capex", "fcf", "revenue_growth"):
            arr = om.get(key) or []
            if arr and len(arr) != n_periods:
                warnings.append(
                    f"operating_model.{key} has {len(arr)} values but {n_periods} periods"
                )

    # ── EBITDA margin coherence ───────────────────────────────────────
    revenues = om.get("revenue") or []
    ebitdas = om.get("ebitda") or []
    if len(revenues) >= 2 and len(ebitdas) >= 2 and len(revenues) == len(ebitdas):
        for i in range(len(revenues) - 1):
            if revenues[i] > 0 and revenues[i + 1] > 0 and ebitdas[i] > 0:
                rev_change = (revenues[i + 1] - revenues[i]) / revenues[i]
                ebitda_change = (ebitdas[i + 1] - ebitdas[i]) / ebitdas[i]
                if rev_change < -0.20 and ebitda_change > 0.05:
                    period_label = periods[i + 1] if i + 1 < len(periods) else f"Period {i + 1}"
                    warnings.append(
                        f"{period_label}: Revenue down {rev_change * 100:.0f}% but "
                        f"EBITDA up {ebitda_change * 100:.0f}% — verify margin assumptions"
                    )

    # ── Debt schedule math ────────────────────────────────────────────
    begin = sched.get("beginning_balance") or []
    amort = sched.get("mandatory_amort") or []
    prepay = sched.get("optional_prepayment") or []
    end = sched.get("ending_balance") or []
    if begin and end and len(begin) == len(end):
        for i in range(len(begin)):
            expected_end = begin[i] - (amort[i] if i < len(amort) else 0) - (prepay[i] if i < len(prepay) else 0)
            if expected_end > 0 and end[i] > 0:
                diff_pct = abs(expected_end - end[i]) / max(expected_end, end[i])
                if diff_pct > 0.05:
                    period_label = sched.get("periods", [])[i] if i < len(sched.get("periods", [])) else f"Period {i}"
                    warnings.append(
                        f"Debt schedule {period_label}: begin(${begin[i] / 1e6:,.1f}M) - "
                        f"amort - prepay ≠ end(${end[i] / 1e6:,.1f}M) — {diff_pct * 100:.0f}% gap"
                    )

    # ── Interest coverage ─────────────────────────────────────────────
    interest = sched.get("interest_expense") or []
    if interest and ebitdas and len(interest) == len(ebitdas):
        for i in range(len(interest)):
            if interest[i] > 0 and ebitdas[i] > 0:
                coverage = ebitdas[i] / interest[i]
                if coverage < 1.0:
                    period_label = periods[i] if i < len(periods) else f"Period {i}"
                    warnings.append(
                        f"{period_label}: Interest coverage {coverage:.1f}x < 1.0x — "
                        f"EBITDA doesn't cover interest"
                    )

    # ── Returns bounds ────────────────────────────────────────────────
    for case_name in ("base", "bull", "bear"):
        case = returns.get(case_name)
        if not case or not isinstance(case, dict):
            continue
        irr = case.get("irr", 0)
        moic = case.get("moic", 0)

        if irr != 0:
            irr_pct = irr * 100 if abs(irr) < 1 else irr
            if irr_pct < -100:
                errors.append(f"{case_name} IRR {irr_pct:.0f}% < -100% — likely hallucinated")
            elif irr_pct > 200:
                warnings.append(f"{case_name} IRR {irr_pct:.0f}% > 200% — verify")

        if moic != 0:
            if moic < 0:
                errors.append(f"{case_name} MOIC {moic:.1f}x is negative — impossible")
            elif moic > 20:
                warnings.append(f"{case_name} MOIC {moic:.1f}x > 20x — verify")

    # ── Sensitivity matrix dimensions ─────────────────────────────────
    sm = returns.get("sensitivity_matrix")
    if sm and isinstance(sm, dict):
        row_vals = sm.get("row_values") or []
        col_vals = sm.get("col_values") or []
        irr_grid = sm.get("irr_grid") or []
        if row_vals and irr_grid and len(irr_grid) != len(row_vals):
            warnings.append(
                f"Sensitivity matrix: {len(row_vals)} row_values but "
                f"{len(irr_grid)} grid rows"
            )
        if col_vals and irr_grid:
            for i, row in enumerate(irr_grid):
                if len(row) != len(col_vals):
                    warnings.append(
                        f"Sensitivity matrix row {i}: {len(row)} values but "
                        f"{len(col_vals)} col_values"
                    )
                    break  # one warning is enough

    valid = len(errors) == 0
    result = {"valid": valid, "warnings": warnings, "errors": errors}

    if errors:
        logger.warning("[PE_VALIDATE] %d errors: %s", len(errors), errors)
    if warnings:
        logger.info("[PE_VALIDATE] %d warnings: %s", len(warnings), warnings)
    if valid and not warnings:
        logger.info("[PE_VALIDATE] All checks passed")

    return result
