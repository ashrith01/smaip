"""Trusted planner.

The plan is derived only from the user instruction. Page text is not an input,
so an injected sentence cannot add a send, write, or delete step or an approval.
"""

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class Step:
    role: str
    tool: str
    arguments: dict
    summary: str
    approval_subject: str | None = None

    def as_dict(self) -> dict:
        return {
            "role": self.role,
            "tool": self.tool,
            "arguments": dict(self.arguments),
            "summary": self.summary,
            "needs_approval": self.approval_subject is not None,
            "approval_subject": self.approval_subject,
        }


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


def plan_user_task(instruction: str) -> list[Step]:
    steps: list[Step] = []
    vendor = detect_vendor(instruction)
    if vendor:
        if re.search(r"\blist\b", instruction, re.IGNORECASE) and not re.search(
            r"\bread\b", instruction, re.IGNORECASE
        ):
            steps.append(
                Step("reader", "list_pages", {"vendor": vendor}, f"List {vendor} pages")
            )
        else:
            steps.append(
                Step(
                    "reader",
                    "read_page",
                    {"vendor": vendor, "page": "overview.md"},
                    f"Read {vendor} overview",
                )
            )
    arithmetic = re.search(r"\bcalculate\s+([0-9.+\-*/() ]+)", instruction, re.IGNORECASE)
    if arithmetic:
        expression = arithmetic.group(1).strip()
        steps.append(
            Step("analyst", "calculate", {"expression": expression}, f"Calculate {expression}")
        )
    email = re.search(r"\bemail\s+(\S+)", instruction, re.IGNORECASE)
    if email:
        recipient = email.group(1).rstrip(".,;")
        steps.append(
            Step(
                "actor",
                "send",
                {
                    "to": recipient,
                    "subject": "status",
                    "body": "Weekly status is on track.",
                },
                f"Email {recipient}",
                approval_subject=recipient,
            )
        )
    write = re.search(r"\bwrite\s+([A-Za-z0-9._-]+)", instruction, re.IGNORECASE)
    if write:
        path = write.group(1)
        steps.append(
            Step(
                "actor",
                "write",
                {"path": path, "content": "note"},
                f"Write {path}",
                approval_subject=path,
            )
        )
    delete = re.search(r"\bdelete\s+([A-Za-z0-9._-]+)", instruction, re.IGNORECASE)
    if delete:
        path = delete.group(1)
        steps.append(
            Step(
                "actor",
                "delete",
                {"path": path},
                f"Delete {path}",
                approval_subject=path,
            )
        )
    return steps
