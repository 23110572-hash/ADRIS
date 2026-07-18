import hashlib
import io
import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any
from urllib.parse import urlparse

import cv2
import numpy as np
import phonenumbers
from PIL import Image

EXTRACTOR_VERSION = "deterministic-extractors-v1.0.0"

URL_RE = re.compile(r"\b(?:https?://|www\.)[^\s<>()\[\]{}]+", re.I)
UPI_RE = re.compile(r"(?<![\w.])([a-zA-Z0-9.\-_]{2,}@[a-zA-Z]{2,})(?![\w.])")
PHONE_RE = re.compile(r"(?<!\d)(?:\+?91[\s-]?)?[6-9]\d(?:[\s-]?\d){8}(?!\d)")
AMOUNT_RE = re.compile(r"(?:₹|Rs\.?|INR)\s*([0-9][0-9,]*(?:\.\d{1,2})?)", re.I)
SHA_RE = re.compile(r"\b[a-fA-F0-9]{64}\b")
AGENCIES = {
    "cbi": "CBI",
    "central bureau of investigation": "CBI",
    "enforcement directorate": "ED",
    "ed officer": "ED",
    "customs": "CUSTOMS",
    "narcotics control bureau": "NCB",
    "ncb": "NCB",
    "police": "POLICE",
    "supreme court": "SUPREME_COURT",
    "rbi": "RBI",
    "reserve bank of india": "RBI",
    "telecom regulatory authority": "TRAI",
    "trai": "TRAI",
}


@dataclass(frozen=True)
class ExtractedIndicator:
    indicator_type: str
    normalized_value: str
    masked_value: str
    confidence: float
    source_reference: str
    extractor_version: str = EXTRACTOR_VERSION

    @property
    def value_hash(self) -> str:
        return hashlib.sha256(self.normalized_value.encode()).hexdigest()


def _reference(source: str, match: re.Match[str]) -> str:
    return f"{source}:chars:{match.start()}-{match.end()}"


def _mask(value: str, visible: int = 3) -> str:
    if len(value) <= visible * 2:
        return value[:1] + "***"
    return f"{value[:visible]}…{value[-visible:]}"


def extract_indicators(text: str, source: str = "submission:text") -> list[ExtractedIndicator]:
    found: list[ExtractedIndicator] = []
    seen: set[tuple[str, str, str]] = set()

    def add(indicator: ExtractedIndicator) -> None:
        key = (indicator.indicator_type, indicator.normalized_value, indicator.source_reference)
        if key not in seen:
            seen.add(key)
            found.append(indicator)

    for match in UPI_RE.finditer(text):
        value = match.group(1).lower()
        add(ExtractedIndicator("UPI_ID", value, _mask(value), 0.96, _reference(source, match)))
    for match in PHONE_RE.finditer(text):
        raw = match.group(0)
        try:
            parsed = phonenumbers.parse(raw, "IN")
            if not phonenumbers.is_possible_number(parsed):
                continue
            value = phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
        except phonenumbers.NumberParseException:
            continue
        add(ExtractedIndicator("PHONE_NUMBER", value, _mask(value, 2), 0.94, _reference(source, match)))
    for match in URL_RE.finditer(text):
        raw = match.group(0).rstrip(".,;:!?")
        normalized = raw if raw.lower().startswith(("http://", "https://")) else f"https://{raw}"
        parsed = urlparse(normalized)
        host = (parsed.hostname or "").lower().rstrip(".")
        if host:
            add(ExtractedIndicator("URL", normalized, _mask(normalized, 8), 0.98, _reference(source, match)))
            add(ExtractedIndicator("DOMAIN", host, _mask(host, 4), 0.99, _reference(source, match)))
    for match in AMOUNT_RE.finditer(text):
        try:
            amount = Decimal(match.group(1).replace(",", "")).quantize(Decimal("0.01"))
        except InvalidOperation:
            continue
        value = f"INR:{amount}"
        add(ExtractedIndicator("PAYMENT_AMOUNT", value, value, 0.97, _reference(source, match)))
    lowered = text.lower()
    for phrase, agency in AGENCIES.items():
        for match in re.finditer(rf"\b{re.escape(phrase)}\b", lowered):
            add(ExtractedIndicator("CLAIMED_AGENCY", agency, agency, 0.92, _reference(source, match)))
    for match in SHA_RE.finditer(text):
        value = match.group(0).lower()
        add(ExtractedIndicator("SHA256", value, _mask(value, 8), 0.99, _reference(source, match)))
    return found


def image_metadata(content: bytes) -> dict[str, Any]:
    with Image.open(io.BytesIO(content)) as image:
        return {
            "format": image.format,
            "width": image.width,
            "height": image.height,
            "mode": image.mode,
            "frames": getattr(image, "n_frames", 1),
            "metadata_version": "image-metadata-v1",
        }


def decode_qr(content: bytes) -> tuple[str | None, float]:
    array = np.frombuffer(content, dtype=np.uint8)
    image = cv2.imdecode(array, cv2.IMREAD_COLOR)
    if image is None:
        return None, 0.0
    detector = cv2.QRCodeDetector()
    value, points, _ = detector.detectAndDecode(image)
    return (value.strip() or None, 0.95 if value and points is not None else 0.0)


def deterministic_rule_signals(text: str, source: str = "submission:text") -> list[dict[str, Any]]:
    rules: list[tuple[str, str, str, float, str]] = [
        ("DIGITAL_ARREST_CLAIM", "AUTHORITY_IMPERSONATION", r"\bdigital\s+arrest\b", 0.99, "A fake digital-arrest process is claimed."),
        ("SAFE_ACCOUNT_TRANSFER", "PAYMENT_COERCION", r"\b(?:safe|secure|verification)\s+account\b", 0.96, "A transfer to a so-called safe or verification account is requested."),
        ("PAYMENT_URGENCY", "PAYMENT_COERCION", r"\b(?:transfer|pay|send)\b.{0,45}\b(?:now|immediately|urgent|today)\b", 0.88, "Urgent payment language is present."),
        ("LEGAL_THREAT", "THREAT_COERCION", r"\b(?:arrest|warrant|jail|case|seize|narcotics|money laundering)\b", 0.82, "Threatening legal or criminal language is present."),
        ("SECRECY_ISOLATION", "ISOLATION", r"\b(?:do not tell|don't tell|keep (?:this )?secret|stay on (?:the )?call|do not disconnect|alone)\b", 0.91, "Secrecy or isolation is requested."),
        ("CREDENTIAL_REQUEST", "CREDENTIAL_THEFT", r"\b(?:otp|one[- ]time password|pin|password|cvv)\b", 0.90, "Sensitive authentication information is requested or discussed."),
        ("REMOTE_ACCESS_REQUEST", "DEVICE_CONTROL", r"\b(?:anydesk|teamviewer|screen ?share|remote access|install (?:this|the) app)\b", 0.94, "Remote screen or device access is requested."),
        ("GOVERNMENT_IMPERSONATION", "AUTHORITY_IMPERSONATION", r"\b(?:cbi|enforcement directorate|customs|ncb|police|supreme court|rbi|trai)\b", 0.78, "A government, police, court, or regulator identity is claimed."),
    ]
    signals: list[dict[str, Any]] = []
    for code, family, pattern, confidence, explanation in rules:
        match = re.search(pattern, text, re.I | re.S)
        if match:
            signals.append(
                {
                    "code": code,
                    "family": family,
                    "severity": confidence,
                    "strength": "STRONG" if confidence >= 0.85 else "MODERATE",
                    "source": "DETERMINISTIC_RULE",
                    "evidence_reference": _reference(source, match),
                    "explanation": explanation,
                    "confidence": confidence,
                }
            )
    return signals
