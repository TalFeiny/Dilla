"""
Gap Resolver — The Brain.

When the agent encounters companies with missing data, this:
1. Assesses what exists vs what's needed
2. Tier 1: Instant benchmark fills (<100ms, no network)
3. Tier 2: Parallel searches (1 Tavily search each, <5s)
4. Tier 3: Compute (valuations, projections — needs Tier 1/2 data)
5. Persists everything to pending_suggestions

The agent should NEVER reach synthesis with empty data.
If stage is known → benchmarks are instant.
If name is known → searches are parallel.
"""

import asyncio
import logging
from typing import Any, Callable, Dict, List, Optional

from . import MicroSkillResult, detect_missing, CORE_FIELDS, VALUATION_FIELDS, CAP_TABLE_FIELDS
from .benchmark_skills import (
    stage_benchmark_fill,
    time_adjusted_estimate,
    quick_valuation,
    similar_companies,
    next_round_model,
    reconstruct_funding_history,
    _normalize_stage,
)
from .search_skills import (
    find_funding,
    find_funding_rounds,
    find_team,
    find_description,
    find_revenue,
    find_competitors,
)
from .suggestion_emitter import emit_suggestions, emit_batch, build_grid_commands

logger = logging.getLogger(__name__)

# ── Field dependency graph ─────────────────────────────────────────────
# When a field is updated, downstream dependents should be recalculated.
# Used by Tier 3 cascading and correction detection.
FIELD_DEPENDENCIES: Dict[str, List[str]] = {
    "arr": ["valuation", "burn_rate", "runway_months", "gross_margin"],
    "revenue": ["valuation", "burn_rate", "runway_months", "gross_margin"],
    "growth_rate": ["valuation"],
    "total_funding": ["valuation", "runway_months", "cash_balance"],
    "cash_balance": ["runway_months", "burn_rate"],
    "burn_rate": ["runway_months"],
    "team_size": ["burn_rate"],
    "valuation": [],
    "runway_months": [],
    "gross_margin": [],
    "last_round_amount": ["valuation", "total_funding"],
}

# Threshold for flagging a correction (15% deviation from grid value)
CORRECTION_THRESHOLD = 0.15


def _detect_corrections(
    company: dict,
    result: "MicroSkillResult",
) -> List[Dict[str, Any]]:
    """Compare search results against _grid_values to find stale/incorrect data.

    Returns list of correction dicts with old_value, new_value, deviation, field.
    """
    grid_vals = company.get("_grid_values", {})
    if not grid_vals:
        return []

    corrections = []
    for field_name, new_value in result.field_updates.items():
        old_value = grid_vals.get(field_name)
        if old_value is None or new_value is None:
            continue
        # Only compare numeric fields
        if not isinstance(old_value, (int, float)) or not isinstance(new_value, (int, float)):
            continue
        if old_value == 0:
            continue
        deviation = abs(new_value - old_value) / abs(old_value)
        if deviation > CORRECTION_THRESHOLD:
            corrections.append({
                "field": field_name,
                "old_value": old_value,
                "new_value": new_value,
                "deviation_pct": round(deviation * 100, 1),
                "is_correction": True,
            })
            logger.info(
                "[CORRECTION] %s.%s: grid=%.2f → search=%.2f (%.1f%% deviation)",
                company.get("name", "?"), field_name, old_value, new_value, deviation * 100,
            )
    return corrections


async def resolve_gaps(
    companies: List[dict],
    needed_fields: Optional[List[str]] = None,
    fund_id: str = "",
    tavily_search_fn: Optional[Callable] = None,
    llm_extract_fn: Optional[Callable] = None,
    portfolio_companies: Optional[List[dict]] = None,
) -> Dict[str, Any]:
    """Fill data gaps for multiple companies using the fastest available method.

    Tier 1: Instant benchmarks (stage → all metrics)
    Tier 2: Parallel searches (1 Tavily search each)
    Tier 3: Compute (valuations, projections from Tier 1/2 data)

    Args:
        companies: List of company dicts with at minimum {name, stage?}
        needed_fields: Which fields to fill. None = CORE_FIELDS
        fund_id: For persisting to pending_suggestions
        tavily_search_fn: async (query: str) -> dict. If None, Tier 2 skipped.
        llm_extract_fn: async (prompt: str, system: str) -> str. If None, Tier 2 skipped.
        portfolio_companies: For similar_companies skill

    Returns:
        {
            "companies": enriched company list,
            "total_fields_filled": int,
            "total_suggestions_persisted": int,
            "skills_run": list of skill names,
            "memo_sections": list of memo section dicts,
            "grid_commands": list of grid command dicts,
            "chart_data": list of chart data dicts,
        }
    """
    if needed_fields is None:
        needed_fields = CORE_FIELDS

    total_filled = 0
    total_persisted = 0
    all_skills_run = []
    all_memo_sections = []
    all_grid_commands = []
    all_chart_data = []

    for company in companies:
        name = company.get("name", "Unknown")
        company_id = company.get("id") or company.get("company_id") or ""

        missing = detect_missing(company, needed_fields)
        if not missing:
            logger.info(f"[GAP_RESOLVER] {name}: no gaps detected")
            continue

        logger.info(f"[GAP_RESOLVER] {name}: {len(missing)} gaps — {missing[:10]}")

        # ── Tier 1: Instant benchmarks (no network) ──────────────────
        tier1_results: List[MicroSkillResult] = []

        if company.get("stage"):
            bench_result = await stage_benchmark_fill(company)
            if bench_result.has_data():
                bench_result.merge_into(company)
                tier1_results.append(bench_result)
                all_skills_run.append("stage_benchmark")

            # Time adjustment if we have a date
            if company.get("last_round_date"):
                time_result = await time_adjusted_estimate(company)
                if time_result.has_data():
                    time_result.merge_into(company)
                    tier1_results.append(time_result)
                    all_skills_run.append("time_adjusted")

            # Reconstruct funding history if missing
            if not company.get("funding_rounds"):
                fh_result = await reconstruct_funding_history(company)
                if fh_result.has_data():
                    fh_result.merge_into(company)
                    tier1_results.append(fh_result)
                    all_skills_run.append("reconstruct_funding_history")

        # Similar companies from portfolio
        if portfolio_companies:
            sim_result = await similar_companies(company, {"portfolio_companies": portfolio_companies})
            if sim_result.has_data():
                tier1_results.append(sim_result)
                all_skills_run.append("similar_companies")

        # Persist Tier 1 results
        for r in tier1_results:
            total_filled += len(r.field_updates)
            if fund_id and company_id:
                total_persisted += await emit_suggestions(r, company_id, fund_id, name)
            all_grid_commands.extend(build_grid_commands(r, name))
            if r.memo_section:
                all_memo_sections.append(r.memo_section)

        # ── Tier 2: Parallel searches (if available) ──────────────────
        # Re-check what's still missing after Tier 1
        still_missing = detect_missing(company, needed_fields)

        if still_missing and tavily_search_fn and llm_extract_fn:
            search_tasks = []
            search_names = []

            if any(f in still_missing for f in ["arr", "revenue", "inferred_revenue", "growth_rate"]):
                search_tasks.append(find_revenue(name, tavily_search_fn, llm_extract_fn))
                search_names.append("find_revenue")

            if any(f in still_missing for f in ["total_funding", "last_round_amount", "last_round_date", "stage"]):
                search_tasks.append(find_funding(name, tavily_search_fn, llm_extract_fn))
                search_names.append("find_funding")

            if any(f in still_missing for f in ["team_size", "employee_count"]):
                search_tasks.append(find_team(name, tavily_search_fn, llm_extract_fn))
                search_names.append("find_team")

            if any(f in still_missing for f in ["description", "business_model", "sector"]):
                search_tasks.append(find_description(name, tavily_search_fn, llm_extract_fn))
                search_names.append("find_description")

            if any(f in still_missing for f in ["competitors"]):
                search_tasks.append(find_competitors(name, tavily_search_fn, llm_extract_fn))
                search_names.append("find_competitors")


            # Funding rounds: if benchmark reconstruction confidence is low, search for real data
            if "funding_rounds" in still_missing or (
                company.get("funding_rounds") and
                all(r.get("source") == "benchmark" for r in company.get("funding_rounds", []))
            ):
                search_tasks.append(find_funding_rounds(name, tavily_search_fn, llm_extract_fn))
                search_names.append("find_funding_rounds")

            if search_tasks:
                logger.info(f"[GAP_RESOLVER] {name}: running {len(search_tasks)} parallel searches: {search_names}")
                results = await asyncio.gather(*search_tasks, return_exceptions=True)

                for i, r in enumerate(results):
                    if isinstance(r, Exception):
                        logger.warning(f"[GAP_RESOLVER] {name}: {search_names[i]} failed: {r}")
                        continue
                    if r.has_data():
                        r.merge_into(company)
                        total_filled += len(r.field_updates)
                        all_skills_run.append(search_names[i])
                        if fund_id and company_id:
                            total_persisted += await emit_suggestions(r, company_id, fund_id, name)
                        all_grid_commands.extend(build_grid_commands(r, name))
                        if r.memo_section:
                            all_memo_sections.append(r.memo_section)

                # ── Correction detection: compare Tier 2 results against grid values ──
                for i, r in enumerate(results):
                    if isinstance(r, Exception) or not r.has_data():
                        continue
                    corrections = _detect_corrections(company, r)
                    for corr in corrections:
                        # Emit correction as a high-confidence suggestion with is_correction flag
                        corr_result = MicroSkillResult(
                            source=f"correction.{search_names[i]}",
                            field_updates={corr["field"]: corr["new_value"]},
                            confidence=min(0.95, r.confidence + 0.15),
                            reasoning=f"Correction: {corr['field']} was {corr['old_value']:,.0f} in grid but search found {corr['new_value']:,.0f} ({corr['deviation_pct']}% deviation)",
                            citations=r.citations,
                            metadata={"is_correction": True, "old_value": corr["old_value"], "deviation_pct": corr["deviation_pct"]},
                        )
                        if fund_id and company_id:
                            total_persisted += await emit_suggestions(corr_result, company_id, fund_id, name)
                        all_grid_commands.extend(build_grid_commands(corr_result, name))
                        all_skills_run.append(f"correction_{corr['field']}")

                # ── Cascading: if key fields changed, re-fill dependents ──
                tier2_fields_filled = set()
                for i, r in enumerate(results):
                    if isinstance(r, Exception) or not r.has_data():
                        continue
                    tier2_fields_filled.update(r.field_updates.keys())

                cascade_fields = set()
                for f in tier2_fields_filled:
                    cascade_fields.update(FIELD_DEPENDENCIES.get(f, []))
                cascade_fields -= tier2_fields_filled  # don't re-fill what we just got

                if cascade_fields:
                    logger.info(f"[GAP_RESOLVER] {name}: cascading to {cascade_fields} from Tier 2 updates")
                    # Re-run benchmarks with updated data to fill cascaded dependents
                    if company.get("stage"):
                        cascade_bench = await stage_benchmark_fill(company)
                        if cascade_bench.has_data():
                            # Only take the cascaded fields
                            cascade_updates = {
                                k: v for k, v in cascade_bench.field_updates.items()
                                if k in cascade_fields and not company.get(k)
                            }
                            if cascade_updates:
                                cascade_bench.field_updates = cascade_updates
                                cascade_bench.merge_into(company)
                                total_filled += len(cascade_updates)
                                all_skills_run.append("cascade_benchmark")

                # If search found a stage we didn't have, run benchmarks now
                if not company.get("stage") and company.get("funding_stage"):
                    company["stage"] = company["funding_stage"]
                    bench_result = await stage_benchmark_fill(company)
                    if bench_result.has_data():
                        bench_result.merge_into(company)
                        total_filled += len(bench_result.field_updates)
                        all_skills_run.append("stage_benchmark_cascade")
                        if fund_id and company_id:
                            total_persisted += await emit_suggestions(bench_result, company_id, fund_id, name)

        # ── Tier 3: Compute (needs Tier 1/2 data) ────────────────────
        # Quick valuation always runs — uses whatever data we accumulated
        val_result = await quick_valuation(company)
        if val_result.has_data():
            val_result.merge_into(company)
            total_filled += len(val_result.field_updates)
            all_skills_run.append("quick_valuation")
            if fund_id and company_id:
                total_persisted += await emit_suggestions(val_result, company_id, fund_id, name)
            if val_result.memo_section:
                all_memo_sections.append(val_result.memo_section)
            if val_result.chart_data:
                all_chart_data.append(val_result.chart_data)

        # Next round model
        round_result = await next_round_model(company)
        if round_result.has_data():
            round_result.merge_into(company)
            all_skills_run.append("next_round_model")
            if round_result.memo_section:
                all_memo_sections.append(round_result.memo_section)
            if round_result.chart_data:
                all_chart_data.append(round_result.chart_data)

        logger.info(f"[GAP_RESOLVER] {name}: resolved — {total_filled} fields filled, {total_persisted} persisted")

    return {
        "companies": companies,
        "total_fields_filled": total_filled,
        "total_suggestions_persisted": total_persisted,
        "skills_run": list(set(all_skills_run)),
        "memo_sections": all_memo_sections,
        "grid_commands": all_grid_commands,
        "chart_data": all_chart_data,
    }


async def resolve_single(
    company: dict,
    needed_fields: Optional[List[str]] = None,
    fund_id: str = "",
    tavily_search_fn: Optional[Callable] = None,
    llm_extract_fn: Optional[Callable] = None,
    portfolio_companies: Optional[List[dict]] = None,
) -> Dict[str, Any]:
    """Convenience: resolve gaps for a single company."""
    result = await resolve_gaps(
        companies=[company],
        needed_fields=needed_fields,
        fund_id=fund_id,
        tavily_search_fn=tavily_search_fn,
        llm_extract_fn=llm_extract_fn,
        portfolio_companies=portfolio_companies,
    )
    return {
        "company": result["companies"][0] if result["companies"] else company,
        **{k: v for k, v in result.items() if k != "companies"},
    }
