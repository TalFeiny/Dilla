"""
Celery background tasks
"""

from celery import Task
from app.core.celery_app import celery_app
from app.core.exceptions import RateLimitError
from app.services.pwerm_service import pwerm_service
try:
    from app.services.market_research_service import market_research_service
except ImportError:
    market_research_service = None  # Module removed; Celery task will handle gracefully
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
        if market_research_service is None:
            return {"status": "error", "error": "market_research_service not available"}
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


@celery_app.task(bind=True, base=CallbackTask, name="app.tasks.agent.run_scheduled")
def run_scheduled_agent_task(self, task_id: str) -> Dict[str, Any]:
    """Execute a persisted agent_task by calling the appropriate brain endpoint.

    Called by RedBeat on the stored cron schedule, or directly for one-shot tasks.
    Reads task definition from Supabase, calls the brain, writes result back.
    If notify_chat=True the result is broadcast via WebSocket so it surfaces
    in the chat panel like the proactive auto-brief.
    """
    import asyncio
    import httpx
    from datetime import datetime, timezone as dt_tz

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    async def _run():
        from app.core.supabase_client import get_supabase_client
        sb = get_supabase_client()
        if not sb:
            return {"status": "error", "error": "No Supabase client"}

        # Fetch task definition
        res = sb.table("agent_tasks").select("*").eq("id", task_id).single().execute()
        if not res.data:
            return {"status": "error", "error": f"Task {task_id} not found"}

        task = res.data
        if task["status"] not in ("active",):
            return {"status": "skipped", "reason": task["status"]}

        params = task.get("params") or {}
        task_type = task["task_type"]
        fund_id = params.get("fund_id") or task.get("fund_id")

        # Build the prompt for the brain based on task_type
        prompt_map = {
            "burn_rate_check": "Run a burn rate and runway check. Pull actuals, flag anomalies, surface any risks. Be direct.",
            "runway_alert": "Calculate current runway. If under 12 months flag it as critical. Give exact numbers.",
            "portfolio_health": "Run a portfolio health check. Score each company, flag anything that needs attention.",
            "market_research": params.get("query", "Run a market research update for this fund's sectors."),
            "valuation_refresh": "Refresh valuations for all portfolio companies with recent data.",
            "custom_query": params.get("query", "Run your standard CFO brief."),
        }
        prompt = prompt_map.get(task_type, params.get("query", "Run your standard CFO brief."))

        # Determine which brain endpoint to use
        mode = params.get("mode", "pnl")
        import os
        base_url = os.environ.get("INTERNAL_API_URL", "http://localhost:8000")
        endpoint = "/api/agent/cfo-brain" if mode == "pnl" else "/api/agent/unified-brain"

        payload = {
            "message": prompt,
            "fund_id": fund_id,
            "mode": mode,
            "context": {**params, "scheduled_task_id": task_id, "task_type": task_type},
        }

        result_text = ""
        error = None
        try:
            async with httpx.AsyncClient(timeout=300) as client:
                resp = await client.post(f"{base_url}{endpoint}", json=payload)
                resp.raise_for_status()
                data = resp.json()
                result_text = data.get("response") or data.get("message") or str(data)[:2000]
        except Exception as e:
            error = str(e)
            logger.error(f"[run_scheduled_agent_task] Brain call failed for {task_id}: {e}")

        now = datetime.now(dt_tz.utc).isoformat()
        run_status = "error" if error else "success"

        # Update task record
        sb.table("agent_tasks").update({
            "last_run_at": now,
            "last_run_status": run_status,
            "last_run_result": {"text": result_text, "error": error},
            "run_count": (task.get("run_count") or 0) + 1,
            "error_count": (task.get("error_count") or 0) + (1 if error else 0),
            "last_error": error,
            # One-shot tasks: mark done after first run
            **({"status": "done"} if not task.get("cron_expr") else {}),
        }).eq("id", task_id).execute()

        # Delivery is handled by Supabase Realtime — the UPDATE above triggers
        # a postgres_changes event that the frontend subscribes to in AgentChat.
        # No WebSocket broadcast needed here (worker is a separate process).

        return {"status": run_status, "task_id": task_id, "error": error}

    result = loop.run_until_complete(_run())
    loop.close()
    return result


# All schedules are dynamic via RedBeat — created by the agent at runtime.
# No static beat_schedule needed.