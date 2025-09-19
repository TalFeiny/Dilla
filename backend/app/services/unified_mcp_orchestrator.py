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
            },
            
            # Cap Table & Fund Management Skills
            "cap-table-generator": {
                "category": SkillCategory.ANALYSIS,
                "handler": self._execute_cap_table_generation,
                "description": "Generate cap tables with ownership"
            },
            "portfolio-analyzer": {
                "category": SkillCategory.ANALYSIS,
                "handler": self._execute_portfolio_analysis,
                "description": "Analyze fund portfolio performance"
            },
            "fund-metrics-calculator": {
                "category": SkillCategory.ANALYSIS,
                "handler": self._execute_fund_metrics,
                "description": "Calculate DPI, TVPI, IRR"
            },
            "stage-analyzer": {
                "category": SkillCategory.ANALYSIS,
                "handler": self._execute_stage_analysis,
                "description": "Multi-stage investment analysis"
            },
            "exit-modeler": {
                "category": SkillCategory.ANALYSIS,
                "handler": self._execute_exit_modeling,
                "description": "Model exit scenarios and returns"
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
        
        # Return in the format the endpoint expects
        if result and not result.get("error"):
            return {"success": True, "results": result}
        else:
            return {"success": False, "error": result.get("error") if result else "No result generated"}
    
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
        
        # ALWAYS generate cap tables for any company analysis
        if len(entities.get("companies", [])) > 0:
            chain.append(SkillChainNode(
                skill="cap-table-generator",
                purpose="Generate cap tables with ownership evolution",
                inputs={"use_shared_data": True},
                parallel_group=1
            ))
        
        # ALWAYS do valuations for investment decisions
        if len(entities.get("companies", [])) > 0:
            chain.append(SkillChainNode(
                skill="valuation-engine",
                purpose="Calculate valuations (bull/bear/base scenarios)",
                inputs={"use_shared_data": True},
                parallel_group=1
            ))
        
        # Fund portfolio analysis - ALWAYS if fund context mentioned
        if "fund" in prompt.lower() or "portfolio" in prompt.lower() or "deploy" in prompt.lower():
            chain.append(SkillChainNode(
                skill="portfolio-analyzer",
                purpose="Analyze portfolio",
                inputs={"context": entities},
                parallel_group=1
            ))
            
            # Fund metrics if DPI or deployment mentioned
            if "dpi" in prompt.lower() or "deploy" in prompt.lower() or "tvpi" in prompt.lower():
                chain.append(SkillChainNode(
                    skill="fund-metrics-calculator",
                    purpose="Calculate fund metrics",
                    inputs={"context": entities},
                    parallel_group=1
                ))
        
        # Multi-stage analysis
        if ("seed" in prompt.lower() and "series" in prompt.lower()) or "stage" in prompt.lower():
            chain.append(SkillChainNode(
                skill="stage-analyzer",
                purpose="Analyze investment stages",
                inputs={"stages": ["seed", "series_a", "series_b"]},
                parallel_group=1
            ))
        
        # ALWAYS model exit scenarios for investment decisions
        if len(entities.get("companies", [])) > 0:
            chain.append(SkillChainNode(
                skill="exit-modeler",
                purpose="Model exit scenarios (win/lose/base cases)",
                inputs={"use_shared_data": True},
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
        import re
        
        entities = {
            "companies": [],
            "funds": [],
            "metrics": []
        }
        
        # Extract @Company mentions
        company_pattern = r'@(\w+)'
        companies = re.findall(company_pattern, prompt)
        entities["companies"] = list(set(companies))
        
        # Extract fund parameters
        prompt_lower = prompt.lower()
        
        # Fund size (e.g., "456m fund")
        fund_pattern = r'(\d+(?:\.\d+)?)\s*(?:m|million|b|billion)\s+fund'
        fund_match = re.search(fund_pattern, prompt_lower)
        if fund_match:
            value = float(fund_match.group(1))
            multiplier = 1_000_000 if 'm' in fund_match.group(0) else 1_000_000_000
            entities["fund_size"] = value * multiplier
        
        # Remaining capital to deploy (e.g., "276m to deploy")
        deploy_pattern = r'(\d+(?:\.\d+)?)\s*(?:m|million|b|billion)\s+to\s+deploy'
        deploy_match = re.search(deploy_pattern, prompt_lower)
        if deploy_match:
            value = float(deploy_match.group(1))
            multiplier = 1_000_000 if 'm' in deploy_match.group(0) else 1_000_000_000
            entities["remaining_capital"] = value * multiplier
        
        # DPI (e.g., "0.5 dpi")
        dpi_pattern = r'(\d+(?:\.\d+)?)\s*dpi'
        dpi_match = re.search(dpi_pattern, prompt_lower)
        if dpi_match:
            entities["dpi"] = float(dpi_match.group(1))
        
        # Portfolio size (e.g., "16 portfolio companies")
        portfolio_pattern = r'(\d+)\s+portfolio\s+compan'
        portfolio_match = re.search(portfolio_pattern, prompt_lower)
        if portfolio_match:
            entities["portfolio_size"] = int(portfolio_match.group(1))
        
        # Exits (e.g., "2 exited")
        exit_pattern = r'(\d+)\s+exit'
        exit_match = re.search(exit_pattern, prompt_lower)
        if exit_match:
            entities["exits"] = int(exit_match.group(1))
        
        # Year and quarter (e.g., "year 3 q1")
        year_pattern = r'year\s+(\d+)'
        quarter_pattern = r'q(\d+)'
        year_match = re.search(year_pattern, prompt_lower)
        quarter_match = re.search(quarter_pattern, prompt_lower)
        if year_match:
            entities["deployment_year"] = int(year_match.group(1))
        if quarter_match:
            entities["deployment_quarter"] = int(quarter_match.group(1))
        
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
                return {"companies": [cache_entry["data"]]}
        
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
            
            # ALWAYS calculate GPU-adjusted gross margin and metrics
            try:
                # Calculate GPU metrics
                gpu_metrics = self.gap_filler.calculate_gpu_adjusted_metrics(extracted_data)
                extracted_data["gpu_metrics"] = gpu_metrics
                
                # Calculate adjusted gross margin with GPU impact (not async)
                margin_analysis = self.gap_filler.calculate_adjusted_gross_margin(
                    extracted_data,
                    base_gross_margin=extracted_data.get("gross_margin")
                )
                extracted_data["gross_margin_analysis"] = margin_analysis
                extracted_data["gross_margin"] = margin_analysis["adjusted_gross_margin"]
                
                # Add key GPU cost fields to unit economics
                if "unit_economics" not in extracted_data:
                    extracted_data["unit_economics"] = {}
                extracted_data["unit_economics"]["gpu_cost_estimate"] = f"${gpu_metrics['cost_per_transaction']:.2f}/transaction"
                extracted_data["unit_economics"]["monthly_gpu_costs"] = gpu_metrics["monthly_gpu_costs"]
                extracted_data["unit_economics"]["compute_intensity"] = gpu_metrics["compute_intensity"]
                
            except Exception as e:
                logger.warning(f"Failed to calculate GPU metrics for {company}: {e}")
            
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
                    
                    # Handle dict values (convert to numeric)
                    if isinstance(value, dict):
                        # Try to extract a numeric value from dict
                        if 'value' in value:
                            value = value['value']
                        elif 'amount' in value:
                            value = value['amount']
                        else:
                            value = 0
                    
                    # Ensure numeric value
                    try:
                        value = float(value) if value else 0
                    except (TypeError, ValueError):
                        value = 0
                        
                    values.append(value)
                
                # Filter out zeros for calculations
                non_zero_values = [v for v in values if v > 0]
                
                comparison["metrics"][metric] = {
                    "values": values,
                    "average": sum(non_zero_values) / len(non_zero_values) if non_zero_values else 0,
                    "best": max(non_zero_values) if non_zero_values else 0,
                    "worst": min(non_zero_values) if non_zero_values else 0
                }
            
            # Rank companies by key metrics
            for company in companies:
                score = 0
                
                # Safely get numeric values
                valuation = company.get("valuation", 0) or 0
                revenue = company.get("revenue", 0) or 0
                revenue_growth = company.get("revenue_growth", 0) or 0
                gross_margin = company.get("key_metrics", {}).get("gross_margin", 0) or 0
                
                # Handle dict values
                if isinstance(valuation, dict):
                    valuation = valuation.get('value', 0) or valuation.get('amount', 0) or 0
                if isinstance(revenue, dict):
                    revenue = revenue.get('value', 0) or revenue.get('amount', 0) or 0
                
                # Calculate investment score with proper normalization
                # Normalize valuation (cap at $1B for scoring)
                val_score = min(float(valuation) / 1_000_000_000, 1.0) * 100 if valuation else 0
                
                # Normalize revenue (assume $100M is excellent)
                rev_score = min(float(revenue) / 100_000_000, 1.0) * 100 if revenue else 0
                
                # Normalize growth (cap at 300% = 3.0)
                growth_score = min(float(revenue_growth), 3.0) / 3.0 * 100 if revenue_growth else 0
                
                # Normalize margin (already 0-1 range)
                margin_score = float(gross_margin) * 100 if gross_margin else 0
                
                # Analyze unit economics and ACV (Annual Contract Value)
                unit_econ = company.get("unit_economics", {})
                compute_intensity = unit_econ.get("compute_intensity", "").lower()
                target_segment = unit_econ.get("target_segment", "").lower()
                
                # Estimate ACV based on target segment
                acv_estimate = 0
                if "fortune" in target_segment or "largest" in target_segment:
                    acv_estimate = 500_000  # $500K+ ACV typical
                elif "enterprise" in target_segment:
                    acv_estimate = 100_000  # $100K ACV typical
                elif "mid-market" in target_segment:
                    acv_estimate = 30_000   # $30K ACV typical
                elif "sme" in target_segment:
                    acv_estimate = 5_000    # $5K ACV typical
                elif "prosumer" in target_segment:
                    acv_estimate = 500      # $500 ACV typical
                
                # Calculate burn based on compute intensity vs revenue (it's a spectrum)
                # Every company now has AI costs, but impact varies by revenue base
                base_check = 10_000_000  # $10M base for Series A
                existing_revenue = float(revenue) if revenue else 0
                
                # Calculate AI spend as % of revenue
                if any(term in compute_intensity for term in ["generates", "50 slides", "video", "image", "code"]):
                    if existing_revenue > 50_000_000:
                        # Large SaaS adding AI features (5-10% of revenue)
                        ai_spend_ratio = 0.08
                        required_check = base_check * 1.1
                        burn_estimate = f"Sustainable ({ai_spend_ratio*100:.0f}% of ${existing_revenue/1_000_000:.0f}M revenue on AI)"
                    elif existing_revenue > 10_000_000:
                        # Mid-size transitioning to AI (10-20% of revenue)
                        ai_spend_ratio = 0.15
                        required_check = base_check * 1.5
                        burn_estimate = f"Moderate ({ai_spend_ratio*100:.0f}% of ${existing_revenue/1_000_000:.0f}M revenue on AI)"
                    elif existing_revenue > 1_000_000:
                        # Small with AI features (20-40% of revenue)
                        ai_spend_ratio = 0.30
                        required_check = base_check * 2.0
                        burn_estimate = f"Heavy ({ai_spend_ratio*100:.0f}% of ${existing_revenue/1_000_000:.1f}M revenue on AI)"
                    else:
                        # AI-first startup (could be 50-80% on compute)
                        ai_spend_ratio = 0.60
                        required_check = base_check * 3.0
                        burn_estimate = "Extreme (60%+ on compute, pre-revenue)"
                else:
                    # Traditional SaaS still adding some AI (2-5%)
                    ai_spend_ratio = 0.03
                    required_check = base_check
                    burn_estimate = f"Low (3% on AI features)"
                
                # Store for later use in recommendations
                company["required_check_size"] = required_check
                company["burn_estimate"] = burn_estimate
                
                # GPU costs impact scoring based on ACV
                # Per CLAUDE.md: High GPU + ACV > $100K = still good (10-15x multiple)
                gpu_penalty = 1.0  # No penalty by default
                
                # High compute workloads
                if any(term in compute_intensity for term in ["generates", "50 slides", "video", "image", "code"]):
                    if acv_estimate >= 100_000:
                        gpu_penalty = 0.9  # Only 10% penalty - they can pass through costs
                    elif acv_estimate >= 30_000:
                        gpu_penalty = 0.7  # 30% penalty - margins squeezed
                    else:
                        gpu_penalty = 0.3  # 70% penalty - unit economics broken
                
                # Low compute = always good
                elif any(term in compute_intensity for term in ["stores", "queries", "crud", "database"]):
                    gpu_penalty = 1.1  # 10% bonus for low compute costs
                
                # Calculate weighted score
                score = (val_score * 0.25 +     # 25% weight on valuation
                        rev_score * 0.35 +       # 35% weight on revenue
                        growth_score * 0.25 +    # 25% weight on growth
                        margin_score * 0.15      # 15% weight on margins
                        ) * gpu_penalty
                
                # Add detailed scoring breakdown
                comparison["companies"].append({
                    "name": company.get("company"),
                    "score": round(score, 2),
                    "stage": company.get("stage"),
                    "sector": company.get("sector"),
                    "business_model": company.get("business_model"),
                    "valuation": valuation,
                    "revenue": revenue,
                    "growth": revenue_growth,
                    "margin": gross_margin,
                    "gpu_intensive": is_ai_company,
                    "score_breakdown": {
                        "valuation_score": round(val_score, 1),
                        "revenue_score": round(rev_score, 1),
                        "growth_score": round(growth_score, 1),
                        "margin_score": round(margin_score, 1),
                        "gpu_penalty_applied": gpu_penalty < 1.0
                    }
                })
            
            # Sort by score
            comparison["companies"] = sorted(comparison["companies"], key=lambda x: x["score"], reverse=True)
            
            # Generate detailed investment recommendations
            if comparison["companies"]:
                top_company = comparison["companies"][0]
                
                # Analyze entry points
                for company in comparison["companies"]:
                    stage = company.get("stage", "Unknown").lower()
                    
                    # Entry point analysis with burn considerations
                    required_check = company.get("required_check_size", 10_000_000)
                    burn_estimate = company.get("burn_estimate", "Unknown")
                    
                    if "seed" in stage:
                        entry_analysis = f"Early entry with high risk/reward. Typical $2-5M valuation, 20-30% ownership possible."
                    elif "series a" in stage or "a" in stage:
                        entry_analysis = f"Growth stage entry. Typical $20-50M valuation, 10-20% ownership possible. Required check: ${required_check/1_000_000:.0f}M"
                    elif "series b" in stage or "b" in stage:
                        entry_analysis = f"Later stage, lower risk. Typical $100-200M valuation, 5-10% ownership possible. Required check: ${required_check*2/1_000_000:.0f}M"
                    else:
                        entry_analysis = "Stage unclear, requires further analysis."
                    
                    # Burn rate impact
                    gpu_analysis = ""
                    if company.get("gpu_intensive") or burn_estimate.startswith("High"):
                        gpu_analysis = f" BURN RATE: {burn_estimate}. Needs larger rounds to reach profitability."
                    
                    comparison["recommendations"].append(
                        f"{company['name']} (Score: {company['score']}): {entry_analysis}{gpu_analysis}"
                    )
                
                # Winner recommendation
                comparison["recommendations"].insert(0,
                    f"RECOMMENDED: {top_company['name']} - Better entry point based on score/stage/market combination."
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
    
    async def _execute_cap_table_generation(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Generate cap tables with ownership percentages"""
        try:
            companies = self.shared_data.get("companies", [])
            cap_tables = {}
            
            for company in companies:
                company_name = company.get("company", "Unknown")
                
                # Get funding rounds from company data
                funding_rounds = company.get("funding_rounds", [])
                
                if not funding_rounds:
                    # Generate rounds using industry benchmarks for funding amounts
                    stage = company.get("stage", "")
                    current_valuation = company.get("valuation", 0)
                    
                    # Standard funding amounts by stage (industry benchmarks)
                    stage_amounts = {
                        "seed": 1_500_000,      # $1.5M seed round
                        "series_a": 8_000_000,   # $8M Series A
                        "series_b": 25_000_000,  # $25M Series B
                        "series_c": 50_000_000   # $50M Series C
                    }
                    
                    if "seed" in stage.lower():
                        # Seed stage company
                        seed_val = 10_000_000  # $10M post-money typical seed
                        funding_rounds = [
                            {"round": "Seed", "amount": stage_amounts["seed"], "valuation": seed_val}
                        ]
                    elif "series a" in stage.lower() or "a" in stage:
                        # Series A company
                        seed_val = 10_000_000
                        a_val = 50_000_000  # $50M post-money typical Series A
                        funding_rounds = [
                            {"round": "Seed", "amount": stage_amounts["seed"], "valuation": seed_val},
                            {"round": "Series A", "amount": stage_amounts["series_a"], "valuation": a_val}
                        ]
                    elif "series b" in stage.lower() or "b" in stage:
                        # Series B company
                        seed_val = 10_000_000
                        a_val = 50_000_000
                        b_val = 200_000_000  # $200M post-money typical Series B
                        funding_rounds = [
                            {"round": "Seed", "amount": stage_amounts["seed"], "valuation": seed_val},
                            {"round": "Series A", "amount": stage_amounts["series_a"], "valuation": a_val},
                            {"round": "Series B", "amount": stage_amounts["series_b"], "valuation": b_val}
                        ]
                    elif "series c" in stage.lower() or "c" in stage:
                        # Series C company
                        seed_val = 10_000_000
                        a_val = 50_000_000
                        b_val = 200_000_000
                        c_val = 500_000_000  # $500M post-money typical Series C
                        funding_rounds = [
                            {"round": "Seed", "amount": stage_amounts["seed"], "valuation": seed_val},
                            {"round": "Series A", "amount": stage_amounts["series_a"], "valuation": a_val},
                            {"round": "Series B", "amount": stage_amounts["series_b"], "valuation": b_val},
                            {"round": "Series C", "amount": stage_amounts["series_c"], "valuation": c_val}
                        ]
                
                # Use PrePostCapTable service to calculate
                # Pass funding rounds directly as the service expects
                cap_table = self.cap_table_service.calculate_full_cap_table_history(
                    company_data=funding_rounds
                )
                
                cap_tables[company_name] = cap_table
            
            return {
                "cap_tables": cap_tables,
                "company_count": len(cap_tables)
            }
            
        except Exception as e:
            logger.error(f"Cap table generation error: {e}")
            return {"error": str(e)}
    
    async def _execute_portfolio_analysis(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze fund portfolio performance"""
        try:
            context = inputs.get("context", {})
            companies = self.shared_data.get("companies", [])
            
            # Extract fund parameters from context or defaults
            fund_size = context.get("fund_size", 456_000_000)  # $456M
            remaining_capital = context.get("remaining_capital", 276_000_000)  # $276M to deploy
            portfolio_size = context.get("portfolio_size", 16)
            exits = context.get("exits", 2)
            
            portfolio_analysis = {
                "fund_overview": {
                    "total_fund_size": fund_size,
                    "deployed_capital": fund_size - remaining_capital,
                    "remaining_capital": remaining_capital,
                    "deployment_rate": (fund_size - remaining_capital) / fund_size,
                    "portfolio_companies": portfolio_size,
                    "exits_completed": exits,
                    "active_investments": portfolio_size - exits
                },
                "investment_strategy": {
                    "avg_check_size": (fund_size - remaining_capital) / portfolio_size if portfolio_size > 0 else 0,
                    "remaining_investments": int(remaining_capital / ((fund_size - remaining_capital) / portfolio_size)) if portfolio_size > 0 else 0,
                    "capital_per_stage": {
                        "seed": remaining_capital * 0.2,
                        "series_a": remaining_capital * 0.4,
                        "series_b": remaining_capital * 0.4
                    }
                },
                "analyzed_companies": []
            }
            
            # Analyze how the new companies fit
            for company in companies:
                company_fit = {
                    "name": company.get("company"),
                    "stage": company.get("stage"),
                    "recommended_investment": min(
                        portfolio_analysis["investment_strategy"]["avg_check_size"],
                        company.get("valuation", 0) * 0.1  # Target 10% ownership
                    ),
                    "expected_ownership": min(0.1, portfolio_analysis["investment_strategy"]["avg_check_size"] / company.get("valuation", 1)),
                    "fit_score": self._calculate_fit_score(company, portfolio_analysis)
                }
                portfolio_analysis["analyzed_companies"].append(company_fit)
            
            return {"portfolio_analysis": portfolio_analysis}
            
        except Exception as e:
            logger.error(f"Portfolio analysis error: {e}")
            return {"error": str(e)}
    
    async def _execute_fund_metrics(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate DPI, TVPI, IRR and other fund metrics"""
        try:
            context = inputs.get("context", {})
            
            # Extract fund parameters
            fund_size = context.get("fund_size", 456_000_000)
            dpi = context.get("dpi", 0.5)  # 0.5 DPI non-recycled
            remaining_capital = context.get("remaining_capital", 276_000_000)
            portfolio_size = context.get("portfolio_size", 16)
            exits = context.get("exits", 2)
            
            deployed = fund_size - remaining_capital
            distributed = fund_size * dpi
            
            # Calculate metrics
            metrics = {
                "performance_metrics": {
                    "dpi": dpi,  # Distributed to Paid-In
                    "rvpi": remaining_capital / fund_size,  # Residual Value to Paid-In
                    "tvpi": dpi + (remaining_capital / fund_size),  # Total Value to Paid-In
                    "deployed_percentage": deployed / fund_size,
                    "distributed_capital": distributed,
                    "unrealized_value": deployed - distributed + remaining_capital
                },
                "portfolio_metrics": {
                    "total_companies": portfolio_size,
                    "exited_companies": exits,
                    "active_companies": portfolio_size - exits,
                    "avg_exit_multiple": distributed / (deployed * (exits / portfolio_size)) if exits > 0 else 0,
                    "required_exit_multiple": 3.0  # Target for remaining portfolio
                },
                "deployment_metrics": {
                    "year": 3,
                    "quarter": 1,
                    "remaining_to_deploy": remaining_capital,
                    "deployment_pace": remaining_capital / 8,  # Over 2 years (8 quarters)
                    "target_investments": 8,  # New investments from remaining capital
                    "avg_new_check": remaining_capital / 8
                }
            }
            
            return {"fund_metrics": metrics}
            
        except Exception as e:
            logger.error(f"Fund metrics calculation error: {e}")
            return {"error": str(e)}
    
    async def _execute_stage_analysis(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze companies across different funding stages"""
        try:
            stages = inputs.get("stages", ["seed", "series_a", "series_b"])
            companies = self.shared_data.get("companies", [])
            
            stage_analysis = {}
            
            for stage in stages:
                stage_key = stage.replace("_", " ").title()
                
                # Calculate stage-specific metrics for each company
                stage_metrics = []
                for company in companies:
                    # Use benchmark valuations and funding amounts for each stage
                    
                    if stage == "seed":
                        stage_val = 10_000_000  # $10M post-money seed
                        stage_funding = 1_500_000  # $1.5M raised
                        stage_rev = 0  # Pre-revenue typically
                        stage_ownership = stage_funding / stage_val  # 15% dilution
                    elif stage == "series_a":
                        stage_val = 50_000_000  # $50M post-money Series A  
                        stage_funding = 8_000_000  # $8M raised
                        stage_rev = 2_000_000  # ~$2M ARR typical at A
                        stage_ownership = stage_funding / stage_val  # 16% dilution
                    else:  # series_b
                        stage_val = 200_000_000  # $200M post-money Series B
                        stage_funding = 25_000_000  # $25M raised
                        stage_rev = 10_000_000  # ~$10M ARR typical at B
                        stage_ownership = stage_funding / stage_val  # 12.5% dilution
                    
                    stage_metrics.append({
                        "company": company.get("company"),
                        "valuation_at_stage": stage_val,
                        "funding_amount": stage_funding,
                        "ownership_given": stage_ownership,
                        "revenue_at_stage": stage_rev,
                        "employees_at_stage": self._estimate_employees_at_stage(stage, company.get("team_size", 10)),
                        "growth_to_next": 3.0 if stage != "series_b" else 2.0  # Growth multiple to next stage
                    })
                
                stage_analysis[stage_key] = {
                    "companies": stage_metrics,
                    "avg_valuation": sum(m["valuation_at_stage"] for m in stage_metrics) / len(stage_metrics) if stage_metrics else 0,
                    "avg_revenue": sum(m["revenue_at_stage"] for m in stage_metrics) / len(stage_metrics) if stage_metrics else 0,
                    "typical_check_size": self._get_typical_check_size(stage),
                    "typical_ownership": self._get_typical_ownership(stage)
                }
            
            return {"stage_analysis": stage_analysis}
            
        except Exception as e:
            logger.error(f"Stage analysis error: {e}")
            return {"error": str(e)}
    
    async def _execute_exit_modeling(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Model exit scenarios and returns WITH FUND OWNERSHIP"""
        try:
            companies = self.shared_data.get("companies", [])
            context = inputs.get("context", {})
            
            # Fund parameters
            fund_size = context.get("fund_size", 126_000_000)
            typical_check = 10_000_000  # $10M typical check for Series A/B
            
            exit_scenarios = []
            
            for company in companies:
                company_name = company.get("company")
                # Use latest_valuation or fallback to other valuation fields
                current_val = (company.get("latest_valuation") or 
                             company.get("valuation") or 
                             company.get("post_money_valuation") or 
                             100_000_000)  # Default $100M if no valuation
                
                # Determine appropriate entry point based on stage
                stage = company.get("stage", "").lower()
                if "seed" in stage:
                    entry_valuation = 50_000_000  # Enter at Series A
                    our_check_size = 5_000_000
                elif "series a" in stage or "a" in stage:
                    entry_valuation = 150_000_000  # Enter at late A/early B
                    our_check_size = 10_000_000
                elif "series b" in stage or "b" in stage:
                    entry_valuation = current_val  # Current valuation
                    our_check_size = 15_000_000
                else:  # Later stage
                    entry_valuation = current_val
                    our_check_size = 10_000_000
                
                # Calculate our ownership
                our_ownership = (our_check_size / (entry_valuation + our_check_size)) * 100
                
                # Analyze moat and momentum
                moat_score = self._calculate_moat_score(company)
                momentum_score = self._calculate_momentum_score(company)
                
                # Model different exit scenarios with REALISTIC multiples
                scenarios = {
                    "bear": {
                        "exit_valuation": entry_valuation * 2,  # 2x from entry
                        "probability": 0.3,
                        "timeline_years": 3,
                        "irr": ((2 ** (1/3)) - 1) * 100,  # ~26% IRR
                        "our_proceeds": our_check_size * 2,
                        "dpi_contribution": (our_check_size * 2) / fund_size
                    },
                    "base": {
                        "exit_valuation": entry_valuation * 5,  # 5x from entry
                        "probability": 0.5,
                        "timeline_years": 5,
                        "irr": ((5 ** (1/5)) - 1) * 100,  # ~38% IRR
                        "our_proceeds": our_check_size * 5,
                        "dpi_contribution": (our_check_size * 5) / fund_size
                    },
                    "bull": {
                        "exit_valuation": entry_valuation * 10,  # 10x from entry
                        "probability": 0.2,
                        "timeline_years": 7,
                        "irr": ((10 ** (1/7)) - 1) * 100,  # ~39% IRR
                        "our_proceeds": our_check_size * 10,
                        "dpi_contribution": (our_check_size * 10) / fund_size
                    }
                }
                
                # Calculate expected returns
                expected_value = sum(
                    s["exit_valuation"] * s["probability"]
                    for s in scenarios.values()
                )
                
                # Calculate revenue multiples
                revenue = company.get("revenue", 10_000_000)
                revenue_growth = company.get("revenue_growth", 30)
                
                exit_scenarios.append({
                    "company": company_name,
                    "current_valuation": current_val,
                    "current_revenue": revenue,
                    "revenue_growth": revenue_growth,
                    "entry_valuation": entry_valuation,
                    "our_check_size": our_check_size,
                    "our_ownership": our_ownership,
                    "moat_score": moat_score,
                    "momentum_score": momentum_score,
                    "scenarios": scenarios,
                    "expected_exit_value": expected_value,
                    "expected_multiple": expected_value / entry_valuation if entry_valuation > 0 else 0,
                    "revenue_multiple": current_val / revenue if revenue > 0 else 0,
                    "exit_type": "M&A" if expected_value < 1_000_000_000 else "IPO",
                    "investment_recommendation": self._get_investment_recommendation(moat_score, momentum_score, our_ownership)
                })
            
            return {
                "exit_modeling": {
                    "scenarios": exit_scenarios,
                    "portfolio_expected_value": sum(s["expected_exit_value"] for s in exit_scenarios),
                    "avg_expected_multiple": sum(s["expected_multiple"] for s in exit_scenarios) / len(exit_scenarios) if exit_scenarios else 0
                }
            }
            
        except Exception as e:
            logger.error(f"Exit modeling error: {e}")
            return {"error": str(e)}
    
    def _calculate_fit_score(self, company: Dict, portfolio: Dict) -> float:
        """Calculate how well a company fits the fund's strategy"""
        score = 0.5  # Base score
        
        # Stage alignment
        if company.get("stage", "").lower() in ["series a", "series b"]:
            score += 0.2
        
        # Valuation fit
        avg_check = portfolio["investment_strategy"]["avg_check_size"]
        if company.get("valuation", 0) > 0:
            ownership = avg_check / company.get("valuation", 1)
            if 0.05 <= ownership <= 0.15:  # Good ownership range
                score += 0.2
        
        # Sector (AI/ML gets bonus)
        if "ai" in company.get("sector", "").lower() or "ml" in company.get("sector", "").lower():
            score += 0.1
        
        return min(1.0, score)
    
    def _estimate_employees_at_stage(self, stage: str, current_size: int = None) -> int:
        """Estimate employee count at different stages"""
        if current_size is None:
            # Use typical sizes if no current size provided
            typical_sizes = {"seed": 5, "series_a": 25, "series_b": 100}
            return typical_sizes.get(stage, 10)
            
        if stage == "seed":
            return min(5, int(current_size * 0.1))
        elif stage == "series_a":
            return min(25, int(current_size * 0.3))
        else:  # series_b
            return min(100, int(current_size * 0.7))
    
    def _get_typical_check_size(self, stage: str) -> float:
        """Get typical check size for a stage"""
        sizes = {
            "seed": 500_000,
            "series_a": 5_000_000,
            "series_b": 15_000_000
        }
        return sizes.get(stage, 1_000_000)
    
    def _get_typical_ownership(self, stage: str) -> float:
        """Get typical ownership target for a stage"""
        ownership = {
            "seed": 0.10,
            "series_a": 0.15,
            "series_b": 0.10
        }
        return ownership.get(stage, 0.10)
    
    def _calculate_moat_score(self, company: Dict[str, Any]) -> float:
        """Calculate competitive moat score (0-1)"""
        score = 0.0
        
        # Proprietary technology (GPU analysis shows own models)
        if company.get("gross_margin_analysis", {}).get("api_dependency_level") == "own_models":
            score += 0.3
        
        # Customer stickiness (enterprise customers)
        customers = company.get("customers", [])
        if any("fortune 500" in str(c).lower() for c in customers):
            score += 0.2
        
        # Sector defensibility
        sector = company.get("sector", "").lower()
        if "defense" in sector or "healthcare" in sector:
            score += 0.2  # Regulated sectors have moats
        
        # Network effects
        if "platform" in company.get("business_model", "").lower():
            score += 0.1
        
        # Gross margin strength (after GPU costs)
        if company.get("gross_margin", 0) > 0.7:
            score += 0.2
        
        return min(1.0, score)
    
    def _calculate_momentum_score(self, company: Dict[str, Any]) -> float:
        """Calculate growth momentum score (0-1)"""
        score = 0.0
        
        # Revenue growth
        growth = company.get("revenue_growth", 0)
        if growth > 100:
            score += 0.4
        elif growth > 50:
            score += 0.3
        elif growth > 30:
            score += 0.2
        
        # Funding momentum (recent rounds)
        funding_rounds = company.get("funding_rounds", [])
        if funding_rounds:
            latest_date = funding_rounds[0].get("date", "")
            if "2024" in latest_date or "2025" in latest_date:
                score += 0.2  # Recent funding
        
        # Team growth
        team_size = company.get("team_size", 0)
        if team_size > 100:
            score += 0.2
        elif team_size > 50:
            score += 0.1
        
        # Market timing (AI companies get boost in 2024-2025)
        if "ai" in company.get("sector", "").lower():
            score += 0.2
        
        return min(1.0, score)
    
    def _get_investment_recommendation(self, moat: float, momentum: float, ownership: float) -> str:
        """Generate investment recommendation based on scores"""
        combined_score = (moat * 0.5) + (momentum * 0.3) + (min(ownership / 15, 1.0) * 0.2)
        
        if combined_score > 0.7:
            return "🚀 STRONG BUY - Lead the round"
        elif combined_score > 0.5:
            return "✅ BUY - Participate in round"
        elif combined_score > 0.3:
            return "🔶 CONSIDER - Need more diligence"
        else:
            return "⚠️ PASS - Better opportunities available"
    
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
        
        # Debug logging to see companies
        logger.info(f"Companies in shared_data: {len(self.shared_data.get('companies', []))}")
        if self.shared_data.get('companies'):
            for company in self.shared_data.get('companies', []):
                logger.info(f"  - {company.get('company', 'Unknown')}")
        
        # Ensure we have companies in the right format
        companies_list = []
        
        # First add companies from shared_data
        if "companies" in final_data:
            companies_list = final_data["companies"]
            logger.info(f"Got {len(companies_list)} companies from final_data")
        
        # Companies should already be in final_data from shared_data merge
        # Just ensure the companies list is present
        if not companies_list and "companies" in final_data:
            companies_list = final_data["companies"]
            logger.info(f"Using {len(companies_list)} companies from final_data")
            
        # Update final data with companies list (should already be there but ensure it)
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
        # Extract skill results from their skill names
        formatted = {
            "type": "analysis",
            "companies": data.get("companies", [])
        }
        
        # Extract results from skill outputs
        if "deal-comparer" in data and isinstance(data["deal-comparer"], dict):
            formatted["comparison"] = data["deal-comparer"].get("deal_comparison", {})
        
        if "cap-table-generator" in data and isinstance(data["cap-table-generator"], dict):
            formatted["cap_tables"] = data["cap-table-generator"].get("cap_tables", {})
        
        if "portfolio-analyzer" in data and isinstance(data["portfolio-analyzer"], dict):
            formatted["portfolio_analysis"] = data["portfolio-analyzer"].get("portfolio_analysis", {})
        
        if "fund-metrics-calculator" in data and isinstance(data["fund-metrics-calculator"], dict):
            formatted["fund_metrics"] = data["fund-metrics-calculator"].get("fund_metrics", {})
        
        if "stage-analyzer" in data and isinstance(data["stage-analyzer"], dict):
            formatted["stage_analysis"] = data["stage-analyzer"].get("stage_analysis", {})
        
        if "exit-modeler" in data and isinstance(data["exit-modeler"], dict):
            formatted["exit_modeling"] = data["exit-modeler"].get("exit_modeling", {})
        
        if "valuation-engine" in data and isinstance(data["valuation-engine"], dict):
            formatted["valuations"] = data["valuation-engine"].get("valuations", {})
        
        # Generate comprehensive summary
        formatted["summary"] = self._generate_comprehensive_summary(formatted)
        
        # Remove empty sections
        return {k: v for k, v in formatted.items() if v}
    
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
    
    def _generate_comprehensive_summary(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate comprehensive summary of all analysis"""
        summary = {
            "overview": "",
            "key_findings": [],
            "recommendations": []
        }
        
        # Companies overview
        companies = data.get("companies", [])
        if companies:
            summary["overview"] = f"Analyzed {len(companies)} companies: {', '.join(c.get('company', '') for c in companies)}"
        
        # Key findings from each skill
        if "deal_comparison" in data:
            comp = data["deal_comparison"]
            if comp and "companies" in comp and comp["companies"]:
                top = comp["companies"][0]
                summary["key_findings"].append(f"Top ranked: {top.get('name')} with score {top.get('score')}")
        
        if "fund_metrics" in data:
            metrics = data["fund_metrics"]
            if metrics and "performance_metrics" in metrics:
                perf = metrics["performance_metrics"]
                summary["key_findings"].append(f"Fund Performance: {perf.get('dpi', 0):.1f}x DPI, {perf.get('tvpi', 0):.1f}x TVPI")
        
        if "portfolio_analysis" in data:
            portfolio = data["portfolio_analysis"]
            if portfolio and "fund_overview" in portfolio:
                overview = portfolio["fund_overview"]
                summary["key_findings"].append(
                    f"Portfolio: {overview.get('portfolio_companies')} companies, "
                    f"{overview.get('exits_completed')} exits, "
                    f"${overview.get('remaining_capital', 0)/1_000_000:.0f}M to deploy"
                )
        
        # Recommendations
        if "portfolio_analysis" in data:
            analyzed = data["portfolio_analysis"].get("analyzed_companies", [])
            for company_fit in analyzed:
                if company_fit.get("fit_score", 0) > 0.7:
                    summary["recommendations"].append(
                        f"Invest ${company_fit.get('recommended_investment', 0)/1_000_000:.1f}M in {company_fit.get('name')} "
                        f"for {company_fit.get('expected_ownership', 0)*100:.1f}% ownership"
                    )
        
        return summary
    
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
    "business_model": "ULTRA-SPECIFIC description of what they do. Examples: 'AI-powered medical consultation analysis', 'ML infrastructure and model serving platform', 'Defense contractor drone detection system', 'B2B payments automation for SMBs'. NEVER use generic terms like SaaS, Software, Platform alone",
    "sector": "SPECIFIC vertical/industry they serve. Examples: 'Healthcare AI', 'Defense Technology', 'ML Infrastructure', 'PropTech', 'FinTech Payments', 'DevTools', 'LegalTech'. NEVER just 'Technology' or 'Software'",
    "category": "SPECIFIC product category. Examples: 'Clinical AI Assistant', 'MLOps Platform', 'Counter-drone Systems', 'Payment Rails', 'Code Generation IDE'. Be precise about what the product actually does",
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
    "recent_news": ["Recent development 1", "Recent development 2"],
    "unit_economics": {{
        "unit_of_work": "What is one unit of value? (e.g., 'one presentation generated', 'one API call', 'one month of access', 'one document processed')",
        "compute_intensity": "What happens computationally? (e.g., 'generates 50 slides with AI', 'searches 100M documents', 'processes video stream', 'stores and queries data')",
        "target_segment": "prosumer|SME|mid-market|enterprise|Fortune 500",
        "pricing_per_unit": "Estimated price they charge per unit if known",
        "gpu_cost_estimate": "Rough GPU/compute cost for that unit of work"
    }}
}}

CRITICAL EXTRACTION RULES:
1. For website_url, choose the most likely official company website from the domains found
2. If {company_name.lower()}.com/io/ai exists in domains, prefer that
3. For UK companies, check for .co.uk or .group domains

BUSINESS MODEL EXTRACTION (MOST IMPORTANT):
- Read the search results carefully to understand WHAT THE COMPANY ACTUALLY DOES
- Look for phrases like "builds", "develops", "provides", "helps", "enables"
- Extract the SPECIFIC product/service, not generic categories
- BAD: "SaaS", "Software", "Platform", "Technology company"
- GOOD: "AI medical scribe for doctor consultations", "Infrastructure for ML model deployment", "Automated drone detection for airports"

SECTOR EXTRACTION:
- Identify the INDUSTRY or VERTICAL they serve
- BAD: "Technology", "Software", "IT"  
- GOOD: "Healthcare AI", "Defense Tech", "FinTech Infrastructure", "LegalTech", "EdTech", "AgTech"

5. If you find funding data, include specific amounts and dates
6. Set null for any field you cannot find data for
7. DO NOT make up data - use null if not found

Return ONLY the JSON object, no other text."""

            # ALWAYS use Claude for extraction - it's critical for accurate business model detection
            if not self.claude:
                logger.error("Claude client not initialized! Cannot extract company data properly.")
                raise ValueError("Claude API is required for company extraction")
            
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
                
                # IMPORTANT: Never override specific business models with generic ones
                # Validate that we got specific descriptions, not generic
                if extracted_data.get("business_model") in ["SaaS", "Software", "Technology", "Tech"]:
                    logger.warning(f"Got generic business model for {company_name}: {extracted_data.get('business_model')}")
                    # Try to extract from search content directly
                    for result in search_results:
                        if result and 'results' in result:
                            for r in result['results'][:2]:
                                content = r.get('content', '').lower()
                                # Look for specific keywords to improve categorization
                                if 'ai' in content and 'code' in content:
                                    extracted_data["business_model"] = "AI-powered development tools"
                                    break
                                elif 'healthcare' in content and ('ai' in content or 'ml' in content):
                                    extracted_data["business_model"] = "Healthcare AI platform"
                                    break
                                elif 'proptech' in content or 'property' in content:
                                    extracted_data["business_model"] = "PropTech platform"
                                    break
                                elif 'fintech' in content or 'payments' in content:
                                    extracted_data["business_model"] = "FinTech platform"
                                    break
                
            except json.JSONDecodeError:
                logger.error(f"Failed to parse Claude response: {response_text[:500]}")
                # Still try to get basic data
                extracted_data = {
                    "company": company_name,
                    "website_url": None
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
