import uuid
from datetime import datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator


class ApiModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class SubmissionType(StrEnum):
    MESSAGE = "MESSAGE"
    SCREENSHOT = "SCREENSHOT"
    DOCUMENT = "DOCUMENT"
    URL = "URL"
    QR = "QR"
    AUDIO = "AUDIO"


class RiskBand(StrEnum):
    HIGH_RISK = "HIGH_RISK"
    CAUTION = "CAUTION"
    NO_STRONG_SIGNAL = "NO_STRONG_SIGNAL"
    UNABLE_TO_ASSESS = "UNABLE_TO_ASSESS"


class IncidentCreate(ApiModel):
    submission_type: SubmissionType
    text: str | None = Field(default=None, max_length=50_000)
    language: str | None = Field(default=None, max_length=20)
    title: str | None = Field(default=None, max_length=160)
    coarse_h3_cell: str | None = Field(default=None, max_length=32)
    district: str | None = Field(default=None, max_length=120)
    state: str | None = Field(default=None, max_length=120)
    consent_confirmed: bool = True

    @model_validator(mode="after")
    def require_text_for_textual_submissions(self) -> "IncidentCreate":
        if self.submission_type in {SubmissionType.MESSAGE, SubmissionType.URL} and not self.text:
            raise ValueError("text is required for message and URL submissions")
        if self.submission_type == SubmissionType.AUDIO and not self.consent_confirmed:
            raise ValueError("consent is required for audio submissions")
        return self


class IncidentCreated(ApiModel):
    id: uuid.UUID
    status: str
    submission_type: str
    access_token: str | None = None
    created_at: datetime
    analysis_job_id: uuid.UUID | None = None


class IncidentView(ApiModel):
    id: uuid.UUID
    status: str
    submission_type: str
    language: str | None
    title: str | None
    input_quality: str
    district: str | None
    state: str | None
    preserved_at: datetime | None
    created_at: datetime
    updated_at: datetime


class PresignUploadRequest(ApiModel):
    filename: str = Field(min_length=1, max_length=255)
    content_type: str = Field(min_length=3, max_length=120)
    size_bytes: int = Field(gt=0, le=100 * 1024 * 1024)


class PresignUploadResponse(ApiModel):
    artifact_id: uuid.UUID
    upload_url: str
    method: Literal["PUT"] = "PUT"
    headers: dict[str, str]
    expires_in: int


class UploadCompleteRequest(ApiModel):
    artifact_id: uuid.UUID


class UploadCompleteResponse(ApiModel):
    artifact_id: uuid.UUID
    status: str
    validation_job_id: uuid.UUID


class AnalyzeResponse(ApiModel):
    incident_id: uuid.UUID
    job_id: uuid.UUID
    status: str


class JobView(ApiModel):
    id: uuid.UUID
    job_type: str
    status: str
    progress_percent: int
    progress_message: str | None
    error_code: str | None
    created_at: datetime
    updated_at: datetime


class IncidentStatusResponse(ApiModel):
    incident_id: uuid.UUID
    incident_status: str
    jobs: list[JobView]
    assessment_ready: bool


class AssessmentView(ApiModel):
    id: uuid.UUID
    incident_id: uuid.UUID
    risk_band: RiskBand
    policy_version: str
    reason_codes: list[str]
    coverage: dict[str, Any]
    missing_sources: list[str]
    agent_disagreement: bool
    explanation: str
    safety_actions: list[str]
    input_quality: str
    created_at: datetime


class IndicatorView(ApiModel):
    id: uuid.UUID
    indicator_type: str
    masked_value: str
    confidence: float
    source_reference: str
    status: str


class AnalystIndicatorView(IndicatorView):
    normalized_value: str
    normalized_value_hash: str
    reviewed: bool


class SignalView(ApiModel):
    id: uuid.UUID
    code: str
    family: str
    severity: float
    strength: str
    source: str
    evidence_reference: str
    explanation: str
    confidence: float
    status: str


class AgentRunView(ApiModel):
    id: uuid.UUID
    agent_name: str
    status: str
    model_provider: str
    model_name: str | None
    prompt_version: str
    agent_version: str
    tool_versions: dict[str, Any]
    latency_ms: int | None
    input_tokens: int | None
    output_tokens: int | None
    error_code: str | None
    created_at: datetime


class ArtifactView(ApiModel):
    id: uuid.UUID
    status: str
    original_filename: str
    expected_mime_type: str
    detected_mime_type: str | None
    size_bytes: int | None
    sha256: str | None
    receipt_at: datetime | None
    validated_at: datetime | None
    rejection_reason: str | None
    download_url: str | None = None


class DerivativeView(ApiModel):
    id: uuid.UUID
    artifact_id: uuid.UUID
    kind: str
    provider: str
    provider_version: str
    mime_type: str
    sha256: str
    confidence: float | None
    source_reference: str
    download_url: str | None = None


class EvidenceView(ApiModel):
    incident_id: uuid.UUID
    preserved_at: datetime | None
    artifacts: list[ArtifactView]
    derivatives: list[DerivativeView]
    custody_events: list[dict[str, Any]]
    limitation: str = "ADRIS supports preservation and review; it does not guarantee court admissibility."


class PreserveResponse(ApiModel):
    incident_id: uuid.UUID
    manifest_id: uuid.UUID
    status: str


class ExportCreateRequest(ApiModel):
    export_format: Literal["ZIP"] = "ZIP"


class ExportView(ApiModel):
    id: uuid.UUID
    incident_id: uuid.UUID
    status: str
    export_format: str
    sha256: str | None
    size_bytes: int | None
    created_at: datetime
    completed_at: datetime | None


class ExportCreated(ApiModel):
    export: ExportView
    job_id: uuid.UUID


class DownloadResponse(ApiModel):
    download_url: HttpUrl
    expires_in: int


class EventView(ApiModel):
    id: uuid.UUID
    event_type: str
    occurred_at: datetime
    actor_type: str
    resource_type: str
    resource_id: str
    event_data: dict[str, Any]


class ReviewRequest(ApiModel):
    review_task_id: uuid.UUID
    disposition: Literal[
        "CONFIRMED_PATTERN", "PLAUSIBLE", "INSUFFICIENT", "LEGITIMATE", "MALICIOUS_SUBMISSION"
    ]
    notes: str | None = Field(default=None, max_length=4000)
    reason_codes: list[str] = Field(default_factory=list, max_length=20)


class ReviewResponse(ApiModel):
    id: uuid.UUID
    incident_id: uuid.UUID
    review_task_id: uuid.UUID
    disposition: str
    status: str
    created_at: datetime


class CorrectionRequest(ApiModel):
    indicator_id: uuid.UUID | None = None
    signal_id: uuid.UUID | None = None
    field_name: Literal["normalized_value", "status", "code", "family", "strength"]
    corrected_value: str = Field(min_length=1, max_length=500)
    reason: str = Field(min_length=3, max_length=500)

    @model_validator(mode="after")
    def require_single_target(self) -> "CorrectionRequest":
        if (self.indicator_id is None) == (self.signal_id is None):
            raise ValueError("exactly one of indicator_id or signal_id is required")
        return self


class AnalystQueueItem(ApiModel):
    review_task_id: uuid.UUID
    incident_id: uuid.UUID
    priority: str
    status: str
    reason: str
    risk_band: str | None
    created_at: datetime


class AnalystIncidentView(ApiModel):
    incident: IncidentView
    artifacts: list[ArtifactView]
    derivatives: list[DerivativeView]
    indicators: list[AnalystIndicatorView]
    signals: list[SignalView]
    assessments: list[AssessmentView]
    agent_runs: list[AgentRunView]
    reviews: list[ReviewResponse]


class GraphNode(ApiModel):
    id: str
    label: str
    entity_type: str
    occurrence_count: int = 1
    risk_band: str | None = None


class GraphEdge(ApiModel):
    id: str
    source: str
    target: str
    relationship_type: str
    explanation: str
    weight: float


class GraphResponse(ApiModel):
    nodes: list[GraphNode]
    edges: list[GraphEdge]
    generated_at: datetime


class MapCell(ApiModel):
    h3_cell: str
    latitude: float
    longitude: float
    incident_count: int
    high_risk_count: int
    caution_count: int
    trend_ratio: float | None
    period_start: datetime
    period_end: datetime


class MapResponse(ApiModel):
    cells: list[MapCell]
    minimum_display_count: int
    privacy_note: str
    generated_at: datetime


class CapabilityView(ApiModel):
    name: str
    partner_type: str
    status: str
    adapter_status: str
    live: bool = False
