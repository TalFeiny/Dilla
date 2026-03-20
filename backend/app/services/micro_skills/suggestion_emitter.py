"""
Suggestion Emitter — Persists MicroSkillResult to pending_suggestions DB.

This is the critical piece that makes micro-skill results STICK.
Every skill result flows through here → DB → frontend shows badges.

The current system's problem: _add_pending_suggestion_to_db exists but
is only called in a few places. This emitter is called AUTOMATICALLY
by gap_resolver for every non-empty result.

Column ID mapping: backend field names → frontend grid column IDs.
"""

import logging
from typing import Any, Dict, List, Optional

from . import CitationSource, MicroSkillResult

logger = logging.getLogger(__name__)

# Sentinel UUID used when company_id or fund_id is unknown.
# Keeps existing unique constraints and ON CONFLICT upserts working.
_UNLINKED = "00000000-0000-0000-0000-000000000000"

# Minimum confidence to persist — anything below this is noise
MIN_EMIT_CONFIDENCE = 0.15

# Backend field → Frontend grid column_id mapping
FIELD_TO_COLUMN = {
    # Revenue & financials — use frontend grid column IDs
    "arr": "arr",
    "revenue": "arr",
    "inferred_revenue": "arr",
    "growth_rate": "revenueGrowthAnnual",
    "revenue_growth_annual_pct": "revenueGrowthAnnual",
    "revenue_growth_monthly_pct": "revenueGrowthMonthly",
    "gross_margin": "grossMargin",
    "burn_rate": "burnRate",
    "burn_rate_monthly_usd": "burnRate",
    "runway_months": "runway",
    "cash_balance": "cashInBank",
    "cash_in_bank_usd": "cashInBank",
    # Valuation — frontend uses "valuation", not "currentValuationUsd"
    "valuation": "valuation",
    "inferred_valuation": "valuation",
    "inferred_growth_rate": "revenueGrowthAnnual",
    "inferred_burn_rate": "burnRate",
    "inferred_runway": "runway",
    "inferred_team_size": "headcount",
    "inferred_gross_margin": "grossMargin",
    "valuation_mid": "valuation",
    "current_valuation_usd": "valuation",
    # Funding
    "total_funding": "totalRaised",
    "last_round_amount": "lastRoundAmount",
    "last_round_date": "lastRoundDate",
    "stage": "stage",
    "funding_stage": "stage",
    # Team
    "team_size": "headcount",
    "employee_count": "headcount",
    # Customers
    "customer_count": "customerCount",
    # Company info
    "description": "description",
    "business_model": "businessModel",
    "sector": "sector",
    "hq_location": "hqLocation",
    "founded_year": "foundedYear",
    "target_market": "targetMarket",
    "pricing_model": "pricingModel",
    # Funding rounds
    "funding_rounds": "fundingRounds",
    # Cap table / next round
    "next_round_stage": "nextRoundStage",
    "down_round_risk": "downRoundRisk",
    # TAM/SAM/SOM
    "tam_usd": "tamUsd",
    "sam_usd": "samUsd",
    "som_usd": "somUsd",
    # Search-result fields that should map to grid columns
    "customers": "customers",
    "ceo": "ceo",
    "cto": "cto",
}

# Fields to skip (internal, not grid columns)
SKIP_FIELDS = {
    "valuation_low", "valuation_high", "valuation_methods",
    "comparable_companies", "comparable_multiple",
    "next_round_months", "next_round_size", "next_round_valuation_pre",
    "next_round_valuation_post", "next_round_dilution",
    "investors", "founders", "competitors",
    "notable_customers", "differentiators",
    "market_position", "tam_estimate",
}

# Numeric columns where we can validate ranges
_NUMERIC_VALIDATORS: Dict[str, tuple] = {
    "arr": (0, 1e12),
    "valuation": (0, 1e13),
    "burnRate": (0, 1e10),
    "runway": (0, 120),
    "headcount": (1, 50000),
    "grossMargin": (0, 1),  # 0-1 scale
    "revenueGrowthAnnual": (-1, 50),  # -100% to 5000%
    "revenueGrowthMonthly": (-0.5, 5),
    "totalRaised": (0, 1e12),
    "lastRoundAmount": (0, 1e11),
    "cashInBank": (0, 1e12),
    "tamUsd": (0, 1e14),
    "samUsd": (0, 1e14),
    "somUsd": (0, 1e14),
}


def _normalize_value(column_id: str, value: Any) -> Any:
    """Normalize value for consistency before persisting.

    - growth_rate: ensure decimal form (1.5 not 150)
    - gross_margin: ensure 0-1 scale
    - numeric range validation
    """
    if value is None:
        return None

    # Non-numeric columns pass through
    if column_id not in _NUMERIC_VALIDATORS:
        return value

    # Coerce to number
    if isinstance(value, str):
        try:
            cleaned = value.replace("$", "").replace(",", "").replace("%", "").strip()
            # Handle shorthand: "1.2M", "500K", "2B"
            multiplier = 1
            if cleaned and cleaned[-1].upper() == "M":
                cleaned = cleaned[:-1]
                multiplier = 1_000_000
            elif cleaned and cleaned[-1].upper() == "K":
                cleaned = cleaned[:-1]
                multiplier = 1_000
            elif cleaned and cleaned[-1].upper() == "B":
                cleaned = cleaned[:-1]
                multiplier = 1_000_000_000
            value = float(cleaned) * multiplier
        except (ValueError, AttributeError):
            logger.debug("[SUGGESTION_EMITTER] Cannot parse '%s' as number for %s", value, column_id)
            return None
    if not isinstance(value, (int, float)):
        return value

    # Gross margin: if >1, assume percentage, convert to decimal
    if column_id == "grossMargin" and value > 1:
        value = value / 100

    # Growth rate: if >5 and this looks like a percentage (e.g. 150 for 150%), convert
    if column_id == "revenueGrowthAnnual" and value > 5:
        value = value / 100

    lo, hi = _NUMERIC_VALIDATORS[column_id]
    if value < lo or value > hi:
        logger.debug(
            "[SUGGESTION_EMITTER] Value %s out of range [%s, %s] for column %s — dropped",
            value, lo, hi, column_id,
        )
        return None

    return value


def _get_supabase_client():
    """Get Supabase client or None. Lazy import to avoid circular deps."""
    try:
        from app.core.database import get_supabase_service
        svc = get_supabase_service()
        if svc:
            client = svc.get_client()
            if not client:
                logger.warning("[SUGGESTION_EMITTER] get_supabase_service().get_client() returned None — DB not initialized")
            return client
    except Exception as e:
        logger.warning("[SUGGESTION_EMITTER] Failed to get Supabase client: %s", e, exc_info=True)
    return None


def _build_row(
    field_name: str,
    value: Any,
    result: MicroSkillResult,
    company_id: str,
    fund_id: str,
) -> Optional[Dict]:
    """Build a single pending_suggestions row dict, or None if invalid."""
    if value is None or field_name in SKIP_FIELDS:
        return None

    column_id = FIELD_TO_COLUMN.get(field_name)
    if not column_id:
        return None

    # Normalize and validate
    normalized = _normalize_value(column_id, value)
    if normalized is None:
        return None

    # JSONB columns accept dicts directly
    if isinstance(normalized, (list, dict)):
        serialized = normalized
    else:
        serialized = {"value": normalized}

    return {
        "fund_id": fund_id or _UNLINKED,
        "company_id": company_id or _UNLINKED,
        "column_id": column_id,
        "suggested_value": serialized,
        "source_service": f"micro_skill:{result.source}",
        "reasoning": result.reasoning[:500],
        "metadata": {
            "confidence": result.confidence,
            "citations": [
                c.to_dict() if isinstance(c, CitationSource) else {"url": c}
                for c in result.citations[:5]
            ],
            "skill": result.source,
            **(result.metadata if result.metadata else {}),
        },
    }


async def emit_suggestions(
    result: MicroSkillResult,
    company_id: str,
    fund_id: str,
    company_name: str = "",
) -> int:
    """Persist a MicroSkillResult to pending_suggestions table.

    Batches all field_updates into a single upsert call.
    Skips results below MIN_EMIT_CONFIDENCE.
    Returns count of suggestions written.
    """
    if not result.has_data():
        return 0

    if result.confidence < MIN_EMIT_CONFIDENCE:
        logger.debug(f"[SUGGESTION_EMITTER] Skipping {company_name}/{result.source}: confidence {result.confidence:.2f} < {MIN_EMIT_CONFIDENCE}")
        return 0

    sb = _get_supabase_client()
    if not sb:
        logger.warning("[SUGGESTION_EMITTER] Supabase unavailable — suggestions not persisted")
        return 0

    # Build all rows first, then batch upsert
    rows = []
    for field_name, value in result.field_updates.items():
        row = _build_row(field_name, value, result, company_id, fund_id)
        if row:
            rows.append(row)

    if not rows:
        return 0

    # Deduplicate by column_id within this result — keep last (most specific)
    seen: Dict[str, Dict] = {}
    for row in rows:
        seen[row["column_id"]] = row
    rows = list(seen.values())

    try:
        sb.table("pending_suggestions").upsert(
            rows,
            on_conflict="fund_id,company_id,column_id",
        ).execute()
        logger.info(f"[SUGGESTION_EMITTER] Persisted {len(rows)} suggestions for {company_name} via {result.source}")
        return len(rows)
    except Exception as e:
        logger.warning(f"[SUGGESTION_EMITTER] Batch upsert failed for {company_name}: {e}")
        # Fall back to individual upserts
        written = 0
        for row in rows:
            try:
                sb.table("pending_suggestions").upsert(
                    row,
                    on_conflict="fund_id,company_id,column_id",
                ).execute()
                written += 1
            except Exception as e2:
                logger.warning(f"[SUGGESTION_EMITTER] Write failed for {company_name}.{row['column_id']}: {e2}")
        return written


async def emit_batch(
    results: List[MicroSkillResult],
    company_id: str,
    fund_id: str,
    company_name: str = "",
) -> int:
    """Persist multiple MicroSkillResults in a single batch upsert.

    Deduplicates by column_id across all results — keeps highest confidence.
    """
    sb = _get_supabase_client()
    if not sb:
        logger.warning("[SUGGESTION_EMITTER] Supabase unavailable — suggestions not persisted")
        return 0

    # Collect all rows across all results, keeping highest confidence per column_id
    best_rows: Dict[str, tuple] = {}  # column_id → (confidence, row_dict)

    for r in results:
        if not r.has_data() or r.confidence < MIN_EMIT_CONFIDENCE:
            continue
        for field_name, value in r.field_updates.items():
            row = _build_row(field_name, value, r, company_id, fund_id)
            if not row:
                continue
            col_id = row["column_id"]
            existing = best_rows.get(col_id)
            if not existing or r.confidence > existing[0]:
                best_rows[col_id] = (r.confidence, row)

    if not best_rows:
        return 0

    rows = [row for _, row in best_rows.values()]

    try:
        sb.table("pending_suggestions").upsert(
            rows,
            on_conflict="fund_id,company_id,column_id",
        ).execute()
        logger.info(f"[SUGGESTION_EMITTER] Batch persisted {len(rows)} suggestions for {company_name}")
        return len(rows)
    except Exception as e:
        logger.warning(f"[SUGGESTION_EMITTER] Batch upsert failed for {company_name}: {e}")
        # Fall back to individual
        written = 0
        for row in rows:
            try:
                sb.table("pending_suggestions").upsert(
                    row,
                    on_conflict="fund_id,company_id,column_id",
                ).execute()
                written += 1
            except Exception as e2:
                logger.warning(f"[SUGGESTION_EMITTER] Write failed for {company_name}.{row['column_id']}: {e2}")
        return written


def _flatten_extracted_data(extracted_data: Dict[str, Any]) -> Dict[str, Any]:
    """Flatten nested extracted_data into a flat field_updates dict.

    Maps the normalized extraction structure (financial_metrics, company_info,
    growth_metrics, operational_metrics, market_size, etc.) to flat field names
    that FIELD_TO_COLUMN can resolve.
    """
    fields: Dict[str, Any] = {}

    # financial_metrics
    fm = extracted_data.get("financial_metrics") or {}
    for key in ("arr", "revenue", "burn_rate", "runway_months", "cash_balance", "gross_margin", "growth_rate"):
        v = fm.get(key)
        if v is not None:
            fields[key] = v
    # mrr → arr conversion when arr is missing
    if "arr" not in fields and "revenue" not in fields:
        mrr = fm.get("mrr")
        if mrr is not None:
            fields["arr"] = mrr * 12
    # customer_count from financial_metrics as backup
    if "customer_count" not in fields and fm.get("customer_count") is not None:
        fields["customer_count"] = fm["customer_count"]

    # growth_metrics
    gm = extracted_data.get("growth_metrics") or {}
    if gm.get("current_arr") and "arr" not in fields:
        fields["arr"] = gm["current_arr"]
    if gm.get("revenue_growth_annual_pct"):
        fields["revenue_growth_annual_pct"] = gm["revenue_growth_annual_pct"]
    if gm.get("revenue_growth_monthly_pct"):
        fields["revenue_growth_monthly_pct"] = gm["revenue_growth_monthly_pct"]

    # company_info
    ci = extracted_data.get("company_info") or {}
    for src, dst in [("valuation", "valuation"), ("sector", "sector"), ("stage", "stage"),
                     ("funding_raised", "total_funding"), ("business_model", "business_model"),
                     ("industry", "sector")]:
        v = ci.get(src)
        if v is not None and dst not in fields:
            fields[dst] = v

    # operational_metrics
    om = extracted_data.get("operational_metrics") or {}
    if om.get("headcount"):
        fields["team_size"] = om["headcount"]
    if om.get("customer_count"):
        fields["customer_count"] = om["customer_count"]
    # new_hires → infer headcount delta when headcount itself is missing
    if "team_size" not in fields:
        new_hires = om.get("new_hires")
        if isinstance(new_hires, list) and new_hires:
            fields["team_size"] = {"delta": len(new_hires)}
        elif isinstance(new_hires, str) and new_hires.strip():
            # "3 new hires" or comma-separated names
            parts = [p.strip() for p in new_hires.split(",") if p.strip()]
            fields["team_size"] = {"delta": max(len(parts), 1)}
        elif isinstance(new_hires, (int, float)) and new_hires > 0:
            fields["team_size"] = {"delta": int(new_hires)}
    # enterprise + smb → total customer_count
    if "customer_count" not in fields:
        ent = om.get("enterprise_customers")
        smb = om.get("smb_customers")
        if ent is not None or smb is not None:
            fields["customer_count"] = (ent or 0) + (smb or 0)

    # market_size
    ms = extracted_data.get("market_size")
    if isinstance(ms, dict):
        for key in ("tam_usd", "sam_usd", "som_usd"):
            if ms.get(key):
                fields[key] = ms[key]

    # runway_and_cash (backup if financial_metrics didn't have them)
    rc = extracted_data.get("runway_and_cash") or {}
    for src, dst in [("runway_months", "runway_months"), ("cash_in_bank", "cash_balance"), ("burn_rate", "burn_rate")]:
        v = rc.get(src)
        if v is not None and dst not in fields:
            fields[dst] = v

    # top-level fields (flat/memo shapes store these at root, signal shapes also have business_model/sector/category)
    for key in ("arr", "revenue", "valuation", "stage", "sector", "target_market", "business_model", "total_funding", "category"):
        v = extracted_data.get(key)
        if v is not None and isinstance(v, (str, int, float)) and key not in fields:
            fields[key] = v

    # impact_estimates — per-metric deltas from the LLM transformation layer.
    # When financial_metrics left a field None, the impact estimate is still
    # a usable signal.  Store as {"delta": value} so the suggestion pipeline
    # and frontend know this is a change, not an absolute.
    ie = extracted_data.get("impact_estimates")
    if isinstance(ie, dict):
        _IMPACT_TO_FIELD = {
            "estimated_arr_impact": "arr",
            "estimated_burn_impact": "burn_rate",
            "estimated_runway_impact": "runway_months",
            "estimated_headcount_impact": "team_size",
            "estimated_cash_impact": "cash_balance",
            "estimated_valuation_impact": "valuation",
            "estimated_growth_rate_change": "growth_rate",
        }
        for impact_key, field_key in _IMPACT_TO_FIELD.items():
            if field_key in fields:
                continue  # absolute value already present, skip delta
            v = ie.get(impact_key)
            if v is not None and v != 0:
                fields[field_key] = {"delta": v}

    # ── Signal-shape qualitative fields ──
    # For board updates / monthly updates the model often fills qualitative
    # arrays (achievements, risks, product_updates) and business_updates but
    # leaves financial_metrics empty.  Capture the usable text fields so
    # they still become suggestions on the grid.

    # business_updates.latest_update → description
    bu = extracted_data.get("business_updates")
    if isinstance(bu, dict):
        lu = bu.get("latest_update")
        if lu and isinstance(lu, str) and lu.strip() and "description" not in fields:
            fields["description"] = lu.strip()

        # Synthesise from achievements / product_updates when latest_update is empty
        if "description" not in fields:
            parts: list = []
            for key in ("achievements", "product_updates", "key_milestones"):
                items = bu.get(key)
                if isinstance(items, list) and items:
                    parts.extend([str(x).strip() for x in items[:3] if x])
            if parts:
                fields["description"] = "; ".join(parts[:4])

    # Top-level summary as fallback description
    summary = extracted_data.get("summary")
    if summary and isinstance(summary, str) and summary.strip() and "description" not in fields:
        fields["description"] = summary.strip()

    # extracted_entities — customer names, key people
    ee = extracted_data.get("extracted_entities")
    if isinstance(ee, dict):
        custs = ee.get("customers") or ee.get("key_customers") or ee.get("notable_customers")
        if isinstance(custs, list) and custs and "customers" not in fields:
            fields["customers"] = ", ".join([str(c) for c in custs[:10] if c])
        for person_key in ("ceo", "cto"):
            pv = ee.get(person_key)
            if pv and isinstance(pv, str) and person_key not in fields:
                fields[person_key] = pv

    # operational_metrics — headcount / customer_count from extracted_entities
    if isinstance(ee, dict):
        hc = ee.get("headcount") or ee.get("employee_count") or ee.get("team_size")
        if hc is not None and "team_size" not in fields:
            fields["team_size"] = hc
        cc = ee.get("customer_count") or ee.get("number_of_customers")
        if cc is not None and "customer_count" not in fields:
            fields["customer_count"] = cc

    if not fields:
        # Debug: log what nested dicts actually contained so we can diagnose
        fm_keys = [k for k, v in (extracted_data.get("financial_metrics") or {}).items() if v is not None]
        om_keys = [k for k, v in (extracted_data.get("operational_metrics") or {}).items() if v is not None]
        ie_keys = [k for k, v in (extracted_data.get("impact_estimates") or {}).items() if v is not None and v != 0]
        logger.info(
            "[SUGGESTION_EMITTER] _flatten debug: fm_non_null=%s, om_non_null=%s, ie_non_null=%s",
            fm_keys, om_keys, ie_keys,
        )

    return fields


def emit_document_suggestions(
    extracted_data: Dict[str, Any],
    company_id: str,
    fund_id: str,
    document_id: str,
    document_name: str = "",
) -> int:
    """Transform extracted_data into per-metric pending_suggestions rows.

    Called after document extraction completes. Flattens the nested extraction
    output, creates one pending_suggestions row per valid metric, and persists
    via upsert. Uses value_explanations for per-metric reasoning.

    Synchronous — called from run_document_process() which already runs in
    its own thread/event-loop.
    """
    if not extracted_data:
        return 0

    field_updates = _flatten_extracted_data(extracted_data)
    if not field_updates:
        logger.info(
            "[SUGGESTION_EMITTER] No fields flattened from document %s. "
            "Keys present: %s",
            document_id,
            list(extracted_data.keys())[:10],
        )
        return 0

    logger.info(
        "[SUGGESTION_EMITTER] Flattened %d fields from document %s: %s",
        len(field_updates), document_id, list(field_updates.keys()),
    )

    value_explanations = extracted_data.get("value_explanations") or {}
    # impact_reasoning provides per-metric reasoning (with quotes) from the LLM
    ie = extracted_data.get("impact_estimates")
    impact_reasoning_raw = (ie.get("impact_reasoning") if isinstance(ie, dict) else None) or {}

    # Build a lookup that maps both impact key names AND field names to reasoning.
    # LLM returns keys like "estimated_arr_impact" but field_updates uses "arr".
    _IMPACT_KEY_TO_FIELD = {
        "estimated_arr_impact": "arr",
        "estimated_burn_impact": "burn_rate",
        "estimated_runway_impact": "runway_months",
        "estimated_headcount_impact": "team_size",
        "estimated_cash_impact": "cash_balance",
        "estimated_valuation_impact": "valuation",
        "estimated_growth_rate_change": "growth_rate",
    }
    impact_reasoning: Dict[str, str] = {}
    for ik, reasoning_text in impact_reasoning_raw.items():
        if not isinstance(reasoning_text, str):
            continue
        impact_reasoning[ik] = reasoning_text
        # Also index by the field name so lookup works later
        field_alias = _IMPACT_KEY_TO_FIELD.get(ik)
        if field_alias:
            impact_reasoning[field_alias] = reasoning_text
            # And by column_id
            col = FIELD_TO_COLUMN.get(field_alias)
            if col:
                impact_reasoning[col] = reasoning_text

    sb = _get_supabase_client()
    if not sb:
        logger.warning("[SUGGESTION_EMITTER] Supabase unavailable — document suggestions not persisted")
        return 0

    rows = []
    dropped_fields: Dict[str, str] = {}
    for field_name, value in field_updates.items():
        if value is None or field_name in SKIP_FIELDS:
            dropped_fields[field_name] = "none/skip"
            continue

        column_id = FIELD_TO_COLUMN.get(field_name)
        if not column_id:
            dropped_fields[field_name] = "no_column_mapping"
            continue

        normalized = _normalize_value(column_id, value)
        if normalized is None:
            dropped_fields[field_name] = f"normalization_failed(raw={value})"
            continue

        if isinstance(normalized, (list, dict)):
            serialized = normalized
        else:
            serialized = {"value": normalized}

        # Per-metric reasoning: value_explanations first, then impact_reasoning (now properly indexed)
        reasoning = (
            value_explanations.get(field_name)
            or value_explanations.get(column_id)
            or impact_reasoning.get(field_name)
            or impact_reasoning.get(column_id)
            or ""
        )
        # For qualitative fields (description, sector, etc.), synthesise reasoning
        # from the document's red_flags / implications / business_updates context.
        if not reasoning and field_name in ("description", "sector", "business_model", "target_market", "customers", "ceo", "cto"):
            parts = []
            bu = extracted_data.get("business_updates") or {}
            if bu.get("latest_update"):
                parts.append(f"Update: {bu['latest_update']}")
            red = extracted_data.get("red_flags")
            if isinstance(red, list) and red:
                parts.append(f"Red flags: {'; '.join(str(r) for r in red[:2])}")
            impl = extracted_data.get("implications")
            if isinstance(impl, list) and impl:
                parts.append(f"Implications: {'; '.join(str(i) for i in impl[:2])}")
            reasoning = " | ".join(parts) if parts else ""
        if not reasoning:
            reasoning = f"Extracted from document: {document_name}" if document_name else "Extracted from uploaded document"

        rows.append({
            "fund_id": fund_id or _UNLINKED,
            "company_id": company_id or _UNLINKED,
            "column_id": column_id,
            "suggested_value": serialized,
            "source_service": f"document:{document_id}",
            "reasoning": reasoning[:500],
            "metadata": {
                "confidence": 0.85,
                "document_id": document_id,
                "document_name": document_name,
                "source_type": "document_extraction",
            },
        })

    if dropped_fields:
        logger.info("[SUGGESTION_EMITTER] Dropped %d fields for doc %s: %s",
                    len(dropped_fields), document_id,
                    {k: v for k, v in list(dropped_fields.items())[:15]})

    if not rows:
        logger.info("[SUGGESTION_EMITTER] No valid rows after normalization for doc %s "
                    "(total fields=%d, dropped=%d)",
                    document_id, len(field_updates), len(dropped_fields))
        return 0

    # Deduplicate by column_id — keep last
    seen_dedup: Dict[str, Dict] = {}
    for row in rows:
        seen_dedup[row["column_id"]] = row
    rows = list(seen_dedup.values())

    try:
        sb.table("pending_suggestions").upsert(
            rows,
            on_conflict="fund_id,company_id,column_id",
        ).execute()
        logger.info(f"[SUGGESTION_EMITTER] Persisted {len(rows)} document suggestions for doc {document_id}")
        return len(rows)
    except Exception as e:
        logger.warning(f"[SUGGESTION_EMITTER] Document suggestion upsert failed for {document_id}: {e}")
        written = 0
        for row in rows:
            try:
                sb.table("pending_suggestions").upsert(
                    row,
                    on_conflict="fund_id,company_id,column_id",
                ).execute()
                written += 1
            except Exception as e2:
                logger.warning(f"[SUGGESTION_EMITTER] Write failed for doc {document_id}.{row['column_id']}: {e2}")
        return written


def build_grid_commands(result: MicroSkillResult, company_name: str) -> List[Dict]:
    """Convert MicroSkillResult to grid_commands for frontend (non-DB path).

    Used when suggestions should go through the frontend's
    handleGridCommandsFromBackend → addServiceSuggestion() pipeline
    instead of direct DB writes.

    Now includes metadata (is_correction, old_value, etc.) for richer frontend display.
    """
    if result.confidence < MIN_EMIT_CONFIDENCE:
        return []

    commands = []
    for field_name, value in result.field_updates.items():
        if value is None or field_name in SKIP_FIELDS:
            continue
        column_id = FIELD_TO_COLUMN.get(field_name)
        if not column_id:
            continue

        normalized = _normalize_value(column_id, value)
        if normalized is None:
            continue

        cmd = {
            "type": "suggest_edit",
            "companyName": company_name,
            "columnId": column_id,
            "value": normalized,
            "reasoning": result.reasoning[:200],
            "confidence": result.confidence,
            "source": f"micro_skill:{result.source}",
            "citations": [
                c.to_dict() if isinstance(c, CitationSource) else {"url": c}
                for c in result.citations[:3]
            ],
        }

        # Pass through metadata for corrections and other enrichments
        if result.metadata:
            if result.metadata.get("is_correction"):
                cmd["isCorrection"] = True
            if "old_value" in result.metadata:
                cmd["oldValue"] = result.metadata["old_value"]
            if "deviation_pct" in result.metadata:
                cmd["deviationPct"] = result.metadata["deviation_pct"]

        commands.append(cmd)

    return commands


# ---------------------------------------------------------------------------
# Legal clause emitter — writes extracted clauses to the legal grid
# Same pending_suggestions pipeline, same accept/reject/reasoning as financial
# ---------------------------------------------------------------------------

# Legal field → Frontend legal grid column_id mapping
LEGAL_FIELD_TO_COLUMN = {
    "clauseId": "clauseId",
    "title": "title",
    "clauseType": "clauseType",
    "text": "text",
    "party": "party",
    "counterparty": "counterparty",
    "flags": "flags",
    "obligationDesc": "obligationDesc",
    "obligationDeadline": "obligationDeadline",
    "crossRefService": "crossRefService",
    "crossRefField": "crossRefField",
    "crossRefValue": "crossRefValue",
    "erpCategory": "erpCategory",
    "erpSubcategory": "erpSubcategory",
    "annualValue": "annualValue",
    "monthlyAmount": "monthlyAmount",
    "documentName": "documentName",
    "reasoning": "reasoning",
}


def _build_clause_reasoning(clause: Dict, value_explanations: Dict, document_name: str) -> str:
    """Build reasoning for a clause: prefer LLM's value_explanation (actual analysis),
    fall back to flags. Never just copy raw clause text — that's useless to the user.
    """
    clause_id = clause.get("id", "")
    clause_type = clause.get("clause_type", "other")

    # Best case: LLM wrote a real explanation for this clause
    explanation = (
        value_explanations.get(clause_id)
        or value_explanations.get(clause_type)
    )
    if explanation:
        return explanation[:500]

    # Second best: flags are now natural-language, so they ARE the reasoning
    flags = clause.get("flags", [])
    if flags:
        return " · ".join(flags)[:500]

    # Obligations as reasoning
    obligations = clause.get("obligations", [])
    if obligations:
        desc = obligations[0].get("description", "")
        if desc:
            return desc[:500]

    # Last resort — just say what we found
    title = clause.get("title") or clause_type
    return f"Extracted from {document_name}: {title}"


def emit_legal_suggestions(
    extracted_data: Dict[str, Any],
    company_id: str,
    fund_id: str,
    document_id: str,
    document_name: str = "",
) -> int:
    """Transform legal extraction into per-clause pending_suggestions rows.

    Called after legal document extraction completes. Each clause becomes one
    row in pending_suggestions, keyed by (fund_id, company_id, column_id)
    where column_id encodes the clause ID for uniqueness.

    Uses the same accept/reject/reasoning pipeline as financial suggestions —
    the frontend shows badges, evidence chains, and source attribution.

    Synchronous — called from run_document_process() in its own thread.
    """
    if not extracted_data:
        return 0

    clauses = extracted_data.get("clauses")
    if not isinstance(clauses, list) or not clauses:
        logger.info("[LEGAL_EMITTER] No clauses in extraction for doc %s", document_id)
        return 0

    value_explanations = extracted_data.get("value_explanations") or {}
    erp = extracted_data.get("erp_attribution") or {}
    parties = extracted_data.get("parties") or []
    doc_type = extracted_data.get("document_type") or "contract"

    sb = _get_supabase_client()
    if not sb:
        logger.warning("[LEGAL_EMITTER] Supabase unavailable — legal suggestions not persisted")
        return 0

    rows = []
    for clause in clauses:
        if not isinstance(clause, dict):
            continue

        clause_id = clause.get("id", "")
        if not clause_id:
            continue

        # Build the reasoning chain: quote → flags → impact
        reasoning = _build_clause_reasoning(clause, value_explanations, document_name)

        # Primary obligation (first one if multiple)
        obligations = clause.get("obligations") or []
        primary_ob = obligations[0] if obligations else {}

        # Primary cross-reference
        xrefs = clause.get("cross_references") or []
        primary_xref = xrefs[0] if xrefs else {}

        # Party / counterparty from obligation or from document-level parties list
        party = primary_ob.get("party", "")
        counterparty = ""
        if not party and parties:
            party = parties[0].get("name", "")
        if len(parties) >= 2:
            # Second party in the list is the counterparty
            counterparty = parties[1].get("name", "")
        elif not counterparty:
            # Try clause-level counterparty if present
            counterparty = clause.get("counterparty", "")

        # Flags as comma-separated string for the grid
        flags = clause.get("flags") or []
        flags_str = ", ".join(flags) if flags else ""

        # Document-level dates/values (not per-clause in most contracts)
        doc_effective_date = extracted_data.get("effective_date")
        doc_expiry_date = extracted_data.get("expiration_date") or extracted_data.get("expiry_date")
        doc_total_value = (
            extracted_data.get("investment_amount")
            or erp.get("annual_value")
            or extracted_data.get("valuation_post_money")
        )

        # Build the clause row — field names match LEGAL_COLUMNS grid IDs
        clause_fields = {
            "clauseId": clause_id,
            "documentName": document_name or f"doc:{document_id}",
            "contractType": clause.get("clause_type", "other"),
            "party": party,
            "counterparty": counterparty,
            "status": "active",
            "effectiveDate": doc_effective_date,
            "expiryDate": doc_expiry_date or primary_ob.get("deadline"),
            "totalValue": doc_total_value,
            "annualValue": erp.get("annual_value"),
            "keyTerms": clause.get("title", ""),
            "flags": flags_str,
            "obligations": primary_ob.get("description", ""),
            "nextDeadline": primary_ob.get("deadline"),
            "reasoning": reasoning,
        }

        # Confidence — flagged clauses get higher confidence (flags are now free-form)
        confidence = 0.80
        if flags:
            confidence = 0.85

        # Each clause → one row keyed by legal:{clauseId} so each clause
        # is a distinct suggestion the user can accept/reject individually
        column_id = f"legal:{clause_id}"

        rows.append({
            "fund_id": fund_id or _UNLINKED,
            "company_id": company_id or _UNLINKED,
            "column_id": column_id,
            "suggested_value": clause_fields,
            "source_service": f"document:{document_id}",
            "reasoning": reasoning,
            "metadata": {
                "confidence": confidence,
                "document_id": document_id,
                "document_name": document_name,
                "document_type": doc_type,
                "source_type": "legal_extraction",
                "clause_type": clause.get("clause_type", "other"),
                "flags": flags,
                "parent_clause_id": clause.get("parent_id"),
                "children_clause_ids": clause.get("children", []),
                "all_obligations": obligations,
                "all_cross_references": xrefs,
            },
        })

    if not rows:
        logger.info("[LEGAL_EMITTER] No valid clause rows for doc %s", document_id)
        return 0

    try:
        sb.table("pending_suggestions").upsert(
            rows,
            on_conflict="fund_id,company_id,column_id",
        ).execute()
        logger.info(f"[LEGAL_EMITTER] Persisted {len(rows)} clause suggestions for doc {document_id}")
        return len(rows)
    except Exception as e:
        logger.warning(f"[LEGAL_EMITTER] Clause upsert failed for {document_id}: {e}")
        # Fall back to individual upserts
        written = 0
        for row in rows:
            try:
                sb.table("pending_suggestions").upsert(
                    row,
                    on_conflict="fund_id,company_id,column_id",
                ).execute()
                written += 1
            except Exception as e2:
                logger.warning(f"[LEGAL_EMITTER] Write failed for {document_id}.{row['column_id']}: {e2}")
        return written


# ---------------------------------------------------------------------------
# Cap table suggestion emitter
# ---------------------------------------------------------------------------


def emit_cap_table_suggestions(
    cap_table_result: Dict[str, Any],
    company_id: str,
    fund_id: str,
    document_id: str,
    document_name: str = "",
) -> int:
    """
    Transform cap table bridge output into per-shareholder pending_suggestions rows.

    Each shareholder entry becomes one row keyed as cap_table:{shareholder_id}:{share_class}.
    Same accept/reject pipeline as legal suggestions.

    Synchronous — called from document processing.
    Returns count of suggestions written.
    """
    if not cap_table_result:
        return 0

    entries = cap_table_result.get("share_entries")
    if not isinstance(entries, list) or not entries:
        logger.info("[CAP_TABLE_EMITTER] No share entries for doc %s", document_id)
        return 0

    sb = _get_supabase_client()
    if not sb:
        logger.warning("[CAP_TABLE_EMITTER] Supabase unavailable")
        return 0

    rows = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue

        holder_id = entry.get("shareholder_id", "")
        share_class = entry.get("share_class", "unknown")
        if not holder_id:
            continue

        column_id = f"cap_table:{holder_id}:{share_class}"

        rights = entry.get("rights", {})
        vesting = entry.get("vesting", {})

        suggested_value = {
            "shareholder": entry.get("shareholder_name", ""),
            "shareClass": share_class,
            "numShares": entry.get("num_shares"),
            "pricePer": entry.get("price_per_share"),
            "investment": None,
            "liquidationPref": f"{rights.get('liquidation_preference', 1.0)}x {'participating' if rights.get('participation_rights') else 'non-participating'}",
            "antiDilution": rights.get("anti_dilution", "none"),
            "boardSeats": rights.get("board_seats", 0),
            "vesting": f"{vesting.get('total_months', 48)}mo / {vesting.get('cliff_months', 12)}mo cliff" if vesting else "",
            "proRata": rights.get("pro_rata_rights", False),
            "sourceDocument": document_name or document_id,
        }

        # Calculate investment if we have shares and price
        try:
            shares = float(entry.get("num_shares", 0))
            price = float(entry.get("price_per_share", 0))
            if shares and price:
                suggested_value["investment"] = shares * price
        except (ValueError, TypeError):
            pass

        reasoning = (
            f"{entry.get('shareholder_name', 'Unknown')} — "
            f"{share_class} — "
            f"from {document_name or document_id}"
        )

        rows.append({
            "fund_id": fund_id or _UNLINKED,
            "company_id": company_id or _UNLINKED,
            "column_id": column_id,
            "suggested_value": suggested_value,
            "source_service": f"document:{document_id}",
            "reasoning": reasoning[:500],
            "metadata": {
                "confidence": 0.85,
                "document_id": document_id,
                "document_name": document_name,
                "source_type": "cap_table_extraction",
                "shareholder_id": holder_id,
                "share_class": share_class,
            },
        })

    if not rows:
        logger.info("[CAP_TABLE_EMITTER] No valid rows for doc %s", document_id)
        return 0

    try:
        sb.table("pending_suggestions").upsert(
            rows,
            on_conflict="fund_id,company_id,column_id",
        ).execute()
        logger.info(f"[CAP_TABLE_EMITTER] Persisted {len(rows)} cap table suggestions for doc {document_id}")
        return len(rows)
    except Exception as e:
        logger.warning(f"[CAP_TABLE_EMITTER] Upsert failed for {document_id}: {e}")
        written = 0
        for row in rows:
            try:
                sb.table("pending_suggestions").upsert(
                    row,
                    on_conflict="fund_id,company_id,column_id",
                ).execute()
                written += 1
            except Exception as e2:
                logger.warning(f"[CAP_TABLE_EMITTER] Write failed for {document_id}.{row['column_id']}: {e2}")
        return written
