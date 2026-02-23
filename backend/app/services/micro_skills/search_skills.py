"""
Tier 2: Search Micro-Skills — 1 Tavily search each, <5s, parallelizable.

Each skill: precise query → JSON schema extraction → MicroSkillResult.
The key: knowing WHAT to search and extracting with a strict schema.

find_field() is the universal entry point — give it any column/field name
and it routes to the right search + extraction strategy automatically.
"""

import asyncio
import json
import logging
import re
from typing import Any, Callable, Coroutine, Dict, List, Optional

from . import CitationSource, MicroSkillResult

logger = logging.getLogger(__name__)


def _parse_llm_json(raw: Any, source: str = "", company: str = "") -> Optional[Dict]:
    """Parse JSON from LLM response, handling fences, prose, and Anthropic quirks.

    Returns parsed dict/list or None on failure.
    """
    if not isinstance(raw, str):
        if isinstance(raw, dict):
            return raw
        return None

    text = raw.strip()
    if not text:
        return None

    # Strip markdown fences
    fence_match = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if fence_match:
        text = fence_match.group(1).strip()

    # Find first { or [ — skip any prose before it
    for i, ch in enumerate(text):
        if ch in ('{', '['):
            text = text[i:]
            break
    else:
        logger.warning(f"[PARSE_JSON:{source}] No JSON found for {company}: {text[:100]}")
        return None

    # Trim trailing prose after the JSON
    # Find matching closing bracket
    try:
        result = json.loads(text)
        return result
    except json.JSONDecodeError:
        pass

    # Try progressively shorter substrings (trim trailing garbage)
    for end in range(len(text), max(0, len(text) - 200), -1):
        try:
            result = json.loads(text[:end])
            return result
        except json.JSONDecodeError:
            continue

    logger.warning(f"[PARSE_JSON:{source}] Failed to parse JSON for {company}: {text[:200]}")
    return None


# ── JSON extraction schemas per skill ──────────────────────────────────

FUNDING_SCHEMA = {
    "valuation": "number|null — latest post-money valuation in USD",
    "total_funding": "number|null — total raised to date in USD",
    "funding_stage": "string — Seed/Series A/Series B/Series C/Series D+",
    "investors": "list[string] — investor names from latest round",
    "last_round_amount": "number|null — latest round size in USD",
    "last_round_date": "string|null — YYYY-MM format",
}

TEAM_SCHEMA = {
    "team_size": "number|null — total employees",
    "founders": "list[string] — founder full names",
    "ceo": "string|null — CEO name",
    "cto": "string|null — CTO name",
    "founded_year": "number|null — YYYY",
    "hq_location": "string|null — City, Country",
}

DESCRIPTION_SCHEMA = {
    "description": "string — what the company actually does (factual, no buzzwords)",
    "business_model": "string — SaaS/Marketplace/Hardware/Services/Fintech/etc",
    "pricing_model": "string — per-seat/usage-based/enterprise/freemium/etc",
    "target_market": "string — who they sell to",
    "sector": "string — industry vertical",
}

REVENUE_SCHEMA = {
    "arr": "number|null — annual recurring revenue in USD",
    "revenue": "number|null — total annual revenue in USD",
    "growth_rate": "number|null — annual growth rate as decimal (e.g. 1.5 = 150%)",
    "customers": "number|null — number of customers",
    "notable_customers": "list[string] — named enterprise customers",
}

COMPETITORS_SCHEMA = {
    "competitors": "list[string] — direct competitor company names",
    "market_position": "string — leader/challenger/niche/emerging",
    "tam_estimate": "number|null — total addressable market in USD",
    "sector": "string — industry sector",
    "differentiators": "list[string] — what makes this company different",
}


async def _search_and_extract(
    company_name: str,
    search_suffix: str,
    schema: Dict[str, str],
    extraction_instructions: str,
    source_name: str,
    tavily_search_fn: Callable,
    llm_extract_fn: Callable,
) -> MicroSkillResult:
    """Core search+extract pattern. 1 Tavily search → LLM JSON extraction.

    Args:
        company_name: Company to search
        search_suffix: Appended to company name for search query
        schema: JSON schema for extraction
        extraction_instructions: Extra LLM guidance
        source_name: Skill name for tracking
        tavily_search_fn: async (query: str) -> dict with 'results' key
        llm_extract_fn: async (prompt: str, system: str) -> str (JSON)
    """
    company_name = company_name.strip().lstrip("@")
    if not company_name:
        return MicroSkillResult(source=source_name, reasoning="No company name provided")

    # 1. Single focused Tavily search
    query = f"{company_name} {search_suffix}"
    try:
        search_result = await tavily_search_fn(query)
        results = search_result.get("results", [])
        if not results:
            logger.warning(f"[MICRO_SKILL:{source_name}] No search results for: {query}")
            return MicroSkillResult(
                source=source_name,
                confidence=0.0,
                reasoning=f"No search results for {company_name} ({source_name})",
            )
        # Concatenate search results into text for extraction
        search_text = "\n\n".join(
            f"Source: {r.get('url', '')}\nTitle: {r.get('title', '')}\n{r.get('content', '')}"
            for r in results[:5]
        )[:4000]
        citations = [
            CitationSource(
                url=r.get('url', ''),
                title=r.get('title', ''),
                snippet=r.get('content', '')[:200],
                date=r.get('published_date', ''),
                source_type="web",
            )
            for r in results[:3] if r.get('url')
        ]
    except Exception as e:
        logger.warning(f"[MICRO_SKILL:{source_name}] Search failed for {company_name}: {e}")
        return MicroSkillResult(source=source_name, reasoning=f"Search failed: {e}")

    # 2. LLM extraction with strict JSON schema
    schema_json = json.dumps(schema, indent=2)
    extraction_prompt = f"""Extract data for "{company_name}" from these search results:

{search_text}

{extraction_instructions}

RESPOND WITH JUST THE JSON. NO MARKDOWN FENCES. NO EXPLANATION. NO PROSE.
Fields (null if unknown):
{schema_json}

RULES:
- Use actual numbers, not ranges
- Convert all currency to USD
- No buzzwords in description fields
- Dates in YYYY-MM format
- JUST THE JSON OBJECT. NOTHING ELSE."""

    try:
        raw_response = await llm_extract_fn(
            extraction_prompt,
            "You are a JSON extraction machine. Return ONLY a raw JSON object. No markdown. No ```json. No explanation. Just {\"key\": \"value\"}.",
        )
        extracted = _parse_llm_json(raw_response, source_name, company_name)
        if extracted is None:
            return MicroSkillResult(
                source=source_name,
                citations=citations,
                reasoning=f"JSON parse failed for {company_name} ({source_name})",
            )
    except Exception as e:
        logger.warning(f"[MICRO_SKILL:{source_name}] Extraction failed for {company_name}: {e}")
        return MicroSkillResult(
            source=source_name,
            citations=citations,
            reasoning=f"Extraction failed for {company_name}: {e}",
        )

    # 3. Filter nulls and build result
    field_updates = {k: v for k, v in extracted.items() if v is not None}

    # Build memo items
    items = []
    for k, v in field_updates.items():
        label = k.replace('_', ' ').title()
        if isinstance(v, list):
            items.append(f"**{label}**: {', '.join(str(x) for x in v)}")
        elif isinstance(v, (int, float)) and v > 1_000_000:
            items.append(f"**{label}**: ${v/1e6:,.1f}M")
        elif isinstance(v, float) and 0 < v < 1:
            items.append(f"**{label}**: {v*100:.0f}%")
        else:
            items.append(f"**{label}**: {v}")

    confidence = min(0.8, 0.3 + (len(field_updates) * 0.1))

    return MicroSkillResult(
        field_updates=field_updates,
        confidence=confidence,
        reasoning=f"{company_name}: extracted {len(field_updates)} fields via {source_name}",
        citations=citations,
        source=source_name,
        memo_section={
            "type": source_name,
            "heading": f"{company_name} — {source_name.replace('find_', '').replace('_', ' ').title()}",
            "items": items,
            "confidence": confidence,
        } if items else None,
    )


# ── Skill factories (each returns an async callable) ──────────────────

async def find_funding(
    company_name: str,
    tavily_search_fn: Callable,
    llm_extract_fn: Callable,
) -> MicroSkillResult:
    """1 search: funding round, investors, valuation."""
    return await _search_and_extract(
        company_name=company_name,
        search_suffix="funding round valuation investors Series stage total raised",
        schema=FUNDING_SCHEMA,
        extraction_instructions="Focus on the most recent funding round. Convert all amounts to USD. If multiple rounds mentioned, extract the latest.",
        source_name="find_funding",
        tavily_search_fn=tavily_search_fn,
        llm_extract_fn=llm_extract_fn,
    )


async def find_team(
    company_name: str,
    tavily_search_fn: Callable,
    llm_extract_fn: Callable,
) -> MicroSkillResult:
    """1 search: founders, CEO, CTO, team size, HQ."""
    return await _search_and_extract(
        company_name=company_name,
        search_suffix="founders CEO CTO team size employees headcount LinkedIn",
        schema=TEAM_SCHEMA,
        extraction_instructions="Look for LinkedIn data, Crunchbase profiles, About pages. Team size = total employees.",
        source_name="find_team",
        tavily_search_fn=tavily_search_fn,
        llm_extract_fn=llm_extract_fn,
    )


async def find_description(
    company_name: str,
    tavily_search_fn: Callable,
    llm_extract_fn: Callable,
) -> MicroSkillResult:
    """1 search: what the company does, business model, pricing."""
    return await _search_and_extract(
        company_name=company_name,
        search_suffix="what does company do product business model pricing customers",
        schema=DESCRIPTION_SCHEMA,
        extraction_instructions="Describe EXACTLY what the company does. NO buzzwords like 'AI-powered platform'. State the actual product/service.",
        source_name="find_description",
        tavily_search_fn=tavily_search_fn,
        llm_extract_fn=llm_extract_fn,
    )


async def find_revenue(
    company_name: str,
    tavily_search_fn: Callable,
    llm_extract_fn: Callable,
) -> MicroSkillResult:
    """1 search: ARR, revenue, growth rate, customer count."""
    return await _search_and_extract(
        company_name=company_name,
        search_suffix="revenue ARR annual recurring revenue growth rate customers",
        schema=REVENUE_SCHEMA,
        extraction_instructions="Focus on annual recurring revenue (ARR) or total annual revenue. Growth rate should be annual YoY as a decimal (2.0 = 200% growth).",
        source_name="find_revenue",
        tavily_search_fn=tavily_search_fn,
        llm_extract_fn=llm_extract_fn,
    )


async def find_competitors(
    company_name: str,
    tavily_search_fn: Callable,
    llm_extract_fn: Callable,
) -> MicroSkillResult:
    """1 search: competitors, market position, TAM."""
    return await _search_and_extract(
        company_name=company_name,
        search_suffix="competitors alternatives market size industry landscape versus",
        schema=COMPETITORS_SCHEMA,
        extraction_instructions="List direct competitors by name. TAM should be the total addressable market in USD. Market position: leader/challenger/niche/emerging.",
        source_name="find_competitors",
        tavily_search_fn=tavily_search_fn,
        llm_extract_fn=llm_extract_fn,
    )



# ── Funding Rounds History (full round-by-round search) ─────────────

FUNDING_ROUNDS_SCHEMA = {
    "rounds": "list[object] — each: {round: string, amount: number|null, date: string|null, lead_investor: string|null, valuation_post: number|null}",
    "total_funding": "number|null — total raised to date in USD",
}


async def find_funding_rounds(
    company_name: str,
    tavily_search_fn: Callable,
    llm_extract_fn: Callable,
) -> MicroSkillResult:
    """1 search: full funding round history — every round, amount, date, lead investor."""
    company_name = company_name.strip().lstrip("@")
    if not company_name:
        return MicroSkillResult(source="find_funding_rounds", reasoning="No company name")

    query = f"{company_name} funding rounds history Series A B C investors Crunchbase"
    try:
        search_result = await tavily_search_fn(query)
        results = search_result.get("results", [])
        if not results:
            return MicroSkillResult(source="find_funding_rounds", reasoning=f"No results for {company_name} funding rounds")
        search_text = "\n\n".join(
            f"Source: {r.get('url', '')}\nTitle: {r.get('title', '')}\n{r.get('content', '')}"
            for r in results[:5]
        )[:4000]
        citations = [
            CitationSource(
                url=r.get('url', ''),
                title=r.get('title', ''),
                snippet=r.get('content', '')[:200],
                date=r.get('published_date', ''),
                source_type="web",
            )
            for r in results[:3] if r.get('url')
        ]
    except Exception as e:
        return MicroSkillResult(source="find_funding_rounds", reasoning=f"Search failed: {e}")

    extraction_prompt = f"""Extract the COMPLETE funding round history for "{company_name}" from these search results:

{search_text}

Return JUST THE JSON. NO MARKDOWN. NO EXPLANATION.
I need every funding round: Pre-seed, Seed, Series A, B, C, D, etc.
For each round: the round name, amount raised in USD, date (YYYY-MM), lead investor, post-money valuation.
If a round is not mentioned, omit it. Only include rounds with evidence.

Schema:
{json.dumps(FUNDING_ROUNDS_SCHEMA, indent=2)}

JUST THE JSON. NOTHING ELSE."""

    try:
        raw = await llm_extract_fn(
            extraction_prompt,
            "You are a JSON extraction machine. Return ONLY raw JSON. No markdown. No fences. No explanation.",
        )
        extracted = _parse_llm_json(raw, "find_funding_rounds", company_name)
        if not extracted:
            return MicroSkillResult(source="find_funding_rounds", citations=citations, reasoning=f"Parse failed for {company_name}")
    except Exception as e:
        return MicroSkillResult(source="find_funding_rounds", citations=citations, reasoning=f"Extract failed: {e}")

    rounds = extracted.get("rounds", [])
    if not rounds:
        return MicroSkillResult(source="find_funding_rounds", citations=citations, reasoning=f"No rounds extracted for {company_name}")

    # Normalize rounds
    normalized = []
    for r in rounds:
        if isinstance(r, dict) and r.get("round"):
            normalized.append({
                "round": r.get("round", ""),
                "amount": r.get("amount") or 0,
                "date": r.get("date", ""),
                "dilution": r.get("dilution", 0),
                "lead_investor": r.get("lead_investor", ""),
                "valuation_post": r.get("valuation_post"),
                "source": "search",
            })

    field_updates = {"funding_rounds": normalized}
    if extracted.get("total_funding"):
        field_updates["total_funding"] = extracted["total_funding"]

    items = [
        f"{r['round']}: ${r['amount']/1e6:.1f}M" + (f" led by {r['lead_investor']}" if r.get('lead_investor') else "") + (f" [{r['date']}]" if r.get('date') else "")
        for r in normalized if r.get('amount')
    ]

    return MicroSkillResult(
        field_updates=field_updates,
        confidence=min(0.8, 0.4 + len(normalized) * 0.1),
        reasoning=f"{company_name}: found {len(normalized)} funding rounds via search",
        citations=citations,
        source="find_funding_rounds",
        memo_section={
            "type": "funding_rounds",
            "heading": f"{company_name} — Funding Round History",
            "items": items,
            "confidence": min(0.8, 0.4 + len(normalized) * 0.1),
        } if items else None,
    )


# ── Dynamic field routing ────────────────────────────────────────────
# Maps any grid column / backend field to the right search skill +
# the specific keys to pull out of a multi-field skill result.
# If a field isn't in this map, find_field() builds a custom query.

_FIELD_SKILL_ROUTE: Dict[str, Dict[str, Any]] = {
    # Revenue / financial metrics → find_revenue
    "arr":                   {"skill": "find_revenue",      "keys": ["arr", "revenue", "growth_rate", "customers"]},
    "revenue":               {"skill": "find_revenue",      "keys": ["arr", "revenue", "growth_rate"]},
    "revenueGrowthAnnual":   {"skill": "find_revenue",      "keys": ["growth_rate"]},
    "revenueGrowthMonthly":  {"skill": "find_revenue",      "keys": ["growth_rate"]},
    "growth_rate":           {"skill": "find_revenue",      "keys": ["growth_rate"]},
    "grossMargin":           {"skill": "find_revenue",      "keys": ["arr", "revenue"]},
    "gross_margin":          {"skill": "find_revenue",      "keys": ["arr", "revenue"]},
    "customers":             {"skill": "find_revenue",      "keys": ["customers", "notable_customers"]},
    "notable_customers":     {"skill": "find_revenue",      "keys": ["notable_customers", "customers"]},
    # Funding → find_funding
    "valuation":             {"skill": "find_funding",      "keys": ["valuation", "total_funding", "funding_stage"]},
    "currentValuationUsd":   {"skill": "find_funding",      "keys": ["valuation", "total_funding"]},
    "totalRaised":           {"skill": "find_funding",      "keys": ["total_funding", "valuation"]},
    "total_funding":         {"skill": "find_funding",      "keys": ["total_funding", "valuation"]},
    "lastRoundAmount":       {"skill": "find_funding",      "keys": ["last_round_amount", "last_round_date"]},
    "lastRoundDate":         {"skill": "find_funding",      "keys": ["last_round_date", "last_round_amount"]},
    "stage":                 {"skill": "find_funding",      "keys": ["funding_stage", "valuation"]},
    "investment_stage":      {"skill": "find_funding",      "keys": ["funding_stage", "valuation"]},
    "investors":             {"skill": "find_funding",      "keys": ["investors"]},
    "fundingRounds":         {"skill": "find_funding_rounds", "keys": ["funding_rounds", "total_funding"]},
    "funding_rounds":        {"skill": "find_funding_rounds", "keys": ["funding_rounds", "total_funding"]},
    # Team → find_team
    "headcount":             {"skill": "find_team",         "keys": ["team_size", "founders", "hq_location"]},
    "team_size":             {"skill": "find_team",         "keys": ["team_size", "founders"]},
    "employee_count":        {"skill": "find_team",         "keys": ["team_size"]},
    "founders":              {"skill": "find_team",         "keys": ["founders", "ceo", "cto"]},
    "ceo":                   {"skill": "find_team",         "keys": ["ceo", "founders"]},
    "cto":                   {"skill": "find_team",         "keys": ["cto", "founders"]},
    "hqLocation":            {"skill": "find_team",         "keys": ["hq_location", "founded_year"]},
    "hq_location":           {"skill": "find_team",         "keys": ["hq_location", "founded_year"]},
    "foundedYear":           {"skill": "find_team",         "keys": ["founded_year", "hq_location"]},
    "founded_year":          {"skill": "find_team",         "keys": ["founded_year"]},
    # Description / identity → find_description
    "description":           {"skill": "find_description",  "keys": ["description", "business_model", "sector"]},
    "sector":                {"skill": "find_description",  "keys": ["sector", "business_model"]},
    "category":              {"skill": "find_description",  "keys": ["sector", "business_model"]},
    "businessModel":         {"skill": "find_description",  "keys": ["business_model", "sector"]},
    "business_model":        {"skill": "find_description",  "keys": ["business_model", "sector"]},
    "targetMarket":          {"skill": "find_description",  "keys": ["target_market", "pricing_model"]},
    "target_market":         {"skill": "find_description",  "keys": ["target_market", "pricing_model"]},
    "pricingModel":          {"skill": "find_description",  "keys": ["pricing_model", "target_market"]},
    "pricing_model":         {"skill": "find_description",  "keys": ["pricing_model", "target_market"]},
    # Competitors / market → find_competitors
    "competitors":           {"skill": "find_competitors",  "keys": ["competitors", "market_position"]},
    "tamUsd":                {"skill": "find_competitors",  "keys": ["tam_estimate", "competitors"]},
    "tam_usd":               {"skill": "find_competitors",  "keys": ["tam_estimate", "competitors"]},
    "samUsd":                {"skill": "find_competitors",  "keys": ["tam_estimate"]},
    "somUsd":                {"skill": "find_competitors",  "keys": ["tam_estimate"]},
    # Burn / runway / cash → find_financials
    "burnRate":              {"skill": "find_financials",   "keys": ["burn_rate", "runway_months", "cash_balance"]},
    "burn_rate":             {"skill": "find_financials",   "keys": ["burn_rate", "runway_months", "cash_balance"]},
    "burnRateMonthlyUsd":    {"skill": "find_financials",   "keys": ["burn_rate", "runway_months"]},
    "runway":                {"skill": "find_financials",   "keys": ["runway_months", "burn_rate"]},
    "runway_months":         {"skill": "find_financials",   "keys": ["runway_months", "burn_rate"]},
    "cashInBank":            {"skill": "find_financials",   "keys": ["cash_balance", "burn_rate", "runway_months"]},
    "cash_balance":          {"skill": "find_financials",   "keys": ["cash_balance", "burn_rate"]},
}

# Skills by name for dispatch
_SKILL_FNS = {
    "find_revenue": find_revenue,
    "find_funding": find_funding,
    "find_team": find_team,
    "find_description": find_description,
    "find_competitors": find_competitors,
    "find_funding_rounds": find_funding_rounds,
}


def _column_id_to_label(col_id: str) -> str:
    """Convert camelCase column ID to a human-readable search term.

    'burnRateMonthlyUsd' → 'burn rate monthly usd'
    'revenueGrowthAnnual' → 'revenue growth annual'
    """
    # Insert space before uppercase letters
    spaced = re.sub(r"([a-z])([A-Z])", r"\1 \2", col_id)
    return spaced.lower().replace("_", " ")


async def find_field(
    company_name: str,
    fields: List[str],
    tavily_search_fn: Callable,
    llm_extract_fn: Callable,
    context: str = "",
) -> List[MicroSkillResult]:
    """Universal field lookup — routes any column/field name(s) to the right search skill.

    For known fields: delegates to the matching skill (find_revenue, find_team, etc.)
    For unknown fields: builds a custom search query from the column name.

    Args:
        company_name: Company to search for.
        fields: List of field/column IDs to find (e.g. ["arr", "burnRate", "description"]).
        tavily_search_fn: Tavily search coroutine.
        llm_extract_fn: LLM extraction coroutine.
        context: Optional extra search context (e.g. "Q3 2024 numbers").

    Returns:
        List of MicroSkillResult, one per skill invoked (skills are deduplicated —
        if "arr" and "growth_rate" both map to find_revenue, it runs once).
    """
    company_name = company_name.strip().lstrip("@")
    if not company_name:
        return [MicroSkillResult(source="find_field", reasoning="No company name")]
    if not fields:
        return [MicroSkillResult(source="find_field", reasoning="No fields requested")]

    # Group fields by which skill handles them, preserving order
    skill_groups: Dict[str, List[str]] = {}  # skill_name → [fields]
    custom_fields: List[str] = []

    for f in fields:
        route = _FIELD_SKILL_ROUTE.get(f)
        if route:
            skill_name = route["skill"]
            if skill_name not in skill_groups:
                skill_groups[skill_name] = []
            skill_groups[skill_name].append(f)
        else:
            custom_fields.append(f)

    # Run known skills in parallel
    tasks = []
    task_labels = []

    for skill_name in skill_groups:
        fn = _SKILL_FNS.get(skill_name)
        if fn:
            tasks.append(fn(company_name, tavily_search_fn, llm_extract_fn))
            task_labels.append(skill_name)

    # Build custom searches for unknown fields (each gets its own search)
    for cf in custom_fields:
        label = _column_id_to_label(cf)
        search_suffix = f"{label} {context}".strip() if context else label
        schema = {cf: f"number, string, or null — {label} for this company"}
        tasks.append(
            _search_and_extract(
                company_name=company_name,
                search_suffix=search_suffix,
                schema=schema,
                extraction_instructions=f"Find the {label} for {company_name}. Return exact data, no estimates.",
                source_name=f"find_field:{cf}",
                tavily_search_fn=tavily_search_fn,
                llm_extract_fn=llm_extract_fn,
            )
        )
        task_labels.append(f"find_field:{cf}")

    if not tasks:
        return [MicroSkillResult(source="find_field", reasoning="No searchable fields")]

    # Run all in parallel
    results = await asyncio.gather(*tasks, return_exceptions=True)

    out: List[MicroSkillResult] = []
    for i, r in enumerate(results):
        if isinstance(r, Exception):
            logger.warning(f"[FIND_FIELD] {task_labels[i]} failed for {company_name}: {r}")
            out.append(MicroSkillResult(
                source=task_labels[i],
                reasoning=f"{task_labels[i]} failed: {r}",
            ))
        elif isinstance(r, MicroSkillResult):
            out.append(r)

    return out
