"""Logs may record sizes, status codes and message types. Not audio or secrets."""

from __future__ import annotations

import logging
import re

_BEARER = re.compile(r"(?i)\bBearer\s+\S+")
_TOKEN = re.compile(r"\bv1\.[0-9a-f:]+\.\d+\.[0-9a-f]{32}\b")
_ASSIGNED = re.compile(
    r"(?i)\b(api[_-]?key|token_secret|authorization|subscription[_-]?key|password)\b(\s*[:=]\s*)(\S+)"
)


def redact(text: str) -> str:
    text = _BEARER.sub("Bearer [redacted]", text)
    text = _TOKEN.sub("[redacted-token]", text)
    text = _ASSIGNED.sub(r"\1\2[redacted]", text)
    return text


class RedactFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        try:
            rendered = record.getMessage()
        except Exception:
            rendered = str(record.msg)
        record.msg = redact(rendered)
        record.args = ()
        return True


def install() -> None:
    logging.getLogger().addFilter(RedactFilter())
    for name in ("aiohttp.access", "aiohttp.client", "aiohttp.server"):
        logging.getLogger(name).addFilter(RedactFilter())
