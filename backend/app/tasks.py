"""
Celery background tasks
"""

from celery import Task
from app.core.celery_app import celery_app
from app.core.exceptions import RateLimitError
from app.services.pwerm_service import pwerm_service
from app.services.market_research_service import market_research_service
try:
    from app.services.document_service import document_processor
except ImportError:
    document_processor = None  # Use document_process_service path when missing
# from app.services.agent_service import self_learning_agent  # Temporarily disabled
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class CallbackTask(Task):
    """Task with callback support"""
    def on_success(self, retval, task_id, args, kwargs):
        """Success callback"""
        logger.info(f"Task {task_id} succeeded with result: {retval}")
    
    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """Failure callback"""
        logger.error(f"Task {task_id} failed with exception: {exc}")


@celery_app.task(bind=True, base=CallbackTask, name="app.tasks.analysis.run_pwerm")
def run_pwerm_analysis(
    self,
    company_name: str,
    arr: Optional[float] = None,
    growth_rate: Optional[float] = None,
    sector: Optional[str] = None
) -> Dict[str, Any]:
    """Run PWERM analysis as background task"""
    try:
        # Update task state
        self.update_state(state="PROGRESS", meta={"status": "Starting PWERM analysis"})
        
        # Run analysis (synchronous version for Celery)
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        result = loop.run_until_complete(
            pwerm_service.analyze_company(
                company_name=company_name,
                arr=arr,
                growth_rate=growth_rate,
                sector=sector
            )
        )
        
        return {
            "status": "success",
            "result": result
        }
        
    except Exception as e:
        logger.error(f"PWERM analysis failed: {e}")
        return {
            "status": "error",
            "error": str(e)
        }


@celery_app.task(
    bind=True,
    base=CallbackTask,
    name="app.tasks.document.process",
    acks_late=True,
    autoretry_for=(RateLimitError,),
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True,
    retry_kwargs={"max_retries": 5},
)
def process_document(
    self,
    document_id: str,
    file_path: str,
    document_type: Optional[str] = "other",
    company_id: Optional[str] = None,
    fund_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Process document as background task (backend-agnostic via document_process_service).
    Supports long-running extraction; retries on rate limit (429).
    """
    try:
        self.update_state(state="PROGRESS", meta={"status": "Processing document"})
        if document_processor is not None:
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            with open(file_path, "rb") as f:
                content = f.read()
            metadata = loop.run_until_complete(
                document_processor.process_document(
                    file_content=content,
                    filename=file_path.split("/")[-1],
                )
            )
            return {"status": "success", "document_id": metadata.id, "processed": metadata.processed}
        from app.core.adapters import get_storage, get_document_repo
        from app.services.document_process_service import run_document_process
        storage = get_storage()
        document_repo = get_document_repo()
        out = run_document_process(
            document_id=document_id,
            storage_path=file_path,
            document_type=document_type or "other",
            storage=storage,
            document_repo=document_repo,
            company_id=company_id,
            fund_id=fund_id,
        )
        return {
            "status": "success" if out.get("success") else "error",
            "document_id": out.get("document_id", document_id),
            "error": out.get("error"),
        }
    except Exception as e:
        err_str = str(e).lower()
        if "429" in str(e) or "rate limit" in err_str or "rate_limit" in err_str or "too many requests" in err_str:
            raise RateLimitError("llm_api", retry_after=60) from e
        logger.exception("Document processing failed: %s", e)
        return {"status": "error", "error": str(e)}


@celery_app.task(bind=True, base=CallbackTask, name="app.tasks.market.research")
def research_market(
    self,
    query: str,
    company_name: Optional[str] = None,
    sector: Optional[str] = None
) -> Dict[str, Any]:
    """Conduct market research as background task"""
    try:
        self.update_state(state="PROGRESS", meta={"status": "Researching market"})
        
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        research = loop.run_until_complete(
            market_research_service.research_market(
                query=query,
                company_name=company_name,
                sector=sector,
                deep_search=True
            )
        )
        
        return {
            "status": "success",
            "research": {
                "market_size": research.market_size,
                "growth_rate": research.growth_rate,
                "summary": research.summary,
                "trends": research.trends
            }
        }
        
    except Exception as e:
        logger.error(f"Market research failed: {e}")
        return {
            "status": "error",
            "error": str(e)
        }


@celery_app.task(bind=True, base=CallbackTask, name="app.tasks.agent.train")
def train_agent(self, training_data: Dict[str, Any]) -> Dict[str, Any]:
    """Train the self-learning agent as background task"""
    try:
        self.update_state(state="PROGRESS", meta={"status": "Training agent"})
        
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        # Trigger learning
        loop.run_until_complete(
            self_learning_agent._learn_from_experience()
        )
        
        # Save state
        state = loop.run_until_complete(
            self_learning_agent.save_state()
        )
        
        return {
            "status": "success",
            "message": "Agent training completed",
            "timestamp": state["timestamp"]
        }
        
    except Exception as e:
        logger.error(f"Agent training failed: {e}")
        return {
            "status": "error",
            "error": str(e)
        }


@celery_app.task(bind=True, base=CallbackTask, name="app.tasks.analysis.run_company_history")
def run_company_history_analysis(
    self,
    fund_id: str,
    company_ids: Optional[list] = None,
    document_ids: Optional[list] = None,
) -> Dict[str, Any]:
    """Long-running: resolve docs, bulk extract, aggregate per company, follow-on, DPI Sankey."""
    try:
        from app.core.adapters import get_storage, get_document_repo, get_company_repo
        from app.services.company_history_analysis_service import run as run_pipeline

        def progress_cb(progress: Dict[str, Any]) -> None:
            self.update_state(state="PROGRESS", meta=progress)

        storage = get_storage()
        document_repo = get_document_repo()
        company_repo = get_company_repo()
        result = run_pipeline(
            fund_id=fund_id,
            company_ids=company_ids,
            document_ids=document_ids,
            storage=storage,
            document_repo=document_repo,
            company_repo=company_repo,
            progress_callback=progress_cb,
        )
        return {"status": "success", "result": result}
    except Exception as e:
        logger.exception("Company history analysis failed: %s", e)
        return {"status": "error", "error": str(e)}


@celery_app.task(bind=True, name="app.tasks.periodic.cleanup")
def cleanup_old_data(self):
    """Periodic task to cleanup old data"""
    try:
        logger.info("Running periodic cleanup")
        
        # Cleanup logic here
        # - Remove old documents
        # - Clear expired cache
        # - Archive old analysis results
        
        return {
            "status": "success",
            "message": "Cleanup completed"
        }
        
    except Exception as e:
        logger.error(f"Cleanup failed: {e}")
        return {
            "status": "error",
            "error": str(e)
        }


# Periodic tasks schedule
from celery.schedules import crontab

celery_app.conf.beat_schedule = {
    "cleanup-old-data": {
        "task": "app.tasks.periodic.cleanup",
        "schedule": crontab(hour=2, minute=0),  # Run at 2 AM daily
    },
    "update-market-data": {
        "task": "app.tasks.market.research",
        "schedule": crontab(hour="*/6"),  # Every 6 hours
        "args": ("technology market trends", None, "Technology")
    }
}