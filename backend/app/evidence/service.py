import hashlib
import io
import json
import textwrap
import uuid
import zipfile
from datetime import UTC, datetime
from typing import Any

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from reportlab.lib import colors
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.artifacts.storage import put_private_bytes
from app.audit.service import record_custody
from app.common.config import get_settings
from app.db.models import (
    AgentRun,
    Artifact,
    ArtifactDerivative,
    CustodyEvent,
    EvidenceManifest,
    Incident,
    Indicator,
    ReportExport,
    ReviewDisposition,
    RiskAssessment,
    Signal,
)

settings = get_settings()
MANIFEST_VERSION = "evidence-manifest-v1"
REPORT_VERSION = "evidence-report-v1"


def _iso(value: datetime | None) -> str | None:
    return value.astimezone(UTC).isoformat() if value else None


def build_manifest_data(db: Session, incident: Incident) -> dict[str, Any]:
    artifacts = db.scalars(select(Artifact).where(Artifact.incident_id == incident.id).order_by(Artifact.created_at)).all()
    derivatives = db.scalars(
        select(ArtifactDerivative).where(ArtifactDerivative.incident_id == incident.id).order_by(ArtifactDerivative.created_at)
    ).all()
    indicators = db.scalars(select(Indicator).where(Indicator.incident_id == incident.id).order_by(Indicator.created_at)).all()
    signals = db.scalars(select(Signal).where(Signal.incident_id == incident.id).order_by(Signal.created_at)).all()
    assessments = db.scalars(
        select(RiskAssessment).where(RiskAssessment.incident_id == incident.id).order_by(RiskAssessment.created_at)
    ).all()
    runs = db.scalars(select(AgentRun).where(AgentRun.incident_id == incident.id).order_by(AgentRun.created_at)).all()
    custody = db.scalars(select(CustodyEvent).where(CustodyEvent.incident_id == incident.id).order_by(CustodyEvent.occurred_at)).all()
    reviews = db.scalars(
        select(ReviewDisposition).where(ReviewDisposition.incident_id == incident.id).order_by(ReviewDisposition.created_at)
    ).all()
    return {
        "schema_version": MANIFEST_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "incident": {
            "id": str(incident.id),
            "created_at": _iso(incident.created_at),
            "submission_type": incident.submission_type,
            "status": incident.status,
            "correlation_id": str(incident.correlation_id),
        },
        "original_artifacts": [
            {
                "id": str(item.id),
                "filename": item.original_filename,
                "detected_mime_type": item.detected_mime_type,
                "size_bytes": item.size_bytes,
                "sha256": item.sha256,
                "receipt_at": _iso(item.receipt_at),
                "validated_at": _iso(item.validated_at),
                "evidence_object": {"bucket": item.evidence_bucket, "key": item.evidence_key, "version_id": item.evidence_version_id},
            }
            for item in artifacts
            if item.status == "ACCEPTED"
        ],
        "derivatives": [
            {
                "id": str(item.id),
                "source_artifact_id": str(item.artifact_id),
                "kind": item.kind,
                "provider": item.provider,
                "provider_version": item.provider_version,
                "transformation_version": item.transformation_version,
                "sha256": item.sha256,
                "source_reference": item.source_reference,
                "object": {"bucket": item.bucket, "key": item.object_key},
            }
            for item in derivatives
        ],
        "indicators": [
            {
                "id": str(item.id),
                "type": item.indicator_type,
                "normalized_value": item.normalized_value,
                "value_hash": item.normalized_value_hash,
                "confidence": item.confidence,
                "source_reference": item.source_reference,
                "extractor_version": item.extractor_version,
                "status": item.status,
            }
            for item in indicators
        ],
        "signals": [
            {
                "id": str(item.id),
                "code": item.code,
                "family": item.family,
                "severity": item.severity,
                "strength": item.strength,
                "evidence_reference": item.evidence_reference,
                "source": item.source,
                "status": item.status,
            }
            for item in signals
        ],
        "assessments": [
            {
                "id": str(item.id),
                "risk_band": item.risk_band,
                "policy_version": item.policy_version,
                "reason_codes": item.reason_codes,
                "coverage": item.coverage,
                "missing_sources": item.missing_sources,
                "agent_disagreement": item.agent_disagreement,
                "created_at": _iso(item.created_at),
            }
            for item in assessments
        ],
        "agent_runs": [
            {
                "id": str(item.id),
                "agent": item.agent_name,
                "status": item.status,
                "model_provider": item.model_provider,
                "model_name": item.model_name,
                "prompt_version": item.prompt_version,
                "agent_version": item.agent_version,
                "tool_versions": item.tool_versions,
                "created_at": _iso(item.created_at),
            }
            for item in runs
        ],
        "custody_events": [
            {
                "id": str(item.id),
                "event_type": item.event_type,
                "artifact_id": str(item.artifact_id) if item.artifact_id else None,
                "occurred_at": _iso(item.occurred_at),
                "from": item.from_location,
                "to": item.to_location,
                "payload_hash": item.payload_hash,
            }
            for item in custody
        ],
        "human_reviews": [
            {
                "id": str(item.id),
                "disposition": item.disposition,
                "reason_codes": item.reason_codes,
                "authority": item.authority,
                "created_at": _iso(item.created_at),
            }
            for item in reviews
        ],
        "limitations": [
            "ADRIS records provenance and chain-of-custody events but does not guarantee court admissibility.",
            "No unavailable institutional source is represented as checked or clear.",
            "Risk assessments are decision support and do not declare criminal guilt.",
        ],
    }


def seal_manifest(db: Session, incident: Incident) -> EvidenceManifest:
    data = build_manifest_data(db, incident)
    encoded = json.dumps(data, ensure_ascii=False, sort_keys=True, indent=2).encode("utf-8")
    digest = hashlib.sha256(encoded).hexdigest()
    manifest = EvidenceManifest(
        incident_id=incident.id,
        status="SEALED",
        schema_version=MANIFEST_VERSION,
        bucket=settings.s3_exports_bucket,
        object_key=f"manifests/{incident.id}/{uuid.uuid4()}/evidence-manifest.json",
        sha256=digest,
        manifest_data=data,
        sealed_at=datetime.now(UTC),
        correlation_id=incident.correlation_id,
    )
    put_private_bytes(
        settings.s3_exports_bucket,
        manifest.object_key,
        encoded,
        "application/json",
        {"incident-id": str(incident.id), "sha256": digest, "schema": MANIFEST_VERSION},
    )
    db.add(manifest)
    incident.preserved_at = incident.preserved_at or datetime.now(UTC)
    db.flush()
    record_custody(
        db,
        incident_id=incident.id,
        artifact_id=None,
        event_type="MANIFEST_SEALED",
        from_location=None,
        to_location=f"s3://{settings.s3_exports_bucket}/{manifest.object_key}",
        details={"manifest_id": str(manifest.id), "sha256": digest, "schema_version": MANIFEST_VERSION},
        correlation_id=incident.correlation_id,
    )
    return manifest


def _pdf_bytes(manifest: dict[str, Any]) -> bytes:
    output = io.BytesIO()
    doc = SimpleDocTemplate(
        output,
        pagesize=A4,
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
        title="ADRIS Evidence Chronology",
        author="ADRIS",
    )
    styles = getSampleStyleSheet()
    story: list[Any] = [
        Paragraph("ADRIS Evidence Chronology", styles["Title"]),
        Paragraph(f"Report version: {REPORT_VERSION}", styles["Normal"]),
        Spacer(1, 8),
        Paragraph("Important limitation", styles["Heading2"]),
        Paragraph("This package supports evidence review and certificate preparation. ADRIS does not guarantee legal admissibility and does not declare any person guilty.", styles["BodyText"]),
        Spacer(1, 10),
        Paragraph("Incident", styles["Heading2"]),
    ]
    incident = manifest["incident"]
    story.append(Table([["Incident ID", incident["id"]], ["Received", incident["created_at"]], ["Submission", incident["submission_type"]], ["Status", incident["status"]]], colWidths=[42 * mm, 125 * mm], style=TableStyle([("GRID", (0, 0), (-1, -1), 0.4, colors.grey), ("BACKGROUND", (0, 0), (0, -1), colors.whitesmoke), ("VALIGN", (0, 0), (-1, -1), "TOP")])))
    story.extend([Spacer(1, 12), Paragraph("Original artifact inventory", styles["Heading2"])])
    rows = [["File", "SHA-256", "Received"]]
    for artifact in manifest["original_artifacts"]:
        rows.append([artifact["filename"], "\n".join(textwrap.wrap(artifact["sha256"] or "Pending", 32)), artifact["receipt_at"] or "-"])
    if len(rows) == 1:
        rows.append(["No uploaded artifact", "-", "-"])
    story.append(Table(rows, repeatRows=1, colWidths=[50 * mm, 75 * mm, 42 * mm], style=TableStyle([("GRID", (0, 0), (-1, -1), 0.4, colors.grey), ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey), ("FONTSIZE", (0, 0), (-1, -1), 8), ("VALIGN", (0, 0), (-1, -1), "TOP")])))
    story.extend([Spacer(1, 12), Paragraph("Assessment chronology", styles["Heading2"])])
    for assessment in manifest["assessments"]:
        story.append(Paragraph(f"{assessment['created_at']}: {assessment['risk_band']} — reasons: {', '.join(assessment['reason_codes'])}", styles["BodyText"]))
    story.extend([PageBreak(), Paragraph("Bharatiya Sakshya Adhiniyam Section 63 certificate worksheet", styles["Heading1"]), Paragraph("This is a worksheet for completion and signature by the responsible person. It is not an automatically issued legal certificate.", styles["BodyText"]), Spacer(1, 10)])
    worksheet = [
        ["System/device producing the electronic record", "ADRIS deployment details to be completed by responsible person"],
        ["Method and ordinary course of production", "Review deployment, S3 versioning, receipt, hashing, and export records"],
        ["Integrity particulars", f"Manifest schema {manifest['schema_version']}; verify listed SHA-256 hashes"],
        ["Relevant period", f"From {incident['created_at']} to {manifest['generated_at']}"],
        ["Responsible person's name and role", "________________________________________"],
        ["Signature, place, and date", "________________________________________"],
    ]
    story.append(Table(worksheet, colWidths=[65 * mm, 102 * mm], style=TableStyle([("GRID", (0, 0), (-1, -1), 0.5, colors.grey), ("VALIGN", (0, 0), (-1, -1), "TOP"), ("FONTSIZE", (0, 0), (-1, -1), 9), ("BACKGROUND", (0, 0), (0, -1), colors.whitesmoke)])))
    doc.build(story)
    return output.getvalue()


def generate_export_package(db: Session, export: ReportExport) -> ReportExport:
    incident = db.get(Incident, export.incident_id)
    if incident is None:
        raise ValueError("INCIDENT_NOT_FOUND")
    manifest = db.get(EvidenceManifest, export.manifest_id) if export.manifest_id else None
    if manifest is None or manifest.status != "SEALED":
        manifest = seal_manifest(db, incident)
        db.flush()
        export.manifest_id = manifest.id
    manifest_bytes = json.dumps(manifest.manifest_data, ensure_ascii=False, sort_keys=True, indent=2).encode("utf-8")
    pdf = _pdf_bytes(manifest.manifest_data)
    base = f"exports/{incident.id}/{export.id}"
    json_key = f"{base}/evidence-manifest.json"
    pdf_key = f"{base}/evidence-chronology.pdf"
    put_private_bytes(settings.s3_exports_bucket, json_key, manifest_bytes, "application/json", {"incident-id": str(incident.id)})
    put_private_bytes(settings.s3_exports_bucket, pdf_key, pdf, "application/pdf", {"incident-id": str(incident.id), "report-version": REPORT_VERSION})
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, mode="w", compression=zipfile.ZIP_DEFLATED) as package:
        package.writestr("evidence-manifest.json", manifest_bytes)
        package.writestr("evidence-chronology.pdf", pdf)
        package.writestr("README.txt", "ADRIS supports evidence review and Section 63 certificate preparation. This package does not guarantee court admissibility.\n")
    content = archive.getvalue()
    digest = hashlib.sha256(content).hexdigest()
    zip_key = f"{base}/adris-evidence-package.zip"
    put_private_bytes(settings.s3_exports_bucket, zip_key, content, "application/zip", {"incident-id": str(incident.id), "sha256": digest})
    export.bucket = settings.s3_exports_bucket
    export.object_key = zip_key
    export.sha256 = digest
    export.size_bytes = len(content)
    export.details = {"json_key": json_key, "pdf_key": pdf_key, "manifest_version": MANIFEST_VERSION, "report_version": REPORT_VERSION}
    export.status = "COMPLETED"
    export.completed_at = datetime.now(UTC)
    record_custody(
        db,
        incident_id=incident.id,
        artifact_id=None,
        event_type="EVIDENCE_EXPORT_GENERATED",
        from_location=f"manifest:{manifest.id}",
        to_location=f"s3://{settings.s3_exports_bucket}/{zip_key}",
        details={"export_id": str(export.id), "sha256": digest, "size_bytes": len(content)},
        correlation_id=incident.correlation_id,
    )
    return export
