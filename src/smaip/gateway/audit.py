"""In-memory audit trail.

This object is not the workspace file named audit.log. The delete tool can
address that file. It cannot reach this list.
"""

from dataclasses import asdict, dataclass
from time import time


@dataclass
class AuditEntry:
    ts: float
    role: str
    tool: str
    arguments: dict
    allowed: bool
    reason: str
    quarantined: bool
    had_approval: bool

    def as_dict(self) -> dict:
        return asdict(self)


class AuditLog:
    def __init__(self) -> None:
        self.entries: list[AuditEntry] = []

    def record(
        self,
        *,
        role: str,
        tool: str,
        arguments: dict,
        allowed: bool,
        reason: str,
        quarantined: bool,
        had_approval: bool,
    ) -> None:
        self.entries.append(
            AuditEntry(
                ts=time(),
                role=role,
                tool=tool,
                arguments=dict(arguments),
                allowed=allowed,
                reason=reason,
                quarantined=quarantined,
                had_approval=had_approval,
            )
        )
