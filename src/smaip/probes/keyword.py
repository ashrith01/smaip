"""Keyword screen for obvious indirect-prompt-injection markers.

The default list is the Week 1 set. Matching is not a raw substring search:
text is normalized, confusable characters are folded, and a single base64
layer is decoded before the list is applied. A second base64 layer, and
base64 halves that would have to be joined, stay misses. That gap is
measured. It is not papered over.

The list is configurable. Pass ``patterns`` or set ``SMAIP_KEYWORD_PATTERNS``
to a comma-separated replacement. ``Gateway`` reads the environment variable.
``KeywordHook()`` with no arguments keeps the built-in list, so a test that
constructs the hook directly is not affected by the variable.
"""

import base64
import os
import re
import unicodedata
from collections.abc import Sequence

# Characters that are removed before matching so they cannot split a phrase.
_STRIP = dict.fromkeys(
    (
        0x00AD,  # soft hyphen
        0x200B,  # zero-width space
        0x200C,  # zero-width non-joiner
        0x200D,  # zero-width joiner
        0x2060,  # word joiner
        0xFEFF,  # BOM
        0x202A,  # LRE
        0x202B,  # RLE
        0x202C,  # PDF
        0x202D,  # LRO
        0x202E,  # RLO
        0x2066,  # LRI
        0x2067,  # RLI
        0x2068,  # FSI
        0x2069,  # PDI
    ),
    None,
)

# Lowercase confusables folded after casefold. Latin letters are not in this map.
_HOMOGLYPHS = str.maketrans(
    {
        "а": "a",  # cyrillic a
        "е": "e",  # cyrillic ie
        "о": "o",  # cyrillic o
        "р": "p",  # cyrillic er
        "с": "c",  # cyrillic es
        "х": "x",  # cyrillic ha
        "у": "y",  # cyrillic u
        "і": "i",  # cyrillic i
        "ѕ": "s",  # cyrillic dze
        "һ": "h",  # cyrillic shha
        "ј": "j",  # cyrillic je
        "α": "a",  # greek alpha
        "ε": "e",  # greek epsilon
        "ι": "i",  # greek iota
        "ο": "o",  # greek omicron
        "ν": "v",  # greek nu
        "κ": "k",  # greek kappa
        "ɡ": "g",  # latin script g
    }
)

_B64_TOKEN = re.compile(r"(?<![A-Za-z0-9+/])([A-Za-z0-9+/]{12,}={0,2})(?![A-Za-z0-9+/=])")
_ENV = "SMAIP_KEYWORD_PATTERNS"


def normalize(text: str) -> str:
    """Fold case, compatibility forms, marks, and confusable letters."""

    if not isinstance(text, str) or not text:
        return ""
    value = unicodedata.normalize("NFKC", text).translate(_STRIP)
    value = "".join(
        char
        for char in unicodedata.normalize("NFKD", value)
        if unicodedata.category(char) != "Mn"
    )
    value = value.casefold().translate(_HOMOGLYPHS)
    return re.sub(r"\s+", " ", value).strip()


def decode_base64_blobs(text: str) -> list[str]:
    """Decode one layer of standard-base64 tokens that look like text.

    The decoded strings are not scanned for a further base64 layer.
    """

    if not isinstance(text, str) or not text:
        return []
    found: list[str] = []
    seen: set[str] = set()
    for match in _B64_TOKEN.finditer(text):
        token = match.group(1)
        pad = (-len(token)) % 4
        if pad == 3:
            continue
        padded = token + ("=" * pad)
        try:
            raw = base64.b64decode(padded, validate=True)
        except ValueError:
            continue
        decoded = _acceptable_text(raw)
        if decoded is None or decoded in seen:
            continue
        seen.add(decoded)
        found.append(decoded)
    return found


def _acceptable_text(raw: bytes) -> str | None:
    if not raw or b"\x00" in raw:
        return None
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        return None
    if len(text) < 4:
        return None
    if any(ord(char) < 32 and char not in "\t\n\r" for char in text):
        return None
    letters = sum(char.isalpha() or char.isspace() or char in "@._-" for char in text)
    if letters / len(text) < 0.85:
        return None
    return text


def screen_forms(text: str) -> list[str]:
    """Normalized forms the list is checked against. One decode deep."""

    if not isinstance(text, str) or not text:
        return []
    sources = [text]
    percent = _percent_decode(text)
    if percent != text:
        sources.append(percent)
    forms: list[str] = []
    seen: set[str] = set()
    for source in sources:
        _add(forms, seen, normalize(source))
        for blob in decode_base64_blobs(source):
            _add(forms, seen, normalize(blob))
    return forms


def _percent_decode(text: str) -> str:
    if "%" not in text:
        return text
    from urllib.parse import unquote

    return unquote(text)


def _add(forms: list[str], seen: set[str], form: str) -> None:
    if form and form not in seen:
        seen.add(form)
        forms.append(form)


class KeywordHook:
    PATTERNS: tuple[str, ...] = (
        "ignore previous instructions",
        "attacker@evil.example",
        "audit.log",
        "exfiltrate",
    )

    def __init__(self, patterns: Sequence[str] | None = None) -> None:
        chosen = self.PATTERNS if patterns is None else tuple(patterns)
        self.patterns = tuple(pattern for pattern in chosen if isinstance(pattern, str) and pattern.strip())
        self._needles = tuple((pattern, normalize(pattern)) for pattern in self.patterns)

    @classmethod
    def from_env(cls) -> "KeywordHook":
        """Use ``SMAIP_KEYWORD_PATTERNS`` when it is set, else the built-in list."""

        raw = os.environ.get(_ENV, "")
        if not raw.strip():
            return cls()
        patterns = tuple(part.strip() for part in raw.split(",") if part.strip())
        if not patterns:
            return cls()
        return cls(patterns)

    def hits(self, text: str) -> list[str]:
        if not isinstance(text, str) or not text:
            return []
        forms = screen_forms(text)
        if not forms:
            return []
        return [label for label, needle in self._needles if needle and any(needle in form for form in forms)]

    def flagged(self, text: str) -> bool:
        return bool(self.hits(text))
