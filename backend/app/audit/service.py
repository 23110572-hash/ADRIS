import hashlib
import json
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from app.db.models import AuditEvent, CustodyEvent, User


def payload_hash(data: Any) -> str:
    encoded = json.dumps(data, sort_keys=True, default=str, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def record_audit(
    db: Session,
    *,
    event_type: str,
    resource_type: str,
    resource_id: str,
    purpose_code: str,
    correlation_id: uuid.UUID,
    user: User | None = None,
    incident_id: uuid.UUID | None = None,
    actor_reference: str = "ADRIS_SYSTEM",
    authority_reference: str | None = None,
    idempotency_key: str | None = None,
    event_data: dict[str, Any] | None = None,
    client_ip: str | None = None,
    classification: str = "INTERNAL",
) -> AuditEvent:
    safe_data = event_data or {}
    event = AuditEvent(
        event_type=event_type,
        actor_type="USER" if user else "SYSTEM",
        actor_reference=str(user.id) if user else actor_reference,
        user_id=user.id if user else None,
        incident_id=incident_id,
        resource_type=resource_type,
        resource_id=resource_id,
        purpose_code=purpose_code,
        authority_reference=authority_reference,
        idempotency_key=idempotency_key,
        classification=classification,
        payload_hash=payload_hash(safe_data),
        client_ip_hash=hashlib.sha256(client_ip.encode()).hexdigest() if client_ip else None,
        event_data=safe_data,
        correlation_id=correlation_id,
        occurred_at=datetime.now(UTC),
        received_at=datetime.now(UTC),
    )
    db.add(event)
    return event


def record_custody(
    db: Session,
    *,
    incident_id: uuid.UUID,
    artifact_id: uuid.UUID | None,
    event_type: str,
    from_location: str | None,
    to_location: str | None,
    details: dict[str, Any],
    correlation_id: uuid.UUID,
    actor_reference: str = "ADRIS_WORKER",
    purpose_code: str = "EVIDENCE_PRESERVATION",
) -> CustodyEvent:
    event = CustodyEvent(
        incident_id=incident_id,
        artifact_id=artifact_id,
        event_type=event_type,
        actor_type="SYSTEM",
        actor_reference=actor_reference,
        from_location=from_location,
        to_location=to_location,
        purpose_code=purpose_code,
        payload_hash=payload_hash(details),
        details=details,
        correlation_id=correlation_id,
    )
    db.add(event)
    return event
