"""OpenAI-compatible Week 1 API.

POST /v1/chat/completions, GET /health, GET /metrics.
The default engine is mock. Nothing in this module downloads weights.
"""

import time
import uuid

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field

from smaip import __version__
from smaip.errors import UnknownEngine
from smaip.serving.cache import ExactPromptCache
from smaip.serving.engines import Engine, engine_for_model
from smaip.serving.metrics import Metrics


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    model: str = "smaip-mock"
    messages: list[ChatMessage] = Field(default_factory=list)
    temperature: float | None = None


def create_app(*, engine: Engine | None = None) -> FastAPI:
    app = FastAPI(title="SMAIP", version=__version__)
    app.state.cache = ExactPromptCache()
    app.state.metrics = Metrics()
    app.state.engine_override = engine

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

    @app.post("/v1/chat/completions")
    def chat(body: ChatRequest) -> dict:
        if not body.messages:
            raise HTTPException(
                status_code=400,
                detail={"message": "messages must not be empty", "type": "invalid_request"},
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
        prompt_tokens = max(1, sum(len(item.content) for item in body.messages) // 4)
        completion_tokens = max(1, len(text) // 4)
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
            "smaip": {"cache": cache_status, "engine": selected.name},
        }

    return app
