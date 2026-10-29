"""Reader specialist.

Lists and reads local vendor fixtures. The return value is a structured
extract plus provenance and taint. The page body stays data: it is not a
task and it is not a plan.
"""

import json

from smaip.fields import extract_fields
from smaip.messages import Taint
from smaip.probes.mock import MockActivationProbe


def list_pages_view(output: str) -> dict:
    """A catalog of filenames. This is a trusted trigger, not page prose."""

    pages = [line for line in output.splitlines() if line]
    return {
        "content": json.dumps({"pages": pages}, sort_keys=True),
        "taint": Taint(),
        "probe_score": None,
        "origin": "tool",
        "trust": "trusted",
    }


def read_page_view(output: str, uri: str | None) -> dict:
    """Untrusted page data. Only allowlisted integers survive in the extract."""

    extracted = extract_fields(output)
    sources = [uri] if uri else []
    return {
        "content": json.dumps({"extract": extracted}, sort_keys=True),
        "taint": Taint(tainted=True, labels=["page"], sources=sources),
        "probe_score": MockActivationProbe().score(output),
        "origin": "page",
        "trust": "untrusted",
    }
