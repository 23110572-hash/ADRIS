import hashlib
import uuid
from datetime import UTC, datetime

import h3
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.schemas import (
    AgentRunView,
    AnalystIncidentView,
    AnalystIndicatorView,
    AnalystQueueItem,
    ArtifactView,
    AssessmentView,
    CorrectionRequest,
    DerivativeView,
    ExportView,
    GraphEdge,
    GraphNode,
    GraphResponse,
    IncidentView,
    MapCell,
    MapResponse,
    ReviewRequest,
    ReviewResponse,
    SignalView,
)
from app.artifacts.storage import presign_download
from app.audit.service import record_audit
from app.auth.dependencies import Principal, analyst_principal
from app.auth.service import resolve_user
from app.db.models import (
    AgentRun,
    Artifact,
    ArtifactDerivative,
    Correction,
    EntityRelationship,
    GeoAggregate,
    Incident,
    Indicator,
    ReportExport,
    ReviewDisposition,
    ReviewTask,
    RiskAssessment,
    Signal,
)
from app.db.session import get_db
from app.geo.service import MINIMUM_DISPLAY_COUNT

router = APIRouter(prefix="/analyst", tags=["analyst"])


def _user_or_500(db: Session, principal: Principal):
    user = resolve_user(db, principal)
    if user is None:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Authenticated user could not be resolved")
    return user


def _artifact_views(artifacts: list[Artifact]) -> list[ArtifactView]:
    return [
        ArtifactView.model_validate(item).model_copy(
            update={
                "download_url": presign_download(item.evidence_bucket, item.evidence_key, item.original_filename)
                if item.status == "ACCEPTED" and item.evidence_bucket and item.evidence_key
                else None
            }
        )
        for item in artifacts
    ]


def _derivative_views(derivatives: list[ArtifactDerivative]) -> list[DerivativeView]:
    return [
        DerivativeView.model_validate(item).model_copy(
            update={"download_url": presign_download(item.bucket, item.object_key, f"{item.kind.lower()}.{item.mime_type.split('/')[-1]}")}
        )
        for item in derivatives
    ]


@router.get("/queue", response_model=list[AnalystQueueItem])
def queue(
    principal: Principal = Depends(analyst_principal),
    db: Session = Depends(get_db),
) -> list[AnalystQueueItem]:
    _user_or_500(db, principal)
    tasks = db.scalars(
        select(ReviewTask)
        .where(ReviewTask.status.in_(["OPEN", "CLAIMED"]))
        .order_by(ReviewTask.priority, ReviewTask.created_at)
        .limit(200)
    ).all()
    output: list[AnalystQueueItem] = []
    for task in tasks:
        assessment = db.get(RiskAssessment, task.assessment_id) if task.assessment_id else None
        output.append(
            AnalystQueueItem(
                review_task_id=task.id,
                incident_id=task.incident_id,
                priority=task.priority,
                status=task.status,
                reason=task.reason,
                risk_band=assessment.risk_band if assessment else None,
                created_at=task.created_at,
            )
        )
    db.commit()
    return output


@router.get("/incidents/{incident_id}", response_model=AnalystIncidentView)
def analyst_incident(
    incident_id: uuid.UUID,
    principal: Principal = Depends(analyst_principal),
    db: Session = Depends(get_db),
) -> AnalystIncidentView:
    user = _user_or_500(db, principal)
    incident = db.get(Incident, incident_id)
    if incident is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Incident not found")
    artifacts = db.scalars(select(Artifact).where(Artifact.incident_id == incident.id).order_by(Artifact.created_at)).all()
    derivatives = db.scalars(
        select(ArtifactDerivative).where(ArtifactDerivative.incident_id == incident.id).order_by(ArtifactDerivative.created_at)
    ).all()
    indicators = db.scalars(select(Indicator).where(Indicator.incident_id == incident.id).order_by(Indicator.created_at)).all()
    signals = db.scalars(select(Signal).where(Signal.incident_id == incident.id).order_by(Signal.created_at)).all()
    assessments = db.scalars(
        select(RiskAssessment).where(RiskAssessment.incident_id == incident.id).order_by(RiskAssessment.created_at.desc())
    ).all()
    runs = db.scalars(select(AgentRun).where(AgentRun.incident_id == incident.id).order_by(AgentRun.created_at)).all()
    reviews = db.scalars(
        select(ReviewDisposition).where(ReviewDisposition.incident_id == incident.id).order_by(ReviewDisposition.created_at)
    ).all()
    record_audit(
        db,
        event_type="ANALYST_EVIDENCE_ACCESSED",
        resource_type="INCIDENT_EVIDENCE",
        resource_id=str(incident.id),
        purpose_code="ANALYST_REVIEW",
        correlation_id=incident.correlation_id,
        user=user,
        incident_id=incident.id,
        authority_reference="ADRIS_ANALYST_ROLE",
        event_data={"artifact_count": len(artifacts), "derivative_count": len(derivatives)},
        classification="SENSITIVE",
    )
    db.commit()
    return AnalystIncidentView(
        incident=IncidentView.model_validate(incident),
        artifacts=_artifact_views(artifacts),
        derivatives=_derivative_views(derivatives),
        indicators=[AnalystIndicatorView.model_validate(item) for item in indicators],
        signals=[SignalView.model_validate(item) for item in signals],
        assessments=[AssessmentView.model_validate(item) for item in assessments],
        agent_runs=[AgentRunView.model_validate(item) for item in runs],
        reviews=[ReviewResponse.model_validate(item) for item in reviews],
    )


@router.post("/incidents/{incident_id}/review", response_model=ReviewResponse)
def review_incident(
    incident_id: uuid.UUID,
    payload: ReviewRequest,
    principal: Principal = Depends(analyst_principal),
    db: Session = Depends(get_db),
) -> ReviewDisposition:
    user = _user_or_500(db, principal)
    incident = db.get(Incident, incident_id)
    task = db.get(ReviewTask, payload.review_task_id)
    if incident is None or task is None or task.incident_id != incident.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Review task not found")
    if task.status == "COMPLETED":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Review task is already completed")
    disposition = ReviewDisposition(
        review_task_id=task.id,
        incident_id=incident.id,
        reviewer_user_id=user.id,
        disposition=payload.disposition,
        notes=payload.notes,
        reason_codes=payload.reason_codes,
        correlation_id=incident.correlation_id,
    )
    db.add(disposition)
    task.status = "COMPLETED"
    task.assigned_to_user_id = user.id
    task.claimed_at = task.claimed_at or datetime.now(UTC)
    task.completed_at = datetime.now(UTC)
    record_audit(
        db,
        event_type="REVIEW_DISPOSITION_RECORDED",
        resource_type="REVIEW_DISPOSITION",
        resource_id=str(disposition.id),
        purpose_code="ANALYST_REVIEW",
        correlation_id=incident.correlation_id,
        user=user,
        incident_id=incident.id,
        event_data={"disposition": payload.disposition, "reason_codes": payload.reason_codes},
        classification="SENSITIVE",
    )
    db.commit()
    db.refresh(disposition)
    return disposition


@router.post("/incidents/{incident_id}/corrections")
def correct_incident(
    incident_id: uuid.UUID,
    payload: CorrectionRequest,
    principal: Principal = Depends(analyst_principal),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    user = _user_or_500(db, principal)
    incident = db.get(Incident, incident_id)
    if incident is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Incident not found")
    target = db.get(Indicator, payload.indicator_id) if payload.indicator_id else db.get(Signal, payload.signal_id)
    if target is None or target.incident_id != incident.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Correction target not found")
    if not hasattr(target, payload.field_name):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Field is not valid for this target")
    previous = getattr(target, payload.field_name)
    setattr(target, payload.field_name, payload.corrected_value)
    if isinstance(target, Indicator) and payload.field_name == "normalized_value":
        target.normalized_value_hash = hashlib.sha256(payload.corrected_value.encode()).hexdigest()
        target.masked_value = payload.corrected_value[:3] + "…" + payload.corrected_value[-3:] if len(payload.corrected_value) > 8 else "***"
    correction = Correction(
        incident_id=incident.id,
        indicator_id=target.id if isinstance(target, Indicator) else None,
        signal_id=target.id if isinstance(target, Signal) else None,
        corrected_by_user_id=user.id,
        field_name=payload.field_name,
        previous_value={"value": previous},
        corrected_value={"value": payload.corrected_value},
        reason=payload.reason,
        correlation_id=incident.correlation_id,
    )
    db.add(correction)
    record_audit(
        db,
        event_type="ANALYST_CORRECTION_APPLIED",
        resource_type="CORRECTION",
        resource_id=str(correction.id),
        purpose_code="QUALITY_CORRECTION",
        correlation_id=incident.correlation_id,
        user=user,
        incident_id=incident.id,
        event_data={"field_name": payload.field_name, "target_type": type(target).__name__},
        classification="SENSITIVE",
    )
    db.commit()
    return {"id": str(correction.id), "status": correction.status}


@router.get("/network", response_model=GraphResponse)
def network(
    principal: Principal = Depends(analyst_principal),
    db: Session = Depends(get_db),
) -> GraphResponse:
    _user_or_500(db, principal)
    relationships = db.scalars(
        select(EntityRelationship)
        .where(EntityRelationship.status == "ACTIVE")
        .order_by(EntityRelationship.occurrence_count.desc(), EntityRelationship.updated_at.desc())
        .limit(1000)
    ).all()
    nodes: dict[str, GraphNode] = {}
    edges: list[GraphEdge] = []
    for edge in relationships:
        source_id = f"{edge.source_type}:{edge.source_value_hash}"
        target_id = f"{edge.target_type}:{edge.target_value_hash}"
        risk_band = None
        if edge.incident_id and edge.source_type == "INCIDENT":
            assessment = db.scalar(
                select(RiskAssessment)
                .where(RiskAssessment.incident_id == edge.incident_id, RiskAssessment.status == "CURRENT")
                .order_by(RiskAssessment.created_at.desc())
            )
            risk_band = assessment.risk_band if assessment else None
        nodes[source_id] = GraphNode(
            id=source_id,
            label=edge.source_label,
            entity_type=edge.source_type,
            occurrence_count=max(nodes.get(source_id, GraphNode(id=source_id, label=edge.source_label, entity_type=edge.source_type)).occurrence_count, edge.occurrence_count),
            risk_band=risk_band,
        )
        nodes[target_id] = GraphNode(
            id=target_id,
            label=edge.target_label,
            entity_type=edge.target_type,
            occurrence_count=max(nodes.get(target_id, GraphNode(id=target_id, label=edge.target_label, entity_type=edge.target_type)).occurrence_count, edge.occurrence_count),
        )
        edges.append(
            GraphEdge(
                id=str(edge.id),
                source=source_id,
                target=target_id,
                relationship_type=edge.relationship_type,
                explanation=edge.explanation,
                weight=edge.weight,
            )
        )
    db.commit()
    return GraphResponse(nodes=list(nodes.values()), edges=edges, generated_at=datetime.now(UTC))


@router.get("/map", response_model=MapResponse)
def map_data(
    principal: Principal = Depends(analyst_principal),
    db: Session = Depends(get_db),
) -> MapResponse:
    _user_or_500(db, principal)
    rows = db.scalars(
        select(GeoAggregate)
        .where(GeoAggregate.status == "CURRENT", GeoAggregate.suppressed.is_(False))
        .order_by(GeoAggregate.period_end.desc())
        .limit(1000)
    ).all()
    latest: dict[str, GeoAggregate] = {}
    for row in rows:
        latest.setdefault(row.h3_cell, row)
    cells = []
    for row in latest.values():
        latitude, longitude = h3.cell_to_latlng(row.h3_cell)
        cells.append(
            MapCell(
                h3_cell=row.h3_cell,
                latitude=latitude,
                longitude=longitude,
                incident_count=row.incident_count,
                high_risk_count=row.high_risk_count,
                caution_count=row.caution_count,
                trend_ratio=row.trend_ratio,
                period_start=row.period_start,
                period_end=row.period_end,
            )
        )
    db.commit()
    return MapResponse(
        cells=cells,
        minimum_display_count=MINIMUM_DISPLAY_COUNT,
        privacy_note="Only coarse H3 cells meeting minimum-count suppression are shown. Victim location is not offender location.",
        generated_at=datetime.now(UTC),
    )


@router.get("/reviews", response_model=list[ReviewResponse])
def reviews(
    principal: Principal = Depends(analyst_principal),
    db: Session = Depends(get_db),
) -> list[ReviewDisposition]:
    _user_or_500(db, principal)
    output = db.scalars(select(ReviewDisposition).order_by(ReviewDisposition.created_at.desc()).limit(200)).all()
    db.commit()
    return list(output)


@router.get("/exports", response_model=list[ExportView])
def exports(
    principal: Principal = Depends(analyst_principal),
    db: Session = Depends(get_db),
) -> list[ReportExport]:
    _user_or_500(db, principal)
    output = db.scalars(select(ReportExport).order_by(ReportExport.created_at.desc()).limit(200)).all()
    db.commit()
    return list(output)
