PYTHON ?= python3

.PHONY: week1 week2 week3 week4 install test eval serve up deploy down

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

install:
	$(PYTHON) -m pip install -e ".[dev]"

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
