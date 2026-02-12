"""
World Model Builder Service
Builds comprehensive world models that capture full business context:
- Qualitative factors (market sentiment, team quality, competitive position)
- Quantitative factors (financial metrics, growth rates)
- Relationships between entities (companies, markets, competitors)
- Temporal dynamics (how factors change over time)
"""

import logging
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import json

from app.core.database import supabase_service
from app.services.intelligent_gap_filler import IntelligentGapFiller
from app.services.valuation_engine_service import ValuationEngineService
from app.services.revenue_projection_service import RevenueProjectionService

logger = logging.getLogger(__name__)


class FactorType(str, Enum):
    QUALITATIVE = "qualitative"
    QUANTITATIVE = "quantitative"
    COMPOSITE = "composite"


class FactorCategory(str, Enum):
    MARKET = "market"
    COMPETITIVE = "competitive"
    OPERATIONAL = "operational"
    FINANCIAL = "financial"
    TEAM = "team"
    PRODUCT = "product"
    REGULATORY = "regulatory"
    TECHNOLOGY = "technology"


class RelationshipType(str, Enum):
    COMPETES_WITH = "competes_with"
    SUPPLIES = "supplies"
    INVESTS_IN = "invests_in"
    REGULATES = "regulates"
    SERVES = "serves"
    PARTNERS_WITH = "partners_with"
    ACQUIRES = "acquires"
    FUNDS = "funds"


@dataclass
class WorldModelEntity:
    """Entity in the world model (company, market, competitor, etc.)"""
    entity_type: str
    entity_id: Optional[str] = None
    entity_name: str = ""
    properties: Dict[str, Any] = field(default_factory=dict)


@dataclass
class WorldModelFactor:
    """Factor in the world model (qualitative or quantitative)"""
    factor_name: str
    factor_type: FactorType
    factor_category: FactorCategory
    value_type: str  # 'score' | 'amount' | 'percentage' | 'count' | 'boolean' | 'text'
    current_value: Any = None
    source: str = "manual"
    confidence_score: float = 0.5
    dependencies: List[str] = field(default_factory=list)
    formula: Optional[str] = None
    assumptions: Dict[str, Any] = field(default_factory=dict)
    historical_values: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class WorldModelRelationship:
    """Relationship between entities"""
    from_entity_id: str
    to_entity_id: str
    relationship_type: RelationshipType
    strength: float = 1.0
    properties: Dict[str, Any] = field(default_factory=dict)


@dataclass
class WorldModelDefinition:
    """Complete world model definition"""
    name: str
    model_type: str
    entities: List[WorldModelEntity] = field(default_factory=list)
    factors: List[WorldModelFactor] = field(default_factory=list)
    relationships: List[WorldModelRelationship] = field(default_factory=list)
    temporal_dynamics: Dict[str, Any] = field(default_factory=dict)


class WorldModelBuilder:
    """
    Builds comprehensive world models that capture full business context
    """
    
    def __init__(self):
        self.gap_filler = IntelligentGapFiller()
        self.valuation_service = ValuationEngineService()
        self.revenue_service = RevenueProjectionService()
    
    async def create_model(
        self,
        name: str,
        model_type: str,
        fund_id: Optional[str] = None,
        company_id: Optional[str] = None,
        created_by: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create a new world model
        
        Args:
            name: Model name
            model_type: 'company' | 'portfolio' | 'market' | 'competitive' | 'operational' | 'custom'
            fund_id: Optional fund ID
            company_id: Optional company ID
            created_by: User ID
            
        Returns:
            Created model record
        """
        model_data = {
            "name": name,
            "model_type": model_type,
            "model_definition": {},
            "formulas": {},
            "assumptions": {},
            "relationships": [],
            "temporal_dynamics": {},
            "fund_id": fund_id,
            "company_id": company_id,
            "created_by": created_by
        }
        
        result = supabase_service.client.table("world_models").insert(model_data).execute()
        return result.data[0] if result.data else {}
    
    async def add_entity(
        self,
        model_id: str,
        entity_type: str,
        entity_name: str,
        entity_id: Optional[str] = None,
        properties: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Add an entity to the world model"""
        entity_data = {
            "model_id": model_id,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "entity_name": entity_name,
            "properties": properties or {}
        }
        
        result = supabase_service.client.table("world_model_entities").insert(entity_data).execute()
        return result.data[0] if result.data else {}
    
    async def add_factor(
        self,
        model_id: str,
        entity_id: str,
        factor_name: str,
        factor_type: FactorType,
        factor_category: FactorCategory,
        value_type: str,
        current_value: Any = None,
        source: str = "manual",
        confidence_score: float = 0.5,
        dependencies: Optional[List[str]] = None,
        formula: Optional[str] = None,
        assumptions: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Add a factor to the world model"""
        factor_data = {
            "model_id": model_id,
            "entity_id": entity_id,
            "factor_name": factor_name,
            "factor_type": factor_type.value,
            "factor_category": factor_category.value,
            "value_type": value_type,
            "current_value": current_value,
            "source": source,
            "confidence_score": confidence_score,
            "dependencies": dependencies or [],
            "formula": formula,
            "assumptions": assumptions or {},
            "historical_values": []
        }
        
        result = supabase_service.client.table("world_model_factors").insert(factor_data).execute()
        return result.data[0] if result.data else {}
    
    async def add_relationship(
        self,
        model_id: str,
        from_entity_id: str,
        to_entity_id: str,
        relationship_type: RelationshipType,
        strength: float = 1.0,
        properties: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Add a relationship between entities"""
        rel_data = {
            "model_id": model_id,
            "from_entity_id": from_entity_id,
            "to_entity_id": to_entity_id,
            "relationship_type": relationship_type.value,
            "strength": strength,
            "properties": properties or {}
        }
        
        result = supabase_service.client.table("world_model_relationships").insert(rel_data).execute()
        return result.data[0] if result.data else {}
    
    async def infer_qualitative_factor(
        self,
        company_data: Dict[str, Any],
        factor_name: str,
        dimension: str
    ) -> Dict[str, Any]:
        """
        Infer a qualitative factor score using IntelligentGapFiller
        
        Args:
            company_data: Company data dictionary
            factor_name: Name of the factor (e.g., 'market_sentiment')
            dimension: Dimension to score (e.g., 'market_timing', 'team_quality')
            
        Returns:
            Score and evidence
        """
        try:
            # Use gap filler to infer missing data and get scores
            inferred_data = await self.gap_filler.infer_missing_data(company_data)
            
            # Map dimensions to gap filler methods
            if dimension == "market_timing":
                # Use market intelligence
                market_score = 50.0  # Default
                # TODO: Integrate with MarketIntelligenceService
                return {
                    "score": market_score,
                    "confidence": 0.7,
                    "source": "inferred",
                    "evidence": []
                }
            
            elif dimension == "team_quality":
                # Score based on team size, investor quality, etc.
                team_size = company_data.get("employee_count", 0) or 0
                team_score = min(100, max(0, (team_size / 50) * 100))
                
                return {
                    "score": team_score,
                    "confidence": 0.6,
                    "source": "inferred",
                    "evidence": [{"metric": "employee_count", "value": team_size}]
                }
            
            elif dimension == "competitive_position":
                # Score based on funding, market position
                funding = company_data.get("total_funding", 0) or 0
                if funding > 50_000_000:
                    position_score = 90
                elif funding > 10_000_000:
                    position_score = 75
                elif funding > 1_000_000:
                    position_score = 60
                else:
                    position_score = 40
                
                return {
                    "score": position_score,
                    "confidence": 0.65,
                    "source": "inferred",
                    "evidence": [{"metric": "total_funding", "value": funding}]
                }
            
            elif dimension == "execution_quality":
                # Score based on revenue, growth
                revenue = company_data.get("revenue", 0) or 0
                growth = company_data.get("growth_rate", 0) or 0
                
                revenue_score = min(50, (revenue / 10_000_000) * 50) if revenue > 0 else 25
                growth_score = min(50, growth * 50) if growth > 0 else 25
                execution_score = revenue_score + growth_score
                
                return {
                    "score": execution_score,
                    "confidence": 0.7,
                    "source": "inferred",
                    "evidence": [
                        {"metric": "revenue", "value": revenue},
                        {"metric": "growth_rate", "value": growth}
                    ]
                }
            
            elif dimension == "market_sentiment":
                # Score based on sector, recent funding
                sector = company_data.get("sector", "").lower()
                sector_scores = {
                    "ai": 90,
                    "fintech": 70,
                    "defense": 80,
                    "climate": 85,
                    "healthtech": 75,
                    "saas": 60
                }
                sentiment_score = sector_scores.get(sector, 50)
                
                return {
                    "score": sentiment_score,
                    "confidence": 0.6,
                    "source": "inferred",
                    "evidence": [{"metric": "sector", "value": sector}]
                }
            
            # Default fallback
            return {
                "score": 50.0,
                "confidence": 0.5,
                "source": "inferred",
                "evidence": []
            }
            
        except Exception as e:
            logger.error(f"Error inferring qualitative factor {factor_name}: {e}")
            return {
                "score": 50.0,
                "confidence": 0.3,
                "source": "inferred",
                "evidence": []
            }
    
    async def calculate_quantitative_factor(
        self,
        company_data: Dict[str, Any],
        factor_name: str
    ) -> Dict[str, Any]:
        """
        Calculate a quantitative factor using existing services
        
        Args:
            company_data: Company data dictionary
            factor_name: Name of the factor (e.g., 'valuation', 'revenue_projection')
            
        Returns:
            Calculated value and metadata
        """
        try:
            if factor_name == "valuation":
                # Use ValuationEngineService
                from app.services.valuation_engine_service import ValuationRequest, Stage
                
                stage_str = company_data.get("stage", "series_a")
                stage_map = {
                    "pre_seed": Stage.PRE_SEED,
                    "seed": Stage.SEED,
                    "series_a": Stage.SERIES_A,
                    "series_b": Stage.SERIES_B,
                    "series_c": Stage.SERIES_C
                }
                stage = stage_map.get(stage_str, Stage.SERIES_A)
                
                request = ValuationRequest(
                    company_name=company_data.get("name", ""),
                    stage=stage,
                    revenue=company_data.get("revenue"),
                    growth_rate=company_data.get("growth_rate"),
                    business_model=company_data.get("business_model"),
                    industry=company_data.get("industry")
                )
                
                result = await self.valuation_service.calculate_valuation(request)
                
                return {
                    "value": result.get("valuation", 0),
                    "confidence": 0.8,
                    "source": "valuation_service",
                    "method": result.get("method", "auto"),
                    "evidence": [{"method": result.get("method"), "details": result}]
                }
            
            elif factor_name == "revenue_projection":
                # Use RevenueProjectionService
                revenue = company_data.get("revenue", 0) or 0
                growth_rate = company_data.get("growth_rate", 0) or 0
                
                # Project 5 years
                projections = []
                current_revenue = revenue
                for year in range(1, 6):
                    # Apply declining growth rate
                    year_growth = growth_rate * (0.9 ** (year - 1))
                    current_revenue = current_revenue * (1 + year_growth)
                    projections.append({
                        "year": year,
                        "revenue": current_revenue,
                        "growth_rate": year_growth
                    })
                
                return {
                    "value": projections,
                    "confidence": 0.75,
                    "source": "revenue_projection_service",
                    "evidence": [{"base_revenue": revenue, "base_growth": growth_rate}]
                }
            
            # Default: return raw value if available
            value = company_data.get(factor_name)
            return {
                "value": value,
                "confidence": 0.5,
                "source": "company_data",
                "evidence": []
            }
            
        except Exception as e:
            logger.error(f"Error calculating quantitative factor {factor_name}: {e}")
            return {
                "value": None,
                "confidence": 0.0,
                "source": "error",
                "evidence": []
            }
    
    async def build_company_world_model(
        self,
        company_data: Dict[str, Any],
        model_name: Optional[str] = None,
        fund_id: Optional[str] = None,
        created_by: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Build a comprehensive world model for a company
        
        This creates entities, factors (qualitative and quantitative), and relationships
        that represent the full context of the company's world.
        """
        company_name = company_data.get("name", "Unknown Company")
        model_name = model_name or f"World Model: {company_name}"
        
        # Create the model
        model = await self.create_model(
            name=model_name,
            model_type="company",
            fund_id=fund_id,
            company_id=company_data.get("id"),
            created_by=created_by
        )
        model_id = model["id"]
        
        # Add company entity
        company_entity = await self.add_entity(
            model_id=model_id,
            entity_type="company",
            entity_name=company_name,
            entity_id=company_data.get("id"),
            properties={
                "stage": company_data.get("stage"),
                "sector": company_data.get("sector"),
                "industry": company_data.get("industry")
            }
        )
        company_entity_id = company_entity["id"]
        
        # Add quantitative factors
        quantitative_factors = [
            ("revenue", FactorCategory.FINANCIAL, "amount"),
            ("growth_rate", FactorCategory.FINANCIAL, "percentage"),
            ("valuation", FactorCategory.FINANCIAL, "amount"),
            ("revenue_projection", FactorCategory.FINANCIAL, "amount"),
            ("burn_rate", FactorCategory.FINANCIAL, "amount"),
            ("runway", FactorCategory.FINANCIAL, "count"),
        ]
        
        for factor_name, category, value_type in quantitative_factors:
            calc_result = await self.calculate_quantitative_factor(company_data, factor_name)
            
            await self.add_factor(
                model_id=model_id,
                entity_id=company_entity_id,
                factor_name=factor_name,
                factor_type=FactorType.QUANTITATIVE,
                factor_category=category,
                value_type=value_type,
                current_value=calc_result["value"],
                source=calc_result["source"],
                confidence_score=calc_result["confidence"],
                assumptions=calc_result.get("evidence", [])
            )
        
        # Add qualitative factors
        qualitative_factors = [
            ("market_sentiment", FactorCategory.MARKET, "market_sentiment"),
            ("team_quality", FactorCategory.TEAM, "team_quality"),
            ("competitive_position", FactorCategory.COMPETITIVE, "competitive_position"),
            ("execution_quality", FactorCategory.OPERATIONAL, "execution_quality"),
            ("market_timing", FactorCategory.MARKET, "market_timing"),
        ]
        
        for factor_name, category, dimension in qualitative_factors:
            infer_result = await self.infer_qualitative_factor(company_data, factor_name, dimension)
            
            factor = await self.add_factor(
                model_id=model_id,
                entity_id=company_entity_id,
                factor_name=factor_name,
                factor_type=FactorType.QUALITATIVE,
                factor_category=category,
                value_type="score",
                current_value=infer_result["score"],
                source=infer_result["source"],
                confidence_score=infer_result["confidence"],
                assumptions=infer_result.get("evidence", [])
            )
            
            # Store detailed qualitative score
            await supabase_service.client.table("qualitative_factor_scores").insert({
                "factor_id": factor["id"],
                "dimension": dimension,
                "score": infer_result["score"],
                "weight": 1.0,
                "source": infer_result["source"],
                "evidence": infer_result.get("evidence", []),
                "scored_by": "system"
            }).execute()
        
        # TODO: Add market entity and relationships
        # TODO: Add competitor entities and relationships
        # TODO: Add investor entities and relationships
        
        return {
            "model_id": model_id,
            "model": model,
            "entities": [company_entity],
            "factors_added": len(quantitative_factors) + len(qualitative_factors)
        }
    
    async def get_model(self, model_id: str) -> Dict[str, Any]:
        """Get a world model with all entities, factors, and relationships"""
        # Get model
        model_result = supabase_service.client.table("world_models").select("*").eq("id", model_id).execute()
        if not model_result.data:
            return {}
        
        model = model_result.data[0]
        
        # Get entities
        entities_result = supabase_service.client.table("world_model_entities").select("*").eq("model_id", model_id).execute()
        entities = entities_result.data or []
        
        # Get factors
        factors_result = supabase_service.client.table("world_model_factors").select("*").eq("model_id", model_id).execute()
        factors = factors_result.data or []
        
        # Get relationships
        rels_result = supabase_service.client.table("world_model_relationships").select("*").eq("model_id", model_id).execute()
        relationships = rels_result.data or []
        
        return {
            "model": model,
            "entities": entities,
            "factors": factors,
            "relationships": relationships
        }
    
    async def execute_model(self, model_id: str) -> Dict[str, Any]:
        """
        Execute a world model - calculate all factors based on formulas and dependencies
        """
        model_data = await self.get_model(model_id)
        factors = model_data.get("factors", [])
        
        # Build dependency graph
        factor_map = {f["id"]: f for f in factors}
        calculated = {}
        
        def calculate_factor(factor_id: str) -> Any:
            if factor_id in calculated:
                return calculated[factor_id]
            
            factor = factor_map[factor_id]
            
            # If has formula, evaluate it
            if factor.get("formula"):
                # TODO: Implement formula evaluator
                # For now, return current value
                calculated[factor_id] = factor.get("current_value")
                return calculated[factor_id]
            
            # If has dependencies, calculate them first
            if factor.get("dependencies"):
                dep_values = [calculate_factor(dep_id) for dep_id in factor["dependencies"]]
                # TODO: Use formula with dependency values
                calculated[factor_id] = factor.get("current_value")
                return calculated[factor_id]
            
            # Otherwise return current value
            calculated[factor_id] = factor.get("current_value")
            return calculated[factor_id]
        
        # Calculate all factors
        results = {}
        for factor in factors:
            results[factor["id"]] = calculate_factor(factor["id"])
        
        return {
            "model_id": model_id,
            "results": results,
            "calculated_at": datetime.now().isoformat()
        }
