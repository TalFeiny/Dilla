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
    worker_prefetch_multiplier=2,
    worker_max_tasks_per_child=1000,
    worker_concurrency=4,
)

# Task routing
celery_app.conf.task_routes = {
    "app.tasks.analysis.*": {"queue": "analysis"},
    "app.tasks.document.*": {"queue": "documents"},
    "app.tasks.market.*": {"queue": "market"},
    "app.tasks.agent.*": {"queue": "agents"},
}
# Task annotations: rate limits and long-running company-history (60 min)
celery_app.conf.task_annotations = {
    "app.tasks.market.research": {"rate_limit": "10/m"},
    "app.tasks.analysis.run_pwerm": {"rate_limit": "5/m"},
    "app.tasks.analysis.run_company_history": {"time_limit": 60 * 60, "soft_time_limit": 55 * 60},
    "app.tasks.document.process": {"rate_limit": "20/m"},  # Bumped from 5/m — model_router handles its own rate limiting
}