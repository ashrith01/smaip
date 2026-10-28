"""Defense presets used by the gateway and the eval harness.

LP-only is the fixed linear probe. It is a different layer from the mock
activation probe (probe-only) and from the tool gateway (gateway-only).
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Enforcement:
    name: str
    keyword: bool = False
    linear_probe: bool = False
    activation_probe: bool = False
    allowlist: bool = False
    schema: bool = False
    approval: bool = False
    audit: bool = False
    protect_audit_log: bool = False


ABLATION_ORDER: tuple[str, ...] = (
    "no-defense",
    "keyword",
    "LP-only",
    "probe-only",
    "gateway-only",
    "full-stack",
)


def no_defense() -> Enforcement:
    return Enforcement(name="no-defense")


def keyword_only() -> Enforcement:
    return Enforcement(name="keyword", keyword=True)


def lp_only() -> Enforcement:
    return Enforcement(name="LP-only", linear_probe=True)


def probe_only() -> Enforcement:
    return Enforcement(name="probe-only", activation_probe=True)


def gateway_only() -> Enforcement:
    return Enforcement(
        name="gateway-only",
        allowlist=True,
        schema=True,
        approval=True,
        audit=True,
        protect_audit_log=True,
    )


def full_stack() -> Enforcement:
    return Enforcement(
        name="full-stack",
        keyword=True,
        linear_probe=True,
        activation_probe=True,
        allowlist=True,
        schema=True,
        approval=True,
        audit=True,
        protect_audit_log=True,
    )


def presets() -> dict[str, Enforcement]:
    ordered = (
        no_defense(),
        keyword_only(),
        lp_only(),
        probe_only(),
        gateway_only(),
        full_stack(),
    )
    mapping = {item.name: item for item in ordered}
    if tuple(mapping) != ABLATION_ORDER:
        raise RuntimeError("ablation order drifted from the presets")
    return mapping
