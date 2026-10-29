"""LangGraph control path.

The orchestrator has no tools. It routes a plan that was built from the user
task and explicit structured fields. Reader, analyst, and actor are the only
nodes that call the gateway. Page results stay tainted and are not parsed for
new steps. The only replan inserts read steps from a trusted filename catalog.

A role/tool pair outside the gateway allowlist is recorded as a refusal and
is not executed. Summarize, digest send, and digest write results carry the
page taint, sources, and probe score forward.
"""

from contextvars import ContextVar
from dataclasses import dataclass
from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from smaip.agents.actor import bind_arguments
from smaip.agents.analyst import present_summary
from smaip.agents.planner import (
    apply_field_overrides,
    expand_catalog,
    parse_user_fields,
    plan_fields,
    scope_refusals,
)
from smaip.agents.reader import list_pages_view, read_page_view
from smaip.agents.taint import Lineage, lineage_for
from smaip.errors import TaintRejected
from smaip.gateway.enforcement import Enforcement, full_stack
from smaip.gateway.gateway import ROLE_TOOLS, Gateway
from smaip.messages import Approval, Provenance, Result, Task, Taint, dump_message

_RUNTIME: ContextVar["Runtime"] = ContextVar("smaip_runtime")


class SmaipState(TypedDict, total=False):
    instruction: str
    fields: dict
    plan: list[dict]
    step: int
    replans: int
    messages: list[dict]
    status: str
    refusals: list[str]


@dataclass
class RunResult:
    state: dict
    gateway: Gateway


class Runtime:
    def __init__(self, enforcement: Enforcement | None = None) -> None:
        self.enforcement = enforcement or full_stack()
        self.gateway = Gateway()
        self._approvals: dict[str, Approval] = {}

    def prepare(self, instruction: str, fields: dict | None = None) -> SmaipState:
        merged = apply_field_overrides(parse_user_fields(instruction), fields)
        steps = plan_fields(merged)
        plan: list[dict] = []
        self._approvals = {}
        for step in steps:
            plan.append(step.as_dict())
            if step.approval_subject is not None:
                self._approvals[step.step_id] = self.gateway.issue_approval(
                    step.tool, step.approval_subject
                )
        user = Task(
            id="user",
            instruction=instruction,
            sender="user",
            to="orchestrator",
            task_id="user",
            content=instruction,
            taint=Taint(),
            provenance=Provenance(origin="user", trust="trusted", agent="orchestrator"),
        )
        refusals = scope_refusals(instruction)
        messages = [dump_message(user)]
        for token in refusals:
            messages.append(dump_message(_refusal_result(token, f"refuse-{token.replace(':', '-')}")))
        return {
            "instruction": instruction,
            "fields": merged.as_dict(),
            "plan": plan,
            "step": 0,
            "replans": 0,
            "messages": messages,
            "status": "running",
            "refusals": refusals,
        }

    def approval_for(self, spec: dict) -> Approval | None:
        return self._approvals.get(str(spec.get("id") or ""))

    def orchestrator(self, state: SmaipState) -> dict:
        messages = list(state.get("messages") or [])
        step = int(state.get("step") or 0)
        plan = list(state.get("plan") or [])
        replans = int(state.get("replans") or 0)
        fields = dict(state.get("fields") or {})
        plan, replans = expand_catalog(plan, step, messages, fields, replans)
        if step >= len(plan) or step > 24:
            messages.append(
                dump_message(
                    Result(
                        task_id="plan",
                        ok=True,
                        output="plan complete",
                        sender="orchestrator",
                        to="user",
                        content="plan complete",
                        provenance=Provenance(
                            origin="system", trust="trusted", agent="orchestrator"
                        ),
                    )
                )
            )
            return {
                "messages": messages,
                "status": "done",
                "plan": plan,
                "replans": replans,
            }
        spec = plan[step]
        task_id = str(spec.get("id") or f"step-{step}")
        messages.append(
            dump_message(
                Task(
                    id=task_id,
                    instruction=str(spec["summary"]),
                    sender="orchestrator",
                    to=str(spec["role"]),
                    task_id=task_id,
                    content=str(spec["summary"]),
                    taint=Taint(),
                    provenance=Provenance(
                        origin="user", trust="trusted", agent="orchestrator"
                    ),
                )
            )
        )
        return {
            "messages": messages,
            "status": "running",
            "plan": plan,
            "replans": replans,
        }


def _run(role: str, state: SmaipState) -> dict:
    runtime = _RUNTIME.get()
    step_i = int(state["step"])
    spec = state["plan"][step_i]
    if spec["role"] != role:
        raise RuntimeError(f"router delivered {role} for a {spec['role']} step")
    messages = list(state.get("messages") or [])
    fields = dict(state.get("fields") or {})
    task_id = str(spec.get("id") or f"step-{step_i}")
    tool = str(spec["tool"])
    if tool not in ROLE_TOOLS.get(role, frozenset()):
        messages.append(dump_message(_refusal_result(f"{role}:{tool}", task_id)))
        return {"messages": messages, "step": step_i + 1}
    try:
        arguments = bind_arguments(spec, messages, fields)
    except TaintRejected:
        messages.append(
            dump_message(
                Result(
                    task_id=task_id,
                    ok=False,
                    output="tainted_subject",
                    sender=role,
                    to="orchestrator",
                    content="tainted_subject",
                    tool=tool,
                    taint=Taint(tainted=True, labels=["rejected"], sources=["page"]),
                    provenance=Provenance(origin="system", trust="trusted", agent=role),
                )
            )
        )
        return {"messages": messages, "step": step_i + 1}
    lineage = lineage_for(spec, messages)
    approval = runtime.approval_for(spec) if spec.get("needs_approval") else None
    decision = runtime.gateway.execute(
        role=role,
        tool=tool,
        arguments=arguments,
        enforcement=runtime.enforcement,
        approval=approval,
        lineage=None if lineage is None else lineage.as_audit(),
    )
    messages.append(dump_message(_result_from_decision(spec, task_id, decision, lineage)))
    return {"messages": messages, "step": step_i + 1}


def _refusal_result(token: str, task_id: str) -> Result:
    text = f"refused:{token}"
    return Result(
        task_id=task_id,
        ok=False,
        output=text,
        sender="orchestrator",
        to="user",
        content=text,
        tool=None,
        taint=Taint(),
        provenance=Provenance(origin="system", trust="trusted", agent="orchestrator"),
    )


def _result_from_decision(spec: dict, task_id: str, decision, lineage: Lineage | None) -> Result:
    tool = str(spec["tool"])
    role = str(spec["role"])
    output = decision.output if decision.allowed else decision.reason
    content = output
    taint = Taint()
    origin = "tool"
    trust = "trusted"
    probe_score = None
    if decision.allowed and tool == "read_page":
        view = read_page_view(decision.output, decision.uri)
        content = view["content"]
        taint = view["taint"]
        probe_score = view["probe_score"]
        origin = view["origin"]
        trust = view["trust"]
    elif decision.allowed and tool == "list_pages":
        view = list_pages_view(decision.output)
        content = view["content"]
        taint = view["taint"]
        probe_score = view["probe_score"]
        origin = view["origin"]
        trust = view["trust"]
    elif lineage is not None and tool in {"summarize", "send", "write"}:
        if decision.allowed and tool == "summarize":
            output, content = present_summary(decision.output)
        taint = lineage.as_taint()
        probe_score = lineage.probe_score
        origin = lineage.origin
        trust = lineage.trust
    uri = decision.uri
    if uri is None and lineage is not None and lineage.sources:
        uri = lineage.sources[0]
    return Result(
        task_id=task_id,
        ok=decision.allowed,
        output=output,
        content=content,
        quarantined=decision.quarantined,
        sender=role,
        to="orchestrator",
        tool=tool,
        taint=taint,
        probe_score=probe_score,
        provenance=Provenance(
            origin=origin,
            trust=trust,
            agent=role,
            uri=uri,
        ),
    )


def orchestrator_node(state: SmaipState) -> dict:
    return _RUNTIME.get().orchestrator(state)


def reader_node(state: SmaipState) -> dict:
    return _run("reader", state)


def analyst_node(state: SmaipState) -> dict:
    return _run("analyst", state)


def actor_node(state: SmaipState) -> dict:
    return _run("actor", state)


def route(state: SmaipState) -> str:
    plan = list(state.get("plan") or [])
    step = int(state.get("step") or 0)
    if state.get("status") == "done" or step >= len(plan):
        return END
    role = str(plan[step]["role"])
    if role not in {"reader", "analyst", "actor"}:
        return END
    return role


def build_graph():
    graph = StateGraph(SmaipState)
    graph.add_node("orchestrator", orchestrator_node)
    graph.add_node("reader", reader_node)
    graph.add_node("analyst", analyst_node)
    graph.add_node("actor", actor_node)
    graph.add_edge(START, "orchestrator")
    graph.add_conditional_edges(
        "orchestrator",
        route,
        {"reader": "reader", "analyst": "analyst", "actor": "actor", END: END},
    )
    graph.add_edge("reader", "orchestrator")
    graph.add_edge("analyst", "orchestrator")
    graph.add_edge("actor", "orchestrator")
    return graph.compile()


_GRAPH = None


def get_graph():
    global _GRAPH
    if _GRAPH is None:
        _GRAPH = build_graph()
    return _GRAPH


def run_task(
    instruction: str,
    enforcement: Enforcement | None = None,
    *,
    fields: dict | None = None,
) -> RunResult:
    runtime = Runtime(enforcement=enforcement)
    token = _RUNTIME.set(runtime)
    try:
        state = get_graph().invoke(
            runtime.prepare(instruction, fields),
            config={"recursion_limit": 80},
        )
    finally:
        _RUNTIME.reset(token)
    return RunResult(state=state, gateway=runtime.gateway)
