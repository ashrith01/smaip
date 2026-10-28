"""Probe factories. The default is the mock probe."""

from smaip.probes.linear import LinearProbe
from smaip.probes.mock import MockActivationProbe
from smaip.probes.qwen import QwenActivationProbe

__all__ = [
    "LinearProbe",
    "MockActivationProbe",
    "QwenActivationProbe",
    "default_activation_probe",
    "load_activation_probe",
]


def default_activation_probe() -> MockActivationProbe:
    return MockActivationProbe()


def load_activation_probe(name: str = "mock") -> MockActivationProbe:
    if name == "mock":
        return MockActivationProbe()
    if name == "qwen":
        # Construction raises ProbeWeightsUnavailable.
        return QwenActivationProbe()
    raise ValueError(f"unknown activation probe: {name}")
