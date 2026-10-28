PYTHON ?= python3

.PHONY: week1 install test eval serve

# Install the scaffold, run the suite, and write the ablation report.
week1: install test eval

install:
	$(PYTHON) -m pip install -e ".[dev]"

test:
	$(PYTHON) -m pytest

eval:
	$(PYTHON) -m smaip.cli eval

serve:
	$(PYTHON) -m smaip.cli serve
