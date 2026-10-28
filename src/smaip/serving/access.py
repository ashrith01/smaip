"""Structured access audit correlated by request id.

Entries stored on the app and lines written to `smaip.access` pass through
the same redaction step. The raw API key is never a field on the entry.
"""

import json
import logging
import re
from threading import Lock

from smaip.privacy import redact_obj

logger = logging.getLogger("smaip.access")

_REQUEST_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")


def configure_access_log(level_name: str) -> None:
    level = getattr(logging, level_name.upper(), logging.INFO)
    logger.setLevel(level)


def request_id_from_header(raw: str | None) -> str | None:
    if not raw:
        return None
    candidate = raw.strip()
    if _REQUEST_ID.fullmatch(candidate):
        return candidate
    return None


class RequestAudit:
    def __init__(self, max_entries: int = 512) -> None:
        self.max_entries = max_entries
        self.entries: list[dict] = []
        self._lock = Lock()

    def record(self, entry: dict) -> dict:
        safe = redact_obj(dict(entry))
        line = json.dumps(safe, sort_keys=True, default=str)
        with self._lock:
            self.entries.append(safe)
            overflow = len(self.entries) - self.max_entries
            if overflow > 0:
                del self.entries[:overflow]
        logger.info(line)
        return safe
