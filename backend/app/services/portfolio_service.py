"""
Portfolio Service - Query portfolio companies, metrics, and pacing from Supabase.
Falls back gracefully if Supabase is unavailable.
"""
from typing import List, Dict, Any, Optional, Set
import logging
from datetime import datetime
from difflib import SequenceMatcher

logger = logging.getLogger(__name__)


def _get_client():
    """Get Supabase client or None."""
    try:
        from app.core.database import get_supabase_service
        return get_supabase_service().get_client()
    except Exception:
        return None


class PortfolioService:
    """Portfolio service with real Supabase queries and graceful fallbacks."""

    def _client(self):
        return _get_client()

    async def get_portfolio(self, fund_id: str) -> Dict[str, Any]:
        """Get all portfolio companies for a fund."""
        client = self._client()
        if not client:
            logger.warning("PortfolioService: Supabase unavailable, returning empty portfolio")
            return {"id": fund_id, "companies": [], "total_investments": 0, "total_value": 0}

        try:
            # Join portfolio_companies with companies
            result = client.table("portfolio_companies").select(
                "*, companies(*)"
            ).eq("fund_id", fund_id).execute()

            companies = []
            total_invested = 0
            total_value = 0
            for row in (result.data or []):
                company = row.get("companies") or {}
                companies.append({
                    "company_id": row.get("company_id"),
                    "companyName": company.get("name", ""),
                    "stage": company.get("stage", ""),
                    "sector": company.get("sector", ""),
                    "arr": company.get("current_arr_usd"),
                    "valuation": company.get("current_valuation_usd") or company.get("last_valuation_usd"),
                    "burn_rate": company.get("burn_rate_monthly_usd"),
                    "runway_months": company.get("runway_months"),
                    "employee_count": company.get("employee_count"),
                    "growth_rate": company.get("growth_rate"),
                    "investment_status": row.get("investment_status"),
                    "initial_investment": row.get("initial_investment"),
                    "current_valuation": row.get("current_valuation"),
                    "ownership_percentage": row.get("ownership_percentage"),
                    "unrealized_gain": row.get("unrealized_gain"),
                    "risk_level": row.get("risk_level"),
                })
                total_invested += (row.get("initial_investment") or 0)
                total_value += (row.get("current_valuation") or 0)

            return {
                "id": fund_id,
                "companies": companies,
                "total_investments": total_invested,
                "total_value": total_value,
                "count": len(companies),
            }
        except Exception as e:
            logger.error(f"PortfolioService.get_portfolio failed: {e}")
            return {"id": fund_id, "companies": [], "total_investments": 0, "total_value": 0, "error": str(e)}

    async def get_company_by_name(self, name: str, fund_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Fuzzy match a company by name. No @ prefix required."""
        client = self._client()
        if not client:
            return None

        try:
            query = client.table("companies").select("*")
            if fund_id:
                query = query.eq("fund_id", fund_id)

            # Try exact ilike first
            result = query.ilike("name", f"%{name}%").limit(10).execute()
            candidates = result.data or []

            if not candidates:
                # Broader search: fetch all for fund and fuzzy match
                if fund_id:
                    all_result = client.table("companies").select("id, name, stage, sector, current_arr_usd, current_valuation_usd").eq("fund_id", fund_id).execute()
                    candidates = all_result.data or []
                else:
                    return None

            if len(candidates) == 1:
                return candidates[0]

            # Fuzzy match
            best_match = None
            best_score = 0.0
            name_lower = name.lower().strip().lstrip("@")
            for c in candidates:
                c_name = (c.get("name") or "").lower()
                score = SequenceMatcher(None, name_lower, c_name).ratio()
                # Boost exact substring matches
                if name_lower in c_name or c_name in name_lower:
                    score = max(score, 0.85)
                if score > best_score:
                    best_score = score
                    best_match = c

            if best_match and best_score > 0.4:
                return best_match
            return None
        except Exception as e:
            logger.error(f"PortfolioService.get_company_by_name failed: {e}")
            return None

    async def get_portfolio_metrics(self, fund_id: str) -> Dict[str, Any]:
        """Aggregate NAV, IRR, DPI across portfolio."""
        client = self._client()
        if not client:
            return {"fund_id": fund_id, "error": "Supabase unavailable"}

        try:
            result = client.table("portfolio_companies").select(
                "initial_investment, current_valuation, unrealized_gain, realized_gain, ownership_percentage"
            ).eq("fund_id", fund_id).execute()

            rows = result.data or []
            total_invested = sum(r.get("initial_investment") or 0 for r in rows)
            total_current = sum(r.get("current_valuation") or 0 for r in rows)
            total_realized = sum(r.get("realized_gain") or 0 for r in rows)
            total_unrealized = sum(r.get("unrealized_gain") or 0 for r in rows)

            # Fund-level info
            fund_result = client.table("funds").select("*").eq("id", fund_id).limit(1).execute()
            fund_data = (fund_result.data or [{}])[0] if fund_result.data else {}
            fund_size = fund_data.get("size") or total_invested

            nav = total_current + total_realized
            dpi = total_realized / total_invested if total_invested > 0 else 0
            tvpi = nav / total_invested if total_invested > 0 else 0

            return {
                "fund_id": fund_id,
                "fund_name": fund_data.get("name", ""),
                "fund_size": fund_size,
                "total_invested": total_invested,
                "total_current_value": total_current,
                "total_realized": total_realized,
                "total_unrealized": total_unrealized,
                "nav": nav,
                "dpi": round(dpi, 2),
                "tvpi": round(tvpi, 2),
                "company_count": len(rows),
            }
        except Exception as e:
            logger.error(f"PortfolioService.get_portfolio_metrics failed: {e}")
            return {"fund_id": fund_id, "error": str(e)}

    async def get_portfolio_pacing(self, fund_id: str) -> Dict[str, Any]:
        """Compute deployment pacing from fund commitments and investments."""
        client = self._client()
        if not client:
            return {"fund_id": fund_id, "error": "Supabase unavailable"}

        try:
            # Get fund info
            fund_result = client.table("funds").select("*").eq("id", fund_id).limit(1).execute()
            fund_data = (fund_result.data or [{}])[0] if fund_result.data else {}
            fund_size = fund_data.get("size") or 0

            # Get total deployed
            pc_result = client.table("portfolio_companies").select("initial_investment").eq("fund_id", fund_id).execute()
            deployed = sum(r.get("initial_investment") or 0 for r in (pc_result.data or []))

            remaining = fund_size - deployed
            pct_deployed = deployed / fund_size if fund_size > 0 else 0

            # LP commitments
            lp_result = client.table("lp_fund_commitments").select("commitment_usd, called_usd, distributed_usd").eq("fund_id", fund_id).execute()
            lp_rows = lp_result.data or []
            total_committed = sum(r.get("commitment_usd") or 0 for r in lp_rows)
            total_called = sum(r.get("called_usd") or 0 for r in lp_rows)
            total_distributed = sum(r.get("distributed_usd") or 0 for r in lp_rows)

            return {
                "fund_id": fund_id,
                "fund_size": fund_size,
                "deployed_capital": deployed,
                "remaining_capital": remaining,
                "pct_deployed": round(pct_deployed, 3),
                "total_lp_committed": total_committed,
                "total_lp_called": total_called,
                "total_lp_distributed": total_distributed,
            }
        except Exception as e:
            logger.error(f"PortfolioService.get_portfolio_pacing failed: {e}")
            return {"fund_id": fund_id, "error": str(e)}

    async def calculate_graduation_rates(self, fund_id: str, time_horizon: str = "5y") -> Dict[str, Any]:
        """Calculate stage progression rates across portfolio."""
        client = self._client()
        if not client:
            return {"fund_id": fund_id, "graduation_rate": 0, "time_horizon": time_horizon}

        try:
            result = client.table("portfolio_companies").select(
                "investment_status, companies(stage, current_arr_usd)"
            ).eq("fund_id", fund_id).execute()

            rows = result.data or []
            stage_counts: Dict[str, int] = {}
            for r in rows:
                company = r.get("companies") or {}
                stage = company.get("stage", "unknown")
                stage_counts[stage] = stage_counts.get(stage, 0) + 1

            total = len(rows)
            return {
                "fund_id": fund_id,
                "time_horizon": time_horizon,
                "total_companies": total,
                "stage_distribution": stage_counts,
                "graduation_rate": 0.15 if total == 0 else sum(1 for r in rows if (r.get("companies") or {}).get("stage", "") in ("Series B", "Series C", "Growth", "Late")) / total,
            }
        except Exception as e:
            logger.error(f"PortfolioService.calculate_graduation_rates failed: {e}")
            return {"fund_id": fund_id, "graduation_rate": 0, "time_horizon": time_horizon, "error": str(e)}



    async def get_all_companies(self, limit: int = 100) -> Dict[str, Any]:
        """Get all companies without fund filter -- for when no fundId is available."""
        client = self._client()
        if not client:
            logger.warning("PortfolioService: Supabase unavailable for get_all_companies")
            return {"companies": []}
        try:
            result = client.table("companies").select("*").limit(limit).execute()
            companies = []
            for r in (result.data or []):
                companies.append({
                    "companyName": r.get("name", ""),
                    "company_id": r.get("id"),
                    "stage": r.get("stage"),
                    "sector": r.get("sector"),
                    "arr": r.get("current_arr_usd"),
                    "valuation": r.get("current_valuation_usd") or r.get("last_valuation_usd"),
                    "growth_rate": r.get("growth_rate"),
                    "employee_count": r.get("employee_count"),
                    "burn_rate": r.get("burn_rate_monthly_usd"),
                    "runway_months": r.get("runway_months"),
                })
            return {"companies": companies, "count": len(companies)}
        except Exception as e:
            logger.error(f"PortfolioService.get_all_companies failed: {e}")
            return {"companies": [], "error": str(e)}

    async def search_companies_db(self, query: str, limit: int = 10) -> Dict[str, Any]:
        """Fuzzy search the rich companies table (1k+ companies).

        Searches name, sector, description via ilike for broad matching.
        Returns top matches with key fields for the agent to use.
        """
        client = self._client()
        if not client:
            return {"companies": [], "error": "Supabase unavailable"}
        try:
            # Try exact ilike on name first
            result = client.table("companies").select(
                "id, name, sector, stage, description, current_arr_usd, "
                "current_valuation_usd, last_valuation_usd, total_funding_usd, "
                "growth_rate, employee_count, hq_location, founded_year, "
                "burn_rate_monthly_usd, runway_months, business_model"
            ).ilike("name", f"%{query}%").limit(limit).execute()

            companies = result.data or []

            # If not enough, broaden to sector + description
            if len(companies) < 3:
                broader = client.table("companies").select(
                    "id, name, sector, stage, description, current_arr_usd, "
                    "current_valuation_usd, last_valuation_usd, total_funding_usd, "
                    "growth_rate, employee_count, hq_location, founded_year, "
                    "burn_rate_monthly_usd, runway_months, business_model"
                ).or_(
                    f"sector.ilike.%{query}%,description.ilike.%{query}%"
                ).limit(limit).execute()
                existing_ids = {c.get("id") for c in companies}
                for c in (broader.data or []):
                    if c.get("id") not in existing_ids:
                        companies.append(c)

            formatted = []
            for c in companies[:limit]:
                formatted.append({
                    "company_id": c.get("id"),
                    "name": c.get("name", ""),
                    "sector": c.get("sector", ""),
                    "stage": c.get("stage", ""),
                    "description": c.get("description", ""),
                    "arr": c.get("current_arr_usd"),
                    "valuation": c.get("current_valuation_usd") or c.get("last_valuation_usd"),
                    "total_funding": c.get("total_funding_usd"),
                    "growth_rate": c.get("growth_rate"),
                    "employee_count": c.get("employee_count"),
                    "hq": c.get("hq_location", ""),
                    "founded": c.get("founded_year"),
                    "burn_rate": c.get("burn_rate_monthly_usd"),
                    "runway_months": c.get("runway_months"),
                    "business_model": c.get("business_model", ""),
                })
            return {"companies": formatted, "count": len(formatted), "query": query}
        except Exception as e:
            logger.error(f"PortfolioService.search_companies_db failed: {e}")
            return {"companies": [], "error": str(e)}

    async def get_portfolio_company_names(self, fund_id: Optional[str] = None) -> Set[str]:
        """Return a set of lowercased company names already in the DB.

        Used for deduplication when sourcing new companies.
        If fund_id is provided, scopes to that fund; otherwise returns all names.
        """
        client = self._client()
        if not client:
            return set()
        try:
            query = client.table("companies").select("name")
            if fund_id:
                query = query.eq("fund_id", fund_id)
            result = query.limit(5000).execute()
            return {
                (r.get("name") or "").lower().strip()
                for r in (result.data or [])
                if r.get("name")
            }
        except Exception as e:
            logger.error(f"PortfolioService.get_portfolio_company_names failed: {e}")
            return set()

    async def upsert_company(
        self,
        name: str,
        data: Dict[str, Any],
        fund_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Upsert an enriched company record to the companies table.

        - Deduplicates by name (ilike match within fund scope).
        - Maps enriched field names to DB column names.
        - Only writes non-None fields (never overwrites existing data with None).
        - Overflow fields go into extra_data JSONB.

        Returns: {"id": <uuid>, "name": <str>, "created": bool, "updated_fields": [...]}
        """
        client = self._client()
        if not client:
            return {"error": "Supabase unavailable"}

        # ---- Field mapping: enriched key -> DB column ----
        FIELD_MAP = {
            # Financial
            "arr": "current_arr_usd",
            "revenue": "current_arr_usd",  # arr takes priority, revenue is fallback
            "inferred_revenue": "current_arr_usd",
            "valuation": "current_valuation_usd",
            "inferred_valuation": "current_valuation_usd",
            "total_funding": "total_funding_usd",
            "total_raised": "total_funding_usd",
            "burn_rate": "burn_rate_monthly_usd",
            "burn_rate_monthly": "burn_rate_monthly_usd",
            "cash_in_bank": "cash_in_bank_usd",
            "gross_margin": "gross_margin",
            "growth_rate": "growth_rate",
            "revenue_growth_annual": "revenue_growth_annual_pct",
            "revenue_growth_monthly": "revenue_growth_monthly_pct",
            # Operational
            "team_size": "employee_count",
            "employee_count": "employee_count",
            "stage": "stage",
            "sector": "sector",
            "category": "category",
            "business_model": "business_model",
            "description": "description",
            "product_description": "description",
            "hq_location": "hq_location",
            "hq": "hq_location",
            "headquarters": "hq_location",
            "founded_year": "founded_year",
            "year_founded": "founded_year",
            # Funding cache
            "latest_round_name": "latest_round_name",
            "latest_round_amount": "latest_round_amount_usd",
            "latest_round_date": "latest_round_date",
            # TAM
            "tam": "tam_numeric",
            "tam_description": "tam_description",
            "tam_citation": "tam_citation",
            # AI flags
            "ai_first": "ai_first",
            "ai_category": "ai_category",
            # Runway
            "runway_months": "runway_months",
        }

        # Known DB columns (non-JSONB) — used to decide what goes to extra_data
        KNOWN_COLUMNS = set(FIELD_MAP.values()) | {
            "id", "name", "domain", "fund_id", "user_id", "visibility",
            "created_by", "funding_stage", "last_funding_date", "status",
            "funnel_status", "last_valuation_usd", "metrics", "data",
            "customers", "extra_data", "cached_funding_data",
            "funding_data_updated_at", "investment_lead",
            "last_contacted_date", "typical_dilution", "cost_of_capital",
            "business_model_citation",
        }

        try:
            # ---- Check for existing company (dedup by name) ----
            existing = None
            clean_name = name.strip()
            search = client.table("companies").select("id, name, extra_data")
            if fund_id:
                search = search.eq("fund_id", fund_id)
            result = search.ilike("name", clean_name).limit(5).execute()
            candidates = result.data or []

            # Exact match (case-insensitive)
            for c in candidates:
                if (c.get("name") or "").lower().strip() == clean_name.lower():
                    existing = c
                    break
            # Fallback: close fuzzy match
            if not existing and candidates:
                for c in candidates:
                    ratio = SequenceMatcher(
                        None, clean_name.lower(), (c.get("name") or "").lower()
                    ).ratio()
                    if ratio > 0.9:
                        existing = c
                        break

            # ---- Build DB row from enriched data ----
            row: Dict[str, Any] = {}
            extra_data: Dict[str, Any] = {}

            # Priority ordering: prefer actual over inferred
            # Process arr/revenue first so inferred doesn't overwrite actual
            priority_keys = ["arr", "revenue", "valuation"]
            other_keys = [k for k in data if k not in priority_keys and k not in ("company", "prompt_handle", "requested_company", "_fetched_at")]

            for key in priority_keys + other_keys:
                value = data.get(key)
                if value is None:
                    continue
                # Unwrap InferenceResult objects
                if hasattr(value, "value"):
                    value = value.value
                if value is None:
                    continue

                db_col = FIELD_MAP.get(key)
                if db_col:
                    # Don't overwrite actual with inferred
                    if key.startswith("inferred_") and db_col in row:
                        continue
                    row[db_col] = value
                elif key not in ("company", "prompt_handle", "requested_company",
                                 "_fetched_at", "key_metrics", "funding_rounds",
                                 "competitors", "pwerm_scenarios",
                                 "ownership_evolution", "fund_fit_score",
                                 "fund_fit_reasons"):
                    # Stash complex/unknown fields into extra_data
                    if isinstance(value, (str, int, float, bool, list, dict)):
                        extra_data[key] = value

            # Always set name
            row["name"] = clean_name
            if fund_id:
                row["fund_id"] = fund_id

            # Stash funding rounds in cached_funding_data if present
            funding_rounds = data.get("funding_rounds")
            if funding_rounds and isinstance(funding_rounds, list):
                row["cached_funding_data"] = funding_rounds
                row["funding_data_updated_at"] = datetime.now().isoformat()

            # Stash competitors / fund_fit into extra_data
            for overflow_key in ("competitors", "fund_fit_score", "fund_fit_reasons",
                                 "ownership_evolution", "pwerm_scenarios"):
                val = data.get(overflow_key)
                if val is not None:
                    if hasattr(val, "value"):
                        val = val.value
                    if val is not None:
                        extra_data[overflow_key] = val

            # Merge extra_data with existing
            if existing and existing.get("extra_data"):
                merged_extra = {**(existing["extra_data"] or {}), **extra_data}
            else:
                merged_extra = extra_data
            if merged_extra:
                row["extra_data"] = merged_extra

            # ---- Upsert ----
            updated_fields = [k for k, v in row.items() if v is not None and k not in ("name", "fund_id")]

            if existing:
                # UPDATE: only set non-None fields (don't overwrite with blanks)
                update_row = {k: v for k, v in row.items() if v is not None and k != "name"}
                if update_row:
                    client.table("companies").update(update_row).eq(
                        "id", existing["id"]
                    ).execute()
                logger.info(
                    f"[UPSERT_COMPANY] Updated '{clean_name}' (id={existing['id']}), "
                    f"fields: {updated_fields}"
                )
                return {
                    "id": existing["id"],
                    "name": clean_name,
                    "created": False,
                    "updated_fields": updated_fields,
                }
            else:
                # INSERT
                insert_result = client.table("companies").insert(row).execute()
                new_id = (insert_result.data[0].get("id") if insert_result.data else None)
                logger.info(
                    f"[UPSERT_COMPANY] Created '{clean_name}' (id={new_id}), "
                    f"fields: {updated_fields}"
                )
                return {
                    "id": new_id,
                    "name": clean_name,
                    "created": True,
                    "updated_fields": updated_fields,
                }

        except Exception as e:
            logger.error(f"PortfolioService.upsert_company failed for '{name}': {e}")
            return {"error": str(e), "name": name}


# Global instance
portfolio_service = PortfolioService()
