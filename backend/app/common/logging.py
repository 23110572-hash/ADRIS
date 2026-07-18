import logging
import re
import sys
from collections.abc import Mapping
from typing import Any

import structlog

_SENSITIVE_KEYS = re.compile(r"(authorization|token|secret|password|api[_-]?key|upi|account|prompt|evidence|content)", re.I)
_PHONE = re.compile(r"(?<!\d)(?:\+?91[-\s]?)?[6-9]\d{9}(?!\d)")
_UPI = re.compile(r"\b[\w.\-]{2,}@[a-zA-Z]{2,}\b")


def _redact_value(key: str, value: Any) -> Any:
    if _SENSITIVE_KEYS.search(key):
        return "[REDACTED]"
    if isinstance(value, str):
        return _UPI.sub("[UPI_REDACTED]", _PHONE.sub("[PHONE_REDACTED]", value))
    if isinstance(value, Mapping):
        return {str(k): _redact_value(str(k), v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_redact_value(key, item) for item in value]
    return value


def redact_pii(_: Any, __: str, event_dict: dict[str, Any]) -> dict[str, Any]:
    return {key: _redact_value(key, value) for key, value in event_dict.items()}


def configure_logging(level: str = "INFO") -> None:
    logging.basicConfig(format="%(message)s", stream=sys.stdout, level=level.upper(), force=True)
    shared = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        redact_pii,
    ]
    structlog.configure(
        processors=[*shared, structlog.processors.JSONRenderer()],
        wrapper_class=structlog.make_filtering_bound_logger(getattr(logging, level.upper(), logging.INFO)),
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )
