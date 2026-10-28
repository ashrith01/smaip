"""The written deliverables stay pointed at the Week 1 contract."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_readme_is_stepwise():
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    for snippet in (
        'pip install -e ".[dev]"',
        "make week1",
        "make serve",
        "make eval",
        "smaip-mock",
        "MockActivationProbe",
        "Qwen/Qwen2.5-3B",
        "API key",
        "Codex",
    ):
        assert snippet in text


def test_makefile_targets():
    text = (ROOT / "Makefile").read_text(encoding="utf-8")
    for target in ("week1:", "serve:", "eval:"):
        assert target in text
    assert "pytest" in text


def test_data_md_lists_the_benchmarks_and_refuses_to_vendor_them():
    text = (ROOT / "DATA.md").read_text(encoding="utf-8")
    for name in ("AgentDojo", "InjecAgent", "BIPIA"):
        assert name in text
    assert "license" in text.lower()
    assert "Do not vendor" in text
    assert "CC BY-SA" in text


def test_prior_art_cites_the_required_line_and_the_novelty_claim():
    text = (ROOT / "PRIOR_ART.md").read_text(encoding="utf-8")
    for name in (
        "IPI-exposure-signal",
        "AASE",
        "OpenClaw",
        "CaMeL",
        "AgentDojo",
        "Progent",
        "FastAPI",
        "vLLM",
    ):
        assert name in text
    lowered = text.lower()
    assert "composition" in lowered
    assert "joint measurement" in lowered
