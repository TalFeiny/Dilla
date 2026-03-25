"""
Cap Table Ledger Service

The cap table equivalent of fpa_actuals. Reads/writes individual cap_table_entries
rows and computes aggregate views (ownership %, equity/debt weights, totals).

Data flows in from:
  - Manual entry (portfolio grid)
  - CSV import (bulk_upsert)
  - Legal doc extraction (legal_cap_table_bridge)

Consumers:
  - CapTableSection / StakeholderSection (memo)
  - unified_financial_state (CapTableSummary)
  - strategic_intelligence_service (WACC weights)
  - waterfall_advanced / valuation_engine (share entries)
"""

from __future__ import annotations

import logging
from decimal import Decimal
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Fields that are safe to write from external input
_WRITABLE_FIELDS = {
    "shareholder_name", "stakeholder_type", "instrument_type", "share_class",
    "num_shares", "price_per_share", "round_name", "investment_date",
    "liquidation_pref", "participating", "participation_cap", "anti_dilution",
    "voting_rights", "board_seat", "pro_rata_rights",
    "vesting_cliff_months", "vesting_total_months", "vested_pct",
    "outstanding_principal", "interest_rate", "coupon_type", "maturity_date",
    "seniority", "secured", "collateral", "amortization_type", "covenants",
    "cross_default",
    "conversion_discount", "valuation_cap", "qualified_financing",
    "auto_convert", "mfn",
    "exercise_price", "warrant_coverage_pct", "underlying_class",
    "expiry_date", "cashless_exercise",
    "pik_rate", "cash_rate", "pik_toggle_type",
    "repayment_cap", "revenue_share_pct",
    "source", "document_id", "notes",
    "fund_id", "is_debt_instrument",
}

_DEBT_TYPES = frozenset({
    "debt", "convertible", "pik", "revenue_based", "mezzanine", "revolver",
})


def _get_sb():
    """Lazy import to avoid circular deps at module load."""
    try:
        from app.core.supabase_client import get_supabase_client
        return get_supabase_client()
    except Exception:
        logger.warning("Supabase client unavailable")
        return None


def _sanitize(entry: dict) -> dict:
    """Filter to writable fields only and auto-set is_debt_instrument."""
    clean = {k: v for k, v in entry.items() if k in _WRITABLE_FIELDS and v is not None}
    # Auto-compute is_debt_instrument from instrument_type
    it = clean.get("instrument_type", entry.get("instrument_type", "equity"))
    clean["is_debt_instrument"] = it in _DEBT_TYPES
    return clean


class CapTableLedger:
    """CRUD + aggregation for cap_table_entries."""

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def load(
        self,
        company_id: str,
        fund_id: Optional[str] = None,
        view: str = "company",
    ) -> dict:
        """Load all entries for a company and compute aggregates.

        Args:
            company_id: Target company.
            fund_id: If view='investor', filter to this fund's entries.
            view: 'company' (all entries) or 'investor' (fund's entries + others aggregated).

        Returns:
            {share_entries, ownership, total_raised, equity_weight, debt_weight,
             total_equity, total_debt, debt_instruments, entry_count}
        """
        sb = _get_sb()
        if not sb:
            return self._empty()

        try:
            q = sb.table("cap_table_entries").select("*").eq("company_id", company_id)
            rows = q.execute().data or []
        except Exception as e:
            logger.error("cap_table_entries load failed: %s", e)
            return self._empty()

        if not rows:
            return self._empty()

        # Compute total shares for ownership %
        total_shares = sum(
            Decimal(str(r.get("num_shares", 0)))
            for r in rows
            if not r.get("is_debt_instrument")
        )

        # Build enriched entries
        entries = []
        total_equity_value = Decimal("0")
        total_debt_value = Decimal("0")
        total_raised = Decimal("0")
        ownership_map: Dict[str, float] = {}
        debt_instruments: List[dict] = []

        for r in rows:
            shares = Decimal(str(r.get("num_shares", 0)))
            pps = Decimal(str(r.get("price_per_share", 0)))
            is_debt = r.get("is_debt_instrument", False)
            principal = Decimal(str(r.get("outstanding_principal") or 0))
            inv_amount = Decimal(str(r.get("investment_amount") or 0))

            # Ownership %
            if total_shares > 0 and not is_debt:
                own_pct = float((shares / total_shares) * 100)
            else:
                own_pct = 0.0

            r["ownership_pct"] = round(own_pct, 4)

            if is_debt:
                val = principal if principal > 0 else inv_amount
                total_debt_value += val
                total_raised += val
                debt_instruments.append(r)
            else:
                total_equity_value += inv_amount
                total_raised += inv_amount

            name = r.get("shareholder_name", "Unknown")
            if not is_debt:
                ownership_map[name] = ownership_map.get(name, 0.0) + own_pct

            entries.append(r)

        # Equity / debt weights
        if total_raised > 0:
            equity_weight = float(total_equity_value / total_raised)
            debt_weight = float(total_debt_value / total_raised)
        else:
            equity_weight = 1.0
            debt_weight = 0.0

        # Investor view: filter to fund's entries, aggregate others
        if view == "investor" and fund_id:
            mine = [e for e in entries if e.get("fund_id") == fund_id]
            others = [e for e in entries if e.get("fund_id") != fund_id]
            if others:
                other_shares = sum(Decimal(str(e.get("num_shares", 0))) for e in others)
                other_own = sum(e.get("ownership_pct", 0) for e in others)
                agg = {
                    "shareholder_name": "Other shareholders",
                    "stakeholder_type": "other",
                    "num_shares": float(other_shares),
                    "ownership_pct": round(other_own, 4),
                    "share_class": "various",
                    "instrument_type": "equity",
                }
                mine.append(agg)
            entries = mine

        return {
            "share_entries": entries,
            "ownership": {k: round(v, 2) for k, v in ownership_map.items()},
            "total_raised": float(total_raised),
            "total_equity": float(total_equity_value),
            "total_debt": float(total_debt_value),
            "equity_weight": round(equity_weight, 4),
            "debt_weight": round(debt_weight, 4),
            "debt_instruments": debt_instruments,
            "entry_count": len(rows),
        }

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    def upsert_row(self, company_id: str, entry: dict) -> dict:
        """Upsert a single cap table entry (manual grid edit)."""
        sb = _get_sb()
        if not sb:
            return {"success": False, "reason": "no_db"}

        data = _sanitize(entry)
        data["company_id"] = company_id
        if "source" not in data:
            data["source"] = "manual"

        try:
            if entry.get("id"):
                # Update existing
                result = (
                    sb.table("cap_table_entries")
                    .update(data)
                    .eq("id", entry["id"])
                    .execute()
                )
            else:
                # Insert new
                result = (
                    sb.table("cap_table_entries")
                    .insert(data)
                    .execute()
                )
            row = result.data[0] if result.data else {}
            return {"success": True, "entry": row}
        except Exception as e:
            logger.error("cap_table_entries upsert failed: %s", e)
            return {"success": False, "reason": str(e)}

    def bulk_upsert(
        self,
        company_id: str,
        entries: List[dict],
        fund_id: Optional[str] = None,
        source: str = "csv",
    ) -> dict:
        """Bulk insert entries (CSV import or legal extraction).

        Deletes existing entries for the same company+source before inserting
        to avoid duplicates (same pattern as fpa_actuals CSV upload).
        """
        sb = _get_sb()
        if not sb:
            return {"success": False, "reason": "no_db"}

        try:
            # Clear previous entries from same source
            q = (
                sb.table("cap_table_entries")
                .delete()
                .eq("company_id", company_id)
                .eq("source", source)
            )
            if fund_id:
                q = q.eq("fund_id", fund_id)
            q.execute()

            # Prepare rows
            rows = []
            for e in entries:
                data = _sanitize(e)
                data["company_id"] = company_id
                data["source"] = source
                if fund_id:
                    data["fund_id"] = fund_id
                rows.append(data)

            if not rows:
                return {"success": True, "inserted": 0}

            # Batch insert (Supabase handles up to ~1000 rows)
            result = sb.table("cap_table_entries").insert(rows).execute()
            inserted = len(result.data) if result.data else 0

            return {"success": True, "inserted": inserted}
        except Exception as e:
            logger.error("cap_table_entries bulk_upsert failed: %s", e)
            return {"success": False, "reason": str(e)}

    # ------------------------------------------------------------------
    # Delete
    # ------------------------------------------------------------------

    def delete_row(self, entry_id: str) -> dict:
        """Delete a single cap table entry."""
        sb = _get_sb()
        if not sb:
            return {"success": False, "reason": "no_db"}

        try:
            sb.table("cap_table_entries").delete().eq("id", entry_id).execute()
            return {"success": True}
        except Exception as e:
            logger.error("cap_table_entries delete failed: %s", e)
            return {"success": False, "reason": str(e)}

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _empty() -> dict:
        return {
            "share_entries": [],
            "ownership": {},
            "total_raised": 0,
            "total_equity": 0,
            "total_debt": 0,
            "equity_weight": 1.0,
            "debt_weight": 0.0,
            "debt_instruments": [],
            "entry_count": 0,
        }
