import uuid
from datetime import UTC, datetime

import structlog
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import AnalysisJob
from worker.celery_app import celery_app

logger = structlog.get_logger(__name__)

TASK_BY_JOB_TYPE = {
    "FILE_VALIDATION": "worker.tasks.validate_artifact",
    "OCR": "worker.tasks.extract_ocr",
    "TRANSCRIPTION": "worker.tasks.transcribe_audio",
    "AGENT_ANALYSIS": "worker.tasks.analyze_incident",
    "GRAPH_ANALYSIS": "worker.tasks.project_graph",
    "EVIDENCE_EXPORT": "worker.tasks.generate_export",
}
QUEUE_BY_JOB_TYPE = {
    "FILE_VALIDATION": "file-validation",
    "OCR": "ocr",
    "TRANSCRIPTION": "transcription",
    "AGENT_ANALYSIS": "agent-analysis",
    "GRAPH_ANALYSIS": "graph-analysis",
    "EVIDENCE_EXPORT": "evidence-export",
}


def create_job(
    db: Session,
    *,
    incident_id: uuid.UUID,
    job_type: str,
    idempotency_key: str,
    artifact_id: uuid.UUID | None = None,
    export_id: uuid.UUID | None = None,
    retry_of_job_id: uuid.UUID | None = None,
    available_at: datetime | None = None,
    max_attempts: int = 3,
) -> tuple[AnalysisJob, bool]:
    existing = db.scalar(
        select(AnalysisJob).where(
            AnalysisJob.idempotency_key == idempotency_key,
            AnalysisJob.job_type == job_type,
        )
    )
    if existing:
        return existing, False
    job = AnalysisJob(
        incident_id=incident_id,
        artifact_id=artifact_id,
        export_id=export_id,
        retry_of_job_id=retry_of_job_id,
        job_type=job_type,
        queue_name=QUEUE_BY_JOB_TYPE[job_type],
        idempotency_key=idempotency_key,
        available_at=available_at or datetime.now(UTC),
        max_attempts=max_attempts,
    )
    db.add(job)
    db.commit()  # Neon is authoritative: the durable job exists before broker publication.
    db.refresh(job)
    return job, True


def enqueue_job(db: Session, job: AnalysisJob, *, countdown: int | None = None) -> bool:
    task_name = TASK_BY_JOB_TYPE[job.job_type]
    try:
        result = celery_app.send_task(
            task_name,
            args=[str(job.id)],
            queue=job.queue_name,
            countdown=countdown,
        )
        job.celery_task_id = result.id
        job.progress_message = "Queued"
        db.commit()
        return True
    except Exception as exc:
        job.progress_message = "Awaiting broker reconciliation"
        job.error_code = "BROKER_UNAVAILABLE"
        db.commit()
        logger.warning(
            "job_enqueue_deferred",
            job_id=str(job.id),
            job_type=job.job_type,
            error_type=type(exc).__name__,
        )
        return False
