import hashlib
import json

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import IdempotencyRecord


def request_hash(payload: object) -> str:
    raw = json.dumps(payload, sort_keys=True, default=str, separators=(",", ":")).encode()
    return hashlib.sha256(raw).hexdigest()


def find_idempotent(
    db: Session, *, scope: str, key: str, payload: object
) -> IdempotencyRecord | None:
    record = db.scalar(
        select(IdempotencyRecord).where(
            IdempotencyRecord.scope == scope,
            IdempotencyRecord.idempotency_key == key,
        )
    )
    if record and record.request_hash != request_hash(payload):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Idempotency key was already used with a different request",
        )
    return record


def save_idempotent(
    db: Session,
    *,
    scope: str,
    key: str,
    payload: object,
    resource_type: str,
    resource_id: str,
    response_code: int,
) -> IdempotencyRecord:
    record = IdempotencyRecord(
        scope=scope,
        idempotency_key=key,
        request_hash=request_hash(payload),
        resource_type=resource_type,
        resource_id=resource_id,
        response_code=response_code,
    )
    db.add(record)
    return record
