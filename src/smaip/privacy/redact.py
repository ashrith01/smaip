"""Redact email addresses and phone numbers.

The phone pattern is intentionally narrow: a North-American grouped number,
a leading +country-code number, or a bare 10-digit run. It will still treat
some 10-digit identifiers as phones. It leaves short numbers, dates, and
dotted versions alone.
"""

import re

_EMAIL = re.compile(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b")

# Grouped NANP (optional country code), E.164 with a leading plus, or 10 digits.
_PHONE = re.compile(
    r"(?<!\d)(?:"
    r"(?:\+\d{1,3}[\s.\-]*)?(?:\(\d{3}\)|\d{3})[\s.\-]+\d{3}[\s.\-]+\d{4}"
    r"|\+\d{11,15}"
    r"|\d{10}"
    r")(?!\d)"
)

EMAIL_TOKEN = "[REDACTED_EMAIL]"
PHONE_TOKEN = "[REDACTED_PHONE]"


def redact_pii(text: str) -> str:
    """Replace emails and phone numbers. Safe to call more than once."""
    if not text:
        return text
    redacted = _EMAIL.sub(EMAIL_TOKEN, text)
    return _PHONE.sub(PHONE_TOKEN, redacted)


def redact_obj(value):
    """Walk strings inside JSON-like objects and redact them."""
    if isinstance(value, str):
        return redact_pii(value)
    if isinstance(value, list):
        return [redact_obj(item) for item in value]
    if isinstance(value, tuple):
        return [redact_obj(item) for item in value]
    if isinstance(value, dict):
        return {str(key): redact_obj(item) for key, item in value.items()}
    return value
