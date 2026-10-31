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

# Keep a suitable installed interpreter; Ubuntu 22.04 needs >=3.11 + venv.
as_root() {
  if [[ "$(id -u)" -eq 0 ]]; then "$@"; else sudo "$@"; fi
}
SMAIP_PYTHON="${SMAIP_PYTHON:-python3}"
if ! "$SMAIP_PYTHON" -c 'import sys, venv, ensurepip; assert sys.version_info >= (3, 11)' >/dev/null 2>&1; then
  if command -v python3.11 >/dev/null 2>&1 && python3.11 -c 'import venv, ensurepip' >/dev/null 2>&1; then
    SMAIP_PYTHON=python3.11
  else
    # shellcheck disable=SC1091
    source /etc/os-release
    if [[ "$ID" != ubuntu || "$VERSION_ID" != 22.04 ]]; then
      echo "Install Python >=3.11 with venv, then set SMAIP_PYTHON to its path." >&2
      exit 1
    fi
    as_root apt-get update
    as_root apt-get install -y software-properties-common ca-certificates
    as_root add-apt-repository -y ppa:deadsnakes/ppa
    as_root apt-get update
    as_root apt-get install -y python3.11 python3.11-venv
    SMAIP_PYTHON=python3.11
  fi
fi

"$SMAIP_PYTHON" -m venv .venv
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
CUDA_VISIBLE_DEVICES=${CUDA_VISIBLE_DEVICES:-0}
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
