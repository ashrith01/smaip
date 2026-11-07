#!/usr/bin/env python3
"""Audit returned V4 binary features against the frozen label-free source."""

import argparse
import hashlib
import json
import math
from pathlib import Path
import re
import struct
import tarfile


SOURCE_SHA256 = 'eb5f57933570e29e8a927a1309c0143d5d32c798c041b11bc8e055eb3c84f443'
BUDGET_SHA256 = '516450afc39e4ff9175863c64230bd58468387b0b015b9092cde4865e3e8154b'
LAYERS = [6, 18, 30]
POOLS = ['content_last', 'content_mean', 'assistant_boundary']
DIM = 2048
ROW_BYTES = len(LAYERS) * len(POOLS) * DIM * 4


def sha(value):
    return hashlib.sha256(value).hexdigest()


def read_archive(path):
    with tarfile.open(path, 'r:gz') as archive:
        members = {}
        for item in archive.getmembers():
            rel = Path(item.name)
            if rel.is_absolute() or '..' in rel.parts or item.issym() or item.islnk():
                raise ValueError('unsafe archive member')
            if item.isfile():
                if item.name in members:
                    raise ValueError('duplicate archive member')
                members[item.name] = archive.extractfile(item).read()
            elif not item.isdir():
                raise ValueError('unsupported archive member')
        return members


def get(members, prefix, name):
    try:
        return members[prefix + '/' + name]
    except KeyError:
        raise ValueError('missing member: ' + name) from None


def archived_collector_hash(checksum_path):
    line = Path(checksum_path).read_text().strip()
    match = re.fullmatch(r'([0-9a-f]{64})  collect_feature_v4\.py', line)
    if match is None:
        raise ValueError('invalid archived collector checksum')
    return match[1]


def analyze(source_path, budget_path, result_path, collector_path=None, *, collector_checksum_path=None):
    if (collector_path is None) == (collector_checksum_path is None):
        raise ValueError('provide one collector source or archived checksum')
    collector_hash = (sha(Path(collector_path).read_bytes()) if collector_path is not None else
                      archived_collector_hash(collector_checksum_path))
    if sha(Path(source_path).read_bytes()) != SOURCE_SHA256 or sha(Path(budget_path).read_bytes()) != BUDGET_SHA256:
        raise ValueError('source or budget archive differs')
    source, budget, result = [read_archive(p) for p in (source_path, budget_path, result_path)]
    sr, br, rr = 'smaip-feature-v4-token-budget-r1', 'token-budget-01', 'feature-collection-01'
    manifest_bytes = get(source, sr, 'bundle-manifest.json')
    manifest = json.loads(manifest_bytes)
    if manifest['kind'] != 'feature-v4-token-budget-source' or manifest['labels_exported'] is not False:
        raise ValueError('source scope differs')
    if {name: sha(get(source, sr, name)) for name in manifest['files']} != manifest['files']:
        raise ValueError('source inventory differs')
    inputs = [json.loads(line) for line in get(source, sr, 'inputs.jsonl').splitlines() if line.strip()]
    budget_summary = json.loads(get(budget, br, 'summary.json'))
    budget_rows = [json.loads(line) for line in get(budget, br, 'token-counts.jsonl').splitlines() if line.strip()]
    if (budget_summary['status'] != 'completed' or len(inputs) != 1012 or len(budget_rows) != 1012 or
            [r['id'] for r in inputs] != [r['id'] for r in budget_rows]):
        raise ValueError('budget/source rows differ')
    by_input = {r['id']: r for r in inputs}
    by_budget = {r['id']: r for r in budget_rows}
    expected_order = sorted(by_input, key=lambda identifier:
        (-by_budget[identifier]['views']['task_boundary']['total_tokens'], identifier))
    inventory = json.loads(get(result, rr, 'files-sha256.json'))
    names = ('model.log', 'protocol.json', 'vectors.f32', 'rows.jsonl', 'summary.json')
    if inventory != {name: sha(get(result, rr, name)) for name in names}:
        raise ValueError('result file inventory differs')
    if set(result) != {rr + '/' + name for name in names + ('files-sha256.json',)}:
        raise ValueError('unexpected result files')
    summary = json.loads(get(result, rr, 'summary.json'))
    protocol = json.loads(get(result, rr, 'protocol.json'))
    if (summary['status'] != 'completed' or summary['kind'] != 'feature-v4-boundary-collection' or
            summary['source_archive_sha256'] != SOURCE_SHA256 or
            summary['token_budget_archive_sha256'] != BUDGET_SHA256 or
            summary['source_manifest_sha256'] != sha(manifest_bytes) or
            summary['collector_sha256'] != collector_hash or
            summary['candidate_corpus_sha256'] != manifest['candidate_corpus_sha256'] or
            any(summary[name] != 1012 for name in ('candidate_count', 'completed_count', 'forwards')) or
            summary['row_bytes'] != ROW_BYTES or summary['vector_bytes'] != ROW_BYTES * 1012 or
            summary['layers'] != LAYERS or summary['pools'] != POOLS or summary['dim'] != DIM or
            summary['max_rendered_tokens'] != max(r['views']['task_boundary']['total_tokens'] for r in budget_rows) or
            summary['training_performed'] is not False or summary['threshold_selected'] is not False or
            summary['detector_quality_measured'] is not False):
        raise ValueError('collection provenance, layout or scope differs')
    saved_protocol = protocol['protocol']
    fingerprint = sha(json.dumps(saved_protocol, sort_keys=True, separators=(',', ':'), allow_nan=False).encode())
    if (protocol['fingerprint'] != fingerprint or summary['protocol_fingerprint'] != fingerprint or
            protocol['source_manifest_sha256'] != sha(manifest_bytes) or
            protocol['token_budget_archive_sha256'] != BUDGET_SHA256 or
            saved_protocol['protocol_version'] != 4 or saved_protocol['max_length'] != 2048 or
            saved_protocol['view'] != 'task-boundary-only' or saved_protocol['layers'] != LAYERS or
            saved_protocol['pools'] != POOLS or
            saved_protocol['model_id'] != manifest['model_id'] or
            saved_protocol['model_revision'] != manifest['model_revision'] or
            saved_protocol['dtype'] != 'float16' or saved_protocol['output_dtype'] != 'little-endian float32' or
            saved_protocol['chat_template_sha256'] != budget_summary['tokenizer_chat_template_sha256']):
        raise ValueError('feature protocol differs')
    metadata = [json.loads(line) for line in get(result, rr, 'rows.jsonl').splitlines() if line.strip()]
    binary = get(result, rr, 'vectors.f32')
    if len(metadata) != 1012 or [r['id'] for r in metadata] != expected_order or len(binary) != ROW_BYTES * 1012:
        raise ValueError('feature rows or binary length differ')
    peak = 0
    for index, row in enumerate(metadata):
        original = by_input[row['id']]
        budget_view = by_budget[row['id']]['views']['task_boundary']
        if (row['source_origin'] != original['source_origin'] or
                row['native_role'] != original['native_role'] or
                row['task_sha256'] != original['task_sha256'] or
                row['text_sha256'] != original['text_sha256'] or
                row['rendered_sha256'] != budget_view['rendered_sha256'] or
                row['total_tokens'] != budget_view['total_tokens'] or
                row['content_tokens'] != budget_view['content_tokens'] or
                row['protocol_fingerprint'] != fingerprint or
                row['boundary_position'] != row['total_tokens'] - 1 or
                row['offset_bytes'] != index * ROW_BYTES or row['length_bytes'] != ROW_BYTES or
                row['last_content_position'] >= row['boundary_position'] or
                'label' in row or 'split_role' in row):
            raise ValueError('row identity/token/protocol differs: ' + row['id'])
        block = binary[index * ROW_BYTES:(index + 1) * ROW_BYTES]
        if sha(block) != row['vector_sha256']:
            raise ValueError('binary vector hash differs: ' + row['id'])
        if not all(math.isfinite(x[0]) for x in struct.iter_unpack('<f', block)):
            raise ValueError('nonfinite float32 vector: ' + row['id'])
        peak = max(peak, row['peak_allocated_gpu_bytes'])
    if summary['peak_allocated_gpu_bytes'] != peak:
        raise ValueError('peak memory differs from per-row trace')
    return {'status': 'verified', 'kind': 'feature-v4-collection-audit',
            'candidate_count': 1012, 'forwards': 1012,
            'source_archive_sha256': SOURCE_SHA256,
            'token_budget_archive_sha256': BUDGET_SHA256,
            'returned_archive_sha256': sha(Path(result_path).read_bytes()),
            'protocol_fingerprint': fingerprint,
            'max_rendered_tokens': summary['max_rendered_tokens'],
            'peak_allocated_gpu_bytes': peak,
            'vector_bytes': len(binary), 'training_performed': False,
            'candidate_reviewed': False,
            'note': 'Verified candidate features, not a fitted or independently evaluated detector.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--budget', type=Path, required=True)
    parser.add_argument('--archive', type=Path, required=True)
    collector = parser.add_mutually_exclusive_group(required=True)
    collector.add_argument('--collector', type=Path)
    collector.add_argument('--collector-checksum', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = analyze(args.source, args.budget, args.archive, args.collector,
                     collector_checksum_path=args.collector_checksum)
    with args.output.open('x') as stream:
        stream.write(json.dumps(result, indent=2, allow_nan=False) + '\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
