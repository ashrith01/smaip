#!/usr/bin/env python3
"""Seal label-free candidate texts for a tokenizer-only GPU-cache preflight."""

import hashlib
import io
import json
from pathlib import Path
import subprocess
import tarfile


NAME = 'smaip-feature-v4-token-budget-r1'
MODEL = 'Qwen/Qwen2.5-3B-Instruct'
REVISION = 'aa8e72537993ba99e69dfaafa59ed015b17504d1'
CANDIDATE_SHA256 = '842b73014b1fc071cf9a61f1daccdd144be899ebf427970b7c8ea3bc539aec9e'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def add(archive, name, data):
    info = tarfile.TarInfo(name)
    info.size, info.mode, info.mtime = len(data), 0o644, 0
    info.uid = info.gid = 0
    info.uname = info.gname = ''
    archive.addfile(info, io.BytesIO(data))


def build():
    root = Path(__file__).resolve().parents[1]
    destination = root / 'reports' / (NAME + '.tar.gz')
    if destination.exists() or destination.with_name(destination.name + '.sha256').exists():
        raise ValueError('preserve the existing bundle; version later changes')
    corpus = root / '.local-data/corpus-review-01/prepared/candidates.jsonl'
    if sha(corpus.read_bytes()) != CANDIDATE_SHA256:
        raise ValueError('candidate queue differs from pinned source')
    raw = [json.loads(line) for line in corpus.read_text().splitlines() if line.strip()]
    selected = [r for r in raw if r['label_scope'] == 'task-document']
    if len(raw) != 1351 or len(selected) != 1012 or len({r['id'] for r in selected}) != 1012:
        raise ValueError('candidate scope/identity differs')
    if any(r['split_role'] != 'unassigned' for r in selected):
        raise ValueError('unexpected assigned candidate; token preflight should use the original unreviewed queue')
    if {r['source_origin'] for r in selected} != {
            'nvidia/Nemotron-RL-Agentic-Indirect-Prompt-Injection-v1',
            'microsoft/llmail-inject-challenge'}:
        raise ValueError('eligible task streams changed')
    inputs = [{'id': r['id'], 'trusted_task': r['trusted_task'], 'untrusted_text': r['untrusted_text'],
               'source_origin': r['source_origin'], 'native_role': r['native_role'],
               'task_sha256': sha(r['trusted_task'].encode()),
               'text_sha256': sha(r['untrusted_text'].encode())} for r in selected]
    payload = ''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in inputs).encode()
    attribution = (root / '.local-data/corpus-review-01/prepared/ATTRIBUTION.md').read_bytes()
    files = sorted((root / 'src').rglob('*.py')) + [root / 'scripts/gpu/token_budget_v4.py']
    inventory = {str(p.relative_to(root)): sha(p.read_bytes()) for p in sorted(files)}
    inventory['inputs.jsonl'] = sha(payload)
    inventory['ATTRIBUTION.md'] = sha(attribution)
    manifest = {'kind': 'feature-v4-token-budget-source', 'base_commit':
        subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip(),
        'source_state': 'local uncommitted source; exported members hash-bound',
        'model_id': MODEL, 'model_revision': REVISION,
        'candidate_corpus_sha256': CANDIDATE_SHA256,
        'input_ids': [r['id'] for r in inputs], 'files': inventory,
        'candidate_reviewed': False, 'labels_exported': False,
        'model_weights_included': False, 'model_loaded': False,
        'training_performed': False}
    with tarfile.open(destination, 'w:gz') as archive:
        for p in sorted(files):
            add(archive, NAME + '/' + str(p.relative_to(root)), p.read_bytes())
        add(archive, NAME + '/inputs.jsonl', payload)
        add(archive, NAME + '/ATTRIBUTION.md', attribution)
        add(archive, NAME + '/bundle-manifest.json', (json.dumps(manifest, indent=2) + '\n').encode())
    digest = sha(destination.read_bytes())
    destination.with_name(destination.name + '.sha256').write_text(digest + '  ' + destination.name + '\n')
    print(json.dumps({'bundle': str(destination), 'sha256': digest,
                      'files': len(inventory), 'candidates': len(inputs),
                      'labels_exported': False, 'model_loaded': False}, indent=2))


if __name__ == '__main__':
    build()
