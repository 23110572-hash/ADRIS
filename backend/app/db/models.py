import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def utcnow() -> datetime:
    return datetime.now(UTC)


class UUIDTimestampMixin:
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), default=utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), default=utcnow, onupdate=func.now()
    )
    correlation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, default=uuid.uuid4, index=True
    )


class User(UUIDTimestampMixin, Base):
    __tablename__ = "users"

    clerk_subject: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    email_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    display_name: Mapped[str | None] = mapped_column(String(160), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="ACTIVE", index=True)
    last_authenticated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Role(UUIDTimestampMixin, Base):
    __tablename__ = "roles"

    name: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    description: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="ACTIVE")


class UserRole(UUIDTimestampMixin, Base):
    __tablename__ = "user_roles"
    __table_args__ = (UniqueConstraint("user_id", "role_id", name="uq_user_roles_user_role"),)

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("roles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    granted_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="ACTIVE")


class Incident(UUIDTimestampMixin, Base):
    __tablename__ = "incidents"
    __table_args__ = (
        Index("ix_incidents_status_created", "status", "created_at"),
        Index("ix_incidents_owner_created", "owner_user_id", "created_at"),
    )

    owner_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="DRAFT", index=True)
    submission_type: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    language: Mapped[str | None] = mapped_column(String(20), nullable=True)
    title: Mapped[str | None] = mapped_column(String(160), nullable=True)
    input_quality: Mapped[str] = mapped_column(String(32), nullable=False, default="PENDING")
    access_token_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    coarse_h3_cell: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    district: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    state: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    preserved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Submission(UUIDTimestampMixin, Base):
    __tablename__ = "submissions"

    incident_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("incidents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    kind: Mapped[str] = mapped_column(String(40), nullable=False)
    text_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_label: Mapped[str] = mapped_column(String(80), nullable=False, default="CITIZEN_SUBMITTED")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="RECEIVED")
    consent_confirmed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class Artifact(UUIDTimestampMixin, Base):
    __tablename__ = "artifacts"
    __table_args__ = (
        UniqueConstraint("quarantine_bucket", "quarantine_key", name="uq_artifact_quarantine_object"),
        UniqueConstraint("evidence_bucket", "evidence_key", name="uq_artifact_evidence_object"),
    )

    incident_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("incidents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    submission_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("submissions.id", ondelete="SET NULL"), nullable=True
    )
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="PRESIGNED", index=True)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    expected_mime_type: Mapped[str] = mapped_column(String(120), nullable=False)
    detected_mime_type: Mapped[str | None] = mapped_column(String(120), nullable=True)
    size_bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    quarantine_bucket: Mapped[str] = mapped_column(String(255), nullable=False)
    quarantine_key: Mapped[str] = mapped_column(String(1024), nullable=False)
    quarantine_version_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    evidence_bucket: Mapped[str | None] = mapped_column(String(255), nullable=True)
    evidence_key: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    evidence_version_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    sha256: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    receipt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    validated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rejection_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    metadata_version: Mapped[str] = mapped_column(String(32), nullable=False, default="artifact-v1")
    trusted_metadata: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)


class ArtifactDerivative(UUIDTimestampMixin, Base):
    __tablename__ = "artifact_derivatives"

    incident_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("incidents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    artifact_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("artifacts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    kind: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="AVAILABLE")
    provider: Mapped[str] = mapped_column(String(80), nullable=False)
    provider_version: Mapped[str] = mapped_column(String(80), nullable=False)
    transformation_version: Mapped[str] = mapped_column(String(80), nullable=False)
    bucket: Mapped[str] = mapped_column(String(255), nullable=False)
    object_key: Mapped[str] = mapped_column(String(1024), nullable=False, unique=True)
    mime_type: Mapped[str] = mapped_column(String(120), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    source_reference: Mapped[str] = mapped_column(String(255), nullable=False)
    details_version: Mapped[str] = mapped_column(String(32), nullable=False, default="derivative-v1")
    details: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)


class Indicator(UUIDTimestampMixin, Base):
    __tablename__ = "indicators"
    __table_args__ = (
        UniqueConstraint(
            "incident_id", "indicator_type", "normalized_value_hash", "source_reference",
            name="uq_indicator_incident_type_hash_source",
        ),
        Index("ix_indicators_type_hash", "indicator_type", "normalized_value_hash"),
    )

    incident_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("incidents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    artifact_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("artifacts.id", ondelete="SET NULL"), nullable=True
    )
    derivative_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("artifact_derivatives.id", ondelete="SET NULL"), nullable=True
    )
    indicator_type: Mapped[str] = mapped_column(String(48), nullable=False)
    normalized_value: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_value_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    masked_value: Mapped[str] = mapped_column(String(255), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    source_reference: Mapped[str] = mapped_column(String(255), nullable=False)
    extractor_version: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="ACTIVE")
    reviewed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class AgentRun(UUIDTimestampMixin, Base):
    __tablename__ = "agent_runs"
    __table_args__ = (Index("ix_agent_runs_incident_agent", "incident_id", "agent_name"),)

    incident_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("incidents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    agent_name: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="STARTED")
    model_provider: Mapped[str] = mapped_column(String(40), nullable=False, default="DETERMINISTIC")
    model_name: Mapped[str | None] = mapped_column(String(160), nullable=True)
    model_version: Mapped[str | None] = mapped_column(String(80), nullable=True)
    prompt_version: Mapped[str] = mapped_column(String(80), nullable=False)
    agent_version: Mapped[str] = mapped_column(String(80), nullable=False)
    tool_versions: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    input_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    output_version: Mapped[str] = mapped_column(String(40), nullable=False, default="v1")
    structured_output: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(80), nullable=True)


class Signal(UUIDTimestampMixin, Base):
    __tablename__ = "signals"
    __table_args__ = (
        UniqueConstraint("incident_id", "code", "evidence_reference", name="uq_signal_incident_code_evidence"),
    )

    incident_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("incidents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    agent_run_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agent_runs.id", ondelete="SET NULL"), nullable=True
    )
    code: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    family: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    severity: Mapped[float] = mapped_column(Float, nullable=False)
    strength: Mapped[str] = mapped_column(String(24), nullable=False)
    source: Mapped[str] = mapped_column(String(40), nullable=False)
    evidence_reference: Mapped[str] = mapped_column(String(255), nullable=False)
    explanation: Mapped[str] = mapped_column(String(500), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="ACTIVE")
    reviewed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class RiskAssessment(UUIDTimestampMixin, Base):
    __tablename__ = "risk_assessments"
    __table_args__ = (Index("ix_assessments_incident_created", "incident_id", "created_at"),)

    incident_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("incidents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="CURRENT")
    risk_band: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    policy_version: Mapped[str] = mapped_column(String(80), nullable=False)
    reason_codes: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    coverage: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    missing_sources: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    agent_disagreement: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    safety_actions: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    input_quality: Mapped[str] = mapped_column(String(32), nullable=False)
    model_summary: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)


class ReviewTask(UUIDTimestampMixin, Base):
    __tablename__ = "review_tasks"
    __table_args__ = (Index("ix_review_tasks_status_priority", "status", "priority"),)

    incident_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("incidents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    assessment_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("risk_assessments.id", ondelete="SET NULL"), nullable=True
    )
    assigned_to_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="OPEN", index=True)
    priority: Mapped[str] = mapped_column(String(32), nullable=False, default="P3", index=True)
    reason: Mapped[str] = mapped_column(String(255), nullable=False)
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ReviewDisposition(UUIDTimestampMixin, Base):
    __tablename__ = "review_dispositions"

    review_task_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("review_tasks.id", ondelete="CASCADE"), nullable=False, index=True
    )
    incident_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("incidents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    reviewer_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    disposition: Mapped[str] = mapped_column(String(48), nullable=False, index=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    reason_codes: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    authority: Mapped[str] = mapped_column(String(80), nullable=False, default="ADRIS_ANALYST")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="FINAL")


class EntityRelationship(UUIDTimestampMixin, Base):
    __tablename__ = "entity_relationships"
    __table_args__ = (
        UniqueConstraint(
            "source_type", "source_value_hash", "target_type", "target_value_hash", "relationship_type",
            name="uq_entity_relationship_edge",
        ),
        Index("ix_relationship_source", "source_type", "source_value_hash"),
        Index("ix_relationship_target", "target_type", "target_value_hash"),
    )

    incident_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("incidents.id", ondelete="SET NULL"), nullable=True, index=True
    )
    source_type: Mapped[str] = mapped_column(String(48), nullable=False)
    source_value_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    source_label: Mapped[str] = mapped_column(String(255), nullable=False)
    target_type: Mapped[str] = mapped_column(String(48), nullable=False)
    target_value_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    target_label: Mapped[str] = mapped_column(String(255), nullable=False)
    relationship_type: Mapped[str] = mapped_column(String(64), nullable=False)
    weight: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    explanation: Mapped[str] = mapped_column(String(500), nullable=False)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    occurrence_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="ACTIVE")
    reviewed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class GeoAggregate(UUIDTimestampMixin, Base):
    __tablename__ = "geo_aggregates"
    __table_args__ = (
        UniqueConstraint("h3_cell", "period_start", "period_end", name="uq_geo_cell_period"),
    )

    h3_cell: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    h3_resolution: Mapped[int] = mapped_column(Integer, nullable=False)
    district: Mapped[str | None] = mapped_column(String(120), nullable=True)
    state: Mapped[str | None] = mapped_column(String(120), nullable=True)
    period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    incident_count: Mapped[int] = mapped_column(Integer, nullable=False)
    high_risk_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    caution_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    minimum_display_count: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    suppressed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    trend_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="CURRENT")


class EvidenceManifest(UUIDTimestampMixin, Base):
    __tablename__ = "evidence_manifests"

    incident_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("incidents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="DRAFT")
    schema_version: Mapped[str] = mapped_column(String(40), nullable=False, default="evidence-manifest-v1")
    bucket: Mapped[str | None] = mapped_column(String(255), nullable=True)
    object_key: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    manifest_data: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    sealed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class CustodyEvent(UUIDTimestampMixin, Base):
    __tablename__ = "custody_events"
    __table_args__ = (Index("ix_custody_incident_occurred", "incident_id", "occurred_at"),)

    incident_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("incidents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    artifact_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("artifacts.id", ondelete="SET NULL"), nullable=True
    )
    event_type: Mapped[str] = mapped_column(String(80), nullable=False)
    actor_type: Mapped[str] = mapped_column(String(40), nullable=False)
    actor_reference: Mapped[str] = mapped_column(String(255), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    from_location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    to_location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    purpose_code: Mapped[str] = mapped_column(String(80), nullable=False)
    payload_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    details_version: Mapped[str] = mapped_column(String(32), nullable=False, default="custody-v1")
    details: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)


class ReportExport(UUIDTimestampMixin, Base):
    __tablename__ = "report_exports"

    incident_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("incidents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    manifest_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("evidence_manifests.id", ondelete="SET NULL"), nullable=True
    )
    requested_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="PENDING", index=True)
    export_format: Mapped[str] = mapped_column(String(32), nullable=False, default="ZIP")
    bucket: Mapped[str | None] = mapped_column(String(255), nullable=True)
    object_key: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    size_bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    details: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    failure_code: Mapped[str | None] = mapped_column(String(80), nullable=True)


class AnalysisJob(UUIDTimestampMixin, Base):
    __tablename__ = "analysis_jobs"
    __table_args__ = (
        UniqueConstraint("idempotency_key", "job_type", name="uq_analysis_job_idempotency_type"),
        Index("ix_analysis_jobs_reconcile", "status", "available_at", "created_at"),
    )

    incident_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("incidents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    artifact_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("artifacts.id", ondelete="SET NULL"), nullable=True
    )
    export_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("report_exports.id", ondelete="SET NULL"), nullable=True
    )
    retry_of_job_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("analysis_jobs.id", ondelete="SET NULL"), nullable=True
    )
    job_type: Mapped[str] = mapped_column(String(48), nullable=False, index=True)
    queue_name: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="PENDING", index=True)
    idempotency_key: Mapped[str] = mapped_column(String(255), nullable=False)
    celery_task_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    progress_percent: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    progress_message: Mapped[str | None] = mapped_column(String(255), nullable=True)
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(80), nullable=True)
    error_detail: Mapped[str | None] = mapped_column(String(500), nullable=True)


class Correction(UUIDTimestampMixin, Base):
    __tablename__ = "corrections"

    incident_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("incidents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    indicator_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("indicators.id", ondelete="SET NULL"), nullable=True
    )
    signal_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("signals.id", ondelete="SET NULL"), nullable=True
    )
    corrected_by_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    field_name: Mapped[str] = mapped_column(String(120), nullable=False)
    previous_value: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    corrected_value: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    reason: Mapped[str] = mapped_column(String(500), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="APPLIED")


class Partner(UUIDTimestampMixin, Base):
    __tablename__ = "partners"

    name: Mapped[str] = mapped_column(String(160), nullable=False, unique=True)
    partner_type: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="FUTURE_ADAPTER")
    adapter_status: Mapped[str] = mapped_column(String(48), nullable=False, default="NOT_CONFIGURED")
    capabilities_version: Mapped[str] = mapped_column(String(32), nullable=False, default="partner-v1")
    capabilities: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)


class PurposeAuthorization(UUIDTimestampMixin, Base):
    __tablename__ = "purpose_authorizations"

    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True
    )
    incident_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("incidents.id", ondelete="CASCADE"), nullable=True, index=True
    )
    partner_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("partners.id", ondelete="CASCADE"), nullable=True
    )
    purpose_code: Mapped[str] = mapped_column(String(80), nullable=False)
    authority_reference: Mapped[str] = mapped_column(String(255), nullable=False)
    consent_reference: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="ACTIVE")
    valid_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    valid_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ActionRecommendation(UUIDTimestampMixin, Base):
    __tablename__ = "action_recommendations"

    incident_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("incidents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    assessment_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("risk_assessments.id", ondelete="SET NULL"), nullable=True
    )
    action_type: Mapped[str] = mapped_column(String(80), nullable=False)
    recommendation: Mapped[str] = mapped_column(String(500), nullable=False)
    rationale_codes: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    authority_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="RECOMMENDED")


class ActionOutcome(UUIDTimestampMixin, Base):
    __tablename__ = "action_outcomes"

    recommendation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("action_recommendations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    recorded_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    outcome: Mapped[str] = mapped_column(String(80), nullable=False)
    source: Mapped[str] = mapped_column(String(80), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="RECORDED")


class AuditEvent(UUIDTimestampMixin, Base):
    __tablename__ = "audit_events"
    __table_args__ = (Index("ix_audit_incident_occurred", "incident_id", "occurred_at"),)

    event_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    schema_version: Mapped[str] = mapped_column(String(32), nullable=False, default="audit-v1")
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    actor_type: Mapped[str] = mapped_column(String(40), nullable=False)
    actor_reference: Mapped[str] = mapped_column(String(255), nullable=False)
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    incident_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("incidents.id", ondelete="SET NULL"), nullable=True, index=True
    )
    resource_type: Mapped[str] = mapped_column(String(80), nullable=False)
    resource_id: Mapped[str] = mapped_column(String(255), nullable=False)
    purpose_code: Mapped[str] = mapped_column(String(80), nullable=False)
    authority_reference: Mapped[str | None] = mapped_column(String(255), nullable=True)
    causation_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(255), nullable=True)
    classification: Mapped[str] = mapped_column(String(40), nullable=False, default="INTERNAL")
    payload_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    client_ip_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    event_data: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="RECORDED")


class IdempotencyRecord(UUIDTimestampMixin, Base):
    __tablename__ = "idempotency_records"
    __table_args__ = (UniqueConstraint("scope", "idempotency_key", name="uq_idempotency_scope_key"),)

    scope: Mapped[str] = mapped_column(String(100), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(255), nullable=False)
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(80), nullable=False)
    resource_id: Mapped[str] = mapped_column(String(255), nullable=False)
    response_code: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="COMPLETED")


class ModelMetric(UUIDTimestampMixin, Base):
    __tablename__ = "model_metrics"

    metric_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    metric_value: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    labels: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="RECORDED")
