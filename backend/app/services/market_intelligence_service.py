"""
MarketIntelligenceService - Geographic and sector-based company discovery
Handles open-ended queries like "find hot defense companies in Europe for Series A"
"""

import asyncio
import aiohttp
import logging
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import json
import numpy as np

from app.core.config import settings

logger = logging.getLogger(__name__)


class Geography(str, Enum):
    """Supported geographies for company search"""
    NORTH_AMERICA = "north_america"
    EUROPE = "europe" 
    EMEA = "emea"
    ASIA_PACIFIC = "asia_pacific"
    UK = "uk"
    GERMANY = "germany"
    FRANCE = "france"
    NORDICS = "nordics"
    ISRAEL = "israel"
    INDIA = "india"
    CHINA = "china"
    SOUTHEAST_ASIA = "southeast_asia"


class MarketTiming(str, Enum):
    """Market timing indicators"""
    HOT = "hot"           # High momentum, trending up
    COOLING = "cooling"   # Recent peak, starting decline
    COLD = "cold"         # Low activity, potential opportunity
    EMERGING = "emerging" # Early momentum, growing interest


@dataclass
class CompanyIntelligence:
    """Structured company intelligence data"""
    name: str
    sector: str
    geography: str
    stage: str
    last_funding_date: Optional[datetime] = None
    last_funding_amount: Optional[float] = None
    estimated_valuation: Optional[float] = None
    employee_count: Optional[int] = None
    growth_momentum: Optional[float] = None  # 0-100 score
    investment_readiness: Optional[float] = None  # 0-100 score
    market_timing_score: Optional[float] = None  # 0-100 score
    key_metrics: Dict[str, Any] = field(default_factory=dict)
    competitive_position: Optional[str] = None
    investors: List[str] = field(default_factory=list)
    news_sentiment: Optional[float] = None  # -100 to 100
    
    
@dataclass 
class MarketLandscape:
    """Market landscape analysis"""
    sector: str
    geography: str
    total_companies: int
    by_stage: Dict[str, int] = field(default_factory=dict)
    avg_valuation_by_stage: Dict[str, float] = field(default_factory=dict)
    funding_velocity: float = 0.0  # Deals per month
    market_timing: MarketTiming = MarketTiming.COLD
    key_trends: List[str] = field(default_factory=list)
    top_investors: List[str] = field(default_factory=list)
    competitive_intensity: float = 0.0  # 0-100 score


class MarketIntelligenceService:
    """
    Advanced market intelligence for geographic and sector-based company discovery
    """
    
    def __init__(self):
        self.tavily_api_key = settings.TAVILY_API_KEY
        self.session = None
        
        # Geography mapping for search terms
        self.geography_search_terms = {
            Geography.EUROPE: ["Europe", "European", "EU", "EMEA"],
            Geography.UK: ["UK", "United Kingdom", "British", "England", "London"],
            Geography.GERMANY: ["Germany", "German", "Berlin", "Munich"],
            Geography.FRANCE: ["France", "French", "Paris"],
            Geography.NORDICS: ["Nordic", "Nordics", "Scandinavia", "Sweden", "Denmark", "Norway", "Finland"],
            Geography.ISRAEL: ["Israel", "Israeli", "Tel Aviv"],
            Geography.INDIA: ["India", "Indian", "Bangalore", "Mumbai", "Delhi"],
            Geography.CHINA: ["China", "Chinese", "Beijing", "Shanghai", "Shenzhen"],
            Geography.SOUTHEAST_ASIA: ["Singapore", "Southeast Asia", "Thailand", "Vietnam", "Malaysia"]
        }
        
        # Sector keywords for enhanced search
        self.sector_keywords = {
            "defense": ["defense", "defence", "military", "cybersecurity", "aerospace", "surveillance"],
            "fintech": ["fintech", "financial", "payments", "banking", "lending", "insurance"],
            "healthtech": ["health", "medical", "biotech", "pharma", "healthcare", "digital health"],
            "climate": ["climate", "cleantech", "sustainability", "renewable", "carbon", "green tech"],
            "ai": ["AI", "artificial intelligence", "machine learning", "ML", "deep learning"],
            "saas": ["SaaS", "software", "enterprise", "B2B", "platform"],
            "consumer": ["consumer", "B2C", "marketplace", "social", "gaming"],
            "deeptech": ["deep tech", "quantum", "robotics", "semiconductors", "hardware"]
        }

    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()

    async def find_companies_by_geography_sector(
        self,
        geography: str,
        sector: str,
        stage: Optional[str] = None,
        limit: int = 20
    ) -> List[CompanyIntelligence]:
        """
        Find companies matching geographic and sector criteria
        
        Args:
            geography: Target geography (e.g., "europe", "uk")  
            sector: Target sector (e.g., "defense", "fintech")
            stage: Optional funding stage filter
            limit: Max companies to return
            
        Returns:
            List of CompanyIntelligence objects with detailed data
        """
        try:
            # Build search queries for parallel execution
            search_queries = self._build_geography_sector_queries(geography, sector, stage)
            
            # Execute parallel searches
            search_tasks = []
            if not self.session:
                self.session = aiohttp.ClientSession()
                
            for query in search_queries:
                search_tasks.append(self._execute_tavily_search(query))
                
            search_results = await asyncio.gather(*search_tasks, return_exceptions=True)
            
            # Process and deduplicate results
            companies = self._process_search_results(search_results, geography, sector, stage)
            
            # Score and rank companies
            scored_companies = await self._score_companies(companies, geography, sector)
            
            # Return top companies sorted by investment readiness
            return sorted(scored_companies, key=lambda x: x.investment_readiness or 0, reverse=True)[:limit]
            
        except Exception as e:
            logger.error(f"Error in find_companies_by_geography_sector: {str(e)}")
            return []

    async def analyze_market_timing(
        self,
        sector: str, 
        geography: Optional[str] = None,
        indicators: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Analyze market timing for investment decisions
        
        Args:
            sector: Target sector
            geography: Optional geographic filter
            indicators: Custom timing indicators to analyze
            
        Returns:
            Market timing analysis with momentum scores and recommendations
        """
        try:
            # Build timing analysis queries
            timing_queries = self._build_timing_analysis_queries(sector, geography, indicators)
            
            # Execute searches for market signals
            if not self.session:
                self.session = aiohttp.ClientSession()
                
            timing_tasks = [self._execute_tavily_search(query) for query in timing_queries]
            timing_results = await asyncio.gather(*timing_tasks, return_exceptions=True)
            
            # Analyze timing signals
            timing_analysis = self._analyze_timing_signals(timing_results, sector, geography)
            
            return timing_analysis
            
        except Exception as e:
            logger.error(f"Error in analyze_market_timing: {str(e)}")
            return {"market_timing": MarketTiming.COLD, "confidence": 0.0}

    async def score_investment_readiness(
        self,
        companies: List[CompanyIntelligence],
        criteria: Optional[Dict[str, Any]] = None
    ) -> List[CompanyIntelligence]:
        """
        Score companies for investment readiness based on multiple factors
        
        Args:
            companies: List of companies to score
            criteria: Optional custom scoring criteria
            
        Returns:
            Companies with updated investment_readiness scores
        """
        default_criteria = {
            "funding_recency_weight": 0.25,      # Recent funding activity
            "growth_momentum_weight": 0.30,      # Growth trajectory  
            "market_position_weight": 0.20,      # Competitive position
            "team_quality_weight": 0.15,         # Team/founder quality
            "market_timing_weight": 0.10         # Market conditions
        }
        
        scoring_criteria = criteria or default_criteria
        
        for company in companies:
            company.investment_readiness = self._calculate_investment_readiness_score(
                company, scoring_criteria
            )
            
        return companies

    async def generate_sector_landscape(
        self,
        sector: str,
        geography: Optional[str] = None
    ) -> MarketLandscape:
        """
        Generate comprehensive sector landscape analysis
        
        Args:
            sector: Target sector for analysis
            geography: Optional geographic filter
            
        Returns:
            MarketLandscape with competitive analysis and trends
        """
        try:
            # Find companies in sector/geography
            companies = await self.find_companies_by_geography_sector(
                geography or "global", sector, limit=50
            )
            
            # Analyze market timing
            timing_analysis = await self.analyze_market_timing(sector, geography)
            
            # Build landscape analysis
            landscape = MarketLandscape(
                sector=sector,
                geography=geography or "global", 
                total_companies=len(companies)
            )
            
            # Calculate stage distribution
            stages = {}
            valuations_by_stage = {}
            
            for company in companies:
                stage = company.stage or "unknown"
                stages[stage] = stages.get(stage, 0) + 1
                
                if company.estimated_valuation:
                    if stage not in valuations_by_stage:
                        valuations_by_stage[stage] = []
                    valuations_by_stage[stage].append(company.estimated_valuation)
            
            landscape.by_stage = stages
            landscape.avg_valuation_by_stage = {
                stage: np.mean(vals) for stage, vals in valuations_by_stage.items()
            }
            
            # Set market timing from analysis
            landscape.market_timing = MarketTiming(timing_analysis.get("market_timing", "cold"))
            landscape.key_trends = timing_analysis.get("key_trends", [])
            
            # Calculate competitive intensity
            landscape.competitive_intensity = min(100.0, len(companies) * 2)  # Simple heuristic
            
            return landscape
            
        except Exception as e:
            logger.error(f"Error in generate_sector_landscape: {str(e)}")
            return MarketLandscape(sector=sector, geography=geography or "global", total_companies=0)

    # Helper methods

    def _build_geography_sector_queries(
        self,
        geography: str,
        sector: str,
        stage: Optional[str] = None
    ) -> List[str]:
        """Build optimized search queries for geography + sector combination"""
        
        geo_terms = self.geography_search_terms.get(Geography(geography.lower()), [geography])
        sector_terms = self.sector_keywords.get(sector.lower(), [sector])
        
        queries = []
        
        # Primary query: geography + sector + stage
        for geo_term in geo_terms[:2]:  # Limit to top 2 geo terms
            for sector_term in sector_terms[:2]:  # Limit to top 2 sector terms
                base_query = f"{geo_term} {sector_term} startup"
                
                if stage:
                    base_query += f" {stage} funding"
                
                queries.append(base_query)
                
                # Add variant with "companies" 
                queries.append(base_query.replace("startup", "companies"))
        
        return queries[:6]  # Limit total queries

    async def _execute_tavily_search(self, query: str) -> Dict[str, Any]:
        """Execute Tavily search with error handling"""
        try:
            tavily_url = "https://api.tavily.com/search"
            
            payload = {
                "api_key": self.tavily_api_key,
                "query": query,
                "search_depth": "advanced",
                "max_results": 10,
                "include_domains": [
                    "crunchbase.com",
                    "pitchbook.com", 
                    "dealroom.co",
                    "techcrunch.com",
                    "venturebeat.com"
                ]
            }
            
            async with self.session.post(tavily_url, json=payload) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    logger.warning(f"Tavily search failed: {response.status}")
                    return {"results": []}
                    
        except Exception as e:
            logger.error(f"Tavily search error: {str(e)}")
            return {"results": []}

    def _process_search_results(
        self,
        search_results: List[Dict[str, Any]],
        geography: str,
        sector: str,
        stage: Optional[str]
    ) -> List[CompanyIntelligence]:
        """Process and deduplicate search results into CompanyIntelligence objects"""
        
        companies = {}  # Dedupe by name
        
        for result_set in search_results:
            if isinstance(result_set, Exception):
                continue
                
            results = result_set.get("results", [])
            
            for result in results:
                # Extract company information from result
                company_data = self._extract_company_from_result(result, geography, sector, stage)
                
                if company_data and company_data.name:
                    # Deduplicate by normalized name
                    normalized_name = company_data.name.lower().strip()
                    
                    if normalized_name not in companies:
                        companies[normalized_name] = company_data
                    else:
                        # Merge data from multiple sources
                        companies[normalized_name] = self._merge_company_data(
                            companies[normalized_name], company_data
                        )
        
        return list(companies.values())

    def _extract_company_from_result(
        self,
        result: Dict[str, Any],
        geography: str,
        sector: str,
        stage: Optional[str]
    ) -> Optional[CompanyIntelligence]:
        """Extract company data from a single search result"""
        try:
            title = result.get("title", "")
            content = result.get("content", "")
            url = result.get("url", "")
            
            # Basic company name extraction
            company_name = self._extract_company_name(title, content)
            if not company_name:
                return None
                
            # Create company intelligence object
            company = CompanyIntelligence(
                name=company_name,
                sector=sector,
                geography=geography,
                stage=stage or self._extract_stage(content)
            )
            
            # Extract additional fields
            company.estimated_valuation = self._extract_valuation(content)
            company.last_funding_amount = self._extract_funding_amount(content)
            company.employee_count = self._extract_employee_count(content)
            company.investors = self._extract_investors(content)
            
            return company
            
        except Exception as e:
            logger.error(f"Error extracting company from result: {str(e)}")
            return None

    def _extract_company_name(self, title: str, content: str) -> Optional[str]:
        """Extract company name from title/content"""
        # Simple heuristic - look for company patterns
        import re
        
        # Look for "Company raises", "Company secures", etc.
        patterns = [
            r'^([A-Z][a-zA-Z0-9\s]+?)\s+(?:raises|secures|announces|closes)',
            r'([A-Z][a-zA-Z0-9\s]+?)\s+(?:startup|company)',
            r'^([A-Z][a-zA-Z0-9\s]{2,30}?)(?:\s|:)'
        ]
        
        text = title + " " + content[:200]  # First 200 chars
        
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                name = match.group(1).strip()
                if len(name) > 2 and len(name) < 50:  # Reasonable name length
                    return name
        
        return None

    def _extract_stage(self, content: str) -> Optional[str]:
        """Extract funding stage from content"""
        import re
        
        stages = ["Pre-seed", "Seed", "Series A", "Series B", "Series C", "Series D", "Series E"]
        content_lower = content.lower()
        
        for stage in stages:
            if stage.lower() in content_lower:
                return stage
        
        return None

    def _extract_valuation(self, content: str) -> Optional[float]:
        """Extract valuation from content"""
        import re
        
        # Look for valuation patterns
        patterns = [
            r'valued at \$?([\d.,]+)\s?([mb]illion)?',
            r'valuation of \$?([\d.,]+)\s?([mb]illion)?',
            r'\$?([\d.,]+)\s?([mb]illion) valuation'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, content.lower())
            if match:
                amount = match.group(1).replace(",", "")
                multiplier = match.group(2) if len(match.groups()) > 1 else None
                
                try:
                    value = float(amount)
                    if multiplier == "billion":
                        value *= 1_000_000_000
                    elif multiplier == "million":
                        value *= 1_000_000
                    
                    return value
                except:
                    continue
        
        return None

    def _extract_funding_amount(self, content: str) -> Optional[float]:
        """Extract funding amount from content"""
        import re
        
        patterns = [
            r'raised \$?([\d.,]+)\s?([mb]illion)?',
            r'funding of \$?([\d.,]+)\s?([mb]illion)?',
            r'\$?([\d.,]+)\s?([mb]illion) funding'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, content.lower())
            if match:
                amount = match.group(1).replace(",", "")
                multiplier = match.group(2) if len(match.groups()) > 1 else None
                
                try:
                    value = float(amount)
                    if multiplier == "billion":
                        value *= 1_000_000_000
                    elif multiplier == "million":
                        value *= 1_000_000
                    
                    return value
                except:
                    continue
        
        return None

    def _extract_employee_count(self, content: str) -> Optional[int]:
        """Extract employee count from content"""
        import re
        
        patterns = [
            r'(\d+)\s+employees',
            r'team of (\d+)',
            r'(\d+)\s+people'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, content.lower())
            if match:
                try:
                    return int(match.group(1))
                except:
                    continue
        
        return None

    def _extract_investors(self, content: str) -> List[str]:
        """Extract investor names from content"""
        # Simple implementation - could be enhanced
        investors = []
        
        # Look for common investor patterns
        investor_keywords = [
            "Sequoia", "Andreessen Horowitz", "Accel", "Kleiner Perkins",
            "Benchmark", "Index Ventures", "Balderton", "Atomico"
        ]
        
        content_lower = content.lower()
        for investor in investor_keywords:
            if investor.lower() in content_lower:
                investors.append(investor)
        
        return investors

    def _merge_company_data(
        self,
        existing: CompanyIntelligence,
        new: CompanyIntelligence  
    ) -> CompanyIntelligence:
        """Merge company data from multiple sources"""
        
        # Take non-null values from either source
        existing.estimated_valuation = existing.estimated_valuation or new.estimated_valuation
        existing.last_funding_amount = existing.last_funding_amount or new.last_funding_amount
        existing.employee_count = existing.employee_count or new.employee_count
        existing.stage = existing.stage or new.stage
        
        # Merge investor lists
        existing.investors = list(set(existing.investors + new.investors))
        
        return existing

    async def _score_companies(
        self,
        companies: List[CompanyIntelligence],
        geography: str,
        sector: str
    ) -> List[CompanyIntelligence]:
        """Score companies for investment readiness"""
        
        for company in companies:
            # Calculate growth momentum (0-100)
            company.growth_momentum = self._calculate_growth_momentum(company)
            
            # Calculate market timing score (0-100)
            company.market_timing_score = self._calculate_market_timing_score(company, sector)
            
            # Calculate overall investment readiness (0-100)
            company.investment_readiness = self._calculate_investment_readiness_score(
                company, {}
            )
        
        return companies

    def _calculate_growth_momentum(self, company: CompanyIntelligence) -> float:
        """Calculate growth momentum score (0-100)"""
        score = 50.0  # Base score
        
        # Recent funding boosts score
        if company.last_funding_date:
            days_since_funding = (datetime.now() - company.last_funding_date).days
            if days_since_funding < 180:  # Less than 6 months
                score += 25
            elif days_since_funding < 365:  # Less than 1 year
                score += 15
        
        # Large funding amount boosts score
        if company.last_funding_amount:
            if company.last_funding_amount > 10_000_000:  # >$10M
                score += 20
            elif company.last_funding_amount > 1_000_000:  # >$1M
                score += 10
        
        # Team size indicates growth
        if company.employee_count:
            if company.employee_count > 100:
                score += 15
            elif company.employee_count > 50:
                score += 10
            elif company.employee_count > 10:
                score += 5
        
        return min(100.0, score)

    def _calculate_market_timing_score(self, company: CompanyIntelligence, sector: str) -> float:
        """Calculate market timing score (0-100)"""
        # Base score varies by sector "hotness"
        sector_scores = {
            "ai": 90,
            "fintech": 70,
            "defense": 80,
            "climate": 85,
            "healthtech": 75,
            "saas": 60,
            "consumer": 45,
            "deeptech": 70
        }
        
        return sector_scores.get(sector.lower(), 50.0)

    def _calculate_investment_readiness_score(
        self,
        company: CompanyIntelligence,
        criteria: Dict[str, Any]
    ) -> float:
        """Calculate overall investment readiness score (0-100)"""
        
        # Default weights
        weights = {
            "funding_recency_weight": 0.25,
            "growth_momentum_weight": 0.30,
            "market_position_weight": 0.20,
            "team_quality_weight": 0.15,
            "market_timing_weight": 0.10
        }
        weights.update(criteria)
        
        # Component scores (0-100)
        funding_recency = 50.0
        if company.last_funding_date:
            days_ago = (datetime.now() - company.last_funding_date).days
            funding_recency = max(0, 100 - (days_ago / 10))  # Decays over time
        
        growth_momentum = company.growth_momentum or 50.0
        market_timing = company.market_timing_score or 50.0
        
        # Market position (based on funding amount as proxy)
        market_position = 50.0
        if company.last_funding_amount:
            if company.last_funding_amount > 50_000_000:
                market_position = 90
            elif company.last_funding_amount > 10_000_000:
                market_position = 80
            elif company.last_funding_amount > 1_000_000:
                market_position = 70
        
        # Team quality (based on employee count and investor quality)
        team_quality = 50.0
        if company.employee_count:
            team_quality += min(30, company.employee_count)  # More employees = stronger team
        if company.investors:
            top_tier_investors = ["Sequoia", "Andreessen Horowitz", "Accel", "Benchmark"]
            if any(inv in company.investors for inv in top_tier_investors):
                team_quality += 20
        
        # Weighted average
        score = (
            funding_recency * weights["funding_recency_weight"] +
            growth_momentum * weights["growth_momentum_weight"] + 
            market_position * weights["market_position_weight"] +
            team_quality * weights["team_quality_weight"] +
            market_timing * weights["market_timing_weight"]
        )
        
        return min(100.0, score)

    def _build_timing_analysis_queries(
        self,
        sector: str,
        geography: Optional[str],
        indicators: Optional[List[str]]
    ) -> List[str]:
        """Build queries for market timing analysis"""
        
        queries = []
        
        # Trend queries
        queries.append(f"{sector} market trends 2024 investment")
        queries.append(f"{sector} funding rounds recent months")
        
        if geography:
            queries.append(f"{geography} {sector} investment activity 2024")
            
        # Indicator-specific queries
        if indicators:
            for indicator in indicators:
                queries.append(f"{sector} {indicator} investment timing")
        
        return queries

    def _analyze_timing_signals(
        self,
        timing_results: List[Dict[str, Any]], 
        sector: str,
        geography: Optional[str]
    ) -> Dict[str, Any]:
        """Analyze timing signals to determine market timing"""
        
        # Simple implementation - could be enhanced with ML
        hot_keywords = ["surge", "boom", "hot", "trending", "record", "peak"]
        cooling_keywords = ["decline", "cooling", "downturn", "slowing", "cautious"]
        
        hot_score = 0
        cooling_score = 0
        
        for result_set in timing_results:
            if isinstance(result_set, Exception):
                continue
                
            results = result_set.get("results", [])
            
            for result in results:
                content = (result.get("title", "") + " " + result.get("content", "")).lower()
                
                for keyword in hot_keywords:
                    hot_score += content.count(keyword)
                    
                for keyword in cooling_keywords:
                    cooling_score += content.count(keyword)
        
        # Determine timing
        if hot_score > cooling_score * 2:
            market_timing = MarketTiming.HOT
        elif cooling_score > hot_score:
            market_timing = MarketTiming.COOLING
        elif hot_score > 0:
            market_timing = MarketTiming.EMERGING
        else:
            market_timing = MarketTiming.COLD
        
        return {
            "market_timing": market_timing,
            "confidence": min(100, (hot_score + cooling_score) * 10),
            "hot_score": hot_score,
            "cooling_score": cooling_score,
            "key_trends": [
                f"{sector} showing {'high' if hot_score > 5 else 'moderate'} momentum",
                f"Investment activity {'increasing' if hot_score > cooling_score else 'stable'}"
            ]
        }