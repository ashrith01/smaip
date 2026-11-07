#!/usr/bin/env bash
# One offline external evaluation job with immutable probes and thresholds.
# Activate the existing GPU Python environment before calling this script.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
export PYTHONPATH="$ROOT/src${PYTHONPATH:+:$PYTHONPATH}"
export HF_HUB_OFFLINE=1
export TRANSFORMERS_OFFLINE=1
export CUDA_VISIBLE_DEVICES="${CUDA_VISIBLE_DEVICES:-0}"
SMAIP_PYTHON="${SMAIP_PYTHON:-python}"
SMAIP_EXTERNAL_OUTPUT="${SMAIP_EXTERNAL_OUTPUT:-reports/v2/external-frozen-01}"
"$SMAIP_PYTHON" - "$SMAIP_EXTERNAL_OUTPUT" <<'PY'
from pathlib import Path
import sys
root = Path.cwd()
output = Path(sys.argv[1]).resolve()
if not output.is_relative_to(root / 'reports/v2'):
    raise SystemExit('Choose an output directory inside reports/v2')
if output.exists() or output.with_name(output.name + '.tar.gz').exists():
    raise SystemExit('Output already exists; preserve it and choose a fresh SMAIP_EXTERNAL_OUTPUT')
PY
mkdir -p "$SMAIP_EXTERNAL_OUTPUT"
save_evidence() {
  code=$?
  trap - EXIT
  "$SMAIP_PYTHON" - "$SMAIP_EXTERNAL_OUTPUT" "$code" <<'PY'
import hashlib, json, sys
from pathlib import Path
root = Path(sys.argv[1])
status = {'exit_code': int(sys.argv[2]), 'status': 'completed' if sys.argv[2] == '0' else 'failed',
          'scope': 'external-pilot',
          'training_performed': False,
          'evaluation_completed': (root / 'evaluation/evaluation.json').exists()}
(root / 'status.json').write_text(json.dumps(status, indent=2) + '\n')
inventory = {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
             for p in sorted(root.rglob('*')) if p.is_file() and p.name != 'files-sha256.json'}
(root / 'files-sha256.json').write_text(json.dumps(inventory, indent=2) + '\n')
print(json.dumps(status, indent=2))
PY
  tar -czf "$SMAIP_EXTERNAL_OUTPUT.tar.gz" "$SMAIP_EXTERNAL_OUTPUT"
  printf 'Evidence saved to %s/%s.tar.gz\n' "$ROOT" "$SMAIP_EXTERNAL_OUTPUT"
  exit "$code"
}
trap save_evidence EXIT
"$SMAIP_PYTHON" - "$SMAIP_EXTERNAL_OUTPUT/bundle-validation.json" <<'PY'
import hashlib, json, sys
from pathlib import Path
root = Path.cwd()
manifest_path = root / 'bundle-manifest.json'
manifest = json.loads(manifest_path.read_text())
if manifest.get('kind') != 'v2-external-frozen-source':
    raise ValueError('Expected the frozen external validation source bundle')
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
nvidia-smi > "$SMAIP_EXTERNAL_OUTPUT/gpu.txt"
"$SMAIP_PYTHON" -m pip freeze > "$SMAIP_EXTERNAL_OUTPUT/packages.txt"
cp -R external-data/prepared "$SMAIP_EXTERNAL_OUTPUT/corpus"
cp -R frozen-probes "$SMAIP_EXTERNAL_OUTPUT/frozen-probes"
"$SMAIP_PYTHON" -u -m smaip.probes.external_v2 evaluate "$SMAIP_EXTERNAL_OUTPUT/corpus" \
  --models "$SMAIP_EXTERNAL_OUTPUT/frozen-probes" --output "$SMAIP_EXTERNAL_OUTPUT/evaluation" \
  2>&1 | tee "$SMAIP_EXTERNAL_OUTPUT/evaluate.log"
