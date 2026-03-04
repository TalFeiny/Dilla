"""
TP Comparable Service — Find and score comparable companies for transfer pricing.

Three sources, layered:
  1. Portfolio DB — extend similar_companies() with FAR-based scoring
  2. Public comps via yfinance — pull PLI data for listed companies
  3. Web search — Tavily + LLM extraction for sector/geography/function matches

Scores candidates on OECD 5 comparability factors (0-10 each):
  product/service similarity, functional comparability (FAR), contractual terms,
  economic circumstances, business strategy.

Stores results in tp_comparable_searches + tp_comparables with rejection log.
"""

import json
import logging
from typing import Any, Callable, Dict, List, Optional

from app.core.database import supabase_service
from app.services.far_analysis_service import (
    FARAnalysisService,
    FUNCTION_TAXONOMY,
    _parse_json_response,
    _ensure_list,
)

logger = logging.getLogger(__name__)

# ── PLI extraction helpers ───────────────────────────────────────────

def _safe_div(num: float, den: float) -> Optional[float]:
    if not den:
        return None
    return round(num / den, 4)


def _compute_pli_from_financials(fin: Dict) -> Dict[str, Optional[float]]:
    """Compute standard PLIs from a financials dict (revenue, cogs, opex, etc.)."""
    revenue = float(fin.get("revenue", 0) or 0)
    cogs = abs(float(fin.get("cogs", 0) or 0))
    opex = abs(float(fin.get("opex", 0) or 0))
    gp = float(fin.get("gross_profit", revenue - cogs))
    op = float(fin.get("operating_profit", gp - opex))
    total_assets = float(fin.get("total_assets", 0) or 0)
    total_costs = cogs + opex

    return {
        "operating_margin": _safe_div(op, revenue),
        "gross_margin": _safe_div(gp, revenue),
        "berry_ratio": _safe_div(gp, opex) if opex else None,
        "markup_on_total_costs": _safe_div(op, total_costs) if total_costs else None,
        "net_cost_plus": _safe_div(op, total_costs) if total_costs else None,
        "return_on_assets": _safe_div(op, total_assets) if total_assets else None,
        "revenue": revenue,
    }


# ── Source 1: Portfolio comparables ──────────────────────────────────

async def _search_portfolio(
    transaction: Dict,
    tested_entity: Dict,
    tested_far: Optional[Dict],
    far_service: FARAnalysisService,
    company_id: str,
) -> List[Dict]:
    """Find comparable entities from the portfolio DB.

    Extends the similar_companies() pattern from benchmark_skills with
    FAR-based scoring and entity-level financial data.
    """
    client = supabase_service.get_client()

    # Get all entities across ALL portfolio companies (excluding current group)
    all_entities = client.from_("company_entities") \
        .select("id, name, company_id, entity_type, jurisdiction, functional_role") \
        .neq("company_id", company_id) \
        .execute().data or []

    if not all_entities:
        return []

    # Get FAR profiles for candidates
    entity_ids = [e["id"] for e in all_entities]
    profiles_resp = client.from_("entity_far_profiles") \
        .select("entity_id, functions, assets, risks, narrative, confidence") \
        .in_("entity_id", entity_ids) \
        .execute()
    profile_map = {}
    for p in (profiles_resp.data or []):
        for key in ("functions", "assets", "risks"):
            p[key] = _ensure_list(p.get(key))
        profile_map[p["entity_id"]] = p

    # Get financials for candidates (latest period aggregates)
    fin_resp = client.from_("entity_financials") \
        .select("entity_id, category, amount") \
        .in_("entity_id", entity_ids) \
        .execute()
    fin_map: Dict[str, Dict[str, float]] = {}
    for f in (fin_resp.data or []):
        eid = f["entity_id"]
        if eid not in fin_map:
            fin_map[eid] = {}
        cat = f.get("category", "")
        fin_map[eid][cat] = fin_map[eid].get(cat, 0) + float(f.get("amount", 0) or 0)

    txn_type = transaction.get("transaction_type", "")
    tested_type = tested_entity.get("entity_type", "")
    tested_jurisdiction = tested_entity.get("jurisdiction", "")

    candidates = []
    for e in all_entities:
        score_detail = {}

        # 1. Entity type match (proxy for product/service similarity)
        if e.get("entity_type") == tested_type:
            score_detail["product_service"] = 7
        elif e.get("entity_type") in ("operating",) and tested_type in ("operating",):
            score_detail["product_service"] = 5
        else:
            score_detail["product_service"] = 3

        # 2. FAR comparability
        candidate_far = profile_map.get(e["id"])
        if candidate_far and tested_far:
            far_result = far_service.compare_far_profiles(tested_far, candidate_far)
            score_detail["functional"] = far_result["score"]
        else:
            score_detail["functional"] = 4  # neutral when unknown

        # 3. Contractual terms (approximate from transaction type)
        # Entities in similar transaction types score higher
        candidate_txns = client.from_("intercompany_transactions") \
            .select("transaction_type") \
            .or_(f"from_entity_id.eq.{e['id']},to_entity_id.eq.{e['id']}") \
            .execute().data or []
        candidate_txn_types = {t.get("transaction_type") for t in candidate_txns}
        if txn_type in candidate_txn_types:
            score_detail["contractual"] = 7
        elif candidate_txn_types:
            score_detail["contractual"] = 4
        else:
            score_detail["contractual"] = 3

        # 4. Economic circumstances (jurisdiction, size proximity)
        econ_score = 5
        if e.get("jurisdiction") == tested_jurisdiction:
            econ_score += 2
        # Revenue proximity
        tested_rev = float((fin_map.get(tested_entity["id"]) or {}).get("revenue", 0) or 0)
        cand_rev = float((fin_map.get(e["id"]) or {}).get("revenue", 0) or 0)
        if tested_rev > 0 and cand_rev > 0:
            ratio = max(tested_rev, cand_rev) / max(min(tested_rev, cand_rev), 1)
            if ratio < 2:
                econ_score += 2
            elif ratio < 5:
                econ_score += 1
        score_detail["economic"] = min(econ_score, 10)

        # 5. Business strategy (approximation)
        score_detail["business_strategy"] = 5  # neutral default for portfolio comps

        composite = (
            score_detail.get("product_service", 0) * 0.20 +
            score_detail.get("functional", 0) * 0.30 +
            score_detail.get("contractual", 0) * 0.15 +
            score_detail.get("economic", 0) * 0.20 +
            score_detail.get("business_strategy", 0) * 0.15
        )

        # Extract PLI data
        pli = _compute_pli_from_financials(fin_map.get(e["id"], {}))

        candidates.append({
            "candidate_name": e.get("name", ""),
            "candidate_source": "portfolio",
            "candidate_source_id": e["id"],
            "score_product_service": score_detail.get("product_service", 0),
            "score_functional": round(score_detail.get("functional", 0)),
            "score_contractual": score_detail.get("contractual", 0),
            "score_economic": score_detail.get("economic", 0),
            "score_business_strategy": score_detail.get("business_strategy", 0),
            "composite_score": round(composite, 2),
            "financials": pli,
            "data_quality": "unaudited",
            "entity_type": e.get("entity_type"),
            "jurisdiction": e.get("jurisdiction"),
        })

    # Sort by composite and return top candidates
    candidates.sort(key=lambda x: x["composite_score"], reverse=True)
    return candidates[:20]


# ── Source 2: Public comps via yfinance ──────────────────────────────

async def _search_yfinance(
    sector: str,
    entity_type: str,
    tickers: Optional[List[str]] = None,
) -> List[Dict]:
    """Pull PLI data from yfinance for public company comparables.

    Uses sector to find relevant tickers if none provided.
    """
    try:
        import yfinance as yf
    except ImportError:
        logger.warning("[TP_COMP] yfinance not installed")
        return []

    # Sector → default tickers mapping (expandable)
    _SECTOR_TICKERS = {
        "saas": ["CRM", "WDAY", "NOW", "ADBE", "TEAM", "ZS", "DDOG", "NET"],
        "fintech": ["SQ", "PYPL", "AFRM", "SOFI", "BILL", "ADYEN.AS"],
        "healthtech": ["VEEV", "HIMS", "TDOC", "DOCS", "OSCR"],
        "e-commerce": ["SHOP", "MELI", "ETSY", "W", "BIGC"],
        "enterprise": ["ORCL", "SAP", "IBM", "PLTR", "SNOW"],
        "consumer": ["SPOT", "NFLX", "DIS", "RBLX", "U"],
        "biotech": ["MRNA", "REGN", "VRTX", "GILD", "AMGN"],
        "cleantech": ["ENPH", "SEDG", "RUN", "FSLR", "PLUG"],
        "manufacturing": ["HON", "MMM", "GE", "CAT", "DE"],
        "distribution": ["FAST", "GWW", "WSO", "POOL", "HD"],
    }

    if not tickers:
        sector_key = (sector or "").lower().replace(" ", "_")
        tickers = _SECTOR_TICKERS.get(sector_key, [])
        if not tickers:
            # Try partial match
            for k, v in _SECTOR_TICKERS.items():
                if k in sector_key or sector_key in k:
                    tickers = v
                    break

    if not tickers:
        return []

    results = []
    for ticker_symbol in tickers[:10]:
        try:
            ticker = yf.Ticker(ticker_symbol)
            info = ticker.info or {}
            financials = ticker.financials

            if financials is None or financials.empty:
                continue

            # Extract multi-year PLI data
            years_data = {}
            financial_years = []
            for col in financials.columns[:3]:  # Last 3 years
                year = str(col.year) if hasattr(col, 'year') else str(col)[:4]
                financial_years.append(year)

                revenue = float(financials.loc["Total Revenue", col]) if "Total Revenue" in financials.index else 0
                gp = float(financials.loc["Gross Profit", col]) if "Gross Profit" in financials.index else 0
                op = float(financials.loc["Operating Income", col]) if "Operating Income" in financials.index else 0
                total_expense = float(financials.loc["Total Expenses", col]) if "Total Expenses" in financials.index else 0

                if revenue > 0:
                    years_data[year] = {
                        "operating_margin": round(op / revenue, 4),
                        "gross_margin": round(gp / revenue, 4),
                        "revenue": revenue,
                    }
                    if total_expense > 0:
                        years_data[year]["berry_ratio"] = round(gp / total_expense, 4)
                        years_data[year]["markup_on_total_costs"] = round(op / total_expense, 4)

            if not years_data:
                continue

            # Average PLIs across years
            avg_pli = {}
            for metric in ("operating_margin", "gross_margin", "berry_ratio", "markup_on_total_costs"):
                values = [y[metric] for y in years_data.values() if metric in y]
                if values:
                    avg_pli[metric] = round(sum(values) / len(values), 4)

            avg_pli["revenue"] = sum(y.get("revenue", 0) for y in years_data.values()) / len(years_data)

            results.append({
                "candidate_name": info.get("shortName", ticker_symbol),
                "candidate_source": "yfinance",
                "candidate_source_id": ticker_symbol,
                "financials": avg_pli,
                "financial_years": financial_years,
                "financials_by_year": years_data,
                "data_quality": "audited",
                "sector": info.get("sector", ""),
                "industry": info.get("industry", ""),
                "country": info.get("country", ""),
                "market_cap": info.get("marketCap"),
                "employees": info.get("fullTimeEmployees"),
            })
        except Exception as e:
            logger.debug(f"[TP_COMP] yfinance failed for {ticker_symbol}: {e}")
            continue

    return results


# ── Source 3: Web search for comparables ─────────────────────────────

async def _search_web_comparables(
    entity_name: str,
    entity_type: str,
    sector: str,
    jurisdiction: str,
    transaction_type: str,
    tavily_search_fn: Optional[Callable] = None,
    llm_fn: Optional[Callable] = None,
) -> List[Dict]:
    """Search web for comparable companies using Tavily + LLM extraction.

    Follows the _search_and_extract pattern from search_skills.py.
    """
    if not tavily_search_fn or not llm_fn:
        return []

    queries = [
        f"{sector} {entity_type} companies {jurisdiction} transfer pricing comparable",
        f"{sector} {transaction_type} service provider operating margin benchmark",
    ]

    all_results = []
    for query in queries:
        try:
            search_result = await tavily_search_fn(query)
            results = search_result.get("results", [])
            if not results:
                continue

            search_text = "\n\n".join(
                f"Source: {r.get('url', '')}\nTitle: {r.get('title', '')}\n{r.get('content', '')}"
                for r in results[:5]
            )[:4000]

            extraction_prompt = f"""From these search results, identify companies that could serve as transfer pricing comparables for a {entity_type} entity performing {transaction_type} in the {sector} sector ({jurisdiction}).

{search_text}

For each comparable company found, extract:
- name: company name
- description: what they do (1 sentence)
- sector: their industry
- country: headquarters country
- revenue_estimate: approximate annual revenue in USD (null if unknown)
- operating_margin_estimate: approximate operating margin as decimal (null if unknown)
- source_url: where you found this info

Return JSON array of companies. Return [] if none found. JUST JSON, NO FENCES."""

            raw = await llm_fn(
                extraction_prompt,
                "Extract comparable company data. Return JSON array only.",
            )
            parsed = _parse_json_response(raw)
            if isinstance(parsed, list):
                for comp in parsed:
                    if not isinstance(comp, dict) or not comp.get("name"):
                        continue
                    pli = {}
                    if comp.get("operating_margin_estimate") is not None:
                        pli["operating_margin"] = float(comp["operating_margin_estimate"])
                    if comp.get("revenue_estimate") is not None:
                        pli["revenue"] = float(comp["revenue_estimate"])

                    all_results.append({
                        "candidate_name": comp["name"],
                        "candidate_source": "web_search",
                        "candidate_source_id": comp.get("source_url", ""),
                        "financials": pli,
                        "data_quality": "estimated",
                        "sector": comp.get("sector", ""),
                        "country": comp.get("country", ""),
                        "description": comp.get("description", ""),
                    })
        except Exception as e:
            logger.warning(f"[TP_COMP] Web search failed for query '{query}': {e}")
            continue

    return all_results


# ── OECD 5-factor scoring ────────────────────────────────────────────

async def _score_candidate(
    candidate: Dict,
    tested_entity: Dict,
    tested_far: Optional[Dict],
    transaction: Dict,
    far_service: FARAnalysisService,
    llm_fn: Optional[Callable] = None,
) -> Dict:
    """Score a candidate on the OECD 5 comparability factors.

    Portfolio candidates may already have scores; yfinance/web candidates need scoring.
    """
    # If already scored (portfolio source), return as-is
    if candidate.get("score_functional") is not None and candidate.get("candidate_source") == "portfolio":
        return candidate

    scores = {}

    # 1. Product/service similarity — approximate from sector/type
    if candidate.get("sector", "").lower() == (tested_entity.get("sector") or tested_entity.get("entity_type") or "").lower():
        scores["product_service"] = 7
    elif candidate.get("industry", "").lower() in (tested_entity.get("functional_role") or "").lower():
        scores["product_service"] = 6
    else:
        scores["product_service"] = 4

    # 2. Functional comparability — if we have FAR for both, use it
    if tested_far and candidate.get("_far_profile"):
        far_result = far_service.compare_far_profiles(tested_far, candidate["_far_profile"])
        scores["functional"] = far_result["score"]
    else:
        scores["functional"] = 5  # neutral

    # 3. Contractual terms — hard to assess from public data
    scores["contractual"] = 5

    # 4. Economic circumstances
    econ = 5
    tested_jurisdiction = tested_entity.get("jurisdiction", "")
    cand_country = candidate.get("country") or candidate.get("jurisdiction", "")
    if tested_jurisdiction and cand_country:
        if tested_jurisdiction.lower() == cand_country.lower():
            econ += 2
        # Same broad region
        eu = {"gb", "ie", "de", "fr", "nl", "be", "es", "it", "at", "ch", "se", "dk", "no", "fi", "pl", "cz", "pt"}
        if tested_jurisdiction.lower() in eu and cand_country.lower() in eu:
            econ += 1
    scores["economic"] = min(econ, 10)

    # 5. Business strategy
    scores["business_strategy"] = 5

    # LLM refinement if available
    if llm_fn and (candidate.get("description") or candidate.get("candidate_name")):
        try:
            prompt = f"""Score this candidate company as a transfer pricing comparable (0-10 each factor).

TESTED ENTITY: {tested_entity.get('name', '')} ({tested_entity.get('entity_type', '')}, {tested_entity.get('jurisdiction', '')})
Transaction: {transaction.get('transaction_type', '')} — {transaction.get('description', '')}

CANDIDATE: {candidate.get('candidate_name', '')}
Sector: {candidate.get('sector', '')}
Country: {candidate.get('country', '')}
Description: {candidate.get('description', '')}
Financials: {json.dumps(candidate.get('financials', {}), default=str)}

Return JSON: {{"product_service": int, "functional": int, "contractual": int, "economic": int, "business_strategy": int, "reasoning": "1 sentence"}}
JUST JSON."""
            raw = await llm_fn(prompt, "Score TP comparability. 0-10 per factor. JSON only.")
            parsed = _parse_json_response(raw)
            if parsed:
                for k in ("product_service", "functional", "contractual", "economic", "business_strategy"):
                    if k in parsed and isinstance(parsed[k], (int, float)):
                        scores[k] = min(max(int(parsed[k]), 0), 10)
        except Exception:
            pass  # Keep rule-based scores

    composite = (
        scores.get("product_service", 0) * 0.20 +
        scores.get("functional", 0) * 0.30 +
        scores.get("contractual", 0) * 0.15 +
        scores.get("economic", 0) * 0.20 +
        scores.get("business_strategy", 0) * 0.15
    )

    candidate["score_product_service"] = scores.get("product_service", 0)
    candidate["score_functional"] = scores.get("functional", 0)
    candidate["score_contractual"] = scores.get("contractual", 0)
    candidate["score_economic"] = scores.get("economic", 0)
    candidate["score_business_strategy"] = scores.get("business_strategy", 0)
    candidate["composite_score"] = round(composite, 2)

    return candidate


# ── Rejection logic ──────────────────────────────────────────────────

def _apply_rejection_filters(
    candidates: List[Dict],
    min_composite: float = 3.5,
    min_functional: int = 3,
    require_financials: bool = True,
) -> List[Dict]:
    """Apply acceptance/rejection with documented reasons (regulatory requirement).

    Every excluded company needs a logged reason per OECD guidelines.
    """
    for c in candidates:
        reasons = []

        if c.get("composite_score", 0) < min_composite:
            reasons.append(f"Composite score {c.get('composite_score', 0):.1f} below threshold {min_composite}")
        if c.get("score_functional", 0) < min_functional:
            reasons.append(f"Functional score {c.get('score_functional', 0)} below minimum {min_functional}")
        if require_financials and not c.get("financials"):
            reasons.append("No financial data available for PLI computation")

        # Check for zero/missing PLI data
        fin = c.get("financials", {})
        if fin and not any(v for k, v in fin.items() if k != "revenue" and v is not None):
            reasons.append("No usable PLI data (all margins null)")

        if reasons:
            c["accepted"] = False
            c["rejection_reason"] = "; ".join(reasons)
        else:
            c["accepted"] = True
            c["rejection_reason"] = None

    return candidates


# ── Main service class ───────────────────────────────────────────────

class TPComparableService:
    """Orchestrates comparable search across portfolio, yfinance, and web."""

    def __init__(
        self,
        llm_fn: Optional[Callable] = None,
        tavily_search_fn: Optional[Callable] = None,
    ):
        self.llm_fn = llm_fn
        self.tavily_search_fn = tavily_search_fn
        self.far_service = FARAnalysisService(llm_fn=llm_fn)

    async def search_comparables(
        self,
        transaction_id: str,
        sector: Optional[str] = None,
        tickers: Optional[List[str]] = None,
        min_composite: float = 3.5,
        include_web: bool = True,
    ) -> Dict[str, Any]:
        """Run full comparable search for an IC transaction.

        Returns search results with OECD 5-factor scores and rejection log.
        """
        client = supabase_service.get_client()

        # Load transaction and tested party
        txn = client.from_("intercompany_transactions") \
            .select("*") \
            .eq("id", transaction_id) \
            .single().execute().data
        if not txn:
            raise ValueError(f"Transaction {transaction_id} not found")

        company_id = txn["company_id"]
        # Determine tested party — prefer flagged entity, else use the simpler side
        tested_entity_id = txn.get("from_entity_id")  # default
        tested_resp = client.from_("company_entities") \
            .select("*") \
            .eq("id", tested_entity_id) \
            .single().execute()
        tested_entity = tested_resp.data

        # Check if the other side is flagged as tested party
        other_id = txn.get("to_entity_id")
        other_resp = client.from_("company_entities") \
            .select("*") \
            .eq("id", other_id) \
            .single().execute()
        if other_resp.data and other_resp.data.get("is_tested_party"):
            tested_entity_id = other_id
            tested_entity = other_resp.data

        # Get tested party FAR profile
        tested_far = await self.far_service.get_profile(tested_entity_id)

        # Create search record
        search_params = {
            "sector": sector,
            "tickers": tickers,
            "transaction_type": txn.get("transaction_type"),
            "tested_entity_type": tested_entity.get("entity_type"),
            "jurisdiction": tested_entity.get("jurisdiction"),
        }
        search_row = client.from_("tp_comparable_searches").insert({
            "transaction_id": transaction_id,
            "tested_party_entity_id": tested_entity_id,
            "search_params": json.dumps(search_params),
            "status": "running",
        }).execute().data[0]
        search_id = search_row["id"]

        try:
            all_candidates = []

            # Source 1: Portfolio
            portfolio_comps = await _search_portfolio(
                txn, tested_entity, tested_far, self.far_service, company_id
            )
            all_candidates.extend(portfolio_comps)
            logger.info(f"[TP_COMP] Portfolio: {len(portfolio_comps)} candidates")

            # Source 2: yfinance
            yf_comps = await _search_yfinance(
                sector or tested_entity.get("entity_type", ""),
                tested_entity.get("entity_type", ""),
                tickers,
            )
            # Score yfinance candidates
            for c in yf_comps:
                await _score_candidate(c, tested_entity, tested_far, txn, self.far_service, self.llm_fn)
            all_candidates.extend(yf_comps)
            logger.info(f"[TP_COMP] yfinance: {len(yf_comps)} candidates")

            # Source 3: Web search
            if include_web and self.tavily_search_fn:
                web_comps = await _search_web_comparables(
                    tested_entity.get("name", ""),
                    tested_entity.get("entity_type", ""),
                    sector or "",
                    tested_entity.get("jurisdiction", ""),
                    txn.get("transaction_type", ""),
                    self.tavily_search_fn,
                    self.llm_fn,
                )
                for c in web_comps:
                    await _score_candidate(c, tested_entity, tested_far, txn, self.far_service, self.llm_fn)
                all_candidates.extend(web_comps)
                logger.info(f"[TP_COMP] Web search: {len(web_comps)} candidates")

            # Apply rejection filters
            all_candidates = _apply_rejection_filters(all_candidates, min_composite=min_composite)

            # Sort: accepted first, then by composite score
            all_candidates.sort(key=lambda x: (x.get("accepted", False), x.get("composite_score", 0)), reverse=True)

            # Save to DB
            for c in all_candidates:
                row = {
                    "search_id": search_id,
                    "candidate_name": c.get("candidate_name", ""),
                    "candidate_source": c.get("candidate_source", ""),
                    "candidate_source_id": c.get("candidate_source_id", ""),
                    "score_product_service": c.get("score_product_service"),
                    "score_functional": c.get("score_functional"),
                    "score_contractual": c.get("score_contractual"),
                    "score_economic": c.get("score_economic"),
                    "score_business_strategy": c.get("score_business_strategy"),
                    "composite_score": c.get("composite_score"),
                    "accepted": c.get("accepted", True),
                    "rejection_reason": c.get("rejection_reason"),
                    "financials": json.dumps(c.get("financials", {})),
                    "financial_years": json.dumps(c.get("financial_years", [])),
                    "data_quality": c.get("data_quality", "estimated"),
                }
                try:
                    client.from_("tp_comparables").insert(row).execute()
                except Exception as e:
                    logger.warning(f"[TP_COMP] Failed to save comparable {c.get('candidate_name')}: {e}")

            # Mark search complete
            client.from_("tp_comparable_searches") \
                .update({"status": "completed", "completed_at": "now()"}) \
                .eq("id", search_id).execute()

            accepted = [c for c in all_candidates if c.get("accepted")]
            rejected = [c for c in all_candidates if not c.get("accepted")]

            return {
                "search_id": search_id,
                "transaction_id": transaction_id,
                "tested_party": tested_entity.get("name"),
                "total_candidates": len(all_candidates),
                "accepted": len(accepted),
                "rejected": len(rejected),
                "candidates": all_candidates,
                "accepted_candidates": accepted,
                "rejection_log": [
                    {"name": c["candidate_name"], "reason": c["rejection_reason"]}
                    for c in rejected
                ],
            }

        except Exception as e:
            client.from_("tp_comparable_searches") \
                .update({"status": "failed"}) \
                .eq("id", search_id).execute()
            raise

    async def get_search_results(self, search_id: str) -> Dict[str, Any]:
        """Retrieve saved comparable search results."""
        client = supabase_service.get_client()

        search = client.from_("tp_comparable_searches") \
            .select("*") \
            .eq("id", search_id) \
            .single().execute().data
        if not search:
            raise ValueError(f"Search {search_id} not found")

        comps = client.from_("tp_comparables") \
            .select("*") \
            .eq("search_id", search_id) \
            .order("composite_score", desc=True) \
            .execute().data or []

        for c in comps:
            for key in ("financials", "financial_years"):
                if isinstance(c.get(key), str):
                    try:
                        c[key] = json.loads(c[key])
                    except (json.JSONDecodeError, TypeError):
                        pass

        accepted = [c for c in comps if c.get("accepted")]
        rejected = [c for c in comps if not c.get("accepted")]

        return {
            "search": search,
            "total_candidates": len(comps),
            "accepted": len(accepted),
            "rejected": len(rejected),
            "candidates": comps,
            "accepted_candidates": accepted,
            "rejection_log": [
                {"name": c["candidate_name"], "reason": c.get("rejection_reason")}
                for c in rejected
            ],
        }

    async def update_comparable_status(
        self, comparable_id: str, accepted: bool, rejection_reason: Optional[str] = None
    ) -> Dict:
        """Manual accept/reject of a comparable (user override)."""
        client = supabase_service.get_client()
        update = {"accepted": accepted}
        if not accepted and rejection_reason:
            update["rejection_reason"] = rejection_reason
        elif accepted:
            update["rejection_reason"] = None

        resp = client.from_("tp_comparables") \
            .update(update) \
            .eq("id", comparable_id) \
            .execute()
        return resp.data[0] if resp.data else update
