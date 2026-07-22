import uuid

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.schemas import (
    AnalyzeResponse,
    ArtifactView,
    AssessmentView,
    DerivativeView,
    DownloadResponse,
    EventView,
    EvidenceView,
    ExportCreateRequest,
    ExportCreated,
    ExportView,
    IncidentCreate,
    IncidentCreated,
    IncidentStatusResponse,
    IncidentView,
    JobView,
    PreserveResponse,
    PresignUploadRequest,
    PresignUploadResponse,
    UploadCompleteRequest,
    UploadCompleteResponse,
)
from app.artifacts.storage import (
    assert_upload_allowed,
    create_presigned_upload,
    presign_download,
    quarantine_key,
)
from app.audit.service import record_audit, record_custody
from app.auth.dependencies import Principal, optional_principal
from app.auth.service import (
    authorize_incident,
    incident_access_token,
    incident_token_hash,
    resolve_user,
)
from app.common.config import get_settings
from app.common.idempotency import find_idempotent, save_idempotent
from app.common.jobs import create_job, enqueue_job
from app.common.redis import rate_limit
from app.db.models import (
    AnalysisJob,
    Artifact,
    ArtifactDerivative,
    AuditEvent,
    CustodyEvent,
    EvidenceManifest,
    Incident,
    ReportExport,
    RiskAssessment,
    Submission,
)
from app.db.session import get_db
from app.evidence.service import seal_manifest
from app.geo.service import validate_coarse_cell

router = APIRouter(prefix="/incidents", tags=["incidents"])
exports_router = APIRouter(prefix="/exports", tags=["exports"])
settings = get_settings()


def _incident_or_404(db: Session, incident_id: uuid.UUID) -> Incident:
    incident = db.get(Incident, incident_id)
    if incident is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Incident not found")
    return incident


def _authorize(
    db: Session,
    incident: Incident,
    principal: Principal,
    incident_token: str | None,
):
    user = resolve_user(db, principal)
    authorize_incident(incident, principal, incident_token, user)
    return user


def _latest_job(db: Session, incident_id: uuid.UUID) -> AnalysisJob | None:
    return db.scalar(
        select(AnalysisJob)
        .where(AnalysisJob.incident_id == incident_id)
        .order_by(AnalysisJob.created_at.desc())
    )


@router.post(
    "",
    response_model=IncidentCreated,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(rate_limit("incident-create", 20, 60))],
)
def create_incident(
    payload: IncidentCreate,
    request: Request,
    idempotency_key: str = Header(..., alias="Idempotency-Key", min_length=8, max_length=255),
    principal: Principal = Depends(optional_principal),
    db: Session = Depends(get_db),
) -> IncidentCreated:
    if not principal.authenticated and not settings.anonymous_incidents_enabled:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    scope = f"incident-create:{principal.subject}"
    request_data = payload.model_dump(mode="json")
    replay = find_idempotent(db, scope=scope, key=idempotency_key, payload=request_data)
    if replay:
        incident = _incident_or_404(db, uuid.UUID(replay.resource_id))
        job = _latest_job(db, incident.id)
        return IncidentCreated(
            id=incident.id,
            status=incident.status,
            submission_type=incident.submission_type,
            access_token=incident_access_token(incident.id) if not principal.authenticated else None,
            created_at=incident.created_at,
            analysis_job_id=job.id if job else None,
        )

    try:
        coarse_cell = validate_coarse_cell(payload.coarse_h3_cell)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    user = resolve_user(db, principal)
    incident = Incident(
        owner_user_id=user.id if user else None,
        status="DRAFT",
        submission_type=payload.submission_type.value,
        language=payload.language,
        title=payload.title,
        coarse_h3_cell=coarse_cell,
        district=payload.district,
        state=payload.state,
        correlation_id=uuid.UUID(request.state.correlation_id),
    )
    db.add(incident)
    db.flush()
    token = None
    if user is None:
        token = incident_access_token(incident.id)
        incident.access_token_hash = incident_token_hash(token)
    if payload.text:
        db.add(
            Submission(
                incident_id=incident.id,
                kind=payload.submission_type.value,
                text_content=payload.text,
                consent_confirmed=payload.consent_confirmed,
                correlation_id=incident.correlation_id,
            )
        )
        incident.status = "QUEUED"
    save_idempotent(
        db,
        scope=scope,
        key=idempotency_key,
        payload=request_data,
        resource_type="INCIDENT",
        resource_id=str(incident.id),
        response_code=status.HTTP_201_CREATED,
    )
    record_audit(
        db,
        event_type="INCIDENT_CREATED",
        resource_type="INCIDENT",
        resource_id=str(incident.id),
        purpose_code="CITIZEN_FRAUD_ASSESSMENT",
        correlation_id=incident.correlation_id,
        user=user,
        incident_id=incident.id,
        idempotency_key=idempotency_key,
        event_data={"submission_type": incident.submission_type, "has_text": bool(payload.text)},
        client_ip=request.client.host if request.client else None,
    )
    db.commit()
    db.refresh(incident)

    analysis_job = None
    if payload.text:
        analysis_job, created = create_job(
            db,
            incident_id=incident.id,
            job_type="AGENT_ANALYSIS",
            idempotency_key=f"incident-create-analysis:{incident.id}:{idempotency_key}",
        )
        if created or not analysis_job.celery_task_id:
            enqueue_job(db, analysis_job)
    return IncidentCreated(
        id=incident.id,
        status=incident.status,
        submission_type=incident.submission_type,
        access_token=token,
        created_at=incident.created_at,
        analysis_job_id=analysis_job.id if analysis_job else None,
    )


@router.get("/{incident_id}", response_model=IncidentView)
def get_incident(
    incident_id: uuid.UUID,
    incident_token: str | None = Header(default=None, alias="X-Incident-Token"),
    principal: Principal = Depends(optional_principal),
    db: Session = Depends(get_db),
) -> Incident:
    incident = _incident_or_404(db, incident_id)
    _authorize(db, incident, principal, incident_token)
    db.commit()
    return incident


@router.post(
    "/{incident_id}/uploads/presign",
    response_model=PresignUploadResponse,
    dependencies=[Depends(rate_limit("upload-presign", 30, 60))],
)
def presign_upload(
    incident_id: uuid.UUID,
    payload: PresignUploadRequest,
    incident_token: str | None = Header(default=None, alias="X-Incident-Token"),
    principal: Principal = Depends(optional_principal),
    db: Session = Depends(get_db),
) -> PresignUploadResponse:
    incident = _incident_or_404(db, incident_id)
    user = _authorize(db, incident, principal, incident_token)
    assert_upload_allowed(incident.submission_type, payload.content_type, payload.size_bytes)
    artifact_id = uuid.uuid4()
    key = quarantine_key(incident.id, artifact_id, payload.filename)
    artifact = Artifact(
        id=artifact_id,
        incident_id=incident.id,
        status="PRESIGNED",
        original_filename=payload.filename,
        expected_mime_type=payload.content_type,
        size_bytes=payload.size_bytes,
        quarantine_bucket=settings.s3_quarantine_bucket,
        quarantine_key=key,
        trusted_metadata={"declared_size_bytes": payload.size_bytes, "declared_content_type": payload.content_type},
        correlation_id=incident.correlation_id,
    )
    db.add(artifact)
    _, upload_url, headers = create_presigned_upload(
        incident_id=incident.id,
        artifact_id=artifact.id,
        filename=payload.filename,
        content_type=payload.content_type,
    )
    record_audit(
        db,
        event_type="UPLOAD_PRESIGNED",
        resource_type="ARTIFACT",
        resource_id=str(artifact.id),
        purpose_code="EVIDENCE_INTAKE",
        correlation_id=incident.correlation_id,
        user=user,
        incident_id=incident.id,
        event_data={"content_type": payload.content_type, "size_bytes": payload.size_bytes},
    )
    db.commit()
    return PresignUploadResponse(
        artifact_id=artifact.id,
        upload_url=upload_url,
        headers=headers,
        expires_in=settings.presign_ttl_seconds,
    )


@router.post("/{incident_id}/uploads/complete", response_model=UploadCompleteResponse)
def complete_upload(
    incident_id: uuid.UUID,
    payload: UploadCompleteRequest,
    incident_token: str | None = Header(default=None, alias="X-Incident-Token"),
    principal: Principal = Depends(optional_principal),
    db: Session = Depends(get_db),
) -> UploadCompleteResponse:
    incident = _incident_or_404(db, incident_id)
    _authorize(db, incident, principal, incident_token)
    artifact = db.get(Artifact, payload.artifact_id)
    if artifact is None or artifact.incident_id != incident.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Artifact not found")
    if artifact.status not in {"PRESIGNED", "UPLOADED"}:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Artifact cannot be completed in its current state")
    artifact.status = "UPLOADED"
    incident.status = "QUEUED"
    record_custody(
        db,
        incident_id=incident.id,
        artifact_id=artifact.id,
        event_type="UPLOAD_COMPLETION_REPORTED",
        from_location="CITIZEN_BROWSER",
        to_location=f"s3://{artifact.quarantine_bucket}/{artifact.quarantine_key}",
        details={"artifact_id": str(artifact.id)},
        correlation_id=incident.correlation_id,
    )
    db.commit()
    job, created = create_job(
        db,
        incident_id=incident.id,
        artifact_id=artifact.id,
        job_type="FILE_VALIDATION",
        idempotency_key=f"file-validation:{artifact.id}",
    )
    if created or not job.celery_task_id:
        enqueue_job(db, job)
    return UploadCompleteResponse(artifact_id=artifact.id, status=artifact.status, validation_job_id=job.id)


@router.post("/{incident_id}/analyze", response_model=AnalyzeResponse)
def analyze(
    incident_id: uuid.UUID,
    idempotency_key: str = Header(..., alias="Idempotency-Key", min_length=8, max_length=255),
    incident_token: str | None = Header(default=None, alias="X-Incident-Token"),
    principal: Principal = Depends(optional_principal),
    db: Session = Depends(get_db),
) -> AnalyzeResponse:
    incident = _incident_or_404(db, incident_id)
    _authorize(db, incident, principal, incident_token)
    incident.status = "QUEUED"
    db.commit()
    job, created = create_job(
        db,
        incident_id=incident.id,
        job_type="AGENT_ANALYSIS",
        idempotency_key=f"manual-analysis:{incident.id}:{idempotency_key}",
    )
    if created or not job.celery_task_id:
        enqueue_job(db, job)
    return AnalyzeResponse(incident_id=incident.id, job_id=job.id, status=job.status)


@router.get("/{incident_id}/status", response_model=IncidentStatusResponse)
def incident_status(
    incident_id: uuid.UUID,
    incident_token: str | None = Header(default=None, alias="X-Incident-Token"),
    principal: Principal = Depends(optional_principal),
    db: Session = Depends(get_db),
) -> IncidentStatusResponse:
    incident = _incident_or_404(db, incident_id)
    _authorize(db, incident, principal, incident_token)
    jobs = db.scalars(
        select(AnalysisJob).where(AnalysisJob.incident_id == incident.id).order_by(AnalysisJob.created_at.desc()).limit(20)
    ).all()
    assessment_ready = db.scalar(
        select(RiskAssessment.id).where(RiskAssessment.incident_id == incident.id, RiskAssessment.status == "CURRENT")
    ) is not None
    db.commit()
    return IncidentStatusResponse(
        incident_id=incident.id,
        incident_status=incident.status,
        jobs=[JobView.model_validate(job) for job in jobs],
        assessment_ready=assessment_ready,
    )


@router.get("/{incident_id}/events", response_model=list[EventView])
def incident_events(
    incident_id: uuid.UUID,
    incident_token: str | None = Header(default=None, alias="X-Incident-Token"),
    principal: Principal = Depends(optional_principal),
    db: Session = Depends(get_db),
) -> list[EventView]:
    incident = _incident_or_404(db, incident_id)
    _authorize(db, incident, principal, incident_token)
    audit_events = db.scalars(
        select(AuditEvent).where(AuditEvent.incident_id == incident.id).order_by(AuditEvent.occurred_at)
    ).all()
    custody_events = db.scalars(
        select(CustodyEvent).where(CustodyEvent.incident_id == incident.id).order_by(CustodyEvent.occurred_at)
    ).all()
    db.commit()
    events = [
        EventView(
            id=item.id,
            event_type=item.event_type,
            occurred_at=item.occurred_at,
            actor_type=item.actor_type,
            resource_type=item.resource_type,
            resource_id=item.resource_id,
            event_data=item.event_data,
        )
        for item in audit_events
    ]
    events.extend(
        EventView(
            id=item.id,
            event_type=item.event_type,
            occurred_at=item.occurred_at,
            actor_type=item.actor_type,
            resource_type="ARTIFACT" if item.artifact_id else "INCIDENT",
            resource_id=str(item.artifact_id or item.incident_id),
            event_data={"from": item.from_location, "to": item.to_location, "payload_hash": item.payload_hash},
        )
        for item in custody_events
    )
    return sorted(events, key=lambda item: item.occurred_at)


@router.get("/{incident_id}/assessment", response_model=AssessmentView)
def get_assessment(
    incident_id: uuid.UUID,
    incident_token: str | None = Header(default=None, alias="X-Incident-Token"),
    principal: Principal = Depends(optional_principal),
    db: Session = Depends(get_db),
) -> RiskAssessment:
    incident = _incident_or_404(db, incident_id)
    _authorize(db, incident, principal, incident_token)
    assessment = db.scalar(
        select(RiskAssessment)
        .where(RiskAssessment.incident_id == incident.id, RiskAssessment.status == "CURRENT")
        .order_by(RiskAssessment.created_at.desc())
    )
    if assessment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assessment is not ready")
    db.commit()
    return assessment


@router.get("/{incident_id}/evidence", response_model=EvidenceView)
def get_evidence(
    incident_id: uuid.UUID,
    incident_token: str | None = Header(default=None, alias="X-Incident-Token"),
    principal: Principal = Depends(optional_principal),
    db: Session = Depends(get_db),
) -> EvidenceView:
    incident = _incident_or_404(db, incident_id)
    user = _authorize(db, incident, principal, incident_token)
    artifacts = db.scalars(select(Artifact).where(Artifact.incident_id == incident.id).order_by(Artifact.created_at)).all()
    derivatives = db.scalars(
        select(ArtifactDerivative).where(ArtifactDerivative.incident_id == incident.id).order_by(ArtifactDerivative.created_at)
    ).all()
    custody = db.scalars(
        select(CustodyEvent).where(CustodyEvent.incident_id == incident.id).order_by(CustodyEvent.occurred_at)
    ).all()
    record_audit(
        db,
        event_type="EVIDENCE_ACCESSED",
        resource_type="INCIDENT_EVIDENCE",
        resource_id=str(incident.id),
        purpose_code="CITIZEN_EVIDENCE_REVIEW" if not principal.roles.intersection({"ANALYST", "SUPERVISOR", "EVIDENCE_OFFICER", "ADMIN"}) else "ANALYST_REVIEW",
        correlation_id=incident.correlation_id,
        user=user,
        incident_id=incident.id,
        event_data={"artifact_count": len(artifacts), "derivative_count": len(derivatives)},
        classification="SENSITIVE",
    )
    db.commit()
    return EvidenceView(
        incident_id=incident.id,
        preserved_at=incident.preserved_at,
        artifacts=[
            ArtifactView.model_validate(item).model_copy(
                update={
                    "download_url": presign_download(item.evidence_bucket, item.evidence_key, item.original_filename)
                    if item.status == "ACCEPTED" and item.evidence_bucket and item.evidence_key
                    else None
                }
            )
            for item in artifacts
        ],
        derivatives=[
            DerivativeView.model_validate(item).model_copy(
                update={"download_url": presign_download(item.bucket, item.object_key, f"{item.kind.lower()}.{item.mime_type.split('/')[-1]}")}
            )
            for item in derivatives
        ],
        custody_events=[
            {"event_type": item.event_type, "occurred_at": item.occurred_at.isoformat(), "payload_hash": item.payload_hash}
            for item in custody
        ],
    )


@router.post("/{incident_id}/preserve", response_model=PreserveResponse)
def preserve(
    incident_id: uuid.UUID,
    idempotency_key: str = Header(..., alias="Idempotency-Key", min_length=8, max_length=255),
    incident_token: str | None = Header(default=None, alias="X-Incident-Token"),
    principal: Principal = Depends(optional_principal),
    db: Session = Depends(get_db),
) -> PreserveResponse:
    incident = _incident_or_404(db, incident_id)
    user = _authorize(db, incident, principal, incident_token)
    scope = f"preserve:{incident.id}"
    replay = find_idempotent(db, scope=scope, key=idempotency_key, payload={"incident_id": str(incident.id)})
    if replay:
        manifest = db.get(EvidenceManifest, uuid.UUID(replay.resource_id))
        if manifest:
            return PreserveResponse(incident_id=incident.id, manifest_id=manifest.id, status=manifest.status)
    manifest = seal_manifest(db, incident)
    save_idempotent(
        db,
        scope=scope,
        key=idempotency_key,
        payload={"incident_id": str(incident.id)},
        resource_type="EVIDENCE_MANIFEST",
        resource_id=str(manifest.id),
        response_code=200,
    )
    record_audit(
        db,
        event_type="INCIDENT_PRESERVED",
        resource_type="EVIDENCE_MANIFEST",
        resource_id=str(manifest.id),
        purpose_code="EVIDENCE_PRESERVATION",
        correlation_id=incident.correlation_id,
        user=user,
        incident_id=incident.id,
        idempotency_key=idempotency_key,
        event_data={"manifest_schema": manifest.schema_version, "manifest_sha256": manifest.sha256},
        classification="SENSITIVE",
    )
    db.commit()
    return PreserveResponse(incident_id=incident.id, manifest_id=manifest.id, status=manifest.status)


@router.post("/{incident_id}/exports", response_model=ExportCreated, status_code=status.HTTP_202_ACCEPTED)
def create_export(
    incident_id: uuid.UUID,
    payload: ExportCreateRequest,
    idempotency_key: str = Header(..., alias="Idempotency-Key", min_length=8, max_length=255),
    incident_token: str | None = Header(default=None, alias="X-Incident-Token"),
    principal: Principal = Depends(optional_principal),
    db: Session = Depends(get_db),
) -> ExportCreated:
    incident = _incident_or_404(db, incident_id)
    user = _authorize(db, incident, principal, incident_token)
    request_data = payload.model_dump(mode="json")
    scope = f"export:{incident.id}"
    replay = find_idempotent(db, scope=scope, key=idempotency_key, payload=request_data)
    if replay:
        export = db.get(ReportExport, uuid.UUID(replay.resource_id))
        if export:
            job = db.scalar(select(AnalysisJob).where(AnalysisJob.export_id == export.id).order_by(AnalysisJob.created_at.desc()))
            if job:
                return ExportCreated(export=ExportView.model_validate(export), job_id=job.id)
    export = ReportExport(
        incident_id=incident.id,
        requested_by_user_id=user.id if user else None,
        export_format=payload.export_format,
        correlation_id=incident.correlation_id,
    )
    db.add(export)
    db.flush()
    save_idempotent(
        db,
        scope=scope,
        key=idempotency_key,
        payload=request_data,
        resource_type="REPORT_EXPORT",
        resource_id=str(export.id),
        response_code=status.HTTP_202_ACCEPTED,
    )
    db.commit()
    job, created = create_job(
        db,
        incident_id=incident.id,
        export_id=export.id,
        job_type="EVIDENCE_EXPORT",
        idempotency_key=f"evidence-export:{incident.id}:{idempotency_key}",
    )
    if created or not job.celery_task_id:
        enqueue_job(db, job)
    db.refresh(export)
    return ExportCreated(export=ExportView.model_validate(export), job_id=job.id)


@exports_router.get("/{export_id}/download", response_model=DownloadResponse)
def download_export(
    export_id: uuid.UUID,
    incident_token: str | None = Header(default=None, alias="X-Incident-Token"),
    principal: Principal = Depends(optional_principal),
    db: Session = Depends(get_db),
) -> DownloadResponse:
    export = db.get(ReportExport, export_id)
    if export is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Export not found")
    incident = _incident_or_404(db, export.incident_id)
    user = _authorize(db, incident, principal, incident_token)
    if export.status != "COMPLETED" or not export.bucket or not export.object_key:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Export is not ready")
    record_audit(
        db,
        event_type="EVIDENCE_EXPORT_DOWNLOADED",
        resource_type="REPORT_EXPORT",
        resource_id=str(export.id),
        purpose_code="EVIDENCE_PACKAGE_DOWNLOAD",
        correlation_id=incident.correlation_id,
        user=user,
        incident_id=incident.id,
        event_data={"sha256": export.sha256},
        classification="SENSITIVE",
    )
    db.commit()
    return DownloadResponse(
        download_url=presign_download(export.bucket, export.object_key, "adris-evidence-package.zip"),
        expires_in=settings.presign_ttl_seconds,
    )
