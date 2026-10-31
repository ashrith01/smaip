#!/usr/bin/env bash
# Reuse the pinned/offline runtime and bundle validation from the pilot.
set -euo pipefail
export SMAIP_PILOT_MODE=development
export SMAIP_PILOT_OUTPUT="${SMAIP_PILOT_OUTPUT:-reports/v2/open-agent-dev-01}"
bash "$(dirname "$0")/open_model_pilot.sh"
