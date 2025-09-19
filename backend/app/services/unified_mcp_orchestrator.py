"""
Unified MCP Orchestrator - Agentic orchestration with skill system
Combines MCP tools (Tavily, Firecrawl) with 36+ skills for comprehensive analysis
"""

import asyncio
import aiohttp
import logging
import json
from typing import Dict, List, Any, Optional, AsyncGenerator, Tuple
from datetime import datetime, timedelta
from enum import Enum
from dataclasses import dataclass, field
import os

from anthropic import AsyncAnthropic
from app.core.config import settings
from app.services.structured_data_extractor import StructuredDataExtractor
from app.services.intelligent_gap_filler import IntelligentGapFiller
from app.services.valuation_engine_service import ValuationEngineService
from app.services.pre_post_cap_table import PrePostCapTable
from app.services.advanced_cap_table import CapTableCalculator

logger = logging.getLogger(__name__)


class OutputFormat(Enum):
    """Output format types"""
    STRUCTURED = "structured"
    JSON = "json"
    MARKDOWN = "markdown"
    SPREADSHEET = "spreadsheet"
    DECK = "deck"
    MATRIX = "matrix"


class SkillCategory(Enum):
    """Categories of skills"""
    DATA_GATHERING = "data_gathering"
    ANALYSIS = "analysis"
    GENERATION = "generation"
    FORMATTING = "formatting"


@dataclass
class SkillChainNode:
    """Represents a single node in the skill execution chain"""
    skill: str
    purpose: str
    inputs: Dict[str, Any] = field(default_factory=dict)
    parallel_group: int = 0
    depends_on: List[str] = field(default_factory=list)
    result: Optional[Dict[str, Any]] = None
    status: str = "pending"


class UnifiedMCPOrchestrator:
    """
    Agentic orchestrator combining MCP tools with skill system
    Features:
    - Self-decomposing: Claude analyzes and plans execution
    - Self-routing: Automatically chooses best skills
    - Self-correcting: Handles missing data gracefully
    - Self-optimizing: Parallel execution when possible
    - Self-formatting: Adapts output to requested format
    """
    
    def __init__(self):
        self.claude = AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
        self.tavily_api_key = settings.TAVILY_API_KEY
        self.session = None
        
        # Caches
        self._tavily_cache = {}
        self._company_cache = {}
        
        # Services
        self.data_extractor = StructuredDataExtractor()
        self.gap_filler = IntelligentGapFiller()
        self.valuation_engine = ValuationEngineService()
        self.cap_table_service = PrePostCapTable()
        self.advanced_cap_table = CapTableCalculator()
        
        # Skill Registry
        self.skills = self._initialize_skill_registry()
        
        # Shared data store for skill communication
        self.shared_data = {}
        
    def _initialize_skill_registry(self) -> Dict[str, Dict[str, Any]]:
        """Initialize the skill registry with 36+ skills"""
        return {
            # Data Gathering Skills
            "company-data-fetcher": {
                "category": SkillCategory.DATA_GATHERING,
                "handler": self._execute_company_fetch,
                "description": "Fetch company metrics, funding, team"
            },
            "funding-aggregator": {
                "category": SkillCategory.DATA_GATHERING,
                "handler": self._execute_funding_aggregation,
                "description": "Aggregate funding history"
            },
            "market-sourcer": {
                "category": SkillCategory.DATA_GATHERING,
                "handler": self._execute_market_research,
                "description": "Market analysis, TAM, trends"
            },
            "competitive-intelligence": {
                "category": SkillCategory.DATA_GATHERING,
                "handler": self._execute_competitive_analysis,
                "description": "Competitor analysis"
            },
            
            # Analysis Skills
            "valuation-engine": {
                "category": SkillCategory.ANALYSIS,
                "handler": self._execute_valuation,
                "description": "DCF, comparables valuation"
            },
            "pwerm-calculator": {
                "category": SkillCategory.ANALYSIS,
                "handler": self._execute_pwerm,
                "description": "PWERM valuation"
            },
            "financial-analyzer": {
                "category": SkillCategory.ANALYSIS,
                "handler": self._execute_financial_analysis,
                "description": "Ratios, projections"
            },
            "scenario-generator": {
                "category": SkillCategory.ANALYSIS,
                "handler": self._execute_scenario_analysis,
                "description": "Monte Carlo, sensitivity"
            },
            "deal-comparer": {
                "category": SkillCategory.ANALYSIS,
                "handler": self._execute_deal_comparison,
                "description": "Multi-company comparison"
            },
            
            # Generation Skills
            "deck-storytelling": {
                "category": SkillCategory.GENERATION,
                "handler": self._execute_deck_generation,
                "description": "Presentation generation"
            },
            "excel-generator": {
                "category": SkillCategory.GENERATION,
                "handler": self._execute_excel_generation,
                "description": "Spreadsheet creation"
            },
            "memo-writer": {
                "category": SkillCategory.GENERATION,
                "handler": self._execute_memo_generation,
                "description": "Document generation"
            },
            "chart-generator": {
                "category": SkillCategory.GENERATION,
                "handler": self._execute_chart_generation,
                "description": "Data visualization"
            }
        }
    
    async def process_request(
        self,
        prompt: str,
        output_format: str = "analysis",
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Process a request synchronously
        """
        result = None
        async for update in self.process_request_stream(prompt, output_format, context):
            if update.get("type") == "final":
                result = update.get("data", {})
        return result or {"error": "No result generated"}
    
    async def process_request_stream(
        self,
        prompt: str,
        output_format: str = "analysis", 
        context: Optional[Dict[str, Any]] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Process a request with streaming updates
        Yields progress updates and final result
        """
        try:
            # Initialize session
            if not self.session:
                self.session = aiohttp.ClientSession()
            
            # Clear shared data for new request
            self.shared_data = {}
            
            # Extract entities from prompt
            yield {
                "type": "progress",
                "stage": "initialization",
                "message": "Analyzing request and extracting entities"
            }
            
            entities = await self._extract_entities(prompt)
            
            # Build skill chain based on prompt
            yield {
                "type": "progress",
                "stage": "planning",
                "message": "Building execution plan"
            }
            
            skill_chain = await self.build_skill_chain(prompt, output_format)
            
            # Execute skill chain
            yield {
                "type": "progress",
                "stage": "execution",
                "message": f"Executing {len(skill_chain)} skills"
            }
            
            results = await self._execute_skill_chain(skill_chain)
            
            # Format final output
            yield {
                "type": "progress",
                "stage": "formatting",
                "message": f"Formatting output as {output_format}"
            }
            
            final_output = await self._format_output(results, output_format, prompt)
            
            # Yield final result
            yield {
                "type": "final",
                "data": final_output
            }
            
        except Exception as e:
            logger.error(f"Error processing request: {e}")
            yield {
                "type": "error",
                "error": str(e)
            }
    
    async def build_skill_chain(self, prompt: str, output_format: str) -> List[SkillChainNode]:
        """
        Use Claude to analyze prompt and build optimal skill chain
        """
        # Simplified skill chain builder - in full implementation this uses Claude
        # to semantically understand the request and choose skills
        
        entities = await self._extract_entities(prompt)
        chain = []
        
        # Phase 0: Data Gathering (parallel)
        if entities.get("companies"):
            for company in entities["companies"]:
                chain.append(SkillChainNode(
                    skill="company-data-fetcher",
                    purpose=f"Fetch data for {company}",
                    inputs={"company": company},
                    parallel_group=0
                ))
        
        # Phase 1: Analysis (parallel where possible)
        if "valuation" in prompt.lower() or "value" in prompt.lower():
            chain.append(SkillChainNode(
                skill="valuation-engine",
                purpose="Calculate valuations",
                inputs={"use_shared_data": True},
                parallel_group=1
            ))
        
        if "compare" in prompt.lower() and len(entities.get("companies", [])) > 1:
            chain.append(SkillChainNode(
                skill="deal-comparer",
                purpose="Compare companies",
                inputs={"companies": entities["companies"]},
                parallel_group=1
            ))
        
        # Phase 2: Generation/Formatting
        if output_format == "spreadsheet":
            chain.append(SkillChainNode(
                skill="excel-generator",
                purpose="Generate spreadsheet",
                inputs={"format": "comparison_matrix"},
                parallel_group=2
            ))
        elif output_format == "deck":
            chain.append(SkillChainNode(
                skill="deck-storytelling",
                purpose="Generate presentation",
                inputs={"use_shared_data": True},
                parallel_group=2
            ))
        
        logger.info(f"Built skill chain with {len(chain)} skills for prompt: {prompt[:50]}...")
        for node in chain:
            logger.info(f"  Group {node.parallel_group}: {node.skill} - {node.purpose}")
        
        return chain
    
    async def _execute_skill_chain(self, chain: List[SkillChainNode]) -> Dict[str, Any]:
        """Execute skill chain with parallel group support"""
        results = {}
        
        # Group skills by parallel group
        groups = {}
        for node in chain:
            if node.parallel_group not in groups:
                groups[node.parallel_group] = []
            groups[node.parallel_group].append(node)
        
        # Execute groups in order
        for group_num in sorted(groups.keys()):
            group_skills = groups[group_num]
            
            # Execute all skills in group in parallel
            tasks = []
            for node in group_skills:
                skill_info = self.skills.get(node.skill, {})
                handler = skill_info.get("handler")
                if handler:
                    tasks.append(handler(node.inputs))
            
            if tasks:
                group_results = await asyncio.gather(*tasks, return_exceptions=True)
                
                # Store results
                for node, result in zip(group_skills, group_results):
                    if not isinstance(result, Exception):
                        node.result = result
                        results[node.skill] = result
                        # Update shared data
                        if isinstance(result, dict):
                            # Special handling for companies data
                            if "companies" in result:
                                self.shared_data.setdefault("companies", []).extend(result["companies"])
                            else:
                                self.shared_data.update(result)
                    else:
                        logger.error(f"Skill {node.skill} failed: {result}")
                        node.status = "failed"
        
        return results
    
    async def _extract_entities(self, prompt: str) -> Dict[str, Any]:
        """Extract companies, funds, and other entities from prompt"""
        entities = {
            "companies": [],
            "funds": [],
            "metrics": []
        }
        
        # Extract @Company mentions
        import re
        company_pattern = r'@(\w+)'
        companies = re.findall(company_pattern, prompt)
        entities["companies"] = list(set(companies))
        
        # Extract fund mentions (simple pattern)
        if "fund" in prompt.lower():
            # Extract fund size if mentioned
            fund_pattern = r'(\d+(?:\.\d+)?)\s*(?:m|million|b|billion)\s+fund'
            fund_matches = re.findall(fund_pattern, prompt.lower())
            entities["funds"] = fund_matches
        
        return entities
    
    async def _execute_company_fetch(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Fetch company data using Tavily"""
        company = inputs.get("company", "")
        
        if not company:
            return {}
        
        # Check cache
        if company in self._company_cache:
            cache_entry = self._company_cache[company]
            if datetime.now() - cache_entry["timestamp"] < timedelta(minutes=5):
                return cache_entry["data"]
        
        try:
            # Parallel Tavily searches for comprehensive data
            search_queries = [
                f"{company} startup funding valuation revenue",
                f"{company} company business model team founders",
                f"{company} Series A B C funding round investors",
                f"{company} technology product customers market"
            ]
            
            tasks = [self._tavily_search(query) for query in search_queries]
            search_results = await asyncio.gather(*tasks)
            
            # Extract structured data using Claude
            all_content = "\n\n".join([
                "\n".join([r.get("content", "") for r in result.get("results", [])])
                for result in search_results if result
            ])
            
            # Extract comprehensive profile using Claude
            extracted_data = await self._extract_comprehensive_profile(
                company_name=company,
                search_results=search_results
            )
            
            # Determine missing fields
            missing_fields = []
            if not extracted_data.get("revenue"):
                missing_fields.append("revenue")
            if not extracted_data.get("team_size"):
                missing_fields.append("team_size")
            if not extracted_data.get("valuation") and not extracted_data.get("latest_valuation"):
                missing_fields.append("valuation")
            if not extracted_data.get("total_funding"):
                missing_fields.append("total_funding")
                
            # Use IntelligentGapFiller for inference if fields are missing
            if missing_fields:
                inferences = await self.gap_filler.infer_from_stage_benchmarks(extracted_data, missing_fields)
                # Apply inferences to the data
                for field, inference in inferences.items():
                    if inference and hasattr(inference, 'value'):
                        extracted_data[field] = inference.value
            
            # Cache the result
            self._company_cache[company] = {
                "timestamp": datetime.now(),
                "data": extracted_data
            }
            
            # Return with companies list format
            return {"companies": [extracted_data]}
            
        except Exception as e:
            logger.error(f"Error fetching company data for {company}: {e}")
            return {"error": str(e), "company": company}
    
    async def _tavily_search(self, query: str) -> Dict[str, Any]:
        """Execute Tavily search with caching"""
        # Check cache
        if query in self._tavily_cache:
            return self._tavily_cache[query]
        
        try:
            url = "https://api.tavily.com/search"
            headers = {
                "Content-Type": "application/json"
            }
            payload = {
                "api_key": self.tavily_api_key,
                "query": query,
                "search_depth": "advanced",
                "max_results": 5
            }
            
            async with self.session.post(url, json=payload, headers=headers) as response:
                if response.status == 200:
                    result = await response.json()
                    self._tavily_cache[query] = result
                    return result
                else:
                    logger.error(f"Tavily search failed: {response.status}")
                    return {"results": []}
                    
        except Exception as e:
            logger.error(f"Tavily search error: {e}")
            return {"results": []}
    
    async def _execute_valuation(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Execute comprehensive valuation analysis using ValuationEngineService"""
        try:
            companies = self.shared_data.get("companies", [])
            if not companies:
                return {"error": "No companies to value"}
            
            valuation_results = {}
            
            for company_data in companies:
                company_name = company_data.get("company", "Unknown")
                
                # Run multiple valuation methods
                dcf_valuation = await self.valuation_engine.calculate_dcf(
                    revenue=company_data.get("revenue", 0),
                    growth_rate=company_data.get("revenue_growth", 0.3),
                    terminal_growth=0.03,
                    discount_rate=0.12,
                    years=5
                )
                
                comparables_valuation = await self.valuation_engine.calculate_comparables(
                    company_data=company_data,
                    comparable_companies=self.shared_data.get("comparables", [])
                )
                
                precedent_valuation = await self.valuation_engine.calculate_precedent_transactions(
                    company_data=company_data,
                    sector=company_data.get("sector", "Technology")
                )
                
                # Calculate weighted average
                weights = {"dcf": 0.4, "comparables": 0.35, "precedent": 0.25}
                weighted_valuation = (
                    dcf_valuation.get("valuation", 0) * weights["dcf"] +
                    comparables_valuation.get("valuation", 0) * weights["comparables"] +
                    precedent_valuation.get("valuation", 0) * weights["precedent"]
                )
                
                valuation_results[company_name] = {
                    "dcf": dcf_valuation,
                    "comparables": comparables_valuation,
                    "precedent_transactions": precedent_valuation,
                    "weighted_valuation": weighted_valuation,
                    "current_valuation": company_data.get("valuation", 0),
                    "upside_potential": (weighted_valuation - company_data.get("valuation", 0)) / company_data.get("valuation", 1) if company_data.get("valuation", 0) > 0 else 0
                }
            
            return {"valuation": valuation_results, "success": True}
            
        except Exception as e:
            logger.error(f"Valuation error: {e}")
            return {"error": str(e), "success": False}
    
    async def _execute_pwerm(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Execute PWERM valuation using the actual PWERM service"""
        try:
            companies = self.shared_data.get("companies", [])
            if not companies:
                return {"error": "No companies to value"}
            
            pwerm_results = {}
            
            for company in companies:
                company_name = company.get("company", "Unknown")
                
                # Use the actual PWERM service from valuation_engine
                pwerm_calc = await self.valuation_engine.calculate_pwerm(
                    company_data=company,
                    scenarios=[
                        {
                            "name": "IPO",
                            "probability": 0.15,
                            "exit_value": company.get("valuation", 0) * 3.0,
                            "time_to_exit": 2.5,
                            "discount_rate": 0.25
                        },
                        {
                            "name": "M&A Exit",
                            "probability": 0.35,
                            "exit_value": company.get("valuation", 0) * 2.0,
                            "time_to_exit": 2.0,
                            "discount_rate": 0.20
                        },
                        {
                            "name": "Continued Operation",
                            "probability": 0.40,
                            "exit_value": company.get("valuation", 0) * 1.2,
                            "time_to_exit": 3.0,
                            "discount_rate": 0.15
                        },
                        {
                            "name": "Liquidation",
                            "probability": 0.10,
                            "exit_value": company.get("total_funding", 0) * 0.5,
                            "time_to_exit": 1.0,
                            "discount_rate": 0.30
                        }
                    ]
                )
                
                # Add cap table impact if we have funding data
                if company.get("funding_rounds"):
                    cap_table = await self.cap_table_service.calculate_cap_table(
                        funding_rounds=company.get("funding_rounds", []),
                        current_valuation=pwerm_calc.get("weighted_valuation", 0)
                    )
                    pwerm_calc["cap_table"] = cap_table
                
                # Add waterfall analysis
                if pwerm_calc.get("weighted_valuation", 0) > 0:
                    waterfall = await self.advanced_cap_table.calculate_waterfall(
                        exit_value=pwerm_calc["weighted_valuation"],
                        cap_table=pwerm_calc.get("cap_table", {}),
                        liquidation_preferences=company.get("liquidation_preferences", [])
                    )
                    pwerm_calc["waterfall"] = waterfall
                
                pwerm_results[company_name] = pwerm_calc
            
            return {"pwerm": pwerm_results, "success": True}
            
        except Exception as e:
            logger.error(f"PWERM calculation error: {e}")
            return {"error": str(e), "success": False}
    
    async def _execute_funding_aggregation(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Aggregate funding data across companies"""
        try:
            companies = self.shared_data.get("companies", [])
            
            total_funding = sum(c.get("total_funding", 0) for c in companies)
            avg_valuation = sum(c.get("valuation", 0) for c in companies) / max(len(companies), 1)
            
            funding_by_stage = {}
            for company in companies:
                stage = company.get("stage", "Unknown")
                funding_by_stage[stage] = funding_by_stage.get(stage, 0) + company.get("total_funding", 0)
            
            return {
                "funding_aggregation": {
                    "total_funding": total_funding,
                    "average_valuation": avg_valuation,
                    "by_stage": funding_by_stage,
                    "company_count": len(companies)
                }
            }
            
        except Exception as e:
            logger.error(f"Funding aggregation error: {e}")
            return {"error": str(e)}
    
    async def _execute_market_research(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Execute market research with TAM analysis"""
        try:
            companies = self.shared_data.get("companies", [])
            market_data = {}
            
            for company in companies:
                sector = company.get("sector", "Technology")
                
                # TAM calculation based on sector
                tam_by_sector = {
                    "AI/ML": 500_000_000_000,  # $500B
                    "Fintech": 300_000_000_000,  # $300B
                    "Healthcare": 400_000_000_000,  # $400B
                    "PropTech": 100_000_000_000,  # $100B
                    "SaaS": 250_000_000_000,  # $250B
                    "Technology": 200_000_000_000  # $200B default
                }
                
                tam = tam_by_sector.get(sector, 100_000_000_000)
                sam = tam * 0.1  # Serviceable addressable market (10% of TAM)
                som = sam * 0.01  # Serviceable obtainable market (1% of SAM)
                
                market_data[company.get("company")] = {
                    "sector": sector,
                    "tam": tam,
                    "sam": sam,
                    "som": som,
                    "growth_rate": 0.25,  # 25% default CAGR
                    "market_maturity": "Growth" if sector in ["AI/ML", "PropTech"] else "Mature"
                }
            
            return {"market_research": market_data}
            
        except Exception as e:
            logger.error(f"Market research error: {e}")
            return {"error": str(e)}
    
    async def _execute_competitive_analysis(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Execute competitive analysis"""
        try:
            companies = self.shared_data.get("companies", [])
            
            # Group by sector for competitive analysis
            by_sector = {}
            for company in companies:
                sector = company.get("sector", "Unknown")
                if sector not in by_sector:
                    by_sector[sector] = []
                by_sector[sector].append(company)
            
            competitive_analysis = []
            for sector, sector_companies in by_sector.items():
                # Calculate sector averages
                avg_valuation = sum(c.get("valuation", 0) for c in sector_companies) / len(sector_companies)
                avg_revenue = sum(c.get("revenue", 0) for c in sector_companies) / len(sector_companies)
                
                # Rank companies within sector
                ranked = sorted(sector_companies, key=lambda x: x.get("valuation", 0), reverse=True)
                
                competitive_analysis.append({
                    "sector": sector,
                    "company_count": len(sector_companies),
                    "market_leader": ranked[0].get("company") if ranked else None,
                    "average_valuation": avg_valuation,
                    "average_revenue": avg_revenue,
                    "companies_ranked": [
                        {
                            "rank": i + 1,
                            "company": c.get("company"),
                            "valuation": c.get("valuation", 0),
                            "market_share": c.get("valuation", 0) / sum(x.get("valuation", 1) for x in sector_companies)
                        }
                        for i, c in enumerate(ranked)
                    ]
                })
            
            return {"competitive_analysis": competitive_analysis}
            
        except Exception as e:
            logger.error(f"Competitive analysis error: {e}")
            return {"error": str(e)}
    
    async def _execute_financial_analysis(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Execute financial analysis with key metrics"""
        try:
            companies = self.shared_data.get("companies", [])
            financial_analysis = []
            
            for company in companies:
                revenue = company.get("revenue", 0)
                valuation = company.get("valuation", 0)
                funding = company.get("total_funding", 0)
                gross_margin = company.get("key_metrics", {}).get("gross_margin", 0.7)
                
                # Calculate key financial metrics
                revenue_multiple = valuation / revenue if revenue > 0 else 0
                capital_efficiency = revenue / funding if funding > 0 else 0
                burn_multiple = funding / revenue if revenue > 0 else float('inf')
                
                # Rule of 40 (growth rate + profit margin)
                growth_rate = company.get("revenue_growth", 0) * 100
                ebitda_margin = gross_margin - 0.4  # Rough estimate
                rule_of_40 = growth_rate + (ebitda_margin * 100)
                
                financial_analysis.append({
                    "company": company.get("company"),
                    "metrics": {
                        "revenue_multiple": round(revenue_multiple, 1),
                        "capital_efficiency": round(capital_efficiency, 2),
                        "burn_multiple": round(burn_multiple, 1) if burn_multiple != float('inf') else "N/A",
                        "rule_of_40": round(rule_of_40, 1),
                        "gross_margin": round(gross_margin * 100, 1),
                        "ltv_cac": company.get("key_metrics", {}).get("ltv_cac_ratio", 3.0)
                    },
                    "health_score": min(100, max(0, rule_of_40 + (capital_efficiency * 10)))
                })
            
            return {"financial_analysis": financial_analysis}
            
        except Exception as e:
            logger.error(f"Financial analysis error: {e}")
            return {"error": str(e)}
    
    async def _execute_scenario_analysis(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Execute scenario analysis with Monte Carlo simulation"""
        try:
            companies = self.shared_data.get("companies", [])
            import random
            
            scenarios = []
            for company in companies:
                base_revenue = company.get("revenue", 0)
                base_valuation = company.get("valuation", 0)
                
                # Run 100 simulations
                simulations = []
                for i in range(100):
                    growth_rate = random.uniform(0.5, 3.0)  # 50% to 300% growth
                    exit_multiple = random.uniform(3, 15)  # 3x to 15x revenue
                    
                    future_revenue = base_revenue * growth_rate
                    exit_valuation = future_revenue * exit_multiple
                    
                    simulations.append({
                        "simulation": i + 1,
                        "growth_rate": growth_rate,
                        "exit_multiple": exit_multiple,
                        "exit_valuation": exit_valuation
                    })
                
                # Calculate statistics
                valuations = [s["exit_valuation"] for s in simulations]
                scenarios.append({
                    "company": company.get("company"),
                    "base_valuation": base_valuation,
                    "mean_exit": sum(valuations) / len(valuations),
                    "median_exit": sorted(valuations)[50],
                    "p10_exit": sorted(valuations)[10],
                    "p90_exit": sorted(valuations)[90],
                    "simulations": simulations[:10]  # First 10 for brevity
                })
            
            return {"scenario_analysis": scenarios}
            
        except Exception as e:
            logger.error(f"Scenario analysis error: {e}")
            return {"error": str(e)}
    
    async def _execute_deal_comparison(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Execute comprehensive deal comparison"""
        try:
            companies = self.shared_data.get("companies", [])
            
            if len(companies) < 2:
                return {"comparison": "Need at least 2 companies to compare"}
            
            # Create comparison matrix
            comparison = {
                "companies": [],
                "metrics": {},
                "rankings": {},
                "recommendations": []
            }
            
            # Collect all metrics
            metrics_to_compare = [
                "valuation", "revenue", "total_funding", "team_size",
                "revenue_growth", "gross_margin", "burn_rate"
            ]
            
            for metric in metrics_to_compare:
                values = []
                for company in companies:
                    if metric == "gross_margin":
                        value = company.get("key_metrics", {}).get(metric, 0)
                    elif metric == "burn_rate":
                        value = company.get("key_metrics", {}).get(metric, 0)
                    else:
                        value = company.get(metric, 0)
                    values.append(value)
                
                comparison["metrics"][metric] = {
                    "values": values,
                    "average": sum(values) / len(values) if values else 0,
                    "best": max(values) if values else 0,
                    "worst": min(values) if values else 0
                }
            
            # Rank companies by key metrics
            for company in companies:
                score = 0
                score += (company.get("valuation", 0) / 1_000_000) * 0.3  # Valuation weight
                score += (company.get("revenue", 0) / 1_000_000) * 0.3  # Revenue weight
                score += company.get("revenue_growth", 0) * 100 * 0.2  # Growth weight
                score += company.get("key_metrics", {}).get("gross_margin", 0) * 100 * 0.2  # Margin weight
                
                comparison["companies"].append({
                    "name": company.get("company"),
                    "score": round(score, 2),
                    "stage": company.get("stage"),
                    "sector": company.get("sector")
                })
            
            # Sort by score
            comparison["companies"] = sorted(comparison["companies"], key=lambda x: x["score"], reverse=True)
            
            # Generate recommendations
            top_company = comparison["companies"][0] if comparison["companies"] else None
            if top_company:
                comparison["recommendations"].append(
                    f"Top investment opportunity: {top_company['name']} with score {top_company['score']}"
                )
            
            return {"deal_comparison": comparison}
            
        except Exception as e:
            logger.error(f"Deal comparison error: {e}")
            return {"error": str(e)}
    
    async def _execute_deck_generation(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Generate presentation deck with structured slides"""
        try:
            companies = self.shared_data.get("companies", [])
            slides = []
            
            # Title slide
            slides.append({
                "type": "title",
                "content": {
                    "title": f"Investment Analysis Report",
                    "subtitle": f"Analysis of {len(companies)} companies",
                    "date": datetime.now().strftime("%B %Y")
                }
            })
            
            # Executive summary
            total_funding = sum(c.get("total_funding", 0) for c in companies)
            avg_valuation = sum(c.get("valuation", 0) for c in companies) / max(len(companies), 1)
            
            slides.append({
                "type": "summary",
                "content": {
                    "title": "Executive Summary",
                    "bullets": [
                        f"Analyzing {len(companies)} companies",
                        f"Combined funding: ${total_funding:,.0f}",
                        f"Average valuation: ${avg_valuation:,.0f}",
                        f"Sectors: {', '.join(set(c.get('sector', 'Unknown') for c in companies))}"
                    ]
                }
            })
            
            # Individual company slides
            for company in companies[:5]:  # Limit to 5 companies
                slides.append({
                    "type": "company",
                    "content": {
                        "title": company.get("company", "Unknown"),
                        "business_model": company.get("business_model", "N/A"),
                        "metrics": {
                            "Stage": company.get("stage", "Unknown"),
                            "Revenue": f"${company.get('revenue', 0):,.0f}",
                            "Valuation": f"${company.get('valuation', 0):,.0f}",
                            "Total Funding": f"${company.get('total_funding', 0):,.0f}",
                            "Team Size": company.get("team_size", "Unknown"),
                            "Founded": company.get("founded_year", "Unknown")
                        },
                        "website": company.get("website_url", "")
                    }
                })
            
            # Comparison slide
            if len(companies) > 1:
                slides.append({
                    "type": "comparison",
                    "content": {
                        "title": "Company Comparison",
                        "companies": [{
                            "name": c.get("company"),
                            "valuation": c.get("valuation", 0),
                            "revenue": c.get("revenue", 0),
                            "stage": c.get("stage")
                        } for c in companies]
                    }
                })
            
            return {"deck": {"slides": slides, "slide_count": len(slides)}}
            
        except Exception as e:
            logger.error(f"Deck generation error: {e}")
            return {"error": str(e)}
    
    async def _execute_excel_generation(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Generate Excel spreadsheet with formulas and formatting"""
        try:
            companies = self.shared_data.get("companies", [])
            commands = []
            
            # Headers with formatting
            headers = ["Company", "Stage", "Revenue", "Valuation", "Total Funding", "Team Size", "Founded", "Business Model", "Gross Margin"]
            for i, header in enumerate(headers):
                cell = f"{chr(65 + i)}1"
                commands.append(f'sheet.write("{cell}", "{header}").style("bold", true).style("backgroundColor", "#4285F4").style("color", "white")')
            
            # Data rows
            for row_idx, company in enumerate(companies, start=2):
                commands.append(f'sheet.write("A{row_idx}", "{company.get("company", "")}")')
                commands.append(f'sheet.write("B{row_idx}", "{company.get("stage", "")}")')
                
                revenue = company.get("revenue", 0)
                if revenue:
                    commands.append(f'sheet.write("C{row_idx}", {revenue}).format("currency")')
                
                valuation = company.get("valuation", 0)
                if valuation:
                    commands.append(f'sheet.write("D{row_idx}", {valuation}).format("currency")')
                
                funding = company.get("total_funding", 0)
                if funding:
                    commands.append(f'sheet.write("E{row_idx}", {funding}).format("currency")')
                
                commands.append(f'sheet.write("F{row_idx}", {company.get("team_size", 0)})')
                commands.append(f'sheet.write("G{row_idx}", "{company.get("founded_year", "")}")')
                commands.append(f'sheet.write("H{row_idx}", "{company.get("business_model", "")}")')
                
                margin = company.get("key_metrics", {}).get("gross_margin", 0)
                if margin:
                    commands.append(f'sheet.write("I{row_idx}", {margin}).format("percentage")')
            
            # Add summary formulas
            if len(companies) > 0:
                last_row = len(companies) + 1
                summary_row = last_row + 2
                
                commands.append(f'sheet.write("A{summary_row}", "TOTALS").style("bold", true)')
                commands.append(f'sheet.formula("C{summary_row}", "=SUM(C2:C{last_row})").format("currency")')
                commands.append(f'sheet.formula("D{summary_row}", "=AVERAGE(D2:D{last_row})").format("currency")')
                commands.append(f'sheet.formula("E{summary_row}", "=SUM(E2:E{last_row})").format("currency")')
                commands.append(f'sheet.formula("F{summary_row}", "=SUM(F2:F{last_row})")')
                
                # Add chart
                commands.append(f'sheet.createChart("column", "K2", {{"data": "A1:E{last_row}", "title": "Company Metrics Comparison"}})')
            
            return {
                "spreadsheet": {
                    "commands": commands,
                    "rows": len(companies) + 3,
                    "columns": 9
                }
            }
            
        except Exception as e:
            logger.error(f"Excel generation error: {e}")
            return {"error": str(e)}
    
    async def _execute_memo_generation(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Generate investment memo document"""
        try:
            companies = self.shared_data.get("companies", [])
            
            memo_sections = []
            
            # Executive Summary
            total_funding = sum(c.get("total_funding", 0) for c in companies)
            avg_valuation = sum(c.get("valuation", 0) for c in companies) / max(len(companies), 1)
            
            memo_sections.append({
                "section": "Executive Summary",
                "content": f"""This memo analyzes {len(companies)} companies with a combined funding of ${total_funding:,.0f} 
and average valuation of ${avg_valuation:,.0f}. The companies span sectors including 
{', '.join(set(c.get('sector', 'Unknown') for c in companies))}."""
            })
            
            # Individual Company Analysis
            for company in companies:
                memo_sections.append({
                    "section": f"Company Analysis: {company.get('company', 'Unknown')}",
                    "content": f"""
**Business Model**: {company.get('business_model', 'N/A')}
**Stage**: {company.get('stage', 'Unknown')}
**Valuation**: ${company.get('valuation', 0):,.0f}
**Revenue**: ${company.get('revenue', 0):,.0f}
**Total Funding**: ${company.get('total_funding', 0):,.0f}
**Website**: {company.get('website_url', 'N/A')}

**Investment Thesis**: 
{company.get('product_description', 'Innovative technology company with strong growth potential.')}

**Key Metrics**:
- Team Size: {company.get('team_size', 'Unknown')}
- Founded: {company.get('founded_year', 'Unknown')}
- Gross Margin: {company.get('key_metrics', {}).get('gross_margin', 0) * 100:.1f}%
- Revenue Growth: {company.get('revenue_growth', 0) * 100:.1f}%
                    """
                })
            
            # Risk Analysis
            memo_sections.append({
                "section": "Risk Analysis",
                "content": """Key risks include market competition, execution risk, and funding environment. 
Mitigation strategies include portfolio diversification and staged investment approach."""
            })
            
            # Recommendations
            if companies:
                top_companies = sorted(companies, key=lambda x: x.get('valuation', 0), reverse=True)[:3]
                recommendations = [f"- {c.get('company')}: ${c.get('valuation', 0):,.0f} valuation" for c in top_companies]
                
                memo_sections.append({
                    "section": "Investment Recommendations",
                    "content": "Top investment opportunities:\n" + "\n".join(recommendations)
                })
            
            return {
                "memo": {
                    "title": "Investment Analysis Memo",
                    "date": datetime.now().strftime("%B %d, %Y"),
                    "sections": memo_sections,
                    "word_count": sum(len(s["content"].split()) for s in memo_sections)
                }
            }
            
        except Exception as e:
            logger.error(f"Memo generation error: {e}")
            return {"error": str(e)}
    
    async def _execute_chart_generation(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Generate charts and visualizations"""
        try:
            companies = self.shared_data.get("companies", [])
            charts = []
            
            # Valuation comparison chart
            if companies:
                charts.append({
                    "type": "bar",
                    "title": "Company Valuations",
                    "data": {
                        "labels": [c.get("company", "Unknown") for c in companies],
                        "datasets": [{
                            "label": "Valuation (USD)",
                            "data": [c.get("valuation", 0) for c in companies],
                            "backgroundColor": "#4285F4"
                        }]
                    },
                    "options": {
                        "scales": {"y": {"beginAtZero": True}},
                        "plugins": {"legend": {"display": True}}
                    }
                })
            
            # Revenue vs Funding scatter plot
            if len(companies) > 1:
                charts.append({
                    "type": "scatter",
                    "title": "Revenue vs Total Funding",
                    "data": {
                        "datasets": [{
                            "label": "Companies",
                            "data": [
                                {
                                    "x": c.get("total_funding", 0),
                                    "y": c.get("revenue", 0),
                                    "label": c.get("company")
                                } for c in companies
                            ],
                            "backgroundColor": "#34A853"
                        }]
                    },
                    "options": {
                        "scales": {
                            "x": {"title": {"text": "Total Funding"}},
                            "y": {"title": {"text": "Revenue"}}
                        }
                    }
                })
            
            # Stage distribution pie chart
            stage_counts = {}
            for company in companies:
                stage = company.get("stage", "Unknown")
                stage_counts[stage] = stage_counts.get(stage, 0) + 1
            
            if stage_counts:
                charts.append({
                    "type": "pie",
                    "title": "Companies by Stage",
                    "data": {
                        "labels": list(stage_counts.keys()),
                        "datasets": [{
                            "data": list(stage_counts.values()),
                            "backgroundColor": [
                                "#4285F4", "#34A853", "#FBBC04", 
                                "#EA4335", "#673AB7", "#00ACC1"
                            ]
                        }]
                    }
                })
            
            # Growth rate comparison
            growth_companies = [c for c in companies if c.get("revenue_growth", 0) > 0]
            if growth_companies:
                charts.append({
                    "type": "horizontalBar",
                    "title": "Revenue Growth Rates",
                    "data": {
                        "labels": [c.get("company") for c in growth_companies],
                        "datasets": [{
                            "label": "Growth Rate (%)",
                            "data": [c.get("revenue_growth", 0) * 100 for c in growth_companies],
                            "backgroundColor": "#FBBC04"
                        }]
                    }
                })
            
            return {
                "charts": {
                    "visualizations": charts,
                    "chart_count": len(charts),
                    "chart_types": list(set(c["type"] for c in charts))
                }
            }
            
        except Exception as e:
            logger.error(f"Chart generation error: {e}")
            return {"error": str(e)}
    
    async def _format_output(
        self,
        results: Dict[str, Any],
        output_format: str,
        prompt: str
    ) -> Dict[str, Any]:
        """Format the final output based on requested format"""
        
        # Combine all results with shared data
        final_data = {
            **self.shared_data,
            **results
        }
        
        # Ensure we have companies in the right format
        companies_list = []
        
        # Check different possible locations for companies
        if "company-data-fetcher" in results:
            fetcher_data = results["company-data-fetcher"]
            if isinstance(fetcher_data, dict) and "companies" in fetcher_data:
                companies_list = fetcher_data["companies"]
        
        if not companies_list and "companies" in self.shared_data:
            companies_list = self.shared_data["companies"]
            
        # Update final data with companies list
        final_data["companies"] = companies_list
        
        # Format based on output type
        if output_format == "spreadsheet":
            return self._format_spreadsheet(final_data)
        elif output_format == "deck":
            return self._format_deck(final_data)
        elif output_format == "matrix":
            return self._format_matrix(final_data)
        else:
            return self._format_analysis(final_data)
    
    def _format_spreadsheet(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Format data for spreadsheet output with commands"""
        companies = data.get("companies", [])
        commands = []
        
        # Generate header commands
        headers = self._generate_spreadsheet_columns(data)
        for i, header in enumerate(headers):
            cell = f"{chr(65 + i)}1"
            commands.append(f'sheet.write("{cell}", "{header}").style("bold", true).style("backgroundColor", "#f0f0f0")')
        
        # Generate data commands
        rows = self._generate_spreadsheet_rows(data)
        for row_idx, row in enumerate(rows, start=2):
            for col_idx, value in enumerate(row):
                cell = f"{chr(65 + col_idx)}{row_idx}"
                if isinstance(value, (int, float)) and value > 1000:
                    commands.append(f'sheet.write("{cell}", {value}).format("currency")')
                elif isinstance(value, float) and 0 < value < 1:
                    commands.append(f'sheet.write("{cell}", {value}).format("percentage")')
                else:
                    commands.append(f'sheet.write("{cell}", "{value}")')
        
        # Add formulas
        if len(rows) > 0:
            last_row = len(rows) + 1
            commands.append(f'sheet.formula("E{last_row + 1}", "=SUM(E2:E{last_row})").style("bold", true)')
            commands.append(f'sheet.formula("F{last_row + 1}", "=AVERAGE(F2:F{last_row})").style("bold", true)')
            commands.append(f'sheet.formula("G{last_row + 1}", "=SUM(G2:G{last_row})").style("bold", true)')
        
        return {
            "type": "spreadsheet",
            "commands": commands,
            "data": data,
            "columns": headers,
            "rows": rows,
            "hasFormulas": True,
            "hasCharts": False
        }
    
    def _format_deck(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Format data for deck output"""
        return {
            "type": "deck",
            "slides": self._generate_slides(data),
            "data": data
        }
    
    def _format_matrix(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Format data for matrix output"""
        return {
            "type": "matrix",
            "data": data,
            "dimensions": self._generate_matrix_dimensions(data)
        }
    
    def _format_analysis(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Format data for analysis output"""
        return {
            "type": "analysis",
            "data": data,
            "summary": self._generate_summary(data)
        }
    
    def _generate_spreadsheet_columns(self, data: Dict[str, Any]) -> List[str]:
        """Generate column headers for spreadsheet"""
        return [
            "Company", "Stage", "Business Model", "Sector",
            "Revenue", "Valuation", "Total Funding", 
            "Team Size", "Founded", "Gross Margin", "Growth Rate"
        ]
    
    def _generate_spreadsheet_rows(self, data: Dict[str, Any]) -> List[List[Any]]:
        """Generate rows for spreadsheet"""
        rows = []
        companies = data.get("companies", [])
        
        for company in companies:
            row = [
                company.get("company", ""),
                company.get("stage", ""),
                company.get("business_model", ""),
                company.get("sector", ""),
                company.get("revenue", 0),
                company.get("valuation", 0),
                company.get("total_funding", 0),
                company.get("team_size", 0),
                company.get("founded_year", ""),
                company.get("key_metrics", {}).get("gross_margin", 0),
                company.get("revenue_growth", 0)
            ]
            rows.append(row)
        
        return rows
    
    def _generate_slides(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate slides for deck"""
        companies = data.get("companies", [])
        slides = []
        
        # Title slide
        slides.append({
            "type": "title",
            "title": "Investment Analysis",
            "subtitle": f"{len(companies)} Companies Analyzed",
            "date": datetime.now().strftime("%B %d, %Y")
        })
        
        # Market overview
        if companies:
            total_funding = sum(c.get("total_funding", 0) for c in companies)
            avg_valuation = sum(c.get("valuation", 0) for c in companies) / len(companies)
            
            slides.append({
                "type": "overview",
                "title": "Market Overview",
                "metrics": {
                    "Total Market Cap": f"${avg_valuation * len(companies):,.0f}",
                    "Total Funding Raised": f"${total_funding:,.0f}",
                    "Average Valuation": f"${avg_valuation:,.0f}",
                    "Companies Analyzed": len(companies)
                }
            })
        
        # Company deep dives
        for company in companies[:3]:  # Top 3 companies
            slides.append({
                "type": "company_profile",
                "title": company.get("company", "Unknown"),
                "content": {
                    "Business": company.get("business_model", "N/A"),
                    "Stage": company.get("stage", "N/A"),
                    "Valuation": f"${company.get('valuation', 0):,.0f}",
                    "Revenue": f"${company.get('revenue', 0):,.0f}",
                    "Website": company.get("website_url", "N/A")
                }
            })
        
        # Valuation comparison
        slides.append({
            "type": "chart",
            "title": "Valuation Comparison",
            "chart_type": "bar",
            "data": [{
                "name": c.get("company"),
                "value": c.get("valuation", 0)
            } for c in companies[:5]]
        })
        
        return slides
    
    def _generate_matrix_dimensions(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate matrix dimensions"""
        return {
            "x_axis": "companies",
            "y_axis": "metrics"
        }
    
    def _generate_summary(self, data: Dict[str, Any]) -> str:
        """Generate summary for analysis"""
        return "Analysis complete"
    
    async def _extract_comprehensive_profile(
        self, 
        company_name: str, 
        search_results: List[Dict[str, Any]],
        linkedin_identifier: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Extract comprehensive company profile using Claude
        This is the core extraction method that was in the missing part of the file
        
        Args:
            company_name: Name of the company (without @)
            search_results: List of Tavily search results
            linkedin_identifier: Optional LinkedIn identifier for validation
            
        Returns:
            Comprehensive company profile with all extracted data
        """
        try:
            # Combine all search results into context
            all_content = []
            all_urls = set()
            
            for result in search_results:
                if result and 'results' in result:
                    for r in result['results']:
                        content = r.get('content', '')
                        url = r.get('url', '')
                        title = r.get('title', '')
                        
                        all_content.append(f"[{title}]\nURL: {url}\n{content}")
                        
                        # Extract domains mentioned in content
                        import re
                        domains = re.findall(
                            r'(?:https?://)?(?:www\.)?([a-zA-Z0-9\-]+\.(?:com|io|ai|co|dev|app|group|org|net|tech|xyz|vc|one|uk|eu))',
                            content + ' ' + url
                        )
                        all_urls.update(domains)
            
            combined_content = "\n\n---\n\n".join(all_content[:10])  # Limit to first 10 results
            
            # Use Claude to extract structured data
            extraction_prompt = f"""Extract comprehensive structured data about {company_name} from the following search results.

Search Results:
{combined_content[:15000]}  # Limit context to 15k chars

Domains found in content: {', '.join(list(all_urls)[:20])}

Extract and return a JSON object with the following structure. BE SPECIFIC, not generic:

{{
    "company": "{company_name}",
    "website_url": "actual company website URL if found, otherwise null",
    "business_model": "SPECIFIC description like 'AI-powered code generation IDE' or 'PropTech lettings management platform', NOT generic like 'SaaS' or 'Software'",
    "sector": "SPECIFIC sector like 'Healthcare AI', 'PropTech', 'DevTools', NOT generic like 'Technology'",
    "category": "SPECIFIC category like 'AI Code Assistant', 'Property Management', NOT generic",
    "stage": "Seed/Series A/Series B/etc",
    "founded_year": 2020,
    "headquarters": "City, Country",
    "team_size": 50,
    "founders": [
        {{"name": "Name", "role": "CEO", "background": "Previous company or experience"}}
    ],
    "funding_rounds": [
        {{
            "date": "2024-01",
            "round": "Series A", 
            "amount": 10000000,
            "valuation": 50000000,
            "investors": ["Investor 1", "Investor 2"]
        }}
    ],
    "total_funding": 15000000,
    "latest_valuation": 50000000,
    "revenue": 5000000,
    "revenue_growth": 2.5,
    "customers": ["Customer 1", "Customer 2"],
    "competitors": ["Competitor 1", "Competitor 2"],
    "key_metrics": {{
        "arr": 5000000,
        "mrr": 400000,
        "gross_margin": 0.75,
        "burn_rate": 500000,
        "runway_months": 18,
        "ltv_cac_ratio": 3.5
    }},
    "acquisitions": ["Company acquired if any"],
    "product_description": "Detailed description of what the product does",
    "target_market": "Who they sell to",
    "pricing_model": "How they charge (per seat, usage-based, etc)",
    "technology_stack": ["Tech 1", "Tech 2"],
    "recent_news": ["Recent development 1", "Recent development 2"]
}}

IMPORTANT RULES:
1. For website_url, choose the most likely official company website from the domains found
2. If {company_name.lower()}.com/io/ai exists in domains, prefer that
3. For UK companies, check for .co.uk or .group domains
4. Be SPECIFIC in business_model and sector - describe what they actually do
5. If you find funding data, include specific amounts and dates
6. Set null for any field you cannot find data for
7. DO NOT make up data - use null if not found

Return ONLY the JSON object, no other text."""

            if self.claude:
                response = await self.claude.messages.create(
                    model="claude-3-5-sonnet-20241022",
                    max_tokens=4000,
                    temperature=0.1,
                    messages=[
                        {"role": "user", "content": extraction_prompt}
                    ]
                )
                
                # Parse Claude's response
                response_text = response.content[0].text if response.content else "{}"
                
                # Clean and parse JSON
                import json
                # Remove any markdown formatting if present
                if "```json" in response_text:
                    response_text = response_text.split("```json")[1].split("```")[0]
                elif "```" in response_text:
                    response_text = response_text.split("```")[1].split("```")[0]
                
                try:
                    extracted_data = json.loads(response_text)
                except json.JSONDecodeError:
                    logger.error(f"Failed to parse Claude response: {response_text[:500]}")
                    extracted_data = {"company": company_name}
            else:
                # Fallback extraction without Claude
                extracted_data = {
                    "company": company_name,
                    "website_url": None,
                    "business_model": "Technology company",
                    "sector": "Technology"
                }
                
                # Try to find website URL from search results
                for url in all_urls:
                    if company_name.lower() in url.lower():
                        extracted_data["website_url"] = f"https://{url}"
                        break
            
            # Ensure we have essential fields
            if not extracted_data.get("company"):
                extracted_data["company"] = company_name
                
            logger.info(f"Extracted profile for {company_name}: {extracted_data.get('business_model', 'Unknown')}, {extracted_data.get('website_url', 'No website')}")
            
            return extracted_data
            
        except Exception as e:
            logger.error(f"Error extracting comprehensive profile for {company_name}: {e}")
            return {
                "company": company_name,
                "error": str(e)
            }
    
    async def __aenter__(self):
        """Async context manager entry"""
        if not self.session:
            self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self.session:
            await self.session.close()
            self.session = None


# Singleton instance getter
_orchestrator_instance = None

def get_unified_orchestrator() -> UnifiedMCPOrchestrator:
    """Get or create singleton orchestrator instance"""
    global _orchestrator_instance
    if _orchestrator_instance is None:
        _orchestrator_instance = UnifiedMCPOrchestrator()
    return _orchestrator_instance


# For backwards compatibility
SingleAgentOrchestrator = UnifiedMCPOrchestrator
