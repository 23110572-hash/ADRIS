import hashlib
import json
import mimetypes
import uuid
from datetime import UTC, datetime, timedelta

import structlog
from celery.exceptions import Retry
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.agents.state import IncidentState, IndicatorState, SignalState
from app.agents.workflow import run_incident_workflow
from app.artifacts.storage import (
    get_object_bytes,
    put_private_bytes,
    validate_and_promote,
)
from app.audit.service import record_custody
from app.common.config import get_settings
from app.common.jobs import TASK_BY_JOB_TYPE, create_job, enqueue_job
from app.common.redis import distributed_lock, set_job_progress
from app.db.models import (
    ActionRecommendation,
    AnalysisJob,
    Artifact,
    ArtifactDerivative,
    Incident,
    Indicator,
    ReportExport,
    ReviewTask,
    RiskAssessment,
    Signal,
    Submission,
)
from app.db.session import SessionLocal
from app.evidence.service import generate_export_package
from app.extraction.deterministic import (
    ExtractedIndicator,
    decode_qr,
    deterministic_rule_signals,
    extract_indicators,
    image_metadata,
)
from app.extraction.providers import get_ocr_provider, get_transcription_provider
from app.geo.service import refresh_aggregates
from app.graph.service import project_incident_graph
from app.policy.engine import POLICY_VERSION, decide_risk
from worker.celery_app import celery_app

settings = get_settings()
logger = structlog.get_logger(__name__)


def _begin_job(db: Session, job_id: str) -> AnalysisJob | None:
    job = db.get(AnalysisJob, uuid.UUID(job_id))
    if job is None:
        raise ValueError("JOB_NOT_FOUND")
    if job.status == "COMPLETED":
        return None
    if job.attempts >= job.max_attempts:
        job.status = "FAILED"
        job.error_code = job.error_code or "MAX_ATTEMPTS_EXCEEDED"
        db.commit()
        return None
    job.status = "RUNNING"
    job.attempts += 1
    job.started_at = job.started_at or datetime.now(UTC)
    job.heartbeat_at = datetime.now(UTC)
    job.error_code = None
    job.error_detail = None
    db.commit()
    set_job_progress(str(job.id), job.progress_percent, "Running")
    return job


def _progress(db: Session, job: AnalysisJob, percent: int, message: str) -> None:
    job.progress_percent = percent
    job.progress_message = message
    job.heartbeat_at = datetime.now(UTC)
    db.commit()
    set_job_progress(str(job.id), percent, message)


def _complete(db: Session, job: AnalysisJob, message: str = "Completed") -> None:
    job.status = "COMPLETED"
    job.progress_percent = 100
    job.progress_message = message
    job.completed_at = datetime.now(UTC)
    job.error_detail = None
    db.commit()
    set_job_progress(str(job.id), 100, message)


def _retry_or_fail(task, db: Session, job: AnalysisJob, exc: Exception, *, countdown: int = 15):
    retryable = job.attempts < job.max_attempts
    job.status = "PENDING" if retryable else "FAILED"
    job.error_code = type(exc).__name__[:80]
    job.error_detail = str(exc)[:500]
    job.progress_message = "Retry scheduled" if retryable else "Failed"
    db.commit()
    logger.warning("job_failed", job_id=str(job.id), job_type=job.job_type, error_type=type(exc).__name__, retryable=retryable)
    if retryable:
        raise task.retry(exc=exc, countdown=countdown, max_retries=job.max_attempts - 1)
    raise exc


def _schedule_analysis(db: Session, incident_id: uuid.UUID, source_key: str) -> AnalysisJob:
    job, created = create_job(
        db,
        incident_id=incident_id,
        job_type="AGENT_ANALYSIS",
        idempotency_key=f"auto-analysis:{incident_id}:{source_key}",
    )
    if created or not job.celery_task_id:
        enqueue_job(db, job)
    return job


def _store_derivative(
    db: Session,
    *,
    artifact: Artifact,
    kind: str,
    content: bytes,
    mime_type: str,
    provider: str,
    provider_version: str,
    transformation_version: str,
    confidence: float | None,
    details: dict,
) -> ArtifactDerivative:
    existing = db.scalar(
        select(ArtifactDerivative).where(
            ArtifactDerivative.artifact_id == artifact.id,
            ArtifactDerivative.kind == kind,
            ArtifactDerivative.transformation_version == transformation_version,
        )
    )
    if existing:
        return existing
    digest = hashlib.sha256(content).hexdigest()
    extension = {"text/plain": "txt", "application/json": "json", "image/png": "png"}.get(mime_type, "bin")
    key = f"derivatives/{artifact.incident_id}/{artifact.id}/{kind.lower()}-{digest[:12]}.{extension}"
    put_private_bytes(
        settings.s3_derivatives_bucket,
        key,
        content,
        mime_type,
        {"incident-id": str(artifact.incident_id), "artifact-id": str(artifact.id), "sha256": digest},
    )
    derivative = ArtifactDerivative(
        incident_id=artifact.incident_id,
        artifact_id=artifact.id,
        kind=kind,
        provider=provider,
        provider_version=provider_version,
        transformation_version=transformation_version,
        bucket=settings.s3_derivatives_bucket,
        object_key=key,
        mime_type=mime_type,
        size_bytes=len(content),
        sha256=digest,
        confidence=confidence,
        source_reference=f"artifact:{artifact.id}",
        details=details,
        correlation_id=artifact.correlation_id,
    )
    db.add(derivative)
    db.flush()
    record_custody(
        db,
        incident_id=artifact.incident_id,
        artifact_id=artifact.id,
        event_type="DERIVATIVE_CREATED",
        from_location=f"s3://{artifact.evidence_bucket}/{artifact.evidence_key}",
        to_location=f"s3://{settings.s3_derivatives_bucket}/{key}",
        details={"derivative_id": str(derivative.id), "kind": kind, "sha256": digest, "transformation_version": transformation_version},
        correlation_id=artifact.correlation_id,
    )
    return derivative


@celery_app.task(bind=True, name="worker.tasks.validate_artifact", max_retries=2)
def validate_artifact(self, job_id: str) -> dict:
    with distributed_lock(f"job:{job_id}", ttl_seconds=600) as acquired:
        if not acquired:
            return {"status": "duplicate_suppressed"}
        with SessionLocal() as db:
            job = _begin_job(db, job_id)
            if job is None:
                return {"status": "already_completed"}
            artifact = db.get(Artifact, job.artifact_id)
            if artifact is None:
                return _retry_or_fail(self, db, job, ValueError("ARTIFACT_NOT_FOUND"))
            try:
                artifact.status = "VALIDATING"
                _progress(db, job, 20, "Validating private upload")
                result = validate_and_promote(
                    incident_id=artifact.incident_id,
                    artifact_id=artifact.id,
                    quarantine_key_value=artifact.quarantine_key,
                    expected_mime=artifact.expected_mime_type,
                    expected_max_bytes=settings.max_upload_bytes,
                )
                artifact.status = "ACCEPTED"
                artifact.detected_mime_type = result.detected_mime_type
                artifact.size_bytes = result.size_bytes
                artifact.sha256 = result.sha256
                artifact.evidence_bucket = settings.s3_evidence_bucket
                artifact.evidence_key = result.evidence_key
                artifact.evidence_version_id = result.evidence_version_id
                artifact.quarantine_version_id = result.quarantine_version_id
                artifact.receipt_at = datetime.now(UTC)
                artifact.validated_at = datetime.now(UTC)
                artifact.trusted_metadata = {
                    "schema_version": "trusted-receipt-v1",
                    "server_computed_sha256": result.sha256,
                    "content_length": result.size_bytes,
                    "detected_mime_type": result.detected_mime_type,
                }
                record_custody(
                    db,
                    incident_id=artifact.incident_id,
                    artifact_id=artifact.id,
                    event_type="ORIGINAL_VALIDATED_AND_PROMOTED",
                    from_location=f"s3://{artifact.quarantine_bucket}/{artifact.quarantine_key}",
                    to_location=f"s3://{artifact.evidence_bucket}/{artifact.evidence_key}",
                    details={"sha256": result.sha256, "size_bytes": result.size_bytes, "detected_mime_type": result.detected_mime_type},
                    correlation_id=artifact.correlation_id,
                )
                db.commit()
                incident = db.get(Incident, artifact.incident_id)
                if incident and incident.submission_type == "AUDIO":
                    next_type = "TRANSCRIPTION"
                elif incident and incident.submission_type in {"SCREENSHOT", "DOCUMENT", "QR"}:
                    next_type = "OCR"
                else:
                    next_type = "AGENT_ANALYSIS"
                if next_type == "AGENT_ANALYSIS":
                    _schedule_analysis(db, artifact.incident_id, str(artifact.id))
                else:
                    next_job, created = create_job(
                        db,
                        incident_id=artifact.incident_id,
                        artifact_id=artifact.id,
                        job_type=next_type,
                        idempotency_key=f"{next_type.lower()}:{artifact.id}:{artifact.sha256}",
                    )
                    if created or not next_job.celery_task_id:
                        enqueue_job(db, next_job)
                _complete(db, job, "Artifact validated and preserved")
                return {"status": "completed", "artifact_id": str(artifact.id), "sha256": artifact.sha256}
            except ValueError as exc:
                if str(exc) in {"INVALID_FILE_SIZE", "UPLOAD_METADATA_MISMATCH", "CONTENT_TYPE_MISMATCH"}:
                    artifact.status = "REJECTED"
                    artifact.rejection_reason = str(exc)
                    job.status = "FAILED"
                    job.error_code = str(exc)
                    job.error_detail = "Artifact failed deterministic validation"
                    job.completed_at = datetime.now(UTC)
                    db.commit()
                    return {"status": "rejected", "reason": str(exc)}
                return _retry_or_fail(self, db, job, exc)
            except Retry:
                raise
            except Exception as exc:
                return _retry_or_fail(self, db, job, exc)


@celery_app.task(bind=True, name="worker.tasks.extract_ocr", max_retries=2)
def extract_ocr(self, job_id: str) -> dict:
    with distributed_lock(f"job:{job_id}", ttl_seconds=900) as acquired:
        if not acquired:
            return {"status": "duplicate_suppressed"}
        with SessionLocal() as db:
            job = _begin_job(db, job_id)
            if job is None:
                return {"status": "already_completed"}
            artifact = db.get(Artifact, job.artifact_id)
            if artifact is None or artifact.status != "ACCEPTED" or not artifact.evidence_bucket or not artifact.evidence_key:
                return _retry_or_fail(self, db, job, ValueError("ARTIFACT_NOT_READY"))
            try:
                _progress(db, job, 20, "Reading preserved original")
                content = get_object_bytes(artifact.evidence_bucket, artifact.evidence_key)
                incident = db.get(Incident, artifact.incident_id)
                unavailable: list[str] = []
                if (artifact.detected_mime_type or "").startswith("image/"):
                    try:
                        metadata = image_metadata(content)
                        _store_derivative(
                            db,
                            artifact=artifact,
                            kind="IMAGE_METADATA",
                            content=json.dumps(metadata, sort_keys=True).encode(),
                            mime_type="application/json",
                            provider="PILLOW",
                            provider_version="11",
                            transformation_version="image-metadata-v1",
                            confidence=1.0,
                            details={"metadata_version": "image-metadata-v1"},
                        )
                    except Exception:
                        unavailable.append("IMAGE_METADATA_EXTRACTION_FAILED")
                    if incident and incident.submission_type == "QR":
                        payload, confidence = decode_qr(content)
                        if payload:
                            _store_derivative(
                                db,
                                artifact=artifact,
                                kind="QR_PAYLOAD",
                                content=payload.encode("utf-8"),
                                mime_type="text/plain",
                                provider="OPENCV_QR",
                                provider_version="4.11",
                                transformation_version="qr-decode-v1",
                                confidence=confidence,
                                details={"payload_length": len(payload)},
                            )
                        else:
                            unavailable.append("QR_PAYLOAD_NOT_DECODED")
                _progress(db, job, 55, "Running OCR provider")
                result = get_ocr_provider().extract(content)
                if result.text:
                    _store_derivative(
                        db,
                        artifact=artifact,
                        kind="OCR_TEXT",
                        content=result.text.encode("utf-8"),
                        mime_type="text/plain",
                        provider=result.provider,
                        provider_version=result.provider_version,
                        transformation_version="ocr-v1",
                        confidence=result.confidence,
                        details={"text_length": len(result.text)},
                    )
                elif result.unavailable_reason:
                    unavailable.append(result.unavailable_reason)
                db.commit()
                if unavailable:
                    job.error_code = ",".join(unavailable)[:80]
                _schedule_analysis(db, artifact.incident_id, str(artifact.id))
                _complete(db, job, "Extraction complete with declared gaps" if unavailable else "OCR extraction complete")
                return {"status": "completed", "unavailable_sources": unavailable}
            except Retry:
                raise
            except Exception as exc:
                return _retry_or_fail(self, db, job, exc, countdown=30)


@celery_app.task(bind=True, name="worker.tasks.transcribe_audio", max_retries=2)
def transcribe_audio(self, job_id: str) -> dict:
    with distributed_lock(f"job:{job_id}", ttl_seconds=1800) as acquired:
        if not acquired:
            return {"status": "duplicate_suppressed"}
        with SessionLocal() as db:
            job = _begin_job(db, job_id)
            if job is None:
                return {"status": "already_completed"}
            artifact = db.get(Artifact, job.artifact_id)
            if artifact is None or artifact.status != "ACCEPTED" or not artifact.evidence_bucket or not artifact.evidence_key:
                return _retry_or_fail(self, db, job, ValueError("ARTIFACT_NOT_READY"))
            try:
                _progress(db, job, 25, "Reading consented audio")
                content = get_object_bytes(artifact.evidence_bucket, artifact.evidence_key)
                suffix = mimetypes.guess_extension(artifact.detected_mime_type or artifact.expected_mime_type) or ".audio"
                result = get_transcription_provider().transcribe(content, suffix)
                unavailable: list[str] = []
                if result.text:
                    _store_derivative(
                        db,
                        artifact=artifact,
                        kind="TRANSCRIPT",
                        content=result.text.encode("utf-8"),
                        mime_type="text/plain",
                        provider=result.provider,
                        provider_version=result.provider_version,
                        transformation_version="transcription-v1",
                        confidence=result.confidence,
                        details={"text_length": len(result.text), "consented_audio": True},
                    )
                else:
                    unavailable.append(result.unavailable_reason or "TRANSCRIPTION_EMPTY")
                    job.error_code = unavailable[0]
                db.commit()
                _schedule_analysis(db, artifact.incident_id, str(artifact.id))
                _complete(db, job, "Transcription complete with declared gap" if unavailable else "Transcription complete")
                return {"status": "completed", "unavailable_sources": unavailable}
            except Retry:
                raise
            except Exception as exc:
                return _retry_or_fail(self, db, job, exc, countdown=60)


def _persist_indicator(db: Session, incident: Incident, value: ExtractedIndicator, derivative_id: uuid.UUID | None = None) -> Indicator:
    existing = db.scalar(
        select(Indicator).where(
            Indicator.incident_id == incident.id,
            Indicator.indicator_type == value.indicator_type,
            Indicator.normalized_value_hash == value.value_hash,
            Indicator.source_reference == value.source_reference,
        )
    )
    if existing:
        return existing
    indicator = Indicator(
        incident_id=incident.id,
        derivative_id=derivative_id,
        indicator_type=value.indicator_type,
        normalized_value=value.normalized_value,
        normalized_value_hash=value.value_hash,
        masked_value=value.masked_value,
        confidence=value.confidence,
        source_reference=value.source_reference,
        extractor_version=value.extractor_version,
        correlation_id=incident.correlation_id,
    )
    db.add(indicator)
    return indicator


def _collect_text_and_extract(db: Session, incident: Incident) -> tuple[list[str], list[str]]:
    texts: list[str] = []
    unavailable: list[str] = []
    submissions = db.scalars(select(Submission).where(Submission.incident_id == incident.id).order_by(Submission.created_at)).all()
    for item in submissions:
        if item.text_content:
            texts.append(item.text_content)
            for extracted in extract_indicators(item.text_content, f"submission:{item.id}"):
                _persist_indicator(db, incident, extracted)
    derivatives = db.scalars(
        select(ArtifactDerivative).where(
            ArtifactDerivative.incident_id == incident.id,
            ArtifactDerivative.kind.in_(["OCR_TEXT", "TRANSCRIPT", "QR_PAYLOAD"]),
        ).order_by(ArtifactDerivative.created_at)
    ).all()
    for item in derivatives:
        try:
            text = get_object_bytes(item.bucket, item.object_key, max_bytes=5 * 1024 * 1024).decode("utf-8", errors="replace")
            texts.append(text)
            for extracted in extract_indicators(text, f"derivative:{item.id}"):
                _persist_indicator(db, incident, extracted, item.id)
            if item.kind == "QR_PAYLOAD":
                value = ExtractedIndicator(
                    indicator_type="QR_PAYLOAD",
                    normalized_value=text.strip(),
                    masked_value=(text[:8] + "…") if len(text) > 8 else text,
                    confidence=item.confidence or 0.9,
                    source_reference=f"derivative:{item.id}",
                )
                _persist_indicator(db, incident, value, item.id)
        except Exception:
            unavailable.append(f"DERIVATIVE_READ_FAILED:{item.kind}")
    extraction_jobs = db.scalars(
        select(AnalysisJob).where(
            AnalysisJob.incident_id == incident.id,
            AnalysisJob.job_type.in_(["OCR", "TRANSCRIPTION"]),
            AnalysisJob.error_code.is_not(None),
        )
    ).all()
    for extraction_job in extraction_jobs:
        unavailable.extend(part for part in (extraction_job.error_code or "").split(",") if part)
    return texts, list(dict.fromkeys(unavailable))


@celery_app.task(bind=True, name="worker.tasks.analyze_incident", max_retries=1)
def analyze_incident(self, job_id: str) -> dict:
    with distributed_lock(f"analysis:{job_id}", ttl_seconds=1200) as acquired:
        if not acquired:
            return {"status": "duplicate_suppressed"}
        with SessionLocal() as db:
            job = _begin_job(db, job_id)
            if job is None:
                return {"status": "already_completed"}
            incident = db.get(Incident, job.incident_id)
            if incident is None:
                return _retry_or_fail(self, db, job, ValueError("INCIDENT_NOT_FOUND"))
            try:
                incident.status = "PROCESSING"
                _progress(db, job, 10, "Running deterministic extraction")
                texts, unavailable = _collect_text_and_extract(db, incident)
                db.flush()
                indicators = db.scalars(select(Indicator).where(Indicator.incident_id == incident.id, Indicator.status == "ACTIVE")).all()
                deterministic = []
                for index, text in enumerate(texts):
                    deterministic.extend(deterministic_rule_signals(text, f"extracted_text:{index}"))
                signal_states = [SignalState.model_validate(item) for item in deterministic]
                artifact_refs = [
                    f"artifact:{artifact.id}"
                    for artifact in db.scalars(select(Artifact).where(Artifact.incident_id == incident.id, Artifact.status == "ACCEPTED")).all()
                ]
                initial = IncidentState(
                    incident_id=str(incident.id),
                    language=incident.language,
                    artifact_references=artifact_refs,
                    extracted_text=texts,
                    indicators=[
                        IndicatorState(
                            indicator_type=item.indicator_type,
                            normalized_value_hash=item.normalized_value_hash,
                            masked_value=item.masked_value,
                            confidence=item.confidence,
                            source_reference=item.source_reference,
                        )
                        for item in indicators
                    ],
                    scam_signals=signal_states,
                    unavailable_sources=unavailable,
                )
                db.commit()  # make deterministic extraction visible to allowlisted graph queries
                _progress(db, job, 35, "Running bounded LLM agent workflow")
                # ADRIS requires the Groq agents. If the LLM workflow fails, the job fails and retries;
                # no risk assessment is produced without the LLM.
                final_state = run_incident_workflow(initial)
                decision = decide_risk(
                    signals=final_state.scam_signals,
                    input_quality=final_state.input_quality,
                    unavailable_sources=final_state.unavailable_sources,
                    agent_disagreement=final_state.agent_disagreement,
                )
                _progress(db, job, 75, "Applying deterministic risk policy")
                db.execute(
                    update(RiskAssessment)
                    .where(RiskAssessment.incident_id == incident.id, RiskAssessment.status == "CURRENT")
                    .values(status="SUPERSEDED")
                )
                for item in final_state.scam_signals:
                    existing = db.scalar(
                        select(Signal).where(
                            Signal.incident_id == incident.id,
                            Signal.code == item.code,
                            Signal.evidence_reference == item.evidence_reference,
                        )
                    )
                    if existing:
                        continue
                    db.add(
                        Signal(
                            incident_id=incident.id,
                            agent_run_id=uuid.UUID(item.agent_run_id) if item.agent_run_id else None,
                            code=item.code,
                            family=item.family,
                            severity=item.severity,
                            strength=item.strength,
                            source=item.source,
                            evidence_reference=item.evidence_reference,
                            explanation=item.explanation,
                            confidence=item.confidence,
                            correlation_id=incident.correlation_id,
                        )
                    )
                explanation = final_state.proposed_explanation if final_state.final_risk_band == decision.risk_band else decision.explanation
                assessment = RiskAssessment(
                    incident_id=incident.id,
                    risk_band=decision.risk_band,
                    policy_version=POLICY_VERSION,
                    reason_codes=decision.reason_codes,
                    coverage=decision.coverage,
                    missing_sources=decision.missing_sources,
                    agent_disagreement=decision.agent_disagreement,
                    explanation=explanation or decision.explanation,
                    safety_actions=decision.safety_actions,
                    input_quality=final_state.input_quality,
                    model_summary={"agent_run_ids": [item.run_id for item in final_state.agent_runs], "groq_model": settings.groq_model or None},
                    correlation_id=incident.correlation_id,
                )
                db.add(assessment)
                db.flush()
                incident.input_quality = final_state.input_quality
                incident.status = "COMPLETED"
                if decision.risk_band in {"HIGH_RISK", "CAUTION", "UNABLE_TO_ASSESS"}:
                    priority = "P1" if decision.risk_band == "HIGH_RISK" else "P2" if decision.risk_band == "UNABLE_TO_ASSESS" else "P3"
                    existing_review = db.scalar(select(ReviewTask).where(ReviewTask.incident_id == incident.id, ReviewTask.status == "OPEN"))
                    if existing_review is None:
                        db.add(
                            ReviewTask(
                                incident_id=incident.id,
                                assessment_id=assessment.id,
                                priority=priority,
                                reason=f"{decision.risk_band}: {', '.join(decision.reason_codes[:3])}",
                                correlation_id=incident.correlation_id,
                            )
                        )
                db.add(
                    ActionRecommendation(
                        incident_id=incident.id,
                        assessment_id=assessment.id,
                        action_type="CITIZEN_SAFETY_GUIDANCE",
                        recommendation="Use official reporting and bank contact channels; ADRIS does not execute institutional action.",
                        rationale_codes=decision.reason_codes,
                        authority_required=False,
                        correlation_id=incident.correlation_id,
                    )
                )
                db.commit()
                graph_job, created = create_job(
                    db,
                    incident_id=incident.id,
                    job_type="GRAPH_ANALYSIS",
                    idempotency_key=f"graph:{incident.id}:{assessment.id}",
                )
                if created or not graph_job.celery_task_id:
                    enqueue_job(db, graph_job)
                _complete(db, job, "Assessment ready")
                return {"status": "completed", "incident_id": str(incident.id), "risk_band": decision.risk_band}
            except Retry:
                raise
            except Exception as exc:
                # If the LLM analysis cannot complete, retry; once retries are exhausted the incident
                # ends in a terminal ANALYSIS_FAILED state instead of receiving a non-LLM assessment.
                retryable = job.attempts < job.max_attempts
                incident.status = "PROCESSING_DELAYED" if retryable else "ANALYSIS_FAILED"
                db.commit()
                return _retry_or_fail(self, db, job, exc, countdown=60)


@celery_app.task(bind=True, name="worker.tasks.project_graph", max_retries=2)
def project_graph(self, job_id: str) -> dict:
    with distributed_lock(f"job:{job_id}", ttl_seconds=600) as acquired:
        if not acquired:
            return {"status": "duplicate_suppressed"}
        with SessionLocal() as db:
            job = _begin_job(db, job_id)
            if job is None:
                return {"status": "already_completed"}
            try:
                incident = db.get(Incident, job.incident_id)
                if incident is None:
                    raise ValueError("INCIDENT_NOT_FOUND")
                count = project_incident_graph(db, incident)
                db.commit()
                _complete(db, job, f"Projected {count} governed relationships")
                return {"status": "completed", "relationship_count": count}
            except Retry:
                raise
            except Exception as exc:
                return _retry_or_fail(self, db, job, exc)


@celery_app.task(bind=True, name="worker.tasks.generate_export", max_retries=2)
def generate_export(self, job_id: str) -> dict:
    with distributed_lock(f"job:{job_id}", ttl_seconds=1200) as acquired:
        if not acquired:
            return {"status": "duplicate_suppressed"}
        with SessionLocal() as db:
            job = _begin_job(db, job_id)
            if job is None:
                return {"status": "already_completed"}
            export = db.get(ReportExport, job.export_id)
            if export is None:
                return _retry_or_fail(self, db, job, ValueError("EXPORT_NOT_FOUND"))
            try:
                _progress(db, job, 25, "Building manifest and chronology")
                generate_export_package(db, export)
                db.commit()
                _complete(db, job, "Evidence package ready")
                return {"status": "completed", "export_id": str(export.id), "sha256": export.sha256}
            except Retry:
                raise
            except Exception as exc:
                export.status = "FAILED"
                export.failure_code = type(exc).__name__[:80]
                db.commit()
                return _retry_or_fail(self, db, job, exc, countdown=30)


@celery_app.task(name="worker.tasks.reconcile_pending_jobs")
def reconcile_pending_jobs() -> dict:
    with distributed_lock("reconcile-pending-jobs", ttl_seconds=55) as acquired:
        if not acquired:
            return {"status": "duplicate_suppressed"}
        with SessionLocal() as db:
            now = datetime.now(UTC)
            stale = now - timedelta(minutes=5)
            jobs = db.scalars(
                select(AnalysisJob)
                .where(
                    AnalysisJob.status == "PENDING",
                    AnalysisJob.available_at <= now,
                    AnalysisJob.attempts < AnalysisJob.max_attempts,
                    (AnalysisJob.celery_task_id.is_(None)) | (AnalysisJob.updated_at < stale),
                )
                .order_by(AnalysisJob.created_at)
                .limit(100)
            ).all()
            enqueued = 0
            for job in jobs:
                task_name = TASK_BY_JOB_TYPE.get(job.job_type)
                if not task_name:
                    job.status = "FAILED"
                    job.error_code = "UNKNOWN_JOB_TYPE"
                    continue
                if enqueue_job(db, job):
                    enqueued += 1
            db.commit()
            return {"status": "completed", "reconciled": len(jobs), "enqueued": enqueued}


@celery_app.task(name="worker.tasks.refresh_geo_aggregates")
def refresh_geo_aggregates() -> dict:
    with distributed_lock("refresh-geo-aggregates", ttl_seconds=600) as acquired:
        if not acquired:
            return {"status": "duplicate_suppressed"}
        with SessionLocal() as db:
            count = refresh_aggregates(db)
            db.commit()
            return {"status": "completed", "aggregate_count": count}
