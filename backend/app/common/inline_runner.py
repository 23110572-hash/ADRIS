"""In-process background execution of durable analysis jobs (Option B).

Instead of publishing jobs to a broker for a separate Celery worker to consume,
the API process runs them itself on a bounded thread pool. The HTTP request that
creates a job returns immediately while the job is executed in the background.

The Celery task functions in ``worker.tasks`` remain the single source of truth
for the pipeline. We invoke them eagerly with ``Task.apply`` (no broker, no
worker) so all the existing durability, locking, progress, retry and chaining
logic is reused unchanged. Retries requested by a task (which set the durable job
back to ``PENDING``) are honoured by re-submitting the job here, bounded by the
job's own ``max_attempts`` guard in ``worker.tasks._begin_job``.
"""

from __future__ import annotations

import threading
import uuid
from concurrent.futures import ThreadPoolExecutor

import structlog

logger = structlog.get_logger(__name__)

# I/O-bound work (Postgres, Redis, Groq, S3), so a small thread pool is plenty and
# keeps the web process responsive. Runs per API worker process.
_MAX_WORKERS = 4
_MAX_RESUBMITS = 5
_executor = ThreadPoolExecutor(max_workers=_MAX_WORKERS, thread_name_prefix="adris-inline")


def _resolve_task(task_name: str):
    # Imported lazily: worker.tasks imports app.common.jobs, so a module-level import
    # here would create a cycle. The import also registers the tasks on the Celery app.
    from worker import tasks as _tasks  # noqa: F401  (side effect: registers tasks)
    from worker.celery_app import celery_app

    return celery_app.tasks.get(task_name)


def _run(task_name: str, job_id: str, attempt: int) -> None:
    task = _resolve_task(task_name)
    if task is None:
        logger.error("inline_task_unknown", task_name=task_name, job_id=job_id)
        return
    try:
        # Eager, synchronous execution in this background thread. The task updates the
        # durable AnalysisJob row itself (status/progress/errors), just as under a worker.
        task.apply(args=[job_id])
    except Exception:
        logger.exception("inline_task_crashed", task_name=task_name, job_id=job_id)
        return
    _maybe_resubmit(task_name, job_id, attempt)


def _maybe_resubmit(task_name: str, job_id: str, attempt: int) -> None:
    """Re-run a job if the task left it retryable (status back to PENDING)."""
    if attempt >= _MAX_RESUBMITS:
        return
    from app.db.models import AnalysisJob
    from app.db.session import SessionLocal

    try:
        with SessionLocal() as db:
            job = db.get(AnalysisJob, uuid.UUID(job_id))
            if job is None or job.status != "PENDING" or job.attempts >= job.max_attempts:
                return
    except Exception:
        logger.exception("inline_resubmit_check_failed", task_name=task_name, job_id=job_id)
        return
    delay = min(30.0, 5.0 * (attempt + 1))
    logger.info("inline_task_retry_scheduled", task_name=task_name, job_id=job_id, delay=delay, attempt=attempt + 1)
    submit(task_name, job_id, attempt=attempt + 1, countdown=int(delay))


def submit(task_name: str, job_id: str, *, attempt: int = 0, countdown: int | None = None) -> None:
    """Schedule a durable job to run in the background. Non-blocking."""
    if countdown and countdown > 0:
        timer = threading.Timer(float(countdown), lambda: _executor.submit(_run, task_name, job_id, attempt))
        timer.daemon = True
        timer.start()
        return
    _executor.submit(_run, task_name, job_id, attempt)


def reconcile_pending_jobs() -> int:
    """Submit any durable jobs left in PENDING (e.g. after a restart) for execution.

    Called on API startup so a backlog drains automatically and no submission is
    stranded when there is no separate worker/beat to reconcile.
    """
    from datetime import UTC, datetime

    from sqlalchemy import select

    from app.common.jobs import TASK_BY_JOB_TYPE
    from app.db.models import AnalysisJob
    from app.db.session import SessionLocal

    targets: list[tuple[str, str]] = []
    try:
        with SessionLocal() as db:
            now = datetime.now(UTC)
            jobs = db.scalars(
                select(AnalysisJob)
                .where(
                    AnalysisJob.status == "PENDING",
                    AnalysisJob.available_at <= now,
                    AnalysisJob.attempts < AnalysisJob.max_attempts,
                )
                .order_by(AnalysisJob.created_at)
                .limit(100)
            ).all()
            for job in jobs:
                task_name = TASK_BY_JOB_TYPE.get(job.job_type)
                if task_name:
                    targets.append((task_name, str(job.id)))
    except Exception:
        logger.exception("inline_reconcile_query_failed")
        return 0
    for task_name, job_id in targets:
        submit(task_name, job_id)
    return len(targets)
