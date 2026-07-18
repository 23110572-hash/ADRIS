from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWKClient

from app.common.config import get_settings

settings = get_settings()
bearer = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class Principal:
    subject: str
    roles: frozenset[str] = field(default_factory=frozenset)
    claims: dict[str, Any] = field(default_factory=dict)
    authenticated: bool = True
    mfa_verified: bool = False


ANONYMOUS = Principal(subject="anonymous", authenticated=False)


@lru_cache(maxsize=1)
def _jwks_client() -> PyJWKClient:
    if not settings.jwks_url:
        raise RuntimeError("JWKS_URL is not configured")
    return PyJWKClient(settings.jwks_url, cache_keys=True, lifespan=300)


def _roles_from_claims(claims: dict[str, Any]) -> frozenset[str]:
    candidates: list[Any] = [claims.get("roles"), claims.get("role")]
    for metadata_key in ("public_metadata", "metadata"):
        metadata = claims.get(metadata_key)
        if isinstance(metadata, dict):
            candidates.extend([metadata.get("roles"), metadata.get("role")])
    roles: set[str] = set()
    for value in candidates:
        if isinstance(value, str):
            roles.update(part.strip().upper() for part in value.split(",") if part.strip())
        elif isinstance(value, list):
            roles.update(str(part).upper() for part in value)
    if not roles:
        roles.add("CITIZEN")
    return frozenset(roles)


def _mfa_from_claims(claims: dict[str, Any]) -> bool:
    amr = claims.get("amr") or []
    if isinstance(amr, str):
        amr = [amr]
    if any(str(method).lower() in {"mfa", "otp", "totp", "webauthn"} for method in amr):
        return True
    fva = claims.get("fva")
    return bool(isinstance(fva, list) and len(fva) > 1 and fva[1] not in {-1, None})


def decode_token(token: str) -> Principal:
    if not settings.jwt_issuer or not settings.jwks_url:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Authentication is not configured")
    try:
        signing_key = _jwks_client().get_signing_key_from_jwt(token)
        kwargs: dict[str, Any] = {
            "key": signing_key.key,
            "algorithms": ["RS256"],
            "issuer": settings.jwt_issuer,
            "options": {"require": ["exp", "iat", "sub"]},
        }
        if settings.jwt_audience:
            kwargs["audience"] = settings.jwt_audience
        claims = jwt.decode(token, **kwargs)
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired access token") from exc
    return Principal(
        subject=str(claims["sub"]),
        roles=_roles_from_claims(claims),
        claims=claims,
        mfa_verified=_mfa_from_claims(claims),
    )


def optional_principal(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
) -> Principal:
    return ANONYMOUS if credentials is None else decode_token(credentials.credentials)


def authenticated_principal(principal: Principal = Depends(optional_principal)) -> Principal:
    if not principal.authenticated:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    return principal


def require_roles(*allowed_roles: str, require_mfa: bool = True):
    normalized = {role.upper() for role in allowed_roles}

    def dependency(principal: Principal = Depends(authenticated_principal)) -> Principal:
        if not principal.roles.intersection(normalized):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient role")
        if require_mfa and settings.app_env == "production" and not principal.mfa_verified:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="MFA is required for analyst access")
        return principal

    return dependency


analyst_principal = require_roles("ANALYST", "SUPERVISOR", "EVIDENCE_OFFICER", "ADMIN")
evidence_principal = require_roles("EVIDENCE_OFFICER", "SUPERVISOR", "ADMIN")
admin_principal = require_roles("ADMIN")
