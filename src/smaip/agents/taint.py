"""Taint carried from page reads onto later tool results.

The planner does not read this object. It is a label on summarize, send, and
write results so a caller can see which pages a derived side effect came from.
"""

from dataclasses import dataclass

from smaip.messages import Taint

_SUMMARY_BODY = "__from_summary__"


@dataclass(frozen=True)
class Lineage:
    tainted: bool
    labels: tuple[str, ...]
    sources: tuple[str, ...]
    probe_score: float | None
    origin: str
    trust: str

    def as_taint(self) -> Taint:
        return Taint(
            tainted=self.tainted,
            labels=list(self.labels),
            sources=list(self.sources),
        )

    def as_audit(self) -> dict:
        return {
            "tainted": self.tainted,
            "labels": list(self.labels),
            "sources": list(self.sources),
        }


def lineage_from_reads(messages: list[dict]) -> Lineage:
    """Union of taint on successful page reads. Clean reads stay trusted."""

    sources: list[str] = []
    labels: list[str] = []
    scores: list[float] = []
    tainted = False
    for message in messages:
        if message.get("kind") != "result" or message.get("tool") != "read_page":
            continue
        if message.get("ok") is not True:
            continue
        taint = message.get("taint") or {}
        if taint.get("tainted") is True:
            tainted = True
        for source in taint.get("sources") or []:
            if isinstance(source, str) and source not in sources:
                sources.append(source)
        for label in taint.get("labels") or []:
            if isinstance(label, str) and label not in labels and label != "derived":
                labels.append(label)
        score = message.get("probe_score")
        if isinstance(score, (int, float)) and not isinstance(score, bool):
            scores.append(float(score))
    probe_score = max(scores) if scores else None
    if not tainted:
        return Lineage(False, (), (), probe_score, "tool", "trusted")
    if "derived" not in labels:
        labels.append("derived")
    return Lineage(True, tuple(labels), tuple(sources), probe_score, "page", "untrusted")


def lineage_for(spec: dict, messages: list[dict]) -> Lineage | None:
    """Lineage for a step whose body is the field digest. Other steps stay unlabeled."""

    tool = str(spec.get("tool") or "")
    arguments = spec.get("arguments") or {}
    if tool == "summarize":
        return lineage_from_reads(messages)
    if tool == "send" and (
        spec.get("body_from_summary") or arguments.get("body") == _SUMMARY_BODY
    ):
        return lineage_from_reads(messages)
    if tool == "write" and (
        spec.get("content_from_summary") or arguments.get("content") == _SUMMARY_BODY
    ):
        return lineage_from_reads(messages)
    return None
