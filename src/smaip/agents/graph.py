"""LangGraph control path.

The orchestrator has no tools. It routes a plan that was built from the user
task. Reader, analyst, and actor are the only nodes that call the gateway.
Page results stay untrusted and are not parsed for new steps.
"""

from contextvars import ContextVar
from dataclasses import dataclass
from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from smaip.agents.planner import plan_user_task
from smaip.gateway.enforcement import Enforcement, full_stack
from smaip.gateway.gateway import Gateway
from smaip.messages import Approval, Provenance, Result, Task

_RUNTIME: ContextVar["Runtime"] = ContextVar("smaip_runtime")


class SmaipState(TypedDict, total=False):
    instruction: str
    plan: list[dict]
    step: int
    messages: list[dict]
    status: str


@dataclass
class RunResult:
    state: dict
    gateway: Gateway


class Runtime:
    def __init__(self, enforcement: Enforcement | None = None) -> None:
        self.enforcement = enforcement or full_stack()
        self.gateway = Gateway()
        self._approvals: dict[int, Approval] = {}

    def prepare(self, instruction: str) -> SmaipState:
        steps = plan_user_task(instruction)
        plan: list[dict] = []
        self._approvals = {}
        for index, step in enumerate(steps):
            plan.append(step.as_dict())
            if step.approval_subject is not None:
                self._approvals[index] = self.gateway.issue_approval(
                    step.tool, step.approval_subject
                )
        user = Task(
            id="user",
            instruction=instruction,
            provenance=Provenance(origin="user", trust="trusted", agent="orchestrator"),
        )
        return {
            "instruction": instruction,
            "plan": plan,
            "step": 0,
            "messages": [user.model_dump(mode="json")],
            "status": "running",
        }

    def approval_for(self, index: int) -> Approval | None:
        return self._approvals.get(index)

    def orchestrator(self, state: SmaipState) -> dict:
        messages = list(state.get("messages") or [])
        step = int(state.get("step") or 0)
        plan = list(state.get("plan") or [])
        if step >= len(plan) or step > 12:
            messages.append(
                Result(
                    task_id="plan",
                    ok=True,
                    output="plan complete",
                    provenance=Provenance(
                        origin="system", trust="trusted", agent="orchestrator"
                    ),
                ).model_dump(mode="json")
            )
            return {"messages": messages, "status": "done"}
        spec = plan[step]
        messages.append(
            Task(
                id=f"step-{step}",
                instruction=str(spec["summary"]),
                provenance=Provenance(origin="user", trust="trusted", agent="orchestrator"),
            ).model_dump(mode="json")
        )
        return {"messages": messages, "status": "running"}


def _run(role: str, state: SmaipState) -> dict:
    runtime = _RUNTIME.get()
    step_i = int(state["step"])
    spec = state["plan"][step_i]
    if spec["role"] != role:
        raise RuntimeError(f"router delivered {role} for a {spec['role']} step")
    approval = runtime.approval_for(step_i) if spec.get("needs_approval") else None
    decision = runtime.gateway.execute(
        role=role,
        tool=str(spec["tool"]),
        arguments=dict(spec["arguments"]),
        enforcement=runtime.enforcement,
        approval=approval,
    )
    if spec["tool"] in {"read_page", "list_pages"}:
        origin = "page"
        trust = "untrusted"
    else:
        origin = "tool"
        trust = "trusted"
    messages = list(state.get("messages") or [])
    messages.append(
        Result(
            task_id=f"step-{step_i}",
            ok=decision.allowed,
            output=decision.output if decision.allowed else decision.reason,
            quarantined=decision.quarantined,
            provenance=Provenance(
                origin=origin,
                trust=trust,
                agent=role,
                uri=decision.uri,
            ),
        ).model_dump(mode="json")
    )
    return {"messages": messages, "step": step_i + 1}


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


def run_task(instruction: str, enforcement: Enforcement | None = None) -> RunResult:
    runtime = Runtime(enforcement=enforcement)
    token = _RUNTIME.set(runtime)
    try:
        state = get_graph().invoke(
            runtime.prepare(instruction),
            config={"recursion_limit": 25},
        )
    finally:
        _RUNTIME.reset(token)
    return RunResult(state=state, gateway=runtime.gateway)
