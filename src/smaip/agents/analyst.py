"""Analyst specialist.

Summaries are built from allowlisted integer fields. Arithmetic stays in the
expression sandbox. The draft is a local mock completion over that digest.
There is no network, and page prose is not the prompt.
"""

import json

from smaip.errors import ValidationError
from smaip.fields import coerce_field_map, digest_fields
from smaip.serving.engines import MockEngine


def collect_extracts(messages: list[dict]) -> dict[str, int]:
    """Merge integer extracts. Raw page output is not parsed here."""

    merged: dict[str, int] = {}
    for message in messages:
        if message.get("kind") != "result" or message.get("tool") != "read_page":
            continue
        if message.get("ok") is not True:
            continue
        raw = message.get("content")
        if not isinstance(raw, str):
            continue
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            continue
        extract = payload.get("extract") if isinstance(payload, dict) else None
        if not isinstance(extract, dict):
            continue
        for key, value in extract.items():
            if isinstance(value, bool) or not isinstance(value, int):
                continue
            try:
                cleaned = coerce_field_map({key: value})
            except ValidationError:
                continue
            merged.update(cleaned)
    return merged


def summary_draft(digest: str) -> str:
    """Mock completion. The prompt is the field digest, not the page."""

    return MockEngine().complete([{"role": "user", "content": digest}])


def draft_from_messages(messages: list[dict]) -> str:
    return summary_draft(digest_fields(collect_extracts(messages)))


def present_summary(digest: str) -> tuple[str, str]:
    draft = summary_draft(digest)
    content = json.dumps({"digest": digest, "draft": draft}, sort_keys=True)
    return draft, content
