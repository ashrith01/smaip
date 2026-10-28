"""Structured agent messages.

Page text is data. It can become a result with untrusted provenance.
It cannot become a trusted task, and it has no field that grants approval.
"""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class Provenance(BaseModel):
    model_config = ConfigDict(extra="forbid")

    origin: Literal["user", "page", "tool", "system"]
    trust: Literal["trusted", "untrusted"]
    agent: str
    uri: str | None = None


class Task(BaseModel):
    """Trusted work item. Only the orchestrator mints these from the user task."""

    model_config = ConfigDict(extra="forbid")

    kind: Literal["task"] = "task"
    id: str
    instruction: str
    provenance: Provenance


class Result(BaseModel):
    """Outcome of a step. Page reads are always untrusted results, never tasks."""

    model_config = ConfigDict(extra="forbid")

    kind: Literal["result"] = "result"
    task_id: str
    ok: bool
    output: str
    provenance: Provenance
    quarantined: bool = False


def coerce_page_message(payload: dict[str, Any], *, uri: str | None = None) -> Result:
    """Turn arbitrary page JSON into an untrusted result.

    Trust, kind, and any approval-shaped keys in the payload are ignored.
    """

    output = payload.get("output", payload.get("text", payload.get("instruction", "")))
    return Result(
        task_id="page",
        ok=True,
        output=str(output),
        quarantined=True,
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
