from typing import Any

from pydantic import BaseModel, Field


class IndicatorState(BaseModel):
    indicator_type: str
    normalized_value_hash: str
    masked_value: str
    confidence: float
    source_reference: str


class SignalState(BaseModel):
    code: str
    family: str
    severity: float
    strength: str
    source: str
    evidence_reference: str
    explanation: str
    confidence: float
    agent_run_id: str | None = None


class TriageResult(BaseModel):
    priority: str
    suspected_type: str
    payment_requested: bool
    active_threat: bool
    isolation_language_detected: bool
    immediate_guidance_required: bool
    confidence: float


class RelationshipState(BaseModel):
    source_id: str
    target_id: str
    relationship_type: str
    explanation: str
    occurrence_count: int


class GeoSummary(BaseModel):
    h3_cell: str | None = None
    incident_count: int = 0
    trend_ratio: float | None = None
    suppressed: bool = True
    limitation: str = "Victim report location must not be treated as offender location."


class AgentRunRef(BaseModel):
    run_id: str
    agent_name: str
    status: str


class IncidentState(BaseModel):
    incident_id: str
    language: str | None = None
    artifact_references: list[str] = Field(default_factory=list)
    extracted_text: list[str] = Field(default_factory=list)
    indicators: list[IndicatorState] = Field(default_factory=list)
    selected_agents: list[str] = Field(default_factory=list)
    triage_result: TriageResult | None = None
    scam_signals: list[SignalState] = Field(default_factory=list)
    graph_matches: list[RelationshipState] = Field(default_factory=list)
    geographic_summary: GeoSummary | None = None
    unavailable_sources: list[str] = Field(default_factory=list)
    agent_runs: list[AgentRunRef] = Field(default_factory=list)
    proposed_explanation: str | None = None
    safety_actions: list[str] = Field(default_factory=list)
    final_risk_band: str | None = None
    policy_reason_codes: list[str] = Field(default_factory=list)
    policy_coverage: dict[str, Any] = Field(default_factory=dict)
    agent_disagreement: bool = False
    input_quality: str = "PENDING"
    evidence_manifest_id: str | None = None
    evidence_manifest_draft: dict[str, Any] = Field(default_factory=dict)
