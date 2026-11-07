#!/usr/bin/env bash
# Run from a recovery checkout with the existing GPU Python environment active.
# No training, package install, instance changes, or base-model download.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
export CUDA_VISIBLE_DEVICES="${CUDA_VISIBLE_DEVICES:-0}"
export SMAIP_PROBE_DEVICE="${SMAIP_PROBE_DEVICE:-cuda}"
export HF_HUB_OFFLINE="${HF_HUB_OFFLINE:-1}"
export PYTHONPATH="$ROOT/src${PYTHONPATH:+:$PYTHONPATH}"
SMAIP_PYTHON="${SMAIP_PYTHON:-python}"
"$SMAIP_PYTHON" -m smaip.cli week7-rescore --device "$SMAIP_PROBE_DEVICE"
tar -czf reports/week7-rescore-results.tar.gz \
  reports/RESULTS_week7_rescore.md reports/week7_rescore.json
printf 'Saved %s/reports/week7-rescore-results.tar.gz\n' "$ROOT"
