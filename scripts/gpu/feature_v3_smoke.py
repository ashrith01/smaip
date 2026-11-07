#!/usr/bin/env python3
"""Offline 32-document, forward-only feature rendering smoke on the pinned GPU."""

import argparse
from contextlib import redirect_stderr, redirect_stdout
import hashlib
from importlib.metadata import version
import json
import math
import os
from pathlib import Path
import platform
import signal
import sys
import tarfile
import time
import traceback


MODEL = 'Qwen/Qwen2.5-3B-Instruct'
REVISION = 'aa8e72537993ba99e69dfaafa59ed015b17504d1'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def check(condition, message):
    if not condition:
        raise ValueError(message)


def verify_bundle(root):
    manifest_path = root / 'bundle-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    check(manifest.get('kind') == 'feature-v3-development-smoke-source', 'wrong source bundle')
    check(manifest.get('model_id') == MODEL and manifest.get('model_revision') == REVISION,
          'different pinned model')
    check(manifest.get('development_only') is True and len(manifest['input_ids']) == 32,
          'unexpected input scope')
    for name, expected in manifest['files'].items():
        relative = Path(name)
        check(not relative.is_absolute() and '..' not in relative.parts, 'invalid source path')
        path = root / relative
        check(path.resolve().is_relative_to(root.resolve()) and path.is_file(), 'source path escapes bundle')
        check(sha(path) == expected, 'source hash mismatch: ' + name)
    rows = [json.loads(line) for line in (root / 'inputs.jsonl').read_text().splitlines() if line.strip()]
    check(len(rows) == 32 and [r['id'] for r in rows] == manifest['input_ids'], 'input identities differ')
    check(len({r['id'] for r in rows}) == 32 and len({r['text_sha256'] for r in rows}) == 32,
          'duplicate smoke inputs')
    for row in rows:
        check(set(row) == {'id', 'text', 'text_sha256', 'scope'}, 'unexpected input fields')
        check(row['scope'] == 'assistant-authored-development-smoke' and row['text'].strip(),
              'wrong document scope')
        check(hashlib.sha256(row['text'].encode()).hexdigest() == row['text_sha256'],
              'input text hash differs')
    return manifest, rows


def run(root, output):
    manifest, rows = verify_bundle(root)
    sys.path.insert(0, str(root / 'src'))
    os.environ['HF_HUB_OFFLINE'] = '1'
    os.environ['TRANSFORMERS_OFFLINE'] = '1'
    os.environ.setdefault('CUDA_VISIBLE_DEVICES', '0')
    import torch
    from huggingface_hub import snapshot_download
    from transformers import AutoConfig, AutoTokenizer
    from smaip.probes.activations import _load_hf
    from smaip.probes.feature_v3 import FeatureProtocolV3, LAYERS, encode_views, pooled_vectors

    check(torch.cuda.is_available(), 'CUDA unavailable; no CPU or mock fallback')
    snapshot = snapshot_download(MODEL, revision=REVISION, local_files_only=True)
    tokenizer = AutoTokenizer.from_pretrained(snapshot, local_files_only=True, use_fast=True)
    check(isinstance(tokenizer.chat_template, str), 'explicit chat template required')
    config = AutoConfig.from_pretrained(snapshot, local_files_only=True)
    check(max(LAYERS) < config.num_hidden_layers, 'selected layer outside pinned model')
    protocol = FeatureProtocolV3(MODEL, REVISION, REVISION,
        hashlib.sha256(tokenizer.chat_template.encode()).hexdigest())
    model, _ = _load_hf(snapshot, 'cuda', protocol.dtype)
    check(str(model.dtype) == 'torch.float16', 'model dtype differs from protocol')
    write_json(output / 'protocol.json', {'protocol': protocol.as_dict(),
        'protocol_fingerprint': protocol.fingerprint, 'layers': LAYERS,
        'source_manifest_sha256': sha(root / 'bundle-manifest.json')})

    comparisons, repeatability, totals = [], {}, {'forwards': 0, 'prefix_stable': 0,
        'prefix_unstable': 0, 'causal_prefix_checked': 0, 'causal_prefix_above_tolerance': 0}
    torch.cuda.reset_peak_memory_stats()
    started = time.monotonic()
    def forward(view):
        inputs = {key: torch.tensor([view[key]], device='cuda', dtype=torch.long)
                  for key in ('input_ids', 'attention_mask')}
        with torch.inference_mode():
            result = model(**inputs, output_hidden_states=True, use_cache=False)
        totals['forwards'] += 1
        return pooled_vectors(result.hidden_states, view, LAYERS)

    with (output / 'vectors.jsonl').open('w') as stream:
        for index, row in enumerate(rows, 1):
            encoded = encode_views(tokenizer, row['text'], protocol)
            baseline = forward(encoded['baseline'])
            boundary = forward(encoded['boundary'])
            stable = encoded['prefix_token_ids_stable']
            totals['prefix_stable' if stable else 'prefix_unstable'] += 1
            if stable:
                totals['causal_prefix_checked'] += 1
                # A suffix cannot change preceding causal states when token IDs
                # agree. Allow fp16 kernel variation, but record exact max error.
                maximum = max(abs(a - b) for pool in ('content_last', 'content_mean')
                              for layer in LAYERS
                              for a, b in zip(baseline[pool][str(layer)], boundary[pool][str(layer)]))
                if maximum > 0.02:
                    totals['causal_prefix_above_tolerance'] += 1
            else:
                maximum = None
            comparisons.append({'id': row['id'], 'prefix_token_ids_stable': stable,
                                'content_pool_max_abs_difference': maximum})
            if index == 1:
                again = forward(encoded['boundary'])
                for pool in ('content_last', 'content_mean', 'assistant_boundary'):
                    for layer in LAYERS:
                        key = f'{pool}/{layer}'
                        diff = max(abs(a - b) for a, b in zip(boundary[pool][str(layer)], again[pool][str(layer)]))
                        repeatability[key] = diff
            for view in (baseline, boundary):
                for pool in view:
                    for layer in LAYERS:
                        vector = view[pool][str(layer)]
                        check(len(vector) == config.hidden_size and all(math.isfinite(v) for v in vector),
                              f'nonfinite/dimension mismatch {row["id"]} {pool}/{layer}')
            feature_row = {'id': row['id'], 'text_sha256': row['text_sha256'],
                'protocol_fingerprint': protocol.fingerprint,
                'rendering': {'content_char_span': encoded['content_char_span'],
                    'prefix_token_ids_stable': stable,
                    'baseline': {key: value for key, value in encoded['baseline'].items() if key != 'attention_mask'},
                    'boundary': {key: value for key, value in encoded['boundary'].items() if key != 'attention_mask'}},
                'baseline_features': {key: baseline[key] for key in ('content_last', 'content_mean')},
                'boundary_features': boundary}
            stream.write(json.dumps(feature_row, allow_nan=False) + '\n')
            stream.flush()
            print(f'{index}/32 {row["id"]}: base={encoded["baseline"]["token_count"]} '
                  f'boundary={encoded["boundary"]["token_count"]} prefix_stable={stable}', flush=True)
    elapsed = time.monotonic() - started
    write_json(output / 'comparisons.json', comparisons)
    write_json(output / 'runtime.json', {'python': platform.python_version(),
        'torch': torch.__version__, 'cuda': torch.version.cuda,
        'transformers': version('transformers'), 'tokenizers': version('tokenizers'),
        'huggingface_hub': version('huggingface-hub'), 'gpu': torch.cuda.get_device_name(0),
        'model_dtype': str(model.dtype), 'peak_allocated_gpu_bytes': torch.cuda.max_memory_allocated(),
        'elapsed_seconds': elapsed, 'forwards': totals['forwards']})
    scientific_pass = (totals['prefix_stable'] == 32 and
                       totals['causal_prefix_above_tolerance'] == 0 and
                       all(v <= 0.02 for v in repeatability.values()))
    return {'status': 'completed', 'kind': 'feature-v3-development-smoke', 'scope': '32 original development documents',
            'source_manifest_sha256': sha(root / 'bundle-manifest.json'),
            'protocol_fingerprint': protocol.fingerprint, 'documents': len(rows),
            'layers': LAYERS, 'hidden_size': config.hidden_size, 'totals': totals,
            'repeatability_max_abs_difference': repeatability,
            'repeatability_above_tolerance': any(v > 0.02 for v in repeatability.values()),
            'scientific_smoke_pass': scientific_pass,
            'training_performed': False, 'threshold_selected': False,
            'detector_quality_measured': False,
            'note': 'Forward-only rendering check. Prefix variation is reported, not silently repaired.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--checkout', type=Path, default=Path.cwd())
    parser.add_argument('--output', type=Path, default=Path('reports/v3/feature-v3-smoke-01'))
    args = parser.parse_args()
    root = args.checkout.resolve()
    output = (args.output if args.output.is_absolute() else root / args.output).resolve()
    check(output.is_relative_to(root / 'reports/v3'), 'output must be inside reports/v3')
    archive = output.with_name(output.name + '.tar.gz')
    check(not output.exists() and not archive.exists(), 'preserve existing output; choose a fresh path')
    output.mkdir(parents=True)
    exit_code = 0
    def terminate(_signum, _frame):
        raise TimeoutError('feature smoke received termination signal')
    signal.signal(signal.SIGTERM, terminate)
    with (output / 'model.log').open('w') as log, redirect_stdout(log), redirect_stderr(log):
        try:
            result = run(root, output)
        except Exception as exc:
            traceback.print_exc()
            result = {'status': 'failed', 'error': str(exc), 'training_performed': False,
                      'detector_quality_measured': False}
            exit_code = 1
    write_json(output / 'summary.json', result)
    inventory = {p.name: sha(p) for p in sorted(output.iterdir()) if p.is_file() and p.name != 'files-sha256.json'}
    write_json(output / 'files-sha256.json', inventory)
    with tarfile.open(archive, 'w:gz') as tar:
        tar.add(output, arcname=output.name)
    print(json.dumps(result, indent=2))
    print('Evidence archive:', archive)
    if exit_code == 0 and not result['scientific_smoke_pass']:
        return 2
    return exit_code


if __name__ == '__main__':
    raise SystemExit(main())
