"""
Celery Application — конфигурация брокера Redis и backend результатов.
"""

from celery import Celery
from backend.src.config import settings

celery_app = Celery(
    "youtube_worker",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["backend.src.worker.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,            # подтверждаем только после выполнения
    worker_prefetch_multiplier=1,   # 1 задача на воркер — не перегружаем при тяжёлом FFmpeg
    task_soft_time_limit=600,       # 10 мин — мягкий лимит для FFmpeg
    task_time_limit=720,            # 12 мин — жёсткий kill
)
