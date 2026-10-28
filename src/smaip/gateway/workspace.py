"""Side effects the actor can reach.

Paths stay inside this object. There is no filesystem access.
"""

from dataclasses import dataclass, field

from smaip.errors import SandboxError


def safe_relative_name(path: str) -> str:
    if not isinstance(path, str):
        raise SandboxError("path rejected")
    if path != path.strip() or "/" in path or "\\" in path or path in {".", ".."}:
        raise SandboxError("path rejected")
    if not path.replace(".", "").replace("_", "").replace("-", "").isalnum():
        raise SandboxError("path rejected")
    if path.startswith(".") or len(path) > 128:
        raise SandboxError("path rejected")
    return path


@dataclass
class Workspace:
    sent: list[dict[str, str]] = field(default_factory=list)
    files: dict[str, str] = field(default_factory=lambda: {"audit.log": "audit-seed\n"})

    def write(self, path: str, content: str) -> str:
        name = safe_relative_name(path)
        self.files[name] = content
        return f"wrote:{name}"

    def delete(self, path: str) -> str:
        name = safe_relative_name(path)
        self.files.pop(name, None)
        return f"deleted:{name}"

    def send(self, to: str, subject: str, body: str) -> str:
        self.sent.append({"to": to, "subject": subject, "body": body})
        return f"sent:{to}"
