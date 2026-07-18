from datetime import UTC, datetime, timedelta

import h3
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import GeoAggregate, Incident, RiskAssessment

MINIMUM_DISPLAY_COUNT = 5
H3_RESOLUTION = 6


def validate_coarse_cell(cell: str | None) -> str | None:
    if not cell:
        return None
    if not h3.is_valid_cell(cell) or h3.get_resolution(cell) > H3_RESOLUTION:
        raise ValueError("Location must be a valid coarse H3 cell at resolution 6 or lower")
    return cell


def refresh_aggregates(db: Session) -> int:
    period_end = datetime.now(UTC)
    period_start = period_end - timedelta(days=30)
    cells = db.scalars(
        select(Incident.coarse_h3_cell)
        .where(Incident.coarse_h3_cell.is_not(None), Incident.created_at >= period_start)
        .distinct()
    ).all()
    refreshed = 0
    for cell in cells:
        if not cell:
            continue
        incident_ids = db.scalars(
            select(Incident.id).where(Incident.coarse_h3_cell == cell, Incident.created_at >= period_start)
        ).all()
        count = len(incident_ids)
        risk_rows = db.execute(
            select(RiskAssessment.risk_band, func.count(RiskAssessment.id))
            .where(RiskAssessment.incident_id.in_(incident_ids), RiskAssessment.status == "CURRENT")
            .group_by(RiskAssessment.risk_band)
        ).all() if incident_ids else []
        risks = {band: int(value) for band, value in risk_rows}
        aggregate = db.scalar(
            select(GeoAggregate).where(
                GeoAggregate.h3_cell == cell,
                GeoAggregate.period_start == period_start,
                GeoAggregate.period_end == period_end,
            )
        )
        if aggregate is None:
            sample = db.scalar(select(Incident).where(Incident.coarse_h3_cell == cell).limit(1))
            aggregate = GeoAggregate(
                h3_cell=cell,
                h3_resolution=h3.get_resolution(cell),
                district=sample.district if sample else None,
                state=sample.state if sample else None,
                period_start=period_start,
                period_end=period_end,
                incident_count=count,
                high_risk_count=risks.get("HIGH_RISK", 0),
                caution_count=risks.get("CAUTION", 0),
                minimum_display_count=MINIMUM_DISPLAY_COUNT,
                suppressed=count < MINIMUM_DISPLAY_COUNT,
                status="CURRENT",
            )
            db.add(aggregate)
        else:
            aggregate.incident_count = count
            aggregate.high_risk_count = risks.get("HIGH_RISK", 0)
            aggregate.caution_count = risks.get("CAUTION", 0)
            aggregate.suppressed = count < MINIMUM_DISPLAY_COUNT
        refreshed += 1
    return refreshed
