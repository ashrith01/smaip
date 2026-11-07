#!/usr/bin/env bash
# One offline development collection -> fit -> frozen evaluation job.
# Activate the existing GPU Python environment before calling this script.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
export PYTHONPATH="$ROOT/src${PYTHONPATH:+:$PYTHONPATH}"
export HF_HUB_OFFLINE=1
export TRANSFORMERS_OFFLINE=1
export CUDA_VISIBLE_DEVICES="${CUDA_VISIBLE_DEVICES:-0}"
SMAIP_PYTHON="${SMAIP_PYTHON:-python}"
SMAIP_V2_OUTPUT="${SMAIP_V2_OUTPUT:-reports/v2/probe-development-01}"
"$SMAIP_PYTHON" - "$SMAIP_V2_OUTPUT" <<'PY'
from pathlib import Path
import sys
root = Path.cwd()
output = Path(sys.argv[1]).resolve()
if not output.is_relative_to(root / 'reports/v2'):
    raise SystemExit('Choose an output directory inside reports/v2')
if output.exists() or output.with_name(output.name + '.tar.gz').exists():
    raise SystemExit('Output already exists; preserve it and choose a fresh SMAIP_V2_OUTPUT')
PY
mkdir -p "$SMAIP_V2_OUTPUT"
save_evidence() {
  code=$?
  trap - EXIT
  "$SMAIP_PYTHON" - "$SMAIP_V2_OUTPUT" "$code" <<'PY'
import hashlib, json, sys
from pathlib import Path
root = Path(sys.argv[1])
status = {'exit_code': int(sys.argv[2]), 'status': 'completed' if sys.argv[2] == '0' else 'failed',
          'scope': 'development-only',
          'fit_completed': (root / 'probes/fit.json').exists(),
          'evaluation_completed': (root / 'evaluation/evaluation.json').exists()}
(root / 'status.json').write_text(json.dumps(status, indent=2) + '\n')
inventory = {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
             for p in sorted(root.rglob('*')) if p.is_file() and p.name != 'files-sha256.json'}
(root / 'files-sha256.json').write_text(json.dumps(inventory, indent=2) + '\n')
print(json.dumps(status, indent=2))
PY
  tar -czf "$SMAIP_V2_OUTPUT.tar.gz" "$SMAIP_V2_OUTPUT"
  printf 'Evidence saved to %s/%s.tar.gz\n' "$ROOT" "$SMAIP_V2_OUTPUT"
  exit "$code"
}
trap save_evidence EXIT
"$SMAIP_PYTHON" - "$SMAIP_V2_OUTPUT/bundle-validation.json" <<'PY'
import hashlib, json, sys
from pathlib import Path
root = Path.cwd()
manifest_path = root / 'bundle-manifest.json'
manifest = json.loads(manifest_path.read_text())
if manifest.get('kind') != 'v2-development-training-source':
    raise ValueError('Expected the V2 development training source bundle')
for name, expected in manifest['files'].items():
    relative = Path(name)
    if relative.is_absolute() or '..' in relative.parts or not (root / relative).resolve().is_relative_to(root):
        raise ValueError('Invalid bundle path')
    if hashlib.sha256((root / relative).read_bytes()).hexdigest() != expected:
        raise ValueError('Source mismatch: ' + name)
Path(sys.argv[1]).write_text(json.dumps({
    'base_commit': manifest['base_commit'], 'source_state': manifest['source_state'],
    'manifest_sha256': hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
    'files_verified': len(manifest['files']),
}, indent=2) + '\n')
PY
nvidia-smi > "$SMAIP_V2_OUTPUT/gpu.txt"
"$SMAIP_PYTHON" -m pip freeze > "$SMAIP_V2_OUTPUT/packages.txt"
"$SMAIP_PYTHON" -u -m smaip.probes.pipeline_v2 collect data/v2/development-01.jsonl \
  --provenance data/v2/development-01.provenance.json --layer 18 \
  --output "$SMAIP_V2_OUTPUT/collection" 2>&1 | tee "$SMAIP_V2_OUTPUT/collect.log"
"$SMAIP_PYTHON" -u -m smaip.probes.pipeline_v2 fit "$SMAIP_V2_OUTPUT/collection" \
  --output "$SMAIP_V2_OUTPUT/probes" 2>&1 | tee "$SMAIP_V2_OUTPUT/fit.log"
"$SMAIP_PYTHON" -u -m smaip.probes.pipeline_v2 evaluate "$SMAIP_V2_OUTPUT/collection" \
  --models "$SMAIP_V2_OUTPUT/probes" --output "$SMAIP_V2_OUTPUT/evaluation" \
  2>&1 | tee "$SMAIP_V2_OUTPUT/evaluate.log"
