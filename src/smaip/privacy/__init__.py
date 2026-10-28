"""PII helpers used before logs and optional echoes.

The patterns are a small stdlib stand-in for serving hygiene. They are not a
detector and they are not a claim about coverage.
"""

from smaip.privacy.redact import redact_obj, redact_pii

__all__ = ["redact_obj", "redact_pii"]
