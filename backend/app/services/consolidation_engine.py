"""
Consolidation Engine — multi-entity P&L consolidation with IC elimination.

Uses:
- group_structure_intelligence.py → entity tree, relationships, ownership
- pnl_builder.py → per-entity P&L
- ic_transaction_suggestions table → IC flows to eliminate

Consolidation methods (IFRS/GAAP):
  - Full (>50% ownership): sum everything, eliminate IC, book minority interest
  - Equity method (20-50%): single line "share of associate profit"
  - None (<20%): not consolidated
"""

from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class EliminationEntry:
    """A single IC elimination adjustment."""
    source_entity_id: str
    target_entity_id: str
    category: str               # revenue, cogs, opex_rd, etc.
    subcategory: Optional[str]
    period: str                 # "YYYY-MM"
    amount: float               # amount eliminated (positive = reduced)
    description: str            # "IC revenue elimination: OpCo → HoldCo management fee"
    source_document_id: Optional[str] = None


@dataclass
class ConsolidatedPnL:
    """Result of group consolidation."""
    # Per-entity P&Ls (before elimination)
    entity_pnls: Dict[str, Dict[str, Dict[str, float]]]  # entity_id → {key → {period → amount}}
    # Summed P&L (before elimination)
    combined: Dict[str, Dict[str, float]]                 # {key → {period → amount}}
    # IC eliminations applied
    eliminations: List[EliminationEntry]
    # Final consolidated P&L (after elimination)
    consolidated: Dict[str, Dict[str, float]]             # {key → {period → amount}}
    # Entities included
    entities_consolidated: List[str]                       # fully consolidated entity IDs
    entities_equity_method: List[str]                      # equity-method entity IDs
    # Minority interest adjustments
    minority_interest: Dict[str, Dict[str, float]]         # {period → amount} per minority entity
    # Periods covered
    periods: List[str]
    # Audit trail
    audit: List[str]


class ConsolidationEngine:
    """Consolidates P&L across a group of entities with IC elimination."""

    def __init__(self, company_id: str, fund_id: Optional[str] = None):
        self.company_id = company_id
        self.fund_id = fund_id

    async def consolidate_pnl(
        self,
        parent_entity_id: str,
        period_start: Optional[str] = None,
        period_end: Optional[str] = None,
    ) -> ConsolidatedPnL:
        """
        Build consolidated P&L for a group headed by parent_entity_id.

        Steps:
        1. Resolve entity tree from group_structure_intelligence
        2. Classify entities: full consolidation vs equity method vs excluded
        3. Pull P&L for each fully-consolidated entity via PnlBuilder
        4. Sum all entity P&Ls
        5. Fetch IC transactions and eliminate matching revenue/cost pairs
        6. Compute minority interest for <100% owned subsidiaries
        7. Return consolidated P&L with full audit trail
        """
        audit: List[str] = []

        # 1. Resolve entity tree
        entities, relationships = await self._resolve_entity_tree(parent_entity_id)
        if not entities:
            audit.append(f"No entities found for parent {parent_entity_id}")
            return self._empty_result(audit)

        # 2. Classify by consolidation method
        full_entities: List[str] = []
        equity_entities: List[str] = []
        ownership_map: Dict[str, float] = {}  # entity_id → ownership %

        for rel in relationships:
            eid = rel["to_entity_id"]
            ownership = rel.get("ownership_pct", 100.0)
            ownership_map[eid] = ownership

            consolidation = rel.get("consolidation", self._infer_consolidation(ownership))
            if consolidation == "full":
                full_entities.append(eid)
            elif consolidation == "equity_method":
                equity_entities.append(eid)

        # Always include parent
        if parent_entity_id not in full_entities:
            full_entities.insert(0, parent_entity_id)
            ownership_map[parent_entity_id] = 100.0

        audit.append(f"Full consolidation: {len(full_entities)} entities")
        audit.append(f"Equity method: {len(equity_entities)} entities")

        # 3. Pull P&L for each fully-consolidated entity
        entity_pnls: Dict[str, Dict[str, Dict[str, float]]] = {}
        all_periods: set = set()

        for eid in full_entities:
            pnl, periods = await self._pull_entity_pnl(eid, period_start, period_end)
            entity_pnls[eid] = pnl
            all_periods.update(periods)
            audit.append(f"Entity {eid}: {len(pnl)} line items, {len(periods)} periods")

        sorted_periods = sorted(all_periods)

        # 4. Sum all entity P&Ls
        combined: Dict[str, Dict[str, float]] = defaultdict(lambda: defaultdict(float))
        for eid, pnl in entity_pnls.items():
            for key, period_data in pnl.items():
                for period, amount in period_data.items():
                    combined[key][period] += amount

        # 5. Fetch IC transactions and eliminate
        ic_transactions = await self._fetch_ic_transactions(
            full_entities, period_start, period_end
        )
        eliminations = self._compute_eliminations(ic_transactions, combined)
        audit.append(f"IC eliminations: {len(eliminations)} entries")

        # Apply eliminations to get consolidated P&L
        consolidated: Dict[str, Dict[str, float]] = defaultdict(lambda: defaultdict(float))
        # Start with combined
        for key, period_data in combined.items():
            for period, amount in period_data.items():
                consolidated[key][period] = amount
        # Subtract eliminations
        for elim in eliminations:
            key = f"{elim.category}:{elim.subcategory}" if elim.subcategory else elim.category
            consolidated[key][elim.period] -= elim.amount

        # 6. Minority interest
        minority_interest: Dict[str, Dict[str, float]] = {}
        for eid in full_entities:
            ownership = ownership_map.get(eid, 100.0)
            if ownership < 100.0:
                minority_pct = (100.0 - ownership) / 100.0
                mi_by_period: Dict[str, float] = {}
                for key, period_data in entity_pnls.get(eid, {}).items():
                    for period, amount in period_data.items():
                        mi_by_period[period] = mi_by_period.get(period, 0) + amount * minority_pct
                if mi_by_period:
                    minority_interest[eid] = mi_by_period
                    audit.append(f"Minority interest for {eid}: {minority_pct:.0%} of net income")

        return ConsolidatedPnL(
            entity_pnls=dict(entity_pnls),
            combined=dict(combined),
            eliminations=eliminations,
            consolidated=dict(consolidated),
            entities_consolidated=full_entities,
            entities_equity_method=equity_entities,
            minority_interest=minority_interest,
            periods=sorted_periods,
            audit=audit,
        )

    # ------------------------------------------------------------------
    # Entity tree resolution
    # ------------------------------------------------------------------

    async def _resolve_entity_tree(
        self, parent_entity_id: str
    ) -> Tuple[List[Dict], List[Dict]]:
        """Get entities and relationships from group_structure_intelligence or DB."""
        from app.core.supabase_client import get_supabase_client

        sb = get_supabase_client()
        if not sb:
            return [], []

        # Try company_entities table first
        try:
            entities_result = (
                sb.table("company_entities")
                .select("*")
                .eq("company_id", self.company_id)
                .execute()
            )
            entities = entities_result.data or []
        except Exception:
            entities = []

        # Build relationships from parent_entity_id links
        relationships = []
        for entity in entities:
            parent = entity.get("parent_entity_id")
            if parent:
                ownership = entity.get("ownership_pct", 100.0)
                relationships.append({
                    "from_entity_id": parent,
                    "to_entity_id": entity["id"],
                    "ownership_pct": ownership,
                    "consolidation": entity.get("consolidation_method")
                                     or self._infer_consolidation(ownership),
                })

        return entities, relationships

    # ------------------------------------------------------------------
    # Per-entity P&L
    # ------------------------------------------------------------------

    async def _pull_entity_pnl(
        self,
        entity_id: str,
        period_start: Optional[str],
        period_end: Optional[str],
    ) -> Tuple[Dict[str, Dict[str, float]], List[str]]:
        """Pull P&L actuals for a single entity."""
        from app.core.supabase_client import get_supabase_client

        sb = get_supabase_client()
        if not sb:
            return {}, []

        query = (
            sb.table("fpa_actuals")
            .select("period, category, subcategory, hierarchy_path, amount")
            .eq("company_id", self.company_id)
            .eq("entity_id", entity_id)
        )
        if period_start:
            query = query.gte("period", f"{period_start}-01")
        if period_end:
            query = query.lte("period", f"{period_end}-01")

        result = query.order("period").execute()
        if not result.data:
            return {}, []

        actuals: Dict[str, Dict[str, float]] = defaultdict(lambda: defaultdict(float))
        periods: set = set()

        for row in result.data:
            period = row["period"][:7]
            cat = row["category"]
            sub = row.get("subcategory")
            key = f"{cat}:{sub}" if sub else cat
            actuals[key][period] += float(row["amount"])
            periods.add(period)

        return dict(actuals), sorted(periods)

    # ------------------------------------------------------------------
    # IC transaction fetching
    # ------------------------------------------------------------------

    async def _fetch_ic_transactions(
        self,
        entity_ids: List[str],
        period_start: Optional[str],
        period_end: Optional[str],
    ) -> List[Dict]:
        """Fetch IC transaction suggestions between consolidated entities."""
        from app.core.supabase_client import get_supabase_client

        sb = get_supabase_client()
        if not sb:
            return []

        try:
            query = (
                sb.table("ic_transaction_suggestions")
                .select("*")
                .eq("company_id", self.company_id)
            )
            result = query.execute()
            if not result.data:
                return []

            # Filter to transactions between consolidated entities
            entity_set = set(entity_ids)
            ic_txns = []
            for txn in result.data:
                from_eid = txn.get("from_entity_id") or txn.get("source_entity_id")
                to_eid = txn.get("to_entity_id") or txn.get("target_entity_id")
                if from_eid in entity_set and to_eid in entity_set:
                    ic_txns.append(txn)

            return ic_txns
        except Exception as e:
            logger.warning(f"Failed to fetch IC transactions: {e}")
            return []

    # ------------------------------------------------------------------
    # IC elimination computation
    # ------------------------------------------------------------------

    def _compute_eliminations(
        self,
        ic_transactions: List[Dict],
        combined_pnl: Dict[str, Dict[str, float]],
    ) -> List[EliminationEntry]:
        """
        For each IC transaction, eliminate matching revenue/cost pairs.

        IC revenue in entity A = IC cost in entity B.
        Both sides get eliminated in consolidation.
        """
        eliminations: List[EliminationEntry] = []

        for txn in ic_transactions:
            from_eid = txn.get("from_entity_id") or txn.get("source_entity_id", "")
            to_eid = txn.get("to_entity_id") or txn.get("target_entity_id", "")
            amount = txn.get("amount") or txn.get("annual_value", 0)
            category = txn.get("category", "revenue")
            subcategory = txn.get("subcategory")
            txn_type = txn.get("transaction_type", "")
            doc_id = txn.get("document_id")

            if not amount:
                continue

            amount = float(amount)

            # Determine periods affected
            periods = txn.get("periods", [])
            if not periods:
                # If no explicit periods, apply to all periods in combined P&L
                all_periods = set()
                for key_data in combined_pnl.values():
                    all_periods.update(key_data.keys())
                periods = sorted(all_periods)
                # Divide annual value by number of periods
                if periods:
                    amount_per_period = amount / len(periods)
                else:
                    continue
            else:
                amount_per_period = amount / len(periods)

            desc = f"IC elimination: {from_eid} → {to_eid} ({txn_type or category})"

            for period in periods:
                # Eliminate revenue side (entity receiving payment)
                eliminations.append(EliminationEntry(
                    source_entity_id=from_eid,
                    target_entity_id=to_eid,
                    category="revenue" if category == "revenue" else category,
                    subcategory=subcategory,
                    period=period,
                    amount=amount_per_period,
                    description=f"{desc} — revenue side",
                    source_document_id=doc_id,
                ))

                # Eliminate cost side (entity making payment)
                cost_category = self._infer_cost_category(txn_type, category)
                eliminations.append(EliminationEntry(
                    source_entity_id=to_eid,
                    target_entity_id=from_eid,
                    category=cost_category,
                    subcategory=subcategory,
                    period=period,
                    amount=amount_per_period,
                    description=f"{desc} — cost side",
                    source_document_id=doc_id,
                ))

        return eliminations

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _infer_consolidation(ownership_pct: float) -> str:
        if ownership_pct > 50:
            return "full"
        elif ownership_pct >= 20:
            return "equity_method"
        return "none"

    @staticmethod
    def _infer_cost_category(txn_type: str, fallback_category: str) -> str:
        """Map IC transaction type to the cost P&L category."""
        mapping = {
            "management_fee": "opex_ga",
            "royalty": "cogs",
            "ip_license": "cogs",
            "services": "opex_ga",
            "cost_recharge": "opex_ga",
            "financing": "opex_ga",
            "goods": "cogs",
        }
        return mapping.get(txn_type, fallback_category)

    def _empty_result(self, audit: List[str]) -> ConsolidatedPnL:
        return ConsolidatedPnL(
            entity_pnls={},
            combined={},
            eliminations=[],
            consolidated={},
            entities_consolidated=[],
            entities_equity_method=[],
            minority_interest={},
            periods=[],
            audit=audit,
        )
