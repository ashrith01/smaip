#!/usr/bin/env python3
"""Build a fresh isolated source bundle; never include external data or weights."""
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tarfile
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from smaip.agents.evidence_task import AGENT_PROTOCOL


def build():
    root = Path(__file__).resolve().parents[1]
    name = 'smaip-task-evidence-pilot-r3'
    destination = root / 'reports' / (name + '.tar.gz')
    if destination.exists():
        raise ValueError('preserve the existing source bundle; version a later build')
    files = [p for p in (root / 'src').rglob('*') if p.is_file() and p.suffix in ('.py', '.json', '.jsonl', '.md')]
    files += [root / p for p in ('pyproject.toml', 'scripts/gpu/run_evidence_pilot.sh', 'scripts/analyze_evidence_pilot.py',
        'docs/brd/EVIDENCE_PILOT_03_SMOKE.md', 'tests/test_evidence_task.py',
        'tests/test_evidence_pilot.py', 'tests/test_corpus_v3.py', 'tests/test_brd_contract.py')]
    inventory = {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(files)}
    manifest = {'kind': f'protocol-{AGENT_PROTOCOL}-clean-pilot-source', 'agent_protocol_version': AGENT_PROTOCOL,
        'base_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip(),
        'source_state': 'local uncommitted implementation; hashes bind exported contents',
        'prefix': name, 'files': inventory, 'external_data_included': False, 'weights_included': False}
    with tarfile.open(destination, 'w:gz') as archive:
        for p in sorted(files):
            info = archive.gettarinfo(str(p), arcname=name + '/' + str(p.relative_to(root)))
            info.mtime, info.uid, info.gid, info.uname, info.gname = 0, 0, 0, '', ''
            with p.open('rb') as stream:
                archive.addfile(info, stream)
        data = (json.dumps(manifest, indent=2) + '\n').encode()
        info = tarfile.TarInfo(name + '/bundle-manifest.json')
        info.size, info.mode = len(data), 0o644
        archive.addfile(info, io.BytesIO(data))
    checksum = hashlib.sha256(destination.read_bytes()).hexdigest()
    destination.with_name(destination.name + '.sha256').write_text(checksum + '  ' + destination.name + '\n')
    print(json.dumps({'bundle': str(destination), 'sha256': checksum, 'files': len(files)}, indent=2))


if __name__ == '__main__':
    build()
