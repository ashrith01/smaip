"""Pytest hooks for opt-in tests."""

import os

import pytest


@pytest.fixture(scope="session", autouse=True)
def isolate_probe_artifacts(tmp_path_factory):
    """Point the gateway at an empty probe directory for the suite.

    A checkout that already ran Week 7 has weights under ``artifacts/probes``.
    The published Week 1–6 tests construct a gateway in a few places and expect
    the phrase stubs. ``SMAIP_PROBE_DIR`` already set by the caller is left
    alone. Tests that load weights point the variable at their own directory.
    """

    if os.environ.get("SMAIP_PROBE_DIR"):
        yield
        return
    empty = tmp_path_factory.mktemp("empty-probes")
    os.environ["SMAIP_PROBE_DIR"] = str(empty)
    yield
    os.environ.pop("SMAIP_PROBE_DIR", None)


def pytest_collection_modifyitems(config, items):
    if os.environ.get("SMAIP_RUN_HF", "").strip() == "1":
        return
    skip = pytest.mark.skip(
        reason="HF CPU path is opt-in and downloads weights; set SMAIP_RUN_HF=1 to run tests marked hf"
    )
    for item in items:
        if "hf" in item.keywords:
            item.add_marker(skip)
