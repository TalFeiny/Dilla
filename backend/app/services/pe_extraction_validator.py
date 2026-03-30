"""PE Extraction Validator — checks LLM-extracted model data for sanity.

Called after _normalize() in PEModelIngestionService.ingest(). Returns a dict
with warnings (non-blocking) and errors (blocking) so the memo can surface
data quality issues instead of silently passing bad numbers to the IC.

Works with the flexible EXTRACTION_SCHEMA — validates universal invariants
that apply to ANY deal type (LBO, structured equity, real asset, etc.).

Usage:
    from app.services.pe_extraction_validator import validate_pe_extraction
    result = validate_pe_extraction(pe_data)
    # result = {"valid": True/False, "warnings": [...], "errors": [...]}
"""

import logging
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


def validate_pe_extraction(pe_data: Dict[str, Any]) -> Dict[str, Any]:
    """Validate extracted model data. Returns {valid, warnings, errors}."""
    warnings: List[str] = []
    errors: List[str] = []

    dp = pe_data.get("deal_profile") or {}
    instruments = pe_data.get("instruments") or []
    su = pe_data.get("sources_uses") or {}
    om = pe_data.get("operating_model") or {}
    returns = pe_data.get("returns") or {}
    sched = pe_data.get("debt_schedule") or {}

    # ── Deal profile — critical fields ──────────────────────────────
    if not dp.get("target_name") or dp.get("target_name") == "Unknown Target":
        errors.append("Missing target name (deal_profile.target_name)")
    if not dp.get("deal_type") or dp.get("deal_type") == "unknown":
        warnings.append("Deal type not identified — LLM could not determine investment type")
    if dp.get("total_investment") and dp["total_investment"] < 0:
        errors.append(f"Negative total_investment: {dp['total_investment']}")

    # ── Instruments ──────────────────────────────────────────────────
    if not instruments:
        warnings.append("No instruments extracted — capital structure incomplete")
    for i, inst in enumerate(instruments):
        amt = inst.get("amount", 0)
        if amt and amt < 0:
            errors.append(f"Instrument '{inst.get('name', i)}' has negative amount: {amt}")

    # ── Instrument amounts sum ≈ total_investment ────────────────────
    total_inv = dp.get("total_investment", 0)
    if instruments and total_inv > 0:
        inst_sum = sum(inst.get("amount", 0) for inst in instruments if inst.get("amount"))
        if inst_sum > 0:
            diff_pct = abs(inst_sum - total_inv) / max(inst_sum, total_inv)
            if diff_pct > 0.10:
                warnings.append(
                    f"Instruments sum (${inst_sum / 1e6:,.1f}M) differs from "
                    f"total_investment (${total_inv / 1e6:,.1f}M) by {diff_pct * 100:.0f}%"
                )

    # ── Operating model ──────────────────────────────────────────────
    periods = om.get("periods") or []
    metrics = om.get("metrics") or {}
    if len(periods) < 2:
        errors.append(f"Only {len(periods)} operating periods extracted — need at least 2 for projections")
    if not metrics:
        warnings.append("No operating metrics extracted")

    # Check metric array lengths match period count
    if periods and metrics:
        n_periods = len(periods)
        for metric_name, metric_data in metrics.items():
            if not isinstance(metric_data, dict):
                continue
            values = metric_data.get("values") or []
            if values and len(values) != n_periods:
                warnings.append(
                    f"operating_model.metrics.{metric_name} has {len(values)} values "
                    f"but {n_periods} periods"
                )

    # ── primary_metric exists in metrics ─────────────────────────────
    primary = dp.get("primary_metric", "")
    if primary and metrics and primary not in metrics:
        warnings.append(
            f"primary_metric '{primary}' not found in operating_model.metrics "
            f"(available: {list(metrics.keys())[:5]})"
        )

    # ── Sources ≈ Uses ───────────────────────────────────────────────
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

    # ── Returns bounds ───────────────────────────────────────────────
    scenarios = returns.get("scenarios") or {}
    for sc_name, sc_data in scenarios.items():
        if not isinstance(sc_data, dict):
            continue
        # Check IRR bounds
        for k, v in sc_data.items():
            k_lower = k.lower()
            if "irr" in k_lower and v != 0:
                irr_pct = v * 100 if abs(v) < 1 else v
                if irr_pct < -100:
                    errors.append(f"{sc_name} {k} {irr_pct:.0f}% < -100% — likely hallucinated")
                elif irr_pct > 200:
                    warnings.append(f"{sc_name} {k} {irr_pct:.0f}% > 200% — verify")
            if "moic" in k_lower or "multiple" in k_lower:
                if v and v < 0:
                    errors.append(f"{sc_name} {k} {v:.1f}x is negative — impossible")
                elif v and v > 20:
                    warnings.append(f"{sc_name} {k} {v:.1f}x > 20x — verify")

    # ── Sensitivity matrix dimensions ────────────────────────────────
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
                    break

    # ── Debt schedule consistency ────────────────────────────────────
    total_balance = sched.get("total_balance") or []
    if total_balance:
        for i, bal in enumerate(total_balance):
            if bal < 0:
                period_label = (sched.get("periods") or [])[i] if i < len(sched.get("periods", [])) else f"Period {i}"
                warnings.append(f"Debt schedule {period_label}: negative balance ${bal / 1e6:,.1f}M")

    valid = len(errors) == 0
    result = {"valid": valid, "warnings": warnings, "errors": errors}

    if errors:
        logger.warning("[PE_VALIDATE] %d errors: %s", len(errors), errors)
    if warnings:
        logger.info("[PE_VALIDATE] %d warnings: %s", len(warnings), warnings)
    if valid and not warnings:
        logger.info("[PE_VALIDATE] All checks passed")

    return result
