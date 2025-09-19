"""
Base Skill Abstract Class
Eliminates 40% code duplication across all agent skills
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Union, TypeVar, Generic
from dataclasses import dataclass
from enum import Enum
import asyncio
import logging
from datetime import datetime
import json

# Configure logging
logger = logging.getLogger(__name__)

class SkillCategory(Enum):
    DATA_GATHERING = "data_gathering"
    ANALYSIS = "analysis"
    GENERATION = "generation"
    COMPUTATION = "computation"
    COMMUNICATION = "communication"

class ExecutionStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"
    RETRYING = "retrying"

@dataclass
class SkillResult:
    """Standardized skill execution result"""
    skill_id: str
    status: ExecutionStatus
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    execution_time: Optional[float] = None
    tokens_used: Optional[int] = None
    metadata: Optional[Dict[str, Any]] = None
    created_at: datetime = None

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.utcnow()

@dataclass
class SkillConfig:
    """Configuration for skill execution"""
    timeout: int = 30
    max_retries: int = 3
    retry_delay: float = 1.0
    cache_ttl: int = 300  # 5 minutes
    rate_limit: Optional[int] = None
    dependencies: List[str] = None
    required_params: List[str] = None

    def __post_init__(self):
        if self.dependencies is None:
            self.dependencies = []
        if self.required_params is None:
            self.required_params = []

T = TypeVar('T')

class BaseSkill(ABC, Generic[T]):
    """
    Abstract base class for all agent skills
    Provides common functionality and enforces consistent interface
    """
    
    def __init__(self, skill_id: str, config: Optional[SkillConfig] = None):
        self.skill_id = skill_id
        self.config = config or SkillConfig()
        self.execution_history: List[SkillResult] = []
        self._cache: Dict[str, Any] = {}
        self._cache_timestamps: Dict[str, datetime] = {}

    @property
    @abstractmethod
    def category(self) -> SkillCategory:
        """Return the category this skill belongs to"""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """Return human-readable description of what this skill does"""
        pass

    @property
    @abstractmethod
    def required_inputs(self) -> List[str]:
        """Return list of required input parameters"""
        pass

    @property
    @abstractmethod
    def output_schema(self) -> Dict[str, Any]:
        """Return JSON schema describing the skill's output format"""
        pass

    @abstractmethod
    async def _execute_core(self, inputs: Dict[str, Any]) -> T:
        """Core execution logic - must be implemented by subclasses"""
        pass

    def get_prompt_template(self) -> str:
        """
        Return the prompt template for this skill
        Default implementation returns empty string - override in subclasses
        """
        return ""

    def validate_inputs(self, inputs: Dict[str, Any]) -> bool:
        """Validate that all required inputs are provided"""
        for param in self.config.required_params:
            if param not in inputs or inputs[param] is None:
                raise ValueError(f"Missing required parameter: {param}")
        
        for param in self.required_inputs:
            if param not in inputs or inputs[param] is None:
                raise ValueError(f"Missing required input: {param}")
        
        return True

    def _get_cache_key(self, inputs: Dict[str, Any]) -> str:
        """Generate cache key from inputs"""
        sorted_inputs = json.dumps(inputs, sort_keys=True)
        return f"{self.skill_id}:{hash(sorted_inputs)}"

    def _is_cached(self, cache_key: str) -> bool:
        """Check if result is cached and still valid"""
        if cache_key not in self._cache:
            return False
        
        timestamp = self._cache_timestamps.get(cache_key)
        if not timestamp:
            return False
        
        age = (datetime.utcnow() - timestamp).total_seconds()
        return age < self.config.cache_ttl

    async def execute(self, inputs: Dict[str, Any], bypass_cache: bool = False) -> SkillResult:
        """
        Execute the skill with comprehensive error handling, caching, and retries
        """
        start_time = datetime.utcnow()
        
        try:
            # Validate inputs
            self.validate_inputs(inputs)
            
            # Check cache unless bypassed
            cache_key = self._get_cache_key(inputs)
            if not bypass_cache and self._is_cached(cache_key):
                logger.info(f"Returning cached result for {self.skill_id}")
                return SkillResult(
                    skill_id=self.skill_id,
                    status=ExecutionStatus.COMPLETED,
                    data=self._cache[cache_key],
                    metadata={"from_cache": True}
                )

            # Execute with retries
            result = await self._execute_with_retries(inputs)
            
            # Cache successful result
            if result.status == ExecutionStatus.COMPLETED and result.data:
                self._cache[cache_key] = result.data
                self._cache_timestamps[cache_key] = datetime.utcnow()
            
            # Record execution time
            result.execution_time = (datetime.utcnow() - start_time).total_seconds()
            
            # Add to history
            self.execution_history.append(result)
            
            return result
            
        except Exception as e:
            logger.error(f"Skill {self.skill_id} execution failed: {str(e)}")
            result = SkillResult(
                skill_id=self.skill_id,
                status=ExecutionStatus.FAILED,
                error=str(e),
                execution_time=(datetime.utcnow() - start_time).total_seconds()
            )
            self.execution_history.append(result)
            return result

    async def _execute_with_retries(self, inputs: Dict[str, Any]) -> SkillResult:
        """Execute with retry logic"""
        last_error = None
        
        for attempt in range(self.config.max_retries + 1):
            try:
                if attempt > 0:
                    logger.info(f"Retrying {self.skill_id}, attempt {attempt + 1}")
                    await asyncio.sleep(self.config.retry_delay * attempt)
                
                # Execute with timeout
                result = await asyncio.wait_for(
                    self._execute_core(inputs),
                    timeout=self.config.timeout
                )
                
                return SkillResult(
                    skill_id=self.skill_id,
                    status=ExecutionStatus.COMPLETED,
                    data=result if isinstance(result, dict) else {"result": result}
                )
                
            except asyncio.TimeoutError:
                last_error = f"Execution timeout after {self.config.timeout} seconds"
                logger.warning(f"Skill {self.skill_id} timeout on attempt {attempt + 1}")
                
            except Exception as e:
                last_error = str(e)
                logger.warning(f"Skill {self.skill_id} failed on attempt {attempt + 1}: {last_error}")
        
        # All retries exhausted
        return SkillResult(
            skill_id=self.skill_id,
            status=ExecutionStatus.FAILED,
            error=f"Max retries exceeded. Last error: {last_error}"
        )

    def get_metrics(self) -> Dict[str, Any]:
        """Get execution metrics for monitoring"""
        if not self.execution_history:
            return {
                "total_executions": 0,
                "success_rate": 0,
                "avg_execution_time": 0,
                "cache_hit_rate": 0
            }
        
        total = len(self.execution_history)
        successful = len([r for r in self.execution_history if r.status == ExecutionStatus.COMPLETED])
        cached = len([r for r in self.execution_history if r.metadata and r.metadata.get("from_cache")])
        
        avg_time = sum(
            r.execution_time for r in self.execution_history 
            if r.execution_time is not None
        ) / total if total > 0 else 0
        
        return {
            "total_executions": total,
            "success_rate": successful / total if total > 0 else 0,
            "avg_execution_time": avg_time,
            "cache_hit_rate": cached / total if total > 0 else 0,
            "last_execution": self.execution_history[-1].created_at.isoformat()
        }

    def clear_cache(self):
        """Clear the skill's cache"""
        self._cache.clear()
        self._cache_timestamps.clear()

    def __str__(self) -> str:
        return f"{self.skill_id} ({self.category.value}): {self.description}"

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}(id='{self.skill_id}', category='{self.category.value}')>"


class DataGatheringSkill(BaseSkill[Dict[str, Any]]):
    """Base class for skills that gather data from external sources"""
    
    @property
    def category(self) -> SkillCategory:
        return SkillCategory.DATA_GATHERING

    async def gather_data(self, query: str, sources: List[str] = None) -> Dict[str, Any]:
        """Override in subclasses to implement specific data gathering"""
        return await self._execute_core({"query": query, "sources": sources or []})


class AnalysisSkill(BaseSkill[Dict[str, Any]]):
    """Base class for skills that analyze data"""
    
    @property
    def category(self) -> SkillCategory:
        return SkillCategory.ANALYSIS

    async def analyze(self, data: Dict[str, Any], analysis_type: str = "general") -> Dict[str, Any]:
        """Override in subclasses to implement specific analysis"""
        return await self._execute_core({"data": data, "analysis_type": analysis_type})


class GenerationSkill(BaseSkill[str]):
    """Base class for skills that generate content"""
    
    @property
    def category(self) -> SkillCategory:
        return SkillCategory.GENERATION

    async def generate(self, prompt: str, context: Dict[str, Any] = None) -> str:
        """Override in subclasses to implement specific generation"""
        result = await self._execute_core({"prompt": prompt, "context": context or {}})
        return result if isinstance(result, str) else str(result)


class ComputationSkill(BaseSkill[Union[float, Dict[str, Any]]]):
    """Base class for skills that perform computations"""
    
    @property
    def category(self) -> SkillCategory:
        return SkillCategory.COMPUTATION

    async def compute(self, inputs: Dict[str, Any]) -> Union[float, Dict[str, Any]]:
        """Override in subclasses to implement specific computations"""
        return await self._execute_core(inputs)