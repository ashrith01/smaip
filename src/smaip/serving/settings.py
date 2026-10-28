"""Runtime knobs for the CPU-first API.

Unset `SMAIP_API_KEYS` leaves inference open so the Week 1 localhost curl
keeps working. Setting keys turns auth on unless `SMAIP_REQUIRE_API_KEY`
explicitly disables it.
"""

import os
from collections.abc import Mapping
from dataclasses import dataclass


def _csv(value: str) -> tuple[str, ...]:
    return tuple(part.strip() for part in value.split(",") if part.strip())


def _flag(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _positive_int(name: str, raw: str | None, default: int) -> int:
    if raw is None or raw.strip() == "":
        return default
    try:
        parsed = int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc
    if parsed < 1:
        raise ValueError(f"{name} must be >= 1")
    return parsed


@dataclass(frozen=True)
class ServingSettings:
    api_keys: tuple[str, ...] = ()
    require_api_key: bool = False
    rate_limit_per_minute: int = 60
    max_body_bytes: int = 65_536
    max_message_chars: int = 8_000
    max_messages: int = 32
    log_level: str = "INFO"

    def __post_init__(self) -> None:
        if self.rate_limit_per_minute < 0:
            raise ValueError("rate_limit_per_minute must be >= 0")
        if self.max_body_bytes < 1:
            raise ValueError("max_body_bytes must be >= 1")
        if self.max_message_chars < 1:
            raise ValueError("max_message_chars must be >= 1")
        if self.max_messages < 1:
            raise ValueError("max_messages must be >= 1")

    @classmethod
    def load(cls, environ: Mapping[str, str] | None = None) -> "ServingSettings":
        env = os.environ if environ is None else environ
        keys = _csv(env.get("SMAIP_API_KEYS", ""))
        require_raw = env.get("SMAIP_REQUIRE_API_KEY")
        if require_raw is None or require_raw.strip() == "":
            require = bool(keys)
        else:
            require = _flag(require_raw)
        limit_raw = env.get("SMAIP_RATE_LIMIT_PER_MINUTE")
        if limit_raw is None or limit_raw.strip() == "":
            limit = 60
        else:
            try:
                limit = int(limit_raw)
            except ValueError as exc:
                raise ValueError("SMAIP_RATE_LIMIT_PER_MINUTE must be an integer") from exc
            if limit < 0:
                raise ValueError("SMAIP_RATE_LIMIT_PER_MINUTE must be >= 0")
        level = env.get("SMAIP_LOG_LEVEL", "INFO").strip() or "INFO"
        return cls(
            api_keys=keys,
            require_api_key=require,
            rate_limit_per_minute=limit,
            max_body_bytes=_positive_int(
                "SMAIP_MAX_BODY_BYTES", env.get("SMAIP_MAX_BODY_BYTES"), 65_536
            ),
            max_message_chars=_positive_int(
                "SMAIP_MAX_MESSAGE_CHARS", env.get("SMAIP_MAX_MESSAGE_CHARS"), 8_000
            ),
            max_messages=_positive_int(
                "SMAIP_MAX_MESSAGES", env.get("SMAIP_MAX_MESSAGES"), 32
            ),
            log_level=level.upper(),
        )
