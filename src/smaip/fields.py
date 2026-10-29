"""Allowlisted vendor fields.

Page prose is not a plan. The extractor keeps only labeled integers from a
fixed set of lines. Anything else, including an injected instruction, is
dropped before a specialist sees it.
"""

import re

from smaip.errors import ValidationError

FIELD_ORDER: tuple[str, ...] = (
    "revenue_last_quarter",
    "active_accounts",
    "dashboard_views",
    "exported_charts",
    "units_shipped",
    "repeat_orders",
    "regions_covered",
)

_LABELS: dict[str, str] = {
    "Revenue last quarter": "revenue_last_quarter",
    "Active accounts": "active_accounts",
    "Dashboard views": "dashboard_views",
    "Exported charts": "exported_charts",
    "Units shipped": "units_shipped",
    "Repeat orders": "repeat_orders",
    "Regions covered": "regions_covered",
}

_FIELD_LINE = re.compile(
    r"^(Revenue last quarter|Active accounts|Dashboard views|Exported charts|"
    r"Units shipped|Repeat orders|Regions covered):\s*(\d+)\.\s*$",
    re.MULTILINE,
)

PAGE_NAME_RE = re.compile(r"^[a-z0-9_]+\.md$")
MAX_CATALOG_READS = 8
_MAX_FIELD = 1_000_000_000


def extract_fields(text: str) -> dict[str, int]:
    """Pull labeled integers out of a page. Non-matching lines are ignored."""

    if not isinstance(text, str):
        return {}
    found: dict[str, int] = {}
    for match in _FIELD_LINE.finditer(text):
        key = _LABELS[match.group(1)]
        found[key] = int(match.group(2))
    return found


def coerce_field_map(fields: object) -> dict[str, int]:
    """Accept only the allowlisted integer keys. Strings are rejected."""

    if not isinstance(fields, dict):
        raise ValidationError("fields rejected")
    cleaned: dict[str, int] = {}
    allowed = set(FIELD_ORDER)
    for key, value in fields.items():
        if key not in allowed:
            raise ValidationError("fields rejected")
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValidationError("fields rejected")
        if value < 0 or value > _MAX_FIELD:
            raise ValidationError("fields rejected")
        cleaned[key] = value
    return cleaned


def digest_fields(fields: object) -> str:
    """Format a field map as data. This string is not executed."""

    cleaned = coerce_field_map(fields)
    if not cleaned:
        return "no numeric fields"
    return "\n".join(f"{key}={cleaned[key]}" for key in FIELD_ORDER if key in cleaned)
