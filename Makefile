PYTHON ?= python3

.PHONY: week1 week2 install test eval serve up deploy down

# Install the scaffold, run the suite, and write the ablation report.
week1: install test eval

# Week 2 gate: install, pytest (includes auth, limits, redaction), and the
# Week 1 ablation thresholds (full-stack utility 1 / ASR 0 / FPR 0; no-defense ASR 1).
week2: install test eval

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
