"""PII redaction stays on the stdlib and does not eat ordinary numbers."""

from smaip.privacy import redact_obj, redact_pii
from smaip.privacy.redact import EMAIL_TOKEN, PHONE_TOKEN


def test_email_is_replaced_and_surrounding_text_stays():
    text = "mail ada@example.com and attacker@evil.example today"
    redacted = redact_pii(text)
    assert "ada@example.com" not in redacted
    assert "attacker@evil.example" not in redacted
    assert redacted.count(EMAIL_TOKEN) == 2
    assert redacted.startswith("mail ")
    assert redacted.endswith(" today")


def test_phone_shapes():
    samples = [
        "415-555-0199",
        "(415) 555-0199",
        "415.555.0199",
        "+1 415 555 0199",
        "+14155550199",
        "4155550199",
    ]
    for sample in samples:
        redacted = redact_pii(f"call {sample} now")
        assert sample not in redacted
        assert PHONE_TOKEN in redacted
        assert redacted.startswith("call ")
        assert redacted.endswith(" now")


def test_short_numbers_dates_and_versions_stay():
    text = "version 1.2.3 on port 8000 in year 2026-10-28 id 120000"
    assert redact_pii(text) == text


def test_redaction_is_idempotent():
    once = redact_pii("ada@example.com / 415-555-0199")
    assert redact_pii(once) == once


def test_redact_obj_walks_nested_json():
    payload = {
        "messages": [{"content": "ping ada@example.com"}],
        "n": 3,
        "ok": True,
    }
    redacted = redact_obj(payload)
    assert redacted["n"] == 3
    assert redacted["ok"] is True
    assert "ada@example.com" not in str(redacted)
    assert EMAIL_TOKEN in redacted["messages"][0]["content"]
