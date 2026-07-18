import hashlib
import hmac
from datetime import UTC, datetime
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.dependencies import Principal
from app.common.config import get_settings
from app.db.models import Incident, User

settings = get_settings()


def _email_hash(principal: Principal) -> str | None:
    email = principal.claims.get("email")
    if not isinstance(email, str) or not email:
        return None
    return hashlib.sha256(email.strip().lower().encode()).hexdigest()


def resolve_user(db: Session, principal: Principal) -> User | None:
    if not principal.authenticated:
        return None
    user = db.scalar(select(User).where(User.clerk_subject == principal.subject))
    if user is None:
        user = User(
            clerk_subject=principal.subject,
            email_hash=_email_hash(principal),
            display_name=principal.claims.get("name") if isinstance(principal.claims.get("name"), str) else None,
            last_authenticated_at=datetime.now(UTC),
        )
        db.add(user)
        db.flush()
    else:
        user.last_authenticated_at = datetime.now(UTC)
    return user


def incident_access_token(incident_id: UUID) -> str:
    secret = settings.incident_token_secret
    if not secret:
        if settings.app_env == "production":
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Anonymous access is unavailable")
        secret = "local-development-only-change-me"
    return hmac.new(secret.encode(), str(incident_id).encode(), hashlib.sha256).hexdigest()


def incident_token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def authorize_incident(
    incident: Incident,
    principal: Principal,
    supplied_token: str | None,
    user: User | None = None,
) -> None:
    if principal.roles.intersection({"ANALYST", "SUPERVISOR", "EVIDENCE_OFFICER", "ADMIN"}):
        return
    if user is not None and incident.owner_user_id == user.id:
        return
    if supplied_token and incident.access_token_hash:
        if hmac.compare_digest(incident.access_token_hash, incident_token_hash(supplied_token)):
            return
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Incident not found")
