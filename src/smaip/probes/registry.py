"""Load the LP-only and probe-only defenses.

A present artifact replaces the phrase stub. A missing artifact leaves the
stub in place, which is what CI and the Week 1–6 gates run. ``SMAIP_PROBES=stub``
forces the stubs even when files exist. ``SMAIP_PROBE_DIR`` relocates the
directory; the default is ``artifacts/probes`` relative to the working directory.
"""

import os
from pathlib import Path

from smaip.probes.linear import LinearProbe
from smaip.probes.mock import MockActivationProbe
from smaip.probes.trained import TrainedProbe


def probe_dir() -> Path:
    raw = os.environ.get("SMAIP_PROBE_DIR", "").strip()
    if raw:
        return Path(raw)
    return Path("artifacts/probes")


def linear_artifact(directory: Path | None = None) -> Path:
    return (directory or probe_dir()) / "linear.json"


def activation_artifact(directory: Path | None = None) -> Path:
    return (directory or probe_dir()) / "activation.json"


def stubs_forced() -> bool:
    return os.environ.get("SMAIP_PROBES", "").strip().lower() == "stub"


def stub_probes() -> tuple[LinearProbe, MockActivationProbe]:
    return LinearProbe(), MockActivationProbe()


def resolve_probes(probes: tuple | None) -> tuple:
    """Suites pass ``None`` to pin the phrase stubs."""

    if probes is None:
        return stub_probes()
    return probes


def load_linear_defense(directory: Path | None = None):
    if stubs_forced():
        return LinearProbe()
    path = linear_artifact(directory)
    if path.is_file():
        return TrainedProbe.load(path)
    return LinearProbe()


def load_activation_defense(directory: Path | None = None):
    if stubs_forced():
        return MockActivationProbe()
    path = activation_artifact(directory)
    if path.is_file():
        return TrainedProbe.load(path)
    return MockActivationProbe()
