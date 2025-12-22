"""Celery application configuration for the Orcheo execution worker."""

from __future__ import annotations
import os
from celery import Celery


celery_app = Celery(
    "orcheo-backend",
    broker=os.getenv("REDIS_URL", "redis://localhost:6379/0"),
    backend=None,  # No result backend needed for fire-and-forget
    include=["orcheo_backend.worker.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,  # Acknowledge after execution completes
    worker_prefetch_multiplier=1,  # Fetch one task at a time for fairness
)

# Celery Beat schedule for cron dispatch
celery_app.conf.beat_schedule = {
    "dispatch-cron-triggers": {
        "task": "orcheo_backend.worker.tasks.dispatch_cron_triggers",
        "schedule": 60.0,  # Run every 60 seconds
    },
}

__all__ = ["celery_app"]
