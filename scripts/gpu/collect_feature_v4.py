#!/usr/bin/env python3
"""Collect nine boundary-view research features from label-free candidate texts.

This standalone continuation verifies the frozen tokenizer-budget source and
result archives. It changes no file in that bundle and fits no detector.
"""

from contextlib import redirect_stderr, redirect_stdout
import hashlib
from importlib.metadata import version
import json
import math
import os
from pathlib import Path
import signal
import struct
import sys
import tarfile
import time
import traceback


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src'))
SOURCE_ARCHIVE_SHA256 = 'eb5f57933570e29e8a927a1309c0143d5d32c798c041b11bc8e055eb3c84f443'
TOKEN_BUDGET_ARCHIVE_SHA256 = '516450afc39e4ff9175863c64230bd58468387b0b015b9092cde4865e3e8154b'
MODEL = 'Qwen/Qwen2.5-3B-Instruct'
REVISION = 'aa8e72537993ba99e69dfaafa59ed015b17504d1'
DIM = 2048
from smaip.probes.feature_v4 import LAYERS, POOLS, MAX_LENGTH

ROW_FLOATS = len(LAYERS) * len(POOLS) * DIM
ROW_BYTES = ROW_FLOATS * 4
PACK = struct.Struct('<' + str(ROW_FLOATS) + 'f')


def sha_bytes(value):
    return hashlib.sha256(value).hexdigest()


def sha(path):
    return sha_bytes(Path(path).read_bytes())


def write(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def preflight():
    source_archive = ROOT.parent / 'smaip-feature-v4-token-budget-r1.tar.gz'
    budget_archive = ROOT / 'reports/v4/token-budget-01.tar.gz'
    require(sha(source_archive) == SOURCE_ARCHIVE_SHA256, 'original source archive differs')
    require(sha(budget_archive) == TOKEN_BUDGET_ARCHIVE_SHA256, 'token-budget result archive differs')
    manifest_path = ROOT / 'bundle-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    require(manifest['kind'] == 'feature-v4-token-budget-source' and
            manifest['model_id'] == MODEL and manifest['model_revision'] == REVISION and
            manifest['candidate_reviewed'] is False and manifest['labels_exported'] is False,
            'source scope differs')
    for name, expected in manifest['files'].items():
        relative = Path(name)
        require(not relative.is_absolute() and '..' not in relative.parts, 'unsafe source path')
        path = ROOT / relative
        require(path.is_file() and path.resolve().is_relative_to(ROOT.resolve()) and sha(path) == expected,
                'source file differs: ' + name)
    inputs = [json.loads(line) for line in (ROOT / 'inputs.jsonl').read_text().splitlines() if line.strip()]
    require(len(inputs) == 1012 and [r['id'] for r in inputs] == manifest['input_ids'], 'candidate IDs differ')
    with tarfile.open(budget_archive, 'r:gz') as archive:
        prefix = 'token-budget-01/'
        summary = json.load(archive.extractfile(prefix + 'summary.json'))
        counts = [json.loads(line) for line in archive.extractfile(prefix + 'token-counts.jsonl').read().splitlines()]
        inventory = json.load(archive.extractfile(prefix + 'files-sha256.json'))
        for name, expected in inventory.items():
            require(sha_bytes(archive.extractfile(prefix + name).read()) == expected,
                    'token-budget member hash differs: ' + name)
    require(summary['status'] == 'completed' and summary['candidate_count'] == 1012 and
            summary['candidate_corpus_sha256'] == manifest['candidate_corpus_sha256'] and
            summary['model_loaded'] is False and summary['training_performed'] is False and
            len(counts) == 1012 and [r['id'] for r in counts] == manifest['input_ids'],
            'token-budget source/count differs')
    by_id = {r['id']: r for r in inputs}
    budget_by_id = {r['id']: r for r in counts}
    for identifier, item in by_id.items():
        count = budget_by_id[identifier]
        require(item['task_sha256'] == count['task_sha256'] and item['text_sha256'] == count['text_sha256'] and
                count['views']['task_boundary']['total_tokens'] <= MAX_LENGTH and
                count['views']['task_boundary']['content_tokens'] > 0,
                'candidate/budget identity or full-span cap differs: ' + identifier)
    # Longest documents first expose memory or full-span issues before a long
    # collection. The row order is saved explicitly and is not a split role.
    ordered = sorted(inputs, key=lambda r: (-budget_by_id[r['id']]['views']['task_boundary']['total_tokens'], r['id']))
    return manifest_path, manifest, summary, ordered, budget_by_id


def run(output):
    manifest_path, manifest, budget, rows, by_id = preflight()
    os.environ['HF_HUB_OFFLINE'] = '1'
    os.environ['TRANSFORMERS_OFFLINE'] = '1'
    import torch
    from huggingface_hub import snapshot_download
    from transformers import AutoConfig, AutoTokenizer
    from smaip.probes.activations import _load_hf
    from smaip.probes.feature_v4 import (encode_task_boundary, pool_task_boundary,
                                         protocol_fingerprint, protocol_identity, token_counts)

    require(torch.cuda.is_available(), 'CUDA unavailable; no CPU/mock fallback')
    snapshot = snapshot_download(MODEL, revision=REVISION, local_files_only=True)
    tokenizer = AutoTokenizer.from_pretrained(snapshot, local_files_only=True, use_fast=True)
    require(tokenizer.is_fast and isinstance(tokenizer.chat_template, str), 'pinned fast tokenizer unavailable')
    template_sha = sha_bytes(tokenizer.chat_template.encode())
    require(template_sha == budget['tokenizer_chat_template_sha256'], 'tokenizer template changed since budget audit')
    config = AutoConfig.from_pretrained(snapshot, local_files_only=True)
    require(config.num_hidden_layers > max(LAYERS) and config.hidden_size == DIM,
            'pinned model layer/dimension changed')
    protocol = protocol_identity(MODEL, REVISION, template_sha)
    fingerprint = protocol_fingerprint(protocol)
    write(output / 'protocol.json', {'protocol': protocol, 'fingerprint': fingerprint,
                                     'source_manifest_sha256': sha(manifest_path),
                                     'token_budget_archive_sha256': TOKEN_BUDGET_ARCHIVE_SHA256})
    model, _ = _load_hf(snapshot, 'cuda', 'float16')
    require(str(model.dtype) == 'torch.float16', 'model dtype differs')
    torch.cuda.reset_peak_memory_stats()
    started, completed = time.monotonic(), 0
    # A terminal interruption leaves completed rows and their binary blocks
    # intact. The summary remains failed/partial and cannot be used for fit.
    with (output / 'vectors.f32').open('wb') as binary, (output / 'rows.jsonl').open('w') as metadata:
        for index, item in enumerate(rows, 1):
            row_started = time.monotonic()
            view = encode_task_boundary(tokenizer, item['trusted_task'], item['untrusted_text'])
            ids, positions = view['input_ids'], view['content_positions']
            saved = by_id[item['id']]['views']['task_boundary']
            require(token_counts(view) == saved,
                    'candidate tokenizer rendering differs from exact budget: ' + item['id'])
            require(len(ids) <= MAX_LENGTH,
                    'full-span bound or assistant boundary unavailable: ' + item['id'])
            tensor = torch.tensor([ids], dtype=torch.long, device='cuda')
            with torch.inference_mode():
                result = model(input_ids=tensor, attention_mask=torch.ones_like(tensor),
                               output_hidden_states=True, use_cache=False)
            pooled = pool_task_boundary(result.hidden_states, view, LAYERS)
            flat = [value for layer in LAYERS for pool in POOLS for value in pooled[pool][str(layer)]]
            require(len(flat) == ROW_FLOATS and all(math.isfinite(x) for x in flat),
                    'nonfinite or incomplete feature vector: ' + item['id'])
            payload = PACK.pack(*flat)
            require(len(payload) == ROW_BYTES, 'binary vector layout differs')
            offset = binary.tell()
            binary.write(payload)
            binary.flush()
            metadata.write(json.dumps({'id': item['id'], 'source_origin': item['source_origin'],
                'native_role': item['native_role'], 'task_sha256': item['task_sha256'],
                'text_sha256': item['text_sha256'], 'rendered_sha256': saved['rendered_sha256'],
                'protocol_fingerprint': fingerprint, 'total_tokens': len(ids),
                'content_tokens': len(positions), 'last_content_position': positions[-1],
                'boundary_position': len(ids) - 1, 'offset_bytes': offset,
                'length_bytes': ROW_BYTES, 'vector_sha256': sha_bytes(payload),
                'elapsed_seconds': time.monotonic() - row_started,
                'peak_allocated_gpu_bytes': torch.cuda.max_memory_allocated()}, allow_nan=False) + '\n')
            metadata.flush()
            completed += 1
            if index % 25 == 0 or index == len(rows):
                print(f'Collected {index}/{len(rows)}: {item["id"]}, tokens={len(ids)}', flush=True)
    return {'status': 'completed', 'kind': 'feature-v4-boundary-collection',
            'scope': 'forward-only unreviewed candidate research features',
            'source_archive_sha256': SOURCE_ARCHIVE_SHA256,
            'source_manifest_sha256': sha(manifest_path),
            'token_budget_archive_sha256': TOKEN_BUDGET_ARCHIVE_SHA256,
            'candidate_corpus_sha256': manifest['candidate_corpus_sha256'],
            'collector_sha256': sha(Path(__file__).resolve()),
            'protocol_fingerprint': fingerprint, 'candidate_count': len(rows),
            'completed_count': completed, 'forwards': completed,
            'row_bytes': ROW_BYTES, 'vector_bytes': ROW_BYTES * completed,
            'layers': LAYERS, 'pools': POOLS, 'dim': DIM,
            'max_rendered_tokens': max(by_id[r['id']]['views']['task_boundary']['total_tokens'] for r in rows),
            'peak_allocated_gpu_bytes': torch.cuda.max_memory_allocated(),
            'gpu': torch.cuda.get_device_name(0), 'gpu_total_memory_bytes': torch.cuda.get_device_properties(0).total_memory,
            'torch': torch.__version__, 'cuda': torch.version.cuda,
            'transformers': version('transformers'), 'elapsed_seconds': time.monotonic() - started,
            'training_performed': False, 'threshold_selected': False,
            'detector_quality_measured': False,
            'note': 'No labels, review decisions or split roles were exported. Feature collection alone is not a fitted detector.'}


def main():
    output = ROOT / 'reports/v4/feature-collection-01'
    archive = output.with_name(output.name + '.tar.gz')
    require(not output.exists() and not archive.exists(), 'preserve existing output; use a new collection version')
    output.mkdir(parents=True)
    def terminate(_signum, _frame):
        raise TimeoutError('feature collection received termination signal')
    signal.signal(signal.SIGTERM, terminate)
    code = 0
    with (output / 'model.log').open('w') as log, redirect_stdout(log), redirect_stderr(log):
        try:
            summary = run(output)
        except Exception as exc:
            traceback.print_exc()
            summary = {'status': 'failed', 'error': str(exc),
                       'source_archive_sha256': SOURCE_ARCHIVE_SHA256,
                       'token_budget_archive_sha256': TOKEN_BUDGET_ARCHIVE_SHA256,
                       'collector_sha256': sha(Path(__file__).resolve()),
                       'training_performed': False, 'detector_quality_measured': False}
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
