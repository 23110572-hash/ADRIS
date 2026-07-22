import ssl

from celery import Celery
from celery.schedules import crontab

from app.common.config import get_settings
from app.common.logging import configure_logging

settings = get_settings()
configure_logging(settings.log_level)

# Managed Redis providers such as Upstash require TLS (rediss://). kombu needs ssl_cert_reqs
# specified explicitly for both the broker and the result backend or it fails on startup.
_uses_tls = settings.redis_url.startswith("rediss://")
_ssl_options = {"ssl_cert_reqs": ssl.CERT_REQUIRED} if _uses_tls else None

celery_app = Celery("adris", broker=settings.redis_url, backend=settings.redis_url, include=["worker.tasks"])
celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    task_track_started=True,
    result_expires=3600,
    broker_connection_retry_on_startup=True,
    broker_use_ssl=_ssl_options,
    redis_backend_use_ssl=_ssl_options,
    task_routes={
        "worker.tasks.validate_artifact": {"queue": "file-validation"},
        "worker.tasks.extract_ocr": {"queue": "ocr"},
        "worker.tasks.transcribe_audio": {"queue": "transcription"},
        "worker.tasks.analyze_incident": {"queue": "agent-analysis"},
        "worker.tasks.project_graph": {"queue": "graph-analysis"},
        "worker.tasks.generate_export": {"queue": "evidence-export"},
    },
    beat_schedule={
        "reconcile-durable-jobs": {
            "task": "worker.tasks.reconcile_pending_jobs",
            "schedule": 60.0,
        },
        "refresh-geo-aggregates": {
            "task": "worker.tasks.refresh_geo_aggregates",
            "schedule": crontab(minute="*/15"),
        },
    },
)
