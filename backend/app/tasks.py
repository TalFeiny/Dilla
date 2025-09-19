"""
Celery background tasks
"""

from celery import Task
from app.core.celery_app import celery_app
from app.services.pwerm_service import pwerm_service
from app.services.document_service import document_processor
from app.services.market_research_service import market_research_service
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


@celery_app.task(bind=True, base=CallbackTask, name="app.tasks.document.process")
def process_document(
    self,
    document_id: str,
    file_path: str
) -> Dict[str, Any]:
    """Process document as background task"""
    try:
        self.update_state(state="PROGRESS", meta={"status": "Processing document"})
        
        # Process document
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        with open(file_path, 'rb') as f:
            content = f.read()
        
        metadata = loop.run_until_complete(
            document_processor.process_document(
                file_content=content,
                filename=file_path.split("/")[-1]
            )
        )
        
        return {
            "status": "success",
            "document_id": metadata.id,
            "processed": metadata.processed
        }
        
    except Exception as e:
        logger.error(f"Document processing failed: {e}")
        return {
            "status": "error",
            "error": str(e)
        }


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