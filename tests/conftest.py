"""Pytest hooks for opt-in tests."""

import os

import pytest


def pytest_collection_modifyitems(config, items):
    if os.environ.get("SMAIP_RUN_HF", "").strip() == "1":
        return
    skip = pytest.mark.skip(
        reason="HF CPU path is opt-in and downloads weights; set SMAIP_RUN_HF=1 to run tests marked hf"
    )
    for item in items:
        if "hf" in item.keywords:
            item.add_marker(skip)
