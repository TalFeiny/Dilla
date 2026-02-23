"""
Tier 1: Computational Micro-Skills — No network, <100ms each.

These use stage benchmarks and existing data to instantly fill gaps.
Reuses constants from IntelligentGapFiller but runs standalone.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from . import MicroSkillResult

logger = logging.getLogger(__name__)

# ── Stage Benchmarks (from IntelligentGapFiller) ──────────────────────

STAGE_BENCHMARKS = {
    "Pre-seed": {
        "revenue_range": (0, 150_000),
        "arr_median": 50_000,
        "growth_rate": 2.5,
        "burn_monthly": 75_000,
        "team_size": (2, 6),
        "runway_months": 18,
        "next_round_months": 12,
        "valuation_median": 5_000_000,
        "valuation_multiple": 25,
        "gross_margin": 0.65,
    },
    "Seed": {
        "revenue_range": (150_000, 500_000),
        "arr_median": 250_000,
        "growth_rate": 3.0,
        "burn_monthly": 100_000,
        "team_size": (5, 12),
        "runway_months": 18,
        "next_round_months": 15,
        "valuation_median": 8_000_000,
        "valuation_multiple": 20,
        "gross_margin": 0.70,
    },
    "Series A": {
        "revenue_range": (500_000, 3_000_000),
        "arr_median": 2_000_000,
        "growth_rate": 2.5,
        "burn_monthly": 400_000,
        "team_size": (15, 35),
        "runway_months": 18,
        "next_round_months": 18,
        "valuation_median": 35_000_000,
        "valuation_multiple": 15,
        "gross_margin": 0.75,
    },
    "Series B": {
        "revenue_range": (3_000_000, 15_000_000),
        "arr_median": 8_000_000,
        "growth_rate": 1.5,
        "burn_monthly": 1_200_000,
        "team_size": (40, 100),
        "runway_months": 24,
        "next_round_months": 20,
        "valuation_median": 100_000_000,
        "valuation_multiple": 12,
        "gross_margin": 0.78,
    },
    "Series C": {
        "revenue_range": (15_000_000, 50_000_000),
        "arr_median": 25_000_000,
        "growth_rate": 1.0,
        "burn_monthly": 2_500_000,
        "team_size": (100, 300),
        "runway_months": 24,
        "next_round_months": 24,
        "valuation_median": 250_000_000,
        "valuation_multiple": 10,
        "gross_margin": 0.80,
    },
    "Series D+": {
        "revenue_range": (50_000_000, 200_000_000),
        "arr_median": 75_000_000,
        "growth_rate": 0.7,
        "burn_monthly": 3_500_000,
        "team_size": (300, 1000),
        "runway_months": 36,
        "next_round_months": 30,
        "valuation_median": 500_000_000,
        "valuation_multiple": 8,
        "gross_margin": 0.82,
    },
}

STAGE_TYPICAL_ROUND = {
    "Pre-seed": {"amount": 1_500_000, "dilution": 0.15},
    "Seed": {"amount": 3_000_000, "dilution": 0.15},
    "Series A": {"amount": 15_000_000, "dilution": 0.20},
    "Series B": {"amount": 50_000_000, "dilution": 0.15},
    "Series C": {"amount": 100_000_000, "dilution": 0.12},
    "Series D": {"amount": 200_000_000, "dilution": 0.10},
    "Series E": {"amount": 350_000_000, "dilution": 0.08},
    "Growth": {"amount": 500_000_000, "dilution": 0.07},
}

# Growth decay by years since last round
GROWTH_DECAY = {1: 1.0, 2: 0.7, 3: 0.5, 4: 0.3}


def _ensure_numeric(value: Any, default: float = 0) -> float:
    if value is None:
        return default
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        cleaned = value.replace('$', '').replace(',', '').replace('€', '').replace('£', '').strip()
        try:
            return float(cleaned)
        except (ValueError, AttributeError):
            return default
    if isinstance(value, dict):
        for f in ['value', 'amount', 'number', 'total']:
            if f in value:
                return _ensure_numeric(value[f], default)
    return default


def _normalize_stage(stage: str) -> str:
    """Normalize stage string to match STAGE_BENCHMARKS keys."""
    if not stage:
        return "Series A"
    s = stage.strip().lower()
    mapping = {
        "pre-seed": "Pre-seed", "preseed": "Pre-seed", "angel": "Pre-seed",
        "seed": "Seed",
        "series a": "Series A", "a": "Series A",
        "series b": "Series B", "b": "Series B",
        "series c": "Series C", "c": "Series C",
        "series d": "Series D+", "series e": "Series D+",
        "series d+": "Series D+", "growth": "Series D+", "late": "Series D+",
    }
    return mapping.get(s, "Series A")


def _months_since_date(date_str: str) -> float:
    """Calculate months since a date string."""
    if not date_str:
        return 12.0
    try:
        if len(date_str) == 7 and '-' in date_str:
            dt = datetime.strptime(date_str + '-01', '%Y-%m-%d')
        elif len(date_str) >= 10 and '-' in date_str[:10]:
            dt = datetime.strptime(date_str[:10], '%Y-%m-%d')
        else:
            for fmt in ['%Y-%m-%d', '%Y/%m/%d', '%d/%m/%Y', '%m/%d/%Y']:
                try:
                    dt = datetime.strptime(date_str, fmt)
                    break
                except ValueError:
                    continue
            else:
                return 6.0
        now = datetime.now()
        months = (now.year - dt.year) * 12 + (now.month - dt.month) + (now.day - dt.day) / 30.0
        return max(0, months)
    except Exception:
        return 6.0


# ── Skill 1: Stage Benchmark Fill ─────────────────────────────────────

async def stage_benchmark_fill(company_data: dict, context: dict = None) -> MicroSkillResult:
    """Fill ALL missing fields from stage benchmarks. Instant, confidence 0.3-0.4."""
    stage = _normalize_stage(company_data.get('stage', ''))
    bench = STAGE_BENCHMARKS.get(stage, STAGE_BENCHMARKS["Series A"])

    updates = {}
    reasons = []

    if not company_data.get('arr') and not company_data.get('revenue') and not company_data.get('inferred_revenue'):
        updates['inferred_revenue'] = bench['arr_median']
        updates['arr'] = bench['arr_median']
        reasons.append(f"ARR=${bench['arr_median']/1e6:.1f}M ({stage} median)")

    if not company_data.get('valuation') and not company_data.get('inferred_valuation'):
        updates['inferred_valuation'] = bench['valuation_median']
        updates['valuation'] = bench['valuation_median']
        reasons.append(f"Valuation=${bench['valuation_median']/1e6:.0f}M ({stage} median)")

    if not company_data.get('growth_rate'):
        updates['growth_rate'] = bench['growth_rate']
        reasons.append(f"Growth={bench['growth_rate']*100:.0f}% YoY")

    if not company_data.get('gross_margin'):
        updates['gross_margin'] = bench.get('gross_margin', 0.75)
        reasons.append(f"Gross margin={bench.get('gross_margin', 0.75)*100:.0f}%")

    if not company_data.get('burn_rate') and not company_data.get('burn_rate_monthly_usd'):
        updates['burn_rate'] = bench['burn_monthly']
        reasons.append(f"Burn=${bench['burn_monthly']/1e3:.0f}K/mo")

    if not company_data.get('runway_months'):
        updates['runway_months'] = bench['runway_months']

    if not company_data.get('team_size') and not company_data.get('employee_count'):
        mid = (bench['team_size'][0] + bench['team_size'][1]) // 2
        updates['team_size'] = mid
        updates['employee_count'] = mid
        reasons.append(f"Team~{mid}")

    if not company_data.get('total_funding'):
        typical = STAGE_TYPICAL_ROUND.get(stage, STAGE_TYPICAL_ROUND.get("Series A"))
        cumulative = sum(
            STAGE_TYPICAL_ROUND[s]["amount"]
            for s in list(STAGE_TYPICAL_ROUND.keys())[:list(STAGE_TYPICAL_ROUND.keys()).index(stage) + 1]
            if s in STAGE_TYPICAL_ROUND
        ) if stage in STAGE_TYPICAL_ROUND else typical["amount"]
        updates['total_funding'] = cumulative

    name = company_data.get('name', 'company')
    return MicroSkillResult(
        field_updates=updates,
        confidence=0.35,
        reasoning=f"{name} ({stage}): {'; '.join(reasons)}" if reasons else f"No gaps to fill for {name}",
        source="stage_benchmark",
        memo_section={
            "type": "benchmark_fill",
            "heading": f"{name} — Stage Benchmarks ({stage})",
            "items": reasons,
            "confidence": 0.35,
        } if reasons else None,
    )


# ── Skill 2: Time-Adjusted Estimate ──────────────────────────────────

async def time_adjusted_estimate(company_data: dict, context: dict = None) -> MicroSkillResult:
    """Adjust benchmarks based on time since last funding round."""
    stage = _normalize_stage(company_data.get('stage', ''))
    bench = STAGE_BENCHMARKS.get(stage, STAGE_BENCHMARKS["Series A"])
    last_date = company_data.get('last_round_date', '')
    months = _months_since_date(last_date) if last_date else 12.0
    years = months / 12.0

    # Growth decay
    decay = GROWTH_DECAY.get(int(min(years, 4)) or 1, 0.3)
    base_growth = _ensure_numeric(company_data.get('growth_rate'), bench['growth_rate'])
    adjusted_growth = base_growth * decay

    # ARR compounds from base
    base_arr = _ensure_numeric(
        company_data.get('arr') or company_data.get('revenue') or company_data.get('inferred_revenue'),
        bench['arr_median']
    )
    # Monthly compound: (1 + annual_growth)^(months/12)
    compounded_arr = base_arr * ((1 + adjusted_growth) ** (months / 12))

    # Team grows ~2.5% monthly (capped)
    base_team = _ensure_numeric(company_data.get('team_size') or company_data.get('employee_count'), (bench['team_size'][0] + bench['team_size'][1]) // 2)
    team_caps = {"Pre-seed": 10, "Seed": 35, "Series A": 120, "Series B": 350, "Series C": 800, "Series D+": 2000}
    adjusted_team = min(int(base_team * (1.025 ** months)), team_caps.get(stage, 500))

    # Runway decreases
    base_runway = _ensure_numeric(company_data.get('runway_months'), bench['runway_months'])
    adjusted_runway = max(0, base_runway - months)

    updates = {}
    reasons = []

    if months > 3:
        updates['inferred_revenue'] = round(compounded_arr)
        updates['growth_rate'] = round(adjusted_growth, 2)
        updates['team_size'] = adjusted_team
        updates['runway_months'] = round(adjusted_runway, 1)
        reasons.append(f"{months:.0f}mo since funding → ARR=${compounded_arr/1e6:.1f}M (decay={decay})")
        reasons.append(f"Growth adjusted: {base_growth*100:.0f}% → {adjusted_growth*100:.0f}% YoY")
        reasons.append(f"Team: {int(base_team)} → {adjusted_team}")
        if adjusted_runway < 6:
            reasons.append(f"RUNWAY WARNING: {adjusted_runway:.0f} months remaining")

    name = company_data.get('name', 'company')
    return MicroSkillResult(
        field_updates=updates,
        confidence=0.45 if months < 12 else 0.3,
        reasoning=f"{name}: {'; '.join(reasons)}" if reasons else f"No time adjustment needed for {name}",
        source="time_adjusted",
        memo_section={
            "type": "time_adjustment",
            "heading": f"{name} — Time-Adjusted Estimates ({months:.0f}mo since last round)",
            "items": reasons,
            "confidence": 0.45 if months < 12 else 0.3,
        } if reasons else None,
    )


# ── Skill 3: Quick Valuation ─────────────────────────────────────────

async def quick_valuation(company_data: dict, context: dict = None) -> MicroSkillResult:
    """Run 3 valuation methods from whatever data exists. Returns low/mid/high."""
    stage = _normalize_stage(company_data.get('stage', ''))
    bench = STAGE_BENCHMARKS.get(stage, STAGE_BENCHMARKS["Series A"])

    arr = _ensure_numeric(
        company_data.get('arr') or company_data.get('revenue') or company_data.get('inferred_revenue'),
        bench['arr_median']
    )
    growth = _ensure_numeric(company_data.get('growth_rate'), bench['growth_rate'])
    total_funding = _ensure_numeric(company_data.get('total_funding'), 0)
    last_round = _ensure_numeric(company_data.get('last_round_amount'), 0)
    existing_val = _ensure_numeric(company_data.get('valuation') or company_data.get('inferred_valuation'), 0)

    methods = []
    valuations = []

    # Method 1: Revenue multiple
    multiple = bench['valuation_multiple']
    if growth > 2.0:
        multiple *= 1.3  # Premium for high growth
    elif growth < 1.0:
        multiple *= 0.7  # Discount for low growth
    rev_val = arr * multiple
    valuations.append(rev_val)
    methods.append(f"Revenue multiple: ${arr/1e6:.1f}M × {multiple:.0f}x = ${rev_val/1e6:.0f}M")

    # Method 2: Funding-implied (if we have round data)
    if last_round > 0:
        typical = STAGE_TYPICAL_ROUND.get(stage, {"dilution": 0.15})
        implied_post = last_round / typical["dilution"]
        # Time step-up (20% per year since round)
        months = _months_since_date(company_data.get('last_round_date', ''))
        step_up = 1 + (0.2 * months / 12)
        funding_val = implied_post * step_up
        valuations.append(funding_val)
        methods.append(f"Funding-implied: ${last_round/1e6:.1f}M/{typical['dilution']*100:.0f}% × {step_up:.2f} step-up = ${funding_val/1e6:.0f}M")
    elif total_funding > 0:
        # Rough: total funding typically = 30-50% of post-money
        funding_val = total_funding * 3
        valuations.append(funding_val)
        methods.append(f"Funding-ratio: ${total_funding/1e6:.1f}M total raised × 3x = ${funding_val/1e6:.0f}M")

    # Method 3: Stage benchmark
    stage_val = bench['valuation_median']
    valuations.append(stage_val)
    methods.append(f"Stage benchmark ({stage}): ${stage_val/1e6:.0f}M median")

    # Compute range
    if valuations:
        low = min(valuations)
        high = max(valuations)
        mid = sum(valuations) / len(valuations)
    else:
        mid = bench['valuation_median']
        low = mid * 0.7
        high = mid * 1.3

    name = company_data.get('name', 'company')
    return MicroSkillResult(
        field_updates={
            'inferred_valuation': round(mid),
            'valuation_low': round(low),
            'valuation_mid': round(mid),
            'valuation_high': round(high),
            'valuation_methods': methods,
        },
        confidence=0.5 if len(valuations) >= 2 else 0.35,
        reasoning=f"{name}: ${low/1e6:.0f}M–${high/1e6:.0f}M (mid ${mid/1e6:.0f}M) from {len(methods)} methods",
        source="quick_valuation",
        memo_section={
            "type": "valuation",
            "heading": f"{name} — Quick Valuation",
            "items": methods + [f"Range: ${low/1e6:.0f}M – ${mid/1e6:.0f}M – ${high/1e6:.0f}M"],
            "confidence": 0.5 if len(valuations) >= 2 else 0.35,
        },
        chart_data={
            "type": "valuation_range",
            "company": name,
            "low": round(low),
            "mid": round(mid),
            "high": round(high),
            "methods": methods,
        },
    )


# ── Skill 4: Similar Companies ────────────────────────────────────────

async def similar_companies(company_data: dict, context: dict = None) -> MicroSkillResult:
    """Find similar companies from portfolio DB. Context must include portfolio_companies list."""
    portfolio = (context or {}).get('portfolio_companies', [])
    if not portfolio:
        return MicroSkillResult(source="similar_companies", reasoning="No portfolio data available")

    target_stage = _normalize_stage(company_data.get('stage', ''))
    target_sector = (company_data.get('sector') or company_data.get('category') or '').lower()
    target_arr = _ensure_numeric(company_data.get('arr') or company_data.get('inferred_revenue'), 0)

    scored = []
    for pc in portfolio:
        if pc.get('name', '').lower() == company_data.get('name', '').lower():
            continue
        score = 0
        # Stage match
        if _normalize_stage(pc.get('stage', '')) == target_stage:
            score += 3
        # Sector match
        pc_sector = (pc.get('sector') or pc.get('category') or '').lower()
        if target_sector and pc_sector and (target_sector in pc_sector or pc_sector in target_sector):
            score += 2
        # Revenue proximity (within 3x)
        pc_arr = _ensure_numeric(pc.get('arr') or pc.get('current_arr_usd') or pc.get('inferred_revenue'), 0)
        if target_arr > 0 and pc_arr > 0:
            ratio = max(target_arr, pc_arr) / max(min(target_arr, pc_arr), 1)
            if ratio < 3:
                score += 2
            elif ratio < 5:
                score += 1

        if score > 0:
            scored.append({**pc, '_match_score': score})

    scored.sort(key=lambda x: x['_match_score'], reverse=True)
    top = scored[:5]

    if not top:
        return MicroSkillResult(source="similar_companies", reasoning="No similar companies found in portfolio")

    comparables = []
    for c in top:
        comparables.append({
            "name": c.get('name', ''),
            "stage": c.get('stage', ''),
            "sector": c.get('sector', ''),
            "arr": _ensure_numeric(c.get('arr') or c.get('current_arr_usd'), 0),
            "valuation": _ensure_numeric(c.get('valuation') or c.get('current_valuation_usd'), 0),
            "match_score": c['_match_score'],
        })

    # Derive comparable multiple from matches
    multiples = []
    for c in comparables:
        if c['arr'] > 0 and c['valuation'] > 0:
            multiples.append(c['valuation'] / c['arr'])
    median_multiple = sorted(multiples)[len(multiples) // 2] if multiples else None

    name = company_data.get('name', 'company')
    items = [f"{c['name']} ({c['stage']}, ${c['arr']/1e6:.1f}M ARR)" for c in comparables]
    if median_multiple:
        items.append(f"Comparable median multiple: {median_multiple:.1f}x ARR")

    return MicroSkillResult(
        field_updates={
            'comparable_companies': comparables,
            'comparable_multiple': median_multiple,
        },
        confidence=0.5 if len(comparables) >= 3 else 0.3,
        reasoning=f"{name}: {len(comparables)} comparables found" + (f", median {median_multiple:.1f}x" if median_multiple else ""),
        source="similar_companies",
        memo_section={
            "type": "comparables",
            "heading": f"{name} — Portfolio Comparables",
            "items": items,
            "confidence": 0.5 if len(comparables) >= 3 else 0.3,
        },
    )


# ── Skill 5: Next Round Model ─────────────────────────────────────────

async def next_round_model(company_data: dict, context: dict = None) -> MicroSkillResult:
    """Predict next round timing, size, dilution, valuation step-up."""
    stage = _normalize_stage(company_data.get('stage', ''))
    bench = STAGE_BENCHMARKS.get(stage, STAGE_BENCHMARKS["Series A"])

    arr = _ensure_numeric(
        company_data.get('arr') or company_data.get('revenue') or company_data.get('inferred_revenue'),
        bench['arr_median']
    )
    burn = _ensure_numeric(company_data.get('burn_rate'), bench['burn_monthly'])
    runway = _ensure_numeric(company_data.get('runway_months'), bench['runway_months'])
    current_val = _ensure_numeric(
        company_data.get('valuation') or company_data.get('inferred_valuation'),
        bench['valuation_median']
    )
    growth = _ensure_numeric(company_data.get('growth_rate'), bench['growth_rate'])

    # Next stage
    stage_progression = {
        "Pre-seed": "Seed", "Seed": "Series A", "Series A": "Series B",
        "Series B": "Series C", "Series C": "Series D+", "Series D+": "IPO/Growth",
    }
    next_stage = stage_progression.get(stage, "Series B")
    next_typical = STAGE_TYPICAL_ROUND.get(next_stage, STAGE_TYPICAL_ROUND.get("Series B"))
    if next_typical is None:
        next_typical = {"amount": 50_000_000, "dilution": 0.15}

    # Timing based on runway
    if runway < 6:
        months_to_next = 3
        urgency = "URGENT — likely fundraising now"
    elif runway < 9:
        months_to_next = 6
        urgency = "Starting within 3 months"
    elif runway < 15:
        months_to_next = min(runway - 6, bench['next_round_months'])
        urgency = "Normal timing"
    else:
        months_to_next = bench['next_round_months']
        urgency = "Well-funded, no rush"

    # Round size
    round_size = max(burn * 24, next_typical["amount"])
    dilution = next_typical["dilution"]

    # Valuation step-up
    step_up = 2.0 if growth > 2.0 else 1.5 if growth > 1.0 else 1.2
    next_val_pre = current_val * step_up
    next_val_post = next_val_pre + round_size

    # Down round risk
    min_revenue_thresholds = {
        "Seed": 100_000, "Series A": 500_000, "Series B": 2_000_000,
        "Series C": 10_000_000, "Series D+": 30_000_000,
    }
    min_rev = min_revenue_thresholds.get(next_stage, 2_000_000)
    projected_arr = arr * ((1 + growth) ** (months_to_next / 12))
    down_round_risk = "HIGH" if projected_arr < min_rev * 0.5 else "MEDIUM" if projected_arr < min_rev else "LOW"

    name = company_data.get('name', 'company')
    items = [
        f"Next round: {next_stage} in ~{months_to_next} months ({urgency})",
        f"Expected raise: ${round_size/1e6:.0f}M at ${next_val_pre/1e6:.0f}M pre / ${next_val_post/1e6:.0f}M post",
        f"Dilution: {dilution*100:.0f}% | Step-up: {step_up:.1f}x",
        f"Projected ARR at raise: ${projected_arr/1e6:.1f}M (need ${min_rev/1e6:.1f}M)",
        f"Down round risk: {down_round_risk}",
    ]

    return MicroSkillResult(
        field_updates={
            'next_round_stage': next_stage,
            'next_round_months': months_to_next,
            'next_round_size': round_size,
            'next_round_valuation_pre': next_val_pre,
            'next_round_valuation_post': next_val_post,
            'next_round_dilution': dilution,
            'down_round_risk': down_round_risk,
        },
        confidence=0.4,
        reasoning=f"{name}: {next_stage} in {months_to_next}mo, ${round_size/1e6:.0f}M raise, {down_round_risk} down-round risk",
        source="next_round_model",
        memo_section={
            "type": "next_round",
            "heading": f"{name} — Next Round Projection",
            "items": items,
            "confidence": 0.4,
        },
        chart_data={
            "type": "round_projection",
            "company": name,
            "current_valuation": current_val,
            "next_valuation_pre": next_val_pre,
            "next_valuation_post": next_val_post,
            "months_to_next": months_to_next,
            "round_size": round_size,
        },
    )


# -- Skill 6: Reconstruct Funding History --------------------------------

async def reconstruct_funding_history(company_data: dict, context: dict = None) -> MicroSkillResult:
    """Reconstruct prior funding rounds from current stage + last round data.

    Works backwards: if stage=Series C, builds Pre-seed -> Seed -> A -> B -> C.
    Last round uses actual data if available; prior rounds use STAGE_TYPICAL_ROUND benchmarks.
    """
    stage = _normalize_stage(company_data.get('stage', ''))
    STAGE_ORDER = ["Pre-seed", "Seed", "Series A", "Series B", "Series C", "Series D+"]

    try:
        current_idx = STAGE_ORDER.index(stage)
    except ValueError:
        current_idx = 2  # default Series A

    last_amount = _ensure_numeric(company_data.get('last_round_amount'), 0)
    last_date = company_data.get('last_round_date', '')
    total_funding = _ensure_numeric(company_data.get('total_funding'), 0)

    rounds = []
    cumulative = 0
    for i in range(current_idx + 1):
        s = STAGE_ORDER[i]
        typical = STAGE_TYPICAL_ROUND.get(s, STAGE_TYPICAL_ROUND.get("Series A", {"amount": 15_000_000, "dilution": 0.20}))

        if i == current_idx and last_amount > 0:
            # Last round -- use real data
            rounds.append({
                "round": s,
                "amount": last_amount,
                "date": last_date or "",
                "dilution": typical["dilution"],
                "source": "actual",
            })
            cumulative += last_amount
        else:
            rounds.append({
                "round": s,
                "amount": typical["amount"],
                "date": "",
                "dilution": typical["dilution"],
                "source": "benchmark",
            })
            cumulative += typical["amount"]

    # If we have total_funding and it differs significantly, scale benchmark rounds
    if total_funding > 0 and cumulative > 0 and last_amount > 0:
        benchmark_total = cumulative - last_amount
        actual_prior = total_funding - last_amount
        if benchmark_total > 0 and actual_prior > 0:
            scale = actual_prior / benchmark_total
            for r in rounds:
                if r["source"] == "benchmark":
                    r["amount"] = round(r["amount"] * scale)

    name = company_data.get('name', 'company')
    items = [
        f"{r['round']}: ${r['amount']/1e6:.1f}M ({r['source']})" + (f" [{r['date']}]" if r['date'] else "")
        for r in rounds
    ]

    return MicroSkillResult(
        field_updates={"funding_rounds": rounds},
        confidence=0.4 if last_amount > 0 else 0.25,
        reasoning=f"{name}: reconstructed {len(rounds)} rounds from Pre-seed to {stage}",
        source="reconstruct_funding_history",
        memo_section={
            "type": "funding_history",
            "heading": f"{name} -- Funding History (Reconstructed)",
            "items": items,
            "confidence": 0.4 if last_amount > 0 else 0.25,
        },
    )

