import hashlib
import io
import re
import uuid
from dataclasses import dataclass
from functools import lru_cache
from typing import BinaryIO

import boto3
import filetype
from botocore.client import BaseClient
from botocore.config import Config
from fastapi import HTTPException, status

from app.common.config import get_settings

settings = get_settings()
_FILENAME = re.compile(r"[^A-Za-z0-9._-]+")

ALLOWED_UPLOAD_MIMES = {
    "SCREENSHOT": {"image/jpeg", "image/png", "image/webp", "application/pdf"},
    "DOCUMENT": {"image/jpeg", "image/png", "image/webp", "application/pdf"},
    "QR": {"image/jpeg", "image/png", "image/webp"},
    "AUDIO": {"audio/mpeg", "audio/wav", "audio/x-wav", "audio/ogg", "audio/webm", "audio/mp4", "video/webm"},
}


@dataclass(frozen=True)
class ValidatedObject:
    size_bytes: int
    detected_mime_type: str
    sha256: str
    evidence_key: str
    evidence_version_id: str | None
    quarantine_version_id: str | None


def sanitize_filename(filename: str) -> str:
    value = _FILENAME.sub("_", filename.rsplit("/", 1)[-1].rsplit("\\", 1)[-1]).strip("._")
    return (value or "upload")[:180]


def assert_upload_allowed(submission_type: str, content_type: str, size_bytes: int) -> None:
    if content_type not in ALLOWED_UPLOAD_MIMES.get(submission_type, set()):
        raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail="File type is not supported for this check")
    if size_bytes > settings.max_upload_bytes:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="File exceeds the configured upload limit")


def _encryption_args() -> dict[str, str]:
    # S3-compatible providers (e.g. Supabase Storage) reject AWS SSE headers and encrypt at rest themselves.
    if settings.s3_endpoint_url:
        return {}
    if settings.aws_kms_key_id:
        return {"ServerSideEncryption": "aws:kms", "SSEKMSKeyId": settings.aws_kms_key_id}
    return {"ServerSideEncryption": "AES256"}


@lru_cache(maxsize=1)
def s3_client() -> BaseClient:
    config_kwargs: dict[str, object] = {"signature_version": "s3v4", "retries": {"max_attempts": 3, "mode": "standard"}}
    if settings.s3_endpoint_url:
        # Non-AWS S3 endpoints require path-style addressing (endpoint/bucket/key).
        config_kwargs["s3"] = {"addressing_style": "path"}
    kwargs: dict[str, object] = {
        "region_name": settings.aws_region,
        "config": Config(**config_kwargs),
    }
    if settings.s3_endpoint_url:
        kwargs["endpoint_url"] = settings.s3_endpoint_url
    if settings.aws_access_key_id and settings.aws_secret_access_key:
        kwargs.update(
            aws_access_key_id=settings.aws_access_key_id,
            aws_secret_access_key=settings.aws_secret_access_key,
        )
    return boto3.client("s3", **kwargs)


def require_s3() -> None:
    if not settings.s3_ready:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Evidence storage is not configured")


def quarantine_key(incident_id: uuid.UUID, artifact_id: uuid.UUID, filename: str) -> str:
    return f"quarantine/{incident_id}/{artifact_id}/{sanitize_filename(filename)}"


def create_presigned_upload(
    *, incident_id: uuid.UUID, artifact_id: uuid.UUID, filename: str, content_type: str
) -> tuple[str, str, dict[str, str]]:
    require_s3()
    key = quarantine_key(incident_id, artifact_id, filename)
    metadata = {"incident-id": str(incident_id), "artifact-id": str(artifact_id), "schema": "upload-v1"}
    params = {
        "Bucket": settings.s3_quarantine_bucket,
        "Key": key,
        "ContentType": content_type,
        "Metadata": metadata,
        **_encryption_args(),
    }
    url = s3_client().generate_presigned_url(
        "put_object", Params=params, ExpiresIn=settings.presign_ttl_seconds, HttpMethod="PUT"
    )
    headers = {
        "Content-Type": content_type,
        "x-amz-meta-incident-id": str(incident_id),
        "x-amz-meta-artifact-id": str(artifact_id),
        "x-amz-meta-schema": "upload-v1",
    }
    if "ServerSideEncryption" in params:
        headers["x-amz-server-side-encryption"] = params["ServerSideEncryption"]
    if settings.aws_kms_key_id and not settings.s3_endpoint_url:
        headers["x-amz-server-side-encryption-aws-kms-key-id"] = settings.aws_kms_key_id
    return key, url, headers


def _detect_mime(prefix: bytes, expected: str) -> str:
    kind = filetype.guess(prefix)
    if kind:
        return kind.mime
    if expected.startswith("text/"):
        return expected
    if prefix.startswith(b"RIFF") and b"WAVE" in prefix[:16]:
        return "audio/wav"
    if prefix.startswith(b"OggS"):
        return "audio/ogg"
    if b"ftyp" in prefix[:16]:
        return "audio/mp4"
    return "application/octet-stream"


def validate_and_promote(
    *,
    incident_id: uuid.UUID,
    artifact_id: uuid.UUID,
    quarantine_key_value: str,
    expected_mime: str,
    expected_max_bytes: int,
) -> ValidatedObject:
    require_s3()
    client = s3_client()
    head = client.head_object(Bucket=settings.s3_quarantine_bucket, Key=quarantine_key_value)
    size = int(head["ContentLength"])
    if size <= 0 or size > expected_max_bytes:
        raise ValueError("INVALID_FILE_SIZE")
    metadata = head.get("Metadata", {})
    if metadata.get("incident-id") != str(incident_id) or metadata.get("artifact-id") != str(artifact_id):
        raise ValueError("UPLOAD_METADATA_MISMATCH")

    response = client.get_object(Bucket=settings.s3_quarantine_bucket, Key=quarantine_key_value)
    body: BinaryIO = response["Body"]
    digest = hashlib.sha256()
    prefix = b""
    total = 0
    while chunk := body.read(1024 * 1024):
        if len(prefix) < 8192:
            prefix += chunk[: 8192 - len(prefix)]
        total += len(chunk)
        if total > expected_max_bytes:
            raise ValueError("INVALID_FILE_SIZE")
        digest.update(chunk)
    detected = _detect_mime(prefix, expected_mime)
    allowed = {expected_mime}
    if expected_mime in {"audio/mpeg", "audio/mp4", "video/webm"}:
        allowed.update({"audio/mpeg", "audio/mp4", "video/mp4", "video/webm", "application/octet-stream"})
    if detected not in allowed:
        raise ValueError("CONTENT_TYPE_MISMATCH")

    evidence_key = f"evidence/{incident_id}/{artifact_id}/original/{quarantine_key_value.rsplit('/', 1)[-1]}"
    copy = client.copy_object(
        Bucket=settings.s3_evidence_bucket,
        Key=evidence_key,
        CopySource={"Bucket": settings.s3_quarantine_bucket, "Key": quarantine_key_value},
        MetadataDirective="COPY",
        **_encryption_args(),
    )
    client.delete_object(Bucket=settings.s3_quarantine_bucket, Key=quarantine_key_value)
    return ValidatedObject(
        size_bytes=size,
        detected_mime_type=detected,
        sha256=digest.hexdigest(),
        evidence_key=evidence_key,
        evidence_version_id=copy.get("VersionId"),
        quarantine_version_id=head.get("VersionId"),
    )


def get_object_bytes(bucket: str, key: str, max_bytes: int | None = None) -> bytes:
    limit = max_bytes or settings.max_upload_bytes
    response = s3_client().get_object(Bucket=bucket, Key=key)
    stream = response["Body"]
    output = io.BytesIO()
    total = 0
    while chunk := stream.read(1024 * 1024):
        total += len(chunk)
        if total > limit:
            raise ValueError("OBJECT_TOO_LARGE")
        output.write(chunk)
    return output.getvalue()


def put_private_bytes(bucket: str, key: str, content: bytes, content_type: str, metadata: dict[str, str] | None = None) -> dict:
    return s3_client().put_object(
        Bucket=bucket,
        Key=key,
        Body=content,
        ContentType=content_type,
        Metadata=metadata or {},
        **_encryption_args(),
    )


def presign_download(bucket: str, key: str, filename: str | None = None) -> str:
    params: dict[str, str] = {"Bucket": bucket, "Key": key}
    if filename:
        params["ResponseContentDisposition"] = f'attachment; filename="{sanitize_filename(filename)}"'
    return s3_client().generate_presigned_url(
        "get_object", Params=params, ExpiresIn=settings.presign_ttl_seconds, HttpMethod="GET"
    )
