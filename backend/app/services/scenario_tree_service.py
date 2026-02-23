"""
Scenario Tree Service
Builds branching scenario trees from per-company growth path assumptions.
Each company can have N alternative growth trajectories; the tree is the
cartesian product of paths, pruned by probability.

At each node: revenue projections (via RevenueProjectionService), valuation,
ownership (dilution from predicted rounds), and fund-level DPI/TVPI.
"""

import logging
import uuid
from dataclasses import dataclass, field
from itertools import product
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class GrowthPath:
    """A single company's year-by-year growth assumption."""
    company_name: str
    yearly_growth_rates: List[float]  # e.g. [1.40, 1.60, 1.00] = 140%, 160%, 100%
    label: str                        # "Endex Bull Case"
    probability: float = 0.5          # path-level probability
    scenario_type: str = "custom"     # "bull", "base", "bear", or "custom"


@dataclass
class CompanySnapshot:
    """State of one company at a single tree node."""
    revenue: float
    valuation: float
    growth_rate: float
    ownership_pct: float        # our ownership after dilution
    dpi_contribution: float     # this company's contribution to fund DPI
    gross_margin: float = 0.0
    ebitda: float = 0.0
    burn_rate: float = 0.0
    cash_balance: float = 0.0
    runway_months: float = 0.0
    stage: str = ""
    sector: str = ""
    predicted_round: Optional[Dict[str, Any]] = None
    year: int = 0


@dataclass
class FundSnapshot:
    """Fund-level metrics at a single tree node."""
    nav: float = 0.0
    dpi: float = 0.0
    tvpi: float = 0.0
    rvpi: float = 0.0
    irr: float = 0.0
    total_invested: float = 0.0
    total_value: float = 0.0
    total_distributed: float = 0.0


@dataclass
class ScenarioNode:
    """A single node in the scenario tree."""
    node_id: str
    year: int
    companies: Dict[str, CompanySnapshot]
    children: List["ScenarioNode"]
    probability: float                     # conditional probability of this branch
    label: str
    fund_metrics: Optional[FundSnapshot] = None


@dataclass
class ScenarioPath:
    """A root-to-leaf path through the tree."""
    path_id: str
    labels: List[str]
    nodes: List[ScenarioNode]
    cumulative_probability: float
    final_fund: Optional[FundSnapshot] = None
    scenario_types: List[str] = field(default_factory=list)  # e.g. ["bull", "base"]


@dataclass
class ScenarioTree:
    """Top-level tree container."""
    root: Optional[ScenarioNode] = None
    paths: List[ScenarioPath] = field(default_factory=list)
    fund_size: float = 0.0
    companies: List[str] = field(default_factory=list)
    expected_value: Optional[FundSnapshot] = None
    sensitivity: Dict[str, float] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Stage constants (mirrors intelligent_gap_filler STAGE_TYPICAL_ROUND)
# ---------------------------------------------------------------------------

STAGE_TYPICAL_ROUND = {
    "Pre-seed":  {"amount": 1_500_000,   "dilution": 0.15},
    "Seed":      {"amount": 3_000_000,   "dilution": 0.15},
    "Series A":  {"amount": 15_000_000,  "dilution": 0.20},
    "Series B":  {"amount": 50_000_000,  "dilution": 0.15},
    "Series C":  {"amount": 100_000_000, "dilution": 0.12},
    "Series D":  {"amount": 200_000_000, "dilution": 0.10},
    "Series E":  {"amount": 350_000_000, "dilution": 0.08},
}

STAGE_ORDER = ["Pre-seed", "Seed", "Series A", "Series B", "Series C", "Series D", "Series E"]

# Exit multiples by stage (midpoint estimates for PWERM leaf valuation)
EXIT_MULTIPLES = {
    "Pre-seed": 50, "Seed": 30, "Series A": 20,
    "Series B": 15, "Series C": 10, "Series D": 8, "Series E": 6,
}

# PWERM exit scenario probabilities and multiples
# At leaf nodes, we probability-weight across exit types
PWERM_EXIT_SCENARIOS = {
    "ipo": {"probability": 0.15, "multiple_premium": 1.5, "pref_coverage": 1.0},
    "strategic": {"probability": 0.35, "multiple_premium": 1.0, "pref_coverage": 1.0},
    "secondary": {"probability": 0.30, "multiple_premium": 0.7, "pref_coverage": 0.8},
    "downside": {"probability": 0.20, "multiple_premium": 0.3, "pref_coverage": 0.5},
}

# Sector heat multipliers for pre-money valuation
SECTOR_HEAT = {
    "ai_first": 1.3, "defense": 1.3, "fintech": 1.1,
    "vertical_saas": 1.15, "saas": 1.0, "marketplace": 0.95,
    "services": 0.8, "hardware": 0.85,
}


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------

class ScenarioTreeService:
    """Builds and evaluates branching scenario trees."""

    def build_tree(
        self,
        company_paths: Dict[str, List[GrowthPath]],
        base_company_data: Dict[str, Dict],
        fund_context: Dict,
        years: int = 5,
    ) -> ScenarioTree:
        """
        Build a branching tree from per-company growth paths.

        Args:
            company_paths: {company_name: [GrowthPath, ...]}
            base_company_data: {company_name: {revenue, valuation, stage, ownership_pct,
                                               sector, investor_quality, ...}}
            fund_context: {fund_size, total_invested, current_dpi}
            years: projection horizon
        """
        company_names = sorted(company_paths.keys())
        fund_size = fund_context.get("fund_size", 260_000_000)
        total_invested = fund_context.get("total_invested", 0)

        # Enumerate every combination of paths across companies
        path_lists = [company_paths[c] for c in company_names]
        combos = list(product(*path_lists))

        # Root node (year 0 — current state)
        root_snapshots: Dict[str, CompanySnapshot] = {}
        for cname in company_names:
            cd = base_company_data.get(cname, {})
            revenue = cd.get("revenue") or cd.get("arr") or cd.get("inferred_revenue") or 0
            valuation = cd.get("valuation") or cd.get("inferred_valuation") or 0
            raw_ownership = cd.get("ownership_pct", 10)
            # DB stores ownership as whole-number percentage (10 = 10%); convert to decimal
            ownership = raw_ownership / 100 if raw_ownership > 1 else raw_ownership
            root_snapshots[cname] = CompanySnapshot(
                revenue=revenue,
                valuation=valuation,
                growth_rate=0,
                ownership_pct=ownership,
                dpi_contribution=0,
                stage=cd.get("stage", "Series A"),
            )

        root_fund = self._compute_fund_snapshot(root_snapshots, fund_context)
        root = ScenarioNode(
            node_id="root",
            year=0,
            companies=root_snapshots,
            children=[],
            probability=1.0,
            label="Current State",
            fund_metrics=root_fund,
        )

        all_paths: List[ScenarioPath] = []

        for combo in combos:
            combo_prob = 1.0
            for gp in combo:
                combo_prob *= gp.probability

            # Skip extremely low-probability combos
            if combo_prob < 0.01:
                continue

            combo_label_parts = [gp.label for gp in combo]

            # Walk year-by-year for this combination
            parent_node = root
            path_nodes = [root]
            current_snapshots = dict(root_snapshots)

            max_years = min(years, max(len(gp.yearly_growth_rates) for gp in combo))

            for yr in range(1, max_years + 1):
                year_snapshots: Dict[str, CompanySnapshot] = {}

                for idx, cname in enumerate(company_names):
                    gp = combo[idx]
                    prev = current_snapshots[cname]
                    cd = base_company_data.get(cname, {})

                    # Growth rate for this year (pad with last rate if path is shorter)
                    if yr - 1 < len(gp.yearly_growth_rates):
                        growth_rate = gp.yearly_growth_rates[yr - 1]
                    else:
                        growth_rate = gp.yearly_growth_rates[-1] if gp.yearly_growth_rates else 0.0

                    snap = self._project_company_snapshot(
                        prev_snapshot=prev,
                        growth_rate=growth_rate,
                        year=yr,
                        company_data=cd,
                    )
                    year_snapshots[cname] = snap

                fund_snap = self._compute_fund_snapshot(year_snapshots, fund_context)
                yr_label = ", ".join(
                    f"{cname} {combo[i].yearly_growth_rates[yr-1]*100 if yr-1 < len(combo[i].yearly_growth_rates) else 0:.0f}%"
                    for i, cname in enumerate(company_names)
                    if yr - 1 < len(combo[i].yearly_growth_rates)
                )

                node = ScenarioNode(
                    node_id=str(uuid.uuid4())[:8],
                    year=yr,
                    companies=year_snapshots,
                    children=[],
                    probability=combo_prob,
                    label=f"Year {yr}: {yr_label}",
                    fund_metrics=fund_snap,
                )

                parent_node.children.append(node)
                path_nodes.append(node)
                parent_node = node
                current_snapshots = year_snapshots

            path = ScenarioPath(
                path_id=str(uuid.uuid4())[:8],
                labels=combo_label_parts,
                nodes=path_nodes,
                cumulative_probability=combo_prob,
                final_fund=path_nodes[-1].fund_metrics,
                scenario_types=[gp.scenario_type for gp in combo],
            )
            all_paths.append(path)

        result = ScenarioTree(
            root=root,
            paths=all_paths,
            fund_size=fund_size,
            companies=company_names,
        )
        result.expected_value = self.evaluate_expected_value(result)
        result.sensitivity = self.sensitivity_by_company(result)
        return result

    # ------------------------------------------------------------------
    # Projection helpers
    # ------------------------------------------------------------------

    def _project_company_snapshot(
        self,
        prev_snapshot: CompanySnapshot,
        growth_rate: float,
        year: int,
        company_data: Dict,
    ) -> CompanySnapshot:
        """Project a single company forward one year."""
        from app.services.revenue_projection_service import RevenueProjectionService

        base_revenue = prev_snapshot.revenue or 1
        sector = company_data.get("sector", "saas")
        stage = prev_snapshot.stage

        # Use RevenueProjectionService for margin calculation
        projections = RevenueProjectionService.project_revenue_with_decay(
            base_revenue=base_revenue,
            initial_growth=growth_rate,
            years=1,
            stage=stage,
            sector=sector,
            investor_quality=company_data.get("investor_quality"),
            geography=company_data.get("geography"),
            return_projections=True,
        )
        if projections and isinstance(projections, list):
            proj = projections[-1]
            new_revenue = proj.get("revenue", base_revenue * (1 + growth_rate))
            gross_margin = proj.get("gross_margin", 0.65)
        else:
            new_revenue = base_revenue * (1 + growth_rate)
            gross_margin = 0.65

        # Valuation = revenue * stage-appropriate multiple
        exit_mult = EXIT_MULTIPLES.get(stage, 12)
        heat = SECTOR_HEAT.get(sector, 1.0)
        new_valuation = new_revenue * exit_mult * heat

        # Predict if company needs to raise → dilution
        ownership = prev_snapshot.ownership_pct
        predicted_round = self._predict_next_round(
            prev_snapshot, company_data, year
        )
        if predicted_round:
            dilution = predicted_round["dilution"]
            ownership = ownership * (1 - dilution)
            stage = predicted_round.get("next_stage", stage)

        return CompanySnapshot(
            revenue=new_revenue,
            valuation=new_valuation,
            growth_rate=growth_rate,
            ownership_pct=ownership,
            dpi_contribution=0,  # computed at fund level
            gross_margin=gross_margin,
            sector=company_data.get("sector", "saas"),
            stage=stage,
            predicted_round=predicted_round,
        )

    def _predict_next_round(
        self,
        snapshot: CompanySnapshot,
        company_data: Dict,
        year: int,
    ) -> Optional[Dict[str, Any]]:
        """
        Predict whether a company needs to raise based on growth and stage.

        Higher growth → better terms → less dilution.
        Factors: growth rate, net retention, IP quality, investor quality, sector heat.
        """
        stage = snapshot.stage
        growth = snapshot.growth_rate

        # Simple heuristic: companies raise roughly every 2 years in early stage
        stage_idx = STAGE_ORDER.index(stage) if stage in STAGE_ORDER else 2
        raise_interval = 2 if stage_idx < 4 else 3

        if year % raise_interval != 0:
            return None

        # Determine next stage
        next_idx = min(stage_idx + 1, len(STAGE_ORDER) - 1)
        next_stage = STAGE_ORDER[next_idx]
        round_info = STAGE_TYPICAL_ROUND.get(next_stage, {"amount": 50_000_000, "dilution": 0.15})

        base_dilution = round_info["dilution"]

        # Adjust dilution based on company quality signals
        # Higher growth → premium valuation → less dilution
        if growth > 1.0:
            base_dilution *= 0.75  # 25% less dilution for hypergrowth
        elif growth > 0.5:
            base_dilution *= 0.85
        elif growth < 0.1:
            base_dilution *= 1.2  # worse terms for slow growers

        # IP quality adjustment
        ip_mult = self._assess_ip_quality(company_data)
        if ip_mult > 1.0:
            # Better IP → higher valuation → less dilution
            base_dilution *= (1.0 / ip_mult)

        # Sector heat
        sector = company_data.get("sector", "saas")
        heat = SECTOR_HEAT.get(sector, 1.0)
        if heat > 1.0:
            base_dilution *= (1.0 / heat)

        # Investor quality
        iq = company_data.get("investor_quality", "tier2")
        if iq == "tier1":
            base_dilution *= 0.9

        # Clamp dilution
        base_dilution = max(0.05, min(0.30, base_dilution))

        pre_money = round_info["amount"] / base_dilution - round_info["amount"]

        return {
            "next_stage": next_stage,
            "round_size": round_info["amount"],
            "dilution": base_dilution,
            "pre_money": pre_money,
            "year": year,
        }

    def _assess_ip_quality(self, company_data: Dict) -> float:
        """
        For deeptech companies, IP quality drives valuation premium.
        Returns multiplier 0.8-1.5x.
        """
        ip_signals = 0.0
        total_weight = 0.0

        patent_count = company_data.get("patent_count", 0) or 0
        if patent_count > 0:
            ip_signals += min(patent_count / 20.0, 1.0) * 0.3
            total_weight += 0.3

        time_to_replicate = company_data.get("time_to_replicate_years", 0) or 0
        if time_to_replicate > 0:
            ip_signals += min(time_to_replicate / 5.0, 1.0) * 0.3
            total_weight += 0.3

        has_regulatory_moat = company_data.get("regulatory_moat", False)
        if has_regulatory_moat:
            ip_signals += 0.2
            total_weight += 0.2

        switching_costs = company_data.get("switching_costs", "low")
        if switching_costs == "high":
            ip_signals += 0.2
            total_weight += 0.2
        elif switching_costs == "medium":
            ip_signals += 0.1
            total_weight += 0.2

        if total_weight == 0:
            return 1.0

        score = ip_signals / total_weight
        return 0.8 + score * 0.7  # range 0.8 to 1.5

    # ------------------------------------------------------------------
    # Fund-level aggregation
    # ------------------------------------------------------------------

    def _compute_fund_snapshot(
        self,
        company_snapshots: Dict[str, CompanySnapshot],
        fund_context: Dict,
        is_leaf: bool = False,
    ) -> FundSnapshot:
        """Aggregate company valuations * ownership -> fund NAV, DPI, TVPI.
        
        At leaf nodes (is_leaf=True), uses PWERM exit probabilities to compute
        a probability-weighted exit value across IPO/strategic/secondary/downside.
        """
        fund_size = fund_context.get("fund_size", 260_000_000)
        total_invested = fund_context.get("total_invested", 0)
        current_distributions = fund_context.get("distributions", 0)

        total_value = 0.0
        total_dpi_contribution = 0.0

        for cname, snap in company_snapshots.items():
            if is_leaf:
                # PWERM: probability-weight across exit scenarios
                weighted_proceeds = 0.0
                for exit_type, params in PWERM_EXIT_SCENARIOS.items():
                    exit_val = snap.valuation * params["multiple_premium"]
                    # Subtract preferences (estimate as total raised by stage)
                    pref_amount = STAGE_TYPICAL_ROUND.get(snap.stage, {}).get("amount", 0)
                    remaining = max(0, exit_val - pref_amount * params["pref_coverage"])
                    proceeds = remaining * snap.ownership_pct
                    weighted_proceeds += proceeds * params["probability"]
                snap.dpi_contribution = weighted_proceeds / fund_size if fund_size else 0
                total_value += weighted_proceeds
                total_dpi_contribution += snap.dpi_contribution
            else:
                company_nav = snap.valuation * snap.ownership_pct
                total_value += company_nav

        nav = total_value
        dpi = (current_distributions / fund_size + total_dpi_contribution) if fund_size else 0
        tvpi = (nav + current_distributions) / total_invested if total_invested else 0
        rvpi = (nav / total_invested) if total_invested else 0

        return FundSnapshot(
            nav=nav,
            dpi=dpi,
            tvpi=tvpi,
            rvpi=rvpi,
            total_invested=total_invested,
            total_value=total_value,
            total_distributed=current_distributions,
        )

    # ------------------------------------------------------------------
    # Tree analysis methods
    # ------------------------------------------------------------------

    def get_all_paths(self, tree: ScenarioTree) -> List[ScenarioPath]:
        """Return all root-to-leaf paths with cumulative probability."""
        return tree.paths

    def evaluate_expected_value(self, tree: ScenarioTree) -> FundSnapshot:
        """Probability-weighted average across all leaf nodes."""
        total_prob = sum(p.cumulative_probability for p in tree.paths)
        if total_prob == 0:
            return FundSnapshot(nav=0, dpi=0, tvpi=0, total_invested=0, total_value=0)

        w_nav = 0.0
        w_dpi = 0.0
        w_tvpi = 0.0
        total_invested = 0.0
        w_value = 0.0

        for path in tree.paths:
            f = path.final_fund
            if not f:
                continue
            w = path.cumulative_probability / total_prob
            w_nav += f.nav * w
            w_dpi += f.dpi * w
            w_tvpi += f.tvpi * w
            total_invested = f.total_invested  # same across paths
            w_value += f.total_value * w

        return FundSnapshot(
            nav=w_nav, dpi=w_dpi, tvpi=w_tvpi,
            total_invested=total_invested, total_value=w_value,
        )

    def sensitivity_by_company(self, tree: ScenarioTree) -> Dict[str, float]:
        """Which company's growth path has the biggest swing on fund DPI."""
        if not tree.paths:
            return {}

        dpi_values = [
            p.final_fund.tvpi for p in tree.paths if p.final_fund
        ]
        if not dpi_values:
            return {}

        best = max(dpi_values)
        worst = min(dpi_values)
        total_range = best - worst if best != worst else 1.0

        sensitivities: Dict[str, float] = {c: 0.0 for c in tree.companies}

        # For each company, find the max TVPI swing attributable to that company
        _scenario_suffixes = {"bull", "base", "bear", "neutral", "upside", "downside"}
        for cname in tree.companies:
            tvpi_by_path_label: Dict[str, List[float]] = {}
            for path in tree.paths:
                # Find which growth path label this path used for this company
                for lbl in path.labels:
                    # Extract company name from label by stripping scenario suffixes
                    parts = lbl.strip().split(" ")
                    while len(parts) > 1 and (parts[-1].lower() in _scenario_suffixes or parts[-1].endswith("%")):
                        parts.pop()
                    label_company = " ".join(parts)
                    if label_company.lower() == cname.lower():
                        tvpi_by_path_label.setdefault(lbl, []).append(
                            path.final_fund.tvpi if path.final_fund else 0
                        )

            if tvpi_by_path_label:
                avgs = [sum(vs) / len(vs) for vs in tvpi_by_path_label.values()]
                if avgs:
                    company_range = max(avgs) - min(avgs)
                    sensitivities[cname] = company_range / total_range

        return sensitivities

    # ------------------------------------------------------------------
    # Serialization for frontend
    # ------------------------------------------------------------------

    def tree_to_chart_data(self, tree: ScenarioTree) -> Dict[str, Any]:
        """Serialize tree to frontend chart-friendly format."""
        nodes = []
        edges = []
        seen_nodes = set()

        def _walk(node: ScenarioNode, parent_id: Optional[str] = None):
            if node.node_id in seen_nodes:
                return
            seen_nodes.add(node.node_id)

            fund = node.fund_metrics
            nodes.append({
                "id": node.node_id,
                "year": node.year,
                "label": node.label,
                "companies": {
                    cname: {
                        "revenue": snap.revenue,
                        "valuation": snap.valuation,
                        "growth_rate": snap.growth_rate,
                        "ownership_pct": snap.ownership_pct,
                    }
                    for cname, snap in node.companies.items()
                },
                "fund": {
                    "dpi": fund.dpi if fund else 0,
                    "tvpi": fund.tvpi if fund else 0,
                    "nav": fund.nav if fund else 0,
                } if fund else None,
                "probability": node.probability,
            })

            if parent_id:
                edges.append({
                    "source": parent_id,
                    "target": node.node_id,
                    "probability": node.probability,
                    "label": node.label,
                })

            for child in node.children:
                _walk(child, node.node_id)

        _walk(tree.root)

        paths_data = []
        for p in tree.paths:
            # Derive a composite scenario type for the whole path
            # If all paths are the same type, use it; otherwise "mixed"
            stypes = p.scenario_types or []
            if stypes and len(set(stypes)) == 1:
                composite_type = stypes[0]
            elif stypes:
                composite_type = "mixed"
            else:
                composite_type = "custom"

            paths_data.append({
                "path_id": p.path_id,
                "labels": p.labels,
                "scenario_types": stypes,
                "composite_scenario_type": composite_type,
                "cumulative_probability": p.cumulative_probability,
                "final_dpi": p.final_fund.dpi if p.final_fund else 0,
                "final_tvpi": p.final_fund.tvpi if p.final_fund else 0,
                "yearly_data": [
                    {
                        "year": n.year,
                        "total_revenue": sum(s.revenue for s in n.companies.values()),
                        "total_valuation": sum(s.valuation for s in n.companies.values()),
                        "fund_tvpi": n.fund_metrics.tvpi if n.fund_metrics else 0,
                        "fund_nav": n.fund_metrics.nav if n.fund_metrics else 0,
                    }
                    for n in p.nodes
                ],
            })

        expected = self.evaluate_expected_value(tree)
        sensitivity = self.sensitivity_by_company(tree)

        return {
            "type": "scenario_tree",
            "data": {
                "nodes": nodes,
                "edges": edges,
                "paths": paths_data,
                "expected_tvpi": expected.tvpi,
                "expected_nav": expected.nav,
                "sensitivity": sensitivity,
                "companies": tree.companies,
                "fund_size": tree.fund_size,
            },
        }

    def paths_to_line_chart_data(self, tree: ScenarioTree, metric: str = "revenue") -> Dict[str, Any]:
        """Serialize paths as multi-line chart data (one line per path)."""
        series = []
        for p in tree.paths:
            data_points = []
            for node in p.nodes:
                if metric == "revenue":
                    val = sum(s.revenue for s in node.companies.values())
                elif metric == "valuation":
                    val = sum(s.valuation for s in node.companies.values())
                elif metric == "tvpi":
                    val = node.fund_metrics.tvpi if node.fund_metrics else 0
                elif metric == "nav":
                    val = node.fund_metrics.nav if node.fund_metrics else 0
                else:
                    val = sum(s.revenue for s in node.companies.values())
                data_points.append({"year": node.year, "value": val})

            stypes = p.scenario_types or []
            composite = stypes[0] if stypes and len(set(stypes)) == 1 else ("mixed" if stypes else "custom")

            series.append({
                "name": " + ".join(p.labels),
                "probability": p.cumulative_probability,
                "scenario_type": composite,
                "scenario_types": stypes,
                "data": data_points,
            })

        return {
            "type": "scenario_paths",
            "data": {
                "metric": metric,
                "series": series,
                "companies": tree.companies,
            },
        }


    # ------------------------------------------------------------------
    # Bull / Bear / Base convenience
    # ------------------------------------------------------------------

    def build_bull_bear_base(
        self,
        company_name: str,
        base_company_data: Dict[str, Any],
        fund_context: Dict[str, Any],
        years: int = 5,
        bull_premium: float = 0.5,
        bear_discount: float = 0.5,
    ) -> ScenarioTree:
        """Build a 3-path tree (bull/base/bear) for a single company."""
        from app.services.revenue_projection_service import RevenueProjectionService

        base_growth = base_company_data.get("growth_rate", 0.5) or 0.5
        if isinstance(base_growth, (int, float)):
            if base_growth > 10: base_growth = base_growth / 100.0
            elif base_growth > 2: base_growth = base_growth - 1.0
        else:
            base_growth = 0.5

        stage = base_company_data.get("stage", "Series A")
        sector = base_company_data.get("sector", "saas")

        def _decay(ig, market):
            proj = RevenueProjectionService.project_revenue_with_decay(
                base_revenue=1_000_000, initial_growth=ig, years=years,
                quality_score=1.0, stage=stage, market_conditions=market,
                return_projections=True, sector=sector,
            )
            return [p.get("growth_rate", ig) for p in proj] if isinstance(proj, list) else [ig]*years

        bull_rates = _decay(base_growth * (1 + bull_premium), "bull")
        base_rates = _decay(base_growth, "neutral")
        bear_rates = _decay(base_growth * (1 - bear_discount), "bear")

        paths = {company_name: [
            GrowthPath(company_name, bull_rates, f"{company_name} Bull", probability=0.25, scenario_type="bull"),
            GrowthPath(company_name, base_rates, f"{company_name} Base", probability=0.50, scenario_type="base"),
            GrowthPath(company_name, bear_rates, f"{company_name} Bear", probability=0.25, scenario_type="bear"),
        ]}
        return self.build_tree(paths, {company_name: base_company_data}, fund_context, years)

    def build_portfolio_scenarios(
        self,
        companies_data: Dict[str, Dict[str, Any]],
        fund_context: Dict[str, Any],
        years: int = 5,
    ) -> ScenarioTree:
        """Build bull/bear/base for multiple companies. Cartesian product, pruned."""
        from app.services.revenue_projection_service import RevenueProjectionService

        def _decay(ig, stage, sector, market):
            proj = RevenueProjectionService.project_revenue_with_decay(
                base_revenue=1_000_000, initial_growth=ig, years=years,
                quality_score=1.0, stage=stage, market_conditions=market,
                return_projections=True, sector=sector,
            )
            return [p.get("growth_rate", ig) for p in proj] if isinstance(proj, list) else [ig]*years

        cp = {}
        for cn, cd in companies_data.items():
            bg = cd.get("growth_rate", 0.5) or 0.5
            if bg > 10: bg /= 100.0
            elif bg > 2: bg -= 1.0
            st, sec = cd.get("stage", "Series A"), cd.get("sector", "saas")
            cp[cn] = [
                GrowthPath(cn, _decay(bg*1.5, st, sec, "bull"), f"{cn} Bull", 0.25, scenario_type="bull"),
                GrowthPath(cn, _decay(bg, st, sec, "neutral"), f"{cn} Base", 0.50, scenario_type="base"),
                GrowthPath(cn, _decay(bg*0.5, st, sec, "bear"), f"{cn} Bear", 0.25, scenario_type="bear"),
            ]
        return self.build_tree(cp, companies_data, fund_context, years)

    # ------------------------------------------------------------------
    # Snapshot-in-time (mark-to-model at a point)
    # ------------------------------------------------------------------

    def snapshot_at_year(self, tree: ScenarioTree, year: int) -> Dict[str, Any]:
        """Probability-weighted portfolio state at a specific year."""
        w_nav, w_dpi, w_tvpi = 0.0, 0.0, 0.0
        co_rev: Dict[str, list] = {}
        co_val: Dict[str, list] = {}
        total_prob = 0.0
        for path in tree.paths:
            if year >= len(path.nodes): continue
            node = path.nodes[year]
            prob = path.cumulative_probability
            total_prob += prob
            fm = node.fund_metrics
            if fm:
                w_nav += prob * fm.nav
                w_dpi += prob * fm.dpi
                w_tvpi += prob * fm.tvpi
            for cn, snap in node.companies.items():
                co_rev.setdefault(cn, []).append((prob, snap.revenue))
                co_val.setdefault(cn, []).append((prob, snap.valuation))
        # Normalize by total probability (probabilities may not sum to 1.0 due to pruning)
        if total_prob > 0 and total_prob != 1.0:
            w_nav /= total_prob
            w_dpi /= total_prob
            w_tvpi /= total_prob
            co_rev = {cn: [(p / total_prob, r) for p, r in e] for cn, e in co_rev.items()}
            co_val = {cn: [(p / total_prob, v) for p, v in e] for cn, e in co_val.items()}
        return {
            "year": year, "expected_nav": w_nav, "expected_dpi": w_dpi, "expected_tvpi": w_tvpi,
            "company_expected_revenue": {cn: sum(p*r for p,r in e) for cn,e in co_rev.items()},
            "company_expected_valuation": {cn: sum(p*v for p,v in e) for cn,e in co_val.items()},
        }

    # ------------------------------------------------------------------
    # Macro / qualitative event overlay
    # ------------------------------------------------------------------

    def apply_macro_shock(
        self,
        tree: ScenarioTree,
        shock_type: str,
        magnitude: float = 0.5,
        affected_sectors: Optional[List[str]] = None,
        start_year: int = 1,
    ) -> ScenarioTree:
        """
        Apply a macro event to an existing tree. Returns a new tree (deep copy).

        shock_type: recession, rate_hike, regulation, market_boom, sector_crash,
                    tariff, pandemic, ai_winter, credit_crunch
        magnitude: 0-1 severity (0.5 = moderate, 1.0 = severe)
        start_year: year the shock hits (affects this year and all subsequent)
        """
        from copy import deepcopy
        SHOCKS = {
            "recession": {"val": -0.30, "gr": -0.25, "burn": 0.0},
            "rate_hike": {"val": -0.20, "gr": -0.10, "burn": 0.05},
            "regulation": {"val": -0.15, "gr": -0.20, "burn": 0.10},
            "market_boom": {"val": 0.25, "gr": 0.15, "burn": 0.0},
            "sector_crash": {"val": -0.40, "gr": -0.35, "burn": 0.0},
            "tariff": {"val": -0.10, "gr": -0.15, "burn": 0.05},
            "pandemic": {"val": -0.25, "gr": -0.20, "burn": -0.10},
            "ai_winter": {"val": -0.35, "gr": -0.30, "burn": 0.05},
            "credit_crunch": {"val": -0.25, "gr": -0.15, "burn": 0.10},
        }
        prof = SHOCKS.get(shock_type, SHOCKS["recession"])
        tree = deepcopy(tree)
        for path in tree.paths:
            for node in path.nodes:
                if node.year < start_year: continue
                for cn, s in node.companies.items():
                    if affected_sectors and s.sector not in affected_sectors: continue
                    s.valuation *= (1 + prof["val"] * magnitude)
                    s.revenue *= (1 + prof["gr"] * magnitude)
                    if s.burn_rate > 0:
                        s.burn_rate *= (1 + prof["burn"] * magnitude)
                        s.runway_months = s.cash_balance / s.burn_rate if s.burn_rate > 0 else 36
            # Recompute leaf fund metrics
            if path.nodes:
                leaf = path.nodes[-1]
                leaf_invested = leaf.fund_metrics.total_invested if leaf.fund_metrics else (tree.expected_value.total_invested if tree.expected_value else 0)
                leaf.fund_metrics = self._compute_fund_snapshot(leaf.companies, {"fund_size": tree.fund_size, "total_invested": leaf_invested})
                path.final_fund = leaf.fund_metrics
        tree.expected_value = self.evaluate_expected_value(tree)
        tree.sensitivity = self.sensitivity_by_company(tree)
        return tree

    def scenario_comparison_chart(self, tree: ScenarioTree) -> Dict[str, Any]:
        """Generate grouped bar charts comparing bull/base/bear across metrics.

        Returns two sub-charts: one for Revenue+NAV (dollar values) and one for
        TVPI (multiples), since mixing them on one axis makes TVPI invisible.
        """
        buckets: Dict[str, List[ScenarioPath]] = {"bull": [], "base": [], "bear": [], "other": []}
        for p in tree.paths:
            stypes = p.scenario_types or []
            if stypes and len(set(stypes)) == 1:
                key = stypes[0] if stypes[0] in buckets else "other"
            else:
                key = "other"
            buckets[key].append(p)

        def _avg(paths: List[ScenarioPath], fn) -> float:
            vals = [fn(p) for p in paths]
            return sum(vals) / len(vals) if vals else 0

        colors = {"bull": "#10b981", "base": "#4e79a7", "bear": "#ef4444"}

        # Chart 1: Revenue & NAV (dollar-scale)
        dollar_datasets = []
        # Chart 2: TVPI (multiple-scale)
        tvpi_datasets = []

        for stype in ["bull", "base", "bear"]:
            group = buckets[stype]
            if not group:
                continue
            avg_rev = _avg(group, lambda p: sum(s.revenue for s in p.nodes[-1].companies.values()) if p.nodes else 0)
            avg_nav = _avg(group, lambda p: p.final_fund.nav if p.final_fund else 0)
            avg_tvpi = _avg(group, lambda p: p.final_fund.tvpi if p.final_fund else 0)
            color = colors.get(stype, "#9ca3af")
            dollar_datasets.append({
                "label": stype.capitalize(),
                "data": [avg_rev, avg_nav],
                "backgroundColor": color,
                "scenario_type": stype,
            })
            tvpi_datasets.append({
                "label": stype.capitalize(),
                "data": [avg_tvpi],
                "backgroundColor": color,
                "scenario_type": stype,
            })

        return {
            "type": "bar_comparison",
            "data": {
                "labels": ["Revenue", "NAV"],
                "datasets": dollar_datasets,
            },
            "tvpi_chart": {
                "type": "bar_comparison",
                "data": {
                    "labels": ["TVPI"],
                    "datasets": tvpi_datasets,
                },
                "value_format": "multiple",
            },
        }

    def to_all_charts(self, tree: ScenarioTree) -> Dict[str, Any]:
        """Return all chart types in one bundle for frontend."""
        ev = tree.expected_value or FundSnapshot()
        return {
            "scenario_tree": self.tree_to_chart_data(tree),
            "scenario_paths": self.paths_to_line_chart_data(tree, metric="revenue"),
            "scenario_paths_tvpi": self.paths_to_line_chart_data(tree, metric="tvpi"),
            "scenario_comparison": self.scenario_comparison_chart(tree),
            "tornado": {
                "type": "tornado",
                "data": [
                    {
                        "name": cn,
                        "low": ev.tvpi * (1 - abs(imp)),
                        "high": ev.tvpi * (1 + abs(imp)),
                        "base": ev.tvpi,
                    }
                    for cn, imp in sorted((tree.sensitivity or {}).items(), key=lambda x: -abs(x[1]))
                ],
            },
            "summary": {
                "expected_nav": ev.nav, "expected_dpi": ev.dpi, "expected_tvpi": ev.tvpi,
                "num_paths": len(tree.paths), "companies": tree.companies, "fund_size": tree.fund_size,
            },
        }

    def tree_to_memo_sections(self, tree: ScenarioTree) -> List[Dict[str, Any]]:
        """Generate memo sections from a scenario tree."""
        expected = self.evaluate_expected_value(tree)
        sensitivity = self.sensitivity_by_company(tree)
        chart_data = self.tree_to_chart_data(tree)
        paths_chart = self.paths_to_line_chart_data(tree, metric="revenue")

        # Executive summary
        best_path = max(tree.paths, key=lambda p: p.final_fund.tvpi if p.final_fund else 0) if tree.paths else None
        worst_path = min(tree.paths, key=lambda p: p.final_fund.tvpi if p.final_fund else 0) if tree.paths else None

        summary_lines = [
            f"Analyzed {len(tree.paths)} scenario paths across {len(tree.companies)} companies.",
            f"Expected TVPI: {expected.tvpi:.2f}x | Expected NAV: ${expected.nav/1e6:.1f}M",
        ]
        if best_path and best_path.final_fund:
            summary_lines.append(
                f"Best case ({' + '.join(best_path.labels)}): {best_path.final_fund.tvpi:.2f}x TVPI "
                f"({best_path.cumulative_probability:.0%} probability)"
            )
        if worst_path and worst_path.final_fund:
            summary_lines.append(
                f"Worst case ({' + '.join(worst_path.labels)}): {worst_path.final_fund.tvpi:.2f}x TVPI "
                f"({worst_path.cumulative_probability:.0%} probability)"
            )

        # Top sensitivity driver
        if sensitivity:
            top_driver = max(sensitivity, key=sensitivity.get)
            summary_lines.append(
                f"Key driver: {top_driver} (accounts for {sensitivity[top_driver]:.0%} of outcome variance)"
            )

        # Round predictions table
        round_rows = []
        seen_rounds = set()
        for path in tree.paths[:4]:
            for node in path.nodes:
                for cname, snap in node.companies.items():
                    if snap.predicted_round:
                        r = snap.predicted_round
                        key = f"{cname}-{r.get('next_stage')}-{r.get('year')}"
                        if key in seen_rounds:
                            continue
                        seen_rounds.add(key)
                        round_rows.append([
                            cname,
                            r.get("next_stage", "?"),
                            f"Year {r.get('year', '?')}",
                            f"${r.get('pre_money', 0)/1e6:.0f}M",
                            f"{r.get('dilution', 0):.1%}",
                            f"{snap.ownership_pct:.1%}",
                        ])

        # Bull / Base / Bear comparison table
        # Classify by composite type: all-bull → bull, all-base → base, etc. Mixed → skip
        scenario_comparison_rows = []
        bull_paths, base_paths, bear_paths = [], [], []
        for p in tree.paths:
            stypes = set(p.scenario_types or [])
            if stypes == {"bull"}:
                bull_paths.append(p)
            elif stypes == {"base"}:
                base_paths.append(p)
            elif stypes == {"bear"}:
                bear_paths.append(p)

        def _avg_metric(paths: List[ScenarioPath], attr: str) -> float:
            vals = [getattr(p.final_fund, attr, 0) for p in paths if p.final_fund]
            return sum(vals) / len(vals) if vals else 0

        if bull_paths or base_paths or bear_paths:
            for label, group in [("Bull", bull_paths), ("Base", base_paths), ("Bear", bear_paths)]:
                if not group:
                    continue
                avg_tvpi = _avg_metric(group, "tvpi")
                avg_nav = _avg_metric(group, "nav")
                avg_prob = sum(p.cumulative_probability for p in group) / len(group) if group else 0
                final_rev = 0
                if group:
                    last_nodes = [p.nodes[-1] for p in group if p.nodes]
                    if last_nodes:
                        final_rev = sum(
                            sum(s.revenue for s in n.companies.values()) for n in last_nodes
                        ) / len(last_nodes)
                scenario_comparison_rows.append([
                    label,
                    f"{avg_prob:.0%}",
                    f"${final_rev/1e6:.1f}M",
                    f"${avg_nav/1e6:.1f}M",
                    f"{avg_tvpi:.2f}x",
                ])

        sections: List[Dict[str, Any]] = [
            {"type": "heading2", "content": f"Scenario Analysis: {', '.join(tree.companies)}"},
            {"type": "paragraph", "content": "\n".join(summary_lines)},
            {"type": "chart", "chart": chart_data},
            {"type": "chart", "chart": paths_chart},
        ]

        # Scenario comparison table + side-by-side bar chart (bull/base/bear)
        if scenario_comparison_rows:
            comparison_chart = self.scenario_comparison_chart(tree)
            sections.extend([
                {"type": "heading3", "content": "Scenario Comparison"},
                {"type": "chart", "chart": comparison_chart},
                {
                    "type": "table",
                    "table": {
                        "headers": ["Scenario", "Avg Probability", "Final Revenue", "Fund NAV", "Fund TVPI"],
                        "rows": scenario_comparison_rows,
                    },
                },
            ])

        # All paths detail table
        sections.append({
            "type": "table",
            "table": {
                "headers": ["Path", "Type", "Probability", "Fund TVPI", "Fund NAV"],
                "rows": [
                    [
                        " + ".join(p.labels),
                        " / ".join(p.scenario_types) if p.scenario_types else "custom",
                        f"{p.cumulative_probability:.0%}",
                        f"{p.final_fund.tvpi:.2f}x" if p.final_fund else "N/A",
                        f"${p.final_fund.nav/1e6:.1f}M" if p.final_fund else "N/A",
                    ]
                    for p in tree.paths
                ],
            },
        })

        if round_rows:
            sections.extend([
                {"type": "heading3", "content": "Round Predictions & Cost of Capital"},
                {
                    "type": "table",
                    "table": {
                        "headers": ["Company", "Predicted Round", "Year", "Pre-Money", "Dilution", "Post-Round Ownership"],
                        "rows": round_rows,
                    },
                },
            ])

        return sections
