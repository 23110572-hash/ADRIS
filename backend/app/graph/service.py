import hashlib
from datetime import UTC, datetime
from itertools import combinations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import EntityRelationship, Incident, Indicator


def _incident_hash(incident_id: object) -> str:
    return hashlib.sha256(str(incident_id).encode()).hexdigest()


def _upsert_edge(
    db: Session,
    *,
    incident: Incident,
    source_type: str,
    source_hash: str,
    source_label: str,
    target_type: str,
    target_hash: str,
    target_label: str,
    relationship_type: str,
    explanation: str,
) -> EntityRelationship:
    edge = db.scalar(
        select(EntityRelationship).where(
            EntityRelationship.source_type == source_type,
            EntityRelationship.source_value_hash == source_hash,
            EntityRelationship.target_type == target_type,
            EntityRelationship.target_value_hash == target_hash,
            EntityRelationship.relationship_type == relationship_type,
        )
    )
    if edge:
        edge.last_seen_at = datetime.now(UTC)
        edge.occurrence_count += 1
        edge.weight = min(10.0, 1.0 + edge.occurrence_count / 5)
        return edge
    edge = EntityRelationship(
        incident_id=incident.id,
        source_type=source_type,
        source_value_hash=source_hash,
        source_label=source_label,
        target_type=target_type,
        target_value_hash=target_hash,
        target_label=target_label,
        relationship_type=relationship_type,
        explanation=explanation,
        correlation_id=incident.correlation_id,
    )
    db.add(edge)
    return edge


def project_incident_graph(db: Session, incident: Incident) -> int:
    indicators = db.scalars(
        select(Indicator).where(Indicator.incident_id == incident.id, Indicator.status == "ACTIVE").limit(100)
    ).all()
    incident_hash = _incident_hash(incident.id)
    incident_label = f"Incident {str(incident.id)[:8]}"
    count = 0
    for indicator in indicators:
        _upsert_edge(
            db,
            incident=incident,
            source_type="INCIDENT",
            source_hash=incident_hash,
            source_label=incident_label,
            target_type=indicator.indicator_type,
            target_hash=indicator.normalized_value_hash,
            target_label=indicator.masked_value,
            relationship_type="MENTIONS",
            explanation=f"The incident contains this {indicator.indicator_type.lower()} indicator.",
        )
        count += 1
    for left, right in combinations(indicators[:20], 2):
        ordered = sorted([left, right], key=lambda item: (item.indicator_type, item.normalized_value_hash))
        _upsert_edge(
            db,
            incident=incident,
            source_type=ordered[0].indicator_type,
            source_hash=ordered[0].normalized_value_hash,
            source_label=ordered[0].masked_value,
            target_type=ordered[1].indicator_type,
            target_hash=ordered[1].normalized_value_hash,
            target_label=ordered[1].masked_value,
            relationship_type="CO_OCCURS_WITH",
            explanation="The governed indicators co-occur in one or more ADRIS incidents.",
        )
        count += 1
    return count
