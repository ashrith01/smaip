"""OpenAI-compatible API.

POST /v1/chat/completions, POST /v1/agent/tasks, GET /health, GET /metrics.
The default engine is mock. Nothing in this module downloads weights.
Health and metrics stay open. Chat and agent-task auth, body size, and
per-key rate limits are configurable via ServingSettings.
"""

import json
import time
import uuid
from typing import Literal

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, PlainTextResponse
from pydantic import BaseModel, ConfigDict, Field

from smaip import __version__
from smaip.errors import UnknownEngine
from smaip.privacy import redact_obj, redact_pii
from smaip.serving.access import RequestAudit, configure_access_log
from smaip.serving.cache import ExactPromptCache
from smaip.serving.engines import Engine, engine_for_model
from smaip.serving.guard import InferenceGuard
from smaip.serving.metrics import Metrics
from smaip.serving.ratelimit import RateLimiter
from smaip.serving.settings import ServingSettings


class ChatMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: Literal["system", "user", "assistant", "tool"]
    content: str = Field(min_length=1, max_length=1_000_000)


class AgentTaskRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    instruction: str = Field(min_length=1, max_length=4_000)


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    model: str = Field(default="smaip-mock", min_length=1, max_length=128)
    messages: list[ChatMessage] = Field(default_factory=list)
    temperature: float | None = Field(default=None, ge=0, le=2)
    stream: bool = False
    redact_echo: bool = False


def create_app(
    *,
    engine: Engine | None = None,
    settings: ServingSettings | None = None,
) -> FastAPI:
    resolved = settings if settings is not None else ServingSettings.load()
    app = FastAPI(title="SMAIP", version=__version__)
    app.state.cache = ExactPromptCache()
    app.state.metrics = Metrics()
    app.state.settings = resolved
    app.state.limiter = RateLimiter(resolved.rate_limit_per_minute)
    app.state.request_audit = RequestAudit()
    app.state.engine_override = engine
    configure_access_log(resolved.log_level)

    @app.exception_handler(RequestValidationError)
    async def on_validation(request: Request, exc: RequestValidationError) -> JSONResponse:
        errors = json.loads(json.dumps(exc.errors(), default=str))
        app.state.metrics.record_payload_rejected()
        app.state.request_audit.record(
            {
                "ts": time.time(),
                "event": "payload.rejected",
                "request_id": getattr(request.state, "request_id", ""),
                "path": request.url.path,
                "status": 422,
                "error_type": "validation_error",
            }
        )
        return JSONResponse(status_code=422, content={"detail": redact_obj(errors)})

    @app.get("/health")
    def health() -> dict:
        return {
            "status": "ok",
            "engine_default": "mock",
            "gpu": False,
            "version": __version__,
        }

    @app.get("/metrics")
    def metrics(format: str = Query("json", alias="format")):
        if format == "prom":
            return PlainTextResponse(
                app.state.metrics.prometheus(),
                media_type="text/plain; version=0.0.4",
            )
        return app.state.metrics.snapshot()

    def reject_payload(
        request: Request,
        *,
        status: int,
        message: str,
        error_type: str,
        preview: str = "",
    ) -> None:
        app.state.metrics.record_payload_rejected()
        entry = {
            "ts": time.time(),
            "event": "payload.rejected",
            "request_id": getattr(request.state, "request_id", ""),
            "path": request.url.path,
            "status": status,
            "error_type": error_type,
        }
        if preview:
            entry["redacted_preview"] = preview[:240]
        app.state.request_audit.record(entry)
        raise HTTPException(
            status_code=status,
            detail={"message": message, "type": error_type},
        )

    @app.post("/v1/chat/completions")
    def chat(body: ChatRequest, request: Request) -> dict:
        if body.stream:
            reject_payload(
                request,
                status=400,
                message="streaming is not supported",
                error_type="unsupported",
            )
        if not body.messages:
            reject_payload(
                request,
                status=400,
                message="messages must not be empty",
                error_type="invalid_request",
            )
        if len(body.messages) > resolved.max_messages:
            reject_payload(
                request,
                status=400,
                message="too many messages",
                error_type="invalid_request",
            )
        for item in body.messages:
            if len(item.content) > resolved.max_message_chars:
                reject_payload(
                    request,
                    status=400,
                    message="message content exceeds limit",
                    error_type="invalid_request",
                    preview=item.content,
                )
        started = time.perf_counter()
        messages = [item.model_dump() for item in body.messages]
        try:
            if app.state.engine_override is not None:
                selected = app.state.engine_override
            else:
                selected = engine_for_model(body.model)
        except UnknownEngine as exc:
            raise HTTPException(
                status_code=400,
                detail={"message": str(exc), "type": "unknown_engine"},
            ) from exc
        cache: ExactPromptCache = app.state.cache
        try:
            key = cache.prompt_key(selected.name, messages)
        except ValueError as exc:
            raise HTTPException(
                status_code=400,
                detail={"message": str(exc), "type": "invalid_request"},
            ) from exc
        cached = cache.get(key)
        if cached is None:
            text = selected.complete(messages)
            cache.put(key, text)
            cache_status = "miss"
        else:
            text = cached
            cache_status = "hit"
        latency_ms = (time.perf_counter() - started) * 1000
        app.state.metrics.record(
            engine=selected.name,
            cache_status=cache_status,
            latency_ms=latency_ms,
        )
        request_id = getattr(request.state, "request_id", "")
        app.state.request_audit.record(
            {
                "ts": time.time(),
                "event": "chat.completion",
                "request_id": request_id,
                "model": body.model,
                "engine": selected.name,
                "cache": cache_status,
                "status": 200,
                "redacted_preview": redact_pii(body.messages[-1].content)[:240],
            }
        )
        prompt_tokens = max(1, sum(len(item.content) for item in body.messages) // 4)
        completion_tokens = max(1, len(text) // 4)
        smaip = {"cache": cache_status, "engine": selected.name}
        if body.redact_echo:
            smaip["redacted_echo"] = [
                {"role": item.role, "content": redact_pii(item.content)} for item in body.messages
            ]
        return {
            "id": "chatcmpl-" + uuid.uuid4().hex[:24],
            "object": "chat.completion",
            "created": int(time.time()),
            "model": body.model,
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": text},
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": prompt_tokens + completion_tokens,
            },
            "smaip": smaip,
        }

    @app.post("/v1/agent/tasks")
    def agent_task(body: AgentTaskRequest, request: Request) -> dict:
        instruction = body.instruction.strip()
        if not instruction:
            reject_payload(
                request,
                status=400,
                message="instruction must not be empty",
                error_type="invalid_request",
            )
        # Imported here so serving.app can load without a cycle through the graph.
        from smaip.agents.graph import run_task
        from smaip.gateway.enforcement import full_stack

        result = run_task(instruction, enforcement=full_stack())
        request_id = getattr(request.state, "request_id", "")
        app.state.request_audit.record(
            {
                "ts": time.time(),
                "event": "agent.task",
                "request_id": request_id,
                "status": 200,
                "engine": "mock",
                "redacted_preview": redact_pii(instruction)[:240],
            }
        )
        return _agent_payload(result, instruction)

    app.add_middleware(InferenceGuard, fastapi_app=app)
    return app


def _agent_payload(result, instruction: str) -> dict:
    messages = []
    for message in result.state.get("messages") or []:
        output = str(message.get("output", ""))
        messages.append(
            {
                "kind": message.get("kind"),
                "from": message.get("from"),
                "to": message.get("to"),
                "tool": message.get("tool"),
                "ok": message.get("ok"),
                "taint": message.get("taint"),
                "provenance": message.get("provenance"),
                "probe_score": message.get("probe_score"),
                "output": output[:500],
            }
        )
    return {
        "object": "smaip.agent_task",
        "status": result.state.get("status"),
        "engine": "mock",
        "gpu": False,
        "instruction": instruction,
        "refusals": list(result.state.get("refusals") or []),
        "sent": list(result.gateway.workspace.sent),
        "files": dict(result.gateway.workspace.files),
        "messages": messages,
        "tool_calls": result.gateway.tool_calls,
        "cost": result.gateway.cost,
    }
