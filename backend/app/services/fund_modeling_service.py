"""
Fund Modeling Service
Portfolio-level world models with NAV, IRR, DPI, TVPI calculations
Cross-portfolio relationships and optimization
Per-company return metrics and portfolio health analytics
"""

import logging
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import json
import math

from app.core.database import supabase_service
from app.services.world_model_builder import WorldModelBuilder
from app.services.scenario_analyzer import ScenarioAnalyzer
from app.services.company_health_scorer import (
    CompanyHealthScorer,
    CompanyAnalytics,
    CompanyReturnMetrics,
    _solve_irr,
)
from app.services.data_validator import ensure_numeric

logger = logging.getLogger(__name__)


class FundModelingService:
    """
    Models entire funds with portfolio-level world models
    Calculates NAV, IRR, DPI, TVPI, and portfolio optimization
    Per-company analytics and return metrics
    """

    def __init__(self):
        self.model_builder = WorldModelBuilder()
        self.scenario_analyzer = ScenarioAnalyzer()
        self.health_scorer = CompanyHealthScorer()

    def _get_portfolio_companies(self, fund_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Resilient portfolio company fetcher. Tries multiple strategies:
        1. portfolio_companies junction table (with company join)
        2. companies WHERE fund_id = fund_id
        3. companies WHERE funnel_status != 'unaffiliated'
        4. All companies ordered by ARR (limit 50)
        """
        client = supabase_service.client

        # Strategy 1: junction table
        if fund_id:
            try:
                r = client.table("portfolio_companies").select("*, companies(*)").eq("fund_id", fund_id).execute()
                if r.data:
                    # Flatten: extract nested company fields to top level
                    companies = []
                    for pc in r.data:
                        company = dict(pc.get("companies") or {})
                        # Merge portfolio_companies fields (investment_amount, ownership_pct, etc.)
                        for k, v in pc.items():
                            if k != "companies":
                                company.setdefault(k, v)
                        companies.append(company)
                    logger.info(f"[PORTFOLIO_FETCH] Strategy 1 (junction table): {len(companies)} companies")
                    return companies
            except Exception as e:
                logger.debug(f"[PORTFOLIO_FETCH] Strategy 1 failed: {e}")

        # Strategy 2: companies WHERE fund_id = fund_id
        if fund_id:
            try:
                r = client.table("companies").select("*").eq("fund_id", fund_id).execute()
                if r.data:
                    logger.info(f"[PORTFOLIO_FETCH] Strategy 2 (fund_id FK): {len(r.data)} companies")
                    return list(r.data)
            except Exception as e:
                logger.debug(f"[PORTFOLIO_FETCH] Strategy 2 failed: {e}")

        # Strategy 3: companies with a non-unaffiliated funnel_status
        try:
            r = client.table("companies").select("*").neq("funnel_status", "unaffiliated").limit(50).execute()
            if r.data:
                logger.info(f"[PORTFOLIO_FETCH] Strategy 3 (affiliated companies): {len(r.data)} companies")
                return list(r.data)
        except Exception as e:
            logger.debug(f"[PORTFOLIO_FETCH] Strategy 3 failed: {e}")

        # Strategy 4: all companies by ARR
        try:
            r = client.table("companies").select("*").order("current_arr_usd", desc=True).limit(50).execute()
            if r.data:
                logger.info(f"[PORTFOLIO_FETCH] Strategy 4 (top companies by ARR): {len(r.data)} companies")
                return list(r.data)
        except Exception as e:
            logger.debug(f"[PORTFOLIO_FETCH] Strategy 4 failed: {e}")

        logger.warning("[PORTFOLIO_FETCH] All strategies exhausted, returning empty list")
        return []

    def _auto_detect_fund_id(self) -> Optional[str]:
        """Auto-detect fund_id when none is provided.

        Uses deterministic ordering (by name ASC) so the same fund is
        always returned regardless of DB row ordering.
        """
        try:
            r = (
                supabase_service.client
                .table("funds")
                .select("id, name")
                .order("name", desc=False)
                .limit(1)
                .execute()
            )
            if r.data:
                fid = r.data[0]["id"]
                fname = r.data[0].get("name", "unknown")
                logger.info(f"[FUND_DETECT] Auto-detected fund_id: {fid} (name: {fname})")
                return fid
        except Exception as e:
            logger.debug(f"[FUND_DETECT] Failed: {e}")
        return None

    async def calculate_fund_metrics(
        self,
        fund_id: str
    ) -> Dict[str, Any]:
        """
        Calculate comprehensive fund metrics

        Args:
            fund_id: Fund ID

        Returns:
            Fund metrics including NAV, IRR, DPI, TVPI, RVPI
        """
        companies = self._get_portfolio_companies(fund_id)

        if not companies:
            return {
                "fund_id": fund_id,
                "warning": "No companies found in portfolio — metrics are zeroed",
                "metrics": {"total_committed": 0, "total_invested": 0, "total_nav": 0, "total_distributed": 0, "dpi": 0, "tvpi": 0, "rvpi": 0, "irr": 0, "deployment_rate": 0},
                "portfolio": {"company_count": 0, "active_count": 0, "exited_count": 0},
                "investments": []
            }

        # Calculate metrics
        total_invested = 0
        total_nav = 0
        total_distributed = 0
        total_committed = 0

        investments = []

        for company in companies:
            investment_amount = company.get("investment_amount", 0) or company.get("total_funding", 0) or 0
            ownership_pct = company.get("ownership_pct", 0) or 0
            current_valuation = company.get("current_valuation_usd", 0) or 0

            total_invested += investment_amount

            # NAV = ownership % * current valuation
            nav_contribution = (ownership_pct / 100) * current_valuation if ownership_pct else current_valuation
            total_nav += nav_contribution

            # Check if exited
            status = company.get("status", "active")
            if status == "exited":
                exit_value = company.get("exit_value_usd", 0) or 0
                distributed = (ownership_pct / 100) * exit_value if ownership_pct else exit_value
                total_distributed += distributed

            investments.append({
                "company_id": company.get("id"),
                "company_name": company.get("name"),
                "investment_amount": investment_amount,
                "ownership_pct": ownership_pct,
                "current_valuation": current_valuation,
                "nav_contribution": nav_contribution,
                "status": status
            })
        
        # Get fund size
        fund_result = supabase_service.client.table("funds").select("*").eq("id", fund_id).execute()
        fund = fund_result.data[0] if fund_result.data else {}
        fund_size = fund.get("fund_size_usd", 0) or 0
        total_committed = fund_size
        
        # Calculate metrics
        dpi = total_distributed / total_invested if total_invested > 0 else 0
        tvpi = (total_nav + total_distributed) / total_invested if total_invested > 0 else 0
        rvpi = total_nav / total_invested if total_invested > 0 else 0
        
        # Calculate IRR using actual cash flow dates when available
        irr = await self._calculate_irr(investments, total_distributed, companies)
        
        # Calculate deployment rate
        deployment_rate = total_invested / total_committed if total_committed > 0 else 0
        
        return {
            "fund_id": fund_id,
            "fund_name": fund.get("name"),
            "metrics": {
                "total_committed": total_committed,
                "total_invested": total_invested,
                "total_nav": total_nav,
                "total_distributed": total_distributed,
                "dpi": dpi,
                "tvpi": tvpi,
                "rvpi": rvpi,
                "irr": irr,
                "deployment_rate": deployment_rate
            },
            "portfolio": {
                "company_count": len(companies),
                "active_count": len([c for c in companies if c.get("status", "active") != "exited"]),
                "exited_count": len([c for c in companies if c.get("status") == "exited"])
            },
            "investments": investments
        }
    
    async def _calculate_irr(
        self,
        investments: List[Dict[str, Any]],
        total_distributed: float,
        companies: Optional[List[Dict[str, Any]]] = None,
    ) -> float:
        """
        Calculate fund-level IRR using Newton-Raphson on actual dated cash flows.
        Falls back to simple approximation when dates are unavailable.
        """
        if not investments:
            return 0.0

        total_invested = sum(i.get("investment_amount", 0) for i in investments)
        if total_invested == 0:
            return 0.0

        # Build cash flow vector from actual investment dates
        cash_flows: List[Tuple[float, datetime]] = []
        has_dates = False

        # Build a lookup of company data keyed by id
        company_map: Dict[str, Dict[str, Any]] = {}
        if companies:
            for c in companies:
                cid = c.get("id")
                if cid:
                    company_map[str(cid)] = c

        for inv in investments:
            amount = inv.get("investment_amount", 0) or 0
            if amount <= 0:
                continue

            # Try to get actual investment date
            cid = str(inv.get("company_id", ""))
            company = company_map.get(cid, {})
            inv_date = (
                company.get("investment_date")
                or company.get("created_at")
                or inv.get("investment_date")
            )

            if isinstance(inv_date, str):
                try:
                    inv_date = datetime.fromisoformat(inv_date.replace("Z", "+00:00")).replace(tzinfo=None)
                    has_dates = True
                except (ValueError, TypeError):
                    inv_date = None

            if isinstance(inv_date, datetime):
                cash_flows.append((-amount, inv_date))
                has_dates = True
            else:
                # Fallback: place 2 years ago
                cash_flows.append((-amount, datetime.now() - timedelta(days=730)))

            # Add distributions for exited companies
            status = inv.get("status") or company.get("status", "active")
            if status == "exited":
                exit_value = ensure_numeric(company.get("exit_value_usd"), 0)
                ownership = ensure_numeric(inv.get("ownership_pct"), 0)
                proceeds = (ownership / 100) * exit_value if ownership > 0 else exit_value
                exit_date_raw = company.get("exit_date") or company.get("updated_at")
                exit_date = None
                if isinstance(exit_date_raw, str):
                    try:
                        exit_date = datetime.fromisoformat(exit_date_raw.replace("Z", "+00:00")).replace(tzinfo=None)
                    except (ValueError, TypeError):
                        pass
                if not isinstance(exit_date, datetime):
                    exit_date = datetime.now() - timedelta(days=180)
                cash_flows.append((proceeds, exit_date))

        # Add current NAV as terminal value
        total_nav = sum(inv.get("nav_contribution", 0) for inv in investments)
        cash_flows.append((total_nav, datetime.now()))

        if has_dates and len(cash_flows) >= 2:
            irr = _solve_irr(cash_flows)
            return irr * 100  # Return as percentage

        # Fallback: simple approximation
        total_value = total_distributed + total_nav
        if total_invested <= 0 or total_value <= 0:
            return 0.0
        multiple = total_value / total_invested
        years = 3.0
        return ((multiple ** (1 / years)) - 1) * 100

    # ------------------------------------------------------------------
    # Per-company analytics & return metrics
    # ------------------------------------------------------------------
    async def analyze_portfolio_companies(
        self, fund_id: str
    ) -> Dict[str, Any]:
        """
        Run CompanyHealthScorer across all portfolio companies and compute
        per-company return metrics plus fund-level aggregates.

        Returns:
            {
                "company_analytics": {company_id: dict},
                "company_returns": {company_id: dict},
                "fund_summary": {...},
            }
        """
        # Resilient fetch — tries junction table, fund_id FK, affiliated, then top-by-ARR
        companies = self._get_portfolio_companies(fund_id)

        if not companies:
            return {"company_analytics": {}, "company_returns": {}, "fund_summary": {"warning": "No portfolio companies found"}}

        # Build investment dicts for the scorer
        fund_investments: Dict[str, Dict[str, Any]] = {}
        for c in companies:
            cid = str(c.get("id", ""))
            inv_amount = ensure_numeric(c.get("investment_amount"), 0)
            if inv_amount > 0:
                fund_investments[cid] = {
                    "amount": inv_amount,
                    "date": c.get("investment_date") or c.get("created_at"),
                    "ownership_pct": ensure_numeric(c.get("ownership_pct"), 0),
                }

        result = self.health_scorer.analyze_portfolio(companies, fund_investments)

        # Serialise dataclasses to dicts for JSON transport
        serialised_analytics = {}
        for cid, a in result["company_analytics"].items():
            serialised_analytics[cid] = {
                "company_id": a.company_id,
                "company_name": a.company_name,
                "stage": a.stage,
                "months_since_investment": a.months_since_investment,
                "current_arr": a.current_arr,
                "arr_source": a.arr_source,
                "growth_rate": a.growth_rate,
                "growth_trend": a.growth_trend,
                "projected_arr_12mo": a.projected_arr_12mo,
                "projected_arr_24mo": a.projected_arr_24mo,
                "projected_arr_36mo": a.projected_arr_36mo,
                "estimated_monthly_burn": a.estimated_monthly_burn,
                "estimated_runway_months": a.estimated_runway_months,
                "burn_as_pct_of_arr": a.burn_as_pct_of_arr,
                "months_since_last_round": a.months_since_last_round,
                "last_round_valuation": a.last_round_valuation,
                "last_round_amount": a.last_round_amount,
                "avg_step_up_multiple": a.avg_step_up_multiple,
                "predicted_next_round_months": a.predicted_next_round_months,
                "predicted_next_round_stage": a.predicted_next_round_stage,
                "predicted_next_raise_amount": a.predicted_next_raise_amount,
                "implied_current_valuation": a.implied_current_valuation,
                "valuation_direction": a.valuation_direction,
                "current_revenue_multiple": a.current_revenue_multiple,
                "fair_value_basis": a.fair_value_basis,
                "vs_benchmark": a.vs_benchmark,
                "signals": a.signals,
            }

        serialised_returns = {}
        for cid, r in result["company_returns"].items():
            serialised_returns[cid] = {
                "company_id": r.company_id,
                "company_name": r.company_name,
                "invested": r.invested,
                "ownership_pct": r.ownership_pct,
                "current_nav": r.current_nav,
                "moic": round(r.moic, 2),
                "irr": round(r.irr * 100, 2),  # as percentage
                "holding_period_years": round(r.holding_period_years, 1),
                "unrealized_gain": r.unrealized_gain,
                "cost_basis_per_pct": round(r.cost_basis_per_pct, 0),
            }

        return {
            "company_analytics": serialised_analytics,
            "company_returns": serialised_returns,
            "fund_summary": result["fund_summary"],
        }

    async def calculate_company_returns(
        self, fund_id: str
    ) -> Dict[str, Any]:
        """Convenience method: just the return metrics per company + fund totals."""
        result = await self.analyze_portfolio_companies(fund_id)
        return {
            "company_returns": result["company_returns"],
            "fund_summary": result["fund_summary"],
        }
    
    async def calculate_nav_time_series(
        self,
        fund_id: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Calculate NAV time series for a fund
        
        Args:
            fund_id: Fund ID
            start_date: Start date for time series
            end_date: End date for time series
            
        Returns:
            NAV time series data
        """
        # Check if time series data exists
        nav_ts_result = supabase_service.client.table("portfolio_nav_timeseries").select(
            "*"
        ).eq("fund_id", fund_id).order("date").execute()
        
        if nav_ts_result.data:
            # Return existing time series
            return {
                "fund_id": fund_id,
                "time_series": nav_ts_result.data
            }
        
        # Calculate current NAV
        current_metrics = await self.calculate_fund_metrics(fund_id)
        current_nav = current_metrics.get("metrics", {}).get("total_nav", 0)
        
        # For now, return single point
        # TODO: Calculate historical NAV from company valuation history
        return {
            "fund_id": fund_id,
            "time_series": [{
                "date": datetime.now().isoformat(),
                "nav": current_nav,
                "invested": current_metrics.get("metrics", {}).get("total_invested", 0)
            }]
        }
    
    async def optimize_portfolio(
        self,
        fund_id: str,
        constraints: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Optimize portfolio construction
        
        Args:
            fund_id: Fund ID
            constraints: Optimization constraints (max check size, sector limits, etc.)
            
        Returns:
            Portfolio optimization recommendations
        """
        # Get current portfolio
        metrics = await self.calculate_fund_metrics(fund_id)
        investments = metrics.get("investments", [])
        
        # Analyze current portfolio — single batch query (fixes N+1)
        company_ids = [inv.get("company_id") for inv in investments if inv.get("company_id")]
        company_map: Dict[str, Dict[str, Any]] = {}
        if company_ids:
            batch_result = supabase_service.client.table("companies").select(
                "id,sector,stage"
            ).in_("id", company_ids).execute()
            for c in (batch_result.data or []):
                company_map[str(c.get("id"))] = c

        sector_allocation = {}
        stage_allocation = {}
        check_size_distribution = []

        for inv in investments:
            company = company_map.get(str(inv.get("company_id", "")), {})

            sector = company.get("sector", "unknown")
            stage = company.get("stage", "unknown")
            check_size = inv.get("investment_amount", 0)

            sector_allocation[sector] = sector_allocation.get(sector, 0) + check_size
            stage_allocation[stage] = stage_allocation.get(stage, 0) + check_size
            check_size_distribution.append(check_size)
        
        # Calculate concentration metrics
        total_invested = sum(check_size_distribution)
        sector_concentration = {
            sector: amount / total_invested if total_invested > 0 else 0
            for sector, amount in sector_allocation.items()
        }
        
        # Identify concentration risks
        concentration_risks = []
        for sector, pct in sector_concentration.items():
            if pct > 0.3:  # >30% in one sector
                concentration_risks.append({
                    "type": "sector_concentration",
                    "sector": sector,
                    "percentage": pct,
                    "risk_level": "high" if pct > 0.5 else "medium"
                })
        
        # Portfolio optimization recommendations
        recommendations = []
        
        # Diversification recommendations
        if len(sector_allocation) < 3:
            recommendations.append({
                "type": "diversification",
                "priority": "high",
                "message": f"Portfolio concentrated in {len(sector_allocation)} sectors. Consider diversifying across more sectors.",
                "action": "Add investments in underrepresented sectors"
            })
        
        # Check size recommendations
        avg_check_size = sum(check_size_distribution) / len(check_size_distribution) if check_size_distribution else 0
        if avg_check_size > 5_000_000:
            recommendations.append({
                "type": "check_size",
                "priority": "medium",
                "message": f"Average check size is ${avg_check_size:,.0f}. Consider smaller checks for diversification.",
                "action": "Reduce average check size"
            })
        
        return {
            "fund_id": fund_id,
            "current_portfolio": {
                "sector_allocation": sector_allocation,
                "stage_allocation": stage_allocation,
                "check_size_distribution": {
                    "min": min(check_size_distribution) if check_size_distribution else 0,
                    "max": max(check_size_distribution) if check_size_distribution else 0,
                    "avg": avg_check_size,
                    "median": sorted(check_size_distribution)[len(check_size_distribution) // 2] if check_size_distribution else 0
                }
            },
            "concentration_analysis": {
                "sector_concentration": sector_concentration,
                "risks": concentration_risks
            },
            "recommendations": recommendations
        }
    
    async def analyze_pacing(
        self,
        fund_id: str,
        target_deployment: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Analyze fund deployment pacing
        
        Args:
            fund_id: Fund ID
            target_deployment: Target deployment percentage (e.g., 0.8 for 80%)
            
        Returns:
            Pacing analysis
        """
        # Get fund details
        fund_result = supabase_service.client.table("funds").select("*").eq("id", fund_id).execute()
        fund = fund_result.data[0] if fund_result.data else {}
        
        fund_size = fund.get("fund_size_usd", 0) or 0
        fund_start_date = fund.get("created_at") or fund.get("start_date")
        
        if fund_start_date:
            if isinstance(fund_start_date, str):
                fund_start_date = datetime.fromisoformat(fund_start_date.replace("Z", "+00:00"))
            days_since_start = (datetime.now() - fund_start_date.replace(tzinfo=None)).days
            years_since_start = days_since_start / 365.25
        else:
            years_since_start = 1.0  # Default
        
        # Get current metrics
        metrics = await self.calculate_fund_metrics(fund_id)
        total_invested = metrics.get("metrics", {}).get("total_invested", 0)
        deployment_rate = metrics.get("metrics", {}).get("deployment_rate", 0)
        
        # Calculate pacing
        target_deployment = target_deployment or 0.8  # 80% deployment target
        target_invested = fund_size * target_deployment
        
        # Ideal pacing (linear over fund life, typically 3-5 years)
        fund_life_years = 5.0  # Typical fund life
        ideal_years_elapsed = min(years_since_start, fund_life_years)
        ideal_deployment_pct = ideal_years_elapsed / fund_life_years
        ideal_invested = fund_size * ideal_deployment_pct * target_deployment
        
        # Pacing analysis
        pacing_status = "on_track"
        if total_invested < ideal_invested * 0.8:
            pacing_status = "behind"
        elif total_invested > ideal_invested * 1.2:
            pacing_status = "ahead"
        
        # Remaining capital
        remaining_capital = fund_size - total_invested
        remaining_to_deploy = target_invested - total_invested
        
        # Projected completion
        if deployment_rate > 0:
            months_to_complete = (remaining_to_deploy / (total_invested / max(years_since_start * 12, 1))) if total_invested > 0 else 0
        else:
            months_to_complete = 0
        
        return {
            "fund_id": fund_id,
            "pacing": {
                "current_deployment": deployment_rate,
                "target_deployment": target_deployment,
                "current_invested": total_invested,
                "target_invested": target_invested,
                "ideal_invested": ideal_invested,
                "status": pacing_status
            },
            "capital": {
                "fund_size": fund_size,
                "total_invested": total_invested,
                "remaining_capital": remaining_capital,
                "remaining_to_deploy": remaining_to_deploy
            },
            "projection": {
                "months_to_complete": months_to_complete,
                "years_since_start": years_since_start,
                "fund_life_years": fund_life_years
            }
        }
    
    async def create_portfolio_world_model(
        self,
        fund_id: str,
        model_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create a portfolio-level world model
        
        This models the entire fund as a world with:
        - Company entities
        - Market entities
        - Relationships between companies
        - Portfolio-level factors (diversification, concentration, etc.)
        """
        # Get fund and companies
        fund_result = supabase_service.client.table("funds").select("*").eq("id", fund_id).execute()
        fund = fund_result.data[0] if fund_result.data else {}
        
        companies_result = supabase_service.client.table("companies").select(
            "*"
        ).eq("fund_id", fund_id).execute()

        companies = companies_result.data or []

        # Create portfolio world model
        model_name = model_name or f"Portfolio World Model: {fund.get('name', 'Fund')}"
        
        model = await self.model_builder.create_model(
            name=model_name,
            model_type="portfolio",
            fund_id=fund_id,
            created_by=None
        )
        model_id = model["id"]
        
        # Add fund entity
        fund_entity = await self.model_builder.add_entity(
            model_id=model_id,
            entity_type="fund",
            entity_name=fund.get("name", "Fund"),
            entity_id=fund_id,
            properties={
                "fund_size": fund.get("fund_size_usd"),
                "stage_focus": fund.get("stage_focus"),
                "sector_focus": fund.get("sector_focus")
            }
        )
        
        # Add company entities and build their world models
        company_entities = []
        for pc in companies:
            company = pc  # companies is already a flat list of company rows
            if not company:
                continue
            
            # Create company world model
            company_model = await self.model_builder.build_company_world_model(
                company_data=company,
                model_name=f"World Model: {company.get('name')}",
                fund_id=fund_id
            )
            
            # Add company entity to portfolio model
            company_entity = await self.model_builder.add_entity(
                model_id=model_id,
                entity_type="company",
                entity_name=company.get("name", "Unknown"),
                entity_id=company.get("id"),
                properties={
                    "investment_amount": pc.get("investment_amount"),
                    "ownership_pct": pc.get("ownership_pct"),
                    "status": pc.get("status")
                }
            )
            company_entities.append(company_entity)
        
        # Add portfolio-level factors
        metrics = await self.calculate_fund_metrics(fund_id)
        
        # Diversification factor
        diversification = await self.model_builder.add_factor(
            model_id=model_id,
            entity_id=fund_entity["id"],
            factor_name="diversification_score",
            factor_type=self.model_builder.FactorType.QUALITATIVE,
            factor_category=self.model_builder.FactorCategory.OPERATIONAL,
            value_type="score",
            current_value=len(set(c.get("sector") for c in companies if c.get("sector"))),
            source="calculated",
            confidence_score=0.9
        )
        
        # NAV factor
        nav_factor = await self.model_builder.add_factor(
            model_id=model_id,
            entity_id=fund_entity["id"],
            factor_name="total_nav",
            factor_type=self.model_builder.FactorType.QUANTITATIVE,
            factor_category=self.model_builder.FactorCategory.FINANCIAL,
            value_type="amount",
            current_value=metrics.get("metrics", {}).get("total_nav", 0),
            source="calculated",
            confidence_score=0.9
        )
        
        return {
            "model_id": model_id,
            "model": model,
            "fund_entity": fund_entity,
            "company_entities": company_entities,
            "portfolio_factors": [diversification, nav_factor]
        }

    # ------------------------------------------------------------------
    # Phase 3: Fund Return Scenario Engine
    # ------------------------------------------------------------------
    async def model_fund_scenarios(
        self,
        fund_id: str,
        company_scenarios: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """Model fund-level returns under different per-company outcome combinations.

        Args:
            fund_id: Fund ID
            company_scenarios: Optional map of company_id → scenario name
                (e.g. {"abc": "base", "def": "bridge"}).
                If None, generates standard portfolio scenarios automatically.

        Returns:
            Multiple portfolio-level scenario results with fund MOIC/IRR/DPI,
            return attribution, and marginal impact per company.
        """
        from app.services.valuation_engine_service import valuation_engine_service

        # Fetch all companies in one query
        companies_result = supabase_service.client.table("companies").select(
            "*"
        ).eq("fund_id", fund_id).execute()
        companies = companies_result.data or []

        fund_result = supabase_service.client.table("funds").select("*").eq("id", fund_id).execute()
        fund = fund_result.data[0] if fund_result.data else {}
        fund_size = ensure_numeric(fund.get("fund_size_usd"), 0)

        if not companies:
            return {"error": "No companies in portfolio", "scenarios": []}

        # Run health scorer on all companies
        portfolio_analysis = self.health_scorer.analyze_portfolio(
            companies,
            {
                str(c.get("id", "")): {
                    "amount": ensure_numeric(c.get("investment_amount"), 0),
                    "date": c.get("investment_date") or c.get("created_at"),
                    "ownership_pct": ensure_numeric(c.get("ownership_pct"), 0),
                }
                for c in companies
                if ensure_numeric(c.get("investment_amount"), 0) > 0
            },
        )

        analytics_map = portfolio_analysis["company_analytics"]
        returns_map = portfolio_analysis["company_returns"]

        # Generate scenario cap tables per company
        company_scenario_data: Dict[str, Dict[str, Any]] = {}
        for c in companies:
            cid = str(c.get("id", ""))
            inv_amount = ensure_numeric(c.get("investment_amount"), 0)
            ownership = ensure_numeric(c.get("ownership_pct"), 0)
            if inv_amount <= 0:
                continue

            a = analytics_map.get(cid)
            analytics_dict = None
            if a:
                analytics_dict = {
                    "growth_rate": a.growth_rate,
                    "estimated_runway_months": a.estimated_runway_months,
                    "valuation_direction": a.valuation_direction,
                }

            try:
                sc_result = valuation_engine_service.generate_scenario_cap_tables(
                    company_data=c,
                    analytics=analytics_dict,
                    our_investment={
                        "amount": inv_amount,
                        "ownership_pct": ownership,
                        "round_name": c.get("stage", "Series A"),
                    },
                )
                company_scenario_data[cid] = sc_result
            except Exception as e:
                logger.warning(f"Scenario gen failed for {c.get('name')}: {e}")

        # --- Build portfolio scenario combinations ---
        def _pick_scenario(cid: str, scenario_name: str) -> Dict[str, Any]:
            """Pick a specific scenario for a company, or fall back to base."""
            scd = company_scenario_data.get(cid, {})
            for sc in scd.get("scenarios", []):
                if sc.get("name") == scenario_name:
                    return sc
            # Fallback to first scenario
            scenarios = scd.get("scenarios", [])
            return scenarios[0] if scenarios else {}

        def _compute_fund_metrics_for_combo(
            combo: Dict[str, str],
            exit_multiplier: float = 5.0,
        ) -> Dict[str, Any]:
            """Given a company→scenario map, compute fund-level metrics."""
            total_invested = 0.0
            total_proceeds = 0.0
            company_outcomes = []

            for c in companies:
                cid = str(c.get("id", ""))
                inv_amount = ensure_numeric(c.get("investment_amount"), 0)
                if inv_amount <= 0:
                    continue

                total_invested += inv_amount
                scenario_name = combo.get(cid, "base")
                sc = _pick_scenario(cid, scenario_name)

                # Use the waterfall at a representative exit value
                # Pick the exit value closest to exit_multiplier × current_valuation
                valuation = ensure_numeric(
                    c.get("valuation") or c.get("current_valuation_usd"), 0
                )
                target_exit = valuation * exit_multiplier if valuation > 0 else 500_000_000

                wf_exits = sc.get("waterfall_at_exits", [])
                best_wf = {}
                best_diff = float("inf")
                for wf in wf_exits:
                    diff = abs(wf.get("exit_value", 0) - target_exit)
                    if diff < best_diff:
                        best_diff = diff
                        best_wf = wf

                our_proceeds = best_wf.get("our_proceeds", 0)
                our_moic = best_wf.get("our_moic", 0)
                total_proceeds += our_proceeds

                company_outcomes.append({
                    "company_id": cid,
                    "company_name": c.get("name", ""),
                    "scenario": scenario_name,
                    # Full investment context
                    "invested": inv_amount,
                    "entry_round": c.get("stage", ""),
                    "ownership_pct": ensure_numeric(c.get("ownership_pct"), 0),
                    "ownership_post_scenario_pct": best_wf.get("our_ownership_post_scenario_pct", 0),
                    "current_valuation": valuation,
                    # Exit context
                    "exit_value": best_wf.get("exit_value", 0),
                    "total_pref_stack": best_wf.get("total_pref_stack", 0),
                    "prefs_senior_to_us": best_wf.get("prefs_senior_to_us", 0),
                    "pref_pct_of_exit": best_wf.get("pref_pct_of_exit", 0),
                    # Proceeds with context
                    "our_proceeds": our_proceeds,
                    "our_proceeds_source": best_wf.get("our_proceeds_source", "unknown"),
                    "our_profit": our_proceeds - inv_amount,
                    "our_moic": our_moic,
                })

            fund_moic = total_proceeds / total_invested if total_invested > 0 else 0

            # Return attribution
            attribution = []
            for co in company_outcomes:
                pct_of_returns = (
                    co["our_proceeds"] / total_proceeds * 100
                    if total_proceeds > 0
                    else 0
                )
                # Marginal impact: fund MOIC with vs without this company
                proceeds_without = total_proceeds - co["our_proceeds"]
                invested_without = total_invested - co["invested"]
                moic_without = (
                    proceeds_without / invested_without
                    if invested_without > 0
                    else 0
                )
                attribution.append({
                    "company_id": co["company_id"],
                    "company_name": co["company_name"],
                    "scenario": co["scenario"],
                    "proceeds": round(co["our_proceeds"], 0),
                    "pct_of_total_returns": round(pct_of_returns, 1),
                    "fund_moic_with": round(fund_moic, 2),
                    "fund_moic_without": round(moic_without, 2),
                    "marginal_moic_impact": round(fund_moic - moic_without, 2),
                })

            fund_dpi = total_proceeds / fund_size if fund_size > 0 else 0

            return {
                "total_invested": round(total_invested, 0),
                "total_proceeds": round(total_proceeds, 0),
                "fund_moic": round(fund_moic, 2),
                "fund_dpi": round(fund_dpi, 2),
                "company_outcomes": company_outcomes,
                "return_attribution": sorted(
                    attribution, key=lambda x: x["proceeds"], reverse=True
                ),
            }

        # Standard portfolio scenarios
        all_company_ids = [
            str(c.get("id", ""))
            for c in companies
            if ensure_numeric(c.get("investment_amount"), 0) > 0
        ]

        portfolio_scenarios = []

        # 1. Everything on plan
        combo_base = {cid: "base" for cid in all_company_ids}
        result_base = _compute_fund_metrics_for_combo(combo_base)
        portfolio_scenarios.append({
            "scenario_name": "everything_on_plan",
            "label": "All companies hit targets",
            **result_base,
        })

        # 2. Power law: top company outperforms, rest base/decay
        if len(all_company_ids) >= 2:
            # Sort by current NAV descending
            sorted_ids = sorted(
                all_company_ids,
                key=lambda cid: (returns_map.get(cid) and returns_map[cid].current_nav) or 0,
                reverse=True,
            )
            combo_power = {}
            for i, cid in enumerate(sorted_ids):
                if i == 0:
                    combo_power[cid] = "outperform"
                elif i <= len(sorted_ids) // 2:
                    combo_power[cid] = "base"
                else:
                    combo_power[cid] = "growth_decay"
            result_power = _compute_fund_metrics_for_combo(combo_power)
            portfolio_scenarios.append({
                "scenario_name": "power_law",
                "label": "Top company 10x, middle base, bottom decay",
                **result_power,
            })

        # 3. Current trajectory (use analytics signals to pick most likely)
        combo_current = {}
        for cid in all_company_ids:
            a = analytics_map.get(cid)
            if a and a.valuation_direction == "down_round_risk":
                combo_current[cid] = "growth_decay"
            elif a and a.valuation_direction == "up_round_likely":
                combo_current[cid] = "outperform"
            elif a and a.estimated_runway_months < 9:
                combo_current[cid] = "bridge"
            else:
                combo_current[cid] = "base"
        result_current = _compute_fund_metrics_for_combo(combo_current)
        portfolio_scenarios.append({
            "scenario_name": "current_trajectory",
            "label": "Each company on its most likely path",
            **result_current,
        })

        # 4. Stress test: bottom half bridges/writes off
        if len(all_company_ids) >= 2:
            sorted_ids = sorted(
                all_company_ids,
                key=lambda cid: (returns_map.get(cid) and returns_map[cid].moic) or 0,
            )
            combo_stress = {}
            for i, cid in enumerate(sorted_ids):
                if i < len(sorted_ids) // 2:
                    combo_stress[cid] = "bridge"
                else:
                    combo_stress[cid] = "base"
            result_stress = _compute_fund_metrics_for_combo(combo_stress)
            portfolio_scenarios.append({
                "scenario_name": "stress_test",
                "label": "Bottom half bridge/writedown, top half on plan",
                **result_stress,
            })

        # 5. User-specified (if provided)
        if company_scenarios:
            result_custom = _compute_fund_metrics_for_combo(company_scenarios)
            portfolio_scenarios.append({
                "scenario_name": "custom",
                "label": "User-specified scenario combination",
                **result_custom,
            })

        return {
            "fund_id": fund_id,
            "fund_size": fund_size,
            "portfolio_scenarios": portfolio_scenarios,
            "company_scenario_data": {
                cid: {
                    "company_name": sd.get("company_name"),
                    "scenarios": [
                        {
                            "name": s.get("name"),
                            "label": s.get("label"),
                            "our_ownership_post": s.get("our_ownership_post"),
                            "breakeven_exit_value": s.get("breakeven_exit_value"),
                            "three_x_exit_value": s.get("three_x_exit_value"),
                            "total_preference_stack": s.get("total_preference_stack"),
                        }
                        for s in sd.get("scenarios", [])
                    ],
                }
                for cid, sd in company_scenario_data.items()
            },
        }

    # ------------------------------------------------------------------
    # Phase 4b: Scenario Tree → Fund Impact Evaluation
    # ------------------------------------------------------------------
    def evaluate_scenario_tree_on_fund(
        self,
        tree_paths: List[Dict[str, Any]],
        portfolio_companies: List[Dict[str, Any]],
        fund_size: float = 260_000_000,
        total_invested: float = 0,
    ) -> List[Dict[str, Any]]:
        """Evaluate a ScenarioTree's paths in the context of the full fund.

        For companies NOT in the tree, uses base-case projections.
        Returns per-path fund metrics with attribution.

        Args:
            tree_paths: Serialized paths from ScenarioTreeService.tree_to_chart_data()
                        Each path: {path_id, labels, cumulative_probability,
                                    final_dpi, final_tvpi, yearly_data}
            portfolio_companies: Full list of portfolio companies (from DB or shared_data)
            fund_size: Total fund size
            total_invested: Total capital deployed so far
        """
        # Collect tree company names from path labels
        # Labels look like "Palo Alto Networks Bull", "CompanyName 30%"
        # Strip trailing scenario keywords (Bull/Base/Bear/percentages) to get the company name
        _SCENARIO_SUFFIXES = {"bull", "base", "bear", "neutral", "upside", "downside"}
        tree_company_names = set()
        for path in tree_paths:
            for label in (path.get("labels") or []):
                parts = label.strip().split(" ")
                # Remove trailing word if it's a scenario keyword or ends with %
                while len(parts) > 1 and (parts[-1].lower() in _SCENARIO_SUFFIXES or parts[-1].endswith("%")):
                    parts.pop()
                tree_company_names.add(" ".join(parts).lower())

        # Separate NAV and invested for tree vs non-tree companies
        base_nav = 0.0
        base_invested = 0.0
        tree_invested = 0.0
        for comp in portfolio_companies:
            cname = (comp.get("company_name") or comp.get("name") or "").lower()
            invested = ensure_numeric(comp.get("investment_amount"), 0)
            if cname in tree_company_names:
                tree_invested += invested
                continue
            valuation = ensure_numeric(comp.get("valuation") or comp.get("current_valuation_usd"), 0)
            ownership = ensure_numeric(comp.get("ownership_pct"), 0)
            # ownership_pct is stored as percentage (e.g. 10 = 10%), convert to decimal
            base_nav += valuation * (ownership / 100)
            base_invested += invested

        # Use explicit total_invested if provided, otherwise sum from portfolio
        combined_invested = total_invested if total_invested > 0 else (base_invested + tree_invested)

        results = []
        for path in tree_paths:
            yearly = path.get("yearly_data", [])
            final = yearly[-1] if yearly else {}
            tree_nav = final.get("fund_nav", 0)

            total_nav = base_nav + tree_nav
            fund_tvpi = total_nav / combined_invested if combined_invested > 0 else 0
            fund_dpi = 0  # No distributions modeled yet in tree

            results.append({
                "path_id": path.get("path_id"),
                "path_label": " + ".join(path.get("labels", [])),
                "probability": path.get("cumulative_probability", 0),
                "tree_nav": tree_nav,
                "rest_of_portfolio_nav": base_nav,
                "fund_total_nav": total_nav,
                "fund_tvpi": round(fund_tvpi, 3),
                "fund_dpi": round(fund_dpi, 3),
                "combined_invested": round(combined_invested, 0),
            })

        return results

    # ------------------------------------------------------------------
    # Phase 5: Follow-On, Exit Planning & Reserve Analysis
    # ------------------------------------------------------------------
    async def analyze_follow_on(
        self,
        fund_id: str,
        company_id: str,
    ) -> Dict[str, Any]:
        """Compute follow-on analysis for a specific company.

        Returns ownership scenarios (pro-rata vs not), proceeds impact at
        various exits, opportunity cost, and fund return impact.
        """
        from app.services.pre_post_cap_table import PrePostCapTable
        from app.services.valuation_engine_service import valuation_engine_service

        # Fetch company
        company_result = supabase_service.client.table("companies").select(
            "*"
        ).eq("id", company_id).execute()
        company = company_result.data[0] if company_result.data else {}
        if not company:
            return {"error": "Company not found"}

        inv_amount = ensure_numeric(company.get("investment_amount"), 0)
        ownership = ensure_numeric(company.get("ownership_pct"), 0)
        if inv_amount <= 0:
            return {"error": "No investment found for this company"}

        # Analytics
        analytics = self.health_scorer.analyze_company(
            company,
            {"amount": inv_amount, "date": company.get("investment_date"), "ownership_pct": ownership},
        )

        # Pro-rata calculation
        cap_service = PrePostCapTable()
        pro_rata_result = cap_service.calculate_pro_rata_investment(
            current_ownership=ensure_numeric(ownership, 0) / 100,
            new_money_raised=analytics.predicted_next_raise_amount,
            pre_money_valuation=analytics.implied_current_valuation
                if analytics.implied_current_valuation > 0
                else ensure_numeric(company.get("valuation"), 100_000_000),
        )

        # Scenario cap tables (from Phase 2)
        scenario_data = valuation_engine_service.generate_scenario_cap_tables(
            company_data=company,
            analytics={
                "growth_rate": analytics.growth_rate,
                "estimated_runway_months": analytics.estimated_runway_months,
                "valuation_direction": analytics.valuation_direction,
            },
            our_investment={
                "amount": inv_amount,
                "ownership_pct": ownership,
                "round_name": company.get("stage", "Series A"),
            },
        )

        # Ownership with vs without follow-on
        ownership_with = pro_rata_result.get("ownership_with_pro_rata", ownership)
        ownership_without = pro_rata_result.get("ownership_without_pro_rata", ownership * 0.8)
        pro_rata_cost = pro_rata_result.get("pro_rata_investment_needed", 0)

        # Fund-level impact of follow-on
        fund_result = supabase_service.client.table("funds").select("*").eq("id", fund_id).execute()
        fund = fund_result.data[0] if fund_result.data else {}
        fund_size = ensure_numeric(fund.get("fund_size_usd"), 0)

        # Calculate proceeds at key exit multiples with/without follow-on
        exit_analysis = []
        for exit_mult_label, exit_mult in [("3x", 3), ("5x", 5), ("8x", 8), ("10x", 10)]:
            valuation = analytics.implied_current_valuation if analytics.implied_current_valuation > 0 else 100_000_000
            exit_value = valuation * exit_mult

            proceeds_with = (ownership_with / 100) * exit_value
            proceeds_without = (ownership_without / 100) * exit_value
            delta = proceeds_with - proceeds_without

            moic_with = proceeds_with / (inv_amount + pro_rata_cost) if (inv_amount + pro_rata_cost) > 0 else 0
            moic_without = proceeds_without / inv_amount if inv_amount > 0 else 0

            fund_moic_delta_with = proceeds_with / fund_size if fund_size > 0 else 0
            fund_moic_delta_without = proceeds_without / fund_size if fund_size > 0 else 0

            exit_analysis.append({
                "exit_multiple": exit_mult_label,
                "exit_value": round(exit_value, 0),
                "proceeds_with_follow_on": round(proceeds_with, 0),
                "proceeds_without": round(proceeds_without, 0),
                "incremental_proceeds": round(delta, 0),
                "moic_with": round(moic_with, 2),
                "moic_without": round(moic_without, 2),
                "fund_dpi_impact_with": round(fund_moic_delta_with, 4),
                "fund_dpi_impact_without": round(fund_moic_delta_without, 4),
            })

        return {
            "company_name": company.get("name"),
            "company_id": company_id,
            "current_ownership_pct": ownership,
            "pro_rata_cost": round(pro_rata_cost, 0),
            "ownership_with_follow_on": round(ownership_with, 2),
            "ownership_without": round(ownership_without, 2),
            "dilution_if_no_follow_on": round(ownership - ownership_without, 2),
            "predicted_next_round": {
                "stage": analytics.predicted_next_round_stage,
                "months_away": round(analytics.predicted_next_round_months, 0),
                "estimated_amount": analytics.predicted_next_raise_amount,
            },
            "company_trajectory": {
                "growth_rate": analytics.growth_rate,
                "growth_trend": analytics.growth_trend,
                "runway_months": round(analytics.estimated_runway_months, 0),
                "valuation_direction": analytics.valuation_direction,
                "signals": analytics.signals,
            },
            "exit_analysis": exit_analysis,
            "scenario_cap_tables": scenario_data.get("scenarios", []),
        }

    async def forecast_reserves(
        self,
        fund_id: str,
    ) -> Dict[str, Any]:
        """Forecast capital needs across the portfolio.

        For each company, predict when the next round happens and how much
        pro-rata would cost. Build a quarter-by-quarter timeline of obligations
        vs available reserves.
        """
        companies_result = supabase_service.client.table("companies").select(
            "*"
        ).eq("fund_id", fund_id).execute()
        companies = companies_result.data or []

        fund_result = supabase_service.client.table("funds").select("*").eq("id", fund_id).execute()
        fund = fund_result.data[0] if fund_result.data else {}
        fund_size = ensure_numeric(fund.get("fund_size_usd"), 0)
        total_invested = sum(ensure_numeric(c.get("investment_amount"), 0) for c in companies)
        available_reserves = fund_size - total_invested

        obligations = []
        for c in companies:
            inv_amount = ensure_numeric(c.get("investment_amount"), 0)
            ownership = ensure_numeric(c.get("ownership_pct"), 0)
            if inv_amount <= 0 or c.get("status") == "exited":
                continue

            analytics = self.health_scorer.analyze_company(
                c,
                {"amount": inv_amount, "date": c.get("investment_date"), "ownership_pct": ownership},
            )

            # Estimate pro-rata obligation
            next_raise = analytics.predicted_next_raise_amount
            pro_rata = (ownership / 100) * next_raise if next_raise > 0 else 0

            if pro_rata > 0:
                months_until = max(analytics.predicted_next_round_months, 1)
                # Map to quarter
                quarter_offset = int(months_until / 3)
                now = datetime.now()
                target_quarter = now + timedelta(days=quarter_offset * 91)
                quarter_label = f"Q{(target_quarter.month - 1) // 3 + 1} {target_quarter.year}"

                obligations.append({
                    "company_name": c.get("name", ""),
                    "company_id": str(c.get("id", "")),
                    "next_round_stage": analytics.predicted_next_round_stage,
                    "months_until_round": round(months_until, 0),
                    "quarter": quarter_label,
                    "pro_rata_amount": round(pro_rata, 0),
                    "next_raise_total": round(next_raise, 0),
                    "current_ownership_pct": ownership,
                    "runway_months": round(analytics.estimated_runway_months, 0),
                })

        # Sort by timing
        obligations.sort(key=lambda x: x["months_until_round"])

        # Aggregate by quarter
        by_quarter: Dict[str, float] = {}
        for ob in obligations:
            q = ob["quarter"]
            by_quarter[q] = by_quarter.get(q, 0) + ob["pro_rata_amount"]

        total_obligations = sum(ob["pro_rata_amount"] for ob in obligations)
        shortfall = total_obligations - available_reserves

        return {
            "fund_id": fund_id,
            "available_reserves": round(available_reserves, 0),
            "total_obligations": round(total_obligations, 0),
            "shortfall": round(max(shortfall, 0), 0),
            "has_shortfall": shortfall > 0,
            "obligations_by_company": obligations,
            "obligations_by_quarter": [
                {"quarter": q, "amount": round(amt, 0)}
                for q, amt in sorted(by_quarter.items())
            ],
        }

    async def plan_exits(
        self,
        fund_id: str,
    ) -> Dict[str, Any]:
        """Exit planning for each portfolio company.

        For each company: compute exit route economics (secondary, M&A, IPO),
        projected timing, and fund return impact.
        """
        from app.services.valuation_engine_service import valuation_engine_service

        companies_result = supabase_service.client.table("companies").select(
            "*"
        ).eq("fund_id", fund_id).execute()
        companies = companies_result.data or []

        fund_result = supabase_service.client.table("funds").select("*").eq("id", fund_id).execute()
        fund = fund_result.data[0] if fund_result.data else {}
        fund_size = ensure_numeric(fund.get("fund_size_usd"), 0)

        exit_plans = []
        for c in companies:
            inv_amount = ensure_numeric(c.get("investment_amount"), 0)
            ownership = ensure_numeric(c.get("ownership_pct"), 0)
            if inv_amount <= 0 or c.get("status") == "exited":
                continue

            analytics = self.health_scorer.analyze_company(
                c,
                {"amount": inv_amount, "date": c.get("investment_date"), "ownership_pct": ownership},
            )

            valuation = analytics.implied_current_valuation if analytics.implied_current_valuation > 0 else ensure_numeric(c.get("valuation"), 0)

            # Secondary: 10-30% discount to last round
            secondary_discount = 0.20
            secondary_value = valuation * (1 - secondary_discount)
            secondary_proceeds = (ownership / 100) * secondary_value
            secondary_moic = secondary_proceeds / inv_amount if inv_amount > 0 else 0

            # M&A at various ARR multiples
            ma_scenarios = []
            for mult_label, mult in [("5x ARR", 5), ("8x ARR", 8), ("10x ARR", 10), ("15x ARR", 15)]:
                exit_val = analytics.current_arr * mult
                proceeds = (ownership / 100) * exit_val
                moic = proceeds / inv_amount if inv_amount > 0 else 0
                fund_impact = proceeds / fund_size if fund_size > 0 else 0
                ma_scenarios.append({
                    "label": mult_label,
                    "exit_value": round(exit_val, 0),
                    "our_proceeds": round(proceeds, 0),
                    "moic": round(moic, 2),
                    "fund_dpi_impact": round(fund_impact, 4),
                })

            # IPO timing: when does ARR hit $100M?
            ipo_arr_threshold = 100_000_000
            months_to_ipo = None
            if analytics.current_arr > 0 and analytics.growth_rate > 0:
                # Project using decay model
                from app.services.company_health_scorer import _project_arr
                for m in range(6, 120, 6):
                    projected = _project_arr(analytics.current_arr, analytics.growth_rate, m)
                    if projected >= ipo_arr_threshold:
                        months_to_ipo = m
                        break

            # Hold vs sell analysis
            projected_arr_24 = analytics.projected_arr_24mo
            projected_val_24 = projected_arr_24 * analytics.stage_benchmark_multiple if projected_arr_24 > 0 else 0
            projected_proceeds_24 = (ownership / 100) * projected_val_24
            sell_now_moic = secondary_moic
            hold_2yr_moic = projected_proceeds_24 / inv_amount if inv_amount > 0 else 0

            exit_plans.append({
                "company_name": c.get("name", ""),
                "company_id": str(c.get("id", "")),
                "stage": analytics.stage,
                "current_arr": round(analytics.current_arr, 0),
                "growth_rate": analytics.growth_rate,
                "valuation_direction": analytics.valuation_direction,
                "signals": analytics.signals,
                "secondary": {
                    "discount": secondary_discount,
                    "value": round(secondary_value, 0),
                    "our_proceeds": round(secondary_proceeds, 0),
                    "moic": round(secondary_moic, 2),
                    "fund_dpi_impact": round(secondary_proceeds / fund_size, 4) if fund_size > 0 else 0,
                    "timeline": "2-4 weeks",
                },
                "ma_scenarios": ma_scenarios,
                "ipo_timing": {
                    "months_to_ipo_arr": months_to_ipo,
                    "arr_threshold": ipo_arr_threshold,
                    "current_arr": round(analytics.current_arr, 0),
                    "lockup_months": 6,
                },
                "hold_vs_sell": {
                    "sell_now_moic": round(sell_now_moic, 2),
                    "hold_2yr_moic": round(hold_2yr_moic, 2),
                    "hold_2yr_projected_arr": round(projected_arr_24, 0),
                    "hold_2yr_projected_val": round(projected_val_24, 0),
                    "recommendation_signal": "hold" if hold_2yr_moic > sell_now_moic * 1.5 else "consider_secondary" if sell_now_moic > 2.0 else "hold",
                },
            })

        # Sort by MOIC potential (hold scenario)
        exit_plans.sort(
            key=lambda x: x["hold_vs_sell"].get("hold_2yr_moic", 0), reverse=True
        )

        return {
            "fund_id": fund_id,
            "fund_size": fund_size,
            "exit_plans": exit_plans,
        }
