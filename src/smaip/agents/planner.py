"""Trusted planner.

The plan is derived only from the user instruction and explicit structured
fields. Page text is not an input, so an injected sentence cannot add a send,
write, or delete step or an approval.

Replanning has one trusted trigger: after a research task lists the vendor
catalog, filename-shaped entries become read steps. The trigger does not read
page prose.

A research write stores the field digest, not a page. A sentence that names a
role and a tool outside that role's allowlist is a refusal, not a step.
"""

import json
import re
from dataclasses import asdict, dataclass

from smaip.fields import MAX_CATALOG_READS, PAGE_NAME_RE

_EMAIL = r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"
_EMAIL_RE = re.compile(_EMAIL)
_VENDOR_RE = re.compile(r"^[a-z][a-z0-9_]*$")
_EXPR_RE = re.compile(r"[0-9+\-*/%.() \t]+")
_INTENTS = frozenset({"none", "read", "list", "research"})
_PAGES: tuple[tuple[str, str], ...] = (
    ("overview", "overview.md"),
    ("runbook", "runbook.md"),
    ("metrics", "metrics.md"),
    ("quarterly", "quarterly.md"),
)


@dataclass(frozen=True)
class Step:
    role: str
    tool: str
    arguments: dict
    summary: str
    approval_subject: str | None = None
    step_id: str = ""
    body_from_summary: bool = False
    content_from_summary: bool = False

    def as_dict(self) -> dict:
        return {
            "id": self.step_id,
            "role": self.role,
            "tool": self.tool,
            "arguments": dict(self.arguments),
            "summary": self.summary,
            "needs_approval": self.approval_subject is not None,
            "approval_subject": self.approval_subject,
            "body_from_summary": self.body_from_summary,
            "content_from_summary": self.content_from_summary,
        }


@dataclass(frozen=True)
class UserFields:
    vendor: str | None = None
    page: str | None = None
    intent: str = "none"
    expression: str | None = None
    recipient: str | None = None
    write_path: str | None = None
    delete_path: str | None = None

    def as_dict(self) -> dict:
        return asdict(self)


_VENDORS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("acme_analytics", ("acme analytics", "acme_analytics")),
    ("northwind_insights", ("northwind insights", "northwind_insights")),
    ("helix_labs", ("helix labs", "helix_labs")),
)


def detect_vendor(instruction: str) -> str | None:
    lowered = instruction.lower()
    for vendor_id, aliases in _VENDORS:
        if any(alias in lowered for alias in aliases):
            return vendor_id
    return None


def detect_page(instruction: str) -> str | None:
    lowered = instruction.lower()
    found: list[tuple[int, str]] = []
    for alias, page in _PAGES:
        match = re.search(rf"\b{alias}\b", lowered)
        if match:
            found.append((match.start(), page))
    if not found:
        return None
    found.sort()
    return found[0][1]


def detect_recipient(instruction: str) -> str | None:
    addressed = re.search(rf"\bto\s+({_EMAIL})", instruction, re.IGNORECASE)
    if addressed:
        return addressed.group(1).rstrip(".,;")
    emailed = re.search(rf"\bemail\s+({_EMAIL})", instruction, re.IGNORECASE)
    if emailed:
        return emailed.group(1).rstrip(".,;")
    return None


def parse_user_fields(instruction: str) -> UserFields:
    vendor = detect_vendor(instruction)
    if re.search(r"\bresearch\b", instruction, re.IGNORECASE):
        intent = "research"
    elif (
        vendor
        and re.search(r"\blist\b", instruction, re.IGNORECASE)
        and not re.search(r"\bread\b", instruction, re.IGNORECASE)
    ):
        intent = "list"
    elif vendor:
        intent = "read"
    else:
        intent = "none"
    page = detect_page(instruction) if intent == "read" else None
    if intent == "read" and page is None:
        page = "overview.md"
    return UserFields(
        vendor=vendor,
        page=page,
        intent=intent,
        expression=_expression(instruction),
        recipient=detect_recipient(instruction),
        write_path=_write_path(instruction),
        delete_path=_token(instruction, "delete"),
    )


def apply_field_overrides(parsed: UserFields, overrides: dict | None) -> UserFields:
    """Merge explicit structured fields. Unknown keys, including approvals, are ignored."""

    if not overrides:
        return parsed
    data = parsed.as_dict()
    for key, value in overrides.items():
        if key == "intent":
            if isinstance(value, str) and value in _INTENTS:
                data["intent"] = value
            continue
        if key == "vendor" and isinstance(value, str) and _VENDOR_RE.fullmatch(value):
            data["vendor"] = value
            continue
        if key == "page" and isinstance(value, str) and PAGE_NAME_RE.fullmatch(value):
            data["page"] = value
            continue
        if key == "expression" and isinstance(value, str) and _safe_expression(value):
            data["expression"] = value
            continue
        if key == "recipient" and isinstance(value, str) and _EMAIL_RE.fullmatch(value):
            data["recipient"] = value
            continue
        if key in {"write_path", "delete_path"} and isinstance(value, str) and _safe_name(value):
            data[key] = value
    if data["intent"] == "read" and not data["page"]:
        data["page"] = "overview.md"
    if data["intent"] != "read":
        data["page"] = None
    return UserFields(**data)


def plan_user_task(instruction: str, fields: dict | None = None) -> list[Step]:
    return plan_fields(apply_field_overrides(parse_user_fields(instruction), fields))


def plan_fields(fields: UserFields) -> list[Step]:
    if fields.intent == "research" and fields.vendor:
        return _research_plan(fields)
    return _legacy_plan(fields)


def expand_catalog(
    plan: list[dict],
    step: int,
    messages: list[dict],
    fields: dict,
    replans: int,
) -> tuple[list[dict], int]:
    """Insert read steps after a trusted catalog. Never inserts a mutating step."""

    if replans >= 1 or fields.get("intent") != "research":
        return plan, replans
    vendor = fields.get("vendor")
    if not isinstance(vendor, str) or _VENDOR_RE.fullmatch(vendor) is None:
        return plan, replans
    if step <= 0 or step > len(plan):
        return plan, replans
    previous = plan[step - 1]
    if previous.get("tool") != "list_pages":
        return plan, replans
    if (previous.get("arguments") or {}).get("vendor") != vendor:
        return plan, replans
    if any(item.get("tool") == "read_page" for item in plan):
        return plan, replans
    pages = trusted_catalog_pages(messages)
    if not pages:
        return plan, replans
    reads = [
        {
            "id": f"read-{index}",
            "role": "reader",
            "tool": "read_page",
            "arguments": {"vendor": vendor, "page": page},
            "summary": f"Read {vendor} {page}",
            "needs_approval": False,
            "approval_subject": None,
            "body_from_summary": False,
            "content_from_summary": False,
        }
        for index, page in enumerate(pages)
    ]
    return plan[:step] + reads + plan[step:], replans + 1


def trusted_catalog_pages(messages: list[dict]) -> list[str] | None:
    """Filenames from a trusted list_pages result. Tainted or page-origin data returns None."""

    result = _last_result(messages)
    if result is None:
        return None
    provenance = result.get("provenance") or {}
    taint = result.get("taint") or {}
    if result.get("tool") != "list_pages" or result.get("ok") is not True:
        return None
    if result.get("from") != "reader":
        return None
    if provenance.get("origin") != "tool" or provenance.get("trust") != "trusted":
        return None
    if provenance.get("agent") != "reader":
        return None
    if taint.get("tainted") is True or "page" in (taint.get("labels") or []):
        return None
    output_pages: list[str] = []
    for line in str(result.get("output", "")).splitlines():
        name = line.strip()
        if not name:
            continue
        if PAGE_NAME_RE.fullmatch(name) is None:
            return None
        output_pages.append(name)
    if not output_pages or len(output_pages) > MAX_CATALOG_READS:
        return None
    raw = result.get("content")
    if not isinstance(raw, str):
        return None
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict) or payload.get("pages") != output_pages:
        return None
    return output_pages


def _research_plan(fields: UserFields) -> list[Step]:
    vendor = fields.vendor
    assert vendor is not None
    steps = [
        Step(
            "reader",
            "list_pages",
            {"vendor": vendor},
            f"List {vendor} pages",
            step_id="list",
        ),
        Step(
            "analyst",
            "summarize",
            {"vendor": vendor},
            f"Summarize {vendor} fields",
            step_id="summarize",
        ),
    ]
    if fields.expression:
        steps.append(
            Step(
                "analyst",
                "calculate",
                {"expression": fields.expression},
                f"Calculate {fields.expression}",
                step_id="calc",
            )
        )
    if fields.recipient:
        steps.append(
            Step(
                "actor",
                "send",
                {
                    "to": fields.recipient,
                    "subject": "field summary",
                    "body": "__from_summary__",
                },
                f"Email {fields.recipient}",
                approval_subject=fields.recipient,
                step_id="email",
                body_from_summary=True,
            )
        )
    if fields.write_path:
        steps.append(
            Step(
                "actor",
                "write",
                {"path": fields.write_path, "content": "__from_summary__"},
                f"Write {fields.write_path}",
                approval_subject=fields.write_path,
                step_id="write",
                content_from_summary=True,
            )
        )
    if fields.delete_path:
        steps.append(
            Step(
                "actor",
                "delete",
                {"path": fields.delete_path},
                f"Delete {fields.delete_path}",
                approval_subject=fields.delete_path,
                step_id="delete",
            )
        )
    return steps


def _legacy_plan(fields: UserFields) -> list[Step]:
    steps: list[Step] = []
    if fields.vendor and fields.intent == "list":
        steps.append(
            Step(
                "reader",
                "list_pages",
                {"vendor": fields.vendor},
                f"List {fields.vendor} pages",
                step_id="list",
            )
        )
    elif fields.vendor and fields.intent == "read":
        page = fields.page or "overview.md"
        steps.append(
            Step(
                "reader",
                "read_page",
                {"vendor": fields.vendor, "page": page},
                f"Read {fields.vendor} {page}",
                step_id="read",
            )
        )
    if fields.expression:
        steps.append(
            Step(
                "analyst",
                "calculate",
                {"expression": fields.expression},
                f"Calculate {fields.expression}",
                step_id="calc",
            )
        )
    if fields.recipient:
        steps.append(
            Step(
                "actor",
                "send",
                {
                    "to": fields.recipient,
                    "subject": "status",
                    "body": "Weekly status is on track.",
                },
                f"Email {fields.recipient}",
                approval_subject=fields.recipient,
                step_id="email",
            )
        )
    if fields.write_path:
        steps.append(
            Step(
                "actor",
                "write",
                {"path": fields.write_path, "content": "note"},
                f"Write {fields.write_path}",
                approval_subject=fields.write_path,
                step_id="write",
            )
        )
    if fields.delete_path:
        steps.append(
            Step(
                "actor",
                "delete",
                {"path": fields.delete_path},
                f"Delete {fields.delete_path}",
                approval_subject=fields.delete_path,
                step_id="delete",
            )
        )
    return steps


# Role word plus a tool that role cannot call. The tool name is the refusal
# token. These pairs match the gateway allowlist; they are not extra tools.
_SCOPE_RULES: tuple[tuple[str, str, str], ...] = (
    ("reader", "send", r"\b(send|email|mail)\b"),
    ("reader", "write", r"\bwrite\b"),
    ("reader", "delete", r"\bdelete\b"),
    ("reader", "calculate", r"\bcalculate\b"),
    ("reader", "summarize", r"\bsummarize\b"),
    ("analyst", "send", r"\b(send|email|mail)\b"),
    ("analyst", "write", r"\bwrite\b"),
    ("analyst", "delete", r"\bdelete\b"),
    ("analyst", "read_page", r"\bread\b"),
    ("analyst", "list_pages", r"\blist\b"),
    ("actor", "read_page", r"\bread\b"),
    ("actor", "list_pages", r"\blist\b"),
    ("actor", "calculate", r"\bcalculate\b"),
    ("actor", "summarize", r"\bsummarize\b"),
)


def scope_refusals(instruction: str) -> list[str]:
    """Tools the user asked a role to run that the allowlist does not grant.

    The returned tokens look like ``reader:send``. They are not plan steps.
    A normal research email does not name a role, so it is not a refusal.
    """

    found: list[str] = []
    for role, tool, pattern in _SCOPE_RULES:
        if re.search(rf"\b{role}\b", instruction, re.IGNORECASE) is None:
            continue
        if re.search(pattern, instruction, re.IGNORECASE) is None:
            continue
        token = f"{role}:{tool}"
        if token not in found:
            found.append(token)
    return found


def _write_path(instruction: str) -> str | None:
    named = re.search(
        r"\bwrite\s+the\s+field\s+summary\s+to\s+([A-Za-z0-9._-]+)",
        instruction,
        re.IGNORECASE,
    )
    if named:
        token = named.group(1).rstrip(".,;")
        if _safe_name(token):
            return token
    return _token(instruction, "write")


def _expression(instruction: str) -> str | None:
    match = re.search(r"\bcalculate\s+([0-9.+\-*/() ]+)", instruction, re.IGNORECASE)
    if not match:
        return None
    text = match.group(1).strip().rstrip(".")
    if not text or not _safe_expression(text):
        return None
    return text


def _token(instruction: str, verb: str) -> str | None:
    match = re.search(rf"\b{verb}\s+([A-Za-z0-9._-]+)", instruction, re.IGNORECASE)
    if not match:
        return None
    token = match.group(1)
    if not _safe_name(token):
        return None
    return token


def _safe_expression(value: str) -> bool:
    return len(value) <= 100 and _EXPR_RE.fullmatch(value) is not None


def _safe_name(value: str) -> bool:
    if value != value.strip() or "/" in value or "\\" in value or value in {".", ".."}:
        return False
    if value.startswith(".") or len(value) > 128:
        return False
    return value.replace(".", "").replace("_", "").replace("-", "").isalnum()


def _last_result(messages: list[dict]) -> dict | None:
    for message in reversed(messages):
        if message.get("kind") == "result":
            return message
    return None
