#!/usr/bin/env python3
"""Test whether the two V3 prefix mismatches follow sequence length or suffix content."""

from contextlib import redirect_stderr, redirect_stdout
import hashlib
import json
import math
import os
from pathlib import Path
import signal
import sys
import tarfile
import time
import traceback


ROOT = Path(__file__).resolve().parents[2]
SOURCE_SHA256 = '28cab08911171840e1f066c725dd23a788e6a9c64a132ec53bba22a5b3a21f94'
SOURCE_MANIFEST_SHA256 = '422cfe258458507d6d846d3dc4c82505b6a0d751109f46cbac40e4c0b131429e'
PARENT_SHA256 = '850528f73d92d370728e48f0e824751e59e52ecb4bcb1d9ebda2fd7f9a4a6266'
IDS = ('dev01-test-1-05', 'dev01-test-1-06', 'dev01-calibration-0-01')
LAYERS = (6, 18, 30)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, obj):
    Path(path).write_text(json.dumps(obj, indent=2, allow_nan=False) + '\n')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def preflight():
    source = ROOT.parent / 'smaip-feature-v3-smoke-r1.tar.gz'
    parent = ROOT / 'reports/v3/feature-v3-smoke-01.tar.gz'
    require(sha(source) == SOURCE_SHA256, 'original source archive differs')
    require(sha(parent) == PARENT_SHA256, 'original GPU result archive differs')
    manifest_path = ROOT / 'bundle-manifest.json'
    require(sha(manifest_path) == SOURCE_MANIFEST_SHA256, 'source manifest differs')
    manifest = json.loads(manifest_path.read_text())
    for name, expected in manifest['files'].items():
        relative = Path(name)
        require(not relative.is_absolute() and '..' not in relative.parts, 'unsafe source path')
        path = ROOT / relative
        require(path.is_file() and path.resolve().is_relative_to(ROOT.resolve()) and sha(path) == expected,
                'source file differs: ' + name)
    with tarfile.open(parent, 'r:gz') as archive:
        root = 'feature-v3-smoke-01/'
        summary = json.load(archive.extractfile(root + 'summary.json'))
        rows = [json.loads(line) for line in archive.extractfile(root + 'vectors.jsonl').read().splitlines()]
    require(summary['status'] == 'completed' and summary['scientific_smoke_pass'] is False,
            'expected completed nonpassing original smoke')
    require(summary['totals']['prefix_stable'] == 32 and summary['totals']['causal_prefix_above_tolerance'] == 2,
            'original mismatch profile differs')
    by_id = {row['id']: row for row in rows}
    require(len(by_id) == 32 and all(x in by_id for x in IDS), 'target rows missing')
    for name in IDS:
        row = by_id[name]
        base = row['rendering']['baseline']['input_ids']
        boundary = row['rendering']['boundary']['input_ids']
        require(boundary[:len(base)] == base and len(boundary) > len(base), 'prefix/suffix differs')
        require(row['rendering']['prefix_token_ids_stable'] is True, 'original prefix unstable')
    return by_id, summary


def run(output):
    rows, original = preflight()
    sys.path.insert(0, str(ROOT / 'src'))
    os.environ['HF_HUB_OFFLINE'] = '1'
    os.environ['TRANSFORMERS_OFFLINE'] = '1'
    import torch
    from huggingface_hub import snapshot_download
    from smaip.probes.activations import _load_hf

    require(torch.cuda.is_available(), 'CUDA unavailable; no fallback')
    snapshot = snapshot_download('Qwen/Qwen2.5-3B-Instruct',
        revision='aa8e72537993ba99e69dfaafa59ed015b17504d1', local_files_only=True)
    model, tokenizer = _load_hf(snapshot, 'cuda', 'float16')
    require(str(model.dtype) == 'torch.float16', 'model precision changed')
    dummy = tokenizer.encode('control', add_special_tokens=False)[0]
    started = time.monotonic()

    def forward(ids, positions):
        tensor = torch.tensor([ids], device='cuda', dtype=torch.long)
        with torch.inference_mode():
            result = model(input_ids=tensor, attention_mask=torch.ones_like(tensor),
                           output_hidden_states=True, use_cache=False)
        vectors = {}
        for layer in LAYERS:
            content = result.hidden_states[layer + 1][0][positions].float()
            vectors[f'content_last/{layer}'] = content[-1].cpu().tolist()
            vectors[f'content_mean/{layer}'] = content.mean(dim=0).cpu().tolist()
        return vectors

    def compare(a, b):
        comparisons = {}
        for key in a:
            left, right = a[key], b[key]
            require(len(left) == len(right) == 2048 and all(math.isfinite(x) for x in left + right),
                    'invalid comparison vectors')
            maximum = max(abs(x - y) for x, y in zip(left, right))
            scale = max(abs(x) for x in left)
            comparisons[key] = {'max_abs': maximum, 'max_abs_over_vector_scale': maximum / max(scale, 1e-8),
                                'different_coordinates': sum(x != y for x, y in zip(left, right))}
        return comparisons

    outcomes = []
    for name in IDS:
        row = rows[name]
        base_view = row['rendering']['baseline']
        boundary_view = row['rendering']['boundary']
        base_ids, boundary_ids = base_view['input_ids'], boundary_view['input_ids']
        positions = base_view['content_positions']
        require(positions == boundary_view['content_positions'], 'selected content positions changed')
        control_ids = base_ids + [dummy] * (len(boundary_ids) - len(base_ids))
        require(control_ids != boundary_ids and len(control_ids) == len(boundary_ids),
                'control suffix does not differ')
        baseline = forward(base_ids, positions)
        boundary = forward(boundary_ids, positions)
        control = forward(control_ids, positions)
        original_baseline = {f'{pool}/{layer}': row['baseline_features'][pool][str(layer)]
                             for pool in ('content_last', 'content_mean') for layer in LAYERS}
        original_boundary = {f'{pool}/{layer}': row['boundary_features'][pool][str(layer)]
                             for pool in ('content_last', 'content_mean') for layer in LAYERS}
        outcome = {'id': name, 'baseline_tokens': len(base_ids), 'boundary_tokens': len(boundary_ids),
                   'control_tokens': len(control_ids), 'control_suffix_token_id': dummy,
                   'replay_baseline': compare(original_baseline, baseline),
                   'replay_boundary': compare(original_boundary, boundary),
                   'length_change_baseline_vs_boundary': compare(baseline, boundary),
                   'same_length_changed_suffix_boundary_vs_control': compare(boundary, control)}
        outcomes.append(outcome)
        print(name, 'max_same_length=', max(v['max_abs'] for v in outcome['same_length_changed_suffix_boundary_vs_control'].values()),
              'max_length_change=', max(v['max_abs'] for v in outcome['length_change_baseline_vs_boundary'].values()), flush=True)
    write(output / 'comparisons.json', outcomes)
    max_replay = max(v['max_abs'] for row in outcomes for group in ('replay_baseline', 'replay_boundary')
                     for v in row[group].values())
    max_same_length = max(v['max_abs'] for row in outcomes
                          for v in row['same_length_changed_suffix_boundary_vs_control'].values())
    # This diagnostic answers only whether the observed mismatch follows
    # a sequence-length change. It does not make the original smoke pass.
    shape_effect_supported = max_replay <= 0.02 and max_same_length <= 0.02
    return {'status': 'completed', 'kind': 'feature-v3-prefix-diagnostic',
            'original_smoke_scientific_pass': original['scientific_smoke_pass'],
            'source_bundle_sha256': SOURCE_SHA256, 'source_manifest_sha256': SOURCE_MANIFEST_SHA256,
            'parent_archive_sha256': PARENT_SHA256, 'target_ids': IDS, 'layers': LAYERS,
            'forwards': 3 * len(IDS), 'max_replay_abs_difference': max_replay,
            'max_same_length_changed_suffix_abs_difference': max_same_length,
            'shape_effect_supported': shape_effect_supported,
            'model_dtype': str(model.dtype), 'attention_implementation': str(getattr(model.config, '_attn_implementation', None)),
            'elapsed_seconds': time.monotonic() - started,
            'training_performed': False, 'detector_quality_measured': False,
            'note': 'Same-length control changes suffix token IDs, preserving all prefix IDs and total length. This is a numerical causal-prefix diagnostic, not a new detector result.'}


def main():
    output = ROOT / 'reports/v3/feature-v3-prefix-diagnostic-01'
    archive = output.with_name(output.name + '.tar.gz')
    require(not output.exists() and not archive.exists(), 'preserve existing output; choose a new diagnostic version')
    output.mkdir(parents=True)
    def terminate(_signum, _frame):
        raise TimeoutError('diagnostic received termination signal')
    signal.signal(signal.SIGTERM, terminate)
    exit_code = 0
    with (output / 'model.log').open('w') as log, redirect_stdout(log), redirect_stderr(log):
        try:
            result = run(output)
        except Exception as exc:
            traceback.print_exc()
            result = {'status': 'failed', 'error': str(exc), 'training_performed': False}
            exit_code = 1
    write(output / 'summary.json', result)
    write(output / 'files-sha256.json', {p.name: sha(p) for p in sorted(output.iterdir())
                                       if p.is_file() and p.name != 'files-sha256.json'})
    with tarfile.open(archive, 'w:gz') as tar:
        tar.add(output, arcname=output.name)
    print(json.dumps(result, indent=2))
    print('Evidence archive:', archive)
    return exit_code


if __name__ == '__main__':
    raise SystemExit(main())
