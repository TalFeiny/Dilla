"""
Celery configuration for background tasks
"""

from celery import Celery
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)

# Create Celery instance
celery_app = Celery(
    "dilla_ai",
    broker=settings.REDIS_URL or "redis://localhost:6379/0",
    backend=settings.REDIS_URL or "redis://localhost:6379/0",
    include=["app.tasks"]
)

# Configure Celery
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=30 * 60,  # 30 minutes
    task_soft_time_limit=25 * 60,  # 25 minutes
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=1000,
)

# Task routing
celery_app.conf.task_routes = {
    "app.tasks.analysis.*": {"queue": "analysis"},
    "app.tasks.document.*": {"queue": "documents"},
    "app.tasks.market.*": {"queue": "market"},
    "app.tasks.agent.*": {"queue": "agents"},
}

# Task rate limits
celery_app.conf.task_annotations = {
    "app.tasks.market.research_market": {"rate_limit": "10/m"},
    "app.tasks.analysis.run_pwerm": {"rate_limit": "5/m"},
}