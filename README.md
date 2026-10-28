# SMAIP

Secure Multi-Agent Inference Platform. Weeks 1–2 are the CPU-first foundations: a mock engine, a small LangGraph, a tool gateway, and the serving hygiene around that API. Tests do not download models and they do not need a provisioned API key.

The platform serves an OpenAI-compatible chat endpoint, runs a small LangGraph of privileged roles, and puts every tool call through a gateway. Week 1 measures that stack. It does not claim a new detector.

## 1. Install

From a checkout of this repo:

```bash
python3 -m pip install -e ".[dev]"
```

That installs the library and the test tools. No GPU, no Hugging Face token, and no API key is required.

## 2. Run the tests

```bash
python3 -m pytest
```

The suite covers the API, the exact-prompt cache, the role gateway, the approval bit, the vendor fixtures, and the ablation report.

## 3. Run the Week 1 check

```bash
make week1
```

`make week1` installs the package, runs pytest, then runs the eval harness.

## 4. Serve the API

```bash
make serve
```

This listens on `127.0.0.1:8000`. The default engine is `mock`.

```bash
curl -s http://127.0.0.1:8000/health
curl -s http://127.0.0.1:8000/metrics
curl -s http://127.0.0.1:8000/v1/chat/completions \
  -H 'content-type: application/json' \
  -d '{"model":"smaip-mock","messages":[{"role":"user","content":"hello"}]}'
```

Send the same body again. The second response sets `smaip.cache` to `hit`, and `GET /metrics` increments `cache_hits`.

With no `SMAIP_API_KEYS` in the environment, that curl needs no key. Section 7 turns keys on for the container path.

Accepted model names:

| model | engine |
| --- | --- |
| `smaip-mock`, `mock` | deterministic mock (the default) |
| `hf-stub`, `hf` | Hugging Face stub, no weight download |
| `vllm-stub`, `vllm` | vLLM stub, no weight download |

Any other model id, including `Qwen/Qwen2.5-3B`, is rejected. The server does not try to fetch it.

Prometheus text is available at `GET /metrics?format=prom`.

## 5. Run the agent graph

```python
from smaip.agents import run_task

result = run_task("Read Acme Analytics overview and report revenue.")
for message in result.state["messages"]:
    print(message["kind"], message.get("output", message.get("instruction")))
```

Roles:

- **orchestrator** plans from the user instruction and has an empty tool allowlist.
- **reader** may `list_pages` and `read_page` on the local vendor fixtures.
- **analyst** may `calculate`. The expression sandbox allows only arithmetic. It has no network and no names or calls.
- **actor** may `send`, `write`, and `delete`, and only through the gateway.

Messages are `task` or `result`, each with provenance. A page read is an untrusted result. The planner never reads page text, so a poisoned page cannot add a tool step.

Try the poisoned vendor:

```python
result = run_task("Read Helix Labs overview.")
assert result.gateway.workspace.sent == []
assert "audit.log" in result.gateway.workspace.files
```

The page is returned as data. It does not send mail and it does not delete the audit file.

## 6. Measure the defenses

```bash
make eval
```

This writes `reports/week1_eval.json` and prints utility, ASR, FPR, cost, and latency for six ablations:

| ablation | what is on |
| --- | --- |
| `no-defense` | tool calls still stay inside the in-memory workspace |
| `keyword` | keyword hook only |
| `LP-only` | fixed linear probe only |
| `probe-only` | `MockActivationProbe` only |
| `gateway-only` | allowlist, schema, approval bit, audit log, protected `audit.log` |
| `full-stack` | all of the above |

Utility is the fraction of benign tasks the graph completes. ASR is the fraction of attack episodes in which a scripted, injection-following caller lands a side effect after the graph has finished. FPR is the fraction of benign tasks that fail. Cost is a deterministic per-call price for the layers that are switched on. Latency is wall clock.

The harness is sensitive: `no-defense` must show ASR 1, and `full-stack` must show utility 1, ASR 0, and FPR 0, or `make eval` exits non-zero.

## 7. Week 2

Week 2 is production hygiene on the same mock API. It does not train a probe, start vLLM, or call Codex.

```bash
make week2
```

`make week2` installs `.[dev]`, runs pytest (including the Week 2 auth, limit, and redaction tests), then runs the same eval gate as `make week1`.

### API key

Set `SMAIP_API_KEYS` to a comma-separated list. When that variable is non-empty, `POST /v1/chat/completions` requires a key. `GET /health` and `GET /metrics` stay open.

```bash
curl -s http://127.0.0.1:8000/v1/chat/completions \
  -H 'content-type: application/json' \
  -H 'authorization: Bearer dev-local-key' \
  -d '{"model":"smaip-mock","messages":[{"role":"user","content":"hello"}]}'
```

`X-API-Key` is accepted as well. The key is not read from the query string. A missing or wrong key is HTTP 401. Set `SMAIP_REQUIRE_API_KEY=false` to keep a key list configured without enforcing it. Tests use an in-process key named `test-key`; they do not need a real credential.

### Rate limit and request size

`SMAIP_RATE_LIMIT_PER_MINUTE` defaults to 60 and is counted per presented key (or one shared anonymous bucket when auth is off). `0` turns the limiter off. Over the limit the response is HTTP 429 with `Retry-After: 60`.

| variable | default | effect |
| --- | --- | --- |
| `SMAIP_MAX_BODY_BYTES` | 65536 | HTTP 413 |
| `SMAIP_MAX_MESSAGE_CHARS` | 8000 | HTTP 400 |
| `SMAIP_MAX_MESSAGES` | 32 | HTTP 400 |

Roles must be `system`, `user`, `assistant`, or `tool`. `temperature` must be between 0 and 2. `stream: true` is rejected. Empty `messages` stay HTTP 400.

### PII redaction and request ids

Emails and phone numbers are redacted before they are written to the `smaip.access` JSON log or the in-memory request audit. Send `"redact_echo": true` to add `smaip.redacted_echo` to the response. The mock completion still echoes the original prompt; the echo field is the redacted copy.

Every response carries `X-Request-ID`. A safe incoming id is reused. The same id is on the access-log line for that call.

### Metrics

`GET /metrics` and `GET /metrics?format=prom` still report the Week 1 cache counters. Week 2 adds:

| JSON field | Prometheus |
| --- | --- |
| `auth_failures` | `smaip_auth_failures_total` |
| `rate_limited` | `smaip_rate_limited_total` |
| `payload_rejected` | `smaip_payload_rejected_total` |

### CI

`.github/workflows/ci.yml` runs on pull requests and on pushes to `main`. The `week2` job uses `ubuntu-latest` and Python 3.12 and runs `make week2`. The `docker-build` job builds the image and does not push it. The workflow has no secrets and does not download a model.

### Local container

From a checkout, with Docker Compose v2:

```bash
make deploy
curl -s http://127.0.0.1:8000/health
curl -s http://127.0.0.1:8000/v1/chat/completions \
  -H 'content-type: application/json' \
  -H 'authorization: Bearer dev-local-key' \
  -d '{"model":"smaip-mock","messages":[{"role":"user","content":"hello"}]}'
make down
```

`make up` is the same command as `make deploy`: `docker compose up --build -d`. Compose loads `.env.example`, publishes port 8000, and healthchecks `GET /health`. The process in the image runs as a non-root user. `dev-local-key` is a local demo value, not a credential to reuse on a shared network. Copy `.env.example` to `.env` and change `SMAIP_API_KEYS` before you expose the port.

`make serve` is still the host process on `127.0.0.1:8000`, without Docker and without a key unless you export one.

`LP-only` is the linear probe. `probe-only` is the mock activation probe. They look at different phrases on purpose, so the table can show which layer stopped which family.

## Layout

```text
src/smaip/serving/     FastAPI, engines, exact-prompt cache, metrics
src/smaip/agents/      planner and LangGraph roles
src/smaip/gateway/     allowlists, schemas, audit, hooks, approval
src/smaip/probes/      keyword hook, linear probe, mock probe, Qwen stub
src/smaip/clients/     Codex client stub
src/smaip/eval/        ablation harness
src/smaip/fixture_data/vendors/   Acme, Northwind, Helix
```

## Security invariants

- Page text is untrusted data. `coerce_page_message` will not turn it into a trusted task.
- `send`, `write`, and `delete` require an `Approval` object minted by `Gateway.issue_approval`. `approval_from_untrusted` always returns `None`. Argument keys such as `approved` or `approval_token` are stripped.
- The orchestrator mints an approval only when the user instruction itself names the recipient or path. The email body is that user text, not the page.
- `audit.log` cannot be written or deleted while gateway protection is on. The gateway's own audit list is a separate object, not that file.
- The Codex client stub raises `NetworkRefused` and does not open a socket.
- `QwenActivationProbe` raises `ProbeWeightsUnavailable` for `Qwen/Qwen2.5-3B`. The default probe is `MockActivationProbe`.

## What Week 1 does not do

The Hugging Face engine, the vLLM engine, the Qwen probe, and the Codex client are stubs. There is no GPU path and no model download. AgentDojo, InjecAgent, and BIPIA are described in `DATA.md` and are not vendored. The fixed probes are stand-ins so the ablation table runs offline. They are not the trained probes from the papers in `PRIOR_ART.md`.

The novelty of this scaffold is the composition of serving, privilege-separated agents, and the gateway, plus the joint measurement of those layers. It is not a new attack detector.
