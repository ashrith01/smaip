"""Actor specialist.

send, write, and delete run only through the gateway. The recipient and the
path are taken from trusted user fields. Tainted page text cannot replace
them, and it cannot mint an approval.
"""

from smaip.agents.analyst import collect_extracts, draft_from_messages
from smaip.errors import TaintRejected

_SMUGGLED = frozenset({"approval", "approved", "approval_token", "approval_bit"})
SUMMARY_BODY = "__from_summary__"


def bind_arguments(spec: dict, messages: list[dict], fields: dict) -> dict:
    """Build tool arguments for one planned step.

    Reader and analyst arguments pass through. Actor subjects are rewritten
    from ``fields``, which the orchestrator stored from the user instruction
    or from explicit structured input. Message content is not consulted for
    those subjects.
    """

    tool = str(spec.get("tool"))
    raw = {
        key: value
        for key, value in dict(spec.get("arguments") or {}).items()
        if key not in _SMUGGLED
    }
    if tool == "summarize":
        return {"fields": collect_extracts(messages)}
    if tool == "send":
        return _send(spec, raw, messages, fields)
    if tool == "write":
        return _write(spec, raw, messages, fields)
    if tool == "delete":
        return _delete(fields)
    return raw


def _trusted(fields: dict, key: str) -> str:
    value = fields.get(key)
    if not isinstance(value, str) or not value or any(char.isspace() for char in value):
        raise TaintRejected("tainted_subject")
    return value


def _send(spec: dict, raw: dict, messages: list[dict], fields: dict) -> dict:
    recipient = _trusted(fields, "recipient")
    subject = raw.get("subject", "status")
    if not isinstance(subject, str):
        raise TaintRejected("tainted_subject")
    if spec.get("body_from_summary") or raw.get("body") == SUMMARY_BODY:
        body = draft_from_messages(messages)
    else:
        body = raw.get("body", "")
        if not isinstance(body, str):
            raise TaintRejected("tainted_subject")
    return {"to": recipient, "subject": subject, "body": body}


def _write(spec: dict, raw: dict, messages: list[dict], fields: dict) -> dict:
    path = _trusted(fields, "write_path")
    if spec.get("content_from_summary") or raw.get("content") == SUMMARY_BODY:
        content = draft_from_messages(messages)
    else:
        content = raw.get("content", "")
        if not isinstance(content, str):
            raise TaintRejected("tainted_subject")
    return {"path": path, "content": content}


def _delete(fields: dict) -> dict:
    return {"path": _trusted(fields, "delete_path")}
