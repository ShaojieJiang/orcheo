"""Celery worker module for Orcheo backend."""

from orcheo_backend.worker.celery_app import celery_app


__all__ = ["celery_app"]
