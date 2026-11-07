#!/usr/bin/env bash
# Activate the restored GPU environment before starting. No downloads or fitting.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
export PYTHONPATH="$ROOT/src${PYTHONPATH:+:$PYTHONPATH}"
export HF_HUB_OFFLINE=1
export TRANSFORMERS_OFFLINE=1
export CUDA_VISIBLE_DEVICES="${CUDA_VISIBLE_DEVICES:-0}"
SMAIP_PYTHON="${SMAIP_PYTHON:-python}"
SMAIP_PILOT_OUTPUT="${SMAIP_PILOT_OUTPUT:-reports/v3/evidence-clean-03-smoke}"
SMAIP_PILOT_MODE="${SMAIP_PILOT_MODE:-smoke}"
"$SMAIP_PYTHON" - "$SMAIP_PILOT_OUTPUT" <<'PY'
import hashlib, json, sys
from pathlib import Path
root = Path.cwd().resolve()
output = Path(sys.argv[1]).resolve()
if not output.is_relative_to(root / 'reports/v3') or output.exists() or output.with_name(output.name + '.tar.gz').exists():
    raise SystemExit('Choose a fresh output under reports/v3; preserve earlier evidence')
manifest = json.loads((root / 'bundle-manifest.json').read_text())
if manifest['kind'] != 'protocol-7-clean-pilot-source':
    raise SystemExit('Expected the new protocol-7 source bundle')
for name, expected in manifest['files'].items():
    relative = Path(name)
    path = (root / relative).resolve()
    if relative.is_absolute() or '..' in relative.parts or not path.is_relative_to(root) or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
        raise SystemExit('Bundle source mismatch: ' + name)
import torch
if not torch.cuda.is_available():
    raise SystemExit('CUDA required; no mock/CPU fallback')
from huggingface_hub import snapshot_download
from smaip.probes.pipeline_v2 import MODEL, REVISION
snapshot_download(MODEL, revision=REVISION, local_files_only=True)
from lmformatenforcer import JsonSchemaParser
from smaip.agents.evidence_task import SECURE_SCHEMA, role_contract
JsonSchemaParser(SECURE_SCHEMA)
for tools in ({'list_pages', 'read_page'}, {'submit_claims'}, {'send_summary'}):
    JsonSchemaParser(role_contract(tools)[1])
print('Source checks, pinned model cache, CUDA and structured schema verified.')
PY
mkdir -p "$SMAIP_PILOT_OUTPUT"
save_evidence() {
  code=$?
  trap - EXIT
  "$SMAIP_PYTHON" - "$SMAIP_PILOT_OUTPUT" "$code" <<'PY'
import hashlib, json, sys
from pathlib import Path
root = Path(sys.argv[1])
(root / 'job-status.json').write_text(json.dumps({'exit_code': int(sys.argv[2]),
    'status': 'completed' if sys.argv[2] == '0' else 'failed-quality-or-execution',
    'training_performed': False, 'sandbox_only': True}, indent=2) + '\n')
inventory = {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
             for p in sorted(root.rglob('*')) if p.is_file() and p.name != 'files-sha256.json'}
(root / 'files-sha256.json').write_text(json.dumps(inventory, indent=2) + '\n')
PY
  tar -czf "$SMAIP_PILOT_OUTPUT.tar.gz" "$SMAIP_PILOT_OUTPUT"
  printf 'Evidence saved to %s/%s.tar.gz\n' "$ROOT" "$SMAIP_PILOT_OUTPUT"
  exit "$code"
}
trap save_evidence EXIT
nvidia-smi > "$SMAIP_PILOT_OUTPUT/gpu.txt"
"$SMAIP_PYTHON" -m pip freeze > "$SMAIP_PILOT_OUTPUT/packages.txt"
# The Python evaluator owns a fresh child directory; interruption preserves runs.
timeout --signal=TERM 900 "$SMAIP_PYTHON" -u -m smaip.eval.evidence_pilot \
  --mode "$SMAIP_PILOT_MODE" --output "$SMAIP_PILOT_OUTPUT/runs" 2>&1 | tee "$SMAIP_PILOT_OUTPUT/model.log"
