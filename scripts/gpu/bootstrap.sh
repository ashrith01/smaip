#!/usr/bin/env bash
# Prepare a fresh Ubuntu GPU box for `make week7-gpu`.
# This script does not create, start, resize, or destroy a cloud instance.
# Create the Vultr instance yourself, SSH in, then run this from a checkout.

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

if ! command -v nvidia-smi >/dev/null 2>&1; then
  echo "nvidia-smi is not on PATH. Install the NVIDIA driver, confirm nvidia-smi works, then rerun." >&2
  exit 1
fi

echo "NVIDIA driver check:"
nvidia-smi

if ! command -v python3 >/dev/null 2>&1; then
  echo "python3 is required." >&2
  exit 1
fi

python3 -m venv .venv
# shellcheck disable=SC1091
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev,hf]"
if ! python -m pip install -e ".[gpu]"; then
  echo "vLLM extra did not install. Collection and training still run. The benchmark will skip."
fi

HF_HOME="${HF_HOME:-$HOME/.cache/huggingface}"
mkdir -p "$HF_HOME"

cat > .venv/smaip-gpu.env <<EOF
HF_HOME=$HF_HOME
HF_HUB_CACHE=$HF_HOME/hub
SMAIP_PROBE_MODEL=\${SMAIP_PROBE_MODEL:-Qwen/Qwen2.5-3B-Instruct}
SMAIP_PROBE_DEVICE=cuda
SMAIP_PROBE_SUBSET=full
SMAIP_PROBE_BACKEND=hf
EOF

echo "Bootstrap finished."
echo "HF cache: $HF_HOME"
echo "Next, from this checkout:"
echo "  source .venv/bin/activate"
echo "  set -a && source .venv/smaip-gpu.env && set +a"
echo "  make week7-gpu"
echo "Copy reports/week7-gpu-results.tar.gz off the box, then destroy the instance."
