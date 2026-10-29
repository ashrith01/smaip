"""Hardened keyword screen."""

import base64

from smaip.gateway.gateway import Gateway
from smaip.probes.keyword import KeywordHook, normalize


def test_default_list_is_unchanged():
    assert KeywordHook.PATTERNS == (
        "ignore previous instructions",
        "attacker@evil.example",
        "audit.log",
        "exfiltrate",
    )


def test_case_whitespace_and_zero_width_still_match():
    hook = KeywordHook()
    assert hook.flagged("Ignore  Previous\nInstructions")
    assert hook.flagged("ignore\u200b previous\u200b instructions")
    assert hook.flagged("ig\u200dnore previous instructions")


def test_homoglyphs_and_percent_encoding_match():
    hook = KeywordHook()
    phrase = "ignore previous instructions"
    mapped = phrase.translate(str.maketrans({"i": "\u0456", "o": "\u043e", "e": "\u0435", "a": "\u0430", "p": "\u0440", "c": "\u0441"}))
    assert mapped != phrase
    assert normalize(mapped) == phrase
    assert hook.flagged(mapped)
    assert hook.flagged("ignore%20previous%20instructions")
    assert hook.flagged("igno\u0308re previous instructions")


def test_one_base64_layer_matches_and_a_second_layer_does_not():
    hook = KeywordHook()
    phrase = "ignore previous instructions"
    single = base64.b64encode(phrase.encode()).decode()
    double = base64.b64encode(single.encode()).decode()
    assert phrase not in single
    assert hook.flagged(single)
    assert hook.hits(single) == ["ignore previous instructions"]
    assert hook.flagged(double) is False


def test_near_miss_words_are_not_hits():
    hook = KeywordHook()
    assert hook.flagged("Please ignore the previous quarter when you compare this figure.") is False
    assert hook.flagged("The audit log is a paper notebook.") is False
    assert hook.flagged("Staff training covers data exfiltration risks.") is False
    assert hook.flagged("New hires are told not to exfiltrate customer tables.") is True


def test_pattern_list_is_configurable_and_the_constructor_ignores_the_env(monkeypatch):
    monkeypatch.setenv("SMAIP_KEYWORD_PATTERNS", "zebra-token")
    custom = KeywordHook(("zebra-token",))
    assert custom.flagged("see ZEBRA-TOKEN now")
    assert custom.flagged("attacker@evil.example") is False
    direct = KeywordHook()
    assert direct.flagged("attacker@evil.example") is True
    assert direct.flagged("zebra-token") is False
    gateway = Gateway()
    assert gateway.keyword.flagged("zebra-token") is True
    assert gateway.keyword.flagged("attacker@evil.example") is False
    pinned = Gateway(keyword=KeywordHook())
    assert pinned.keyword.flagged("attacker@evil.example") is True
