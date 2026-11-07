#!/usr/bin/env bash
# Reuse the existing recovery checkout and activated GPU environment.
# Does not train, install packages, download weights, or alter probe files.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
export CUDA_VISIBLE_DEVICES="${CUDA_VISIBLE_DEVICES:-0}"
export HF_HUB_OFFLINE=1
export TRANSFORMERS_OFFLINE=1
export PYTHONPATH="$ROOT/src${PYTHONPATH:+:$PYTHONPATH}"
SMAIP_PYTHON="${SMAIP_PYTHON:-python}"
SMAIP_PARITY_OUTPUT="${SMAIP_PARITY_OUTPUT:-reports/week7-parity}"
SMAIP_PARITY_ARCHIVE="${SMAIP_PARITY_ARCHIVE:-reports/week7-parity-results.tar.gz}"
if [[ -e "$SMAIP_PARITY_OUTPUT" || -e "$SMAIP_PARITY_ARCHIVE" ]]; then
  echo "Parity output already exists. Preserve it; choose new SMAIP_PARITY_OUTPUT and SMAIP_PARITY_ARCHIVE paths for another run." >&2
  exit 1
fi
"$SMAIP_PYTHON" scripts/gpu/probe_parity.py --backend hf --device cuda \
  --artifacts artifacts/probes --subset full --repeats 2 --score-tolerance 0.001 \
  --output "$SMAIP_PARITY_OUTPUT"
tar -czf "$SMAIP_PARITY_ARCHIVE" "$SMAIP_PARITY_OUTPUT"
printf 'Diagnostic completed. Copy back %s/%s\n' "$ROOT" "$SMAIP_PARITY_ARCHIVE"
