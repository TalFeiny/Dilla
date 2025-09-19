"""
Parallel Execution Engine - Migrated from Frontend
Massively parallel task execution with intelligent orchestration
"""

import asyncio
import time
import logging
from typing import Dict, List, Optional, Any, Set, Tuple
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict
import hashlib
import json
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class TaskStatus(str, Enum):
    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRYING = "retrying"

class WorkerPoolType(str, Enum):
    CPU = "cpu"
    IO = "io"
    API = "api"

@dataclass
class ExecutionTask:
    """Task to be executed"""
    id: str
    type: str
    skill: str
    inputs: Dict[str, Any]
    priority: int = 5  # 1-10, higher = more important
    dependencies: List[str] = field(default_factory=list)
    retry_count: int = 0
    max_retries: int = 3
    timeout: int = 30000  # milliseconds
    status: TaskStatus = TaskStatus.PENDING
    result: Optional[Any] = None
    error: Optional[str] = None
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    execution_time: Optional[float] = None
    worker: Optional[str] = None

@dataclass
class ExecutionGroup:
    """Group of tasks that can be executed together"""
    id: str
    tasks: List[ExecutionTask]
    parallel: bool = True
    max_concurrency: Optional[int] = None
    priority: int = 5

@dataclass
class WorkerPool:
    """Worker pool for different task types"""
    id: str
    type: WorkerPoolType
    max_workers: int
    active_workers: int = 0
    queue: List[ExecutionTask] = field(default_factory=list)
    throughput: float = 0.0  # tasks per second
    total_processed: int = 0
    last_update: float = field(default_factory=time.time)

class ParallelExecutionEngine:
    """
    High-performance parallel execution engine for backend skills
    """
    
    # Configuration
    CONFIG = {
        "MAX_CONCURRENT_TASKS": 100,
        "MAX_API_CONCURRENT": 50,
        "MAX_CPU_CONCURRENT": 20,
        "MAX_IO_CONCURRENT": 30,
        "BATCH_SIZE": 25,
        "QUEUE_CHECK_INTERVAL": 0.01,  # seconds
        "TASK_TIMEOUT_DEFAULT": 30,  # seconds
        "RETRY_DELAYS": [1, 2, 5],  # seconds
        "SMART_BATCHING": True,
        "PRIORITY_BOOST_WAITING": 0.1,
    }
    
    # Skill to worker pool mapping
    SKILL_TO_POOL = {
        # API-bound skills
        "company-data-fetcher": WorkerPoolType.API,
        "funding-aggregator": WorkerPoolType.API,
        "competitive-intelligence": WorkerPoolType.API,
        "market-sourcer": WorkerPoolType.API,
        "tavily-search": WorkerPoolType.API,
        "firecrawl-scrape": WorkerPoolType.API,
        "web-research": WorkerPoolType.API,
        
        # CPU-bound skills
        "deal-comparer": WorkerPoolType.CPU,
        "valuation-engine": WorkerPoolType.CPU,
        "scenario-generator": WorkerPoolType.CPU,
        "pwerm-calculator": WorkerPoolType.CPU,
        "dcf-model": WorkerPoolType.CPU,
        "financial-analysis": WorkerPoolType.CPU,
        "chart-generator": WorkerPoolType.CPU,
        
        # IO-bound skills
        "deck-storytelling": WorkerPoolType.IO,
        "cim-builder": WorkerPoolType.IO,
        "excel-generator": WorkerPoolType.IO,
        "document-generator": WorkerPoolType.IO,
    }
    
    def __init__(self):
        # Worker pools
        self.worker_pools: Dict[WorkerPoolType, WorkerPool] = {}
        
        # Task management
        self.task_queue: List[ExecutionTask] = []
        self.executing_tasks: Dict[str, ExecutionTask] = {}
        self.completed_tasks: Dict[str, ExecutionTask] = {}
        self.task_dependency_graph: Dict[str, Set[str]] = {}
        
        # Skill executor reference
        self.skill_executor = None
        
        # Performance metrics
        self.metrics = {
            "total_tasks": 0,
            "completed_tasks": 0,
            "failed_tasks": 0,
            "average_execution_time": 0.0,
            "peak_concurrency": 0,
            "current_concurrency": 0,
        }
        
        # Semaphores for concurrency control
        self.semaphores: Dict[WorkerPoolType, asyncio.Semaphore] = {}
        
        # Initialize
        self._initialize_worker_pools()
        
    def _initialize_worker_pools(self):
        """Initialize worker pools and semaphores"""
        # API pool
        self.worker_pools[WorkerPoolType.API] = WorkerPool(
            id="api-pool",
            type=WorkerPoolType.API,
            max_workers=self.CONFIG["MAX_API_CONCURRENT"]
        )
        self.semaphores[WorkerPoolType.API] = asyncio.Semaphore(
            self.CONFIG["MAX_API_CONCURRENT"]
        )
        
        # CPU pool
        self.worker_pools[WorkerPoolType.CPU] = WorkerPool(
            id="cpu-pool",
            type=WorkerPoolType.CPU,
            max_workers=self.CONFIG["MAX_CPU_CONCURRENT"]
        )
        self.semaphores[WorkerPoolType.CPU] = asyncio.Semaphore(
            self.CONFIG["MAX_CPU_CONCURRENT"]
        )
        
        # IO pool
        self.worker_pools[WorkerPoolType.IO] = WorkerPool(
            id="io-pool",
            type=WorkerPoolType.IO,
            max_workers=self.CONFIG["MAX_IO_CONCURRENT"]
        )
        self.semaphores[WorkerPoolType.IO] = asyncio.Semaphore(
            self.CONFIG["MAX_IO_CONCURRENT"]
        )
    
    def set_skill_executor(self, executor):
        """Set the skill executor to use for task execution"""
        self.skill_executor = executor
    
    async def execute_tasks(self, tasks: List[ExecutionTask]) -> Dict[str, Any]:
        """
        Execute tasks with massive parallelism
        Returns mapping of task_id to result
        """
        logger.info(f"Executing {len(tasks)} tasks with parallel execution")
        
        # Build dependency graph
        self._build_dependency_graph(tasks)
        
        # Group tasks by dependency levels
        execution_groups = self._create_execution_groups(tasks)
        
        # Track all tasks
        for task in tasks:
            task.status = TaskStatus.PENDING
            self.metrics["total_tasks"] += 1
        
        # Execute groups
        results = {}
        
        for group in execution_groups:
            logger.info(
                f"Executing group {group.id} with {len(group.tasks)} tasks "
                f"(parallel: {group.parallel})"
            )
            
            if group.parallel:
                # Parallel execution within group
                group_results = await self._execute_parallel_group(group)
                results.update(group_results)
            else:
                # Sequential execution (rare)
                for task in group.tasks:
                    result = await self._execute_task(task)
                    results[task.id] = result
        
        logger.info(f"Completed execution. Metrics: {self.metrics}")
        return results
    
    async def _execute_parallel_group(self, group: ExecutionGroup) -> Dict[str, Any]:
        """Execute a group of tasks in parallel with smart batching"""
        results = {}
        tasks = group.tasks
        
        # Smart batching - group similar tasks
        if self.CONFIG["SMART_BATCHING"]:
            batches = self._create_smart_batches(tasks)
        else:
            batches = [[task] for task in tasks]
        
        # Execute batches
        for batch in batches:
            # Create coroutines for batch
            coroutines = [self._execute_with_pooling(task) for task in batch]
            
            # Execute with gather (allows partial failures)
            batch_results = await asyncio.gather(*coroutines, return_exceptions=True)
            
            # Process results
            for task, result in zip(batch, batch_results):
                if isinstance(result, Exception):
                    # Handle failure
                    logger.error(f"Task {task.id} failed: {result}")
                    task.status = TaskStatus.FAILED
                    task.error = str(result)
                    self.metrics["failed_tasks"] += 1
                    
                    # Schedule retry if needed
                    if task.retry_count < task.max_retries:
                        await self._schedule_retry(task)
                    else:
                        results[task.id] = {"error": str(result)}
                else:
                    # Success
                    task.status = TaskStatus.COMPLETED
                    task.result = result
                    self.metrics["completed_tasks"] += 1
                    results[task.id] = result
        
        return results
    
    async def _execute_with_pooling(self, task: ExecutionTask) -> Any:
        """Execute task with worker pool management"""
        # Determine pool type
        pool_type = self.SKILL_TO_POOL.get(task.skill, WorkerPoolType.CPU)
        pool = self.worker_pools[pool_type]
        semaphore = self.semaphores[pool_type]
        
        # Acquire semaphore for concurrency control
        async with semaphore:
            # Update pool stats
            pool.active_workers += 1
            self.metrics["current_concurrency"] += 1
            self.metrics["peak_concurrency"] = max(
                self.metrics["peak_concurrency"],
                self.metrics["current_concurrency"]
            )
            
            task.status = TaskStatus.RUNNING
            task.start_time = time.time()
            task.worker = f"{pool_type.value}-{pool.active_workers}"
            
            try:
                # Execute with timeout
                timeout = task.timeout / 1000  # Convert ms to seconds
                result = await asyncio.wait_for(
                    self._execute_skill(task),
                    timeout=timeout
                )
                
                task.end_time = time.time()
                task.execution_time = task.end_time - task.start_time
                task.status = TaskStatus.COMPLETED
                task.result = result
                
                # Update metrics
                self._update_metrics(task)
                self._update_throughput(pool)
                
                return result
                
            except asyncio.TimeoutError:
                task.status = TaskStatus.FAILED
                task.error = f"Task timed out after {timeout}s"
                raise
                
            except Exception as e:
                task.status = TaskStatus.FAILED
                task.error = str(e)
                raise
                
            finally:
                # Release worker
                pool.active_workers -= 1
                self.metrics["current_concurrency"] -= 1
    
    async def _execute_skill(self, task: ExecutionTask) -> Any:
        """Execute the actual skill"""
        if not self.skill_executor:
            # Try to import unified MCP orchestrator
            try:
                from app.services.unified_mcp_orchestrator import unified_mcp_orchestrator
                self.skill_executor = unified_mcp_orchestrator
            except ImportError:
                logger.error("No skill executor available")
                raise RuntimeError(f"Cannot execute skill {task.skill}: No executor")
        
        # Execute through unified MCP orchestrator
        result = await self.skill_executor.execute_skill(
            skill_name=task.skill,
            inputs=task.inputs
        )
        
        return result
    
    def _build_dependency_graph(self, tasks: List[ExecutionTask]):
        """Build dependency graph for tasks"""
        self.task_dependency_graph.clear()
        
        for task in tasks:
            self.task_dependency_graph[task.id] = set(task.dependencies)
    
    def _create_execution_groups(self, tasks: List[ExecutionTask]) -> List[ExecutionGroup]:
        """Create execution groups based on dependencies"""
        groups = []
        levels: Dict[str, int] = {}
        
        def calculate_level(task_id: str) -> int:
            """Calculate dependency level for a task"""
            if task_id in levels:
                return levels[task_id]
            
            task = next((t for t in tasks if t.id == task_id), None)
            if not task:
                return 0
            
            if not task.dependencies:
                levels[task_id] = 0
                return 0
            
            max_dep_level = max(
                calculate_level(dep) for dep in task.dependencies
            )
            level = max_dep_level + 1
            levels[task_id] = level
            return level
        
        # Calculate levels for all tasks
        for task in tasks:
            calculate_level(task.id)
        
        # Group tasks by level
        tasks_by_level: Dict[int, List[ExecutionTask]] = defaultdict(list)
        for task in tasks:
            level = levels.get(task.id, 0)
            tasks_by_level[level].append(task)
        
        # Create execution groups
        for index, level in enumerate(sorted(tasks_by_level.keys())):
            groups.append(ExecutionGroup(
                id=f"group-{index}",
                tasks=tasks_by_level[level],
                parallel=True,
                max_concurrency=self.CONFIG["MAX_CONCURRENT_TASKS"],
                priority=10 - index  # Higher priority for earlier groups
            ))
        
        return groups
    
    def _create_smart_batches(self, tasks: List[ExecutionTask]) -> List[List[ExecutionTask]]:
        """Create smart batches by grouping similar tasks"""
        batches = []
        tasks_by_skill: Dict[str, List[ExecutionTask]] = defaultdict(list)
        
        # Group by skill type
        for task in tasks:
            tasks_by_skill[task.skill].append(task)
        
        # Create batches respecting batch size
        batch_size = self.CONFIG["BATCH_SIZE"]
        for skill, skill_tasks in tasks_by_skill.items():
            for i in range(0, len(skill_tasks), batch_size):
                batches.append(skill_tasks[i:i + batch_size])
        
        # Sort batches by average priority
        batches.sort(
            key=lambda batch: sum(t.priority for t in batch) / len(batch),
            reverse=True
        )
        
        return batches
    
    async def _schedule_retry(self, task: ExecutionTask):
        """Schedule task retry with exponential backoff"""
        task.retry_count += 1
        delay = self.CONFIG["RETRY_DELAYS"][
            min(task.retry_count - 1, len(self.CONFIG["RETRY_DELAYS"]) - 1)
        ]
        
        logger.info(f"Scheduling retry {task.retry_count} for task {task.id} in {delay}s")
        
        # Wait and retry
        await asyncio.sleep(delay)
        task.status = TaskStatus.RETRYING
        
        # Re-execute
        try:
            result = await self._execute_with_pooling(task)
            task.result = result
            self.completed_tasks[task.id] = task
        except Exception as e:
            logger.error(f"Retry failed for task {task.id}: {e}")
            task.error = str(e)
    
    def _update_metrics(self, task: ExecutionTask):
        """Update performance metrics"""
        if task.execution_time:
            current_avg = self.metrics["average_execution_time"]
            completed = self.metrics["completed_tasks"]
            if completed > 1:
                self.metrics["average_execution_time"] = (
                    (current_avg * (completed - 1) + task.execution_time) / completed
                )
            else:
                self.metrics["average_execution_time"] = task.execution_time
    
    def _update_throughput(self, pool: WorkerPool):
        """Update pool throughput"""
        pool.total_processed += 1
        current_time = time.time()
        time_elapsed = current_time - pool.last_update
        
        if time_elapsed > 0:
            pool.throughput = pool.total_processed / time_elapsed
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get current execution metrics"""
        return self.metrics.copy()
    
    def get_pool_status(self) -> Dict[str, Any]:
        """Get worker pool status"""
        status = {}
        
        for pool_type, pool in self.worker_pools.items():
            status[pool_type.value] = {
                "active": pool.active_workers,
                "max": pool.max_workers,
                "utilization": f"{(pool.active_workers / pool.max_workers * 100):.1f}%",
                "queue_length": len(pool.queue),
                "throughput": f"{pool.throughput:.2f} tasks/sec",
                "total_processed": pool.total_processed
            }
        
        return status

# Singleton instance
_parallel_execution_engine = None

def get_parallel_execution_engine() -> ParallelExecutionEngine:
    """Get singleton instance of parallel execution engine"""
    global _parallel_execution_engine
    if _parallel_execution_engine is None:
        _parallel_execution_engine = ParallelExecutionEngine()
    return _parallel_execution_engine