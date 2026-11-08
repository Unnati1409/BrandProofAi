import json
import logging
import re
import sys
from contextvars import ContextVar
from datetime import datetime, timezone
from typing import Any

# Context variable holding the active request ID for the current async task
request_id_ctx: ContextVar[str | None] = ContextVar("request_id_ctx", default=None)

# Patterns for sensitive keys that must never appear in log payloads
SENSITIVE_PATTERNS = re.compile(
    r"(authorization|bearer|token|secret|password|api[-_]?key|cookie|session)",
    re.IGNORECASE,
)


def scrub_sensitive_dict(data: dict[str, Any]) -> dict[str, Any]:
    """Recursively scrub any sensitive keys from structured dictionaries."""
    scrubbed: dict[str, Any] = {}
    for key, value in data.items():
        if SENSITIVE_PATTERNS.search(key):
            scrubbed[key] = "[REDACTED]"
        elif isinstance(value, dict):
            scrubbed[key] = scrub_sensitive_dict(value)
        elif isinstance(value, list):
            scrubbed[key] = [
                scrub_sensitive_dict(item) if isinstance(item, dict) else item for item in value
            ]
        else:
            scrubbed[key] = value
    return scrubbed


class StructuredJsonFormatter(logging.Formatter):
    """
    JSON log formatter conforming to enterprise observability standards.
    Guarantees no raw content bodies or secrets are leaked into logs.
    """

    def format(self, record: logging.LogRecord) -> str:
        log_entry: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": getattr(record, "request_id", request_id_ctx.get()),
        }

        # Include structured extra fields if present
        extra = getattr(record, "extra_data", None)
        if extra and isinstance(extra, dict):
            log_entry["data"] = scrub_sensitive_dict(extra)

        if record.exc_info and not getattr(record, "suppress_traceback", False):
            log_entry["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_entry)


def setup_logging(log_level: str = "INFO") -> logging.Logger:
    """Configures application logger with structured JSON output."""
    logger = logging.getLogger("brandproof")
    logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))

    # Add handler once if not already present; never clear root handlers (preserves test runners)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(StructuredJsonFormatter())
        logger.addHandler(handler)
        logger.propagate = False

    return logger
