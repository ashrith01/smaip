#!/usr/bin/env python3
"""Package a sealed 32-document development-only feature smoke source bundle."""

import hashlib
import io
import json
from pathlib import Path
import subprocess
import tarfile


MODEL = 'Qwen/Qwen2.5-3B-Instruct'
REVISION = 'aa8e72537993ba99e69dfaafa59ed015b17504d1'
NAME = 'smaip-feature-v3-smoke-r1'


def sha_bytes(value):
    return hashlib.sha256(value).hexdigest()


def add_bytes(archive, name, payload):
    info = tarfile.TarInfo(name)
    info.size, info.mode, info.mtime = len(payload), 0o644, 0
    info.uid = info.gid = 0
    info.uname = info.gname = ''
    archive.addfile(info, io.BytesIO(payload))


def build():
    root = Path(__file__).resolve().parents[1]
    destination = root / 'reports' / (NAME + '.tar.gz')
    if destination.exists() or destination.with_name(destination.name + '.sha256').exists():
        raise ValueError('preserve existing bundle; use a new version for changes')
    source = root / 'data/v2/development-01.jsonl'
    corpus = [json.loads(line) for line in source.read_text().splitlines() if line.strip()]
    if len(corpus) != 36 or {r['label'] for r in corpus} != {0, 1}:
        raise ValueError('expected frozen 36-row original development corpus')
    selected = []
    for label in (0, 1):
        rows = [r for r in corpus if r['label'] == label]
        if len(rows) != 18:
            raise ValueError('expected 18 rows per development label')
        rows.sort(key=lambda r: sha_bytes(r['id'].encode()))
        selected.extend(rows[:16])
    selected.sort(key=lambda r: r['id'])
    inputs = [{'id': r['id'], 'text': r['text'], 'text_sha256': sha_bytes(r['text'].encode()),
               'scope': 'assistant-authored-development-smoke'} for r in selected]
    payload = ''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in inputs).encode()
    files = [p for p in (root / 'src').rglob('*.py') if p.is_file()]
    files.append(root / 'scripts/gpu/feature_v3_smoke.py')
    inventory = {str(p.relative_to(root)): sha_bytes(p.read_bytes()) for p in sorted(files)}
    inventory['inputs.jsonl'] = sha_bytes(payload)
    manifest = {'kind': 'feature-v3-development-smoke-source', 'base_commit':
        subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip(),
        'source_state': 'local uncommitted implementation; every exported file is hash-bound',
        'model_id': MODEL, 'model_revision': REVISION, 'development_only': True,
        'original_development_corpus_sha256': sha_bytes(source.read_bytes()),
        'selection': '16 per label, lowest SHA256 of existing ID; labels omitted from exported inputs',
        'input_ids': [r['id'] for r in inputs], 'files': inventory,
        'model_weights_included': False, 'external_data_included': False,
        'training_performed': False}
    manifest_bytes = (json.dumps(manifest, indent=2) + '\n').encode()
    with tarfile.open(destination, 'w:gz') as archive:
        for p in sorted(files):
            relative = str(p.relative_to(root))
            add_bytes(archive, NAME + '/' + relative, p.read_bytes())
        add_bytes(archive, NAME + '/inputs.jsonl', payload)
        add_bytes(archive, NAME + '/bundle-manifest.json', manifest_bytes)
    digest = sha_bytes(destination.read_bytes())
    destination.with_name(destination.name + '.sha256').write_text(digest + '  ' + destination.name + '\n')
    print(json.dumps({'bundle': str(destination), 'sha256': digest, 'files': len(inventory),
                      'documents': len(inputs), 'training_performed': False}, indent=2))


if __name__ == '__main__':
    build()
