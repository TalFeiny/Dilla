"""
Scenario Branch Service
Fork-aware execution engine with parent chain inheritance.

Handles:
- Walking parent_branch_id chain to collect ancestor assumptions
- Sharing parent projection up to fork_period, then diverging
- Applying all override types (growth, burn, headcount, opex, one-time costs, funding)
- Multi-branch chart generation with real fork points and monthly granularity
- Probability-weighted expected value across sibling branches
- Recursive cascade delete through full tree
"""

import logging
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class LegalBranchOverride:
    """Legal parameter changes for a scenario branch.

    Represents "what if we accept these terms" — clause parameter
    overrides that get layered onto the company's base legal structure.
    """
    param_overrides: Dict[str, Any] = field(default_factory=dict)
    # param_type:applies_to → new value
    new_documents: List[str] = field(default_factory=list)
    # document IDs layered in (term sheet, amendment)
    removed_documents: List[str] = field(default_factory=list)
    # documents superseded
    description: str = ""
    # "Accept Investor X term sheet as-is"

DEFAULT_COST_PER_HEAD_MONTHLY = 15_000

BRANCH_COLORS = [
    "#6366f1",  # indigo (base)
    "#f59e0b",  # amber
    "#10b981",  # emerald
    "#ef4444",  # red
    "#8b5cf6",  # violet
    "#06b6d4",  # cyan
    "#f97316",  # orange
    "#ec4899",  # pink
]


class ScenarioBranchService:

    def __init__(self):
        from app.services.cash_flow_planning_service import CashFlowPlanningService
        self._cfp = CashFlowPlanningService()

    # ------------------------------------------------------------------
    # Active forecast loading
    # ------------------------------------------------------------------

    def _load_active_forecast_data(
        self, company_id: str
    ) -> Optional[List[Dict[str, Any]]]:
        """Try to load the active persisted forecast as a monthly dict list.

        Returns the same shape as CashFlowPlanningService output so it can
        be used as a drop-in replacement for base_forecast.
        """
        try:
            from app.services.forecast_persistence_service import (
                ForecastPersistenceService,
                FORECAST_KEY_TO_CATEGORY,
            )
            fps = ForecastPersistenceService()
            active = fps.get_active_forecast(company_id)
            if not active:
                return None

            full = fps.load_forecast(active["id"])
            if not full or not full.get("lines"):
                return None

            # Invert the key→category mapping
            cat_to_key = {v: k for k, v in FORECAST_KEY_TO_CATEGORY.items()}

            # Group lines by period
            by_period: Dict[str, Dict[str, float]] = {}
            for line in full["lines"]:
                period = line.get("period", "")[:7]
                cat = line.get("category", "")
                amt = line.get("amount", 0) or 0
                key = cat_to_key.get(cat, cat)
                by_period.setdefault(period, {"period": period})[key] = amt

            if not by_period:
                return None

            forecast = [by_period[p] for p in sorted(by_period)]
            logger.info(
                "Loaded active forecast (%s) with %d periods for company %s",
                active.get("name", active["id"]),
                len(forecast),
                company_id,
            )
            return forecast
        except Exception as e:
            logger.warning("Failed to load active forecast: %s", e)
            return None

    # ------------------------------------------------------------------
    # Parent chain walk
    # ------------------------------------------------------------------

    def get_ancestor_chain(self, branch_id: str, sb=None) -> List[Dict[str, Any]]:
        """
        Walk from branch_id up to root via parent_branch_id.
        Returns list ordered root-first: [root, ..., parent, self].
        Loads all branches for the company in one query to avoid N+1.
        """
        if not sb:
            from app.core.supabase_client import get_supabase_client
            sb = get_supabase_client()
        if not sb:
            return []

        result = sb.table("scenario_branches").select("*").eq("id", branch_id).execute()
        if not result.data:
            return []

        company_id = result.data[0]["company_id"]
        all_result = sb.table("scenario_branches").select("*").eq("company_id", company_id).execute()
        by_id = {b["id"]: b for b in (all_result.data or [])}

        chain = []
        current = by_id.get(branch_id)
        visited = set()
        while current and current["id"] not in visited:
            visited.add(current["id"])
            chain.append(current)
            pid = current.get("parent_branch_id")
            current = by_id.get(pid) if pid else None

        chain.reverse()
        return chain

    # ------------------------------------------------------------------
    # Assumption merging
    # ------------------------------------------------------------------

    def merge_assumptions(self, chain: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Merge assumptions down the chain (root → leaf). Child overrides parent.
        opex_adjustments: merge at sub-key level.
        growth_overrides_by_month: merge (child month wins).
        one_time_costs: concatenate.
        legal_overrides: merge using DOC_PRIORITY logic (child beats parent).
        """
        import json as _json

        merged: Dict[str, Any] = {}

        for branch in chain:
            raw = branch.get("assumptions", {})
            if isinstance(raw, str):
                try:
                    raw = _json.loads(raw)
                except (ValueError, TypeError):
                    raw = {}

            for key in (
                "revenue_growth_override", "revenue_override",
                "burn_rate_override", "burn_rate_delta", "burn_rate_pct_change",
                "cash_override", "funding_injection",
                "headcount_change", "gross_margin_override",
                # New driver keys
                "churn_rate", "nrr", "pricing_pct_change",
                "new_customer_growth_rate", "acv_override",
                "cac_override", "sales_cycle_months",
                "cost_per_head", "hiring_plan_monthly",
                "capex_override", "debt_service_monthly",
                "interest_rate", "outstanding_debt",
                "tax_rate", "working_capital_days",
                # Balance sheet drivers
                "dso_days", "dpo_days", "dio_days",
                "debt_drawdown", "deferred_revenue_delta",
                "depreciation_monthly",
            ):
                if key in raw:
                    merged[key] = raw[key]

            if "opex_adjustments" in raw:
                merged.setdefault("opex_adjustments", {}).update(raw["opex_adjustments"])

            if "growth_overrides_by_month" in raw:
                merged.setdefault("growth_overrides_by_month", {}).update(
                    raw["growth_overrides_by_month"]
                )

            if "one_time_costs" in raw:
                merged.setdefault("one_time_costs", []).extend(raw["one_time_costs"])

            # Legal overrides — child legal overrides beat parent
            if "legal_overrides" in raw:
                merged.setdefault("legal_overrides", {}).update(raw["legal_overrides"])

            # Contract changes — concatenate (child can add more changes)
            if "contract_changes" in raw:
                merged.setdefault("contract_changes", []).extend(raw["contract_changes"])

            # Model spec — child's spec wins (replaces parent entirely)
            if "model_spec" in raw:
                merged["model_spec"] = raw["model_spec"]

        return merged

    # ------------------------------------------------------------------
    # Fork-aware execution
    # ------------------------------------------------------------------

    def execute_branch(
        self,
        branch_id: str,
        company_id: str,
        forecast_months: int = 24,
        start_period: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Execute a single branch with full parent chain inheritance and
        fork-period-aware projection.

        Shares the parent projection up to fork_period, then applies
        merged assumptions and diverges.

        Returns dict with forecast, base_forecast, source_map, fork info.
        """
        from app.services.company_data_pull import pull_company_data

        chain = self.get_ancestor_chain(branch_id)
        if not chain:
            return {"error": f"Branch {branch_id} not found"}

        leaf = chain[-1]
        merged = self.merge_assumptions(chain)

        company_data_obj = pull_company_data(company_id)
        base_data = company_data_obj.to_forecast_seed()
        if not base_data.get("revenue"):
            return {"error": "No actuals data. Upload financials first."}

        if not start_period:
            today = date.today()
            start_period = f"{today.year}-{today.month:02d}"

        # Model construction path — branch carries a ModelSpec in assumptions
        model_spec_data = merged.get("model_spec")
        if model_spec_data:
            return self._execute_model_spec_branch(
                branch_id, leaf, chain, merged, model_spec_data,
                base_data, forecast_months, start_period, company_id,
            )

        fork_period = leaf.get("fork_period")
        fork_idx = self._period_to_index(fork_period, start_period) if fork_period else 0
        fork_idx = max(0, min(fork_idx, forecast_months - 1))

        # Full base projection — prefer active persisted forecast, fall back to computing
        base_forecast = self._load_active_forecast_data(company_id)
        if base_forecast and len(base_forecast) >= forecast_months:
            base_forecast = base_forecast[:forecast_months]
        else:
            base_forecast = self._cfp.build_monthly_cash_flow_model(
                base_data, months=forecast_months, start_period=start_period,
            )

        # Pre-compute contract change params for P&L builder if applicable
        contract_changes = merged.get("contract_changes", [])
        contract_pnl_params = self._contract_changes_to_pnl_params(
            contract_changes, company_id
        ) if contract_changes else {}

        if fork_idx == 0:
            branch_data = self._apply_overrides(base_data, merged)
            # If contract changes exist, re-seed from modified actuals
            if contract_pnl_params:
                branch_data = self._reseed_with_contract_changes(
                    branch_data, company_id, contract_pnl_params
                )
            branch_forecast = self._cfp.build_monthly_cash_flow_model(
                branch_data,
                months=forecast_months,
                monthly_overrides=merged.get("growth_overrides_by_month"),
                start_period=start_period,
            )
            branch_forecast = self._apply_opex_adjustments(
                branch_forecast, merged.get("opex_adjustments")
            )
            branch_forecast = self._apply_one_time_costs(
                branch_forecast, merged.get("one_time_costs", [])
            )
            source_map = ["branch"] * len(branch_forecast)
        else:
            parent_segment = base_forecast[:fork_idx]

            fork_state = base_forecast[fork_idx - 1]
            branched_data = self._snapshot_to_data(fork_state, base_data)
            branched_data = self._apply_overrides(branched_data, merged)
            if contract_pnl_params:
                branched_data = self._reseed_with_contract_changes(
                    branched_data, company_id, contract_pnl_params
                )

            branch_start = self._offset_period(start_period, fork_idx)
            branch_segment = self._cfp.build_monthly_cash_flow_model(
                branched_data,
                months=forecast_months - fork_idx,
                monthly_overrides=merged.get("growth_overrides_by_month"),
                start_period=branch_start,
            )
            branch_segment = self._apply_opex_adjustments(
                branch_segment, merged.get("opex_adjustments")
            )
            branch_segment = self._apply_one_time_costs(
                branch_segment, merged.get("one_time_costs", [])
            )

            branch_forecast = parent_segment + branch_segment
            source_map = ["parent"] * fork_idx + ["branch"] * len(branch_segment)

        result = {
            "branch_id": branch_id,
            "name": leaf.get("name", ""),
            "probability": leaf.get("probability"),
            "chain": [{"id": b["id"], "name": b["name"]} for b in chain],
            "assumptions": merged,
            "forecast": branch_forecast,
            "base_forecast": base_forecast,
            "source_map": source_map,
            "fork_month_index": fork_idx,
        }

        # Contract change summary if applicable
        if contract_changes:
            result["contract_changes_applied"] = contract_changes
            if contract_pnl_params:
                result["contract_pnl_params"] = contract_pnl_params

        # Legal branch overrides — resolve legal params if available
        legal_overrides = merged.get("legal_overrides")
        if legal_overrides:
            result["legal"] = self._resolve_legal_branch(
                company_id, legal_overrides, branch_forecast
            )

        return result

    # ------------------------------------------------------------------
    # Model spec branch execution
    # ------------------------------------------------------------------

    def _execute_model_spec_branch(
        self,
        branch_id: str,
        leaf: Dict[str, Any],
        chain: List[Dict],
        merged: Dict[str, Any],
        model_spec_data: Dict[str, Any],
        base_data: Dict[str, Any],
        forecast_months: int,
        start_period: str,
        company_id: str,
    ) -> Dict[str, Any]:
        """Execute a branch that carries a ModelSpec instead of simple overrides.

        The ModelSpec (stored as JSON in branch assumptions) gets deserialized
        and run through ModelSpecExecutor, producing the same forecast shape
        as the default cascade but with LLM-constructed curves + confidence bands.
        """
        from app.services.model_spec_schema import ModelSpec
        from app.services.model_spec_executor import ModelSpecExecutor

        spec = ModelSpec(**model_spec_data)
        executor = ModelSpecExecutor()

        # Resolve parent model if spec inherits from another branch's spec
        parent_result = None
        if spec.parent_model:
            for ancestor in chain[:-1]:
                ancestor_spec = (ancestor.get("assumptions") or {}).get("model_spec")
                if ancestor_spec and ancestor_spec.get("model_id") == spec.parent_model:
                    parent_spec = ModelSpec(**ancestor_spec)
                    parent_result = executor.execute(
                        parent_spec, base_data,
                        months=forecast_months, start_period=start_period,
                    )
                    break

        result = executor.execute(
            spec, base_data,
            months=forecast_months,
            start_period=start_period,
            parent_result=parent_result,
        )

        # Build base forecast for comparison (same as default path)
        base_forecast = self._load_active_forecast_data(company_id)
        if base_forecast and len(base_forecast) >= forecast_months:
            base_forecast = base_forecast[:forecast_months]
        else:
            base_forecast = self._cfp.build_monthly_cash_flow_model(
                base_data, months=forecast_months, start_period=start_period,
            )

        return {
            "branch_id": branch_id,
            "name": leaf.get("name", ""),
            "probability": leaf.get("probability"),
            "chain": [{"id": b["id"], "name": b["name"]} for b in chain],
            "assumptions": merged,
            "forecast": result.forecast,
            "base_forecast": base_forecast,
            "source_map": ["model_spec"] * len(result.forecast),
            "fork_month_index": 0,
            "model_spec": {
                "model_id": result.model_id,
                "narrative": result.narrative,
                "confidence_bands": result.confidence_bands,
                "milestones": result.milestones,
                "curves": result.curves,
            },
        }

    # ------------------------------------------------------------------
    # Multi-branch comparison
    # ------------------------------------------------------------------

    def execute_comparison(
        self,
        company_id: str,
        branch_ids: List[str],
        forecast_months: int = 24,
        start_period: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Run fork-aware projection for each branch and return side-by-side
        comparison with deltas, expected-value forecast, and multi-branch charts.
        """
        from app.services.company_data_pull import pull_company_data

        if not start_period:
            today = date.today()
            start_period = f"{today.year}-{today.month:02d}"

        base_data = pull_company_data(company_id).to_forecast_seed()
        if not base_data.get("revenue"):
            return {"error": "No actuals data. Upload financials first."}

        # Prefer active persisted forecast, fall back to computing
        base_forecast = self._load_active_forecast_data(company_id)
        if base_forecast and len(base_forecast) >= forecast_months:
            base_forecast = base_forecast[:forecast_months]
        else:
            base_forecast = self._cfp.build_monthly_cash_flow_model(
                base_data, months=forecast_months, start_period=start_period,
            )

        comparisons: List[Dict[str, Any]] = [{
            "branch_id": None,
            "name": "Base Case",
            "probability": None,
            "forecast": base_forecast,
            "source_map": ["base"] * len(base_forecast),
            "fork_month_index": 0,
        }]

        for bid in branch_ids:
            result = self.execute_branch(bid, company_id, forecast_months, start_period)
            if "error" in result:
                logger.warning("Skipping branch %s: %s", bid, result["error"])
                continue
            result["deltas"] = self._compute_deltas(base_forecast, result["forecast"])
            comparisons.append(result)

        ev_forecast = self._compute_expected_value(comparisons)
        charts = self._build_multi_branch_charts(comparisons)

        # Capital impact cascade: how each branch affects fundraising
        capital_impact = self._compute_capital_impact_cascade(
            comparisons, company_id, base_data, forecast_months
        )

        # Legal diff: if any branches have legal overrides, run clause diff
        legal_diffs = self._compute_legal_diffs(comparisons, company_id)

        result = {
            "company_id": company_id,
            "forecast_months": forecast_months,
            "start_period": start_period,
            "comparisons": comparisons,
            "expected_value": ev_forecast,
            "charts": charts,
            "capital_impact": capital_impact,
        }

        if legal_diffs:
            result["legal_diffs"] = legal_diffs

        return result

    # ------------------------------------------------------------------
    # Recursive delete
    # ------------------------------------------------------------------

    def delete_branch_recursive(self, branch_id: str) -> List[str]:
        """
        Delete a branch and ALL descendants via BFS.
        Deletes leaves first to respect FK constraints.
        Returns list of deleted IDs.
        """
        from app.core.supabase_client import get_supabase_client

        sb = get_supabase_client()
        if not sb:
            return []

        branch = sb.table("scenario_branches").select("id, company_id").eq("id", branch_id).execute()
        if not branch.data:
            return []

        company_id = branch.data[0]["company_id"]
        all_rows = (
            sb.table("scenario_branches")
            .select("id, parent_branch_id")
            .eq("company_id", company_id)
            .execute()
        )

        children_of: Dict[str, List[str]] = {}
        for b in (all_rows.data or []):
            pid = b.get("parent_branch_id")
            if pid:
                children_of.setdefault(pid, []).append(b["id"])

        # BFS collect
        to_delete: List[str] = []
        queue = [branch_id]
        while queue:
            cur = queue.pop(0)
            to_delete.append(cur)
            queue.extend(children_of.get(cur, []))

        # Delete leaves first
        for bid in reversed(to_delete):
            sb.table("scenario_branches").delete().eq("id", bid).execute()

        return to_delete

    # ------------------------------------------------------------------
    # Tree endpoint enrichment
    # ------------------------------------------------------------------

    def get_enriched_tree(
        self,
        company_id: str,
        forecast_months: int = 12,
        start_period: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Build the scenario tree with computed metrics per branch
        (final revenue, EBITDA, cash, runway) instead of metadata-only.
        """
        from app.core.supabase_client import get_supabase_client

        sb = get_supabase_client()
        if not sb:
            return {"company_id": company_id, "branches": []}

        result = sb.table("scenario_branches").select("*").eq("company_id", company_id).order("created_at").execute()
        branches = result.data or []

        enriched = {}
        for b in branches:
            exec_result = self.execute_branch(
                b["id"], company_id, forecast_months, start_period,
            )
            forecast = exec_result.get("forecast", [])
            last = forecast[-1] if forecast else {}
            enriched[b["id"]] = {
                **b,
                "children": [],
                "computed": {
                    "final_revenue": last.get("revenue", 0),
                    "final_ebitda": last.get("ebitda", 0),
                    "final_cash": last.get("cash_balance", 0),
                    "final_runway": last.get("runway_months", 0),
                },
            }

        # Build tree
        roots: List[Dict] = []
        for b in branches:
            node = enriched[b["id"]]
            pid = b.get("parent_branch_id")
            if pid and pid in enriched:
                enriched[pid]["children"].append(node)
            else:
                roots.append(node)

        return {"company_id": company_id, "branches": roots}

    # ------------------------------------------------------------------
    # Driver resolution
    # ------------------------------------------------------------------

    def resolve_drivers(
        self,
        branch_id: str,
        company_id: str,
    ) -> Dict[str, Any]:
        """
        For each driver in the registry, compute base / override / effective values
        for a given branch. Uses merged assumptions from the parent chain.

        Returns dict keyed by driver_id with full metadata + computed values.
        """
        from app.services.company_data_pull import pull_company_data
        from app.services.driver_registry import get_all_drivers, assumptions_to_drivers

        chain = self.get_ancestor_chain(branch_id)
        if not chain:
            return {"error": f"Branch {branch_id} not found"}

        merged = self.merge_assumptions(chain)
        base_data = pull_company_data(company_id).to_forecast_seed()

        # Map: driver_id → base value from actuals/defaults
        base_values = self._extract_base_driver_values(base_data)

        # Overridden drivers from branch assumptions
        overridden = assumptions_to_drivers(merged)

        all_drivers = get_all_drivers()
        result: Dict[str, Any] = {}

        for did, ddef in all_drivers.items():
            base_val = base_values.get(did)
            override_val = overridden.get(did, {}).get("value")
            has_override = override_val is not None

            # Compute effective value based on `how`
            if has_override:
                if ddef.how == "set":
                    effective = override_val
                elif ddef.how == "shift":
                    effective = (base_val or 0) + (override_val or 0)
                elif ddef.how == "scale":
                    effective = (base_val or 0) * (1 + (override_val or 0))
                else:
                    effective = override_val
                source = "branch"
            else:
                effective = base_val
                source = "base"

            result[did] = {
                "id": did,
                "label": ddef.label,
                "level": ddef.level,
                "unit": ddef.unit,
                "how": ddef.how,
                "base": base_val,
                "override": override_val,
                "effective": effective,
                "source": source,
                "nl_hint": ddef.nl_hint,
                "ripple": ddef.ripple,
                "range": list(ddef.range) if ddef.range else None,
                "computed": ddef.computed,
            }

        # Compute derived unit-economics drivers
        result = self._compute_derived_drivers(result)

        return result

    def _extract_base_driver_values(self, base_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract base driver values from actuals/seed data."""
        revenue = base_data.get("revenue") or base_data.get("arr") or 0
        gross_margin = base_data.get("gross_margin") or 0.65
        burn = base_data.get("burn_rate") or 0
        cash = base_data.get("cash_balance") or 0
        growth = base_data.get("growth_rate") or base_data.get("inferred_growth_rate") or 0

        # Use actuals-derived cost_per_head when available, else fall back to default
        cost_per_head = (
            base_data.get("cost_per_head")
            or DEFAULT_COST_PER_HEAD_MONTHLY
        )

        return {
            "revenue_growth": growth,
            "revenue_override": revenue,
            "gross_margin": gross_margin,
            "burn_rate": burn,
            "cash_override": cash,
            "funding_injection": 0,
            "headcount_change": 0,
            "payroll_cost_per_head": cost_per_head,
        }

    def _compute_derived_drivers(self, resolved: Dict[str, Any]) -> Dict[str, Any]:
        """Compute LTV and LTV:CAC from resolved driver values."""
        acv_entry = resolved.get("avg_contract_value", {})
        churn_entry = resolved.get("churn_rate", {})
        margin_entry = resolved.get("gross_margin", {})
        cac_entry = resolved.get("cac", {})

        acv = acv_entry.get("effective") or 0
        churn = churn_entry.get("effective") or 0
        margin = margin_entry.get("effective") or 0.65
        cac_val = cac_entry.get("effective") or 0

        # LTV = ACV * gross_margin / annual churn_rate
        # churn_rate is monthly, annualize: 1 - (1 - monthly)^12
        annual_churn = 1 - (1 - churn) ** 12 if churn and churn < 1 else churn
        ltv = (acv * margin / annual_churn) if annual_churn and acv else None

        if "ltv" in resolved:
            resolved["ltv"]["effective"] = round(ltv, 2) if ltv else None
            resolved["ltv"]["base"] = None
            resolved["ltv"]["source"] = "computed"

        ltv_cac = (ltv / cac_val) if ltv and cac_val else None
        if "ltv_cac_ratio" in resolved:
            resolved["ltv_cac_ratio"]["effective"] = round(ltv_cac, 2) if ltv_cac else None
            resolved["ltv_cac_ratio"]["base"] = None
            resolved["ltv_cac_ratio"]["source"] = "computed"

        return resolved

    # ------------------------------------------------------------------
    # Branch fuzzy match
    # ------------------------------------------------------------------

    def find_branch_by_name(
        self, company_id: str, name_query: str
    ) -> Optional[Dict[str, Any]]:
        """
        Fuzzy match a branch name for a company. Returns the best match or None.
        Used by the agent when referencing branches by name ("the downturn scenario").
        """
        from app.core.supabase_client import get_supabase_client

        sb = get_supabase_client()
        if not sb:
            return None

        result = sb.table("scenario_branches").select("*").eq("company_id", company_id).execute()
        branches = result.data or []
        if not branches:
            return None

        query_lower = name_query.lower().strip()

        # Exact match first
        for b in branches:
            if (b.get("name") or "").lower() == query_lower:
                return b

        # Substring match
        for b in branches:
            name = (b.get("name") or "").lower()
            if query_lower in name or name in query_lower:
                return b

        # Token overlap scoring
        query_tokens = set(query_lower.split())
        best, best_score = None, 0
        for b in branches:
            name_tokens = set((b.get("name") or "").lower().split())
            overlap = len(query_tokens & name_tokens)
            if overlap > best_score:
                best_score = overlap
                best = b

        return best if best_score > 0 else None

    # ------------------------------------------------------------------
    # Capital raising analysis
    # ------------------------------------------------------------------

    def analyze_capital_needs(
        self,
        branch_id: str,
        company_id: str,
        runway_threshold_months: int = 6,
        forecast_months: int = 24,
    ) -> Optional[Dict[str, Any]]:
        """
        When resolved drivers show runway < threshold, auto-compute:
        - Funding gap
        - Stage-appropriate round estimate
        - Pre-money valuation
        - Dilution estimate
        - Post-money ownership

        Returns None if runway is adequate.
        """
        exec_result = self.execute_branch(branch_id, company_id, forecast_months)
        if "error" in exec_result:
            return None

        forecast = exec_result.get("forecast", [])
        if not forecast:
            return None

        last = forecast[-1]
        runway = last.get("runway_months", 999)

        if runway >= runway_threshold_months:
            return None

        # Compute funding gap
        monthly_burn = abs(last.get("free_cash_flow", 0))
        if monthly_burn <= 0:
            return None

        target_runway = 18  # months
        current_cash = last.get("cash_balance", 0)
        cash_needed = (monthly_burn * target_runway) - max(current_cash, 0)
        if cash_needed <= 0:
            return None

        # Stage-appropriate round sizing from gap_filler benchmarks
        from app.services.company_data_pull import pull_company_data
        base_data = pull_company_data(company_id).to_forecast_seed()
        stage = base_data.get("funding_stage") or base_data.get("stage") or "Seed"

        round_estimate = self._estimate_round_size(stage, cash_needed)
        pre_money = self._estimate_pre_money(base_data, stage)
        dilution = round_estimate / (pre_money + round_estimate) if pre_money > 0 else 0.20

        # Estimate post-money ownership (simplified)
        founder_ownership = base_data.get("founder_ownership", 0.70)
        post_money_ownership = founder_ownership * (1 - dilution)

        runway_extension = round_estimate / monthly_burn if monthly_burn > 0 else 0

        return {
            "needs_funding": True,
            "current_runway_months": round(runway, 1),
            "monthly_burn": round(monthly_burn, 2),
            "funding_gap": round(cash_needed, 2),
            "round_estimate": round(round_estimate, 2),
            "pre_money_valuation": round(pre_money, 2),
            "dilution_pct": round(dilution, 4),
            "post_money_ownership": round(post_money_ownership, 4),
            "runway_extension_months": round(runway_extension, 1),
            "stage": stage,
            "target_runway_months": target_runway,
        }

    def _estimate_round_size(self, stage: str, cash_needed: float) -> float:
        """Stage-appropriate round size, at least enough to cover the gap."""
        typical_rounds = {
            "Pre-seed": 1_500_000,
            "Seed": 3_000_000,
            "Series A": 15_000_000,
            "Series B": 50_000_000,
            "Series C": 100_000_000,
            "Series D": 200_000_000,
        }
        typical = typical_rounds.get(stage, 5_000_000)
        return max(typical, cash_needed * 1.2)  # 20% buffer over gap

    def _estimate_pre_money(self, base_data: Dict[str, Any], stage: str) -> float:
        """Estimate pre-money from revenue multiple or last round."""
        revenue = base_data.get("revenue") or base_data.get("arr") or 0
        last_val = base_data.get("last_round_valuation") or base_data.get("inferred_valuation") or 0

        if last_val > 0:
            return last_val

        # Revenue multiple by stage
        multiples = {
            "Pre-seed": 20, "Seed": 15, "Series A": 12,
            "Series B": 10, "Series C": 8, "Series D": 6,
        }
        mult = multiples.get(stage, 10)
        if revenue > 0:
            return revenue * mult

        # Fallback: stage-based estimate
        stage_vals = {
            "Pre-seed": 5_000_000, "Seed": 10_000_000,
            "Series A": 50_000_000, "Series B": 150_000_000,
            "Series C": 400_000_000, "Series D": 800_000_000,
        }
        return stage_vals.get(stage, 20_000_000)

    # ------------------------------------------------------------------
    # Legal branch resolution
    # ------------------------------------------------------------------

    def _resolve_legal_branch(
        self,
        company_id: str,
        legal_overrides: Dict[str, Any],
        branch_forecast: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Resolve legal parameters for a branch, run cascade + legal signals.

        1. Load extracted docs for the company
        2. Resolve clause parameters with branch overrides applied
        3. Build cascade graph
        4. Detect legal signals against the branch forecast
        5. Identify constraints
        """
        from app.services.clause_parameter_registry import (
            ClauseParameterRegistry,
        )
        from app.services.cascade_engine import CascadeGraph
        from app.services.legal_signal_detector import detect_legal_signals

        # Load extracted documents
        extracted_docs = self._load_legal_documents(company_id)

        registry = ClauseParameterRegistry()
        branch_params = registry.resolve_with_overrides(
            company_id, extracted_docs, legal_overrides
        )

        # Build cascade graph from branch params
        cascade = CascadeGraph()
        cascade.build_from_clauses(branch_params)

        # Build a lightweight state object for signal detection
        financial_state = self._forecast_to_signal_state(branch_forecast)

        # Detect legal signals specific to this branch
        signals = detect_legal_signals(branch_params, financial_state, cascade)

        # Identify constraints
        constraints = cascade.identify_constraints()

        return {
            "params": {
                "count": len(branch_params.parameters),
                "conflicts": len(branch_params.conflicts),
                "gaps": branch_params.gaps,
                "instruments": [
                    {
                        "id": i.instrument_id,
                        "type": i.instrument_type,
                        "holder": i.holder,
                    }
                    for i in branch_params.instruments
                ],
            },
            "signals": [
                {
                    "type": s.signal_type,
                    "metric": s.metric,
                    "description": s.description,
                    "severity": s.severity,
                    "data": s.data,
                }
                for s in signals
            ],
            "constraints": [
                {
                    "description": c.description,
                    "constraint_type": c.constraint_type,
                    "source_clause": c.source_clause.source_clause_id
                    if c.source_clause else None,
                    "source_ref": c.source_clause.section_reference
                    if c.source_clause else None,
                }
                for c in constraints
            ],
            "cascade_node_count": len(cascade.nodes),
            "cascade_edge_count": len(cascade.edges),
        }

    def _load_legal_documents(self, company_id: str) -> List[Dict[str, Any]]:
        """Load all processed documents with legal clause data for a company."""
        from app.core.supabase_client import get_supabase_client

        sb = get_supabase_client()
        if not sb:
            return []

        legal_doc_types = [
            "sha", "term_sheet", "side_letter", "spa",
            "option_agreement", "warrant_agreement",
            "convertible_note", "safe", "loan_agreement",
            "credit_facility", "venture_debt",
            "articles_of_association", "amendment",
            "subscription_agreement", "guarantee",
            "indemnity_agreement", "escrow_agreement",
            "management_agreement", "ip_agreement",
            "services_agreement",
        ]

        try:
            resp = (
                sb.table("processed_documents")
                .select("id, document_type, extracted_data, created_at")
                .eq("company_id", company_id)
                .in_("document_type", legal_doc_types)
                .order("created_at", desc=False)
                .execute()
            )
            docs = resp.data or []

            # Flatten extracted_data into top-level dict for the registry
            result = []
            for doc in docs:
                extracted = doc.get("extracted_data", {})
                if isinstance(extracted, str):
                    import json as _json
                    try:
                        extracted = _json.loads(extracted)
                    except (ValueError, TypeError):
                        continue
                if not isinstance(extracted, dict):
                    continue
                entry = {
                    "id": doc["id"],
                    "document_type": doc.get("document_type", ""),
                    **extracted,
                }
                result.append(entry)

            return result

        except Exception as e:
            logger.warning(
                "Failed to load legal docs for %s: %s", company_id, e
            )
            return []

    def _forecast_to_signal_state(
        self, forecast: List[Dict[str, Any]]
    ) -> Any:
        """Build a lightweight state object from forecast for signal detection."""
        if not forecast:
            return None

        last = forecast[-1]

        class _BranchState:
            pass

        state = _BranchState()
        state.runway_months = last.get("runway_months")
        state.revenue = last.get("revenue", 0)
        state.ebitda = last.get("ebitda", 0)
        state.cash_balance = last.get("cash_balance", 0)
        state.free_cash_flow = last.get("free_cash_flow", 0)

        # Estimate DSCR from forecast if debt service is present
        debt_service = last.get("debt_service_monthly", 0)
        if debt_service and debt_service > 0:
            state.dscr = last.get("ebitda", 0) / (debt_service * 12) if debt_service else None
        else:
            state.dscr = None

        state.leverage_ratio = None

        # Trajectory estimation from forecast trend
        if len(forecast) >= 3:
            recent_ebitda = [m.get("ebitda", 0) for m in forecast[-3:]]
            if recent_ebitda[-1] < recent_ebitda[0]:
                state.burn_trajectory = "accelerating"
            elif recent_ebitda[-1] > recent_ebitda[0]:
                state.burn_trajectory = "improving"
            else:
                state.burn_trajectory = "stable"
        else:
            state.burn_trajectory = "stable"

        state.stage = None
        state.kpis = {}
        state.drivers = {}

        return state

    def _compute_legal_diffs(
        self,
        comparisons: List[Dict[str, Any]],
        company_id: str,
    ) -> Optional[Dict[str, Any]]:
        """
        If branches carry legal overrides, diff their resolved params
        against the base structure and against each other.

        Returns clause-diff results showing per-stakeholder dollar impact
        at multiple exit values.
        """
        legal_branches = [
            c for c in comparisons
            if c.get("branch_id") and c.get("legal")
        ]
        if not legal_branches:
            return None

        try:
            from app.services.clause_parameter_registry import (
                ClauseParameterRegistry,
            )
            from app.services.clause_diff_engine import ClauseDiffEngine

            extracted_docs = self._load_legal_documents(company_id)
            registry = ClauseParameterRegistry()
            diff_engine = ClauseDiffEngine()

            # Resolve base params (no overrides)
            base_params = registry.resolve_parameters(company_id, extracted_docs)

            # Resolve each legal branch's params
            branch_params = {}
            for comp in legal_branches:
                bid = comp["branch_id"]
                overrides = comp.get("assumptions", {}).get("legal_overrides", {})
                branch_params[bid] = registry.resolve_with_overrides(
                    company_id, extracted_docs, overrides
                )

            # Diff: base vs each branch
            diffs: Dict[str, Any] = {"base_vs_branch": {}, "pairwise": {}}

            for bid, params in branch_params.items():
                name = next(
                    (c["name"] for c in legal_branches if c["branch_id"] == bid),
                    bid,
                )
                result = diff_engine.diff(base_params, params)
                diffs["base_vs_branch"][name] = {
                    "delta_count": len(result.deltas),
                    "summary": result.summary,
                    "cost_of_capital": result.cost_of_capital_comparison,
                    "stakeholder_impacts": {
                        k: {
                            "ownership_delta": v.ownership_delta,
                            "alignment_shift": v.alignment_shift,
                            "rights_gained": v.new_rights_gained,
                            "rights_lost": v.rights_lost,
                        }
                        for k, v in result.stakeholder_impacts.items()
                    },
                    "constraint_changes": result.net_impact.constraint_changes,
                }

            # Pairwise diffs between legal branches
            branch_list = list(branch_params.items())
            for i in range(len(branch_list)):
                for j in range(i + 1, len(branch_list)):
                    bid_a, params_a = branch_list[i]
                    bid_b, params_b = branch_list[j]
                    name_a = next(
                        (c["name"] for c in legal_branches if c["branch_id"] == bid_a),
                        bid_a,
                    )
                    name_b = next(
                        (c["name"] for c in legal_branches if c["branch_id"] == bid_b),
                        bid_b,
                    )
                    result = diff_engine.diff(params_a, params_b)
                    diffs["pairwise"][f"{name_a} vs {name_b}"] = {
                        "delta_count": len(result.deltas),
                        "summary": result.summary,
                        "alignment_matrix": result.alignment_matrix,
                    }

            return diffs

        except Exception as e:
            logger.warning("Legal diff failed: %s", e)
            return None

    # ------------------------------------------------------------------
    # Private: override application
    # ------------------------------------------------------------------

    def _apply_overrides(
        self, base: Dict[str, Any], assumptions: Dict[str, Any]
    ) -> Dict[str, Any]:
        data = {**base}

        if "revenue_growth_override" in assumptions:
            data["growth_rate"] = assumptions["revenue_growth_override"]
        if "revenue_override" in assumptions:
            data["revenue"] = assumptions["revenue_override"]

        if "burn_rate_override" in assumptions:
            data["burn_rate"] = assumptions["burn_rate_override"]
        if "burn_rate_delta" in assumptions:
            data["burn_rate"] = (data.get("burn_rate") or 0) + assumptions["burn_rate_delta"]
        if "burn_rate_pct_change" in assumptions:
            data["burn_rate"] = (data.get("burn_rate") or 0) * (1 + assumptions["burn_rate_pct_change"])

        if "cash_override" in assumptions:
            data["cash_balance"] = assumptions["cash_override"]
        if "funding_injection" in assumptions:
            data["cash_balance"] = (data.get("cash_balance") or 0) + assumptions["funding_injection"]

        # Headcount → burn rate using configurable cost_per_head
        cost_per_head = assumptions.get("cost_per_head") or data.get("cost_per_head") or DEFAULT_COST_PER_HEAD_MONTHLY
        hc = assumptions.get("headcount_change")
        if hc and "burn_rate_delta" not in assumptions:
            data["burn_rate"] = (data.get("burn_rate") or 0) + hc * cost_per_head

        if "gross_margin_override" in assumptions:
            data["gross_margin"] = assumptions["gross_margin_override"]

        # Pass through new driver keys so the P&L engine can read them
        _PASSTHROUGH_KEYS = [
            "churn_rate", "nrr", "pricing_pct_change",
            "new_customer_growth_rate", "acv_override",
            "cac_override", "sales_cycle_months",
            "cost_per_head", "hiring_plan_monthly",
            "capex_override", "debt_service_monthly",
            "interest_rate", "outstanding_debt",
            "tax_rate", "working_capital_days",
        ]
        for key in _PASSTHROUGH_KEYS:
            if key in assumptions:
                data[key] = assumptions[key]

        return data

    def _apply_opex_adjustments(
        self,
        forecast: List[Dict[str, Any]],
        adjustments: Optional[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Post-process forecast to apply opex percentage adjustments.

        Treats pct_delta as multiplicative: rd_pct_delta of -0.30 means
        reduce R&D spending by 30% of its current value.
        Cascades the change through EBITDA → FCF → cash balance.
        """
        if not adjustments:
            return forecast

        cash_adj = 0.0
        for month in forecast:
            opex_delta = 0.0

            for key, spend_key in [
                ("rd_pct_delta", "rd_spend"),
                ("sm_pct_delta", "sm_spend"),
                ("ga_pct_delta", "ga_spend"),
            ]:
                if key in adjustments:
                    change = month[spend_key] * adjustments[key]
                    month[spend_key] = round(month[spend_key] + change, 2)
                    opex_delta += change

            month["total_opex"] = round(
                month["rd_spend"] + month["sm_spend"] + month["ga_spend"], 2
            )
            month["ebitda"] = round(month["gross_profit"] - month["total_opex"], 2)
            month["ebitda_margin"] = (
                round(month["ebitda"] / month["revenue"], 4)
                if month["revenue"] > 0 else -1.0
            )
            month["free_cash_flow"] = round(month["ebitda"] - month["capex"], 2)

            cash_adj -= opex_delta
            month["cash_balance"] = round(month["cash_balance"] + cash_adj, 2)

            if month["free_cash_flow"] < 0:
                month["runway_months"] = round(
                    max(0, month["cash_balance"] / (-month["free_cash_flow"])), 1
                )
            else:
                month["runway_months"] = 999

        return forecast

    def _apply_one_time_costs(
        self,
        forecast: List[Dict[str, Any]],
        costs: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Apply one-time costs at specific months.
        Each entry: {"period": "YYYY-MM", "amount": float, "label": str}
        """
        if not costs:
            return forecast

        by_period: Dict[str, float] = {}
        for item in costs:
            p = item.get("period", "")[:7]
            by_period[p] = by_period.get(p, 0) + item.get("amount", 0)

        for month in forecast:
            period = month.get("period", "")[:7]
            if period in by_period:
                cost = by_period[period]
                month["ebitda"] = round(month["ebitda"] - cost, 2)
                month["free_cash_flow"] = round(month["free_cash_flow"] - cost, 2)
                month["cash_balance"] = round(month["cash_balance"] - cost, 2)
            if month["free_cash_flow"] < 0:
                month["runway_months"] = round(
                    max(0, month["cash_balance"] / (-month["free_cash_flow"])), 1
                )

        return forecast

    # ------------------------------------------------------------------
    # Contract changes → P&L scenario params
    # ------------------------------------------------------------------

    def _contract_changes_to_pnl_params(
        self,
        changes: List[Dict[str, Any]],
        company_id: str,
    ) -> Dict[str, Any]:
        """Convert contract_changes list into params for PnlBuilder._pull_actuals().

        Supports actions:
            exclude       — remove all fpa_actuals for this contract
            modify_price  — multiply amounts by factor (e.g. 0.8 = 20% cut, 1.15 = 15% increase)
            terminate_early — zero out rows after effective date
            extend        — (future: generate new period rows beyond expiration)

        Returns: {excluded_sources, source_multipliers, terminated_sources}
        """
        excluded: List[str] = []
        multipliers: Dict[str, float] = {}
        terminated: Dict[str, str] = {}

        for change in changes:
            doc_id = change.get("document_id", "")
            source = f"document:{doc_id}"
            action = change.get("action", "")

            if action == "exclude":
                excluded.append(source)
            elif action == "modify_price":
                factor = change.get("factor", 1.0)
                multipliers[source] = factor
            elif action == "terminate_early":
                effective = change.get("effective", "")[:7]
                if effective:
                    terminated[source] = effective

        return {
            "excluded_sources": excluded or None,
            "source_multipliers": multipliers or None,
            "terminated_sources": terminated or None,
        }

    def _reseed_with_contract_changes(
        self,
        base_data: Dict[str, Any],
        company_id: str,
        contract_pnl_params: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Re-compute seed data from modified actuals after contract changes.

        Uses PnlBuilder._pull_actuals() with contract filters to get modified
        totals, then adjusts the base_data (revenue, burn_rate, etc.) accordingly.
        """
        from app.services.pnl_builder import PnlBuilder

        builder = PnlBuilder(company_id)
        modified_actuals, periods = builder._pull_actuals(
            start=None, end=None,
            excluded_sources=contract_pnl_params.get("excluded_sources"),
            source_multipliers=contract_pnl_params.get("source_multipliers"),
            terminated_sources=contract_pnl_params.get("terminated_sources"),
        )

        if not periods:
            return base_data

        # Recompute totals from the last period of modified actuals
        last = periods[-1]
        data = {**base_data}

        rev_total = 0.0
        cost_total = 0.0
        for key, vals in modified_actuals.items():
            if last not in vals:
                continue
            root = key.split("/")[0].split(":")[0]
            if root == "revenue":
                rev_total += vals[last]
            elif root in ("cogs", "opex_rd", "opex_sm", "opex_ga"):
                cost_total += vals[last]

        # Adjust base data with modified totals (annualize monthly figures)
        if rev_total > 0:
            data["revenue"] = rev_total * 12
        if cost_total > 0:
            data["burn_rate"] = cost_total

        return data

    # ------------------------------------------------------------------
    # Private: projection helpers
    # ------------------------------------------------------------------

    def _snapshot_to_data(
        self, month_state: Dict[str, Any], base: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Convert a forecast month's end state into company_data for next segment."""
        return {
            **base,
            "revenue": month_state.get("revenue", 0) * 12,
            "cash_balance": month_state.get("cash_balance", 0),
            "growth_rate": month_state.get("growth_rate_annual", base.get("growth_rate", 0.5)),
        }

    def _period_to_index(self, period: Optional[str], start: str) -> int:
        if not period:
            return 0
        try:
            fy, fm = int(period[:4]), int(period[5:7])
            sy, sm = int(start[:4]), int(start[5:7])
            return (fy - sy) * 12 + (fm - sm)
        except (ValueError, IndexError):
            return 0

    def _offset_period(self, start: str, months: int) -> str:
        try:
            y, m = int(start[:4]), int(start[5:7])
            m += months
            while m > 12:
                m -= 12
                y += 1
            while m < 1:
                m += 12
                y -= 1
            return f"{y}-{m:02d}"
        except (ValueError, IndexError):
            return start

    # ------------------------------------------------------------------
    # Private: comparison helpers
    # ------------------------------------------------------------------

    def _compute_capital_impact_cascade(
        self,
        comparisons: List[Dict[str, Any]],
        company_id: str,
        base_data: Dict[str, Any],
        forecast_months: int,
    ) -> Dict[str, Any]:
        """Compute how each branch scenario impacts capital raising plans.

        For each branch, calculates:
        - Runway trajectory (when cash hits zero)
        - Whether/when fundraising is needed
        - Implied round size, dilution, and post-money ownership
        - How the branch's growth trajectory affects valuation multiples
        - Net impact: which scenario is best/worst for founder economics

        Returns a dict with per-branch capital analysis + summary comparison.
        """
        stage = base_data.get("funding_stage") or base_data.get("stage") or "Seed"
        founder_ownership = base_data.get("founder_ownership", 0.70)

        branch_analyses: List[Dict[str, Any]] = []

        for comp in comparisons:
            forecast = comp.get("forecast", [])
            if not forecast:
                continue

            name = comp.get("name", "Unknown")
            bid = comp.get("branch_id")
            is_base = bid is None

            # Find cash-zero month (runway exhaustion)
            cash_zero_month = None
            min_cash_month = None
            min_cash = float("inf")
            for i, month in enumerate(forecast):
                cash = month.get("cash_balance", 0) or 0
                if cash < min_cash:
                    min_cash = cash
                    min_cash_month = i
                if cash <= 0 and cash_zero_month is None:
                    cash_zero_month = i

            last = forecast[-1]
            first = forecast[0]

            # Revenue trajectory
            start_rev = first.get("revenue", 0) or 0
            end_rev = last.get("revenue", 0) or 0
            if start_rev > 0:
                total_rev_growth = (end_rev / start_rev) - 1
                annualized_growth = ((end_rev / start_rev) ** (12 / max(len(forecast), 1))) - 1
            else:
                total_rev_growth = 0
                annualized_growth = 0

            # Average monthly burn (last 6 months)
            recent_months = forecast[-min(6, len(forecast)):]
            avg_fcf = sum(m.get("free_cash_flow", 0) or 0 for m in recent_months) / len(recent_months)
            monthly_burn = abs(avg_fcf) if avg_fcf < 0 else 0

            # Current runway
            end_cash = last.get("cash_balance", 0) or 0
            runway_at_end = end_cash / monthly_burn if monthly_burn > 0 else 999

            # Does this branch need funding?
            needs_funding = cash_zero_month is not None or runway_at_end < 6

            # Capital raising implications
            capital_plan = None
            if needs_funding:
                # When should they raise? (6 months before cash-zero, or now if already tight)
                if cash_zero_month is not None:
                    raise_by_month = max(0, cash_zero_month - 6)
                    raise_period = forecast[raise_by_month].get("period", "") if raise_by_month < len(forecast) else ""
                else:
                    raise_by_month = max(0, len(forecast) - 12)
                    raise_period = forecast[raise_by_month].get("period", "") if raise_by_month < len(forecast) else ""

                # Revenue at raise time (determines valuation)
                raise_month_data = forecast[raise_by_month] if raise_by_month < len(forecast) else last
                rev_at_raise = raise_month_data.get("revenue", 0) or 0
                arr_at_raise = rev_at_raise * 12

                # Round sizing: 18 months of runway from raise point
                target_runway = 18
                cash_at_raise = raise_month_data.get("cash_balance", 0) or 0
                # Use burn at raise point, not end
                burn_at_raise = abs(raise_month_data.get("free_cash_flow", 0) or avg_fcf)
                cash_needed = max(0, (burn_at_raise * target_runway) - max(cash_at_raise, 0))

                round_size = self._estimate_round_size(stage, cash_needed)

                # Valuation: growth-adjusted multiple
                # Higher growth = higher multiple = less dilution
                base_multiples = {
                    "Pre-seed": 20, "Seed": 15, "Series A": 12,
                    "Series B": 10, "Series C": 8, "Series D": 6,
                }
                base_mult = base_multiples.get(stage, 10)

                # Growth premium/discount: +50% growth = +2x multiple, -50% = -2x
                growth_premium = min(2.0, max(-0.5, annualized_growth)) * 4
                effective_multiple = max(3, base_mult + growth_premium)

                pre_money = arr_at_raise * effective_multiple
                if pre_money < round_size:
                    pre_money = round_size * 3  # Floor: at least 3x round size

                dilution = round_size / (pre_money + round_size) if pre_money > 0 else 0.25
                post_money_ownership = founder_ownership * (1 - dilution)
                runway_extension = round_size / burn_at_raise if burn_at_raise > 0 else 0

                capital_plan = {
                    "needs_funding": True,
                    "raise_by_period": raise_period,
                    "raise_by_month_index": raise_by_month,
                    "cash_zero_month": cash_zero_month,
                    "cash_zero_period": forecast[cash_zero_month].get("period", "") if cash_zero_month is not None and cash_zero_month < len(forecast) else None,
                    "arr_at_raise": round(arr_at_raise, 0),
                    "growth_at_raise": round(annualized_growth, 4),
                    "effective_multiple": round(effective_multiple, 1),
                    "pre_money_valuation": round(pre_money, 0),
                    "round_size": round(round_size, 0),
                    "dilution_pct": round(dilution, 4),
                    "post_money_ownership": round(post_money_ownership, 4),
                    "runway_extension_months": round(runway_extension, 1),
                    "monthly_burn_at_raise": round(burn_at_raise, 0),
                }
            else:
                capital_plan = {
                    "needs_funding": False,
                    "reason": "Sufficient runway through forecast horizon",
                    "end_cash": round(end_cash, 0),
                    "runway_months": round(runway_at_end, 1),
                }

            analysis = {
                "branch_name": name,
                "branch_id": bid,
                "is_base": is_base,
                "revenue_trajectory": {
                    "start": round(start_rev, 0),
                    "end": round(end_rev, 0),
                    "total_growth": round(total_rev_growth, 4),
                    "annualized_growth": round(annualized_growth, 4),
                },
                "cash_trajectory": {
                    "start": round(first.get("cash_balance", 0) or 0, 0),
                    "end": round(end_cash, 0),
                    "minimum": round(min_cash, 0),
                    "minimum_month": min_cash_month,
                    "cash_zero_month": cash_zero_month,
                },
                "burn_profile": {
                    "avg_monthly_burn": round(monthly_burn, 0),
                    "runway_at_end": round(runway_at_end, 1),
                },
                "capital_plan": capital_plan,
            }

            branch_analyses.append(analysis)

        # Summary: rank branches by founder economics (post-money ownership)
        funded_branches = [
            a for a in branch_analyses
            if a["capital_plan"].get("needs_funding")
        ]
        unfunded = [
            a for a in branch_analyses
            if not a["capital_plan"].get("needs_funding")
        ]

        # Best scenario = highest post-money ownership (least dilution)
        # or no funding needed at all
        ranking = []
        for a in unfunded:
            ranking.append({
                "branch": a["branch_name"],
                "score": 1.0,  # No dilution = best
                "reason": f"No funding needed. {a['capital_plan'].get('runway_months', 0):.0f} months runway.",
            })
        for a in sorted(funded_branches, key=lambda x: x["capital_plan"].get("post_money_ownership", 0), reverse=True):
            cp = a["capital_plan"]
            ranking.append({
                "branch": a["branch_name"],
                "score": cp.get("post_money_ownership", 0),
                "reason": (
                    f"Raise ${cp.get('round_size', 0):,.0f} at "
                    f"${cp.get('pre_money_valuation', 0):,.0f} pre-money "
                    f"({cp.get('dilution_pct', 0):.1%} dilution). "
                    f"Post-money ownership: {cp.get('post_money_ownership', 0):.1%}."
                ),
            })

        return {
            "branches": branch_analyses,
            "ranking": ranking,
            "stage": stage,
            "founder_ownership_current": founder_ownership,
        }

    def _compute_deltas(
        self, base: List[Dict], branch: List[Dict]
    ) -> List[Dict[str, Any]]:
        metrics = [
            "revenue", "ebitda", "cash_balance", "runway_months",
            "total_opex", "free_cash_flow",
        ]
        deltas = []
        for i in range(min(len(base), len(branch))):
            d: Dict[str, Any] = {"period": branch[i].get("period", "")}
            for key in metrics:
                bv = base[i].get(key, 0) or 0
                sv = branch[i].get(key, 0) or 0
                d[key] = {
                    "base": round(bv, 2),
                    "scenario": round(sv, 2),
                    "diff": round(sv - bv, 2),
                    "pct": round((sv - bv) / bv * 100, 1) if bv else 0,
                }
            deltas.append(d)
        return deltas

    def _compute_expected_value(
        self, comparisons: List[Dict[str, Any]]
    ) -> Optional[List[Dict[str, Any]]]:
        """Probability-weighted expected value across branches with probability set."""
        weighted = [
            c for c in comparisons
            if c.get("branch_id") and c.get("probability") is not None
        ]
        if not weighted:
            return None

        total_prob = sum(c["probability"] for c in weighted)
        if total_prob <= 0:
            return None

        weights = [c["probability"] / total_prob for c in weighted]
        n = min(len(c["forecast"]) for c in weighted)
        if n == 0:
            return None

        keys = [
            "revenue", "cogs", "gross_profit", "ebitda",
            "total_opex", "free_cash_flow", "cash_balance",
        ]
        ev: List[Dict[str, Any]] = []
        for i in range(n):
            row: Dict[str, Any] = {"period": weighted[0]["forecast"][i].get("period", "")}
            for k in keys:
                row[k] = round(
                    sum(w * (c["forecast"][i].get(k, 0) or 0) for w, c in zip(weights, weighted)),
                    2,
                )
            ev.append(row)
        return ev

    # ------------------------------------------------------------------
    # Private: chart generation
    # ------------------------------------------------------------------

    def _build_multi_branch_charts(
        self, comparisons: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Monthly branched-line charts with real fork points and N branches.
        One chart per metric.
        """
        if not comparisons:
            return []

        base_forecast = comparisons[0].get("forecast", [])
        labels = [m.get("period", f"M{i+1}") for i, m in enumerate(base_forecast)]

        charts: List[Dict[str, Any]] = []
        for metric, title, fmt in [
            ("revenue", "Revenue", "$"),
            ("gross_profit", "Gross Profit", "$"),
            ("ebitda", "EBITDA", "$"),
            ("cash_balance", "Cash Balance", "$"),
            ("runway_months", "Runway", "#"),
        ]:
            series = []
            annotations = []
            seen_forks: set = set()

            for idx, comp in enumerate(comparisons):
                forecast = comp.get("forecast", [])
                values = [m.get(metric, 0) for m in forecast]
                while len(values) < len(labels):
                    values.append(values[-1] if values else 0)

                is_base = comp.get("branch_id") is None
                series.append({
                    "name": comp.get("name", f"Branch {idx}"),
                    "data": values,
                    "style": "solid" if is_base else "dashed",
                    "color": BRANCH_COLORS[idx % len(BRANCH_COLORS)],
                    "branch_id": comp.get("branch_id"),
                })

                fork_idx = comp.get("fork_month_index", 0)
                if not is_base and fork_idx > 0 and fork_idx not in seen_forks:
                    seen_forks.add(fork_idx)
                    annotations.append({
                        "type": "fork_point",
                        "x": labels[fork_idx] if fork_idx < len(labels) else labels[-1],
                        "x_index": fork_idx,
                        "label": f"Fork: {comp.get('name', '')}",
                    })

            charts.append({
                "type": "branched_line",
                "title": f"{title} Comparison",
                "x_axis": labels,
                "format": fmt,
                "series": series,
                "annotations": annotations,
            })

        return charts


# ------------------------------------------------------------------
# FPA Chart Helpers
# Reusable builders for fpa_forecast, fpa_cash_flow, etc.
# ------------------------------------------------------------------

def build_fpa_line_chart(
    forecast: List[Dict[str, Any]],
    metric: str,
    title: str,
    fmt: str = "$",
    color: str = "#6366f1",
) -> Dict[str, Any]:
    """Single-series line chart from a forecast array."""
    labels = [m.get("period", f"M{i+1}") for i, m in enumerate(forecast)]
    values = [m.get(metric, 0) or 0 for m in forecast]
    return {
        "type": "line",
        "title": title,
        "x_axis": labels,
        "format": fmt,
        "series": [{"name": title, "data": values, "color": color}],
    }


def build_fpa_stacked_bar(
    forecast: List[Dict[str, Any]],
    metrics: List[tuple],  # [(key, label, color), ...]
    title: str,
    fmt: str = "$",
) -> Dict[str, Any]:
    """Stacked bar chart from a forecast array."""
    labels = [m.get("period", f"M{i+1}") for i, m in enumerate(forecast)]
    series = []
    for key, label, color in metrics:
        values = [m.get(key, 0) or 0 for m in forecast]
        series.append({"name": label, "data": values, "color": color})
    return {
        "type": "stacked_bar",
        "title": title,
        "x_axis": labels,
        "format": fmt,
        "series": series,
    }


def build_forecast_charts(forecast: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Standard chart set for fpa_forecast / fpa_cash_flow results."""
    if not forecast:
        return []
    return [
        build_fpa_line_chart(forecast, "revenue", "Revenue", "$", "#6366f1"),
        build_fpa_line_chart(forecast, "ebitda", "EBITDA", "$", "#10b981"),
        build_fpa_line_chart(forecast, "cash_balance", "Cash Balance", "$", "#f59e0b"),
        build_fpa_line_chart(forecast, "runway_months", "Runway (Months)", "#", "#ef4444"),
        build_fpa_stacked_bar(
            forecast,
            [
                ("rd_spend", "R&D", "#8b5cf6"),
                ("sm_spend", "S&M", "#06b6d4"),
                ("ga_spend", "G&A", "#f97316"),
            ],
            "OpEx Breakdown",
        ),
    ]
