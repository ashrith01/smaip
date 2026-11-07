#!/usr/bin/env python3
"""Tokenizer-only budget audit for the unreviewed V4 task/document queue."""

from collections import defaultdict
from contextlib import redirect_stderr, redirect_stdout
import hashlib
import json
import os
from pathlib import Path
import signal
import sys
import tarfile
import time
import traceback


ROOT = Path(__file__).resolve().parents[2]
MODEL = 'Qwen/Qwen2.5-3B-Instruct'
REVISION = 'aa8e72537993ba99e69dfaafa59ed015b17504d1'
BUDGETS = (512, 1024, 2048, 4096)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, obj):
    Path(path).write_text(json.dumps(obj, indent=2, allow_nan=False) + '\n')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def preflight():
    manifest = json.loads((ROOT / 'bundle-manifest.json').read_text())
    require(manifest.get('kind') == 'feature-v4-token-budget-source' and
            manifest.get('model_id') == MODEL and manifest.get('model_revision') == REVISION and
            manifest.get('candidate_reviewed') is False and manifest.get('training_performed') is False,
            'wrong source scope or model')
    for name, expected in manifest['files'].items():
        rel = Path(name)
        require(not rel.is_absolute() and '..' not in rel.parts, 'unsafe source path')
        path = ROOT / rel
        require(path.is_file() and path.resolve().is_relative_to(ROOT.resolve()) and sha(path) == expected,
                'source hash mismatch: ' + name)
    inputs = [json.loads(line) for line in (ROOT / 'inputs.jsonl').read_text().splitlines() if line.strip()]
    require(len(inputs) == 1012 and len({r['id'] for r in inputs}) == 1012 and
            [r['id'] for r in inputs] == manifest['input_ids'], 'candidate identity/count differs')
    for row in inputs:
        require(set(row) == {'id', 'trusted_task', 'untrusted_text', 'source_origin', 'native_role',
                             'task_sha256', 'text_sha256'}, 'unexpected candidate fields')
        require(row['trusted_task'].strip() and row['untrusted_text'].strip(), 'empty candidate input')
        require(hashlib.sha256(row['trusted_task'].encode()).hexdigest() == row['task_sha256'] and
                hashlib.sha256(row['untrusted_text'].encode()).hexdigest() == row['text_sha256'],
                'candidate content hash differs')
    return manifest, inputs


def distribution(values):
    values = sorted(values)
    return {'min': values[0], 'median': values[(len(values) - 1) // 2],
            'p95': values[int(.95 * (len(values) - 1))], 'max': values[-1],
            'above_budget': {str(b): sum(value > b for value in values) for b in BUDGETS}}


def run(output):
    manifest, inputs = preflight()
    sys.path.insert(0, str(ROOT / 'src'))
    os.environ['HF_HUB_OFFLINE'] = '1'
    os.environ['TRANSFORMERS_OFFLINE'] = '1'
    from huggingface_hub import snapshot_download
    from transformers import AutoTokenizer
    from smaip.probes.feature_v3 import render_boundary
    from smaip.probes.feature_v4 import (RENDERING_ID, count_tokens, encode_task_boundary,
                                         render_task_only, token_counts)

    snapshot = snapshot_download(MODEL, revision=REVISION, local_files_only=True)
    tokenizer = AutoTokenizer.from_pretrained(snapshot, local_files_only=True, use_fast=True)
    require(tokenizer.is_fast and isinstance(tokenizer.chat_template, str), 'pinned fast tokenizer unavailable')
    template_sha = hashlib.sha256(tokenizer.chat_template.encode()).hexdigest()
    started = time.monotonic()
    rows, by_source = [], defaultdict(list)
    with (output / 'token-counts.jsonl').open('w') as stream:
        for index, item in enumerate(inputs, 1):
            _, inspection, istart, iend = render_boundary(tokenizer, item['untrusted_text'])
            task_view = encode_task_boundary(tokenizer, item['trusted_task'], item['untrusted_text'])
            task_only_rendered = render_task_only(tokenizer, item['trusted_task'])
            views = {
                'inspection_boundary': count_tokens(tokenizer, inspection, content_span=(istart, iend)),
                'task_boundary': token_counts(task_view),
                'task_only_boundary': count_tokens(tokenizer, task_only_rendered),
            }
            require(views['inspection_boundary']['content_tokens'] > 0 and
                    views['task_boundary']['content_tokens'] > 0, 'tool content has no fully contained tokens')
            row = {'id': item['id'], 'source_origin': item['source_origin'],
                   'native_role': item['native_role'], 'task_sha256': item['task_sha256'],
                   'text_sha256': item['text_sha256'], 'views': views}
            stream.write(json.dumps(row, allow_nan=False) + '\n')
            stream.flush()
            rows.append(row)
            by_source[item['source_origin']].append(row)
            if index % 100 == 0 or index == len(inputs):
                print(f'Tokenized {index}/{len(inputs)}', flush=True)
    def summarize(subset):
        return {name: distribution([r['views'][name]['total_tokens'] for r in subset])
                for name in ('inspection_boundary', 'task_boundary', 'task_only_boundary')}
    return {'status': 'completed', 'kind': 'feature-v4-token-budget',
            'scope': 'unreviewed task-document candidates; tokenizer only',
            'candidate_corpus_sha256': manifest['candidate_corpus_sha256'],
            'source_manifest_sha256': sha(ROOT / 'bundle-manifest.json'),
            'model_id': MODEL, 'model_revision': REVISION,
            'tokenizer_chat_template_sha256': template_sha,
            'rendering_id': RENDERING_ID, 'candidate_count': len(rows),
            'eligible_task_stream_count': len(by_source),
            'by_source_counts': {name: len(group) for name, group in by_source.items()},
            'overall': summarize(rows),
            'by_source': {name: summarize(group) for name, group in by_source.items()},
            'elapsed_seconds': time.monotonic() - started,
            'model_loaded': False, 'training_performed': False,
            'threshold_selected': False, 'detector_quality_measured': False,
            'note': 'Counts are exact for the pinned tokenizer/renderers. Rows are unreviewed; no full-span truncation or dataset fitness is implied.'}


def main():
    output = ROOT / 'reports/v4/token-budget-01'
    archive = output.with_name(output.name + '.tar.gz')
    require(not output.exists() and not archive.exists(), 'preserve existing output; version another run')
    output.mkdir(parents=True)
    def terminate(_signum, _frame):
        raise TimeoutError('token budget audit received termination signal')
    signal.signal(signal.SIGTERM, terminate)
    code = 0
    with (output / 'model.log').open('w') as log, redirect_stdout(log), redirect_stderr(log):
        try:
            summary = run(output)
        except Exception as exc:
            traceback.print_exc()
            summary = {'status': 'failed', 'error': str(exc), 'model_loaded': False,
                       'training_performed': False}
            code = 1
    write(output / 'summary.json', summary)
    write(output / 'files-sha256.json', {p.name: sha(p) for p in sorted(output.iterdir())
                                       if p.is_file() and p.name != 'files-sha256.json'})
    with tarfile.open(archive, 'w:gz') as tar:
        tar.add(output, arcname=output.name)
    print(json.dumps(summary, indent=2))
    print('Evidence archive:', archive)
    return code


if __name__ == '__main__':
    raise SystemExit(main())
