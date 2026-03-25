"""
Legal Cap Table Bridge

Closes the feedback loop between legal document extraction (SHAs, term sheets,
side letters, option agreements) and the cap table model. Reads extracted clauses
with cap_table cross-references, resolves conflicts across documents, parses
human-readable terms into typed values, and builds ShareEntry objects for
CapTableCalculator.
"""

import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from app.services.advanced_cap_table import (
    CapTableCalculator,
    ShareClass,
    ShareEntry,
    ShareholderRights,
    VestingSchedule,
)

logger = logging.getLogger(__name__)

# Document priority: higher number = higher authority (overrides lower)
DOC_PRIORITY = {
    "term_sheet": 10,
    "sha": 20,
    "side_letter": 30,
    "amendment": 40,
    "option_agreement": 15,
    "warrant_agreement": 15,
    "convertible_note": 15,
    "safe": 15,
    "subscription_agreement": 15,
    "articles_of_association": 25,
    "spa": 20,
    "spv_agreement": 15,
    "pro_rata_agreement": 15,
}

# Map extracted round names to ShareClass enum
ROUND_TO_SHARE_CLASS = {
    "seed": ShareClass.PREFERRED_A,
    "pre-seed": ShareClass.COMMON,
    "pre_seed": ShareClass.COMMON,
    "angel": ShareClass.COMMON,
    "series_a": ShareClass.PREFERRED_A,
    "series a": ShareClass.PREFERRED_A,
    "series_b": ShareClass.PREFERRED_B,
    "series b": ShareClass.PREFERRED_B,
    "series_c": ShareClass.PREFERRED_C,
    "series c": ShareClass.PREFERRED_C,
    "series_d": ShareClass.PREFERRED_D,
    "series d": ShareClass.PREFERRED_D,
    "series_e": ShareClass.PREFERRED_E,
    "series e": ShareClass.PREFERRED_E,
    "series_f": ShareClass.PREFERRED_F,
    "series f": ShareClass.PREFERRED_F,
    "common": ShareClass.COMMON,
    "options": ShareClass.OPTIONS,
    "warrants": ShareClass.WARRANTS,
    "safe": ShareClass.SAFE,
    "convertible_note": ShareClass.CONVERTIBLE_NOTE,
    "convertible note": ShareClass.CONVERTIBLE_NOTE,
}

# Round ordering for chronological processing — lower = earlier
ROUND_ORDER = {
    "founders": 0,
    "common": 1,
    "pre-seed": 2,
    "pre_seed": 2,
    "angel": 3,
    "seed": 4,
    "series_a": 5,
    "series a": 5,
    "series_b": 6,
    "series b": 6,
    "series_c": 7,
    "series c": 7,
    "series_d": 8,
    "series d": 8,
    "series_e": 9,
    "series e": 9,
    "series_f": 10,
    "series f": 10,
}

# Convertible instrument types that need conversion mechanics
CONVERTIBLE_TYPES = {"safe", "convertible_note", "convertible note", "warrants"}

# Default founder shares when no prior cap table exists
DEFAULT_FOUNDER_SHARES = Decimal("10000000")


@dataclass
class ConflictRecord:
    """Records a conflict between documents for a given field."""
    field: str
    values: Dict[str, Any]  # {doc_id: value}
    resolved_value: Any
    strategy: str  # "priority" | "latest_date" | "manual"


@dataclass
class InvestorOverride:
    """Per-investor rights override from a side letter."""
    investor_name: str
    source_doc_id: str
    overrides: Dict[str, Any]  # {field_name: value}


@dataclass
class ResolvedRound:
    """A single funding round resolved from one or more documents."""
    round_name: str
    pre_money: Optional[float] = None
    post_money: Optional[float] = None
    investment_amount: Optional[float] = None
    liq_pref_multiple: float = 1.0
    liq_pref_participating: bool = False
    anti_dilution_type: str = "none"  # "weighted_average" | "full_ratchet" | "none"
    board_seats: int = 0
    option_pool_pct: Optional[float] = None
    vesting_cliff_months: int = 12
    vesting_total_months: int = 48
    pro_rata: bool = False
    drag_along: bool = False
    tag_along: bool = False
    information_rights: bool = False
    registration_rights: bool = False
    acceleration_on_coc: bool = False
    # Participation & dividends
    participation_cap: Optional[float] = None  # e.g. 3.0 = capped at 3x
    cumulative_dividends: bool = False
    dividend_rate: Optional[float] = None  # e.g. 0.08 = 8%
    # Transfer & follow-on
    preemptive_rights: bool = False
    rofr: bool = False
    co_sale: bool = False
    # Conversion
    mandatory_conversion: bool = False
    conversion_ratio: float = 1.0
    # Redemption & enforcement
    redemption_rights: bool = False
    redemption_date: Optional[str] = None
    pay_to_play: bool = False
    # Protective provisions (veto rights)
    protective_provisions: bool = False
    # Founder
    founder_lockup_months: Optional[int] = None
    # Convertible instrument fields
    valuation_cap: Optional[float] = None
    discount_rate: Optional[float] = None  # e.g. 0.20 = 20% discount
    is_convertible: bool = False
    conversion_trigger: Optional[str] = None  # "qualified_financing", "maturity", "change_of_control"
    interest_rate: Optional[float] = None  # for convertible notes
    maturity_date: Optional[str] = None
    effective_date: Optional[str] = None  # ISO date string from document
    investors: List[Dict] = field(default_factory=list)  # [{name, role, amount}]
    source_docs: List[str] = field(default_factory=list)
    converted: bool = False  # internal: set True after conversion into equity


@dataclass
class ResolvedCapTableTerms:
    """Aggregated cap table terms resolved from all documents for a company."""
    rounds: List[ResolvedRound] = field(default_factory=list)
    conflicts: List[ConflictRecord] = field(default_factory=list)
    source_document_ids: List[str] = field(default_factory=list)
    investor_overrides: List[InvestorOverride] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Parsing helpers — convert human-readable legal strings to typed values
# ---------------------------------------------------------------------------

def parse_liquidation_preference(text: str) -> Tuple[float, bool]:
    """Parse '1x non-participating', '2x participating', etc."""
    if not text or not isinstance(text, str):
        return 1.0, False

    text_lower = text.lower().strip()
    participating = "participating" in text_lower and "non-participating" not in text_lower

    mult_match = re.search(r'(\d+(?:\.\d+)?)\s*x', text_lower)
    multiple = float(mult_match.group(1)) if mult_match else 1.0

    return multiple, participating


def parse_anti_dilution(text: str) -> str:
    """Parse 'broad-based weighted average', 'full ratchet', 'narrow-based', etc."""
    if not text or not isinstance(text, str):
        return "none"

    text_lower = text.lower().strip()
    if "full ratchet" in text_lower or "full_ratchet" in text_lower:
        return "full_ratchet"
    if "narrow" in text_lower:
        return "narrow_weighted_average"
    if "broad" in text_lower or "weighted" in text_lower:
        return "broad_weighted_average"
    return "none"


def parse_vesting(text: str) -> Tuple[int, int]:
    """Parse '4 year / 1 year cliff' → (cliff_months=12, total_months=48)."""
    if not text or not isinstance(text, str):
        return 12, 48

    text_lower = text.lower().strip()
    cliff_months = 12
    total_months = 48

    # "X year cliff"
    cliff_match = re.search(r'(\d+)\s*(?:year|yr)?\s*cliff', text_lower)
    if cliff_match:
        cliff_months = int(cliff_match.group(1)) * 12

    # "X month cliff"
    cliff_m_match = re.search(r'(\d+)\s*month\s*cliff', text_lower)
    if cliff_m_match:
        cliff_months = int(cliff_m_match.group(1))

    # "X year" total vesting (not cliff)
    total_match = re.search(r'(\d+)\s*(?:year|yr)', text_lower)
    if total_match:
        total_months = int(total_match.group(1)) * 12

    return cliff_months, total_months


def parse_money(value: Any) -> Optional[float]:
    """Parse money values — handles numbers, strings like '$10M', '10000000'."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        text = value.strip().replace(",", "").replace("$", "").replace("£", "").replace("€", "")
        multipliers = {"k": 1_000, "m": 1_000_000, "b": 1_000_000_000}
        for suffix, mult in multipliers.items():
            if text.lower().endswith(suffix):
                try:
                    return float(text[:-1]) * mult
                except ValueError:
                    return None
        try:
            return float(text)
        except ValueError:
            return None
    return None


def parse_percentage(value: Any) -> Optional[float]:
    """Parse percentage — returns as fraction (0.20 not 20).

    Disambiguation: values > 1.0 are treated as percentages (20 → 0.20).
    Values between 0 and 1.0 are ambiguous:
      - If the original text had a '%' sign, treat as percentage (1% → 0.01)
      - Otherwise, treat as already a fraction (0.20 → 0.20)
    """
    if value is None:
        return None
    if isinstance(value, str):
        text = value.strip()
        has_pct_sign = "%" in text
        text = text.replace("%", "").strip()
        try:
            v = float(text)
            if has_pct_sign:
                # Explicit percentage sign: always divide by 100
                return v / 100.0
            # No % sign: values > 1 are percentages, <= 1 are fractions
            return v if v <= 1.0 else v / 100.0
        except ValueError:
            return None
    if isinstance(value, (int, float)):
        # Numeric input: values > 1 are percentages
        return value if value <= 1.0 else value / 100.0
    return None


def _parse_investment_date(date_str: Optional[str]) -> datetime:
    """Parse an ISO date string into a datetime for investment_date.

    Falls back to datetime.now() only when no date data is available.
    """
    if date_str:
        try:
            return datetime.fromisoformat(str(date_str).replace("Z", "+00:00").rstrip("+00:00"))
        except (ValueError, TypeError):
            pass
        # Try just the date portion
        try:
            return datetime.fromisoformat(str(date_str)[:10])
        except (ValueError, TypeError):
            pass
    return datetime.now()


def _share_class_for_round(round_name: str) -> ShareClass:
    """Map a round name to a ShareClass."""
    key = round_name.lower().strip().replace("-", "_")
    return ROUND_TO_SHARE_CLASS.get(key, ShareClass.PREFERRED_A)


def _round_sort_key(rr: ResolvedRound) -> int:
    """Sort key for processing rounds chronologically."""
    key = rr.round_name.lower().strip().replace("-", "_")
    return ROUND_ORDER.get(key, 50)


def _is_convertible_round(round_name: str) -> bool:
    """Check if a round name represents a convertible instrument."""
    key = round_name.lower().strip().replace("-", "_")
    return key in CONVERTIBLE_TYPES


# ---------------------------------------------------------------------------
# Main bridge class
# ---------------------------------------------------------------------------

class LegalCapTableBridge:
    """
    Bridges legal document extraction → CapTableCalculator.

    1. Loads extracted documents for a company
    2. Aggregates cap-table-relevant fields across docs
    3. Resolves conflicts (priority + date)
    4. Parses strings → typed values
    5. Builds ShareEntry objects with cumulative share tracking
    6. Runs CapTableCalculator
    7. Persists to company_cap_tables
    """

    def __init__(self):
        self._sb = None

    def _get_sb(self):
        if self._sb is None:
            from app.core.database import get_supabase_service
            sb = get_supabase_service()
            self._sb = sb.get_client() if hasattr(sb, "get_client") else sb
        return self._sb

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def build_from_documents(
        self,
        company_id: str,
        fund_id: str,
        trigger_document_id: Optional[str] = None,
        document_ids: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Main entry point. Loads all cap-table-relevant documents for a company,
        resolves terms, builds the cap table, and persists.

        When document_ids is provided (legal mode), loads those specific documents
        directly instead of querying by company_id — supports untethered legal flow.

        Returns dict with share_entries, ownership, reconciliation_log, etc.
        """
        try:
            # Step 1: Load documents — prefer document_ids if provided
            if document_ids:
                docs = self._load_documents_by_ids(document_ids)
            else:
                docs = self._load_documents(company_id)
            if not docs:
                logger.info("[CAP_BRIDGE] No cap-table docs for company %s (doc_ids=%s)", company_id, bool(document_ids))
                return {"success": False, "reason": "no_documents"}

            # Step 2+3: Aggregate and resolve
            resolved = self._aggregate_and_resolve(docs)

            # Step 4+5: Build ShareEntry objects
            share_entries = self._build_share_entries(resolved)

            # Step 6: Calculate via CapTableCalculator
            calc = CapTableCalculator()
            calc.share_entries = share_entries
            ownership_df = calc.calculate_ownership()
            ownership_data = ownership_df.to_dict("records") if not ownership_df.empty else []

            # Build model inputs summary
            model_inputs = {
                "rounds": [
                    {
                        "round_name": r.round_name,
                        "pre_money": r.pre_money,
                        "post_money": r.post_money,
                        "investment_amount": r.investment_amount,
                        "liq_pref": f"{r.liq_pref_multiple}x {'participating' if r.liq_pref_participating else 'non-participating'}",
                        "anti_dilution": r.anti_dilution_type,
                        "board_seats": r.board_seats,
                        "option_pool_pct": r.option_pool_pct,
                        "vesting": f"{r.vesting_total_months}mo / {r.vesting_cliff_months}mo cliff",
                        "pro_rata": r.pro_rata,
                        "drag_along": r.drag_along,
                        "tag_along": r.tag_along,
                        "information_rights": r.information_rights,
                        "registration_rights": r.registration_rights,
                        "acceleration_on_coc": r.acceleration_on_coc,
                        "valuation_cap": r.valuation_cap,
                        "discount_rate": r.discount_rate,
                        "is_convertible": r.is_convertible,
                        "investors": r.investors,
                    }
                    for r in resolved.rounds
                ],
                "investor_overrides": [
                    {
                        "investor": ov.investor_name,
                        "source_doc": ov.source_doc_id,
                        "overrides": ov.overrides,
                    }
                    for ov in resolved.investor_overrides
                ],
                "source_documents": resolved.source_document_ids,
            }

            # Serialise share entries for DB
            serialised_entries = []
            for se in share_entries:
                entry = {
                    "shareholder_id": se.shareholder_id,
                    "shareholder_name": se.shareholder_name,
                    "share_class": se.share_class.value,
                    "num_shares": str(se.num_shares),
                    "price_per_share": str(se.price_per_share),
                    "investment_date": se.investment_date.isoformat(),
                    "rights": {
                        "voting_rights": se.rights.voting_rights,
                        "board_seats": se.rights.board_seats,
                        "protective_provisions": se.rights.protective_provisions,
                        "liquidation_preference": se.rights.liquidation_preference,
                        "participation_rights": se.rights.participation_rights,
                        "participation_cap": se.rights.participation_cap,
                        "cumulative_dividends": se.rights.cumulative_dividends,
                        "dividend_rate": se.rights.dividend_rate,
                        "anti_dilution": se.rights.anti_dilution,
                        "pro_rata_rights": se.rights.pro_rata_rights,
                        "preemptive_rights": se.rights.preemptive_rights,
                        "rofr": se.rights.rofr,
                        "co_sale": se.rights.co_sale,
                        "drag_along": se.rights.drag_along,
                        "tag_along": se.rights.tag_along,
                        "conversion_ratio": se.rights.conversion_ratio,
                        "mandatory_conversion": se.rights.mandatory_conversion,
                        "information_rights": se.rights.information_rights,
                        "registration_rights": se.rights.registration_rights,
                        "redemption_rights": se.rights.redemption_rights,
                        "redemption_date": se.rights.redemption_date,
                        "pay_to_play": se.rights.pay_to_play,
                        "founder_lockup_months": se.rights.founder_lockup_months,
                    },
                }
                if se.vesting_schedule:
                    entry["vesting"] = {
                        "cliff_months": se.vesting_schedule.cliff_months,
                        "total_months": se.vesting_schedule.vesting_months,
                        "acceleration_on_coc": se.vesting_schedule.acceleration_on_change_of_control,
                    }
                serialised_entries.append(entry)

            reconciliation_log = [
                {
                    "field": c.field,
                    "values": {k: str(v) for k, v in c.values.items()},
                    "resolved_value": str(c.resolved_value),
                    "strategy": c.strategy,
                }
                for c in resolved.conflicts
            ]

            # Step 7: Persist
            self._persist(
                company_id=company_id,
                fund_id=fund_id,
                share_entries=serialised_entries,
                document_ids=resolved.source_document_ids,
                reconciliation_log=reconciliation_log,
                model_inputs=model_inputs,
                ownership_data=ownership_data,
                trigger_document_id=trigger_document_id,
                docs=docs,
            )

            logger.info(
                "[CAP_BRIDGE] Built cap table for company %s from %d docs, %d entries, %d conflicts, %d overrides",
                company_id, len(docs), len(share_entries), len(resolved.conflicts),
                len(resolved.investor_overrides),
            )

            return {
                "success": True,
                "share_entries": serialised_entries,
                "ownership": ownership_data,
                "model_inputs": model_inputs,
                "reconciliation_log": reconciliation_log,
                "source_document_ids": resolved.source_document_ids,
                "num_conflicts": len(resolved.conflicts),
                "num_investor_overrides": len(resolved.investor_overrides),
            }

        except Exception as e:
            logger.error("[CAP_BRIDGE] Failed for company %s: %s", company_id, e, exc_info=True)
            return {"success": False, "reason": str(e)}

    def recalculate(
        self,
        share_entries_json: List[Dict],
    ) -> Dict[str, Any]:
        """
        Re-run CapTableCalculator from edited share entries (frontend edits).
        Returns updated ownership, waterfall, sankey data.
        """
        entries = self._deserialise_entries(share_entries_json)
        calc = CapTableCalculator()
        calc.share_entries = entries

        ownership_df = calc.calculate_ownership()
        ownership_data = ownership_df.to_dict("records") if not ownership_df.empty else []

        return {
            "ownership": ownership_data,
        }

    def simulate(
        self,
        share_entries_json: List[Dict],
        investment_amount: float,
        pre_money_valuation: float,
        option_pool_increase: float = 0,
        exit_value: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Run scenario simulation from share entries + new round params.
        """
        entries = self._deserialise_entries(share_entries_json)
        calc = CapTableCalculator()
        calc.share_entries = entries

        result: Dict[str, Any] = {}

        # Simulate new round
        round_result = calc.simulate_financing_round(
            investment_amount=Decimal(str(investment_amount)),
            pre_money_valuation=Decimal(str(pre_money_valuation)),
            option_pool_increase=Decimal(str(option_pool_increase)),
        )
        result["financing_round"] = round_result

        # If exit value provided, run waterfall
        if exit_value is not None:
            ownership_df = calc.calculate_ownership()
            if not ownership_df.empty:
                cap_table = {}
                for _, row in ownership_df.iterrows():
                    name = row.get("shareholder", "Unknown")
                    pct = row.get("ownership_pct", 0)
                    cap_table[name] = float(pct) / 100.0

                waterfall = calc.calculate_liquidation_waterfall(
                    exit_value=exit_value,
                    cap_table=cap_table,
                )
                result["waterfall"] = waterfall

        return result

    # ------------------------------------------------------------------
    # Internal methods
    # ------------------------------------------------------------------

    def _load_documents(self, company_id: str) -> List[Dict]:
        """Load all processed documents with cap-table-relevant types."""
        sb = self._get_sb()
        if not sb:
            return []

        cap_doc_types = [
            "sha", "term_sheet", "side_letter", "option_agreement",
            "warrant_agreement", "convertible_note", "safe", "spa",
            "subscription_agreement", "articles_of_association",
            "spv_agreement", "pro_rata_agreement", "amendment",
        ]

        try:
            resp = (
                sb.table("processed_documents")
                .select("id, document_type, extracted_data, created_at, document_name")
                .eq("company_id", company_id)
                .in_("document_type", cap_doc_types)
                .order("created_at", desc=False)
                .execute()
            )
            return resp.data or []
        except Exception as e:
            logger.warning("[CAP_BRIDGE] Failed to load docs for %s: %s", company_id, e)
            return []

    def _load_documents_by_ids(self, document_ids: List[str]) -> List[Dict]:
        """Load specific documents by ID — for legal mode where company_id may be absent.

        Filters to cap-table-relevant types after loading by ID.
        """
        sb = self._get_sb()
        if not sb or not document_ids:
            return []

        cap_doc_types = [
            "sha", "term_sheet", "side_letter", "option_agreement",
            "warrant_agreement", "convertible_note", "safe", "spa",
            "subscription_agreement", "articles_of_association",
            "spv_agreement", "pro_rata_agreement", "amendment",
        ]

        try:
            resp = (
                sb.table("processed_documents")
                .select("id, document_type, extracted_data, created_at, document_name")
                .in_("id", document_ids)
                .order("created_at", desc=False)
                .execute()
            )
            # Filter to cap-table-relevant types
            docs = [d for d in (resp.data or []) if d.get("document_type") in cap_doc_types]
            logger.info("[CAP_BRIDGE] Loaded %d/%d docs by ID (cap-table relevant)", len(docs), len(resp.data or []))
            return docs
        except Exception as e:
            logger.warning("[CAP_BRIDGE] Failed to load docs by IDs: %s", e)
            return []

    def _aggregate_and_resolve(self, docs: List[Dict]) -> ResolvedCapTableTerms:
        """
        Aggregate cap-table-relevant fields from all documents.
        Resolve conflicts by priority then date.
        Extract clause-level rights (drag/tag along, info rights, etc.).
        Track side letter per-investor overrides.
        """
        resolved = ResolvedCapTableTerms()

        # Collect per-round data across all documents
        round_data: Dict[str, Dict[str, List[Tuple[int, str, str, Any]]]] = {}
        # round_data[round_name][field_name] = [(priority, doc_id, date_str, value)]

        # Track clause-level rights per round
        round_clause_rights: Dict[str, Dict[str, bool]] = {}
        # round_clause_rights[round_name] = {right_name: True}

        for doc in docs:
            doc_id = doc.get("id", "")
            doc_type = doc.get("document_type", "")
            created_at = doc.get("created_at", "")
            extracted = doc.get("extracted_data")
            if not extracted:
                continue
            if isinstance(extracted, str):
                try:
                    extracted = json.loads(extracted)
                except (json.JSONDecodeError, TypeError):
                    continue

            resolved.source_document_ids.append(doc_id)
            priority = DOC_PRIORITY.get(doc_type, 10)

            # Determine round name from doc
            round_name = (
                extracted.get("round")
                or extracted.get("stage")
                or extracted.get("round_name")
                or doc_type
            )

            # --- Side letter investor targeting ---
            # Side letters apply to specific investors, not globally
            side_letter_target = None
            if doc_type == "side_letter":
                parties = extracted.get("parties", [])
                # The non-company party in a side letter is the investor it targets
                for p in (parties if isinstance(parties, list) else []):
                    if isinstance(p, dict):
                        role = (p.get("role") or "").lower()
                        if role in ("investor", "shareholder", "lp", "holder"):
                            side_letter_target = p.get("name")
                            break

            # Extract from cross_references in clauses
            clauses = extracted.get("clauses", [])
            if isinstance(clauses, list):
                for clause in clauses:
                    if not isinstance(clause, dict):
                        continue

                    clause_type = (clause.get("clause_type") or clause.get("type") or "").lower()

                    # --- Extract rights from clause types ---
                    rights_map = {
                        "drag_along": "drag_along",
                        "tag_along": "tag_along",
                        "information_rights": "information_rights",
                        "registration_rights": "registration_rights",
                        "preemptive_rights": "preemptive_rights",
                        "pre_emptive_rights": "preemptive_rights",
                        "rofr": "rofr",
                        "right_of_first_refusal": "rofr",
                        "co_sale": "co_sale",
                        "co_sale_rights": "co_sale",
                        "protective_provisions": "protective_provisions",
                        "veto_rights": "protective_provisions",
                        "redemption_rights": "redemption_rights",
                        "redemption": "redemption_rights",
                        "pay_to_play": "pay_to_play",
                        "mandatory_conversion": "mandatory_conversion",
                        "founder_lockup": "founder_lockup",
                        "lockup": "founder_lockup",
                        "transfer_restriction": "founder_lockup",
                    }
                    if clause_type in rights_map:
                        right_name = rights_map[clause_type]
                        # Special handling for lockup — extract months
                        if right_name == "founder_lockup":
                            text = (clause.get("text") or clause.get("clause_text") or "").lower()
                            months = 12  # default
                            m_match = re.search(r'(\d+)\s*month', text)
                            y_match = re.search(r'(\d+)\s*(?:year|yr)', text)
                            if m_match:
                                months = int(m_match.group(1))
                            elif y_match:
                                months = int(y_match.group(1)) * 12
                            if side_letter_target:
                                resolved.investor_overrides.append(InvestorOverride(
                                    investor_name=side_letter_target,
                                    source_doc_id=doc_id,
                                    overrides={"founder_lockup_months": months},
                                ))
                            else:
                                if round_name not in round_clause_rights:
                                    round_clause_rights[round_name] = {}
                                round_clause_rights[round_name]["founder_lockup_months"] = months
                        elif side_letter_target:
                            # Per-investor override from side letter
                            resolved.investor_overrides.append(InvestorOverride(
                                investor_name=side_letter_target,
                                source_doc_id=doc_id,
                                overrides={right_name: True},
                            ))
                        else:
                            if round_name not in round_clause_rights:
                                round_clause_rights[round_name] = {}
                            round_clause_rights[round_name][right_name] = True

                    # Acceleration on change of control
                    if clause_type in ("change_of_control", "acceleration", "vesting_acceleration"):
                        text = (clause.get("text") or clause.get("clause_text") or "").lower()
                        if "accelerat" in text:
                            if round_name not in round_clause_rights:
                                round_clause_rights[round_name] = {}
                            round_clause_rights[round_name]["acceleration_on_coc"] = True

                    # --- Side letter liq pref / anti-dilution overrides ---
                    if side_letter_target and clause_type in (
                        "liquidation_preference", "anti_dilution",
                        "pro_rata", "board_seat", "board_composition",
                        "participation_cap", "cumulative_dividends", "dividend",
                        "redemption", "redemption_rights",
                        "pay_to_play", "conversion_ratio",
                    ):
                        text = clause.get("text") or clause.get("clause_text") or ""
                        override_fields: Dict[str, Any] = {}
                        if clause_type == "liquidation_preference":
                            mult, part = parse_liquidation_preference(text)
                            override_fields["liq_pref_multiple"] = mult
                            override_fields["liq_pref_participating"] = part
                        elif clause_type == "anti_dilution":
                            override_fields["anti_dilution_type"] = parse_anti_dilution(text)
                        elif clause_type == "pro_rata":
                            override_fields["pro_rata"] = True
                        elif clause_type in ("board_seat", "board_composition"):
                            try:
                                seats = int(re.search(r'(\d+)', text).group(1)) if re.search(r'(\d+)', text) else 1
                                override_fields["board_seats"] = seats
                            except (AttributeError, ValueError):
                                override_fields["board_seats"] = 1
                        elif clause_type == "participation_cap":
                            cap_match = re.search(r'(\d+(?:\.\d+)?)\s*x', text.lower())
                            if cap_match:
                                override_fields["participation_cap"] = float(cap_match.group(1))
                        elif clause_type in ("cumulative_dividends", "dividend"):
                            override_fields["cumulative_dividends"] = True
                            rate = parse_percentage(text)
                            if rate:
                                override_fields["dividend_rate"] = rate
                        elif clause_type in ("redemption", "redemption_rights"):
                            override_fields["redemption_rights"] = True
                        elif clause_type == "pay_to_play":
                            override_fields["pay_to_play"] = True
                        elif clause_type == "conversion_ratio":
                            ratio_match = re.search(r'(\d+(?:\.\d+)?)', text)
                            if ratio_match:
                                override_fields["conversion_ratio"] = float(ratio_match.group(1))

                        if override_fields:
                            resolved.investor_overrides.append(InvestorOverride(
                                investor_name=side_letter_target,
                                source_doc_id=doc_id,
                                overrides=override_fields,
                            ))

                    # --- Cross-references to cap_table service ---
                    xrefs = clause.get("cross_references", [])
                    if not isinstance(xrefs, list):
                        continue
                    for xr in xrefs:
                        if not isinstance(xr, dict):
                            continue
                        if xr.get("to_service") != "cap_table":
                            continue

                        entity = xr.get("to_entity", "unknown_round")
                        fld = xr.get("field", "")
                        val = xr.get("value")
                        if not fld or val is None:
                            continue

                        if entity not in round_data:
                            round_data[entity] = {}
                        if fld not in round_data[entity]:
                            round_data[entity][fld] = []
                        round_data[entity][fld].append((priority, doc_id, created_at, val))

            # Also extract top-level term sheet / SHA fields
            top_level_fields = {
                "valuation_pre_money": "pre_money",
                "valuation_post_money": "post_money",
                "investment_amount": "investment_amount",
                "liquidation_preference": "liq_pref_text",
                "anti_dilution": "anti_dilution_text",
                "option_pool": "option_pool_pct",
                "board_seats": "board_seats",
                "vesting": "vesting_text",
                "pro_rata": "pro_rata",
                # Participation & dividends
                "participation_cap": "participation_cap",
                "dividend_rate": "dividend_rate",
                "cumulative_dividends": "cumulative_dividends",
                # Redemption
                "redemption_date": "redemption_date",
                # Convertible instrument fields
                "valuation_cap": "valuation_cap",
                "discount_rate": "discount_rate",
                "discount": "discount_rate",
                "conversion_trigger": "conversion_trigger",
                "interest_rate": "interest_rate",
                "maturity_date": "maturity_date",
                "maturity": "maturity_date",
                "effective_date": "effective_date",
                "date": "effective_date",
                "closing_date": "effective_date",
            }

            for src_field, target_field in top_level_fields.items():
                val = extracted.get(src_field)
                if val is not None:
                    if round_name not in round_data:
                        round_data[round_name] = {}
                    if target_field not in round_data[round_name]:
                        round_data[round_name][target_field] = []
                    round_data[round_name][target_field].append(
                        (priority, doc_id, created_at, val)
                    )

            # Extract investors/parties with amounts
            parties = extracted.get("parties", [])
            if isinstance(parties, list) and parties:
                if round_name not in round_data:
                    round_data[round_name] = {}
                if "investors" not in round_data[round_name]:
                    round_data[round_name]["investors"] = []
                round_data[round_name]["investors"].append(
                    (priority, doc_id, created_at, parties)
                )

        # Now resolve each round
        for round_name, fields in round_data.items():
            rr = ResolvedRound(round_name=round_name)
            round_docs = set()

            for fld, entries in fields.items():
                # Sort by priority desc, then date desc
                entries.sort(key=lambda x: (x[0], x[2]), reverse=True)
                winner = entries[0]
                val = winner[3]

                # Record conflict if multiple distinct values
                if len(entries) > 1:
                    distinct = {e[1]: e[3] for e in entries}
                    if len(set(str(v) for v in distinct.values())) > 1:
                        resolved.conflicts.append(ConflictRecord(
                            field=f"{round_name}.{fld}",
                            values=distinct,
                            resolved_value=val,
                            strategy="priority" if entries[0][0] != entries[1][0] else "latest_date",
                        ))

                round_docs.update(e[1] for e in entries)

                # Apply resolved value
                if fld == "pre_money":
                    rr.pre_money = parse_money(val)
                elif fld == "post_money":
                    rr.post_money = parse_money(val)
                elif fld == "investment_amount":
                    rr.investment_amount = parse_money(val)
                elif fld in ("liq_pref_text", "liquidation_pref_multiple"):
                    if isinstance(val, str):
                        rr.liq_pref_multiple, rr.liq_pref_participating = parse_liquidation_preference(val)
                    elif isinstance(val, (int, float)):
                        rr.liq_pref_multiple = float(val)
                elif fld in ("anti_dilution_text", "anti_dilution_type"):
                    if isinstance(val, str):
                        rr.anti_dilution_type = parse_anti_dilution(val)
                    else:
                        rr.anti_dilution_type = str(val) if val else "none"
                elif fld == "board_seats":
                    try:
                        rr.board_seats = int(val)
                    except (ValueError, TypeError):
                        pass
                elif fld == "option_pool_pct":
                    pct = parse_percentage(val)
                    if pct is not None:
                        rr.option_pool_pct = pct
                elif fld == "vesting_text":
                    if isinstance(val, str):
                        rr.vesting_cliff_months, rr.vesting_total_months = parse_vesting(val)
                elif fld == "pro_rata":
                    rr.pro_rata = bool(val)
                elif fld == "participation_cap":
                    pc = parse_money(val)
                    if pc is not None:
                        rr.participation_cap = pc
                elif fld == "dividend_rate":
                    dr = parse_percentage(val)
                    if dr is not None:
                        rr.dividend_rate = dr
                elif fld == "cumulative_dividends":
                    rr.cumulative_dividends = bool(val)
                elif fld == "redemption_date":
                    rr.redemption_date = str(val) if val else None
                elif fld == "valuation_cap":
                    rr.valuation_cap = parse_money(val)
                elif fld == "discount_rate":
                    rr.discount_rate = parse_percentage(val)
                elif fld == "conversion_trigger":
                    rr.conversion_trigger = str(val) if val else None
                elif fld == "interest_rate":
                    rr.interest_rate = parse_percentage(val)
                elif fld == "maturity_date":
                    rr.maturity_date = str(val) if val else None
                elif fld == "effective_date":
                    rr.effective_date = str(val) if val else None
                elif fld == "investors":
                    if isinstance(val, list):
                        for party in val:
                            if isinstance(party, dict):
                                inv_entry = {
                                    "name": party.get("name", ""),
                                    "role": party.get("role", "investor"),
                                }
                                # Preserve per-investor amounts if available
                                amt = party.get("amount") or party.get("investment_amount")
                                if amt is not None:
                                    inv_entry["amount"] = parse_money(amt)
                                rr.investors.append(inv_entry)

            # Apply clause-level rights
            clause_rights = round_clause_rights.get(round_name, {})
            rr.drag_along = clause_rights.get("drag_along", False)
            rr.tag_along = clause_rights.get("tag_along", False)
            rr.information_rights = clause_rights.get("information_rights", False)
            rr.registration_rights = clause_rights.get("registration_rights", False)
            rr.acceleration_on_coc = clause_rights.get("acceleration_on_coc", False)
            rr.preemptive_rights = clause_rights.get("preemptive_rights", False)
            rr.rofr = clause_rights.get("rofr", False)
            rr.co_sale = clause_rights.get("co_sale", False)
            rr.protective_provisions = clause_rights.get("protective_provisions", False)
            rr.redemption_rights = clause_rights.get("redemption_rights", False)
            rr.pay_to_play = clause_rights.get("pay_to_play", False)
            rr.mandatory_conversion = clause_rights.get("mandatory_conversion", False)
            if "founder_lockup_months" in clause_rights:
                rr.founder_lockup_months = clause_rights["founder_lockup_months"]

            # Mark convertible instruments
            rr.is_convertible = (
                _is_convertible_round(round_name)
                or rr.valuation_cap is not None
                or rr.discount_rate is not None
            )

            rr.source_docs = list(round_docs)
            resolved.rounds.append(rr)

        return resolved

    def _build_share_entries(self, resolved: ResolvedCapTableTerms) -> List[ShareEntry]:
        """
        Convert resolved rounds into ShareEntry objects for CapTableCalculator.

        Processes rounds chronologically, tracking cumulative shares so each
        round's price-per-share reflects actual shares outstanding — not a
        hardcoded assumption.

        Handles SAFE/convertible note conversion at the qualifying round's price.
        Creates option pool entries. Applies per-investor side letter overrides.
        """
        entries: List[ShareEntry] = []

        # Build per-investor override lookup: investor_name → merged overrides
        investor_override_map: Dict[str, Dict[str, Any]] = {}
        for ov in resolved.investor_overrides:
            name_key = ov.investor_name.lower().strip()
            if name_key not in investor_override_map:
                investor_override_map[name_key] = {}
            investor_override_map[name_key].update(ov.overrides)

        # Sort rounds chronologically
        equity_rounds: List[ResolvedRound] = []
        convertible_rounds: List[ResolvedRound] = []
        for rr in resolved.rounds:
            if rr.is_convertible:
                convertible_rounds.append(rr)
            else:
                equity_rounds.append(rr)

        equity_rounds.sort(key=_round_sort_key)

        # Derive initial founder shares from docs when available.
        # If a "founders" or "common" round exists with explicit share data,
        # use that instead of the blind 10M default.
        cumulative_shares = DEFAULT_FOUNDER_SHARES
        founder_round_names = {"founders", "common"}
        initial_rounds: List[ResolvedRound] = []
        remaining_rounds: List[ResolvedRound] = []
        for rr in equity_rounds:
            rr_key = rr.round_name.lower().strip().replace("-", "_")
            if rr_key in founder_round_names and _round_sort_key(rr) <= 1:
                initial_rounds.append(rr)
            else:
                remaining_rounds.append(rr)

        if initial_rounds:
            # Use the founders/common round to set initial shares
            cumulative_shares = Decimal("0")
            for fr in initial_rounds:
                if fr.investors:
                    for inv in fr.investors:
                        inv_name = inv.get("name", "Founder")
                        inv_id = inv_name.lower().replace(" ", "_")
                        inv_amount = inv.get("amount")
                        if inv_amount:
                            inv_shares = Decimal(str(inv_amount))
                        else:
                            inv_shares = DEFAULT_FOUNDER_SHARES / Decimal(str(max(len(fr.investors), 1)))
                        entries.append(ShareEntry(
                            shareholder_id=inv_id,
                            shareholder_name=inv_name,
                            share_class=ShareClass.COMMON,
                            num_shares=inv_shares,
                            price_per_share=Decimal("0.0001"),
                            investment_date=_parse_investment_date(fr.effective_date),
                            rights=ShareholderRights(),
                            metadata={"round": fr.round_name, "source_docs": fr.source_docs},
                        ))
                        cumulative_shares += inv_shares
                elif fr.investment_amount:
                    founder_shares = Decimal(str(fr.investment_amount))
                    entries.append(ShareEntry(
                        shareholder_id=f"founders_{fr.round_name.lower().replace(' ', '_')}",
                        shareholder_name="Founders",
                        share_class=ShareClass.COMMON,
                        num_shares=founder_shares,
                        price_per_share=Decimal("0.0001"),
                        investment_date=_parse_investment_date(fr.effective_date),
                        rights=ShareholderRights(),
                        metadata={"round": fr.round_name, "source_docs": fr.source_docs},
                    ))
                    cumulative_shares += founder_shares
            # If we got 0 shares from the founder round data, fall back to default
            if cumulative_shares <= 0:
                cumulative_shares = DEFAULT_FOUNDER_SHARES
            equity_rounds = remaining_rounds
        else:
            equity_rounds = remaining_rounds

        for rr in equity_rounds:
            share_class = _share_class_for_round(rr.round_name)

            # --- Calculate price per share from cumulative shares ---
            price_per_share = Decimal("1.00")
            num_new_shares = Decimal("0")

            if rr.pre_money and rr.investment_amount:
                price_per_share = Decimal(str(rr.pre_money)) / cumulative_shares
                num_new_shares = Decimal(str(rr.investment_amount)) / price_per_share
            elif rr.post_money and rr.investment_amount:
                post_money_dec = Decimal(str(rr.post_money))
                invest_dec = Decimal(str(rr.investment_amount))
                if post_money_dec <= invest_dec:
                    # Edge case: 100% ownership (or invalid data)
                    # Use investment amount as total valuation
                    num_new_shares = cumulative_shares if cumulative_shares > 0 else Decimal("1000000")
                    price_per_share = invest_dec / num_new_shares
                else:
                    ownership_pct = invest_dec / post_money_dec
                    num_new_shares = (cumulative_shares * ownership_pct) / (
                        Decimal("1") - ownership_pct
                    )
                    if num_new_shares > 0:
                        price_per_share = invest_dec / num_new_shares
            elif rr.investment_amount:
                # No valuation data — use $1/share as fallback
                num_new_shares = Decimal(str(rr.investment_amount))
                price_per_share = Decimal("1.00")

            # --- Convert any convertible instruments at this round's price ---
            converted_entries = self._convert_instruments(
                convertible_rounds, price_per_share, cumulative_shares,
                rr, investor_override_map,
            )
            for ce in converted_entries:
                entries.append(ce)
                cumulative_shares += ce.num_shares

            # Remove converted instruments so they don't convert again
            convertible_rounds = [
                cr for cr in convertible_rounds if not cr.converted
            ]

            # --- Build rights for this round ---
            base_rights = ShareholderRights(
                liquidation_preference=rr.liq_pref_multiple,
                participation_rights=rr.liq_pref_participating,
                participation_cap=rr.participation_cap,
                cumulative_dividends=rr.cumulative_dividends,
                dividend_rate=rr.dividend_rate,
                pro_rata_rights=rr.pro_rata,
                preemptive_rights=rr.preemptive_rights,
                board_seats=rr.board_seats,
                anti_dilution=rr.anti_dilution_type if rr.anti_dilution_type != "none" else None,
                drag_along=rr.drag_along,
                tag_along=rr.tag_along,
                rofr=rr.rofr,
                co_sale=rr.co_sale,
                information_rights=rr.information_rights,
                registration_rights=rr.registration_rights,
                protective_provisions=rr.protective_provisions,
                redemption_rights=rr.redemption_rights,
                redemption_date=rr.redemption_date,
                pay_to_play=rr.pay_to_play,
                mandatory_conversion=rr.mandatory_conversion,
                conversion_ratio=rr.conversion_ratio,
                founder_lockup_months=rr.founder_lockup_months,
            )

            # --- Create entries per investor with actual amounts ---
            if rr.investors:
                # Check if we have per-investor amounts
                investors_with_amounts = [
                    inv for inv in rr.investors if inv.get("amount")
                ]

                if investors_with_amounts:
                    # Use actual per-investor amounts
                    for inv in rr.investors:
                        inv_name = inv.get("name", "Unknown Investor")
                        inv_id = inv_name.lower().replace(" ", "_")
                        inv_amount = inv.get("amount")

                        if inv_amount and price_per_share > 0:
                            inv_shares = Decimal(str(inv_amount)) / price_per_share
                        elif num_new_shares > 0:
                            # Fallback: proportional split for investors without amounts
                            inv_shares = num_new_shares / Decimal(str(len(rr.investors)))
                        else:
                            inv_shares = Decimal("0")

                        # Apply per-investor side letter overrides
                        inv_rights = self._apply_investor_overrides(
                            base_rights, inv_name, investor_override_map,
                        )

                        round_date = _parse_investment_date(rr.effective_date)
                        vesting = None
                        if share_class == ShareClass.OPTIONS:
                            vesting = VestingSchedule(
                                total_shares=inv_shares,
                                cliff_months=rr.vesting_cliff_months,
                                vesting_months=rr.vesting_total_months,
                                start_date=round_date,
                                acceleration_on_change_of_control=rr.acceleration_on_coc,
                            )

                        entries.append(ShareEntry(
                            shareholder_id=inv_id,
                            shareholder_name=inv_name,
                            share_class=share_class,
                            num_shares=inv_shares,
                            price_per_share=price_per_share,
                            investment_date=round_date,
                            vesting_schedule=vesting,
                            rights=inv_rights,
                            metadata={"round": rr.round_name, "source_docs": rr.source_docs},
                        ))
                        cumulative_shares += inv_shares
                else:
                    # No per-investor amounts — equal split
                    shares_each = num_new_shares / Decimal(str(max(len(rr.investors), 1)))
                    round_date = _parse_investment_date(rr.effective_date)
                    for inv in rr.investors:
                        inv_name = inv.get("name", "Unknown Investor")
                        inv_id = inv_name.lower().replace(" ", "_")

                        inv_rights = self._apply_investor_overrides(
                            base_rights, inv_name, investor_override_map,
                        )

                        vesting = None
                        if share_class == ShareClass.OPTIONS:
                            vesting = VestingSchedule(
                                total_shares=shares_each,
                                cliff_months=rr.vesting_cliff_months,
                                vesting_months=rr.vesting_total_months,
                                start_date=round_date,
                                acceleration_on_change_of_control=rr.acceleration_on_coc,
                            )

                        entries.append(ShareEntry(
                            shareholder_id=inv_id,
                            shareholder_name=inv_name,
                            share_class=share_class,
                            num_shares=shares_each,
                            price_per_share=price_per_share,
                            investment_date=round_date,
                            vesting_schedule=vesting,
                            rights=inv_rights,
                            metadata={"round": rr.round_name, "source_docs": rr.source_docs},
                        ))
                    cumulative_shares += num_new_shares

            elif num_new_shares > 0:
                # No named investors — create a single round-level entry
                entries.append(ShareEntry(
                    shareholder_id=f"round_{rr.round_name.lower().replace(' ', '_')}",
                    shareholder_name=f"{rr.round_name} Investors",
                    share_class=share_class,
                    num_shares=num_new_shares,
                    price_per_share=price_per_share,
                    investment_date=_parse_investment_date(rr.effective_date),
                    rights=base_rights,
                    metadata={"round": rr.round_name, "source_docs": rr.source_docs},
                ))
                cumulative_shares += num_new_shares

            # --- Materialize option pool if specified ---
            # Pool is X% of post-money (which includes the pool itself), so:
            #   pool / (cumulative + pool) = pct
            #   pool = cumulative * pct / (1 - pct)
            if rr.option_pool_pct and rr.option_pool_pct > 0:
                pct = Decimal(str(rr.option_pool_pct))
                pool_shares = cumulative_shares * pct / (Decimal("1") - pct)
                pool_date = _parse_investment_date(rr.effective_date)
                entries.append(ShareEntry(
                    shareholder_id=f"option_pool_{rr.round_name.lower().replace(' ', '_')}",
                    shareholder_name=f"Option Pool ({rr.round_name})",
                    share_class=ShareClass.OPTIONS,
                    num_shares=pool_shares,
                    price_per_share=price_per_share,
                    investment_date=pool_date,
                    vesting_schedule=VestingSchedule(
                        total_shares=pool_shares,
                        cliff_months=12,
                        vesting_months=48,
                        start_date=pool_date,
                        acceleration_on_change_of_control=rr.acceleration_on_coc,
                    ),
                    rights=ShareholderRights(),
                    metadata={
                        "round": rr.round_name,
                        "pool_pct": rr.option_pool_pct,
                        "source_docs": rr.source_docs,
                    },
                ))
                cumulative_shares += pool_shares

        # Handle any unconverted instruments (SAFEs/notes that haven't hit a trigger)
        for cr in convertible_rounds:
            if not cr.converted:
                entries.extend(
                    self._create_unconverted_entries(cr, investor_override_map)
                )

        return entries

    def _convert_instruments(
        self,
        convertible_rounds: List[ResolvedRound],
        round_price: Decimal,
        pre_shares: Decimal,
        equity_round: ResolvedRound,
        investor_override_map: Dict[str, Dict[str, Any]],
    ) -> List[ShareEntry]:
        """
        Convert SAFEs and convertible notes at the qualifying equity round.

        Conversion price = min(cap_price, round_price * (1 - discount)).
        For convertible notes, accrued interest increases the principal.
        """
        converted_entries: List[ShareEntry] = []

        for cr in convertible_rounds:
            if cr.converted:
                continue

            if not cr.investment_amount:
                continue

            # Check conversion trigger — only convert at matching events.
            # "qualified_financing" triggers require minimum raise amount;
            # "maturity" and "change_of_control" don't auto-convert at equity rounds.
            trigger = (cr.conversion_trigger or "").lower().strip()
            if trigger in ("maturity", "change_of_control"):
                continue  # these instruments don't convert at equity rounds
            if trigger == "qualified_financing" and equity_round.investment_amount:
                # Some SAFEs require a minimum qualified financing threshold.
                # Without an explicit threshold, any priced round qualifies.
                pass  # proceed to convert
            # Default: no trigger specified → convert at first priced round (standard SAFE)

            # Calculate effective conversion price
            effective_price = round_price

            if cr.valuation_cap and pre_shares > 0:
                cap_price = Decimal(str(cr.valuation_cap)) / pre_shares
                effective_price = min(effective_price, cap_price)

            if cr.discount_rate:
                discounted_price = round_price * (Decimal("1") - Decimal(str(cr.discount_rate)))
                effective_price = min(effective_price, discounted_price)

            if effective_price <= 0:
                continue

            # For convertible notes, add accrued interest to principal
            # Use actual time from effective_date to conversion (equity round date)
            principal = Decimal(str(cr.investment_amount))
            if cr.interest_rate:
                years_outstanding = self._compute_years_outstanding(
                    cr.effective_date, equity_round.effective_date, cr.maturity_date
                )
                principal = principal * (Decimal("1") + Decimal(str(cr.interest_rate)) * Decimal(str(years_outstanding)))

            num_shares = principal / effective_price

            # Determine share class — converts into the equity round's class
            share_class = _share_class_for_round(equity_round.round_name)

            base_rights = ShareholderRights(
                liquidation_preference=cr.liq_pref_multiple,
                participation_rights=cr.liq_pref_participating,
                pro_rata_rights=cr.pro_rata,
                anti_dilution=cr.anti_dilution_type if cr.anti_dilution_type != "none" else None,
            )

            if cr.investors:
                investors_with_amounts = [inv for inv in cr.investors if inv.get("amount")]
                for inv in cr.investors:
                    inv_name = inv.get("name", "Unknown Investor")
                    inv_id = inv_name.lower().replace(" ", "_")
                    inv_amount = inv.get("amount")

                    if inv_amount:
                        inv_principal = Decimal(str(inv_amount))
                        if cr.interest_rate:
                            years_outstanding = self._compute_years_outstanding(
                                cr.effective_date, equity_round.effective_date, cr.maturity_date
                            )
                            inv_principal = inv_principal * (Decimal("1") + Decimal(str(cr.interest_rate)) * Decimal(str(years_outstanding)))
                        inv_shares = inv_principal / effective_price
                    elif investors_with_amounts:
                        inv_shares = num_shares / Decimal(str(max(len(cr.investors), 1)))
                    else:
                        inv_shares = num_shares / Decimal(str(max(len(cr.investors), 1)))

                    inv_rights = self._apply_investor_overrides(
                        base_rights, inv_name, investor_override_map,
                    )

                    converted_entries.append(ShareEntry(
                        shareholder_id=inv_id,
                        shareholder_name=inv_name,
                        share_class=share_class,
                        num_shares=inv_shares,
                        price_per_share=effective_price,
                        investment_date=_parse_investment_date(cr.effective_date or equity_round.effective_date),
                        rights=inv_rights,
                        metadata={
                            "round": cr.round_name,
                            "converted_at": equity_round.round_name,
                            "conversion_price": str(effective_price),
                            "original_instrument": cr.round_name,
                            "valuation_cap": cr.valuation_cap,
                            "discount_rate": cr.discount_rate,
                            "source_docs": cr.source_docs,
                        },
                    ))
            else:
                converted_entries.append(ShareEntry(
                    shareholder_id=f"converted_{cr.round_name.lower().replace(' ', '_')}",
                    shareholder_name=f"{cr.round_name} Holders",
                    share_class=share_class,
                    num_shares=num_shares,
                    price_per_share=effective_price,
                    investment_date=_parse_investment_date(cr.effective_date or equity_round.effective_date),
                    rights=base_rights,
                    metadata={
                        "round": cr.round_name,
                        "converted_at": equity_round.round_name,
                        "conversion_price": str(effective_price),
                        "valuation_cap": cr.valuation_cap,
                        "discount_rate": cr.discount_rate,
                        "source_docs": cr.source_docs,
                    },
                ))

            cr.converted = True

            logger.info(
                "[CAP_BRIDGE] Converted %s at %s: $%s → %s shares @ $%s/share (cap=%s, discount=%s)",
                cr.round_name, equity_round.round_name,
                cr.investment_amount, num_shares, effective_price,
                cr.valuation_cap, cr.discount_rate,
            )

        return converted_entries

    def _create_unconverted_entries(
        self,
        cr: ResolvedRound,
        investor_override_map: Dict[str, Dict[str, Any]],
    ) -> List[ShareEntry]:
        """Create entries for unconverted instruments (SAFEs/notes pre-trigger)."""
        entries: List[ShareEntry] = []
        if not cr.investment_amount:
            return entries

        share_class = _share_class_for_round(cr.round_name)
        num_shares = Decimal(str(cr.investment_amount))
        price_per_share = Decimal("1.00")

        base_rights = ShareholderRights(
            pro_rata_rights=cr.pro_rata,
        )

        if cr.investors:
            for inv in cr.investors:
                inv_name = inv.get("name", "Unknown Investor")
                inv_id = inv_name.lower().replace(" ", "_")
                inv_amount = inv.get("amount")

                inv_shares = Decimal(str(inv_amount)) if inv_amount else (
                    num_shares / Decimal(str(max(len(cr.investors), 1)))
                )

                inv_rights = self._apply_investor_overrides(
                    base_rights, inv_name, investor_override_map,
                )

                entries.append(ShareEntry(
                    shareholder_id=inv_id,
                    shareholder_name=inv_name,
                    share_class=share_class,
                    num_shares=inv_shares,
                    price_per_share=price_per_share,
                    investment_date=_parse_investment_date(cr.effective_date),
                    rights=inv_rights,
                    metadata={
                        "round": cr.round_name,
                        "unconverted": True,
                        "valuation_cap": cr.valuation_cap,
                        "discount_rate": cr.discount_rate,
                        "source_docs": cr.source_docs,
                    },
                ))
        else:
            entries.append(ShareEntry(
                shareholder_id=f"unconverted_{cr.round_name.lower().replace(' ', '_')}",
                shareholder_name=f"{cr.round_name} Holders (unconverted)",
                share_class=share_class,
                num_shares=num_shares,
                price_per_share=price_per_share,
                investment_date=_parse_investment_date(cr.effective_date),
                rights=base_rights,
                metadata={
                    "round": cr.round_name,
                    "unconverted": True,
                    "valuation_cap": cr.valuation_cap,
                    "discount_rate": cr.discount_rate,
                    "source_docs": cr.source_docs,
                },
            ))

        return entries

    def _compute_years_outstanding(
        self,
        issuance_date: Optional[str],
        conversion_date: Optional[str],
        maturity_date: Optional[str],
    ) -> float:
        """Compute the number of years between issuance and conversion/maturity.

        Uses actual dates when available. Falls back to 1 year only when no
        date information exists.
        """
        start = None
        end = None

        # Parse start date (when the note was issued)
        if issuance_date:
            try:
                start = datetime.fromisoformat(str(issuance_date)[:10])
            except (ValueError, TypeError):
                pass

        # Parse end date (when conversion happens)
        if conversion_date:
            try:
                end = datetime.fromisoformat(str(conversion_date)[:10])
            except (ValueError, TypeError):
                pass

        # If no conversion date, use maturity_date or today
        if end is None and maturity_date:
            try:
                end = datetime.fromisoformat(str(maturity_date)[:10])
            except (ValueError, TypeError):
                pass

        if end is None:
            end = datetime.now()

        if start is not None and end > start:
            return max(0, (end - start).days / 365.25)

        # No start date — fallback to 1 year
        return 1.0

    def _apply_investor_overrides(
        self,
        base_rights: ShareholderRights,
        investor_name: str,
        override_map: Dict[str, Dict[str, Any]],
    ) -> ShareholderRights:
        """Apply per-investor side letter overrides to base rights."""
        name_key = investor_name.lower().strip()
        overrides = override_map.get(name_key)
        if not overrides:
            return base_rights

        # Copy base rights and apply overrides
        return ShareholderRights(
            voting_rights=base_rights.voting_rights,
            board_seats=overrides.get("board_seats", base_rights.board_seats),
            protective_provisions=overrides.get("protective_provisions", base_rights.protective_provisions),
            liquidation_preference=overrides.get("liq_pref_multiple", base_rights.liquidation_preference),
            participation_rights=overrides.get("liq_pref_participating", base_rights.participation_rights),
            participation_cap=overrides.get("participation_cap", base_rights.participation_cap),
            cumulative_dividends=overrides.get("cumulative_dividends", base_rights.cumulative_dividends),
            dividend_rate=overrides.get("dividend_rate", base_rights.dividend_rate),
            anti_dilution=overrides.get("anti_dilution_type", base_rights.anti_dilution),
            pro_rata_rights=overrides.get("pro_rata", base_rights.pro_rata_rights),
            preemptive_rights=overrides.get("preemptive_rights", base_rights.preemptive_rights),
            rofr=overrides.get("rofr", base_rights.rofr),
            co_sale=overrides.get("co_sale", base_rights.co_sale),
            drag_along=overrides.get("drag_along", base_rights.drag_along),
            tag_along=overrides.get("tag_along", base_rights.tag_along),
            conversion_ratio=overrides.get("conversion_ratio", base_rights.conversion_ratio),
            mandatory_conversion=overrides.get("mandatory_conversion", base_rights.mandatory_conversion),
            information_rights=overrides.get("information_rights", base_rights.information_rights),
            registration_rights=overrides.get("registration_rights", base_rights.registration_rights),
            redemption_rights=overrides.get("redemption_rights", base_rights.redemption_rights),
            redemption_date=overrides.get("redemption_date", base_rights.redemption_date),
            pay_to_play=overrides.get("pay_to_play", base_rights.pay_to_play),
            founder_lockup_months=overrides.get("founder_lockup_months", base_rights.founder_lockup_months),
        )

    def _deserialise_entries(self, entries_json: List[Dict]) -> List[ShareEntry]:
        """Convert serialised share entry dicts back to ShareEntry objects."""
        entries: List[ShareEntry] = []
        for e in entries_json:
            rights_data = e.get("rights", {})
            rights = ShareholderRights(
                voting_rights=rights_data.get("voting_rights", True),
                board_seats=rights_data.get("board_seats", 0),
                protective_provisions=rights_data.get("protective_provisions", False),
                liquidation_preference=rights_data.get("liquidation_preference", 1.0),
                participation_rights=rights_data.get("participation_rights", False),
                participation_cap=rights_data.get("participation_cap"),
                cumulative_dividends=rights_data.get("cumulative_dividends", False),
                dividend_rate=rights_data.get("dividend_rate"),
                anti_dilution=rights_data.get("anti_dilution"),
                pro_rata_rights=rights_data.get("pro_rata_rights", False),
                preemptive_rights=rights_data.get("preemptive_rights", False),
                rofr=rights_data.get("rofr", False),
                co_sale=rights_data.get("co_sale", False),
                drag_along=rights_data.get("drag_along", False),
                tag_along=rights_data.get("tag_along", False),
                conversion_ratio=rights_data.get("conversion_ratio", 1.0),
                mandatory_conversion=rights_data.get("mandatory_conversion", False),
                information_rights=rights_data.get("information_rights", False),
                registration_rights=rights_data.get("registration_rights", False),
                redemption_rights=rights_data.get("redemption_rights", False),
                redemption_date=rights_data.get("redemption_date"),
                pay_to_play=rights_data.get("pay_to_play", False),
                founder_lockup_months=rights_data.get("founder_lockup_months"),
            )

            vesting = None
            v_data = e.get("vesting")
            if v_data:
                vesting_start = _parse_investment_date(v_data.get("start_date") or e.get("investment_date"))
                vesting = VestingSchedule(
                    total_shares=Decimal(e.get("num_shares", "0")),
                    cliff_months=v_data.get("cliff_months", 12),
                    vesting_months=v_data.get("total_months", 48),
                    start_date=vesting_start,
                    acceleration_on_change_of_control=v_data.get("acceleration_on_coc", False),
                )

            # Map share class string to enum
            sc_str = e.get("share_class", "common")
            try:
                share_class = ShareClass(sc_str)
            except ValueError:
                share_class = _share_class_for_round(sc_str)

            entries.append(ShareEntry(
                shareholder_id=e.get("shareholder_id", "unknown"),
                shareholder_name=e.get("shareholder_name", "Unknown"),
                share_class=share_class,
                num_shares=Decimal(e.get("num_shares", "0")),
                price_per_share=Decimal(e.get("price_per_share", "1")),
                investment_date=datetime.fromisoformat(e["investment_date"]) if e.get("investment_date") else datetime.now(),
                vesting_schedule=vesting,
                rights=rights,
                metadata=e.get("metadata", {}),
            ))

        return entries

    def _persist(
        self,
        company_id: str,
        fund_id: str,
        share_entries: List[Dict],
        document_ids: List[str],
        reconciliation_log: List[Dict],
        model_inputs: Dict,
        ownership_data: List[Dict],
        trigger_document_id: Optional[str],
        docs: List[Dict],
    ):
        """Persist cap table data to Supabase."""
        sb = self._get_sb()
        if not sb:
            return

        try:
            # Upsert main cap table record
            sb.table("company_cap_tables").upsert({
                "portfolio_id": fund_id,
                "company_id": company_id,
                "share_entries": share_entries,
                "document_ids": document_ids,
                "reconciliation_log": reconciliation_log,
                "model_inputs": model_inputs,
                "cap_table_json": {"ownership": ownership_data},
                "source": "extracted",
                "funding_data_source": f"document:{trigger_document_id}" if trigger_document_id else "multi_document",
            }, on_conflict="portfolio_id,company_id").execute()

            # Upsert join table entries
            cap_table_resp = (
                sb.table("company_cap_tables")
                .select("id")
                .eq("portfolio_id", fund_id)
                .eq("company_id", company_id)
                .limit(1)
                .execute()
            )
            if cap_table_resp.data:
                cap_table_id = cap_table_resp.data[0]["id"]
                for doc in docs:
                    doc_id = doc.get("id", "")
                    if not doc_id:
                        continue
                    try:
                        sb.table("cap_table_documents").upsert({
                            "cap_table_id": cap_table_id,
                            "document_id": doc_id,
                            "document_type": doc.get("document_type"),
                            "priority": DOC_PRIORITY.get(doc.get("document_type", ""), 10),
                        }, on_conflict="cap_table_id,document_id").execute()
                    except Exception as e:
                        logger.warning("[CAP_BRIDGE] Failed to upsert cap_table_documents for %s: %s", doc_id, e)

        except Exception as e:
            logger.error("[CAP_BRIDGE] Persist failed for company %s: %s", company_id, e, exc_info=True)

        # --- Also write to cap_table_entries ledger ---
        try:
            from app.services.cap_table_ledger import CapTableLedger
            ledger = CapTableLedger()
            ledger_entries = []
            for se in share_entries:
                entry = {
                    "shareholder_name": se.get("shareholder_name", "Unknown"),
                    "share_class": se.get("share_class", "common"),
                    "num_shares": float(se.get("num_shares", 0)),
                    "price_per_share": float(se.get("price_per_share", 0)),
                    "investment_date": se.get("investment_date"),
                }
                # Map rights
                rights = se.get("rights", {})
                if rights:
                    entry["voting_rights"] = rights.get("voting_rights", True)
                    entry["board_seat"] = rights.get("board_seats", 0) > 0 if isinstance(rights.get("board_seats"), int) else bool(rights.get("board_seats"))
                    entry["liquidation_pref"] = rights.get("liquidation_preference")
                    entry["participating"] = rights.get("participation_rights", False)
                    entry["participation_cap"] = rights.get("participation_cap")
                    entry["anti_dilution"] = rights.get("anti_dilution")
                    entry["pro_rata_rights"] = rights.get("pro_rata_rights", False)
                # Map vesting
                vesting = se.get("vesting", {})
                if vesting:
                    entry["vesting_cliff_months"] = vesting.get("cliff_months")
                    entry["vesting_total_months"] = vesting.get("total_months")
                # Infer instrument type from share_class
                sc = entry["share_class"]
                if sc in ("safe",):
                    entry["instrument_type"] = "safe"
                    entry["is_debt_instrument"] = False
                elif sc in ("convertible_note",):
                    entry["instrument_type"] = "convertible"
                    entry["is_debt_instrument"] = True
                elif sc in ("warrants",):
                    entry["instrument_type"] = "warrant"
                    entry["is_debt_instrument"] = False
                elif sc in ("options",):
                    entry["instrument_type"] = "option"
                    entry["is_debt_instrument"] = False
                else:
                    entry["instrument_type"] = "equity"
                    entry["is_debt_instrument"] = False
                # Stakeholder type from metadata or name
                entry["stakeholder_type"] = se.get("metadata", {}).get("stakeholder_type", "other")
                if trigger_document_id:
                    entry["document_id"] = trigger_document_id
                ledger_entries.append(entry)

            if ledger_entries:
                ledger.bulk_upsert(
                    company_id=company_id,
                    entries=ledger_entries,
                    fund_id=fund_id,
                    source="legal_docs",
                )
                logger.info("[CAP_BRIDGE] Wrote %d entries to cap_table_entries ledger", len(ledger_entries))
        except Exception as e:
            logger.warning("[CAP_BRIDGE] Failed to write to cap_table_entries ledger: %s", e)
