PYTHON ?= python3

.PHONY: week1 week2 week3 week4 week5 week6 week7-cpu week7-gpu install install-gpu test eval serve up deploy down

# Install the scaffold, run the suite, and write the ablation report.
week1: install test eval

# Week 2 gate: install, pytest (includes auth, limits, redaction), and the
# Week 1 ablation thresholds (full-stack utility 1 / ASR 0 / FPR 0; no-defense ASR 1).
week2: install test eval

# Week 3 gate: the Week 2 checks, plus the mock task suite
# (full-stack utility 1 / ASR 0 / FPR 0; no-defense ASR 1).
week3: install test eval
	$(PYTHON) -m smaip.cli week3

# Week 4 gate: the Week 3 checks, the broadened task suite
# (file write, scope refusal, keyword / LP-only / probe-only families),
# and the HTTP smoke in tests/test_week4_smoke.py (collected by `test`).
# Full-stack utility 1 / ASR 0 / FPR 0; no-defense ASR 1; each stub layer
# stops only its own attack family.
week4: install test eval
	$(PYTHON) -m smaip.cli week3
	$(PYTHON) -m smaip.cli week4

# Week 5 gate: the Week 4 checks, plus the indirect-injection suite
# (keyword screen, traces, failure taxonomy, ablation table).
# Pytest includes the skipped `hf` test. CI does not set SMAIP_HF_CPU
# and does not download a model.
week5: install test eval
	$(PYTHON) -m smaip.cli week3
	$(PYTHON) -m smaip.cli week4
	$(PYTHON) -m smaip.cli week5

# Week 6 gate: the Week 5 checks, plus instruction-versus-quote context,
# bounded nested base64, cross-message fragment joins, and the Week 6 suite.
# CPU only. The default engine stays MockEngine. CI does not download a model.
week6: install test eval
	$(PYTHON) -m smaip.cli week3
	$(PYTHON) -m smaip.cli week4
	$(PYTHON) -m smaip.cli week5
	$(PYTHON) -m smaip.cli week6

# Week 7 CPU path: tiny subset. The default model id is the 0.5B instruct
# checkpoint. SMAIP_PROBE_BACKEND=mock skips the download (the CI job).
# Unset that variable, with the hf extra installed, to collect real residuals.
week7-cpu: install
	export SMAIP_PROBE_MODEL="$${SMAIP_PROBE_MODEL:-Qwen/Qwen2.5-0.5B-Instruct}"; \
	export SMAIP_PROBE_SUBSET="$${SMAIP_PROBE_SUBSET:-tiny}"; \
	$(PYTHON) -m smaip.cli week7 --subset tiny --model "$$SMAIP_PROBE_MODEL" && \
	$(PYTHON) -m smaip.cli bench

# Week 7 GPU path: full subset, Qwen2.5-3B-Instruct, then the vLLM comparison.
# The Hugging Face extra is required. The vLLM extra is attempted; if it does
# not install, bench exits 0 and records a skip. The tarball is the artifact
# to copy off the box before teardown.
week7-gpu:
	$(PYTHON) -m pip install -e ".[dev,hf]"
	export SMAIP_PROBE_MODEL="$${SMAIP_PROBE_MODEL:-Qwen/Qwen2.5-3B-Instruct}"; \
	export SMAIP_PROBE_DEVICE=cuda; \
	export SMAIP_PROBE_SUBSET=full; \
	$(PYTHON) -m smaip.cli week7 --subset full --backend hf --device cuda --model "$$SMAIP_PROBE_MODEL" && \
	{ $(PYTHON) -m pip install -e ".[gpu]" || echo "vLLM extra did not install; the benchmark will skip."; } && \
	$(PYTHON) -m smaip.cli bench --model "$$SMAIP_PROBE_MODEL" && \
	mkdir -p reports && \
	tar -czf reports/week7-gpu-results.tar.gz \
		reports/RESULTS_week7.md \
		reports/week7_eval.json \
		reports/week7_bench.json \
		artifacts/probes

install:
	$(PYTHON) -m pip install -e ".[dev]"

install-gpu:
	$(PYTHON) -m pip install -e ".[dev,hf,gpu]"

test:
	$(PYTHON) -m pytest

eval:
	$(PYTHON) -m smaip.cli eval

serve:
	$(PYTHON) -m smaip.cli serve

up deploy:
	docker compose up --build -d

down:
	docker compose down
