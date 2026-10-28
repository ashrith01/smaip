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
    for target in ("week1:", "week2:", "serve:", "eval:", "deploy:", "down:"):
        assert target in text
    assert "pytest" in text
    assert "docker compose up --build -d" in text
    assert "docker compose down" in text


def test_week2_docs_ci_and_deploy_files():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    for snippet in (
        "make week2",
        "make deploy",
        "make down",
        "SMAIP_API_KEYS",
        "SMAIP_RATE_LIMIT_PER_MINUTE",
        "redact_echo",
        "X-Request-ID",
        "smaip_auth_failures_total",
        "smaip_rate_limited_total",
        "smaip_payload_rejected_total",
        "dev-local-key",
    ):
        assert snippet in readme

    data = (ROOT / "DATA.md").read_text(encoding="utf-8")
    assert "Week 2 does not add datasets" in data

    workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    for snippet in (
        "pull_request:",
        "main",
        "ubuntu-latest",
        'python-version: "3.12"',
        "make week2",
        "docker build",
    ):
        assert snippet in workflow
    assert "secrets:" not in workflow

    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    assert "USER smaip" in dockerfile
    assert "EXPOSE 8000" in dockerfile
    compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    assert '"8000:8000"' in compose or "'8000:8000'" in compose or "8000:8000" in compose
    assert "/health" in compose
    example = (ROOT / ".env.example").read_text(encoding="utf-8")
    assert "SMAIP_API_KEYS=dev-local-key" in example
    assert "SMAIP_REQUIRE_API_KEY=true" in example


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
