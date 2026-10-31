"""Tool gateway: allowlists, schemas, audit, hooks, and the approval bit.

Mutating tools are send, write, and delete. An approval is a token minted by
trusted code. Page text and tool-argument fields cannot mint or present one.
"""

import json
import re
import secrets
from dataclasses import dataclass
from typing import Any

from smaip.errors import SandboxError, ValidationError
from smaip.fields import coerce_field_map, digest_fields
from smaip.gateway.audit import AuditLog
from smaip.gateway.enforcement import Enforcement
from smaip.gateway.sandbox import evaluate
from smaip.gateway.workspace import Workspace, safe_relative_name
from smaip.messages import Approval
from smaip.probes.keyword import KeywordHook
from smaip.probes.registry import load_activation_defense, load_linear_defense
from smaip.vendors import VendorLibrary

ROLE_TOOLS: dict[str, frozenset[str]] = {
    "orchestrator": frozenset(),
    "reader": frozenset({"list_pages", "read_page"}),
    "analyst": frozenset({"calculate", "summarize"}),
    "actor": frozenset({"send", "write", "delete"}),
}

MUTATING = frozenset({"send", "write", "delete"})
KNOWN_TOOLS = frozenset().union(*ROLE_TOOLS.values())
SMUGGLED_KEYS = frozenset({"approval", "approved", "approval_token", "approval_bit"})
EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")
VENDOR_RE = re.compile(r"^[a-z][a-z0-9_]*$")

# Integer cost units. 100 units = 1.0 reported cost.
_COST_TOOL = 100
_COST_KEYWORD = 10
_COST_LINEAR = 25
_COST_PROBE = 50
_COST_GATEWAY = 5


@dataclass
class Decision:
    allowed: bool
    reason: str
    tool: str
    role: str
    output: str
    quarantined: bool
    uri: str | None = None
    had_approval: bool = False


class Gateway:
    def __init__(
        self,
        *,
        workspace: Workspace | None = None,
        vendors: VendorLibrary | None = None,
        probe=None,
        keyword: KeywordHook | None = None,
        linear=None,
    ) -> None:
        self.workspace = workspace or Workspace()
        self.vendors = vendors or VendorLibrary()
        self.audit = AuditLog()
        self.keyword = keyword if keyword is not None else KeywordHook.from_env()
        # Trained weights replace the phrase stubs when artifacts/probes exists.
        # Week 1–6 suites pass the stubs explicitly so their gates stay published.
        self.linear = linear if linear is not None else load_linear_defense()
        self.probe = probe if probe is not None else load_activation_defense()
        self._issued: dict[str, Approval] = {}
        self.tool_calls = 0
        self.cost_units = 0
        self.decisions: list[dict] = []
        # Raw page bodies, in read order. Keyword aggregation joins decoded
        # fragments across these messages. The list is not an approval source.
        self._tainted_pages: list[str] = []

    @property
    def cost(self) -> float:
        return self.cost_units / 100

    def issue_approval(self, action: str, subject: str) -> Approval:
        if action not in MUTATING:
            raise ValidationError("approval rejected")
        if not isinstance(subject, str) or not subject or any(char.isspace() for char in subject):
            raise ValidationError("approval rejected")
        approval = Approval(token=secrets.token_urlsafe(16), action=action, subject=subject)
        self._issued[approval.token] = approval
        return approval

    def approval_from_untrusted(self, value: Any) -> Approval | None:
        """Page text, model output, and argument blobs cannot set the approval bit."""

        del value
        return None

    def execute(
        self,
        *,
        role: str,
        tool: str,
        arguments: dict[str, Any],
        enforcement: Enforcement,
        untrusted_text: str = "",
        untrusted_documents: list[str] | None = None,
        approval: Approval | None = None,
        lineage: dict | None = None,
    ) -> Decision:
        cleaned = {
            key: value
            for key, value in dict(arguments).items()
            if key not in SMUGGLED_KEYS
        }
        self._charge(enforcement)
        had_approval = isinstance(approval, Approval)
        reason: str | None = None
        output = ""
        uri: str | None = None
        quarantined = False

        if tool not in KNOWN_TOOLS:
            reason = "unknown_tool"
        elif enforcement.allowlist and tool not in ROLE_TOOLS.get(role, frozenset()):
            reason = "role_denied"
        elif enforcement.schema:
            try:
                cleaned = self._validate(tool, cleaned)
            except (ValidationError, SandboxError):
                reason = "invalid_args"

        if reason is None and tool in MUTATING and enforcement.approval:
            reason = self._approval_problem(tool, cleaned, approval)

        if (
            reason is None
            and enforcement.protect_audit_log
            and tool in {"write", "delete"}
            and str(cleaned.get("path", "")).lower() == "audit.log"
        ):
            reason = "audit_log_protected"

        if reason is None and tool in MUTATING:
            hook_text = _hook_text(untrusted_text, cleaned)
            # Trained detectors score original documents. A generated digest
            # plus recipient/subject is outside their training distribution.
            documents = untrusted_documents
            if documents is None:
                documents = [untrusted_text] if untrusted_text else list(self._tainted_pages)
            hook_reason = self._hook_reason(hook_text, enforcement, documents)
            if (
                hook_reason is None
                and untrusted_text
                and enforcement.keyword
                and self.keyword.hits_many([*self._tainted_pages, hook_text])
            ):
                hook_reason = "keyword_hook"
            if hook_reason:
                reason = hook_reason

        if reason is None:
            try:
                output, uri = self._dispatch(tool, cleaned)
            except (SandboxError, ValidationError, KeyError, TypeError) as exc:
                reason = f"execution_failed:{exc}"
                output = ""

        if reason is None and tool == "read_page":
            self._tainted_pages.append(output)
            hook_reason = self._hook_reason(output, enforcement, [output])
            if hook_reason is None and enforcement.keyword and _aggregate_closed(
                self.keyword, self._tainted_pages
            ):
                hook_reason = "keyword_hook"
            if hook_reason:
                quarantined = True
                output = "[quarantined untrusted page]\n" + output

        allowed = reason is None
        final_reason = "ok" if reason is None else reason
        self.decisions.append(
            {
                "role": role,
                "tool": tool,
                "arguments": dict(cleaned),
                "allowed": allowed,
                "reason": final_reason,
                "quarantined": quarantined,
                "had_approval": had_approval,
                "taint": _recorded_taint(tool, reason, uri, lineage),
            }
        )
        if enforcement.audit:
            self.audit.record(
                role=role,
                tool=tool,
                arguments=cleaned,
                allowed=allowed,
                reason=final_reason,
                quarantined=quarantined,
                had_approval=had_approval,
                taint=_recorded_taint(tool, reason, uri, lineage),
            )
        return Decision(
            allowed=allowed,
            reason=final_reason,
            tool=tool,
            role=role,
            output=output,
            quarantined=quarantined,
            uri=uri,
            had_approval=had_approval,
        )

    def _charge(self, enforcement: Enforcement) -> None:
        self.tool_calls += 1
        self.cost_units += _COST_TOOL
        if enforcement.keyword:
            self.cost_units += _COST_KEYWORD
        if enforcement.linear_probe:
            self.cost_units += _COST_LINEAR
        if enforcement.activation_probe:
            self.cost_units += _COST_PROBE
        if enforcement.allowlist:
            self.cost_units += _COST_GATEWAY

    def _approval_problem(
        self,
        tool: str,
        arguments: dict[str, Any],
        approval: Approval | None,
    ) -> str | None:
        if not isinstance(approval, Approval):
            return "approval_required"
        known = self._issued.get(approval.token)
        if known is None or known.action != approval.action or known.subject != approval.subject:
            return "approval_invalid"
        if known.action != tool:
            return "approval_action_mismatch"
        subject = arguments.get("to") if tool == "send" else arguments.get("path")
        if known.subject != subject:
            return "approval_subject_mismatch"
        return None

    def _hook_reason(
        self, text: str, enforcement: Enforcement, documents: list[str] | None = None,
    ) -> str | None:
        if enforcement.keyword and self.keyword.flagged(text):
            return "keyword_hook"
        docs = documents if documents is not None else ([text] if text else [])
        if enforcement.linear_probe and _defense_flags(self.linear, text, docs):
            return "linear_probe_hook"
        if enforcement.activation_probe and _defense_flags(self.probe, text, docs):
            return "activation_probe_hook"
        return None

    def _validate(self, tool: str, arguments: dict[str, Any]) -> dict[str, Any]:
        if tool == "list_pages":
            vendor = arguments.get("vendor")
            if not isinstance(vendor, str) or VENDOR_RE.fullmatch(vendor) is None:
                raise ValidationError("vendor rejected")
            return {"vendor": vendor}
        if tool == "read_page":
            vendor = arguments.get("vendor")
            page = arguments.get("page")
            if not isinstance(vendor, str) or VENDOR_RE.fullmatch(vendor) is None:
                raise ValidationError("vendor rejected")
            if not isinstance(page, str):
                raise ValidationError("page rejected")
            safe_relative_name(page)
            if not page.endswith(".md"):
                raise ValidationError("page rejected")
            return {"vendor": vendor, "page": page}
        if tool == "calculate":
            expression = arguments.get("expression")
            if not isinstance(expression, str):
                raise ValidationError("expression rejected")
            if len(expression) > 100 or any(char not in "0123456789+-*/%.() \t" for char in expression):
                raise ValidationError("expression rejected")
            return {"expression": expression}
        if tool == "summarize":
            return {"fields": coerce_field_map(arguments.get("fields"))}
        if tool == "send":
            to = arguments.get("to")
            subject = arguments.get("subject", "")
            body = arguments.get("body", "")
            if not isinstance(to, str) or EMAIL_RE.fullmatch(to) is None:
                raise ValidationError("email rejected")
            if not isinstance(subject, str) or not isinstance(body, str):
                raise ValidationError("message rejected")
            if len(subject) > 200 or len(body) > 4000:
                raise ValidationError("message rejected")
            return {"to": to, "subject": subject, "body": body}
        if tool in {"write", "delete"}:
            path = arguments.get("path")
            if not isinstance(path, str):
                raise ValidationError("path rejected")
            safe_relative_name(path)
            if tool == "delete":
                return {"path": path}
            content = arguments.get("content", "")
            if not isinstance(content, str) or len(content) > 4000:
                raise ValidationError("content rejected")
            return {"path": path, "content": content}
        raise ValidationError("tool rejected")

    def _dispatch(self, tool: str, arguments: dict[str, Any]) -> tuple[str, str | None]:
        if tool == "list_pages":
            names = self.vendors.list_pages(str(arguments["vendor"]))
            return "\n".join(names), f"vendor://{arguments['vendor']}"
        if tool == "read_page":
            text = self.vendors.read(str(arguments["vendor"]), str(arguments["page"]))
            uri = f"vendor://{arguments['vendor']}/{arguments['page']}"
            return text, uri
        if tool == "calculate":
            return str(evaluate(str(arguments["expression"]))), None
        if tool == "summarize":
            return digest_fields(arguments.get("fields")), None
        if tool == "send":
            output = self.workspace.send(
                str(arguments["to"]),
                str(arguments.get("subject", "")),
                str(arguments.get("body", "")),
            )
            return output, None
        if tool == "write":
            return self.workspace.write(str(arguments["path"]), str(arguments.get("content", ""))), None
        if tool == "delete":
            return self.workspace.delete(str(arguments["path"])), None
        raise ValidationError("tool rejected")


def _recorded_taint(
    tool: str,
    reason: str | None,
    uri: str | None,
    lineage: dict | None,
) -> dict:
    """Taint stored on the audit row for this call.

    A successful page read is tainted at the source. Later steps pass the
    lineage computed from those reads. Other calls stay clean.
    """

    if reason is None and tool == "read_page":
        return {
            "tainted": True,
            "labels": ["page"],
            "sources": [uri] if uri else [],
        }
    if reason is None and tool == "list_pages":
        return {"tainted": False, "labels": [], "sources": []}
    if isinstance(lineage, dict):
        return {
            "tainted": bool(lineage.get("tainted")),
            "labels": [item for item in lineage.get("labels") or [] if isinstance(item, str)],
            "sources": [item for item in lineage.get("sources") or [] if isinstance(item, str)],
        }
    return {"tainted": False, "labels": [], "sources": []}


def _aggregate_closed(keyword: KeywordHook, pages: list[str]) -> bool:
    """True when this page completes a hit the earlier pages did not have.

    A page that already matched stays in the ledger. A later clean page is
    not quarantined just because that earlier page is still there. A split
    payload quarantines the page that supplies the missing half.
    """

    if len(pages) < 2 or keyword.hits_many(pages[:-1]):
        return False
    return bool(keyword.hits_many(pages))


def _defense_flags(probe, hook_text: str, documents: list[str]) -> bool:
    if getattr(probe, "matches_training_documents", False):
        return any(probe.flagged(document) for document in documents if document)
    return bool(hook_text) and bool(probe.flagged(hook_text))


def _hook_text(untrusted_text: str, arguments: dict[str, Any]) -> str:
    """Page text plus argument values, without JSON quotes.

    Values are screened as prose. A quoted citation inside a value can be
    skipped by the instruction filter. The same words in a bare argument
    still match. Wrapping every value in JSON quotes would hide those words
    from that filter.
    """

    parts = [untrusted_text] if untrusted_text else []
    for key in sorted(arguments):
        value = arguments[key]
        if isinstance(value, str):
            if value:
                parts.append(value)
        else:
            parts.append(json.dumps(value, sort_keys=True, default=str))
    return "\n".join(parts)
