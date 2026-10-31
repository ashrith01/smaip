#!/usr/bin/env bash
# Manual pre-destruction backup. Creates files only; never stops/destroys anything.
set -euo pipefail
umask 077

SMAIP_BACKUP_ROOT="${SMAIP_BACKUP_ROOT:-/root}"
SMAIP_BACKUP_NAME="${SMAIP_BACKUP_NAME:-smaip-preserve-2026-10-31}"
SMAIP_BACKUP_PYTHON="${SMAIP_BACKUP_PYTHON:-$SMAIP_BACKUP_ROOT/smaip/.venv/bin/python}"
case "$SMAIP_BACKUP_NAME" in
  smaip-preserve-*) ;;
  *) echo 'Backup name must begin with smaip-preserve-.' >&2; exit 1 ;;
esac
if [[ "$SMAIP_BACKUP_NAME" == */* ]]; then
  echo 'Use a simple backup name without slashes.' >&2
  exit 1
fi
cd "$SMAIP_BACKUP_ROOT"
if [[ -e "$SMAIP_BACKUP_NAME" || -e "$SMAIP_BACKUP_NAME.tar.gz" || -e "$SMAIP_BACKUP_NAME.tar.gz.sha256" ]]; then
  echo 'Backup already exists. Preserve it; choose a fresh SMAIP_BACKUP_NAME.' >&2
  exit 1
fi
test -x "$SMAIP_BACKUP_PYTHON"
projects=()
for project in smaip smaip-week7-recovery smaip-open-model-v2 smaip-open-model-v2-r2 smaip-open-model-v2-r3 smaip-open-model-v2-r4; do
  if [[ -d "$project" && ! -L "$project" ]]; then
    projects+=("$project")
  fi
done
if [[ ${#projects[@]} == 0 ]]; then
  echo 'No expected SMAIP project directories found; nothing was backed up.' >&2
  exit 1
fi
mkdir "$SMAIP_BACKUP_NAME"
printf '%s\n' "${projects[@]}" > "$SMAIP_BACKUP_NAME/project-directories.txt"
"$SMAIP_BACKUP_PYTHON" - "$SMAIP_BACKUP_NAME/environment.json" <<'PY'
from importlib import metadata
import json, platform, sys
from pathlib import Path
packages = sorted(({'name': dist.metadata['Name'], 'version': dist.version}
                   for dist in metadata.distributions()), key=lambda item: item['name'].lower())
Path(sys.argv[1]).write_text(json.dumps({
    'python_executable': sys.executable, 'python': sys.version,
    'platform': platform.platform(), 'packages': packages,
    'model_id': 'Qwen/Qwen2.5-3B-Instruct',
    'model_revision': 'aa8e72537993ba99e69dfaafa59ed015b17504d1',
    'known_model_cache': '/root/.cache/huggingface/hub',
    'note': 'Project archive excludes virtual environments and caches. Retain a completed disk snapshot to preserve those.',
}, indent=2) + '\n')
PY
uname -a > "$SMAIP_BACKUP_NAME/os.txt"
if [[ -f /etc/os-release ]]; then
  cp /etc/os-release "$SMAIP_BACKUP_NAME/os-release.txt"
fi
if command -v nvidia-smi >/dev/null 2>&1; then
  nvidia-smi > "$SMAIP_BACKUP_NAME/nvidia-smi.txt"
fi
tar \
  --exclude='.venv' --exclude='venv' --exclude='.git' \
  --exclude='__pycache__' --exclude='.pytest_cache' --exclude='.cache' \
  --exclude='node_modules' --exclude='.env' --exclude='.env.*' \
  -czf "$SMAIP_BACKUP_NAME.tar.gz" "${projects[@]}" "$SMAIP_BACKUP_NAME"
tar -tzf "$SMAIP_BACKUP_NAME.tar.gz" >/dev/null
if command -v sha256sum >/dev/null 2>&1; then
  sha256sum "$SMAIP_BACKUP_NAME.tar.gz" > "$SMAIP_BACKUP_NAME.tar.gz.sha256"
else
  shasum -a 256 "$SMAIP_BACKUP_NAME.tar.gz" > "$SMAIP_BACKUP_NAME.tar.gz.sha256"
fi
cat "$SMAIP_BACKUP_NAME.tar.gz.sha256"
sync
printf 'Archive created and integrity check passed: %s/%s.tar.gz\n' "$SMAIP_BACKUP_ROOT" "$SMAIP_BACKUP_NAME"
printf 'Download both archive and checksum; verify on your Mac. Then create and retain a completed Vultr snapshot before destroying the instance.\n'
