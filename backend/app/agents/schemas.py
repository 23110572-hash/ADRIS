from typing import Literal

from pydantic import BaseModel, Field


class SupervisorOutput(BaseModel):
    selected_agents: list[Literal["TRIAGE", "FORENSICS", "SCAM_ANALYSIS", "GRAPH", "GEO", "EVIDENCE", "CITIZEN_SAFETY"]]
    missing_information: list[str] = Field(default_factory=list)


class TriageOutput(BaseModel):
    priority: Literal["P1_ACTIVE_THREAT", "P2_HIGH", "P3_STANDARD", "P4_LOW"]
    suspected_type: Literal[
        "DIGITAL_ARREST", "GOVERNMENT_IMPERSONATION", "PAYMENT_FRAUD", "CREDENTIAL_THEFT", "OTHER", "UNCLEAR"
    ]
    payment_requested: bool
    active_threat: bool
    isolation_language_detected: bool
    immediate_guidance_required: bool
    confidence: float = Field(ge=0, le=1)


class SignalOutput(BaseModel):
    code: str = Field(max_length=80)
    family: str = Field(max_length=80)
    severity: float = Field(ge=0, le=1)
    strength: Literal["STRONG", "MODERATE", "WEAK"]
    evidence_reference: str = Field(max_length=255)
    explanation: str = Field(max_length=500)
    confidence: float = Field(ge=0, le=1)


class ScamAnalysisOutput(BaseModel):
    signals: list[SignalOutput] = Field(default_factory=list, max_length=20)
    disagreement_with_triage: bool = False


class CitizenSafetyOutput(BaseModel):
    explanation: str = Field(min_length=10, max_length=1200)
    acknowledged_limitations: list[str] = Field(default_factory=list, max_length=8)


class ForensicsOutput(BaseModel):
    input_quality: Literal["PASSED", "PARTIAL", "LOW_QUALITY", "UNSUPPORTED"]
    unavailable_sources: list[str] = Field(default_factory=list)


class EvidenceOutput(BaseModel):
    chronology: list[dict[str, str]] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
