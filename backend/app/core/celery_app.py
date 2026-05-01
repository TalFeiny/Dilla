"""
Celery configuration for background tasks
"""

from celery import Celery
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)

_broker = settings.REDIS_URL or "redis://localhost:6379/0"

# Create Celery instance
celery_app = Celery(
    "dilla_ai",
    broker=_broker,
    backend=_broker,
    include=["app.tasks"]
)

# Configure Celery — use RedBeatScheduler so agent_tasks written to Redis
# at runtime are picked up by beat without a restart.
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=30 * 60,
    task_soft_time_limit=25 * 60,
    worker_prefetch_multiplier=2,
    worker_max_tasks_per_child=1000,
    worker_concurrency=4,
    # RedBeat: dynamic beat schedules stored in Redis
    beat_scheduler="redbeat.RedBeatScheduler",
    redbeat_redis_url=_broker,
    redbeat_lock_timeout=10 * 60,  # 10 min — longer than any single task
)

# Single default queue — one worker drains everything.
# Long-running tasks (company history) get their own time limit via annotations.
celery_app.conf.task_annotations = {
    "app.tasks.analysis.run_company_history": {"time_limit": 60 * 60, "soft_time_limit": 55 * 60},
}