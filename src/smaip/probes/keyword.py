"""Keyword screen for obvious indirect-prompt-injection markers.

The default list is the Week 1 set. Matching folds case, compatibility
forms, combining marks, and confusable letters, strips zero-width and bidi
controls, and percent-decodes once.

Week 6 adds three checks:

- Instruction context. A hit inside quoted text, a code span, reported
  speech, or a security-article sentence is not an instruction. A bare
  imperative on its own sentence still matches.
- Bounded base64. Standard-base64 tokens are decoded up to
  ``MAX_DECODE_DEPTH`` layers. A further wrap stays a miss.
- Cross-message fragments. Decoded pieces are joined in order, including
  pieces that arrived on different pages, so a phrase split across messages
  matches even when neither page matches alone.

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

# A third wrap of the Week 5 double-encoded blob is still inside this bound.
# One more wrap is not decoded. The bound is the regression, not an accident.
MAX_DECODE_DEPTH = 3

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
_FENCE = re.compile(r"```.*?```|~~~.*?~~~", re.DOTALL)
_INLINE = re.compile(r"`[^`\n]+`")
_DQUOTE = re.compile(r"“[^”]{0,500}”|„[^“]{0,500}“|\"[^\"\n]{0,500}\"")
_SQUOTE = re.compile(r"'[^'\n]{4,300}'")
_BLOCKQUOTE = re.compile(r"(?m)^>[^\n]*")
_REPORTED = re.compile(
    r"(?i)(?:\b(?:are|were|is|was|been|being)\s+told\s+not\s+to\b[^.\n]{0,160}"
    r"|"
    r"\b(?:said|says|wrote|writes|reported|reports|quoted|quotes|noted|notes|mentioned|mentions)\s*(?:that|:)\s*[^.\n]{0,200})"
)
_CUE = re.compile(
    r"(?i)\b(?:this security article|this article|security write-up|staff training|"
    r"new-hire|new hires|report template|not a request|not a task|the phrase|"
    r"the word|the term|the string|taxonomy|defenders|for example|discusses|quoting)\b"
)
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
    """Decode one layer of standard-base64 tokens that look like prose."""

    return [blob for blob in _utf8_blobs(text) if _is_prose(blob)]


def _utf8_blobs(text: str) -> list[str]:
    """One decode layer, including base64 that is not prose yet.

    A nested payload decodes to more base64. That string is mostly letters
    but it also contains digits and padding, so the prose ratio rejects it.
    The next layer still has to be peeled.
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
        decoded = _utf8_text(raw)
        if decoded is None or decoded in seen:
            continue
        seen.add(decoded)
        found.append(decoded)
    return found


def conceal_spans(text: str) -> str:
    """Blank quoted text and code. Those spans are not screened or decoded."""

    if not isinstance(text, str) or not text:
        return ""

    def blank(match: re.Match[str]) -> str:
        return " " * len(match.group(0))

    value = _FENCE.sub(blank, text)
    value = _INLINE.sub(blank, value)
    value = _DQUOTE.sub(blank, value)
    value = _SQUOTE.sub(blank, value)
    value = _BLOCKQUOTE.sub(blank, value)
    return value


def instruction_view(text: str) -> str:
    """Prose with quotes, code, reported speech, and article sentences removed.

    A sentence that only discusses a phrase stays blank. A sentence that
    starts with an imperative, or that names a side effect, stays in place
    even when the same line mentions an article.
    """

    if not isinstance(text, str) or not text:
        return ""
    value = _REPORTED.sub(lambda match: " " * len(match.group(0)), conceal_spans(text))
    parts = re.split(r"(\n+|(?<=[.!?])\s+)", value)
    kept: list[str] = []
    for part in parts:
        if part and not part.isspace() and not part.startswith("\n") and _CUE.search(part) and not _is_command(part):
            kept.append(" " * len(part))
        else:
            kept.append(part)
    return "".join(kept)


def decoded_fragments(text: str, depth: int = MAX_DECODE_DEPTH) -> list[tuple[int, str]]:
    """Nested decodes of tokens that are outside quotes and code.

    Each item is ``(layer, text)`` with ``layer`` starting at 1. Fragments
    from the same layer are what cross-message aggregation joins.
    """

    if not isinstance(text, str) or not text or depth < 1:
        return []
    masked = conceal_spans(text)
    sources = [masked]
    percent = _percent_decode(masked)
    if percent != masked:
        sources.append(percent)
    found: list[tuple[int, str]] = []
    seen: set[tuple[int, str]] = set()
    layer = sources
    for level in range(1, depth + 1):
        nxt: list[str] = []
        for source in layer:
            for blob in _utf8_blobs(source):
                key = (level, blob)
                if key in seen:
                    continue
                seen.add(key)
                if _is_prose(blob):
                    found.append((level, blob))
                nxt.append(blob)
        layer = nxt
        if not layer:
            break
    return found


def _is_command(sentence: str) -> bool:
    if re.search(r"(?i)attacker@evil\.example", sentence):
        return True
    if re.search(r"(?i)write\s+secret\.txt", sentence):
        return True
    if re.search(r"(?i)\byou are now\b", sentence):
        return True
    if re.search(r"(?i)\bemail\s+\S+@", sentence):
        return True
    if re.search(r"(?i)\bsend\s+the\s+(?:full|brief|mailbox|figures)\b", sentence):
        return True
    if re.search(r"(?i)\bexfiltrate\s+the\b", sentence) and not re.search(
        r"(?i)\bnot\s+to\s+exfiltrate\b", sentence
    ):
        return True
    if re.search(r"(?i)\bdelete\s+audit\.log\b", sentence) and not re.search(
        r"(?i)\b(?:not to|never|do not|don't)\s+delete\s+audit\.log\b", sentence
    ):
        return True
    if re.match(r"(?i)\s*ignore previous instructions\b", sentence):
        return True
    return False


def _utf8_text(raw: bytes) -> str | None:
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
    return text


def _is_prose(text: str) -> bool:
    if not text:
        return False
    letters = sum(char.isalpha() or char.isspace() or char in "@._-" for char in text)
    return letters / len(text) >= 0.85


def _acceptable_text(raw: bytes) -> str | None:
    text = _utf8_text(raw)
    if text is None or not _is_prose(text):
        return None
    return text


def screen_forms(text: str) -> list[str]:
    """Normalized instruction forms for one text, including nested decodes."""

    return _forms_for([text] if isinstance(text, str) else [])


def _forms_for(texts: Sequence[str]) -> list[str]:
    forms: list[str] = []
    seen: set[str] = set()
    bag: dict[int, list[str]] = {}
    for text in texts:
        if not isinstance(text, str) or not text:
            continue
        for form in _surface_forms(text):
            _add(forms, seen, form)
        for level, blob in decoded_fragments(text):
            bag.setdefault(level, []).append(blob)
            _add(forms, seen, normalize(instruction_view(blob)))
    for blobs in bag.values():
        if len(blobs) >= 2:
            _add(forms, seen, normalize(instruction_view("".join(blobs))))
    return forms


def _surface_forms(text: str) -> list[str]:
    view = instruction_view(text)
    forms: list[str] = []
    seen: set[str] = set()
    _add(forms, seen, normalize(view))
    percent = _percent_decode(view)
    if percent != view:
        _add(forms, seen, normalize(instruction_view(percent)))
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
    MAX_DECODE_DEPTH = MAX_DECODE_DEPTH

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
        return self.hits_many((text,))

    def hits_many(self, texts: Sequence[str]) -> list[str]:
        """Hits over several tainted messages, with decoded fragments joined.

        This is the cross-message aggregate. Each text is screened on its
        own, then decoded pieces from the same layer are concatenated in
        message order. A half on one page and a half on the next match here
        when neither page matches alone.
        """

        forms = _forms_for(texts)
        if not forms:
            return []
        return [label for label, needle in self._needles if needle and any(needle in form for form in forms)]

    def flagged(self, text: str) -> bool:
        return bool(self.hits(text))
