"""Auth, body size, and per-key rate limit in front of inference and agent routes.

`/health` and `/metrics` stay open. Keys are accepted only from
`Authorization: Bearer` or `X-API-Key`, never from the query string.
`POST /v1/chat/completions` and `POST /v1/agent/tasks` share one guard.
"""

import hashlib
import hmac
import uuid
from time import time

from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from smaip.serving.access import request_id_from_header

_GUARDED_PATHS = frozenset({"/v1/chat/completions", "/v1/agent/tasks", "/v2/agent/tasks"})
_BODY_METHODS = {"POST", "PUT", "PATCH"}


def fingerprint(secret: str) -> str:
    return hashlib.sha256(secret.encode("utf-8")).hexdigest()[:12]


def extract_api_key(headers) -> str:
    presented = headers.get("x-api-key", "").strip()
    if presented:
        return presented
    authorization = headers.get("authorization", "")
    scheme, _, rest = authorization.partition(" ")
    if scheme.lower() == "bearer":
        return rest.strip()
    return ""


def key_accepted(candidate: str, keys: tuple[str, ...]) -> bool:
    if not candidate or not keys:
        return False
    digest = hashlib.sha256(candidate.encode("utf-8")).digest()
    for key in keys:
        if hmac.compare_digest(digest, hashlib.sha256(key.encode("utf-8")).digest()):
            return True
    return False


def _error(status: int, message: str, error_type: str, request_id: str, extra: dict | None = None):
    headers = {"X-Request-ID": request_id}
    if extra:
        headers.update(extra)
    return JSONResponse(
        status_code=status,
        content={"detail": {"message": message, "type": error_type}},
        headers=headers,
    )


async def _read_limited(receive: Receive, max_bytes: int) -> bytes | None:
    chunks: list[bytes] = []
    total = 0
    while True:
        message = await receive()
        if message["type"] != "http.request":
            break
        piece = message.get("body", b"")
        total += len(piece)
        if total > max_bytes:
            return None
        chunks.append(piece)
        if not message.get("more_body", False):
            break
    return b"".join(chunks)


class InferenceGuard:
    def __init__(self, app: ASGIApp, fastapi_app) -> None:
        self.app = app
        self.fastapi_app = fastapi_app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request = Request(scope, receive)
        header_id = request_id_from_header(request.headers.get("x-request-id"))
        request_id = header_id or uuid.uuid4().hex
        scope.setdefault("state", {})
        scope["state"]["request_id"] = request_id

        async def send_with_id(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                headers.append((b"x-request-id", request_id.encode("ascii")))
                message = {**message, "headers": headers}
            await send(message)

        state = self.fastapi_app.state
        path = scope.get("path", "")
        method = scope.get("method", "GET").upper()
        guarded = method == "POST" and path.rstrip("/") in _GUARDED_PATHS

        if method in _BODY_METHODS:
            content_length = request.headers.get("content-length", "").strip()
            if len(content_length) > 12:
                self._reject_payload(state, request_id, method, path, "content-length")
                response = _error(413, "request body too large", "request_too_large", request_id)
                await response(scope, receive, send)
                return
            if content_length:
                try:
                    declared = int(content_length)
                except ValueError:
                    declared = -1
                if declared > state.settings.max_body_bytes:
                    self._reject_payload(state, request_id, method, path, "content-length")
                    response = _error(413, "request body too large", "request_too_large", request_id)
                    await response(scope, receive, send)
                    return

        if guarded:
            candidate = extract_api_key(request.headers)
            settings = state.settings
            if settings.require_api_key and not key_accepted(candidate, settings.api_keys):
                state.metrics.record_auth_failure()
                state.request_audit.record(
                    {
                        "ts": time(),
                        "event": "auth.rejected",
                        "request_id": request_id,
                        "method": method,
                        "path": path,
                        "status": 401,
                        "key_fp": fingerprint(candidate) if candidate else "missing",
                    }
                )
                response = _error(
                    401,
                    "invalid or missing API key",
                    "auth_error",
                    request_id,
                    {"WWW-Authenticate": 'Bearer realm="smaip"'},
                )
                await response(scope, receive, send)
                return
            bucket = fingerprint(candidate) if candidate else "anonymous"
            if not state.limiter.allow(bucket):
                state.metrics.record_rate_limited()
                state.request_audit.record(
                    {
                        "ts": time(),
                        "event": "rate_limited",
                        "request_id": request_id,
                        "method": method,
                        "path": path,
                        "status": 429,
                        "key_fp": bucket,
                    }
                )
                response = _error(
                    429,
                    "rate limit exceeded",
                    "rate_limit",
                    request_id,
                    {"Retry-After": "60"},
                )
                await response(scope, receive, send)
                return

        if method in _BODY_METHODS:
            body = await _read_limited(receive, state.settings.max_body_bytes)
            if body is None:
                self._reject_payload(state, request_id, method, path, "body")
                response = _error(413, "request body too large", "request_too_large", request_id)
                await response(scope, receive, send)
                return

            sent = False

            async def replay() -> Message:
                nonlocal sent
                if sent:
                    return {"type": "http.request", "body": b"", "more_body": False}
                sent = True
                return {"type": "http.request", "body": body, "more_body": False}

            await self.app(scope, replay, send_with_id)
            return

        await self.app(scope, receive, send_with_id)

    @staticmethod
    def _reject_payload(state, request_id: str, method: str, path: str, reason: str) -> None:
        state.metrics.record_payload_rejected()
        state.request_audit.record(
            {
                "ts": time(),
                "event": "payload.rejected",
                "request_id": request_id,
                "method": method,
                "path": path,
                "status": 413,
                "reason": reason,
            }
        )
