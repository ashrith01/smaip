"""Structured agent messages.

Page text is data. It can become a result with untrusted provenance and a
taint label. It cannot become a trusted task, and it has no field that grants
approval or clears taint.
"""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Provenance(BaseModel):
    model_config = ConfigDict(extra="forbid")

    origin: Literal["user", "page", "tool", "system"]
    trust: Literal["trusted", "untrusted"]
    agent: str
    uri: str | None = None


class Taint(BaseModel):
    """Data-flow label. Control flow does not read this object for new steps."""

    model_config = ConfigDict(extra="forbid")

    tainted: bool = False
    labels: list[str] = Field(default_factory=list)
    sources: list[str] = Field(default_factory=list)


class Task(BaseModel):
    """Trusted work item. Only the orchestrator mints these from the user task."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    kind: Literal["task"] = "task"
    id: str
    instruction: str
    provenance: Provenance
    sender: str = Field(default="user", alias="from")
    to: str = "orchestrator"
    task_id: str = ""
    content: str | None = None
    taint: Taint = Field(default_factory=Taint)
    probe_score: float | None = None

    @model_validator(mode="after")
    def _fill(self) -> "Task":
        if not self.task_id:
            self.task_id = self.id
        if self.content is None:
            self.content = self.instruction
        return self


class Result(BaseModel):
    """Outcome of a step. Page reads are always untrusted tainted results."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    kind: Literal["result"] = "result"
    task_id: str
    ok: bool
    output: str
    provenance: Provenance
    quarantined: bool = False
    sender: str = Field(default="orchestrator", alias="from")
    to: str = "orchestrator"
    content: str | None = None
    taint: Taint = Field(default_factory=Taint)
    probe_score: float | None = None
    tool: str | None = None

    @model_validator(mode="after")
    def _fill(self) -> "Result":
        if self.content is None:
            self.content = self.output
        return self


def dump_message(model: BaseModel) -> dict[str, Any]:
    """JSON-ready message. ``from`` is the sender; page payloads cannot set it."""

    return model.model_dump(mode="json", by_alias=True)


def coerce_page_message(payload: dict[str, Any], *, uri: str | None = None) -> Result:
    """Turn arbitrary page JSON into an untrusted tainted result.

    Trust, kind, sender, recipient, taint, probe score, and any approval-shaped
    keys in the payload are ignored. The text is kept only as data.
    """

    output = payload.get("output", payload.get("text", payload.get("instruction", payload.get("content", ""))))
    text = str(output)
    sources = [uri] if uri else []
    return Result(
        task_id="page",
        ok=True,
        output=text,
        content=text,
        quarantined=True,
        sender="reader",
        to="orchestrator",
        taint=Taint(tainted=True, labels=["page"], sources=sources),
        probe_score=None,
        tool=None,
        provenance=Provenance(
            origin="page",
            trust="untrusted",
            agent="reader",
            uri=uri,
        ),
    )


class Approval(BaseModel):
    """Capability minted by the gateway. Page text is not a constructor for this."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    token: str = Field(min_length=8)
    action: str
    subject: str
